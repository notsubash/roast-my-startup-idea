"""JSON and markdown report generation for eval runs."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any


def utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def write_json_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def summarize_run(payload: dict[str, Any]) -> str:
    tier = payload.get("tier", "local")
    lines = [
        "# Eval Report",
        "",
        f"- **Tier:** {tier}",
        f"- **Timestamp:** {payload.get('timestamp')}",
        f"- **Ideas evaluated:** {payload.get('ideas_evaluated', 0)}",
    ]
    if tier == "audit":
        lines.append(f"- **Grader:** {payload.get('grader', 'deepseek')}")
        lines.append(f"- **API calls:** {payload.get('api_calls', 'n/a')}")
    else:
        lines.append(f"- **Runtime:** {payload.get('runtime', 'local')}")

    lines.extend(["", "## Aggregate Metrics", ""])
    aggregate = payload.get("aggregate", {})
    for key, value in aggregate.items():
        lines.append(f"- **{key}:** {value}")
    lines.extend(["", "## Per-Idea Results", ""])

    for idea_result in payload.get("ideas", []):
        lines.append(f"### {idea_result['idea_id']}")
        if "grader" in idea_result:
            grader = idea_result["grader"]
            lines.append(f"- Composite dimension avg: {grader.get('composite_dimension_avg')}")
            failed_gates = [
                name for name, passed in grader.get("gates", {}).items() if passed is False
            ]
            if failed_gates:
                lines.append(f"- Failed gates: {', '.join(failed_gates)}")
        metrics = idea_result.get("metrics", {})
        if metrics:
            lines.append(f"- Structural pass: {metrics.get('passed')}")
            reliability = metrics.get("reliability", {})
            if reliability:
                lines.append(
                    f"- Judge parse success: {reliability.get('judge_parse_success_rate')}"
                )
            lens = metrics.get("lens", {})
            if lens and not lens.get("lens_legacy", True):
                lines.append(
                    f"- Lens differentiation: {lens.get('lens_differentiation_passed')}"
                )
                if not lens.get("lens_differentiation_passed"):
                    duplicates = lens.get("lens_duplicate_evidence_judges") or []
                    if duplicates:
                        lines.append(f"- Duplicate evidence judges: {', '.join(duplicates)}")
                    for pair in lens.get("lens_overlapping_concern_pairs") or []:
                        if isinstance(pair, dict):
                            lines.append(
                                f"- Overlapping concerns: {pair.get('left')}/{pair.get('right')} "
                                f"(sim {pair.get('similarity')})"
                            )
                    for pair in lens.get("lens_overlapping_evidence_pairs") or []:
                        if isinstance(pair, dict):
                            lines.append(
                                f"- Overlapping evidence: {pair.get('left')}/{pair.get('right')} "
                                f"(sim {pair.get('similarity')})"
                            )
                    generic_rate = lens.get("lens_generic_evidence_rate")
                    if isinstance(generic_rate, int | float) and generic_rate > 0.4:
                        lines.append(f"- Generic evidence rate: {generic_rate}")
        timings = idea_result.get("timings", {})
        if timings.get("total_seconds") is not None:
            lines.append(f"- Total seconds: {timings.get('total_seconds')}")
        lines.append("")

    regressions = payload.get("regressions")
    if regressions:
        lines.extend(["## Regressions", ""])
        for item in regressions:
            lines.append(f"- {item}")
        lines.append("")

    return "\n".join(lines)


def write_markdown_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(summarize_run(payload) + "\n", encoding="utf-8")


def load_json_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def list_reports(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.glob("*.json"), key=lambda item: item.stat().st_mtime)


def compare_audit_reports(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    *,
    regression_threshold: float = 0.5,
) -> list[str]:
    if not previous:
        return []

    regressions: list[str] = []
    prev_by_id = {item["idea_id"]: item for item in previous.get("ideas", [])}
    for idea in current.get("ideas", []):
        idea_id = idea["idea_id"]
        prior = prev_by_id.get(idea_id)
        if not prior:
            continue
        current_dims = idea.get("grader", {}).get("dimensions", {})
        prior_dims = prior.get("grader", {}).get("dimensions", {})
        for name, score in current_dims.items():
            if not isinstance(score, int | float):
                continue
            old = prior_dims.get(name)
            if isinstance(old, int | float) and old - score >= regression_threshold:
                regressions.append(f"{idea_id}.{name} dropped {old:.2f} -> {score:.2f}")
        for gate, passed in idea.get("grader", {}).get("gates", {}).items():
            if passed is False and prior.get("grader", {}).get("gates", {}).get(gate) is True:
                regressions.append(f"{idea_id}.{gate} gate newly failing")
    return regressions
