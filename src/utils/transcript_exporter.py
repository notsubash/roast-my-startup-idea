from pathlib import Path
from datetime import datetime

from judges.schemas import RoastPanel


def export_transcript(
    startup_idea: str,
    roast_panel: RoastPanel,
    debate_result: dict,
    output_dir: Path = Path("transcripts"),
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
        "---",
        "",
        "## Phase 1: Individual Roasts",
        "",
    ]

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

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath
