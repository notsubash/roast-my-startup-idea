"""Tier 2 DeepSeek quality audit CLI."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evals import BASELINES_DIR, EVAL_RUNTIMES, RESULTS_AUDITS_DIR, RESULTS_LOCAL_DIR
from evals.dataset.loader import filter_ideas, load_golden_ideas
from evals.grader.deepseek_judge import DeepSeekGrader, estimate_audit_tokens, flatten_grade
from evals.report import (
    compare_audit_reports,
    list_reports,
    load_json_report,
    utc_timestamp,
    write_json_report,
    write_markdown_report,
)
from evals.run_eval import run_local_eval

DEFAULT_TOKEN_CAP = 500_000

logger = None


def _logger():
    global logger
    if logger is None:
        from log_config import get_logger

        logger = get_logger(__name__)
    return logger


def _load_baseline_idea(idea_id: str) -> dict | None:
    path = BASELINES_DIR / f"{idea_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _load_latest_local_results() -> dict[str, dict]:
    reports = list_reports(RESULTS_LOCAL_DIR)
    if not reports:
        return {}
    payload = load_json_report(reports[-1])
    return {row["idea_id"]: row for row in payload.get("ideas", [])}


def _available_baseline_ids() -> list[str]:
    if not BASELINES_DIR.exists():
        return []
    return sorted(path.stem for path in BASELINES_DIR.glob("*.json"))


def _resolve_idea_results(
    ideas,
    *,
    reuse_last_local: bool,
    refresh_local: bool,
    baseline_only: bool,
    runtime: str,
) -> list[dict]:
    if refresh_local:
        payload = run_local_eval(full=True, include_appeals=True, runtime=runtime)
        return payload["ideas"]

    if reuse_last_local:
        cached = _load_latest_local_results()
        rows: list[dict] = []
        missing: list[str] = []
        for idea in ideas:
            row = cached.get(idea.id) or _load_baseline_idea(idea.id)
            if row:
                rows.append(row)
            else:
                missing.append(idea.id)
        if missing:
            raise FileNotFoundError(
                "Missing cached results for ideas: "
                f"{missing}. Run with --refresh-local or commit baselines."
            )
        return rows

    rows = []
    for idea in ideas:
        baseline = _load_baseline_idea(idea.id)
        if baseline is None:
            if baseline_only:
                continue
            raise FileNotFoundError(
                f"No baseline for {idea.id} at {BASELINES_DIR / (idea.id + '.json')}"
            )
        rows.append(baseline)
    if baseline_only and not rows:
        raise FileNotFoundError(f"No baseline fixtures found in {BASELINES_DIR}")
    return rows


def _estimate_audit_tokens(idea_rows: list[dict], golden_by_id: dict) -> int:
    return estimate_audit_tokens(idea_rows, golden_by_id)


def run_audit(
    *,
    grader: str = "deepseek",
    runtime: str = "local",
    reuse_last_local: bool = True,
    refresh_local: bool = False,
    baseline_only: bool = False,
    limit: int | None = None,
    idea_ids: list[str] | None = None,
    dry_run: bool = False,
    max_input_tokens: int = DEFAULT_TOKEN_CAP,
) -> dict:
    if grader != "deepseek":
        raise ValueError(f"Unsupported grader: {grader}")
    if runtime not in EVAL_RUNTIMES:
        raise ValueError(f"Unsupported runtime: {runtime}. Choose from {EVAL_RUNTIMES}.")

    ideas = load_golden_ideas()
    ideas = filter_ideas(ideas, idea_ids=idea_ids, limit=limit)

    if baseline_only and not refresh_local and not reuse_last_local:
        available = set(_available_baseline_ids())
        ideas = [idea for idea in ideas if idea.id in available]

    idea_rows = _resolve_idea_results(
        ideas,
        reuse_last_local=reuse_last_local,
        refresh_local=refresh_local,
        baseline_only=baseline_only and not refresh_local and not reuse_last_local,
        runtime=runtime,
    )

    golden_by_id = {idea.id: idea for idea in load_golden_ideas()}
    estimated_tokens = _estimate_audit_tokens(idea_rows, golden_by_id)
    if estimated_tokens > max_input_tokens:
        raise RuntimeError(
            f"Estimated input tokens {estimated_tokens} exceeds cap {max_input_tokens}"
        )

    if dry_run:
        _logger().info(
            "Audit dry run: %d ideas, ~%d input tokens",
            len(idea_rows),
            estimated_tokens,
        )
        return {
            "tier": "audit",
            "grader": grader,
            "dry_run": True,
            "ideas_evaluated": len(idea_rows),
            "estimated_input_tokens": estimated_tokens,
            "estimated_api_calls": len(idea_rows),
        }

    deepseek = DeepSeekGrader()
    audited_rows: list[dict] = []
    for index, row in enumerate(idea_rows, start=1):
        _logger().info("Auditing idea %d/%d: %s", index, len(idea_rows), row["idea_id"])
        golden = golden_by_id.get(row["idea_id"])
        grade = deepseek.grade_idea_result(row, golden)
        flattened = flatten_grade(grade)
        audited_rows.append(
            {
                "idea_id": row["idea_id"],
                "idea_text": row["idea_text"],
                "grader": flattened,
                "grader_raw": grade.model_dump(mode="json"),
            }
        )

    previous_reports = list_reports(RESULTS_AUDITS_DIR)
    previous = load_json_report(previous_reports[-1]) if previous_reports else None

    payload = {
        "tier": "audit",
        "grader": grader,
        "timestamp": utc_timestamp(),
        "ideas_evaluated": len(audited_rows),
        "estimated_input_tokens": deepseek.estimated_input_tokens,
        "api_calls": deepseek.calls_made,
        "ideas": audited_rows,
        "aggregate": {
            "mean_composite_dimension_avg": round(
                sum(item["grader"]["composite_dimension_avg"] for item in audited_rows)
                / len(audited_rows),
                3,
            )
            if audited_rows
            else 0.0,
        },
    }
    payload["regressions"] = compare_audit_reports(payload, previous)

    stamp = payload["timestamp"]
    json_path = RESULTS_AUDITS_DIR / f"{stamp}.json"
    md_path = RESULTS_AUDITS_DIR / f"{stamp}.md"
    write_json_report(json_path, payload)
    write_markdown_report(md_path, payload)
    payload["report_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Tier 2 DeepSeek quality audit")
    parser.add_argument("--grader", default="deepseek", choices=["deepseek"])
    parser.add_argument("--reuse-last-local", action="store_true", default=True)
    parser.add_argument("--no-reuse-last-local", action="store_true")
    parser.add_argument(
        "--refresh-local",
        action="store_true",
        help="Re-run Tier 1 pipeline before grading (use --runtime to pick local vs deepseek)",
    )
    parser.add_argument(
        "--runtime",
        default="local",
        choices=list(EVAL_RUNTIMES),
        help="Pipeline runtime when using --refresh-local",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--ideas", default=None)
    parser.add_argument("--baseline-only", action="store_true", default=False)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-input-tokens", type=int, default=DEFAULT_TOKEN_CAP)
    parser.add_argument(
        "--log-level",
        default=None,
        help="Logging level (DEBUG, INFO, WARNING). Default: LOG_LEVEL env or INFO",
    )
    args = parser.parse_args()

    from log_config import configure_logging

    configure_logging(level=args.log_level)

    reuse_last_local = not args.no_reuse_last_local
    if args.refresh_local:
        reuse_last_local = False

    idea_ids = [item.strip() for item in args.ideas.split(",")] if args.ideas else None
    payload = run_audit(
        grader=args.grader,
        runtime=args.runtime,
        reuse_last_local=reuse_last_local,
        refresh_local=args.refresh_local,
        baseline_only=args.baseline_only,
        limit=args.limit,
        idea_ids=idea_ids,
        dry_run=args.dry_run,
        max_input_tokens=args.max_input_tokens,
    )

    if payload.get("dry_run"):
        print(
            f"Dry run: {payload['ideas_evaluated']} ideas, "
            f"~{payload['estimated_input_tokens']} input tokens, "
            f"{payload.get('estimated_api_calls', payload['ideas_evaluated'])} API call(s)"
        )
        return

    print(f"Audit complete: {payload['report_paths']['json']}")
    print(f"Mean composite: {payload['aggregate']['mean_composite_dimension_avg']}")
    if payload.get("regressions"):
        print("Regressions detected:")
        for item in payload["regressions"]:
            print(f"- {item}")


if __name__ == "__main__":
    main()
