"""Validation and normalization rules of request parameters."""

import re
from datetime import date

from finbrain_server.domain.exceptions import InvalidParameterError

TICKER_PATTERN = re.compile(r"^[A-Z0-9^][A-Z0-9.\-=^]{0,19}$")
CRYPTO_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{1,15}/[A-Z0-9]{1,15}$")
INDICATOR_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.]{1,39}$")
COUNTRY_CODE_PATTERN = re.compile(r"^[A-Z]{3}$")

PERIODS = ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max")
INTERVALS = (
    "1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h",
    "1d", "5d", "1wk", "1mo", "3mo",
)
INTRADAY_INTERVALS = ("1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h")
CRYPTO_TIMEFRAMES = ("1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M")
MAX_TICKERS = 20
MAX_COUNTRIES = 20


def normalize_ticker(ticker: str) -> str:
    """Upper-case a Yahoo Finance ticker and check its format.

    Parameters
    ----------
    ticker : str
        Ticker such as ``petr4.sa``, ``^BVSP`` or ``BRL=X``.

    Returns
    -------
    str
        The ticker in upper case.

    Raises
    ------
    InvalidParameterError
        When the ticker has unexpected characters or length.
    """
    normalized = str(ticker or "").strip().upper()
    if not TICKER_PATTERN.match(normalized):
        raise InvalidParameterError(f"Invalid ticker '{ticker}'.")
    return normalized


def parse_ticker_list(tickers: str) -> list[str]:
    """Split a comma-separated list of tickers, without duplicates.

    Parameters
    ----------
    tickers : str
        For example ``PETR4.SA,VALE3.SA,^BVSP``.

    Returns
    -------
    list[str]
        Normalized tickers in the given order.

    Raises
    ------
    InvalidParameterError
        When the list is empty, too long or has an invalid ticker.
    """
    parsed = []
    for item in str(tickers or "").split(","):
        if item.strip():
            ticker = normalize_ticker(item)
            if ticker not in parsed:
                parsed.append(ticker)
    if not parsed:
        raise InvalidParameterError("Inform at least one ticker.")
    if len(parsed) > MAX_TICKERS:
        raise InvalidParameterError(f"Inform at most {MAX_TICKERS} tickers.")
    return parsed


def ensure_choice(
    name: str,
    value: str,
    choices: tuple[str, ...],
) -> str:
    """Check that a value is one of the accepted options.

    Parameters
    ----------
    name : str
        Parameter name used in the error message.
    value : str
        Value received.
    choices : tuple[str, ...]
        Accepted values.

    Returns
    -------
    str
        The value itself.

    Raises
    ------
    InvalidParameterError
        When the value is not accepted.
    """
    if value not in choices:
        raise InvalidParameterError(
            f"Invalid {name} '{value}'. Use one of: {', '.join(choices)}."
        )
    return value


def ensure_range(
    name: str,
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    """Check that a number lies in a closed interval.

    Parameters
    ----------
    name : str
        Parameter name used in the error message.
    value : float
        Value received.
    minimum : float
        Smallest accepted value.
    maximum : float
        Largest accepted value.

    Returns
    -------
    float
        The value itself.

    Raises
    ------
    InvalidParameterError
        When the value is outside the interval.
    """
    if not minimum <= value <= maximum:
        raise InvalidParameterError(
            f"{name} must be between {minimum} and {maximum}."
        )
    return value


def ensure_date_range(
    start: date,
    end: date,
    max_days: int,
) -> None:
    """Check the order and the length of a date interval.

    Parameters
    ----------
    start : date
        First day.
    end : date
        Last day.
    max_days : int
        Longest accepted interval, in days.

    Raises
    ------
    InvalidParameterError
        When ``start`` is after ``end`` or the interval is too long.
    """
    if start > end:
        raise InvalidParameterError("start_date must not be after end_date.")
    if (end - start).days > max_days:
        raise InvalidParameterError(
            f"The interval must have at most {max_days} days."
        )


def normalize_crypto_symbol(symbol: str) -> str:
    """Upper-case a crypto pair such as ``btc/usdt``.

    Parameters
    ----------
    symbol : str
        Pair in the ``BASE/QUOTE`` format.

    Returns
    -------
    str
        The pair in upper case.

    Raises
    ------
    InvalidParameterError
        When the pair is not in the ``BASE/QUOTE`` format.
    """
    normalized = str(symbol or "").strip().upper()
    if not CRYPTO_SYMBOL_PATTERN.match(normalized):
        raise InvalidParameterError(
            f"Invalid pair '{symbol}'. Use the BASE/QUOTE format, e.g. BTC/USDT."
        )
    return normalized


def normalize_indicator_code(code: str) -> str:
    """Upper-case a World Bank indicator code such as ``fp.cpi.totl.zg``.

    Parameters
    ----------
    code : str
        Indicator code.

    Returns
    -------
    str
        The code in upper case.

    Raises
    ------
    InvalidParameterError
        When the code has unexpected characters.
    """
    normalized = str(code or "").strip().upper()
    if not INDICATOR_CODE_PATTERN.match(normalized):
        raise InvalidParameterError(f"Invalid indicator code '{code}'.")
    return normalized


def parse_country_list(countries: str) -> list[str]:
    """Split a comma-separated list of ISO 3166 alpha-3 country codes.

    Parameters
    ----------
    countries : str
        For example ``BRA,USA,CHN``.

    Returns
    -------
    list[str]
        Upper-case codes without duplicates.

    Raises
    ------
    InvalidParameterError
        When the list is empty, too long or has an invalid code.
    """
    parsed = []
    for item in str(countries or "").split(","):
        code = item.strip().upper()
        if not code:
            continue
        if not COUNTRY_CODE_PATTERN.match(code):
            raise InvalidParameterError(f"Invalid country code '{item.strip()}'.")
        if code not in parsed:
            parsed.append(code)
    if not parsed:
        raise InvalidParameterError("Inform at least one country code.")
    if len(parsed) > MAX_COUNTRIES:
        raise InvalidParameterError(f"Inform at most {MAX_COUNTRIES} countries.")
    return parsed
