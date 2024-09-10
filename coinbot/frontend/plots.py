from typing import List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QWidget
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg

from coinbot import GRAY, RED, GREEN
from coinbot.backend.candles import OHLCVCandles


class CoinbotPlotWidget(QWidget):
    """ The CoinbotPlotWidget class can be used to render a simple Matplotlib x vs. y plot in a qt widget with
     appropriate background coloring. Data can be set and reset easily through the set_data method. """

    def __init__(self, parent: QWidget = None):
        """ Makes the QWidget with an empty placeholder figure in it. """
        super(CoinbotPlotWidget, self).__init__(parent)

        self.matplotlib_figure = plt.figure("CoinbotPlotWidgetFigure")
        self.matplotlib_figure.patch.set_facecolor(np.array(GRAY) / 255)

        self.canvas = FigureCanvasQTAgg(self.matplotlib_figure)
        self.canvas.draw()

        plt.gca().axis("off")
        plt.tight_layout()

        self._layout = QVBoxLayout()
        self._layout.addWidget(self.canvas)
        self.setLayout(self._layout)

    def set_loading_screen(self):
        self.set_text_to_plot("Loading", 0.5)

    def set_error_screen(self):
        self.set_text_to_plot("Graph could not be loaded", 0.325)

    def set_text_to_plot(self, text, x):
        plt.clf()
        plt.text(x, 0.5, text, fontsize=7)
        plt.gca().axis("off")
        plt.gcf().set_tight_layout(True)
        plt.xlim(0, 1)
        plt.ylim(0, 1)

        self.canvas.draw()

    def set_data(self, times: List[int], prices: List[float]):
        """ (Re)sets the data to the figure. """
        try:
            plt.clf()

            max_price = np.max(prices)
            min_price = np.min(prices)
            diff = max_price - min_price
            plt.plot(times, [max_price for _ in prices], "k--", linewidth=0.25)
            plt.plot(times, [min_price for _ in prices], "k--", linewidth=0.25)

            if prices[0] < prices[-1]:
                plt.plot(times, prices, color=np.array(GREEN) / 255, linewidth=0.99)
                plt.scatter([times[0], times[-1]], [prices[0], prices[-1]], marker=".", color=np.array(GREEN) / 255, s=2)
            else:
                plt.plot(times, prices, color=np.array(RED) / 255, linewidth=0.99)
                plt.scatter([times[0], times[-1]], [prices[0], prices[-1]], marker=".", color=np.array(RED) / 255, s=2)

            fmt = "{:.0f} €" if min_price > 1000 else("{:.2f} €" if min_price > 0.01 else "{:.6f} €")
            plt.text(times[0], max_price + 0.02 * diff, fmt.format(max_price), fontsize=7)
            plt.text(times[0], min_price - 0.075 * diff, fmt.format(min_price), fontsize=7)

            plt.gca().axis("off")
            plt.gcf().set_tight_layout(True)

            self.canvas.draw()

        except:
            self.set_error_screen()


def plot_candles(candles: OHLCVCandles) -> None:
    """ Makes a Matplotlib figure with the candles on top and the trading volume on bottom. """
    # Convert the candles object to a Pandas dataframe
    prices = pd.DataFrame({'open': candles.opening_positions,
                           'close': candles.close_positions,
                           'high': candles.high_positions,
                           'low': candles.low_positions,
                           'volume': candles.volumes},
                          index=[i for i in range(candles.num_candles)])

    # Initialize the figure
    plt.figure("Candles")

    plt.subplot(211)
    plt.title("{} - {} days, {} - {} candles".format(candles.symbol, candles.timespan_in_days,
                                                        candles.time_resolution, candles.num_candles))
    candle_width = .5
    wick_width = .075

    # define up and down prices
    up = prices[prices.close >= prices.open]
    down = prices[prices.close < prices.open]

    # plot up prices
    plt.bar(up.index, up.close - up.open, candle_width, bottom=up.open, color='green')
    plt.bar(up.index, up.high - up.close, wick_width, bottom=up.close, color='green')
    plt.bar(up.index, up.low - up.open, wick_width, bottom=up.open, color='green')

    # plot down prices
    plt.bar(down.index, down.close - down.open, candle_width, bottom=down.open, color='red')
    plt.bar(down.index, down.high - down.open, wick_width, bottom=down.open, color='red')
    plt.bar(down.index, down.low - down.close, wick_width, bottom=down.close, color='red')
    plt.gca().get_xaxis().set_visible(False)

    # Volume
    plt.subplot(212)
    plt.title("Volume")
    plt.bar(down.index, down.volume, candle_width, bottom=0, color='red')
    plt.bar(up.index, up.volume, candle_width, bottom=0, color='green')

    # rotate x-axis tick labels
    mod = candles.num_candles // 20
    label_loc = [i for i, _ in enumerate(candles.timelabels) if i % mod == 0]
    label_val = [l for i, l in enumerate(candles.timelabels) if i % mod == 0]

    plt.gca().set_xticks(label_loc)
    plt.gca().set_xticklabels(label_val)
    plt.xticks(rotation=90)


def plot_macd_analysis(candles: OHLCVCandles, macd_candles: pd.DataFrame, save_path=None, title=None) -> None:
    # Initialize the figure
    plt.figure("MACD analysis", figsize=(11.69, 8.27))

    plt.subplot(211)
    plt.title("{} - {} days, {} - {} candles".format(candles.symbol, candles.timespan_in_days,
                                                     candles.time_resolution, candles.num_candles))
    candle_width = .5
    wick_width = .075

    # define up and down prices
    up = macd_candles[macd_candles.close >= macd_candles.open]
    down = macd_candles[macd_candles.close < macd_candles.open]

    # plot up prices
    plt.bar(up.index, up.close - up.open, candle_width, bottom=up.open, color='green')
    plt.bar(up.index, up.high - up.close, wick_width, bottom=up.close, color='green')
    plt.bar(up.index, up.low - up.open, wick_width, bottom=up.open, color='green')

    # plot down prices
    plt.bar(down.index, down.close - down.open, candle_width, bottom=down.open, color='red')
    plt.bar(down.index, down.high - down.open, wick_width, bottom=down.open, color='red')
    plt.bar(down.index, down.low - down.close, wick_width, bottom=down.close, color='red')
    plt.gca().get_xaxis().set_visible(False)

    # Plot fast EMA
    plt.plot(macd_candles.index, macd_candles["ema_fast"], color="c", label="12-period EMA")
    plt.plot(macd_candles.index, macd_candles["ema_slow"], color="b", label="26-period EMA")

    # MACD
    plt.subplot(212)
    plt.title("MACD") if title is None else plt.title(title)
    plt.plot(macd_candles.index, [0 for _ in macd_candles.index], "k")
    plt.plot(macd_candles.index, macd_candles["macd_line"], color="b")
    plt.plot(macd_candles.index, macd_candles["macd_signal"], color="r")
    macd_hist_pos = [h if h >= 0 else 0 for h in macd_candles["macd_line"] - macd_candles["macd_signal"]]
    macd_hist_neg = [h if h < 0 else 0 for h in macd_candles["macd_line"] - macd_candles["macd_signal"]]
    plt.bar(macd_candles.index, macd_hist_pos, color="green")
    plt.bar(macd_candles.index, macd_hist_neg, color="red")

    # Rotated x-axis tick labels
    mod = candles.num_candles // 20
    label_loc = [i for i, _ in enumerate(candles.timelabels) if i % mod == 0]
    label_val = [l for i, l in enumerate(candles.timelabels) if i % mod == 0]

    plt.gca().set_xticks(label_loc)
    plt.gca().set_xticklabels(label_val)
    plt.xticks(rotation=90)
    plt.tight_layout()

    if save_path is not None:
        plt.savefig(save_path)
