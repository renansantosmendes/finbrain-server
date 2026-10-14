"""Adapter of crypto exchanges through ``ccxt``."""

import math
import threading
from datetime import datetime, timezone
from typing import Any

import ccxt

from finbrain_server.application.ports import CryptoProvider
from finbrain_server.domain.entities import CryptoCandle, CryptoTicker, OrderBook
from finbrain_server.domain.exceptions import (
    AssetNotFoundError,
    ExchangeNotFoundError,
    UpstreamUnavailableError,
)


class CcxtCryptoProvider(CryptoProvider):
    """Reads public market data of crypto exchanges.

    Exchange clients are created once and reused, because the first call
    of each one downloads its list of markets.

    Parameters
    ----------
    library : Any
        Module with ``exchanges`` and one class per exchange (``ccxt``;
        replaceable in tests).
    """

    def __init__(self, library: Any = ccxt) -> None:
        self._library = library
        self._clients: dict[str, Any] = {}
        self._lock = threading.Lock()

    def list_exchanges(self) -> list[str]:
        """Identifiers of the supported exchanges.

        Returns
        -------
        list[str]
            Exchange identifiers, such as ``binance``.
        """
        return list(self._library.exchanges)

    def get_ticker(
        self,
        exchange: str,
        symbol: str,
    ) -> CryptoTicker:
        """Current 24-hour data of a pair.

        Parameters
        ----------
        exchange : str
            Exchange identifier.
        symbol : str
            Pair such as ``BTC/USDT``.

        Returns
        -------
        CryptoTicker
            Current data.
        """
        data = self._call(exchange, symbol, "fetch_ticker")
        return CryptoTicker(
            exchange=exchange,
            symbol=symbol,
            last=_number(data.get("last")),
            high=_number(data.get("high")),
            low=_number(data.get("low")),
            change_percent=_number(data.get("percentage")),
            base_volume=_number(data.get("baseVolume")),
            timestamp=_timestamp(data.get("timestamp")),
        )

    def get_ohlcv(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> list[CryptoCandle]:
        """Recent candles of a pair.

        Parameters
        ----------
        exchange : str
            Exchange identifier.
        symbol : str
            Pair such as ``BTC/USDT``.
        timeframe : str
            Candle size, such as ``1d``.
        limit : int
            Number of most recent candles.

        Returns
        -------
        list[CryptoCandle]
            Candles in chronological order.
        """
        rows = self._call(exchange, symbol, "fetch_ohlcv", timeframe=timeframe, limit=limit)
        return [
            CryptoCandle(
                timestamp=_timestamp(row[0]),
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5] or 0),
            )
            for row in rows
        ]

    def get_order_book(
        self,
        exchange: str,
        symbol: str,
        limit: int,
    ) -> OrderBook:
        """Best levels of the order book of a pair.

        Parameters
        ----------
        exchange : str
            Exchange identifier.
        symbol : str
            Pair such as ``BTC/USDT``.
        limit : int
            Levels on each side.

        Returns
        -------
        OrderBook
            Bids and asks.
        """
        book = self._call(exchange, symbol, "fetch_order_book", limit=limit)
        return OrderBook(
            exchange=exchange,
            symbol=symbol,
            bids=tuple((float(level[0]), float(level[1])) for level in book["bids"][:limit]),
            asks=tuple((float(level[0]), float(level[1])) for level in book["asks"][:limit]),
        )

    def _client(self, exchange: str) -> Any:
        """Shared client of an exchange.

        Parameters
        ----------
        exchange : str
            Exchange identifier, already validated by the service.

        Returns
        -------
        Any
            The ``ccxt`` exchange instance.

        Raises
        ------
        ExchangeNotFoundError
            When the identifier is not a supported exchange.
        """
        if exchange not in self._library.exchanges:
            raise ExchangeNotFoundError(f"Exchange '{exchange}' is not supported.")
        with self._lock:
            if exchange not in self._clients:
                self._clients[exchange] = getattr(self._library, exchange)(
                    {"enableRateLimit": True, "timeout": 10000}
                )
            return self._clients[exchange]

    def _call(
        self,
        exchange: str,
        symbol: str,
        method: str,
        **options: Any,
    ) -> Any:
        """Call a public method of an exchange, translating its errors.

        Parameters
        ----------
        exchange : str
            Exchange identifier.
        symbol : str
            Pair such as ``BTC/USDT``.
        method : str
            ``fetch_ticker``, ``fetch_ohlcv`` or ``fetch_order_book``.
        **options : Any
            Extra arguments of the method.

        Returns
        -------
        Any
            Raw answer of the exchange.

        Raises
        ------
        AssetNotFoundError
            When the exchange does not list the pair.
        UpstreamUnavailableError
            When the exchange fails.
        """
        client = self._client(exchange)
        try:
            return getattr(client, method)(symbol, **options)
        except self._library.BadSymbol as error:
            raise AssetNotFoundError(
                f"{exchange} does not list the pair {symbol}."
            ) from error
        except Exception as error:
            raise UpstreamUnavailableError(
                f"{exchange} did not answer for {symbol}: {error}"
            ) from error


def _number(value: Any) -> float | None:
    """Convert a value to a finite float.

    Parameters
    ----------
    value : Any
        Value reported by the exchange.

    Returns
    -------
    float | None
        The number, or ``None`` when missing or not finite.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _timestamp(milliseconds: Any) -> datetime | None:
    """Convert a Unix timestamp in milliseconds to an aware datetime.

    Parameters
    ----------
    milliseconds : Any
        Timestamp reported by the exchange.

    Returns
    -------
    datetime | None
        UTC datetime, or ``None`` when missing.
    """
    number = _number(milliseconds)
    if number is None:
        return None
    return datetime.fromtimestamp(number / 1000, tz=timezone.utc)
