"""Market data adapter backed by Yahoo Finance (``yfinance``)."""

import math
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import yfinance

from finbrain_server.application.ports import MarketDataProvider
from finbrain_server.domain.entities import (
    FundamentalIndicators,
    PriceBar,
    PriceHistory,
    Quote,
)
from finbrain_server.domain.exceptions import (
    AssetNotFoundError,
    UpstreamUnavailableError,
)


class YFinanceMarketDataProvider(MarketDataProvider):
    """Reads prices and company data from Yahoo Finance.

    Candles with missing or zero prices (Yahoo publishes a placeholder for
    the day before the session opens) are discarded.

    Parameters
    ----------
    ticker_factory : Callable[[str], Any]
        Builds the ``yfinance.Ticker`` of a symbol (replaceable in tests).
    """

    def __init__(
        self,
        ticker_factory: Callable[[str], Any] = yfinance.Ticker,
    ) -> None:
        self._ticker_factory = ticker_factory

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
            Valid candles in chronological order (possibly empty).

        Raises
        ------
        AssetNotFoundError
            When Yahoo Finance does not know the ticker.
        UpstreamUnavailableError
            When Yahoo Finance fails.
        """
        try:
            source = self._ticker_factory(ticker)
            frame = source.history(period=period, interval=interval)
            metadata = getattr(source, "history_metadata", None) or {}
        except KeyError as error:
            raise AssetNotFoundError(f"Unknown ticker '{ticker}'.") from error
        except Exception as error:
            raise UpstreamUnavailableError(
                f"Yahoo Finance did not answer for '{ticker}': {error}"
            ) from error
        bars = []
        for index, row in frame.iterrows():
            prices = [_number(row.get(column)) for column in ("Open", "High", "Low", "Close")]
            if any(price is None or price <= 0 for price in prices):
                continue
            volume = _number(row.get("Volume")) or 0
            bars.append(
                PriceBar(
                    date=index.date(),
                    open=round(prices[0], 4),
                    high=round(prices[1], 4),
                    low=round(prices[2], 4),
                    close=round(prices[3], 4),
                    volume=int(volume),
                )
            )
        return PriceHistory(
            ticker=ticker,
            period=period,
            interval=interval,
            bars=tuple(bars),
            currency=metadata.get("currency"),
        )

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

        Raises
        ------
        AssetNotFoundError
            When Yahoo Finance has no price for the ticker.
        """
        info = self._info(ticker)
        price = _number(info.get("currentPrice")) or _number(
            info.get("regularMarketPrice")
        )
        if price is None:
            raise AssetNotFoundError(f"No quote for ticker '{ticker}'.")
        market_time = info.get("regularMarketTime")
        return Quote(
            ticker=ticker,
            name=info.get("longName") or info.get("shortName"),
            currency=info.get("currency"),
            price=price,
            previous_close=_number(info.get("previousClose"))
            or _number(info.get("regularMarketPreviousClose")),
            fifty_day_average=_number(info.get("fiftyDayAverage")),
            volume=_integer(info.get("volume")),
            average_volume=_integer(info.get("averageVolume")),
            market_time=(
                datetime.fromtimestamp(market_time, tz=timezone.utc)
                if isinstance(market_time, (int, float))
                else None
            ),
        )

    def get_fundamentals(self, ticker: str) -> FundamentalIndicators:
        """Fundamental indicators of a company.

        Parameters
        ----------
        ticker : str
            Yahoo Finance ticker.

        Returns
        -------
        FundamentalIndicators
            Ratios reported by Yahoo Finance.

        Raises
        ------
        AssetNotFoundError
            When Yahoo Finance knows nothing about the ticker.
        """
        info = self._info(ticker)
        if not (info.get("longName") or info.get("shortName") or info.get("quoteType")):
            raise AssetNotFoundError(f"No company data for ticker '{ticker}'.")
        return FundamentalIndicators(
            ticker=ticker,
            name=info.get("longName") or info.get("shortName"),
            sector=info.get("sector"),
            pe_ratio=_number(info.get("trailingPE")),
            pb_ratio=_number(info.get("priceToBook")),
            roe=_number(info.get("returnOnEquity")),
            net_margin=_number(info.get("profitMargins")),
            dividend_yield=_number(info.get("dividendYield")),
            debt_to_equity=_number(info.get("debtToEquity")),
            earnings_per_share=_number(info.get("trailingEps")),
            market_cap=_number(info.get("marketCap")),
            currency=info.get("currency"),
        )

    def _info(self, ticker: str) -> dict[str, Any]:
        """Raw ``info`` dictionary of a ticker.

        Parameters
        ----------
        ticker : str
            Yahoo Finance ticker.

        Returns
        -------
        dict[str, Any]
            Data reported by Yahoo Finance.

        Raises
        ------
        UpstreamUnavailableError
            When Yahoo Finance fails.
        AssetNotFoundError
            When the answer is empty.
        """
        try:
            info = self._ticker_factory(ticker).info or {}
        except Exception as error:
            raise UpstreamUnavailableError(
                f"Yahoo Finance did not answer for '{ticker}': {error}"
            ) from error
        if len(info) <= 1:
            raise AssetNotFoundError(f"Unknown ticker '{ticker}'.")
        return info


def _number(value: Any) -> float | None:
    """Convert a value to a finite float.

    Parameters
    ----------
    value : Any
        Value reported by the source.

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


def _integer(value: Any) -> int | None:
    """Convert a value to an integer.

    Parameters
    ----------
    value : Any
        Value reported by the source.

    Returns
    -------
    int | None
        The integer, or ``None`` when missing.
    """
    number = _number(value)
    return None if number is None else int(number)
