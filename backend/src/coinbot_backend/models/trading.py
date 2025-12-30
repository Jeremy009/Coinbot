"""Trading-related data models."""

from pydantic import BaseModel, Field


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
