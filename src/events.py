"""Frontend-agnostic pipeline events.

Any UI (Streamlit, React, CLI) should consume these events rather than
calling LangChain / LangGraph APIs directly.
"""

from dataclasses import dataclass
from typing import Literal

from judges.schemas import RoastPanel, Verdict


@dataclass(frozen=True)
class PhaseStarted:
    phase: Literal["roast", "debate"]


@dataclass(frozen=True)
class JudgesDispatched:
    total: int


@dataclass(frozen=True)
class JudgeVerdictCompleted:
    judge: str
    verdict: Verdict
    completed: int
    total: int


@dataclass(frozen=True)
class RoastPanelCompleted:
    panel: RoastPanel


@dataclass(frozen=True)
class DebateRoundStarted:
    round: int


@dataclass(frozen=True)
class DebateSpeakerThinking:
    judge: str
    round: int


@dataclass(frozen=True)
class DebateTokenDelta:
    speaker: str
    round: int
    delta: str


@dataclass(frozen=True)
class DebateMessagePublished:
    speaker: str
    round: int
    content: str


@dataclass(frozen=True)
class DebateSynthesisPublished:
    content: str


@dataclass(frozen=True)
class DebateCompleted:
    debate_messages: list[dict]
    final_synthesis: str | None


@dataclass(frozen=True)
class PipelineCompleted:
    roast_panel: RoastPanel
    debate_result: dict


PipelineEvent = (
    PhaseStarted
    | JudgesDispatched
    | JudgeVerdictCompleted
    | RoastPanelCompleted
    | DebateRoundStarted
    | DebateSpeakerThinking
    | DebateTokenDelta
    | DebateMessagePublished
    | DebateSynthesisPublished
    | DebateCompleted
    | PipelineCompleted
)
