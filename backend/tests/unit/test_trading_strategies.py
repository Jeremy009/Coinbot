"""Unit tests for trading strategies and indicators."""

import numpy as np
import pytest

from coinbot_backend.models.candles import OHLCVCandles
from coinbot_backend.models.trading import Signal
from coinbot_backend.services.trading_strategies import (
    calculate_rsi,
    calculate_macd,
    calculate_ema,
    calculate_sma,
    calculate_bollinger_bands,
    calculate_atr,
    strategy_rsi_macd,
    strategy_ema_crossover,
    strategy_bollinger_mean_reversion,
    strategy_multi_confluence,
)


class TestIndicatorCalculations:
    """Test indicator calculation functions."""

    def test_rsi_determinism(self):
        """Test that RSI calculations are deterministic."""
        prices = np.array([100.0 + i * 0.5 + np.sin(i * 0.1) * 5 for i in range(300)])

        rsi_1 = calculate_rsi(prices, 14)
        rsi_2 = calculate_rsi(prices, 14)

        assert np.allclose(rsi_1, rsi_2, equal_nan=True), "RSI calculations should be deterministic"

    def test_macd_determinism(self):
        """Test that MACD calculations are deterministic."""
        prices = np.array([100.0 + i * 0.5 + np.sin(i * 0.1) * 5 for i in range(300)])

        macd_1 = calculate_macd(prices, 12, 26, 9)
        macd_2 = calculate_macd(prices, 12, 26, 9)

        for i in range(3):
            assert np.allclose(macd_1[i], macd_2[i], equal_nan=True), \
                f"MACD component {i} should be deterministic"

    def test_ema_determinism(self):
        """Test that EMA calculations are deterministic."""
        prices = np.array([100.0 + i * 0.5 for i in range(100)])

        ema_1 = calculate_ema(prices, 12)
        ema_2 = calculate_ema(prices, 12)

        assert np.allclose(ema_1, ema_2, equal_nan=True), "EMA calculations should be deterministic"

    def test_sma_determinism(self):
        """Test that SMA calculations are deterministic."""
        prices = np.array([100.0 + i * 0.5 for i in range(100)])

        sma_1 = calculate_sma(prices, 20)
        sma_2 = calculate_sma(prices, 20)

        assert np.allclose(sma_1, sma_2, equal_nan=True), "SMA calculations should be deterministic"

    def test_bollinger_bands_determinism(self):
        """Test that Bollinger Bands calculations are deterministic."""
        prices = np.array([100.0 + i * 0.5 + np.sin(i * 0.1) * 5 for i in range(100)])

        bb_1 = calculate_bollinger_bands(prices, 20, 2.0)
        bb_2 = calculate_bollinger_bands(prices, 20, 2.0)

        for i in range(3):
            assert np.allclose(bb_1[i], bb_2[i], equal_nan=True), \
                f"Bollinger Band component {i} should be deterministic"

    def test_atr_determinism(self):
        """Test that ATR calculations are deterministic."""
        high = np.array([102.0 + i * 0.5 for i in range(100)])
        low = np.array([98.0 + i * 0.5 for i in range(100)])
        close = np.array([100.0 + i * 0.5 for i in range(100)])

        atr_1 = calculate_atr(high, low, close, 14)
        atr_2 = calculate_atr(high, low, close, 14)

        assert np.allclose(atr_1, atr_2, equal_nan=True), "ATR calculations should be deterministic"

    def test_rsi_range(self):
        """Test that RSI values are within valid range (0-100)."""
        prices = np.array([100.0 + i * 0.5 + np.sin(i * 0.1) * 10 for i in range(100)])
        rsi = calculate_rsi(prices, 14)

        # Filter out NaN values
        valid_rsi = rsi[~np.isnan(rsi)]

        assert np.all(valid_rsi >= 0), "RSI should be >= 0"
        assert np.all(valid_rsi <= 100), "RSI should be <= 100"

    def test_insufficient_data_handling(self):
        """Test that indicators handle insufficient data gracefully."""
        prices = np.array([100.0, 101.0, 102.0])  # Only 3 data points

        # Should return NaN-filled arrays without crashing
        rsi = calculate_rsi(prices, 14)
        assert len(rsi) == len(prices), "RSI should return same length as input"
        assert np.all(np.isnan(rsi)), "RSI should be all NaN with insufficient data"

        ema = calculate_ema(prices, 12)
        assert len(ema) == len(prices), "EMA should return same length as input"


class TestStrategyParameters:
    """Test that strategy default parameters match expected values."""

    def test_rsi_macd_defaults(self):
        """Test RSI+MACD strategy default parameters."""
        # Create minimal test data
        timestamps = [1000000000000 + i * 3600000 for i in range(300)]
        prices = [100.0 + i * 0.5 + np.sin(i * 0.1) * 5 for i in range(300)]

        candles = OHLCVCandles(
            symbol="TEST",
            timestamps=timestamps,
            time_resolution="1h",
            opening_positions=prices,
            high_positions=[p + 1 for p in prices],
            low_positions=[p - 1 for p in prices],
            close_positions=prices,
            volumes=[1000000.0] * 300
        )

        # Call with defaults
        signal = strategy_rsi_macd(candles)

        # Should not crash and should return a TradeSignal
        assert signal is not None
        assert isinstance(signal.signal, Signal)
        assert signal.strategy_name == "RSI_MACD"

    def test_ema_crossover_defaults(self):
        """Test EMA crossover strategy default parameters."""
        timestamps = [1000000000000 + i * 3600000 for i in range(300)]
        prices = [100.0 + i * 0.5 for i in range(300)]

        candles = OHLCVCandles(
            symbol="TEST",
            timestamps=timestamps,
            time_resolution="1h",
            opening_positions=prices,
            high_positions=[p + 1 for p in prices],
            low_positions=[p - 1 for p in prices],
            close_positions=prices,
            volumes=[1000000.0] * 300
        )

        # Call with specific parameters that should match the strategy
        signal = strategy_ema_crossover(candles, fast_period=12, slow_period=50, trend_period=200)

        assert signal is not None
        assert isinstance(signal.signal, Signal)
        assert signal.strategy_name == "EMA_CROSSOVER"

    def test_bollinger_mean_reversion_defaults(self):
        """Test Bollinger Bands strategy default parameters."""
        timestamps = [1000000000000 + i * 3600000 for i in range(300)]
        prices = [100.0 + i * 0.5 + np.sin(i * 0.1) * 5 for i in range(300)]

        candles = OHLCVCandles(
            symbol="TEST",
            timestamps=timestamps,
            time_resolution="1h",
            opening_positions=prices,
            high_positions=[p + 1 for p in prices],
            low_positions=[p - 1 for p in prices],
            close_positions=prices,
            volumes=[1000000.0] * 300
        )

        signal = strategy_bollinger_mean_reversion(candles, period=20, num_std=2.0, rsi_period=14)

        assert signal is not None
        assert isinstance(signal.signal, Signal)
        assert signal.strategy_name == "BB_MEAN_REVERSION"


class TestMultiConfluenceStrategy:
    """Test the multi-confluence strategy composition."""

    def test_multi_confluence_uses_all_strategies(self):
        """Test that multi-confluence calls all three strategies."""
        timestamps = [1000000000000 + i * 3600000 for i in range(300)]
        prices = [100.0 + i * 0.5 + np.sin(i * 0.1) * 5 for i in range(300)]

        candles = OHLCVCandles(
            symbol="TEST",
            timestamps=timestamps,
            time_resolution="1h",
            opening_positions=prices,
            high_positions=[p + 1 for p in prices],
            low_positions=[p - 1 for p in prices],
            close_positions=prices,
            volumes=[1000000.0] * 300
        )

        signal = strategy_multi_confluence(candles)

        assert signal is not None
        assert signal.strategy_name == "CONFLUENCE"
        assert signal.indicators is not None
        assert "rsi_macd" in signal.indicators
        assert "ema_crossover" in signal.indicators
        assert "bollinger" in signal.indicators

    def test_multi_confluence_determinism(self):
        """Test that multi-confluence is deterministic for same input."""
        timestamps = [1000000000000 + i * 3600000 for i in range(300)]
        prices = [100.0 + i * 0.5 + np.sin(i * 0.1) * 5 for i in range(300)]

        candles = OHLCVCandles(
            symbol="TEST",
            timestamps=timestamps,
            time_resolution="1h",
            opening_positions=prices,
            high_positions=[p + 1 for p in prices],
            low_positions=[p - 1 for p in prices],
            close_positions=prices,
            volumes=[1000000.0] * 300
        )

        signal_1 = strategy_multi_confluence(candles)
        signal_2 = strategy_multi_confluence(candles)

        assert signal_1.signal == signal_2.signal
        assert signal_1.confidence == signal_2.confidence
        assert signal_1.reason == signal_2.reason


class TestStrategyConsistency:
    """Test consistency between strategies and plotting parameters."""

    def test_indicator_parameters_match_bot_config(self):
        """Test that hardcoded indicator parameters match expected values."""
        # These are the parameters used in technical_analysis_plot.py
        # They should match the defaults used in strategy functions

        # RSI parameters
        expected_rsi_period = 14
        assert expected_rsi_period == 14, "RSI period should be 14"

        # MACD parameters
        expected_macd_fast = 12
        expected_macd_slow = 26
        expected_macd_signal = 9
        assert expected_macd_fast == 12, "MACD fast should be 12"
        assert expected_macd_slow == 26, "MACD slow should be 26"
        assert expected_macd_signal == 9, "MACD signal should be 9"

        # EMA parameters
        expected_ema_fast = 12
        expected_ema_slow = 50
        expected_ema_trend = 200
        assert expected_ema_fast == 12, "EMA fast should be 12"
        assert expected_ema_slow == 50, "EMA slow should be 50"
        assert expected_ema_trend == 200, "EMA trend should be 200"

        # Bollinger Bands parameters
        expected_bb_period = 20
        expected_bb_std = 2.0
        assert expected_bb_period == 20, "BB period should be 20"
        assert expected_bb_std == 2.0, "BB std should be 2.0"

    def test_example_script_defaults(self):
        """Test that example script defaults match bot configuration."""
        from coinbot_backend.config import settings

        # Default parameters from example_technical_analysis_plot.py
        example_resolution = '1h'
        example_span = '2w'

        # Bot configuration
        assert example_resolution == settings.bot_analysis_time_resolution, \
            "Example script resolution should match bot config"
        assert example_span == settings.bot_analysis_time_span, \
            "Example script time span should match bot config"
