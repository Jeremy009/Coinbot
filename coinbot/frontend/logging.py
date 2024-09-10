import logging

from PyQt5.QtCore import QThread
from PyQt5.QtWidgets import QApplication, QTextBrowser


class QTLogHandler(logging.Handler):
    """ This class implements a logging handler that takes care of displaying log messages in a QTextBrowser
    widget so that log messages may be redirected into a PyQt GUI. """

    def __init__(self, redirect_widget: QTextBrowser, msg_format: str, time_format: str):
        """ Initializes the handler. Needs a reference to a QPlainTextEdit widget to which to actually  write the logs,
        and a format template for the log message, and for the timestamp. """
        super(QTLogHandler, self).__init__()
        self.logger = logging.getLogger()

        self.setFormatter(logging.Formatter(msg_format, time_format))
        self.setLevel(self.logger.getEffectiveLevel())

        self.widget = redirect_widget
        self.widget.setReadOnly(True)

        self.log_level = self.logger.getEffectiveLevel()
        self.records = []
        self.levels = []

        self.logger.addHandler(self)

    def emit(self, record):
        """ Overloaded method from the logging.Handler class that gets called when a log message is emitted. Formats
        the message, and saves the formatted message and log level before calling a method that actually writes
        the message in the QTextBrowser. """
        msg = self.format(record)
        if record.levelno < 20:
            msg = "<font color=\"gray\">{}</font>".format(msg)
        elif 20 <= record.levelno < 30:
            msg = "<font color=\"black\">{}</font>".format(msg)
        elif 30 <= record.levelno < 40:
            msg = "<font color=\"orange\">{}</font>".format(msg)
        else:
            msg = "<font color=\"red\">{}</font>".format(msg)
        msg = msg.replace("\n", "<br>--- ")
        self.records.append(msg)
        self.levels.append(record.levelno)
        self.set_text()

    def set_text(self):
        """ Sets the log messages as formatted text in the QTextBrowser if and only if the log level of the message
        is equal or larger that the currently selected log level. """
        if QApplication.instance().thread() == QThread.currentThread():
            self.widget.clear()
            for level, record in zip(self.levels, self.records):
                if level >= self.log_level:
                    self.widget.append(record)

    def update_log_level(self, selected_ind: int):
        """ Updates the current log level, the level up to which logs are shown/printed. """
        self.log_level = (selected_ind + 1) * 10
        self.logger.setLevel(self.log_level)
        self.set_text()
