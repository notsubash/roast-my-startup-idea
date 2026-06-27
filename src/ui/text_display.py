"""Render LLM prose in Streamlit without accidental markdown/HTML formatting."""

import html

import streamlit as st

_PLAIN_STYLE = "margin:0; white-space:pre-wrap;"


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
