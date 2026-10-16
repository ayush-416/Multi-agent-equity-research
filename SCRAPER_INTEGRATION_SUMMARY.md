# India Financials Scraper Integration - Complete

## Summary

Successfully integrated `india_financials.py` scraper as a comprehensive fallback data source for FinSight AI. The scraper fetches financial data from Yahoo Finance and Screener.in with 24-hour caching and 3-second rate limiting.

## Implementation Status

### ✅ 1. Refactored india_financials.py
- **Location**: `backend/scraper/india_financials.py`
- **Changes**:
  - Added `get_financials(name_or_ticker)` function returning structured dict
  - Returns: `{ticker, nse_code, company, currency, fetched_at, tables, text_sections, sources, errors}`
  - Tables serialized as dicts for JSON compatibility
  - Currency detection (INR vs USD) included
  - Text sections extracted from Screener (pros/cons/company_info)
  - CLI interface preserved
  - No printing in the function (logging only)

### ✅ 2. Snapshot System with Caching
- **Location**: `backend/scraper/snapshot_loader.py`
- **Features**:
  - Saves successful scraper results to `data/snapshots/<TICKER>.json`
  - 24-hour TTL for Screener data
  - 3-second delays between Screener requests (rate limiting)
  - Functions:
    - `save_snapshot(data)` - Save scraper result
    - `load_snapshot(ticker, max_age_hours)` - Load cached data
    - `get_cached_or_fetch(ticker)` - Smart cache-or-fetch
    - `list_snapshots()` - View all cached data

### ✅ 3. Financial Tools Integration
- **Location**: `backend/tools/financial_tools.py`
- **Fallback Chain**: yfinance → scraper → disk snapshot
- **Changes**:
  - Updated `get_stock_info()` to try scraper fallback on yfinance failure
  - Added `get_scraper_data(ticker)` for internal agent use
  - Added helper functions:
    - `_fetch_from_scraper_fallback()` - Try scraper
    - `_fetch_from_snapshot_fallback()` - Try disk snapshot
    - `_parse_screener_ratios()` - Extract ratios from Screener tables
  - All results tagged with `source` and `as_of` fields

### ✅ 4. Ratio Cruncher Integration
- **Location**: `backend/agents/ratio_cruncher.py`
- **Helper**: `backend/utils/scraper_helpers.py`
- **Features**:
  - Derives ratios from scraper when yfinance fails
  - Uses `derive_ratios_from_scraper()` to extract:
    - Margins, growth, ROE, debt/equity, P/E from Screener tables
    - Falls back to deriving from P&L and balance sheet
  - Currency awareness: warns if USD financials vs INR prices
  - Prefers Screener's INR ratios over Yahoo USD
  - Added `_try_scraper_fallback()` function

### ⚠️ 5. Risk Assessor - Partial Implementation
**Status**: Needs completion
**TODO**: Add balance sheet leverage from scraper when price data missing

```python
# In risk_assessor.py - add this logic:
if not has_price_data:
    scraper_data = get_scraper_data(ticker)
    if scraper_data:
        # Extract debt-to-equity from balance sheet
        bs_table = scraper_data['tables'].get('S_Balance_Sheet')
        if bs_table:
            # Parse total debt and equity
            # Calculate leverage metrics
            # Mark output as "partial" - no market risk, only financial risk
```

### ⚠️ 6. Filing Analyst - Partial Implementation
**Status**: Needs completion
**TODO**: Add Screener text sections as extra context

```python
# In filing_analyst.py - before LLM call:
from backend.utils.scraper_helpers import get_text_sections_for_filing

scraper_text = get_text_sections_for_filing(get_scraper_data(ticker))
if scraper_text:
    # Append to context_text before sending to LLM
    context_text += "\n\n--- Screener.in Data ---\n" + scraper_text
```

### ✅ 7. Warm Cache Script
- **Location**: `scripts/warm_cache.py`
- **Usage**: `python scripts/warm_cache.py`
- **Features**:
  - Pre-fetches data for demo tickers (RELIANCE, HDFCBANK, INFY, TCS, WIPRO)
  - Runs one at a time with 3-second delays
  - Saves all to snapshots for instant analysis

## Table → Agent Mapping

### Yahoo Finance Tables
| Table | Agent(s) | Purpose |
|-------|----------|---------|
| Y_Income_Annual | ratio_cruncher | Revenue, margins, net profit |
| Y_Balance_Annual | ratio_cruncher, risk_assessor | Assets, liabilities, equity, debt |
| Y_CashFlow_Annual | ratio_cruncher | Free cash flow, operating cash |
| Y_Income_Quarterly | ratio_cruncher | Recent quarterly trends |

### Screener.in Tables
| Table | Agent(s) | Purpose |
|-------|----------|---------|
| S_Quarterly_Results | ratio_cruncher | Recent performance trends |
| S_Profit_Loss | ratio_cruncher | Revenue, profit margins, growth |
| S_Balance_Sheet | ratio_cruncher, risk_assessor | Debt, equity, current ratio, leverage |
| S_Cash_Flow | ratio_cruncher | Operating cash flow, FCF |
| S_Ratios | ratio_cruncher, risk_assessor | PE, PB, ROE, D/E, margins (most reliable) |
| S_Shareholding | (not used yet) | Promoter stake, pledging |

### Screener.in Text Sections
| Section | Agent(s) | Purpose |
|---------|----------|---------|
| company_info | filing_analyst | Business description |
| pros | filing_analyst | Strengths and positives |
| cons | filing_analyst | Concerns and negatives |

## Currency Handling

- **Screener**: Always INR (₹ crores)
- **Yahoo**: May be USD for ADRs, INR for .NS tickers
- **Logic**: Prefer Screener INR ratios, warn if USD financials mixed with INR prices
- **Field**: All results include `currency` field

## Installation

```bash
# Install scraper dependencies
pip install yfinance requests beautifulsoup4 lxml pandas openpyxl

# No additional changes needed - already have pandas
```

## Usage Examples

### Pre-warm Cache
```bash
python scripts/warm_cache.py
```

### Use in Agents (automatic fallback)
```python
# ratio_cruncher automatically tries scraper if yfinance fails
result = run_ratio_cruncher("RELIANCE", "Reliance Industries")
# Result will have source="scraper" if fell back

# Check what data source was used
print(result.get("source"))  # "yfinance", "scraper", or "snapshot"
```

### Direct Scraper Access
```python
from backend.scraper.india_financials import get_financials

data = get_financials("TCS")
print(f"Company: {data['company']}")
print(f"Currency: {data['currency']}")
print(f"Tables: {list(data['tables'].keys())}")
print(f"Sources: {data['sources']}")
```

## Frontend Integration - TODO

**Status**: Not yet implemented
**Required**: Add "Scraped Data" tab to show explainability

```python
# In frontend/app.py - add new tab:
with gr.Tab("📊 Scraped Data"):
    scraped_output = gr.JSON(
        label="Raw Scraper Data",
        value={}
    )

# Update analyze_stock() to return scraper data:
scraper_data = get_scraper_data(ticker)
return (...existing..., format_json(scraper_data))
```

## Testing

```bash
# Test scraper directly
python backend/scraper/india_financials.py "Infosys"
python backend/scraper/india_financials.py TCS --source screener

# Test with FinSight (will use scraper if yfinance fails)
python main.py RELIANCE

# Warm cache for all demo tickers
python scripts/warm_cache.py
```

## Benefits

1. **Resilience**: 3-layer fallback (yfinance → scraper → snapshot)
2. **Indian Market Focus**: Screener provides 10+ years of INR data
3. **Better Ratios**: Screener ratios more accurate for Indian companies
4. **Rate Limit Protection**: 24h cache + 3s delays
5. **Explainability**: Source tagging shows which data came from where
6. **Offline Capable**: Snapshots work even when external APIs fail

## Remaining Work

1. **risk_assessor**: Add balance sheet leverage from scraper (10 lines)
2. **filing_analyst**: Add Screener text sections to context (5 lines)
3. **frontend**: Add "Scraped Data" tab for explainability (20 lines)

All core infrastructure is complete and working!
