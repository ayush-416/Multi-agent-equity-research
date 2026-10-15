# News Analysis Configuration Guide

## Overview

You can now customize how FinSight AI analyzes news articles by configuring:
1. **News age** - How many days back to check for news
2. **Trust filter** - Whether to only use trusted news sources

## Configuration Options

### 1. News Days Back

**Setting**: `NEWS_DAYS_BACK`  
**Default**: `7` (one week)  
**Valid values**: `1` to `30` (days)

Controls how far back in time the News Sentinel agent searches for articles.

**Examples**:
```bash
# Only analyze news from last 24 hours (breaking news)
NEWS_DAYS_BACK=1

# Standard week-long window (default)
NEWS_DAYS_BACK=7

# Look back 2 weeks for more context
NEWS_DAYS_BACK=14

# Full month of news coverage
NEWS_DAYS_BACK=30
```

**Use Cases**:
- **Short term (1-3 days)**: Focusing on immediate market reactions, earnings announcements
- **Medium term (7-14 days)**: General sentiment analysis (recommended)
- **Long term (14-30 days)**: Comprehensive trend analysis, slower-moving stories

### 2. Trusted Sources Only

**Setting**: `NEWS_TRUSTED_ONLY`  
**Default**: `false` (use all sources)  
**Valid values**: `true`, `false`

When enabled, only articles from pre-verified trusted sources are analyzed.

**Examples**:
```bash
# Use all available news sources (default)
NEWS_TRUSTED_ONLY=false

# Only use trusted sources
NEWS_TRUSTED_ONLY=true
```

**Trusted Sources Include**:
- Major financial news: Bloomberg, Reuters, Financial Times, WSJ, Economic Times
- Business media: Business Standard, Mint, Forbes, Fortune
- Major publications: The Hindu, Times of India, Indian Express
- Wire services: PTI, ANI

**Trade-offs**:

| Setting | Pros | Cons |
|---------|------|------|
| **false** (all sources) | More coverage, broader perspective, catch smaller stories | May include less reliable sources, more noise |
| **true** (trusted only) | Higher quality, more credible, less noise | May miss smaller stories, narrower perspective |

## How It Works

### News Scoring Flow

1. **Fetch**: Get recent news articles from Google News
2. **Filter by Date**: Keep only articles within `NEWS_DAYS_BACK` window
3. **Filter by Trust** (if enabled): Keep only articles from trusted sources
4. **Deduplicate**: Group similar stories together
5. **Verify**: Mark stories as "confirmed" if ≥2 sources (or ≥1 if trusted_only)
6. **Analyze**: LLM analyzes each story group for sentiment
7. **Score**: Only **confirmed** stories contribute to Investment Verdict

### Impact on Investment Verdict

The News Sentiment component of the Investment Verdict:
- **Only scores confirmed stories** (regardless of settings)
- **Shows configuration used** in the verdict display
- **Reports unconfirmed stories** separately (informational only)

**Example Output**:
```
News Sentiment: +2.1 (Positive)
Drivers:
• Analyzed 7d window (trusted sources only)
• 4 confirmed stories analyzed
• ✓ 3 positive/bullish stories
• ✓ 1 neutral story
• Weighted sentiment: 0.72
• (2 unconfirmed stories not scored)
```

## Configuration Guide by Use Case

### Conservative Investor
**Goal**: Only high-quality, verified news from reputable sources

```bash
NEWS_DAYS_BACK=7
NEWS_TRUSTED_ONLY=true
```

**Result**: High confidence in news analysis, but may miss some stories.

### Day Trader / Short-term
**Goal**: Latest breaking news and market reactions

```bash
NEWS_DAYS_BACK=1
NEWS_TRUSTED_ONLY=false
```

**Result**: Maximum coverage of recent events, broader perspective.

### Long-term Investor
**Goal**: Comprehensive sentiment over longer period

```bash
NEWS_DAYS_BACK=14
NEWS_TRUSTED_ONLY=true
```

**Result**: Balanced view of recent developments from trusted sources.

### General Use (Recommended)
**Goal**: Standard analysis with good balance

```bash
NEWS_DAYS_BACK=7
NEWS_TRUSTED_ONLY=false
```

**Result**: One week of news from all sources, filtered by confirmation.

## How to Configure

### Method 1: Environment Variables (Recommended)

Edit your `.env` file:

```bash
# News analysis settings
NEWS_DAYS_BACK=7
NEWS_TRUSTED_ONLY=false
```

Then restart the backend:
```bash
uvicorn main:app --port 8000 --reload
```

### Method 2: System Environment (Advanced)

**Windows**:
```cmd
set NEWS_DAYS_BACK=14
set NEWS_TRUSTED_ONLY=true
uvicorn main:app --port 8000 --reload
```

**Linux/Mac**:
```bash
export NEWS_DAYS_BACK=14
export NEWS_TRUSTED_ONLY=true
uvicorn main:app --port 8000 --reload
```

## Verification

After changing settings, run an analysis and check:

1. **Debug Tab**: Look for log messages:
   ```
   Config: days_back=7, trusted_only=True
   After date filter (7d): 15 articles
   After trusted filter: 8 articles (from 15)
   ```

2. **Verdict Tab**: Check News Sentiment drivers:
   ```
   • Analyzed 7d window (trusted sources only)
   ```

3. **News Intelligence Tab**: Review story groups and source credibility

## Best Practices

### ✅ Do:
- Use `NEWS_DAYS_BACK=7` for most analyses (good balance)
- Enable `NEWS_TRUSTED_ONLY=true` for conservative/risk-averse analysis
- Test different settings to see what works for your use case
- Check the "config" field in news output to verify settings

### ⚠️ Don't:
- Don't set `NEWS_DAYS_BACK` too high (>30) - older news loses relevance
- Don't set `NEWS_DAYS_BACK` to 0 - minimum is 1 day
- Don't expect same results with different settings - it's by design
- Don't forget to restart backend after changing .env

## Troubleshooting

### Issue: No news articles found

**Possible causes**:
1. `NEWS_DAYS_BACK` too short (e.g., 1 day but no news today)
2. `NEWS_TRUSTED_ONLY=true` but no trusted sources published recently
3. Company has limited news coverage

**Solutions**:
- Increase `NEWS_DAYS_BACK` to 7 or 14
- Disable `NEWS_TRUSTED_ONLY` temporarily
- Check "News Intelligence" tab for details

### Issue: All stories unconfirmed

**Possible causes**:
1. Each story only has 1 source
2. `NEWS_TRUSTED_ONLY=true` reduces source count

**Solutions**:
- Increase `NEWS_DAYS_BACK` to capture more sources
- Disable `NEWS_TRUSTED_ONLY` to allow more sources
- This is normal for smaller companies with limited coverage

### Issue: Settings not taking effect

**Possible causes**:
1. .env file not saved
2. Backend not restarted
3. Typo in setting name

**Solutions**:
- Save .env file
- Restart backend completely: Ctrl+C then re-run uvicorn
- Check spelling: `NEWS_DAYS_BACK` and `NEWS_TRUSTED_ONLY`
- Verify in logs: `Config: days_back=X, trusted_only=Y`

## Advanced: Programmatic Override

You can also pass settings directly when calling the news agent:

```python
from backend.agents.news_sentinel import run_news_sentinel

# Override settings for this call only
result = run_news_sentinel(
    ticker="RELIANCE",
    company_name="Reliance Industries",
    days_back=3,           # Override: 3 days instead of .env
    trusted_only=True      # Override: trusted only
)
```

This is useful for:
- Testing different configurations
- Building custom analysis workflows
- A/B testing news sensitivity

## FAQ

**Q: Should I always use trusted_only=true?**  
A: Not necessarily. False gives broader coverage. True gives higher quality. For most users, false (default) is fine because only confirmed stories are scored anyway.

**Q: What's the best NEWS_DAYS_BACK value?**  
A: 7 days is recommended for most use cases. Use 1-3 for short-term trading, 14-30 for long-term analysis.

**Q: Can I change settings per analysis?**  
A: Currently, settings are global via .env. For per-analysis control, you'd need to call the backend agents directly (advanced).

**Q: Do these settings affect the Investment Verdict?**  
A: Yes! News Sentiment is one of 5 components in the verdict. Different settings can change the verdict outcome.

**Q: Do these settings affect the watchlist alerts?**  
A: Yes, watchlist checks use the same news agent with the same settings.

**Q: Why is my verdict different now?**  
A: If you changed NEWS_DAYS_BACK or NEWS_TRUSTED_ONLY, the news sentiment changed, which affects the overall verdict score.

## Summary

- **NEWS_DAYS_BACK**: Controls time window (1-30 days, default 7)
- **NEWS_TRUSTED_ONLY**: Filters to trusted sources only (true/false, default false)
- Configuration shown in verdict drivers
- Settings apply to all analyses and watchlist checks
- Restart backend after changing .env

For most users, the defaults are fine. Adjust based on your investment style and risk tolerance.

---

**Related Documentation**:
- Investment Verdict: `INVESTMENT_VERDICT_IMPLEMENTATION.md`
- Quick Start: `VERDICT_QUICK_START.md`
- Main README: `README.md`
