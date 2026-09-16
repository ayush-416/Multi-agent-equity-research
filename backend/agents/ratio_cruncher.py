"""
Ratio Cruncher Agent: Computes and analyzes financial ratios using real data.

Fetches stock fundamentals, calculates ratios, compares against sector benchmarks,
and provides strengths/concerns analysis based on computed metrics.
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
        if cached_stock_info is not None and "error" not in cached_stock_info:
            logger.info("Using cached stock info from workflow state")
            stock_info = cached_stock_info
        else:
            logger.info("Fetching stock info (cache not available)")
            stock_info = get_stock_info.func(ticker)

        if "error" in stock_info:
            logger.error(f"Failed to fetch stock info: {stock_info['error']}")
            result["error"] = f"Stock data unavailable: {stock_info['error']}"
            return result

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
        logger.info(f"Extracted {len([v for v in ratios.values() if v is not None])} ratios")

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

        # Set final status
        if sector_benchmarks:
            result["status"] = "success"
            logger.info(f"Ratio analysis completed successfully for {ticker}")
        else:
            result["status"] = "partial_success"
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

    # Add generic messages if lists are empty
    if not strengths:
        strengths.append("Limited ratio data available for analysis")
    if not concerns:
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
        return "Limited financial data available for valuation assessment"

    return ". ".join(summary_parts) + "."
