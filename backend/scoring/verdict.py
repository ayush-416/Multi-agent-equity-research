"""
Investment Verdict Scoring System

Converts agent outputs into deterministic scores on a fixed scale.
Each component contributes between -3 and +3, with net score between -10 and +10.
LLMs do NOT assign scores - all scoring is computed deterministically.
"""

import logging
import os
from typing import Dict, Any, List, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# === Configuration ===

def get_verdict_config() -> Dict[str, Any]:
    """
    Load verdict scoring configuration from environment or use defaults.

    Returns:
        Dict with weights and thresholds for scoring
    """
    return {
        "weights": {
            "news": float(os.getenv("VERDICT_WEIGHT_NEWS", "1.0")),
            "fundamentals": float(os.getenv("VERDICT_WEIGHT_FUNDAMENTALS", "1.0")),
            "technical": float(os.getenv("VERDICT_WEIGHT_TECHNICAL", "1.0")),
            "risk": float(os.getenv("VERDICT_WEIGHT_RISK", "1.0")),
            "filings": float(os.getenv("VERDICT_WEIGHT_FILINGS", "1.0")),
        },
        "thresholds": {
            "invest": float(os.getenv("VERDICT_THRESHOLD_INVEST", "3.0")),
            "avoid": float(os.getenv("VERDICT_THRESHOLD_AVOID", "-3.0")),
        }
    }


# === News Scoring ===

def score_news_component(news_output: Optional[Dict[str, Any]]) -> Tuple[float, str, List[str], bool]:
    """
    Score news sentiment from confirmed stories only.

    Args:
        news_output: Output from news_sentinel agent

    Returns:
        Tuple of (score, label, drivers, available)
        - score: -3.0 to +3.0
        - label: descriptive label
        - drivers: list of 2-4 explanation strings
        - available: True if data was available
    """
    if not news_output or news_output.get("status") == "error":
        return 0.0, "Unavailable", ["News data could not be fetched"], False

    drivers = []

    # Get configuration info
    config = news_output.get("config", {})
    days_back = config.get("days_back", 7)
    trusted_only = config.get("trusted_only", False)

    # Only use confirmed stories
    story_groups = news_output.get("story_groups", [])
    confirmed_stories = [s for s in story_groups if s.get("confirmed")]
    unconfirmed_stories = [s for s in story_groups if not s.get("confirmed")]

    # Add configuration info to drivers
    config_info = f"Analyzed {days_back}d window"
    if trusted_only:
        config_info += " (trusted sources only)"
    drivers.append(config_info)

    if not confirmed_stories:
        # Show that we have stories but none confirmed
        if unconfirmed_stories:
            drivers.append(f"{len(unconfirmed_stories)} unconfirmed stories (not scored)")
        else:
            drivers.append("No recent news coverage")
        return 0.0, "Neutral", drivers, True

    # Calculate weighted sentiment from confirmed stories only
    total_weight = 0.0
    total_weighted_score = 0.0

    positive_count = 0
    negative_count = 0
    neutral_count = 0

    for story in confirmed_stories:
        sentiment = story.get("sentiment", "").lower()
        confidence = story.get("confidence_score", 0.5)  # 0 to 1

        # Convert sentiment to numeric score
        if sentiment in ["positive", "bullish"]:
            story_score = 1.0
            positive_count += 1
        elif sentiment in ["negative", "bearish"]:
            story_score = -1.0
            negative_count += 1
        else:
            story_score = 0.0
            neutral_count += 1

        weighted_score = story_score * confidence
        total_weighted_score += weighted_score
        total_weight += confidence

    # Calculate average weighted sentiment
    if total_weight > 0:
        avg_sentiment = total_weighted_score / total_weight
    else:
        avg_sentiment = 0.0

    # Scale to -3 to +3 range
    # At full negative (-1.0), score = -3.0
    # At full positive (+1.0), score = +3.0
    score = avg_sentiment * 3.0

    # Generate drivers
    drivers.append(f"{len(confirmed_stories)} confirmed stories analyzed")

    if positive_count > 0:
        drivers.append(f"✓ {positive_count} positive/bullish stories")
    if negative_count > 0:
        drivers.append(f"✗ {negative_count} negative/bearish stories")
    if neutral_count > 0:
        drivers.append(f"→ {neutral_count} neutral stories")

    # Add sentiment score
    drivers.append(f"Weighted sentiment: {avg_sentiment:.2f}")

    # Determine label
    if score >= 2.0:
        label = "Very Positive"
    elif score >= 1.0:
        label = "Positive"
    elif score <= -2.0:
        label = "Very Negative"
    elif score <= -1.0:
        label = "Negative"
    else:
        label = "Neutral"

    # Mention unconfirmed stories separately
    if unconfirmed_stories:
        drivers.append(f"({len(unconfirmed_stories)} unconfirmed stories not scored)")

    return score, label, drivers[:4], True


# === Fundamentals/Ratios Scoring ===

def score_fundamentals_component(ratio_output: Optional[Dict[str, Any]]) -> Tuple[float, str, List[str], bool]:
    """
    Score fundamentals based on P/E, ROE, debt/equity, margins vs sector.

    Args:
        ratio_output: Output from ratio_cruncher agent

    Returns:
        Tuple of (score, label, drivers, available)
    """
    if not ratio_output or ratio_output.get("status") == "error":
        return 0.0, "Unavailable", ["Financial data could not be fetched"], False

    ratios = ratio_output.get("ratios", {})
    sector_benchmarks = ratio_output.get("sector_benchmarks", {})

    if not ratios:
        return 0.0, "Unavailable", ["No ratio data available"], False

    drivers = []
    score = 0.0
    component_count = 0

    # 1. P/E ratio vs sector (weight: 0.75 of component)
    pe_ratio = ratios.get("pe_ratio")
    sector_pe = sector_benchmarks.get("pe_ratio")

    if pe_ratio is not None and sector_pe is not None and sector_pe > 0:
        pe_diff_pct = ((pe_ratio - sector_pe) / sector_pe) * 100

        # Scoring: lower P/E relative to sector is better (cheaper valuation)
        # -20% or more vs sector: +0.75
        # +20% or more vs sector: -0.75
        if pe_diff_pct <= -20:
            pe_score = 0.75
        elif pe_diff_pct >= 20:
            pe_score = -0.75
        else:
            pe_score = -0.75 * (pe_diff_pct / 20)

        score += pe_score
        component_count += 1
        drivers.append(f"P/E {pe_ratio:.1f} vs sector {sector_pe:.1f} → {pe_score:+.2f}")

    # 2. ROE (weight: 0.75 of component)
    roe = ratios.get("roe_pct")
    sector_roe = sector_benchmarks.get("roe_pct")

    if roe is not None and sector_roe is not None and sector_roe > 0:
        roe_diff_pct = ((roe - sector_roe) / sector_roe) * 100

        # Scoring: higher ROE relative to sector is better
        # +20% or more vs sector: +0.75
        # -20% or more vs sector: -0.75
        if roe_diff_pct >= 20:
            roe_score = 0.75
        elif roe_diff_pct <= -20:
            roe_score = -0.75
        else:
            roe_score = 0.75 * (roe_diff_pct / 20)

        score += roe_score
        component_count += 1
        drivers.append(f"ROE {roe:.1f}% vs sector {sector_roe:.1f}% → {roe_score:+.2f}")

    # 3. Debt-to-Equity vs sector (weight: 0.75 of component)
    de_ratio = ratios.get("debt_to_equity")
    sector_de = sector_benchmarks.get("debt_to_equity")

    if de_ratio is not None and sector_de is not None and sector_de > 0:
        de_diff_pct = ((de_ratio - sector_de) / sector_de) * 100

        # Scoring: lower D/E relative to sector is better (less leverage risk)
        # -30% or more vs sector: +0.75
        # +30% or more vs sector: -0.75
        if de_diff_pct <= -30:
            de_score = 0.75
        elif de_diff_pct >= 30:
            de_score = -0.75
        else:
            de_score = -0.75 * (de_diff_pct / 30)

        score += de_score
        component_count += 1
        drivers.append(f"D/E {de_ratio:.2f} vs sector {sector_de:.2f} → {de_score:+.2f}")

    # 4. Profit margin vs sector (weight: 0.75 of component)
    profit_margin = ratios.get("profit_margins_pct")
    sector_margin = sector_benchmarks.get("profit_margins_pct")

    if profit_margin is not None and sector_margin is not None and sector_margin > 0:
        margin_diff_pct = ((profit_margin - sector_margin) / sector_margin) * 100

        # Scoring: higher margin relative to sector is better
        # +20% or more vs sector: +0.75
        # -20% or more vs sector: -0.75
        if margin_diff_pct >= 20:
            margin_score = 0.75
        elif margin_diff_pct <= -20:
            margin_score = -0.75
        else:
            margin_score = 0.75 * (margin_diff_pct / 20)

        score += margin_score
        component_count += 1
        drivers.append(f"Margin {profit_margin:.1f}% vs sector {sector_margin:.1f}% → {margin_score:+.2f}")

    # Scale to -3 to +3 range
    if component_count > 0:
        # We have 4 components each worth 0.75, total = 3.0
        final_score = score
    else:
        final_score = 0.0
        drivers.append("Insufficient data for sector comparison")

    # Ensure within bounds
    final_score = max(-3.0, min(3.0, final_score))

    # Determine label
    if final_score >= 2.0:
        label = "Strong"
    elif final_score >= 1.0:
        label = "Above Average"
    elif final_score <= -2.0:
        label = "Weak"
    elif final_score <= -1.0:
        label = "Below Average"
    else:
        label = "Average"

    return final_score, label, drivers[:4], True


# === Technical Scoring ===

def score_technical_component(technical_output: Optional[Dict[str, Any]]) -> Tuple[float, str, List[str], bool]:
    """
    Score technical indicators: trend, RSI/MACD, price vs moving averages, 52w position.

    Args:
        technical_output: Output from technical_analyst agent

    Returns:
        Tuple of (score, label, drivers, available)
    """
    if not technical_output or technical_output.get("status") == "error":
        return 0.0, "Unavailable", ["Technical data could not be fetched"], False

    indicators = technical_output.get("indicators", {})
    if not indicators:
        return 0.0, "Unavailable", ["No technical indicators available"], False

    drivers = []
    score = 0.0

    # 1. Trend (weight: 1.0)
    trend = technical_output.get("trend", "NEUTRAL").upper()
    if trend == "BULLISH":
        trend_score = 1.0
        drivers.append(f"✓ Bullish trend → +1.0")
    elif trend == "BEARISH":
        trend_score = -1.0
        drivers.append(f"✗ Bearish trend → -1.0")
    else:
        trend_score = 0.0
        drivers.append(f"→ Neutral trend → 0.0")

    score += trend_score

    # 2. RSI momentum (weight: 0.75)
    rsi = indicators.get("rsi_14")
    if rsi is not None:
        if rsi >= 70:
            rsi_score = -0.75  # Overbought - negative
            drivers.append(f"RSI {rsi:.1f} (overbought) → -0.75")
        elif rsi <= 30:
            rsi_score = 0.75  # Oversold - positive (buy opportunity)
            drivers.append(f"✓ RSI {rsi:.1f} (oversold) → +0.75")
        elif rsi >= 50:
            rsi_score = 0.25  # Moderate bullish
            drivers.append(f"RSI {rsi:.1f} (bullish) → +0.25")
        else:
            rsi_score = -0.25  # Moderate bearish
            drivers.append(f"RSI {rsi:.1f} (bearish) → -0.25")

        score += rsi_score

    # 3. Price vs 52-week high/low (weight: 0.75)
    current_price = indicators.get("latest_price")
    w52_high = indicators.get("52w_high")
    w52_low = indicators.get("52w_low")

    if current_price and w52_high and w52_low and w52_high > w52_low:
        position_pct = ((current_price - w52_low) / (w52_high - w52_low)) * 100

        # Near 52w high (>80%): slightly negative (resistance)
        # Near 52w low (<20%): positive (value opportunity)
        # Mid-range: neutral
        if position_pct >= 80:
            position_score = -0.5
            drivers.append(f"Price at {position_pct:.0f}% of 52w range (near high) → -0.5")
        elif position_pct <= 20:
            position_score = 0.75
            drivers.append(f"✓ Price at {position_pct:.0f}% of 52w range (near low) → +0.75")
        elif position_pct >= 60:
            position_score = 0.25
            drivers.append(f"Price at {position_pct:.0f}% of 52w range → +0.25")
        else:
            position_score = 0.0
            drivers.append(f"Price at {position_pct:.0f}% of 52w range → 0.0")

        score += position_score

    # 4. MACD signal (weight: 0.5)
    macd = indicators.get("macd")
    macd_signal = indicators.get("macd_signal")

    if macd is not None and macd_signal is not None:
        if macd > macd_signal and macd > 0:
            macd_score = 0.5
            drivers.append(f"✓ MACD bullish → +0.5")
        elif macd < macd_signal and macd < 0:
            macd_score = -0.5
            drivers.append(f"✗ MACD bearish → -0.5")
        else:
            macd_score = 0.0
            drivers.append(f"MACD neutral → 0.0")

        score += macd_score

    # Ensure within bounds
    score = max(-3.0, min(3.0, score))

    # Determine label
    if score >= 2.0:
        label = "Very Bullish"
    elif score >= 1.0:
        label = "Bullish"
    elif score <= -2.0:
        label = "Very Bearish"
    elif score <= -1.0:
        label = "Bearish"
    else:
        label = "Neutral"

    return score, label, drivers[:4], True


# === Risk Scoring ===

def score_risk_component(risk_output: Optional[Dict[str, Any]]) -> Tuple[float, str, List[str], bool]:
    """
    Score risk: volatility, VaR, max drawdown, beta, Z-score.
    Higher risk = negative contribution.

    Args:
        risk_output: Output from risk_assessor agent

    Returns:
        Tuple of (score, label, drivers, available)
    """
    if not risk_output or risk_output.get("status") == "error":
        return 0.0, "Unavailable", ["Risk data could not be fetched"], False

    metrics = risk_output.get("metrics", {})
    if not metrics:
        return 0.0, "Unavailable", ["No risk metrics available"], False

    drivers = []
    score = 0.0
    component_count = 0

    # 1. Volatility (weight: 0.75)
    volatility = metrics.get("volatility_pct")
    if volatility is not None:
        # Lower volatility is better
        # <20%: +0.75
        # 20-40%: 0.0
        # >60%: -0.75
        if volatility < 20:
            vol_score = 0.75
        elif volatility > 60:
            vol_score = -0.75
        else:
            # Linear interpolation between 20 and 60
            vol_score = 0.75 - (1.5 * (volatility - 20) / 40)

        score += vol_score
        component_count += 1
        drivers.append(f"Volatility {volatility:.1f}% → {vol_score:+.2f}")

    # 2. VaR (Value at Risk) (weight: 0.75)
    var_95 = metrics.get("var_95_pct")
    if var_95 is not None:
        # VaR is typically negative, showing potential loss
        # VaR better than -5%: +0.75
        # VaR worse than -10%: -0.75
        if var_95 > -5:
            var_score = 0.75
        elif var_95 < -10:
            var_score = -0.75
        else:
            # Linear interpolation
            var_score = 0.75 + (1.5 * (var_95 + 5) / 5)

        score += var_score
        component_count += 1
        drivers.append(f"VaR 95% {var_95:.1f}% → {var_score:+.2f}")

    # 3. Max Drawdown (weight: 0.75)
    max_dd = metrics.get("max_drawdown_pct")
    if max_dd is not None:
        # Lower drawdown is better
        # Better than -10%: +0.75
        # Worse than -30%: -0.75
        if max_dd > -10:
            dd_score = 0.75
        elif max_dd < -30:
            dd_score = -0.75
        else:
            # Linear interpolation
            dd_score = 0.75 + (1.5 * (max_dd + 10) / 20)

        score += dd_score
        component_count += 1
        drivers.append(f"Max drawdown {max_dd:.1f}% → {dd_score:+.2f}")

    # 4. Beta (market sensitivity) (weight: 0.75)
    beta = metrics.get("beta")
    if beta is not None:
        # Beta around 1.0 is neutral
        # Beta < 0.8: +0.75 (lower market risk)
        # Beta > 1.3: -0.75 (higher market risk)
        if beta < 0.8:
            beta_score = 0.75
        elif beta > 1.3:
            beta_score = -0.75
        elif beta < 1.0:
            beta_score = 0.75 * (1.0 - beta) / 0.2
        else:
            beta_score = -0.75 * (beta - 1.0) / 0.3

        score += beta_score
        component_count += 1
        drivers.append(f"Beta {beta:.2f} → {beta_score:+.2f}")

    # Scale to -3 to +3 range based on components found
    if component_count > 0:
        # We have 4 components each worth 0.75, total = 3.0
        final_score = score
    else:
        final_score = 0.0
        drivers.append("Insufficient risk metrics")

    # Ensure within bounds
    final_score = max(-3.0, min(3.0, final_score))

    # Determine label (inverted - higher score = lower risk)
    if final_score >= 2.0:
        label = "Low Risk"
    elif final_score >= 0.5:
        label = "Medium-Low Risk"
    elif final_score <= -2.0:
        label = "High Risk"
    elif final_score <= -0.5:
        label = "Medium-High Risk"
    else:
        label = "Medium Risk"

    return final_score, label, drivers[:4], True


# === Filings (RAG) Scoring ===

def score_filings_component(filing_output: Optional[Dict[str, Any]]) -> Tuple[float, str, List[str], bool]:
    """
    Score filings based on RAG retrieval and sentiment.
    Only scores if filing context was actually retrieved.

    Args:
        filing_output: Output from filing_analyst agent

    Returns:
        Tuple of (score, label, drivers, available)
    """
    if not filing_output or filing_output.get("status") == "error":
        return 0.0, "Unavailable", ["Filing data could not be fetched"], False

    # Check if any context was actually retrieved
    rag_status = filing_output.get("rag_status", "not_available")
    context_retrieved = filing_output.get("context_retrieved", False)

    if rag_status == "not_available" or not context_retrieved:
        return 0.0, "Unavailable", ["No filing index available"], False

    drivers = []

    # Check for key insights
    key_insights = filing_output.get("key_insights", [])
    sentiment = filing_output.get("filing_sentiment", "NEUTRAL").upper()

    if not key_insights:
        drivers.append("No significant insights from filings")
        return 0.0, "Neutral", drivers, True

    # Score based on sentiment
    # This is a simplified scoring - in production you might want more sophisticated analysis
    if sentiment == "POSITIVE":
        score = 1.5
        label = "Positive"
        drivers.append("✓ Positive filing sentiment")
    elif sentiment == "NEGATIVE":
        score = -1.5
        label = "Negative"
        drivers.append("✗ Negative filing sentiment")
    else:
        score = 0.0
        label = "Neutral"
        drivers.append("Neutral filing sentiment")

    drivers.append(f"{len(key_insights)} key insights extracted")

    # Add a sample insight
    if key_insights:
        drivers.append(f"e.g.: {key_insights[0][:60]}...")

    return score, label, drivers[:4], True


# === Main Verdict Computation ===

def compute_investment_verdict(
    news_output: Optional[Dict[str, Any]],
    ratio_output: Optional[Dict[str, Any]],
    technical_output: Optional[Dict[str, Any]],
    risk_output: Optional[Dict[str, Any]],
    filing_output: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Compute comprehensive investment verdict from all agent outputs.

    Args:
        news_output: Output from news_sentinel agent
        ratio_output: Output from ratio_cruncher agent
        technical_output: Output from technical_analyst agent
        risk_output: Output from risk_assessor agent
        filing_output: Output from filing_analyst agent

    Returns:
        Dict with:
        - verdict: INVEST/HOLD/WATCH/AVOID
        - net_score: Overall score (-10 to +10)
        - confidence: 0-100 based on data availability
        - components: List of component scores with details
        - top_positive_drivers: Top positive factors
        - top_negative_drivers: Top negative factors
        - unavailable_components: List of unavailable components
    """
    logger.info("Computing investment verdict")

    config = get_verdict_config()
    weights = config["weights"]

    components = []
    all_drivers = []
    unavailable_count = 0
    total_components = 5

    # Score each component
    news_score, news_label, news_drivers, news_available = score_news_component(news_output)
    components.append({
        "name": "News Sentiment",
        "score": news_score,
        "label": news_label,
        "drivers": news_drivers,
        "available": news_available,
        "weight": weights["news"]
    })
    if not news_available:
        unavailable_count += 1
    else:
        all_drivers.extend([(d, news_score) for d in news_drivers if "→" in d])

    fund_score, fund_label, fund_drivers, fund_available = score_fundamentals_component(ratio_output)
    components.append({
        "name": "Fundamentals",
        "score": fund_score,
        "label": fund_label,
        "drivers": fund_drivers,
        "available": fund_available,
        "weight": weights["fundamentals"]
    })
    if not fund_available:
        unavailable_count += 1
    else:
        all_drivers.extend([(d, fund_score) for d in fund_drivers if "→" in d])

    tech_score, tech_label, tech_drivers, tech_available = score_technical_component(technical_output)
    components.append({
        "name": "Technical",
        "score": tech_score,
        "label": tech_label,
        "drivers": tech_drivers,
        "available": tech_available,
        "weight": weights["technical"]
    })
    if not tech_available:
        unavailable_count += 1
    else:
        all_drivers.extend([(d, tech_score) for d in tech_drivers if "→" in d])

    risk_score, risk_label, risk_drivers, risk_available = score_risk_component(risk_output)
    components.append({
        "name": "Risk",
        "score": risk_score,
        "label": risk_label,
        "drivers": risk_drivers,
        "available": risk_available,
        "weight": weights["risk"]
    })
    if not risk_available:
        unavailable_count += 1
    else:
        all_drivers.extend([(d, risk_score) for d in risk_drivers if "→" in d])

    filing_score, filing_label, filing_drivers, filing_available = score_filings_component(filing_output)
    components.append({
        "name": "Filings",
        "score": filing_score,
        "label": filing_label,
        "drivers": filing_drivers,
        "available": filing_available,
        "weight": weights["filings"]
    })
    if not filing_available:
        unavailable_count += 1
    else:
        all_drivers.extend([(d, filing_score) for d in filing_drivers if "→" in d])

    # Calculate net score (weighted sum, excluding unavailable components)
    net_score = 0.0
    total_weight = 0.0
    available_count = 0

    for component in components:
        if component["available"]:
            net_score += component["score"] * component["weight"]
            total_weight += component["weight"]
            available_count += 1

    # If fewer than 3 components are available, return INSUFFICIENT DATA verdict
    if available_count < 3:
        logger.warning(f"Only {available_count} agent components succeeded - returning INSUFFICIENT DATA")
        return {
            "verdict": "INSUFFICIENT DATA",
            "net_score": 0.0,
            "confidence": 0.0,
            "components": components,
            "top_positive_drivers": [],
            "top_negative_drivers": [],
            "unavailable_components": [c["name"] for c in components if not c["available"]],
            "error": f"Insufficient data: only {available_count} of 5 analysis components succeeded (need at least 3)"
        }

    # Normalize if some components unavailable (maintain -10 to +10 range)
    if total_weight > 0 and total_weight < sum(weights.values()):
        # Scale up to maintain -10 to +10 range
        scale_factor = sum(weights.values()) / total_weight
        net_score *= scale_factor

    # Ensure bounds
    net_score = max(-10.0, min(10.0, net_score))

    # Calculate confidence (0-100) based on data availability
    confidence = ((total_components - unavailable_count) / total_components) * 100

    # Determine verdict
    invest_threshold = config["thresholds"]["invest"]
    avoid_threshold = config["thresholds"]["avoid"]

    if net_score >= invest_threshold:
        verdict = "INVEST"
    elif net_score <= avoid_threshold:
        verdict = "AVOID"
    elif net_score >= 0:
        verdict = "HOLD"
    else:
        verdict = "WATCH"

    # Extract top positive and negative drivers
    # Sort by absolute contribution
    positive_drivers = [(d, s) for d, s in all_drivers if s > 0]
    negative_drivers = [(d, s) for d, s in all_drivers if s < 0]

    positive_drivers.sort(key=lambda x: abs(x[1]), reverse=True)
    negative_drivers.sort(key=lambda x: abs(x[1]), reverse=True)

    top_positive = [d for d, _ in positive_drivers[:5]]
    top_negative = [d for d, _ in negative_drivers[:5]]

    # List unavailable components
    unavailable_components = [c["name"] for c in components if not c["available"]]

    result = {
        "verdict": verdict,
        "net_score": round(net_score, 2),
        "confidence": round(confidence, 1),
        "components": components,
        "top_positive_drivers": top_positive,
        "top_negative_drivers": top_negative,
        "unavailable_components": unavailable_components,
    }

    logger.info(f"Verdict computed: {verdict} (score: {net_score:.2f}, confidence: {confidence:.1f}%)")

    return result
