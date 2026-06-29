"""L3 panel-level checks shared by runtime guardrails and eval scorers."""

from __future__ import annotations

from typing import Any

from judges.schemas import Verdict
from verification.invariants import (
    check_score_change_bounded,
    check_score_change_justification,
    normalize_sentence,
)


def _score_verdict_pair(verdict: Verdict | dict[str, Any]) -> tuple[int, str]:
    if isinstance(verdict, Verdict):
        return verdict.score, verdict.verdict.value
    return verdict.get("score", 0), verdict.get("verdict", "")


def _recommended_fix(verdict: Verdict | dict[str, Any]) -> str | None:
    if isinstance(verdict, Verdict):
        return verdict.recommended_fix
    value = verdict.get("recommended_fix")
    return value if isinstance(value, str) else None


def is_degenerate_panel(verdicts: list[Verdict | dict[str, Any]]) -> bool:
    if len(verdicts) < 2:
        return False
    first_score, first_verdict = _score_verdict_pair(verdicts[0])
    return all(
        _score_verdict_pair(verdict) == (first_score, first_verdict) for verdict in verdicts[1:]
    )


def _as_verdict(verdict: Verdict | dict[str, Any]) -> Verdict:
    return verdict if isinstance(verdict, Verdict) else Verdict.model_validate(verdict)


def assess_revote_quality(
    initial_verdicts: list[Verdict | dict[str, Any]] | None,
    revised_verdicts: list[Verdict | dict[str, Any]] | None,
    *,
    max_delta: int = 3,
) -> dict[str, Any]:
    """Structural checks for post-debate re-vote honesty and bounds."""
    if not initial_verdicts or not revised_verdicts:
        return {
            "revote_present": False,
            "revote_legacy": True,
            "revote_passed": True,
        }

    originals = {_as_verdict(item).judge.value: _as_verdict(item) for item in initial_verdicts}
    revised = [_as_verdict(item) for item in revised_verdicts]

    unexplained: list[str] = []
    out_of_bounds: list[str] = []
    deltas: list[int] = []
    for verdict in revised:
        original = originals.get(verdict.judge.value)
        if original is None:
            continue
        delta = verdict.score - original.score
        deltas.append(delta)
        if delta == 0:
            continue
        if check_score_change_justification(original, verdict) is not None:
            unexplained.append(verdict.judge.value)
        if check_score_change_bounded(original, verdict, max_delta=max_delta) is not None:
            out_of_bounds.append(verdict.judge.value)

    non_zero = [delta for delta in deltas if delta != 0]
    herded_deltas = len(non_zero) >= 4 and len(set(non_zero)) == 1
    pile_on_direction: str | None = None
    directional_pile_on = False
    if len(non_zero) >= 3:
        signs = {1 if delta > 0 else -1 for delta in non_zero}
        if len(signs) == 1:
            directional_pile_on = True
            pile_on_direction = "up" if next(iter(signs)) > 0 else "down"

    degenerate = is_degenerate_panel(revised)
    passed = not unexplained and not out_of_bounds and not degenerate

    return {
        "revote_present": True,
        "revote_legacy": False,
        "revote_passed": passed,
        "revote_degenerate_panel": degenerate,
        "revote_unexplained_changes": unexplained,
        "revote_out_of_bounds_changes": out_of_bounds,
        "revote_herded_deltas": herded_deltas,
        "revote_directional_pile_on": directional_pile_on,
        "revote_pile_on_direction": pile_on_direction,
        "revote_scores_moved": any(delta != 0 for delta in deltas),
        "revote_delta_count": sum(1 for delta in deltas if delta != 0),
    }


def is_degenerate_fixes(verdicts: list[Verdict | dict[str, Any]]) -> bool:
    fixes = [
        normalize_sentence(fix)
        for fix in (_recommended_fix(verdict) for verdict in verdicts)
        if fix and fix.strip()
    ]
    if len(fixes) < 2:
        return False
    first = fixes[0]
    return all(fix == first for fix in fixes[1:])
