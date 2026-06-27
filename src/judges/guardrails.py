"""Post-validation guardrails for judge outputs."""

from judges.schemas import Verdict, VerdictLabel


class GuardrailError(ValueError):
    """Verdict failed a consistency or degeneracy check."""


def expected_verdict_for_score(score: int) -> VerdictLabel:
    if score <= 3:
        return VerdictLabel.FAIL
    if score <= 6:
        return VerdictLabel.CONDITIONAL
    return VerdictLabel.PASS


def validate_verdict_guardrails(verdict: Verdict) -> None:
    expected = expected_verdict_for_score(verdict.score)
    if verdict.verdict != expected:
        raise GuardrailError(
            f"Score {verdict.score} inconsistent with verdict {verdict.verdict.value} "
            f"(expected {expected.value})"
        )


def validate_structured_verdict(verdict: Verdict, *, judge: str) -> None:
    if verdict.judge.value != judge:
        raise GuardrailError(f"Expected judge {judge}, got {verdict.judge.value}")
    validate_verdict_guardrails(verdict)


def is_degenerate_panel(verdicts: list[Verdict]) -> bool:
    if len(verdicts) < 2:
        return False
    first = verdicts[0]
    return all(
        verdict.score == first.score and verdict.verdict == first.verdict
        for verdict in verdicts[1:]
    )
