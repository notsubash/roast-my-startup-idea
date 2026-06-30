"""Reliability and structural completeness metrics."""

from __future__ import annotations

from typing import Any

from config import get_settings
from judges.synthesis import Synthesis
from verification import (
    assess_lens_uniqueness,
    assess_revote_quality,
    fix_fields_missing_judges,
    is_degenerate_fixes,
    score_verdict_mismatches,
)


def score_verdict_score_consistency(verdicts: list[dict[str, Any]]) -> dict[str, Any]:
    """Return pass rate for verdict label vs score band alignment."""
    mismatches = score_verdict_mismatches(verdicts)
    total = len(verdicts)
    passed = total - len(mismatches)
    rate = passed / total if total else 0.0
    return {
        "verdict_score_consistency_rate": rate,
        "verdict_score_mismatches": mismatches,
        "passed": rate == 1.0,
    }


def score_fix_fields(verdicts: list[dict[str, Any]]) -> dict[str, Any]:
    if not verdicts:
        return {
            "fix_fields_missing_judges": [],
            "fix_fields_complete": False,
            "fix_fields_legacy": False,
        }
    # ponytail: pre-Feature-1 baselines omit fix fields entirely; skip gate until refreshed
    if not any(verdict.get("recommended_fix") for verdict in verdicts):
        return {
            "fix_fields_missing_judges": [],
            "fix_fields_complete": True,
            "fix_fields_legacy": True,
        }
    missing = fix_fields_missing_judges(verdicts)
    return {
        "fix_fields_missing_judges": missing,
        "fix_fields_complete": not missing,
        "fix_fields_legacy": False,
    }


def score_synthesis_structure(debate_result: dict[str, Any] | None) -> dict[str, Any]:
    if not debate_result:
        return {
            "synthesis_structured": False,
            "synthesis_parses": False,
            "synthesis_legacy": True,
        }
    raw = debate_result.get("structured_synthesis")
    if raw is None:
        has_prose = bool(str(debate_result.get("final_synthesis") or "").strip())
        return {
            "synthesis_structured": False,
            "synthesis_parses": has_prose,
            "synthesis_legacy": True,
        }
    try:
        Synthesis.model_validate(raw)
        return {
            "synthesis_structured": True,
            "synthesis_parses": True,
            "synthesis_legacy": False,
        }
    except Exception:
        return {
            "synthesis_structured": True,
            "synthesis_parses": False,
            "synthesis_legacy": False,
        }


def score_revote_quality(debate_result: dict[str, Any] | None) -> dict[str, Any]:
    if not debate_result:
        return {"revote_present": False, "revote_legacy": True, "revote_passed": True}
    return assess_revote_quality(
        debate_result.get("initial_verdicts"),
        debate_result.get("revised_verdicts"),
        max_delta=get_settings().max_revote_score_delta,
    )


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

    verdicts = (roast_panel or {}).get("verdicts", [])
    panel_complete = bool(roast_panel and len(verdicts) == 5)
    synthesis = (debate_result or {}).get("final_synthesis") or ""
    debate_complete = bool(debate_result and synthesis.strip())

    messages = (debate_result or {}).get("debate_messages") or []
    speaker_messages = [m for m in messages if m.get("speaker") != "moderator"]
    expected_speaker_count = max_debate_rounds * 5
    debate_structure_ok = len(speaker_messages) == expected_speaker_count
    has_moderator = any(m.get("speaker") == "moderator" for m in messages)

    consistency = score_verdict_score_consistency(verdicts)
    fix_fields = score_fix_fields(verdicts)
    synthesis_structure = score_synthesis_structure(debate_result)
    revote_quality = score_revote_quality(debate_result)
    lens_uniqueness = assess_lens_uniqueness(verdicts)

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
        "panel_fixes_degenerate": is_degenerate_fixes(verdicts),
        **consistency,
        **fix_fields,
        **synthesis_structure,
        **revote_quality,
        **lens_uniqueness,
    }
