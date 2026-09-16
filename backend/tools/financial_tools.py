"""
LangChain @tool wrappers around yfinance for Indian stock data.
All functions handle .NS suffix automatically.
All returns are JSON-serializable dicts (no pandas objects).
All external calls use cache and handle errors gracefully.
"""
import logging
import time
from typing import Optional
import yfinance as yf
import numpy as np
from langchain.tools import tool
from curl_cffi import requests as curl_requests

from backend.utils.cache import cache_get, cache_set
from backend.utils.yfinance_disk_cache import get_cached_data, set_cached_data
from backend.utils.validators import normalize_ticker, add_ns_suffix

logger = logging.getLogger(__name__)

# Global curl_cffi session with Chrome impersonation to bypass Yahoo Finance TLS fingerprint blocks
# This session is shared across all yfinance calls to maintain cookie/crumb state
_curl_session = None


def _get_curl_session():
    """
    Get or create the shared curl_cffi session with Chrome impersonation.

    This bypasses Yahoo Finance's TLS fingerprint-based blocking.
    Do NOT wrap this in requests_cache or other session wrappers.
    """
    global _curl_session
    if _curl_session is None:
        logger.info("Creating curl_cffi session with Chrome impersonation")
        _curl_session = curl_requests.Session(impersonate="chrome")
    return _curl_session


def _retry_with_backoff(func, max_retries=3, initial_delay=1.0):
    """
    Retry a function with exponential backoff for transient errors.

    Args:
        func: Callable to retry
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 1.0)

    Returns:
        Function result if successful

    Raises:
        Last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_exception = e
            error_msg = str(e).lower()

            # Check if it's a rate limit error
            if "rate limit" in error_msg or "too many requests" in error_msg or "429" in error_msg:
                if attempt < max_retries - 1:
                    delay = initial_delay * (2 ** attempt)
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


@tool
def get_stock_info(ticker: str) -> dict:
    """
    Fetch current stock info for an NSE-listed Indian company.

    Args:
        ticker: NSE ticker symbol, e.g. 'RELIANCE' or 'RELIANCE.NS'

    Returns:
        Dict with price, market cap, P/E, P/B, ROE, D/E, beta, EPS,
        dividend yield, margins, and other fundamentals.
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
        session = _get_curl_session()
        stock = yf.Ticker(ticker, session=session)
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
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "market_cap": info.get("marketCap"),
            "market_cap_cr": round(info.get("marketCap", 0) / 1e7, 1) if info.get("marketCap") else None,
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "pb_ratio": info.get("priceToBook"),
            "eps": info.get("trailingEps"),
            "dividend_yield_pct": round(info.get("dividendYield", 0) * 100, 2) if info.get("dividendYield") else 0,
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "beta": info.get("beta"),
            "roe_pct": round(info.get("returnOnEquity", 0) * 100, 2) if info.get("returnOnEquity") else None,
            "roa_pct": round(info.get("returnOnAssets", 0) * 100, 2) if info.get("returnOnAssets") else None,
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "revenue": info.get("totalRevenue"),
            "revenue_cr": round(info.get("totalRevenue", 0) / 1e7, 1) if info.get("totalRevenue") else None,
            "net_income": info.get("netIncomeToCommon"),
            "net_income_cr": round(info.get("netIncomeToCommon", 0) / 1e7, 1) if info.get("netIncomeToCommon") else None,
            "gross_margins_pct": round(info.get("grossMargins", 0) * 100, 2) if info.get("grossMargins") else None,
            "operating_margins_pct": round(info.get("operatingMargins", 0) * 100, 2) if info.get("operatingMargins") else None,
            "profit_margins_pct": round(info.get("profitMargins", 0) * 100, 2) if info.get("profitMargins") else None,
            "shares_outstanding": info.get("sharesOutstanding"),
            "book_value": info.get("bookValue"),
            "free_cashflow": info.get("freeCashflow"),
            "total_debt": info.get("totalDebt"),
            "total_cash": info.get("totalCash"),
        }

        # Cache the result (both memory and disk)
        cache_set(cache_key, result)
        set_cached_data("stock_info", ticker, result)
        return result

    except Exception as e:
        logger.error(f"yfinance get_stock_info error for {ticker}: {e}")
        return {"error": str(e), "ticker": ticker}


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
        session = _get_curl_session()
        stock = yf.Ticker(ticker, session=session)
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
        return {"error": str(e), "ticker": ticker}


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
        session = _get_curl_session()
        nifty = yf.Ticker("^NSEI", session=session)
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
        return {"error": str(e), "period": period}


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
