"""How long each kind of data stays in the cache."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CachePolicy:
    """Time to live, in seconds, of each kind of cached data.

    Prices change during the session, so quotes live for a minute; daily
    candles, company data and economic series change at most once a day.

    Parameters
    ----------
    quote : float
        Current quotes.
    history : float
        Daily and longer candles (also the input of indicators, dashboard and GARCH).
    intraday_history : float
        Intraday candles (1 minute to 1 hour), refreshed while the market is open.
    fundamentals : float
        Company indicators.
    macro : float
        Central Bank of Brazil series, PTAX and Focus.
    world_bank : float
        World Bank indicators and searches.
    crypto_ticker : float
        Crypto 24-hour data.
    crypto_ohlcv : float
        Crypto candles.
    order_book : float
        Crypto order books.
    exchanges : float
        List of crypto exchanges.
    simulation : float
        GARCH fits and simulations.
    """

    quote: float = 60
    history: float = 900
    intraday_history: float = 60
    fundamentals: float = 21600
    macro: float = 21600
    world_bank: float = 86400
    crypto_ticker: float = 15
    crypto_ohlcv: float = 60
    order_book: float = 5
    exchanges: float = 86400
    simulation: float = 3600
