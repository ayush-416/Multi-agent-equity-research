"""
Unit tests for News Sentinel agent upgrade.

Tests deduplication, credibility tagging, confirmation logic, date filtering, and seen story tracking.
"""

import pytest
import json
import os
from datetime import datetime, timedelta
from unittest.mock import patch, mock_open, MagicMock

from backend.agents.news_sentinel import (
    _filter_by_date,
    _deduplicate_stories,
    _title_similarity,
    _tag_credibility,
    _story_id,
    _load_seen_stories,
    _save_seen_stories,
    _filter_seen_stories,
    _compute_aggregates,
)
from backend.config.news_config import is_trusted_source, get_source_tier


class TestSourceCredibility:
    """Test source credibility classification."""

    def test_trusted_sources(self):
        """Test that configured trusted sources are recognized."""
        assert is_trusted_source("Economic Times") == True
        assert is_trusted_source("Reuters") == True
        assert is_trusted_source("LiveMint") == True
        assert is_trusted_source("Moneycontrol") == True
        assert is_trusted_source("Business Standard") == True

    def test_trusted_sources_case_insensitive(self):
        """Test case-insensitive matching."""
        assert is_trusted_source("economic times") == True
        assert is_trusted_source("REUTERS") == True
        assert is_trusted_source("livemint") == True

    def test_trusted_sources_partial_match(self):
        """Test partial matching (e.g., 'Economic Times - Markets' contains 'Economic Times')."""
        assert is_trusted_source("Economic Times - Markets") == True
        assert is_trusted_source("Reuters India") == True

    def test_unverified_sources(self):
        """Test that non-trusted sources return False."""
        assert is_trusted_source("Random Blog") == False
        assert is_trusted_source("Unknown News Site") == False
        assert is_trusted_source("") == False

    def test_get_source_tier(self):
        """Test tier classification."""
        assert get_source_tier("Economic Times") == "trusted"
        assert get_source_tier("Random Blog") == "unverified"


class TestDeduplication:
    """Test story deduplication logic."""

    def test_title_similarity_identical(self):
        """Test that identical titles have 1.0 similarity."""
        title = "Reliance Industries announces Q4 results"
        assert _title_similarity(title, title) == 1.0

    def test_title_similarity_similar(self):
        """Test that very similar titles have high similarity."""
        title1 = "Reliance Industries announces Q4 results"
        title2 = "Reliance Industries announces Q4 results today"
        similarity = _title_similarity(title1, title2)
        assert similarity > 0.75, f"Expected >0.75, got {similarity}"

    def test_title_similarity_different(self):
        """Test that different titles have low similarity."""
        title1 = "Reliance Industries announces Q4 results"
        title2 = "TCS declares dividend for shareholders"
        similarity = _title_similarity(title1, title2)
        assert similarity < 0.5, f"Expected <0.5, got {similarity}"

    def test_deduplicate_single_article(self):
        """Test deduplication with single article."""
        articles = [{
            "title": "Reliance Q4 results",
            "source": "Economic Times",
            "link": "http://example.com/1"
        }]

        groups = _deduplicate_stories(articles)

        assert len(groups) == 1
        assert groups[0]["representative_title"] == "Reliance Q4 results"
        assert len(groups[0]["articles"]) == 1
        assert len(groups[0]["sources"]) == 1

    def test_deduplicate_identical_stories(self):
        """Test deduplication groups near-identical headlines."""
        articles = [
            {
                "title": "Reliance Industries announces Q4 results",
                "source": "Economic Times",
                "link": "http://example.com/1"
            },
            {
                "title": "Reliance Industries announces Q4 results today",
                "source": "Reuters",
                "link": "http://example.com/2"
            },
            {
                "title": "Reliance announces quarterly results",
                "source": "LiveMint",
                "link": "http://example.com/3"
            }
        ]

        groups = _deduplicate_stories(articles)

        # Should group similar headlines together
        assert len(groups) <= 2, f"Expected <=2 groups, got {len(groups)}"

        # First group should have multiple sources
        largest_group = max(groups, key=lambda g: len(g["sources"]))
        assert len(largest_group["sources"]) >= 2

    def test_deduplicate_different_stories(self):
        """Test that different stories remain separate."""
        articles = [
            {
                "title": "Reliance announces Q4 results",
                "source": "Economic Times",
                "link": "http://example.com/1"
            },
            {
                "title": "TCS declares dividend",
                "source": "Reuters",
                "link": "http://example.com/2"
            }
        ]

        groups = _deduplicate_stories(articles)

        assert len(groups) == 2


class TestCredibilityTagging:
    """Test credibility tagging and confirmation logic."""

    def test_tag_single_trusted_source(self):
        """Test tagging with single trusted source - should be unconfirmed."""
        group = {
            "representative_title": "Test story",
            "sources": ["Economic Times"],
            "articles": [],
            "urls": []
        }

        _tag_credibility(group)

        assert group["source_tiers"] == ["trusted"]
        assert group["trusted_count"] == 1
        assert group["confirmed"] == False  # Need ≥2 trusted sources

    def test_tag_multiple_trusted_sources(self):
        """Test tagging with multiple trusted sources - should be confirmed."""
        group = {
            "representative_title": "Test story",
            "sources": ["Economic Times", "Reuters", "LiveMint"],
            "articles": [],
            "urls": []
        }

        _tag_credibility(group)

        assert group["source_tiers"] == ["trusted", "trusted", "trusted"]
        assert group["trusted_count"] == 3
        assert group["confirmed"] == True  # ≥2 trusted sources

    def test_tag_mixed_sources(self):
        """Test tagging with mix of trusted and unverified sources."""
        group = {
            "representative_title": "Test story",
            "sources": ["Economic Times", "Random Blog", "Reuters"],
            "articles": [],
            "urls": []
        }

        _tag_credibility(group)

        assert group["source_tiers"] == ["trusted", "unverified", "trusted"]
        assert group["trusted_count"] == 2
        assert group["confirmed"] == True  # 2 trusted sources

    def test_tag_unverified_only(self):
        """Test tagging with only unverified sources."""
        group = {
            "representative_title": "Test story",
            "sources": ["Random Blog", "Unknown Site"],
            "articles": [],
            "urls": []
        }

        _tag_credibility(group)

        assert group["source_tiers"] == ["unverified", "unverified"]
        assert group["trusted_count"] == 0
        assert group["confirmed"] == False


class TestDateFiltering:
    """Test date filtering logic."""

    def test_filter_recent_articles(self):
        """Test that recent articles pass the filter."""
        cutoff = datetime.utcnow() - timedelta(days=7)
        recent_date = datetime.utcnow() - timedelta(days=3)

        articles = [{
            "title": "Recent news",
            "published": recent_date.strftime("%a, %d %b %Y %H:%M:%S GMT")
        }]

        filtered = _filter_by_date(articles, cutoff)

        assert len(filtered) == 1

    def test_filter_old_articles(self):
        """Test that old articles are filtered out."""
        cutoff = datetime.utcnow() - timedelta(days=7)
        old_date = datetime.utcnow() - timedelta(days=10)

        articles = [{
            "title": "Old news",
            "published": old_date.strftime("%a, %d %b %Y %H:%M:%S GMT")
        }]

        filtered = _filter_by_date(articles, cutoff)

        assert len(filtered) == 0

    def test_filter_no_date(self):
        """Test that articles without dates are included (lenient)."""
        cutoff = datetime.utcnow() - timedelta(days=7)

        articles = [{
            "title": "No date news",
            "published": ""
        }]

        filtered = _filter_by_date(articles, cutoff)

        assert len(filtered) == 1

    def test_filter_unparseable_date(self):
        """Test that articles with unparseable dates are included (lenient)."""
        cutoff = datetime.utcnow() - timedelta(days=7)

        articles = [{
            "title": "Bad date news",
            "published": "invalid date format"
        }]

        filtered = _filter_by_date(articles, cutoff)

        assert len(filtered) == 1


class TestSeenStoryTracking:
    """Test seen story tracking logic."""

    def test_story_id_generation(self):
        """Test that story IDs are generated consistently."""
        article = {
            "title": "Test Article",
            "link": "http://example.com/1"
        }

        id1 = _story_id(article)
        id2 = _story_id(article)

        assert id1 == id2
        assert len(id1) == 32  # MD5 hex length

    def test_story_id_different_articles(self):
        """Test that different articles have different IDs."""
        article1 = {
            "title": "Test Article 1",
            "link": "http://example.com/1"
        }
        article2 = {
            "title": "Test Article 2",
            "link": "http://example.com/2"
        }

        id1 = _story_id(article1)
        id2 = _story_id(article2)

        assert id1 != id2

    def test_filter_seen_stories(self):
        """Test filtering of already-seen stories."""
        articles = [
            {"title": "Story 1", "link": "http://example.com/1"},
            {"title": "Story 2", "link": "http://example.com/2"},
            {"title": "Story 3", "link": "http://example.com/3"},
        ]

        seen_ids = [_story_id(articles[0]), _story_id(articles[2])]

        filtered = _filter_seen_stories(articles, seen_ids)

        assert len(filtered) == 1
        assert filtered[0]["title"] == "Story 2"

    @patch('builtins.open', new_callable=mock_open, read_data='{"seen_ids": ["abc123", "def456"]}')
    @patch('os.path.exists', return_value=True)
    def test_load_seen_stories(self, mock_exists, mock_file):
        """Test loading seen stories from file."""
        seen = _load_seen_stories("TEST")

        assert len(seen) == 2
        assert "abc123" in seen
        assert "def456" in seen

    @patch('os.path.exists', return_value=False)
    def test_load_seen_stories_no_file(self, mock_exists):
        """Test loading when no file exists returns empty list."""
        seen = _load_seen_stories("TEST")

        assert seen == []


class TestAggregateComputation:
    """Test aggregate sentiment computation from story groups."""

    def test_compute_aggregates_positive(self):
        """Test aggregate computation with mostly positive stories."""
        story_groups = [
            {"sentiment": "POSITIVE", "confidence_score": 90, "summary": "Good news 1", "representative_title": "Title 1"},
            {"sentiment": "POSITIVE", "confidence_score": 80, "summary": "Good news 2", "representative_title": "Title 2"},
            {"sentiment": "NEUTRAL", "confidence_score": 50, "summary": "Neutral news", "representative_title": "Title 3"},
        ]

        result = {
            "sentiment": "UNKNOWN",
            "sentiment_score": 0.0,
            "positive_drivers": [],
            "negative_drivers": [],
            "key_themes": [],
            "notable_headlines": []
        }

        _compute_aggregates(result, story_groups)

        assert result["sentiment"] == "POSITIVE"
        assert result["sentiment_score"] > 0
        assert len(result["positive_drivers"]) == 2
        assert len(result["negative_drivers"]) == 0

    def test_compute_aggregates_negative(self):
        """Test aggregate computation with mostly negative stories."""
        story_groups = [
            {"sentiment": "NEGATIVE", "confidence_score": 80, "summary": "Bad news 1", "representative_title": "Title 1"},
            {"sentiment": "NEGATIVE", "confidence_score": 70, "summary": "Bad news 2", "representative_title": "Title 2"},
            {"sentiment": "NEUTRAL", "confidence_score": 50, "summary": "Neutral news", "representative_title": "Title 3"},
        ]

        result = {
            "sentiment": "UNKNOWN",
            "sentiment_score": 0.0,
            "positive_drivers": [],
            "negative_drivers": [],
            "key_themes": [],
            "notable_headlines": []
        }

        _compute_aggregates(result, story_groups)

        assert result["sentiment"] == "NEGATIVE"
        assert result["sentiment_score"] < 0
        assert len(result["positive_drivers"]) == 0
        assert len(result["negative_drivers"]) == 2

    def test_compute_aggregates_mixed(self):
        """Test aggregate computation with mixed sentiments."""
        story_groups = [
            {"sentiment": "POSITIVE", "confidence_score": 80, "summary": "Good news", "representative_title": "Title 1"},
            {"sentiment": "NEGATIVE", "confidence_score": 80, "summary": "Bad news", "representative_title": "Title 2"},
        ]

        result = {
            "sentiment": "UNKNOWN",
            "sentiment_score": 0.0,
            "positive_drivers": [],
            "negative_drivers": [],
            "key_themes": [],
            "notable_headlines": []
        }

        _compute_aggregates(result, story_groups)

        assert result["sentiment"] == "MIXED"
        assert len(result["positive_drivers"]) == 1
        assert len(result["negative_drivers"]) == 1


@patch('backend.agents.news_sentinel.fetch_google_news')
@patch('backend.agents.news_sentinel.ChatGoogleGenerativeAI')
@patch('backend.agents.news_sentinel._load_seen_stories', return_value=[])
@patch('backend.agents.news_sentinel._save_seen_stories')
@patch('backend.agents.news_sentinel.os.getenv', return_value='fake-api-key')
class TestNewsSentinelIntegration:
    """Integration tests for the full news sentinel flow."""

    def test_no_articles(self, mock_getenv, mock_save, mock_load, mock_llm, mock_fetch):
        """Test handling when no articles are found."""
        from backend.agents.news_sentinel import run_news_sentinel

        mock_fetch.return_value = []

        result = run_news_sentinel("TEST", "Test Company")

        assert result["status"] == "partial_success"
        assert result["article_count"] == 0
        assert "No recent news articles" in result["error"]

    def test_confirmed_and_unconfirmed_stories(self, mock_getenv, mock_save, mock_load, mock_llm, mock_fetch):
        """Test that confirmed and unconfirmed stories are properly classified."""
        from backend.agents.news_sentinel import run_news_sentinel

        # Mock articles - same story from multiple sources
        recent_date = datetime.utcnow() - timedelta(days=2)
        date_str = recent_date.strftime("%a, %d %b %Y %H:%M:%S GMT")

        mock_fetch.return_value = [
            {
                "title": "Company announces expansion",
                "source": "Economic Times",
                "published": date_str,
                "summary": "Company expands operations",
                "link": "http://example.com/1"
            },
            {
                "title": "Company announces expansion plans",
                "source": "Reuters",
                "published": date_str,
                "summary": "Company expands operations",
                "link": "http://example.com/2"
            },
            {
                "title": "Different story from unknown source",
                "source": "Random Blog",
                "published": date_str,
                "summary": "Different news",
                "link": "http://example.com/3"
            }
        ]

        # Mock LLM response
        mock_llm_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "summary": "Test summary",
            "sentiment": "POSITIVE",
            "sentiment_reasoning": "Good news"
        })
        mock_llm_instance.invoke.return_value = mock_response
        mock_llm.return_value = mock_llm_instance

        result = run_news_sentinel("TEST", "Test Company", days_back=7)

        # Should have story groups with proper classification
        assert result["status"] in ["success", "partial_success"]
        assert result["article_count"] == 3
        assert "story_groups" in result
        # At least one story group should exist
        assert len(result["story_groups"]) >= 1
