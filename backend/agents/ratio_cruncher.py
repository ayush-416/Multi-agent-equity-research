"""
Ratio Cruncher Agent: Computes and analyzes financial ratios using real data.

Fetches stock fundamentals, calculates ratios, compares against sector benchmarks,
and provides strengths/concerns analysis based on computed metrics.

Falls back to scraper data when yfinance fails.
"""

import logging
from typing import Dict, Any, Optional

from backend.tools.financial_tools import get_stock_info, get_sector_median

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_ratio_cruncher(
    ticker: str,
    company_name: str,
    sector: str = "",
    cached_stock_info: dict = None
) -> Dict[str, Any]:
    """
    Compute and analyze financial ratios for a company.

    Args:
        ticker: Stock ticker symbol (e.g., "RELIANCE")
        company_name: Full company name
        sector: Sector name (optional, will be fetched if not provided)
        cached_stock_info: Pre-fetched stock info from workflow state (optional)

    Returns:
        Dict with keys:
        - status: "success", "partial_success", or "error"
        - ticker: Stock ticker
        - company_name: Company name
        - sector: Company sector
        - ratios: Dict of computed financial ratios
        - sector_benchmarks: Dict of sector median ratios
        - strengths: List of positive ratio signals
        - concerns: List of concerning ratio signals
        - valuation_summary: Brief valuation assessment
        - error: Error message if applicable
    """
    result = {
        "status": "error",
        "ticker": ticker,
        "company_name": company_name,
        "sector": sector,
        "ratios": {},
        "sector_benchmarks": {},
        "strengths": [],
        "concerns": [],
        "valuation_summary": "",
        "error": None
    }

    try:
        logger.info(f"Starting ratio analysis for {ticker} ({company_name})")

        # Use cached stock info if provided, otherwise fetch
        if cached_stock_info is not None:
            if "error" not in cached_stock_info:
                logger.info("Using cached stock info from workflow state")
                stock_info = cached_stock_info
            else:
                logger.error(f"Cached stock info has error: {cached_stock_info['error']}")
                # Try india_financials fallback
                fallback_result = _try_india_financials_fallback(ticker, company_name)
                if fallback_result:
                    return fallback_result
                result["error"] = f"Stock data unavailable: {cached_stock_info['error']}"
                result["status"] = "no_data"
                return result
        else:
            logger.info("Fetching stock info (cache not available)")
            stock_info = get_stock_info.func(ticker)

        if "error" in stock_info:
            logger.error(f"Failed to fetch stock info: {stock_info['error']}")
            # Try india_financials fallback
            fallback_result = _try_india_financials_fallback(ticker, company_name)
            if fallback_result:
                return fallback_result
            result["error"] = f"Stock data unavailable: {stock_info['error']}"
            result["status"] = "no_data"
            return result

        # Check currency mismatch
        currency = stock_info.get("currency", "INR")
        if currency != "INR":
            logger.warning(f"Data is in {currency}, not INR - may not align with Indian stock prices")
            result["currency_warning"] = f"Financial data is in {currency}, not INR"

        # Extract sector if not provided
        if not sector and stock_info.get("sector"):
            sector = stock_info["sector"]
            result["sector"] = sector
            logger.info(f"Detected sector: {sector}")

        # Extract and organize ratios
        ratios = {
            "pe_ratio": stock_info.get("pe_ratio"),
            "forward_pe": stock_info.get("forward_pe"),
            "pb_ratio": stock_info.get("pb_ratio"),
            "eps": stock_info.get("eps"),
            "roe_pct": stock_info.get("roe_pct"),
            "roa_pct": stock_info.get("roa_pct"),
            "debt_to_equity": stock_info.get("debt_to_equity"),
            "current_ratio": stock_info.get("current_ratio"),
            "dividend_yield_pct": stock_info.get("dividend_yield_pct"),
            "operating_margins_pct": stock_info.get("operating_margins_pct"),
            "profit_margins_pct": stock_info.get("profit_margins_pct"),
            "market_cap_cr": stock_info.get("market_cap_cr"),
            "revenue_cr": stock_info.get("revenue_cr"),
            "net_income_cr": stock_info.get("net_income_cr"),
            "current_price": stock_info.get("current_price"),
            "52w_high": stock_info.get("52w_high"),
            "52w_low": stock_info.get("52w_low"),
            "beta": stock_info.get("beta"),
        }

        result["ratios"] = ratios
        result["source"] = stock_info.get("source", "unknown")
        result["as_of"] = stock_info.get("as_of")

        # Check if we have any meaningful data
        non_null_ratios = {k: v for k, v in ratios.items() if v is not None}
        if not non_null_ratios:
            logger.warning(f"No ratios available for {ticker}")
            result["status"] = "no_data"
            result["error"] = f"No financial ratios available (source: {result['source']})"
            return result

        # Check for minimum key ratios (need at least 3 core metrics)
        key_ratios = ["pe_ratio", "pb_ratio", "roe_pct", "debt_to_equity", "profit_margins_pct", "current_ratio"]
        available_key_ratios = [k for k in key_ratios if ratios.get(k) is not None]

        if len(available_key_ratios) < 3:
            logger.warning(f"Insufficient key ratios for {ticker}: only {len(available_key_ratios)} available")
            result["status"] = "partial"
            result["error"] = f"Limited ratio data: only {len(available_key_ratios)} key ratios available (source: {result['source']})"
            # Continue with analysis but flag as partial
        else:
            logger.info(f"Extracted {len(non_null_ratios)} ratios ({len(available_key_ratios)} key ratios)")


        # Fetch sector benchmarks if sector is available
        sector_benchmarks = {}
        if sector:
            try:
                benchmark_data = get_sector_median.func(sector)
                if "error" not in benchmark_data:
                    sector_benchmarks = benchmark_data.get("medians", {})
                    result["sector_benchmarks"] = sector_benchmarks
                    logger.info(f"Fetched sector benchmarks for {sector}")
                else:
                    logger.warning(f"Sector benchmarks unavailable: {benchmark_data.get('error')}")
            except Exception as e:
                logger.warning(f"Failed to fetch sector benchmarks: {e}")

        # Analyze strengths and concerns based on computed ratios
        strengths, concerns = _analyze_ratios(ratios, sector_benchmarks)
        result["strengths"] = strengths
        result["concerns"] = concerns

        # Generate valuation summary
        result["valuation_summary"] = _generate_valuation_summary(
            ratios, sector_benchmarks, company_name
        )

        # Set final status (preserve "partial" if already set)
        if result["status"] != "partial":
            if sector_benchmarks:
                result["status"] = "success"
                logger.info(f"Ratio analysis completed successfully for {ticker}")
            else:
                result["status"] = "partial_success"
                if not result.get("error"):
                    result["error"] = "Sector benchmarks unavailable"
                logger.info(f"Ratio analysis completed with partial success (no sector benchmarks)")

    except Exception as e:
        logger.error(f"Ratio analysis failed for {ticker}: {e}", exc_info=True)
        result["status"] = "error"
        result["error"] = str(e)

    return result


def _analyze_ratios(
    ratios: Dict[str, Any],
    sector_benchmarks: Dict[str, Any]
) -> tuple[list[str], list[str]]:
    """
    Analyze ratios to identify strengths and concerns.

    Uses code logic to compare ratios against sector benchmarks
    and absolute thresholds. No LLM hallucination.

    Returns:
        Tuple of (strengths list, concerns list)
    """
    strengths = []
    concerns = []

    # ROE analysis
    roe = ratios.get("roe_pct")
    if roe is not None:
        sector_roe = sector_benchmarks.get("roe_pct")
        if sector_roe and roe > sector_roe * 1.2:
            strengths.append(f"Strong ROE of {roe:.1f}% (sector median: {sector_roe:.1f}%)")
        elif roe > 15:
            strengths.append(f"Healthy ROE of {roe:.1f}%")
        elif roe < 10:
            concerns.append(f"Low ROE of {roe:.1f}%")

    # ROA analysis
    roa = ratios.get("roa_pct")
    if roa is not None:
        sector_roa = sector_benchmarks.get("roa_pct")
        if sector_roa and roa > sector_roa * 1.2:
            strengths.append(f"Strong ROA of {roa:.1f}% (sector median: {sector_roa:.1f}%)")
        elif roa > 10:
            strengths.append(f"Healthy ROA of {roa:.1f}%")
        elif roa < 5:
            concerns.append(f"Low ROA of {roa:.1f}%")

    # P/E ratio analysis
    pe = ratios.get("pe_ratio")
    if pe is not None and pe > 0:
        sector_pe = sector_benchmarks.get("pe_ratio")
        if sector_pe:
            if pe < sector_pe * 0.8:
                strengths.append(f"Attractive valuation: P/E {pe:.1f}x vs sector {sector_pe:.1f}x")
            elif pe > sector_pe * 1.5:
                concerns.append(f"High valuation: P/E {pe:.1f}x vs sector {sector_pe:.1f}x")
        else:
            if pe < 15:
                strengths.append(f"Reasonable P/E ratio of {pe:.1f}x")
            elif pe > 40:
                concerns.append(f"High P/E ratio of {pe:.1f}x")

    # P/B ratio analysis
    pb = ratios.get("pb_ratio")
    if pb is not None and pb > 0:
        sector_pb = sector_benchmarks.get("pb_ratio")
        if sector_pb:
            if pb < sector_pb * 0.8:
                strengths.append(f"Trading below book value relative to sector: P/B {pb:.1f}x vs {sector_pb:.1f}x")
            elif pb > sector_pb * 1.5:
                concerns.append(f"Premium to book value: P/B {pb:.1f}x vs sector {sector_pb:.1f}x")

    # Debt-to-equity analysis
    de = ratios.get("debt_to_equity")
    if de is not None:
        sector_de = sector_benchmarks.get("debt_to_equity")
        if de < 50:
            strengths.append(f"Low debt-to-equity ratio of {de:.1f}")
        elif de > 150:
            if sector_de and de < sector_de:
                strengths.append(f"Debt-to-equity {de:.1f} within sector norms ({sector_de:.1f})")
            else:
                concerns.append(f"High debt-to-equity ratio of {de:.1f}")

    # Current ratio analysis (liquidity)
    cr = ratios.get("current_ratio")
    if cr is not None:
        if cr > 1.5:
            strengths.append(f"Strong liquidity: current ratio {cr:.2f}")
        elif cr < 1.0:
            concerns.append(f"Weak liquidity: current ratio {cr:.2f}")

    # Operating margin analysis
    op_margin = ratios.get("operating_margins_pct")
    if op_margin is not None:
        sector_op_margin = sector_benchmarks.get("operating_margins_pct")
        if sector_op_margin and op_margin > sector_op_margin * 1.2:
            strengths.append(f"Superior operating margin of {op_margin:.1f}% (sector: {sector_op_margin:.1f}%)")
        elif op_margin > 20:
            strengths.append(f"Strong operating margin of {op_margin:.1f}%")
        elif op_margin < 5:
            concerns.append(f"Thin operating margin of {op_margin:.1f}%")

    # Profit margin analysis
    profit_margin = ratios.get("profit_margins_pct")
    if profit_margin is not None:
        if profit_margin > 15:
            strengths.append(f"Strong net margin of {profit_margin:.1f}%")
        elif profit_margin < 5:
            concerns.append(f"Low net margin of {profit_margin:.1f}%")

    # Dividend yield analysis
    div_yield = ratios.get("dividend_yield_pct")
    if div_yield is not None and div_yield > 2:
        strengths.append(f"Attractive dividend yield of {div_yield:.1f}%")

    # Don't add generic messages if we have no data at all
    # Only add them if we have SOME ratios but no clear signals
    has_any_ratios = any(v is not None for v in ratios.values())

    if not strengths and has_any_ratios:
        strengths.append("No standout positive ratio signals identified")
    if not concerns and has_any_ratios:
        concerns.append("No major concerns identified in available ratios")

    return strengths, concerns


def _generate_valuation_summary(
    ratios: Dict[str, Any],
    sector_benchmarks: Dict[str, Any],
    company_name: str
) -> str:
    """
    Generate valuation summary based on computed ratios.

    Uses code logic only - no LLM, no hallucinated numbers.

    Returns:
        Valuation summary string
    """
    summary_parts = []

    # Check if we have any ratios at all
    has_any_ratios = any(v is not None for v in ratios.values())
    if not has_any_ratios:
        return "No financial ratio data available for valuation assessment"

    # Market cap context
    market_cap_cr = ratios.get("market_cap_cr")
    if market_cap_cr:
        if market_cap_cr > 100000:
            summary_parts.append(f"{company_name} is a large-cap company (₹{market_cap_cr:,.0f} cr)")
        elif market_cap_cr > 10000:
            summary_parts.append(f"{company_name} is a mid-cap company (₹{market_cap_cr:,.0f} cr)")
        else:
            summary_parts.append(f"{company_name} is a small-cap company (₹{market_cap_cr:,.0f} cr)")

    # Valuation assessment
    pe = ratios.get("pe_ratio")
    pb = ratios.get("pb_ratio")

    if pe and pb:
        sector_pe = sector_benchmarks.get("pe_ratio")
        sector_pb = sector_benchmarks.get("pb_ratio")

        if sector_pe and sector_pb:
            pe_premium = (pe / sector_pe - 1) * 100 if sector_pe else 0
            pb_premium = (pb / sector_pb - 1) * 100 if sector_pb else 0

            if pe_premium < -10 and pb_premium < -10:
                summary_parts.append(f"Trading at a discount to sector (P/E {pe_premium:.0f}%, P/B {pb_premium:.0f}%)")
            elif pe_premium > 20 and pb_premium > 20:
                summary_parts.append(f"Trading at a premium to sector (P/E {pe_premium:.0f}%, P/B {pb_premium:.0f}%)")
            else:
                summary_parts.append("Trading roughly in line with sector multiples")
        else:
            summary_parts.append(f"Current valuation: P/E {pe:.1f}x, P/B {pb:.1f}x")

    # Profitability context
    roe = ratios.get("roe_pct")
    if roe:
        if roe > 15:
            summary_parts.append(f"with strong profitability (ROE {roe:.1f}%)")
        elif roe < 10:
            summary_parts.append(f"with modest profitability (ROE {roe:.1f}%)")

    # Financial health
    de = ratios.get("debt_to_equity")
    if de is not None:
        if de < 50:
            summary_parts.append("and conservative leverage")
        elif de > 150:
            summary_parts.append("and elevated leverage levels")

    if not summary_parts:
        # We have some ratios but couldn't build a summary
        available_fields = [k for k, v in ratios.items() if v is not None]
        return f"Limited financial data available (found: {', '.join(available_fields[:3])})"

    return ". ".join(summary_parts) + "."


def _try_india_financials_fallback(ticker: str, company_name: str) -> Optional[Dict[str, Any]]:
    """
    Try to get ratios from india_financials (Screener) when yfinance fails.

    Args:
        ticker: Stock ticker
        company_name: Company name

    Returns:
        Complete ratio_cruncher result dict or None
    """
    try:
        from backend.scraper.india_financials import get_financials

        logger.info(f"Attempting india_financials fallback for {ticker}")

        # Extract base ticker (remove .NS/.BO suffix)
        base_ticker = ticker.replace(".NS", "").replace(".BO", "")

        scraper_data = get_financials(base_ticker, source="screener")

        if not scraper_data or not scraper_data.get("tables"):
            logger.warning(f"No india_financials data available for {ticker}")
            return None

        tables = scraper_data.get("tables", {})
        currency = scraper_data.get("currency", "INR")

        # Extract ratios from Screener ratios table
        ratios_table = tables.get("S_Ratios")
        if not ratios_table:
            logger.warning(f"No ratios table in india_financials data for {ticker}")
            return None

        # Parse ratios
        ratios = _parse_india_financials_ratios(ratios_table)

        if not ratios:
            logger.warning(f"Could not parse ratios from india_financials data for {ticker}")
            return None

        logger.info(f"Extracted {len(ratios)} ratios from india_financials (currency: {currency})")

        # Extract sector from company info if available
        sector = ""
        text_sections = scraper_data.get("text_sections", {})
        if text_sections and "company_info" in text_sections:
            # Try to extract sector from company info text
            # Format is often "Sector: XYZ" in the company info
            company_info = text_sections["company_info"]
            import re
            sector_match = re.search(r'Sector[:\s]+([A-Za-z\s&]+?)(?:\s+\||$)', company_info)
            if sector_match:
                sector = sector_match.group(1).strip()
                logger.info(f"Extracted sector from Screener: {sector}")

        result = {
            "status": "success",
            "ticker": ticker,
            "company_name": scraper_data.get("company", company_name),
            "sector": sector,
            "ratios": ratios,
            "sector_benchmarks": {},
            "strengths": [],
            "concerns": [],
            "valuation_summary": "",
            "error": None,
            "source": "india_financials",
            "currency": currency,
            "as_of": scraper_data.get("fetched_at")
        }

        # Try to get sector benchmarks if we have sector info
        if sector:
            try:
                from backend.tools.financial_tools import get_sector_median
                benchmark_data = get_sector_median.func(sector)
                if "error" not in benchmark_data:
                    result["sector_benchmarks"] = benchmark_data.get("medians", {})
                    logger.info(f"Fetched sector benchmarks for {sector}")
            except Exception as e:
                logger.warning(f"Could not fetch sector benchmarks: {e}")

        # Analyze strengths and concerns
        strengths, concerns = _analyze_ratios(ratios, result["sector_benchmarks"])
        result["strengths"] = strengths
        result["concerns"] = concerns

        # Generate valuation summary
        result["valuation_summary"] = _generate_valuation_summary(
            ratios, result["sector_benchmarks"], company_name
        )

        return result

    except Exception as e:
        logger.error(f"india_financials fallback failed for {ticker}: {e}", exc_info=True)
        return None


def _parse_india_financials_ratios(ratios_table: list) -> Dict[str, Any]:
    """
    Parse ratios from india_financials Screener ratios table.

    Args:
        ratios_table: List of dicts from S_Ratios table

    Returns:
        Dict with extracted ratios
    """
    ratios = {}

    # Convert to lookup
    rows = {row.get("Item", ""): row for row in ratios_table}

    def get_latest(item_name):
        """Get latest value from rightmost column."""
        row = rows.get(item_name)
        if not row:
            return None
        # Get last non-Item column
        cols = [k for k in row.keys() if k != "Item"]
        if not cols:
            return None
        latest_col = cols[-1]
        val = row.get(latest_col)
        if val and val != "-":
            try:
                cleaned = str(val).replace(",", "").replace("%", "")
                return float(cleaned)
            except:
                return None
        return None

    # Map Screener items to our format
    ratios["pe_ratio"] = get_latest("Stock P/E")
    ratios["pb_ratio"] = get_latest("Price to book value")
    ratios["dividend_yield_pct"] = get_latest("Dividend yield %")
    ratios["roe_pct"] = get_latest("ROCE %") or get_latest("ROE %")
    ratios["roa_pct"] = get_latest("ROA %")
    ratios["debt_to_equity"] = get_latest("Debt to equity")
    ratios["operating_margins_pct"] = get_latest("OPM %")
    ratios["profit_margins_pct"] = get_latest("Net Profit Margin %")
    ratios["current_ratio"] = get_latest("Current ratio")
    ratios["eps"] = get_latest("EPS in Rs")

    # Market cap (often in Cr)
    market_cap_cr = get_latest("Market Cap")
    if market_cap_cr:
        ratios["market_cap_cr"] = market_cap_cr

    # Revenue and net income (often in Cr)
    revenue_cr = get_latest("Sales") or get_latest("Revenue")
    if revenue_cr:
        ratios["revenue_cr"] = revenue_cr

    net_income_cr = get_latest("Net Profit")
    if net_income_cr:
        ratios["net_income_cr"] = net_income_cr

    # Price data
    current_price = get_latest("Current Price") or get_latest("Price")
    if current_price:
        ratios["current_price"] = current_price

    ratios["52w_high"] = get_latest("52W High") or get_latest("High")
    ratios["52w_low"] = get_latest("52W Low") or get_latest("Low")

    # Filter out None values
    return {k: v for k, v in ratios.items() if v is not None}
