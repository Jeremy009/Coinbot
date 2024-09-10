from pathlib import Path

from PyQt5 import uic
from PyQt5.QtWidgets import QWidget

from coinbot import RED, GREEN


class CoinbotOverviewWidget(QWidget):
    """ This widget is a basic QWidget and represents an 'overview' that summarizes the main financial data relevant
     for an automatic trader. """

    def __init__(self, parent: QWidget):
        """ Initialize a CoinbotOverviewWidget by calling an ui builder. """
        super(CoinbotOverviewWidget, self).__init__(parent=parent)
        self.build_ui()

    def build_ui(self):
        """ Builds the ui by loading it from a resource file. """
        file_dir = Path(__file__).parent.parent
        ui_path = str((file_dir / 'resources/ui/overview.ui').resolve())
        uic.loadUi(ui_path, self)

    def set_data(self, credits_euro: float, wallet: float, deposited: float, withdrawn: float, gains: float):
        """ Sets and formats the data to the widget, """
        ft = "{:.2f} €"
        self.credits_label.setText(ft.format(credits_euro))
        self.wallet_label.setText(ft.format(wallet))
        self.deposited_label.setText(ft.format(deposited))
        self.withdrawn_label.setText(ft.format(withdrawn))

        if gains <= 0.0:
            self.gains_label.setText("{:.2f} €".format(gains))
            self.gains_label.setStyleSheet("QLabel {color: rgb" + str(RED) + "}")
        else:
            self.gains_label.setText("+{:.2f} €".format(gains))
            self.gains_label.setStyleSheet("QLabel {color: rgb" + str(GREEN) + "}")
