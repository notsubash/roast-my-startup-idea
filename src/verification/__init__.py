"""Deterministic verification shared by runtime guardrails and eval scorers."""

from verification.invariants import (
    expected_verdict_for_score,
    fix_fields_missing_judges,
    score_verdict_mismatches,
    verify_verdict_invariants,
)
from verification.panel import is_degenerate_fixes, is_degenerate_panel
from verification.result import Check, VerificationResult

__all__ = [
    "Check",
    "VerificationResult",
    "expected_verdict_for_score",
    "fix_fields_missing_judges",
    "is_degenerate_fixes",
    "is_degenerate_panel",
    "score_verdict_mismatches",
    "verify_verdict_invariants",
]
