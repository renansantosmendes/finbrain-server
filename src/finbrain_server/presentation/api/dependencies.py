"""Composition root: wires adapters into services for the routes."""

from collections.abc import Callable
from functools import lru_cache

from fastapi import Response

from finbrain_server.application.crypto import CryptoService
from finbrain_server.application.macro_brasil import BrazilMacroService
from finbrain_server.application.market import MarketDataService
from finbrain_server.application.ports import Cache
from finbrain_server.application.simulations import SimulationService
from finbrain_server.infrastructure.cache.memory_cache import InMemoryTtlCache
from finbrain_server.infrastructure.config import get_settings
from finbrain_server.infrastructure.providers.bcb_provider import BcbMacroProvider
from finbrain_server.infrastructure.providers.ccxt_provider import CcxtCryptoProvider

from finbrain_server.infrastructure.providers.yfinance_provider import (
    YFinanceMarketDataProvider,
)
from finbrain_server.infrastructure.simulation.arch_garch_engine import (
    ArchGarchEngine,
)


@lru_cache
def get_cache() -> Cache:
    """Cache shared by every service of the process.

    Returns
    -------
    Cache
        In-memory cache sized by the settings.
    """
    return InMemoryTtlCache(max_entries=get_settings().cache_max_entries)


@lru_cache
def get_market_service() -> MarketDataService:
    """Market data service backed by Yahoo Finance.

    Returns
    -------
    MarketDataService
        Shared service.
    """
    return MarketDataService(
        YFinanceMarketDataProvider(), get_cache(), get_settings().cache_policy
    )


@lru_cache
def get_macro_brasil_service() -> BrazilMacroService:
    """Brazilian macro service backed by the Central Bank APIs.

    Returns
    -------
    BrazilMacroService
        Shared service.
    """
    return BrazilMacroService(
        BcbMacroProvider(), get_cache(), get_settings().cache_policy
    )


@lru_cache
def get_crypto_service() -> CryptoService:
    """Crypto service backed by ccxt.

    Returns
    -------
    CryptoService
        Shared service.
    """
    return CryptoService(CcxtCryptoProvider(), get_cache(), get_settings().cache_policy)


@lru_cache
def get_simulation_service() -> SimulationService:
    """GARCH simulation service on top of the market data service.

    Returns
    -------
    SimulationService
        Shared service.
    """
    return SimulationService(
        get_market_service(), ArchGarchEngine(), get_cache(), get_settings().cache_policy
    )


def get_default_watchlist() -> str:
    """Tickers of the dashboard when the client sends none.

    Returns
    -------
    str
        Comma-separated tickers from the settings.
    """
    return get_settings().watchlist


def cache_for(seconds: int) -> Callable[[Response], None]:
    """Dependency that lets browsers and the CDN reuse a response.

    ``max-age`` keeps it in the browser for up to a minute; ``s-maxage``
    keeps it in the Vercel CDN, shared by every visitor, and
    ``stale-while-revalidate`` serves the old copy while a new one loads.

    Parameters
    ----------
    seconds : int
        How long the CDN may serve the response.

    Returns
    -------
    Callable[[Response], None]
        Dependency that sets the ``Cache-Control`` header.

    Example
    -------
    >>> @router.get("/quote", dependencies=[Depends(cache_for(60))])
    ... def quote() -> dict: ...
    """
    header = (
        f"public, max-age={min(seconds, 60)}, s-maxage={seconds}, "
        f"stale-while-revalidate={seconds}"
    )

    def set_header(response: Response) -> None:
        """Set the ``Cache-Control`` header of a successful response.

        Parameters
        ----------
        response : Response
            Response being built.
        """
        response.headers["Cache-Control"] = header

    return set_header
