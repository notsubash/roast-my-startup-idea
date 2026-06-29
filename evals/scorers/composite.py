"""Structural scoring for Tier 1 local eval (no keyword heuristics)."""

from __future__ import annotations

from typing import Any

from evals.scorers.reliability import score_reliability


def score_idea_result(
    result: dict[str, Any],
    *,
    max_debate_rounds: int,
    **_ignored: Any,
) -> dict[str, Any]:
    """Score pipeline structural reliability only. Quality is judged in Tier 2."""
    roast_panel = result.get("roast_panel") or {}
    debate_result = result.get("debate_result") or {}

    reliability = score_reliability(
        judge_attempts=result.get("judge_attempts", []),
        roast_panel=roast_panel,
        debate_result=debate_result,
        max_debate_rounds=max_debate_rounds,
    )

    legacy_output = reliability.get("fix_fields_legacy") or reliability.get("synthesis_legacy")
    fix_ok = reliability.get("fix_fields_complete", False)
    synthesis_ok = reliability.get("synthesis_parses", False)
    fixes_ok = fix_ok and not reliability.get("panel_fixes_degenerate", False)

    passed = (
        reliability.get("judge_parse_success_rate", 0) >= 0.95
        and reliability.get("panel_complete", False)
        and reliability.get("debate_complete", False)
        and reliability.get("debate_structure_ok", False)
        and reliability.get("passed", False)
        and (legacy_output or (fixes_ok and synthesis_ok))
    )

    return {
        "reliability": reliability,
        "passed": passed,
    }
