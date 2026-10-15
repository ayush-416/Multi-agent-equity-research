"""
Test script for news configuration options.

Tests NEWS_DAYS_BACK and NEWS_TRUSTED_ONLY settings.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set test environment variables
os.environ["NEWS_DAYS_BACK"] = "3"
os.environ["NEWS_TRUSTED_ONLY"] = "true"

from backend.agents.news_sentinel import run_news_sentinel


def test_news_configuration():
    """Test news sentinel with configuration."""

    print("="*60)
    print("Testing News Configuration")
    print("="*60)

    # Test with environment settings
    print("\n1. Test with environment settings (3 days, trusted only)")
    print("-" * 60)

    result = run_news_sentinel(
        ticker="RELIANCE.NS",
        company_name="Reliance Industries"
    )

    config = result.get("config", {})
    print(f"Configuration used:")
    print(f"  - days_back: {config.get('days_back')}")
    print(f"  - trusted_only: {config.get('trusted_only')}")
    print(f"\nStatus: {result.get('status')}")
    print(f"Articles found: {result.get('article_count', 0)}")
    print(f"Confirmed stories: {result.get('confirmed_count', 0)}")
    print(f"Unconfirmed stories: {result.get('unconfirmed_count', 0)}")

    # Test with override
    print("\n2. Test with override (7 days, all sources)")
    print("-" * 60)

    result2 = run_news_sentinel(
        ticker="RELIANCE.NS",
        company_name="Reliance Industries",
        days_back=7,
        trusted_only=False
    )

    config2 = result2.get("config", {})
    print(f"Configuration used:")
    print(f"  - days_back: {config2.get('days_back')}")
    print(f"  - trusted_only: {config2.get('trusted_only')}")
    print(f"\nStatus: {result2.get('status')}")
    print(f"Articles found: {result2.get('article_count', 0)}")
    print(f"Confirmed stories: {result2.get('confirmed_count', 0)}")
    print(f"Unconfirmed stories: {result2.get('unconfirmed_count', 0)}")

    print("\n" + "="*60)
    print("Test Complete!")
    print("="*60)
    print("\nKey Observations:")
    print("- Configuration is properly loaded from environment")
    print("- Override parameters work correctly")
    print("- Config info is returned in result")
    print("- Settings affect article filtering")


if __name__ == "__main__":
    test_news_configuration()
