"""Helpers to keep developer LangSmith settings out of unit tests."""

from __future__ import annotations

import os
from pathlib import Path
import sys

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

TRACING_ENV_KEYS = (
    "LANGSMITH_TRACING",
    "LANGSMITH_API_KEY",
    "LANGSMITH_PROJECT",
    "LANGSMITH_ENDPOINT",
    "LANGCHAIN_TRACING_V2",
    "LANGCHAIN_API_KEY",
    "LANGCHAIN_PROJECT",
    "LANGCHAIN_ENDPOINT",
)


def disable_tracing_for_tests() -> None:
    """Clear LangSmith env vars so fakes without config= support stay valid."""
    os.environ["ROAST_DISABLE_TRACING"] = "true"
    for key in TRACING_ENV_KEYS:
        os.environ.pop(key, None)

    from observability.langsmith import configure_observability

    configure_observability.__globals__["_CONFIGURED"] = False
