"""Render LLM prose in Streamlit without accidental markdown/HTML formatting."""

import html

import streamlit as st

from judges.schemas import RoastPanel
from judges.synthesis import OverallRecommendation, Synthesis, top_priorities

_PLAIN_STYLE = "margin:0; white-space:pre-wrap;"
_RECOMMENDATION_ICON = {
    OverallRecommendation.GO: "\U0001f7e2",
    OverallRecommendation.ITERATE: "\U0001f7e1",
    OverallRecommendation.NO_GO: "\U0001f534",
}


def plain_text_html(text: str) -> str:
    """Escaped plain-text paragraph HTML for Streamlit markdown placeholders."""
    safe = html.escape(text or "")
    return f'<p class="llm-plain-text" style="{_PLAIN_STYLE}">{safe}</p>'


def write_plain_text(text: str) -> None:
    """Display model output as normal prose (no markdown interpretation)."""
    st.markdown(plain_text_html(text), unsafe_allow_html=True)


def write_roast_quote(text: str) -> None:
    """Display a roast line as an italic quote."""
    safe = html.escape(text or "")
    st.markdown(
        f'<p class="llm-plain-text" style="{_PLAIN_STYLE} font-style:italic;">"{safe}"</p>',
        unsafe_allow_html=True,
    )


def write_appeal_coaching_item(
    *,
    icon: str,
    judge: str,
    verdict_label: str,
    score: int,
    hint: str,
    quality: str | None = None,
) -> None:
    """Single appeal coaching checklist row with escaped model text."""
    quality_note = ""
    if quality == "derived":
        quality_note = ' <span style="opacity:0.75;">(inferred from concern)</span>'
    elif quality == "generic":
        quality_note = ' <span style="opacity:0.75;">(generic ask)</span>'
    elif quality == "duplicate":
        quality_note = ' <span style="opacity:0.75;">(same as another judge)</span>'
    st.markdown(
        f'<p class="llm-plain-text" style="margin:0;">'
        f"- <strong>{icon} {html.escape(judge)}</strong> "
        f"({html.escape(verdict_label)}, {score}/10): {html.escape(hint or '')}"
        f"{quality_note}</p>",
        unsafe_allow_html=True,
    )


def write_labelled_plain(label: str, text: str) -> None:
    """Display a bold label followed by plain model text."""
    safe_label = html.escape(label)
    safe_text = html.escape(text or "")
    st.markdown(
        f'<p class="llm-plain-text" style="{_PLAIN_STYLE}">'
        f"<strong>{safe_label}</strong> {safe_text}</p>",
        unsafe_allow_html=True,
    )


def write_status_badge(status: str, *, tone: str = "neutral") -> None:
    """Compact colored status pill for iteration comparison."""
    safe = html.escape(status)
    st.markdown(
        f'<span class="iteration-status iteration-status-{tone}">{safe}</span>',
        unsafe_allow_html=True,
    )


def write_appeal_outcome_badge(outcome: str) -> None:
    """Compact outcome label for post-appeal evidence asks."""
    tone = "neutral"
    if outcome == "Evidence met":
        tone = "positive"
    elif outcome == "Not met":
        tone = "negative"
    write_status_badge(outcome, tone=tone)


def write_synthesis(text: str) -> None:
    """Display synthesis in a bordered container with markdown formatting."""
    with st.container(border=True):
        st.markdown(text or "")


def write_verdict_card(
    synthesis: Synthesis,
    roast_panel: RoastPanel | None = None,
    *,
    quality: dict | None = None,
) -> None:
    """Decision-first verdict card for structured moderator synthesis."""
    icon = _RECOMMENDATION_ICON.get(synthesis.overall_recommendation, "\u26aa")
    priorities = top_priorities(synthesis, roast_panel)
    low_confidence = bool((quality or {}).get("low_confidence"))
    reasons = (quality or {}).get("reasons") or []

    with st.container(border=True):
        if low_confidence:
            st.warning(
                "Low-confidence verdict — treat priorities as directional, not precise. "
                + " ".join(reasons)
            )

        st.markdown(
            f"### {icon} {synthesis.overall_recommendation.value} "
            f"({synthesis.confidence.value} confidence)"
        )

        if priorities:
            st.markdown("**Top priorities**")
            for idx, item in enumerate(priorities, start=1):
                write_labelled_plain(f"{idx}.", item)

        detail_lines: list[str] = []
        if synthesis.top_strengths:
            detail_lines.append("**Strengths**")
            detail_lines.extend(f"- {item}" for item in synthesis.top_strengths)
        if synthesis.top_risks and synthesis.top_risks != priorities:
            detail_lines.append("**Top risks**")
            detail_lines.extend(f"- {item}" for item in synthesis.top_risks)
        detail_lines.append(f"**Biggest disagreement:** {synthesis.biggest_disagreement}")

        if detail_lines:
            with st.expander("Full rationale", expanded=False):
                st.markdown("\n\n".join(detail_lines))
