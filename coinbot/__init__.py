from python_bitvavo_api.bitvavo import Bitvavo

BITVAVO = Bitvavo({
    'RESTURL': 'https://api.bitvavo.com/v2',
    'WSURL': 'wss://ws.BITVAVO.com/v2/',
    'ACCESSWINDOW': 10000,
    'DEBUGGING': False,
    'APIKEY': '<your Bitvavo api key>',
    'APISECRET': '<your Bitvavo api secret>',
})

APP_NAME = "Coinbot"
APP_VERSION = "1.0"
APP_TITLE = APP_NAME + " V" + APP_VERSION
APP_SUBTITLE = "Trade the future!"

LOG_MSG_FORMAT = "[%(asctime)s - %(levelname)s] %(message)s"
LOG_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_LOG_LEVEL = 20

GREEN = (69, 168, 121)
RED = (255, 112, 140)
CYAN = (63, 224, 229)
BLUE = (20, 61, 204)
GRAY = (229, 229, 229)

TIME_RESOLUTIONS = {
    "1m": 60,
    "5m": 5 * 60,
    "15m": 15 * 60,
    "30m": 30 * 60,
    "1h": 60 * 60,
    "2h": 2 * 60 * 60,
    "4h": 4 * 60 * 60,
    "6h": 6 * 60 * 60,
    "8h": 8 * 60 * 60,
    "12h": 12 * 60 * 60,
    "1d": 24 * 60 * 60,
}

TIME_SPANS = {
    "1h": 60 * 60,
    "2h": 2 * 60 * 60,
    "4h": 4 * 60 * 60,
    "8h": 8 * 60 * 60,
    "12h": 12 * 60 * 60,
    "1d": 24 * 60 * 60,
    "1w": 7 * 24 * 60 * 60,
    "2w": 14 * 24 * 60 * 60,
    "1m": 30 * 24 * 60 * 60,
    "2m": 61 * 24 * 60 * 60,
    "4m": 122 * 24 * 60 * 60,
    "6m": 183 * 24 * 60 * 60,
    "1y": 365 * 24 * 60 * 60,
    "2y": 2 * 365 * 24 * 60 * 60,
    "5y": 5 * 365 * 24 * 60 * 60,
}
