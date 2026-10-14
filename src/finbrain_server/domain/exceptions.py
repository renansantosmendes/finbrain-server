"""Business errors with stable codes, translated to HTTP by the API."""


class DomainError(Exception):
    """Base class of every expected error of the FinBrain server.

    Parameters
    ----------
    message : str
        Human-readable explanation of the error.
    """

    code = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidParameterError(DomainError):
    """A request parameter is malformed or outside the accepted range."""

    code = "invalid_parameter"


class AssetNotFoundError(DomainError):
    """The data source has no data for the requested ticker."""

    code = "asset_not_found"


class SeriesNotFoundError(DomainError):
    """The requested economic series or indicator does not exist."""

    code = "series_not_found"


class ExchangeNotFoundError(DomainError):
    """The requested crypto exchange is not supported."""

    code = "exchange_not_found"


class UpstreamUnavailableError(DomainError):
    """A data source (Yahoo Finance, BCB, World Bank, exchange) failed."""

    code = "upstream_unavailable"


class SimulationError(DomainError):
    """The GARCH model could not be fitted or simulated with the data."""

    code = "simulation_failed"
