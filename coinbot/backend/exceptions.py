class CoinbotBaseError(Exception):
    """ Base class for other exceptions. """
    pass


class CoinbotUnexpectedValueError(CoinbotBaseError):
    """ Raised when an unexpected value is encountered. """
    pass


class CoinbotUnexpectedTypeError(CoinbotBaseError):
    """ Raised when an unexpected type is encountered. """
    pass


class CoinbotExceededNumAPICallsError(CoinbotBaseError):
    """ Raised when there are too many consecutive API calls in a too short timespan. """
    pass
