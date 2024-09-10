import logging
from typing import Any

import numpy as np
from PyQt5.QtCore import *
from PyQt5.QtCore import QTimer

from coinbot import TIME_RESOLUTIONS, TIME_SPANS
from coinbot.backend.clients import BitvavoClient
from coinbot.frontend.threading import SeparateThreadWorker


class CoinbotController:
    def __init__(self, exchange_client: BitvavoClient, update_frequency: int = 30000):
        self._main_view = None
        self.exchange_client = exchange_client
        self._update_frequency = update_frequency
        self._update_timer = QTimer()
        self._update_frequency = update_frequency
        self._symbols_table_widget = None
        self._threadpool = QThreadPool.globalInstance()

    # Getters and setters
    @property
    def main_view(self) -> Any:
        return self._main_view

    @main_view.setter
    def main_view(self, main_view: Any):
        self._main_view = main_view

    # Update UI
    def configure_main_view(self):
        all_symbols = self.exchange_client.get_available_symbols()
        all_symbols.sort()

        for os in all_symbols:
            self.main_view.price_symbol_selector.addItem(os, os)
            self.main_view.price_symbol_selector.setCurrentIndex(0)

        for tr in TIME_RESOLUTIONS:
            self.main_view.price_resolution_selector.addItem(tr, tr)
            self.main_view.price_resolution_selector.setCurrentIndex(0)

        for ts in TIME_SPANS:
            self.main_view.price_period_selector.addItem(ts, ts)
            self.main_view.price_period_selector.setCurrentIndex(0)

    def start_update_loop(self):
        self._update_timer.timeout.connect(self.update_main_view)
        self._update_timer.start(self._update_frequency)

    def update_main_view(self):
        self.update_overview_view()
        self.update_symbols_view()
        self.update_mpl_view()

    def update_overview_view(self):
        logging.info(f"Updating overview. {self.exchange_client.get_remaining_limit()} API calls remaining")

        def _get_data(client):
            return client.get_available_funds(), \
                client.get_total_wallet_balance(), \
                client.get_total_deposited(), \
                client.get_total_withdrawn(), \
                client.get_total_gains()

        worker = SeparateThreadWorker(fn=_get_data, client=self.exchange_client)
        worker.signals.result.connect(lambda d: self.main_view.overview_widget.set_data(*d))
        worker.signals.error.connect(lambda e: logger.error("There was an error in the overview get_data thread. "
                                                            "The error was:\n{}".format(e[1])))
        self._threadpool.start(worker)

    def update_symbols_view(self):
        logging.info(f"Updating symbols. {self.exchange_client.get_remaining_limit()} API calls remaining")

        def _get_data(client):
            data = []
            owned_symbols = client.get_owned_symbols()
            for symbol in owned_symbols:
                if symbol == "EUR":
                    continue
                price = client.get_symbol_price(symbol)
                amount = client.get_symbol_owned_amount(symbol)
                value = price * amount
                change = client.get_symbol_24h_percentual_change(symbol)
                data.append([symbol, price, amount, value, change])
            return data

        worker = SeparateThreadWorker(fn=_get_data, client=self.exchange_client)
        worker.signals.result.connect(lambda d: self.main_view.symbols_widget.set_data(d))
        worker.signals.error.connect(lambda e: logging.error("There was an error in the symbols get_data thread. "
                                                             "The error was:\n{}".format(e[1])))
        self._threadpool.start(worker)

    def update_mpl_view(self):
        logging.info(f"Updating plots. {self.exchange_client.get_remaining_limit()} API calls remaining")
        self.main_view.price_widget.set_loading_screen()

        symbol = self.main_view.price_symbol_selector.currentData()
        time_resolution = self.main_view.price_resolution_selector.currentData()
        time_span = self.main_view.price_period_selector.currentData()

        if symbol is None or time_resolution is None or time_span is None:
            return

        def _get_data(client):
            candles = client.get_candles(symbol, time_resolution, time_span)
            times = np.array(candles.timestamps)
            prices = (np.array(candles.high_positions) +
                      np.array(candles.low_positions) +
                      np.array(candles.close_positions)) / 3.0
            return times, prices

        worker = SeparateThreadWorker(fn=_get_data, client=self.exchange_client)
        worker.signals.result.connect(lambda d: self.main_view.price_widget.set_data(*d))
        worker.signals.error.connect(lambda d: self.main_view.price_widget.set_error_screen())
        worker.signals.error.connect(lambda e: logging.error("There was an error in the symbols get_data thread. "
                                                             "The error was:\n{}".format(e[1])))
        self._threadpool.start(worker)
