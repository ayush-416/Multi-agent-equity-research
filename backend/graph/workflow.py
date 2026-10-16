"""
FinSight LangGraph Workflow: Multi-agent orchestration for investment research.

Orchestrates six specialist agents in a structured pipeline:
1. Parallel execution: filing_analyst, ratio_cruncher, news_sentinel, technical_analyst
2. Sequential: risk_assessor (uses ratio + technical outputs)
3. Sequential: report_writer (synthesizes all outputs)
"""

import logging
from datetime import datetime
from typing import Dict, Any

from langgraph.graph import StateGraph, END, START
from langgraph.types import Send

from backend.graph.state import FinSightState
from backend.agents.filing_analyst import run_filing_analyst
from backend.agents.ratio_cruncher import run_ratio_cruncher
from backend.agents.news_sentinel import run_news_sentinel
from backend.agents.technical_analyst import run_technical_analyst
from backend.agents.risk_assessor import run_risk_assessor
from backend.agents.report_writer import run_report_writer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_analysis(
    ticker: str,
    company_name: str = "",
    sector: str = ""
) -> Dict[str, Any]:
    """
    Run complete FinSight investment research analysis.

    Orchestrates six specialist agents through LangGraph workflow:
    - Four parallel specialists: filing, ratio, news, technical
    - Sequential risk assessor
    - Sequential report writer

    Args:
        ticker: Stock ticker symbol (e.g., "RELIANCE" or "RELIANCE.NS")
        company_name: Full company name (optional, will fetch if empty)
        sector: Industry sector (optional)

    Returns:
        Final state dict with all agent outputs and final report
    """
    # Normalize ticker
    ticker_normalized = _normalize_ticker(ticker)

    logger.info(f"Starting FinSight analysis for {ticker_normalized} ({company_name})")

    # Initialize state
    initial_state: FinSightState = {
        "ticker": ticker_normalized,
        "company_name": company_name or ticker_normalized,
        "sector": sector,
        "yfinance_cache": None,
        "filing_output": None,
        "ratio_output": None,
        "news_output": None,
        "technical_output": None,
        "risk_output": None,
        "final_report": None,
        "errors": [],
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": ""
    }

    # Build workflow graph
    workflow = _build_workflow()

    # Compile and run
    app = workflow.compile()

    try:
        # Execute workflow
        final_state = app.invoke(initial_state)

        # Set completion time
        final_state["completed_at"] = datetime.utcnow().isoformat()

        logger.info("FinSight analysis completed")
        logger.info(f"Errors: {len(final_state.get('errors', []))}")
        logger.info(f"Final report available: {final_state.get('final_report') is not None}")

        return final_state

    except Exception as e:
        logger.error(f"Workflow execution failed: {e}", exc_info=True)
        initial_state["errors"].append(f"Workflow execution failed: {str(e)}")
        initial_state["completed_at"] = datetime.utcnow().isoformat()
        return initial_state


def _normalize_ticker(ticker: str) -> str:
    """
    Normalize ticker symbol.

    Adds .NS suffix for Indian stocks if not present.
    """
    ticker = ticker.strip().upper()

    # If already has exchange suffix, return as-is
    if "." in ticker:
        return ticker

    # For Indian market, add .NS suffix for NSE
    # Common Indian tickers: RELIANCE, TCS, INFY, HDFCBANK, etc.
    return f"{ticker}.NS"


def _build_workflow() -> StateGraph:
    """
    Build LangGraph StateGraph for FinSight analysis.

    Pipeline structure:
    START ─> fetch_yfinance_data ─> continue_to_parallel
      ├─> filing_analyst ────┐
      ├─> ratio_cruncher ────┤
      ├─> news_sentinel ─────┼─> risk_assessor ─> report_writer ─> END
      └─> technical_analyst ─┘

    The fetch_yfinance_data node pre-fetches all yfinance data once and caches it in state.
    The four specialist agents (filing, ratio, news, technical) run in parallel
    using LangGraph's conditional edges with Send API for true concurrent execution.
    """
    workflow = StateGraph(FinSightState)

    # Add data fetching node at start
    workflow.add_node("fetch_yfinance_data", _fetch_yfinance_data_node)

    # Define nodes for each agent
    workflow.add_node("filing_analyst", _filing_analyst_node)
    workflow.add_node("ratio_cruncher", _ratio_cruncher_node)
    workflow.add_node("news_sentinel", _news_sentinel_node)
    workflow.add_node("technical_analyst", _technical_analyst_node)
    workflow.add_node("risk_assessor", _risk_assessor_node)
    workflow.add_node("report_writer", _report_writer_node)

    # Define edges
    # Start by fetching yfinance data
    workflow.add_edge(START, "fetch_yfinance_data")

    # Then conditional edge that fans out to all four specialists
    workflow.add_conditional_edges("fetch_yfinance_data", _continue_to_parallel)

    # All specialists converge to risk assessor
    workflow.add_edge("filing_analyst", "risk_assessor")
    workflow.add_edge("ratio_cruncher", "risk_assessor")
    workflow.add_edge("news_sentinel", "risk_assessor")
    workflow.add_edge("technical_analyst", "risk_assessor")

    # Risk assessor to report writer
    workflow.add_edge("risk_assessor", "report_writer")

    # End workflow
    workflow.add_edge("report_writer", END)

    return workflow


# === Agent Node Functions ===


def _fetch_yfinance_data_node(state: FinSightState) -> Dict[str, Any]:
    """
    Pre-fetch all yfinance data needed by downstream agents.

    This runs once at workflow start to avoid rate limiting from multiple agents
    fetching the same data independently.
    """
    logger.info(f"Pre-fetching yfinance data for {state['ticker']}")

    from backend.tools.financial_tools import get_stock_info, get_price_history, get_nifty_history

    cache = {}
    errors = []

    # Fetch stock info (used by ratio_cruncher, risk_assessor)
    try:
        stock_info = get_stock_info.func(state["ticker"])
        cache["stock_info"] = stock_info
        if "error" in stock_info:
            errors.append(f"Stock info fetch failed: {stock_info['error']}")
            logger.warning(f"Stock info fetch failed: {stock_info['error']}")
        else:
            logger.info("Stock info fetched successfully")
    except Exception as e:
        error_msg = f"Stock info fetch exception: {str(e)}"
        errors.append(error_msg)
        logger.error(error_msg)
        cache["stock_info"] = {"error": str(e)}

    # Fetch price history (used by technical_analyst, risk_assessor)
    try:
        price_history = get_price_history.func(state["ticker"], period="1y")
        cache["price_history"] = price_history
        if "error" in price_history:
            errors.append(f"Price history fetch failed: {price_history['error']}")
            logger.warning(f"Price history fetch failed: {price_history['error']}")
        else:
            logger.info("Price history fetched successfully")
    except Exception as e:
        error_msg = f"Price history fetch exception: {str(e)}"
        errors.append(error_msg)
        logger.error(error_msg)
        cache["price_history"] = {"error": str(e)}

    # Fetch Nifty history (used by risk_assessor for beta calculation)
    try:
        nifty_history = get_nifty_history.func(period="1y")
        cache["nifty_history"] = nifty_history
        if "error" in nifty_history:
            errors.append(f"Nifty history fetch failed: {nifty_history['error']}")
            logger.warning(f"Nifty history fetch failed: {nifty_history['error']}")
        else:
            logger.info("Nifty history fetched successfully")
    except Exception as e:
        error_msg = f"Nifty history fetch exception: {str(e)}"
        errors.append(error_msg)
        logger.error(error_msg)
        cache["nifty_history"] = {"error": str(e)}

    logger.info(f"yfinance data fetch complete: {len([k for k, v in cache.items() if 'error' not in v])}/3 successful")

    return {
        "yfinance_cache": cache,
        "errors": errors
    }


def _continue_to_parallel(state: FinSightState):
    """
    Conditional edge function that dispatches to all four specialist agents in parallel.

    Returns a list of Send objects that LangGraph will execute concurrently.
    """
    return [
        Send("filing_analyst", state),
        Send("ratio_cruncher", state),
        Send("news_sentinel", state),
        Send("technical_analyst", state),
    ]


def _filing_analyst_node(state: FinSightState) -> Dict[str, Any]:
    """Run filing analyst agent."""
    logger.info(f"Running filing_analyst for {state['ticker']}")

    try:
        result = run_filing_analyst(state["ticker"], state["company_name"])

        if result.get("status") == "error":
            error_msg = f"filing_analyst error: {result.get('error', 'unknown')}"
            logger.warning(error_msg)
            return {"filing_output": result, "errors": [error_msg]}
        else:
            logger.info("filing_analyst completed successfully")
            return {"filing_output": result}

    except Exception as e:
        error_msg = f"filing_analyst exception: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "filing_output": {
                "status": "error",
                "error": str(e),
                "ticker": state["ticker"],
                "company_name": state["company_name"]
            },
            "errors": [error_msg]
        }


def _ratio_cruncher_node(state: FinSightState) -> Dict[str, Any]:
    """Run ratio cruncher agent."""
    logger.info(f"Running ratio_cruncher for {state['ticker']}")

    try:
        # Pass cached stock info if available
        cached_stock_info = None
        if state.get("yfinance_cache"):
            cached_stock_info = state["yfinance_cache"].get("stock_info")

        result = run_ratio_cruncher(
            state["ticker"],
            state["company_name"],
            cached_stock_info=cached_stock_info
        )

        if result.get("status") == "error":
            error_msg = f"ratio_cruncher error: {result.get('error', 'unknown')}"
            logger.warning(error_msg)
            return {"ratio_output": result, "errors": [error_msg]}
        else:
            logger.info("ratio_cruncher completed successfully")
            return {"ratio_output": result}

    except Exception as e:
        error_msg = f"ratio_cruncher exception: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "ratio_output": {
                "status": "error",
                "error": str(e),
                "ticker": state["ticker"],
                "company_name": state["company_name"]
            },
            "errors": [error_msg]
        }


def _news_sentinel_node(state: FinSightState) -> Dict[str, Any]:
    """Run news sentinel agent."""
    logger.info(f"Running news_sentinel for {state['ticker']}")

    try:
        result = run_news_sentinel(state["ticker"], state["company_name"], use_history_dedup=False)

        if result.get("status") == "error":
            error_msg = f"news_sentinel error: {result.get('error', 'unknown')}"
            logger.warning(error_msg)
            return {"news_output": result, "errors": [error_msg]}
        else:
            logger.info("news_sentinel completed successfully")
            return {"news_output": result}

    except Exception as e:
        error_msg = f"news_sentinel exception: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "news_output": {
                "status": "error",
                "error": str(e),
                "ticker": state["ticker"],
                "company_name": state["company_name"]
            },
            "errors": [error_msg]
        }


def _technical_analyst_node(state: FinSightState) -> Dict[str, Any]:
    """Run technical analyst agent."""
    logger.info(f"Running technical_analyst for {state['ticker']}")

    try:
        # Pass cached price history if available
        cached_price_history = None
        if state.get("yfinance_cache"):
            cached_price_history = state["yfinance_cache"].get("price_history")

        result = run_technical_analyst(
            state["ticker"],
            state["company_name"],
            cached_price_history=cached_price_history
        )

        if result.get("status") == "error":
            error_msg = f"technical_analyst error: {result.get('error', 'unknown')}"
            logger.warning(error_msg)
            return {"technical_output": result, "errors": [error_msg]}
        else:
            logger.info("technical_analyst completed successfully")
            return {"technical_output": result}

    except Exception as e:
        error_msg = f"technical_analyst exception: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "technical_output": {
                "status": "error",
                "error": str(e),
                "ticker": state["ticker"],
                "company_name": state["company_name"]
            },
            "errors": [error_msg]
        }


def _risk_assessor_node(state: FinSightState) -> Dict[str, Any]:
    """Run risk assessor agent (uses ratio and technical outputs)."""
    logger.info(f"Running risk_assessor for {state['ticker']}")

    try:
        # Pass cached yfinance data if available
        cached_stock_info = None
        cached_price_history = None
        cached_nifty_history = None
        if state.get("yfinance_cache"):
            cached_stock_info = state["yfinance_cache"].get("stock_info")
            cached_price_history = state["yfinance_cache"].get("price_history")
            cached_nifty_history = state["yfinance_cache"].get("nifty_history")

        result = run_risk_assessor(
            ticker=state["ticker"],
            company_name=state["company_name"],
            ratio_output=state.get("ratio_output"),
            technical_output=state.get("technical_output"),
            cached_stock_info=cached_stock_info,
            cached_price_history=cached_price_history,
            cached_nifty_history=cached_nifty_history
        )

        if result.get("status") == "error":
            error_msg = f"risk_assessor error: {result.get('error', 'unknown')}"
            logger.warning(error_msg)
            return {"risk_output": result, "errors": [error_msg]}
        else:
            logger.info("risk_assessor completed successfully")
            return {"risk_output": result}

    except Exception as e:
        error_msg = f"risk_assessor exception: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "risk_output": {
                "status": "error",
                "error": str(e),
                "ticker": state["ticker"],
                "company_name": state["company_name"]
            },
            "errors": [error_msg]
        }


def _report_writer_node(state: FinSightState) -> Dict[str, Any]:
    """Run report writer agent (synthesizes all outputs)."""
    logger.info(f"Running report_writer for {state['ticker']}")

    try:
        result = run_report_writer(
            ticker=state["ticker"],
            company_name=state["company_name"],
            filing_output=state.get("filing_output"),
            ratio_output=state.get("ratio_output"),
            news_output=state.get("news_output"),
            technical_output=state.get("technical_output"),
            risk_output=state.get("risk_output")
        )

        if result.get("status") == "error":
            error_msg = f"report_writer error: {result.get('error', 'unknown')}"
            logger.warning(error_msg)
            return {"final_report": result, "errors": [error_msg]}
        else:
            logger.info("report_writer completed successfully")
            return {"final_report": result}

    except Exception as e:
        error_msg = f"report_writer exception: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "final_report": {
                "status": "error",
                "error": str(e),
                "ticker": state["ticker"],
                "company_name": state["company_name"]
            },
            "errors": [error_msg]
        }
