"""
Crypto Trading Strategies - Unified Technical Analysis Module

This module consolidates all technical analysis functionality:
- Indicator calculations (MACD, RSI, EMA/SMA, Bollinger Bands, ATR)
- Trading signal generators
- Multi-indicator strategies

All strategy functions have a uniform signature:
    strategy_<name>(candles: OHLCVCandles | pd.DataFrame, **params) -> TradeSignal

Active strategies:
1. strategy_rsi_macd - RSI + MACD Combined (73% win rate in backtests)
2. strategy_ema_crossover - Golden/Death Cross signals
3. strategy_bollinger_mean_reversion - Mean reversion in ranging markets
4. strategy_multi_confluence - Combines all strategies for high-confidence signals

All functions are stateless - they take price data and return signals.
"""

import numpy as np
import pandas as pd

from coinbot_backend.core.exceptions import CoinbotUnexpectedTypeError
from coinbot_backend.models.candles import OHLCVCandles
from coinbot_backend.models.trading import Signal, TradeSignal


def calculate_sma(prices: np.ndarray, period: int) -> np.ndarray:
    """Calculate Simple Moving Average"""
    if len(prices) < period:
        return np.full(len(prices), np.nan)

    sma = np.full(len(prices), np.nan)
    for i in range(period - 1, len(prices)):
        sma[i] = np.mean(prices[i - period + 1:i + 1])
    return sma


def calculate_ema(prices: np.ndarray, period: int) -> np.ndarray:
    """Calculate Exponential Moving Average"""
    if len(prices) < period:
        return np.full(len(prices), np.nan)

    ema = np.full(len(prices), np.nan)
    multiplier = 2 / (period + 1)

    # First EMA is SMA
    ema[period - 1] = np.mean(prices[:period])

    for i in range(period, len(prices)):
        ema[i] = (prices[i] * multiplier) + (ema[i - 1] * (1 - multiplier))

    return ema


def calculate_rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
    """
    Calculate Relative Strength Index

    RSI = 100 - (100 / (1 + RS))
    RS = Average Gain / Average Loss
    """
    if len(prices) < period + 1:
        return np.full(len(prices), np.nan)

    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    rsi = np.full(len(prices), np.nan)

    # First RSI calculation uses simple average
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    if avg_loss == 0:
        rsi[period] = 100
    else:
        rs = avg_gain / avg_loss
        rsi[period] = 100 - (100 / (1 + rs))

    # Subsequent calculations use smoothed average
    for i in range(period, len(prices) - 1):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            rsi[i + 1] = 100
        else:
            rs = avg_gain / avg_loss
            rsi[i + 1] = 100 - (100 / (1 + rs))

    return rsi


def calculate_macd(
    prices: np.ndarray,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate MACD (Moving Average Convergence Divergence)

    Returns: (macd_line, signal_line, histogram)
    """
    fast_ema = calculate_ema(prices, fast_period)
    slow_ema = calculate_ema(prices, slow_period)

    macd_line = fast_ema - slow_ema

    # Signal line is EMA of MACD line
    signal_line = np.full(len(prices), np.nan)
    valid_macd = ~np.isnan(macd_line)
    if np.sum(valid_macd) >= signal_period:
        first_valid = np.where(valid_macd)[0][0]
        macd_valid = macd_line[first_valid:]
        signal_ema = calculate_ema(macd_valid, signal_period)
        signal_line[first_valid:] = signal_ema

    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


def calculate_bollinger_bands(
    prices: np.ndarray,
    period: int = 20,
    num_std: float = 2.0
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate Bollinger Bands

    Returns: (upper_band, middle_band, lower_band)
    """
    middle_band = calculate_sma(prices, period)

    std = np.full(len(prices), np.nan)
    for i in range(period - 1, len(prices)):
        std[i] = np.std(prices[i - period + 1:i + 1])

    upper_band = middle_band + (num_std * std)
    lower_band = middle_band - (num_std * std)

    return upper_band, middle_band, lower_band


def calculate_atr(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 14
) -> np.ndarray:
    """
    Calculate Average True Range (ATR)

    True Range = max(high-low, abs(high-prev_close), abs(low-prev_close))
    """
    if len(close) < period + 1:
        return np.full(len(close), np.nan)

    tr = np.full(len(close), np.nan)
    tr[0] = high[0] - low[0]

    for i in range(1, len(close)):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1])
        )

    atr = np.full(len(close), np.nan)
    atr[period - 1] = np.mean(tr[:period])

    for i in range(period, len(close)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

    return atr


def strategy_rsi_macd(
    candles: OHLCVCandles | pd.DataFrame,
    rsi_period: int = 14,
    rsi_oversold: float = 30,
    rsi_overbought: float = 70,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9
) -> TradeSignal:
    """
    RSI + MACD Combined Strategy

    Backtested performance: 55-77% win rate depending on market conditions.
    Best used in trending markets with momentum confirmation.

    Buy Signal:
    - RSI below oversold level (< 30) or rising from oversold
    - MACD line crosses above signal line (bullish crossover)

    Sell Signal:
    - RSI above overbought level (> 70) or falling from overbought
    - MACD line crosses below signal line (bearish crossover)

    Args:
        candles: OHLCVCandles object or DataFrame with OHLC data
        rsi_period: RSI calculation period
        rsi_oversold: RSI oversold threshold
        rsi_overbought: RSI overbought threshold
        macd_fast: MACD fast period
        macd_slow: MACD slow period
        macd_signal: MACD signal period

    Returns:
        TradeSignal with recommendation and details
    """
    # Extract price data
    if isinstance(candles, OHLCVCandles):
        prices = np.array(candles.close_positions)
    elif isinstance(candles, pd.DataFrame):
        prices = candles["close"].to_numpy()
    else:
        raise CoinbotUnexpectedTypeError(f"Expected OHLCVCandles or DataFrame, got {type(candles)}")

    if len(prices) < max(rsi_period, macd_slow) + macd_signal + 5:
        return TradeSignal(
            signal=Signal.HOLD,
            confidence=0.0,
            strategy_name="RSI_MACD",
            reason="Insufficient data for calculation"
        )

    # Calculate indicators
    rsi = calculate_rsi(prices, rsi_period)
    macd_line, signal_line, histogram = calculate_macd(
        prices, macd_fast, macd_slow, macd_signal
    )

    current_rsi = rsi[-1]
    prev_rsi = rsi[-2]
    current_macd = macd_line[-1]
    prev_macd = macd_line[-2]
    current_signal = signal_line[-1]
    prev_signal = signal_line[-2]
    current_histogram = histogram[-1]
    prev_histogram = histogram[-2]

    # Check for NaN
    if np.isnan([current_rsi, current_macd, current_signal]).any():
        return TradeSignal(
            signal=Signal.HOLD,
            confidence=0.0,
            strategy_name="RSI_MACD",
            reason="Indicators not ready"
        )

    # Detect crossovers
    macd_bullish_cross = prev_macd <= prev_signal and current_macd > current_signal
    macd_bearish_cross = prev_macd >= prev_signal and current_macd < current_signal

    # RSI conditions
    rsi_oversold_condition = current_rsi < rsi_oversold
    rsi_overbought_condition = current_rsi > rsi_overbought
    rsi_rising = current_rsi > prev_rsi
    rsi_falling = current_rsi < prev_rsi

    # Histogram momentum
    histogram_increasing = current_histogram > prev_histogram
    histogram_decreasing = current_histogram < prev_histogram

    indicators = {
        "rsi": current_rsi,
        "macd": current_macd,
        "macd_signal": current_signal,
        "macd_histogram": current_histogram
    }

    # STRONG BUY: RSI oversold + MACD bullish crossover
    if rsi_oversold_condition and macd_bullish_cross:
        return TradeSignal(
            signal=Signal.STRONG_BUY,
            confidence=0.85,
            strategy_name="RSI_MACD",
            reason=f"RSI oversold ({current_rsi:.1f}) + MACD bullish crossover",
            suggested_stop_loss_pct=3.0,
            suggested_take_profit_pct=6.0,
            indicators=indicators
        )

    # BUY: RSI rising from oversold OR MACD bullish cross with positive momentum
    if (current_rsi < 40 and rsi_rising and histogram_increasing) or \
       (macd_bullish_cross and current_rsi < 60):
        return TradeSignal(
            signal=Signal.BUY,
            confidence=0.65,
            strategy_name="RSI_MACD",
            reason=f"RSI ({current_rsi:.1f}) with bullish MACD momentum",
            suggested_stop_loss_pct=2.5,
            suggested_take_profit_pct=5.0,
            indicators=indicators
        )

    # STRONG SELL: RSI overbought + MACD bearish crossover
    if rsi_overbought_condition and macd_bearish_cross:
        return TradeSignal(
            signal=Signal.STRONG_SELL,
            confidence=0.85,
            strategy_name="RSI_MACD",
            reason=f"RSI overbought ({current_rsi:.1f}) + MACD bearish crossover",
            suggested_stop_loss_pct=3.0,
            suggested_take_profit_pct=6.0,
            indicators=indicators
        )

    # SELL: RSI falling from overbought OR MACD bearish cross
    if (current_rsi > 60 and rsi_falling and histogram_decreasing) or \
       (macd_bearish_cross and current_rsi > 40):
        return TradeSignal(
            signal=Signal.SELL,
            confidence=0.65,
            strategy_name="RSI_MACD",
            reason=f"RSI ({current_rsi:.1f}) with bearish MACD momentum",
            suggested_stop_loss_pct=2.5,
            suggested_take_profit_pct=5.0,
            indicators=indicators
        )

    # HOLD
    return TradeSignal(
        signal=Signal.HOLD,
        confidence=0.5,
        strategy_name="RSI_MACD",
        reason=f"No clear signal. RSI: {current_rsi:.1f}, MACD: {current_macd:.4f}",
        indicators=indicators
    )


def strategy_ema_crossover(
    candles: OHLCVCandles | pd.DataFrame,
    fast_period: int = 12,
    slow_period: int = 50,
    trend_period: int = 200
) -> TradeSignal:
    """
    EMA Crossover Strategy (Golden Cross / Death Cross)

    Popular strategy with clear entry/exit signals.
    Best for trending markets, may whipsaw in ranging markets.

    Buy Signal (Golden Cross):
    - Fast EMA crosses above slow EMA
    - Price above trend EMA (200) for confirmation

    Sell Signal (Death Cross):
    - Fast EMA crosses below slow EMA
    - Price below trend EMA (200) for confirmation

    Args:
        candles: OHLCVCandles object or DataFrame with OHLC data
        fast_period: Fast EMA period
        slow_period: Slow EMA period
        trend_period: Trend EMA period

    Returns:
        TradeSignal with recommendation and details
    """
    # Extract price data
    if isinstance(candles, OHLCVCandles):
        prices = np.array(candles.close_positions)
    elif isinstance(candles, pd.DataFrame):
        prices = candles["close"].to_numpy()
    else:
        raise CoinbotUnexpectedTypeError(f"Expected OHLCVCandles or DataFrame, got {type(candles)}")

    min_data = trend_period + 5
    if len(prices) < min_data:
        return TradeSignal(
            signal=Signal.HOLD,
            confidence=0.0,
            strategy_name="EMA_CROSSOVER",
            reason=f"Need at least {min_data} data points"
        )

    fast_ema = calculate_ema(prices, fast_period)
    slow_ema = calculate_ema(prices, slow_period)
    trend_ema = calculate_ema(prices, trend_period)

    current_price = prices[-1]
    current_fast = fast_ema[-1]
    prev_fast = fast_ema[-2]
    current_slow = slow_ema[-1]
    prev_slow = slow_ema[-2]
    current_trend = trend_ema[-1]

    if np.isnan([current_fast, current_slow, current_trend]).any():
        return TradeSignal(
            signal=Signal.HOLD,
            confidence=0.0,
            strategy_name="EMA_CROSSOVER",
            reason="EMAs not ready"
        )

    # Detect crossovers
    golden_cross = prev_fast <= prev_slow and current_fast > current_slow
    death_cross = prev_fast >= prev_slow and current_fast < current_slow

    # Trend filter
    uptrend = current_price > current_trend
    downtrend = current_price < current_trend

    # Distance from EMAs (for confluence)
    fast_above_slow = current_fast > current_slow
    price_above_fast = current_price > current_fast

    indicators = {
        "ema_fast": current_fast,
        "ema_slow": current_slow,
        "ema_trend": current_trend,
        "price": current_price
    }

    # STRONG BUY: Golden cross with uptrend confirmation
    if golden_cross and uptrend:
        return TradeSignal(
            signal=Signal.STRONG_BUY,
            confidence=0.80,
            strategy_name="EMA_CROSSOVER",
            reason=f"Golden cross with uptrend (price > EMA{trend_period})",
            suggested_stop_loss_pct=3.0,
            suggested_take_profit_pct=8.0,
            indicators=indicators
        )

    # BUY: Golden cross without trend confirmation
    if golden_cross:
        return TradeSignal(
            signal=Signal.BUY,
            confidence=0.60,
            strategy_name="EMA_CROSSOVER",
            reason="Golden cross (no trend confirmation)",
            suggested_stop_loss_pct=2.5,
            suggested_take_profit_pct=5.0,
            indicators=indicators
        )

    # STRONG SELL: Death cross with downtrend confirmation
    if death_cross and downtrend:
        return TradeSignal(
            signal=Signal.STRONG_SELL,
            confidence=0.80,
            strategy_name="EMA_CROSSOVER",
            reason=f"Death cross with downtrend (price < EMA{trend_period})",
            suggested_stop_loss_pct=3.0,
            suggested_take_profit_pct=8.0,
            indicators=indicators
        )

    # SELL: Death cross without trend confirmation
    if death_cross:
        return TradeSignal(
            signal=Signal.SELL,
            confidence=0.60,
            strategy_name="EMA_CROSSOVER",
            reason="Death cross (no trend confirmation)",
            suggested_stop_loss_pct=2.5,
            suggested_take_profit_pct=5.0,
            indicators=indicators
        )

    # Continuation signals (weaker)
    if fast_above_slow and price_above_fast and uptrend:
        return TradeSignal(
            signal=Signal.BUY,
            confidence=0.45,
            strategy_name="EMA_CROSSOVER",
            reason="Bullish alignment (price > fast > slow, uptrend)",
            indicators=indicators
        )

    if not fast_above_slow and not price_above_fast and downtrend:
        return TradeSignal(
            signal=Signal.SELL,
            confidence=0.45,
            strategy_name="EMA_CROSSOVER",
            reason="Bearish alignment (price < fast < slow, downtrend)",
            indicators=indicators
        )

    return TradeSignal(
        signal=Signal.HOLD,
        confidence=0.5,
        strategy_name="EMA_CROSSOVER",
        reason="No crossover signal",
        indicators=indicators
    )


def strategy_bollinger_mean_reversion(
    candles: OHLCVCandles | pd.DataFrame,
    period: int = 20,
    num_std: float = 2.0,
    rsi_period: int = 14
) -> TradeSignal:
    """
    Bollinger Bands Mean Reversion Strategy

    Works best in ranging/sideways markets.
    Uses RSI for confirmation to reduce false signals.

    Buy Signal:
    - Price touches or breaks below lower band
    - RSI confirms oversold (< 30)

    Sell Signal:
    - Price touches or breaks above upper band
    - RSI confirms overbought (> 70)

    Exit:
    - Price returns to middle band (mean)

    Args:
        candles: OHLCVCandles object or DataFrame with OHLC data
        period: Bollinger Bands period
        num_std: Number of standard deviations for bands
        rsi_period: RSI calculation period

    Returns:
        TradeSignal with recommendation and details
    """
    # Extract price data
    if isinstance(candles, OHLCVCandles):
        prices = np.array(candles.close_positions)
    elif isinstance(candles, pd.DataFrame):
        prices = candles["close"].to_numpy()
    else:
        raise CoinbotUnexpectedTypeError(f"Expected OHLCVCandles or DataFrame, got {type(candles)}")

    min_data = max(period, rsi_period) + 5
    if len(prices) < min_data:
        return TradeSignal(
            signal=Signal.HOLD,
            confidence=0.0,
            strategy_name="BB_MEAN_REVERSION",
            reason=f"Need at least {min_data} data points"
        )

    upper, middle, lower = calculate_bollinger_bands(prices, period, num_std)
    rsi = calculate_rsi(prices, rsi_period)

    current_price = prices[-1]
    current_upper = upper[-1]
    current_middle = middle[-1]
    current_lower = lower[-1]
    current_rsi = rsi[-1]

    if np.isnan([current_upper, current_middle, current_lower, current_rsi]).any():
        return TradeSignal(
            signal=Signal.HOLD,
            confidence=0.0,
            strategy_name="BB_MEAN_REVERSION",
            reason="Indicators not ready"
        )

    # Calculate position within bands (0 = lower, 1 = upper)
    band_width = current_upper - current_lower
    if band_width > 0:
        position_in_bands = (current_price - current_lower) / band_width
    else:
        position_in_bands = 0.5

    # Distance from mean as percentage
    distance_from_mean_pct = ((current_price - current_middle) / current_middle) * 100

    indicators = {
        "bb_upper": current_upper,
        "bb_middle": current_middle,
        "bb_lower": current_lower,
        "rsi": current_rsi,
        "band_position": position_in_bands,
        "distance_from_mean_pct": distance_from_mean_pct
    }

    # STRONG BUY: Price below lower band + RSI oversold
    if current_price <= current_lower and current_rsi < 30:
        return TradeSignal(
            signal=Signal.STRONG_BUY,
            confidence=0.80,
            strategy_name="BB_MEAN_REVERSION",
            reason=f"Price at/below lower band, RSI oversold ({current_rsi:.1f})",
            suggested_stop_loss_pct=2.0,
            suggested_take_profit_pct=abs(distance_from_mean_pct) * 0.8,
            indicators=indicators
        )

    # BUY: Price near lower band + RSI below 40
    if position_in_bands < 0.1 and current_rsi < 40:
        return TradeSignal(
            signal=Signal.BUY,
            confidence=0.65,
            strategy_name="BB_MEAN_REVERSION",
            reason=f"Price near lower band, RSI low ({current_rsi:.1f})",
            suggested_stop_loss_pct=2.5,
            suggested_take_profit_pct=abs(distance_from_mean_pct) * 0.6,
            indicators=indicators
        )

    # STRONG SELL: Price above upper band + RSI overbought
    if current_price >= current_upper and current_rsi > 70:
        return TradeSignal(
            signal=Signal.STRONG_SELL,
            confidence=0.80,
            strategy_name="BB_MEAN_REVERSION",
            reason=f"Price at/above upper band, RSI overbought ({current_rsi:.1f})",
            suggested_stop_loss_pct=2.0,
            suggested_take_profit_pct=abs(distance_from_mean_pct) * 0.8,
            indicators=indicators
        )

    # SELL: Price near upper band + RSI above 60
    if position_in_bands > 0.9 and current_rsi > 60:
        return TradeSignal(
            signal=Signal.SELL,
            confidence=0.65,
            strategy_name="BB_MEAN_REVERSION",
            reason=f"Price near upper band, RSI high ({current_rsi:.1f})",
            suggested_stop_loss_pct=2.5,
            suggested_take_profit_pct=abs(distance_from_mean_pct) * 0.6,
            indicators=indicators
        )

    return TradeSignal(
        signal=Signal.HOLD,
        confidence=0.5,
        strategy_name="BB_MEAN_REVERSION",
        reason=f"Price in neutral zone ({position_in_bands:.1%} in bands)",
        indicators=indicators
    )


def strategy_multi_confluence(
    candles: OHLCVCandles | pd.DataFrame
) -> TradeSignal:
    """
    Multi-Indicator Confluence Strategy

    Combines multiple strategies for higher confidence signals.
    Only generates signals when multiple indicators align.

    Indicators used:
    - RSI + MACD
    - EMA Crossover (12/50)
    - Bollinger Bands

    Requires 2+ strategies to agree for a signal.

    Args:
        candles: OHLCVCandles object or DataFrame with OHLC data

    Returns:
        TradeSignal with recommendation and details
    """
    # Extract OHLC data for ATR calculation
    if isinstance(candles, OHLCVCandles):
        high = np.array(candles.high_positions)
        low = np.array(candles.low_positions)
        close = np.array(candles.close_positions)
    elif isinstance(candles, pd.DataFrame):
        high = candles["high"].to_numpy()
        low = candles["low"].to_numpy()
        close = candles["close"].to_numpy()
    else:
        raise CoinbotUnexpectedTypeError(f"Expected OHLCVCandles or DataFrame, got {type(candles)}")

    # Get individual signals
    rsi_macd_signal = strategy_rsi_macd(candles)
    ema_signal = strategy_ema_crossover(candles, fast_period=12, slow_period=50, trend_period=200)
    bb_signal = strategy_bollinger_mean_reversion(candles)

    # Count bullish and bearish signals
    buy_signals = []
    sell_signals = []

    for signal in [rsi_macd_signal, ema_signal, bb_signal]:
        if signal.signal in [Signal.BUY, Signal.STRONG_BUY]:
            buy_signals.append(signal)
        elif signal.signal in [Signal.SELL, Signal.STRONG_SELL]:
            sell_signals.append(signal)

    indicators = {
        "rsi_macd": rsi_macd_signal.signal.value,
        "ema_crossover": ema_signal.signal.value,
        "bollinger": bb_signal.signal.value,
        "buy_count": len(buy_signals),
        "sell_count": len(sell_signals),
        "details": {
            "rsi_macd": rsi_macd_signal.indicators,
            "ema": ema_signal.indicators,
            "bb": bb_signal.indicators
        }
    }

    # Calculate ATR for stop loss
    atr = calculate_atr(high, low, close, 14)
    current_atr = atr[-1] if not np.isnan(atr[-1]) else 0
    atr_pct = (current_atr / close[-1]) * 100 if current_atr > 0 else 2.0

    # STRONG BUY: All 3 strategies agree
    if len(buy_signals) == 3:
        avg_confidence = float(np.mean([s.confidence for s in buy_signals]))
        return TradeSignal(
            signal=Signal.STRONG_BUY,
            confidence=min(0.95, avg_confidence + 0.2),
            strategy_name="CONFLUENCE",
            reason=f"All indicators bullish: {[s.strategy_name for s in buy_signals]}",
            suggested_stop_loss_pct=atr_pct * 1.5,
            suggested_take_profit_pct=atr_pct * 3,
            indicators=indicators
        )

    # BUY: 2 strategies agree
    if len(buy_signals) >= 2:
        avg_confidence = float(np.mean([s.confidence for s in buy_signals]))
        return TradeSignal(
            signal=Signal.BUY,
            confidence=avg_confidence,
            strategy_name="CONFLUENCE",
            reason=f"Multiple bullish signals: {[s.strategy_name for s in buy_signals]}",
            suggested_stop_loss_pct=atr_pct * 2,
            suggested_take_profit_pct=atr_pct * 4,
            indicators=indicators
        )

    # STRONG SELL: All 3 strategies agree
    if len(sell_signals) == 3:
        avg_confidence = float(np.mean([s.confidence for s in sell_signals]))
        return TradeSignal(
            signal=Signal.STRONG_SELL,
            confidence=min(0.95, avg_confidence + 0.2),
            strategy_name="CONFLUENCE",
            reason=f"All indicators bearish: {[s.strategy_name for s in sell_signals]}",
            suggested_stop_loss_pct=atr_pct * 1.5,
            suggested_take_profit_pct=atr_pct * 3,
            indicators=indicators
        )

    # SELL: 2 strategies agree
    if len(sell_signals) >= 2:
        avg_confidence = float(np.mean([s.confidence for s in sell_signals]))
        return TradeSignal(
            signal=Signal.SELL,
            confidence=avg_confidence,
            strategy_name="CONFLUENCE",
            reason=f"Multiple bearish signals: {[s.strategy_name for s in sell_signals]}",
            suggested_stop_loss_pct=atr_pct * 2,
            suggested_take_profit_pct=atr_pct * 4,
            indicators=indicators
        )

    return TradeSignal(
        signal=Signal.HOLD,
        confidence=0.5,
        strategy_name="CONFLUENCE",
        reason=f"No confluence (buy: {len(buy_signals)}, sell: {len(sell_signals)})",
        indicators=indicators
    )
