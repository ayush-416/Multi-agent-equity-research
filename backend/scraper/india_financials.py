"""
Indian company financials scraper.

Fetches financial data from Yahoo Finance and Screener.in for Indian companies.
Provides structured data output for programmatic use.

Usage as library:
    from backend.scraper.india_financials import get_financials

    result = get_financials("Infosys")
    # Returns dict with ticker, company, currency, fetched_at, tables

Usage as CLI:
    python backend/scraper/india_financials.py "Infosys"
    python backend/scraper/india_financials.py TCS --source screener
    python backend/scraper/india_financials.py "reliance industries" --source both --out reliance.xlsx
"""
import argparse
import re
import sys
import time
from datetime import datetime
from io import StringIO
from typing import Dict, Tuple, Optional

import pandas as pd
import requests
import yfinance as yf
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


# ---------- 1. Resolve what the user typed to an NSE/BSE symbol ----------
def resolve_symbol(query: str) -> Tuple[str, str, str]:
    """
    Return (yahoo_symbol, nse_code, display_name) or raise ValueError.

    Args:
        query: Company name or ticker

    Returns:
        Tuple of (yahoo_symbol like "TCS.NS", nse_code like "TCS", display_name)
    """
    q = query.strip()

    # Already a ticker like INFY.NS / TCS.BO
    if re.fullmatch(r"[A-Za-z0-9&\-]+\.(NS|BO)", q, re.I):
        sym = q.upper()
        return sym, sym.split(".")[0], sym

    try:
        quotes = yf.Search(q, max_results=15).quotes
    except Exception as e:
        raise ValueError(f"Search failed: {e}")

    indian = [x for x in quotes if x.get("symbol", "").endswith((".NS", ".BO"))]
    if not indian:
        # maybe the user typed a bare NSE code, e.g. "TCS"
        for suffix in (".NS", ".BO"):
            try:
                if not yf.Ticker(q.upper() + suffix).history(period="5d").empty:
                    return q.upper() + suffix, q.upper(), q.upper()
            except Exception:
                pass
        raise ValueError(f"No NSE/BSE listing found for '{query}'")

    indian.sort(key=lambda x: 0 if x["symbol"].endswith(".NS") else 1)  # prefer NSE
    best = indian[0]
    name = best.get("longname") or best.get("shortname") or best["symbol"]
    return best["symbol"], best["symbol"].split(".")[0], name


# ---------- 2a. Yahoo Finance ----------
def fetch_yahoo(symbol: str) -> Tuple[dict, str]:
    """
    Fetch Yahoo Finance data.

    Returns:
        Tuple of (tables_dict, currency)
    """
    t = yf.Ticker(symbol)

    # Detect currency from ticker info
    try:
        info = t.info
        currency = info.get("currency", "INR")
    except:
        currency = "INR"

    tables = {
        "Y_Income_Annual": t.income_stmt,
        "Y_Balance_Annual": t.balance_sheet,
        "Y_CashFlow_Annual": t.cashflow,
        "Y_Income_Quarterly": t.quarterly_income_stmt,
    }

    # Filter out empty tables
    filtered = {k: v for k, v in tables.items() if v is not None and not v.empty}

    return filtered, currency


# ---------- 2b. Screener.in ----------
SCREENER_SECTIONS = {
    "quarters": "S_Quarterly_Results",
    "profit-loss": "S_Profit_Loss",
    "balance-sheet": "S_Balance_Sheet",
    "cash-flow": "S_Cash_Flow",
    "ratios": "S_Ratios",
    "shareholding": "S_Shareholding",
}


def fetch_screener(nse_code: str) -> Tuple[dict, str, Optional[dict]]:
    """
    Fetch Screener.in data with 3-second delays between requests.

    Returns:
        Tuple of (tables_dict, currency, text_sections_dict)
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    html = None
    for variant in ("consolidated/", ""):  # prefer consolidated, fall back to standalone
        url = f"https://www.screener.in/company/{nse_code}/{variant}"
        r = session.get(url, timeout=20)
        if r.status_code == 200 and 'id="profit-loss"' in r.text:
            html = r.text
            break
        time.sleep(3)  # 3-second delay between requests

    if html is None:
        raise RuntimeError(
            f"Screener page not found for '{nse_code}' "
            "(symbol may differ, or the site blocked the request)"
        )

    soup = BeautifulSoup(html, "lxml")

    # Extract text sections for filing_analyst
    text_sections = {}

    # Company info section
    company_info = soup.find("div", class_="company-info")
    if company_info:
        text_sections["company_info"] = company_info.get_text(strip=True, separator=" ")

    # Pros and Cons
    pros = soup.find("div", class_="pros")
    if pros:
        text_sections["pros"] = pros.get_text(strip=True, separator=" ")

    cons = soup.find("div", class_="cons")
    if cons:
        text_sections["cons"] = cons.get_text(strip=True, separator=" ")

    # Extract tables
    out = {}
    for sec_id, sheet in SCREENER_SECTIONS.items():
        section = soup.find("section", id=sec_id)
        if not section:
            continue
        table = section.find("table")
        if not table:
            continue
        df = pd.read_html(StringIO(str(table)))[0]
        df.rename(columns={df.columns[0]: "Item"}, inplace=True)
        df["Item"] = df["Item"].astype(str).str.replace(r"\s*\+$", "", regex=True)
        out[sheet] = df

    # Screener uses INR
    return out, "INR", text_sections if text_sections else None


# ---------- 3. Main API Function ----------
def get_financials(name_or_ticker: str, source: str = "both") -> dict:
    """
    Fetch financial data for an Indian company.

    Args:
        name_or_ticker: Company name or ticker (e.g., "Infosys" or "INFY")
        source: "yahoo", "screener", or "both" (default: "both")

    Returns:
        Dict with structure:
        {
            "ticker": str,  # e.g., "TCS.NS"
            "nse_code": str,  # e.g., "TCS"
            "company": str,  # display name
            "currency": str,  # "INR" or "USD"
            "fetched_at": str,  # ISO timestamp
            "tables": {
                table_name: dict (DataFrame converted to dict with orient='records')
            },
            "text_sections": dict or None,  # From Screener
            "sources": list,  # ["yahoo", "screener"]
            "errors": list  # Any errors encountered
        }
    """
    try:
        symbol, nse_code, name = resolve_symbol(name_or_ticker)
    except ValueError as e:
        return {
            "ticker": name_or_ticker,
            "nse_code": None,
            "company": name_or_ticker,
            "currency": None,
            "fetched_at": datetime.utcnow().isoformat(),
            "tables": {},
            "text_sections": None,
            "sources": [],
            "errors": [str(e)]
        }

    tables = {}
    text_sections = None
    sources = []
    errors = []
    currency = "INR"  # default

    # Fetch from Yahoo
    if source in ("yahoo", "both"):
        try:
            yahoo_tables, yahoo_currency = fetch_yahoo(symbol)
            tables.update(yahoo_tables)
            currency = yahoo_currency
            sources.append("yahoo")
            logger.info(f"Yahoo fetch succeeded for {symbol}: {len(yahoo_tables)} tables")
        except Exception as e:
            error_msg = f"Yahoo failed: {str(e)}"
            errors.append(error_msg)
            logger.warning(f"Yahoo fetch failed for {symbol}: {e}")

    # Fetch from Screener
    if source in ("screener", "both"):
        try:
            screener_tables, screener_currency, screener_text = fetch_screener(nse_code)
            tables.update(screener_tables)
            text_sections = screener_text
            # Prefer Screener's INR currency for Indian companies
            if screener_tables:
                currency = screener_currency
            sources.append("screener")
            logger.info(f"Screener fetch succeeded for {nse_code}: {len(screener_tables)} tables")
        except Exception as e:
            error_msg = f"Screener failed: {str(e)}"
            errors.append(error_msg)
            logger.warning(f"Screener fetch failed for {nse_code}: {e}")

    # Convert DataFrames to dicts for JSON serialization
    serialized_tables = {}
    for table_name, df in tables.items():
        try:
            # Convert to dict with records orientation
            serialized_tables[table_name] = df.to_dict(orient='records')
        except Exception as e:
            errors.append(f"Failed to serialize {table_name}: {str(e)}")

    return {
        "ticker": symbol,
        "nse_code": nse_code,
        "company": name,
        "currency": currency,
        "fetched_at": datetime.utcnow().isoformat(),
        "tables": serialized_tables,
        "text_sections": text_sections,
        "sources": sources,
        "errors": errors
    }


# ---------- 4. Save Excel (for CLI use) ----------
def save_excel(tables: dict, path: str):
    """Save tables to Excel file."""
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        for name, df in tables.items():
            if isinstance(df, list):
                # Convert back from serialized format
                df = pd.DataFrame(df)
            keep_index = not name.startswith("S_")  # screener tables have an Item column
            df.to_excel(xw, sheet_name=name[:31], index=keep_index)
    print(f"\nSaved {len(tables)} sheets -> {path}")


# ---------- 5. CLI ----------
def main():
    ap = argparse.ArgumentParser(description="Fetch Indian company financials")
    ap.add_argument("company", help="Company name or ticker, e.g. 'Infosys' or TCS")
    ap.add_argument("--source", choices=["yahoo", "screener", "both"], default="both")
    ap.add_argument("--out", help="Output .xlsx path")
    args = ap.parse_args()

    print(f"Fetching data for: {args.company}")

    result = get_financials(args.company, source=args.source)

    if result["errors"]:
        print("\nErrors encountered:")
        for error in result["errors"]:
            print(f"  - {error}")

    if not result["tables"]:
        sys.exit("\nNo data retrieved.")

    print(f"\nResolved: {result['company']} ({result['ticker']})")
    print(f"Currency: {result['currency']}")
    print(f"Sources: {', '.join(result['sources'])}")

    # Print table previews
    for name, records in result["tables"].items():
        df = pd.DataFrame(records)
        print(f"\n=== {name} ===")
        print(df.head(8).to_string())

    # Save to Excel if requested
    if args.out:
        # Convert back to DataFrames for Excel export
        df_tables = {k: pd.DataFrame(v) for k, v in result["tables"].items()}
        save_excel(df_tables, args.out)
    else:
        out_file = f"{result['nse_code']}_financials.xlsx"
        df_tables = {k: pd.DataFrame(v) for k, v in result["tables"].items()}
        save_excel(df_tables, out_file)


if __name__ == "__main__":
    main()
