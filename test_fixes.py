"""
Quick verification script for all fixes.
Run this to verify the fixes are working.
"""

import os
import sys

# Set up path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("FinSight Fixes Verification")
print("=" * 60)

# Test 1: yfinance without custom session
print("\n[1/5] Testing yfinance (HDFCBANK.NS)...")
try:
    import yfinance as yf
    ticker = yf.Ticker('HDFCBANK.NS')
    hist = ticker.history(period='5d')
    if len(hist) > 0:
        print(f"[PASS] Retrieved {len(hist)} days of data")
    else:
        print("[FAIL] No data returned")
except Exception as e:
    print(f"[FAIL] {e}")

# Test 2: yfinance Nifty index
print("\n[2/5] Testing yfinance (^NSEI)...")
try:
    nifty = yf.Ticker('^NSEI')
    hist = nifty.history(period='5d')
    if len(hist) > 0:
        print(f"[PASS] Retrieved {len(hist)} days of Nifty data")
    else:
        print("[FAIL] No Nifty data returned")
except Exception as e:
    print(f"[FAIL] {e}")

# Test 3: RAG company name normalization
print("\n[3/5] Testing RAG company name normalization...")
try:
    from backend.rag.retriever import _normalize_company_name

    tests = [
        ("HDFC Bank", "HDFCBANK"),
        ("Reliance Industries", "RELIANCE"),
        ("hdfc bank", "HDFCBANK"),
        ("TCS Limited", "TCS"),
    ]

    passed = 0
    for input_name, expected in tests:
        result = _normalize_company_name(input_name)
        if result == expected:
            passed += 1
            print(f"  [OK] '{input_name}' -> '{result}'")
        else:
            print(f"  [FAIL] '{input_name}' -> '{result}' (expected '{expected}')")

    if passed == len(tests):
        print(f"[PASS] All {passed}/{len(tests)} normalization tests passed")
    else:
        print(f"[PARTIAL] {passed}/{len(tests)} tests passed")

except Exception as e:
    print(f"[FAIL] {e}")

# Test 4: Verdict handles all failures
print("\n[4/5] Testing verdict failure handling...")
try:
    from backend.scoring.verdict import compute_investment_verdict

    # Simulate all agents failing
    result = compute_investment_verdict(
        news_output={"status": "error", "error": "test"},
        ratio_output={"status": "error", "error": "test"},
        technical_output={"status": "error", "error": "test"},
        risk_output={"status": "error", "error": "test"},
        filing_output={"status": "error", "error": "test"}
    )

    if result["verdict"] == "INSUFFICIENT DATA":
        print(f"[PASS] Returns 'INSUFFICIENT DATA' when all agents fail")
        print(f"  Confidence: {result['confidence']}%")
    else:
        print(f"[FAIL] Returns '{result['verdict']}' instead of 'INSUFFICIENT DATA'")

except Exception as e:
    print(f"[FAIL] {e}")

# Test 5: Scheduler config check
print("\n[5/5] Testing scheduler configuration...")
try:
    from dotenv import load_dotenv
    load_dotenv()

    scheduler_enabled = os.getenv("ENABLE_WATCHLIST_SCHEDULER", "false").lower() in ["true", "1", "yes"]

    if not scheduler_enabled:
        print(f"[PASS] Watchlist scheduler disabled by default")
        print(f"  (Set ENABLE_WATCHLIST_SCHEDULER=true to enable)")
    else:
        print(f"[INFO] Watchlist scheduler is enabled")

except Exception as e:
    print(f"[FAIL] {e}")

print("\n" + "=" * 60)
print("Verification Complete")
print("=" * 60)
print("\nTo test the full system, run: python main.py")
print("Then analyze HDFCBANK: POST /analyze with ticker=HDFCBANK")
