"""Use cases of Brazilian economic data (Central Bank of Brazil)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta

from finbrain_server.application.cache_policy import CachePolicy
from finbrain_server.application.ports import BrazilMacroProvider, Cache
from finbrain_server.domain.entities import (
    EconomicSeries,
    MarketExpectation,
    Observation,
    PtaxQuote,
)
from finbrain_server.domain.exceptions import (
    InvalidParameterError,
    SeriesNotFoundError,
)
from finbrain_server.domain.validation import ensure_date_range, ensure_range

SOURCE = "Banco Central do Brasil · SGS"
MAX_SERIES_DAYS = 3650
MAX_PTAX_DAYS = 1830
LATEST_WINDOW_DAYS = 120
EXPECTATION_INDICATORS = ("IPCA", "Selic", "PIB Total", "Câmbio", "IGP-M")


@dataclass(frozen=True)
class SeriesDefinition:
    """An SGS series offered by the API.

    Parameters
    ----------
    code : int
        SGS code.
    description : str
        What the series measures, with the unit.
    frequency : str
        ``daily`` or ``monthly``.
    """

    code: int
    description: str
    frequency: str


SERIES = {
    "selic": SeriesDefinition(432, "Selic target rate (% per year)", "daily"),
    "cdi": SeriesDefinition(4391, "CDI accumulated in the month (%)", "monthly"),
    "cdi_anual": SeriesDefinition(
        4389, "CDI annualized, 252-day basis (% per year)", "daily"
    ),
    "ipca": SeriesDefinition(433, "IPCA, monthly change (%)", "monthly"),
    "ipca_12m": SeriesDefinition(
        13522, "IPCA accumulated in 12 months (%)", "monthly"
    ),
    "pib": SeriesDefinition(4380, "GDP, monthly (R$ million)", "monthly"),
    "dolar_comercial": SeriesDefinition(
        1, "Commercial dollar, sell rate (R$ per US$)", "daily"
    ),
}


@dataclass(frozen=True)
class BrazilMacroSummary:
    """Latest Selic, CDI and IPCA with the real interest rate.

    Parameters
    ----------
    selic : Observation | None
        Selic target rate, % per year.
    cdi : Observation | None
        Annualized CDI, % per year.
    ipca_12m : Observation | None
        IPCA accumulated in 12 months, %.
    """

    selic: Observation | None
    cdi: Observation | None
    ipca_12m: Observation | None

    @property
    def real_rate(self) -> float | None:
        """CDI discounted by the 12-month IPCA, in percent per year.

        Returns
        -------
        float | None
            ``(1 + CDI) / (1 + IPCA) - 1``, or ``None`` without data.
        """
        if self.cdi is None or self.ipca_12m is None:
            return None
        return ((1 + self.cdi.value / 100) / (1 + self.ipca_12m.value / 100) - 1) * 100


class BrazilMacroService:
    """Central Bank of Brazil series, PTAX and Focus, with caching.

    Parameters
    ----------
    provider : BrazilMacroProvider
        Source of the data.
    cache : Cache
        Cache shared by the services.
    policy : CachePolicy
        Time to live of each kind of data.
    today : Callable[[], date]
        Current day; series values dated after it are ignored.
    """

    def __init__(
        self,
        provider: BrazilMacroProvider,
        cache: Cache,
        policy: CachePolicy,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._policy = policy
        self._today = today

    @staticmethod
    def list_series() -> dict[str, SeriesDefinition]:
        """Series offered by :meth:`get_series`.

        Returns
        -------
        dict[str, SeriesDefinition]
            Definitions by name.
        """
        return dict(SERIES)

    def get_series(
        self,
        name: str,
        start: date | None = None,
        end: date | None = None,
    ) -> EconomicSeries:
        """Observations of a named series in a date interval.

        Parameters
        ----------
        name : str
            Series name, such as ``selic`` (see :meth:`list_series`).
        start : date | None
            First day; defaults to one year before ``end``.
        end : date | None
            Last day; defaults to today.

        Returns
        -------
        EconomicSeries
            Observations in chronological order.

        Raises
        ------
        SeriesNotFoundError
            When the name is not offered.
        """
        definition = SERIES.get(str(name).lower())
        if definition is None:
            raise SeriesNotFoundError(
                f"Unknown series '{name}'. Options: {', '.join(SERIES)}."
            )
        last_day = end or self._today()
        first_day = start or last_day - timedelta(days=365)
        ensure_date_range(first_day, last_day, MAX_SERIES_DAYS)
        pairs = self._cache.get_or_load(
            f"sgs:{definition.code}:{first_day}:{last_day}",
            self._policy.macro,
            lambda: self._provider.get_series(
                definition.code, first_day, last_day, None
            ),
        )
        return EconomicSeries(
            name=str(name).lower(),
            description=definition.description,
            source=SOURCE,
            observations=tuple(Observation(day, value) for day, value in pairs),
        )

    def get_summary(self) -> BrazilMacroSummary:
        """Latest Selic, annualized CDI and 12-month IPCA.

        Returns
        -------
        BrazilMacroSummary
            Most recent value of each indicator up to today.
        """
        return BrazilMacroSummary(
            selic=self._latest(SERIES["selic"].code),
            cdi=self._latest(SERIES["cdi_anual"].code),
            ipca_12m=self._latest(SERIES["ipca_12m"].code),
        )

    def get_ptax(
        self,
        start: date | None = None,
        end: date | None = None,
    ) -> list[PtaxQuote]:
        """Daily PTAX dollar rates of a period.

        Parameters
        ----------
        start : date | None
            First day; defaults to 30 days before ``end``.
        end : date | None
            Last day; defaults to today.

        Returns
        -------
        list[PtaxQuote]
            Rates in chronological order.
        """
        last_day = end or self._today()
        first_day = start or last_day - timedelta(days=30)
        ensure_date_range(first_day, last_day, MAX_PTAX_DAYS)
        return self._cache.get_or_load(
            f"ptax:{first_day}:{last_day}",
            self._policy.macro,
            lambda: self._provider.get_ptax(first_day, last_day),
        )

    def get_expectations(
        self,
        indicator: str,
        reference_year: int,
        limit: int = 5,
    ) -> list[MarketExpectation]:
        """Latest Focus survey statistics of an indicator.

        Parameters
        ----------
        indicator : str
            One of :data:`EXPECTATION_INDICATORS`, such as ``IPCA``.
        reference_year : int
            Year the expectation refers to.
        limit : int
            Number of surveys, most recent first (1 to 50).

        Returns
        -------
        list[MarketExpectation]
            Survey statistics.

        Raises
        ------
        InvalidParameterError
            When the indicator, year or limit is not accepted.
        """
        matches = [
            option
            for option in EXPECTATION_INDICATORS
            if option.lower() == str(indicator).strip().lower()
        ]
        if not matches:
            raise InvalidParameterError(
                "Invalid indicator. Use one of: "
                + ", ".join(EXPECTATION_INDICATORS)
                + "."
            )
        ensure_range("reference_year", reference_year, 2000, 2100)
        ensure_range("limit", limit, 1, 50)
        return self._cache.get_or_load(
            f"focus:{matches[0]}:{reference_year}:{limit}",
            self._policy.macro,
            lambda: self._provider.get_expectations(
                matches[0], str(reference_year), limit
            ),
        )

    def _latest(self, code: int) -> Observation | None:
        """Most recent observation of a series up to today.

        Parameters
        ----------
        code : int
            SGS code.

        Returns
        -------
        Observation | None
            The observation, or ``None`` when the series is empty.
        """
        today = self._today()
        start = today - timedelta(days=LATEST_WINDOW_DAYS)
        pairs = self._cache.get_or_load(
            f"sgs-latest:{code}:{today}",
            self._policy.macro,
            lambda: self._provider.get_series(code, start, today, None),
        )
        past = [(day, value) for day, value in pairs if day <= today]
        if not past:
            return None
        day, value = past[-1]
        return Observation(day, value)
