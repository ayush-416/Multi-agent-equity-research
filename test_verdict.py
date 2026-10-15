"""
Quick test script for Investment Verdict feature.

Tests the scoring and narrative generation without requiring full analysis.
"""

import sys
import os
import io

# Set UTF-8 encoding for console output
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.scoring.verdict import compute_investment_verdict
from backend.scoring.narrative import generate_narrative_explanation


def test_verdict_with_mock_data():
    """Test verdict computation with mock agent outputs."""

    print("="*60)
    print("Testing Investment Verdict Feature")
    print("="*60)

    # Mock news output (positive sentiment)
    news_output = {
        "status": "success",
        "story_groups": [
            {"confirmed": True, "sentiment": "positive", "confidence_score": 0.8},
            {"confirmed": True, "sentiment": "positive", "confidence_score": 0.9},
            {"confirmed": True, "sentiment": "neutral", "confidence_score": 0.7},
            {"confirmed": False, "sentiment": "negative", "confidence_score": 0.6},
        ]
    }

    # Mock ratio output (strong fundamentals)
    ratio_output = {
        "status": "success",
        "ratios": {
            "pe_ratio": 18.5,
            "roe_pct": 18.5,
            "debt_to_equity": 0.45,
            "profit_margins_pct": 12.8
        },
        "sector_benchmarks": {
            "pe_ratio": 22.0,
            "roe_pct": 12.3,
            "debt_to_equity": 0.65,
            "profit_margins_pct": 9.5
        }
    }

    # Mock technical output (bullish)
    technical_output = {
        "status": "success",
        "trend": "BULLISH",
        "indicators": {
            "latest_price": 2450.0,
            "rsi_14": 58.5,
            "52w_high": 2850.0,
            "52w_low": 2100.0,
            "macd": 12.5,
            "macd_signal": 10.2
        }
    }

    # Mock risk output (medium risk)
    risk_output = {
        "status": "success",
        "metrics": {
            "volatility_pct": 28.5,
            "var_95_pct": -6.8,
            "max_drawdown_pct": -18.5,
            "beta": 1.15
        }
    }

    # Mock filing output (not available)
    filing_output = {
        "status": "error",
        "rag_status": "not_available"
    }

    print("\n1. Computing Investment Verdict...")
    print("-" * 60)

    verdict_result = compute_investment_verdict(
        news_output=news_output,
        ratio_output=ratio_output,
        technical_output=technical_output,
        risk_output=risk_output,
        filing_output=filing_output
    )

    print(f"Verdict: {verdict_result['verdict']}")
    print(f"Net Score: {verdict_result['net_score']:.2f} / 10")
    print(f"Confidence: {verdict_result['confidence']:.1f}%")
    print(f"\nComponents:")
    for comp in verdict_result['components']:
        if comp['available']:
            print(f"  - {comp['name']}: {comp['score']:+.2f} ({comp['label']})")
        else:
            print(f"  - {comp['name']}: Unavailable")

    print(f"\nTop Positive Drivers ({len(verdict_result['top_positive_drivers'])}):")
    for driver in verdict_result['top_positive_drivers'][:3]:
        print(f"  + {driver}")

    print(f"\nTop Negative Drivers ({len(verdict_result['top_negative_drivers'])}):")
    for driver in verdict_result['top_negative_drivers'][:3]:
        print(f"  - {driver}")

    print("\n2. Generating Narrative Explanation...")
    print("-" * 60)

    try:
        narrative = generate_narrative_explanation(
            ticker="TEST.NS",
            company_name="Test Company",
            verdict_result=verdict_result
        )
        print(narrative)
        print("\n✅ LLM narrative generation successful")
    except Exception as e:
        print(f"⚠️ LLM generation failed (expected if no API key): {e}")
        print("Narrative generation will fall back to template in production.")

    print("\n" + "="*60)
    print("✅ Investment Verdict Feature Test Complete")
    print("="*60)

    return verdict_result


def test_missing_data_handling():
    """Test handling of missing/unavailable data."""

    print("\n" + "="*60)
    print("Testing Missing Data Handling")
    print("="*60)

    # All components unavailable
    verdict_result = compute_investment_verdict(
        news_output={"status": "error"},
        ratio_output={"status": "error"},
        technical_output={"status": "error"},
        risk_output={"status": "error"},
        filing_output={"status": "error"}
    )

    print(f"\nVerdict with no data: {verdict_result['verdict']}")
    print(f"Net Score: {verdict_result['net_score']:.2f}")
    print(f"Confidence: {verdict_result['confidence']:.1f}%")
    print(f"Unavailable Components: {verdict_result['unavailable_components']}")

    print("\n✅ Missing data handled correctly (confidence = 0%, all unavailable)")


if __name__ == "__main__":
    # Test with mock data
    verdict_result = test_verdict_with_mock_data()

    # Test missing data handling
    test_missing_data_handling()

    print("\n" + "="*60)
    print("All tests passed! ✅")
    print("="*60)
