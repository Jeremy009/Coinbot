"""Bitvavo exchange client wrapper."""
import functools
import logging
import math
import time
from collections.abc import Callable
from typing import Any, TypeVar

from python_bitvavo_api.bitvavo import Bitvavo
from tqdm import tqdm

from coinbot_backend.config import settings
from coinbot_backend.core.constants import TIME_RESOLUTIONS, TIME_SPANS
from coinbot_backend.core.exceptions import CoinbotUnexpectedValueError
from coinbot_backend.models.candles import OHLCVCandles

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def limit_api_calls(func: F) -> F:
    """
    Decorator to check API rate limits before making calls.

    If remaining calls are low (< threshold), automatically waits for rate limit reset.
    Bitvavo rate limits: 1000 calls/minute, resets on rolling 1-minute window.
    If limit is exceeded, account is blocked for 1 minute.
    """

    @functools.wraps(func)
    def wrapper(self: "BitvavoClient", *args: Any, **kwargs: Any) -> Any:
        remaining = self.get_remaining_limit()

        # If we're running low on API calls, wait for the rate limit to reset
        if remaining < settings.bitvavo_rate_limit_threshold:
            logger.warning(
                f"Only {remaining} API calls remaining. "
                f"Waiting {settings.bitvavo_rate_limit_reset_seconds} seconds for rate limit reset..."
            )
            time.sleep(settings.bitvavo_rate_limit_reset_seconds)
            remaining = self.get_remaining_limit()
            logger.info(f"Rate limit reset. Now have {remaining} calls remaining.")

        return func(self, *args, **kwargs)

    return wrapper  # type: ignore


class BitvavoClient:
    """Wrapper for the Bitvavo API client with rate limiting and error handling."""

    def __init__(self, dry_run: bool = False) -> None:
        """
        Initialize the Bitvavo client.

        Args:
            dry_run: If True, simulates trades without placing real orders
        """
        self.dry_run = dry_run
        self._client = Bitvavo(
            {
                "RESTURL": settings.bitvavo_rest_url,
                "WSURL": settings.bitvavo_ws_url,
                "ACCESSWINDOW": settings.bitvavo_access_window,
                "DEBUGGING": False,
                "APIKEY": settings.bitvavo_api_key,
                "APISECRET": settings.bitvavo_api_secret,
            }
        )
        self.available_symbols = self.get_available_symbols()

        # Dry-run mode: simulated balances
        if self.dry_run:
            initial_balance = settings.bot_dry_run_initial_balance
            self._dry_run_balances: dict[str, float] = {"EUR": initial_balance}
            self._dry_run_order_counter = 0
            logger.info(f"DRY-RUN MODE ENABLED - Starting with €{initial_balance:.2f}")

    def get_remaining_limit(self) -> int:
        """Get remaining API calls allowed (max 1000 calls per minute)."""
        return self._client.getRemainingLimit()

    @limit_api_calls
    def buy(self, symbol: str, amount_in_euro: float) -> dict[str, Any]:
        """
        Place a BUY market order.

        In dry-run mode, simulates the order without hitting the exchange.
        """
        if self.dry_run:
            return self._simulate_buy_order(symbol, amount_in_euro)

        return self._client.placeOrder(
            symbol + "-EUR",
            "buy",
            "market",
            {"amountQuote": str(amount_in_euro)}
        )

    @limit_api_calls
    def sell(self, symbol: str, amount_in_coins: float) -> dict[str, Any]:
        """
        Place a SELL market order.

        In dry-run mode, simulates the order without hitting the exchange.
        """
        if self.dry_run:
            return self._simulate_sell_order(symbol, amount_in_coins)

        return self._client.placeOrder(
            symbol + "-EUR",
            "sell",
            "market",
            {"amount": str(amount_in_coins)}
        )

    @limit_api_calls
    def get_available_symbols(self) -> list[str]:
        """Get list of all symbols available on the exchange."""
        markets = self._client.markets({})
        symbols = [m["market"].split("-")[0] for m in markets]
        symbols.extend(["EUR"])
        unique_symbols = list(set(symbols))
        unique_symbols.sort()
        return unique_symbols

    @limit_api_calls
    def get_total_deposited(self) -> float:
        """Get total amount deposited into the account."""
        if self.dry_run:
            # In dry-run mode, return the initial balance as the "deposited" amount
            return settings.bot_dry_run_initial_balance

        total = 0.0
        for deposit in self._client.depositHistory({}):
            total += float(deposit["amount"]) - float(deposit["fee"])
        return total

    @limit_api_calls
    def get_total_withdrawn(self) -> float:
        """Get total amount withdrawn from the account."""
        if self.dry_run:
            # In dry-run mode, no withdrawals have been made
            return 0.0

        total = 0.0
        for withdrawal in self._client.withdrawalHistory({}):
            total += float(withdrawal["amount"]) - float(withdrawal["fee"])
        return total

    @limit_api_calls
    def get_total_gains(self) -> float:
        """Get total net gains (wallet + withdrawn - deposited)."""
        return self.get_total_wallet_balance() + self.get_total_withdrawn() - self.get_total_deposited()

    @limit_api_calls
    def get_available_funds(self) -> float:
        """Get available EUR funds."""
        if self.dry_run:
            return self._dry_run_balances.get("EUR", 0.0)
        return self.get_symbol_owned_amount("EUR")

    @limit_api_calls
    def get_total_wallet_balance(self) -> float:
        """Get total portfolio value in EUR."""
        if self.dry_run:
            # Calculate total value: EUR + all crypto positions valued at current prices
            total = self._dry_run_balances.get("EUR", 0.0)
            crypto_symbols = [s for s in self._dry_run_balances.keys() if s != "EUR"]
            if crypto_symbols:
                prices = self.get_symbols_prices(crypto_symbols)
                for symbol, price in zip(crypto_symbols, prices):
                    total += self._dry_run_balances[symbol] * price
            return total

        balances = self._client.balance({})

        # Separate EUR and crypto balances
        eur_balance = 0.0
        crypto_symbols = []
        crypto_amounts = {}

        for balance in balances:
            symbol = balance["symbol"]
            amount = float(balance["available"])
            if symbol == "EUR":
                eur_balance = amount
            elif amount > 0:
                crypto_symbols.append(symbol)
                crypto_amounts[symbol] = amount

        # Batch fetch prices for all crypto symbols
        total = eur_balance
        if crypto_symbols:
            prices = self.get_symbols_prices(crypto_symbols)
            for symbol, price in zip(crypto_symbols, prices):
                total += crypto_amounts[symbol] * price

        # Add value locked in orders
        orders = self._client.ordersOpen(options={})
        if orders:
            order_symbols = list(set(order["market"].split("-")[0] for order in orders))
            order_prices_dict = {}
            if order_symbols:
                order_prices = self.get_symbols_prices(order_symbols)
                order_prices_dict = dict(zip(order_symbols, order_prices))

            for order in orders:
                symbol = order["market"].split("-")[0]
                total += order_prices_dict.get(symbol, 0.0) * float(order["amount"])

        return total

    @limit_api_calls
    def get_owned_symbols(self) -> list[str]:
        """Get list of owned symbols (excluding EUR)."""
        if self.dry_run:
            return [s for s in self._dry_run_balances.keys() if s != "EUR" and self._dry_run_balances[s] > 0]

        owned = []
        for balance in self._client.balance({}):
            symbol = balance["symbol"]
            available = float(balance["available"])
            in_order = float(balance["inOrder"])
            if symbol != "EUR" and (available > 0.0 or in_order > 0.0):
                owned.append(symbol)
        return owned

    @limit_api_calls
    def get_symbol_price(self, symbol: str) -> float:
        """Get current market price for a symbol in EUR."""
        if symbol not in self.available_symbols:
            raise CoinbotUnexpectedValueError(f"Could not retrieve price because {symbol} does not exist.")
        if symbol == "EUR":
            return 1.0
        ticker = self._client.tickerPrice({"market": symbol.upper() + "-EUR"})
        return float(ticker["price"])

    @limit_api_calls
    def get_symbols_prices(self, symbols: list[str]) -> list[float]:
        """Get current market prices in EUR for multiple symbols."""
        ticker_book = self._client.tickerPrice({})
        prices = []
        for symbol in symbols:
            if symbol == "EUR":
                prices.append(1.0)
                continue
            if symbol not in self.available_symbols:
                raise CoinbotUnexpectedValueError(f"Could not retrieve price because {symbol} does not exist.")
            for ticker_data in ticker_book:
                if ticker_data["market"] == symbol.upper() + "-EUR":
                    prices.append(float(ticker_data["price"]))
                    break
        return prices

    @limit_api_calls
    def get_symbol_owned_amount(self, symbol: str) -> float:
        """Get owned amount of a specific symbol."""
        if symbol not in self.available_symbols:
            raise CoinbotUnexpectedValueError(
                f"Could not retrieve amount of coins because {symbol} does not exist."
            )

        if self.dry_run:
            return self._dry_run_balances.get(symbol, 0.0)

        for balance in self._client.balance({}):
            if balance["symbol"].lower() == symbol.lower():
                return float(balance["available"])
        return 0.0

    @limit_api_calls
    def get_symbol_24h_percentual_change(self, symbol: str) -> float:
        """Get 24h percentage price change for a symbol."""
        if symbol not in self.available_symbols:
            raise CoinbotUnexpectedValueError(
                f"Could not retrieve symbol 24h change because {symbol} does not exist."
            )
        if symbol == "EUR":
            return 0.0
        try:
            ticker = self._client.ticker24h({"market": symbol.upper() + "-EUR"})
            open_price = float(ticker["open"])
            last_price = float(ticker["last"])
            return (last_price - open_price) / open_price * 100
        except (TypeError, KeyError):
            return 0.0

    @limit_api_calls
    def get_symbol_24h_volume(self, symbol: str) -> float:
        """Get 24h trading volume in EUR for a symbol."""
        if symbol not in self.available_symbols:
            raise CoinbotUnexpectedValueError(
                f"Could not retrieve symbol 24h volume because {symbol} does not exist."
            )
        if symbol == "EUR":
            return 0.0
        ticker = self._client.ticker24h({"market": symbol.upper() + "-EUR"})
        volume = float(ticker["volumeQuote"]) if ticker["volumeQuote"] is not None else 0.0
        return volume

    @limit_api_calls
    def get_candles(
        self, symbol: str, time_resolution: str, time_span: str, verbose: bool = False
    ) -> OHLCVCandles:
        """
        Get historic candles data from the exchange and make a candles object out of it.

        Args:
            symbol: Trading symbol (e.g., "BTC", "ETH")
            time_resolution: Candle interval (e.g., "1m", "1h")
            time_span: Lookback period (e.g., "1d", "1w", "1m")
            verbose: Show progress bar if True

        Returns:
            OHLCVCandles object with historical data
        """
        # Check input
        if time_resolution not in TIME_RESOLUTIONS:
            raise CoinbotUnexpectedValueError(
                f"Time resolution should be one of {list(TIME_RESOLUTIONS.keys())}"
            )
        if time_span not in TIME_SPANS:
            raise CoinbotUnexpectedValueError(f"Time span should be one of {list(TIME_SPANS.keys())}")
        if symbol not in self.available_symbols:
            raise CoinbotUnexpectedValueError(f"Could not retrieve candles because {symbol} does not exist.")

        # Determine how many candles are needed to cover the requested span at the given resolution
        num_candles = int(math.ceil(TIME_SPANS[time_span] / TIME_RESOLUTIONS[time_resolution]))

        # Determine the begin and end bound of the timespan
        begin_timestamp = int(self._client.time()["time"])
        end_timestamp = int(begin_timestamp / 1000 - TIME_SPANS[time_span]) * 1000

        # Set up
        num_requests = int(math.ceil(num_candles / 1000))
        total_time_span = begin_timestamp - end_timestamp
        time_span_per_request = total_time_span // num_requests
        times, opens, highs, lows, closes, volumes = [], [], [], [], [], []

        # Request candles in several requests since Bitvavo refuses to return more than 1440 candles at once
        for request_nr in tqdm(
            range(num_requests), disable=not verbose, desc=f"Loading historical {symbol} candles"
        ):
            start_timestamp = begin_timestamp - (request_nr + 1) * time_span_per_request
            request_end_timestamp = begin_timestamp - request_nr * time_span_per_request
            params = {"start": start_timestamp, "end": request_end_timestamp}
            candles = self._client.candles(symbol + "-EUR", time_resolution, params)

            times.extend([float(c[0]) for c in candles])
            opens.extend([float(c[1]) for c in candles])
            highs.extend([float(c[2]) for c in candles])
            lows.extend([float(c[3]) for c in candles])
            closes.extend([float(c[4]) for c in candles])
            volumes.extend([float(c[5]) for c in candles])

        # Return result as a candles object
        return OHLCVCandles(
            symbol=symbol,
            time_resolution=time_resolution,
            timestamps=times,
            opening_positions=opens,
            high_positions=highs,
            low_positions=lows,
            close_positions=closes,
            volumes=volumes,
            order="newer-to-older",
        )

    # Dry-run simulation helpers
    def _simulate_buy_order(self, symbol: str, amount_in_euro: float) -> dict[str, Any]:
        """
        Simulate a buy order in dry-run mode.

        Uses Bitvavo's taker fee (default 0.25%) since market orders always take liquidity.
        Fee rate is configurable via BOT_DRY_RUN_FEE_RATE setting.
        """
        # Validate symbol exists
        if symbol not in self.available_symbols:
            return {"error": f"Unknown market {symbol}-EUR"}

        # Get current market price
        current_price = self.get_symbol_price(symbol)

        # Simulate Bitvavo taker fee (market orders)
        fee_rate = settings.bot_dry_run_fee_rate
        fee_amount = amount_in_euro * fee_rate
        amount_after_fee = amount_in_euro - fee_amount

        # Calculate how many coins we get
        coins_bought = amount_after_fee / current_price

        # Update simulated balances
        current_eur = self._dry_run_balances.get("EUR", 0.0)
        if current_eur < amount_in_euro:
            return {
                "error": f"Insufficient EUR balance. Have {current_eur:.2f}, need {amount_in_euro:.2f}"
            }

        self._dry_run_balances["EUR"] = current_eur - amount_in_euro
        self._dry_run_balances[symbol] = self._dry_run_balances.get(symbol, 0.0) + coins_bought

        # Generate order ID
        self._dry_run_order_counter += 1
        order_id = f"dry-run-{self._dry_run_order_counter}"

        logger.info(
            f"DRY-RUN BUY: {coins_bought:.8f} {symbol} @ €{current_price:.2f} "
            f"(cost: €{amount_in_euro:.2f}, fee: €{fee_amount:.4f})"
        )

        # Return response matching Bitvavo API format
        return {
            "orderId": order_id,
            "market": f"{symbol}-EUR",
            "created": int(time.time() * 1000),
            "side": "buy",
            "orderType": "market",
            "filledAmount": str(coins_bought),
            "filledAmountQuote": str(amount_after_fee),
            "feePaid": str(fee_amount),
            "feeCurrency": "EUR",
            "status": "filled",
        }

    def _simulate_sell_order(self, symbol: str, amount_in_coins: float) -> dict[str, Any]:
        """
        Simulate a sell order in dry-run mode.

        Uses Bitvavo's taker fee (default 0.25%) since market orders always take liquidity.
        Fee rate is configurable via BOT_DRY_RUN_FEE_RATE setting.
        """
        # Validate symbol exists
        if symbol not in self.available_symbols:
            return {"error": f"Unknown market {symbol}-EUR"}

        # Get current market price
        current_price = self.get_symbol_price(symbol)

        # Calculate EUR value
        eur_value = amount_in_coins * current_price

        # Simulate Bitvavo taker fee (market orders)
        fee_rate = settings.bot_dry_run_fee_rate
        fee_amount = eur_value * fee_rate
        eur_after_fee = eur_value - fee_amount

        # Check balance
        current_coins = self._dry_run_balances.get(symbol, 0.0)
        if current_coins < amount_in_coins:
            return {
                "error": f"Insufficient {symbol} balance. "
                         f"Have {current_coins:.8f}, need {amount_in_coins:.8f}"
            }

        # Update simulated balances
        self._dry_run_balances[symbol] = current_coins - amount_in_coins
        self._dry_run_balances["EUR"] = self._dry_run_balances.get("EUR", 0.0) + eur_after_fee

        # Clean up zero balances
        if self._dry_run_balances[symbol] == 0.0:
            del self._dry_run_balances[symbol]

        # Generate order ID
        self._dry_run_order_counter += 1
        order_id = f"dry-run-{self._dry_run_order_counter}"

        logger.info(
            f"DRY-RUN SELL: {amount_in_coins:.8f} {symbol} @ €{current_price:.2f} "
            f"(received: €{eur_after_fee:.2f}, fee: €{fee_amount:.4f})"
        )

        # Return response matching Bitvavo API format
        return {
            "orderId": order_id,
            "market": f"{symbol}-EUR",
            "created": int(time.time() * 1000),
            "side": "sell",
            "orderType": "market",
            "filledAmount": str(amount_in_coins),
            "filledAmountQuote": str(eur_value),
            "feePaid": str(fee_amount),
            "feeCurrency": "EUR",
            "status": "filled",
        }

    def restore_dry_run_balances_from_positions(self, positions: dict[str, Any]) -> None:
        """
        Restore dry-run balances from loaded positions.

        This is needed when the bot restarts - positions are persisted to S3,
        but dry-run balances are not. We need to sync them to prevent positions
        from being removed due to appearing "not owned".

        Args:
            positions: Dictionary of positions loaded from S3 (symbol -> position data)
        """
        if not self.dry_run:
            return

        logger.info("Restoring dry-run balances from loaded positions...")

        # Start with initial balance
        total_cost = 0.0

        # Add all position amounts to dry-run balances
        for symbol, position_data in positions.items():
            amount = position_data.get("amount", 0.0)
            cost = position_data.get("total_cost", 0.0)

            self._dry_run_balances[symbol] = amount
            total_cost += cost

            logger.info(f"  Restored {amount:.8f} {symbol} (cost: €{cost:.2f})")

        # Subtract total cost from EUR balance
        initial_eur = settings.bot_dry_run_initial_balance
        remaining_eur = initial_eur - total_cost

        if remaining_eur < 0:
            logger.warning(
                f"Total position cost (€{total_cost:.2f}) exceeds initial balance (€{initial_eur:.2f}). "
                f"Setting EUR balance to 0."
            )
            self._dry_run_balances["EUR"] = 0.0
        else:
            self._dry_run_balances["EUR"] = remaining_eur
            logger.info(f"  EUR balance: €{remaining_eur:.2f} (€{total_cost:.2f} allocated to positions)")

        logger.info(f"Dry-run balances restored: {len(positions)} position(s) loaded")


# Singleton instance
_bitvavo_client: BitvavoClient | None = None


def get_bitvavo_client() -> BitvavoClient:
    """Get or create the Bitvavo client singleton."""
    global _bitvavo_client
    if _bitvavo_client is None:
        _bitvavo_client = BitvavoClient(dry_run=settings.bot_dry_run)
    return _bitvavo_client
