"""Disable LangSmith tracing for unit tests unless a test opts in explicitly."""

import os

os.environ.setdefault("ROAST_DISABLE_TRACING", "true")
