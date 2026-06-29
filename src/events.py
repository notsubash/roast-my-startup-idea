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
    structured_synthesis: dict | None = None
    initial_verdicts: list[dict] | None = None
    revised_verdicts: list[dict] | None = None


@dataclass(frozen=True)
class PipelineCompleted:
    roast_panel: RoastPanel
    debate_result: dict


@dataclass(frozen=True)
class RunMetrics:
    roast_seconds: float
    debate_seconds: float
    total_seconds: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    model_runtime: str
    judge_calls: list[dict]
    debate_calls: list[dict]

    def as_dict(self) -> dict:
        return {
            "roast_seconds": self.roast_seconds,
            "debate_seconds": self.debate_seconds,
            "total_seconds": self.total_seconds,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "model_runtime": self.model_runtime,
            "judge_calls": self.judge_calls,
            "debate_calls": self.debate_calls,
        }


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
    | RunMetrics
    | PipelineCompleted
)
