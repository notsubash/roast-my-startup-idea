"""Streamlit-specific adapters — maps pipeline events to widgets."""

import streamlit as st

from debate.service import stream_debate
from events import (
    DebateCompleted,
    DebateMessagePublished,
    DebateRoundStarted,
    DebateSpeakerThinking,
    DebateSynthesisPublished,
    JudgeVerdictCompleted,
    JudgesDispatched,
    RoastPanelCompleted,
)
from judges.panel import stream_roast_panel
from judges.schemas import RoastPanel

VERDICT_ICONS = {"PASS": "\U0001f7e2", "FAIL": "\U0001f534", "CONDITIONAL": "\U0001f7e1"}

JUDGE_AVATARS = {
    "vc": "\U0001f4b0",
    "engineer": "\U0001f527",
    "pm": "\U0001f4cb",
    "customer": "\U0001f464",
    "competitor": "\U0001f3af",
}


def run_roast_panel_in_status(
    model,
    startup_idea: str,
    status,
    memory_context: str | None = None,
) -> RoastPanel:
    """Consume roast events and render progress inside a st.status block."""
    panel: RoastPanel | None = None
    progress_bar = None

    for event in stream_roast_panel(model, startup_idea, memory_context):
        if isinstance(event, JudgesDispatched):
            status.write(f"Dispatching {event.total} judges in parallel...")
            progress_bar = status.progress(0, text=f"0/{event.total} judges responded")

        elif isinstance(event, JudgeVerdictCompleted):
            icon = VERDICT_ICONS.get(event.verdict.verdict.value, "\u26aa")
            status.write(
                f"{icon} **{event.judge.upper()}** — "
                f"{event.verdict.score}/10 ({event.verdict.verdict.value})"
            )
            if progress_bar:
                progress_bar.progress(
                    event.completed / event.total,
                    text=f"{event.completed}/{event.total} judges responded",
                )

        elif isinstance(event, RoastPanelCompleted):
            panel = event.panel

    if panel is None:
        raise RuntimeError("Roast panel did not complete")
    return panel


def run_debate_in_container(
    model,
    startup_idea: str,
    roast_panel: RoastPanel,
    max_rounds: int,
    container,
) -> dict:
    """Consume debate events and render messages inside a Streamlit container."""
    thinking_placeholder = container.empty()
    result: dict = {}

    for event in stream_debate(model, startup_idea, roast_panel, max_rounds):
        if isinstance(event, DebateRoundStarted):
            thinking_placeholder.empty()
            container.markdown(f"#### Round {event.round}")

        elif isinstance(event, DebateMessagePublished):
            thinking_placeholder.empty()
            avatar = JUDGE_AVATARS.get(event.speaker, "\U0001f916")
            with container.chat_message(event.speaker, avatar=avatar):
                st.markdown(f"**{event.speaker.upper()}**")
                st.write(event.content)

        elif isinstance(event, DebateSpeakerThinking):
            thinking_placeholder.caption(f"⏳ {event.judge.upper()} is thinking...")

        elif isinstance(event, DebateSynthesisPublished):
            thinking_placeholder.empty()

        elif isinstance(event, DebateCompleted):
            thinking_placeholder.empty()
            result = {
                "debate_messages": event.debate_messages,
                "final_synthesis": event.final_synthesis,
            }

    return result
