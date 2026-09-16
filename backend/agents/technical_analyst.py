"""
Technical Analyst Agent: Analyzes technical indicators and generates trading signals.

Uses computed technical indicators from technical_tools and applies code-based
signal generation logic. No LLM usage - pure technical analysis.
"""

import logging
from typing import Dict, Any, List

from backend.tools.technical_tools import compute_technical_indicators

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_technical_analyst(ticker: str, company_name: str, cached_price_history: dict = None) -> Dict[str, Any]:
    """
    Analyze technical indicators and generate trading signals.

    Args:
        ticker: Stock ticker symbol (e.g., "RELIANCE")
        company_name: Full company name (e.g., "Reliance Industries")
        cached_price_history: Pre-fetched price history from workflow state (optional)

    Returns:
        Dict with keys:
        - status: "success" or "error"
        - ticker: Stock ticker
        - company_name: Company name
        - trend: Trend signal (BULLISH, BEARISH, NEUTRAL)
        - momentum: Momentum signal (OVERBOUGHT, OVERSOLD, NEUTRAL)
        - technical_score: Overall technical score (0-100)
        - indicators: Dict of computed indicator values
        - signals: List of generated trading signals
        - support_resistance: Dict with support/resistance levels
        - summary: Technical analysis summary
        - error: Error message if applicable
    """
    result = {
        "status": "error",
        "ticker": ticker,
        "company_name": company_name,
        "trend": "NEUTRAL",
        "momentum": "NEUTRAL",
        "technical_score": 50.0,
        "indicators": {},
        "signals": [],
        "support_resistance": {},
        "summary": "",
        "error": None
    }

    try:
        logger.info(f"Starting technical analysis for {ticker} ({company_name})")

        # Compute technical indicators (pass cached price history if available)
        tech_data = compute_technical_indicators(ticker, period="1y", cached_price_history=cached_price_history)

        if "error" in tech_data:
            logger.error(f"Technical indicators computation failed: {tech_data['error']}")
            result["error"] = tech_data["error"]
            return result

        logger.info(f"Computed technical indicators for {ticker}")

        # Extract and organize indicators
        indicators = {
            "latest_price": tech_data.get("current_price"),
            "sma_20": tech_data.get("sma_20"),
            "sma_50": tech_data.get("sma_50"),
            "sma_200": tech_data.get("sma_200"),
            "ema_12": tech_data.get("ema_12"),
            "ema_26": tech_data.get("ema_26"),
            "macd": tech_data.get("macd"),
            "macd_signal": tech_data.get("macd_signal"),
            "macd_histogram": tech_data.get("macd_histogram"),
            "rsi_14": tech_data.get("rsi"),
            "volume_average": tech_data.get("volume_avg_20d"),
            "latest_volume": tech_data.get("latest_volume"),
            "price_return_pct": tech_data.get("price_return_pct"),
            "52w_high": tech_data.get("52w_high"),
            "52w_low": tech_data.get("52w_low"),
        }

        result["indicators"] = indicators

        # Extract trend and momentum from computed data
        result["trend"] = tech_data.get("trend", "NEUTRAL")
        result["momentum"] = tech_data.get("momentum", "NEUTRAL")
        result["technical_score"] = tech_data.get("technical_score", 50.0)

        # Extract support and resistance
        result["support_resistance"] = {
            "support_20d": tech_data.get("support_20d"),
            "resistance_20d": tech_data.get("resistance_20d"),
            "52w_high": tech_data.get("52w_high"),
            "52w_low": tech_data.get("52w_low"),
        }

        # Generate signals from computed indicators (code-based, no LLM)
        signals = _generate_signals(indicators, result["trend"], result["momentum"])
        result["signals"] = signals

        # Generate summary from computed data
        result["summary"] = _generate_summary(
            company_name=company_name,
            trend=result["trend"],
            momentum=result["momentum"],
            technical_score=result["technical_score"],
            indicators=indicators,
            support_resistance=result["support_resistance"]
        )

        result["status"] = "success"
        logger.info(f"Technical analysis completed: {result['trend']} trend, score {result['technical_score']:.0f}/100")

    except Exception as e:
        logger.error(f"Technical analysis failed for {ticker}: {e}", exc_info=True)
        result["status"] = "error"
        result["error"] = str(e)

    return result


def _generate_signals(
    indicators: Dict[str, Any],
    trend: str,
    momentum: str
) -> List[str]:
    """
    Generate trading signals based on computed indicators.

    Uses code logic only - no LLM, no hallucination.

    Returns:
        List of signal strings
    """
    signals = []

    latest_price = indicators.get("latest_price")
    sma_20 = indicators.get("sma_20")
    sma_50 = indicators.get("sma_50")
    sma_200 = indicators.get("sma_200")
    macd = indicators.get("macd")
    macd_signal = indicators.get("macd_signal")
    rsi = indicators.get("rsi_14")

    # Price vs SMA signals
    if latest_price and sma_20:
        if latest_price > sma_20:
            signals.append(f"Price ${latest_price:.2f} above 20-day SMA ${sma_20:.2f} (bullish)")
        else:
            signals.append(f"Price ${latest_price:.2f} below 20-day SMA ${sma_20:.2f} (bearish)")

    if latest_price and sma_50:
        if latest_price > sma_50:
            signals.append(f"Price above 50-day SMA ${sma_50:.2f} (uptrend)")
        else:
            signals.append(f"Price below 50-day SMA ${sma_50:.2f} (downtrend)")

    # SMA crossover signals
    if sma_20 and sma_50:
        if sma_20 > sma_50:
            signals.append(f"20-day SMA above 50-day SMA (golden cross - bullish)")
        else:
            signals.append(f"20-day SMA below 50-day SMA (death cross - bearish)")

    # Long-term trend
    if latest_price and sma_200:
        if latest_price > sma_200:
            signals.append(f"Price above 200-day SMA ${sma_200:.2f} (long-term uptrend)")
        else:
            signals.append(f"Price below 200-day SMA ${sma_200:.2f} (long-term downtrend)")

    # MACD signals
    if macd is not None and macd_signal is not None:
        if macd > macd_signal:
            signals.append(f"MACD {macd:.2f} above signal {macd_signal:.2f} (bullish momentum)")
        else:
            signals.append(f"MACD {macd:.2f} below signal {macd_signal:.2f} (bearish momentum)")

    # RSI signals
    if rsi is not None:
        if rsi > 70:
            signals.append(f"RSI {rsi:.1f} overbought (>70) - potential pullback")
        elif rsi < 30:
            signals.append(f"RSI {rsi:.1f} oversold (<30) - potential bounce")
        else:
            signals.append(f"RSI {rsi:.1f} in neutral zone (30-70)")

    # Overall signal
    if trend == "BULLISH" and momentum != "OVERBOUGHT":
        signals.append("Overall: BULLISH trend with favorable momentum")
    elif trend == "BEARISH" and momentum != "OVERSOLD":
        signals.append("Overall: BEARISH trend with negative momentum")
    elif trend == "BULLISH" and momentum == "OVERBOUGHT":
        signals.append("Overall: BULLISH but overbought - caution advised")
    elif trend == "BEARISH" and momentum == "OVERSOLD":
        signals.append("Overall: BEARISH but oversold - potential reversal")
    else:
        signals.append("Overall: NEUTRAL trend - no clear directional bias")

    return signals


def _generate_summary(
    company_name: str,
    trend: str,
    momentum: str,
    technical_score: float,
    indicators: Dict[str, Any],
    support_resistance: Dict[str, Any]
) -> str:
    """
    Generate technical analysis summary from computed data.

    Uses code logic only - no LLM, no hallucinated values.

    Returns:
        Summary string
    """
    summary_parts = []

    # Overall assessment
    summary_parts.append(
        f"{company_name} shows a {trend} trend with {momentum} momentum. "
        f"Technical score: {technical_score:.0f}/100."
    )

    # Price position
    latest_price = indicators.get("latest_price")
    sma_50 = indicators.get("sma_50")
    if latest_price and sma_50:
        position = "above" if latest_price > sma_50 else "below"
        pct_diff = abs((latest_price / sma_50 - 1) * 100)
        summary_parts.append(
            f"Price ${latest_price:.2f} is {position} 50-day SMA by {pct_diff:.1f}%."
        )

    # RSI
    rsi = indicators.get("rsi_14")
    if rsi is not None:
        if rsi > 70:
            summary_parts.append(f"RSI at {rsi:.1f} indicates overbought conditions.")
        elif rsi < 30:
            summary_parts.append(f"RSI at {rsi:.1f} indicates oversold conditions.")
        else:
            summary_parts.append(f"RSI at {rsi:.1f} is in neutral territory.")

    # Support/Resistance
    support = support_resistance.get("support_20d")
    resistance = support_resistance.get("resistance_20d")
    if support and resistance and latest_price:
        summary_parts.append(
            f"20-day support at ${support:.2f}, resistance at ${resistance:.2f}."
        )

    # Performance
    price_return = indicators.get("price_return_pct")
    if price_return is not None:
        direction = "up" if price_return > 0 else "down"
        summary_parts.append(
            f"1-year return: {direction} {abs(price_return):.1f}%."
        )

    return " ".join(summary_parts)
