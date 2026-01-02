"""Unit tests for Bitvavo client dry-run mode."""

from coinbot_backend.services.bitvavo_client import BitvavoClient


class TestBitvavoClientDryRunMode:
    """Test dry-run mode functionality without real API calls."""

    def test_dry_run_initialization(self):
        """Test that dry-run mode initializes with starting balance."""
        client = BitvavoClient(dry_run=True)

        # Should have EUR balance set
        assert "EUR" in client._dry_run_balances
        assert client._dry_run_balances["EUR"] > 0
        assert client._dry_run_order_counter == 0
        assert client.dry_run is True

    def test_dry_run_get_available_funds(self):
        """Test getting available EUR in dry-run mode."""
        client = BitvavoClient(dry_run=True)
        initial_balance = client._dry_run_balances["EUR"]

        funds = client.get_available_funds()

        assert funds == initial_balance
        assert funds > 0

    def test_dry_run_get_total_deposited(self):
        """Test get_total_deposited returns initial balance in dry-run."""
        client = BitvavoClient(dry_run=True)
        initial_balance = client._dry_run_balances["EUR"]

        deposited = client.get_total_deposited()

        assert deposited == initial_balance

    def test_dry_run_get_total_withdrawn(self):
        """Test get_total_withdrawn returns 0 in dry-run mode."""
        client = BitvavoClient(dry_run=True)

        withdrawn = client.get_total_withdrawn()

        assert withdrawn == 0.0

    def test_dry_run_buy_order(self):
        """Test simulated buy order in dry-run mode."""
        client = BitvavoClient(dry_run=True)
        initial_eur = client._dry_run_balances["EUR"]

        # Buy some BTC
        result = client.buy("BTC", 100.0)

        # Should have order ID
        assert "orderId" in result
        assert result["orderId"].startswith("dry-run-")
        assert result["side"] == "buy"
        assert result["status"] == "filled"

        # EUR balance should decrease
        assert client._dry_run_balances["EUR"] < initial_eur
        assert client._dry_run_balances["EUR"] == initial_eur - 100.0

        # Should have BTC balance now
        assert "BTC" in client._dry_run_balances
        assert client._dry_run_balances["BTC"] > 0

    def test_dry_run_sell_order(self):
        """Test simulated sell order in dry-run mode."""
        client = BitvavoClient(dry_run=True)

        # First buy some BTC
        client.buy("BTC", 100.0)
        btc_amount = client._dry_run_balances["BTC"]
        eur_before_sell = client._dry_run_balances["EUR"]

        # Now sell it
        result = client.sell("BTC", btc_amount)

        # Should have order ID
        assert "orderId" in result
        assert result["orderId"].startswith("dry-run-")
        assert result["side"] == "sell"
        assert result["status"] == "filled"

        # BTC should be gone (or very close to 0)
        assert client._dry_run_balances.get("BTC", 0.0) < 0.0001

        # EUR balance should increase
        assert client._dry_run_balances["EUR"] > eur_before_sell

    def test_dry_run_insufficient_balance_buy(self):
        """Test buy order fails with insufficient EUR balance."""
        client = BitvavoClient(dry_run=True)
        initial_balance = client._dry_run_balances["EUR"]

        # Try to buy more than we have
        result = client.buy("BTC", initial_balance + 1000.0)

        # Should return error
        assert "error" in result
        assert "Insufficient EUR balance" in result["error"]

    def test_dry_run_insufficient_balance_sell(self):
        """Test sell order fails with insufficient coin balance."""
        client = BitvavoClient(dry_run=True)

        # Try to sell BTC we don't have
        result = client.sell("BTC", 10.0)

        # Should return error
        assert "error" in result
        assert "Insufficient BTC balance" in result["error"]

    def test_dry_run_buy_invalid_symbol(self):
        """Test buy order fails with invalid symbol."""
        client = BitvavoClient(dry_run=True)

        # Try to buy a symbol that doesn't exist
        result = client.buy("FAKECOIN", 100.0)

        # Should return error
        assert "error" in result
        assert "Unknown market FAKECOIN-EUR" in result["error"]

    def test_dry_run_sell_invalid_symbol(self):
        """Test sell order fails with invalid symbol."""
        client = BitvavoClient(dry_run=True)

        # Try to sell a symbol that doesn't exist
        result = client.sell("FAKECOIN", 10.0)

        # Should return error
        assert "error" in result
        assert "Unknown market FAKECOIN-EUR" in result["error"]

    def test_dry_run_get_owned_symbols(self):
        """Test getting owned symbols in dry-run mode."""
        client = BitvavoClient(dry_run=True)

        # Initially should be empty (EUR is excluded)
        owned = client.get_owned_symbols()
        assert owned == []

        # Buy some BTC and ETH
        client.buy("BTC", 100.0)
        client.buy("ETH", 50.0)

        # Should show both symbols
        owned = client.get_owned_symbols()
        assert "BTC" in owned
        assert "ETH" in owned
        assert "EUR" not in owned

    def test_dry_run_get_total_wallet_balance(self):
        """Test getting total wallet balance in dry-run mode."""
        client = BitvavoClient(dry_run=True)
        initial_balance = client._dry_run_balances["EUR"]

        # Initial balance should equal total (only EUR)
        total = client.get_total_wallet_balance()
        assert total == initial_balance

        # Buy some BTC (total should stay roughly the same minus fees)
        client.buy("BTC", 100.0)
        new_total = client.get_total_wallet_balance()

        # Total should be less than initial due to fees, but close
        assert new_total < initial_balance
        assert new_total > initial_balance * 0.99  # Within 1% (fee is 0.3%)

    def test_dry_run_multiple_orders_increment_counter(self):
        """Test that order counter increments with each order."""
        client = BitvavoClient(dry_run=True)

        assert client._dry_run_order_counter == 0

        # Place first order
        result1 = client.buy("BTC", 50.0)
        assert client._dry_run_order_counter == 1
        assert "dry-run-1" in result1["orderId"]

        # Place second order
        result2 = client.buy("ETH", 50.0)
        assert client._dry_run_order_counter == 2
        assert "dry-run-2" in result2["orderId"]

        # Place third order
        result3 = client.sell("BTC", client._dry_run_balances["BTC"])
        assert client._dry_run_order_counter == 3
        assert "dry-run-3" in result3["orderId"]


class TestBitvavoClientEURHandling:
    """Test special handling of EUR symbol."""

    def test_get_symbol_price_eur_returns_one(self):
        """Test that EUR price always returns 1.0."""
        client = BitvavoClient(dry_run=True)

        price = client.get_symbol_price("EUR")

        assert price == 1.0

    def test_get_symbols_prices_with_eur(self):
        """Test batch price fetch includes EUR as 1.0."""
        client = BitvavoClient(dry_run=True)

        prices = client.get_symbols_prices(["EUR", "BTC", "ETH"])

        # First should be EUR = 1.0
        assert prices[0] == 1.0
        # Others should be real prices
        assert prices[1] > 1.0  # BTC is expensive
        assert prices[2] > 1.0  # ETH is expensive

    def test_get_symbol_24h_change_eur_returns_zero(self):
        """Test that EUR 24h change always returns 0.0."""
        client = BitvavoClient(dry_run=True)

        change = client.get_symbol_24h_percentual_change("EUR")

        assert change == 0.0

    def test_get_symbol_24h_volume_eur_returns_zero(self):
        """Test that EUR 24h volume always returns 0.0."""
        client = BitvavoClient(dry_run=True)

        volume = client.get_symbol_24h_volume("EUR")

        assert volume == 0.0

    def test_get_symbol_owned_amount_eur(self):
        """Test getting EUR amount in dry-run mode."""
        client = BitvavoClient(dry_run=True)
        initial_balance = client._dry_run_balances["EUR"]

        amount = client.get_symbol_owned_amount("EUR")

        assert amount == initial_balance
