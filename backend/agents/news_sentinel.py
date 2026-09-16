"""
News Sentinel Agent: Analyzes recent news sentiment and themes for a company.

Fetches recent news articles, deduplicates stories, verifies with source credibility,
and uses LLM to analyze sentiment per story group with confidence scoring.
"""

import logging
import json
import re
import os
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from difflib import SequenceMatcher

from langchain_google_genai import ChatGoogleGenerativeAI
from backend.tools.news_tools import fetch_google_news
from backend.config.news_config import is_trusted_source, get_source_tier

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Path for tracking seen stories (per-company)
SEEN_STORIES_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def run_news_sentinel(
    ticker: str,
    company_name: str,
    days_back: int = 7
) -> Dict[str, Any]:
    """
    Analyze recent news sentiment and themes for a company with source verification.

    Args:
        ticker: Stock ticker symbol (e.g., "RELIANCE")
        company_name: Full company name (e.g., "Reliance Industries")
        days_back: Number of days to look back for news (default: 7)

    Returns:
        Dict with keys:
        - status: "success", "partial_success", or "error"
        - ticker: Stock ticker
        - company_name: Company name
        - article_count: Total number of articles fetched
        - story_groups: List of deduplicated story groups with verification
        - confirmed_count: Number of confirmed story groups
        - unconfirmed_count: Number of unconfirmed story groups
        - sentiment: Aggregate sentiment from confirmed stories (POSITIVE/NEGATIVE/NEUTRAL/MIXED/UNKNOWN)
        - sentiment_score: Aggregate numeric score from confirmed stories (-1 to 1)
        - key_themes: Aggregate themes from confirmed stories
        - positive_drivers: Aggregate positive drivers from confirmed stories
        - negative_drivers: Aggregate negative drivers from confirmed stories
        - notable_headlines: Most important headlines from confirmed stories
        - sources: All source links
        - error: Error message if applicable
    """
    result = {
        "status": "error",
        "ticker": ticker,
        "company_name": company_name,
        "article_count": 0,
        "story_groups": [],
        "confirmed_count": 0,
        "unconfirmed_count": 0,
        "sentiment": "UNKNOWN",
        "sentiment_score": 0.0,
        "key_themes": [],
        "positive_drivers": [],
        "negative_drivers": [],
        "notable_headlines": [],
        "sources": [],
        "error": None
    }

    try:
        logger.info(f"Starting news sentinel for {ticker} ({company_name}), {days_back} days back")

        # Fetch news articles
        articles = fetch_google_news(company_name, ticker, limit=20)

        if not articles:
            logger.warning(f"No news articles found for {company_name}")
            result["status"] = "partial_success"
            result["error"] = "No recent news articles found"
            return result

        logger.info(f"Fetched {len(articles)} raw articles")

        # Filter by date window
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        articles_filtered = _filter_by_date(articles, cutoff_date)
        logger.info(f"After date filter ({days_back}d): {len(articles_filtered)} articles")

        if not articles_filtered:
            logger.warning(f"No articles within {days_back} day window")
            result["status"] = "partial_success"
            result["article_count"] = len(articles)
            result["error"] = f"No articles within {days_back} day window"
            return result

        # Load seen stories for this company
        seen_stories = _load_seen_stories(ticker)

        # Filter out already-seen stories
        articles_new = _filter_seen_stories(articles_filtered, seen_stories)
        logger.info(f"After dedup with history: {len(articles_new)} new articles")

        if not articles_new:
            logger.info(f"All articles already seen for {ticker}")
            result["status"] = "partial_success"
            result["article_count"] = len(articles)
            result["error"] = "All articles already processed in prior runs"
            return result

        result["article_count"] = len(articles_new)

        # Extract sources for result
        result["sources"] = [article.get("link", "") for article in articles_new if article.get("link")]

        # Deduplicate near-identical headlines into story groups
        story_groups = _deduplicate_stories(articles_new)
        logger.info(f"Deduplicated into {len(story_groups)} story groups")

        # Tag source credibility and determine confirmed status
        for group in story_groups:
            _tag_credibility(group)

        # Analyze each story group with LLM
        analyzed_groups = []
        for i, group in enumerate(story_groups):
            logger.info(f"Analyzing story group {i+1}/{len(story_groups)}: {group['representative_title'][:60]}...")
            analysis = _analyze_story_group(group, company_name, ticker)
            if analysis:
                analyzed_groups.append(analysis)

        result["story_groups"] = analyzed_groups
        result["confirmed_count"] = sum(1 for g in analyzed_groups if g.get("confirmed"))
        result["unconfirmed_count"] = sum(1 for g in analyzed_groups if not g.get("confirmed"))

        logger.info(f"Analysis complete: {result['confirmed_count']} confirmed, {result['unconfirmed_count']} unconfirmed")

        # Compute aggregate metrics from CONFIRMED stories only
        confirmed_groups = [g for g in analyzed_groups if g.get("confirmed")]

        if confirmed_groups:
            _compute_aggregates(result, confirmed_groups)
            result["status"] = "success"
        else:
            logger.warning("No confirmed stories found")
            result["status"] = "partial_success"
            result["error"] = "No confirmed stories (all from unverified sources or single source)"

            # Still compute aggregates from all stories for partial_success
            if analyzed_groups:
                _compute_aggregates(result, analyzed_groups)

        # Save story IDs as seen
        new_seen_ids = [_story_id(article) for article in articles_new]
        _save_seen_stories(ticker, seen_stories + new_seen_ids)

    except Exception as e:
        logger.error(f"News sentinel failed for {ticker}: {e}", exc_info=True)
        result["status"] = "error"
        result["error"] = str(e)

    return result


def _filter_by_date(articles: List[Dict], cutoff_date: datetime) -> List[Dict]:
    """Filter articles to those published after cutoff_date."""
    filtered = []

    for article in articles:
        published_str = article.get("published", "")
        if not published_str:
            # No date - include it (lenient approach)
            filtered.append(article)
            continue

        try:
            # Parse RSS date format (e.g., "Wed, 10 Sep 2026 12:34:56 GMT")
            # Use multiple formats to handle variations
            article_date = None
            for fmt in [
                "%a, %d %b %Y %H:%M:%S %Z",
                "%a, %d %b %Y %H:%M:%S %z",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%d %H:%M:%S"
            ]:
                try:
                    article_date = datetime.strptime(published_str, fmt)
                    break
                except ValueError:
                    continue

            if article_date and article_date >= cutoff_date:
                filtered.append(article)
            elif not article_date:
                # Could not parse - include it (lenient)
                logger.debug(f"Could not parse date '{published_str}', including article")
                filtered.append(article)

        except Exception as e:
            logger.debug(f"Date parsing error for '{published_str}': {e}, including article")
            filtered.append(article)

    return filtered


def _story_id(article: Dict) -> str:
    """Generate unique ID for a story based on title and link."""
    title = article.get("title", "").strip().lower()
    link = article.get("link", "").strip()

    # Use hash of title + link
    content = f"{title}|{link}"
    return hashlib.md5(content.encode()).hexdigest()


def _load_seen_stories(ticker: str) -> List[str]:
    """Load previously seen story IDs for this ticker."""
    os.makedirs(SEEN_STORIES_DIR, exist_ok=True)
    filepath = os.path.join(SEEN_STORIES_DIR, f"seen_stories_{ticker}.json")

    if not os.path.exists(filepath):
        return []

    try:
        with open(filepath, "r") as f:
            data = json.load(f)
            return data.get("seen_ids", [])
    except Exception as e:
        logger.warning(f"Could not load seen stories for {ticker}: {e}")
        return []


def _save_seen_stories(ticker: str, seen_ids: List[str]):
    """Save seen story IDs for this ticker."""
    os.makedirs(SEEN_STORIES_DIR, exist_ok=True)
    filepath = os.path.join(SEEN_STORIES_DIR, f"seen_stories_{ticker}.json")

    # Keep only recent IDs (last 1000 to prevent unbounded growth)
    seen_ids_trimmed = seen_ids[-1000:]

    try:
        with open(filepath, "w") as f:
            json.dump({"seen_ids": seen_ids_trimmed}, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not save seen stories for {ticker}: {e}")


def _filter_seen_stories(articles: List[Dict], seen_ids: List[str]) -> List[Dict]:
    """Filter out articles that have been seen before."""
    seen_set = set(seen_ids)
    return [article for article in articles if _story_id(article) not in seen_set]


def _deduplicate_stories(articles: List[Dict]) -> List[Dict]:
    """
    Deduplicate near-identical headlines into story groups.

    Groups stories with similar headlines (same event reported by multiple outlets).
    Each group tracks all sources and URLs.
    """
    groups = []

    for article in articles:
        title = article.get("title", "").strip()
        if not title:
            continue

        # Try to find an existing group with similar title
        matched_group = None
        for group in groups:
            similarity = _title_similarity(title, group["representative_title"])
            if similarity >= 0.75:  # 75% similarity threshold
                matched_group = group
                break

        if matched_group:
            # Add to existing group
            matched_group["articles"].append(article)
            matched_group["sources"].append(article.get("source", "Unknown"))
            matched_group["urls"].append(article.get("link", ""))
        else:
            # Create new group
            groups.append({
                "representative_title": title,
                "articles": [article],
                "sources": [article.get("source", "Unknown")],
                "urls": [article.get("link", "")],
            })

    return groups


def _title_similarity(title1: str, title2: str) -> float:
    """Calculate similarity between two titles (0 to 1)."""
    # Normalize: lowercase, remove punctuation
    t1 = re.sub(r'[^\w\s]', '', title1.lower())
    t2 = re.sub(r'[^\w\s]', '', title2.lower())

    return SequenceMatcher(None, t1, t2).ratio()


def _tag_credibility(story_group: Dict):
    """
    Tag sources in a story group as trusted/unverified and determine confirmation status.

    Modifies story_group in place, adding:
    - source_tiers: List of "trusted" or "unverified" for each source
    - trusted_sources: List of trusted source names
    - confirmed: True if ≥2 independent trusted sources, False otherwise
    """
    source_tiers = [get_source_tier(source) for source in story_group["sources"]]
    story_group["source_tiers"] = source_tiers

    # Get unique trusted sources
    trusted_sources = [
        source for source, tier in zip(story_group["sources"], source_tiers)
        if tier == "trusted"
    ]
    story_group["trusted_sources"] = trusted_sources
    story_group["trusted_count"] = len(trusted_sources)

    # Confirmed if ≥2 trusted sources
    story_group["confirmed"] = len(trusted_sources) >= 2


def _analyze_story_group(story_group: Dict, company_name: str, ticker: str) -> Optional[Dict]:
    """
    Use LLM to analyze a story group: summary, sentiment, confidence.

    Returns dict with:
    - representative_title
    - summary
    - sentiment: POSITIVE/NEGATIVE/NEUTRAL
    - sentiment_reasoning
    - confidence_score: 0-100 (based on source credibility + count)
    - sources: list of source names
    - urls: list of URLs
    - source_tiers: list of "trusted"/"unverified"
    - confirmed: bool
    """
    articles_text = "\n\n".join([
        f"Headline: {article.get('title', '')}\n"
        f"Source: {article.get('source', '')}\n"
        f"Published: {article.get('published', '')}\n"
        f"Summary: {article.get('summary', '')}"
        for article in story_group["articles"]
    ])

    prompt = f"""You are a financial news analyst. Analyze the following news story about {company_name} ({ticker}).

This story has been reported by {len(story_group['sources'])} source(s):
{', '.join(story_group['sources'])}

News Articles:
{articles_text}

Provide a concise analysis in JSON format with this exact structure:

{{
  "summary": "<one-line summary of the story, max 120 characters>",
  "sentiment": "<POSITIVE|NEGATIVE|NEUTRAL>",
  "sentiment_reasoning": "<brief explanation why this sentiment, max 200 characters>"
}}

Guidelines:
- summary: One line only, focus on the key fact or event
- sentiment: POSITIVE if good for investors, NEGATIVE if bad, NEUTRAL if mixed/routine
- sentiment_reasoning: Explain your sentiment in plain language

Return ONLY the JSON object, no markdown code fences or additional text."""

    try:
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")

        # Use configurable model (defaults to gemini-2.5-flash for free tier)
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,
            timeout=30,
            google_api_key=google_api_key
        )

        response = llm.invoke(prompt)
        response_text = response.content.strip()

        # Strip markdown code fences
        response_text = re.sub(r'^```(?:json)?\s*\n?', '', response_text)
        response_text = re.sub(r'\n?```\s*$', '', response_text)
        response_text = response_text.strip()

        analysis = json.loads(response_text)

        # Calculate confidence score
        # Base: 40 for single source, +20 per additional source (max 80)
        # +20 if confirmed (≥2 trusted sources)
        source_count = len(story_group["sources"])
        confidence = min(40 + (source_count - 1) * 20, 80)
        if story_group.get("confirmed"):
            confidence += 20

        confidence = min(100, confidence)

        return {
            "representative_title": story_group["representative_title"],
            "summary": analysis.get("summary", "")[:120],
            "sentiment": analysis.get("sentiment", "NEUTRAL").upper(),
            "sentiment_reasoning": analysis.get("sentiment_reasoning", "")[:200],
            "confidence_score": confidence,
            "sources": story_group["sources"],
            "urls": story_group["urls"],
            "source_tiers": story_group["source_tiers"],
            "trusted_sources": story_group.get("trusted_sources", []),
            "trusted_count": story_group.get("trusted_count", 0),
            "confirmed": story_group.get("confirmed", False),
        }

    except Exception as e:
        logger.error(f"Story group analysis failed: {e}")
        return None


def _compute_aggregates(result: Dict, story_groups: List[Dict]):
    """
    Compute aggregate sentiment metrics from story groups.

    Updates result dict with:
    - sentiment: aggregate sentiment
    - sentiment_score: weighted average score
    - key_themes: extracted themes
    - positive_drivers: positive stories
    - negative_drivers: negative stories
    - notable_headlines: top headlines
    """
    if not story_groups:
        return

    # Count sentiments
    sentiment_counts = defaultdict(int)
    sentiment_scores = []

    for group in story_groups:
        sentiment = group.get("sentiment", "NEUTRAL")
        sentiment_counts[sentiment] += 1

        # Convert sentiment to score
        score_map = {"POSITIVE": 1.0, "NEUTRAL": 0.0, "NEGATIVE": -1.0}
        score = score_map.get(sentiment, 0.0)
        confidence = group.get("confidence_score", 50) / 100.0
        sentiment_scores.append(score * confidence)

    # Determine overall sentiment
    pos_count = sentiment_counts["POSITIVE"]
    neg_count = sentiment_counts["NEGATIVE"]
    neu_count = sentiment_counts["NEUTRAL"]

    if pos_count > neg_count and pos_count > neu_count:
        result["sentiment"] = "POSITIVE"
    elif neg_count > pos_count and neg_count > neu_count:
        result["sentiment"] = "NEGATIVE"
    elif pos_count > 0 and neg_count > 0:
        result["sentiment"] = "MIXED"
    else:
        result["sentiment"] = "NEUTRAL"

    # Average sentiment score
    if sentiment_scores:
        result["sentiment_score"] = round(sum(sentiment_scores) / len(sentiment_scores), 2)

    # Extract positive and negative drivers
    positive_drivers = [
        group["summary"] for group in story_groups
        if group.get("sentiment") == "POSITIVE"
    ][:5]

    negative_drivers = [
        group["summary"] for group in story_groups
        if group.get("sentiment") == "NEGATIVE"
    ][:5]

    result["positive_drivers"] = positive_drivers
    result["negative_drivers"] = negative_drivers

    # Key themes (top summaries from confirmed stories)
    themes = [group["summary"] for group in story_groups[:7]]
    result["key_themes"] = themes

    # Notable headlines (top 5 by confidence)
    sorted_groups = sorted(story_groups, key=lambda g: g.get("confidence_score", 0), reverse=True)
    result["notable_headlines"] = [
        group["representative_title"] for group in sorted_groups[:5]
    ]
