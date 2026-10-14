"""Tests of the adapters with stand-ins of the third-party libraries."""

import threading
import time
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from finbrain_server.domain.entities import GarchParameters
from finbrain_server.domain.exceptions import (
    AssetNotFoundError,
    ExchangeNotFoundError,
    SeriesNotFoundError,
    SimulationError,
    UpstreamUnavailableError,
)
from finbrain_server.infrastructure.cache.memory_cache import InMemoryTtlCache
from finbrain_server.infrastructure.config import Settings
from finbrain_server.infrastructure.providers.bcb_provider import BcbMacroProvider
from finbrain_server.infrastructure.providers.ccxt_provider import CcxtCryptoProvider
from finbrain_server.infrastructure.providers.world_bank_provider import (
    WbdataWorldBankProvider,
)
from finbrain_server.infrastructure.providers.yfinance_provider import (
    YFinanceMarketDataProvider,
)
from finbrain_server.infrastructure.simulation.arch_garch_engine import ArchGarchEngine


class FakeClock:
    """Manual clock for the cache."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_cache_expires_entries_and_counts_hits():
    clock = FakeClock()
    cache = InMemoryTtlCache(max_entries=10, clock=clock)
    loads = []
    assert cache.get_or_load("k", 10, lambda: loads.append(1) or "v1") == "v1"
    assert cache.get_or_load("k", 10, lambda: "other") == "v1"
    clock.now = 11
    assert cache.get_or_load("k", 10, lambda: "v2") == "v2"
    assert cache.stats() == {"entries": 1, "max_entries": 10, "hits": 1, "misses": 2}
    cache.clear()
    assert cache.stats()["entries"] == 0


def test_cache_evicts_the_least_recently_used_entry():
    cache = InMemoryTtlCache(max_entries=2)
    cache.get_or_load("a", 60, lambda: 1)
    cache.get_or_load("b", 60, lambda: 2)
    cache.get_or_load("a", 60, lambda: 0)
    cache.get_or_load("c", 60, lambda: 3)
    assert cache.get_or_load("a", 60, lambda: "reloaded") == 1
    assert cache.get_or_load("b", 60, lambda: "reloaded") == "reloaded"


def test_cache_does_not_store_errors():
    cache = InMemoryTtlCache()

    def fail():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        cache.get_or_load("k", 60, fail)
    assert cache.get_or_load("k", 60, lambda: "ok") == "ok"


def test_concurrent_misses_load_once():
    cache = InMemoryTtlCache()
    loads = []

    def slow():
        loads.append(1)
        time.sleep(0.05)
        return "v"

    threads = [threading.Thread(target=cache.get_or_load, args=("k", 60, slow)) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(loads) == 1


def test_settings_build_cors_origins_and_policy():
    settings = Settings(FINBRAIN_CORS_ORIGINS="https://a.com, https://b.com", cache_ttl_quote=5)
    assert settings.cors_origins == ["https://a.com", "https://b.com"]
    assert settings.cache_policy.quote == 5
    assert settings.cache_policy.history == 900


class FakeTicker:
    """Stand-in of ``yfinance.Ticker``."""

    def __init__(self, info=None, frame=None, error=None) -> None:
        self.info = info if info is not None else {}
        self._frame = frame
        self._error = error
        self.history_metadata = {"currency": "BRL"}

    def history(self, period, interval):
        if self._error:
            raise self._error
        return self._frame


def candles_frame():
    index = pd.DatetimeIndex(
        ["2026-10-08", "2026-10-09", "2026-10-13"], tz="America/Sao_Paulo"
    )
    return pd.DataFrame(
        {
            "Open": [55.3, 55.45, 0.0],
            "High": [55.96, 56.8, 0.0],
            "Low": [55.0, 55.1, 0.0],
            "Close": [55.5, 56.0, 56.85],
            "Volume": [100, 200, np.nan],
        },
        index=index,
    )


def test_yfinance_history_drops_placeholder_candles():
    provider = YFinanceMarketDataProvider(lambda symbol: FakeTicker(frame=candles_frame()))
    history = provider.get_history("PETR4.SA", "5d", "1d")
    assert [bar.date for bar in history.bars] == [date(2026, 10, 8), date(2026, 10, 9)]
    assert history.bars[-1].close == 56.0 and history.currency == "BRL"


def test_yfinance_errors_are_translated():
    unknown = YFinanceMarketDataProvider(lambda symbol: FakeTicker(error=KeyError("tz")))
    with pytest.raises(AssetNotFoundError):
        unknown.get_history("XXXX9.SA", "1y", "1d")
    broken = YFinanceMarketDataProvider(lambda symbol: FakeTicker(error=ConnectionError("x")))
    with pytest.raises(UpstreamUnavailableError):
        broken.get_history("PETR4.SA", "1y", "1d")
    empty = YFinanceMarketDataProvider(lambda symbol: FakeTicker(info={"trailingPegRatio": None}))
    with pytest.raises(AssetNotFoundError):
        empty.get_quote("XXXX9.SA")

    def explode(symbol):
        raise ConnectionError("down")

    with pytest.raises(UpstreamUnavailableError):
        YFinanceMarketDataProvider(explode).get_fundamentals("PETR4.SA")


def test_yfinance_quote_and_fundamentals():
    info = {
        "longName": "Petrobras", "currency": "BRL", "regularMarketPrice": 56.85,
        "previousClose": 56.0, "volume": 10.0, "regularMarketTime": 1791921950,
        "trailingPE": 5.4, "dividendYield": 6.54, "sector": "Energy", "marketCap": float("nan"),
    }
    provider = YFinanceMarketDataProvider(lambda symbol: FakeTicker(info=info))
    quote = provider.get_quote("PETR4.SA")
    assert (quote.price, quote.previous_close, quote.volume) == (56.85, 56.0, 10)
    assert quote.market_time.year == 2026
    fundamentals = provider.get_fundamentals("PETR4.SA")
    assert fundamentals.pe_ratio == 5.4 and fundamentals.market_cap is None
    no_price = YFinanceMarketDataProvider(lambda symbol: FakeTicker(info={"longName": "X", "a": 1}))
    with pytest.raises(AssetNotFoundError):
        no_price.get_quote("X")
    with pytest.raises(AssetNotFoundError):
        YFinanceMarketDataProvider(lambda symbol: FakeTicker(info={"a": 1, "b": 2})).get_fundamentals("X")


class FakeQuery:
    """Stand-in of the OData query builder of ``python-bcb``."""

    def __init__(self, frame) -> None:
        self.frame = frame
        self.arguments = {}

    def parameters(self, **values):
        self.arguments.update(values)
        return self

    def filter(self, *conditions):
        return self

    def orderby(self, *fields):
        return self

    def limit(self, count):
        return self

    def collect(self):
        return self.frame


class FakeEndpoint:
    """Stand-in of an OData endpoint."""


    def __init__(self, frame) -> None:
        self.last_query = FakeQuery(frame)
        self.Indicador = "Indicador"
        self.DataReferencia = "DataReferencia"
        self.Data = SimpleNamespace(desc=lambda: "Data desc")

    def query(self):
        return self.last_query


def test_bcb_series_ptax_and_focus():
    frame = pd.DataFrame({"value": [13.75, np.nan]}, index=pd.to_datetime(["2026-10-10", "2026-10-11"]))
    sgs_module = SimpleNamespace(get=lambda codes, **options: frame)
    ptax_endpoint = FakeEndpoint(pd.DataFrame({
        "cotacaoCompra": [4.9886], "cotacaoVenda": [4.9892],
        "dataHoraCotacao": pd.to_datetime(["2026-10-09 13:07:30"]),
    }))
    focus_endpoint = FakeEndpoint(pd.DataFrame({
        "Indicador": ["IPCA", "IPCA"], "IndicadorDetalhe": [None, None],
        "Data": pd.to_datetime(["2026-10-09", "2026-10-09"]), "DataReferencia": ["2026", "2026"],
        "Media": [5.2, 5.1], "Mediana": [5.22, 5.19], "Minimo": [4.5, 4.8], "Maximo": [5.9, 5.8],
        "numeroRespondentes": [144, 54], "baseCalculo": [0, 1],
    }))
    provider = BcbMacroProvider(
        sgs_module,
        lambda: SimpleNamespace(get_endpoint=lambda name: ptax_endpoint),
        lambda: SimpleNamespace(get_endpoint=lambda name: focus_endpoint),
    )
    assert provider.get_series(432, None, None, 5) == [(date(2026, 10, 10), 13.75)]
    assert provider.get_series(432, date(2026, 1, 1), date(2026, 10, 1), None)[0][1] == 13.75
    ptax = provider.get_ptax(date(2026, 10, 1), date(2026, 10, 9))
    assert ptax[0].sell == 4.9892
    assert ptax_endpoint.last_query.arguments == {"dataInicial": "10-01-2026", "dataFinalCotacao": "10-09-2026"}
    focus = provider.get_expectations("IPCA", "2026", 5)
    assert len(focus) == 1 and focus[0].respondents == 144


def test_bcb_errors_are_translated():
    def fail(*args, **kwargs):
        raise ConnectionError("down")

    provider = BcbMacroProvider(SimpleNamespace(get=fail), fail, fail)
    for call in (
        lambda: provider.get_series(432, None, None, 5),
        lambda: provider.get_ptax(date(2026, 1, 1), date(2026, 1, 2)),
        lambda: provider.get_expectations("IPCA", "2026", 5),
    ):
        with pytest.raises(UpstreamUnavailableError):
            call()


def test_world_bank_adapter():
    rows = [
        {"countryiso3code": "BRA", "date": "2023", "value": 4.59},
        {"countryiso3code": "", "country": {"id": "US"}, "date": "2023", "value": 4.1},
        {"countryiso3code": "BRA", "date": "2022", "value": None},
    ]
    calls = []
    client = SimpleNamespace(
        get_indicators=lambda query: [{"id": "FP.CPI.TOTL.ZG", "name": "Inflation"}] * 3,
        get_data=lambda code, **options: calls.append(options) or rows,
    )
    provider = WbdataWorldBankProvider(client)
    assert len(provider.search_indicators("inflation", 2)) == 2
    values = provider.get_indicator("FP.CPI.TOTL.ZG", ["BRA", "USA"], 2020, 2023)
    assert [(item.country, item.value) for item in values] == [("BRA", 4.59), ("US", 4.1)]
    assert calls[0] == {"country": ["BRA", "USA"], "date": ("2020", "2023")}
    provider.get_indicator("FP.CPI.TOTL.ZG", ["BRA"], None, None)
    assert calls[1] == {"country": ["BRA"]}


def test_world_bank_errors_are_translated():
    def invalid(*args, **kwargs):
        raise RuntimeError("The indicator was not found")

    def down(*args, **kwargs):
        raise ConnectionError("timeout")

    with pytest.raises(SeriesNotFoundError):
        WbdataWorldBankProvider(SimpleNamespace(get_data=invalid)).get_indicator("X.Y", ["BRA"], None, None)
    with pytest.raises(UpstreamUnavailableError):
        WbdataWorldBankProvider(SimpleNamespace(get_data=down)).get_indicator("X.Y", ["BRA"], None, None)
    with pytest.raises(UpstreamUnavailableError):
        WbdataWorldBankProvider(SimpleNamespace(get_indicators=down)).search_indicators("x", 5)


class BadSymbol(Exception):
    """Stand-in of ``ccxt.BadSymbol``."""


class FakeExchange:
    """Stand-in of a ccxt exchange class."""

    created = 0

    def __init__(self, options) -> None:
        FakeExchange.created += 1
        self.options = options

    def fetch_ticker(self, symbol):
        if symbol == "NOPE/USDT":
            raise BadSymbol(symbol)
        if symbol == "DOWN/USDT":
            raise ConnectionError("down")
        return {"last": 62000.0, "high": 63000.0, "low": None, "percentage": 1.2,
                "baseVolume": 10.0, "timestamp": 1791921950000}

    def fetch_ohlcv(self, symbol, timeframe, limit):
        return [[1791921950000, 1, 2, 0.5, 1.5, None]] * limit

    def fetch_order_book(self, symbol, limit):
        return {"bids": [[100, 1], [99, 2], [98, 3]], "asks": [[101, 1]]}


def test_ccxt_adapter_reuses_clients_and_translates_errors():
    library = SimpleNamespace(exchanges=["binance"], binance=FakeExchange, BadSymbol=BadSymbol)
    provider = CcxtCryptoProvider(library)
    FakeExchange.created = 0
    ticker = provider.get_ticker("binance", "BTC/USDT")
    assert ticker.last == 62000.0 and ticker.low is None and ticker.timestamp.year == 2026
    assert provider.get_ohlcv("binance", "BTC/USDT", "1d", 2)[0].volume == 0.0
    book = provider.get_order_book("binance", "BTC/USDT", 2)
    assert book.bids == ((100.0, 1.0), (99.0, 2.0)) and book.spread == 1.0
    assert FakeExchange.created == 1
    assert provider.list_exchanges() == ["binance"]
    with pytest.raises(AssetNotFoundError):
        provider.get_ticker("binance", "NOPE/USDT")
    with pytest.raises(UpstreamUnavailableError):
        provider.get_ticker("binance", "DOWN/USDT")
    with pytest.raises(ExchangeNotFoundError):
        provider.get_ticker("__class__", "BTC/USDT")


def garch_returns(count: int = 600) -> list[float]:
    generator = np.random.default_rng(5)
    variance, returns = 1.0, []
    for _ in range(count):
        value = 0.05 + np.sqrt(variance) * generator.standard_normal()
        returns.append(float(value))
        variance = 0.05 + 0.1 * (value - 0.05) ** 2 + 0.85 * variance
    return returns


def test_garch_fit_recovers_a_stationary_model():
    parameters = ArchGarchEngine().fit(garch_returns())
    assert 0 < parameters.persistence < 1
    assert parameters.last_variance > 0 and parameters.last_residual is not None


def test_garch_fit_failures_are_simulation_errors(monkeypatch):
    from finbrain_server.infrastructure.simulation import arch_garch_engine

    def broken(*args, **kwargs):
        raise ValueError("singular matrix")

    monkeypatch.setattr(arch_garch_engine, "arch_model", broken)
    with pytest.raises(SimulationError):
        ArchGarchEngine().fit([0.1] * 50)


def test_garch_simulation_is_reproducible_and_bounded():
    engine = ArchGarchEngine()
    model = GarchParameters(mu=0.05, omega=0.02, alpha=0.1, beta=0.85)
    first = engine.simulate_returns(model, 50, 400, seed=9)
    assert first == engine.simulate_returns(model, 50, 400, seed=9)
    assert len(first) == 400 and len(first[0]) == 50
    flat = np.asarray(first)
    assert abs(flat.mean() - 0.05) < 0.05
    assert abs(flat.var() - model.long_run_variance) < 0.15
    turbulent = GarchParameters(0.0, 0.02, 0.1, 0.85, last_variance=900.0, last_residual=40.0)
    wild = np.asarray(engine.simulate_returns(turbulent, 3, 200, seed=1))
    assert wild.max() <= 50.0 and wild.min() >= -50.0
