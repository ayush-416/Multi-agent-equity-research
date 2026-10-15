"""
FinSight AI - FastAPI Backend

Multi-agent equity research platform for Indian stocks.
Orchestrates six specialist agents through LangGraph workflow.
"""

import logging
import math
import os
from typing import Optional, Any, Dict, List
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.graph.workflow import run_analysis
from backend.utils.watchlist import (
    get_watchlist,
    add_to_watchlist,
    remove_from_watchlist,
    update_stock_status,
    get_stock_from_watchlist
)
from backend.agents.news_sentinel import run_news_sentinel
from backend.utils.alerting import should_send_alert, send_alert_email
from backend.scoring.verdict import compute_investment_verdict
from backend.scoring.narrative import generate_narrative_explanation

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# === Helper Functions ===


def sanitize_for_json(obj: Any) -> Any:
    """
    Recursively sanitize an object for JSON serialization.

    Converts NaN and Infinity to None to prevent JSON encoding errors.
    """
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    else:
        return obj

# Create FastAPI app
app = FastAPI(
    title="FinSight AI",
    description="Multi-agent equity research platform for Indian stocks",
    version="0.1.0"
)

# Add CORS middleware for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Request/Response Models ===


class AnalysisRequest(BaseModel):
    """Request model for stock analysis."""
    ticker: str = Field(..., description="Stock ticker symbol (e.g., RELIANCE, TCS, INFY)")
    company_name: Optional[str] = Field(None, description="Full company name (optional)")
    sector: Optional[str] = Field(None, description="Industry sector (optional)")

    class Config:
        json_schema_extra = {
            "example": {
                "ticker": "RELIANCE",
                "company_name": "Reliance Industries",
                "sector": "Energy"
            }
        }


class WatchlistAddRequest(BaseModel):
    """Request model for adding stock to watchlist."""
    ticker: str = Field(..., description="Stock ticker symbol")
    company_name: Optional[str] = Field(None, description="Full company name (optional)")

    class Config:
        json_schema_extra = {
            "example": {
                "ticker": "RELIANCE",
                "company_name": "Reliance Industries"
            }
        }


class WatchlistRemoveRequest(BaseModel):
    """Request model for removing stock from watchlist."""
    ticker: str = Field(..., description="Stock ticker symbol to remove")

    class Config:
        json_schema_extra = {
            "example": {
                "ticker": "RELIANCE"
            }
        }


# === Endpoints ===


@app.get("/")
async def root():
    """
    Root endpoint - API information and available endpoints.
    """
    return {
        "service": "FinSight AI",
        "description": "Multi-agent equity research platform for Indian stocks",
        "version": "0.1.0",
        "endpoints": {
            "health": "/health",
            "analyze": "/analyze (POST)",
            "watchlist": "/watchlist (GET)",
            "watchlist_add": "/watchlist/add (POST)",
            "watchlist_remove": "/watchlist/remove (POST)"
        },
        "documentation": "/docs",
        "github": "https://github.com/yourusername/finsight"
    }


@app.get("/health")
async def health():
    """
    Health check endpoint.

    Returns service status and version information.
    """
    return {
        "status": "healthy",
        "service": "FinSight AI",
        "version": "0.1.0",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/analyze")
async def analyze(request: AnalysisRequest):
    """
    Run comprehensive investment research analysis.

    Orchestrates six specialist agents:
    - Filing Analyst: Analyzes SEC/company filings
    - Ratio Cruncher: Calculates financial ratios
    - News Sentinel: Sentiment analysis on recent news
    - Technical Analyst: Technical indicators and signals
    - Risk Assessor: Market and financial risk metrics
    - Report Writer: Synthesizes comprehensive investment report

    Args:
        request: AnalysisRequest with ticker and optional company_name/sector

    Returns:
        Complete workflow state with all agent outputs and final report

    Raises:
        HTTPException 400: Invalid ticker format
        HTTPException 500: Backend workflow execution error
    """
    ticker = request.ticker.strip()
    company_name = request.company_name or ""
    sector = request.sector or ""

    # Validate ticker
    if not ticker:
        logger.warning("Empty ticker received")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ticker symbol is required"
        )

    if len(ticker) > 20:
        logger.warning(f"Invalid ticker length: {ticker}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ticker symbol too long (max 20 characters)"
        )

    logger.info(f"Starting analysis for {ticker} ({company_name})")

    try:
        # Run multi-agent analysis workflow
        result = run_analysis(
            ticker=ticker,
            company_name=company_name,
            sector=sector
        )

        logger.info(f"Analysis completed for {ticker}")
        logger.info(f"Errors: {len(result.get('errors', []))}")
        logger.info(f"Report generated: {result.get('final_report') is not None}")

        # Compute investment verdict
        try:
            logger.info(f"Computing investment verdict for {ticker}")
            verdict_result = compute_investment_verdict(
                news_output=result.get("news_output"),
                ratio_output=result.get("ratio_output"),
                technical_output=result.get("technical_output"),
                risk_output=result.get("risk_output"),
                filing_output=result.get("filing_output")
            )

            # Generate narrative explanation
            narrative = generate_narrative_explanation(
                ticker=result.get("ticker", ticker),
                company_name=result.get("company_name", company_name),
                verdict_result=verdict_result
            )
            verdict_result["narrative"] = narrative

            # Add disclaimer
            verdict_result["disclaimer"] = "This analysis is for informational purposes only and does not constitute financial advice. Consult a qualified financial advisor before making investment decisions."

            result["investment_verdict"] = verdict_result
            logger.info(f"Verdict computed: {verdict_result['verdict']} (score: {verdict_result['net_score']})")

        except Exception as e:
            logger.error(f"Failed to compute verdict: {e}", exc_info=True)
            result["investment_verdict"] = {
                "error": f"Verdict computation failed: {str(e)}",
                "verdict": "UNKNOWN",
                "net_score": 0.0,
                "confidence": 0.0
            }

        # Sanitize result to handle NaN/Infinity values
        sanitized_result = sanitize_for_json(result)

        return sanitized_result

    except ValueError as e:
        # Invalid input from workflow (e.g., ticker normalization issues)
        logger.error(f"Invalid input for {ticker}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except Exception as e:
        # Unexpected backend error
        logger.error(f"Analysis failed for {ticker}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )


@app.get("/watchlist")
async def get_watchlist_endpoint():
    """
    Get all stocks in the watchlist.

    Returns:
        List of tracked stocks with their status
    """
    try:
        watchlist = get_watchlist()
        return {
            "status": "success",
            "count": len(watchlist),
            "stocks": watchlist
        }
    except Exception as e:
        logger.error(f"Failed to get watchlist: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve watchlist: {str(e)}"
        )


@app.post("/watchlist/add")
async def add_to_watchlist_endpoint(request: WatchlistAddRequest):
    """
    Add a stock to the watchlist.

    Args:
        request: WatchlistAddRequest with ticker and optional company_name

    Returns:
        The added stock entry
    """
    ticker = request.ticker.strip().upper()
    company_name = request.company_name or ticker

    try:
        stock = add_to_watchlist(ticker, company_name)
        logger.info(f"Added {ticker} to watchlist")
        return {
            "status": "success",
            "message": f"Added {ticker} to watchlist",
            "stock": stock
        }
    except Exception as e:
        logger.error(f"Failed to add {ticker} to watchlist: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add to watchlist: {str(e)}"
        )


@app.post("/watchlist/remove")
async def remove_from_watchlist_endpoint(request: WatchlistRemoveRequest):
    """
    Remove a stock from the watchlist.

    Args:
        request: WatchlistRemoveRequest with ticker

    Returns:
        Success status
    """
    ticker = request.ticker.strip().upper()

    try:
        removed = remove_from_watchlist(ticker)
        if removed:
            logger.info(f"Removed {ticker} from watchlist")
            return {
                "status": "success",
                "message": f"Removed {ticker} from watchlist"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stock {ticker} not found in watchlist"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove {ticker} from watchlist: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove from watchlist: {str(e)}"
        )


# === Background Scheduler ===

# Create scheduler
scheduler = AsyncIOScheduler()


async def check_watchlist_stocks():
    """
    Background job: Check all watchlist stocks for news updates.

    Runs every 10 minutes. For each stock, runs News Sentinel agent
    and sends alerts if confirmed negative news is found.
    """
    logger.info("Starting watchlist check...")

    try:
        watchlist = get_watchlist()

        if not watchlist:
            logger.info("Watchlist is empty, nothing to check")
            return

        logger.info(f"Checking {len(watchlist)} stocks in watchlist")

        for stock in watchlist:
            ticker = stock["ticker"]
            company_name = stock["company_name"]
            seen_story_ids = stock.get("seen_story_ids", [])

            logger.info(f"Checking news for {ticker}...")

            try:
                # Run News Sentinel agent (lightweight check)
                news_result = run_news_sentinel(ticker, company_name)

                if news_result.get("status") in ["success", "partial_success"]:
                    story_groups = news_result.get("story_groups", [])
                    sentiment = news_result.get("sentiment", "neutral")
                    article_count = news_result.get("article_count", 0)

                    # Check if we should alert
                    should_alert, new_negative_stories, all_story_ids = should_send_alert(
                        story_groups, seen_story_ids
                    )

                    # Count confirmed negatives
                    confirmed_negative_count = len([
                        s for s in story_groups
                        if s.get("confirmed") and s.get("sentiment", "").lower() in ["negative", "bearish"]
                    ])

                    # Update stock status
                    update_stock_status(
                        ticker=ticker,
                        last_check_at=datetime.utcnow().isoformat(),
                        last_sentiment=sentiment,
                        last_story_count=len(story_groups),
                        confirmed_negative_count=confirmed_negative_count,
                        seen_story_ids=all_story_ids
                    )

                    # Send alert if needed
                    if should_alert:
                        logger.warning(f"ALERT: {len(new_negative_stories)} new confirmed negative stories for {ticker}")
                        send_alert_email(ticker, company_name, new_negative_stories)
                    else:
                        logger.info(f"No new alerts for {ticker} (checked {article_count} articles)")

                else:
                    logger.warning(f"News check failed for {ticker}: {news_result.get('error')}")

            except Exception as e:
                logger.error(f"Error checking {ticker}: {e}", exc_info=True)
                continue

        logger.info("Watchlist check complete")

    except Exception as e:
        logger.error(f"Watchlist check failed: {e}", exc_info=True)


# === Application Lifecycle ===


@app.on_event("startup")
async def startup_event():
    """Start application and background scheduler."""
    logger.info("=" * 60)
    logger.info("FinSight AI - Starting up")
    logger.info("Multi-agent equity research platform")
    logger.info("Version: 0.1.0")
    logger.info("=" * 60)

    # Start background scheduler only if enabled
    enable_scheduler = os.getenv("ENABLE_WATCHLIST_SCHEDULER", "false").lower() in ["true", "1", "yes"]

    if enable_scheduler:
        try:
            scheduler.add_job(
                check_watchlist_stocks,
                trigger=IntervalTrigger(minutes=10),
                id="watchlist_checker",
                name="Check watchlist for news updates",
                replace_existing=True
            )
            scheduler.start()
            logger.info("✓ Background scheduler started - checking watchlist every 10 minutes")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}", exc_info=True)
    else:
        logger.info("⊘ Background scheduler disabled (set ENABLE_WATCHLIST_SCHEDULER=true to enable)")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown application and stop scheduler."""
    logger.info("FinSight AI - Shutting down")

    # Stop scheduler if it was started
    enable_scheduler = os.getenv("ENABLE_WATCHLIST_SCHEDULER", "false").lower() in ["true", "1", "yes"]
    if enable_scheduler:
        try:
            scheduler.shutdown()
            logger.info("✓ Background scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")


# === Run Server ===
# To run this server, use:
#   uvicorn main:app --port 8000 --reload
# or with production settings:
#   uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

if __name__ == "__main__":
    import uvicorn
    # This block only runs when main.py is executed directly
    # In production, use uvicorn CLI instead
    uvicorn.run(app, host="0.0.0.0", port=8000)
