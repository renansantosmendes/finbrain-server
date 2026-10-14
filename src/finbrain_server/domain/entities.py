"""Entities returned by the data sources and by the simulations."""

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True)
class PriceBar:
    """One OHLCV candle of an asset.

    Parameters
    ----------
    date : date
        Trading day (or start of the interval) of the candle.
    open, high, low, close : float
        Prices of the interval.
    volume : int
        Traded volume (0 when the source does not report it).
    """

    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int = 0


@dataclass(frozen=True)
class PriceHistory:
    """Candles of an asset for a period and interval.

    Parameters
    ----------
    ticker : str
        Yahoo Finance ticker.
    period : str
        Period requested (for example ``1y``).
    interval : str
        Candle interval (for example ``1d``).
    bars : tuple[PriceBar, ...]
        Candles in chronological order.
    currency : str | None
        Currency of the prices, when known.
    """

    ticker: str
    period: str
    interval: str
    bars: tuple[PriceBar, ...]
    currency: str | None = None

    @property
    def closes(self) -> list[float]:
        """Closing prices in chronological order.

        Returns
        -------
        list[float]
            One close per candle.
        """
        return [bar.close for bar in self.bars]


@dataclass(frozen=True)
class Quote:
    """Current price and market data of an asset.

    Parameters
    ----------
    ticker : str
        Yahoo Finance ticker.
    name : str | None
        Long name of the asset.
    currency : str | None
        Currency of the prices.
    price : float | None
        Last traded price.
    previous_close : float | None
        Close of the previous session.
    fifty_day_average : float | None
        50-day moving average reported by the source.
    volume : int | None
        Volume of the current session.
    average_volume : int | None
        Average daily volume.
    market_time : datetime | None
        Time of the last price.
    """

    ticker: str
    name: str | None
    currency: str | None
    price: float | None
    previous_close: float | None
    fifty_day_average: float | None = None
    volume: int | None = None
    average_volume: int | None = None
    market_time: datetime | None = None

    @property
    def day_change_percent(self) -> float | None:
        """Change of the price against the previous close, in percent.

        Returns
        -------
        float | None
            Rounded change, or ``None`` when a price is missing.
        """
        if not self.price or not self.previous_close:
            return None
        return round((self.price / self.previous_close - 1) * 100, 2)


@dataclass(frozen=True)
class FundamentalIndicators:
    """Fundamental indicators of a company.

    Ratios come as reported by Yahoo Finance: ``roe`` and ``net_margin``
    are fractions (0.25 = 25%), ``dividend_yield`` is already in percent.
    """

    ticker: str
    name: str | None
    sector: str | None
    pe_ratio: float | None
    pb_ratio: float | None
    roe: float | None
    net_margin: float | None
    dividend_yield: float | None
    debt_to_equity: float | None
    earnings_per_share: float | None
    market_cap: float | None
    currency: str | None


@dataclass(frozen=True)
class TechnicalIndicators:
    """Technical indicators computed from the closing prices.

    Parameters
    ----------
    ticker : str
        Yahoo Finance ticker.
    period : str
        History period used in the computation.
    current_price : float
        Last close.
    moving_average_9, moving_average_21, moving_average_50 : float | None
        Simple moving averages (``None`` without enough data).
    rsi_14 : float | None
        14-day relative strength index.
    macd, macd_signal : float | None
        MACD line (EMA12 - EMA26) and its 9-day EMA.
    """

    ticker: str
    period: str
    current_price: float
    moving_average_9: float | None
    moving_average_21: float | None
    moving_average_50: float | None
    rsi_14: float | None
    macd: float | None
    macd_signal: float | None


@dataclass(frozen=True)
class AssetComparison:
    """One row of the side-by-side comparison of assets."""

    ticker: str
    name: str | None = None
    current_price: float | None = None
    day_change_percent: float | None = None
    pe_ratio: float | None = None
    dividend_yield: float | None = None
    currency: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class Observation:
    """One dated value of an economic series."""

    date: date
    value: float


@dataclass(frozen=True)
class EconomicSeries:
    """An economic time series with its metadata.

    Parameters
    ----------
    name : str
        Identifier used in the API (for example ``selic``).
    description : str
        Human-readable description, with the unit.
    source : str
        Source of the data.
    observations : tuple[Observation, ...]
        Values in chronological order.
    """

    name: str
    description: str
    source: str
    observations: tuple[Observation, ...]


@dataclass(frozen=True)
class PtaxQuote:
    """Daily PTAX dollar rates published by the Central Bank of Brazil."""

    timestamp: datetime
    buy: float
    sell: float


@dataclass(frozen=True)
class MarketExpectation:
    """One Focus survey statistic for an indicator and reference year."""

    indicator: str
    reference_year: str
    survey_date: date
    mean: float | None
    median: float | None
    minimum: float | None
    maximum: float | None
    respondents: int | None


@dataclass(frozen=True)
class IndicatorInfo:
    """A World Bank indicator found by a search."""

    code: str
    name: str


@dataclass(frozen=True)
class CountryValue:
    """A World Bank indicator value for a country and year."""

    country: str
    year: int
    value: float


@dataclass(frozen=True)
class CryptoTicker:
    """Current 24-hour market data of a crypto pair on an exchange."""

    exchange: str
    symbol: str
    last: float | None
    high: float | None
    low: float | None
    change_percent: float | None
    base_volume: float | None
    timestamp: datetime | None


@dataclass(frozen=True)
class CryptoCandle:
    """One OHLCV candle of a crypto pair."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class OrderBook:
    """Best levels of the order book of a crypto pair.

    ``bids`` and ``asks`` are ``(price, amount)`` pairs, best first.
    """

    exchange: str
    symbol: str
    bids: tuple[tuple[float, float], ...]
    asks: tuple[tuple[float, float], ...]

    @property
    def best_bid(self) -> float | None:
        """Highest buying price.

        Returns
        -------
        float | None
            Best bid, or ``None`` on an empty side.
        """
        return self.bids[0][0] if self.bids else None

    @property
    def best_ask(self) -> float | None:
        """Lowest selling price.

        Returns
        -------
        float | None
            Best ask, or ``None`` on an empty side.
        """
        return self.asks[0][0] if self.asks else None

    @property
    def spread(self) -> float | None:
        """Difference between the best ask and the best bid.

        Returns
        -------
        float | None
            Spread, or ``None`` when a side is empty.
        """
        if self.best_bid is None or self.best_ask is None:
            return None
        return self.best_ask - self.best_bid


@dataclass(frozen=True)
class GarchParameters:
    """Parameters of a GARCH(1,1) model on daily returns in percent.

    Parameters
    ----------
    mu : float
        Mean daily return, in percent.
    omega, alpha, beta : float
        Variance equation: ``s2[t] = omega + alpha * e[t-1]^2 + beta *
        s2[t-1]``.
    last_variance : float | None
        Conditional variance of the last observed day (starts the
        simulation); ``None`` uses the long-run variance.
    last_residual : float | None
        Residual of the last observed day.
    """

    mu: float
    omega: float
    alpha: float
    beta: float
    last_variance: float | None = None
    last_residual: float | None = None

    @property
    def persistence(self) -> float:
        """Persistence of volatility shocks (``alpha + beta``).

        Returns
        -------
        float
            Values close to 1 mean long-lived volatility.
        """
        return self.alpha + self.beta

    @property
    def long_run_variance(self) -> float:
        """Unconditional daily variance, in percent squared.

        Returns
        -------
        float
            ``omega / (1 - alpha - beta)``.
        """
        return self.omega / (1 - self.persistence)

    @property
    def annualized_volatility_percent(self) -> float:
        """Long-run volatility annualized with 252 trading days.

        Returns
        -------
        float
            Volatility in percent per year.
        """
        return (self.long_run_variance * 252) ** 0.5


@dataclass(frozen=True)
class SimulationFan:
    """Distribution of simulated price paths of an asset.

    Parameters
    ----------
    ticker : str
        Simulated asset.
    last_close : float
        Price the paths start from.
    last_date : date
        Day of ``last_close``.
    dates : tuple[date, ...]
        Future business days of the horizon.
    percentiles : dict[str, tuple[float, ...]]
        Price per day for each percentile key (``p10``, ``p50``...).
    sample_paths : tuple[tuple[float, ...], ...]
        A few complete simulated paths, for illustration.
    final_prices : tuple[float, ...]
        Last price of every path.
    parameters : GarchParameters
        Model used in the simulation.
    n_paths : int
        Number of simulated paths.
    """

    ticker: str
    last_close: float
    last_date: date
    dates: tuple[date, ...]
    percentiles: dict[str, tuple[float, ...]]
    sample_paths: tuple[tuple[float, ...], ...]
    final_prices: tuple[float, ...]
    parameters: GarchParameters
    n_paths: int
    observations_used: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)
