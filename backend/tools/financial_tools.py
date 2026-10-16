"""
LangChain @tool wrappers around yfinance for Indian stock data.
All functions handle .NS suffix automatically.
All returns are JSON-serializable dicts (no pandas objects).
All external calls use cache and handle errors gracefully.

Fallback chain: yfinance → scraper → disk snapshot
"""
import logging
import time
from typing import Optional
from datetime import datetime, timedelta
import yfinance as yf
import numpy as np
from langchain.tools import tool
from backend.utils.cache import cache_get, cache_set
from backend.utils.yfinance_disk_cache import get_cached_data, set_cached_data
from backend.utils.validators import normalize_ticker, add_ns_suffix

logger = logging.getLogger(__name__)

# Note: Custom curl_cffi session removed - vanilla yfinance works reliably
# The custom session was causing "'str' object has no attribute 'name'" errors


def _retry_with_backoff(func, max_retries=3, initial_delay=5.0):
    """
    Retry a function with exponential backoff for transient errors.

    Args:
        func: Callable to retry
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 5.0)

    Returns:
        Function result if successful

    Raises:
        Last exception if all retries fail
    """
    last_exception = None
    # Backoff schedule: 5s, 15s, 45s
    delays = [5.0, 15.0, 45.0]

    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_exception = e
            error_msg = str(e).lower()

            # Check if it's a rate limit error
            if "rate limit" in error_msg or "too many requests" in error_msg or "429" in error_msg:
                if attempt < max_retries - 1:
                    delay = delays[attempt]
                    logger.warning(f"Rate limit hit, retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"Rate limit persists after {max_retries} attempts")

            # For non-rate-limit errors, don't retry
            raise

    # If we exhausted all retries
    raise last_exception


def _ensure_ns(ticker: str) -> str:
    """
    Add .NS suffix if not already present.
    Handles plain tickers, .NS, and .BO suffixes.
    """
    try:
        return add_ns_suffix(ticker)
    except ValueError:
        # If validation fails, try to normalize and add suffix anyway
        ticker_clean = ticker.strip().upper()
        if not ticker_clean.endswith(".NS") and not ticker_clean.endswith(".BO"):
            return ticker_clean + ".NS"
        return ticker_clean


def _fetch_from_scraper_fallback(ticker: str) -> Optional[dict]:
    """
    Fallback to india_financials.get_financials when yfinance fails.

    Args:
        ticker: Stock ticker (e.g., "RELIANCE.NS")

    Returns:
        Stock info dict or None if failed
    """
    try:
        from backend.scraper.india_financials import get_financials

        logger.info(f"Fetching from india_financials for {ticker}")

        # Extract base ticker (remove .NS/.BO suffix)
        base_ticker = ticker.replace(".NS", "").replace(".BO", "")

        scraper_data = get_financials(base_ticker, source="screener")

        if not scraper_data.get("tables"):
            logger.warning(f"india_financials returned no tables for {ticker}")
            return None

        tables = scraper_data.get("tables", {})
        currency = scraper_data.get("currency", "INR")

        result = {
            "ticker": ticker,
            "company_name": scraper_data.get("company", ""),
            "sector": "",  # Try to extract from company_info if available
            "currency": currency,
            "source": "india_financials",
            "as_of": scraper_data.get("fetched_at"),
        }

        # Parse ratios from Screener ratios table if available
        ratios_table = tables.get("S_Ratios")
        if ratios_table:
            result.update(_parse_screener_ratios(ratios_table))

        # Parse quarterly results for current price and market cap
        quarterly_table = tables.get("S_Quarterly_Results")
        if quarterly_table:
            # Try to extract market cap and current price from quarterly data
            rows = {row.get("Item", ""): row for row in quarterly_table}

            def get_latest_value(item_name):
                row = rows.get(item_name)
                if not row:
                    return None
                cols = [k for k in row.keys() if k != "Item"]
                if not cols:
                    return None
                latest_col = cols[-1]
                val = row.get(latest_col)
                if val and val != "-":
                    try:
                        return float(str(val).replace(",", ""))
                    except:
                        return None
                return None

            # Market cap is often in the quarterly results
            market_cap = get_latest_value("Market Cap")
            if market_cap:
                result["market_cap_cr"] = round(market_cap, 1)

        return result

    except Exception as e:
        logger.warning(f"india_financials fallback failed for {ticker}: {e}")
        return None


def _fetch_from_snapshot_fallback(ticker: str) -> Optional[dict]:
    """
    Fallback to disk snapshot as last resort.

    Args:
        ticker: Stock ticker

    Returns:
        Stock info dict or None if not found
    """
    try:
        from backend.scraper.snapshot_loader import load_snapshot
        from backend.utils.snapshot_parser import parse_snapshot_to_stock_info

        logger.info(f"Loading disk snapshot for {ticker}")
        snapshot = load_snapshot(ticker, max_age_hours=None)  # No age limit for last resort

        if not snapshot:
            return None

        # Parse snapshot into full stock_info format
        result = parse_snapshot_to_stock_info(snapshot)

        logger.info(f"Snapshot fallback successful for {ticker}: {len([k for k, v in result.items() if v is not None])} fields")
        return result

    except Exception as e:
        logger.warning(f"Snapshot fallback failed for {ticker}: {e}")
        return None


def _parse_screener_ratios(ratios_table: list) -> dict:
    """
    Parse Screener ratios table into stock_info format.

    Args:
        ratios_table: List of dicts from Screener ratios table

    Returns:
        Dict with extracted ratios
    """
    result = {}

    # Convert list of dicts to lookup
    ratios = {row.get("Item", ""): row for row in ratios_table}

    # Extract latest values (usually in the rightmost column)
    def get_latest(item_name):
        row = ratios.get(item_name)
        if not row:
            return None
        # Get last non-Item column value
        cols = [k for k in row.keys() if k != "Item"]
        if not cols:
            return None
        latest_col = cols[-1]  # Rightmost column
        val = row.get(latest_col)
        if val and val != "-":
            try:
                # Clean and convert
                cleaned = str(val).replace(",", "").replace("%", "")
                return float(cleaned)
            except:
                return None
        return None

    # Map Screener items to our format
    result["pe_ratio"] = get_latest("Stock P/E")
    result["pb_ratio"] = get_latest("Price to book value")
    result["dividend_yield_pct"] = get_latest("Dividend yield %")
    result["roe_pct"] = get_latest("ROCE %") or get_latest("ROE %")
    result["roa_pct"] = get_latest("ROA %")
    result["debt_to_equity"] = get_latest("Debt to equity")
    result["operating_margins_pct"] = get_latest("OPM %")
    result["profit_margins_pct"] = get_latest("Net Profit Margin %")
    result["current_ratio"] = get_latest("Current ratio")
    result["eps"] = get_latest("EPS in Rs")
    result["book_value"] = get_latest("Book value")

    # Market cap (often in Cr)
    market_cap_cr = get_latest("Market Cap")
    if market_cap_cr:
        result["market_cap_cr"] = market_cap_cr
        # Convert to absolute value (Cr to actual)
        result["market_cap"] = market_cap_cr * 1e7

    # Revenue and net income (often in Cr)
    revenue_cr = get_latest("Sales") or get_latest("Revenue")
    if revenue_cr:
        result["revenue_cr"] = revenue_cr
        result["revenue"] = revenue_cr * 1e7

    net_income_cr = get_latest("Net Profit")
    if net_income_cr:
        result["net_income_cr"] = net_income_cr
        result["net_income"] = net_income_cr * 1e7

    # Price data
    current_price = get_latest("Current Price") or get_latest("Price")
    if current_price:
        result["current_price"] = current_price

    result["52w_high"] = get_latest("52W High") or get_latest("High")
    result["52w_low"] = get_latest("52W Low") or get_latest("Low")

    return result


@tool
def get_stock_info(ticker: str) -> dict:
    """
    Fetch current stock info for an NSE-listed Indian company.

    Fallback chain: yfinance → scraper → disk snapshot

    Args:
        ticker: NSE ticker symbol, e.g. 'RELIANCE' or 'RELIANCE.NS'

    Returns:
        Dict with price, market cap, P/E, P/B, ROE, D/E, beta, EPS,
        dividend yield, margins, and other fundamentals.
        Includes 'source' field: 'yfinance', 'scraper', or 'snapshot'
        Includes 'as_of' field: timestamp of data
    """
    ticker = _ensure_ns(ticker)

    # Try disk cache first (survives Yahoo blocks)
    cached = get_cached_data("stock_info", ticker)
    if cached:
        return cached

    # Try memory cache (older cache layer)
    cache_key = f"stock_info_{ticker}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    def _fetch():
        stock = yf.Ticker(ticker)
        info = stock.info

        # Check if we got valid data
        if not info or len(info) < 5:
            logger.warning(f"yfinance returned minimal data for {ticker}")
            raise ValueError("No data available from yfinance")
        return info

    try:
        info = _retry_with_backoff(_fetch)

        result = {
            "ticker": ticker,
            "company_name": info.get("longName", ""),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "currency": info.get("currency", "INR"),
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "market_cap": info.get("marketCap"),
            "market_cap_cr": round(info.get("marketCap", 0) / 1e7, 1) if info.get("marketCap") else None,
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "pb_ratio": info.get("priceToBook"),
            "eps": info.get("trailingEps"),
            "dividend_yield_pct": round(info.get("dividendYield") * 100, 2) if info.get("dividendYield") is not None else None,
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "beta": info.get("beta"),
            "roe_pct": round(info.get("returnOnEquity") * 100, 2) if info.get("returnOnEquity") is not None else None,
            "roa_pct": round(info.get("returnOnAssets") * 100, 2) if info.get("returnOnAssets") is not None else None,
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "revenue": info.get("totalRevenue"),
            "revenue_cr": round(info.get("totalRevenue", 0) / 1e7, 1) if info.get("totalRevenue") else None,
            "net_income": info.get("netIncomeToCommon"),
            "net_income_cr": round(info.get("netIncomeToCommon", 0) / 1e7, 1) if info.get("netIncomeToCommon") else None,
            "gross_margins_pct": round(info.get("grossMargins") * 100, 2) if info.get("grossMargins") is not None else None,
            "operating_margins_pct": round(info.get("operatingMargins") * 100, 2) if info.get("operatingMargins") is not None else None,
            "profit_margins_pct": round(info.get("profitMargins") * 100, 2) if info.get("profitMargins") is not None else None,
            "shares_outstanding": info.get("sharesOutstanding"),
            "book_value": info.get("bookValue"),
            "free_cashflow": info.get("freeCashflow"),
            "total_debt": info.get("totalDebt"),
            "total_cash": info.get("totalCash"),
            "source": "yfinance",
            "as_of": datetime.utcnow().isoformat()
        }

        # Cache the result (both memory and disk)
        cache_set(cache_key, result)
        set_cached_data("stock_info", ticker, result)
        return result

    except Exception as e:
        logger.error(f"yfinance get_stock_info error for {ticker}: {e}")

        # Try scraper fallback
        logger.info(f"Attempting scraper fallback for {ticker}")
        scraper_result = _fetch_from_scraper_fallback(ticker)

        if scraper_result:
            # Cache the scraper result
            cache_set(cache_key, scraper_result)
            set_cached_data("stock_info", ticker, scraper_result)
            return scraper_result

        # Try disk snapshot as last resort
        logger.info(f"Attempting disk snapshot fallback for {ticker}")
        snapshot_result = _fetch_from_snapshot_fallback(ticker)

        if snapshot_result:
            return snapshot_result

        # All sources failed
        return {
            "error": f"All sources failed: yfinance={str(e)}",
            "ticker": ticker,
            "source": "none",
            "as_of": datetime.utcnow().isoformat()
        }


def _fetch_from_jugaad_fallback(ticker: str, period: str = "1y") -> Optional[dict]:
    """
    Fallback to fetch price data from jugaad-data (NSE).

    Args:
        ticker: NSE ticker (e.g., "RELIANCE.NS")
        period: Time period (e.g., "1y", "6mo")

    Returns:
        Price history dict or None if failed
    """
    try:
        from jugaad_data.nse import stock_df
        from datetime import datetime, timedelta

        # Convert period to date range
        end_date = datetime.now()
        period_map = {
            "1mo": 30,
            "3mo": 90,
            "6mo": 180,
            "1y": 365,
            "2y": 730,
            "5y": 1825
        }
        days = period_map.get(period, 365)
        start_date = end_date - timedelta(days=days)

        # Extract base ticker (jugaad uses NSE symbols without .NS)
        ticker_base = ticker.replace(".NS", "").replace(".BO", "")
        logger.info(f"Attempting jugaad-data fallback for {ticker_base}")

        # Fetch from NSE via jugaad
        df = stock_df(
            symbol=ticker_base,
            from_date=start_date,
            to_date=end_date,
            series="EQ"  # Equity series
        )

        if df.empty:
            logger.warning(f"jugaad-data returned no data for {ticker_base}")
            return None

        # jugaad returns columns: DATE, SYMBOL, SERIES, OPEN, HIGH, LOW, PREV. CLOSE, LTP, CLOSE, VWAP, 52W H, 52W L, VOLUME, VALUE, etc.
        # Convert to our format
        result = {
            "ticker": ticker,
            "period": period,
            "dates": [str(d.date()) for d in df.index],
            "open": [round(float(v), 2) for v in df["OPEN"].tolist()],
            "high": [round(float(v), 2) for v in df["HIGH"].tolist()],
            "low": [round(float(v), 2) for v in df["LOW"].tolist()],
            "close": [round(float(v), 2) for v in df["CLOSE"].tolist()],
            "volume": [int(v) for v in df["VOLUME"].tolist()],
            "latest_price": round(float(df["CLOSE"].iloc[-1]), 2),
            "oldest_price": round(float(df["CLOSE"].iloc[0]), 2),
            "price_return_pct": round(
                (float(df["CLOSE"].iloc[-1]) / float(df["CLOSE"].iloc[0]) - 1) * 100, 2
            ),
            "source": "jugaad-data"  # Mark the source
        }

        logger.info(f"jugaad-data fallback successful for {ticker_base}: {len(df)} data points")
        return result

    except Exception as e:
        logger.warning(f"jugaad-data fallback failed for {ticker}: {e}")
        return None


@tool
def get_price_history(ticker: str, period: str = "1y") -> dict:
    """
    Fetch daily OHLCV price history for a stock.

    Args:
        ticker: NSE ticker e.g. 'RELIANCE.NS'
        period: '1y', '2y', '6mo', '3mo', '1mo'

    Returns:
        Dict with dates, opens, highs, lows, closes, volumes as lists,
        plus latest price, oldest price, and price return percentage.
    """
    ticker = _ensure_ns(ticker)

    # Try disk cache first
    cached = get_cached_data("price_history", ticker, period)
    if cached:
        return cached

    # Try memory cache
    cache_key = f"price_history_{ticker}_{period}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    def _fetch():
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)

        if hist.empty:
            logger.warning(f"No price data returned for {ticker}")
            raise ValueError(f"No price data for {ticker}")
        return hist

    try:
        hist = _retry_with_backoff(_fetch)

        # Convert to JSON-serializable format
        result = {
            "ticker": ticker,
            "period": period,
            "dates": [str(d.date()) for d in hist.index],
            "open": [round(float(v), 2) for v in hist["Open"].tolist()],
            "high": [round(float(v), 2) for v in hist["High"].tolist()],
            "low": [round(float(v), 2) for v in hist["Low"].tolist()],
            "close": [round(float(v), 2) for v in hist["Close"].tolist()],
            "volume": [int(v) for v in hist["Volume"].tolist()],
            "latest_price": round(float(hist["Close"].iloc[-1]), 2),
            "oldest_price": round(float(hist["Close"].iloc[0]), 2),
            "price_return_pct": round(
                (float(hist["Close"].iloc[-1]) / float(hist["Close"].iloc[0]) - 1) * 100, 2
            ),
        }

        # Cache the result (both memory and disk)
        cache_set(cache_key, result)
        set_cached_data("price_history", ticker, result, period)
        return result

    except Exception as e:
        logger.error(f"yfinance get_price_history error for {ticker}: {e}")

        # Try fallback to jugaad-data
        logger.info(f"Attempting fallback price source for {ticker}")
        fallback_result = _fetch_from_jugaad_fallback(ticker, period)

        if fallback_result:
            # Cache the fallback result
            cache_set(cache_key, fallback_result)
            set_cached_data("price_history", ticker, fallback_result, period)
            return fallback_result

        # Both sources failed
        return {"error": f"All price sources failed: {str(e)}", "ticker": ticker}


@tool
def get_nifty_history(period: str = "1y") -> dict:
    """
    Fetch Nifty 50 index price history for Beta computation.

    Args:
        period: '1y', '2y', '6mo', '3mo'

    Returns:
        Dict with dates and closes as lists.
    """
    # Try disk cache first
    cached = get_cached_data("nifty_history", "NSEI", period)
    if cached:
        return cached

    # Try memory cache
    cache_key = f"nifty_{period}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    def _fetch():
        nifty = yf.Ticker("^NSEI")
        hist = nifty.history(period=period)

        if hist.empty:
            logger.warning(f"No Nifty data returned for period {period}")
            raise ValueError("No Nifty 50 data available")
        return hist

    try:
        hist = _retry_with_backoff(_fetch)

        result = {
            "dates": [str(d.date()) for d in hist.index],
            "close": [round(float(v), 2) for v in hist["Close"].tolist()],
            "period": period,
        }

        # Cache the result (both memory and disk)
        cache_set(cache_key, result)
        set_cached_data("nifty_history", "NSEI", result, period)
        return result

    except Exception as e:
        logger.error(f"Nifty fetch error: {e}")

        # Try jugaad-data fallback
        try:
            from jugaad_data.nse import index_df
            from datetime import datetime, timedelta

            end_date = datetime.now()
            period_map = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730, "5y": 1825}
            days = period_map.get(period, 365)
            start_date = end_date - timedelta(days=days)

            logger.info(f"Attempting jugaad-data fallback for Nifty 50")
            df = index_df(symbol="NIFTY 50", from_date=start_date, to_date=end_date)

            if df.empty:
                logger.warning("jugaad-data returned no Nifty data")
                return {"error": f"All Nifty sources failed: {str(e)}", "period": period}

            result = {
                "dates": [str(d.date()) for d in df.index],
                "close": [round(float(v), 2) for v in df["CLOSE"].tolist()],
                "period": period,
                "source": "jugaad-data"
            }

            # Cache the fallback result
            cache_set(cache_key, result)
            set_cached_data("nifty_history", "NSEI", result, period)
            logger.info(f"jugaad-data Nifty fallback successful: {len(df)} data points")
            return result

        except Exception as fallback_error:
            logger.error(f"jugaad-data Nifty fallback failed: {fallback_error}")
            return {"error": f"All Nifty sources failed: yfinance={str(e)}, jugaad={str(fallback_error)}", "period": period}


@tool
def get_sector_median(sector: str) -> dict:
    """
    Return median financial ratios for a given sector.

    Args:
        sector: One of IT, BFSI, Auto, FMCG, Pharma, Infra, Defence, Energy, NBFC, Diversified

    Returns:
        Dict with sector name and median ratios.
    """
    from backend.utils.sector_data import get_sector_median as _get_sector_median

    try:
        return _get_sector_median(sector)
    except Exception as e:
        logger.error(f"get_sector_median error for {sector}: {e}")
        return {
            "error": str(e),
            "sector": sector,
            "medians": {}
        }


def get_scraper_data(ticker: str) -> Optional[dict]:
    """
    Get full scraper data for a ticker (not a @tool, used internally by agents).

    Args:
        ticker: Stock ticker

    Returns:
        Full scraper data dict with tables, or None if not available
    """
    try:
        from backend.scraper.snapshot_loader import get_cached_or_fetch

        ticker = _ensure_ns(ticker)
        data = get_cached_or_fetch(ticker)

        if data.get("tables"):
            return data
        return None

    except Exception as e:
        logger.error(f"Failed to get scraper data for {ticker}: {e}")
        return None
