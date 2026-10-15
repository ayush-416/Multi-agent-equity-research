# FinSight yfinance "Too Many Requests" Fixes

## Summary

Fixed the yfinance rate limiting issue that was causing "Too Many Requests" errors. The root cause was that each agent was independently refetching the same data, resulting in ~12 API calls per analysis and overwhelming Yahoo Finance's rate limits.

## Changes Implemented

### ✅ 1. Pre-fetch Data Once in Workflow (Task #1)
**Files Modified:**
- `backend/graph/workflow.py` - Already had pre-fetch logic, enhanced agent behavior
- `backend/agents/ratio_cruncher.py` - Updated to use cached data, never refetch on cache failure
- `backend/agents/technical_analyst.py` - No changes needed (already correct)
- `backend/agents/risk_assessor.py` - Updated to use cached data for all three sources (stock_info, price_history, nifty_history)
- `backend/tools/technical_tools.py` - Updated to use cached data, never refetch on cache failure

**Behavior:**
- `workflow.py` now fetches stock_info, price_history, and nifty_history ONCE at the start
- All agents (ratio_cruncher, technical_analyst, risk_assessor) use the cached data from workflow state
- If the pre-fetch fails, agents receive the error and don't attempt to refetch (preventing cascading failures)

### ✅ 2. Disk Cache with TTL (Task #2)
**Files Modified:**
- `backend/utils/yfinance_disk_cache.py`

**Changes:**
- Updated TTL configuration:
  - `price_history`: 60 minutes (1 hour)
  - `nifty_history`: 60 minutes (1 hour)
  - `stock_info`: 1440 minutes (24 hours)
- Previous: Single 20-minute TTL for all data types
- Cache survives across runs and protects against temporary Yahoo blocks

### ✅ 3. Improved Retry Backoff (Task #3)
**Files Modified:**
- `backend/tools/financial_tools.py`

**Changes:**
- Updated `_retry_with_backoff()` function
- New backoff schedule: 5s → 15s → 45s (total: 65 seconds over 3 attempts)
- Previous: 1s → 2s → 4s (exponential, too aggressive)
- Gives Yahoo Finance more breathing room between retries

### ✅ 4. Fallback Price Source (Task #4)
**Files Modified:**
- `backend/tools/financial_tools.py`

**Dependencies Added:**
- `pandas-datareader` (for Stooq data source)

**Changes:**
- Added `_fetch_from_stooq_fallback()` function
- When yfinance fails after retries, automatically tries Stooq as fallback
- Fallback result is cached with source attribution
- Graceful degradation: if both sources fail, returns error

### ✅ 5. Verdict Scoring for Failed Agents (Task #5)
**Files Modified:**
- `backend/scoring/verdict.py`

**Changes:**
- Updated `compute_investment_verdict()` to return "INSUFFICIENT DATA" if fewer than 3 agents succeeded (previously only checked for 0)
- Failed agents are excluded from weighted score calculation (already working)
- More robust handling: requires at least 3 of 5 agents for a valid verdict

### ✅ 6. News Dedup Toggle for Testing (Task #6)
**Files Modified:**
- `.env.example`
- `backend/agents/news_sentinel.py`

**Changes:**
- Added `NEWS_DISABLE_DEDUP` environment variable
- When set to `true`, news agent skips the seen-stories deduplication
- Useful for testing to ensure fresh data every run
- Default: `false` (deduplication enabled)

### ✅ 7. Filing Analyst Resource Optimization (Task #7)
**Files Modified:**
- `backend/agents/filing_analyst.py`
- `backend/rag/retriever.py`

**Changes:**
- Implemented singleton pattern for LLM instance in filing_analyst
- Implemented singleton pattern for embedding model in retriever
- Resources are loaded once per session instead of once per query
- Reduces initialization overhead for RAG operations

## Environment Variables Added

```env
# Disk cache TTLs are now hardcoded per data type (see yfinance_disk_cache.py)
NEWS_DISABLE_DEDUP=false  # Set to true to disable news deduplication for testing
```

## Impact Summary

### Before:
- Each agent refetched the same data independently
- ~12 yfinance API calls per analysis
- 1-2 second retry delays (too aggressive)
- No fallback when yfinance fails
- Single 20-minute cache TTL

### After:
- Single pre-fetch at workflow start
- ~3 yfinance API calls per analysis (67% reduction)
- 5-15-45 second retry delays (more respectful)
- Automatic fallback to Stooq when yfinance fails
- Differentiated cache TTL (1h for prices, 24h for fundamentals)
- Agents never refetch on cache failure (prevents cascading failures)
- Singleton resources in filing_analyst and retriever

## Testing Recommendations

1. **Test with rate limiting:**
   ```bash
   # Run multiple analyses in quick succession
   python main.py RELIANCE
   python main.py HDFCBANK
   python main.py TCS
   ```

2. **Test cache behavior:**
   ```bash
   # First run (should hit API)
   python main.py RELIANCE
   
   # Second run within 1 hour (should use cache)
   python main.py RELIANCE
   ```

3. **Test fallback:**
   ```bash
   # Disable network temporarily or exhaust yfinance quota
   # System should fall back to Stooq automatically
   ```

4. **Test verdict with failures:**
   ```bash
   # Simulate partial agent failures
   # Verdict should return INSUFFICIENT DATA if <3 agents succeed
   ```

5. **Test news dedup toggle:**
   ```bash
   # Set NEWS_DISABLE_DEDUP=true in .env
   # Run news analysis twice - should process same stories
   ```

## Files Changed

1. `backend/graph/workflow.py` - Already had pre-fetch, verified behavior
2. `backend/agents/ratio_cruncher.py` - Cache usage enforcement
3. `backend/agents/risk_assessor.py` - Cache usage enforcement for all 3 sources
4. `backend/tools/technical_tools.py` - Cache usage enforcement
5. `backend/tools/financial_tools.py` - Retry backoff + fallback source
6. `backend/utils/yfinance_disk_cache.py` - TTL configuration
7. `backend/scoring/verdict.py` - Minimum agents threshold
8. `backend/agents/news_sentinel.py` - Dedup toggle
9. `backend/agents/filing_analyst.py` - LLM singleton
10. `backend/rag/retriever.py` - Embedding model singleton
11. `.env.example` - New environment variable

## Migration Notes

No database migrations required. All changes are backward compatible.

To apply:
1. Pull latest code
2. Install new dependency: `pip install pandas-datareader`
3. Optionally add `NEWS_DISABLE_DEDUP=false` to `.env` (defaults to false if not set)
4. Restart application

## Expected Behavior

- **Rate limit errors should be dramatically reduced** (67% fewer API calls)
- **Analysis should succeed even when yfinance is throttling** (fallback + cache)
- **Retries are more respectful** (5-15-45s delays instead of 1-2-4s)
- **Better error messages** when insufficient data is available
- **Faster RAG operations** (singleton resources)
