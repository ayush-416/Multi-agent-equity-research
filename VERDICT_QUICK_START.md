# Investment Verdict - Quick Start Guide

## Overview

The Investment Verdict feature provides a data-driven investment recommendation based on analysis from all FinSight AI agents.

## How to Use

### 1. Start the Application

**Backend:**
```bash
uvicorn main:app --port 8000 --reload
```

**Frontend:**
```bash
cd frontend
python app.py
```

Access at: http://localhost:7860

### 2. Run Analysis

1. Enter a ticker symbol (e.g., "RELIANCE", "TCS", "INFY")
2. Optionally add company name and sector
3. Click "🔍 Analyze Stock"
4. Wait 2-5 minutes for analysis to complete

### 3. View Verdict

Click the **"🎯 Investment Verdict"** tab (first tab) to see:

- **Verdict Banner**: Large color-coded recommendation (INVEST/HOLD/WATCH/AVOID)
- **Net Score**: Overall score from -10 to +10
- **Confidence**: Percentage based on data availability
- **Explanation**: Plain-English narrative of the verdict
- **Component Bars**: Visual breakdown of contributions
- **Why Invest / Why Not**: Top positive and negative factors
- **Component Details**: Expandable sections with all drivers

## Understanding the Verdict

### Verdict Types

| Verdict | Score Range | Color | Meaning |
|---------|-------------|-------|---------|
| **INVEST** | ≥ +3.0 | Green | Strong positive signals across components |
| **HOLD** | 0 to +3.0 | Amber | Moderately positive, hold current position |
| **WATCH** | -3.0 to 0 | Amber | Slightly negative, monitor closely |
| **AVOID** | ≤ -3.0 | Red | Strong negative signals, avoid investment |

### Component Scores

Each component contributes -3 to +3:

1. **News Sentiment** (from confirmed stories only)
   - Positive: Recent positive news coverage
   - Negative: Recent negative news coverage

2. **Fundamentals** (vs sector benchmarks)
   - P/E ratio vs sector median
   - ROE vs sector median
   - Debt-to-Equity vs sector median
   - Profit margins vs sector median

3. **Technical** (trend and momentum)
   - Trend direction (bullish/bearish)
   - RSI levels (overbought/oversold)
   - Price position in 52-week range
   - MACD signals

4. **Risk** (lower risk = positive contribution)
   - Volatility
   - Value at Risk (VaR)
   - Maximum drawdown
   - Beta (market sensitivity)

5. **Filings** (RAG-based sentiment)
   - Only scores if filing index available
   - Sentiment from company filings

### Confidence Score

- **80-100%**: High confidence (4-5 components available)
- **60-80%**: Moderate confidence (3 components available)
- **<60%**: Limited confidence (≤2 components available)

## Customization

### Adjust Component Weights

Edit `.env` file:

```bash
# Emphasize fundamentals over technicals
VERDICT_WEIGHT_FUNDAMENTALS=1.5
VERDICT_WEIGHT_TECHNICAL=0.5
```

### Adjust Verdict Thresholds

```bash
# Require higher score for INVEST
VERDICT_THRESHOLD_INVEST=4.0

# More lenient on AVOID
VERDICT_THRESHOLD_AVOID=-2.0
```

## Interpreting Results

### Example 1: Strong Buy Signal

```
Verdict: INVEST
Net Score: +7.2 / 10
Confidence: 100%

Components:
✓ News Sentiment: +2.5 (Very Positive)
✓ Fundamentals: +2.8 (Strong)
✓ Technical: +1.9 (Bullish)
✓ Risk: +0.5 (Medium-Low Risk)
→ Filings: +0.0 (Neutral)

Why Invest:
• ROE 18.5% vs sector 12.3% → +0.75
• P/E 18.5 vs sector 22.0 → +0.60
• 5 confirmed positive news stories
• Bullish trend with RSI at 58

Why Not:
• Beta 1.15 (higher market sensitivity)
```

**Interpretation**: Strong across-the-board signal. Good fundamentals, positive news, bullish technicals, and manageable risk.

### Example 2: Mixed Signal

```
Verdict: HOLD
Net Score: +1.5 / 10
Confidence: 80%

Components:
✓ News Sentiment: +1.0 (Positive)
✓ Fundamentals: +0.5 (Above Average)
✗ Technical: -0.8 (Bearish)
✓ Risk: +0.8 (Medium-Low Risk)
? Filings: Unavailable

Why Invest:
• Positive news sentiment
• ROE above sector average
• Low volatility

Why Not:
• Bearish technical trend
• RSI 72 (overbought)
• Price near 52-week high
```

**Interpretation**: Fundamentals and news are positive, but technicals suggest price may be stretched. Consider waiting for better entry point.

### Example 3: Avoid Signal

```
Verdict: AVOID
Net Score: -4.2 / 10
Confidence: 100%

Components:
✗ News Sentiment: -2.5 (Very Negative)
✗ Fundamentals: -1.8 (Weak)
✗ Technical: -1.2 (Bearish)
✓ Risk: +0.3 (Medium Risk)
→ Filings: +1.0 (Positive)

Why Not:
• 4 confirmed negative news stories
• P/E 45.2 vs sector 22.0 → -0.75
• ROE 8.5% vs sector 12.3% → -0.58
• Bearish trend with MACD negative
• High volatility 52%

Why Invest:
• Positive insights from filings
```

**Interpretation**: Multiple red flags across news, fundamentals, and technicals. High valuation with weak returns. Avoid despite positive filing sentiment.

## Important Notes

### What the Verdict IS:

✅ Data-driven synthesis of multiple analysis dimensions
✅ Transparent scoring based on real computed values
✅ Helpful starting point for research

### What the Verdict is NOT:

❌ Financial advice or a buy/sell recommendation
❌ Guarantee of investment performance
❌ Replacement for professional financial guidance
❌ Consideration of your personal financial situation

### Always Remember:

⚠️ **This analysis is for informational purposes only**
⚠️ **Past performance does not indicate future results**
⚠️ **Consult a qualified financial advisor before investing**
⚠️ **Do your own due diligence**

## Troubleshooting

### Verdict shows "Unavailable"
- Check that backend is running
- Verify analysis completed successfully
- Check backend logs for errors

### Low Confidence Score
- Normal if data sources are unavailable (e.g., no filing index)
- Verdict still computed from available components
- Consider as less reliable

### All Components "Unavailable"
- Likely data fetching issues (yfinance rate limits, API errors)
- Check "🐛 Debug" tab for error details
- Try again in a few minutes

### Unexpected Verdict
- Review component details to understand scoring
- Check "Why Invest" and "Why Not" sections
- Remember: verdict is mechanical, not judgment-based
- Cross-reference with full "📄 Investment Report"

## Support

For issues or questions:
1. Check backend logs: `uvicorn main:app --port 8000 --reload`
2. Check "🐛 Debug" tab in frontend
3. Review INVESTMENT_VERDICT_IMPLEMENTATION.md for technical details
4. Run test: `python test_verdict.py`

---

**Version**: 1.0  
**Last Updated**: 2024  
**Feature Status**: ✅ Production Ready
