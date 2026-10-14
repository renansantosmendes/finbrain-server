"""Use cases of stocks, indices and currencies (Yahoo Finance)."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from finbrain_server.application.cache_policy import CachePolicy
from finbrain_server.application.ports import Cache, MarketDataProvider
from finbrain_server.domain import technical
from finbrain_server.domain.entities import (
    AssetComparison,
    FundamentalIndicators,
    PriceHistory,
    Quote,
    TechnicalIndicators,
)
from finbrain_server.domain.exceptions import AssetNotFoundError, DomainError
from finbrain_server.domain.validation import (
    INTERVALS,
    PERIODS,
    ensure_choice,
    normalize_ticker,
    parse_ticker_list,
)

TECHNICAL_PERIODS = ("1mo", "3mo", "6mo", "1y", "2y", "5y")
DASHBOARD_PERIODS = ("1mo", "3mo", "6mo", "1y", "2y")


@dataclass(frozen=True)
class AssetSnapshot:
    """History of one dashboard asset, or the error that prevented it.

    Parameters
    ----------
    ticker : str
        Yahoo Finance ticker.
    history : PriceHistory | None
        Candles of the period, when they could be loaded.
    error_code : str | None
        Stable error code when the asset failed.
    error_message : str | None
        Explanation of the failure.
    """

    ticker: str
    history: PriceHistory | None = None
    error_code: str | None = None
    error_message: str | None = None


class MarketDataService:
    """Market data with caching, validation and technical indicators.

    Parameters
    ----------
    provider : MarketDataProvider
        Source of prices and company data.
    cache : Cache
        Cache shared by the services.
    policy : CachePolicy
        Time to live of each kind of data.
    max_workers : int
        Parallel requests when several tickers are loaded.
    """

    def __init__(
        self,
        provider: MarketDataProvider,
        cache: Cache,
        policy: CachePolicy,
        max_workers: int = 6,
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._policy = policy
        self._max_workers = max_workers

    def get_history(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> PriceHistory:
        """Candles of an asset, cached by ticker, period and interval.

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

        Raises
        ------
        AssetNotFoundError
            When the source has no candles for the ticker.
        """
        symbol = normalize_ticker(ticker)
        ensure_choice("period", period, PERIODS)
        ensure_choice("interval", interval, INTERVALS)

        def load() -> PriceHistory:
            history = self._provider.get_history(symbol, period, interval)
            if not history.bars:
                raise AssetNotFoundError(f"No price data for ticker '{symbol}'.")
            return history

        return self._cache.get_or_load(
            f"history:{symbol}:{period}:{interval}", self._policy.history, load
        )

    def get_quote(self, ticker: str) -> Quote:
        """Current quote of an asset, cached for a short time.

        Parameters
        ----------
        ticker : str
            Yahoo Finance ticker.

        Returns
        -------
        Quote
            Current price and market data.
        """
        symbol = normalize_ticker(ticker)
        return self._cache.get_or_load(
            f"quote:{symbol}",
            self._policy.quote,
            lambda: self._provider.get_quote(symbol),
        )

    def get_fundamentals(self, ticker: str) -> FundamentalIndicators:
        """Fundamental indicators of a company, cached for hours.

        Parameters
        ----------
        ticker : str
            Yahoo Finance ticker.

        Returns
        -------
        FundamentalIndicators
            Ratios reported by the source.
        """
        symbol = normalize_ticker(ticker)
        return self._cache.get_or_load(
            f"fundamentals:{symbol}",
            self._policy.fundamentals,
            lambda: self._provider.get_fundamentals(symbol),
        )

    def get_technical_indicators(
        self,
        ticker: str,
        period: str = "3mo",
    ) -> TechnicalIndicators:
        """Moving averages (9, 21, 50), RSI 14 and MACD of an asset.

        Parameters
        ----------
        ticker : str
            Yahoo Finance ticker.
        period : str
            Daily history used, such as ``3mo``.

        Returns
        -------
        TechnicalIndicators
            Indicators of the last close.
        """
        ensure_choice("period", period, TECHNICAL_PERIODS)
        history = self.get_history(ticker, period, "1d")
        closes = history.closes
        macd_line, macd_signal = technical.macd(closes)
        return TechnicalIndicators(
            ticker=history.ticker,
            period=period,
            current_price=round(closes[-1], 4),
            moving_average_9=_rounded(technical.simple_moving_average(closes, 9)),
            moving_average_21=_rounded(technical.simple_moving_average(closes, 21)),
            moving_average_50=_rounded(technical.simple_moving_average(closes, 50)),
            rsi_14=_rounded(technical.relative_strength_index(closes, 14), 2),
            macd=_rounded(macd_line),
            macd_signal=_rounded(macd_signal),
        )

    def compare_assets(self, tickers: str) -> list[AssetComparison]:
        """Price, day change, P/E and dividend yield side by side.

        An asset that fails is returned with its ``error`` instead of
        failing the whole comparison.

        Parameters
        ----------
        tickers : str
            Comma-separated Yahoo Finance tickers.

        Returns
        -------
        list[AssetComparison]
            One row per ticker, in the given order.
        """
        symbols = parse_ticker_list(tickers)
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            return list(executor.map(self._compare_one, symbols))

    def get_snapshots(
        self,
        tickers: list[str],
        period: str = "1y",
    ) -> list[AssetSnapshot]:
        """Daily histories of several assets, loaded in parallel.

        Parameters
        ----------
        tickers : list[str]
            Normalized Yahoo Finance tickers.
        period : str
            Period of the daily candles.

        Returns
        -------
        list[AssetSnapshot]
            One snapshot per ticker, in the given order.
        """
        ensure_choice("period", period, DASHBOARD_PERIODS)

        def load(symbol: str) -> AssetSnapshot:
            try:
                return AssetSnapshot(symbol, self.get_history(symbol, period, "1d"))
            except DomainError as error:
                return AssetSnapshot(symbol, None, error.code, error.message)

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            return list(executor.map(load, tickers))

    def _compare_one(self, symbol: str) -> AssetComparison:
        """Build the comparison row of one ticker.

        Parameters
        ----------
        symbol : str
            Normalized ticker.

        Returns
        -------
        AssetComparison
            Row with data, or with the error message.
        """
        try:
            quote = self.get_quote(symbol)
            fundamentals = self.get_fundamentals(symbol)
        except DomainError as error:
            return AssetComparison(ticker=symbol, error=error.message)
        return AssetComparison(
            ticker=symbol,
            name=quote.name or fundamentals.name,
            current_price=quote.price,
            day_change_percent=quote.day_change_percent,
            pe_ratio=fundamentals.pe_ratio,
            dividend_yield=fundamentals.dividend_yield,
            currency=quote.currency or fundamentals.currency,
        )


def _rounded(
    value: float | None,
    digits: int = 4,
) -> float | None:
    """Round a value that may be missing.

    Parameters
    ----------
    value : float | None
        Value to round.
    digits : int
        Decimal places.

    Returns
    -------
    float | None
        Rounded value, or ``None``.
    """
    return None if value is None else round(value, digits)
