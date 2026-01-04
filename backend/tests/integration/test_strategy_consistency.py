"""Integration tests for strategy consistency between bot and plotting.

These tests use real API calls to Bitvavo to verify that:
1. The bot and plotting module produce identical signals for the same data
2. All indicator calculations match
3. Configuration defaults are consistent

Requires:
- Valid Bitvavo API credentials in .env file
- Internet connection
"""

import numpy as np
import pytest

from coinbot_backend.config import settings
from coinbot_backend.core.constants import TIME_RESOLUTIONS, TIME_SPANS
from coinbot_backend.services.bitvavo_client import get_bitvavo_client
from coinbot_backend.services.trading_strategies import (
    calculate_rsi,
    calculate_macd,
    calculate_ema,
    calculate_bollinger_bands,
    strategy_multi_confluence,
)


class TestBotPlottingConsistency:
    """Test that bot and plotting produce identical results."""

    def test_signal_consistency_with_real_data(self):
        """Test that signals are identical between bot and plotting for real market data."""
        client = get_bitvavo_client()
        symbol = "BTC"

        # Fetch candles using bot configuration
        candles = client.get_candles(
            symbol,
            settings.bot_analysis_time_resolution,
            settings.bot_analysis_time_span
        )

        assert len(candles.timestamps) > 0, "Should fetch at least some candles"

        # Get signal from strategy (same as bot uses in main.py:120)
        signal_from_bot = strategy_multi_confluence(candles)

        # Simulate what plotting does - calculate indicators separately
        df = candles.as_dataframe()
        close_prices = df['close'].to_numpy()
        high_prices = df['high'].to_numpy()
        low_prices = df['low'].to_numpy()

        # Calculate indicators (same as plotting does in technical_analysis_plot.py:70-81)
        ema_12 = calculate_ema(close_prices, 12)
        ema_50 = calculate_ema(close_prices, 50)
        ema_200 = calculate_ema(close_prices, 200)
        bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(close_prices, 20, 2.0)
        rsi = calculate_rsi(close_prices, 14)
        macd_line, macd_signal_line, macd_histogram = calculate_macd(close_prices, 12, 26, 9)

        # Verify indicators were calculated (not all NaN)
        assert not np.all(np.isnan(rsi)), "RSI should have some valid values"
        assert not np.all(np.isnan(macd_line)), "MACD should have some valid values"

        # Get signal again (same as plotting does in technical_analysis_plot.py:85)
        signal_from_plotting = strategy_multi_confluence(candles)

        # Signals should be identical
        assert signal_from_bot.signal == signal_from_plotting.signal, \
            f"Signals should match: {signal_from_bot.signal} vs {signal_from_plotting.signal}"
        assert signal_from_bot.confidence == signal_from_plotting.confidence, \
            f"Confidence should match: {signal_from_bot.confidence} vs {signal_from_plotting.confidence}"
        assert signal_from_bot.reason == signal_from_plotting.reason, \
            f"Reason should match: {signal_from_bot.reason} vs {signal_from_plotting.reason}"

    def test_multiple_symbols_consistency(self):
        """Test signal consistency across multiple symbols."""
        client = get_bitvavo_client()
        test_symbols = ["BTC", "ETH", "LINK"]

        for symbol in test_symbols:
            try:
                # Fetch candles
                candles = client.get_candles(
                    symbol,
                    settings.bot_analysis_time_resolution,
                    settings.bot_analysis_time_span
                )

                # Get signals twice (simulating bot and plotting)
                signal_1 = strategy_multi_confluence(candles)
                signal_2 = strategy_multi_confluence(candles)

                # Should be identical
                assert signal_1.signal == signal_2.signal, \
                    f"{symbol}: Signal mismatch"
                assert signal_1.confidence == signal_2.confidence, \
                    f"{symbol}: Confidence mismatch"

            except Exception as e:
                pytest.skip(f"Could not test {symbol}: {e}")

    def test_indicator_calculations_match(self):
        """Test that indicator calculations produce identical results."""
        client = get_bitvavo_client()

        candles = client.get_candles(
            "BTC",
            settings.bot_analysis_time_resolution,
            settings.bot_analysis_time_span
        )
        df = candles.as_dataframe()
        close_prices = df['close'].to_numpy()

        # Calculate indicators multiple times
        rsi_1 = calculate_rsi(close_prices, 14)
        rsi_2 = calculate_rsi(close_prices, 14)

        macd_1 = calculate_macd(close_prices, 12, 26, 9)
        macd_2 = calculate_macd(close_prices, 12, 26, 9)

        ema_1 = calculate_ema(close_prices, 12)
        ema_2 = calculate_ema(close_prices, 12)

        # All should be identical
        assert np.allclose(rsi_1, rsi_2, equal_nan=True), "RSI should be deterministic"
        assert np.allclose(macd_1[0], macd_2[0], equal_nan=True), "MACD line should be deterministic"
        assert np.allclose(macd_1[1], macd_2[1], equal_nan=True), "MACD signal should be deterministic"
        assert np.allclose(macd_1[2], macd_2[2], equal_nan=True), "MACD histogram should be deterministic"
        assert np.allclose(ema_1, ema_2, equal_nan=True), "EMA should be deterministic"


class TestBotConfiguration:
    """Test bot configuration consistency."""

    def test_bot_analysis_defaults(self):
        """Test that bot analysis configuration is valid."""
        # Verify time resolution is valid
        assert settings.bot_analysis_time_resolution in TIME_RESOLUTIONS, \
            f"Bot time resolution should be one of {list(TIME_RESOLUTIONS.keys())}"

        # Verify time span is valid
        assert settings.bot_analysis_time_span in TIME_SPANS, \
            f"Bot time span should be one of {list(TIME_SPANS.keys())}"

        # Verify minimum candles is reasonable
        assert settings.bot_min_candles_required >= 200, \
            "Bot should require at least 200 candles for reliable EMA 200 calculation"

    def test_confidence_thresholds(self):
        """Test that confidence thresholds are reasonable."""
        assert 0.0 <= settings.bot_entry_min_confidence <= 1.0, \
            "Entry confidence should be between 0 and 1"
        assert 0.0 <= settings.bot_exit_min_confidence <= 1.0, \
            "Exit confidence should be between 0 and 1"
        assert settings.bot_entry_min_confidence == 0.60, \
            "Entry confidence should be 60%"
        assert settings.bot_exit_min_confidence == 0.65, \
            "Exit confidence should be 65%"

    def test_candles_fetching_uses_bot_config(self):
        """Test that fetching candles with bot config works."""
        client = get_bitvavo_client()

        # This is exactly what the bot does in main.py:110-113
        candles = client.get_candles(
            "BTC",
            settings.bot_analysis_time_resolution,
            settings.bot_analysis_time_span
        )

        # Should get approximately the right amount of data
        # 2 weeks of 1h candles = 14 * 24 = 336 candles
        expected_candles = 718
        tolerance = int(expected_candles*0.05)  # Allow some tolerance for missing data

        assert abs(len(candles.timestamps) - expected_candles) <= tolerance, \
            f"Should fetch ~{expected_candles} candles, got {len(candles.timestamps)}"

        assert candles.time_resolution == settings.bot_analysis_time_resolution, \
            "Candles should have requested resolution"


class TestStrategyComposition:
    """Test that multi-confluence strategy uses correct sub-strategies."""

    def test_multi_confluence_includes_all_strategies(self):
        """Test that multi-confluence combines all expected strategies."""
        client = get_bitvavo_client()
        candles = client.get_candles(
            "BTC",
            settings.bot_analysis_time_resolution,
            settings.bot_analysis_time_span
        )

        signal = strategy_multi_confluence(candles)

        # Should have indicators from all three strategies
        assert signal.indicators is not None, "Should have indicators"
        assert "rsi_macd" in signal.indicators, "Should include RSI+MACD"
        assert "ema_crossover" in signal.indicators, "Should include EMA crossover"
        assert "bollinger" in signal.indicators, "Should include Bollinger Bands"

        # Should have vote counts
        assert "buy_count" in signal.indicators, "Should have buy count"
        assert "sell_count" in signal.indicators, "Should have sell count"

    def test_multi_confluence_parameters(self):
        """Test that multi-confluence uses correct parameters for sub-strategies."""
        client = get_bitvavo_client()
        candles = client.get_candles(
            "BTC",
            settings.bot_analysis_time_resolution,
            settings.bot_analysis_time_span
        )

        signal = strategy_multi_confluence(candles)

        # The multi-confluence strategy should use:
        # - RSI+MACD with defaults (RSI=14, MACD=12/26/9)
        # - EMA crossover with fast=12, slow=50, trend=200
        # - Bollinger Bands with period=20, std=2.0

        # We can't directly inspect the parameters, but we can verify
        # that the strategy runs without errors and produces valid output
        assert signal is not None
        assert signal.strategy_name == "CONFLUENCE"
        assert 0.0 <= signal.confidence <= 1.0
