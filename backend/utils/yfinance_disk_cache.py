"""
On-disk cache for yfinance data with short TTL (15-30 minutes).

This provides a safety net during development when Yahoo Finance blocks requests.
Separate from the main cache to use a shorter TTL appropriate for market data.
"""
import json
import os
import time
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Separate cache directory for yfinance data
YFINANCE_CACHE_DIR = Path("data/yfinance_cache")
# TTL for different data types (in minutes)
CACHE_TTL_MINUTES = {
    "price_history": 60,  # 1 hour for price data
    "nifty_history": 60,  # 1 hour for market index
    "stock_info": 1440,   # 24 hours for fundamental info
}
# Default TTL if type not specified
DEFAULT_CACHE_TTL_MINUTES = 60


def _cache_path(cache_type: str, ticker: str, period: str = None) -> Path:
    """
    Generate cache file path for yfinance data.

    Args:
        cache_type: "stock_info", "price_history", or "nifty_history"
        ticker: Stock ticker (e.g., "RELIANCE.NS")
        period: Time period for history (e.g., "1y"), optional
    """
    safe_ticker = ticker.replace(".", "_").replace("/", "_")
    if period:
        filename = f"{cache_type}_{safe_ticker}_{period}.json"
    else:
        filename = f"{cache_type}_{safe_ticker}.json"
    return YFINANCE_CACHE_DIR / filename


def get_cached_data(cache_type: str, ticker: str, period: str = None) -> Optional[Any]:
    """
    Get cached yfinance data if it exists and is not expired.

    Args:
        cache_type: "stock_info", "price_history", or "nifty_history"
        ticker: Stock ticker
        period: Time period for history, optional

    Returns:
        Cached data if valid, None otherwise
    """
    path = _cache_path(cache_type, ticker, period)
    if not path.exists():
        return None

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Check structure
        if not isinstance(data, dict) or "_cached_at" not in data or "data" not in data:
            logger.warning(f"Corrupted yfinance cache for {cache_type}/{ticker}, ignoring")
            return None

        # Check TTL based on cache type
        ttl_minutes = CACHE_TTL_MINUTES.get(cache_type, DEFAULT_CACHE_TTL_MINUTES)
        age_minutes = (time.time() - data["_cached_at"]) / 60
        if age_minutes > ttl_minutes:
            logger.debug(f"Yfinance cache expired for {cache_type}/{ticker} (age: {age_minutes:.1f}min, TTL: {ttl_minutes}min)")
            return None

        logger.info(f"Yfinance disk cache HIT for {cache_type}/{ticker} (age: {age_minutes:.1f}min)")
        return data["data"]

    except json.JSONDecodeError as e:
        logger.warning(f"Corrupted yfinance cache JSON for {cache_type}/{ticker}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error reading yfinance cache for {cache_type}/{ticker}: {e}")
        return None


def set_cached_data(cache_type: str, ticker: str, data: Any, period: str = None) -> None:
    """
    Cache yfinance data to disk.

    Args:
        cache_type: "stock_info", "price_history", or "nifty_history"
        ticker: Stock ticker
        data: Data to cache (must be JSON-serializable)
        period: Time period for history, optional
    """
    YFINANCE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(cache_type, ticker, period)

    try:
        cache_entry = {
            "_cached_at": time.time(),
            "_cache_type": cache_type,
            "_ticker": ticker,
            "_period": period,
            "data": data
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(cache_entry, f, indent=2)

        logger.debug(f"Cached yfinance {cache_type} for {ticker} to disk")
    except Exception as e:
        logger.warning(f"Failed to cache yfinance data for {cache_type}/{ticker}: {e}")


def clear_cache(ticker: str = None) -> None:
    """
    Clear yfinance cache files.

    Args:
        ticker: If provided, only clear cache for this ticker. Otherwise clear all.
    """
    if not YFINANCE_CACHE_DIR.exists():
        return

    try:
        if ticker:
            safe_ticker = ticker.replace(".", "_").replace("/", "_")
            pattern = f"*_{safe_ticker}*.json"
            files = list(YFINANCE_CACHE_DIR.glob(pattern))
        else:
            files = list(YFINANCE_CACHE_DIR.glob("*.json"))

        for file in files:
            file.unlink()
            logger.debug(f"Deleted cache file: {file.name}")

        logger.info(f"Cleared {len(files)} yfinance cache files" + (f" for {ticker}" if ticker else ""))
    except Exception as e:
        logger.warning(f"Error clearing yfinance cache: {e}")
