"""Vercel entry point: exposes the ASGI application as ``app``.

Vercel runs this module as a Python serverless function; ``vercel.json``
rewrites every path to it. Locally, run the same application with
``uv run --no-project uvicorn api.index:app --reload``.
"""

import importlib
import sys
from pathlib import Path

SOURCE_DIRECTORY = Path(__file__).resolve().parent.parent / "src"
if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))

app = importlib.import_module(
    "finbrain_server.presentation.api.app"
).create_app()
