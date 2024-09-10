import logging
import sys
import time
from pathlib import Path

from PyQt5 import QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QSplashScreen, QProgressBar

from coinbot import LOG_MSG_FORMAT, LOG_TIME_FORMAT, DEFAULT_LOG_LEVEL, BITVAVO
from coinbot.backend.clients import BitvavoClient
from coinbot.frontend.controller import CoinbotController
from coinbot.frontend.stylesheet import STYLE_SHEET
from coinbot.frontend.view import CoinbotView

if __name__ == "__main__":
    # Setup logging to the console and logging to the log.txt file
    logger = logging.getLogger()
    logger.setLevel(DEFAULT_LOG_LEVEL)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter(LOG_MSG_FORMAT, LOG_TIME_FORMAT))
    logger.addHandler(stream_handler)

    # Get some graphics
    file_dir = Path(__file__).parent
    icon_path = str((file_dir / 'resources/graphics/icons/coinbot_icon.png').resolve())
    splashscreen_path = str((file_dir / 'resources/graphics/splashscreens/coinbot_splashscreen@0,5x.png').resolve())

    # Prepare the application
    QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication([])
    app.setWindowIcon(QIcon(icon_path)) if Path(icon_path).is_file() else None
    app.setStyleSheet(STYLE_SHEET)

    # Load the splash screen and the application
    pmp = QPixmap(splashscreen_path) if Path(splashscreen_path).is_file() else QPixmap()
    pmp.setDevicePixelRatio(2.0)
    splash = QSplashScreen(pmp, Qt.WindowStaysOnTopHint)
    splash.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
    splash.setEnabled(False)
    progressBar = QProgressBar(splash)
    progressBar.setMaximum(100)
    progressBar.setGeometry(64, 169, 370, 22)
    progressBar.setObjectName("SplashscreenProgressBar")
    progressBar.setValue(0)
    splash.show()


    def _update_splash(value, speed):
        for i in range(progressBar.value(), value):
            progressBar.setValue(i)
            app.processEvents()
            time.sleep(speed)


    _update_splash(0, speed=0.05)
    bitvavo_client = BitvavoClient(BITVAVO)
    _update_splash(10, speed=0.05)
    coinbot_controller = CoinbotController(bitvavo_client)
    _update_splash(15, speed=0.05)
    coinbot_view = CoinbotView(controller=coinbot_controller)
    _update_splash(20, speed=0.05)
    coinbot_controller.main_view = coinbot_view.main_widget
    _update_splash(30, speed=0.05)
    coinbot_controller.configure_main_view()
    _update_splash(40, speed=0.05)
    coinbot_controller.update_main_view()
    _update_splash(50, speed=0.21)
    coinbot_controller.start_update_loop()
    _update_splash(100, speed=0.21)

    splash.hide()
    coinbot_view.show()
    sys.exit(app.exec())
