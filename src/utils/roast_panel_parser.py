import json
import re

from pydantic import ValidationError

from judges.schemas import RoastPanel, Verdict, judgeLabel


def _strip_code_fences(text: str) -> str:
    """Remove ```json ... ``` wrappers some local models add."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _coerce_verdict_dict(data: dict) -> dict:
    """Normalize known model quirks before schema validation."""
    if "judge" in data and isinstance(data["judge"], str):
        data["judge"] = data["judge"].strip().lower()
    if "verdict" in data and isinstance(data["verdict"], str):
        data["verdict"] = data["verdict"].strip().upper()
    return data


def _coerce_roast_panel_dict(data: dict) -> dict:
    """Normalize all verdicts in a panel before schema validation."""
    if "verdicts" in data and isinstance(data["verdicts"], list):
        for verdict in data["verdicts"]:
            if isinstance(verdict, dict):
                _coerce_verdict_dict(verdict)
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


def _parse_labeled_verdict(content: str, judge: str | None) -> dict | None:
    if judge is None:
        return None

    match = re.search(
        r"Verdict:\s*\**(?P<verdict>PASS|FAIL|CONDITIONAL)\**"
        r".*?Roast:\s*(?P<roast>.*?)"
        r"\n\s*Score:\s*\**(?P<score>\d+)(?:\s*/\s*10)?\**"
        r".*?Key concern:\s*(?P<key_concern>.*)",
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        return None

    return {
        "judge": judge,
        "verdict": match.group("verdict"),
        "roast": match.group("roast").strip(),
        "score": int(match.group("score")),
        "key_concern": match.group("key_concern").strip(),
    }


def _panel_from_verdicts(verdicts_by_judge: dict[str, Verdict]) -> RoastPanel:
    ordered_verdicts = [
        verdicts_by_judge[judge.value]
        for judge in judgeLabel
        if judge.value in verdicts_by_judge
    ]
    return RoastPanel.model_validate({"verdicts": ordered_verdicts})


def extract_roast_panel(result: dict) -> RoastPanel:
    """Pull a validated RoastPanel out of a DeepAgents result.

    Preferred path is a structured/final RoastPanel. If the local model stops
    after tool calls, fall back to assembling the panel from individual judge
    ToolMessage JSON payloads.
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

        data = _parse_json_dict(content)
        if data is None:
            tool_call_id = getattr(message, "tool_call_id", None)
            data = _parse_labeled_verdict(content, tool_call_judges.get(tool_call_id))
            if data is None:
                continue

        if "verdicts" in data:
            try:
                return RoastPanel.model_validate(_coerce_roast_panel_dict(data))
            except ValidationError as error:
                last_validation_error = error
                continue

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
