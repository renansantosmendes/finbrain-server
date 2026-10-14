"""Routes of crypto market data (exchanges through ccxt)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from finbrain_server.application.crypto import CryptoService
from finbrain_server.presentation.api.dependencies import cache_for, get_crypto_service
from finbrain_server.presentation.api.error_handlers import INVALID, UPSTREAM, error_doc
from finbrain_server.presentation.api.schemas import (
    CryptoCandleSchema,
    CryptoTickerResponse,
    OrderBookResponse,
)

router = APIRouter(prefix="/crypto", tags=["Crypto"])

Service = Annotated[CryptoService, Depends(get_crypto_service)]
Exchange = Annotated[
    str,
    Path(description="Exchange identifier (see `/crypto/exchanges`).", examples=["binance"]),
]
Symbol = Annotated[
    str, Query(description="Pair in the BASE/QUOTE format.", examples=["BTC/USDT"])
]
NOT_FOUND = {
    404: error_doc(
        "Unknown exchange (`exchange_not_found`) or pair not listed "
        "(`asset_not_found`)."
    )
}


@router.get(
    "/exchanges",
    summary="Supported crypto exchanges",
    description="Identifiers accepted by the other crypto routes. Same data as "
    "the finbrain-mcp tool `list_available_exchanges`.",
    response_description="Exchange identifiers.",
    dependencies=[Depends(cache_for(86400))],
)
def list_exchanges(service: Service) -> list[str]:
    """Return the supported exchanges.

    Parameters
    ----------
    service : CryptoService
        Crypto service.

    Returns
    -------
    list[str]
        Exchange identifiers.
    """
    return service.list_exchanges()


@router.get(
    "/exchanges/{exchange}/ticker",
    summary="Current price of a crypto pair",
    description="Last price, 24-hour high, low, change and volume. Cached for "
    "15 seconds. Same data as the finbrain-mcp tool `get_crypto_price`.",
    response_description="Current 24-hour data.",
    responses={**NOT_FOUND, **INVALID, **UPSTREAM},
    dependencies=[Depends(cache_for(15))],
)
def get_ticker(
    service: Service,
    exchange: Exchange,
    symbol: Symbol,
) -> CryptoTickerResponse:
    """Return the current data of a pair.

    Parameters
    ----------
    service : CryptoService
        Crypto service.
    exchange : str
        Exchange identifier.
    symbol : str
        Pair.

    Returns
    -------
    CryptoTickerResponse
        Current data.
    """
    return CryptoTickerResponse.build(service.get_ticker(exchange, symbol))


@router.get(
    "/exchanges/{exchange}/ohlcv",
    summary="Candles of a crypto pair",
    description="Most recent OHLCV candles. Same data as the finbrain-mcp tool "
    "`get_crypto_ohlcv`.",
    response_description="Candles, oldest first.",
    responses={**NOT_FOUND, **INVALID, **UPSTREAM},
    dependencies=[Depends(cache_for(60))],
)
def get_ohlcv(
    service: Service,
    exchange: Exchange,
    symbol: Symbol,
    timeframe: Annotated[
        str, Query(description="1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w or 1M.")
    ] = "1d",
    limit: Annotated[int, Query(description="Number of candles (1 to 500).")] = 30,
) -> list[CryptoCandleSchema]:
    """Return the candles of a pair.

    Parameters
    ----------
    service : CryptoService
        Crypto service.
    exchange : str
        Exchange identifier.
    symbol : str
        Pair.
    timeframe : str
        Candle size.
    limit : int
        Number of candles.

    Returns
    -------
    list[CryptoCandleSchema]
        Candles.
    """
    candles = service.get_ohlcv(exchange, symbol, timeframe, limit)
    return [CryptoCandleSchema.build(item) for item in candles]


@router.get(
    "/exchanges/{exchange}/order-book",
    summary="Order book of a crypto pair",
    description="Best bids and asks with the spread. Cached for 5 seconds. "
    "Same data as the finbrain-mcp tool `get_crypto_order_book`.",
    response_description="Best levels of each side.",
    responses={**NOT_FOUND, **INVALID, **UPSTREAM},
    dependencies=[Depends(cache_for(5))],
)
def get_order_book(
    service: Service,
    exchange: Exchange,
    symbol: Symbol,
    limit: Annotated[int, Query(description="Levels on each side (1 to 100).")] = 5,
) -> OrderBookResponse:
    """Return the order book of a pair.

    Parameters
    ----------
    service : CryptoService
        Crypto service.
    exchange : str
        Exchange identifier.
    symbol : str
        Pair.
    limit : int
        Levels on each side.

    Returns
    -------
    OrderBookResponse
        Bids and asks.
    """
    return OrderBookResponse.build(service.get_order_book(exchange, symbol, limit))
