"""
FinSight AI - Gradio Frontend

Multi-agent equity research platform for Indian stocks.
Provides an intuitive interface for stock analysis with tabbed results.
"""

import gradio as gr
import requests
import json
from typing import Dict, Any, Optional, Tuple


# Backend API configuration
API_BASE_URL = "http://localhost:8000"
API_ANALYZE_URL = f"{API_BASE_URL}/analyze"
API_HEALTH_URL = f"{API_BASE_URL}/health"
API_WATCHLIST_URL = f"{API_BASE_URL}/watchlist"
API_WATCHLIST_ADD_URL = f"{API_BASE_URL}/watchlist/add"
API_WATCHLIST_REMOVE_URL = f"{API_BASE_URL}/watchlist/remove"


# === Helper Functions ===


def check_backend_health() -> bool:
    """Check if FastAPI backend is running."""
    try:
        response = requests.get(API_HEALTH_URL, timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def format_json(data: Optional[Dict[str, Any]]) -> str:
    """Format dictionary as pretty JSON string."""
    if data is None:
        return "No data available"

    try:
        return json.dumps(data, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error formatting data: {str(e)}"


def format_ratios_display(ratio_output: Optional[Dict[str, Any]]) -> str:
    """Format financial ratios for display."""
    if not ratio_output or ratio_output.get("status") != "success":
        return format_json(ratio_output)

    ratios = ratio_output.get("ratios", {})

    display = "# Financial Ratios\n\n"

    # Profitability
    display += "## Profitability Metrics\n"
    display += f"- **ROE**: {ratios.get('roe_pct', 'N/A')}%\n"
    display += f"- **ROA**: {ratios.get('roa_pct', 'N/A')}%\n"
    display += f"- **Net Margin**: {ratios.get('net_margin_pct', 'N/A')}%\n"
    display += f"- **Gross Margin**: {ratios.get('gross_margin_pct', 'N/A')}%\n\n"

    # Leverage
    display += "## Leverage Metrics\n"
    display += f"- **Debt-to-Equity**: {ratios.get('debt_to_equity', 'N/A')}\n"
    display += f"- **Interest Coverage**: {ratios.get('interest_coverage', 'N/A')}x\n\n"

    # Liquidity
    display += "## Liquidity Metrics\n"
    display += f"- **Current Ratio**: {ratios.get('current_ratio', 'N/A')}\n"
    display += f"- **Quick Ratio**: {ratios.get('quick_ratio', 'N/A')}\n\n"

    # Efficiency
    display += "## Efficiency Metrics\n"
    display += f"- **Asset Turnover**: {ratios.get('asset_turnover', 'N/A')}x\n"
    display += f"- **Days Inventory**: {ratios.get('days_inventory', 'N/A')}\n"
    display += f"- **Days Receivable**: {ratios.get('days_receivable', 'N/A')}\n\n"

    # Valuation
    display += "## Valuation Metrics\n"
    display += f"- **P/E Ratio**: {ratios.get('pe_ratio', 'N/A')}\n"
    display += f"- **P/B Ratio**: {ratios.get('pb_ratio', 'N/A')}\n"
    display += f"- **EV/EBITDA**: {ratios.get('ev_ebitda', 'N/A')}\n\n"

    return display


def format_news_display(news_output: Optional[Dict[str, Any]]) -> str:
    """Format news sentiment for display."""
    if not news_output or news_output.get("status") not in ["success", "partial_success"]:
        return format_json(news_output)

    display = "# News Intelligence\n\n"

    display += f"## Sentiment Analysis\n"
    display += f"- **Overall Sentiment**: {news_output.get('sentiment', 'N/A')}\n"
    display += f"- **Sentiment Score**: {news_output.get('sentiment_score', 'N/A')}\n"
    display += f"- **Articles Analyzed**: {news_output.get('article_count', 0)}\n\n"

    if news_output.get('key_themes'):
        display += f"## Key Themes\n"
        for theme in news_output['key_themes']:
            display += f"- {theme}\n"
        display += "\n"

    if news_output.get('positive_drivers'):
        display += f"## Positive Drivers\n"
        for driver in news_output['positive_drivers']:
            display += f"- ✓ {driver}\n"
        display += "\n"

    if news_output.get('negative_drivers'):
        display += f"## Negative Drivers\n"
        for driver in news_output['negative_drivers']:
            display += f"- ✗ {driver}\n"
        display += "\n"

    if news_output.get('notable_headlines'):
        display += f"## Notable Headlines\n"
        for headline in news_output['notable_headlines'][:5]:
            display += f"- {headline}\n"
        display += "\n"

    return display


def format_technical_display(technical_output: Optional[Dict[str, Any]]) -> str:
    """Format technical analysis for display."""
    if not technical_output or technical_output.get("status") != "success":
        return format_json(technical_output)

    display = "# Technical Analysis\n\n"

    display += f"## Overview\n"
    display += f"- **Trend**: {technical_output.get('trend', 'N/A')}\n"
    display += f"- **Momentum**: {technical_output.get('momentum', 'N/A')}\n"
    display += f"- **Technical Score**: {technical_output.get('technical_score', 'N/A')}/100\n\n"

    indicators = technical_output.get('indicators', {})
    if indicators:
        display += f"## Key Indicators\n"
        display += f"- **Latest Price**: ₹{indicators.get('latest_price', 'N/A')}\n"
        display += f"- **20-day SMA**: ₹{indicators.get('sma_20', 'N/A')}\n"
        display += f"- **50-day SMA**: ₹{indicators.get('sma_50', 'N/A')}\n"
        display += f"- **RSI (14)**: {indicators.get('rsi_14', 'N/A')}\n"
        display += f"- **MACD**: {indicators.get('macd', 'N/A')}\n\n"

    if technical_output.get('signals'):
        display += f"## Trading Signals\n"
        for signal in technical_output['signals']:
            display += f"- {signal}\n"
        display += "\n"

    return display


def format_risk_display(risk_output: Optional[Dict[str, Any]]) -> str:
    """Format risk assessment for display."""
    if not risk_output or risk_output.get("status") not in ["success", "partial_success"]:
        return format_json(risk_output)

    display = "# Risk Scorecard\n\n"

    display += f"## Risk Assessment\n"
    display += f"- **Risk Level**: {risk_output.get('risk_level', 'N/A')}\n"
    display += f"- **Risk Score**: {risk_output.get('risk_score', 'N/A')}/100\n\n"

    metrics = risk_output.get('metrics', {})
    if metrics:
        display += f"## Risk Metrics\n"
        display += f"- **Beta**: {metrics.get('beta', 'N/A')}\n"
        display += f"- **Volatility**: {metrics.get('volatility_pct', 'N/A')}%\n"
        display += f"- **VaR (95%)**: {metrics.get('var_95_pct', 'N/A')}%\n"
        display += f"- **Max Drawdown**: {metrics.get('max_drawdown_pct', 'N/A')}%\n\n"

    if risk_output.get('risk_factors'):
        display += f"## Risk Factors\n"
        for factor in risk_output['risk_factors']:
            display += f"- ⚠ {factor}\n"
        display += "\n"

    if risk_output.get('risk_flags'):
        display += f"## Risk Flags\n"
        for flag in risk_output['risk_flags']:
            display += f"- 🚩 {flag}\n"
        display += "\n"

    return display


def format_errors_display(result: Dict[str, Any]) -> str:
    """Format errors and debug info for display."""
    display = "# Debug Information\n\n"

    errors = result.get("errors", [])
    if errors:
        display += f"## Errors ({len(errors)})\n"
        for i, error in enumerate(errors, 1):
            display += f"{i}. {error}\n"
        display += "\n"
    else:
        display += "## Errors\nNo errors encountered ✓\n\n"

    display += "## Execution Metadata\n"
    display += f"- **Ticker**: {result.get('ticker', 'N/A')}\n"
    display += f"- **Company**: {result.get('company_name', 'N/A')}\n"
    display += f"- **Sector**: {result.get('sector', 'N/A')}\n"
    display += f"- **Started**: {result.get('started_at', 'N/A')}\n"
    display += f"- **Completed**: {result.get('completed_at', 'N/A')}\n\n"

    display += "## Agent Status\n"
    agents = [
        ("Filing Analyst", result.get("filing_output")),
        ("Ratio Cruncher", result.get("ratio_output")),
        ("News Sentinel", result.get("news_output")),
        ("Technical Analyst", result.get("technical_output")),
        ("Risk Assessor", result.get("risk_output")),
        ("Report Writer", result.get("final_report")),
    ]

    for agent_name, output in agents:
        if output:
            status = output.get("status", "unknown")
            icon = "✓" if status == "success" else "⚠" if status == "partial_success" else "✗"
            display += f"- {icon} **{agent_name}**: {status}\n"
        else:
            display += f"- ✗ **{agent_name}**: not run\n"

    return display


def analyze_stock(
    ticker: str,
    company_name: str,
    sector: str
) -> Tuple[str, str, str, str, str, str, str]:
    """
    Call FastAPI backend to analyze stock.

    Returns tuple of formatted outputs for each tab:
    (report, filing, ratios, news, technical, risk, errors)
    """
    # Check if backend is running
    if not check_backend_health():
        error_msg = """# ⚠️ Backend Not Running

The FastAPI backend is not available at `{}`

Please start the backend first:

```bash
uvicorn main:app --port 8000 --reload
```

Then refresh this page and try again.""".format(API_BASE_URL)

        return error_msg, error_msg, error_msg, error_msg, error_msg, error_msg, error_msg

    # Validate input
    if not ticker or not ticker.strip():
        error_msg = "# ⚠️ Invalid Input\n\nPlease enter a ticker symbol."
        return error_msg, error_msg, error_msg, error_msg, error_msg, error_msg, error_msg

    # Prepare request
    payload = {
        "ticker": ticker.strip(),
        "company_name": company_name.strip() if company_name else "",
        "sector": sector.strip() if sector else ""
    }

    try:
        # Call backend API
        response = requests.post(API_ANALYZE_URL, json=payload, timeout=300)

        # Handle error responses
        if response.status_code != 200:
            error_detail = response.json().get("detail", "Unknown error")
            error_msg = f"""# ⚠️ Analysis Failed

**Status Code**: {response.status_code}

**Error**: {error_detail}

Please check your input and try again."""

            return error_msg, error_msg, error_msg, error_msg, error_msg, error_msg, error_msg

        # Parse successful response
        result = response.json()

        # Extract outputs
        final_report = result.get("final_report", {})
        filing_output = result.get("filing_output")
        ratio_output = result.get("ratio_output")
        news_output = result.get("news_output")
        technical_output = result.get("technical_output")
        risk_output = result.get("risk_output")

        # Format each tab
        report_display = final_report.get("report_markdown", "# No report generated")

        # Add metadata to report
        if final_report:
            report_metadata = f"\n\n---\n\n"
            report_metadata += f"**Confidence Score**: {final_report.get('confidence_score', 'N/A')}/100\n\n"
            report_metadata += f"**Data Quality**: {final_report.get('data_quality', 'N/A')}\n\n"
            if final_report.get('sources_used'):
                report_metadata += f"**Sources Used**: {', '.join(final_report['sources_used'])}\n\n"
            if final_report.get('missing_sections'):
                report_metadata += f"**Missing Data**: {', '.join(final_report['missing_sections'])}\n\n"
            report_display += report_metadata

        filing_display = format_json(filing_output)
        ratios_display = format_ratios_display(ratio_output)
        news_display = format_news_display(news_output)
        technical_display = format_technical_display(technical_output)
        risk_display = format_risk_display(risk_output)
        errors_display = format_errors_display(result)

        return (
            report_display,
            filing_display,
            ratios_display,
            news_display,
            technical_display,
            risk_display,
            errors_display
        )

    except requests.exceptions.Timeout:
        error_msg = """# ⚠️ Request Timeout

The analysis is taking longer than expected (>5 minutes).

This may happen if:
- The backend is processing a complex analysis
- Network connectivity is slow
- External APIs (yfinance, OpenAI) are slow

Please try again or check the backend logs."""

        return error_msg, error_msg, error_msg, error_msg, error_msg, error_msg, error_msg

    except Exception as e:
        error_msg = f"""# ⚠️ Unexpected Error

An unexpected error occurred:

```
{str(e)}
```

Please check:
1. Backend is running at `{API_BASE_URL}`
2. Network connectivity
3. Backend logs for details"""

        return error_msg, error_msg, error_msg, error_msg, error_msg, error_msg, error_msg


def get_watchlist_display() -> str:
    """
    Fetch and format watchlist for display.

    Returns:
        Markdown-formatted watchlist
    """
    try:
        response = requests.get(API_WATCHLIST_URL, timeout=5)

        if response.status_code != 200:
            return f"# ⚠️ Error\n\nFailed to fetch watchlist: {response.status_code}"

        data = response.json()
        stocks = data.get("stocks", [])

        if not stocks:
            return """# 📋 Watchlist

No stocks in watchlist yet. Add one below to start tracking!"""

        # Build table
        display = "# 📋 Watchlist\n\n"
        display += f"**Tracking {len(stocks)} stock(s)**\n\n"
        display += "| Ticker | Company | Last Check | Sentiment | Stories | Alerts |\n"
        display += "|--------|---------|------------|-----------|---------|--------|\n"

        for stock in stocks:
            ticker = stock.get("ticker", "N/A")
            company = stock.get("company_name", "N/A")
            last_check = stock.get("last_check_at")
            sentiment = stock.get("last_sentiment", "N/A")
            story_count = stock.get("last_story_count", 0)
            negative_count = stock.get("confirmed_negative_count", 0)

            # Format last check time
            if last_check:
                from datetime import datetime
                try:
                    dt = datetime.fromisoformat(last_check.replace('Z', '+00:00'))
                    last_check_str = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    last_check_str = "N/A"
            else:
                last_check_str = "Never"

            # Color sentiment
            if sentiment:
                sentiment_upper = sentiment.upper()
                if "NEGATIVE" in sentiment_upper or "BEARISH" in sentiment_upper:
                    sentiment_display = f"🔴 {sentiment}"
                elif "POSITIVE" in sentiment_upper or "BULLISH" in sentiment_upper:
                    sentiment_display = f"🟢 {sentiment}"
                else:
                    sentiment_display = f"⚪ {sentiment}"
            else:
                sentiment_display = "N/A"

            # Alert indicator
            alert_display = f"⚠️ {negative_count}" if negative_count > 0 else "-"

            display += f"| {ticker} | {company} | {last_check_str} | {sentiment_display} | {story_count} | {alert_display} |\n"

        display += "\n---\n\n"
        display += "**Note**: Watchlist is checked every 10 minutes. Alerts are sent for new confirmed negative news.\n"

        return display

    except Exception as e:
        return f"# ⚠️ Error\n\nFailed to fetch watchlist: {str(e)}"


def add_to_watchlist_action(ticker: str, company_name: str) -> tuple:
    """
    Add a stock to the watchlist.

    Returns:
        Tuple of (updated_watchlist_display, status_message, cleared_ticker_input)
    """
    if not ticker or not ticker.strip():
        return get_watchlist_display(), "⚠️ Please enter a ticker symbol", ""

    try:
        payload = {
            "ticker": ticker.strip().upper(),
            "company_name": company_name.strip() if company_name else None
        }

        response = requests.post(API_WATCHLIST_ADD_URL, json=payload, timeout=5)

        if response.status_code == 200:
            data = response.json()
            message = f"✅ Added {ticker.upper()} to watchlist"
        else:
            error_detail = response.json().get("detail", "Unknown error")
            message = f"❌ Failed to add: {error_detail}"

        return get_watchlist_display(), message, ""

    except Exception as e:
        return get_watchlist_display(), f"❌ Error: {str(e)}", ticker


def remove_from_watchlist_action(ticker: str) -> tuple:
    """
    Remove a stock from the watchlist.

    Returns:
        Tuple of (updated_watchlist_display, status_message)
    """
    if not ticker or not ticker.strip():
        return get_watchlist_display(), "⚠️ Please enter a ticker symbol to remove"

    try:
        payload = {"ticker": ticker.strip().upper()}

        response = requests.post(API_WATCHLIST_REMOVE_URL, json=payload, timeout=5)

        if response.status_code == 200:
            message = f"✅ Removed {ticker.upper()} from watchlist"
        elif response.status_code == 404:
            message = f"⚠️ {ticker.upper()} not found in watchlist"
        else:
            error_detail = response.json().get("detail", "Unknown error")
            message = f"❌ Failed to remove: {error_detail}"

        return get_watchlist_display(), message

    except Exception as e:
        return get_watchlist_display(), f"❌ Error: {str(e)}"


def refresh_watchlist_action() -> str:
    """Refresh the watchlist display."""
    return get_watchlist_display()


# === Example Stock Presets ===

EXAMPLE_STOCKS = {
    "RELIANCE": ("RELIANCE", "Reliance Industries", "Energy"),
    "HDFCBANK": ("HDFCBANK", "HDFC Bank", "Banking"),
    "INFY": ("INFY", "Infosys", "IT Services"),
    "TCS": ("TCS", "Tata Consultancy Services", "IT Services"),
    "WIPRO": ("WIPRO", "Wipro", "IT Services"),
}


# === Gradio Interface ===


def create_interface():
    """Create and configure Gradio interface."""

    with gr.Blocks(
        title="FinSight AI",
        theme=gr.themes.Soft(),
        css="""
        .gradio-container {max-width: 1200px !important}
        """
    ) as demo:

        gr.Markdown("""
        # 📊 FinSight AI

        **Multi-agent equity research platform for Indian stocks**

        Powered by six specialist AI agents analyzing filings, financials, news, technicals, and risk.
        """)

        # Check backend status on load
        with gr.Row():
            backend_status = gr.Markdown(
                "🔄 Checking backend status..." if check_backend_health()
                else "⚠️ **Backend not running**. Please start: `uvicorn main:app --port 8000 --reload`"
            )

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### Input")

                ticker_input = gr.Textbox(
                    label="Ticker Symbol",
                    placeholder="e.g., RELIANCE, TCS, INFY",
                    value="",
                    lines=1
                )

                company_name_input = gr.Textbox(
                    label="Company Name (optional)",
                    placeholder="e.g., Reliance Industries",
                    value="",
                    lines=1
                )

                sector_input = gr.Textbox(
                    label="Sector (optional)",
                    placeholder="e.g., Energy, IT Services, Banking",
                    value="",
                    lines=1
                )

                analyze_btn = gr.Button("🔍 Analyze", variant="primary", size="lg")

                gr.Markdown("### Quick Examples")

                with gr.Row():
                    reliance_btn = gr.Button("RELIANCE", size="sm")
                    hdfcbank_btn = gr.Button("HDFCBANK", size="sm")

                with gr.Row():
                    infy_btn = gr.Button("INFY", size="sm")
                    tcs_btn = gr.Button("TCS", size="sm")

                with gr.Row():
                    wipro_btn = gr.Button("WIPRO", size="sm")

                gr.Markdown("""
                ### About

                FinSight AI orchestrates six specialist agents:
                1. **Filing Analyst** - Analyzes company filings
                2. **Ratio Cruncher** - Calculates financial ratios
                3. **News Sentinel** - Sentiment analysis
                4. **Technical Analyst** - Technical indicators
                5. **Risk Assessor** - Risk metrics
                6. **Report Writer** - Synthesizes final report

                Analysis takes 2-5 minutes depending on data availability.
                """)

            with gr.Column(scale=2):
                gr.Markdown("### Results")

                with gr.Tabs() as tabs:
                    with gr.Tab("📄 Investment Report"):
                        report_output = gr.Markdown(
                            "Run an analysis to see the comprehensive investment report.",
                            line_breaks=True
                        )

                    with gr.Tab("📁 Filing Insights"):
                        filing_output = gr.Markdown(
                            "Filing analysis will appear here.",
                            line_breaks=True
                        )

                    with gr.Tab("💰 Financial Ratios"):
                        ratios_output = gr.Markdown(
                            "Financial ratios will appear here.",
                            line_breaks=True
                        )

                    with gr.Tab("📰 News Intelligence"):
                        news_output = gr.Markdown(
                            "News sentiment analysis will appear here.",
                            line_breaks=True
                        )

                    with gr.Tab("📈 Technical Analysis"):
                        technical_output = gr.Markdown(
                            "Technical indicators will appear here.",
                            line_breaks=True
                        )

                    with gr.Tab("⚠️ Risk Scorecard"):
                        risk_output = gr.Markdown(
                            "Risk assessment will appear here.",
                            line_breaks=True
                        )

                    with gr.Tab("🐛 Debug"):
                        errors_output = gr.Markdown(
                            "Debug information will appear here.",
                            line_breaks=True
                        )

                    with gr.Tab("📊 Tracking"):
                        gr.Markdown("""
                        ### Stock Watchlist

                        Add stocks to track and receive email alerts when confirmed negative news is detected.

                        **Alert Criteria:**
                        - ✅ Confirmed (≥2 trusted sources)
                        - ✅ Negative sentiment
                        - ✅ New story (not previously seen)

                        Watchlist is checked every 10 minutes automatically.
                        """)

                        watchlist_display = gr.Markdown(
                            get_watchlist_display(),
                            line_breaks=True
                        )

                        with gr.Row():
                            refresh_btn = gr.Button("🔄 Refresh", size="sm")

                        gr.Markdown("### Add Stock to Watchlist")

                        with gr.Row():
                            add_ticker_input = gr.Textbox(
                                label="Ticker Symbol",
                                placeholder="e.g., RELIANCE",
                                scale=2
                            )
                            add_company_input = gr.Textbox(
                                label="Company Name (optional)",
                                placeholder="e.g., Reliance Industries",
                                scale=3
                            )

                        add_btn = gr.Button("➕ Add to Watchlist", variant="primary")

                        gr.Markdown("### Remove Stock from Watchlist")

                        with gr.Row():
                            remove_ticker_input = gr.Textbox(
                                label="Ticker Symbol to Remove",
                                placeholder="e.g., RELIANCE"
                            )
                            remove_btn = gr.Button("➖ Remove", variant="stop")

                        status_message = gr.Markdown("")

        # Wire up analyze button
        analyze_btn.click(
            fn=analyze_stock,
            inputs=[ticker_input, company_name_input, sector_input],
            outputs=[
                report_output,
                filing_output,
                ratios_output,
                news_output,
                technical_output,
                risk_output,
                errors_output
            ]
        )

        # Wire up example buttons
        def set_example(ticker: str, company: str, sector: str):
            return ticker, company, sector

        for stock_key, (ticker, company, sector) in EXAMPLE_STOCKS.items():
            btn = locals()[f"{stock_key.lower()}_btn"]
            btn.click(
                fn=lambda t=ticker, c=company, s=sector: (t, c, s),
                inputs=None,
                outputs=[ticker_input, company_name_input, sector_input]
            )

        # Wire up watchlist actions
        refresh_btn.click(
            fn=refresh_watchlist_action,
            inputs=None,
            outputs=[watchlist_display]
        )

        add_btn.click(
            fn=add_to_watchlist_action,
            inputs=[add_ticker_input, add_company_input],
            outputs=[watchlist_display, status_message, add_ticker_input]
        )

        remove_btn.click(
            fn=remove_from_watchlist_action,
            inputs=[remove_ticker_input],
            outputs=[watchlist_display, status_message]
        )

    return demo


# === Launch Application ===


if __name__ == "__main__":
    demo = create_interface()

    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )
