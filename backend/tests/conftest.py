"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def mock_bitvavo_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock Bitvavo client for testing."""
    from coinbot_backend.services import bitvavo_client

    class MockBitvavoClient:
        """Mock Bitvavo client for testing."""

        def __init__(self) -> None:
            self.available_symbols = ["BTC", "ETH", "EUR"]

        def get_remaining_limit(self) -> int:
            return 1000

        def get_available_symbols(self) -> list[str]:
            return self.available_symbols

        def get_available_funds(self) -> float:
            return 1000.0

        def get_total_wallet_balance(self) -> float:
            return 1500.0

        def get_total_deposited(self) -> float:
            return 1000.0

        def get_total_withdrawn(self) -> float:
            return 0.0

        def get_total_gains(self) -> float:
            return 500.0

        def get_symbol_price(self, symbol: str) -> float:
            prices = {"BTC": 40000.0, "ETH": 2500.0, "EUR": 1.0}
            return prices.get(symbol, 0.0)

        def get_symbol_owned_amount(self, symbol: str) -> float:
            amounts = {"EUR": 1000.0, "BTC": 0.01}
            return amounts.get(symbol, 0.0)

        def get_symbol_24h_percentual_change(self, symbol: str) -> float:
            return 5.0

        def get_symbol_24h_volume(self, symbol: str) -> float:
            return 1000000.0

    mock_client = MockBitvavoClient()
    monkeypatch.setattr(bitvavo_client, "_bitvavo_client", mock_client)
