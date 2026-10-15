"""
Quick validation script to test yfinance fixes.

Tests:
1. Retry backoff timing
2. Disk cache TTL configuration
3. Fallback source availability
4. Verdict scoring with insufficient data
5. News dedup toggle
6. Singleton resources in filing_analyst
"""
import os
import sys
import time
from datetime import datetime

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

def test_retry_backoff():
    """Test that retry backoff uses 5s/15s/45s schedule."""
    print("\n=== Test 1: Retry Backoff Schedule ===")
    from backend.tools.financial_tools import _retry_with_backoff

    def failing_func():
        raise Exception("429 Too Many Requests")

    start = time.time()
    try:
        _retry_with_backoff(failing_func, max_retries=3)
    except Exception:
        elapsed = time.time() - start
        # Should be ~20s (5 + 15, then gives up on 3rd)
        if 18 <= elapsed <= 22:
            print(f"✓ Retry backoff timing correct: {elapsed:.1f}s")
            return True
        else:
            print(f"✗ Retry backoff timing incorrect: {elapsed:.1f}s (expected ~20s)")
            return False


def test_disk_cache_ttl():
    """Test that disk cache has correct TTL configuration."""
    print("\n=== Test 2: Disk Cache TTL Configuration ===")
    from backend.utils.yfinance_disk_cache import CACHE_TTL_MINUTES

    expected = {
        "price_history": 60,
        "nifty_history": 60,
        "stock_info": 1440,
    }

    if CACHE_TTL_MINUTES == expected:
        print("✓ Cache TTL configuration correct")
        print(f"  - price_history: {CACHE_TTL_MINUTES['price_history']}min (1h)")
        print(f"  - nifty_history: {CACHE_TTL_MINUTES['nifty_history']}min (1h)")
        print(f"  - stock_info: {CACHE_TTL_MINUTES['stock_info']}min (24h)")
        return True
    else:
        print(f"✗ Cache TTL configuration incorrect: {CACHE_TTL_MINUTES}")
        return False


def test_fallback_source_available():
    """Test that fallback source (pandas-datareader) is available."""
    print("\n=== Test 3: Fallback Price Source ===")
    try:
        import pandas_datareader as pdr
        print(f"✓ pandas-datareader installed (v{pdr.__version__})")

        # Test that fallback function exists
        from backend.tools.financial_tools import _fetch_from_stooq_fallback
        print("✓ _fetch_from_stooq_fallback function available")
        return True
    except ImportError as e:
        print(f"✗ pandas-datareader not installed: {e}")
        return False


def test_verdict_insufficient_data():
    """Test that verdict returns INSUFFICIENT DATA when <3 agents succeed."""
    print("\n=== Test 4: Verdict Insufficient Data Handling ===")
    from backend.scoring.verdict import compute_investment_verdict

    # Simulate only 2 agents succeeding
    result = compute_investment_verdict(
        news_output={"status": "error", "error": "Failed"},
        ratio_output={"status": "success", "ratios": {"pe_ratio": 20}},
        technical_output={"status": "success", "indicators": {}, "trend": "NEUTRAL", "momentum": "NEUTRAL"},
        risk_output={"status": "error", "error": "Failed"},
        filing_output={"status": "error", "error": "Failed"}
    )

    if result["verdict"] == "INSUFFICIENT DATA":
        print("✓ Verdict correctly returns INSUFFICIENT DATA with <3 agents")
        print(f"  - Available: {5 - len(result['unavailable_components'])}/5 agents")
        return True
    else:
        print(f"✗ Verdict incorrect: {result['verdict']} (expected INSUFFICIENT DATA)")
        return False


def test_news_dedup_toggle():
    """Test that NEWS_DISABLE_DEDUP environment variable exists."""
    print("\n=== Test 5: News Dedup Toggle ===")

    # Check if the env var is referenced in news_sentinel
    try:
        with open("backend/agents/news_sentinel.py", "r", encoding="utf-8") as f:
            content = f.read()

        if "NEWS_DISABLE_DEDUP" in content and "disable_dedup" in content:
            print("✓ NEWS_DISABLE_DEDUP toggle implemented in news_sentinel.py")
            return True
        else:
            print("✗ NEWS_DISABLE_DEDUP toggle not found in news_sentinel.py")
            return False
    except Exception as e:
        print(f"✗ Error checking news_sentinel.py: {e}")
        return False


def test_singleton_resources():
    """Test that singleton resources are implemented."""
    print("\n=== Test 6: Singleton Resources ===")

    passed = True

    # Check filing_analyst LLM singleton
    try:
        from backend.agents.filing_analyst import _get_llm
        print("✓ filing_analyst _get_llm singleton function available")
    except ImportError:
        print("✗ filing_analyst _get_llm singleton not found")
        passed = False

    # Check retriever embedding singleton
    try:
        from backend.rag.retriever import _get_embedding_model
        print("✓ retriever _get_embedding_model singleton function available")
    except ImportError:
        print("✗ retriever _get_embedding_model singleton not found")
        passed = False

    return passed


def test_workflow_prefetch():
    """Test that workflow has pre-fetch logic."""
    print("\n=== Test 7: Workflow Pre-fetch Logic ===")

    try:
        with open("backend/graph/workflow.py", "r", encoding="utf-8") as f:
            content = f.read()

        checks = [
            ("_fetch_yfinance_data_node" in content, "Pre-fetch node function exists"),
            ("yfinance_cache" in content, "yfinance_cache state variable used"),
            ("cached_stock_info" in content, "Agents receive cached_stock_info"),
            ("cached_price_history" in content, "Agents receive cached_price_history"),
            ("cached_nifty_history" in content, "Agents receive cached_nifty_history"),
        ]

        all_passed = True
        for check, description in checks:
            if check:
                print(f"  ✓ {description}")
            else:
                print(f"  ✗ {description}")
                all_passed = False

        return all_passed
    except Exception as e:
        print(f"✗ Error checking workflow.py: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("FinSight yfinance Fixes Validation")
    print("=" * 60)

    tests = [
        ("Retry Backoff", test_retry_backoff),
        ("Disk Cache TTL", test_disk_cache_ttl),
        ("Fallback Source", test_fallback_source_available),
        ("Verdict Logic", test_verdict_insufficient_data),
        ("News Dedup Toggle", test_news_dedup_toggle),
        ("Singleton Resources", test_singleton_resources),
        ("Workflow Pre-fetch", test_workflow_prefetch),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"✗ {name} failed with exception: {e}")
            results.append((name, False))

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        print("\n🎉 All tests passed! Fixes implemented correctly.")
        return 0
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
