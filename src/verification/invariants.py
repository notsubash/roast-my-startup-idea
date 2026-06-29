"""Deterministic L2 invariant checks shared by runtime guardrails and eval scorers."""

from __future__ import annotations

from typing import Any

from judges.schemas import Verdict, VerdictLabel
from verification.result import Check, VerificationResult


def expected_verdict_for_score(score: int) -> VerdictLabel:
    if score <= 3:
        return VerdictLabel.FAIL
    if score <= 6:
        return VerdictLabel.CONDITIONAL
    return VerdictLabel.PASS


def normalize_sentence(text: str) -> str:
    return " ".join(text.lower().split())


def _verdict_fields(verdict: Verdict | dict[str, Any]) -> dict[str, Any]:
    if isinstance(verdict, Verdict):
        return {
            "judge": verdict.judge.value,
            "verdict": verdict.verdict.value,
            "score": verdict.score,
            "key_concern": verdict.key_concern,
            "recommended_fix": verdict.recommended_fix,
            "evidence_to_change_verdict": verdict.evidence_to_change_verdict,
        }
    return {
        "judge": verdict.get("judge", "?"),
        "verdict": verdict.get("verdict", ""),
        "score": verdict.get("score", 0),
        "key_concern": verdict.get("key_concern", ""),
        "recommended_fix": verdict.get("recommended_fix"),
        "evidence_to_change_verdict": verdict.get("evidence_to_change_verdict"),
    }


def check_score_verdict_alignment(*, score: int, verdict_label: str) -> Check | None:
    expected = expected_verdict_for_score(score).value
    if verdict_label != expected:
        return Check(
            code="score_verdict_mismatch",
            message=(
                f"Score {score} inconsistent with verdict {verdict_label} (expected {expected})"
            ),
        )
    return None


def score_verdict_mismatches(verdicts: list[Verdict | dict[str, Any]]) -> list[str]:
    mismatches: list[str] = []
    for verdict in verdicts:
        fields = _verdict_fields(verdict)
        check = check_score_verdict_alignment(
            score=fields["score"],
            verdict_label=fields["verdict"],
        )
        if check is not None:
            mismatches.append(f"{fields['judge']}: {check.message}")
    return mismatches


def check_required_sentence(value: str | None, field_name: str) -> Check | None:
    if not value or not value.strip():
        return Check(
            code=f"{field_name}_missing",
            message=f"{field_name} is required and must not be empty",
        )
    return None


def check_score_change_bounded(
    original: Verdict,
    revised: Verdict,
    *,
    max_delta: int,
) -> Check | None:
    if original.score == revised.score:
        return None
    delta = abs(revised.score - original.score)
    if delta > max_delta:
        return Check(
            code="score_change_out_of_bounds",
            message=(
                f"Score moved {delta} points (max {max_delta} per re-vote); "
                "revise by smaller steps unless debate evidence is overwhelming"
            ),
        )
    return None


def check_score_change_justification(original: Verdict, revised: Verdict) -> Check | None:
    if original.score == revised.score:
        return None
    missing = check_required_sentence(
        revised.evidence_to_change_verdict,
        "evidence_to_change_verdict",
    )
    if missing is not None:
        return Check(
            code="score_change_missing_justification",
            message=(
                "Score changed but evidence_to_change_verdict must cite what in the debate "
                "changed your mind"
            ),
        )
    if normalize_sentence(revised.evidence_to_change_verdict or "") == normalize_sentence(
        original.evidence_to_change_verdict or ""
    ):
        return Check(
            code="score_change_unchanged_evidence",
            message=(
                "Score changed but evidence_to_change_verdict was not updated to cite the debate"
            ),
        )
    return None


def check_not_duplicate(
    left: str | None,
    right: str | None,
    *,
    left_name: str,
    right_name: str,
) -> Check | None:
    if not left or not right:
        return None
    if normalize_sentence(left) == normalize_sentence(right):
        return Check(
            code=f"{left_name}_duplicates_{right_name}",
            message=f"{left_name} must not duplicate {right_name}",
        )
    return None


def verify_verdict_invariants(
    verdict: Verdict | dict[str, Any],
    *,
    expected_judge: str | None = None,
    require_fix_fields: bool = True,
) -> VerificationResult:
    fields = _verdict_fields(verdict)
    checks: list[Check] = []

    if expected_judge is not None and fields["judge"] != expected_judge:
        checks.append(
            Check(
                code="judge_mismatch",
                message=f"Expected judge {expected_judge}, got {fields['judge']}",
            )
        )

    alignment = check_score_verdict_alignment(
        score=fields["score"],
        verdict_label=fields["verdict"],
    )
    if alignment is not None:
        checks.append(alignment)

    if require_fix_fields:
        for field_name in ("recommended_fix", "evidence_to_change_verdict"):
            missing = check_required_sentence(fields[field_name], field_name)
            if missing is not None:
                checks.append(missing)

        fix = fields["recommended_fix"]
        evidence = fields["evidence_to_change_verdict"]
        concern = fields["key_concern"]

        for duplicate in (
            check_not_duplicate(
                fix,
                concern,
                left_name="recommended_fix",
                right_name="key_concern",
            ),
            check_not_duplicate(
                evidence,
                concern,
                left_name="evidence_to_change_verdict",
                right_name="key_concern",
            ),
            check_not_duplicate(
                evidence,
                fix,
                left_name="evidence_to_change_verdict",
                right_name="recommended_fix",
            ),
        ):
            if duplicate is not None:
                checks.append(duplicate)

    return VerificationResult(checks=checks)


def fix_fields_missing_judges(verdicts: list[Verdict | dict[str, Any]]) -> list[str]:
    missing: list[str] = []
    for verdict in verdicts:
        fields = _verdict_fields(verdict)
        if check_required_sentence(fields["recommended_fix"], "recommended_fix"):
            missing.append(fields["judge"])
            continue
        if check_required_sentence(
            fields["evidence_to_change_verdict"], "evidence_to_change_verdict"
        ):
            missing.append(fields["judge"])
    return missing
