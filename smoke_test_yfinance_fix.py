"""
Smoke test for yfinance fixes with RELIANCE ticker.
Tests curl_cffi integration, disk cache, and workflow-level caching.
"""
import sys
import os
import json
import logging

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from dotenv import load_dotenv
load_dotenv()

from backend.graph.workflow import run_analysis

def main():
    print("=" * 80)
    print("SMOKE TEST: RELIANCE with yfinance fixes")
    print("=" * 80)
    print()

    ticker = "RELIANCE"
    company_name = "Reliance Industries"

    print(f"Running analysis for {ticker} ({company_name})...")
    print()

    try:
        result = run_analysis(ticker, company_name)

        print("\n" + "=" * 80)
        print("RESULTS SUMMARY")
        print("=" * 80)

        # Check yfinance pre-fetch status
        yfinance_cache = result.get("yfinance_cache", {})
        if yfinance_cache:
            stock_info_ok = "error" not in yfinance_cache.get("stock_info", {})
            price_history_ok = "error" not in yfinance_cache.get("price_history", {})
            nifty_history_ok = "error" not in yfinance_cache.get("nifty_history", {})

            success_count = sum([stock_info_ok, price_history_ok, nifty_history_ok])

            print(f"\nyfinance Pre-fetch Status: {success_count}/3 successful")
            print(f"  - Stock Info: {'OK' if stock_info_ok else 'FAIL'}")
            print(f"  - Price History: {'OK' if price_history_ok else 'FAIL'}")
            print(f"  - Nifty History: {'OK' if nifty_history_ok else 'FAIL'}")
        else:
            print("\nWARNING: No yfinance cache data found")

        # Check agent outputs
        print(f"\nAgent Outputs:")

        ratio_output = result.get("ratio_output", {})
        ratio_status = ratio_output.get("status", "missing")
        print(f"  - Ratio Cruncher: {ratio_status}")
        if ratio_status == "success":
            ratios = ratio_output.get("ratios", {})
            print(f"    • Current Price: ₹{ratios.get('current_price')}")
            print(f"    • P/E Ratio: {ratios.get('pe_ratio')}")
            print(f"    • ROE: {ratios.get('roe_pct')}%")
            print(f"    • D/E: {ratios.get('debt_to_equity')}")

        technical_output = result.get("technical_output", {})
        technical_status = technical_output.get("status", "missing")
        print(f"\n  - Technical Analyst: {technical_status}")
        if technical_status == "success":
            print(f"    • Trend: {technical_output.get('trend')}")
            print(f"    • Momentum: {technical_output.get('momentum')}")
            print(f"    • Technical Score: {technical_output.get('technical_score')}/100")

        risk_output = result.get("risk_output", {})
        risk_status = risk_output.get("status", "missing")
        print(f"\n  - Risk Assessor: {risk_status}")
        if risk_status in ["success", "partial_success"]:
            metrics = risk_output.get("metrics", {})
            print(f"    • Risk Level: {risk_output.get('risk_level')}")
            print(f"    • Risk Score: {risk_output.get('risk_score')}/100")
            print(f"    • Beta: {metrics.get('beta')}")
            print(f"    • Volatility: {metrics.get('volatility_pct')}%")

        # Check for errors
        errors = result.get("errors", [])
        if errors:
            print(f"\nWARNING: Errors encountered: {len(errors)}")
            for i, error in enumerate(errors[:5], 1):
                print(f"  {i}. {error}")
        else:
            print(f"\nSUCCESS: No errors encountered")

        # Save full output
        output_file = "smoke_test_reliance_yfinance_fix.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\nFull output saved to: {output_file}")

        print("\n" + "=" * 80)
        print("SMOKE TEST COMPLETE")
        print("=" * 80)

        return result

    except Exception as e:
        print(f"\nERROR: SMOKE TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    main()
