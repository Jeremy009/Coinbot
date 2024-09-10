import datetime
import logging
import math
import time
from pathlib import Path
from typing import Tuple

import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm

from coinbot import LOG_MSG_FORMAT, LOG_TIME_FORMAT, DEFAULT_LOG_LEVEL, BITVAVO
from coinbot.backend.clients import BitvavoClient
from coinbot.backend.indicators import macd_indicator
from coinbot.backend.signals import macd_signal, TradebotAction
from coinbot.frontend.plots import plot_macd_analysis

# Set up logging
logger = logging.getLogger()
logger.setLevel(DEFAULT_LOG_LEVEL)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter(LOG_MSG_FORMAT, LOG_TIME_FORMAT))
logger.addHandler(stream_handler)


def get_promising_symbols(exchange_client: BitvavoClient, volume_limit: float, macd_params: Tuple[str, int, int, int]):
    """ This function will do a batch analysis of all symbols that can currently be exchanged on the client and will
    return a list with promising symbols.

    A symbol is promising if:
    - It's past 24h growth was positive
    - Its pas 34 h volume was larger that the specified threshold
    - Its MACD signal is 'BUY'

    """
    # Determine, for all symbols tradeable on the exchange, whether they are promising or not
    interesting_symbols = {}

    for symbol in tqdm(exchange_client.get_available_symbols(), "Analysing exchange", leave=False, disable=False):
        # Compute the 24 hours growth in price
        price_24h_growth = exchange_client.get_symbol_24h_percentual_change(symbol)
        if price_24h_growth <= 0.0:
            logger.debug(f"{symbol} not promising because 24h growth = {price_24h_growth:,.2f}%")
            continue

        # Compute the 24h volume
        volume_24_h = exchange_client.get_symbol_24h_volume(symbol)
        if volume_24_h < volume_limit:
            logger.debug(f"{symbol} not promising because the past 24h volume was {int(volume_24_h)} (<{volume_limit})")
            continue

        # Compute MACD
        candles = exchange_client.get_candles(symbol, macd_params[0], "1m")
        if len(candles.timestamps) != 90:
            logger.debug(f"{symbol} not promising because there were missing {macd_params[0]} candles the past month")
            continue
        macd_candles = macd_indicator(candles, macd_params[1], macd_params[2], macd_params[3])
        macd_ind = macd_signal(macd_candles)
        macd_strength = (macd_candles["macd_line"] - macd_candles["macd_signal"]).tail(1).item()
        if macd_ind != TradebotAction.BUY:
            logger.debug(f"{symbol} not promising because the MACD indicator is {macd_ind}")
            continue

        # Save metrics
        logger.debug(f"{symbol} saved as a promising symbol")
        interesting_symbols[symbol] = {
            "price_24h_growth": price_24h_growth,
            "volume_24h": volume_24_h,
            "volume_24h_magnitude": math.floor(math.log(volume_24_h, 10)),
            "macd_ind": macd_ind,
            "macd_val": macd_strength,
        }

    return interesting_symbols


def select_best_symbols(interesting_symbols: dict, num_symbols_to_select: int):
    """ This function determines what symbols are the most promising by sorting the promising symbols first by order
    of magnitude of the trade volume of the past 24h and then by the gains of the past 24h. """
    intr_s = interesting_symbols
    data = [(s, intr_s[s]["volume_24h_magnitude"], intr_s[s]["price_24h_growth"], intr_s[s]["volume_24h_magnitude"])
            for s in intr_s.keys()]
    data = sorted(data, key=lambda x: (x[1], x[2]))
    data.reverse()
    data = data[:num_symbols_to_select]

    for d in data:
        logger.debug(f"{d[0]} was selected for trading based on 24h volume {int(d[3])} and 24h gains {d[2]:,.2f}%")

    return [d[0] for d in data]


def live_buy(exchange_client: BitvavoClient, symbol: str, amount_in_euro: float, taker_fee_in_percent: float):
    """ This function places a BUY market order on the exchange. The function receives the amount to buy in euro,
    converts that amount to coins at the current exchange rate, and takes into account the maker fee.

    Arg:
        exchange_client: The trade client
        symbol: The symbol to buy
        amount_in_euro: How much to buy (in euro)

    returns:
        success: Bool whether the buy succeeded or not

    """
    response = exchange_client.buy(symbol, amount_in_euro)
    if "error" in response.keys():
        logger.error("Failed to buy {} because {}".format(symbol, response["error"].lower()))
        return False
    else:
        logger.info("Bought {} {} for {} EUR at a rate of {} EUR/{} (fee: {} {})".format(
            response["filledAmount"],
            response["market"].replace("-EUR", ""),
            np.round(float(response["filledAmountQuote"]), 2),
            np.round(float(response["filledAmountQuote"]) / float(response["filledAmount"]), 2),
            response["market"].replace("-EUR", ""),
            response["feePaid"],
            response["feeCurrency"],
        ))
        return True


def live_sell(exchange_client: BitvavoClient, symbol: str):
    """ This function places a SELL market order on the exchange. The function receives the symbol to sell and will
    simply dump all of the owned symbol at the market price.

    Arg:
        exchange_client: The trade client
        symbol: The symbol to sell

    returns:
        success: Bool whether the sell succeeded or not

    """
    amount_in_coins = exchange_client.get_symbol_owned_amount(symbol)
    response = exchange_client.sell(symbol, amount_in_coins)
    if "error" in response.keys():
        logger.error("Failed to sell {} because {}".format(symbol, response["error"].lower()))
        return False
    else:
        logger.info("Sold {} {} for {} EUR at a rate of {} EUR/{} (fee: {} {})".format(
            response["filledAmount"],
            response["market"].replace("-EUR", ""),
            np.round(float(response["filledAmountQuote"]), 2),
            np.round(float(response["filledAmountQuote"]) / float(response["filledAmount"]), 2),
            response["market"].replace("-EUR", ""),
            response["feePaid"],
            response["feeCurrency"],
        ))
        return True


def open_new_positions(exchange_client: BitvavoClient, volume_limit: float, macd_params: Tuple,
                       num_desired_positions: int, taker_fee_in_percent: float):
    """ This function opens new positions if need be. """
    # Check the current situation and keep a little funds on the side to handle fluctuations when entering positions
    num_open_pos = len(exchange_client.get_owned_symbols())
    num_pos_to_open = num_desired_positions - num_open_pos
    tradeable_funds = exchange_client.get_available_funds() * 0.975
    minimal_funds_per_symbol = 5.1

    # Check if there is a need to open new position(s) and if the necessary funds to open new positions are there
    if num_open_pos < num_desired_positions and tradeable_funds > minimal_funds_per_symbol * num_pos_to_open:
        # Determine which symbols are trade-worthy
        additional_pos = num_desired_positions - num_open_pos
        logger.info(f"{num_open_pos} open positions. Try to open {additional_pos} more positions")
        interesting_symbols = get_promising_symbols(exchange_client, volume_limit, macd_params)
        selected_symbols = select_best_symbols(interesting_symbols, additional_pos)
        logger.info(f"{len(selected_symbols)} symbols selected for trade: {selected_symbols}")

        # Determine how much to invest in each symbol
        funds_per_symbol = np.floor(tradeable_funds / additional_pos)
        logger.info(f"{tradeable_funds:,.2f} EUR available. Investing {funds_per_symbol:,.2f} in each symbol")

        # Buy the symbol
        for ss in selected_symbols:
            live_buy(exchange_client, ss, funds_per_symbol, taker_fee_in_percent)

    # Do nothing if not enough funds are available to buy more coins
    elif num_open_pos < num_desired_positions and tradeable_funds <= minimal_funds_per_symbol * num_pos_to_open:
        logger.warning(f"Currently there is only {tradeable_funds:,.2f} EUR available for trading, which is too "
                       f"little for opening {num_desired_positions} new positions")

    # Do nothing is there are already enough open positions
    else:
        logger.info(f"{num_open_pos}/{num_desired_positions} open positions. Not considering opening more positions")


def analyse_existing_positions(exchange_client: BitvavoClient, macd_params: Tuple):
    """ This function analyses all existing positions and decides whether to keep the position open or close the
    position, based on MACD analysis. """
    for os in exchange_client.get_owned_symbols():
        candles = exchange_client.get_candles(os, macd_params[0], "1m")
        macd_candles = macd_indicator(candles, macd_params[1], macd_params[2], macd_params[3])
        macd_ind = macd_signal(macd_candles)
        if macd_ind == TradebotAction.SELL:
            live_sell(exchange_client, os)
            logger.info(f"{os} dumped based on MACD: "
                        f"Fast EMA = {np.round(macd_candles.tail(1)['ema_fast'].item(), 2)}, "
                        f"Slow EMA = {np.round(macd_candles.tail(1)['ema_slow'].item(), 2)}, "
                        f"MACD Line = {np.round(macd_candles.tail(1)['macd_line'].item(), 2)}, "
                        f"MACD Signal = {np.round(macd_candles.tail(1)['macd_signal'].item(), 2)}  "
                        )
        else:
            logger.info(f"{os} bought/kept based on MACD: "
                        f"Fast EMA = {np.round(macd_candles.tail(1)['ema_fast'].item(), 2)}, "
                        f"Slow EMA = {np.round(macd_candles.tail(1)['ema_slow'].item(), 2)}, "
                        f"MACD Line = {np.round(macd_candles.tail(1)['macd_line'].item(), 2)}, "
                        f"MACD Signal = {np.round(macd_candles.tail(1)['macd_signal'].item(), 2)}  "
                        )

        save_dir = Path("/Users/jeremylombaerts/Library/Mobile Documents/com~apple~CloudDocs/Python/Coin"
                        "bot/data/live logs")
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        plot_macd_analysis(
            candles=candles,
            macd_candles=macd_candles,
            save_path=save_dir.joinpath(os + " " + timestamp + " " + str(macd_ind).split(".")[-1] + ".png")
        )
        plt.cla()
        plt.clf()
        plt.close()


def macd_stateless_trading_bot():
    # Manual constants
    num_desired_positions = 4
    volume_limit = 250000
    macd_timeresolution = "8h"
    macd_short_period = 12
    macd_long_period = 39
    macd_signal_period = 9
    taker_fee = 0.25
    timeout = 120

    # Automatic constants
    macd_params = (macd_timeresolution, macd_short_period, macd_long_period, macd_signal_period)
    client = BitvavoClient(BITVAVO)

    # Start the event loop
    logger.info(f"Start the bot's event loop in LIVE mode")
    while True:
        # Keep track of iteration time
        iteration_start_time = datetime.datetime.now()

        # Actual trading logic
        analyse_existing_positions(client, macd_params)
        open_new_positions(client, volume_limit, macd_params, num_desired_positions, taker_fee)

        # Wait until end of cooldown
        it_t = (datetime.datetime.now() - iteration_start_time).seconds
        rem_t = timeout * 60 - it_t
        if rem_t > 0:
            logger.info(f"Iteration completed in {it_t} s. Now waiting for {rem_t} s until next iteration.")
            logger.info(f" -------------------------------------------------------------------------------------------"
                        f"----------")
            time.sleep(rem_t)


if __name__ == "__main__":
    macd_stateless_trading_bot()
