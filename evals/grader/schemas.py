"""Structured schemas for DeepSeek grader outputs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_DEFAULT_RATIONALE = "Rationale not provided by grader."
_RATIONALE_MIN = 10
_RATIONALE_MAX = 500

_PERSONA_ALIASES: tuple[tuple[str, str], ...] = (
    ("vc", "vc_persona"),
    ("engineer", "engineer_persona"),
    ("pm", "pm_persona"),
    ("customer", "customer_persona"),
    ("competitor", "competitor_persona"),
)


class DimensionScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: int = Field(ge=1, le=5, description="Score from 1 (poor) to 5 (excellent)")
    rationale: str = Field(min_length=10, max_length=500)


class RoastPanelGrade(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vc_persona: DimensionScore
    engineer_persona: DimensionScore
    pm_persona: DimensionScore
    customer_persona: DimensionScore
    competitor_persona: DimensionScore
    roast_specificity: DimensionScore
    verdict_score_alignment: bool


class DebateGrade(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cross_judge_engagement: DimensionScore
    non_repetition: DimensionScore


class SynthesisGrade(BaseModel):
    model_config = ConfigDict(extra="forbid")

    synthesis_faithfulness: DimensionScore
    dissent_preservation: bool


class AppealGrade(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_responsiveness: DimensionScore
    score_movement_appropriate: bool


class IdeaAuditGrade(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roast_panel: RoastPanelGrade
    debate: DebateGrade
    synthesis: SynthesisGrade
    appeal: AppealGrade | None = None


def _as_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return value
    return {}


def _clamp_rationale(text: str | None) -> str:
    rationale = (text or "").strip() or _DEFAULT_RATIONALE
    if len(rationale) < _RATIONALE_MIN:
        return _DEFAULT_RATIONALE
    if len(rationale) <= _RATIONALE_MAX:
        return rationale
    return rationale[:_RATIONALE_MAX]


def _coerce_dimension(section: dict[str, Any], key: str) -> dict[str, Any] | None:
    value = section.get(key)
    if isinstance(value, dict) and "score" in value:
        return {
            "score": value["score"],
            "rationale": _clamp_rationale(value.get("rationale")),
        }
    if isinstance(value, int):
        return {
            "score": value,
            "rationale": _clamp_rationale(section.get(f"{key}_rationale")),
        }
    return None


def _normalize_persona(section: dict[str, Any], prefix: str, target: str) -> dict[str, Any] | None:
    existing = section.get(target)
    if isinstance(existing, dict) and "score" in existing:
        return {
            "score": existing["score"],
            "rationale": _clamp_rationale(existing.get("rationale")),
        }
    score = section.get(f"{prefix}_score")
    if score is not None:
        return {
            "score": score,
            "rationale": _clamp_rationale(section.get(f"{prefix}_rationale")),
        }
    return None


def _normalize_roast_panel(section: Any) -> dict[str, Any]:
    raw = _as_dict(section)
    normalized: dict[str, Any] = {}
    for prefix, target in _PERSONA_ALIASES:
        persona = _normalize_persona(raw, prefix, target)
        if persona is not None:
            normalized[target] = persona
    roast_specificity = _coerce_dimension(raw, "roast_specificity")
    if roast_specificity is not None:
        normalized["roast_specificity"] = roast_specificity
    if "verdict_score_alignment" in raw:
        normalized["verdict_score_alignment"] = raw["verdict_score_alignment"]
    return normalized


def _normalize_dimension_section(section: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    raw = _as_dict(section)
    normalized: dict[str, Any] = {}
    for key in keys:
        dimension = _coerce_dimension(raw, key)
        if dimension is not None:
            normalized[key] = dimension
    return normalized


def normalize_grade_payload(raw: Any) -> dict[str, Any]:
    """Coerce flat grader JSON (vc_score/vc_rationale) into nested schema shape."""
    payload = _as_dict(raw)
    normalized: dict[str, Any] = {}
    if "roast_panel" in payload:
        raw_roast = _as_dict(payload["roast_panel"])
        roast_panel = _normalize_roast_panel(raw_roast)
        if "verdict_score_alignment" in raw_roast:
            roast_panel["verdict_score_alignment"] = raw_roast["verdict_score_alignment"]
        normalized["roast_panel"] = roast_panel
    if "debate" in payload:
        debate = _normalize_dimension_section(
            payload["debate"],
            ("cross_judge_engagement", "non_repetition"),
        )
        normalized["debate"] = debate
    if "synthesis" in payload:
        synthesis = _normalize_dimension_section(
            payload["synthesis"],
            ("synthesis_faithfulness",),
        )
        raw_synthesis = _as_dict(payload["synthesis"])
        if "dissent_preservation" in raw_synthesis:
            synthesis["dissent_preservation"] = raw_synthesis["dissent_preservation"]
        normalized["synthesis"] = synthesis
    if "appeal" in payload:
        appeal_value = payload["appeal"]
        if appeal_value is None:
            normalized["appeal"] = None
        else:
            appeal = _normalize_dimension_section(
                appeal_value,
                ("evidence_responsiveness",),
            )
            raw_appeal = _as_dict(appeal_value)
            if "score_movement_appropriate" in raw_appeal:
                appeal["score_movement_appropriate"] = raw_appeal["score_movement_appropriate"]
            normalized["appeal"] = appeal
    return normalized
