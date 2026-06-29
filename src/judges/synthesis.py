"""Structured moderator synthesis — parse, format, and compact summaries."""

from enum import StrEnum
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from judges.schemas import RoastPanel, Verdict
from verification import is_degenerate_fixes

SYNTHESIS_ITEM_MAX_LENGTH = 300
BIGGEST_DISAGREEMENT_MAX_LENGTH = 400
_NUMBERED_PROSE_SYNTHESIS = re.compile(r"\*\*1\.\s*Overall verdict:\*\*", re.I)


def is_numbered_prose_synthesis(text: str | None) -> bool:
    """True when moderator prose fallback matches the expected five-section shape."""
    return bool(text and _NUMBERED_PROSE_SYNTHESIS.search(text))


class OverallRecommendation(StrEnum):
    GO = "GO"
    ITERATE = "ITERATE"
    NO_GO = "NO-GO"


class ConfidenceLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Synthesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_recommendation: OverallRecommendation
    confidence: ConfidenceLevel
    top_strengths: list[str] = Field(default_factory=list, max_length=3)
    top_risks: list[str] = Field(default_factory=list, max_length=3)
    biggest_disagreement: str = Field(
        min_length=5,
        max_length=BIGGEST_DISAGREEMENT_MAX_LENGTH,
        description="The single biggest point of disagreement among judges.",
    )

    @field_validator("top_strengths", "top_risks", mode="before")
    @classmethod
    def trim_bounded_list(cls, value):
        if not isinstance(value, list):
            return value
        trimmed = [item for item in value if isinstance(item, str) and item.strip()][:3]
        return trimmed

    @field_validator("top_strengths", "top_risks")
    @classmethod
    def validate_list_items(cls, items: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in items:
            text = " ".join(item.split())
            if len(text) > SYNTHESIS_ITEM_MAX_LENGTH:
                text = text[: SYNTHESIS_ITEM_MAX_LENGTH - 3].rstrip() + "..."
            cleaned.append(text)
        return cleaned


def parse_structured_synthesis(debate_result: dict[str, Any] | None) -> Synthesis | None:
    if not debate_result:
        return None
    raw = debate_result.get("structured_synthesis")
    if raw is None:
        return None
    try:
        return Synthesis.model_validate(raw)
    except Exception:
        return None


def synthesis_to_prose(synthesis: Synthesis) -> str:
    lines = [
        f"**Recommendation:** {synthesis.overall_recommendation.value}",
        f"**Confidence:** {synthesis.confidence.value}",
    ]
    if synthesis.top_strengths:
        lines.append("**Strengths:**")
        lines.extend(f"- {item}" for item in synthesis.top_strengths)
    if synthesis.top_risks:
        lines.append("**Top risks:**")
        lines.extend(f"- {item}" for item in synthesis.top_risks)
    lines.append(f"**Biggest disagreement:** {synthesis.biggest_disagreement}")
    return "\n".join(lines)


def top_priorities(
    synthesis: Synthesis | None,
    roast_panel: RoastPanel | None = None,
    *,
    limit: int = 3,
) -> list[str]:
    if synthesis and synthesis.top_risks:
        return synthesis.top_risks[:limit]

    if roast_panel is None:
        return []

    verdict_rank = {"FAIL": 0, "CONDITIONAL": 1, "PASS": 2}

    def sort_key(verdict: Verdict) -> tuple[int, int]:
        return (verdict_rank.get(verdict.verdict.value, 9), verdict.score)

    fixes: list[str] = []
    seen: set[str] = set()
    for verdict in sorted(roast_panel.verdicts, key=sort_key):
        fix = (verdict.recommended_fix or "").strip()
        if not fix or fix in seen:
            continue
        seen.add(fix)
        fixes.append(fix)
        if len(fixes) >= limit:
            break
    return fixes


def synthesis_compact_summary(debate_result: dict[str, Any] | None) -> str:
    structured = parse_structured_synthesis(debate_result)
    if structured is not None:
        parts = [
            f"{structured.overall_recommendation.value} ({structured.confidence.value})",
        ]
        if structured.top_risks:
            parts.append("Risks: " + "; ".join(structured.top_risks[:2]))
        elif structured.biggest_disagreement:
            parts.append(structured.biggest_disagreement)
        return " | ".join(parts)

    return str((debate_result or {}).get("final_synthesis") or "")


def assess_verdict_output_quality(
    roast_panel: RoastPanel | None,
    debate_result: dict[str, Any] | None,
) -> dict[str, Any]:
    """Surface degraded output for UI when local models return weak structured content."""
    verdicts = roast_panel.verdicts if roast_panel else []
    structured = parse_structured_synthesis(debate_result)
    reasons: list[str] = []

    if verdicts and is_degenerate_fixes(verdicts):
        reasons.append("Judges returned near-identical recommended fixes.")

    final_synthesis = str((debate_result or {}).get("final_synthesis") or "")
    if (
        structured is None
        and final_synthesis.strip()
        and not is_numbered_prose_synthesis(final_synthesis)
    ):
        reasons.append("Moderator fell back to free-text synthesis.")

    if structured is not None and structured.confidence == ConfidenceLevel.LOW:
        reasons.append("Moderator reported low confidence in the recommendation.")

    return {
        "low_confidence": bool(reasons),
        "reasons": reasons,
        "structured_synthesis": structured is not None,
        "degenerate_fixes": is_degenerate_fixes(verdicts) if verdicts else False,
    }
