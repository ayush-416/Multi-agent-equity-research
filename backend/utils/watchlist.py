"""
Watchlist storage for stock tracking feature.

Simple JSON-based storage for tracking stocks, check times, and sentiment status.
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

WATCHLIST_FILE = Path("data/watchlist.json")


def _ensure_watchlist_file():
    """Ensure watchlist file and directory exist."""
    WATCHLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not WATCHLIST_FILE.exists():
        WATCHLIST_FILE.write_text(json.dumps({"stocks": []}, indent=2))


def get_watchlist() -> List[Dict[str, Any]]:
    """
    Get all stocks in the watchlist.

    Returns:
        List of dicts with keys: ticker, company_name, added_at, last_check_at,
        last_sentiment, last_story_count, confirmed_negative_count
    """
    _ensure_watchlist_file()

    try:
        with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("stocks", [])
    except Exception as e:
        logger.error(f"Failed to read watchlist: {e}")
        return []


def add_to_watchlist(ticker: str, company_name: str = None) -> Dict[str, Any]:
    """
    Add a stock to the watchlist.

    Args:
        ticker: Stock ticker (e.g., "RELIANCE")
        company_name: Full company name (optional)

    Returns:
        The added stock entry
    """
    _ensure_watchlist_file()

    ticker = ticker.strip().upper()
    watchlist = get_watchlist()

    # Check if already exists
    for stock in watchlist:
        if stock["ticker"] == ticker:
            logger.info(f"Stock {ticker} already in watchlist")
            return stock

    # Create new entry
    new_stock = {
        "ticker": ticker,
        "company_name": company_name or ticker,
        "added_at": datetime.utcnow().isoformat(),
        "last_check_at": None,
        "last_sentiment": None,
        "last_story_count": 0,
        "confirmed_negative_count": 0,
        "seen_story_ids": []  # Track seen story IDs to detect new stories
    }

    watchlist.append(new_stock)

    # Save
    try:
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            json.dump({"stocks": watchlist}, f, indent=2)
        logger.info(f"Added {ticker} to watchlist")
        return new_stock
    except Exception as e:
        logger.error(f"Failed to add {ticker} to watchlist: {e}")
        raise


def remove_from_watchlist(ticker: str) -> bool:
    """
    Remove a stock from the watchlist.

    Args:
        ticker: Stock ticker to remove

    Returns:
        True if removed, False if not found
    """
    _ensure_watchlist_file()

    ticker = ticker.strip().upper()
    watchlist = get_watchlist()

    # Find and remove
    original_len = len(watchlist)
    watchlist = [s for s in watchlist if s["ticker"] != ticker]

    if len(watchlist) == original_len:
        logger.warning(f"Stock {ticker} not found in watchlist")
        return False

    # Save
    try:
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            json.dump({"stocks": watchlist}, f, indent=2)
        logger.info(f"Removed {ticker} from watchlist")
        return True
    except Exception as e:
        logger.error(f"Failed to remove {ticker} from watchlist: {e}")
        raise


def update_stock_status(
    ticker: str,
    last_check_at: str = None,
    last_sentiment: str = None,
    last_story_count: int = None,
    confirmed_negative_count: int = None,
    seen_story_ids: List[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Update the status of a stock in the watchlist.

    Args:
        ticker: Stock ticker
        last_check_at: ISO timestamp of last check
        last_sentiment: Last sentiment detected (e.g., "positive", "negative", "neutral")
        last_story_count: Number of stories found in last check
        confirmed_negative_count: Number of confirmed negative stories found
        seen_story_ids: List of story IDs that have been seen

    Returns:
        Updated stock entry or None if not found
    """
    _ensure_watchlist_file()

    ticker = ticker.strip().upper()
    watchlist = get_watchlist()

    # Find and update
    updated = False
    for stock in watchlist:
        if stock["ticker"] == ticker:
            if last_check_at is not None:
                stock["last_check_at"] = last_check_at
            if last_sentiment is not None:
                stock["last_sentiment"] = last_sentiment
            if last_story_count is not None:
                stock["last_story_count"] = last_story_count
            if confirmed_negative_count is not None:
                stock["confirmed_negative_count"] = confirmed_negative_count
            if seen_story_ids is not None:
                stock["seen_story_ids"] = seen_story_ids
            updated = True
            break

    if not updated:
        logger.warning(f"Stock {ticker} not found in watchlist for update")
        return None

    # Save
    try:
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            json.dump({"stocks": watchlist}, f, indent=2)
        logger.debug(f"Updated status for {ticker}")
        return next(s for s in watchlist if s["ticker"] == ticker)
    except Exception as e:
        logger.error(f"Failed to update {ticker} status: {e}")
        raise


def get_stock_from_watchlist(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Get a single stock from the watchlist.

    Args:
        ticker: Stock ticker

    Returns:
        Stock entry or None if not found
    """
    ticker = ticker.strip().upper()
    watchlist = get_watchlist()

    for stock in watchlist:
        if stock["ticker"] == ticker:
            return stock

    return None
