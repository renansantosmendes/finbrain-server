"""Routes about the API itself: health and cache counters."""

from typing import Annotated

from fastapi import APIRouter, Depends

from finbrain_server import __version__
from finbrain_server.application.ports import Cache
from finbrain_server.presentation.api.dependencies import get_cache
from finbrain_server.presentation.api.schemas import CacheStatsResponse, HealthResponse

router = APIRouter(tags=["System"])


@router.get(
    "/health",
    summary="Liveness check",
    description="Answers `ok` while the API is running. It does not call the "
    "data sources.",
    response_description="Status and version.",
)
def health() -> HealthResponse:
    """Report that the API is running.

    Returns
    -------
    HealthResponse
        Status and version.
    """
    return HealthResponse(status="ok", version=__version__)


@router.get(
    "/cache/stats",
    summary="Counters of the in-memory cache",
    description="Entries, capacity, hits and misses of the cache of the "
    "instance that answered (each serverless instance has its own).",
    response_description="Cache counters.",
)
def cache_stats(cache: Annotated[Cache, Depends(get_cache)]) -> CacheStatsResponse:
    """Report the cache counters.

    Parameters
    ----------
    cache : Cache
        Shared cache.

    Returns
    -------
    CacheStatsResponse
        Counters.
    """
    return CacheStatsResponse(**cache.stats())
