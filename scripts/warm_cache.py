"""
Warm cache script - pre-fetch scraper data for demo tickers.

Usage:
    python scripts/warm_cache.py
"""
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.scraper.india_financials import get_financials
from backend.scraper.snapshot_loader import save_snapshot

# Demo tickers
DEMO_TICKERS = [
    "RELIANCE",
    "HDFCBANK",
    "INFY",
    "TCS",
    "WIPRO",
]


def warm_cache():
    """Fetch and cache data for all demo tickers."""
    print("=" * 60)
    print("FinSight Cache Warmer")
    print("=" * 60)
    print(f"\nFetching data for {len(DEMO_TICKERS)} tickers...")
    print("Note: 3-second delay between requests for Screener rate limiting\n")

    results = []

    for i, ticker in enumerate(DEMO_TICKERS, 1):
        print(f"[{i}/{len(DEMO_TICKERS)}] Fetching {ticker}...")

        try:
            # Fetch data
            data = get_financials(ticker, source="both")

            # Save snapshot
            if data.get("tables"):
                save_snapshot(data)
                print(f"  ✓ Success: {len(data['tables'])} tables from {', '.join(data['sources'])}")
                results.append({
                    "ticker": ticker,
                    "status": "success",
                    "tables": len(data["tables"]),
                    "sources": data["sources"]
                })
            else:
                print(f"  ✗ Failed: {', '.join(data.get('errors', ['Unknown error']))}")
                results.append({
                    "ticker": ticker,
                    "status": "failed",
                    "errors": data.get("errors", [])
                })

        except Exception as e:
            print(f"  ✗ Error: {e}")
            results.append({
                "ticker": ticker,
                "status": "error",
                "error": str(e)
            })

        # Rate limiting delay (except for last ticker)
        if i < len(DEMO_TICKERS):
            print("  Waiting 3 seconds...")
            time.sleep(3)

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    success_count = sum(1 for r in results if r["status"] == "success")
    print(f"\nTotal: {len(results)} tickers")
    print(f"Success: {success_count}")
    print(f"Failed: {len(results) - success_count}")

    print("\nDetails:")
    for result in results:
        ticker = result["ticker"]
        status = result["status"]

        if status == "success":
            tables = result["tables"]
            sources = ", ".join(result["sources"])
            print(f"  ✓ {ticker:12} - {tables} tables ({sources})")
        else:
            errors = result.get("errors", [result.get("error", "Unknown")])
            print(f"  ✗ {ticker:12} - {errors[0] if errors else 'Failed'}")

    print("\nCache ready for use!")


if __name__ == "__main__":
    warm_cache()
