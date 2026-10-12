# FinSight AI - Complete Metrics & Formulas Reference

## 📊 All Metrics Used in FinSight AI

---

## 1. PRICE DATA (OHLCV)

### Source
- **O**pen, **H**igh, **L**ow, **C**lose, **V**olume
- Fetched from yfinance for 1-year period
- Used for technical analysis and risk calculations

---

## 2. PROFITABILITY RATIOS

### ROE (Return on Equity)
```
ROE = Net Income / Shareholders' Equity × 100
```
- **Good**: > 15%
- **Moderate**: 10-15%
- **Concern**: < 10%

### ROA (Return on Assets)
```
ROA = Net Income / Total Assets × 100
```
- **Good**: > 10%
- **Moderate**: 5-10%
- **Concern**: < 5%

### Profit Margin
```
Profit Margin = Net Income / Revenue × 100
```

### Operating Margin
```
Operating Margin = Operating Income / Revenue × 100
```

### Gross Margin
```
Gross Margin = (Revenue - COGS) / Revenue × 100
```

---

## 3. LEVERAGE RATIOS

### Debt-to-Equity (D/E)
```
D/E Ratio = Total Debt / Shareholders' Equity
```
- **Low**: < 50
- **Moderate**: 50-150
- **High**: > 150
- **Very High**: > 200

---

## 4. LIQUIDITY RATIOS

### Current Ratio
```
Current Ratio = Current Assets / Current Liabilities
```
- **Strong**: > 1.5
- **Adequate**: 1.0-1.5
- **Weak**: < 1.0 (liquidity concern)

### Quick Ratio
```
Quick Ratio = (Current Assets - Inventory) / Current Liabilities
```

---

## 5. VALUATION RATIOS

### P/E Ratio (Price-to-Earnings)
```
P/E Ratio = Market Price per Share / Earnings per Share
```
- **Reasonable**: < 15
- **Moderate**: 15-40
- **High**: > 40 (valuation risk)
- **Very High**: > 50

### P/B Ratio (Price-to-Book)
```
P/B Ratio = Market Price per Share / Book Value per Share
```

### EPS (Earnings per Share)
```
EPS = Net Income / Shares Outstanding
```

---

## 6. TECHNICAL INDICATORS

### SMA (Simple Moving Average)
```
SMA_n = (P₁ + P₂ + ... + Pₙ) / n
```
- Calculated for 20, 50, 200-day periods
- **Golden Cross**: 20-day SMA > 50-day SMA (bullish)
- **Death Cross**: 20-day SMA < 50-day SMA (bearish)

### EMA (Exponential Moving Average)
```
EMA_today = (Price_today × k) + (EMA_yesterday × (1 - k))
where k = 2 / (n + 1)
```
- Calculated for 12, 26-day periods

### RSI (Relative Strength Index)
```
RS = Average Gain / Average Loss (over 14 days)
RSI = 100 - (100 / (1 + RS))
```
- **Overbought**: > 70
- **Neutral**: 30-70
- **Oversold**: < 30

### MACD (Moving Average Convergence Divergence)
```
MACD Line = EMA(12) - EMA(26)
Signal Line = EMA(9) of MACD Line
Histogram = MACD Line - Signal Line
```
- **Bullish**: MACD > Signal
- **Bearish**: MACD < Signal

---

## 7. RISK METRICS

### Beta (Systematic Risk)
```
Beta = Covariance(Stock Returns, Market Returns) / Variance(Market Returns)
```
- **Beta > 1.5**: High volatility (+10 risk points)
- **Beta > 1.2**: Above-market (+7 risk points)
- **Beta < 0.8**: Defensive (low risk)
- **Beta = 1**: Moves with market

### Volatility (Standard Deviation)
```
Volatility = StdDev(Returns) × √252
```
(Annualized for daily returns)

**Risk Points:**
- **> 40%**: +15 points (very volatile)
- **> 30%**: +12 points (elevated)
- **> 20%**: +8 points (moderate)
- **< 20%**: Low volatility (stable)

### VaR (Value at Risk) - 95% Confidence
```
VaR = Percentile(Returns, 5th percentile) × 100
```
- Estimates maximum expected loss at 95% confidence
- Uses historical simulation method

### Max Drawdown
```
Max Drawdown = (Trough Price - Peak Price) / Peak Price × 100
```
**Risk Points:**
- **> 40%**: +15 points (severe)
- **> 30%**: +12 points (high)
- **> 20%**: +8 points (moderate)

---

## 8. ALTMAN Z-SCORE (Bankruptcy Prediction)

### Formula
```
Z = 1.2×X1 + 1.4×X2 + 3.3×X3 + 0.6×X4 + 1.0×X5

Where:
X1 = Working Capital / Total Assets
X2 = Retained Earnings / Total Assets
X3 = EBIT / Total Assets
X4 = Market Value of Equity / Total Liabilities
X5 = Sales / Total Assets
```

### Interpretation
- **Z > 2.99**: Safe zone
- **1.81 < Z < 2.99**: Grey zone
- **Z < 1.81**: Distress zone (bankruptcy risk)

**Note**: Currently unavailable for Indian stocks (yfinance data limitation)

---

## 9. FINAL RISK SCORE CALCULATION

### Formula (0-100 scale, higher = higher risk)

```python
Risk Score = Market Risk + Financial Risk + Agent Risk

# === MARKET RISK (40 points max) ===
Volatility:     0-15 points
Beta:           0-10 points
Max Drawdown:   0-15 points

# === FINANCIAL RISK (40 points max) ===
Leverage (D/E): 0-15 points
Liquidity:      0-10 points
Valuation (P/E): 0-15 points

# === AGENT RISK (20 points max) ===
Low ROE (<10%): +5 points
Weak Technicals: 0-10 points

TOTAL = min(100, sum of all points)
```

### Detailed Scoring

#### Volatility (0-15 points)
```
if volatility > 40%:  +15 points + "HIGH_VOLATILITY" flag
elif volatility > 30%: +12 points
elif volatility > 20%: +8 points
else: 0 points (stable)
```

#### Beta (0-10 points)
```
if beta > 1.5:  +10 points + "HIGH_BETA" flag
elif beta > 1.2: +7 points
elif beta < 0.8: 0 points (defensive)
```

#### Max Drawdown (0-15 points)
```
if max_dd > 40%: +15 points + "SEVERE_DRAWDOWN" flag
elif max_dd > 30%: +12 points
elif max_dd > 20%: +8 points
```

#### Leverage - D/E Ratio (0-15 points)
```
if D/E > 200: +15 points + "HIGH_LEVERAGE" flag
elif D/E > 150: +12 points
elif D/E > 100: +8 points
else: 0 points (low leverage)
```

#### Liquidity - Current Ratio (0-10 points)
```
if current_ratio < 1.0: +10 points + "LIQUIDITY_RISK" flag
elif current_ratio < 1.5: +5 points
else: 0 points (strong liquidity)
```

#### Valuation - P/E Ratio (0-15 points)
```
if P/E > 50: +10 points + "VALUATION_RISK" flag
elif P/E > 35: +5 points
else: 0 points
```

#### Profitability - ROE (0-5 points)
```
if ROE < 10%: +5 points (low profitability)
else: 0 points
```

#### Technical Strength (0-10 points)
```
if technical_score < 30: +10 points + "WEAK_TECHNICALS" flag
elif technical_score < 40: +5 points
else: 0 points
```

### Risk Level Classification
```python
def classify_risk_level(score: float) -> str:
    if score < 20:   return "LOW"
    elif score < 40: return "MEDIUM"
    elif score < 60: return "MEDIUM-HIGH"
    elif score < 80: return "HIGH"
    else:            return "VERY HIGH"
```

---

## 10. TECHNICAL SCORE CALCULATION

### Formula (0-100 scale)
```python
Score = Trend Signals + Momentum Signals + Volume Signals

# TREND (0-40 points)
Price vs SMA 20/50/200: Up to 40 points
Golden/Death Cross: Major impact

# MOMENTUM (0-40 points)
MACD vs Signal: Up to 20 points
RSI levels: Up to 20 points

# VOLUME (0-20 points)
Volume trends: Up to 20 points

TOTAL = sum of all components (capped at 100)
```

---

## 11. NEWS SENTIMENT SCORING

### Story Confirmation
```
Confirmed = Number of Trusted Sources ≥ 2
```

### Confidence Score
```python
confidence = min(40 + (source_count - 1) × 20, 80)
if confirmed:
    confidence += 20

Maximum = 100
```

### Sentiment Classification
- **Positive/Bullish**
- **Neutral**
- **Negative/Bearish**

---

## 12. SECTOR BENCHMARKING

Compares stock ratios against sector median values:
- ROE, ROA, D/E, Current Ratio, P/E, P/B
- Operating Margin, Profit Margin

---

## EXAMPLE CALCULATION: RELIANCE

From your last test:

### Risk Score = 26/100 (MEDIUM)

**Breakdown:**
```
Market Risk:
- Volatility: 20.39% → +8 points (moderate)
- Beta: Data not available → 0 points
- Max Drawdown: 22.06% → +8 points (moderate)
Market Risk Subtotal: 16 points

Financial Risk:
- D/E: 36.65 → 0 points (low leverage)
- Current Ratio: Not available → 0 points
- P/E: 22.69 → 0 points (reasonable)
Financial Risk Subtotal: 0 points

Agent Risk:
- ROE: Not available → 0 points
- Technical Score: 0/100 → +10 points (weak technicals)
Agent Risk Subtotal: 10 points

TOTAL: 16 + 0 + 10 = 26/100 → MEDIUM RISK
```

---

## Key Takeaways

1. **Risk Score is additive** from three categories
2. **Higher score = Higher risk** (0-100 scale)
3. **Multiple data sources**: yfinance, calculated ratios, agent outputs
4. **Graceful degradation**: Missing data doesn't break scoring
5. **Conservative approach**: Flags raised at reasonable thresholds
6. **No LLM involved**: Pure code-based calculations

---

## Data Sources

- **yfinance**: Price history, OHLCV, fundamentals
- **Nifty 50**: Market benchmark for beta
- **Manual calculations**: All technical indicators, risk metrics
- **No external APIs**: Everything computed in-house
