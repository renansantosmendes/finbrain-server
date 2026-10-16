"""Request and response bodies of the API (documented for Swagger)."""

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from finbrain_server.domain.entities import (
    AssetComparison,
    CountryValue,
    CryptoCandle,
    CryptoTicker,
    EconomicSeries,
    FundamentalIndicators,
    GarchParameters,
    IndicatorInfo,
    MarketExpectation,
    OrderBook,
    PriceBar,
    PriceHistory,
    PtaxQuote,
    Quote,
    SimulationFan,
    TechnicalIndicators,
)


class ApiModel(BaseModel):
    """Base of every schema: built from attributes of the entities."""

    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(ApiModel):
    """Body of every error response."""

    code: str = Field(
        description="Stable machine-readable error code.",
        examples=["asset_not_found"],
    )
    message: str = Field(
        description="Human-readable explanation.",
        examples=["No price data for ticker 'XXXX3.SA'."],
    )
    details: list[str] | None = Field(
        default=None, description="Extra explanations, such as invalid fields."
    )


class HealthResponse(ApiModel):
    """Liveness of the API."""

    status: str = Field(description="Always `ok`.", examples=["ok"])
    version: str = Field(description="Version of the server.", examples=["0.1.0"])


class CacheStatsResponse(ApiModel):
    """Counters of the in-memory cache of this instance."""

    entries: int = Field(description="Entries currently cached.")
    max_entries: int = Field(description="Capacity of the cache.")
    hits: int = Field(description="Lookups answered from the cache.")
    misses: int = Field(description="Lookups that loaded the data.")


class PriceBarSchema(ApiModel):
    """One daily (or intraday) candle."""

    date: dt.date = Field(description="Trading day.", examples=["2026-10-09"])
    open: float = Field(description="Opening price.", examples=[55.45])
    high: float = Field(description="Highest price.", examples=[56.8])
    low: float = Field(description="Lowest price.", examples=[55.1])
    close: float = Field(description="Closing price.", examples=[56.0])
    volume: int = Field(description="Traded volume.", examples=[41250300])
    timestamp: dt.datetime | None = Field(
        default=None,
        description="Start of the candle with its time zone. Only for intraday intervals.",
        examples=["2026-10-15T10:01:00-03:00"],
    )

    @classmethod
    def build(cls, bar: PriceBar) -> "PriceBarSchema":
        """Build the schema from an entity.

        Parameters
        ----------
        bar : PriceBar
            Candle.

        Returns
        -------
        PriceBarSchema
            Response body.
        """
        return cls.model_validate(bar)


class PriceHistoryResponse(ApiModel):
    """Candles of an asset."""

    ticker: str = Field(description="Yahoo Finance ticker.", examples=["PETR4.SA"])
    period: str = Field(description="Period requested.", examples=["1y"])
    interval: str = Field(description="Candle interval.", examples=["1d"])
    currency: str | None = Field(description="Currency of the prices.", examples=["BRL"])
    bars: list[PriceBarSchema] = Field(description="Candles, oldest first.")

    @classmethod
    def build(cls, history: PriceHistory) -> "PriceHistoryResponse":
        """Build the schema from an entity.

        Parameters
        ----------
        history : PriceHistory
            Candles of the asset.

        Returns
        -------
        PriceHistoryResponse
            Response body.
        """
        return cls(
            ticker=history.ticker,
            period=history.period,
            interval=history.interval,
            currency=history.currency,
            bars=[PriceBarSchema.build(bar) for bar in history.bars],
        )


class QuoteResponse(ApiModel):
    """Current price and market data of an asset."""

    ticker: str = Field(examples=["PETR4.SA"])
    name: str | None = Field(examples=["Petróleo Brasileiro S.A. - Petrobras"])
    currency: str | None = Field(examples=["BRL"])
    price: float | None = Field(description="Last price.", examples=[56.85])
    previous_close: float | None = Field(examples=[56.0])
    day_change_percent: float | None = Field(
        description="Change against the previous close, in percent.",
        examples=[1.52],
    )
    fifty_day_average: float | None = Field(examples=[54.3])
    volume: int | None = Field(examples=[38000000])
    average_volume: int | None = Field(examples=[42000000])
    market_time: dt.datetime | None = Field(description="Time of the last price (UTC).")

    @classmethod
    def build(cls, quote: Quote) -> "QuoteResponse":
        """Build the schema from an entity.

        Parameters
        ----------
        quote : Quote
            Current quote.

        Returns
        -------
        QuoteResponse
            Response body.
        """
        return cls(
            ticker=quote.ticker,
            name=quote.name,
            currency=quote.currency,
            price=quote.price,
            previous_close=quote.previous_close,
            day_change_percent=quote.day_change_percent,
            fifty_day_average=quote.fifty_day_average,
            volume=quote.volume,
            average_volume=quote.average_volume,
            market_time=quote.market_time,
        )


class FundamentalsResponse(ApiModel):
    """Fundamental indicators as reported by Yahoo Finance.

    `roe` and `net_margin` are fractions (0.25 = 25%); `dividend_yield` is
    already in percent.
    """

    ticker: str = Field(examples=["PETR4.SA"])
    name: str | None = Field(examples=["Petróleo Brasileiro S.A. - Petrobras"])
    sector: str | None = Field(examples=["Energy"])
    pe_ratio: float | None = Field(description="Price / earnings.", examples=[5.42])
    pb_ratio: float | None = Field(description="Price / book value.", examples=[1.31])
    roe: float | None = Field(description="Return on equity (fraction).", examples=[0.25])
    net_margin: float | None = Field(description="Net margin (fraction).", examples=[0.18])
    dividend_yield: float | None = Field(description="Dividend yield (%).", examples=[6.54])
    debt_to_equity: float | None = Field(examples=[72.4])
    earnings_per_share: float | None = Field(examples=[10.49])
    market_cap: float | None = Field(examples=[776769175552])
    currency: str | None = Field(examples=["BRL"])

    @classmethod
    def build(cls, item: FundamentalIndicators) -> "FundamentalsResponse":
        """Build the schema from an entity.

        Parameters
        ----------
        item : FundamentalIndicators
            Company indicators.

        Returns
        -------
        FundamentalsResponse
            Response body.
        """
        return cls.model_validate(item)


class TechnicalResponse(ApiModel):
    """Technical indicators of the last close."""

    ticker: str = Field(examples=["PETR4.SA"])
    period: str = Field(description="History used.", examples=["3mo"])
    current_price: float = Field(examples=[56.0])
    moving_average_9: float | None = Field(examples=[55.2])
    moving_average_21: float | None = Field(examples=[54.1])
    moving_average_50: float | None = Field(examples=[52.7])
    rsi_14: float | None = Field(description="RSI between 0 and 100.", examples=[61.3])
    macd: float | None = Field(description="EMA12 - EMA26.", examples=[0.84])
    macd_signal: float | None = Field(description="EMA9 of the MACD.", examples=[0.71])

    @classmethod
    def build(cls, item: TechnicalIndicators) -> "TechnicalResponse":
        """Build the schema from an entity.

        Parameters
        ----------
        item : TechnicalIndicators
            Indicators.

        Returns
        -------
        TechnicalResponse
            Response body.
        """
        return cls.model_validate(item)


class ComparisonRow(ApiModel):
    """One asset of a comparison; `error` is set when it failed."""

    ticker: str = Field(examples=["VALE3.SA"])
    name: str | None = None
    current_price: float | None = None
    day_change_percent: float | None = None
    pe_ratio: float | None = None
    dividend_yield: float | None = Field(default=None, description="In percent.")
    currency: str | None = None
    error: str | None = None

    @classmethod
    def build(cls, item: AssetComparison) -> "ComparisonRow":
        """Build the schema from an entity.

        Parameters
        ----------
        item : AssetComparison
            Comparison row.

        Returns
        -------
        ComparisonRow
            Response body.
        """
        return cls.model_validate(item)


class ObservationSchema(ApiModel):
    """A dated value."""

    date: dt.date = Field(examples=["2026-10-09"])
    value: float = Field(examples=[13.65])


class DashboardAsset(ApiModel):
    """An asset of the dashboard with its daily candles.

    When the asset failed, `bars` is empty and `error_code` and
    `error_message` explain why; the other assets are still returned.
    """

    ticker: str = Field(examples=["PETR4.SA"])
    currency: str | None = Field(default=None, examples=["BRL"])
    last_close: float | None = Field(default=None, examples=[56.0])
    previous_close: float | None = Field(default=None, examples=[55.3])
    day_change_percent: float | None = Field(default=None, examples=[1.27])
    last_date: dt.date | None = Field(default=None, examples=["2026-10-09"])
    bars: list[PriceBarSchema] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None


class MacroBrasilSummaryResponse(ApiModel):
    """Latest Brazilian rates; `real_rate` is CDI discounted by the IPCA."""

    selic: ObservationSchema | None = Field(description="Selic target, % per year.")
    cdi: ObservationSchema | None = Field(description="Annualized CDI, % per year.")
    ipca_12m: ObservationSchema | None = Field(description="IPCA in 12 months, %.")
    real_rate: float | None = Field(
        description="(1 + CDI) / (1 + IPCA 12m) - 1, % per year.", examples=[8.7]
    )
    source: str = Field(examples=["Banco Central do Brasil · SGS"])


class DashboardResponse(ApiModel):
    """Everything the Dashboards screen needs in one request."""

    generated_at: dt.datetime = Field(description="When the answer was built (UTC).")
    period: str = Field(examples=["1y"])
    assets: list[DashboardAsset]
    macro: MacroBrasilSummaryResponse | None = Field(
        description="Brazilian rates; null when the Central Bank API failed."
    )
    macro_error: str | None = Field(
        default=None, description="Why `macro` is null, when it is."
    )


class SeriesInfoResponse(ApiModel):
    """A Central Bank series offered by the API."""

    name: str = Field(examples=["selic"])
    code: int = Field(description="SGS code.", examples=[432])
    description: str = Field(examples=["Selic target rate (% per year)"])
    frequency: str = Field(examples=["daily"])


class EconomicSeriesResponse(ApiModel):
    """Observations of an economic series."""

    name: str = Field(examples=["ipca_12m"])
    description: str
    source: str
    observations: list[ObservationSchema]

    @classmethod
    def build(cls, series: EconomicSeries) -> "EconomicSeriesResponse":
        """Build the schema from an entity.

        Parameters
        ----------
        series : EconomicSeries
            Series.

        Returns
        -------
        EconomicSeriesResponse
            Response body.
        """
        return cls(
            name=series.name,
            description=series.description,
            source=series.source,
            observations=[ObservationSchema.model_validate(item) for item in series.observations],
        )


class PtaxQuoteSchema(ApiModel):
    """PTAX dollar rates of a day."""

    timestamp: dt.datetime = Field(description="Publication time.")
    buy: float = Field(description="Buy rate (R$ per US$).", examples=[4.9886])
    sell: float = Field(description="Sell rate (R$ per US$).", examples=[4.9892])

    @classmethod
    def build(cls, quote: PtaxQuote) -> "PtaxQuoteSchema":
        """Build the schema from an entity.

        Parameters
        ----------
        quote : PtaxQuote
            Rates.

        Returns
        -------
        PtaxQuoteSchema
            Response body.
        """
        return cls.model_validate(quote)


class ExpectationSchema(ApiModel):
    """Focus survey statistics of a day."""

    indicator: str = Field(examples=["IPCA"])
    reference_year: str = Field(examples=["2026"])
    survey_date: dt.date = Field(examples=["2026-10-09"])
    mean: float | None = Field(examples=[5.21])
    median: float | None = Field(examples=[5.22])
    minimum: float | None = Field(examples=[4.5])
    maximum: float | None = Field(examples=[5.88])
    respondents: int | None = Field(examples=[144])

    @classmethod
    def build(cls, item: MarketExpectation) -> "ExpectationSchema":
        """Build the schema from an entity.

        Parameters
        ----------
        item : MarketExpectation
            Survey statistics.

        Returns
        -------
        ExpectationSchema
            Response body.
        """
        return cls.model_validate(item)


class IndicatorInfoSchema(ApiModel):
    """A World Bank indicator."""

    code: str = Field(examples=["FP.CPI.TOTL.ZG"])
    name: str = Field(examples=["Inflation, consumer prices (annual %)"])

    @classmethod
    def build(cls, item: IndicatorInfo) -> "IndicatorInfoSchema":
        """Build the schema from an entity.

        Parameters
        ----------
        item : IndicatorInfo
            Indicator.

        Returns
        -------
        IndicatorInfoSchema
            Response body.
        """
        return cls.model_validate(item)


class CountryValueSchema(ApiModel):
    """Value of an indicator for a country and year."""

    country: str = Field(description="ISO alpha-3 code.", examples=["BRA"])
    year: int = Field(examples=[2023])
    value: float = Field(examples=[4.59])

    @classmethod
    def build(cls, item: CountryValue) -> "CountryValueSchema":
        """Build the schema from an entity.

        Parameters
        ----------
        item : CountryValue
            Value.

        Returns
        -------
        CountryValueSchema
            Response body.
        """
        return cls.model_validate(item)


class CryptoTickerResponse(ApiModel):
    """Current 24-hour data of a crypto pair."""

    exchange: str = Field(examples=["binance"])
    symbol: str = Field(examples=["BTC/USDT"])
    last: float | None = Field(examples=[62000.5])
    high: float | None = Field(description="24-hour high.")
    low: float | None = Field(description="24-hour low.")
    change_percent: float | None = Field(description="24-hour change, %.")
    base_volume: float | None = Field(description="24-hour volume in the base asset.")
    timestamp: dt.datetime | None = None

    @classmethod
    def build(cls, item: CryptoTicker) -> "CryptoTickerResponse":
        """Build the schema from an entity.

        Parameters
        ----------
        item : CryptoTicker
            Ticker.

        Returns
        -------
        CryptoTickerResponse
            Response body.
        """
        return cls.model_validate(item)


class CryptoCandleSchema(ApiModel):
    """One candle of a crypto pair."""

    timestamp: dt.datetime | None
    open: float
    high: float
    low: float
    close: float
    volume: float

    @classmethod
    def build(cls, item: CryptoCandle) -> "CryptoCandleSchema":
        """Build the schema from an entity.

        Parameters
        ----------
        item : CryptoCandle
            Candle.

        Returns
        -------
        CryptoCandleSchema
            Response body.
        """
        return cls.model_validate(item)


class OrderBookResponse(ApiModel):
    """Best levels of an order book; levels are `[price, amount]`."""

    exchange: str = Field(examples=["binance"])
    symbol: str = Field(examples=["BTC/USDT"])
    best_bid: float | None
    best_ask: float | None
    spread: float | None
    bids: list[tuple[float, float]]
    asks: list[tuple[float, float]]

    @classmethod
    def build(cls, book: OrderBook) -> "OrderBookResponse":
        """Build the schema from an entity.

        Parameters
        ----------
        book : OrderBook
            Order book.

        Returns
        -------
        OrderBookResponse
            Response body.
        """
        return cls(
            exchange=book.exchange,
            symbol=book.symbol,
            best_bid=book.best_bid,
            best_ask=book.best_ask,
            spread=book.spread,
            bids=list(book.bids),
            asks=list(book.asks),
        )


class GarchParametersSchema(ApiModel):
    """GARCH(1,1) parameters on daily returns in percent."""

    mu: float = Field(description="Mean daily return, %.", examples=[0.06])
    omega: float = Field(examples=[0.05])
    alpha: float = Field(examples=[0.08])
    beta: float = Field(examples=[0.9])
    persistence: float = Field(description="alpha + beta.", examples=[0.98])
    annualized_volatility_percent: float = Field(
        description="Long-run volatility, % per year.", examples=[31.2]
    )

    @classmethod
    def build(cls, item: GarchParameters) -> "GarchParametersSchema":
        """Build the schema from an entity.

        Parameters
        ----------
        item : GarchParameters
            Model.

        Returns
        -------
        GarchParametersSchema
            Response body.
        """
        return cls(
            mu=item.mu,
            omega=item.omega,
            alpha=item.alpha,
            beta=item.beta,
            persistence=item.persistence,
            annualized_volatility_percent=item.annualized_volatility_percent,
        )


class AssetSimulationRequest(ApiModel):
    """Inputs of the GARCH simulation of an asset."""

    ticker: str = Field(description="Yahoo Finance ticker.", examples=["PETR4.SA"])
    horizon_days: int = Field(
        default=126, ge=5, le=756, description="Business days simulated."
    )
    n_paths: int = Field(default=500, ge=100, le=2000, description="Number of paths.")
    history_period: str = Field(
        default="2y", description="History used in the fit: 1y, 2y or 5y."
    )
    seed: int | None = Field(
        default=None,
        ge=0,
        le=2**31 - 1,
        description="Random seed; omitted, a fixed seed makes results repeatable.",
    )


class AssetSimulationResponse(ApiModel):
    """Distribution of the simulated prices of an asset."""

    ticker: str = Field(examples=["PETR4.SA"])
    last_close: float = Field(description="Price the paths start from.")
    last_date: dt.date = Field(description="Day of the last close.")
    n_paths: int
    observations_used: int = Field(description="Daily returns used in the fit.")
    parameters: GarchParametersSchema
    dates: list[dt.date] = Field(description="Future business days of the horizon.")
    percentiles: dict[str, list[float]] = Field(
        description="Price per day for p5, p10, p25, p50, p75, p90 and p95."
    )
    sample_paths: list[list[float]] = Field(description="Five complete paths.")
    final: dict[str, float] = Field(
        description="Final price percentiles and the probability of ending "
        "above the last close (`prob_above_last`, 0 to 1)."
    )

    @classmethod
    def build(cls, fan: SimulationFan) -> "AssetSimulationResponse":
        """Build the schema from an entity.

        Parameters
        ----------
        fan : SimulationFan
            Simulation result.

        Returns
        -------
        AssetSimulationResponse
            Response body.
        """
        final = {key: values[-1] for key, values in fan.percentiles.items()}
        above = sum(1 for price in fan.final_prices if price > fan.last_close)
        final["prob_above_last"] = round(above / len(fan.final_prices), 4)
        return cls(
            ticker=fan.ticker,
            last_close=fan.last_close,
            last_date=fan.last_date,
            n_paths=fan.n_paths,
            observations_used=fan.observations_used,
            parameters=GarchParametersSchema.build(fan.parameters),
            dates=list(fan.dates),
            percentiles={key: list(values) for key, values in fan.percentiles.items()},
            sample_paths=[list(path) for path in fan.sample_paths],
            final=final,
        )


class SyntheticSeriesRequest(ApiModel):
    """Inputs of the synthetic GARCH series (same as the finbrain-mcp tool)."""

    ticker: str = Field(examples=["PETR4.SA"])
    start_date: dt.date = Field(examples=["2026-10-14"])
    n_days: int = Field(ge=1, le=2520, examples=[60])
    value_type: str = Field(default="close", description="open, high, low or close.")
    n_series: int = Field(default=1, ge=1, le=100)
    mode: str = Field(
        default="simulate",
        description="`simulate` uses mu/omega/alpha/beta; `fit_and_simulate` "
        "fits them on `historical_returns` or on the ticker's history.",
    )
    initial_price: float = Field(default=100.0, gt=0)
    mu: float = Field(default=0.0, description="Mean daily return, %.")
    omega: float = Field(default=0.02, gt=0)
    alpha: float = Field(default=0.10, ge=0)
    beta: float = Field(default=0.85, ge=0)
    historical_returns: list[float] | None = Field(
        default=None,
        max_length=10000,
        description="Daily fractional returns (0.01 = 1%), at least 30.",
    )
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)


class SyntheticSeriesResponse(ApiModel):
    """Synthetic series: `series` maps `serie_1`... to the values."""

    value_type: str = Field(examples=["close"])
    dates: list[dt.date]
    series: dict[str, list[float]]
    parameters: GarchParametersSchema
