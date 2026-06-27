"""Streamlit-specific adapters — maps pipeline events to widgets."""

import streamlit as st

from debate.service import stream_debate
from events import (
    DebateCompleted,
    DebateMessagePublished,
    DebateRoundStarted,
    DebateSpeakerThinking,
    DebateSynthesisPublished,
    DebateTokenDelta,
    JudgesDispatched,
    JudgeVerdictCompleted,
    RoastPanelCompleted,
)
from judges.panel import run_roast_panel, stream_roast_panel
from judges.schemas import RoastPanel
from orchestrator.deep_agent import run_roast_via_orchestrator
from ui.text_display import plain_text_html, write_plain_text

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
    research_context: str | None = None,
) -> RoastPanel:
    """Consume roast events and render progress inside a st.status block."""
    panel: RoastPanel | None = None
    progress_bar = None

    for event in stream_roast_panel(model, startup_idea, memory_context, research_context):
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


def run_deepagent_roast_in_status(
    model,
    startup_idea: str,
    status,
    memory_context: str | None = None,
    research_context: str | None = None,
    web_search_enabled: bool = False,
) -> RoastPanel:
    """Run experimental DeepAgents phase-1 and render progress."""
    status.write("Booting DeepAgents orchestrator...")
    if research_context:
        status.write("Injecting bounded web research context.")
    status.write("Dispatching subagents via task()...")
    try:
        panel = run_roast_via_orchestrator(
            model=model,
            startup_idea=startup_idea,
            research_context=research_context,
            web_search_enabled=web_search_enabled,
        )
        status.write("Collected DeepAgents verdict payloads.")
        return panel
    except Exception as exc:
        status.write(f"DeepAgents phase 1 failed ({exc}); falling back to deterministic phase 1.")
        panel = run_roast_panel(
            model=model,
            startup_idea=startup_idea,
            memory_context=memory_context,
            research_context=research_context,
        )
        status.write("Fallback completed via deterministic panel.")
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
    streaming: dict | None = None

    for event in stream_debate(model, startup_idea, roast_panel, max_rounds):
        if isinstance(event, DebateRoundStarted):
            thinking_placeholder.empty()
            container.markdown(f"#### Round {event.round}")

        elif isinstance(event, DebateTokenDelta):
            thinking_placeholder.empty()
            key = (event.speaker, event.round)
            if streaming is None or streaming["key"] != key:
                avatar = JUDGE_AVATARS.get(event.speaker, "\U0001f916")
                with container.chat_message(event.speaker, avatar=avatar):
                    st.markdown(f"**{event.speaker.upper()}**")
                    streaming = {"key": key, "text": "", "placeholder": st.empty()}
            streaming["text"] += event.delta
            streaming["placeholder"].markdown(
                plain_text_html(streaming["text"]),
                unsafe_allow_html=True,
            )

        elif isinstance(event, DebateMessagePublished):
            thinking_placeholder.empty()
            key = (event.speaker, event.round)
            if streaming is not None and streaming["key"] == key:
                streaming["placeholder"].markdown(
                    plain_text_html(event.content),
                    unsafe_allow_html=True,
                )
                streaming = None
            else:
                avatar = JUDGE_AVATARS.get(event.speaker, "\U0001f916")
                with container.chat_message(event.speaker, avatar=avatar):
                    st.markdown(f"**{event.speaker.upper()}**")
                    write_plain_text(event.content)

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
