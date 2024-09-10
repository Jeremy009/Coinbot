from enum import Enum

import pandas as pd

from coinbot.backend.candles import OHLCVCandles
from coinbot.backend.indicators import rsi_indicator, macd_indicator


class TradebotAction(Enum):
    """ Possible trade/position actions. Either open a trade (BUY), hold position, or close a trade (SELL). """
    BUY = 1
    HOLD = 0
    SELL = -1


def macd_signal(candles: OHLCVCandles or pd.DataFrame, **kwargs) -> TradebotAction:
    """ MACD triggers technical signals when it crosses above (to buy) or below (to sell) its signal line. The speed of
    crossovers is also taken as a signal of a market is overbought or oversold. MACD helps investors understand whether
    the bullish or bearish movement in the price is strengthening or weakening. """
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


def rsi_signal(candles: OHLCVCandles, **kwargs) -> TradebotAction:
    """ The rsi-signal is a signal based on the rsi.

    Args:
        candles: An object with candles data
        kwargs: For all possible kwargs see the documentation at coinbot.backend.indicators.rsi_indicator

    Returns:
         action: Recommended action based on current data and established strategy

    """
    rsi = rsi_indicator(candles, **kwargs)

    if rsi < 30:
        return TradebotAction.BUY
    elif rsi > 70:
        return TradebotAction.SELL
    else:
        return TradebotAction.HOLD
