"""
Helper functions for deriving financial ratios from scraper data.

Handles currency mismatches and extracts ratios from Screener/Yahoo tables.
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def derive_ratios_from_scraper(scraper_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Derive financial ratios from scraper tables.

    Args:
        scraper_data: Result from get_financials() or snapshot

    Returns:
        Dict with derived ratios in same format as yfinance
    """
    tables = scraper_data.get("tables", {})
    currency = scraper_data.get("currency", "INR")

    result = {
        "ticker": scraper_data.get("ticker"),
        "company_name": scraper_data.get("company"),
        "currency": currency,
        "source": "scraper_derived",
        "ratios": {}
    }

    # Priority 1: Use Screener Ratios table (most reliable, in INR)
    if "S_Ratios" in tables:
        ratios = _parse_screener_ratios(tables["S_Ratios"])
        result["ratios"].update(ratios)

    # Priority 2: Derive from Profit/Loss and Balance Sheet
    if "S_Profit_Loss" in tables and "S_Balance_Sheet" in tables:
        derived = _derive_from_statements(
            tables["S_Profit_Loss"],
            tables["S_Balance_Sheet"]
        )
        # Only add if not already present from ratios table
        for key, val in derived.items():
            if key not in result["ratios"] and val is not None:
                result["ratios"][key] = val

    # Priority 3: Yahoo data if available (but check currency)
    if currency != "INR":
        logger.warning(f"Yahoo data is in {currency}, not INR - may not match Indian prices")

    return result


def _parse_screener_ratios(ratios_table: list) -> Dict[str, Any]:
    """
    Parse Screener ratios table.

    Args:
        ratios_table: List of dicts from S_Ratios

    Returns:
        Dict with extracted ratios
    """
    ratios = {}

    # Convert to lookup
    rows = {row.get("Item", ""): row for row in ratios_table}

    def get_latest(item_name):
        """Get latest value from rightmost column."""
        row = rows.get(item_name)
        if not row:
            return None
        # Get last non-Item column
        cols = [k for k in row.keys() if k != "Item"]
        if not cols:
            return None
        latest_col = cols[-1]
        val = row.get(latest_col)
        if val and val != "-":
            try:
                cleaned = str(val).replace(",", "").replace("%", "")
                return float(cleaned)
            except:
                return None
        return None

    # Map Screener items to our format
    ratios["pe_ratio"] = get_latest("Stock P/E")
    ratios["pb_ratio"] = get_latest("Price to book value")
    ratios["dividend_yield_pct"] = get_latest("Dividend yield %")
    ratios["roe_pct"] = get_latest("ROCE %") or get_latest("ROE %")
    ratios["debt_to_equity"] = get_latest("Debt to equity")
    ratios["operating_margins_pct"] = get_latest("OPM %")
    ratios["profit_margins_pct"] = get_latest("Net Profit Margin %")
    ratios["current_ratio"] = get_latest("Current ratio")
    ratios["interest_coverage"] = get_latest("Interest coverage")

    # EPS and Book Value
    ratios["eps"] = get_latest("EPS in Rs")
    ratios["book_value"] = get_latest("Book value")

    return {k: v for k, v in ratios.items() if v is not None}


def _derive_from_statements(profit_loss: list, balance_sheet: list) -> Dict[str, Any]:
    """
    Derive ratios from P&L and balance sheet.

    Args:
        profit_loss: S_Profit_Loss table
        balance_sheet: S_Balance_Sheet table

    Returns:
        Dict with derived ratios
    """
    derived = {}

    # Convert to lookup
    pl_rows = {row.get("Item", ""): row for row in profit_loss}
    bs_rows = {row.get("Item", ""): row for row in balance_sheet}

    def get_latest(rows, item_name):
        """Get latest value."""
        row = rows.get(item_name)
        if not row:
            return None
        cols = [k for k in row.keys() if k != "Item"]
        if not cols:
            return None
        latest_col = cols[-1]
        val = row.get(latest_col)
        if val and val != "-":
            try:
                return float(str(val).replace(",", ""))
            except:
                return None
        return None

    # Revenue and margins
    revenue = get_latest(pl_rows, "Sales")
    net_profit = get_latest(pl_rows, "Net Profit")
    operating_profit = get_latest(pl_rows, "Operating Profit")

    if revenue and revenue > 0:
        if net_profit is not None:
            derived["profit_margins_pct"] = round((net_profit / revenue) * 100, 2)
        if operating_profit is not None:
            derived["operating_margins_pct"] = round((operating_profit / revenue) * 100, 2)

    # ROE
    equity = get_latest(bs_rows, "Equity Capital") or get_latest(bs_rows, "Total Shareholders Funds")
    if equity and equity > 0 and net_profit is not None:
        derived["roe_pct"] = round((net_profit / equity) * 100, 2)

    # Debt to Equity
    total_debt = get_latest(bs_rows, "Total Debt") or get_latest(bs_rows, "Borrowings")
    if total_debt is not None and equity and equity > 0:
        derived["debt_to_equity"] = round(total_debt / equity, 2)

    # Current Ratio
    current_assets = get_latest(bs_rows, "Current Assets")
    current_liabilities = get_latest(bs_rows, "Current Liabilities")
    if current_assets and current_liabilities and current_liabilities > 0:
        derived["current_ratio"] = round(current_assets / current_liabilities, 2)

    return derived


def get_text_sections_for_filing(scraper_data: Dict[str, Any]) -> Optional[str]:
    """
    Extract text sections from scraper data for filing_analyst context.

    Args:
        scraper_data: Result from get_financials()

    Returns:
        Combined text string or None
    """
    text_sections = scraper_data.get("text_sections")
    if not text_sections:
        return None

    combined = []

    company = scraper_data.get("company", "")
    if company:
        combined.append(f"Company: {company}")

    if "company_info" in text_sections:
        combined.append(f"Company Info: {text_sections['company_info']}")

    if "pros" in text_sections:
        combined.append(f"Strengths: {text_sections['pros']}")

    if "cons" in text_sections:
        combined.append(f"Concerns: {text_sections['cons']}")

    return "\n\n".join(combined) if combined else None
