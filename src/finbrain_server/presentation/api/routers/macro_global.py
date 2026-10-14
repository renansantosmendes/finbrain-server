"""Routes of global economic data (World Bank)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from fastapi import HTTPException
from finbrain_server.presentation.api.dependencies import (
    cache_for,
)  # World Bank endpoints removed
from finbrain_server.presentation.api.error_handlers import INVALID, UPSTREAM, error_doc
from finbrain_server.presentation.api.schemas import (
    CountryValueSchema,
    IndicatorInfoSchema,
)

router = APIRouter(prefix="/macro/global", tags=["Macro global"]) 


# Service = Annotated[WorldBankService, Depends(get_world_bank_service)]
IndicatorCode = Annotated[
    str,
    Path(
        description="World Bank code: `NY.GDP.MKTP.CD` (GDP), `NY.GDP.PCAP.CD` "
        "(GDP per capita), `FP.CPI.TOTL.ZG` (inflation), `SL.UEM.TOTL.ZS` "
        "(unemployment), `SP.POP.TOTL` (population).",
        examples=["FP.CPI.TOTL.ZG"],
    ),
]
Countries = Annotated[
    str,
    Query(description="Comma-separated ISO alpha-3 codes.", examples=["BRA,USA,CHN"]),
]
NOT_FOUND = {404: error_doc("Unknown indicator (`series_not_found`).")}


# @router.get(
#     "/indicators",
#     summary="Search World Bank indicators",
#     description="Indicators whose name matches a keyword, with their codes. "
#     "Same purpose as the finbrain-mcp tool `search_world_bank_indicator`.",
#     response_description="Matching indicators.",
#     responses={**INVALID, **UPSTREAM},
#     dependencies=[Depends(cache_for(86400))],
# )
def search_indicators(
    query: Annotated[str, Query(description="Keyword.", examples=["inflation"])],
    limit: Annotated[int, Query(description="Maximum results (1 to 50).")] = 15,
) -> list[IndicatorInfoSchema]:
    """Search indicators by keyword.

    Parameters
    ----------
    service : WorldBankService
        World Bank service.
    query : str
        Keyword.
    limit : int
        Maximum results.

    Returns
    -------
    list[IndicatorInfoSchema]
        Matching indicators.
    """
    raise HTTPException(status_code=404, detail="World Bank endpoints are disabled in this deployment")


@router.get(
    "/indicators/{code}",
    summary="Values of an indicator by country and year",
    description="Yearly values of an indicator for up to 20 countries. Same "
    "data as the finbrain-mcp tool `get_world_bank_indicator`.",
    response_description="Values sorted by country and year.",
    responses={**NOT_FOUND, **INVALID, **UPSTREAM},
    dependencies=[Depends(cache_for(86400))],
)
def get_indicator(
    code: IndicatorCode,
    countries: Countries,
    start_year: Annotated[int, Query(description="First year.", examples=[2015])],
    end_year: Annotated[int, Query(description="Last year.", examples=[2024])],
) -> list[CountryValueSchema]:
    """Return the values of an indicator.

    Parameters
    ----------
    service : WorldBankService
        World Bank service.
    code : str
        Indicator code.
    countries : str
        Comma-separated country codes.
    start_year : int
        First year.
    end_year : int
        Last year.

    Returns
    -------
    list[CountryValueSchema]
        Values by country and year.
    """
    raise HTTPException(status_code=404, detail="World Bank endpoints are disabled in this deployment")


@router.get(
    "/indicators/{code}/latest",
    summary="Latest value of an indicator per country, ranked",
    description="Most recent available value for each country, from the "
    "highest to the lowest. Same data as the finbrain-mcp tool "
    "`compare_countries_latest`.",
    response_description="One value per country.",
    responses={**NOT_FOUND, **INVALID, **UPSTREAM},
    dependencies=[Depends(cache_for(86400))],
)
def compare_countries_latest(
    code: IndicatorCode,
    countries: Countries,
) -> list[CountryValueSchema]:
    """Return the latest value of each country.

    Parameters
    ----------
    service : WorldBankService
        World Bank service.
    code : str
        Indicator code.
    countries : str
        Comma-separated country codes.

    Returns
    -------
    list[CountryValueSchema]
        Ranked values.
    """
    raise HTTPException(status_code=404, detail="World Bank endpoints are disabled in this deployment")
