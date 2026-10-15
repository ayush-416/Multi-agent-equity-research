# FinSight Fixes Summary

## Issues Fixed

### 1. ✅ yfinance Failure (HDFCBANK.NS, ^NSEI)
**Problem:** Custom curl_cffi session caused "'str' object has no attribute 'name'" errors
**Fix:** Removed custom curl_cffi session from `backend/tools/financial_tools.py`. Vanilla yfinance works reliably without the Chrome impersonation session.
**Files Changed:**
- `backend/tools/financial_tools.py` - Removed `_get_curl_session()` and all `session=` parameters

### 2. ✅ Cut Gemini API Calls (Free Tier Limit)
**Problem:** News sentinel made 1 LLM call per story, quickly exhausting 20 req/day limit
**Fixes Applied:**
- **Batched analysis**: Replaced per-story LLM calls with ONE batch call analyzing up to 8 stories
- **Story limit**: Cap at top 8 story groups (prioritizing confirmed stories)
- **Scheduler disabled**: Watchlist background job now disabled by default
- **Configuration**: Added `GEMINI_FALLBACK_MODEL` and `ENABLE_WATCHLIST_SCHEDULER` env vars

**Files Changed:**
- `backend/agents/news_sentinel.py` - New `_analyze_story_groups_batch()` function
- `main.py` - Scheduler only starts if `ENABLE_WATCHLIST_SCHEDULER=true`
- `.env.example` - Added new config options

**API Call Reduction:**
- Before: ~10-15 calls per analysis (1 per story)
- After: ~1-2 calls per analysis (1 batched call)

### 3. ✅ RAG Index Lookup (HDFC Bank)
**Problem:** Index exists as "HDFCBANK" folder but queries used "HDFC Bank" - name mismatch
**Fix:** Added company name normalization in `backend/rag/retriever.py`:
- Removes spaces/special chars first: "HDFC Bank" → "HDFCBANK"
- Then removes common suffixes: "Reliance Industries" → "RELIANCE"

**Files Changed:**
- `backend/rag/retriever.py` - New `_normalize_company_name()` function

### 4. ✅ Filing Analyst Status Reporting
**Problem:** Agent returned "completed successfully" even when no context retrieved
**Fix:** Added proper status tracking in `backend/agents/filing_analyst.py`:
- New fields: `rag_status` and `context_retrieved`
- Returns `partial_success` with clear error when no data found

**Files Changed:**
- `backend/agents/filing_analyst.py` - Added RAG status tracking

### 5. ✅ Verdict Failure Handling
**Problem:** Failed agents counted as score 0, resulting in misleading "HOLD (0.0)" verdicts
**Fix:** Modified `backend/scoring/verdict.py`:
- Exclude failed agents from weighted score calculation
- Return "INSUFFICIENT DATA" verdict when ALL agents fail (instead of "HOLD (0.0)")
- Only normalize scores when SOME (not all) components fail

**Files Changed:**
- `backend/scoring/verdict.py` - Updated `compute_investment_verdict()`

## Configuration Changes

Add to your `.env` file (copy from `.env.example`):
```bash
# Gemini models
GEMINI_MODEL=gemini-2.5-flash
GEMINI_FALLBACK_MODEL=gemini-1.5-flash

# Disable watchlist scheduler by default (saves API calls)
ENABLE_WATCHLIST_SCHEDULER=false
```

## What You Need to Run

### 1. Update Dependencies (if needed)
```bash
pip install -U yfinance
```

### 2. Run the Server
```bash
python main.py
```

### 3. Test HDFC Bank Analysis
The RAG index for HDFCBANK already exists in `data/vector_store/HDFCBANK/`. 
When you analyze HDFCBANK, it should now find the index successfully.

```bash
# Test via API
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"ticker": "HDFCBANK", "company_name": "HDFC Bank"}'
```

### 4. Optional: Enable Watchlist Scheduler
If you want the 10-minute background job:
```bash
# In .env file
ENABLE_WATCHLIST_SCHEDULER=true
```

## Expected Behavior After Fixes

1. **yfinance calls work** for HDFCBANK.NS and ^NSEI without errors
2. **News analysis uses ~1-2 API calls** instead of 10+ per ticker
3. **RAG retrieval succeeds** for "HDFC Bank" queries (normalizes to HDFCBANK)
4. **Filing analyst reports "no data"** status correctly instead of false success
5. **Verdict returns "INSUFFICIENT DATA"** when all agents fail (not "HOLD (0.0)")

## Files Modified Summary

- `backend/tools/financial_tools.py` - yfinance session fix
- `backend/agents/news_sentinel.py` - batched LLM calls
- `backend/rag/retriever.py` - company name normalization
- `backend/agents/filing_analyst.py` - status tracking
- `backend/scoring/verdict.py` - failure handling
- `main.py` - conditional scheduler
- `.env.example` - new config options
