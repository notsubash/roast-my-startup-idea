from config import JUDGE_ORDER


def route_next_speaker(state: dict) -> str:
    if state["current_speaker_idx"] < len(JUDGE_ORDER):
        return JUDGE_ORDER[state["current_speaker_idx"]]

    if state["round"] < state["max_rounds"]:
        return "advance_round"

    return "revote"


def advance_round(state: dict) -> dict:
    return {
        "round": state["round"] + 1,
        "current_speaker_idx": 0,
    }
