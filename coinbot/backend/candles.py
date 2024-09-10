from datetime import datetime
from typing import *

import numpy as np
import pandas as pd

from coinbot import *
from coinbot.backend.exceptions import CoinbotUnexpectedValueError
import pickle
from pathlib import Path


class OHLCVCandles:
    """ OHLCVCandles is a class that holds financial candles data in a convenient and easily readable and handelable
     manner. """

    def __init__(self, symbol: str, timestamps: List, time_resolution: str, opening_positions: List,
                 high_positions: List, low_positions: List, close_positions: List, volumes: List,
                 order: str = "older-to-newer"):
        """ Initialise a candles object  for a given symbol. """
        self.symbol = symbol
        self.timestamps = timestamps
        self.time_resolution = time_resolution
        self.opening_positions = opening_positions
        self.high_positions = high_positions
        self.low_positions = low_positions
        self.close_positions = close_positions
        self.volumes = volumes
        self.order = order

        self.num_candles = len(timestamps)
        self.timelabels = [datetime.fromtimestamp(t / 1000.0) for t in self.timestamps]

        if len(self.timestamps) > 0:
            self.timespan = (np.max(self.timestamps) - np.min(timestamps)) / 1000.0 + TIME_RESOLUTIONS[time_resolution]
        else:
            self.timespan = 0.0

        self.timespan_in_seconds = np.round(self.timespan)
        self.timespan_in_minutes = np.round(self.timespan / 60, 2)
        self.timespan_in_hours = np.round(self.timespan / (60 * 60), 2)
        self.timespan_in_days = np.round(self.timespan / (60 * 60 * 24), 2)

        self._dataframe_object = None

        assert len(timestamps) == len(opening_positions) == len(close_positions) == len(high_positions)
        assert len(timestamps) == len(low_positions) == len(volumes)

        if self.order not in ["older-to-newer", "newer-to-older"]:
            raise CoinbotUnexpectedValueError("Order should be either older-to-newer or newer-to-older")
        if self.order == "newer-to-older":
            self.timestamps.reverse()
            self.opening_positions.reverse()
            self.high_positions.reverse()
            self.low_positions.reverse()
            self.close_positions.reverse()
            self.volumes.reverse()
            self.timelabels.reverse()
            
    def as_dataframe(self) -> pd.DataFrame:
        """ Returns a Pandas dataframe with colums 'timestamp', 'open', 'high', 'low', 'close', 'volume' columns. """
        if self._dataframe_object is None:
            df = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = self.timestamps
            df["open"] = self.opening_positions
            df["high"] = self.high_positions
            df["low"] = self.low_positions
            df["close"] = self.close_positions
            df["volume"] = self.volumes
            self._dataframe_object = df

        return self._dataframe_object
