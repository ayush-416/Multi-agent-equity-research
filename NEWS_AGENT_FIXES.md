# News Agent Fixes Summary

## Issues Fixed

### 1. Sentiment Always Showing "Unavailable" ✅
**Problem**: News sentiment was always "UNKNOWN" even when articles were fetched.

**Root Causes**:
- Stories needed ≥2 trusted sources to be "confirmed"
- Most stories only had 1 source each (not deduplicated across outlets)
- When no confirmed stories existed, sentiment wasn't computed at all
- LLM quota exceeded → all sentiments fell back to "NEUTRAL"

**Fixes Applied**:
1. **Tiered sentiment computation**:
   - First try: Use confirmed stories (≥2 trusted sources)
   - Fallback 1: Use single-source trusted stories when `trusted_only=False`
   - Fallback 2: Use all unconfirmed stories (marked as "partial" status)

2. **Rule-based sentiment analyzer** when LLM fails:
   - Analyzes headline keywords (surge, soar, jump, gain, profit, rise, etc.)
   - Positive keywords → POSITIVE sentiment
   - Negative keywords → NEGATIVE sentiment
   - Much better than blanket "NEUTRAL"

**Files Modified**: `backend/agents/news_sentinel.py`

---

### 2. Added Trusted Sources Toggle ✅

**Feature**: Control whether to strictly require trusted sources or accept all sources.

**Configuration**: Set in `.env` file:

```bash
# Only use articles from trusted sources for sentiment scoring
NEWS_TRUSTED_ONLY=false   # Default: accepts single-source trusted articles

# Set to true for strict mode (requires ≥2 trusted sources)
NEWS_TRUSTED_ONLY=true
```

**Behavior**:

| Mode | Behavior |
|------|----------|
| `false` (default) | Accepts single-source articles from trusted outlets (Business Standard, Reuters, Moneycontrol, etc.) |
| `true` | Requires ≥2 independent trusted sources to confirm a story |

**Trusted Sources List** (in `backend/config/news_config.py`):
- Economic Times, LiveMint, Business Standard, Financial Express
- Reuters, Bloomberg, Wall Street Journal, Financial Times
- Moneycontrol, Investing.com
- BSE, NSE, SEBI (official sources)
- Major Indian newspapers (Hindu BusinessLine, Times of India, etc.)

---

## Testing Results

### Before Fix
```
Status: partial
Sentiment: UNKNOWN
Sentiment Score: 0.0
Error: No confirmed stories
```

### After Fix
```
Status: ok
Sentiment: POSITIVE
Sentiment Score: 0.3
Positive drivers: 3 stories identified
  - "Reliance Jio IPO skyrockets RIL share price..."
  - "Jio listing could trigger 47% upside..."
  - "RIL rises 3% as Jio IPO date out..."
```

---

## How It Works Now

### Story Confirmation Logic

1. **Fetch articles** from Google News RSS (20 articles)
2. **Filter by date** (last 7 days by default)
3. **Deduplicate** similar headlines into story groups
4. **Tag credibility** for each source:
   - Trusted (Business Standard, Reuters, etc.)
   - Unverified (blogs, aggregators, etc.)
5. **Mark confirmation**:
   - Confirmed: ≥2 trusted sources report the same story
   - Unconfirmed: Single source or unverified sources

### Sentiment Computation Priority

1. **Best**: Use confirmed stories (multi-source)
2. **Good**: Use single-source trusted stories (when `trusted_only=false`)
3. **Fallback**: Use all stories (marked as "partial" status)

### LLM Analysis with Fallback

1. **Primary**: Gemini LLM analyzes all stories in one batch call
2. **Fallback**: Rule-based keyword analysis if LLM fails/quota exceeded
   - Positive: surge, soar, jump, gain, profit, rise, growth, upside, target, boost, IPO
   - Negative: fall, drop, decline, loss, bearish, downside, concern, weak, risk, warning

---

## Configuration Options

All configurable via `.env` file:

```bash
# Number of days to look back for news (default: 7)
NEWS_DAYS_BACK=7

# Only use trusted sources (default: false)
NEWS_TRUSTED_ONLY=false

# Disable deduplication for testing (default: false)
NEWS_DISABLE_DEDUP=false
```

---

## Files Modified

- `backend/agents/news_sentinel.py`
  - Added tiered sentiment computation
  - Added rule-based sentiment fallback
  - Fixed aggregate computation logic

---

## Status Values

The news agent now returns:

| Status | Meaning |
|--------|---------|
| `ok` | Sentiment computed from confirmed or trusted stories |
| `partial` | Sentiment computed from unverified stories only |
| `no_data` | No articles found or all filtered out |
| `error` | Failed to fetch or process articles |

---

## What You Can Do

### View All Stories (Including Unconfirmed)
All story groups are always returned in `result["story_groups"]`, with:
- `confirmed` flag (True/False)
- `trusted_count` (number of trusted sources)
- `sentiment` (POSITIVE/NEGATIVE/NEUTRAL)
- `sources` list
- `urls` list

### Toggle Strict Mode
Edit `.env`:
```bash
NEWS_TRUSTED_ONLY=true  # Strict: requires ≥2 trusted sources
```

### Adjust Time Window
Edit `.env`:
```bash
NEWS_DAYS_BACK=14  # Look back 14 days instead of 7
```

---

## Notes

- **LLM Quota**: If you see "Based on headline keywords" in reasoning, it means LLM quota was hit
- **Single Source Stories**: Most news stories come from single sources initially; deduplication happens over time
- **Trusted Sources**: You can add more sources to `backend/config/news_config.py` → `TRUSTED_SOURCES` set
