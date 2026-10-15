"""
Simple validation of yfinance fixes - no unicode characters.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

print("\n" + "="*60)
print("FinSight yfinance Fixes - Quick Validation")
print("="*60)

# Test 1: Check retry backoff configuration
print("\n[1/7] Retry Backoff Configuration")
try:
    from backend.tools.financial_tools import _retry_with_backoff
    # Check the delays list exists
    import inspect
    source = inspect.getsource(_retry_with_backoff)
    if "delays = [5.0, 15.0, 45.0]" in source:
        print("PASS: Retry delays set to 5s, 15s, 45s")
    else:
        print("FAIL: Retry delays not configured correctly")
except Exception as e:
    print(f"FAIL: {e}")

# Test 2: Check disk cache TTL
print("\n[2/7] Disk Cache TTL Configuration")
try:
    from backend.utils.yfinance_disk_cache import CACHE_TTL_MINUTES
    expected = {"price_history": 60, "nifty_history": 60, "stock_info": 1440}
    if CACHE_TTL_MINUTES == expected:
        print("PASS: Cache TTLs - price:1h, nifty:1h, info:24h")
    else:
        print(f"FAIL: {CACHE_TTL_MINUTES}")
except Exception as e:
    print(f"FAIL: {e}")

# Test 3: Check fallback source
print("\n[3/7] Fallback Price Source")
try:
    import pandas_datareader
    from backend.tools.financial_tools import _fetch_from_stooq_fallback
    print("PASS: pandas-datareader installed, fallback available")
except ImportError:
    print("FAIL: pandas-datareader not installed")

# Test 4: Check verdict logic
print("\n[4/7] Verdict Insufficient Data Logic")
try:
    from backend.scoring.verdict import compute_investment_verdict
    result = compute_investment_verdict(
        news_output=None,
        ratio_output={"status": "success", "ratios": {}},
        technical_output=None,
        risk_output=None,
        filing_output=None
    )
    if result["verdict"] == "INSUFFICIENT DATA":
        print("PASS: Returns INSUFFICIENT DATA with <3 agents")
    else:
        print(f"FAIL: Got {result['verdict']}")
except Exception as e:
    print(f"FAIL: {e}")

# Test 5: Check news dedup toggle
print("\n[5/7] News Dedup Toggle")
try:
    with open("backend/agents/news_sentinel.py", encoding="utf-8") as f:
        content = f.read()
    if "NEWS_DISABLE_DEDUP" in content and "disable_dedup" in content:
        print("PASS: NEWS_DISABLE_DEDUP toggle implemented")
    else:
        print("FAIL: Toggle not found")
except Exception as e:
    print(f"FAIL: {e}")

# Test 6: Check singleton resources
print("\n[6/7] Singleton Resources")
try:
    from backend.agents.filing_analyst import _get_llm
    from backend.rag.retriever import _get_embedding_model
    print("PASS: Singleton functions available")
except ImportError as e:
    print(f"FAIL: {e}")

# Test 7: Check workflow pre-fetch
print("\n[7/7] Workflow Pre-fetch")
try:
    with open("backend/graph/workflow.py", encoding="utf-8") as f:
        content = f.read()
    checks = [
        "_fetch_yfinance_data_node" in content,
        "yfinance_cache" in content,
        "cached_stock_info" in content,
    ]
    if all(checks):
        print("PASS: Workflow pre-fetch logic present")
    else:
        print("FAIL: Missing pre-fetch components")
except Exception as e:
    print(f"FAIL: {e}")

print("\n" + "="*60)
print("Validation Complete")
print("="*60 + "\n")
