import logging
from pathlib import Path

from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWidgets import QWidget

from coinbot import APP_TITLE
from coinbot import LOG_TIME_FORMAT, LOG_MSG_FORMAT, DEFAULT_LOG_LEVEL
from coinbot.frontend.controller import CoinbotController
from coinbot.frontend.logging import QTLogHandler
from coinbot.frontend.overview import CoinbotOverviewWidget
from coinbot.frontend.plots import CoinbotPlotWidget
from coinbot.frontend.symbols import CoinbotSymbolsWidget
from coinbot.backend.macd_bot import macd_stateless_trading_bot


class CoinbotMainWidget(QWidget):
    """ The CoinbotMainWidget implements the main widget that loads its ui from an .ui file where all objects and
    fields are declared. """

    def __init__(self, parent: QMainWindow):
        super(CoinbotMainWidget, self).__init__(parent=parent)

        self.overview_widget = None
        self.symbols_widget = None
        self.price_widget = None
        self._log_handler = None

        self.build_ui()
        self.connect_signals_to_slots()

    @property
    def controller(self) -> CoinbotController:
        return self.parent().controller

    def build_ui(self):
        file_dir = Path(__file__).parent.parent
        ui_path = str((file_dir / 'resources/ui/main.ui').resolve())
        uic.loadUi(ui_path, self)

        # Connect logging to ui
        logger = logging.getLogger()
        self._log_handler = QTLogHandler(self.logs_textbox, LOG_MSG_FORMAT, LOG_TIME_FORMAT)
        logger.addHandler(self._log_handler)
        self.logs_level_selector.setCurrentIndex(DEFAULT_LOG_LEVEL // 10 - 1)

        # Add an overview widget
        self.overview_widget = CoinbotOverviewWidget(self)
        self.overview_layout.addWidget(self.overview_widget)

        # Add a symbols table widget
        self.symbols_widget = CoinbotSymbolsWidget(self)
        self.symbols_layout.addWidget(self.symbols_widget)

        # Add a plot widget
        self.price_widget = CoinbotPlotWidget(self)
        self.price_layout.addWidget(self.price_widget)

    def connect_signals_to_slots(self):
        self.logs_level_selector.currentIndexChanged.connect(self._log_handler.update_log_level)
        self.price_symbol_selector.currentIndexChanged.connect(self.controller.update_mpl_view)
        self.price_resolution_selector.currentIndexChanged.connect(self.controller.update_mpl_view)
        self.price_period_selector.currentIndexChanged.connect(self.controller.update_mpl_view)
        self.start_bot_button.clicked.connect(macd_stateless_trading_bot)
        pass


class CoinbotView(QMainWindow):
    """ This class implements the main view (window) of the application. The controller gets orders from the view,
    interacts with the data, and updates the view. QT needs a main window, which can embed a (main) widget. """

    def __init__(self, controller: CoinbotController):
        super(CoinbotView, self).__init__(parent=None)
        self.controller = controller
        self.main_widget = CoinbotMainWidget(parent=self)
        self.setCentralWidget(self.main_widget)
        self.setWindowTitle(APP_TITLE)
        self.move(QApplication.desktop().screen().rect().center() - self.centralWidget().rect().center())
