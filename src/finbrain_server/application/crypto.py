"""Use cases of crypto market data (exchanges through ccxt)."""

from finbrain_server.application.cache_policy import CachePolicy
from finbrain_server.application.ports import Cache, CryptoProvider
from finbrain_server.domain.entities import CryptoCandle, CryptoTicker, OrderBook
from finbrain_server.domain.exceptions import ExchangeNotFoundError
from finbrain_server.domain.validation import (
    CRYPTO_TIMEFRAMES,
    ensure_choice,
    ensure_range,
    normalize_crypto_symbol,
)


class CryptoService:
    """Crypto prices, candles and order books with validation and caching.

    Only exchanges listed by the provider are accepted, so a request can
    never reach an arbitrary attribute of the exchange library.

    Parameters
    ----------
    provider : CryptoProvider
        Source of the data.
    cache : Cache
        Cache shared by the services.
    policy : CachePolicy
        Time to live of each kind of data.
    """

    def __init__(
        self,
        provider: CryptoProvider,
        cache: Cache,
        policy: CachePolicy,
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._policy = policy

    def list_exchanges(self) -> list[str]:
        """Identifiers of the supported exchanges.

        Returns
        -------
        list[str]
            Sorted identifiers.
        """
        return self._cache.get_or_load(
            "crypto-exchanges",
            self._policy.exchanges,
            lambda: sorted(self._provider.list_exchanges()),
        )

    def get_ticker(
        self,
        exchange: str,
        symbol: str,
    ) -> CryptoTicker:
        """Current 24-hour data of a pair.

        Parameters
        ----------
        exchange : str
            Exchange identifier, such as ``binance``.
        symbol : str
            Pair such as ``BTC/USDT``.

        Returns
        -------
        CryptoTicker
            Current data.
        """
        name = self._exchange(exchange)
        pair = normalize_crypto_symbol(symbol)
        return self._cache.get_or_load(
            f"crypto-ticker:{name}:{pair}",
            self._policy.crypto_ticker,
            lambda: self._provider.get_ticker(name, pair),
        )

    def get_ohlcv(
        self,
        exchange: str,
        symbol: str,
        timeframe: str = "1d",
        limit: int = 30,
    ) -> list[CryptoCandle]:
        """Recent candles of a pair.

        Parameters
        ----------
        exchange : str
            Exchange identifier.
        symbol : str
            Pair such as ``BTC/USDT``.
        timeframe : str
            Candle size (see :data:`CRYPTO_TIMEFRAMES`).
        limit : int
            Number of candles (1 to 500).

        Returns
        -------
        list[CryptoCandle]
            Candles in chronological order.
        """
        name = self._exchange(exchange)
        pair = normalize_crypto_symbol(symbol)
        ensure_choice("timeframe", timeframe, CRYPTO_TIMEFRAMES)
        ensure_range("limit", limit, 1, 500)
        return self._cache.get_or_load(
            f"crypto-ohlcv:{name}:{pair}:{timeframe}:{limit}",
            self._policy.crypto_ohlcv,
            lambda: self._provider.get_ohlcv(name, pair, timeframe, limit),
        )

    def get_order_book(
        self,
        exchange: str,
        symbol: str,
        limit: int = 5,
    ) -> OrderBook:
        """Best levels of the order book of a pair.

        Parameters
        ----------
        exchange : str
            Exchange identifier.
        symbol : str
            Pair such as ``BTC/USDT``.
        limit : int
            Levels on each side (1 to 100).

        Returns
        -------
        OrderBook
            Bids and asks.
        """
        name = self._exchange(exchange)
        pair = normalize_crypto_symbol(symbol)
        ensure_range("limit", limit, 1, 100)
        return self._cache.get_or_load(
            f"crypto-book:{name}:{pair}:{limit}",
            self._policy.order_book,
            lambda: self._provider.get_order_book(name, pair, limit),
        )

    def _exchange(self, exchange: str) -> str:
        """Check that an exchange is supported.

        Parameters
        ----------
        exchange : str
            Exchange identifier received.

        Returns
        -------
        str
            The identifier in lower case.

        Raises
        ------
        ExchangeNotFoundError
            When the exchange is not supported.
        """
        name = str(exchange or "").strip().lower()
        if name not in self.list_exchanges():
            raise ExchangeNotFoundError(f"Exchange '{exchange}' is not supported.")
        return name
