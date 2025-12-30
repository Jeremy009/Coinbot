"""Trading signal generators based on technical indicators."""

from enum import Enum
from typing import Any

import pandas as pd

from coinbot_backend.models.candles import OHLCVCandles
from coinbot_backend.services.indicators import macd_indicator, rsi_indicator


class TradebotAction(Enum):
    """Possible trade/position actions: open a trade (BUY), hold position, or close a trade (SELL)."""

    BUY = 1
    HOLD = 0
    SELL = -1


def macd_signal(candles: OHLCVCandles | pd.DataFrame, **kwargs: Any) -> TradebotAction:
    """
    Generate trading signals based on MACD indicator.

    MACD triggers technical signals when it crosses above (to buy) or below (to sell)
    its signal line. The speed of crossovers is also taken as a signal of whether a
    market is overbought or oversold. MACD helps investors understand whether the bullish
    or bearish movement in the price is strengthening or weakening.

    Args:
        candles: Candles data or DataFrame with MACD columns
        **kwargs: Additional arguments to pass to macd_indicator

    Returns:
        TradebotAction: BUY, HOLD, or SELL signal
    """
    if isinstance(candles, pd.DataFrame) and "macd_line" in candles.columns and "macd_signal" in candles.columns:
        macd_df = candles
    else:
        macd_df = macd_indicator(candles, **kwargs)

    macd_hist = [h for h in macd_df["macd_line"] - macd_df["macd_signal"]]

    if macd_hist[-1] > 0 and macd_hist[-1] >= macd_hist[-2] >= macd_hist[-3]:
        # Momentum is positive and building
        return TradebotAction.BUY
    elif 0 < macd_hist[-1] <= macd_hist[-2] <= macd_hist[-3] <= macd_hist[-4]:
        # Momentum is still positive but clearly decreasing
        return TradebotAction.SELL
    elif macd_hist[-1] > 0:
        # Momentum is positive
        return TradebotAction.HOLD
    else:
        return TradebotAction.SELL


def rsi_signal(candles: OHLCVCandles, **kwargs: Any) -> TradebotAction:
    """
    Generate trading signals based on RSI indicator.

    Args:
        candles: An object with candles data
        **kwargs: For all possible kwargs see the documentation at coinbot_backend.services.indicators.rsi_indicator

    Returns:
        TradebotAction: Recommended action based on current data and established strategy
    """
    rsi_df = rsi_indicator(candles, **kwargs)
    rsi_value = rsi_df["rsi"].iloc[-1]

    if rsi_value < 30:
        return TradebotAction.BUY
    elif rsi_value > 70:
        return TradebotAction.SELL
    else:
        return TradebotAction.HOLD
