"""
Comprehensive snapshot parser for converting disk snapshots into full stock_info format.

Computes all required ratios from Screener tables: S_Profit_Loss, S_Balance_Sheet, S_Ratios.
Returns data in the same shape as yfinance stock_info for seamless fallback.
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def parse_snapshot_to_stock_info(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert snapshot data to full stock_info format.

    Extracts ratios from:
    - S_Ratios table (ROCE, etc.)
    - S_Profit_Loss table (sales, profit, margins)
    - S_Balance_Sheet table (equity, debt, assets)

    Computes derived ratios:
    - ROE, ROA, profit margins, debt ratios, etc.

    Args:
        snapshot: Snapshot dict from load_snapshot()

    Returns:
        Dict in stock_info format with pe_ratio, pb_ratio, roe_pct, roa_pct,
        debt_to_equity, current_ratio, margins, market_cap, revenue, net_income,
        current_price, 52w_high, 52w_low, source, as_of
    """
    tables = snapshot.get("tables", {})

    result = {
        "ticker": snapshot.get("ticker"),
        "company_name": snapshot.get("company"),
        "sector": "",  # Not available in snapshot
        "currency": snapshot.get("currency", "INR"),
        "source": "snapshot",
        "as_of": snapshot.get("fetched_at") or snapshot.get("_snapshot_created_at"),
    }

    # Parse S_Ratios table
    ratios_table = tables.get("S_Ratios", [])
    if ratios_table:
        ratios_data = _parse_ratios_table(ratios_table)
        result.update(ratios_data)

    # Parse S_Profit_Loss table
    pl_table = tables.get("S_Profit_Loss", [])
    if pl_table:
        pl_data = _parse_profit_loss_table(pl_table)
        result.update(pl_data)

    # Parse S_Balance_Sheet table
    bs_table = tables.get("S_Balance_Sheet", [])
    if bs_table:
        bs_data = _parse_balance_sheet_table(bs_table)
        result.update(bs_data)

    # Compute derived ratios from P&L and B/S
    if pl_table and bs_table:
        derived = _compute_derived_ratios(pl_table, bs_table)
        result.update(derived)

    return result


def _parse_ratios_table(ratios_table: list) -> Dict[str, Any]:
    """Parse S_Ratios table for direct ratio values."""
    result = {}

    # Convert to dict lookup
    rows = {row.get("Item", ""): row for row in ratios_table}

    def get_latest(item_name):
        """Get latest value (rightmost non-TTM column)."""
        row = rows.get(item_name)
        if not row:
            return None
        # Get columns excluding 'Item' and 'TTM'
        cols = [k for k in row.keys() if k not in ("Item", "TTM")]
        if not cols:
            return None
        # Sort to get latest (e.g., "Mar 2026")
        cols_sorted = sorted(cols)
        latest_col = cols_sorted[-1]
        val = row.get(latest_col)
        if val and val != "-":
            try:
                cleaned = str(val).replace(",", "").replace("%", "")
                return float(cleaned)
            except:
                return None
        return None

    # Extract available ratios
    result["roe_pct"] = get_latest("ROCE %") or get_latest("ROE %")
    result["roa_pct"] = get_latest("ROA %")

    # Note: P/E, P/B, dividend yield usually not in S_Ratios for snapshots
    # They would be computed from price + fundamentals

    return {k: v for k, v in result.items() if v is not None}


def _parse_profit_loss_table(pl_table: list) -> Dict[str, Any]:
    """Parse S_Profit_Loss table for revenue, profit, margins."""
    result = {}

    rows = {row.get("Item", ""): row for row in pl_table}

    def get_latest(item_name):
        """Get latest value."""
        row = rows.get(item_name)
        if not row:
            return None
        # Prefer TTM, else latest annual
        if "TTM" in row and row["TTM"] not in (None, "-", ""):
            val = row["TTM"]
        else:
            cols = [k for k in row.keys() if k != "Item" and k != "TTM"]
            if not cols:
                return None
            cols_sorted = sorted(cols)
            latest_col = cols_sorted[-1]
            val = row.get(latest_col)

        if val and val != "-":
            try:
                cleaned = str(val).replace(",", "").replace("%", "")
                return float(cleaned)
            except:
                return None
        return None

    # Revenue (in Cr)
    sales_cr = get_latest("Sales")
    if sales_cr:
        result["revenue_cr"] = sales_cr
        result["revenue"] = sales_cr * 1e7  # Convert Cr to absolute

    # Net Income (in Cr)
    net_profit_cr = get_latest("Net Profit")
    if net_profit_cr:
        result["net_income_cr"] = net_profit_cr
        result["net_income"] = net_profit_cr * 1e7

    # Operating margin
    opm_pct = get_latest("OPM %")
    if opm_pct:
        result["operating_margins_pct"] = opm_pct

    # Net profit margin
    if sales_cr and net_profit_cr and sales_cr > 0:
        result["profit_margins_pct"] = round((net_profit_cr / sales_cr) * 100, 2)

    return {k: v for k, v in result.items() if v is not None}


def _parse_balance_sheet_table(bs_table: list) -> Dict[str, Any]:
    """Parse S_Balance_Sheet table for equity, debt, assets."""
    result = {}

    rows = {row.get("Item", ""): row for row in bs_table}

    def get_latest(item_name):
        """Get latest value."""
        row = rows.get(item_name)
        if not row:
            return None
        cols = [k for k in row.keys() if k not in ("Item", "TTM")]
        if not cols:
            return None
        cols_sorted = sorted(cols)
        latest_col = cols_sorted[-1]
        val = row.get(latest_col)

        if val and val != "-":
            try:
                cleaned = str(val).replace(",", "")
                return float(cleaned)
            except:
                return None
        return None

    # Get key balance sheet items (in Cr)
    equity_cr = get_latest("Equity Capital") or get_latest("Total Shareholders Funds")
    debt_cr = get_latest("Total Debt") or get_latest("Borrowings")
    current_assets_cr = get_latest("Current Assets")
    current_liab_cr = get_latest("Current Liabilities")

    # Debt to Equity
    if debt_cr is not None and equity_cr and equity_cr > 0:
        result["debt_to_equity"] = round(debt_cr / equity_cr, 2)

    # Current Ratio
    if current_assets_cr and current_liab_cr and current_liab_cr > 0:
        result["current_ratio"] = round(current_assets_cr / current_liab_cr, 2)

    return {k: v for k, v in result.items() if v is not None}


def _compute_derived_ratios(pl_table: list, bs_table: list) -> Dict[str, Any]:
    """Compute derived ratios from P&L and Balance Sheet."""
    result = {}

    pl_rows = {row.get("Item", ""): row for row in pl_table}
    bs_rows = {row.get("Item", ""): row for row in bs_table}

    def get_latest(rows, item_name):
        """Get latest value from rows."""
        row = rows.get(item_name)
        if not row:
            return None
        # Prefer TTM for P&L
        if "TTM" in row and row["TTM"] not in (None, "-", ""):
            val = row["TTM"]
        else:
            cols = [k for k in row.keys() if k not in ("Item", "TTM")]
            if not cols:
                return None
            cols_sorted = sorted(cols)
            latest_col = cols_sorted[-1]
            val = row.get(latest_col)

        if val and val != "-":
            try:
                return float(str(val).replace(",", ""))
            except:
                return None
        return None

    # Get values
    net_profit_cr = get_latest(pl_rows, "Net Profit")
    equity_cr = get_latest(bs_rows, "Equity Capital") or get_latest(bs_rows, "Total Shareholders Funds")
    total_assets_cr = get_latest(bs_rows, "Total Assets")

    # ROE (if not already extracted from S_Ratios)
    if "roe_pct" not in result and net_profit_cr and equity_cr and equity_cr > 0:
        result["roe_pct"] = round((net_profit_cr / equity_cr) * 100, 2)

    # ROA
    if net_profit_cr and total_assets_cr and total_assets_cr > 0:
        result["roa_pct"] = round((net_profit_cr / total_assets_cr) * 100, 2)

    return {k: v for k, v in result.items() if v is not None}
