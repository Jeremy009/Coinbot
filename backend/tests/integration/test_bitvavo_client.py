"""Integration tests for BitvavoClient."""

import math
import time

import pytest

from coinbot_backend.core.constants import TIME_RESOLUTIONS, TIME_SPANS
from coinbot_backend.core.exceptions import CoinbotUnexpectedValueError
from coinbot_backend.models.candles import OHLCVCandles
from coinbot_backend.services.bitvavo_client import BitvavoClient


@pytest.fixture(scope="module")
def bitvavo_client() -> BitvavoClient:
    """Create a shared Bitvavo client for all tests in this module."""
    return BitvavoClient()


class TestBitvavoClient:
    """Integration tests for the Bitvavo client."""

    def test_limit_api_calls_decorator(self, bitvavo_client: BitvavoClient, monkeypatch):
        """Test that the API rate limiter waits and retries when calls are low."""
        # Track calls
        call_count = {"get_remaining": 0, "sleep": 0}

        def mock_get_remaining_limit():
            call_count["get_remaining"] += 1
            # First call: low remaining (< 100), second call after sleep: reset to high value
            return 50 if call_count["get_remaining"] == 1 else 950

        def mock_sleep(seconds: float):
            call_count["sleep"] += 1
            assert seconds == 60  # Should wait exactly 60 seconds

        # Apply mocks
        monkeypatch.setattr(bitvavo_client, "get_remaining_limit", mock_get_remaining_limit)
        monkeypatch.setattr(time, "sleep", mock_sleep)

        # Mock the actual API call to avoid making real requests
        def mock_deposit_history(options):
            return []  # Empty history is fine for this test

        monkeypatch.setattr(bitvavo_client._client, "depositHistory", mock_deposit_history)

        # Call a decorated method - should trigger wait and retry
        result = bitvavo_client.get_total_deposited()

        # Verify behavior
        assert call_count["get_remaining"] == 2  # Called twice: before and after sleep
        assert call_count["sleep"] == 1  # Slept once for 60 seconds
        assert result == 0.0  # Empty deposit history returns 0

    def test_get_total_deposited(self, bitvavo_client: BitvavoClient):
        """Test getting total deposited amount."""
        total_deposited = bitvavo_client.get_total_deposited()
        print(f"Total deposited: {total_deposited}")
        assert isinstance(total_deposited, float)
        assert total_deposited > 0.0

    def test_get_total_withdrawn(self, bitvavo_client: BitvavoClient):
        """Test getting total withdrawn amount."""
        total_withdrawn = bitvavo_client.get_total_withdrawn()
        print(f"Total withdrawn: {total_withdrawn}")
        assert isinstance(total_withdrawn, float)
        assert total_withdrawn > 0.0

    def test_get_total_gains(self, bitvavo_client: BitvavoClient):
        """Test getting total gains."""
        total_gains = bitvavo_client.get_total_gains()
        print(f"Total gains: {total_gains}")
        assert isinstance(total_gains, float)

    def test_get_available_funds(self, bitvavo_client: BitvavoClient):
        """Test getting available funds."""
        available_funds = bitvavo_client.get_available_funds()
        print(f"Total available funds: {available_funds}")
        assert isinstance(available_funds, float)
        assert available_funds >= 0.0

    def test_get_total_wallet_balance(self, bitvavo_client: BitvavoClient):
        """Test getting total wallet balance."""
        total_wallet_balance = bitvavo_client.get_total_wallet_balance()
        print(f"Total wallet balance: {total_wallet_balance}")
        assert isinstance(total_wallet_balance, float)
        assert total_wallet_balance > 0.0

    def test_get_available_symbols(self, bitvavo_client: BitvavoClient):
        """Test getting available symbols."""
        available_symbols = bitvavo_client.get_available_symbols()
        print(f"Available symbols: {available_symbols}")
        assert isinstance(available_symbols, list)
        assert len(available_symbols) > 0
        for symbol in bitvavo_client.get_owned_symbols():
            assert symbol in available_symbols

    def test_get_owned_symbols(self, bitvavo_client: BitvavoClient):
        """Test getting owned symbols."""
        owned_symbols = bitvavo_client.get_owned_symbols()
        print(f"Owned symbols: {owned_symbols}")
        assert isinstance(owned_symbols, list)
        assert len(owned_symbols) > 0

    def test_get_symbol_price(self, bitvavo_client: BitvavoClient):
        """Test getting symbol prices."""
        for owned_symbol in bitvavo_client.get_owned_symbols():
            price = bitvavo_client.get_symbol_price(owned_symbol)
            print(f"Current {owned_symbol} price: {price}")
            assert isinstance(price, float)
            assert price > 0.0

        for not_owned_symbol in ["LINK", "UNI"]:
            price = bitvavo_client.get_symbol_price(not_owned_symbol)
            print(f"Current {not_owned_symbol} price: {price}")
            assert isinstance(price, float)
            assert price > 0.0

        for garbage_symbol in ["LKUJWDA", "MIQVZGH", "QLXIHEDS"]:
            with pytest.raises(CoinbotUnexpectedValueError):
                bitvavo_client.get_symbol_price(garbage_symbol)

    def test_get_symbols_prices(self, bitvavo_client: BitvavoClient):
        """Test getting multiple symbol prices at once."""
        owned_symbols = bitvavo_client.get_owned_symbols()
        prices = bitvavo_client.get_symbols_prices(owned_symbols)
        for i, symbol in enumerate(owned_symbols):
            price = prices[i]
            other_price = bitvavo_client.get_symbol_price(symbol)
            assert abs(price - other_price) < 0.01 * price, f"{symbol}: {price} vs. {other_price}"

        not_owned_symbols = ["LINK", "UNI", "DOT"]
        prices = bitvavo_client.get_symbols_prices(not_owned_symbols)
        for i, symbol in enumerate(not_owned_symbols):
            price = prices[i]
            other_price = bitvavo_client.get_symbol_price(symbol)
            assert abs(price - other_price) < 0.01 * price, f"{symbol}: {price} vs. {other_price}"

        garbage_symbols = ["LKUJWDA", "MIQVZGH", "QLXIHEDS"]
        with pytest.raises(CoinbotUnexpectedValueError):
            bitvavo_client.get_symbols_prices(garbage_symbols)

    def test_get_symbol_amount(self, bitvavo_client: BitvavoClient):
        """Test getting owned amount of symbols."""
        for owned_symbol in bitvavo_client.get_owned_symbols():
            amount = bitvavo_client.get_symbol_owned_amount(owned_symbol)
            print(f"Current {owned_symbol} amount: {amount}")
            assert isinstance(amount, float)
            assert amount >= 0.0

        for not_owned_symbol in ["LINK", "UNI", "DOT"]:
            amount = bitvavo_client.get_symbol_owned_amount(not_owned_symbol)
            print(f"Current {not_owned_symbol} amount: {amount}")
            assert isinstance(amount, float)
            assert amount == 0.0

        for garbage_symbol in ["LKUJWDA", "MIQVZGH", "QLXIHEDS"]:
            with pytest.raises(CoinbotUnexpectedValueError):
                bitvavo_client.get_symbol_owned_amount(garbage_symbol)

    def test_get_symbol_24h_change(self, bitvavo_client: BitvavoClient):
        """Test getting 24h percentage change."""
        for owned_symbol in bitvavo_client.get_owned_symbols():
            percentual_change = bitvavo_client.get_symbol_24h_percentual_change(owned_symbol)
            print(f"Current {owned_symbol} change: {percentual_change}%")
            assert isinstance(percentual_change, float)

        for not_owned_symbol in ["LINK", "UNI", "DOT"]:
            percentual_change = bitvavo_client.get_symbol_24h_percentual_change(not_owned_symbol)
            print(f"Current {not_owned_symbol} change: {percentual_change}%")
            assert isinstance(percentual_change, float)

        for garbage_symbol in ["LKUJWDA", "MIQVZGH", "QLXIHEDS"]:
            with pytest.raises(CoinbotUnexpectedValueError):
                bitvavo_client.get_symbol_24h_percentual_change(garbage_symbol)

    def test_get_historic_candles(self, bitvavo_client: BitvavoClient):
        """Test getting historic candles data."""
        # Test invalid inputs
        with pytest.raises(CoinbotUnexpectedValueError):
            bitvavo_client.get_candles(symbol="Garbage", time_resolution="1m", time_span="1h")
        with pytest.raises(CoinbotUnexpectedValueError):
            bitvavo_client.get_candles(symbol="BTC", time_resolution="Garbage", time_span="1h")
        with pytest.raises(CoinbotUnexpectedValueError):
            bitvavo_client.get_candles(symbol="BTC", time_resolution="1m", time_span="Garbage")

        def _run_test(c: OHLCVCandles, time_res: str, time_spn: str):
            # Check correct type
            assert isinstance(c, OHLCVCandles)
            # Check number of candles does not exceed theoretical max number of candles (possibly missing candles)
            assert c.num_candles <= int(math.ceil(TIME_SPANS[time_spn] / TIME_RESOLUTIONS[time_res]))
            # Check actually spanned time is comparable to theoretically spanned time (max 6 missing begin/end candles)
            dt = TIME_SPANS[time_spn]
            assert dt - 6 * TIME_RESOLUTIONS[time_res] <= (c.timestamps[-1] - c.timestamps[0]) / 1000.0 <= dt
            # Check that the candles object computed its timespan correctly based on the first and last candles
            assert (c.timestamps[-1] - c.timestamps[0]) / 1000.0 + TIME_RESOLUTIONS[time_res] == c.timespan_in_seconds
            # Check that the timestamps are strictly increasing
            for i in range(len(c.timestamps) - 1):
                assert c.timestamps[i + 1] >= c.timestamps[i] + TIME_RESOLUTIONS[time_res] * 1000

        # Test a small number of candles (reduced from original test)
        time_resolution, time_span = "1h", "1d"
        cdls = bitvavo_client.get_candles("BTC", time_resolution=time_resolution, time_span=time_span)
        _run_test(cdls, time_resolution, time_span)

        time_resolution, time_span = "1h", "1w"
        cdls = bitvavo_client.get_candles("ETH", time_resolution=time_resolution, time_span=time_span)
        _run_test(cdls, time_resolution, time_span)

        # Test one larger dataset
        time_resolution, time_span = "1d", "1m"
        cdls = bitvavo_client.get_candles("BTC", time_resolution=time_resolution, time_span=time_span)
        _run_test(cdls, time_resolution, time_span)
