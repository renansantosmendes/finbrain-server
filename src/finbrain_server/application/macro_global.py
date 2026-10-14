"""Use cases of global economic data (World Bank Open Data)."""

from collections.abc import Callable
from datetime import date

from finbrain_server.application.cache_policy import CachePolicy
from finbrain_server.application.ports import Cache, WorldBankProvider
from finbrain_server.domain.entities import CountryValue, IndicatorInfo
from finbrain_server.domain.exceptions import InvalidParameterError
from finbrain_server.domain.validation import (
    ensure_range,
    normalize_indicator_code,
    parse_country_list,
)

FIRST_YEAR = 1960
MAX_QUERY_LENGTH = 60


class WorldBankService:
    """World Bank indicators with validation and caching.

    Parameters
    ----------
    provider : WorldBankProvider
        Source of the indicators.
    cache : Cache
        Cache shared by the services.
    policy : CachePolicy
        Time to live of each kind of data.
    today : Callable[[], date]
        Current day, used to bound the years.
    """

    def __init__(
        self,
        provider: WorldBankProvider,
        cache: Cache,
        policy: CachePolicy,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._policy = policy
        self._today = today

    def search_indicators(
        self,
        query: str,
        limit: int = 15,
    ) -> list[IndicatorInfo]:
        """Indicators whose name matches a keyword.

        Parameters
        ----------
        query : str
            Keyword, such as ``inflation`` or ``gdp``.
        limit : int
            Maximum number of results (1 to 50).

        Returns
        -------
        list[IndicatorInfo]
            Matching indicators.

        Raises
        ------
        InvalidParameterError
            When the keyword is empty or too long.
        """
        text = str(query or "").strip()
        if not text or len(text) > MAX_QUERY_LENGTH:
            raise InvalidParameterError(
                f"query must have between 1 and {MAX_QUERY_LENGTH} characters."
            )
        ensure_range("limit", limit, 1, 50)
        return self._cache.get_or_load(
            f"wb-search:{text.lower()}:{limit}",
            self._policy.world_bank,
            lambda: self._provider.search_indicators(text, limit),
        )

    def get_indicator(
        self,
        code: str,
        countries: str,
        start_year: int,
        end_year: int,
    ) -> list[CountryValue]:
        """Values of an indicator for countries in a year interval.

        Parameters
        ----------
        code : str
            Indicator code, such as ``FP.CPI.TOTL.ZG``.
        countries : str
            Comma-separated ISO alpha-3 codes, such as ``BRA,USA``.
        start_year : int
            First year.
        end_year : int
            Last year.

        Returns
        -------
        list[CountryValue]
            Values sorted by country and year.

        Raises
        ------
        InvalidParameterError
            When a parameter is not accepted.
        """
        indicator = normalize_indicator_code(code)
        country_list = parse_country_list(countries)
        current_year = self._today().year
        ensure_range("start_year", start_year, FIRST_YEAR, current_year)
        ensure_range("end_year", end_year, FIRST_YEAR, current_year)
        if start_year > end_year:
            raise InvalidParameterError("start_year must not be after end_year.")
        values = self._cache.get_or_load(
            f"wb:{indicator}:{','.join(country_list)}:{start_year}:{end_year}",
            self._policy.world_bank,
            lambda: self._provider.get_indicator(
                indicator, country_list, start_year, end_year
            ),
        )
        return sorted(values, key=lambda item: (item.country, item.year))

    def compare_countries_latest(
        self,
        code: str,
        countries: str,
    ) -> list[CountryValue]:
        """Most recent value of an indicator per country, highest first.

        Parameters
        ----------
        code : str
            Indicator code, such as ``NY.GDP.PCAP.CD``.
        countries : str
            Comma-separated ISO alpha-3 codes.

        Returns
        -------
        list[CountryValue]
            One value per country with data, from highest to lowest.
        """
        indicator = normalize_indicator_code(code)
        country_list = parse_country_list(countries)
        values = self._cache.get_or_load(
            f"wb-latest:{indicator}:{','.join(country_list)}",
            self._policy.world_bank,
            lambda: self._provider.get_indicator(indicator, country_list, None, None),
        )
        latest = {}
        for item in values:
            if item.country not in latest or item.year > latest[item.country].year:
                latest[item.country] = item
        return sorted(latest.values(), key=lambda item: item.value, reverse=True)
