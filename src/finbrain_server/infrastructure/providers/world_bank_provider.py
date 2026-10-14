"""Adapter of the World Bank Open Data API (``wbdata``)."""

import math
from typing import Any

import wbdata

from finbrain_server.application.ports import WorldBankProvider
from finbrain_server.domain.entities import CountryValue, IndicatorInfo
from finbrain_server.domain.exceptions import (
    SeriesNotFoundError,
    UpstreamUnavailableError,
)


class WbdataWorldBankProvider(WorldBankProvider):
    """Reads World Bank indicators.

    Parameters
    ----------
    client : Any
        Module or object with ``get_indicators`` and ``get_data``
        (``wbdata``; replaceable in tests).
    """

    def __init__(self, client: Any = wbdata) -> None:
        self._client = client

    def search_indicators(
        self,
        query: str,
        limit: int,
    ) -> list[IndicatorInfo]:
        """Indicators whose name matches a keyword.

        Parameters
        ----------
        query : str
            Keyword, such as ``inflation``.
        limit : int
            Maximum number of results.

        Returns
        -------
        list[IndicatorInfo]
            Matching indicators.

        Raises
        ------
        UpstreamUnavailableError
            When the World Bank API fails.
        """
        try:
            results = list(self._client.get_indicators(query=query))
        except Exception as error:
            raise UpstreamUnavailableError(
                f"The World Bank API failed: {error}"
            ) from error
        return [
            IndicatorInfo(code=str(item["id"]), name=str(item["name"]))
            for item in results[:limit]
        ]

    def get_indicator(
        self,
        code: str,
        countries: list[str],
        start_year: int | None,
        end_year: int | None,
    ) -> list[CountryValue]:
        """Values of an indicator for countries and years.

        Parameters
        ----------
        code : str
            Indicator code, such as ``FP.CPI.TOTL.ZG``.
        countries : list[str]
            ISO alpha-3 country codes.
        start_year : int | None
            First year, or ``None`` for every available year.
        end_year : int | None
            Last year, or ``None`` for every available year.

        Returns
        -------
        list[CountryValue]
            Non-empty values.

        Raises
        ------
        SeriesNotFoundError
            When the indicator does not exist.
        UpstreamUnavailableError
            When the World Bank API fails.
        """
        options = {"country": countries}
        if start_year is not None and end_year is not None:
            options["date"] = (str(start_year), str(end_year))
        try:
            rows = list(self._client.get_data(code, **options) or [])
        except Exception as error:
            if "invalid" in str(error).lower() or "not found" in str(error).lower():
                raise SeriesNotFoundError(
                    f"Unknown World Bank indicator '{code}'."
                ) from error
            raise UpstreamUnavailableError(
                f"The World Bank API failed: {error}"
            ) from error
        values = []
        for row in rows:
            value = _number(row.get("value"))
            year = str(row.get("date", ""))
            country = row.get("countryiso3code") or (row.get("country") or {}).get("id")
            if value is None or not year.isdigit() or not country:
                continue
            values.append(CountryValue(country=str(country), year=int(year), value=value))
        return values


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
