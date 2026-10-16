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

from dotenv import load_dotenv
from backend.llm import get_llm
from backend.tools.news_tools import fetch_google_news
from backend.config.news_config import is_trusted_source, get_source_tier

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Path for tracking seen stories (per-company)
SEEN_STORIES_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def run_news_sentinel(
    ticker: str,
    company_name: str,
    days_back: Optional[int] = None,
    trusted_only: Optional[bool] = None,
    use_history_dedup: bool = False
) -> Dict[str, Any]:
    """
    Analyze recent news sentiment and themes for a company with source verification.

    Args:
        ticker: Stock ticker symbol (e.g., "RELIANCE")
        company_name: Full company name (e.g., "Reliance Industries")
        days_back: Number of days to look back for news (default: from env or 7)
        trusted_only: Only use trusted sources for scoring (default: from env or False)
        use_history_dedup: Apply seen-stories deduplication (default: False for /analyze, True for watchlist)

    Returns:
        Dict with keys:
        - status: "ok", "partial", "no_data", or "error"
        - ticker: Stock ticker
        - company_name: Company name
        - article_count: Total number of articles fetched
        - raw_articles: List of all articles with title, source, date, url
        - story_groups: List of ALL analyzed story groups (confirmed and unconfirmed)
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
        - config: Configuration used (days_back, trusted_only, use_history_dedup)
    """
    # Load configuration from environment if not provided
    if days_back is None:
        days_back = int(os.getenv("NEWS_DAYS_BACK", "7"))

    if trusted_only is None:
        trusted_only_str = os.getenv("NEWS_TRUSTED_ONLY", "false").lower()
        trusted_only = trusted_only_str in ["true", "1", "yes"]

    # Check if news dedup is disabled (for testing)
    disable_dedup_str = os.getenv("NEWS_DISABLE_DEDUP", "false").lower()
    disable_dedup = disable_dedup_str in ["true", "1", "yes"]

    result = {
        "status": "error",
        "ticker": ticker,
        "company_name": company_name,
        "article_count": 0,
        "raw_articles": [],
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
        "error": None,
        "config": {
            "days_back": days_back,
            "trusted_only": trusted_only,
            "disable_dedup": disable_dedup,
            "use_history_dedup": use_history_dedup
        }
    }

    try:
        logger.info(f"Starting news sentinel for {ticker} ({company_name})")
        logger.info(f"Config: days_back={days_back}, trusted_only={trusted_only}, use_history_dedup={use_history_dedup}")

        # Fetch news articles
        articles = fetch_google_news(company_name, ticker, limit=20)

        if not articles:
            logger.warning(f"No news articles found for {company_name}")
            result["status"] = "no_data"
            result["error"] = f"No news articles found for {company_name} in the last {days_back} days (source: Google News RSS)"
            return result

        logger.info(f"Fetched {len(articles)} raw articles")

        # Store raw articles for output
        result["raw_articles"] = [
            {
                "title": article.get("title", ""),
                "source": article.get("source", ""),
                "published_date": article.get("published_date", ""),
                "url": article.get("link", "")
            }
            for article in articles
        ]

        # Filter by date window
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        articles_filtered = _filter_by_date(articles, cutoff_date)
        logger.info(f"After date filter ({days_back}d): {len(articles_filtered)} articles")

        if not articles_filtered:
            logger.warning(f"No articles within {days_back} day window")
            result["status"] = "partial"
            result["article_count"] = len(articles)
            result["error"] = f"No articles within {days_back} day window"
            return result

        # Filter by trusted sources if enabled
        if trusted_only:
            articles_trusted = [
                article for article in articles_filtered
                if is_trusted_source(article.get("source", ""))
            ]
            logger.info(f"After trusted filter: {len(articles_trusted)} articles (from {len(articles_filtered)})")

            if not articles_trusted:
                logger.warning("No articles from trusted sources")
                result["status"] = "partial"
                result["article_count"] = len(articles)
                result["error"] = "No articles from trusted sources in the date window"
                return result

            articles_filtered = articles_trusted

        # Load seen stories for this company (only if use_history_dedup is True AND not disabled by env)
        if use_history_dedup and not disable_dedup:
            logger.info("History deduplication enabled (watchlist mode)")
            seen_stories = _load_seen_stories(ticker)
            # Filter out already-seen stories
            articles_new = _filter_seen_stories(articles_filtered, seen_stories)
            logger.info(f"After dedup with history: {len(articles_new)} new articles")
        else:
            if disable_dedup:
                logger.info("History deduplication disabled (NEWS_DISABLE_DEDUP=true)")
            else:
                logger.info("History deduplication skipped (/analyze mode)")
            articles_new = articles_filtered
            seen_stories = []

        if not articles_new:
            logger.info(f"All articles already seen for {ticker} (or filtered out)")
            result["status"] = "no_data"
            result["article_count"] = len(articles)
            result["error"] = "All articles already processed in prior runs (or filtered by trust filter)"
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

        # Limit to top 8 story groups to reduce LLM calls (free tier limit)
        # Prioritize confirmed stories first, then by source count
        story_groups_sorted = sorted(
            story_groups,
            key=lambda g: (g.get("confirmed", False), len(g["sources"])),
            reverse=True
        )
        story_groups_to_analyze = story_groups_sorted[:8]

        if len(story_groups) > 8:
            logger.info(f"Limited analysis to top 8 of {len(story_groups)} story groups to reduce API calls")

        # Analyze story groups in ONE batched LLM call
        analyzed_groups = _analyze_story_groups_batch(story_groups_to_analyze, company_name, ticker)

        # Return ALL analyzed groups (both confirmed and unconfirmed), sorted confirmed first
        analyzed_groups_sorted = sorted(analyzed_groups, key=lambda g: (not g.get("confirmed", False), -len(g.get("sources", []))))

        result["story_groups"] = analyzed_groups_sorted
        result["confirmed_count"] = sum(1 for g in analyzed_groups_sorted if g.get("confirmed"))
        result["unconfirmed_count"] = sum(1 for g in analyzed_groups_sorted if not g.get("confirmed"))

        logger.info(f"Analysis complete: {result['confirmed_count']} confirmed, {result['unconfirmed_count']} unconfirmed")

        # Compute aggregate metrics from CONFIRMED stories only
        # Wrap in try/except to ensure we always return analyzed stories even if post-processing fails
        try:
            confirmed_groups = [g for g in analyzed_groups_sorted if g.get("confirmed")]
            unconfirmed_groups = [g for g in analyzed_groups_sorted if not g.get("confirmed")]

            if confirmed_groups:
                _compute_aggregates(result, confirmed_groups)
                result["status"] = "ok"
            else:
                logger.warning("No confirmed stories found")
                result["status"] = "partial"
                result["error"] = f"No confirmed stories - all from unverified sources or single-source reports ({len(unconfirmed_groups)} unconfirmed)"

                # Still show unconfirmed stories but don't compute aggregates from them
                # Aggregates remain at their default neutral values

            # Save story IDs as seen (only if dedup was used)
            if use_history_dedup and not disable_dedup:
                new_seen_ids = [_story_id(article) for article in articles_new]
                _save_seen_stories(ticker, seen_stories + new_seen_ids)

        except Exception as post_error:
            logger.error(f"Post-processing error (stories still returned): {post_error}", exc_info=True)
            # Ensure we still have a valid status
            if result["status"] == "error":
                result["status"] = "partial"
            if not result.get("error"):
                result["error"] = f"Post-processing issue: {str(post_error)}"

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


def _analyze_story_groups_batch(story_groups: List[Dict], company_name: str, ticker: str) -> List[Dict]:
    """
    Use ONE batched LLM call to analyze multiple story groups at once.
    This reduces API calls dramatically (was N calls, now 1 call).

    Returns list of analyzed story dicts.
    """
    if not story_groups:
        return []

    # Build batch prompt with all stories
    stories_text = ""
    for idx, group in enumerate(story_groups, 1):
        articles_text = "\n".join([
            f"  - {article.get('title', '')} ({article.get('source', '')})"
            for article in group["articles"][:3]  # Limit to 3 articles per group to save tokens
        ])

        stories_text += f"""
STORY {idx}:
Representative Headline: {group['representative_title']}
Sources ({len(group['sources'])}): {', '.join(group['sources'][:5])}
Articles:
{articles_text}

"""

    prompt = f"""You are a financial news analyst. Analyze ALL the following news stories about {company_name} ({ticker}).

{stories_text}

For EACH story above, provide a concise analysis. Return a JSON array with this exact structure:

[
  {{
    "story_number": 1,
    "summary": "<one-line summary, max 120 characters>",
    "sentiment": "<POSITIVE|NEGATIVE|NEUTRAL>",
    "sentiment_reasoning": "<brief explanation, max 200 characters>"
  }},
  {{
    "story_number": 2,
    "summary": "...",
    "sentiment": "...",
    "sentiment_reasoning": "..."
  }}
  // ... for all stories
]

Guidelines:
- Analyze ALL {len(story_groups)} stories
- sentiment: POSITIVE if good for investors, NEGATIVE if bad, NEUTRAL if mixed/routine
- Keep summaries and reasoning concise

Return ONLY the JSON array, no markdown code fences or additional text."""

    try:
        # Use centralized LLM with fallback
        llm = get_llm(temperature=0)

        logger.info(f"Sending batched analysis request for {len(story_groups)} stories")
        response = llm.invoke(prompt)
        response_text = response.content.strip()

        # Strip markdown code fences
        response_text = re.sub(r'^```(?:json)?\s*\n?', '', response_text)
        response_text = re.sub(r'\n?```\s*$', '', response_text)
        response_text = response_text.strip()

        analyses = json.loads(response_text)

        # Map analyses back to story groups
        analyzed_groups = []
        for idx, group in enumerate(story_groups):
            # Find matching analysis by story_number
            analysis = next((a for a in analyses if a.get("story_number") == idx + 1), None)

            if not analysis:
                logger.warning(f"No analysis returned for story {idx + 1}")
                continue

            # Calculate confidence score
            source_count = len(group["sources"])
            confidence = min(40 + (source_count - 1) * 20, 80)
            if group.get("confirmed"):
                confidence += 20
            confidence = min(100, confidence)

            analyzed_groups.append({
                "representative_title": group["representative_title"],
                "summary": analysis.get("summary", "")[:120],
                "sentiment": analysis.get("sentiment", "NEUTRAL").upper(),
                "sentiment_reasoning": analysis.get("sentiment_reasoning", "")[:200],
                "confidence_score": confidence,
                "sources": group["sources"],
                "urls": group["urls"],
                "source_tiers": group["source_tiers"],
                "trusted_sources": group.get("trusted_sources", []),
                "trusted_count": group.get("trusted_count", 0),
                "confirmed": group.get("confirmed", False),
            })

        logger.info(f"Successfully analyzed {len(analyzed_groups)}/{len(story_groups)} stories in batch")
        return analyzed_groups

    except Exception as e:
        logger.error(f"Batch story analysis failed: {e}")
        # Fallback: return groups without LLM analysis
        fallback_groups = []
        for group in story_groups:
            source_count = len(group["sources"])
            confidence = min(40 + (source_count - 1) * 20, 80)
            if group.get("confirmed"):
                confidence += 20
            confidence = min(100, confidence)

            fallback_groups.append({
                "representative_title": group["representative_title"],
                "summary": group["representative_title"][:120],
                "sentiment": "NEUTRAL",
                "sentiment_reasoning": "Analysis failed - using headline as fallback",
                "confidence_score": confidence,
                "sources": group["sources"],
                "urls": group["urls"],
                "source_tiers": group["source_tiers"],
                "trusted_sources": group.get("trusted_sources", []),
                "trusted_count": group.get("trusted_count", 0),
                "confirmed": group.get("confirmed", False),
            })
        return fallback_groups


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
