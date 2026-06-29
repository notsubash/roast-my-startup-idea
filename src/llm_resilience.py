"""Retry helpers for transient LLM provider / transport failures."""

from __future__ import annotations

from collections.abc import Callable
import logging
import time
from typing import TypeVar

logger = logging.getLogger(__name__)

LLM_MAX_ATTEMPTS = 3
_TRANSIENT_ERROR_NAMES = frozenset(
    {
        "RemoteProtocolError",
        "ReadError",
        "ConnectError",
        "ReadTimeout",
        "ConnectTimeout",
        "TimeoutException",
        "ProtocolError",
    }
)

T = TypeVar("T")


def is_transient_llm_error(exc: BaseException) -> bool:
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if type(current).__name__ in _TRANSIENT_ERROR_NAMES:
            return True
        current = current.__cause__ or current.__context__
    return False


def call_with_llm_retry(fn: Callable[[], T], *, label: str = "LLM call") -> T:
    last_error: BaseException | None = None
    for attempt in range(LLM_MAX_ATTEMPTS):
        try:
            return fn()
        except Exception as exc:
            if not is_transient_llm_error(exc) or attempt + 1 >= LLM_MAX_ATTEMPTS:
                raise
            last_error = exc
            delay = 0.5 * (attempt + 1)
            logger.warning(
                "%s failed with transient error (%s); retrying in %.1fs (%d/%d)",
                label,
                exc,
                delay,
                attempt + 2,
                LLM_MAX_ATTEMPTS,
            )
            time.sleep(delay)
    assert last_error is not None
    raise last_error
