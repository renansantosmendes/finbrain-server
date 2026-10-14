"""In-memory fakes of the ports, so tests never call the real sources."""

from datetime import date, datetime, timedelta, timezone

from finbrain_server.application.ports import (
    BrazilMacroProvider,
    CryptoProvider,
    MarketDataProvider,
    WorldBankProvider,
)
from finbrain_server.domain.entities import (
    CountryValue,
    CryptoCandle,
    CryptoTicker,
    FundamentalIndicators,
    IndicatorInfo,
    MarketExpectation,
    OrderBook,
    PriceBar,
    PriceHistory,
    PtaxQuote,
    Quote,
)
from finbrain_server.domain.exceptions import (
    AssetNotFoundError,
    UpstreamUnavailableError,
)

TODAY = date(2026, 10, 13)


def make_bars(
    count: int,
    start_price: float = 50.0,
    last_day: date = date(2026, 10, 9),
) -> tuple[PriceBar, ...]:
    """Deterministic daily candles ending on ``last_day``.

    Parameters
    ----------
    count : int
        Number of candles.
    start_price : float
        Open of the first candle.
    last_day : date
        Day of the last candle.

    Returns
    -------
    tuple[PriceBar, ...]
        Candles with a wave-shaped close.
    """
    days = []
    day = last_day
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day -= timedelta(days=1)
    days.reverse()
    bars = []
    price = start_price
    for index, current in enumerate(days):
        change = 0.012 if index % 3 else -0.015
        close = price * (1 + change + (index % 7 - 3) * 0.002)
        bars.append(
            PriceBar(
                date=current,
                open=round(price, 4),
                high=round(max(price, close) * 1.01, 4),
                low=round(min(price, close) * 0.99, 4),
                close=round(close, 4),
                volume=1000 + index,
            )
        )
        price = close
    return tuple(bars)


class FakeMarketData(MarketDataProvider):
    """Market data with a fixed universe and call counters."""

    def __init__(self) -> None:
        self.calls = []
        self.unknown = {"XXXX9.SA"}
        self.failing = set()

    def _check(self, ticker: str) -> None:
        """Raise the configured error of a ticker.

        Parameters
        ----------
        ticker : str
            Ticker requested.
        """
        if ticker in self.failing:
            raise UpstreamUnavailableError(f"Source down for {ticker}.")
        if ticker in self.unknown:
            raise AssetNotFoundError(f"Unknown ticker '{ticker}'.")

    def get_history(
        self,
        ticker: str,
        period: str,
        interval: str,
    ) -> PriceHistory:
        """Return deterministic candles.

        Parameters
        ----------
        ticker : str
            Ticker.
        period : str
            Period.
        interval : str
            Interval.

        Returns
        -------
        PriceHistory
            Candles (none for ``EMPTY``).
        """
        self.calls.append(("history", ticker, period, interval))
        self._check(ticker)
        count = {"1mo": 21, "3mo": 63, "6mo": 126, "1y": 250, "2y": 500, "5y": 1250}
        bars = () if ticker == "EMPTY" else make_bars(count.get(period, 250))
        return PriceHistory(ticker, period, interval, bars, "BRL")

    def get_quote(self, ticker: str) -> Quote:
        """Return a fixed quote.

        Parameters
        ----------
        ticker : str
            Ticker.

        Returns
        -------
        Quote
            Quote with price 56.85 and previous close 56.
        """
        self.calls.append(("quote", ticker))
        self._check(ticker)
        return Quote(ticker, f"Name of {ticker}", "BRL", 56.85, 56.0)

    def get_fundamentals(self, ticker: str) -> FundamentalIndicators:
        """Return fixed indicators.

        Parameters
        ----------
        ticker : str
            Ticker.

        Returns
        -------
        FundamentalIndicators
            Indicators with P/E 5.4 and dividend yield 6.5.
        """
        self.calls.append(("fundamentals", ticker))
        self._check(ticker)
        return FundamentalIndicators(
            ticker, f"Name of {ticker}", "Energy", 5.4, 1.5, 0.3, 0.24, 6.5,
            76.0, 10.49, 7.7e11, "BRL",
        )


class FakeBrazilMacro(BrazilMacroProvider):
    """Central Bank data with fixed values; Selic has a future date."""

    def __init__(self) -> None:
        self.calls = []
        self.fail = False

    def get_series(
        self,
        code: int,
        start: date | None,
        end: date | None,
        last: int | None,
    ) -> list[tuple[date, float]]:
        """Return fixed observations of the series used by the API.

        Parameters
        ----------
        code : int
            SGS code.
        start : date | None
            First day.
        end : date | None
            Last day.
        last : int | None
            Number of recent observations.

        Returns
        -------
        list[tuple[date, float]]
            Observations.
        """
        self.calls.append(("series", code, start, end, last))
        if self.fail:
            raise UpstreamUnavailableError("SGS down.")
        data = {
            432: [(date(2026, 10, 10), 13.75), (date(2026, 11, 4), 13.5)],
            4389: [(date(2026, 10, 8), 13.6), (date(2026, 10, 9), 13.65)],
            13522: [(date(2026, 8, 1), 4.22), (date(2026, 9, 1), 4.58)],
        }
        return data.get(code, [(date(2026, 9, 1), 1.0)])

    def get_ptax(
        self,
        start: date,
        end: date,
    ) -> list[PtaxQuote]:
        """Return one PTAX quote.

        Parameters
        ----------
        start : date
            First day.
        end : date
            Last day.

        Returns
        -------
        list[PtaxQuote]
            Quotes.
        """
        self.calls.append(("ptax", start, end))
        return [PtaxQuote(datetime(2026, 10, 9, 13, 7), 4.9886, 4.9892)]

    def get_expectations(
        self,
        indicator: str,
        reference_year: str,
        limit: int,
    ) -> list[MarketExpectation]:
        """Return one Focus statistic.

        Parameters
        ----------
        indicator : str
            Indicator.
        reference_year : str
            Year.
        limit : int
            Number of surveys.

        Returns
        -------
        list[MarketExpectation]
            Statistics.
        """
        self.calls.append(("focus", indicator, reference_year, limit))
        return [
            MarketExpectation(
                indicator, reference_year, date(2026, 10, 9), 5.2, 5.22, 4.5, 5.9, 144
            )
        ]


class FakeWorldBank(WorldBankProvider):
    """World Bank data with fixed values."""

    def __init__(self) -> None:
        self.calls = []

    def search_indicators(
        self,
        query: str,
        limit: int,
    ) -> list[IndicatorInfo]:
        """Return one indicator.

        Parameters
        ----------
        query : str
            Keyword.
        limit : int
            Maximum results.

        Returns
        -------
        list[IndicatorInfo]
            Indicators.
        """
        self.calls.append(("search", query, limit))
        return [IndicatorInfo("FP.CPI.TOTL.ZG", "Inflation, consumer prices (annual %)")]

    def get_indicator(
        self,
        code: str,
        countries: list[str],
        start_year: int | None,
        end_year: int | None,
    ) -> list[CountryValue]:
        """Return two years per country.

        Parameters
        ----------
        code : str
            Indicator.
        countries : list[str]
            Countries.
        start_year : int | None
            First year.
        end_year : int | None
            Last year.

        Returns
        -------
        list[CountryValue]
            Values.
        """
        self.calls.append(("indicator", code, tuple(countries), start_year, end_year))
        values = []
        for offset, country in enumerate(countries):
            values.append(CountryValue(country, 2023, 10.0 + offset))
            values.append(CountryValue(country, 2022, 5.0 + offset))
        return values


class FakeCrypto(CryptoProvider):
    """Crypto data of one exchange."""

    def __init__(self) -> None:
        self.calls = []

    def list_exchanges(self) -> list[str]:
        """Return the supported exchanges.

        Returns
        -------
        list[str]
            Two exchanges.
        """
        self.calls.append(("exchanges",))
        return ["kraken", "binance"]

    def get_ticker(
        self,
        exchange: str,
        symbol: str,
    ) -> CryptoTicker:
        """Return a fixed ticker.

        Parameters
        ----------
        exchange : str
            Exchange.
        symbol : str
            Pair.

        Returns
        -------
        CryptoTicker
            Ticker.
        """
        self.calls.append(("ticker", exchange, symbol))
        return CryptoTicker(
            exchange, symbol, 62000.0, 63000.0, 61000.0, 1.2, 1500.0,
            datetime(2026, 10, 13, tzinfo=timezone.utc),
        )

    def get_ohlcv(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> list[CryptoCandle]:
        """Return ``limit`` candles.

        Parameters
        ----------
        exchange : str
            Exchange.
        symbol : str
            Pair.
        timeframe : str
            Candle size.
        limit : int
            Number of candles.

        Returns
        -------
        list[CryptoCandle]
            Candles.
        """
        self.calls.append(("ohlcv", exchange, symbol, timeframe, limit))
        return [
            CryptoCandle(
                datetime(2026, 10, 1 + index, tzinfo=timezone.utc),
                100.0, 110.0, 90.0, 105.0, 3.0,
            )
            for index in range(limit)
        ]

    def get_order_book(
        self,
        exchange: str,
        symbol: str,
        limit: int,
    ) -> OrderBook:
        """Return a fixed order book.

        Parameters
        ----------
        exchange : str
            Exchange.
        symbol : str
            Pair.
        limit : int
            Levels.

        Returns
        -------
        OrderBook
            Book with a spread of 1.
        """
        self.calls.append(("book", exchange, symbol, limit))
        return OrderBook(exchange, symbol, ((100.0, 1.0), (99.0, 2.0)), ((101.0, 1.5),))
