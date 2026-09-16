"""
Simple smoke test - ASCII only output
"""
import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

from backend.graph.workflow import run_analysis

def main():
    print("=" * 80)
    print("YFINANCE FIX SMOKE TEST - RELIANCE")
    print("=" * 80)

    result = run_analysis("RELIANCE", "Reliance Industries")

    # Save to file first
    with open('smoke_test_output.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, default=str)

    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)

    # Check yfinance pre-fetch
    cache = result.get("yfinance_cache", {})
    stock_ok = "error" not in cache.get("stock_info", {})
    price_ok = "error" not in cache.get("price_history", {})
    nifty_ok = "error" not in cache.get("nifty_history", {})
    success_count = sum([stock_ok, price_ok, nifty_ok])

    print(f"\nyfinance Pre-fetch: {success_count}/3 successful")
    print(f"  Stock Info: {'OK' if stock_ok else 'FAIL'}")
    print(f"  Price History: {'OK' if price_ok else 'FAIL'}")
    print(f"  Nifty History: {'OK' if nifty_ok else 'FAIL'}")

    # Agent outputs
    ratio_out = result.get("ratio_output", {})
    tech_out = result.get("technical_output", {})
    risk_out = result.get("risk_output", {})

    print(f"\nAgent Outputs:")
    print(f"  Ratio Cruncher: {ratio_out.get('status', 'missing')}")
    if ratio_out.get("status") == "success":
        ratios = ratio_out.get("ratios", {})
        print(f"    Current Price: Rs {ratios.get('current_price')}")
        print(f"    P/E: {ratios.get('pe_ratio')}")
        print(f"    ROE: {ratios.get('roe_pct')}%")
        print(f"    D/E: {ratios.get('debt_to_equity')}")

    print(f"\n  Technical Analyst: {tech_out.get('status', 'missing')}")
    if tech_out.get("status") == "success":
        print(f"    Trend: {tech_out.get('trend')}")
        print(f"    Momentum: {tech_out.get('momentum')}")
        print(f"    Score: {tech_out.get('technical_score')}/100")

    print(f"\n  Risk Assessor: {risk_out.get('status', 'missing')}")
    if risk_out.get("status") in ["success", "partial_success"]:
        metrics = risk_out.get("metrics", {})
        print(f"    Risk Level: {risk_out.get('risk_level')}")
        print(f"    Risk Score: {risk_out.get('risk_score')}/100")
        print(f"    Beta: {metrics.get('beta')}")
        print(f"    Volatility: {metrics.get('volatility_pct')}%")

    errors = result.get("errors", [])
    print(f"\nErrors: {len(errors)}")

    print(f"\nFull output saved to: smoke_test_output.json")
    print("=" * 80)

if __name__ == "__main__":
    main()
