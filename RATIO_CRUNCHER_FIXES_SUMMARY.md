# Ratio Cruncher Fixes Summary

## Issues Fixed

### 1. **Removed Hardcoded Default Values (roe_pct = 0.0 bug)**

**Location**: `backend/tools/financial_tools.py` lines 273-283, 269

**Problem**: 
- `info.get("returnOnEquity", 0)` defaulted to `0`, creating false `roe_pct = 0.0` instead of `None`
- Same issue for `roa_pct`, `dividend_yield_pct`, and margin percentages

**Fix**:
```python
# BEFORE (WRONG):
"roe_pct": round(info.get("returnOnEquity", 0) * 100, 2) if info.get("returnOnEquity") else None

# AFTER (CORRECT):
"roe_pct": round(info.get("returnOnEquity") * 100, 2) if info.get("returnOnEquity") is not None else None
```

**Changed fields**:
- `roe_pct`: No longer defaults to 0, now properly returns `None` when unavailable
- `roa_pct`: No longer defaults to 0, now properly returns `None` when unavailable
- `dividend_yield_pct`: No longer defaults to 0, now properly returns `None` when unavailable
- `gross_margins_pct`: Proper None checking
- `operating_margins_pct`: Proper None checking
- `profit_margins_pct`: Proper None checking

---

### 2. **Added india_financials.get_financials as Fallback**

**Location**: `backend/agents/ratio_cruncher.py`

**Problem**: 
- When yfinance fails, the old scraper fallback didn't fill all required fields
- No proper extraction of sector, market_cap_cr, revenue_cr, net_income_cr, 52w high/low

**Fix**:
- Replaced `_try_scraper_fallback()` with `_try_india_financials_fallback()`
- Uses `backend.scraper.india_financials.get_financials()` to fetch Screener data
- Properly extracts all ratio fields from Screener ratios table

**New function**: `_try_india_financials_fallback(ticker, company_name)`
- Fetches from Screener.in via `india_financials.get_financials()`
- Parses S_Ratios table for: pe_ratio, pb_ratio, roe_pct, roa_pct, debt_to_equity, current_ratio, dividend_yield_pct, margins, market_cap_cr, revenue_cr, net_income_cr, current_price, 52w_high, 52w_low
- Extracts sector from company_info text sections using regex
- Properly tags results with `source: "india_financials"`, `currency: "INR"`, and `as_of` timestamp

**New function**: `_parse_india_financials_ratios(ratios_table)`
- Parses Screener ratios table into standardized format
- Extracts latest values from rightmost column
- Filters out None values
- Returns only available ratios

---

### 3. **Currency Checking and Warnings**

**Location**: 
- `backend/tools/financial_tools.py` line 260 (added currency field)
- `backend/agents/ratio_cruncher.py` lines 84-86 (currency warning)

**Problem**: 
- USD Yahoo financials were mixed with INR prices without warning
- No way to detect currency mismatches

**Fix**:
- Added `currency` field to yfinance results: `"currency": info.get("currency", "INR")`
- Added currency mismatch detection in ratio_cruncher:
  ```python
  currency = stock_info.get("currency", "INR")
  if currency != "INR":
      logger.warning(f"Data is in {currency}, not INR - may not align with Indian stock prices")
      result["currency_warning"] = f"Financial data is in {currency}, not INR"
  ```
- Fallback data from india_financials is always in INR and properly tagged

---

### 4. **Proper no_data Status When Ratios Are Empty**

**Location**: `backend/agents/ratio_cruncher.py`

**Problem**: 
- When no ratios available, status was "error" or "success" with generic messages
- Claimed "no concerns" even when data was completely missing

**Fix**:

**A. Check for empty ratios and return no_data status (lines 115-121)**:
```python
# Check if we have any meaningful data
non_null_ratios = {k: v for k, v in ratios.items() if v is not None}
if not non_null_ratios:
    logger.warning(f"No ratios available for {ticker}")
    result["status"] = "no_data"
    result["error"] = "No financial ratios available from any source"
    return result
```

**B. Updated `_analyze_ratios()` to avoid generic messages when empty (lines 266-273)**:
```python
# Don't add generic messages if we have no data at all
# Only add them if we have SOME ratios but no clear signals
has_any_ratios = any(v is not None for v in ratios.values())

if not strengths and has_any_ratios:
    strengths.append("No standout positive ratio signals identified")
if not concerns and has_any_ratios:
    concerns.append("No major concerns identified in available ratios")
```

**C. Updated `_generate_valuation_summary()` to handle empty ratios (lines 293-296)**:
```python
# Check if we have any ratios at all
has_any_ratios = any(v is not None for v in ratios.values())
if not has_any_ratios:
    return "No financial ratio data available for valuation assessment"
```

**D. Better error messages showing which fields are missing**:
```python
if not summary_parts:
    # We have some ratios but couldn't build a summary
    available_fields = [k for k, v in ratios.items() if v is not None]
    return f"Limited financial data available (found: {', '.join(available_fields[:3])})"
```

---

### 5. **Enhanced financial_tools.py Fallback**

**Location**: `backend/tools/financial_tools.py`

**Updates to `_fetch_from_scraper_fallback()`**:
- Renamed internal usage to work with india_financials
- Now extracts sector, market_cap_cr, revenue_cr, net_income_cr
- Properly handles quarterly results table

**Updates to `_parse_screener_ratios()`**:
- Added `roa_pct` extraction
- Added market cap (Cr) and conversion to absolute value
- Added revenue_cr, net_income_cr extraction
- Added current_price, 52w_high, 52w_low extraction
- Added eps and book_value extraction

---

## Result Tracking

All ratio results now include:
- `source`: "yfinance", "india_financials", "snapshot"
- `as_of`: ISO timestamp of when data was fetched
- `currency`: "INR", "USD", etc.
- `currency_warning`: Optional warning if currency != INR

---

## Status Flow

1. **"success"**: Ratios available + sector benchmarks available
2. **"partial_success"**: Ratios available but no sector benchmarks
3. **"no_data"**: No ratios available from any source
4. **"error"**: Exception during processing

---

## Testing Recommendations

1. Test with ticker that has no yfinance data → should fallback to Screener
2. Test with ticker that has USD data → should show currency warning
3. Test with ticker that has no data anywhere → should return no_data with clear message
4. Test with ticker that has partial data → should show only available fields
5. Verify roe_pct is None (not 0.0) when unavailable from yfinance
