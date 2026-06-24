"""Run one golden idea through the production pipeline for eval."""

from __future__ import annotations

from pathlib import Path
import sys
import time
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from appeal.service import run_appeal
from evals.dataset.loader import GoldenIdea
from events import (
    DebateMessagePublished,
    DebateRoundStarted,
    DebateSynthesisPublished,
    JudgesDispatched,
    JudgeVerdictCompleted,
    PhaseStarted,
    PipelineCompleted,
)
from judges.schemas import RoastPanel
from log_config import get_logger
from pipeline import stream_pipeline

logger = get_logger(__name__)


def _panel_to_dict(panel: RoastPanel) -> dict[str, Any]:
    return panel.model_dump(mode="json")


def run_idea_eval(
    model,
    idea: GoldenIdea,
    *,
    max_debate_rounds: int,
    include_appeals: bool = True,
) -> dict[str, Any]:
    judge_attempts: list[dict[str, Any]] = []
    roast_panel_dict: dict[str, Any] | None = None
    debate_result: dict[str, Any] | None = None

    start = time.perf_counter()
    phase_started_at = start
    roast_seconds = 0.0
    debate_seconds = 0.0
    in_debate = False

    roast_panel_obj: RoastPanel | None = None
    judges_total = 0

    logger.info(
        "Starting idea %s (%d chars, debate_rounds=%d, appeals=%s)",
        idea.id,
        len(idea.idea_text),
        max_debate_rounds,
        include_appeals,
    )

    for event in stream_pipeline(model, idea.idea_text, max_debate_rounds=max_debate_rounds):
        if isinstance(event, JudgesDispatched):
            judges_total = event.total
            logger.info("[%s] roast phase: dispatching %d judges", idea.id, event.total)
        elif isinstance(event, JudgeVerdictCompleted):
            judge_attempts.append({"judge": event.judge, "success": True})
            logger.info(
                "[%s] roast: judge %s done (%d/%d)",
                idea.id,
                event.judge,
                event.completed,
                event.total,
            )
        elif isinstance(event, PhaseStarted) and event.phase == "debate":
            roast_seconds = time.perf_counter() - phase_started_at
            in_debate = True
            phase_started_at = time.perf_counter()
            logger.info("[%s] roast complete in %.1fs — starting debate", idea.id, roast_seconds)
        elif isinstance(event, DebateRoundStarted):
            logger.info("[%s] debate round %d started", idea.id, event.round)
        elif isinstance(event, DebateMessagePublished):
            logger.debug(
                "[%s] debate r%d %s spoke (%d chars)",
                idea.id,
                event.round,
                event.speaker,
                len(event.content),
            )
        elif isinstance(event, DebateSynthesisPublished):
            logger.info("[%s] debate synthesis complete (%d chars)", idea.id, len(event.content))
        elif isinstance(event, PipelineCompleted):
            roast_panel_obj = event.roast_panel
            roast_panel_dict = _panel_to_dict(event.roast_panel)
            debate_result = event.debate_result
            if in_debate:
                debate_seconds = time.perf_counter() - phase_started_at
            else:
                roast_seconds = time.perf_counter() - start
            logger.info(
                "[%s] pipeline complete — roast %.1fs, debate %.1fs",
                idea.id,
                roast_seconds,
                debate_seconds,
            )

    total_seconds = time.perf_counter() - start

    result: dict[str, Any] = {
        "idea_id": idea.id,
        "idea_text": idea.idea_text,
        "tags": idea.tags,
        "judge_attempts": judge_attempts,
        "roast_panel": roast_panel_dict,
        "debate_result": debate_result,
        "timings": {
            "roast_seconds": round(roast_seconds, 2),
            "debate_seconds": round(debate_seconds, 2),
            "total_seconds": round(total_seconds, 2),
        },
    }

    if include_appeals and idea.appeal_cases and roast_panel_obj and debate_result:
        logger.info("[%s] starting appeals (weak + strong)", idea.id)
        for case_name, appeal_text in (
            ("weak", idea.appeal_cases.weak),
            ("strong", idea.appeal_cases.strong),
        ):
            appeal_start = time.perf_counter()
            logger.info("[%s] appeal_%s started", idea.id, case_name)
            try:
                appeal_result = run_appeal(
                    model=model,
                    startup_idea=idea.idea_text,
                    roast_panel=roast_panel_obj,
                    debate_result=debate_result,
                    appeal_text=appeal_text,
                )
            except ValueError as exc:
                appeal_seconds = time.perf_counter() - appeal_start
                logger.error(
                    "[%s] appeal_%s failed after %.1fs: %s", idea.id, case_name, appeal_seconds, exc
                )
                result[f"appeal_{case_name}"] = {
                    "appeal_text": appeal_text,
                    "error": str(exc),
                    "success": False,
                    "seconds": round(appeal_seconds, 2),
                }
                continue

            appeal_seconds = time.perf_counter() - appeal_start
            result[f"appeal_{case_name}"] = {
                "appeal_text": appeal_text,
                "revised_panel": _panel_to_dict(appeal_result.revised_panel),
                "revised_synthesis": appeal_result.revised_synthesis,
                "success": True,
                "seconds": round(appeal_seconds, 2),
            }
            logger.info("[%s] appeal_%s complete in %.1fs", idea.id, case_name, appeal_seconds)

    logger.info(
        "[%s] finished in %.1fs (judges=%d, appeals=%s)",
        idea.id,
        total_seconds,
        judges_total or len(judge_attempts),
        include_appeals,
    )
    return result
