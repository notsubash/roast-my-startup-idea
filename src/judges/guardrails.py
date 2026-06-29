"""Post-validation guardrails for judge outputs (runtime adapter over verification)."""

from judges.schemas import Verdict
from verification import (
    expected_verdict_for_score,
    is_degenerate_panel,
    verify_verdict_invariants,
)
from verification.invariants import (
    check_not_duplicate,
    check_required_sentence,
    check_score_change_justification,
    check_score_verdict_alignment,
)

# Re-export panel helper for existing imports.
__all__ = [
    "GuardrailError",
    "expected_verdict_for_score",
    "is_degenerate_panel",
    "validate_revote_verdict",
    "validate_structured_verdict",
    "validate_verdict_guardrails",
]


class GuardrailError(ValueError):
    """Verdict failed a consistency or degeneracy check."""


def _raise_first_failure(result) -> None:
    failure = result.first_failure()
    if failure is not None:
        raise GuardrailError(failure.message)


def validate_verdict_guardrails(verdict: Verdict) -> None:
    check = check_score_verdict_alignment(
        score=verdict.score,
        verdict_label=verdict.verdict.value,
    )
    if check is not None:
        raise GuardrailError(check.message)


def validate_structured_verdict(verdict: Verdict, *, judge: str) -> None:
    _raise_first_failure(
        verify_verdict_invariants(verdict, expected_judge=judge, require_fix_fields=True)
    )


def validate_revote_verdict(original: Verdict, revised: Verdict) -> None:
    validate_structured_verdict(revised, judge=revised.judge.value)
    check = check_score_change_justification(original, revised)
    if check is not None:
        raise GuardrailError(check.message)


def validate_recommended_fix(value: str | None, *, key_concern: str) -> None:
    missing = check_required_sentence(value, "recommended_fix")
    if missing is not None:
        raise GuardrailError(missing.message)
    duplicate = check_not_duplicate(
        value,
        key_concern,
        left_name="recommended_fix",
        right_name="key_concern",
    )
    if duplicate is not None:
        raise GuardrailError(duplicate.message)


def validate_evidence_to_change_verdict(
    value: str | None,
    *,
    key_concern: str,
    recommended_fix: str | None,
) -> None:
    missing = check_required_sentence(value, "evidence_to_change_verdict")
    if missing is not None:
        raise GuardrailError(missing.message)
    for duplicate in (
        check_not_duplicate(
            value,
            key_concern,
            left_name="evidence_to_change_verdict",
            right_name="key_concern",
        ),
        check_not_duplicate(
            value,
            recommended_fix,
            left_name="evidence_to_change_verdict",
            right_name="recommended_fix",
        ),
    ):
        if duplicate is not None:
            raise GuardrailError(duplicate.message)
