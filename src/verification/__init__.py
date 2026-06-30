"""Deterministic verification shared by runtime guardrails and eval scorers."""

from verification.invariants import (
    expected_verdict_for_score,
    fix_fields_missing_judges,
    is_generic_evidence,
    score_verdict_mismatches,
    verify_verdict_invariants,
)
from verification.lens import (
    DERIVED_HINT_PREFIX,
    JUDGE_ROLE_NAMES,
    assess_lens_uniqueness,
    coaching_hint,
    find_duplicate_evidence_judges,
    panel_quality_for_api,
)
from verification.panel import assess_revote_quality, is_degenerate_fixes, is_degenerate_panel
from verification.result import Check, VerificationResult

__all__ = [
    "Check",
    "VerificationResult",
    "expected_verdict_for_score",
    "fix_fields_missing_judges",
    "is_generic_evidence",
    "assess_lens_uniqueness",
    "panel_quality_for_api",
    "assess_revote_quality",
    "coaching_hint",
    "DERIVED_HINT_PREFIX",
    "find_duplicate_evidence_judges",
    "JUDGE_ROLE_NAMES",
    "is_degenerate_fixes",
    "is_degenerate_panel",
    "score_verdict_mismatches",
    "verify_verdict_invariants",
]
