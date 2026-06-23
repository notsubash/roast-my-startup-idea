"""Write committed baseline fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evals import BASELINES_DIR, BASELINE_SOURCES
from evals.dataset.baseline_builder import BASELINE_BUILDERS


def _write_synthetic_baselines() -> None:
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    for idea_id, builder in BASELINE_BUILDERS.items():
        payload = builder()
        payload.pop("_meta", None)
        path = BASELINES_DIR / f"{idea_id}.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote {path}")


def _write_llm_baselines(
    *,
    runtime: str,
    idea_ids: list[str] | None,
    include_appeals: bool,
    max_debate_rounds: int | None,
) -> None:
    from evals.run_eval import run_local_eval

    run_local_eval(
        runtime=runtime,
        full=idea_ids is None,
        idea_ids=idea_ids,
        include_appeals=include_appeals,
        write_baselines=True,
        max_debate_rounds=max_debate_rounds,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write evals/dataset/baselines/latest/ fixtures"
    )
    parser.add_argument(
        "--runtime",
        default="synthetic",
        choices=list(BASELINE_SOURCES),
        help="synthetic = fast CI fixtures; local/deepseek = live pipeline outputs",
    )
    parser.add_argument(
        "--ideas",
        default=None,
        help="Comma-separated idea ids (default: all baseline builders / full golden set)",
    )
    parser.add_argument("--no-appeals", action="store_true")
    parser.add_argument(
        "--debate-rounds",
        type=int,
        default=None,
        help="Override MAX_DEBATE_ROUNDS for live pipeline runs",
    )
    args = parser.parse_args()

    if args.runtime == "synthetic":
        if args.ideas or args.no_appeals or args.debate_rounds is not None:
            parser.error("--ideas, --no-appeals, and --debate-rounds apply only to live runtimes")
        _write_synthetic_baselines()
        return

    idea_ids = [item.strip() for item in args.ideas.split(",")] if args.ideas else None
    if idea_ids is None:
        idea_ids = list(BASELINE_BUILDERS.keys())
    _write_llm_baselines(
        runtime=args.runtime,
        idea_ids=idea_ids,
        include_appeals=not args.no_appeals,
        max_debate_rounds=args.debate_rounds,
    )


if __name__ == "__main__":
    main()
