"""Reliability and structural completeness metrics."""

from __future__ import annotations

from typing import Any


def score_verdict_score_consistency(verdicts: list[dict[str, Any]]) -> dict[str, Any]:
    """Return pass rate for verdict label vs score band alignment."""
    mismatches: list[str] = []
    for verdict in verdicts:
        judge = verdict.get("judge", "?")
        label = verdict.get("verdict", "")
        score = verdict.get("score", 0)
        if label == "FAIL" and not (1 <= score <= 3):
            mismatches.append(f"{judge}: FAIL with score {score}")
        elif label == "CONDITIONAL" and not (4 <= score <= 6):
            mismatches.append(f"{judge}: CONDITIONAL with score {score}")
        elif label == "PASS" and not (7 <= score <= 10):
            mismatches.append(f"{judge}: PASS with score {score}")
    total = len(verdicts)
    passed = total - len(mismatches)
    rate = passed / total if total else 0.0
    return {
        "verdict_score_consistency_rate": rate,
        "verdict_score_mismatches": mismatches,
        "passed": rate == 1.0,
    }


def score_reliability(
    *,
    judge_attempts: list[dict[str, Any]],
    roast_panel: dict[str, Any] | None,
    debate_result: dict[str, Any] | None,
    max_debate_rounds: int,
) -> dict[str, Any]:
    """Aggregate reliability metrics for one pipeline run."""
    total_judge_calls = len(judge_attempts)
    successful = sum(1 for item in judge_attempts if item.get("success"))
    parse_rate = successful / total_judge_calls if total_judge_calls else 0.0

    panel_complete = bool(roast_panel and len(roast_panel.get("verdicts", [])) == 5)
    synthesis = (debate_result or {}).get("final_synthesis") or ""
    debate_complete = bool(debate_result and synthesis.strip())

    messages = (debate_result or {}).get("debate_messages") or []
    speaker_messages = [m for m in messages if m.get("speaker") != "moderator"]
    expected_speaker_count = max_debate_rounds * 5
    debate_structure_ok = len(speaker_messages) == expected_speaker_count
    has_moderator = any(m.get("speaker") == "moderator" for m in messages)

    consistency = score_verdict_score_consistency(
        (roast_panel or {}).get("verdicts", [])
    )

    return {
        "judge_parse_success_rate": parse_rate,
        "judge_calls_total": total_judge_calls,
        "judge_calls_successful": successful,
        "panel_complete": panel_complete,
        "debate_complete": debate_complete,
        "debate_structure_ok": debate_structure_ok,
        "debate_speaker_count": len(speaker_messages),
        "debate_expected_speaker_count": expected_speaker_count,
        "has_moderator_message": has_moderator,
        **consistency,
    }
