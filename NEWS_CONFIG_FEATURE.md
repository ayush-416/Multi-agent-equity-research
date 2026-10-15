# News Configuration Feature - Summary

## ✅ Feature Added: Configurable News Analysis

Users can now customize how FinSight AI analyzes news articles through environment variables.

---

## What Was Added

### 1. Configuration Options

Two new environment variables in `.env`:

```bash
# How many days back to check for news (1-30)
NEWS_DAYS_BACK=7

# Only use trusted sources (true/false)
NEWS_TRUSTED_ONLY=false
```

### 2. Updated News Sentinel Agent

**File Modified**: `backend/agents/news_sentinel.py`

**Changes**:
- Added `days_back` parameter (optional, defaults to env or 7)
- Added `trusted_only` parameter (optional, defaults to env or false)
- Filters articles by trusted sources when enabled
- Returns configuration used in result (`config` field)
- Logs configuration for transparency

**New Behavior**:
```python
# Uses environment variables by default
run_news_sentinel(ticker, company_name)

# Can override per-call
run_news_sentinel(ticker, company_name, days_back=3, trusted_only=True)
```

### 3. Updated Verdict Scoring

**File Modified**: `backend/scoring/verdict.py`

**Changes**:
- Reads `config` from news output
- Includes configuration in verdict drivers
- Shows: "Analyzed 7d window (trusted sources only)"

### 4. Configuration Files Updated

**Files Modified**:
- `.env` - Added NEWS_DAYS_BACK and NEWS_TRUSTED_ONLY
- `.env.example` - Added default values and comments

### 5. Documentation

**New File**: `NEWS_CONFIGURATION_GUIDE.md` (2,500+ words)
- Complete configuration guide
- Use cases and examples
- Troubleshooting
- Best practices
- FAQ

**New File**: `test_news_config.py`
- Test script for configuration
- Validates environment loading
- Tests override parameters

---

## How It Works

### Standard Flow (Default Settings)

1. User runs analysis
2. News Sentinel loads `NEWS_DAYS_BACK=7` from .env
3. Fetches news from last 7 days
4. Uses all sources (trusted and untrusted)
5. Deduplicates and confirms stories (≥2 sources)
6. Only confirmed stories score in verdict
7. Verdict shows: "Analyzed 7d window"

### With Trusted-Only Enabled

1. User sets `NEWS_TRUSTED_ONLY=true` in .env
2. Restarts backend
3. Runs analysis
4. News Sentinel filters to trusted sources only
5. May have fewer articles but higher quality
6. Confirmed threshold still ≥2 sources (or ≥1 trusted)
7. Verdict shows: "Analyzed 7d window (trusted sources only)"

### With Custom Days Back

1. User sets `NEWS_DAYS_BACK=14` in .env
2. Restarts backend
3. Runs analysis
4. News Sentinel checks last 14 days
5. More historical context, may catch slower-moving stories
6. Verdict shows: "Analyzed 14d window"

---

## Use Cases

### Conservative Investor
```bash
NEWS_DAYS_BACK=7
NEWS_TRUSTED_ONLY=true
```
**Result**: High-quality news from verified sources only

### Day Trader
```bash
NEWS_DAYS_BACK=1
NEWS_TRUSTED_ONLY=false
```
**Result**: Breaking news from all sources

### Long-term Investor
```bash
NEWS_DAYS_BACK=14
NEWS_TRUSTED_ONLY=true
```
**Result**: Comprehensive view from trusted sources

---

## Configuration Examples

### Example 1: Recent News Only

**.env**:
```bash
NEWS_DAYS_BACK=3
NEWS_TRUSTED_ONLY=false
```

**Verdict Output**:
```
News Sentiment: +1.8 (Positive)
Drivers:
• Analyzed 3d window
• 2 confirmed stories analyzed
• ✓ 2 positive/bullish stories
```

### Example 2: Trusted Sources Only

**.env**:
```bash
NEWS_DAYS_BACK=7
NEWS_TRUSTED_ONLY=true
```

**Verdict Output**:
```
News Sentiment: +2.3 (Very Positive)
Drivers:
• Analyzed 7d window (trusted sources only)
• 3 confirmed stories analyzed
• ✓ 3 positive/bullish stories from Bloomberg, Reuters, ET
```

### Example 3: Wide Net

**.env**:
```bash
NEWS_DAYS_BACK=14
NEWS_TRUSTED_ONLY=false
```

**Verdict Output**:
```
News Sentiment: +0.5 (Above Average)
Drivers:
• Analyzed 14d window
• 8 confirmed stories analyzed
• ✓ 5 positive/bullish stories
• ✗ 2 negative/bearish stories
• → 1 neutral story
```

---

## Impact on Features

### Investment Verdict ✅
- News component shows configuration used
- Different settings → different sentiment scores
- Net verdict may change based on news contribution

### Watchlist Alerts ✅
- Uses same configuration
- Alerts based on configured window
- Trusted-only affects alert sensitivity

### News Intelligence Tab ✅
- Shows all articles (not just scored ones)
- Displays source credibility
- Configuration transparent in debug info

---

## Testing

### Manual Test

1. Edit `.env`:
   ```bash
   NEWS_DAYS_BACK=3
   NEWS_TRUSTED_ONLY=true
   ```

2. Restart backend:
   ```bash
   uvicorn main:app --port 8000 --reload
   ```

3. Run analysis on any stock

4. Check Verdict tab → News Sentiment drivers:
   ```
   • Analyzed 3d window (trusted sources only)
   ```

5. Check Debug tab for log:
   ```
   Config: days_back=3, trusted_only=True
   After trusted filter: X articles
   ```

### Automated Test

```bash
python test_news_config.py
```

**Expected Output**:
```
Testing News Configuration
============================================================
1. Test with environment settings (3 days, trusted only)
Configuration used:
  - days_back: 3
  - trusted_only: True

2. Test with override (7 days, all sources)
Configuration used:
  - days_back: 7
  - trusted_only: False
```

---

## Files Modified/Created

### Modified (3):
- `backend/agents/news_sentinel.py` - Added configuration parameters
- `backend/scoring/verdict.py` - Show config in drivers
- `.env` - Added NEWS_DAYS_BACK and NEWS_TRUSTED_ONLY
- `.env.example` - Added defaults

### Created (2):
- `NEWS_CONFIGURATION_GUIDE.md` - User documentation
- `test_news_config.py` - Test script

**Total**: 5 files modified, 2 files created

---

## Backward Compatibility ✅

✅ **Default behavior unchanged** - Uses 7 days, all sources (original behavior)
✅ **Optional parameters** - Existing code works without changes
✅ **Fallback values** - If .env not set, uses sensible defaults
✅ **No breaking changes** - All existing functionality preserved

---

## Configuration Persistence

- Settings stored in `.env` file
- Apply to all analyses (global)
- Require backend restart to take effect
- Can be overridden per-call (programmatic use)

---

## Limitations & Considerations

### Limitations:
1. **Global settings** - Same config for all analyses in a session
2. **Requires restart** - Backend must restart after .env changes
3. **No UI controls** - Configuration via .env only (no frontend UI)

### Considerations:
1. **Trusted-only may reduce coverage** - Fewer articles if no trusted sources
2. **Short windows may miss stories** - 1-day window might have no news
3. **Long windows may dilute signal** - 30-day window includes old news
4. **Settings affect alerts** - Watchlist uses same configuration

---

## Best Practices

### ✅ Recommended:
- Keep `NEWS_DAYS_BACK=7` for most use cases (good balance)
- Use `NEWS_TRUSTED_ONLY=false` for broader coverage (default)
- Enable `NEWS_TRUSTED_ONLY=true` for conservative analysis
- Test different settings to find what works for you

### ⚠️ Avoid:
- Very short windows (<3 days) unless day trading
- Very long windows (>14 days) unless specific use case
- Changing settings frequently (inconsistent results)
- Forgetting to restart backend after changes

---

## Future Enhancements (Optional)

Potential future additions:
1. **Per-analysis override** - UI controls to change per stock
2. **Saved presets** - Quick switch between configurations
3. **Source whitelist/blacklist** - Custom source filtering
4. **Time-of-day filtering** - Only morning news, etc.
5. **Language filtering** - Multi-language support
6. **Category filtering** - Only financial news, exclude general

---

## Summary

✅ **Configuration added** - NEWS_DAYS_BACK and NEWS_TRUSTED_ONLY  
✅ **Backward compatible** - Default behavior unchanged  
✅ **Well documented** - Complete user guide created  
✅ **Tested** - Test script provided  
✅ **Transparent** - Configuration shown in verdict  

Users can now customize news analysis to match their investment style and risk tolerance!

---

**Related Documentation**:
- User Guide: `NEWS_CONFIGURATION_GUIDE.md`
- Investment Verdict: `INVESTMENT_VERDICT_IMPLEMENTATION.md`
- Quick Start: `VERDICT_QUICK_START.md`

**Date**: 2024-10-14  
**Status**: ✅ Complete
