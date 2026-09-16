"""
Report Writer Agent: Synthesizes multi-agent outputs into investment research report.

Uses LLM to create structured markdown report from existing agent outputs only.
No invention of financial data - only synthesis of provided information.
"""

import logging
import json
import re
import os
from typing import Dict, Any, Optional, List

from langchain_google_genai import ChatGoogleGenerativeAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_report_writer(
    ticker: str,
    company_name: str,
    filing_output: Optional[Dict] = None,
    ratio_output: Optional[Dict] = None,
    news_output: Optional[Dict] = None,
    technical_output: Optional[Dict] = None,
    risk_output: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Synthesize multi-agent outputs into comprehensive investment research report.

    Args:
        ticker: Stock ticker symbol (e.g., "RELIANCE")
        company_name: Full company name (e.g., "Reliance Industries")
        filing_output: Optional output from filing analyzer
        ratio_output: Optional output from ratio_cruncher
        news_output: Optional output from news_sentinel
        technical_output: Optional output from technical_analyst
        risk_output: Optional output from risk_assessor

    Returns:
        Dict with keys:
        - status: "success", "partial_success", or "error"
        - ticker: Stock ticker
        - company_name: Company name
        - report_markdown: Full markdown report
        - executive_summary: Brief summary
        - bull_case: Bullish arguments
        - bear_case: Bearish arguments
        - key_risks: List of key risks
        - confidence_score: Report confidence (0-100)
        - data_quality: Summary of data availability
        - sources_used: List of agent outputs used
        - missing_sections: List of missing data sources
        - error: Error message if applicable
    """
    result = {
        "status": "error",
        "ticker": ticker,
        "company_name": company_name,
        "report_markdown": "",
        "executive_summary": "",
        "bull_case": "",
        "bear_case": "",
        "key_risks": [],
        "confidence_score": 0,
        "data_quality": "",
        "sources_used": [],
        "missing_sections": [],
        "error": None
    }

    try:
        logger.info(f"Starting report generation for {ticker} ({company_name})")

        # Assess data availability
        sources_used, missing_sections, data_quality = _assess_data_quality(
            filing_output, ratio_output, news_output, technical_output, risk_output
        )

        result["sources_used"] = sources_used
        result["missing_sections"] = missing_sections
        result["data_quality"] = data_quality

        # Check if we have any data
        if not sources_used:
            logger.error("No agent outputs available for report generation")
            result["error"] = "No agent outputs available - cannot generate report"
            return result

        logger.info(f"Data available: {len(sources_used)} sources, {len(missing_sections)} missing")

        # Build context from available agent outputs
        context = _build_context(
            ticker, company_name,
            filing_output, ratio_output, news_output, technical_output, risk_output
        )

        # Generate report using LLM
        try:
            report_data = _generate_report_with_llm(
                ticker, company_name, context, sources_used, missing_sections
            )

            if report_data:
                # Extract structured data from report
                result["report_markdown"] = report_data.get("report_markdown", "")
                result["executive_summary"] = report_data.get("executive_summary", "")
                result["bull_case"] = report_data.get("bull_case", "")
                result["bear_case"] = report_data.get("bear_case", "")
                result["key_risks"] = report_data.get("key_risks", [])
                result["confidence_score"] = report_data.get("confidence_score", 50)

                # Ensure confidence_score is bounded
                result["confidence_score"] = max(0, min(100, result["confidence_score"]))

                # Set status
                if missing_sections:
                    result["status"] = "partial_success"
                    result["error"] = f"Report generated with limited data: missing {', '.join(missing_sections)}"
                else:
                    result["status"] = "success"

                logger.info(f"Report generated successfully (confidence: {result['confidence_score']})")
            else:
                # Fallback: create basic report from structured data
                logger.warning("LLM report generation failed, creating fallback report")
                fallback_report = _create_fallback_report(
                    ticker, company_name,
                    filing_output, ratio_output, news_output, technical_output, risk_output,
                    sources_used, missing_sections
                )

                result.update(fallback_report)
                result["status"] = "partial_success"
                result["error"] = "LLM synthesis failed, using structured data fallback"

        except Exception as e:
            logger.error(f"Report generation error: {e}", exc_info=True)

            # Fallback to structured report
            fallback_report = _create_fallback_report(
                ticker, company_name,
                filing_output, ratio_output, news_output, technical_output, risk_output,
                sources_used, missing_sections
            )

            result.update(fallback_report)
            result["status"] = "partial_success"
            result["error"] = f"Report synthesis error: {str(e)}, using fallback"

    except Exception as e:
        logger.error(f"Report writer failed for {ticker}: {e}", exc_info=True)
        result["status"] = "error"
        result["error"] = str(e)

    return result


def _assess_data_quality(
    filing_output: Optional[Dict],
    ratio_output: Optional[Dict],
    news_output: Optional[Dict],
    technical_output: Optional[Dict],
    risk_output: Optional[Dict]
) -> tuple[List[str], List[str], str]:
    """
    Assess which data sources are available.

    Returns:
        Tuple of (sources_used, missing_sections, data_quality_summary)
    """
    sources_used = []
    missing_sections = []

    # Check filing data
    if filing_output and filing_output.get("status") == "success":
        sources_used.append("filing_analysis")
    else:
        missing_sections.append("filing_analysis")

    # Check ratio data
    if ratio_output and ratio_output.get("status") == "success":
        sources_used.append("ratio_analysis")
    else:
        missing_sections.append("ratio_analysis")

    # Check news data
    if news_output and news_output.get("status") in ["success", "partial_success"]:
        sources_used.append("news_sentiment")
    else:
        missing_sections.append("news_sentiment")

    # Check technical data
    if technical_output and technical_output.get("status") == "success":
        sources_used.append("technical_analysis")
    else:
        missing_sections.append("technical_analysis")

    # Check risk data
    if risk_output and risk_output.get("status") in ["success", "partial_success"]:
        sources_used.append("risk_assessment")
    else:
        missing_sections.append("risk_assessment")

    # Build data quality summary
    total = len(sources_used) + len(missing_sections)
    quality_pct = (len(sources_used) / total * 100) if total > 0 else 0

    data_quality = f"{len(sources_used)}/{total} data sources available ({quality_pct:.0f}%)"

    return sources_used, missing_sections, data_quality


def _build_context(
    ticker: str,
    company_name: str,
    filing_output: Optional[Dict],
    ratio_output: Optional[Dict],
    news_output: Optional[Dict],
    technical_output: Optional[Dict],
    risk_output: Optional[Dict]
) -> str:
    """
    Build context string from available agent outputs.

    Only includes data that was actually provided - no invention.
    """
    context_parts = []

    context_parts.append(f"Company: {company_name} ({ticker})")
    context_parts.append("")

    # Filing analysis
    if filing_output and filing_output.get("status") == "success":
        context_parts.append("=== FILING ANALYSIS ===")
        context_parts.append(f"Insights: {json.dumps(filing_output.get('insights', {}), indent=2)}")
        context_parts.append("")

    # Ratio analysis
    if ratio_output and ratio_output.get("status") == "success":
        context_parts.append("=== FINANCIAL RATIOS ===")
        ratios = ratio_output.get("ratios", {})
        context_parts.append(f"Profitability: ROE {ratios.get('roe_pct')}%, ROA {ratios.get('roa_pct')}%, Net Margin {ratios.get('net_margin_pct')}%")
        context_parts.append(f"Leverage: D/E {ratios.get('debt_to_equity')}, Interest Coverage {ratios.get('interest_coverage')}x")
        context_parts.append(f"Liquidity: Current {ratios.get('current_ratio')}, Quick {ratios.get('quick_ratio')}")
        context_parts.append(f"Efficiency: Asset Turnover {ratios.get('asset_turnover')}x, Inventory Days {ratios.get('days_inventory')}")
        context_parts.append(f"Valuation: P/E {ratios.get('pe_ratio')}, P/B {ratios.get('pb_ratio')}, EV/EBITDA {ratios.get('ev_ebitda')}")
        context_parts.append("")

    # News sentiment
    if news_output and news_output.get("status") in ["success", "partial_success"]:
        context_parts.append("=== NEWS SENTIMENT ===")
        context_parts.append(f"Sentiment: {news_output.get('sentiment')} (score: {news_output.get('sentiment_score')})")
        context_parts.append(f"Articles analyzed: {news_output.get('article_count')}")

        # Story group details with confirmation status
        confirmed_count = news_output.get('confirmed_count', 0)
        unconfirmed_count = news_output.get('unconfirmed_count', 0)
        context_parts.append(f"Story groups: {confirmed_count} confirmed, {unconfirmed_count} unconfirmed")

        # Confirmed stories (high credibility, multiple trusted sources)
        story_groups = news_output.get('story_groups', [])
        confirmed_stories = [g for g in story_groups if g.get('confirmed')]
        unconfirmed_stories = [g for g in story_groups if not g.get('confirmed')]

        if confirmed_stories:
            context_parts.append("\nConfirmed Stories (≥2 trusted sources):")
            for story in confirmed_stories[:5]:
                context_parts.append(f"  • {story.get('summary')} [{story.get('sentiment')}] (confidence: {story.get('confidence_score')}%)")
                context_parts.append(f"    Sources: {', '.join(story.get('trusted_sources', []))}")

        if unconfirmed_stories:
            context_parts.append("\nUnconfirmed Stories (single source or unverified):")
            for story in unconfirmed_stories[:3]:
                context_parts.append(f"  • {story.get('summary')} [{story.get('sentiment')}] (confidence: {story.get('confidence_score')}%)")
                context_parts.append(f"    Sources: {', '.join(story.get('sources', []))}")

        # Aggregate themes from confirmed stories
        if news_output.get('key_themes'):
            context_parts.append(f"\nKey themes (from confirmed stories): {', '.join(news_output['key_themes'][:5])}")
        if news_output.get('positive_drivers'):
            context_parts.append(f"Positive drivers: {', '.join(news_output['positive_drivers'][:3])}")
        if news_output.get('negative_drivers'):
            context_parts.append(f"Negative drivers: {', '.join(news_output['negative_drivers'][:3])}")

        context_parts.append("")

    # Technical analysis
    if technical_output and technical_output.get("status") == "success":
        context_parts.append("=== TECHNICAL ANALYSIS ===")
        context_parts.append(f"Trend: {technical_output.get('trend')}, Momentum: {technical_output.get('momentum')}")
        context_parts.append(f"Technical score: {technical_output.get('technical_score')}/100")
        indicators = technical_output.get("indicators", {})
        context_parts.append(f"Price: {indicators.get('latest_price')}, RSI: {indicators.get('rsi_14')}")
        context_parts.append(f"Signals: {json.dumps(technical_output.get('signals', []))}")
        context_parts.append("")

    # Risk assessment
    if risk_output and risk_output.get("status") in ["success", "partial_success"]:
        context_parts.append("=== RISK ASSESSMENT ===")
        context_parts.append(f"Risk level: {risk_output.get('risk_level')} (score: {risk_output.get('risk_score')}/100)")
        metrics = risk_output.get("metrics", {})
        context_parts.append(f"Beta: {metrics.get('beta')}, Volatility: {metrics.get('volatility_pct')}%")
        context_parts.append(f"Max drawdown: {metrics.get('max_drawdown_pct')}%")
        if risk_output.get('risk_factors'):
            context_parts.append(f"Risk factors: {json.dumps(risk_output['risk_factors'])}")
        context_parts.append("")

    return "\n".join(context_parts)


def _generate_report_with_llm(
    ticker: str,
    company_name: str,
    context: str,
    sources_used: List[str],
    missing_sections: List[str]
) -> Optional[Dict]:
    """
    Generate investment research report using LLM synthesis.

    Returns report data dict or None if generation fails.
    """
    # Create prompt for report generation
    prompt = f"""You are a financial analyst writing an investment research report.

Based ONLY on the data provided below, synthesize a comprehensive investment research report for {company_name} ({ticker}).

CRITICAL RULES:
1. Use ONLY the data provided - do not invent any financial numbers, ratios, news, or technical indicators
2. If data is missing for a section, note it as "Data not available" rather than inventing
3. Be factual and analytical - cite specific numbers from the provided data
4. Maintain professional investment research tone
5. IMPORTANT: For news sentiment, distinguish between CONFIRMED stories (≥2 trusted sources) and UNCONFIRMED stories (single source or unverified sources)
6. Weight CONFIRMED news stories more heavily in your investment thesis - do NOT let a single UNCONFIRMED story swing the buy/hold/sell recommendation on its own
7. If presenting unconfirmed stories, explicitly label them as "unconfirmed" or "single-source"

DATA PROVIDED:
{context}

DATA AVAILABILITY:
- Sources available: {', '.join(sources_used)}
- Missing data: {', '.join(missing_sections) if missing_sections else 'None'}

Generate a structured report in JSON format with the following structure:

{{
  "executive_summary": "3-4 sentence overview of investment thesis and key findings",
  "bull_case": "Detailed bullish arguments with specific data points (200-300 words)",
  "bear_case": "Detailed bearish arguments with specific data points (200-300 words)",
  "key_risks": [
    "Specific risk 1 with data",
    "Specific risk 2 with data",
    "Specific risk 3 with data"
  ],
  "confidence_score": <integer 0-100, based on data completeness>,
  "report_markdown": "# Investment Research Report: {company_name} ({ticker})\\n\\n## Executive Summary\\n[executive_summary]\\n\\n## Financial Analysis\\n[Synthesize ratio/filing data]\\n\\n## Market Position & News\\n[Synthesize news/sentiment - clearly distinguish confirmed vs unconfirmed stories]\\n\\n## Technical Outlook\\n[Synthesize technical data]\\n\\n## Risk Assessment\\n[Synthesize risk data]\\n\\n## Investment Thesis\\n### Bull Case\\n[bull_case]\\n\\n### Bear Case\\n[bear_case]\\n\\n## Key Risks\\n[List key_risks]\\n\\n## Data Quality Note\\nThis report is based on: {', '.join(sources_used)}{'. Missing: ' + ', '.join(missing_sections) if missing_sections else ''}\\n\\n---\\n*Generated by FinSight AI*"
}}

Return ONLY the JSON object, no markdown code fences or additional text."""

    # Call LLM
    try:
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")

        # Use configurable model (defaults to gemini-2.5-flash for free tier)
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,
            timeout=120,
            google_api_key=google_api_key
        )

        logger.info("Calling LLM for report generation")
        response = llm.invoke(prompt)
        response_text = response.content.strip()

        # Strip markdown code fences
        response_text = re.sub(r'^```(?:json)?\s*\n?', '', response_text)
        response_text = re.sub(r'\n?```\s*$', '', response_text)
        response_text = response_text.strip()

        # Parse JSON
        try:
            report_data = json.loads(response_text)

            # Validate required fields
            if not all(k in report_data for k in ["executive_summary", "bull_case", "bear_case", "key_risks", "report_markdown"]):
                logger.warning("LLM response missing required fields")
                return None

            logger.info("LLM report generated successfully")
            return report_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            logger.error(f"Response text: {response_text[:500]}")
            return None

    except Exception as e:
        logger.error(f"LLM report generation failed: {e}", exc_info=True)
        return None


def _create_fallback_report(
    ticker: str,
    company_name: str,
    filing_output: Optional[Dict],
    ratio_output: Optional[Dict],
    news_output: Optional[Dict],
    technical_output: Optional[Dict],
    risk_output: Optional[Dict],
    sources_used: List[str],
    missing_sections: List[str]
) -> Dict:
    """
    Create basic fallback report from structured data when LLM fails.

    Uses only provided data - no invention.
    """
    sections = []

    sections.append(f"# Investment Research Report: {company_name} ({ticker})")
    sections.append("")
    sections.append("*Note: This report was generated from structured data without LLM synthesis.*")
    sections.append("")

    # Executive summary from available data
    summary_parts = []
    if ratio_output and ratio_output.get("status") == "success":
        ratios = ratio_output.get("ratios", {})
        summary_parts.append(f"ROE {ratios.get('roe_pct')}%, D/E {ratios.get('debt_to_equity')}")

    if news_output and news_output.get("status") in ["success", "partial_success"]:
        summary_parts.append(f"News sentiment: {news_output.get('sentiment')}")

    if technical_output and technical_output.get("status") == "success":
        summary_parts.append(f"Technical trend: {technical_output.get('trend')}")

    if risk_output and risk_output.get("status") in ["success", "partial_success"]:
        summary_parts.append(f"Risk level: {risk_output.get('risk_level')}")

    executive_summary = f"{company_name} analysis based on available data: " + ". ".join(summary_parts) + "."

    sections.append("## Executive Summary")
    sections.append(executive_summary)
    sections.append("")

    # Financial analysis
    if ratio_output and ratio_output.get("status") == "success":
        sections.append("## Financial Analysis")
        ratios = ratio_output.get("ratios", {})
        sections.append(f"- **Profitability**: ROE {ratios.get('roe_pct')}%, ROA {ratios.get('roa_pct')}%, Net Margin {ratios.get('net_margin_pct')}%")
        sections.append(f"- **Leverage**: D/E {ratios.get('debt_to_equity')}, Interest Coverage {ratios.get('interest_coverage')}x")
        sections.append(f"- **Liquidity**: Current Ratio {ratios.get('current_ratio')}, Quick Ratio {ratios.get('quick_ratio')}")
        sections.append(f"- **Valuation**: P/E {ratios.get('pe_ratio')}, P/B {ratios.get('pb_ratio')}")
        sections.append("")

    # News sentiment
    if news_output and news_output.get("status") in ["success", "partial_success"]:
        sections.append("## Market Sentiment")
        sections.append(f"- **Sentiment**: {news_output.get('sentiment')} (score: {news_output.get('sentiment_score')})")
        sections.append(f"- **Articles Analyzed**: {news_output.get('article_count')}")
        if news_output.get('key_themes'):
            sections.append(f"- **Key Themes**: {', '.join(news_output['key_themes'])}")
        sections.append("")

    # Technical analysis
    if technical_output and technical_output.get("status") == "success":
        sections.append("## Technical Analysis")
        sections.append(f"- **Trend**: {technical_output.get('trend')}")
        sections.append(f"- **Momentum**: {technical_output.get('momentum')}")
        sections.append(f"- **Technical Score**: {technical_output.get('technical_score')}/100")
        sections.append("")

    # Risk assessment
    if risk_output and risk_output.get("status") in ["success", "partial_success"]:
        sections.append("## Risk Assessment")
        sections.append(f"- **Risk Level**: {risk_output.get('risk_level')}")
        sections.append(f"- **Risk Score**: {risk_output.get('risk_score')}/100")
        if risk_output.get('risk_factors'):
            sections.append("- **Risk Factors**:")
            for factor in risk_output['risk_factors'][:5]:
                sections.append(f"  - {factor}")
        sections.append("")

    # Data quality note
    sections.append("## Data Quality")
    sections.append(f"Report based on: {', '.join(sources_used)}")
    if missing_sections:
        sections.append(f"Missing data: {', '.join(missing_sections)}")
    sections.append("")
    sections.append("---")
    sections.append("*Generated by FinSight AI*")

    report_markdown = "\n".join(sections)

    # Extract bull/bear case
    bull_case = "Based on available data, positive factors include: " + ". ".join(summary_parts[:2]) if summary_parts else "Insufficient data for bull case."
    bear_case = "Risk factors to consider based on available data." if risk_output else "Insufficient data for bear case."

    # Extract key risks
    key_risks = []
    if risk_output and risk_output.get("risk_factors"):
        key_risks = risk_output["risk_factors"][:5]

    # Calculate confidence based on data availability
    confidence_score = int((len(sources_used) / 5) * 100)

    return {
        "report_markdown": report_markdown,
        "executive_summary": executive_summary,
        "bull_case": bull_case,
        "bear_case": bear_case,
        "key_risks": key_risks,
        "confidence_score": confidence_score,
    }
