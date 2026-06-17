import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
from langchain.chat_models import init_chat_model
from pydantic import ValidationError

from coordinator_agent import run_roast_panel, run_debate
from config import get_settings
from utils.scoring_chart import generate_radar_chart
from utils.transcript_exporter import export_transcript

# ── Page config ──

st.set_page_config(page_title="Roast My Startup", page_icon="\U0001f525", layout="wide")

# ── Custom CSS ──

st.markdown("""
<style>
    .stMetricValue { font-size: 2rem !important; }
    .verdict-pass { color: #2ecc71; font-weight: bold; }
    .verdict-fail { color: #e74c3c; font-weight: bold; }
    .verdict-conditional { color: #f39c12; font-weight: bold; }
    div[data-testid="stChatMessage"] {
        border-left: 3px solid #e74c3c;
        padding-left: 1rem;
        margin-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ──

st.title("Roast My Startup")
st.caption("Submit your startup idea. Five AI judges will roast it, then debate each other.")

# ── Sidebar: settings ──

with st.sidebar:
    st.header("\u2699\ufe0f Settings")
    settings = get_settings()
    model_name = st.text_input("Model", value=settings.local_model)
    max_rounds = st.slider("Debate rounds", min_value=1, max_value=5, value=settings.max_debate_rounds)
    st.divider()
    st.caption(f"Running on: `{model_name}`")

# ── Main input ──

startup_idea = st.text_area(
    "Describe your startup idea:",
    height=120,
    placeholder="e.g., An AI-powered journal that tracks your decisions and measures whether your reasoning was correct months later.",
)

run_clicked = st.button("\U0001f525 Roast It!", type="primary", use_container_width=True)

if run_clicked and startup_idea.strip():
    model = init_chat_model(model_name)

    # ── Phase 1: Roast Panel ──

    with st.status("Phase 1: Judges are roasting your idea...", expanded=True) as status:
        try:
            roast_panel = run_roast_panel(model, startup_idea)
        except (ValidationError, Exception) as exc:
            st.error(f"Phase 1 failed: {exc}")
            st.stop()
        status.update(label="\u2705 Phase 1 complete — all judges have spoken!", state="complete")

    st.subheader("Individual Verdicts")

    verdict_icon = {"PASS": "\U0001f7e2", "FAIL": "\U0001f534", "CONDITIONAL": "\U0001f7e1"}
    cols = st.columns(5)
    for i, v in enumerate(roast_panel.verdicts):
        with cols[i]:
            icon = verdict_icon.get(v.verdict.value, "\u26aa")
            st.metric(
                label=f"{icon} {v.judge.value.upper()}",
                value=f"{v.score}/10",
            )
            st.caption(v.verdict.value)
            st.markdown(f"*\"{v.roast}\"*")
            st.markdown(f"**Key concern:** {v.key_concern}")

    # ── Radar chart ──

    chart_path = Path("roast_radar.png")
    generate_radar_chart(roast_panel, output_path=chart_path)

    col_chart, col_summary = st.columns([1, 1])
    with col_chart:
        st.image(str(chart_path), use_container_width=True)
    with col_summary:
        avg = sum(v.score for v in roast_panel.verdicts) / len(roast_panel.verdicts)
        pass_count = sum(1 for v in roast_panel.verdicts if v.verdict.value == "PASS")
        fail_count = sum(1 for v in roast_panel.verdicts if v.verdict.value == "FAIL")
        cond_count = sum(1 for v in roast_panel.verdicts if v.verdict.value == "CONDITIONAL")

        st.metric("Average Score", f"{avg:.1f} / 10")
        st.markdown(
            f"\U0001f7e2 **{pass_count}** Pass &nbsp;&nbsp; "
            f"\U0001f7e1 **{cond_count}** Conditional &nbsp;&nbsp; "
            f"\U0001f534 **{fail_count}** Fail"
        )

    st.divider()

    # ── Phase 2: Debate ──

    with st.status("Phase 2: Judges are debating...", expanded=True) as status:
        try:
            debate_result = run_debate(model, startup_idea, roast_panel, max_rounds)
        except Exception as exc:
            st.error(f"Phase 2 failed: {exc}")
            st.stop()
        status.update(label="\u2705 Phase 2 complete — debate concluded!", state="complete")

    st.subheader("Debate")

    judge_avatars = {
        "vc": "\U0001f4b0",
        "engineer": "\U0001f527",
        "pm": "\U0001f4cb",
        "customer": "\U0001f464",
        "competitor": "\U0001f3af",
    }

    current_round = 0
    for msg in debate_result.get("debate_messages", []):
        if msg["speaker"] == "moderator":
            continue
        if msg["round"] != current_round:
            current_round = msg["round"]
            st.markdown(f"#### Round {current_round}")

        avatar = judge_avatars.get(msg["speaker"], "\U0001f916")
        with st.chat_message(msg["speaker"], avatar=avatar):
            st.markdown(f"**{msg['speaker'].upper()}**")
            st.write(msg["content"])

    st.divider()

    # ── Synthesis ──

    st.subheader("\U0001f3af Final Synthesis")
    synthesis = debate_result.get("final_synthesis", "No synthesis produced.")
    st.info(synthesis)

    # ── Export ──

    transcript_path = export_transcript(startup_idea, roast_panel, debate_result)
    transcript_content = transcript_path.read_text(encoding="utf-8")

    st.download_button(
        "\U0001f4e5 Download Transcript (.md)",
        data=transcript_content,
        file_name=transcript_path.name,
        mime="text/markdown",
    )

elif run_clicked:
    st.warning("Please enter a startup idea first.")
