"""Bitvavo exchange client wrapper."""

import functools
import logging
import math
from typing import Any, Callable, TypeVar

from python_bitvavo_api.bitvavo import Bitvavo
from tqdm import tqdm

from coinbot_backend.config import settings
from coinbot_backend.core.constants import TIME_RESOLUTIONS, TIME_SPANS
from coinbot_backend.core.exceptions import (
    CoinbotExceededNumAPICallsError,
    CoinbotUnexpectedValueError,
)
from coinbot_backend.models.candles import OHLCVCandles

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def limit_api_calls(func: F) -> F:
    """Decorator to check API rate limits before making calls."""

    @functools.wraps(func)
    def wrapper(self: "BitvavoClient", *args: Any, **kwargs: Any) -> Any:
        remaining = self.get_remaining_limit()
        if remaining < 100:
            raise CoinbotExceededNumAPICallsError(
                f"Only {remaining} API calls remaining. Request rejected to prevent blacklisting."
            )
        return func(self, *args, **kwargs)

    return wrapper  # type: ignore


class BitvavoClient:
    """Wrapper for the Bitvavo API client with rate limiting and error handling."""

    def __init__(self) -> None:
        """Initialize the Bitvavo client."""
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

    def get_remaining_limit(self) -> int:
        """Get remaining API calls allowed (max 1000 calls per minute)."""
        return self._client.getRemainingLimit()

    @limit_api_calls
    def buy(self, symbol: str, amount_in_euro: float) -> dict[str, Any]:
        """Place a BUY market order."""
        return self._client.placeOrder(
            symbol + "-EUR", "buy", "market", {"amountQuote": str(amount_in_euro)}
        )

    @limit_api_calls
    def sell(self, symbol: str, amount_in_coins: float) -> dict[str, Any]:
        """Place a SELL market order."""
        return self._client.placeOrder(
            symbol + "-EUR", "sell", "market", {"amount": str(amount_in_coins)}
        )

    @limit_api_calls
    def panic(self) -> None:
        """Place a SELL market order for each and every owned symbol on the exchange."""
        for owned_symbol in self.get_owned_symbols():
            amount_in_coins = self.get_symbol_owned_amount(owned_symbol)
            self.sell(owned_symbol, amount_in_coins)

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
        total = 0.0
        for deposit in self._client.depositHistory({}):
            total += float(deposit["amount"]) - float(deposit["fee"])
        return total

    @limit_api_calls
    def get_total_withdrawn(self) -> float:
        """Get total amount withdrawn from the account."""
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
        return self.get_symbol_owned_amount("EUR")

    @limit_api_calls
    def get_open_positions(self) -> list[tuple[str, float]]:
        """Get all owned symbols with an open position."""
        open_positions = []
        for balance in self._client.balance({}):
            symbol = balance["symbol"]
            if symbol != "EUR" and float(balance["available"]) > 0.0:
                open_positions.append((symbol, float(balance["available"])))
        return open_positions

    @limit_api_calls
    def get_open_orders(self) -> list[tuple[str, float]]:
        """Get all owned symbols with open orders."""
        open_orders = []
        for balance in self._client.balance({}):
            symbol = balance["symbol"]
            if symbol != "EUR" and float(balance["inOrder"]) > 0.0:
                open_orders.append((symbol, float(balance["inOrder"])))
        return open_orders

    @limit_api_calls
    def get_total_wallet_balance(self) -> float:
        """Get total portfolio value in EUR."""
        total = 0.0
        for balance in self._client.balance({}):
            symbol = balance["symbol"]
            if symbol == "EUR":
                total += float(balance["available"])
            else:
                total += float(balance["available"]) * self.get_symbol_price(symbol)

        # Add value locked in orders
        orders = self._client.ordersOpen(options={})
        for order in orders:
            symbol = order["market"].split("-")[0]
            total += float(self.get_symbol_price(symbol)) * float(order["amount"])

        return total

    @limit_api_calls
    def get_owned_symbols(self) -> list[str]:
        """Get list of owned symbols (excluding EUR)."""
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


# Singleton instance
_bitvavo_client: BitvavoClient | None = None


def get_bitvavo_client() -> BitvavoClient:
    """Get or create the Bitvavo client singleton."""
    global _bitvavo_client
    if _bitvavo_client is None:
        _bitvavo_client = BitvavoClient()
    return _bitvavo_client
