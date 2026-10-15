"""
Technical indicator computation using pandas and numpy.
NO pandas-ta dependency - all indicators implemented manually.
All functions return JSON-serializable dicts.
"""
import logging
import pandas as pd
import numpy as np
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def _calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Calculate Simple Moving Average"""
    return series.rolling(window=period, min_periods=period).mean()


def _calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average"""
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def _calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index (RSI)
    RSI = 100 - (100 / (1 + RS))
    where RS = Average Gain / Average Loss
    """
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period, min_periods=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period, min_periods=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def _calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
    """
    Calculate MACD (Moving Average Convergence Divergence)
    Returns: (macd_line, signal_line, histogram)
    """
    ema_fast = _calculate_ema(series, fast)
    ema_slow = _calculate_ema(series, slow)

    macd_line = ema_fast - ema_slow
    signal_line = _calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


def compute_technical_indicators(ticker: str, period: str = "1y", cached_price_history: dict = None) -> Dict:
    """
    Compute technical indicators for a stock ticker.
    All indicators calculated manually using pandas/numpy (no pandas-ta).

    Args:
        ticker: Stock ticker (e.g., 'RELIANCE' or 'RELIANCE.NS')
        period: Time period ('1y', '6mo', '3mo', '1mo')
        cached_price_history: Pre-fetched price history from workflow state (optional)

    Returns:
        Dict with all indicators and signal summary:
        - SMA 20, 50, 200
        - EMA 12, 26
        - MACD, signal, histogram
        - RSI 14
        - Volume average
        - Price return %
        - Trend signal (BULLISH/BEARISH/NEUTRAL)
        - Momentum signal (OVERBOUGHT/OVERSOLD/NEUTRAL)
        - Technical score (0-100)
    """
    from backend.tools.financial_tools import get_price_history

    try:
        # Use cached price history if provided (don't refetch on cache failure)
        if cached_price_history is not None:
            if "error" not in cached_price_history:
                logger.info("Using cached price history from workflow state")
                price_data = cached_price_history
            else:
                logger.error(f"Cached price history has error: {cached_price_history['error']}")
                return {
                    "error": f"Price data unavailable: {cached_price_history['error']}",
                    "ticker": ticker
                }
        else:
            logger.info("Fetching price history (cache not provided)")
            price_data = get_price_history.func(ticker, period)
            if "error" in price_data:
                logger.error(f"Cannot fetch price data for {ticker}: {price_data['error']}")
                return {
                    "error": f"Price data unavailable: {price_data['error']}",
                    "ticker": ticker
                }

        # Convert to DataFrame
        df = pd.DataFrame({
            "date": pd.to_datetime(price_data["dates"]),
            "open": price_data["open"],
            "high": price_data["high"],
            "low": price_data["low"],
            "close": price_data["close"],
            "volume": price_data["volume"],
        })
        df.set_index("date", inplace=True)

        if len(df) < 50:
            logger.warning(f"Insufficient data for {ticker}: only {len(df)} data points")
            return {
                "error": f"Insufficient data: only {len(df)} data points (need at least 50)",
                "ticker": ticker
            }

        # Calculate all indicators
        df["sma_20"] = _calculate_sma(df["close"], 20)
        df["sma_50"] = _calculate_sma(df["close"], 50)
        df["sma_200"] = _calculate_sma(df["close"], 200)

        df["ema_12"] = _calculate_ema(df["close"], 12)
        df["ema_26"] = _calculate_ema(df["close"], 26)

        df["macd"], df["macd_signal"], df["macd_histogram"] = _calculate_macd(df["close"])

        df["rsi"] = _calculate_rsi(df["close"], 14)

        df["volume_sma_20"] = _calculate_sma(df["volume"], 20)

        # Get latest values
        latest = df.iloc[-1]
        current_price = float(latest["close"])

        # Extract indicator values (handle NaN)
        sma_20 = float(latest["sma_20"]) if pd.notna(latest["sma_20"]) else None
        sma_50 = float(latest["sma_50"]) if pd.notna(latest["sma_50"]) else None
        sma_200 = float(latest["sma_200"]) if pd.notna(latest["sma_200"]) else None

        ema_12 = float(latest["ema_12"]) if pd.notna(latest["ema_12"]) else None
        ema_26 = float(latest["ema_26"]) if pd.notna(latest["ema_26"]) else None

        macd = float(latest["macd"]) if pd.notna(latest["macd"]) else None
        macd_signal = float(latest["macd_signal"]) if pd.notna(latest["macd_signal"]) else None
        macd_histogram = float(latest["macd_histogram"]) if pd.notna(latest["macd_histogram"]) else None

        rsi = float(latest["rsi"]) if pd.notna(latest["rsi"]) else None

        volume_avg = float(latest["volume_sma_20"]) if pd.notna(latest["volume_sma_20"]) else None

        # Price performance
        price_return_pct = price_data.get("price_return_pct", 0)

        # Support and Resistance (20-day rolling)
        support = float(df["low"].tail(20).min()) if len(df) >= 20 else None
        resistance = float(df["high"].tail(20).max()) if len(df) >= 20 else None

        # 52-week high/low
        week_52_high = float(df["high"].max())
        week_52_low = float(df["low"].min())

        # === SIGNAL GENERATION ===

        # Trend signal
        trend_score = 0
        trend_signals = []

        if sma_50 and current_price > sma_50:
            trend_score += 30
            trend_signals.append("Price above 50-day SMA")
        elif sma_50 and current_price < sma_50:
            trend_score -= 30
            trend_signals.append("Price below 50-day SMA")

        if sma_20 and sma_50 and sma_20 > sma_50:
            trend_score += 20
            trend_signals.append("20-day SMA above 50-day (golden cross)")
        elif sma_20 and sma_50 and sma_20 < sma_50:
            trend_score -= 20
            trend_signals.append("20-day SMA below 50-day (death cross)")

        if sma_200 and current_price > sma_200:
            trend_score += 15
            trend_signals.append("Price above 200-day SMA (long-term uptrend)")
        elif sma_200 and current_price < sma_200:
            trend_score -= 15
            trend_signals.append("Price below 200-day SMA (long-term downtrend)")

        # Momentum signal
        momentum_score = 0
        momentum_signals = []

        if rsi is not None:
            if rsi > 70:
                momentum_score -= 25
                momentum_signals.append(f"RSI overbought ({rsi:.1f})")
            elif rsi < 30:
                momentum_score += 25
                momentum_signals.append(f"RSI oversold ({rsi:.1f})")
            else:
                momentum_signals.append(f"RSI neutral ({rsi:.1f})")

        if macd is not None and macd_signal is not None:
            if macd > macd_signal:
                momentum_score += 20
                momentum_signals.append("MACD bullish (above signal)")
            else:
                momentum_score -= 20
                momentum_signals.append("MACD bearish (below signal)")

        # Overall technical score (0-100 scale)
        raw_score = 50 + trend_score + momentum_score
        technical_score = max(0, min(100, raw_score))

        # Trend label
        if trend_score > 20:
            trend = "BULLISH"
        elif trend_score < -20:
            trend = "BEARISH"
        else:
            trend = "NEUTRAL"

        # Momentum label
        if rsi is not None:
            if rsi > 70:
                momentum = "OVERBOUGHT"
            elif rsi < 30:
                momentum = "OVERSOLD"
            else:
                momentum = "NEUTRAL"
        else:
            momentum = "NEUTRAL"

        # Build result
        result = {
            "ticker": ticker,
            "period": period,
            "current_price": round(current_price, 2),
            "data_points": len(df),

            # Moving averages
            "sma_20": round(sma_20, 2) if sma_20 else None,
            "sma_50": round(sma_50, 2) if sma_50 else None,
            "sma_200": round(sma_200, 2) if sma_200 else None,
            "ema_12": round(ema_12, 2) if ema_12 else None,
            "ema_26": round(ema_26, 2) if ema_26 else None,

            # MACD
            "macd": round(macd, 2) if macd else None,
            "macd_signal": round(macd_signal, 2) if macd_signal else None,
            "macd_histogram": round(macd_histogram, 2) if macd_histogram else None,

            # RSI
            "rsi": round(rsi, 2) if rsi else None,

            # Volume
            "volume_avg_20d": int(volume_avg) if volume_avg else None,
            "latest_volume": int(latest["volume"]),

            # Support/Resistance
            "support_20d": round(support, 2) if support else None,
            "resistance_20d": round(resistance, 2) if resistance else None,

            # 52-week range
            "52w_high": round(week_52_high, 2),
            "52w_low": round(week_52_low, 2),

            # Performance
            "price_return_pct": round(price_return_pct, 2),

            # Signals
            "trend": trend,
            "momentum": momentum,
            "technical_score": round(technical_score, 1),
            "trend_signals": trend_signals,
            "momentum_signals": momentum_signals,

            # Summary
            "summary": (
                f"{trend} trend with {momentum} momentum. "
                f"Technical score: {technical_score:.0f}/100. "
                f"Price {'above' if sma_50 and current_price > sma_50 else 'below'} 50-day SMA. "
                f"RSI: {rsi:.1f}." if rsi else ""
            )
        }

        return result

    except Exception as e:
        logger.error(f"Technical indicator computation error for {ticker}: {e}")
        return {
            "error": str(e),
            "ticker": ticker
        }
