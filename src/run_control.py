"""Cooperative stop signals for the roast pipeline."""

from collections.abc import Callable


class RunAbort(Exception):
    """Cancel or budget guard tripped between pipeline phases / debate turns."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def check_abort(abort_check: Callable[[], str | None] | None) -> None:
    if abort_check is None:
        return
    reason = abort_check()
    if reason:
        raise RunAbort(reason)
