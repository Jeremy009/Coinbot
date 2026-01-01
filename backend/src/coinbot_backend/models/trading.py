"""Trading-related data models."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Signal(Enum):
    """Trading signals."""

    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class TradeSignal(BaseModel):
    """Result from a trading strategy with validation."""

    signal: Signal = Field(..., description="Trading signal recommendation")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence level (0.0 to 1.0)")
    strategy_name: str = Field(..., description="Name of the strategy that generated this signal")
    reason: str = Field(..., description="Human-readable explanation")
    suggested_stop_loss_pct: float | None = Field(None, ge=0.0, description="Stop loss percentage")
    suggested_take_profit_pct: float | None = Field(None, ge=0.0, description="Take profit percentage")
    indicators: dict[str, Any] | None = Field(None, description="Raw indicator values")


class OpenPosition(BaseModel):
    """Represents an open trading position."""

    symbol: str = Field(..., description="Trading symbol (e.g., 'BTC', 'ETH')")
    buy_datetime: datetime = Field(..., description="When the position was opened")
    amount: float = Field(..., description="Amount of coins purchased")
    buy_price: float = Field(..., description="Price per coin at purchase (EUR)")
    ath: float = Field(..., description="All-time high price since purchase (EUR)")
    total_cost: float = Field(..., description="Total cost including fees (EUR)")
    reason_for_buying: str = Field(..., description="Strategy or reason for opening position")
