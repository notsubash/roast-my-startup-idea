from datetime import datetime
from pathlib import Path
from typing import Any

from judges.schemas import RoastPanel
from observability.metrics import format_run_metrics_markdown


def export_transcript(
    startup_idea: str,
    roast_panel: RoastPanel,
    debate_result: dict,
    output_dir: Path = Path("transcripts"),
    appeal_text: str | None = None,
    revised_panel: RoastPanel | None = None,
    revised_synthesis: str | None = None,
    run_metrics: dict[str, Any] | None = None,
) -> Path:
    """Export the full roast + debate session to a Markdown file."""
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = "".join(c if c.isalnum() or c == " " else "" for c in startup_idea[:40])
    slug = slug.strip().replace(" ", "_").lower()
    filepath = output_dir / f"{timestamp}_{slug}.md"

    lines = [
        "# Roast My Startup — Transcript",
        "",
        f"**Idea:** {startup_idea}",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]
    lines.extend(format_run_metrics_markdown(run_metrics))
    lines.extend(
        [
            "---",
            "",
            "## Phase 1: Individual Roasts",
            "",
        ]
    )

    for v in roast_panel.verdicts:
        lines.append(f"### {v.judge.value.upper()} — {v.verdict.value} ({v.score}/10)")
        lines.append("")
        lines.append(f"> {v.roast}")
        lines.append("")
        lines.append(f"**Key concern:** {v.key_concern}")
        lines.append("")

    lines.extend(["---", "", "## Phase 2: Debate", ""])

    current_round = 0
    for msg in debate_result.get("debate_messages", []):
        if msg["speaker"] == "moderator":
            continue
        if msg["round"] != current_round:
            current_round = msg["round"]
            lines.extend([f"### Round {current_round}", ""])
        lines.append(f"**{msg['speaker'].upper()}:** {msg['content']}")
        lines.append("")

    synthesis = debate_result.get("final_synthesis", "")
    if synthesis:
        lines.extend(["---", "", "## Final Synthesis", "", synthesis, ""])

    if appeal_text and revised_panel is not None:
        lines.extend(
            ["---", "", "## Phase 3: Appeal", "", "### Founder Appeal", "", appeal_text, ""]
        )
        lines.extend(["### Revised Verdicts", ""])
        for v in revised_panel.verdicts:
            original = next(
                orig for orig in roast_panel.verdicts if orig.judge.value == v.judge.value
            )
            delta = v.score - original.score
            delta_label = f", {delta:+d}" if delta else ""
            lines.append(
                f"#### {v.judge.value.upper()} — {v.verdict.value} "
                f"({v.score}/10, was {original.score}/10{delta_label})"
            )
            lines.append("")
            lines.append(f"> {v.roast}")
            lines.append("")
            lines.append(f"**Key concern:** {v.key_concern}")
            lines.append("")

        if revised_synthesis:
            lines.extend(["### Appeal Synthesis", "", revised_synthesis, ""])

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath
