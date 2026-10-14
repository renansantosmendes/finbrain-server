"""Routes of GARCH(1,1) simulations."""

from typing import Annotated

from fastapi import APIRouter, Depends

from finbrain_server.application.simulations import SimulationService, SyntheticRequest
from finbrain_server.domain.entities import GarchParameters
from finbrain_server.presentation.api.dependencies import get_simulation_service
from finbrain_server.presentation.api.error_handlers import (
    INVALID,
    NOT_FOUND,
    UPSTREAM,
    error_doc,
)
from finbrain_server.presentation.api.schemas import (
    AssetSimulationRequest,
    AssetSimulationResponse,
    GarchParametersSchema,
    SyntheticSeriesRequest,
    SyntheticSeriesResponse,
)

router = APIRouter(prefix="/simulations", tags=["Simulations"])

Service = Annotated[SimulationService, Depends(get_simulation_service)]
FAILED = {
    422: error_doc(
        "Invalid parameter (`invalid_parameter`, `validation_error`) or the "
        "model could not be fitted (`simulation_failed`)."
    )
}


@router.post(
    "/garch/asset",
    summary="Simulate future prices of an asset with GARCH(1,1)",
    description="Fits a GARCH(1,1) to the real daily returns of the asset "
    "(Yahoo Finance) and simulates price paths from the last close and the "
    "last observed volatility. Answers the percentiles of each future day "
    "(fan chart), five sample paths and the final distribution. Fits and "
    "results are cached; the same inputs and seed give the same answer.",
    response_description="Fan of simulated prices.",
    responses={**FAILED, **NOT_FOUND, **UPSTREAM},
)
def simulate_asset(
    service: Service,
    request: AssetSimulationRequest,
) -> AssetSimulationResponse:
    """Simulate the prices of an asset.

    Parameters
    ----------
    service : SimulationService
        Simulation service.
    request : AssetSimulationRequest
        Asset, horizon, paths, history and seed.

    Returns
    -------
    AssetSimulationResponse
        Fan of simulated prices.
    """
    fan = service.simulate_asset(
        request.ticker,
        request.horizon_days,
        request.n_paths,
        request.history_period,
        request.seed,
    )
    return AssetSimulationResponse.build(fan)


@router.post(
    "/garch/synthetic",
    summary="Generate synthetic price series with GARCH(1,1)",
    description="Same behavior as the finbrain-mcp tool "
    "`generate_synthetic_stock_series_garch_arch`: `simulate` uses the "
    "informed mu/omega/alpha/beta; `fit_and_simulate` fits them on "
    "`historical_returns` or, when omitted, on two years of the ticker's "
    "real history.",
    response_description="Dates, series and the parameters used.",
    responses={**INVALID, **NOT_FOUND, **UPSTREAM},
)
def generate_synthetic(
    service: Service,
    request: SyntheticSeriesRequest,
) -> SyntheticSeriesResponse:
    """Generate synthetic series.

    Parameters
    ----------
    service : SimulationService
        Simulation service.
    request : SyntheticSeriesRequest
        Generation inputs.

    Returns
    -------
    SyntheticSeriesResponse
        Generated series.
    """
    result = service.generate_synthetic(
        SyntheticRequest(
            ticker=request.ticker,
            start_date=request.start_date,
            n_days=request.n_days,
            value_type=request.value_type,
            n_series=request.n_series,
            mode=request.mode,
            initial_price=request.initial_price,
            manual=GarchParameters(
                mu=request.mu,
                omega=request.omega,
                alpha=request.alpha,
                beta=request.beta,
            ),
            historical_returns=(
                tuple(request.historical_returns)
                if request.historical_returns
                else None
            ),
            seed=request.seed,
        )
    )
    return SyntheticSeriesResponse(
        value_type=result.value_type,
        dates=list(result.dates),
        series={name: list(values) for name, values in result.series.items()},
        parameters=GarchParametersSchema.build(result.parameters),
    )
