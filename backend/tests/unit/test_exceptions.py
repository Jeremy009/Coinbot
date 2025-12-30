"""Tests for custom exceptions."""

import pytest

from coinbot_backend.core.exceptions import (
    CoinbotAPIError,
    CoinbotException,
    CoinbotInvalidSymbolError,
    CoinbotRateLimitError,
)


def test_base_exception() -> None:
    """Test base exception."""
    with pytest.raises(CoinbotException):
        raise CoinbotException("Test error")


def test_api_error() -> None:
    """Test API error exception."""
    with pytest.raises(CoinbotAPIError):
        raise CoinbotAPIError("API error")


def test_rate_limit_error() -> None:
    """Test rate limit error exception."""
    with pytest.raises(CoinbotRateLimitError):
        raise CoinbotRateLimitError("Rate limit exceeded")


def test_invalid_symbol_error() -> None:
    """Test invalid symbol error exception."""
    with pytest.raises(CoinbotInvalidSymbolError):
        raise CoinbotInvalidSymbolError("Invalid symbol")
