"""Adapter of the Central Bank of Brazil APIs (``python-bcb``)."""

import math
from datetime import date
from typing import Any

from bcb import PTAX, Expectativas, sgs

from finbrain_server.application.ports import BrazilMacroProvider
from finbrain_server.domain.entities import MarketExpectation, PtaxQuote
from finbrain_server.domain.exceptions import UpstreamUnavailableError


class BcbMacroProvider(BrazilMacroProvider):
    """Reads SGS series, PTAX rates and the Focus survey.

    Parameters
    ----------
    sgs_module : Any
        Module with ``get`` (``bcb.sgs``; replaceable in tests).
    ptax_factory : Any
        Builds the PTAX client (``bcb.PTAX``).
    expectations_factory : Any
        Builds the Focus client (``bcb.Expectativas``).
    """

    def __init__(
        self,
        sgs_module: Any = sgs,
        ptax_factory: Any = PTAX,
        expectations_factory: Any = Expectativas,
    ) -> None:
        self._sgs = sgs_module
        self._ptax_factory = ptax_factory
        self._expectations_factory = expectations_factory

    def get_series(
        self,
        code: int,
        start: date | None,
        end: date | None,
        last: int | None,
    ) -> list[tuple[date, float]]:
        """Observations of an SGS series.

        Parameters
        ----------
        code : int
            SGS code of the series.
        start : date | None
            First day (with ``end``).
        end : date | None
            Last day (with ``start``).
        last : int | None
            Number of most recent observations, instead of the dates.

        Returns
        -------
        list[tuple[date, float]]
            ``(date, value)`` pairs in chronological order.

        Raises
        ------
        UpstreamUnavailableError
            When the Central Bank API fails.
        """
        try:
            if last is not None:
                frame = self._sgs.get({"value": code}, last=last)
            else:
                frame = self._sgs.get(
                    {"value": code}, start=start.isoformat(), end=end.isoformat()
                )
        except Exception as error:
            raise UpstreamUnavailableError(
                f"The Central Bank SGS API failed for series {code}: {error}"
            ) from error
        pairs = []
        for index, row in frame.iterrows():
            value = _number(row.iloc[0])
            if value is not None:
                pairs.append((index.date(), value))
        return sorted(pairs)

    def get_ptax(
        self,
        start: date,
        end: date,
    ) -> list[PtaxQuote]:
        """Daily PTAX dollar rates of a period.

        Parameters
        ----------
        start : date
            First day.
        end : date
            Last day.

        Returns
        -------
        list[PtaxQuote]
            Rates in chronological order.

        Raises
        ------
        UpstreamUnavailableError
            When the Central Bank API fails.
        """
        try:
            endpoint = self._ptax_factory().get_endpoint("CotacaoDolarPeriodo")
            frame = (
                endpoint.query()
                .parameters(
                    dataInicial=start.strftime("%m-%d-%Y"),
                    dataFinalCotacao=end.strftime("%m-%d-%Y"),
                )
                .collect()
            )
        except Exception as error:
            raise UpstreamUnavailableError(
                f"The Central Bank PTAX API failed: {error}"
            ) from error
        quotes = [
            PtaxQuote(
                timestamp=row["dataHoraCotacao"].to_pydatetime(),
                buy=float(row["cotacaoCompra"]),
                sell=float(row["cotacaoVenda"]),
            )
            for _, row in frame.iterrows()
        ]
        return sorted(quotes, key=lambda quote: quote.timestamp)

    def get_expectations(
        self,
        indicator: str,
        reference_year: str,
        limit: int,
    ) -> list[MarketExpectation]:
        """Latest Focus survey statistics of an indicator.

        Only the statistics over all respondents (``baseCalculo = 0``) are
        returned.

        Parameters
        ----------
        indicator : str
            Focus indicator name, such as ``IPCA``.
        reference_year : str
            Year the expectation refers to.
        limit : int
            Number of surveys, most recent first.

        Returns
        -------
        list[MarketExpectation]
            Survey statistics.

        Raises
        ------
        UpstreamUnavailableError
            When the Central Bank API fails.
        """
        try:
            endpoint = self._expectations_factory().get_endpoint(
                "ExpectativasMercadoAnuais"
            )
            frame = (
                endpoint.query()
                .filter(
                    endpoint.Indicador == indicator,
                    endpoint.DataReferencia == reference_year,
                )
                .orderby(endpoint.Data.desc())
                .limit(limit * 4)
                .collect()
            )
        except Exception as error:
            raise UpstreamUnavailableError(
                f"The Central Bank Focus API failed: {error}"
            ) from error
        expectations = []
        for _, row in frame.iterrows():
            if "baseCalculo" in row and int(row["baseCalculo"]) != 0:
                continue
            if row.get("IndicadorDetalhe") not in (None, "") and not _is_nan(
                row.get("IndicadorDetalhe")
            ):
                continue
            expectations.append(
                MarketExpectation(
                    indicator=str(row["Indicador"]),
                    reference_year=str(row["DataReferencia"]),
                    survey_date=row["Data"].date(),
                    mean=_number(row.get("Media")),
                    median=_number(row.get("Mediana")),
                    minimum=_number(row.get("Minimo")),
                    maximum=_number(row.get("Maximo")),
                    respondents=(
                        None
                        if _number(row.get("numeroRespondentes")) is None
                        else int(row["numeroRespondentes"])
                    ),
                )
            )
        return expectations[:limit]


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


def _is_nan(value: Any) -> bool:
    """Tell whether a value is a float NaN.

    Parameters
    ----------
    value : Any
        Value to check.

    Returns
    -------
    bool
        ``True`` for NaN.
    """
    return isinstance(value, float) and math.isnan(value)
