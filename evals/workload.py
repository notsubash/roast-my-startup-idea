"""Estimate LLM call volume for eval runs."""

from __future__ import annotations

JUDGE_COUNT = 5


def estimate_llm_calls(
    *,
    num_ideas: int,
    max_debate_rounds: int,
    include_appeals: bool,
) -> dict[str, int | float]:
    """Return per-idea and total LLM call counts for a local eval run."""
    roast_calls = JUDGE_COUNT
    debate_calls = max_debate_rounds * JUDGE_COUNT + 1  # speakers + moderator

    appeal_cases = 2 if include_appeals else 0
    appeal_judge_calls = appeal_cases * JUDGE_COUNT
    appeal_synthesis_calls = appeal_cases
    appeal_calls = appeal_judge_calls + appeal_synthesis_calls

    per_idea = roast_calls + debate_calls + appeal_calls
    # Roast and appeal judges run in parallel; debate speakers and synthesis are sequential.
    per_idea_sequential = debate_calls + appeal_synthesis_calls

    return {
        "roast_calls_per_idea": roast_calls,
        "debate_calls_per_idea": debate_calls,
        "appeal_calls_per_idea": appeal_calls,
        "llm_calls_per_idea": per_idea,
        "sequential_steps_per_idea": per_idea_sequential,
        "llm_calls_total": per_idea * num_ideas,
        "sequential_steps_total": per_idea_sequential * num_ideas,
    }
