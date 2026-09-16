"""
Live smoke test for News Sentinel with RELIANCE.

Tests the full upgraded News Sentinel agent with real data.
"""

import os
from dotenv import load_dotenv
from backend.agents.news_sentinel import run_news_sentinel
import json

# Load environment variables
load_dotenv()


def main():
    print("=" * 80)
    print("NEWS SENTINEL LIVE SMOKE TEST - RELIANCE")
    print("=" * 80)
    print()

    ticker = "RELIANCE"
    company_name = "Reliance Industries"

    print(f"Running News Sentinel for {company_name} ({ticker})...")
    print()

    result = run_news_sentinel(ticker, company_name, days_back=7)

    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()
    print(f"Status: {result['status']}")
    print(f"Article Count: {result['article_count']}")
    print(f"Confirmed Stories: {result['confirmed_count']}")
    print(f"Unconfirmed Stories: {result['unconfirmed_count']}")
    print(f"Overall Sentiment: {result['sentiment']} (score: {result['sentiment_score']})")
    print()

    if result.get('error'):
        print(f"Error: {result['error']}")
        print()

    print("=" * 80)
    print("STORY GROUPS")
    print("=" * 80)
    print()

    story_groups = result.get('story_groups', [])

    if not story_groups:
        print("No story groups found.")
    else:
        for i, group in enumerate(story_groups, 1):
            print(f"\n--- Story {i} ---")
            print(f"Title: {group['representative_title']}")
            print(f"Summary: {group['summary']}")
            print(f"Sentiment: {group['sentiment']} ({group['sentiment_reasoning']})")
            print(f"Confidence: {group['confidence_score']}%")
            print(f"Confirmed: {'✓ YES' if group['confirmed'] else '✗ NO'}")
            print(f"Sources ({len(group['sources'])}):")
            for source, tier in zip(group['sources'], group['source_tiers']):
                marker = "✓" if tier == "trusted" else "?"
                print(f"  {marker} {source} [{tier}]")
            if group.get('trusted_sources'):
                print(f"Trusted sources: {', '.join(group['trusted_sources'])}")
            print()

    print("=" * 80)
    print("AGGREGATE FIELDS (for backward compatibility)")
    print("=" * 80)
    print()
    print(f"Key Themes: {result.get('key_themes', [])}")
    print(f"Positive Drivers: {result.get('positive_drivers', [])}")
    print(f"Negative Drivers: {result.get('negative_drivers', [])}")
    print(f"Notable Headlines: {result.get('notable_headlines', [])}")
    print()

    # Save full result
    with open("news_sentinel_smoke_test_result.json", "w") as f:
        json.dump(result, f, indent=2)

    print("Full result saved to: news_sentinel_smoke_test_result.json")
    print()


if __name__ == "__main__":
    main()
