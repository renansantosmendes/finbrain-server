"""Tests of the services: validation, caching and composition of data."""

import random
from datetime import date

import pytest

from finbrain_server.application.simulations import (
    SyntheticRequest,
    business_days_after,
)
from finbrain_server.domain.entities import GarchParameters
from finbrain_server.domain.exceptions import (
    AssetNotFoundError,
    ExchangeNotFoundError,
    InvalidParameterError,
    SeriesNotFoundError,
    SimulationError,
)


def test_history_is_cached_by_ticker_period_and_interval(market_service, market_provider):
    first = market_service.get_history("petr4.sa", "1y", "1d")
    second = market_service.get_history("PETR4.SA", "1y", "1d")
    assert first is second
    assert market_provider.calls == [("history", "PETR4.SA", "1y", "1d")]
    market_service.get_history("PETR4.SA", "3mo", "1d")
    assert len(market_provider.calls) == 2


def test_history_validates_parameters_and_empty_answers(market_service):
    with pytest.raises(InvalidParameterError):
        market_service.get_history("PETR4.SA", "7y", "1d")
    with pytest.raises(InvalidParameterError):
        market_service.get_history("PETR4.SA", "1y", "2d")
    with pytest.raises(AssetNotFoundError):
        market_service.get_history("EMPTY", "1y", "1d")
    with pytest.raises(AssetNotFoundError):
        market_service.get_history("XXXX9.SA", "1y", "1d")


def test_errors_are_not_cached(market_service, market_provider):
    market_provider.failing.add("VALE3.SA")
    with pytest.raises(Exception):
        market_service.get_quote("VALE3.SA")
    market_provider.failing.clear()
    assert market_service.get_quote("VALE3.SA").price == 56.85


def test_technical_indicators_come_from_the_daily_history(market_service):
    result = market_service.get_technical_indicators("PETR4.SA", "3mo")
    assert result.period == "3mo"
    assert result.moving_average_50 is not None
    assert 0 <= result.rsi_14 <= 100
    short = market_service.get_technical_indicators("PETR4.SA", "1mo")
    assert short.moving_average_50 is None
    with pytest.raises(InvalidParameterError):
        market_service.get_technical_indicators("PETR4.SA", "1d")


def test_comparison_keeps_failed_assets_as_rows(market_service):
    rows = market_service.compare_assets("PETR4.SA,XXXX9.SA")
    assert [row.ticker for row in rows] == ["PETR4.SA", "XXXX9.SA"]
    assert rows[0].pe_ratio == 5.4 and rows[0].day_change_percent == 1.52
    assert rows[1].error and rows[1].current_price is None


def test_snapshots_report_errors_per_asset(market_service):
    snapshots = market_service.get_snapshots(["PETR4.SA", "XXXX9.SA"], "1y")
    assert len(snapshots[0].history.bars) == 250
    assert snapshots[1].history is None
    assert snapshots[1].error_code == "asset_not_found"
    with pytest.raises(InvalidParameterError):
        market_service.get_snapshots(["PETR4.SA"], "max")


def test_macro_summary_ignores_future_dates_and_computes_real_rate(macro_service):
    summary = macro_service.get_summary()
    assert summary.selic.date == date(2026, 10, 10) and summary.selic.value == 13.75
    assert summary.cdi.value == 13.65 and summary.ipca_12m.value == 4.58
    assert summary.real_rate == pytest.approx((1.1365 / 1.0458 - 1) * 100)


def test_macro_series_defaults_and_validation(macro_service, macro_provider):
    series = macro_service.get_series("IPCA_12M")
    assert series.name == "ipca_12m" and len(series.observations) == 2
    assert macro_provider.calls[-1] == ("series", 13522, date(2025, 10, 13), date(2026, 10, 13), None)
    with pytest.raises(SeriesNotFoundError):
        macro_service.get_series("bitcoin")
    with pytest.raises(InvalidParameterError):
        macro_service.get_series("selic", date(2000, 1, 1), date(2026, 1, 1))
    assert "selic" in macro_service.list_series()


def test_ptax_and_expectations(macro_service, macro_provider):
    assert macro_service.get_ptax()[0].sell == 4.9892
    assert macro_provider.calls[-1] == ("ptax", date(2026, 9, 13), date(2026, 10, 13))
    assert macro_service.get_expectations("ipca", 2026)[0].median == 5.22
    assert macro_provider.calls[-1] == ("focus", "IPCA", "2026", 5)
    with pytest.raises(InvalidParameterError):
        macro_service.get_expectations("bitcoin", 2026)
    with pytest.raises(InvalidParameterError):
        macro_service.get_expectations("IPCA", 1990)


def test_world_bank_service(world_bank_service):
    assert world_bank_service.search_indicators("inflation")[0].code == "FP.CPI.TOTL.ZG"
    values = world_bank_service.get_indicator("fp.cpi.totl.zg", "usa,bra", 2020, 2023)
    assert [(item.country, item.year) for item in values][:2] == [("BRA", 2022), ("BRA", 2023)]
    latest = world_bank_service.compare_countries_latest("NY.GDP.PCAP.CD", "BRA,USA")
    assert [(item.country, item.year, item.value) for item in latest] == [
        ("USA", 2023, 11.0),
        ("BRA", 2023, 10.0),
    ]
    for call in (
        lambda: world_bank_service.search_indicators(" "),
        lambda: world_bank_service.get_indicator("FP.CPI.TOTL.ZG", "BRA", 2024, 2020),
        lambda: world_bank_service.get_indicator("FP.CPI.TOTL.ZG", "BRA", 1900, 2020),
    ):
        with pytest.raises(InvalidParameterError):
            call()


def test_crypto_service_accepts_only_listed_exchanges(crypto_service, crypto_provider):
    assert crypto_service.list_exchanges() == ["binance", "kraken"]
    assert crypto_service.get_ticker("Binance", "btc/usdt").symbol == "BTC/USDT"
    assert len(crypto_service.get_ohlcv("binance", "BTC/USDT", "1h", 3)) == 3
    assert crypto_service.get_order_book("binance", "BTC/USDT").spread == 1.0
    with pytest.raises(ExchangeNotFoundError):
        crypto_service.get_ticker("__class__", "BTC/USDT")
    with pytest.raises(InvalidParameterError):
        crypto_service.get_ohlcv("binance", "BTC/USDT", "2d", 3)
    with pytest.raises(InvalidParameterError):
        crypto_service.get_order_book("binance", "BTC/USDT", 500)
    assert crypto_provider.calls.count(("exchanges",)) == 1


def test_asset_simulation_fan_is_ordered_and_reproducible(simulation_service):
    fan = simulation_service.simulate_asset("PETR4.SA", horizon_days=21, n_paths=200, seed=3)
    assert len(fan.dates) == 21 and fan.dates[0] == date(2026, 10, 12)
    assert fan.observations_used == 499
    for day in range(21):
        assert fan.percentiles["p5"][day] <= fan.percentiles["p50"][day] <= fan.percentiles["p95"][day]
    assert len(fan.sample_paths) == 5 and len(fan.final_prices) == 200
    again = simulation_service.simulate_asset("PETR4.SA", horizon_days=21, n_paths=200, seed=3)
    assert again is fan
    with pytest.raises(InvalidParameterError):
        simulation_service.simulate_asset("PETR4.SA", horizon_days=2)
    with pytest.raises(InvalidParameterError):
        simulation_service.simulate_asset("PETR4.SA", history_period="1mo")


def test_short_histories_cannot_be_fitted(simulation_service, market_service, monkeypatch):
    short = market_service.get_history("PETR4.SA", "1mo", "1d")
    monkeypatch.setattr(market_service, "get_history", lambda *args: short)
    with pytest.raises(SimulationError):
        simulation_service.fit_asset("PETR4.SA", "1y")


def test_synthetic_series_follow_the_mcp_contract(simulation_service):
    request = SyntheticRequest(
        ticker="PETR4.SA",
        start_date=date(2026, 10, 17),
        n_days=4,
        n_series=3,
        manual=GarchParameters(0.0, 0.02, 0.1, 0.85),
        seed=1,
    )
    result = simulation_service.generate_synthetic(request)
    assert list(result.series) == ["serie_1", "serie_2", "serie_3"]
    assert result.dates[0] == date(2026, 10, 19)
    assert all(len(values) == 4 for values in result.series.values())
    assert simulation_service.generate_synthetic(request).series == result.series
    fitted = simulation_service.generate_synthetic(
        SyntheticRequest("PETR4.SA", date(2026, 10, 19), 3, mode="fit_and_simulate", seed=1)
    )
    assert fitted.parameters.persistence < 1
    generator = random.Random(3)
    returns = tuple(generator.gauss(0.0005, 0.015) for _ in range(300))
    from_returns = simulation_service.generate_synthetic(
        SyntheticRequest(
            "X", date(2026, 10, 19), 3, value_type="high",
            mode="fit_and_simulate", historical_returns=returns, seed=2,
        )
    )
    assert from_returns.value_type == "high"


@pytest.mark.parametrize(
    "changes",
    [
        {"value_type": "volume"},
        {"mode": "guess"},
        {"n_days": 0},
        {"n_series": 101},
        {"manual": None},
        {"manual": GarchParameters(0.0, 0.02, 0.5, 0.6)},
        {"manual": GarchParameters(0.0, -1.0, 0.1, 0.8)},
        {"mode": "fit_and_simulate", "historical_returns": (0.01,) * 5},
    ],
)
def test_synthetic_series_reject_invalid_inputs(simulation_service, changes):
    values = {
        "ticker": "X",
        "start_date": date(2026, 10, 19),
        "n_days": 3,
        "manual": GarchParameters(0.0, 0.02, 0.1, 0.85),
    }
    values.update(changes)
    with pytest.raises(InvalidParameterError):
        simulation_service.generate_synthetic(SyntheticRequest(**values))


def test_business_days_skip_weekends():
    assert business_days_after(date(2026, 10, 9), 2) == [date(2026, 10, 12), date(2026, 10, 13)]
