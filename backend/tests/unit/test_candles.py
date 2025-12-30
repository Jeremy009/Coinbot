"""Tests for OHLCVCandles model."""

import numpy as np
import pandas as pd

from coinbot_backend.models.candles import OHLCVCandles


def test_candles_creation():
    """Test creating a candles object."""
    timestamps = [1000.0, 2000.0, 3000.0]
    opens = [100.0, 110.0, 105.0]
    highs = [115.0, 120.0, 110.0]
    lows = [95.0, 105.0, 100.0]
    closes = [110.0, 105.0, 108.0]
    volumes = [1000.0, 1500.0, 1200.0]

    candles = OHLCVCandles(
        symbol="TEST",
        timestamps=timestamps,
        time_resolution="1m",
        opening_positions=opens,
        high_positions=highs,
        low_positions=lows,
        close_positions=closes,
        volumes=volumes,
    )

    assert candles.symbol == "TEST"
    assert candles.num_candles == 3
    assert len(candles.timestamps) == 3


def test_candles_as_dataframe():
    """Test converting candles to DataFrame."""
    timestamps = [1000.0, 2000.0, 3000.0]
    opens = [100.0, 110.0, 105.0]
    highs = [115.0, 120.0, 110.0]
    lows = [95.0, 105.0, 100.0]
    closes = [110.0, 105.0, 108.0]
    volumes = [1000.0, 1500.0, 1200.0]

    candles = OHLCVCandles(
        symbol="TEST",
        timestamps=timestamps,
        time_resolution="1m",
        opening_positions=opens,
        high_positions=highs,
        low_positions=lows,
        close_positions=closes,
        volumes=volumes,
    )

    df = candles.as_dataframe()
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]

    # Verify data integrity
    for i in range(3):
        assert df["timestamp"].iloc[i] == timestamps[i]
        assert df["open"].iloc[i] == opens[i]
        assert df["high"].iloc[i] == highs[i]
        assert df["low"].iloc[i] == lows[i]
        assert df["close"].iloc[i] == closes[i]
        assert df["volume"].iloc[i] == volumes[i]
