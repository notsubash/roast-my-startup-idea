"""Tier 1 local golden-set evaluation CLI."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import get_settings
from evals import BASELINES_DIR, EVAL_RUNTIMES, RESULTS_LOCAL_DIR
from evals.dataset.loader import filter_ideas, load_golden_ideas
from evals.report import utc_timestamp, write_json_report, write_markdown_report
from evals.runner import run_idea_eval
from evals.scorers.composite import score_idea_result
from evals.workload import estimate_llm_calls
from log_config import configure_logging, get_logger
from modeling import build_chat_model

logger = get_logger(__name__)


def _aggregate_metrics(idea_rows: list[dict]) -> dict:
    if not idea_rows:
        return {}
    reliability_rates = [
        row["metrics"]["reliability"]["judge_parse_success_rate"] for row in idea_rows
    ]
    passed = sum(1 for row in idea_rows if row["metrics"]["passed"])
    appeal_scored = [
        row["metrics"]["appeal"]["appeal_discrimination_passed"]
        for row in idea_rows
        if row["metrics"].get("appeal", {}).get("appeal_weak", {}).get("appeal_present")
    ]
    lens_scored = [
        row["metrics"]["lens"]["lens_differentiation_passed"]
        for row in idea_rows
        if not row["metrics"].get("lens", {}).get("lens_legacy", True)
    ]
    return {
        "mean_judge_parse_success_rate": round(sum(reliability_rates) / len(reliability_rates), 3),
        "ideas_passed": passed,
        "ideas_total": len(idea_rows),
        "pass_rate": round(passed / len(idea_rows), 3),
        "appeal_discrimination_pass_rate": (
            round(sum(appeal_scored) / len(appeal_scored), 3) if appeal_scored else None
        ),
        "lens_differentiation_pass_rate": (
            round(sum(lens_scored) / len(lens_scored), 3) if lens_scored else None
        ),
    }


def run_local_eval(
    *,
    runtime: str = "local",
    full: bool = False,
    limit: int | None = None,
    idea_ids: list[str] | None = None,
    include_appeals: bool = True,
    write_baselines: bool = False,
    max_debate_rounds: int | None = None,
) -> dict:
    settings = get_settings()
    debate_rounds = (
        max_debate_rounds if max_debate_rounds is not None else settings.max_debate_rounds
    )
    if runtime not in EVAL_RUNTIMES:
        raise ValueError(f"Unsupported runtime: {runtime}. Choose from {EVAL_RUNTIMES}.")

    model = build_chat_model(runtime, settings, os.getenv("DEEPSEEK_API_KEY"))
    model_name = settings.local_model if runtime == "local" else settings.deepseek_model

    ideas = load_golden_ideas()
    if full:
        ideas = filter_ideas(ideas, idea_ids=idea_ids)
    else:
        effective_limit = limit if limit is not None else 3
        ideas = filter_ideas(ideas, idea_ids=idea_ids, limit=effective_limit)

    workload = estimate_llm_calls(
        num_ideas=len(ideas),
        max_debate_rounds=debate_rounds,
        include_appeals=include_appeals,
    )
    logger.info(
        "Eval starting: runtime=%s model=%s ideas=%d debate_rounds=%d appeals=%s",
        runtime,
        model_name,
        len(ideas),
        debate_rounds,
        include_appeals,
    )
    logger.info(
        "Estimated workload: %d LLM calls total (~%d sequential steps/idea). "
        "Local Ollama runs debate speakers one-at-a-time — expect several minutes per step.",
        workload["llm_calls_total"],
        workload["sequential_steps_per_idea"],
    )
    logger.info("Ideas: %s", ", ".join(idea.id for idea in ideas))

    eval_start = time.perf_counter()
    idea_rows: list[dict] = []
    for index, idea in enumerate(ideas, start=1):
        logger.info("=== Idea %d/%d: %s ===", index, len(ideas), idea.id)
        result = run_idea_eval(
            model,
            idea,
            max_debate_rounds=debate_rounds,
            include_appeals=include_appeals,
            model_runtime=runtime,  # type: ignore[arg-type]
        )
        metrics = score_idea_result(
            result,
            max_debate_rounds=debate_rounds,
            expected_delta_direction=idea.expected_delta_direction,
        )
        idea_rows.append({**result, "metrics": metrics})
        logger.info(
            "Idea %s scored: passed=%s (%.1fs elapsed total so far)",
            idea.id,
            metrics["passed"],
            time.perf_counter() - eval_start,
        )

    payload = {
        "tier": "golden",
        "runtime": runtime,
        "model": model_name,
        "timestamp": utc_timestamp(),
        "ideas_evaluated": len(idea_rows),
        "ideas": idea_rows,
        "aggregate": _aggregate_metrics(idea_rows),
    }

    stamp = payload["timestamp"]
    json_path = RESULTS_LOCAL_DIR / f"{stamp}.json"
    md_path = RESULTS_LOCAL_DIR / f"{stamp}.md"
    write_json_report(json_path, payload)
    write_markdown_report(md_path, payload)

    if write_baselines:
        BASELINES_DIR.mkdir(parents=True, exist_ok=True)
        for row in idea_rows:
            baseline_path = BASELINES_DIR / f"{row['idea_id']}.json"
            baseline_payload = {key: value for key, value in row.items() if key != "metrics"}
            baseline_payload["baseline_runtime"] = runtime
            baseline_payload["baseline_model"] = model_name
            write_json_report(baseline_path, baseline_payload)
            logger.info("Wrote baseline %s (%s)", baseline_path, runtime)

    elapsed = time.perf_counter() - eval_start
    logger.info(
        "Eval complete in %.1fs: %d/%d passed",
        elapsed,
        payload["aggregate"].get("ideas_passed", 0),
        payload["aggregate"].get("ideas_total", 0),
    )

    payload["report_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tier 1 golden-set evaluation (local Ollama or DeepSeek pipeline runtime)"
    )
    parser.add_argument(
        "--runtime",
        default="local",
        choices=list(EVAL_RUNTIMES),
        help="Pipeline LLM runtime: local Ollama or DeepSeek API",
    )
    parser.add_argument("--full", action="store_true", help="Evaluate all golden ideas")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of ideas")
    parser.add_argument("--ideas", default=None, help="Comma-separated idea ids")
    parser.add_argument("--no-appeals", action="store_true")
    parser.add_argument(
        "--debate-rounds",
        type=int,
        default=None,
        help="Override MAX_DEBATE_ROUNDS (default from .env, usually 3)",
    )
    parser.add_argument(
        "--write-baselines",
        action="store_true",
        help="Also write evals/dataset/baselines/latest/<idea_id>.json",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        help="Logging level (DEBUG, INFO, WARNING). Default: LOG_LEVEL env or INFO",
    )
    args = parser.parse_args()

    configure_logging(level=args.log_level)

    idea_ids = [item.strip() for item in args.ideas.split(",")] if args.ideas else None
    payload = run_local_eval(
        runtime=args.runtime,
        full=args.full,
        limit=args.limit,
        idea_ids=idea_ids,
        include_appeals=not args.no_appeals,
        write_baselines=args.write_baselines,
        max_debate_rounds=args.debate_rounds,
    )
    aggregate = payload["aggregate"]
    print(f"Eval complete: {payload['report_paths']['json']}")
    print(
        "Pass rate "
        f"{aggregate.get('pass_rate')} "
        f"({aggregate.get('ideas_passed')}/{aggregate.get('ideas_total')})"
    )


if __name__ == "__main__":
    main()
