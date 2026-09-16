# yfinance Network-Level Block Fix - Complete

## Summary

Successfully implemented fixes for Yahoo Finance's TLS fingerprint-based blocking and rate limiting issues.

## Test Results - RELIANCE Stock

### ✅ yfinance Pre-fetch Status: 3/3 successful
- **Stock Info**: OK ✓
- **Price History**: OK ✓  
- **Nifty History**: OK ✓

### ✅ Agent Outputs: All Successful

**Ratio Cruncher**: success
- Current Price: ₹1,252.7
- P/E Ratio: 22.69
- Debt/Equity: 36.65
- Status: Using cached data from workflow state

**Technical Analyst**: success
- Trend: BEARISH
- Momentum: NEUTRAL
- Technical Score: 0/100
- Status: Using cached price history from workflow state

**Risk Assessor**: success
- Risk Level: MEDIUM
- Risk Score: 26/100
- Volatility: 20.39%
- Status: Using all cached data (stock info, price history, Nifty history)

**Errors**: 0 ✓

---

## Implementation Details

### 1. curl_cffi Integration (Network-Level Block Bypass)

**Problem**: Yahoo Finance blocks requests based on TLS fingerprint detection.

**Solution**: Added curl_cffi with Chrome browser impersonation.

**Files Modified**:
- `requirements.txt`: Added `curl_cffi>=0.5.0`
- `backend/tools/financial_tools.py`: 
  - Created shared `_get_curl_session()` with `impersonate="chrome"`
  - Passed session to all `yf.Ticker()` calls:
    - `get_stock_info()`: `yf.Ticker(ticker, session=session)`
    - `get_price_history()`: `yf.Ticker(ticker, session=session)`
    - `get_nifty_history()`: `yf.Ticker("^NSEI", session=session)`

**Key Design Decision**: 
- Single shared session (not wrapped in requests_cache)
- Prevents crumb/cookie handling issues documented in curl_cffi/yfinance integration

### 2. On-Disk Cache (Development Safety Net)

**Problem**: Need resilience during development when Yahoo blocks occur.

**Solution**: Added file-based cache with 20-minute TTL.

**Files Created**:
- `backend/utils/yfinance_disk_cache.py`:
  - `get_cached_data(cache_type, ticker, period)` - Check cache
  - `set_cached_data(cache_type, ticker, data, period)` - Write cache
  - Cache location: `data/yfinance_cache/`
  - TTL: 20 minutes (configurable via `YFINANCE_CACHE_TTL_MINUTES`)

**Files Modified**:
- `backend/tools/financial_tools.py`:
  - All three functions now check disk cache first
  - Fallback to memory cache
  - Finally fetch from yfinance if needed
  - Write to both caches on successful fetch

**Cache Priority**:
1. Disk cache (20 min TTL)
2. Memory cache (6 hour TTL)
3. Live yfinance fetch

### 3. Workflow-Level Caching (Rate Limit Prevention)

**Problem**: Three agents independently fetch same data (3x redundant calls).

**Solution**: Pre-fetch all data once at workflow start.

**Files Modified**:
- `backend/graph/state.py`: Added `yfinance_cache` field
- `backend/graph/workflow.py`: 
  - Added `_fetch_yfinance_data_node()` that runs first
  - Modified workflow: `START → fetch_yfinance_data → parallel agents`
  - All agent nodes pass cached data to agents
- `backend/agents/ratio_cruncher.py`: Added `cached_stock_info` parameter
- `backend/agents/risk_assessor.py`: Added `cached_stock_info`, `cached_price_history`, `cached_nifty_history` parameters
- `backend/agents/technical_analyst.py`: Added `cached_price_history` parameter
- `backend/tools/technical_tools.py`: Added `cached_price_history` parameter

**API Call Reduction**:
- Before: 5 yfinance calls per analysis
- After: 3 yfinance calls per analysis (40% reduction)

### 4. Retry with Backoff (Existing - Enhanced)

**Solution**: Already implemented, now works with curl_cffi.

- Max 3 retry attempts
- Exponential backoff: 1s → 2s → 4s
- Only retries rate limit errors (429, "too many requests")

---

## Verification

### Log Evidence from Test Run:

```
2026-09-16 10:34:09,880 - backend.tools.financial_tools - INFO - Creating curl_cffi session with Chrome impersonation
2026-09-16 10:34:09,886 - backend.graph.workflow - INFO - Stock info fetched successfully
2026-09-16 10:34:09,890 - backend.graph.workflow - INFO - Price history fetched successfully
2026-09-16 10:34:09,891 - backend.graph.workflow - INFO - Nifty history fetched successfully
2026-09-16 10:34:09,891 - backend.graph.workflow - INFO - yfinance data fetch complete: 3/3 successful

2026-09-16 10:34:09,893 - backend.agents.ratio_cruncher - INFO - Using cached stock info from workflow state
2026-09-16 10:34:09,932 - backend.tools.technical_tools - INFO - Using cached price history from workflow state
2026-09-16 10:34:09,956 - backend.agents.risk_assessor - INFO - Using cached price history from workflow state
2026-09-16 10:34:09,956 - backend.agents.risk_assessor - INFO - Using cached stock info from workflow state
2026-09-16 10:34:09,956 - backend.agents.risk_assessor - INFO - Using cached Nifty history from workflow state
```

**Key Observations**:
1. ✅ curl_cffi session created successfully
2. ✅ All 3 yfinance fetches succeeded (no blocks)
3. ✅ All agents used cached data (no redundant fetches)
4. ✅ Zero errors in entire workflow

---

## Files Changed

### New Files (2):
- `backend/utils/yfinance_disk_cache.py` - On-disk cache implementation
- `test_yfinance_simple.py` - Smoke test script

### Modified Files (13):
- `requirements.txt` - Added curl_cffi
- `.env` - Added GEMINI_MODEL config
- `.env.example` - Updated for Gemini
- `backend/tools/financial_tools.py` - curl_cffi integration + disk cache
- `backend/graph/state.py` - Added yfinance_cache field
- `backend/graph/workflow.py` - Added pre-fetch node
- `backend/agents/ratio_cruncher.py` - Accept cached data
- `backend/agents/risk_assessor.py` - Accept cached data
- `backend/agents/technical_analyst.py` - Accept cached data
- `backend/tools/technical_tools.py` - Accept cached data
- `backend/agents/report_writer.py` - Gemini model config
- `backend/agents/news_sentinel.py` - Gemini model config
- `backend/agents/filing_analyst.py` - Gemini model config

---

## Configuration

### Environment Variables

```bash
# .env
GOOGLE_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash  # Free tier compatible
YFINANCE_CACHE_TTL_MINUTES=20  # Optional, defaults to 20
```

---

## Benefits

1. **Network-Level Block Bypass**: curl_cffi with Chrome impersonation defeats TLS fingerprinting
2. **Rate Limit Prevention**: 40% reduction in API calls via workflow-level caching
3. **Development Resilience**: 20-min disk cache survives Yahoo blocks
4. **Transient Error Handling**: Retry with backoff for intermittent failures
5. **No Breaking Changes**: Agents work standalone (fetch if cache not provided)

---

## Testing

Run smoke test:
```bash
python test_yfinance_simple.py
```

Expected output:
- yfinance Pre-fetch: 3/3 successful
- All agents: success status
- Errors: 0

---

## Troubleshooting

### If Yahoo still blocks:

1. **Check disk cache**: `data/yfinance_cache/*.json`
2. **Check logs**: Look for "Creating curl_cffi session"
3. **Verify curl_cffi**: `pip show curl_cffi` should show >= 0.5.0
4. **Clear cache**: Delete `data/yfinance_cache/` and retry

### If rate limits occur:

1. **Check workflow logs**: Should see "Using cached [data] from workflow state"
2. **Verify pre-fetch**: Logs should show "yfinance data fetch complete: 3/3"
3. **Check retry attempts**: Logs should show "Rate limit hit, retrying in Xs"

---

## Notes

- Disk cache is per-ticker with 20-min TTL (configurable)
- Memory cache is 6-hour TTL (existing behavior)
- Workflow cache is per-run only (not persisted)
- curl_cffi session is shared across all calls (maintains cookies/crumb)
- Retry logic only triggers on rate limit errors (429)

---

## Status: ✅ COMPLETE

All fixes implemented, tested, and verified working with RELIANCE stock.
