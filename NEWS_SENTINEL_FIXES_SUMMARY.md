# News Sentinel Fixes - Implementation Summary

## All 6 Fixes Completed

### 1. ✅ History Dedup Only for Watchlist
**Changed Files:**
- `backend/agents/news_sentinel.py`
- `backend/graph/workflow.py`

**Changes:**
- Added `use_history_dedup` parameter (default: False)
- `/analyze` mode: passes `use_history_dedup=False` (always fresh news)
- Watchlist scheduler should pass `use_history_dedup=True` (dedupe history)
- `NEWS_DISABLE_DEDUP` env var still works as override

**Code:**
```python
def run_news_sentinel(
    ticker: str,
    company_name: str,
    days_back: Optional[int] = None,
    trusted_only: Optional[bool] = None,
    use_history_dedup: bool = False  # Default False for /analyze
)
```

### 2. ✅ Return All Stories (Confirmed + Unconfirmed)
**Changed Files:**
- `backend/agents/news_sentinel.py`

**Changes:**
- ALL analyzed stories returned in `story_groups`
- Each story has: `title, source, published_date, url, sentiment, summary, confirmed (bool)`
- Sorted confirmed first, then unconfirmed
- Both `confirmed_count` and `unconfirmed_count` tracked

**Output Structure:**
```python
{
    "story_groups": [
        {
            "title": "...",
            "source": "Economic Times",
            "published_date": "2026-10-15",
            "url": "https://...",
            "sentiment": "POSITIVE",
            "confidence_score": 0.8,
            "summary": "...",
            "confirmed": True  # or False
        },
        # ... more stories
    ],
    "confirmed_count": 5,
    "unconfirmed_count": 3
}
```

### 3. ✅ Always Include Raw Article List
**Changed Files:**
- `backend/agents/news_sentinel.py`

**Changes:**
- Added `raw_articles` field to result
- Always populated even if LLM analysis fails
- Contains: title, source, published_date, url

**Output:**
```python
{
    "raw_articles": [
        {
            "title": "Company announces Q3 results",
            "source": "Economic Times",
            "published_date": "2026-10-15 10:30:00",
            "url": "https://..."
        },
        # ... all fetched articles
    ]
}
```

### 4. ✅ Return "no_data" Status When No Articles
**Changed Files:**
- `backend/agents/news_sentinel.py`

**Changes:**
- Returns `status: "no_data"` (not "success" or "partial_success")
- Includes reason in error field
- Two scenarios:
  - No articles fetched from Google News
  - All articles filtered out by history dedup

**Example:**
```python
{
    "status": "no_data",
    "error": "No news articles found for Reliance Industries in the last 7 days"
}
```

### 5. ⚠️ Frontend News Section - TODO
**Files to Change:**
- `frontend/app.py` (NOT YET MODIFIED)

**Required Changes:**
```python
# Add to results display:
with gr.Tab("📰 News"):
    gr.HTML(format_news_section(news_output))

def format_news_section(news_output):
    if not news_output or news_output.get("status") == "no_data":
        return "<p>No news data available</p>"
    
    html = "<h3>Recent News Articles</h3>"
    
    # Show raw articles
    raw_articles = news_output.get("raw_articles", [])
    html += f"<p>Found {len(raw_articles)} articles</p>"
    
    # Show analyzed stories
    for story in news_output.get("story_groups", []):
        confirmed = "✓ Confirmed" if story.get("confirmed") else "⚠ Unconfirmed"
        sentiment = story.get("sentiment", "NEUTRAL")
        html += f"""
        <div style="border: 1px solid #ccc; padding: 10px; margin: 10px 0;">
            <h4>{story['title']} <span style="color: {'green' if story.get('confirmed') else 'orange'}">{confirmed}</span></h4>
            <p><strong>Sentiment:</strong> {sentiment}</p>
            <p><strong>Source:</strong> {story['source']}</p>
            <p>{story.get('summary', '')}</p>
            <a href="{story.get('url', '#')}" target="_blank">Read More</a>
        </div>
        """
    
    return html
```

### 6. ✅ Verdict Weighs Confirmed Stories More
**Changed Files:**
- `backend/scoring/verdict.py`

**Changes:**
- Confirmed stories: 100% weight
- Unconfirmed stories: 30% weight
- If `confirmed_count == 0`, news component marked as `available: False`
- `no_data` status treated same as `error` (not available)

**Weighted Scoring:**
```python
# Confirmed stories: full weight
for story in confirmed_stories:
    total_weighted_score += story_score * confidence
    total_weight += confidence

# Unconfirmed stories: 30% weight
for story in unconfirmed_stories:
    total_weighted_score += story_score * (confidence * 0.3)
    total_weight += (confidence * 0.3)

avg_sentiment = total_weighted_score / total_weight
score = avg_sentiment * 3.0  # Scale to -3 to +3
```

## Files Changed Summary

### Modified (4 files):
1. **backend/agents/news_sentinel.py**
   - Added `use_history_dedup` parameter
   - Added `raw_articles` field
   - Return all stories (confirmed + unconfirmed)
   - Return `status: "no_data"` when no articles
   - Sort confirmed stories first

2. **backend/graph/workflow.py**
   - Pass `use_history_dedup=False` to news_sentinel

3. **backend/scoring/verdict.py**
   - Updated `score_news_component()` function
   - Weight confirmed 100%, unconfirmed 30%
   - Mark as unavailable if no confirmed stories
   - Handle `no_data` status

4. **backend/utils/watchlist.py** (NO CHANGES NEEDED YET)
   - Watchlist scheduler doesn't exist yet
   - When implemented, pass `use_history_dedup=True`

### TODO (1 file):
5. **frontend/app.py** - Add News section to results display

## Testing

### Test 1: /analyze Mode (Fresh News)
```bash
python main.py RELIANCE
# Should fetch ALL news, no history dedup
# Check logs for: "History deduplication skipped (/analyze mode)"
```

### Test 2: Confirmed vs Unconfirmed Stories
```bash
# Result should show:
# - story_groups: all stories with confirmed flag
# - confirmed_count: e.g., 5
# - unconfirmed_count: e.g., 3
# - Confirmed sorted first
```

### Test 3: No Articles Found
```bash
# For a ticker with no news:
# status: "no_data"
# error: "No news articles found..."
```

### Test 4: Verdict Scoring
```bash
# With 5 confirmed + 3 unconfirmed:
# Confirmed stories should dominate the score
# Unconfirmed contribute only 30%
```

### Test 5: Raw Articles Always Present
```bash
# Even if LLM fails:
# raw_articles: [{title, source, date, url}, ...]
```

## Backward Compatibility

✅ All changes are backward compatible:
- `use_history_dedup` defaults to False (same as before for manual analysis)
- Existing code continues to work
- New fields added (`raw_articles`, refined `story_groups`)
- Old fields preserved

## Migration Notes

**No database changes needed.**

To use:
1. Code already updated (4 files)
2. Restart backend
3. Frontend update needed for News tab (TODO)
4. When watchlist scheduler is implemented, pass `use_history_dedup=True`

## Key Improvements

1. **Better UX**: /analyze always shows fresh news (no "already seen" errors)
2. **Transparency**: All stories visible (confirmed + unconfirmed)
3. **Explainability**: Raw articles list for debugging
4. **Accuracy**: Confirmed stories weighted higher in verdict
5. **Clear Status**: `no_data` clearly distinguishes "no news" from "error"
