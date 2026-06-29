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


def write_labelled_plain(label: str, text: str) -> None:
    """Display a bold label followed by plain model text."""
    safe_label = html.escape(label)
    safe_text = html.escape(text or "")
    st.markdown(
        f'<p class="llm-plain-text" style="{_PLAIN_STYLE}">'
        f"<strong>{safe_label}</strong> {safe_text}</p>",
        unsafe_allow_html=True,
    )


def write_synthesis(text: str) -> None:
    """Display synthesis in a bordered container with markdown formatting."""
    with st.container(border=True):
        st.markdown(text or "")


def write_verdict_card(
    synthesis: Synthesis,
    roast_panel: RoastPanel | None = None,
) -> None:
    """Decision-first verdict card for structured moderator synthesis."""
    icon = _RECOMMENDATION_ICON.get(synthesis.overall_recommendation, "\u26aa")
    priorities = top_priorities(synthesis, roast_panel)

    with st.container(border=True):
        st.markdown(
            f"### {icon} {synthesis.overall_recommendation.value} "
            f"({synthesis.confidence.value} confidence)"
        )

        if priorities:
            st.markdown("**Top priorities**")
            for idx, item in enumerate(priorities, start=1):
                write_labelled_plain(f"{idx}.", item)

        if synthesis.top_strengths:
            st.markdown("**Strengths**")
            for item in synthesis.top_strengths:
                st.markdown(f"- {html.escape(item)}")

        if synthesis.top_risks and synthesis.top_risks != priorities:
            st.markdown("**Top risks**")
            for item in synthesis.top_risks:
                st.markdown(f"- {html.escape(item)}")

        write_labelled_plain("Biggest disagreement:", synthesis.biggest_disagreement)
