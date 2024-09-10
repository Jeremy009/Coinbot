from PyQt5 import QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import QTableWidget, QAbstractItemView, QWidget
from PyQt5.QtWidgets import QTableWidgetItem

from coinbot import RED, GREEN


class CoinbotSymbolsWidget(QTableWidget):
    """ This widget subclasses a QTableWIdget and represents a 'symbols' table that summarizes all owned symbols.
    The table is read-only and data can be set using the set_data method. """

    def __init__(self, parent: QWidget):
        """ Initialize a CoinbotSymbolsWidget by configuring the parent class mostly. """
        super(CoinbotSymbolsWidget, self).__init__(0, 5, parent=parent)
        super().setEditTriggers(QAbstractItemView.NoEditTriggers)
        super().verticalHeader().hide()
        super().setShowGrid(False)
        self.font_size = 11
        self.build_ui()

    def build_ui(self):
        """ Creates the table header. """
        for col_nr, header_title in enumerate(["Symbol ", "Price ", "Amount ", "Value ", "24h "]):
            super().setHorizontalHeaderItem(col_nr, self._get_bold_item(header_title))

    def set_data(self, data):
        """ Sets the data to the table view. Data must be a list of lists where each sublist consists of 5 entries
        where those entries correspond to [symbol, price, amount, value, 24h change]. This method also takes care of
        formatting the data to/for the view. """
        self.clearContents()
        self.setRowCount(len(data))

        data.sort(key=lambda d: d[3])
        data.reverse()

        for row_nr, data_row in enumerate(data):
            # Column header
            super().setItem(row_nr, 0, self._get_bold_item(data_row[0]))
            # Price
            fmt = "{:.0f} €" if data_row[1] > 1000 else ("{:.2f} €" if data_row[1] > 0.01 else "{:.6f} €")
            super().setItem(row_nr, 1, self._get_regular_item(fmt.format(data_row[1])))
            # Amount
            super().setItem(row_nr, 2, self._get_regular_item("{:.2f}".format(data_row[2])))
            # Value
            super().setItem(row_nr, 3, self._get_regular_item("{:.2f} €".format(data_row[3])))
            # 24h change
            if data_row[4] < 0.0:
                item = self._get_regular_item("{:.2f}%".format(data_row[4]))
                item.setForeground(QBrush(QColor(*RED)))
                super().setItem(row_nr, 4, item)
            else:
                item = self._get_regular_item("+{:.2f}%".format(data_row[4]))
                item.setForeground(QBrush(QColor(*GREEN)))
                super().setItem(row_nr, 4, item)

        super().resizeColumnsToContents()

    def get_item(self, string: str, bold: bool) -> QTableWidgetItem:
        """ Get a formatted QTableWidgetItem. """
        font = QtGui.QFont()
        font.setBold(bold)
        font.setPointSize(self.font_size)
        header_item = QTableWidgetItem(string)
        header_item.setFont(font)
        header_item.setTextAlignment(Qt.AlignVCenter)

        return header_item

    def _get_bold_item(self, string):
        """ Get a QTableWidgetItem with bold font weight. """
        return self.get_item(string, True)

    def _get_regular_item(self, string):
        """ Get a QTableWidgetItem with regular font weight. """
        return self.get_item(string, False)
