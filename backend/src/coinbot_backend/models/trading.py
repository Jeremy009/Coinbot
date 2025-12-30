"""Trading-related data models."""

from datetime import datetime

from pydantic import BaseModel, Field


class OpenPosition(BaseModel):
    """Represents an open trading position."""

    symbol: str = Field(..., description="Trading symbol (e.g., 'BTC', 'ETH')")
    buy_datetime: datetime = Field(..., description="When the position was opened")
    amount: float = Field(..., description="Amount of coins purchased")
    buy_price: float = Field(..., description="Price per coin at purchase (EUR)")
    total_cost: float = Field(..., description="Total cost including fees (EUR)")
    reason_for_buying: str = Field(..., description="Strategy or reason for opening position")


class BalanceResponse(BaseModel):
    """Account balance information."""

    available_funds: float = Field(..., description="Available EUR funds")
    total_balance: float = Field(..., description="Total portfolio value in EUR")
    total_deposited: float = Field(..., description="Total deposited amount")
    total_withdrawn: float = Field(..., description="Total withdrawn amount")
    total_gains: float = Field(..., description="Total gains/losses")


class SymbolInfo(BaseModel):
    """Information about a trading symbol."""

    symbol: str = Field(..., description="Symbol name")
    price: float = Field(..., description="Current price in EUR")
    owned_amount: float = Field(..., description="Amount owned")
    change_24h: float = Field(..., description="24h price change percentage")
    volume_24h: float = Field(..., description="24h trading volume in EUR")


class CandleData(BaseModel):
    """OHLCV candle data."""

    timestamp: int = Field(..., description="Unix timestamp")
    open: float = Field(..., description="Opening price")
    high: float = Field(..., description="Highest price")
    low: float = Field(..., description="Lowest price")
    close: float = Field(..., description="Closing price")
    volume: float = Field(..., description="Trading volume")
