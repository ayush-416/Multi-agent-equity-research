"""
FinSight AI - FastAPI Backend

Multi-agent equity research platform for Indian stocks.
Orchestrates six specialist agents through LangGraph workflow.
"""

import logging
import math
import os
from typing import Optional, Any, Dict
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.graph.workflow import run_analysis

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
            "analyze": "/analyze (POST)"
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


# === Application Lifecycle ===


@app.on_event("startup")
async def startup_event():
    """Log application startup."""
    logger.info("=" * 60)
    logger.info("FinSight AI - Starting up")
    logger.info("Multi-agent equity research platform")
    logger.info("Version: 0.1.0")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Log application shutdown."""
    logger.info("FinSight AI - Shutting down")


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
