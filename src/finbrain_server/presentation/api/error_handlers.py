"""Translation of errors into HTTP responses with a uniform body."""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from finbrain_server.domain.exceptions import (
    AssetNotFoundError,
    DomainError,
    ExchangeNotFoundError,
    InvalidParameterError,
    SeriesNotFoundError,
    SimulationError,
    UpstreamUnavailableError,
)
from finbrain_server.presentation.api.schemas import ErrorResponse

logger = logging.getLogger(__name__)

STATUS_BY_ERROR: dict[type[DomainError], int] = {
    InvalidParameterError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    AssetNotFoundError: status.HTTP_404_NOT_FOUND,
    SeriesNotFoundError: status.HTTP_404_NOT_FOUND,
    ExchangeNotFoundError: status.HTTP_404_NOT_FOUND,
    SimulationError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    UpstreamUnavailableError: status.HTTP_502_BAD_GATEWAY,
}


def error_doc(description: str) -> dict[str, Any]:
    """Describe an error response for the OpenAPI document.

    Parameters
    ----------
    description : str
        When the status is returned, in Markdown.

    Returns
    -------
    dict[str, Any]
        Entry of the ``responses`` argument of a route.
    """
    return {"model": ErrorResponse, "description": description}


INVALID = {422: error_doc("A parameter is invalid (`invalid_parameter`, `validation_error`).")}
UPSTREAM = {502: error_doc("The data source failed (`upstream_unavailable`).")}
NOT_FOUND = {404: error_doc("No data for the ticker (`asset_not_found`).")}


def build_error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[str] | None = None,
) -> JSONResponse:
    """Create a JSON response with the ``ErrorResponse`` body.

    Parameters
    ----------
    status_code : int
        HTTP status code.
    code : str
        Machine-readable error identifier.
    message : str
        Human-readable explanation.
    details : list[str] | None
        Additional explanations.

    Returns
    -------
    JSONResponse
        The error response, never cached.
    """
    body = ErrorResponse(code=code, message=message, details=details)
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json", exclude_none=True),
        headers={"Cache-Control": "no-store"},
    )


async def handle_domain_error(
    _request: Request,
    error: DomainError,
) -> JSONResponse:
    """Translate a business error into its HTTP response.

    Parameters
    ----------
    _request : Request
        Request that failed.
    error : DomainError
        Error raised by a service.

    Returns
    -------
    JSONResponse
        Response with the status of the error class.
    """
    status_code = next(
        (code for kind, code in STATUS_BY_ERROR.items() if isinstance(error, kind)),
        status.HTTP_400_BAD_REQUEST,
    )
    if status_code >= 500:
        logger.warning("%s: %s", error.code, error.message)
    return build_error_response(status_code, error.code, error.message)


async def handle_validation_error(
    _request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    """Translate a FastAPI validation error into the uniform body.

    Parameters
    ----------
    _request : Request
        Request that failed.
    error : RequestValidationError
        Validation error of the parameters or body.

    Returns
    -------
    JSONResponse
        422 response listing each invalid field.
    """
    details = [
        f"{'.'.join(str(part) for part in item.get('loc', ()))}: {item.get('msg')}"
        for item in error.errors()
    ]
    return build_error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "validation_error",
        "The request has invalid parameters.",
        details,
    )


async def handle_unexpected_error(
    _request: Request,
    error: Exception,
) -> JSONResponse:
    """Hide unexpected errors behind a generic 500 response.

    Parameters
    ----------
    _request : Request
        Request that failed.
    error : Exception
        Unexpected error.

    Returns
    -------
    JSONResponse
        500 response without internal details.
    """
    logger.exception("Unexpected error", exc_info=error)
    return build_error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "internal_error",
        "Unexpected error. Try again later.",
    )


def register_error_handlers(app: FastAPI) -> None:
    """Install the error handlers on the application.

    Parameters
    ----------
    app : FastAPI
        Application being built.
    """
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
