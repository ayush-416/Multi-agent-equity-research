"""
Snapshot loader for cached scraper data.

Manages disk snapshots of scraped financial data with TTL-based caching.
"""
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Snapshot directory
SNAPSHOTS_DIR = Path(__file__).parent.parent.parent / "data" / "snapshots"
SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Cache TTL: 24 hours for Screener data
SCREENER_CACHE_TTL_HOURS = 24


def _snapshot_path(ticker: str) -> Path:
    """Get snapshot file path for a ticker."""
    safe_ticker = ticker.replace(".", "_").upper()
    return SNAPSHOTS_DIR / f"{safe_ticker}.json"


def save_snapshot(data: Dict[str, Any]) -> None:
    """
    Save scraper result to disk snapshot.

    Args:
        data: Result from get_financials()
    """
    ticker = data.get("ticker")
    if not ticker:
        logger.warning("Cannot save snapshot: no ticker in data")
        return

    path = _snapshot_path(ticker)

    try:
        # Add snapshot metadata
        snapshot = {
            "_snapshot_created_at": datetime.utcnow().isoformat(),
            "_snapshot_version": "1.0",
            **data
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved snapshot: {path}")
    except Exception as e:
        logger.error(f"Failed to save snapshot for {ticker}: {e}")


def load_snapshot(ticker: str, max_age_hours: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """
    Load scraper data from disk snapshot.

    Args:
        ticker: Stock ticker (e.g., "TCS.NS" or "TCS")
        max_age_hours: Maximum age in hours (None = no limit)

    Returns:
        Snapshot data or None if not found/expired
    """
    path = _snapshot_path(ticker)

    if not path.exists():
        logger.debug(f"Snapshot not found: {path}")
        return None

    try:
        with open(path, 'r', encoding='utf-8') as f:
            snapshot = json.load(f)

        # Check age if TTL specified
        if max_age_hours is not None:
            created_at = snapshot.get("_snapshot_created_at")
            if created_at:
                created_time = datetime.fromisoformat(created_at)
                age = datetime.utcnow() - created_time
                if age > timedelta(hours=max_age_hours):
                    logger.debug(f"Snapshot expired (age: {age.total_seconds()/3600:.1f}h): {path}")
                    return None

        logger.info(f"Loaded snapshot: {path}")
        return snapshot

    except json.JSONDecodeError as e:
        logger.warning(f"Corrupted snapshot: {path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to load snapshot for {ticker}: {e}")
        return None


def get_cached_or_fetch(ticker: str, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Get financial data from cache or fetch fresh.

    Args:
        ticker: Stock ticker
        force_refresh: Skip cache and fetch fresh data

    Returns:
        Financial data dict with source attribution
    """
    from backend.scraper.india_financials import get_financials

    # Check cache first (unless force refresh)
    if not force_refresh:
        cached = load_snapshot(ticker, max_age_hours=SCREENER_CACHE_TTL_HOURS)
        if cached:
            cached["_from_cache"] = True
            return cached

    # Fetch fresh data
    logger.info(f"Fetching fresh data for {ticker}")

    # Add 3-second delay before Screener requests (rate limiting)
    time.sleep(3)

    result = get_financials(ticker)

    # Save snapshot if successful
    if result.get("tables"):
        save_snapshot(result)

    result["_from_cache"] = False
    return result


def clear_snapshot(ticker: str) -> bool:
    """
    Delete snapshot for a ticker.

    Args:
        ticker: Stock ticker

    Returns:
        True if deleted, False if not found
    """
    path = _snapshot_path(ticker)

    if path.exists():
        try:
            path.unlink()
            logger.info(f"Deleted snapshot: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete snapshot for {ticker}: {e}")
            return False

    return False


def list_snapshots() -> list:
    """
    List all available snapshots.

    Returns:
        List of dicts with ticker, age, and size info
    """
    snapshots = []

    for path in SNAPSHOTS_DIR.glob("*.json"):
        try:
            stat = path.stat()
            age_hours = (time.time() - stat.st_mtime) / 3600

            # Try to read ticker from file
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                ticker = data.get("ticker", path.stem)
                company = data.get("company", "")

            snapshots.append({
                "ticker": ticker,
                "company": company,
                "age_hours": round(age_hours, 1),
                "size_kb": round(stat.st_size / 1024, 1),
                "path": str(path)
            })
        except Exception as e:
            logger.warning(f"Failed to read snapshot {path}: {e}")

    return sorted(snapshots, key=lambda x: x["age_hours"])
