"""Tests of the pure domain rules: indicators, validation and entities."""

from datetime import date

import pandas as pd
import pytest

from finbrain_server.domain import technical
from finbrain_server.domain.entities import GarchParameters, OrderBook, Quote
from finbrain_server.domain.exceptions import InvalidParameterError
from finbrain_server.domain.validation import (
    ensure_date_range,
    normalize_crypto_symbol,
    normalize_indicator_code,
    normalize_ticker,
    parse_country_list,
    parse_ticker_list,
)

PRICES = [10, 11, 10.5, 12, 11.8, 12.5, 13, 12.2, 12.9, 13.4, 13.1, 14, 13.6, 14.2, 14.8, 14.1]


def test_moving_average_needs_enough_values():
    assert technical.simple_moving_average([1.0, 2.0, 3.0], 2) == 2.5
    assert technical.simple_moving_average([1.0], 2) is None


def test_ema_and_macd_match_pandas():
    series = pd.Series(PRICES, dtype=float)
    expected = series.ewm(span=12, adjust=False).mean().tolist()
    assert technical.exponential_moving_average(PRICES, 12) == pytest.approx(expected)
    line = series.ewm(span=12, adjust=False).mean() - series.ewm(span=26, adjust=False).mean()
    signal = line.ewm(span=9, adjust=False).mean()
    assert technical.macd(PRICES) == pytest.approx((line.iloc[-1], signal.iloc[-1]))
    assert technical.macd([]) == (None, None)


def test_rsi_matches_the_mcp_formula():
    series = pd.Series(PRICES, dtype=float)
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    expected = 100 - 100 / (1 + gain / loss)
    assert technical.relative_strength_index(PRICES) == pytest.approx(expected.iloc[-1])
    assert technical.relative_strength_index(PRICES[:5]) is None
    assert technical.relative_strength_index([float(x) for x in range(1, 20)]) == 100.0
    assert technical.relative_strength_index([5.0] * 20) == 50.0


def test_daily_returns_skip_non_positive_prices():
    assert technical.daily_returns([10.0, 11.0, 0.0, 5.0]) == pytest.approx([0.1, -1.0])


@pytest.mark.parametrize("ticker", ["petr4.sa", "^BVSP", "BRL=X", "AAPL", "BRK-B"])
def test_valid_tickers_are_upper_cased(ticker):
    assert normalize_ticker(ticker) == ticker.upper()


@pytest.mark.parametrize("ticker", ["", "bad t", "a/b", "x" * 21, "../etc"])
def test_invalid_tickers_are_rejected(ticker):
    with pytest.raises(InvalidParameterError):
        normalize_ticker(ticker)


def test_ticker_lists_are_deduplicated_and_bounded():
    assert parse_ticker_list("petr4.sa, VALE3.SA,PETR4.SA,") == ["PETR4.SA", "VALE3.SA"]
    with pytest.raises(InvalidParameterError):
        parse_ticker_list(" , ")
    with pytest.raises(InvalidParameterError):
        parse_ticker_list(",".join(f"T{index}" for index in range(21)))


def test_crypto_symbols_indicator_codes_and_countries():
    assert normalize_crypto_symbol("btc/usdt") == "BTC/USDT"
    assert normalize_indicator_code("fp.cpi.totl.zg") == "FP.CPI.TOTL.ZG"
    assert parse_country_list("bra, usa,BRA") == ["BRA", "USA"]
    for call, value in (
        (normalize_crypto_symbol, "BTCUSDT"),
        (normalize_indicator_code, "FP;DROP"),
        (parse_country_list, "BR"),
        (parse_country_list, ""),
    ):
        with pytest.raises(InvalidParameterError):
            call(value)


def test_date_ranges_must_be_ordered_and_bounded():
    ensure_date_range(date(2026, 1, 1), date(2026, 2, 1), 60)
    with pytest.raises(InvalidParameterError):
        ensure_date_range(date(2026, 2, 1), date(2026, 1, 1), 60)
    with pytest.raises(InvalidParameterError):
        ensure_date_range(date(2020, 1, 1), date(2026, 1, 1), 60)


def test_entities_derived_values():
    assert Quote("A", None, None, 56.85, 56.0).day_change_percent == 1.52
    assert Quote("A", None, None, None, 56.0).day_change_percent is None
    book = OrderBook("x", "BTC/USDT", ((100.0, 1.0),), ((101.0, 1.0),))
    assert (book.best_bid, book.best_ask, book.spread) == (100.0, 101.0, 1.0)
    assert OrderBook("x", "BTC/USDT", (), ()).spread is None
    model = GarchParameters(mu=0.0, omega=0.02, alpha=0.1, beta=0.85)
    assert model.persistence == pytest.approx(0.95)
    assert model.long_run_variance == pytest.approx(0.4)
    assert model.annualized_volatility_percent == pytest.approx((0.4 * 252) ** 0.5)
