import functools
import logging
import math
from typing import *
from tqdm import tqdm

from coinbot import *
from coinbot.backend.candles import OHLCVCandles
from coinbot.backend.exceptions import CoinbotUnexpectedValueError, CoinbotExceededNumAPICallsError

logger = logging.getLogger()


def limit_api_calls(func):
    """ This function implements the 'limit_api_calls' decorator. This decorator/function checks that there are
    sufficient remaining API calls remaining before attempting to make additional calls to the exchange API. This
    ensures that the current API key does not get blacklisted. """

    @functools.wraps(func)
    def check_remaining_api_calls_wrapper(*args, **kwargs):
        if args[0].get_remaining_limit() < 100:
            raise CoinbotExceededNumAPICallsError("There are only 50 API calls remaining in this timewindow and the "
                                                  "request was preventively rejected. Wait one minute and try again.")
        return func(*args, **kwargs)

    return check_remaining_api_calls_wrapper


class BitvavoClient:
    """ This class implements the interface to the Bitvavo exchange. """

    def __init__(self, credentials: Bitvavo):
        """ Initialise the exchange manager with the credentials containing an API key. """
        super().__init__()
        self._bitvavo = credentials
        self.available_symbols = self.get_available_symbols()

    def get_remaining_limit(self) -> int:
        """ Returns how many API calls are still allowed to be made (max 1000 calls per minute). """
        return self._bitvavo.getRemainingLimit()

    @limit_api_calls
    def buy(self, symbol, amount_in_euro):
        """ Place a BUY market order on the exchange. """
        response = self._bitvavo.placeOrder(symbol+"-EUR", 'buy', 'market', {'amountQuote': str(amount_in_euro)})
        return response

    @limit_api_calls
    def sell(self, symbol, amount_in_coins):
        """ Place a SELL market order on the exchange. """
        response = self._bitvavo.placeOrder(symbol+"-EUR", 'sell', 'market', {'amount': amount_in_coins})
        return response

    @limit_api_calls
    def panic(self):
        """ Place a SELL market order for each and every owned symbol on the exchange. """
        for owned_symbol in self.get_owned_symbols():
            amount_in_coins = self.get_symbol_owned_amount(owned_symbol)
            self.sell(owned_symbol, amount_in_coins)

    @limit_api_calls
    def get_available_symbols(self) -> List[str]:
        """ Returns the list of all symbols available on the exchange. """
        available_symbols = [m["market"].split("-")[0] for m in self._bitvavo.markets({})]
        available_symbols.extend(["EUR"])
        unique_markets = list(set(available_symbols))
        unique_markets.sort()

        return unique_markets

    @limit_api_calls
    def get_total_deposited(self) -> float:
        """ Return how much money has been deposited into the account in total. """
        total_deposit = 0.0
        for d in self._bitvavo.depositHistory({}):
            total_deposit += float(d["amount"]) - float(d["fee"])
        return total_deposit

    @limit_api_calls
    def get_total_withdrawn(self) -> float:
        """ Returns how much money was withdrawn from the account in total. """
        total_withdrawn = 0.0
        for w in self._bitvavo.withdrawalHistory({}):
            total_withdrawn += float(w["amount"]) - float(w["fee"])
        return total_withdrawn

    @limit_api_calls
    def get_total_gains(self) -> float:
        """ Returns the total net gains made in euro over all time. """
        return self.get_total_wallet_balance() + self.get_total_withdrawn() - self.get_total_deposited()

    @limit_api_calls
    def get_available_funds(self) -> float:
        """ Returns the funds available for withdrawal of buying. """
        return self.get_symbol_owned_amount("EUR")

    @limit_api_calls
    def get_open_positions(self) -> float:
        """ Returns all owned symbols with an open position. """
        open_positions = []
        for b in self._bitvavo.balance({}):
            symbol = b["symbol"]
            if symbol != "EUR" and b["available"] > 0.0:
                open_positions.append((symbol, b["available"]))

        return open_positions

    @limit_api_calls
    def get_open_orders(self) -> float:
        """ Returns all owned symbols with an open position. """
        open_orders = []
        for b in self._bitvavo.balance({}):
            symbol = b["symbol"]
            if symbol != "EUR" and b["inOrder"] > 0.0:
                open_orders.append((symbol, b["available"]))

        return open_orders

    @limit_api_calls
    def get_total_wallet_balance(self) -> float:
        """ Returns the net worth of the account as the sum of all funds, symbols, and open orders at the current
        exchange rate. """
        # Funds and symbols
        total_balance = 0.0
        for b in self._bitvavo.balance({}):
            symbol = b["symbol"]
            if symbol == "EUR":
                total_balance += float(b["available"])
            else:
                total_balance += float(b["available"]) * self.get_symbol_price(symbol)

        # Value locked in orders
        orders = BITVAVO.ordersOpen(options={})
        for order in orders:
            total_balance += float(self.get_symbol_price(order["market"].split("-")[0])) * float(order["amount"])

        return total_balance

    @limit_api_calls
    def get_owned_symbols(self) -> List[str]:
        """ Get a list with all owned funds and symbols. """
        owned_symbols = []
        for b in self._bitvavo.balance({}):
            symbol = b["symbol"]
            available = float(b["available"])
            in_order = float(b["inOrder"])
            if symbol != "EUR" and (available > 0.0 or in_order > 0.0):
                owned_symbols.append(symbol)
        return owned_symbols

    @limit_api_calls
    def get_symbol_price(self, symbol: str) -> float:
        """ Get the current market price in euro for a given symbol. """
        if symbol not in self.available_symbols:
            raise CoinbotUnexpectedValueError(f"Could not retrieve price because {symbol} does not exist.")
        if symbol == "EUR":
            return 1.0
        return float(self._bitvavo.tickerPrice({"market": symbol.upper() + "-EUR"})["price"])

    @limit_api_calls
    def get_symbols_prices(self, symbols: List[str]) -> List[float]:
        """ Get the current market prices in euro for each symbol in a list of symbols. """
        ticker_book = self._bitvavo.tickerPrice({})
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
        """ Get the owned amount of the specified symbol. """
        if symbol not in self.available_symbols:
            raise CoinbotUnexpectedValueError(f"Could not retrieve amount of coins because {symbol} does not exist.")
        for b in self._bitvavo.balance({}):
            if b["symbol"].lower() == symbol.lower():
                return float(b["available"])
        return 0.0

    @limit_api_calls
    def get_symbol_24h_percentual_change(self, symbol: str) -> float:
        """ Gets the percentual change in value of the selected symbol over the last 24 hours. """
        if symbol not in self.available_symbols:
            raise CoinbotUnexpectedValueError(f"Could not retrieve symbol 24h change because {symbol} does not exist.")
        if symbol == "EUR":
            return 0.0
        try:
            ticker_24 = self._bitvavo.ticker24h({"market": symbol.upper() + "-EUR"})
            open_price = float(ticker_24["open"])
            last_price = float(ticker_24["last"])

            return (last_price - open_price) / open_price * 100
        except TypeError:
            return 0.0

    @limit_api_calls
    def get_symbol_24h_volume(self, symbol: str) -> float:
        """ Gets the volume in euro of the past 24 hours.  """
        if symbol not in self.available_symbols:
            raise CoinbotUnexpectedValueError(f"Could not retrieve symbol 24h volume because {symbol} does not exist.")
        if symbol == "EUR":
            return 0.0
        ticker_24 = self._bitvavo.ticker24h({"market": symbol.upper() + "-EUR"})
        volume = float(ticker_24["volumeQuote"]) if ticker_24["volumeQuote"] is not None else 0.0

        return volume

    @limit_api_calls
    def get_candles(self, symbol: str, time_resolution: str, time_span: str, verbose: bool = False) -> OHLCVCandles:
        # TODO: Loading all data every time is not very efficient. Rather subscribe to the candleupdateevent.
        """ Get historic candles data from the exchange and make a candles object out of it. """
        # Check input
        if time_resolution not in TIME_RESOLUTIONS:
            raise CoinbotUnexpectedValueError("Time resolution should be one of {}".format(TIME_RESOLUTIONS.keys()))
        if time_span not in TIME_SPANS:
            raise CoinbotUnexpectedValueError("Time span should be one of {}".format(TIME_SPANS.keys()))
        if symbol not in self.available_symbols:
            raise CoinbotUnexpectedValueError(f"Could not retrieve candles because {symbol} does not exist.")

        # Determine how many candles are (maximally) needed to cover the requested span at the given resolution
        num_candles = int(math.ceil(TIME_SPANS[time_span] / TIME_RESOLUTIONS[time_resolution]))

        # Determine the begin and end bound of the timespan
        begin_timestamp = int(self._bitvavo.time()["time"])
        end_timestamp = int(begin_timestamp / 1000 - TIME_SPANS[time_span]) * 1000

        # Set up
        num_requests = int(math.ceil(num_candles / 1000))
        total_time_span = begin_timestamp - end_timestamp
        time_span_per_request = total_time_span // num_requests
        times, opens, highs, lows, closes, volumes = [], [], [], [], [], []

        # Request candles in several requests since Bitvavo refuses to return more than 1440 candles at once
        for request_nr in tqdm(range(num_requests), disable=not verbose, desc=f"Loading historical {symbol} candles"):
            start_timestamp = begin_timestamp - (request_nr + 1) * time_span_per_request
            end_timestamp = begin_timestamp - request_nr * time_span_per_request
            params = {"start": start_timestamp, "end": end_timestamp}
            candles = self._bitvavo.candles(symbol + "-EUR", time_resolution, params)

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
            order="newer-to-older")
