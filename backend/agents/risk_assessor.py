"""
Risk Assessor Agent: Comprehensive financial risk analysis.

Calculates market risk, financial risk, and bankruptcy indicators using
real data and code-based metrics. No LLM hallucination of risk values.
"""

import logging
from typing import Dict, Any, Optional, List

from backend.risk.metrics import (
    calculate_beta,
    calculate_var,
    calculate_volatility,
    calculate_max_drawdown,
    calculate_altman_z_score,
    classify_risk_level
)
from backend.tools.financial_tools import (
    get_price_history,
    get_nifty_history,
    get_stock_info
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_risk_assessor(
    ticker: str,
    company_name: str,
    ratio_output: Optional[Dict] = None,
    technical_output: Optional[Dict] = None,
    cached_stock_info: dict = None,
    cached_price_history: dict = None,
    cached_nifty_history: dict = None
) -> Dict[str, Any]:
    """
    Assess comprehensive financial risk for a company.

    Args:
        ticker: Stock ticker symbol (e.g., "RELIANCE")
        company_name: Full company name (e.g., "Reliance Industries")
        ratio_output: Optional output from ratio_cruncher agent
        technical_output: Optional output from technical_analyst agent
        cached_stock_info: Pre-fetched stock info from workflow state (optional)
        cached_price_history: Pre-fetched price history from workflow state (optional)
        cached_nifty_history: Pre-fetched Nifty history from workflow state (optional)

    Returns:
        Dict with keys:
        - status: "ok", "partial", "no_data", or "error"
        - ticker: Stock ticker
        - company_name: Company name
        - risk_score: Overall risk score (0-100, higher = higher risk)
        - risk_level: Risk classification (LOW/MEDIUM/MEDIUM-HIGH/HIGH/VERY HIGH/UNKNOWN)
        - risk_factors: List of identified risk factors
        - risk_flags: List of warning flags
        - metrics: Dict of calculated risk metrics
        - unavailable_metrics: List of metrics that couldn't be calculated
        - summary: Risk assessment summary
        - error: Error message if applicable
    """
    result = {
        "status": "error",
        "ticker": ticker,
        "company_name": company_name,
        "risk_score": 50.0,
        "risk_level": "UNKNOWN",
        "risk_factors": [],
        "risk_flags": [],
        "metrics": {},
        "unavailable_metrics": [],
        "summary": "",
        "error": None
    }

    try:
        logger.info(f"Starting risk assessment for {ticker} ({company_name})")

        # Track what data we successfully retrieved
        has_price_data = False
        has_stock_info = False
        has_nifty_data = False

        metrics = {}
        unavailable = []

        # === 1. Use cached price history (don't refetch on cache failure) ===
        if cached_price_history is not None:
            if "error" not in cached_price_history:
                logger.info("Using cached price history from workflow state")
                price_data = cached_price_history
                has_price_data = True
            else:
                logger.warning(f"Cached price history has error: {cached_price_history['error']}")
                price_data = cached_price_history
        else:
            logger.info("Fetching price history (cache not provided)")
            try:
                price_data = get_price_history.func(ticker, period="1y")
                if "error" not in price_data:
                    has_price_data = True
                    logger.info("Price data retrieved successfully")
                else:
                    logger.warning(f"Price data unavailable: {price_data['error']}")
            except Exception as e:
                logger.warning(f"Failed to fetch price data: {e}")
                price_data = {"error": str(e)}

        # === 2. Use cached stock info (don't refetch on cache failure) ===
        if cached_stock_info is not None:
            if "error" not in cached_stock_info:
                logger.info("Using cached stock info from workflow state")
                stock_info = cached_stock_info
                has_stock_info = True
            else:
                logger.warning(f"Cached stock info has error: {cached_stock_info['error']}")
                stock_info = cached_stock_info
        else:
            logger.info("Fetching stock info (cache not provided)")
            try:
                stock_info = get_stock_info.func(ticker)
                if "error" not in stock_info:
                    has_stock_info = True
                    logger.info("Stock info retrieved successfully")
                else:
                    logger.warning(f"Stock info unavailable: {stock_info['error']}")
            except Exception as e:
                logger.warning(f"Failed to fetch stock info: {e}")
                stock_info = {"error": str(e)}

        # === 3. Use cached Nifty history (don't refetch on cache failure) ===
        if cached_nifty_history is not None:
            if "error" not in cached_nifty_history:
                logger.info("Using cached Nifty history from workflow state")
                nifty_data = cached_nifty_history
                has_nifty_data = True
            else:
                logger.warning(f"Cached Nifty history has error: {cached_nifty_history['error']}")
                nifty_data = cached_nifty_history
        else:
            logger.info("Fetching Nifty history (cache not provided)")
            try:
                nifty_data = get_nifty_history.func(period="1y")
                if "error" not in nifty_data:
                    has_nifty_data = True
                    logger.info("Nifty data retrieved successfully")
                else:
                    logger.warning(f"Nifty data unavailable: {nifty_data['error']}")
            except Exception as e:
                logger.warning(f"Failed to fetch Nifty data: {e}")
                nifty_data = {"error": str(e)}

        # Check if we have any data
        if not (has_price_data or has_stock_info):
            result["error"] = "Unable to fetch any financial data for risk assessment"
            result["status"] = "no_data"
            result["unavailable_metrics"] = ["all metrics - no price or fundamental data available"]
            return result

        # === 4. Calculate market risk metrics ===

        # Beta vs Nifty 50
        if has_price_data and has_nifty_data:
            try:
                # Calculate returns
                stock_prices = price_data["close"]
                stock_returns = [
                    (stock_prices[i] - stock_prices[i-1]) / stock_prices[i-1]
                    for i in range(1, len(stock_prices))
                ]

                nifty_prices = nifty_data["close"]
                nifty_returns = [
                    (nifty_prices[i] - nifty_prices[i-1]) / nifty_prices[i-1]
                    for i in range(1, len(nifty_prices))
                ]

                beta = calculate_beta(stock_returns, nifty_returns)
                if beta is not None:
                    metrics["beta"] = round(beta, 2)
                    logger.info(f"Beta: {beta:.2f}")
                else:
                    unavailable.append("beta")
            except Exception as e:
                logger.warning(f"Beta calculation failed: {e}")
                unavailable.append("beta")
        else:
            unavailable.append("beta")

        # Volatility
        if has_price_data:
            try:
                stock_prices = price_data["close"]
                stock_returns = [
                    (stock_prices[i] - stock_prices[i-1]) / stock_prices[i-1]
                    for i in range(1, len(stock_prices))
                ]

                volatility = calculate_volatility(stock_returns, annualize=True)
                if volatility is not None:
                    metrics["volatility_pct"] = round(volatility, 2)
                    logger.info(f"Volatility: {volatility:.2f}%")
                else:
                    unavailable.append("volatility")
            except Exception as e:
                logger.warning(f"Volatility calculation failed: {e}")
                unavailable.append("volatility")
        else:
            unavailable.append("volatility")

        # VaR 95%
        if has_price_data:
            try:
                var_95 = calculate_var(stock_returns, confidence=0.95)
                if var_95 is not None:
                    metrics["var_95_pct"] = round(var_95, 2)
                    logger.info(f"VaR 95%: {var_95:.2f}%")
                else:
                    unavailable.append("var_95")
            except Exception as e:
                logger.warning(f"VaR calculation failed: {e}")
                unavailable.append("var_95")
        else:
            unavailable.append("var_95")

        # Max Drawdown
        if has_price_data:
            try:
                max_dd = calculate_max_drawdown(price_data["close"])
                if max_dd is not None:
                    metrics["max_drawdown_pct"] = round(max_dd, 2)
                    logger.info(f"Max Drawdown: {max_dd:.2f}%")
                else:
                    unavailable.append("max_drawdown")
            except Exception as e:
                logger.warning(f"Max drawdown calculation failed: {e}")
                unavailable.append("max_drawdown")
        else:
            unavailable.append("max_drawdown")

        # === 5. Calculate financial risk metrics ===

        # Leverage risk (debt-to-equity)
        if has_stock_info and stock_info.get("debt_to_equity") is not None:
            metrics["debt_to_equity"] = stock_info["debt_to_equity"]
        else:
            unavailable.append("debt_to_equity")

        # Liquidity risk (current ratio)
        if has_stock_info and stock_info.get("current_ratio") is not None:
            metrics["current_ratio"] = stock_info["current_ratio"]
        else:
            unavailable.append("current_ratio")

        # Valuation risk
        if has_stock_info:
            if stock_info.get("pe_ratio") is not None:
                metrics["pe_ratio"] = stock_info["pe_ratio"]
            else:
                unavailable.append("pe_ratio")

            if stock_info.get("pb_ratio") is not None:
                metrics["pb_ratio"] = stock_info["pb_ratio"]
            else:
                unavailable.append("pb_ratio")

        # === 6. Altman Z-Score ===
        if has_stock_info:
            try:
                # Extract required fields from stock_info
                # Note: yfinance may not provide all fields, so this is best-effort
                working_capital = None  # Not directly available
                retained_earnings = None  # Not directly available
                ebit = stock_info.get("ebit")
                market_cap = stock_info.get("market_cap")
                revenue = stock_info.get("revenue")
                total_assets = None  # Not directly available
                total_debt = stock_info.get("total_debt")

                # For Indian stocks, yfinance data is limited
                # We'll mark Z-score as unavailable if we don't have enough data
                z_score = None

                if all(v is not None for v in [market_cap, total_debt, revenue]):
                    # Attempt calculation with available data
                    # This is a partial calculation and should be noted
                    pass  # Most data not available from yfinance

                if z_score is not None:
                    metrics["altman_z_score"] = round(z_score, 2)
                else:
                    unavailable.append("altman_z_score")
            except Exception as e:
                logger.warning(f"Altman Z-Score calculation failed: {e}")
                unavailable.append("altman_z_score")
        else:
            unavailable.append("altman_z_score")

        # Promoter pledge (not available from yfinance)
        unavailable.append("promoter_pledge")

        result["metrics"] = metrics
        result["unavailable_metrics"] = unavailable

        # === 7. Calculate risk score and identify risk factors ===
        risk_score, risk_factors, risk_flags = _calculate_risk_score(
            metrics, ratio_output, technical_output, company_name
        )

        result["risk_score"] = risk_score
        result["risk_level"] = classify_risk_level(risk_score)
        result["risk_factors"] = risk_factors
        result["risk_flags"] = risk_flags

        # === 8. Generate summary ===
        result["summary"] = _generate_risk_summary(
            company_name, risk_score, result["risk_level"], metrics, risk_factors, risk_flags
        )

        # Set final status based on data quality
        available_metrics = len([m for m in metrics.values() if m is not None])
        total_possible = 10  # Rough count of key metrics we try to calculate

        if available_metrics < 3:
            result["status"] = "partial"
            result["error"] = f"Limited risk metrics: only {available_metrics} available. Need price and fundamental data."
            logger.warning(f"Risk assessment has limited data: {available_metrics} metrics")
        elif has_price_data and has_stock_info:
            result["status"] = "ok"
            logger.info(f"Risk assessment completed: {result['risk_level']} ({risk_score:.0f}/100)")
        else:
            result["status"] = "partial"
            result["error"] = f"Some data sources unavailable: price_data={has_price_data}, stock_info={has_stock_info}"
            logger.info("Risk assessment completed with partial data")

    except Exception as e:
        logger.error(f"Risk assessment failed for {ticker}: {e}", exc_info=True)
        result["status"] = "error"
        result["error"] = str(e)

    return result


def _calculate_risk_score(
    metrics: Dict[str, Any],
    ratio_output: Optional[Dict],
    technical_output: Optional[Dict],
    company_name: str
) -> tuple[float, List[str], List[str]]:
    """
    Calculate overall risk score and identify risk factors.

    Uses code-based scoring logic - no LLM.

    Returns:
        Tuple of (risk_score, risk_factors list, risk_flags list)
    """
    risk_score = 0.0
    risk_factors = []
    risk_flags = []

    # === Market Risk (40 points max) ===

    # Volatility (0-15 points)
    volatility = metrics.get("volatility_pct")
    if volatility is not None:
        if volatility > 40:
            risk_score += 15
            risk_factors.append(f"High volatility: {volatility:.1f}% (very volatile)")
            risk_flags.append("HIGH_VOLATILITY")
        elif volatility > 30:
            risk_score += 12
            risk_factors.append(f"Elevated volatility: {volatility:.1f}%")
        elif volatility > 20:
            risk_score += 8
            risk_factors.append(f"Moderate volatility: {volatility:.1f}%")
        else:
            risk_factors.append(f"Low volatility: {volatility:.1f}% (stable)")

    # Beta (0-10 points)
    beta = metrics.get("beta")
    if beta is not None:
        if beta > 1.5:
            risk_score += 10
            risk_factors.append(f"High beta: {beta:.2f} (50%+ more volatile than market)")
            risk_flags.append("HIGH_BETA")
        elif beta > 1.2:
            risk_score += 7
            risk_factors.append(f"Above-market beta: {beta:.2f}")
        elif beta < 0.8:
            risk_factors.append(f"Below-market beta: {beta:.2f} (defensive)")

    # Max Drawdown (0-15 points)
    max_dd = metrics.get("max_drawdown_pct")
    if max_dd is not None:
        if max_dd > 40:
            risk_score += 15
            risk_factors.append(f"Severe drawdown: {max_dd:.1f}% peak-to-trough")
            risk_flags.append("SEVERE_DRAWDOWN")
        elif max_dd > 30:
            risk_score += 12
            risk_factors.append(f"High drawdown: {max_dd:.1f}%")
        elif max_dd > 20:
            risk_score += 8
            risk_factors.append(f"Moderate drawdown: {max_dd:.1f}%")

    # === Financial Risk (40 points max) ===

    # Leverage risk (0-15 points)
    de_ratio = metrics.get("debt_to_equity")
    if de_ratio is not None:
        if de_ratio > 200:
            risk_score += 15
            risk_factors.append(f"Very high leverage: D/E {de_ratio:.0f}")
            risk_flags.append("HIGH_LEVERAGE")
        elif de_ratio > 150:
            risk_score += 12
            risk_factors.append(f"High leverage: D/E {de_ratio:.0f}")
        elif de_ratio > 100:
            risk_score += 8
            risk_factors.append(f"Moderate leverage: D/E {de_ratio:.0f}")
        else:
            risk_factors.append(f"Low leverage: D/E {de_ratio:.0f}")

    # Liquidity risk (0-10 points)
    current_ratio = metrics.get("current_ratio")
    if current_ratio is not None:
        if current_ratio < 1.0:
            risk_score += 10
            risk_factors.append(f"Liquidity concern: Current ratio {current_ratio:.2f}")
            risk_flags.append("LIQUIDITY_RISK")
        elif current_ratio < 1.5:
            risk_score += 5
            risk_factors.append(f"Tight liquidity: Current ratio {current_ratio:.2f}")

    # Valuation risk (0-15 points)
    pe_ratio = metrics.get("pe_ratio")
    pb_ratio = metrics.get("pb_ratio")
    if pe_ratio is not None and pe_ratio > 0:
        if pe_ratio > 50:
            risk_score += 10
            risk_factors.append(f"High valuation risk: P/E {pe_ratio:.1f}x")
            risk_flags.append("VALUATION_RISK")
        elif pe_ratio > 35:
            risk_score += 5
            risk_factors.append(f"Elevated valuation: P/E {pe_ratio:.1f}x")

    # === Additional Risk from other agents (20 points max) ===

    # From ratio analysis
    if ratio_output and ratio_output.get("status") == "success":
        roe = ratio_output.get("ratios", {}).get("roe_pct")
        if roe is not None and roe < 10:
            risk_score += 5
            risk_factors.append(f"Low profitability: ROE {roe:.1f}%")

    # From technical analysis
    if technical_output and technical_output.get("status") == "success":
        tech_score = technical_output.get("technical_score", 50)
        if tech_score < 30:
            risk_score += 10
            risk_factors.append("Weak technical indicators")
            risk_flags.append("WEAK_TECHNICALS")
        elif tech_score < 40:
            risk_score += 5
            risk_factors.append("Below-average technical strength")

    # Cap at 100
    risk_score = min(100, risk_score)

    return risk_score, risk_factors, risk_flags


def _generate_risk_summary(
    company_name: str,
    risk_score: float,
    risk_level: str,
    metrics: Dict[str, Any],
    risk_factors: List[str],
    risk_flags: List[str]
) -> str:
    """
    Generate risk assessment summary from computed data.

    Uses code logic only - no LLM, no hallucinated values.

    Returns:
        Summary string
    """
    summary_parts = []

    # Overall risk assessment
    summary_parts.append(
        f"{company_name} has a {risk_level} risk profile with a risk score of {risk_score:.0f}/100."
    )

    # Key risk metrics
    key_metrics = []
    if metrics.get("volatility_pct") is not None:
        key_metrics.append(f"volatility {metrics['volatility_pct']:.1f}%")
    if metrics.get("beta") is not None:
        key_metrics.append(f"beta {metrics['beta']:.2f}")
    if metrics.get("debt_to_equity") is not None:
        key_metrics.append(f"D/E {metrics['debt_to_equity']:.0f}")

    if key_metrics:
        summary_parts.append(f"Key metrics: {', '.join(key_metrics)}.")

    # Primary risks
    if risk_flags:
        primary_risks = []
        if "HIGH_VOLATILITY" in risk_flags:
            primary_risks.append("high price volatility")
        if "HIGH_LEVERAGE" in risk_flags:
            primary_risks.append("elevated debt levels")
        if "LIQUIDITY_RISK" in risk_flags:
            primary_risks.append("liquidity concerns")
        if "VALUATION_RISK" in risk_flags:
            primary_risks.append("stretched valuation")

        if primary_risks:
            summary_parts.append(f"Primary risks: {', '.join(primary_risks)}.")

    # Risk factor count
    if len(risk_factors) > 0:
        summary_parts.append(f"Identified {len(risk_factors)} risk factors for consideration.")

    return " ".join(summary_parts)
