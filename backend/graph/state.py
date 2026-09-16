"""
FinSight State Definition for LangGraph workflow.

Defines the state structure that flows through the multi-agent pipeline.
"""

from typing import Annotated, Optional, List, Dict, Any
from datetime import datetime
from langgraph.graph import add_messages
from operator import add


def merge_dicts(existing: Optional[Dict[str, Any]], new: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Merge two dictionaries, with new values overriding existing ones."""
    if existing is None:
        return new
    if new is None:
        return existing
    return {**existing, **new}


class FinSightState(dict):
    """
    State for FinSight multi-agent analysis workflow.

    Fields:
        ticker: Stock ticker symbol (e.g., "RELIANCE")
        company_name: Full company name (e.g., "Reliance Industries")
        sector: Industry sector (optional)
        yfinance_cache: Cached yfinance data to avoid duplicate API calls
        filing_output: Output from filing_analyst agent
        ratio_output: Output from ratio_cruncher agent
        news_output: Output from news_sentinel agent
        technical_output: Output from technical_analyst agent
        risk_output: Output from risk_assessor agent
        final_report: Output from report_writer agent
        errors: List of errors encountered during workflow
        started_at: Workflow start timestamp (ISO 8601 string)
        completed_at: Workflow completion timestamp (ISO 8601 string)
    """

    ticker: str
    company_name: str
    sector: str
    yfinance_cache: Annotated[Optional[Dict[str, Any]], merge_dicts]
    filing_output: Annotated[Optional[Dict[str, Any]], merge_dicts]
    ratio_output: Annotated[Optional[Dict[str, Any]], merge_dicts]
    news_output: Annotated[Optional[Dict[str, Any]], merge_dicts]
    technical_output: Annotated[Optional[Dict[str, Any]], merge_dicts]
    risk_output: Optional[Dict[str, Any]]
    final_report: Optional[Dict[str, Any]]
    errors: Annotated[List[str], add]
    started_at: str
    completed_at: str
