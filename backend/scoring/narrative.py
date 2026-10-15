"""
Narrative explanation generator for Investment Verdict.

Uses Gemini LLM to generate plain-English explanation of the verdict,
with fallback to template-based generation if LLM fails.
"""

import logging
import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_narrative_explanation(
    ticker: str,
    company_name: str,
    verdict_result: Dict[str, Any]
) -> str:
    """
    Generate plain-English explanation of the investment verdict.

    Args:
        ticker: Stock ticker symbol
        company_name: Company name
        verdict_result: Result from compute_investment_verdict()

    Returns:
        String explanation in markdown format
    """
    try:
        # Try LLM-based generation first
        return _generate_with_llm(ticker, company_name, verdict_result)
    except Exception as e:
        logger.warning(f"LLM narrative generation failed: {e}, falling back to template")
        # Fall back to template
        return _generate_with_template(ticker, company_name, verdict_result)


def _generate_with_llm(
    ticker: str,
    company_name: str,
    verdict_result: Dict[str, Any]
) -> str:
    """
    Generate narrative using Gemini LLM.

    Args:
        ticker: Stock ticker symbol
        company_name: Company name
        verdict_result: Verdict computation result

    Returns:
        Narrative explanation
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    # Get model from environment
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set")

    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0.3,
        max_tokens=500
    )

    # Build prompt with computed data
    prompt = _build_llm_prompt(ticker, company_name, verdict_result)

    # Call LLM
    response = llm.invoke(prompt)
    narrative = response.content.strip()

    logger.info("Generated narrative explanation using LLM")
    return narrative


def _build_llm_prompt(
    ticker: str,
    company_name: str,
    verdict_result: Dict[str, Any]
) -> str:
    """
    Build prompt for LLM narrative generation.

    Args:
        ticker: Stock ticker
        company_name: Company name
        verdict_result: Verdict result

    Returns:
        Prompt string
    """
    verdict = verdict_result["verdict"]
    net_score = verdict_result["net_score"]
    confidence = verdict_result["confidence"]
    components = verdict_result["components"]
    top_positive = verdict_result["top_positive_drivers"]
    top_negative = verdict_result["top_negative_drivers"]

    prompt = f"""You are an investment analyst writing a brief explanation of an investment verdict for {company_name} ({ticker}).

**Verdict**: {verdict}
**Net Score**: {net_score:.2f} / 10
**Confidence**: {confidence:.1f}%

**Component Scores**:
"""

    for component in components:
        if component["available"]:
            prompt += f"- {component['name']}: {component['score']:+.2f} ({component['label']})\n"
        else:
            prompt += f"- {component['name']}: Unavailable\n"

    if top_positive:
        prompt += f"\n**Top Positive Factors**:\n"
        for driver in top_positive[:3]:
            prompt += f"- {driver}\n"

    if top_negative:
        prompt += f"\n**Top Negative Factors**:\n"
        for driver in top_negative[:3]:
            prompt += f"- {driver}\n"

    prompt += """
Write a 2-3 paragraph plain-English explanation of why this verdict was reached. Reference ONLY the numbers and factors provided above - do not invent any data. Be direct and concise.

Your explanation:"""

    return prompt


def _generate_with_template(
    ticker: str,
    company_name: str,
    verdict_result: Dict[str, Any]
) -> str:
    """
    Generate narrative using template (fallback).

    Args:
        ticker: Stock ticker
        company_name: Company name
        verdict_result: Verdict result

    Returns:
        Template-based narrative
    """
    verdict = verdict_result["verdict"]
    net_score = verdict_result["net_score"]
    confidence = verdict_result["confidence"]
    components = verdict_result["components"]
    top_positive = verdict_result["top_positive_drivers"]
    top_negative = verdict_result["top_negative_drivers"]

    # Verdict explanation
    if verdict == "INVEST":
        verdict_text = f"Based on our multi-factor analysis, {company_name} ({ticker}) receives an **INVEST** rating with a net score of **{net_score:+.2f}/10**."
    elif verdict == "AVOID":
        verdict_text = f"Based on our multi-factor analysis, {company_name} ({ticker}) receives an **AVOID** rating with a net score of **{net_score:+.2f}/10**."
    elif verdict == "HOLD":
        verdict_text = f"Based on our multi-factor analysis, {company_name} ({ticker}) receives a **HOLD** rating with a net score of **{net_score:+.2f}/10**."
    else:  # WATCH
        verdict_text = f"Based on our multi-factor analysis, {company_name} ({ticker}) receives a **WATCH** rating with a net score of **{net_score:+.2f}/10**."

    # Confidence statement
    available_count = sum(1 for c in components if c["available"])
    total_count = len(components)

    if confidence >= 80:
        confidence_text = f"This assessment has **high confidence** ({confidence:.1f}%) with {available_count}/{total_count} data components available."
    elif confidence >= 50:
        confidence_text = f"This assessment has **moderate confidence** ({confidence:.1f}%) with {available_count}/{total_count} data components available."
    else:
        confidence_text = f"This assessment has **limited confidence** ({confidence:.1f}%) due to incomplete data ({available_count}/{total_count} components available)."

    # Build component summary
    strong_components = [c for c in components if c["available"] and c["score"] >= 1.5]
    weak_components = [c for c in components if c["available"] and c["score"] <= -1.5]

    component_text = ""
    if strong_components:
        names = ", ".join([c["name"] for c in strong_components])
        component_text += f"Strong positive signals from {names}. "
    if weak_components:
        names = ", ".join([c["name"] for c in weak_components])
        component_text += f"Concerning signals from {names}. "

    if not component_text:
        component_text = "Mixed signals across all components. "

    # Build driver summary
    driver_text = ""
    if top_positive:
        driver_text += "**Key strengths**: "
        driver_text += "; ".join(top_positive[:2]) + ". "

    if top_negative:
        driver_text += "**Key concerns**: "
        driver_text += "; ".join(top_negative[:2]) + ". "

    # Combine
    narrative = f"{verdict_text} {confidence_text}\n\n{component_text}{driver_text}"

    logger.info("Generated narrative explanation using template")
    return narrative
