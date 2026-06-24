"""Load golden eval dataset."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from evals import GOLDEN_IDEAS_PATH


@dataclass(frozen=True)
class AppealCases:
    weak: str
    strong: str


@dataclass(frozen=True)
class GoldenIdea:
    id: str
    idea_text: str
    tags: list[str]
    expected_panel_avg_range: tuple[int, int]
    must_surface_concerns: list[str]
    appeal_cases: AppealCases | None
    expected_delta_direction: dict[str, str]


def load_golden_ideas(path: Path | None = None) -> list[GoldenIdea]:
    source = path or GOLDEN_IDEAS_PATH
    ideas: list[GoldenIdea] = []
    with source.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            appeal_raw = record.get("appeal_cases")
            appeal_cases = None
            if appeal_raw:
                appeal_cases = AppealCases(
                    weak=appeal_raw["weak"],
                    strong=appeal_raw["strong"],
                )
            low, high = record["expected_panel_avg_range"]
            ideas.append(
                GoldenIdea(
                    id=record["id"],
                    idea_text=record["idea_text"],
                    tags=record.get("tags", []),
                    expected_panel_avg_range=(int(low), int(high)),
                    must_surface_concerns=record.get("must_surface_concerns", []),
                    appeal_cases=appeal_cases,
                    expected_delta_direction=record.get("expected_delta_direction", {}),
                )
            )
    return ideas


def filter_ideas(
    ideas: list[GoldenIdea],
    *,
    idea_ids: list[str] | None = None,
    limit: int | None = None,
) -> list[GoldenIdea]:
    filtered = ideas
    if idea_ids:
        wanted = set(idea_ids)
        filtered = [idea for idea in filtered if idea.id in wanted]
        missing = wanted - {idea.id for idea in filtered}
        if missing:
            raise ValueError(f"Unknown golden idea ids: {sorted(missing)}")
    if limit is not None:
        filtered = filtered[:limit]
    return filtered
