"""Intraday candles: their time of day and the cache time to live for them."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pandas as pd

from finbrain_server.application.cache_policy import CachePolicy
from finbrain_server.application.market import MarketDataService
from finbrain_server.application.ports import Cache
from finbrain_server.domain.entities import PriceBar
from finbrain_server.infrastructure.providers.yfinance_provider import YFinanceMarketDataProvider
from finbrain_server.presentation.api.schemas import PriceBarSchema
from tests.fakes import FakeMarketData


class RecordingCache(Cache):
    """Cache that remembers the time to live of each entry and always loads."""

    def __init__(self):
        self.ttls = {}

    def get_or_load(self, key, ttl_seconds, loader):
        self.ttls[key] = ttl_seconds
        return loader()

    def stats(self):
        return {"entries": len(self.ttls), "hits": 0, "misses": len(self.ttls)}

    def clear(self):
        self.ttls.clear()


def test_intraday_history_uses_the_short_time_to_live():
    cache = RecordingCache()
    policy = CachePolicy()
    service = MarketDataService(FakeMarketData(), cache, policy)
    service.get_history("PETR4.SA", "1d", "5m")
    service.get_history("PETR4.SA", "1y", "1d")
    assert cache.ttls["history:PETR4.SA:1d:5m"] == policy.intraday_history == 60
    assert cache.ttls["history:PETR4.SA:1y:1d"] == policy.history == 900


def test_intraday_bar_serializes_its_time_of_day_with_offset():
    start = datetime(2026, 10, 15, 10, 1, tzinfo=timezone(timedelta(hours=-3)))
    bar = PriceBar(date=start.date(), open=1, high=2, low=1, close=2, volume=5, timestamp=start)
    body = PriceBarSchema.build(bar).model_dump(mode="json")
    assert body["timestamp"] == "2026-10-15T10:01:00-03:00"
    assert body["date"] == "2026-10-15"


def test_daily_bar_has_no_timestamp():
    bar = PriceBar(date=datetime(2026, 10, 15).date(), open=1, high=2, low=1, close=2)
    assert PriceBarSchema.build(bar).model_dump(mode="json")["timestamp"] is None


def test_provider_keeps_the_timestamp_only_for_intraday_intervals():
    index = pd.DatetimeIndex(
        [pd.Timestamp("2026-10-15 10:01", tz="America/Sao_Paulo"), pd.Timestamp("2026-10-15 10:02", tz="America/Sao_Paulo")]
    )
    frame = pd.DataFrame({"Open": [1.0, 1.1], "High": [1.2, 1.3], "Low": [0.9, 1.0], "Close": [1.1, 1.2], "Volume": [10, 20]}, index=index)
    source = SimpleNamespace(history=lambda period, interval: frame, history_metadata={"currency": "BRL"})
    provider = YFinanceMarketDataProvider(ticker_factory=lambda ticker: source)

    intraday = provider.get_history("PETR4.SA", "1d", "1m")
    assert intraday.bars[0].timestamp.isoformat() == "2026-10-15T10:01:00-03:00"

    daily = provider.get_history("PETR4.SA", "1mo", "1d")
    assert daily.bars[0].timestamp is None
