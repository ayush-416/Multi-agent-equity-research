#!/usr/bin/env python3
"""
Test data source availability for a given ticker.

Tests which data sources are working:
1. yfinance stock_info
2. yfinance price_history
3. yfinance nifty_history
4. india_financials (Screener)
5. Snapshot (disk cache)

Usage:
    python scripts/test_data_sources.py RELIANCE
    python scripts/test_data_sources.py TCS.NS
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import logging
from backend.tools.financial_tools import get_stock_info, get_price_history, get_nifty_history
from backend.scraper.india_financials import get_financials
from backend.scraper.snapshot_loader import load_snapshot
from backend.utils.snapshot_parser import parse_snapshot_to_stock_info

logging.basicConfig(level=logging.WARNING)  # Suppress info logs
logger = logging.getLogger(__name__)


def test_ticker(ticker: str):
    """Test all data sources for a ticker."""
    print(f"\n{'='*60}")
    print(f"Testing data sources for: {ticker}")
    print(f"{'='*60}\n")

    results = {}

    # Normalize ticker
    if not ticker.endswith('.NS') and not ticker.endswith('.BO'):
        ticker_ns = f"{ticker}.NS"
    else:
        ticker_ns = ticker

    base_ticker = ticker_ns.replace('.NS', '').replace('.BO', '')

    # 1. Test yfinance stock_info
    print("1. yfinance stock_info...")
    try:
        stock_info = get_stock_info.func(ticker_ns)
        if "error" in stock_info:
            print(f"   ❌ FAILED: {stock_info['error']}")
            results['stock_info'] = False
        else:
            source = stock_info.get('source', 'unknown')
            fields = len([k for k, v in stock_info.items() if v is not None])
            print(f"   ✓ SUCCESS (source: {source}, {fields} fields)")
            results['stock_info'] = True
            # Show some key fields
            print(f"     - Current Price: {stock_info.get('current_price')}")
            print(f"     - Market Cap (Cr): {stock_info.get('market_cap_cr')}")
            print(f"     - ROE %: {stock_info.get('roe_pct')}")
            print(f"     - P/E Ratio: {stock_info.get('pe_ratio')}")
    except Exception as e:
        print(f"   ❌ EXCEPTION: {e}")
        results['stock_info'] = False

    # 2. Test yfinance price_history
    print("\n2. yfinance price_history...")
    try:
        price_hist = get_price_history.func(ticker_ns, period="1y")
        if "error" in price_hist:
            print(f"   ❌ FAILED: {price_hist['error']}")
            results['price_history'] = False
        else:
            source = price_hist.get('source', 'yfinance')
            count = len(price_hist.get('dates', []))
            print(f"   ✓ SUCCESS (source: {source}, {count} days)")
            results['price_history'] = True
            print(f"     - Latest Price: {price_hist.get('latest_price')}")
            print(f"     - Return %: {price_hist.get('price_return_pct')}")
    except Exception as e:
        print(f"   ❌ EXCEPTION: {e}")
        results['price_history'] = False

    # 3. Test yfinance nifty_history
    print("\n3. yfinance nifty_history...")
    try:
        nifty_hist = get_nifty_history.func(period="1y")
        if "error" in nifty_hist:
            print(f"   ❌ FAILED: {nifty_hist['error']}")
            results['nifty_history'] = False
        else:
            source = nifty_hist.get('source', 'yfinance')
            count = len(nifty_hist.get('dates', []))
            print(f"   ✓ SUCCESS (source: {source}, {count} days)")
            results['nifty_history'] = True
    except Exception as e:
        print(f"   ❌ EXCEPTION: {e}")
        results['nifty_history'] = False

    # 4. Test india_financials (Screener)
    print("\n4. india_financials (Screener)...")
    try:
        financials = get_financials(base_ticker, source='screener')
        if not financials.get('tables'):
            errors = financials.get('errors', [])
            print(f"   ❌ FAILED: No tables returned")
            if errors:
                print(f"     - Errors: {errors}")
            results['india_financials'] = False
        else:
            sources = financials.get('sources', [])
            tables = list(financials.get('tables', {}).keys())
            print(f"   ✓ SUCCESS (sources: {sources})")
            print(f"     - Tables: {len(tables)} ({', '.join(tables[:3])}...)")
            results['india_financials'] = True
    except Exception as e:
        print(f"   ❌ EXCEPTION: {e}")
        results['india_financials'] = False

    # 5. Test snapshot
    print("\n5. Snapshot (disk cache)...")
    try:
        snapshot = load_snapshot(ticker_ns, max_age_hours=None)
        if not snapshot:
            print(f"   ❌ NOT FOUND")
            results['snapshot'] = False
        else:
            # Parse snapshot
            parsed = parse_snapshot_to_stock_info(snapshot)
            fields = len([k for k, v in parsed.items() if v is not None])
            age = snapshot.get('_snapshot_created_at', 'unknown')
            print(f"   ✓ SUCCESS ({fields} fields)")
            print(f"     - Created: {age}")
            print(f"     - ROE %: {parsed.get('roe_pct')}")
            print(f"     - Revenue (Cr): {parsed.get('revenue_cr')}")
            results['snapshot'] = True
    except Exception as e:
        print(f"   ❌ EXCEPTION: {e}")
        results['snapshot'] = False

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY:")
    print(f"{'='*60}")
    success_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    print(f"✓ {success_count}/{total_count} data sources succeeded\n")

    for source, succeeded in results.items():
        status = "✓" if succeeded else "❌"
        print(f"  {status} {source}")

    print()

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_data_sources.py TICKER")
        print("Example: python scripts/test_data_sources.py RELIANCE")
        sys.exit(1)

    ticker = sys.argv[1]
    test_ticker(ticker)
