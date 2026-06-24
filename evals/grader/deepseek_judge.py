"""DeepSeek LLM-as-judge — one structured call per idea."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from jinja2 import Environment, FileSystemLoader
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from config import PROMPTS_DIR, get_settings
from evals.dataset.loader import GoldenIdea
from evals.grader.schemas import IdeaAuditGrade, normalize_grade_payload
from modeling import build_chat_model

template_env = Environment(loader=FileSystemLoader(PROMPTS_DIR))
GRADER_MAX_ATTEMPTS = 3

_FALLBACK_JSON_SCHEMA_HINT = """\
Return ONLY one JSON object with this exact nested shape (no markdown fences):
{
  "roast_panel": {
    "vc_persona": {"score": 1, "rationale": "..."},
    "engineer_persona": {"score": 1, "rationale": "..."},
    "pm_persona": {"score": 1, "rationale": "..."},
    "customer_persona": {"score": 1, "rationale": "..."},
    "competitor_persona": {"score": 1, "rationale": "..."},
    "roast_specificity": {"score": 1, "rationale": "..."},
    "verdict_score_alignment": true
  },
  "debate": {
    "cross_judge_engagement": {"score": 1, "rationale": "..."},
    "non_repetition": {"score": 1, "rationale": "..."}
  },
  "synthesis": {
    "synthesis_faithfulness": {"score": 1, "rationale": "..."},
    "dissent_preservation": true
  },
  "appeal": {
    "evidence_responsiveness": {"score": 1, "rationale": "..."},
    "score_movement_appropriate": true
  }
}
Use null for appeal when no strong appeal section was provided. Do NOT use flat keys like vc_score.
Keep each rationale under 500 characters."""


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _compact_debate_messages(
    messages: list[dict[str, Any]], limit: int = 16
) -> list[dict[str, Any]]:
    if len(messages) <= limit:
        return messages
    return messages[-limit:]


def build_grader_prompt(
    idea_result: dict[str, Any],
    golden: GoldenIdea | None = None,
) -> tuple[str, str]:
    roast_panel = idea_result.get("roast_panel") or {}
    debate_result = idea_result.get("debate_result") or {}

    appeal_weak = idea_result.get("appeal_weak")
    appeal_strong = idea_result.get("appeal_strong")

    context = {
        "idea_text": idea_result.get("idea_text", ""),
        "expected_panel_avg_range": (golden.expected_panel_avg_range if golden else (1, 10)),
        "must_surface_concerns": golden.must_surface_concerns if golden else [],
        "verdicts": roast_panel.get("verdicts", []),
        "debate_messages": _compact_debate_messages(debate_result.get("debate_messages", [])),
        "final_synthesis": debate_result.get("final_synthesis") or "",
        "appeal_weak": {
            "appeal_text": appeal_weak.get("appeal_text", ""),
            "revised_verdicts": (appeal_weak.get("revised_panel") or {}).get("verdicts", []),
        }
        if appeal_weak
        else None,
        "appeal_strong": {
            "appeal_text": appeal_strong.get("appeal_text", ""),
            "revised_verdicts": (appeal_strong.get("revised_panel") or {}).get("verdicts", []),
        }
        if appeal_strong
        else None,
    }

    system_prompt = template_env.get_template("eval_grader_system.jinja2").render()
    user_prompt = template_env.get_template("eval_grader_user.jinja2").render(**context)
    return system_prompt, user_prompt


def _extract_json_object(text: str) -> Any:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def _response_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    return str(content).strip()


class DeepSeekGrader:
    """Grade one idea with a single DeepSeek structured-output call."""

    def __init__(self, model=None):
        if model is None:
            settings = get_settings()
            model = build_chat_model("deepseek", settings, os.getenv("DEEPSEEK_API_KEY"))
        self.model = model
        self.estimated_input_tokens = 0
        self.calls_made = 0

    def _parse_grade(self, result: Any, idea_id: str) -> IdeaAuditGrade:
        try:
            return IdeaAuditGrade.model_validate(normalize_grade_payload(result))
        except ValidationError as exc:
            raise ValueError(
                f"Grader returned invalid structured output for {idea_id}: {exc}"
            ) from exc

    def grade_idea_result(
        self,
        idea_result: dict[str, Any],
        golden: GoldenIdea | None = None,
    ) -> IdeaAuditGrade:
        idea_id = idea_result.get("idea_id", "unknown")
        system_prompt, user_prompt = build_grader_prompt(idea_result, golden)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        structured = self.model.with_structured_output(IdeaAuditGrade)

        last_validation_error: ValidationError | None = None
        for _attempt in range(GRADER_MAX_ATTEMPTS):
            self.estimated_input_tokens += _estimate_tokens(system_prompt + user_prompt)
            result = structured.invoke(messages)
            self.calls_made += 1

            if result is None:
                continue

            try:
                return self._parse_grade(result, idea_id)
            except ValueError as exc:
                last_validation_error = exc.__cause__
                if not isinstance(last_validation_error, ValidationError):
                    raise

        if last_validation_error is not None:
            raise ValueError(
                f"Grader returned invalid structured output for {idea_id} after "
                f"{GRADER_MAX_ATTEMPTS} attempts: {last_validation_error}"
            ) from last_validation_error

        return self._grade_via_json_fallback(messages, idea_id)

    def _grade_via_json_fallback(
        self,
        messages: list[SystemMessage | HumanMessage],
        idea_id: str,
    ) -> IdeaAuditGrade:
        """Fallback when with_structured_output returns None (common on nested schemas)."""
        fallback_message = HumanMessage(content=_FALLBACK_JSON_SCHEMA_HINT)
        self.estimated_input_tokens += _estimate_tokens(fallback_message.content)
        response = self.model.invoke([*messages, fallback_message])
        self.calls_made += 1
        try:
            return self._parse_grade(_extract_json_object(_response_text(response)), idea_id)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"Grader JSON fallback failed for {idea_id}: {exc}") from exc

    def estimate_idea_tokens(
        self,
        idea_result: dict[str, Any],
        golden: GoldenIdea | None = None,
    ) -> int:
        system_prompt, user_prompt = build_grader_prompt(idea_result, golden)
        return _estimate_tokens(system_prompt + user_prompt) + 500


def estimate_audit_tokens(
    idea_rows: list[dict[str, Any]],
    golden_by_id: dict[str, GoldenIdea | None] | None = None,
) -> int:
    golden_by_id = golden_by_id or {}
    return sum(
        _estimate_tokens("".join(build_grader_prompt(row, golden_by_id.get(row["idea_id"])))) + 500
        for row in idea_rows
    )


def flatten_grade(grade: IdeaAuditGrade) -> dict[str, Any]:
    dimensions = {
        "vc_persona": grade.roast_panel.vc_persona.score,
        "engineer_persona": grade.roast_panel.engineer_persona.score,
        "pm_persona": grade.roast_panel.pm_persona.score,
        "customer_persona": grade.roast_panel.customer_persona.score,
        "competitor_persona": grade.roast_panel.competitor_persona.score,
        "roast_specificity": grade.roast_panel.roast_specificity.score,
        "cross_judge_engagement": grade.debate.cross_judge_engagement.score,
        "non_repetition": grade.debate.non_repetition.score,
        "synthesis_faithfulness": grade.synthesis.synthesis_faithfulness.score,
    }
    if grade.appeal:
        dimensions["evidence_responsiveness"] = grade.appeal.evidence_responsiveness.score

    gates = {
        "verdict_score_alignment": grade.roast_panel.verdict_score_alignment,
        "dissent_preservation": grade.synthesis.dissent_preservation,
    }
    if grade.appeal:
        gates["score_movement_appropriate"] = grade.appeal.score_movement_appropriate

    return {
        "dimensions": dimensions,
        "gates": gates,
        "composite_dimension_avg": round(
            sum(dimensions.values()) / len(dimensions),
            3,
        ),
    }
