"""
End-to-end smoke test for RELIANCE showing actual output.
"""
import os
import json
from dotenv import load_dotenv
from backend.graph.workflow import run_analysis

load_dotenv()

print("=" * 80)
print("END-TO-END SMOKE TEST FOR RELIANCE")
print("=" * 80)
print()

# Verify API key
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("ERROR: GOOGLE_API_KEY not set in .env")
    exit(1)

print(f"GOOGLE_API_KEY: {'SET (' + api_key[:10] + '...)' if api_key else 'NOT SET'}")
print()

ticker = "RELIANCE"
company_name = "Reliance Industries"

print(f"Running full analysis for {company_name} ({ticker})...")
print()

result = run_analysis(ticker=ticker, company_name=company_name)

print("=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
print()
print(f"Status: {result.get('final_report', {}).get('status', 'N/A')}")
print(f"Errors: {len(result.get('errors', []))}")
print()

# Show news output
news_output = result.get('news_output', {})
print("=" * 80)
print("NEWS SENTINEL OUTPUT")
print("=" * 80)
print(f"Status: {news_output.get('status')}")
print(f"Article Count: {news_output.get('article_count')}")
print(f"Confirmed Stories: {news_output.get('confirmed_count')}")
print(f"Unconfirmed Stories: {news_output.get('unconfirmed_count')}")
print(f"Overall Sentiment: {news_output.get('sentiment')} (score: {news_output.get('sentiment_score')})")
print()

story_groups = news_output.get('story_groups', [])
if story_groups:
    print(f"Total Story Groups: {len(story_groups)}")
    print()
    for i, group in enumerate(story_groups[:5], 1):
        print(f"--- Story Group {i} ---")
        print(f"Title: {group.get('representative_title', '')[:80]}...")
        print(f"Summary: {group.get('summary', '')}")
        print(f"Sentiment: {group.get('sentiment')} - {group.get('sentiment_reasoning', '')}")
        print(f"Confidence: {group.get('confidence_score')}%")
        print(f"Confirmed: {'YES (>=2 trusted sources)' if group.get('confirmed') else 'NO (single/unverified source)'}")
        print(f"Sources ({len(group.get('sources', []))}): {', '.join(group.get('sources', [])[:3])}")
        print(f"Trusted: {', '.join(group.get('trusted_sources', []))}" if group.get('trusted_sources') else "Trusted: None")
        print()
else:
    print("No story groups found")
    if news_output.get('error'):
        print(f"Error: {news_output['error']}")
print()

# Show report writer output
final_report = result.get('final_report', {})
print("=" * 80)
print("REPORT WRITER OUTPUT")
print("=" * 80)
print(f"Status: {final_report.get('status')}")
print(f"Confidence Score: {final_report.get('confidence_score')}")
print()

if final_report.get('executive_summary'):
    print("Executive Summary:")
    print(final_report['executive_summary'][:300] + "..." if len(final_report['executive_summary']) > 300 else final_report['executive_summary'])
    print()

if final_report.get('bull_case'):
    print("Bull Case (first 200 chars):")
    print(final_report['bull_case'][:200] + "...")
    print()

if final_report.get('bear_case'):
    print("Bear Case (first 200 chars):")
    print(final_report['bear_case'][:200] + "...")
    print()

if final_report.get('key_risks'):
    print("Key Risks:")
    for i, risk in enumerate(final_report['key_risks'][:3], 1):
        print(f"  {i}. {risk}")
    print()

# Save full output
with open("smoke_test_reliance_full_output.json", "w") as f:
    json.dump(result, f, indent=2)

print("Full output saved to: smoke_test_reliance_full_output.json")
print()
print("=" * 80)
print("SMOKE TEST COMPLETE")
print("=" * 80)
