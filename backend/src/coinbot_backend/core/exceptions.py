"""Custom exceptions for Coinbot."""


class CoinbotException(Exception):
    """Base exception for Coinbot."""

    pass


class CoinbotAPIError(CoinbotException):
    """API-related error."""

    pass


class CoinbotRateLimitError(CoinbotException):
    """Rate limit exceeded error."""

    pass


class CoinbotInvalidSymbolError(CoinbotException):
    """Invalid symbol error."""

    pass


class CoinbotUnexpectedValueError(CoinbotException):
    """Raised when an unexpected value is encountered."""

    pass


class CoinbotUnexpectedTypeError(CoinbotException):
    """Raised when an unexpected type is encountered."""

    pass
