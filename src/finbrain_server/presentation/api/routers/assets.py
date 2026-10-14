"""Routes of stocks, indices and currencies (Yahoo Finance)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from finbrain_server.application.market import MarketDataService
from finbrain_server.presentation.api.dependencies import cache_for, get_market_service
from finbrain_server.presentation.api.error_handlers import INVALID, NOT_FOUND, UPSTREAM
from finbrain_server.presentation.api.schemas import (
    ComparisonRow,
    FundamentalsResponse,
    PriceHistoryResponse,
    QuoteResponse,
    TechnicalResponse,
)

router = APIRouter(prefix="/assets", tags=["Assets"])

Ticker = Annotated[
    str,
    Path(
        description="Yahoo Finance ticker: `PETR4.SA` (B3), `AAPL` (US), "
        "`^BVSP` (Ibovespa), `BRL=X` (USD/BRL).",
        examples=["PETR4.SA"],
    ),
]
Service = Annotated[MarketDataService, Depends(get_market_service)]


@router.get(
    "/compare",
    summary="Compare assets side by side",
    description="Price, day change, P/E and dividend yield of up to 20 "
    "assets. An asset that fails comes with `error` instead of failing the "
    "whole answer. Same data as the finbrain-mcp tool `compare_assets`.",
    response_description="One row per ticker, in the given order.",
    responses=INVALID,
    dependencies=[Depends(cache_for(60))],
)
def compare_assets(
    service: Service,
    tickers: Annotated[
        str,
        Query(description="Comma-separated tickers.", examples=["PETR4.SA,VALE3.SA"]),
    ],
) -> list[ComparisonRow]:
    """Compare several assets.

    Parameters
    ----------
    service : MarketDataService
        Market data service.
    tickers : str
        Comma-separated tickers.

    Returns
    -------
    list[ComparisonRow]
        One row per ticker.
    """
    return [ComparisonRow.build(row) for row in service.compare_assets(tickers)]


@router.get(
    "/{ticker}/quote",
    summary="Current quote of an asset",
    description="Last price, previous close, day change, 50-day average and "
    "volumes. Cached for one minute. Same data as the finbrain-mcp tool "
    "`collect_yfinance_data` without the history.",
    response_description="Current quote.",
    responses={**INVALID, **NOT_FOUND, **UPSTREAM},
    dependencies=[Depends(cache_for(60))],
)
def get_quote(
    service: Service,
    ticker: Ticker,
) -> QuoteResponse:
    """Return the current quote of an asset.

    Parameters
    ----------
    service : MarketDataService
        Market data service.
    ticker : str
        Yahoo Finance ticker.

    Returns
    -------
    QuoteResponse
        Current quote.
    """
    return QuoteResponse.build(service.get_quote(ticker))


@router.get(
    "/{ticker}/history",
    summary="Price history (candles) of an asset",
    description="OHLCV candles of a period and interval, oldest first. "
    "Candles with missing prices are discarded. Cached for 15 minutes.",
    response_description="Candles of the asset.",
    responses={**INVALID, **NOT_FOUND, **UPSTREAM},
    dependencies=[Depends(cache_for(900))],
)
def get_history(
    service: Service,
    ticker: Ticker,
    period: Annotated[
        str,
        Query(description="1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd or max."),
    ] = "1y",
    interval: Annotated[
        str,
        Query(description="1m, 5m, 15m, 30m, 60m, 1h, 1d, 1wk or 1mo."),
    ] = "1d",
) -> PriceHistoryResponse:
    """Return the candles of an asset.

    Parameters
    ----------
    service : MarketDataService
        Market data service.
    ticker : str
        Yahoo Finance ticker.
    period : str
        Period of the history.
    interval : str
        Candle interval.

    Returns
    -------
    PriceHistoryResponse
        Candles of the asset.
    """
    return PriceHistoryResponse.build(service.get_history(ticker, period, interval))


@router.get(
    "/{ticker}/fundamentals",
    summary="Fundamental indicators of a company",
    description="P/E, P/B, ROE, net margin, dividend yield, debt-to-equity, "
    "EPS and market cap. Cached for 6 hours. Same data as the finbrain-mcp "
    "tool `collect_fundamental_indicators`.",
    response_description="Indicators reported by Yahoo Finance.",
    responses={**INVALID, **NOT_FOUND, **UPSTREAM},
    dependencies=[Depends(cache_for(3600))],
)
def get_fundamentals(
    service: Service,
    ticker: Ticker,
) -> FundamentalsResponse:
    """Return the fundamental indicators of a company.

    Parameters
    ----------
    service : MarketDataService
        Market data service.
    ticker : str
        Yahoo Finance ticker.

    Returns
    -------
    FundamentalsResponse
        Company indicators.
    """
    return FundamentalsResponse.build(service.get_fundamentals(ticker))


@router.get(
    "/{ticker}/technical",
    summary="Technical indicators of an asset",
    description="Moving averages of 9, 21 and 50 days, RSI 14 and MACD of the "
    "last close, computed from the daily history. Same data as the "
    "finbrain-mcp tool `collect_technical_indicators`.",
    response_description="Indicators of the last close.",
    responses={**INVALID, **NOT_FOUND, **UPSTREAM},
    dependencies=[Depends(cache_for(900))],
)
def get_technical(
    service: Service,
    ticker: Ticker,
    period: Annotated[
        str, Query(description="1mo, 3mo, 6mo, 1y, 2y or 5y.")
    ] = "3mo",
) -> TechnicalResponse:
    """Return the technical indicators of an asset.

    Parameters
    ----------
    service : MarketDataService
        Market data service.
    ticker : str
        Yahoo Finance ticker.
    period : str
        History used in the computation.

    Returns
    -------
    TechnicalResponse
        Indicators of the last close.
    """
    return TechnicalResponse.build(service.get_technical_indicators(ticker, period))
