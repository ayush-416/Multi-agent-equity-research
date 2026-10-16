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


def _is_valid_stock_info(data: Any) -> bool:
    """
    Check if stock_info data has required key fields.

    Must have either currentPrice or marketCap, AND sector.

    Args:
        data: Stock info dict

    Returns:
        True if valid, False otherwise
    """
    if not isinstance(data, dict):
        return False

    # Must have price or market cap
    has_price_data = data.get("current_price") is not None or data.get("market_cap") is not None

    # Must have sector
    has_sector = bool(data.get("sector"))

    return has_price_data and has_sector


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

        # Validate stock_info has key fields before returning
        if cache_type == "stock_info":
            cached_data = data["data"]
            if not _is_valid_stock_info(cached_data):
                age_minutes = (time.time() - data["_cached_at"]) / 60
                source = cached_data.get("source", "unknown")
                logger.warning(
                    f"Invalid stock_info cache for {ticker} (source: {source}, age: {age_minutes:.1f}min) - "
                    f"missing key fields (currentPrice/marketCap + sector)"
                )
                return None

        # Check TTL based on cache type
        ttl_minutes = CACHE_TTL_MINUTES.get(cache_type, DEFAULT_CACHE_TTL_MINUTES)
        age_minutes = (time.time() - data["_cached_at"]) / 60
        if age_minutes > ttl_minutes:
            logger.debug(f"Yfinance cache expired for {cache_type}/{ticker} (age: {age_minutes:.1f}min, TTL: {ttl_minutes}min)")
            return None

        # Log source and age for cache hits
        cached_data = data["data"]
        source = cached_data.get("source", "unknown") if isinstance(cached_data, dict) else "unknown"
        logger.info(f"Yfinance disk cache HIT for {cache_type}/{ticker} (source: {source}, age: {age_minutes:.1f}min)")
        return cached_data

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


def purge_invalid_cache() -> int:
    """
    Purge invalid stock_info cache entries (missing key fields).

    Returns:
        Number of invalid entries purged
    """
    if not YFINANCE_CACHE_DIR.exists():
        return 0

    purged = 0
    try:
        # Only check stock_info files
        files = list(YFINANCE_CACHE_DIR.glob("stock_info_*.json"))

        for file in files:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Check if data is valid
                if "data" in data and not _is_valid_stock_info(data["data"]):
                    ticker = data.get("_ticker", "unknown")
                    source = data["data"].get("source", "unknown") if isinstance(data.get("data"), dict) else "unknown"
                    logger.info(f"Purging invalid cache: {file.name} (ticker: {ticker}, source: {source})")
                    file.unlink()
                    purged += 1

            except Exception as e:
                logger.warning(f"Error checking cache file {file.name}: {e}")
                # Delete corrupted files too
                file.unlink()
                purged += 1

        logger.info(f"Purged {purged} invalid stock_info cache entries")
        return purged

    except Exception as e:
        logger.error(f"Error during cache purge: {e}")
        return purged


# CLI interface
if __name__ == "__main__":
    import sys
    import argparse

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    parser = argparse.ArgumentParser(description="yfinance disk cache management")
    parser.add_argument("action", choices=["clear", "purge", "purge-ticker"],
                        help="Action to perform: clear (all), purge (invalid), purge-ticker (specific ticker)")
    parser.add_argument("--ticker", help="Ticker to clear (for clear/purge-ticker actions)")
    args = parser.parse_args()

    if args.action == "clear":
        clear_cache(args.ticker)
        print(f"Cache cleared" + (f" for {args.ticker}" if args.ticker else ""))

    elif args.action == "purge":
        count = purge_invalid_cache()
        print(f"Purged {count} invalid cache entries")

    elif args.action == "purge-ticker":
        if not args.ticker:
            print("Error: --ticker required for purge-ticker action")
            sys.exit(1)
        clear_cache(args.ticker)
        print(f"Purged cache for {args.ticker}")
