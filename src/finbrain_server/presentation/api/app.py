"""FastAPI application factory."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse

from finbrain_server import __version__
from finbrain_server.infrastructure.config import Settings, get_settings
from finbrain_server.presentation.api.error_handlers import register_error_handlers
# Import routers; import macro_global lazily to tolerate its removal
from finbrain_server.presentation.api.routers import (
    assets,
    crypto,
    dashboard,
    macro_brasil,
    simulations,
    system,
)
try:
    from finbrain_server.presentation.api.routers import macro_global
except Exception:
    macro_global = None


API_PREFIX = "/api/v1"

API_DESCRIPTION = """
Data API of **FinBrain** (SynapseAI Solutions): real market data, Brazilian
and global macro data, crypto data and GARCH(1,1) simulations, with the same
capabilities as the finbrain-mcp tools, for the FinBrain front end.

## Sources

| Data | Source |
|------|--------|
| Stocks, indices, currencies | Yahoo Finance (`yfinance`) |
| Selic, CDI, IPCA, PTAX, Focus | Central Bank of Brazil (`python-bcb`) |
| Crypto | Public APIs of exchanges (`ccxt`) |
| Simulations | GARCH(1,1) fitted with `arch` |

Tickers follow Yahoo Finance: `PETR4.SA` (B3), `AAPL` (US), `^BVSP`
(Ibovespa), `BRL=X` (USD/BRL).

## Caching

Every answer from a data source is cached in memory with a time to live per
kind of data (quotes 1 min, candles 15 min, company data and macro 6 h,
crypto 5 to 60 s, simulations 1 h). Successful `GET`
answers also carry `Cache-Control` so browsers and the CDN can reuse them.
`GET /api/v1/cache/stats` shows the cache counters.

## Errors

Every error answers with the same body:

```json
{"code": "asset_not_found", "message": "No price data for ticker 'XXXX3.SA'."}
```

| Status | Codes |
|--------|-------|
| 404 | `asset_not_found`, `series_not_found`, `exchange_not_found` |
| 422 | `invalid_parameter`, `validation_error`, `simulation_failed` |
| 500 | `internal_error` |
| 502 | `upstream_unavailable` |

The content is informative and is not investment advice.
"""

OPENAPI_TAGS = [
    {"name": "Dashboard", "description": "Everything the Dashboards screen needs."},
    {"name": "Assets", "description": "Stocks, indices and currencies (Yahoo Finance)."},
    {"name": "Macro Brasil", "description": "Central Bank of Brazil: SGS, PTAX, Focus."},
    {"name": "Macro global", "description": "World Bank indicators."},
    {"name": "Crypto", "description": "Crypto exchanges (ccxt)."},
    {"name": "Simulations", "description": "GARCH(1,1) fits and Monte Carlo paths."},
    {"name": "System", "description": "Health and cache counters."},
]


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application with routes, CORS and error handlers.

    Parameters
    ----------
    settings : Settings | None
        Settings used at start-up (CORS origins). When omitted, they are
        read from the environment.

    Returns
    -------
    FastAPI
        Configured application.

    Example
    -------
    >>> import uvicorn
    >>> uvicorn.run(create_app(), port=8000)
    """
    settings = settings or get_settings()
    logging.basicConfig(level=logging.INFO)
    app = FastAPI(
        title="FinBrain Server",
        version=__version__,
        summary="Market data, macro data and GARCH simulations for FinBrain.",
        description=API_DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        contact={"name": "SynapseAI Solutions"},
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        swagger_ui_parameters={"displayRequestDuration": True, "tryItOutEnabled": True},
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type"],
        )
    register_error_handlers(app)
    for module in (dashboard, assets, macro_brasil, simulations, system, crypto):
        app.include_router(module.router, prefix=API_PREFIX)
    # include macro_global if available
    if macro_global is not None:
        app.include_router(macro_global.router, prefix=API_PREFIX)


    @app.get("/", include_in_schema=False)
    def redirect_to_docs() -> RedirectResponse:
        """Send visitors of the root URL to the Swagger UI.

        Returns
        -------
        RedirectResponse
            Redirect to ``/docs``.
        """
        return RedirectResponse(url="/docs")

    return app
