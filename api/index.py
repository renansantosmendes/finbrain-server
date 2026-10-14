"""Vercel entry point: exposes the ASGI application as ``app``.

Vercel runs this module as a Python serverless function; ``vercel.json``
rewrites every path to it and passes the original path in the
``__vercel_path`` query parameter, which ``RestoreOriginalPathMiddleware``
puts back before FastAPI routes the request. Locally, run the same
application with ``uv run --no-project uvicorn api.index:app --reload``.
"""

import importlib
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qsl, urlencode

SOURCE_DIRECTORY = Path(__file__).resolve().parent.parent / "src"
if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))

ORIGINAL_PATH_PARAMETER = "__vercel_path"

AsgiApp = Callable[
    [dict[str, Any], Callable[[], Awaitable[Any]], Callable[[Any], Awaitable[None]]],
    Awaitable[None],
]


class RestoreOriginalPathMiddleware:
    """Restore the request path that the Vercel rewrite replaced.

    Parameters
    ----------
    app : AsgiApp
        Wrapped ASGI application.
    """

    def __init__(self, app: AsgiApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[Any]],
        send: Callable[[Any], Awaitable[None]],
    ) -> None:
        """Rewrite ``path`` and ``query_string`` of HTTP requests.

        Parameters
        ----------
        scope : dict[str, Any]
            ASGI connection scope.
        receive : Callable[[], Awaitable[Any]]
            ASGI receive channel.
        send : Callable[[Any], Awaitable[None]]
            ASGI send channel.
        """
        if scope.get("type") in ("http", "websocket"):
            scope = restore_original_path(scope)
        await self.app(scope, receive, send)


def restore_original_path(scope: dict[str, Any]) -> dict[str, Any]:
    """Return a scope whose path comes from ``__vercel_path``.

    Parameters
    ----------
    scope : dict[str, Any]
        ASGI connection scope received from the Vercel runtime.

    Returns
    -------
    dict[str, Any]
        The same scope when the parameter is absent; otherwise a copy
        with the original path and without the parameter in the query.

    Example
    -------
    >>> restore_original_path(
    ...     {"path": "/api/index.py", "query_string": b"__vercel_path=docs"}
    ... )["path"]
    '/docs'
    """
    query_pairs = parse_qsl(
        scope.get("query_string", b"").decode("latin-1"),
        keep_blank_values=True,
    )
    original_paths = [
        value for key, value in query_pairs if key == ORIGINAL_PATH_PARAMETER
    ]
    if not original_paths:
        return scope
    original_path = "/" + original_paths[0].lstrip("/")
    remaining_pairs = [
        (key, value) for key, value in query_pairs if key != ORIGINAL_PATH_PARAMETER
    ]
    return {
        **scope,
        "path": original_path,
        "raw_path": original_path.encode(),
        "query_string": urlencode(remaining_pairs).encode(),
    }


app = importlib.import_module(
    "finbrain_server.presentation.api.app"
).create_app()
app.add_middleware(RestoreOriginalPathMiddleware)
