import operator
from typing import Annotated, TypedDict

class DebateMessage(TypedDict):
    speaker: str
    round: int
    content: str

class DebateState(TypedDict):
    startup_idea: str
    verdicts: list[dict]
    messages: Annotated[list[DebateMessage], operator.add]
    round: int
    max_rounds: int
    current_speaker_idx: int
    final_synthesis: str | None