"""Shared logging configuration for the application."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

DEFAULT_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
DEFAULT_DATE_FORMAT = "%H:%M:%S"

_configured = False


def configure_logging(
    *,
    level: str | None = None,
    log_file: str | Path | None = None,
) -> None:
    """Configure root logging. Safe to call multiple times; only applies handlers once."""
    global _configured

    resolved_level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    numeric_level = getattr(logging, resolved_level, logging.INFO)

    root = logging.getLogger()
    root.setLevel(numeric_level)

    if _configured:
        return

    formatter = logging.Formatter(DEFAULT_FORMAT, datefmt=DEFAULT_DATE_FORMAT)

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    file_target = log_file or os.getenv("LOG_FILE")
    if file_target:
        file_handler = logging.FileHandler(Path(file_target), encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger, configuring defaults if needed."""
    if not _configured:
        configure_logging()
    return logging.getLogger(name)
