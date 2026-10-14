"""Routes of Brazilian economic data (Central Bank of Brazil)."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from finbrain_server.application.macro_brasil import (
    SOURCE,
    BrazilMacroService,
    BrazilMacroSummary,
)
from finbrain_server.presentation.api.dependencies import (
    cache_for,
    get_macro_brasil_service,
)
from finbrain_server.presentation.api.error_handlers import INVALID, UPSTREAM, error_doc
from finbrain_server.presentation.api.schemas import (
    EconomicSeriesResponse,
    ExpectationSchema,
    MacroBrasilSummaryResponse,
    ObservationSchema,
    PtaxQuoteSchema,
    SeriesInfoResponse,
)

router = APIRouter(prefix="/macro/brasil", tags=["Macro Brasil"])

Service = Annotated[BrazilMacroService, Depends(get_macro_brasil_service)]
StartDate = Annotated[
    date | None, Query(description="First day (YYYY-MM-DD).", examples=["2025-10-01"])
]
EndDate = Annotated[
    date | None,
    Query(description="Last day (YYYY-MM-DD); defaults to today.", examples=["2026-10-13"]),
]


def summary_response(summary: BrazilMacroSummary) -> MacroBrasilSummaryResponse:
    """Build the response of the macro summary.

    Parameters
    ----------
    summary : BrazilMacroSummary
        Latest rates.

    Returns
    -------
    MacroBrasilSummaryResponse
        Response body.
    """
    def observation(item: object) -> ObservationSchema | None:
        """Convert an optional observation.

        Parameters
        ----------
        item : object
            Observation or ``None``.

        Returns
        -------
        ObservationSchema | None
            Schema or ``None``.
        """
        return None if item is None else ObservationSchema.model_validate(item)

    real_rate = summary.real_rate
    return MacroBrasilSummaryResponse(
        selic=observation(summary.selic),
        cdi=observation(summary.cdi),
        ipca_12m=observation(summary.ipca_12m),
        real_rate=None if real_rate is None else round(real_rate, 4),
        source=SOURCE,
    )


@router.get(
    "/summary",
    summary="Latest Selic, CDI, IPCA 12 months and real rate",
    description="Most recent Selic target, annualized CDI and 12-month IPCA, "
    "with the real interest rate. Cached for 6 hours.",
    response_description="Latest Brazilian rates.",
    responses=UPSTREAM,
    dependencies=[Depends(cache_for(3600))],
)
def get_summary(service: Service) -> MacroBrasilSummaryResponse:
    """Return the latest Brazilian rates.

    Parameters
    ----------
    service : BrazilMacroService
        Brazilian macro service.

    Returns
    -------
    MacroBrasilSummaryResponse
        Latest rates.
    """
    return summary_response(service.get_summary())


@router.get(
    "/series",
    summary="Series offered by the API",
    description="Names, SGS codes and units of the Central Bank series that "
    "`/macro/brasil/series/{name}` accepts.",
    response_description="Catalog of series.",
    dependencies=[Depends(cache_for(86400))],
)
def list_series(service: Service) -> list[SeriesInfoResponse]:
    """Return the catalog of series.

    Parameters
    ----------
    service : BrazilMacroService
        Brazilian macro service.

    Returns
    -------
    list[SeriesInfoResponse]
        One entry per series.
    """
    return [
        SeriesInfoResponse(
            name=name,
            code=item.code,
            description=item.description,
            frequency=item.frequency,
        )
        for name, item in service.list_series().items()
    ]


@router.get(
    "/series/{name}",
    summary="Observations of a Central Bank series",
    description="SGS series by name (see `/macro/brasil/series`), up to 10 "
    "years. Without dates, the last 12 months. Same data as the finbrain-mcp "
    "tool `get_bcb_series`.",
    response_description="Observations, oldest first.",
    responses={
        404: error_doc("Unknown series (`series_not_found`)."),
        **INVALID,
        **UPSTREAM,
    },
    dependencies=[Depends(cache_for(3600))],
)
def get_series(
    service: Service,
    name: Annotated[str, Path(description="Series name.", examples=["selic"])],
    start_date: StartDate = None,
    end_date: EndDate = None,
) -> EconomicSeriesResponse:
    """Return the observations of a series.

    Parameters
    ----------
    service : BrazilMacroService
        Brazilian macro service.
    name : str
        Series name.
    start_date : date | None
        First day.
    end_date : date | None
        Last day.

    Returns
    -------
    EconomicSeriesResponse
        Observations of the series.
    """
    return EconomicSeriesResponse.build(service.get_series(name, start_date, end_date))


@router.get(
    "/ptax",
    summary="PTAX dollar rates of a period",
    description="Daily buy and sell PTAX rates, up to 5 years. Without dates, "
    "the last 30 days. Same data as the finbrain-mcp tool "
    "`get_ptax_dolar_periodo` (dates here are ISO, YYYY-MM-DD).",
    response_description="Rates, oldest first.",
    responses={**INVALID, **UPSTREAM},
    dependencies=[Depends(cache_for(3600))],
)
def get_ptax(
    service: Service,
    start_date: StartDate = None,
    end_date: EndDate = None,
) -> list[PtaxQuoteSchema]:
    """Return the PTAX rates of a period.

    Parameters
    ----------
    service : BrazilMacroService
        Brazilian macro service.
    start_date : date | None
        First day.
    end_date : date | None
        Last day.

    Returns
    -------
    list[PtaxQuoteSchema]
        Daily rates.
    """
    return [PtaxQuoteSchema.build(item) for item in service.get_ptax(start_date, end_date)]


@router.get(
    "/expectations",
    summary="Market expectations (Focus survey)",
    description="Latest Focus statistics (mean, median, min, max, "
    "respondents) of an indicator for a reference year. Same data as the "
    "finbrain-mcp tool `get_market_expectations`.",
    response_description="Surveys, most recent first.",
    responses={**INVALID, **UPSTREAM},
    dependencies=[Depends(cache_for(3600))],
)
def get_expectations(
    service: Service,
    indicator: Annotated[
        str, Query(description="IPCA, Selic, PIB Total, Câmbio or IGP-M.", examples=["IPCA"])
    ],
    reference_year: Annotated[int, Query(description="Year of the expectation.", examples=[2026])],
    limit: Annotated[int, Query(description="Number of surveys (1 to 50).")] = 5,
) -> list[ExpectationSchema]:
    """Return the Focus expectations of an indicator.

    Parameters
    ----------
    service : BrazilMacroService
        Brazilian macro service.
    indicator : str
        Focus indicator.
    reference_year : int
        Year of the expectation.
    limit : int
        Number of surveys.

    Returns
    -------
    list[ExpectationSchema]
        Survey statistics.
    """
    return [
        ExpectationSchema.build(item)
        for item in service.get_expectations(indicator, reference_year, limit)
    ]
