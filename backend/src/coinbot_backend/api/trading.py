"""Trading API endpoints."""

from fastapi import APIRouter, HTTPException

from coinbot_backend.models.trading import BalanceResponse, SymbolInfo
from coinbot_backend.services.bitvavo_client import get_bitvavo_client

router = APIRouter()


@router.get("/balance")
async def get_balance() -> BalanceResponse:
    """Get account balance information."""
    try:
        client = get_bitvavo_client()
        available_funds = client.get_available_funds()
        total_balance = client.get_total_wallet_balance()
        total_deposited = client.get_total_deposited()
        total_withdrawn = client.get_total_withdrawn()
        total_gains = client.get_total_gains()

        return BalanceResponse(
            available_funds=available_funds,
            total_balance=total_balance,
            total_deposited=total_deposited,
            total_withdrawn=total_withdrawn,
            total_gains=total_gains,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/symbols")
async def get_available_symbols() -> list[str]:
    """Get list of available trading symbols."""
    try:
        client = get_bitvavo_client()
        return client.get_available_symbols()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/symbols/{symbol}")
async def get_symbol_info(symbol: str) -> SymbolInfo:
    """Get information about a specific symbol."""
    try:
        client = get_bitvavo_client()
        price = client.get_symbol_price(symbol)
        owned_amount = client.get_symbol_owned_amount(symbol)
        change_24h = client.get_symbol_24h_percentual_change(symbol)
        volume_24h = client.get_symbol_24h_volume(symbol)

        return SymbolInfo(
            symbol=symbol,
            price=price,
            owned_amount=owned_amount,
            change_24h=change_24h,
            volume_24h=volume_24h,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
