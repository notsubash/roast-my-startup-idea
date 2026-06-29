"""L3 panel-level checks shared by runtime guardrails and eval scorers."""

from __future__ import annotations

from typing import Any

from judges.schemas import Verdict
from verification.invariants import normalize_sentence


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
