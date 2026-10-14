"""Ports: interfaces the services depend on, implemented by adapters."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import date
from typing import TypeVar

from finbrain_server.domain.entities import (
    CountryValue,
    CryptoCandle,
    CryptoTicker,
    EconomicSeries,
    FundamentalIndicators,
    GarchParameters,
    IndicatorInfo,
    MarketExpectation,
    OrderBook,
    PriceHistory,
    PtaxQuote,
    Quote,
)

T = TypeVar("T")


class Cache(ABC):
    """Key-value cache with a time to live per entry."""

    @abstractmethod
    def get_or_load(
        self,
        key: str,
        ttl_seconds: float,
        loader: Callable[[], T],
    ) -> T:
        """Return the cached value of ``key`` or load and store it.

        Parameters
        ----------
        key : str
            Identifier of the value.
        ttl_seconds : float
            How long a loaded value stays valid.
        loader : Callable[[], T]
            Produces the value on a miss. Errors are not cached.

        Returns
        -------
        T
            Cached or freshly loaded value.
        """

    @abstractmethod
    def stats(self) -> dict[str, int]:
        """Usage counters of the cache.

        Returns
        -------
        dict[str, int]
            ``entries``, ``max_entries``, ``hits`` and ``misses``.
        """

    @abstractmethod
    def clear(self) -> None:
        """Remove every entry."""


class MarketDataProvider(ABC):
    """Prices and company data of stocks, indices and currencies."""

    @abstractmethod
    def get_history(
        self,
        ticker: str,
        period: str,
        interval: str,
    ) -> PriceHistory:
        """Candles of an asset.

        Parameters
        ----------
        ticker : str
            Yahoo Finance ticker.
        period : str
            Period such as ``1y``.
        interval : str
            Interval such as ``1d``.

        Returns
        -------
        PriceHistory
            Candles in chronological order.
        """

    @abstractmethod
    def get_quote(self, ticker: str) -> Quote:
        """Current price and market data of an asset.

        Parameters
        ----------
        ticker : str
            Yahoo Finance ticker.

        Returns
        -------
        Quote
            Current quote.
        """

    @abstractmethod
    def get_fundamentals(self, ticker: str) -> FundamentalIndicators:
        """Fundamental indicators of a company.

        Parameters
        ----------
        ticker : str
            Yahoo Finance ticker.

        Returns
        -------
        FundamentalIndicators
            Ratios reported by the source.
        """


class BrazilMacroProvider(ABC):
    """Economic data of the Central Bank of Brazil."""

    @abstractmethod
    def get_series(
        self,
        code: int,
        start: date | None,
        end: date | None,
        last: int | None,
    ) -> list[tuple[date, float]]:
        """Observations of an SGS series.

        Parameters
        ----------
        code : int
            SGS code of the series.
        start : date | None
            First day (with ``end``).
        end : date | None
            Last day (with ``start``).
        last : int | None
            Number of most recent observations, instead of the dates.

        Returns
        -------
        list[tuple[date, float]]
            ``(date, value)`` pairs in chronological order.
        """

    @abstractmethod
    def get_ptax(
        self,
        start: date,
        end: date,
    ) -> list[PtaxQuote]:
        """Daily PTAX dollar rates of a period.

        Parameters
        ----------
        start : date
            First day.
        end : date
            Last day.

        Returns
        -------
        list[PtaxQuote]
            Rates in chronological order.
        """

    @abstractmethod
    def get_expectations(
        self,
        indicator: str,
        reference_year: str,
        limit: int,
    ) -> list[MarketExpectation]:
        """Latest Focus survey statistics of an indicator.

        Parameters
        ----------
        indicator : str
            Focus indicator name, such as ``IPCA``.
        reference_year : str
            Year the expectation refers to.
        limit : int
            Number of surveys returned, most recent first.

        Returns
        -------
        list[MarketExpectation]
            Survey statistics.
        """


class WorldBankProvider(ABC):
    """Indicators of the World Bank Open Data."""

    @abstractmethod
    def search_indicators(
        self,
        query: str,
        limit: int,
    ) -> list[IndicatorInfo]:
        """Indicators whose name matches a keyword.

        Parameters
        ----------
        query : str
            Keyword, such as ``inflation``.
        limit : int
            Maximum number of results.

        Returns
        -------
        list[IndicatorInfo]
            Matching indicators.
        """

    @abstractmethod
    def get_indicator(
        self,
        code: str,
        countries: list[str],
        start_year: int | None,
        end_year: int | None,
    ) -> list[CountryValue]:
        """Values of an indicator for countries and years.

        Parameters
        ----------
        code : str
            Indicator code, such as ``FP.CPI.TOTL.ZG``.
        countries : list[str]
            ISO alpha-3 country codes.
        start_year : int | None
            First year, or ``None`` for every available year.
        end_year : int | None
            Last year, or ``None`` for every available year.

        Returns
        -------
        list[CountryValue]
            Non-empty values.
        """


class CryptoProvider(ABC):
    """Market data of crypto exchanges."""

    @abstractmethod
    def list_exchanges(self) -> list[str]:
        """Identifiers of the supported exchanges.

        Returns
        -------
        list[str]
            Exchange identifiers, such as ``binance``.
        """

    @abstractmethod
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

    @abstractmethod
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

    @abstractmethod
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


class GarchEngine(ABC):
    """Fits and simulates GARCH(1,1) models of daily returns."""

    @abstractmethod
    def fit(self, returns_percent: list[float]) -> GarchParameters:
        """Estimate the model by maximum likelihood.

        Parameters
        ----------
        returns_percent : list[float]
            Daily returns in percent (1.0 = 1%).

        Returns
        -------
        GarchParameters
            Fitted parameters with the last conditional variance.
        """

    @abstractmethod
    def simulate_returns(
        self,
        parameters: GarchParameters,
        n_days: int,
        n_paths: int,
        seed: int | None,
    ) -> list[list[float]]:
        """Simulate daily returns in percent.

        Parameters
        ----------
        parameters : GarchParameters
            Model to simulate.
        n_days : int
            Days per path.
        n_paths : int
            Number of independent paths.
        seed : int | None
            Seed of the random generator, for reproducible results.

        Returns
        -------
        list[list[float]]
            ``n_paths`` lists of ``n_days`` returns.
        """
