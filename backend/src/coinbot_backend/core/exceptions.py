"""Custom exceptions for Coinbot."""


class CoinbotException(Exception):
    """Base exception for Coinbot."""

    pass


# Legacy alias for backwards compatibility
CoinbotBaseError = CoinbotException


class CoinbotAPIError(CoinbotException):
    """API-related error."""

    pass


class CoinbotRateLimitError(CoinbotException):
    """Rate limit exceeded error."""

    pass


# Legacy alias for backwards compatibility
CoinbotExceededNumAPICallsError = CoinbotRateLimitError


class CoinbotInvalidSymbolError(CoinbotException):
    """Invalid symbol error."""

    pass


class CoinbotUnexpectedValueError(CoinbotException):
    """Raised when an unexpected value is encountered."""

    pass


class CoinbotUnexpectedTypeError(CoinbotException):
    """Raised when an unexpected type is encountered."""

    pass
