"""Shared fixtures: services wired to fakes and an API client."""

import pytest
from fastapi.testclient import TestClient

from finbrain_server.application.cache_policy import CachePolicy
from finbrain_server.application.crypto import CryptoService
from finbrain_server.application.macro_brasil import BrazilMacroService
from finbrain_server.application.macro_global import WorldBankService
from finbrain_server.application.market import MarketDataService
from finbrain_server.application.simulations import SimulationService
from finbrain_server.infrastructure.cache.memory_cache import InMemoryTtlCache
from finbrain_server.infrastructure.config import Settings
from finbrain_server.infrastructure.simulation.arch_garch_engine import ArchGarchEngine
from finbrain_server.presentation.api import dependencies
from finbrain_server.presentation.api.app import create_app
from tests.fakes import (
    TODAY,
    FakeBrazilMacro,
    FakeCrypto,
    FakeMarketData,
    FakeWorldBank,
)


@pytest.fixture
def cache():
    """Fresh in-memory cache."""
    return InMemoryTtlCache(max_entries=256)


@pytest.fixture
def policy():
    """Default cache policy."""
    return CachePolicy()


@pytest.fixture
def market_provider():
    """Fake market data provider."""
    return FakeMarketData()


@pytest.fixture
def macro_provider():
    """Fake Central Bank provider."""
    return FakeBrazilMacro()


@pytest.fixture
def world_bank_provider():
    """Fake World Bank provider."""
    return FakeWorldBank()


@pytest.fixture
def crypto_provider():
    """Fake crypto provider."""
    return FakeCrypto()


@pytest.fixture
def market_service(market_provider, cache, policy):
    """Market service on the fake provider."""
    return MarketDataService(market_provider, cache, policy)


@pytest.fixture
def macro_service(macro_provider, cache, policy):
    """Brazilian macro service on the fake provider."""
    return BrazilMacroService(macro_provider, cache, policy, today=lambda: TODAY)


@pytest.fixture
def world_bank_service(world_bank_provider, cache, policy):
    """World Bank service on the fake provider."""
    return WorldBankService(world_bank_provider, cache, policy, today=lambda: TODAY)


@pytest.fixture
def crypto_service(crypto_provider, cache, policy):
    """Crypto service on the fake provider."""
    return CryptoService(crypto_provider, cache, policy)


@pytest.fixture
def simulation_service(market_service, cache, policy):
    """Simulation service with the real GARCH engine."""
    return SimulationService(market_service, ArchGarchEngine(), cache, policy)


@pytest.fixture
def client(
    cache,
    market_service,
    macro_service,
    world_bank_service,
    crypto_service,
    simulation_service,
):
    """API client whose services use the fakes."""
    app = create_app(Settings(FINBRAIN_CORS_ORIGINS="https://finbrain.example"))
    app.dependency_overrides.update({
        dependencies.get_cache: lambda: cache,
        dependencies.get_market_service: lambda: market_service,
        dependencies.get_macro_brasil_service: lambda: macro_service,
        dependencies.get_crypto_service: lambda: crypto_service,
        dependencies.get_simulation_service: lambda: simulation_service,
        dependencies.get_default_watchlist: lambda: "PETR4.SA,^BVSP",
    })
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
