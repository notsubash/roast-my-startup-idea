from idea_context import unwrap_user_idea
from judges.synthesis import synthesis_compact_summary
from memory.models import IdeaRecord


def _truncate(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def build_memory_context(records: list[IdeaRecord], *, max_chars: int = 1800) -> str:
    """Build compact prior-idea context for judge prompts.

    Full debate transcripts intentionally stay out of prompts; local models need
    concise signals like prior ideas, score trends, and recurring concerns.
    """
    if not records:
        return ""

    lines = [
        "The user has submitted prior startup ideas. Use this only to judge progress, repeated risks, and whether this pitch addresses earlier criticism.",
    ]

    for idx, record in enumerate(records, start=1):
        scores = [verdict.score for verdict in record.roast_panel.verdicts]
        average = sum(scores) / len(scores)
        concerns = "; ".join(
            f"{verdict.judge.value}: {verdict.key_concern}"
            for verdict in record.roast_panel.verdicts[:3]
        )
        synthesis = synthesis_compact_summary(record.debate_result)

        lines.extend(
            [
                f"{idx}. {record.created_at.date()} | avg {average:.1f}/10 | {_truncate(unwrap_user_idea(record.idea_text), 220)}",
                f"   Key concerns: {_truncate(concerns, 420)}",
                f"   Prior synthesis: {_truncate(synthesis, 300)}",
            ]
        )

        if record.appeal_text:
            lines.append(f"   Prior appeal: {_truncate(record.appeal_text, 220)}")
        if record.revised_synthesis:
            lines.append(f"   Revised synthesis: {_truncate(record.revised_synthesis, 260)}")

    context = "\n".join(lines)
    return _truncate(context, max_chars)
