"""Route that loads everything the Dashboards screen needs at once."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from finbrain_server.application.macro_brasil import BrazilMacroService
from finbrain_server.application.market import AssetSnapshot, MarketDataService
from finbrain_server.domain.exceptions import DomainError
from finbrain_server.domain.validation import parse_ticker_list
from finbrain_server.presentation.api.dependencies import (
    cache_for,
    get_default_watchlist,
    get_macro_brasil_service,
    get_market_service,
)
from finbrain_server.presentation.api.error_handlers import INVALID
from finbrain_server.presentation.api.routers.macro_brasil import summary_response
from finbrain_server.presentation.api.schemas import (
    DashboardAsset,
    DashboardResponse,
    PriceBarSchema,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "",
    summary="Watchlist and Brazilian rates in one request",
    description="Daily candles of every watchlist asset (loaded in parallel "
    "and cached) plus the latest Selic, CDI and 12-month IPCA. Assets that "
    "fail come with `error_code` and the others are still returned, so the "
    "screen can show partial data. Without `tickers`, the server watchlist "
    "is used (`FINBRAIN_WATCHLIST`).",
    response_description="Assets with candles and the macro summary.",
    responses=INVALID,
    dependencies=[Depends(cache_for(300))],
)
def get_dashboard(
    market: Annotated[MarketDataService, Depends(get_market_service)],
    macro: Annotated[BrazilMacroService, Depends(get_macro_brasil_service)],
    default_watchlist: Annotated[str, Depends(get_default_watchlist)],
    tickers: Annotated[
        str | None,
        Query(
            description="Comma-separated Yahoo Finance tickers (up to 20).",
            examples=["PETR4.SA,VALE3.SA,ITUB4.SA,^BVSP,AAPL,BRL=X"],
        ),
    ] = None,
    period: Annotated[
        str, Query(description="Period of the candles: 1mo, 3mo, 6mo, 1y or 2y.")
    ] = "1y",
) -> DashboardResponse:
    """Return the data of the Dashboards screen.

    Parameters
    ----------
    market : MarketDataService
        Market data service.
    macro : BrazilMacroService
        Brazilian macro service.
    default_watchlist : str
        Tickers used when ``tickers`` is omitted.
    tickers : str | None
        Comma-separated tickers.
    period : str
        Period of the candles.

    Returns
    -------
    DashboardResponse
        Assets and the macro summary.
    """
    symbols = parse_ticker_list(tickers or default_watchlist)
    snapshots = market.get_snapshots(symbols, period)
    try:
        macro_summary = summary_response(macro.get_summary())
        macro_error = None
    except DomainError as error:
        macro_summary = None
        macro_error = error.message
    return DashboardResponse(
        generated_at=datetime.now(timezone.utc),
        period=period,
        assets=[_asset(snapshot) for snapshot in snapshots],
        macro=macro_summary,
        macro_error=macro_error,
    )


def _asset(snapshot: AssetSnapshot) -> DashboardAsset:
    """Build the dashboard entry of one asset.

    Parameters
    ----------
    snapshot : AssetSnapshot
        History or error of the asset.

    Returns
    -------
    DashboardAsset
        Entry with candles and the day change.
    """
    if snapshot.history is None:
        return DashboardAsset(
            ticker=snapshot.ticker,
            error_code=snapshot.error_code,
            error_message=snapshot.error_message,
        )
    bars = snapshot.history.bars
    last = bars[-1]
    previous = bars[-2].close if len(bars) > 1 else None
    return DashboardAsset(
        ticker=snapshot.ticker,
        currency=snapshot.history.currency,
        last_close=last.close,
        previous_close=previous,
        day_change_percent=(
            round((last.close / previous - 1) * 100, 4) if previous else None
        ),
        last_date=last.date,
        bars=[PriceBarSchema.build(bar) for bar in bars],
    )
