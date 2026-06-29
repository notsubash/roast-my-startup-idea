from config import JUDGE_ORDER


def make_route_next_speaker(*, enable_revote: bool = True):
    """Route after the last speaker in a round — optionally skip re-vote."""

    def route_next_speaker(state: dict) -> str:
        if state["current_speaker_idx"] < len(JUDGE_ORDER):
            return JUDGE_ORDER[state["current_speaker_idx"]]

        if state["round"] < state["max_rounds"]:
            return "advance_round"

        return "revote" if enable_revote else "moderator"

    return route_next_speaker


def route_next_speaker(state: dict) -> str:
    """Default router with re-vote enabled (tests and legacy callers)."""
    return make_route_next_speaker(enable_revote=True)(state)


def advance_round(state: dict) -> dict:
    return {
        "round": state["round"] + 1,
        "current_speaker_idx": 0,
    }
