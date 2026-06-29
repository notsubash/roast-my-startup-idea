"""Appeal discrimination metrics for Tier 1 eval."""

from __future__ import annotations

from typing import Any

from appeal.coaching import appeal_score_movement
from judges.schemas import RoastPanel


def _panel_from_dict(raw: dict[str, Any] | None) -> RoastPanel | None:
    if not raw:
        return None
    try:
        return RoastPanel.model_validate(raw)
    except Exception:
        return None


def score_appeal_case(
    baseline: RoastPanel | None,
    appeal_result: dict[str, Any] | None,
) -> dict[str, Any]:
    if baseline is None or not appeal_result or not appeal_result.get("success"):
        return {
            "appeal_present": False,
            "positive_moves": 0,
            "net_delta": 0,
        }
    revised = _panel_from_dict(appeal_result.get("revised_panel"))
    if revised is None:
        return {
            "appeal_present": False,
            "positive_moves": 0,
            "net_delta": 0,
        }
    movement = appeal_score_movement(baseline, revised)
    return {
        "appeal_present": True,
        **movement,
    }


def score_appeal_discrimination(
    result: dict[str, Any],
    *,
    expected_delta_direction: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Targeted appeals should move scores more than generic ones."""
    baseline = _panel_from_dict(result.get("roast_panel"))
    weak = score_appeal_case(baseline, result.get("appeal_weak"))
    strong = score_appeal_case(baseline, result.get("appeal_strong"))

    expected = expected_delta_direction or {}
    weak_expected = expected.get("weak", "flat")
    strong_expected = expected.get("strong", "up")

    beats_weak = True
    if weak["appeal_present"] and strong["appeal_present"]:
        beats_weak = (
            strong["positive_moves"] > weak["positive_moves"]
            or strong["net_delta"] > weak["net_delta"]
        )

    weak_direction_ok = True
    if weak["appeal_present"] and weak_expected == "flat":
        weak_direction_ok = weak["positive_moves"] == 0

    strong_direction_ok = True
    if strong["appeal_present"]:
        if strong_expected == "up":
            strong_direction_ok = strong["positive_moves"] > 0
        elif strong_expected == "flat":
            strong_direction_ok = strong["positive_moves"] == 0

    # ponytail: discrimination (strong vs weak) is the Phase 3 gate; direction checks are advisory
    passed = beats_weak if weak["appeal_present"] and strong["appeal_present"] else True
    return {
        "appeal_weak": weak,
        "appeal_strong": strong,
        "appeal_beats_weak": beats_weak,
        "appeal_weak_direction_ok": weak_direction_ok,
        "appeal_strong_direction_ok": strong_direction_ok,
        "appeal_discrimination_passed": passed,
        "passed": passed,
    }
