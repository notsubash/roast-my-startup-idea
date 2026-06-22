import json
import re

from pydantic import ValidationError

from judges.schemas import RoastPanel, Verdict, judgeLabel


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


_VERDICT_KEYS = {"judge", "verdict", "roast", "score", "key_concern"}


def _coerce_verdict_dict(data: dict) -> dict:
    """Normalize known model quirks before schema validation."""
    if "judge" in data and isinstance(data["judge"], str):
        data["judge"] = data["judge"].strip().lower()
    if "verdict" in data and isinstance(data["verdict"], str):
        data["verdict"] = data["verdict"].strip().upper()
    for key in list(data.keys()):
        if key not in _VERDICT_KEYS:
            del data[key]
    return data


def _parse_json_dict(content: str) -> dict | None:
    candidate = _strip_code_fences(content)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _extract_markdown_field(content: str, label: str) -> str | None:
    pattern = rf"(?is){re.escape(label)}\s*:\s*(.+?)(?=\n\s*(?:Verdict|Roast|Score|Key concern)\s*:|\Z)"
    match = re.search(pattern, content)
    if not match:
        return None
    value = match.group(1).strip()
    return re.sub(r"^\*\*|\*\*$", "", value).strip()


def _parse_markdown_verdict(content: str, judge: str | None) -> dict | None:
    if judge is None:
        return None

    verdict = _extract_markdown_field(content, "Verdict")
    roast = _extract_markdown_field(content, "Roast")
    score = _extract_markdown_field(content, "Score")
    key_concern = _extract_markdown_field(content, "Key concern")

    if not all([verdict, roast, score, key_concern]):
        return None

    score_match = re.search(r"\d+", score or "")
    if not score_match:
        return None

    return {
        "judge": judge,
        "verdict": verdict,
        "roast": roast,
        "score": int(score_match.group(0)),
        "key_concern": key_concern,
    }


def _judge_from_subagent_type(subagent_type: str | None) -> str | None:
    if not isinstance(subagent_type, str):
        return None
    judge = subagent_type.removesuffix("_judge").strip().lower()
    if judge in {label.value for label in judgeLabel}:
        return judge
    return None


def _tool_call_judges(result: dict) -> dict[str, str]:
    tool_call_judges: dict[str, str] = {}
    for message in result.get("messages", []):
        for tool_call in getattr(message, "tool_calls", None) or []:
            tool_call_id = tool_call.get("id")
            args = tool_call.get("args") or {}
            judge = _judge_from_subagent_type(args.get("subagent_type"))
            if isinstance(tool_call_id, str) and judge is not None:
                tool_call_judges[tool_call_id] = judge
    return tool_call_judges


def _panel_from_verdicts(verdicts_by_judge: dict[str, Verdict]) -> RoastPanel:
    ordered_verdicts = [
        verdicts_by_judge[judge.value]
        for judge in judgeLabel
        if judge.value in verdicts_by_judge
    ]
    return RoastPanel.model_validate({"verdicts": ordered_verdicts})


def extract_roast_panel(result: dict) -> RoastPanel:
    """Pull a validated RoastPanel from a DeepAgents result.

    With response_format=Verdict on judge subagents, ToolMessages contain
    clean JSON. We try the structured_response first, then fall back to
    assembling individual Verdict objects from ToolMessages, deduplicating
    by judge name (first seen wins).
    """
    structured = result.get("structured_response")
    if structured is not None:
        if isinstance(structured, RoastPanel):
            return structured
        return RoastPanel.model_validate(structured)

    expected_judges = {judge.value for judge in judgeLabel}
    verdicts_by_judge: dict[str, Verdict] = {}
    tool_call_judges = _tool_call_judges(result)
    last_validation_error: ValidationError | None = None

    for message in reversed(result.get("messages", [])):
        content = getattr(message, "content", None)
        if not isinstance(content, str) or not content.strip():
            continue

        tool_call_id = getattr(message, "tool_call_id", None)
        tool_judge = tool_call_judges.get(tool_call_id)

        data = _parse_json_dict(content)
        if data is None:
            data = _parse_markdown_verdict(content, tool_judge)
            if data is None:
                continue

        if "verdicts" in data and isinstance(data["verdicts"], list):
            try:
                coerced = [_coerce_verdict_dict(v) for v in data["verdicts"] if isinstance(v, dict)]
                return RoastPanel.model_validate({"verdicts": coerced})
            except ValidationError as error:
                last_validation_error = error
                continue

        if "judge" not in data:
            if tool_judge:
                data["judge"] = tool_judge

        try:
            verdict = Verdict.model_validate(_coerce_verdict_dict(data))
        except ValidationError as error:
            last_validation_error = error
            continue

        verdicts_by_judge.setdefault(verdict.judge.value, verdict)
        if expected_judges.issubset(verdicts_by_judge):
            return _panel_from_verdicts(verdicts_by_judge)

    if verdicts_by_judge:
        return _panel_from_verdicts(verdicts_by_judge)

    if last_validation_error is not None:
        raise ValueError(
            "Found JSON content, but it failed RoastPanel/Verdict validation:\n"
            f"{last_validation_error}"
        )

    raise ValueError("No valid RoastPanel or individual judge verdicts found")
