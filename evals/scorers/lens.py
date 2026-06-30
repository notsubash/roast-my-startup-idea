"""Lens differentiation metrics for Tier 1 eval (Feature 2 Phase 3 gate)."""

from __future__ import annotations

from typing import Any

from verification import assess_lens_uniqueness


def score_lens_differentiation(verdicts: list[dict[str, Any]]) -> dict[str, Any]:
    """Fail eval when judge evidence asks or concerns overlap beyond threshold.

    Exposes ``lens_differentiation_passed`` for Tier 1 metrics; aliases
    ``assess_lens_uniqueness``'s ``lens_uniqueness_passed`` (used in SSE/API).
    """
    result = assess_lens_uniqueness(verdicts)
    legacy = result.get("lens_legacy", True)
    passed = result.get("lens_uniqueness_passed", True) if legacy else result.get(
        "lens_uniqueness_passed", False
    )
    return {
        **result,
        "lens_differentiation_passed": passed,
        "passed": passed,
    }
