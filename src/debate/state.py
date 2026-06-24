import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class DebateMessage(TypedDict):
    speaker: str
    round: int
    content: str


class DebateState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    startup_idea: str
    verdicts: list[dict]
    debate_messages: Annotated[list[DebateMessage], operator.add]
    round: int
    max_rounds: int
    current_speaker_idx: int
    final_synthesis: str | None
