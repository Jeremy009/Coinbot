import numpy as np
import pandas as pd

from coinbot.backend.candles import OHLCVCandles
from coinbot.backend.exceptions import CoinbotUnexpectedTypeError


def macd_indicator(candles: OHLCVCandles or pd.DataFrame, short_period: int = 12, long_period: int = 26,
                   signal_period: int = 9) -> pd.DataFrame:
    """ This function computes the MACD (Moving Average Convergence Divergence) indicator based on a list of
    chandles data. THe MACD is a trend-following momentum indicator that shows the relationship between two moving
    averages of a security’s price. The MACD is generally calculated by subtracting the 26-period exponential moving
    average (EMA) from the 12-period EMA.

    Moving average convergence divergence (MACD) indicators can be interpreted in several ways, but the more common
    methods are crossovers, divergences, and rapid rises/falls.

    Args:
        candles: An object with candles data
        short_period: The number of periods to consider for the short signal or timeframe (current/recent state)
        long_period: The number of periods to consider for the long signal or timeframe (global/historic trend)
        signal_period: The number of periods needed for performing the EMA on the MACD-line

    Returns:
        candles_df: The dataframe with an additional macd_line and macd_signal colums

    """
    # Get the closing positions of the candles and convert to a Pandas series
    if isinstance(candles, OHLCVCandles):
        closing_positions = pd.Series(candles.close_positions)
    elif isinstance(candles, pd.DataFrame):
        closing_positions = candles["close"]

    # Get an exponential moving average over different time periods to analyze changes in trends
    ema_fast = closing_positions.ewm(span=short_period).mean()
    ema_slow = closing_positions.ewm(span=long_period).mean()

    # Compute the indicators
    macd_line = ema_fast - ema_slow
    macd_signal = macd_line.ewm(span=signal_period).mean()

    # Save everything in dataframe and return dataframe
    df = candles.as_dataframe() if not isinstance(candles, pd.DataFrame) else candles
    df["ema_fast"] = ema_fast
    df["ema_slow"] = ema_slow
    df["macd_line"] = macd_line
    df["macd_signal"] = macd_signal

    return df


def rsi_indicator(candles: OHLCVCandles, period: int = 14) -> pd.DataFrame:
    """ This function computes the RSI (Relative Strength Index) indicator based on a list of chandles data. The RSI
    is a momentum oscillator indicator between 0 and 100. Standard RSI uses a 14 days period or 14 weeks period.

    Traditional interpretation and usage of the RSI are that values of 70 or above indicate that a security is becoming
    overbought or overvalued and may be primed for a trend reversal or corrective pullback in price. An RSI reading of
    30 or below indicates an oversold or undervalued condition.

    Args:
        candles: An object with candles data
        period: The length of the past period to consider for the RSI computation

    Returns:
        candles_df: The dataframe with an additional rsi colums

    """
    # Get the closing positions of the candles and convert to a Pandas series
    closing_positions = pd.Series(candles.close_positions)
    difference = closing_positions.diff().dropna()

    # Split the series in gains and losses
    gains, losses = difference.copy(), difference.copy()
    gains[gains <= 0.0] = 0.0
    losses[losses >= 0.0] = 0.0

    # Compute the exponentially weighted moving averages for the gains and the losses separately
    average_gain = gains.ewm(com=(period - 1), min_periods=period).mean()
    average_losses = losses.abs().ewm(com=(period - 1), min_periods=period).mean()

    # Compute the relative strength
    rs = average_gain / average_losses
    rsi = 100 - 100 / (1 + rs)
    rsi = np.round(rsi, 2)

    # Save everything in dataframe and return dataframe
    df = candles.as_dataframe()
    df["rsi"] = rsi

    return df


def mfi_indicator(candles: OHLCVCandles, period: int = 14) -> pd.DataFrame:
    """ Computes and returns the  Money Flow Index (MFI) which is a technical oscillator that uses price and volume
    data for identifying overbought or oversold signals in an asset. It can also be used to spot divergences which
    warn of a trend change in price.

    The oscillator moves between 0 and 100. Generally an MFI reading above 80 is considered overbought and an MFI
    reading below 20 is considered oversold, although levels of 90 and 10 are also used as thresholds.

    Args:
        candles: An object with candles data
        period: The length of the past period to consider for the MFI computation

    Returns:
        candles_df: The dataframe with an additional macd_line and macd_signal colums

    """
    # Restructure the data to a Pandas dataframe
    df = candles.as_dataframe()
    df['typical_price'] = (df["high"] + df["low"] + df["close"]) / 3.0
    df['money_flow'] = df['typical_price'] * df["volume"]
    df['money_flow_index'] = 0.0
    df['money_flow_positive'] = 0.0
    df['money_flow_negative'] = 0.0

    # Iterate over all rows and compute the mfi
    for i, row in df.iterrows():
        if not isinstance(i, int):
            raise CoinbotUnexpectedTypeError("Expected 'i' returned from df.iterrows() to be an integer")
        if i > 0:
            if row['typical_price'] > df.at[i - 1, 'typical_price']:
                df.at[i, 'money_flow_positive'] = row['money_flow']
            else:
                df.at[i, 'money_flow_negative'] = row['money_flow']

        if i >= period:
            positive_sum = df['money_flow_positive'][i - period + 1:i + 1].sum()
            negative_sum = df['money_flow_negative'][i - period + 1:i + 1].sum()
            m_r = positive_sum / (negative_sum if negative_sum != 0.0 else 0.00001)

            mfi = 100 - (100 / (1 + m_r))

            df.at[i, 'money_flow_index'] = mfi

    # Drop intermediate columns
    df = df.drop(['typical_price'], axis=1)
    df = df.drop(['money_flow'], axis=1)
    df = df.drop(['money_flow_negative'], axis=1)
    df = df.drop(['money_flow_positive'], axis=1)

    return df
