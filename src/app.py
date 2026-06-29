import base64
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pydantic import ValidationError
import streamlit as st

from appeal.service import run_appeal
from config import get_settings
from debate.revote import (
    appeal_baseline_panel,
    roast_panel_from_state_verdicts,
    score_change_reason,
)
from idea_context import build_startup_idea_context, idea_display_summary
from judges.synthesis import assess_verdict_output_quality, parse_structured_synthesis
from memory.context import build_memory_context
from memory.factory import build_idea_store
from memory.identity import get_local_user_id
from memory.models import IdeaRecord
from memory.retrieval import records_for_memory
from modeling import build_chat_model
from research.service import (
    TavilyHttpClient,
    build_research_context,
    decide_web_search_usage,
    format_research_context,
)
from ui.streamlit_runner import (
    render_run_metrics_footer,
    run_debate_in_container,
    run_deepagent_roast_in_status,
    run_deterministic_pipeline_in_ui,
)
from ui.text_display import (
    write_labelled_plain,
    write_plain_text,
    write_roast_quote,
    write_synthesis,
    write_verdict_card,
)
from utils.scoring_chart import generate_radar_chart
from utils.transcript_exporter import export_transcript
from verification import assess_revote_quality
from version import get_version

get_settings()

# ── Page config ──

st.set_page_config(page_title="Roast My Startup", page_icon="\U0001f525", layout="wide")

# ── Custom CSS ──

st.markdown(
    """
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
    img.radar-chart-img {
        width: 100%;
        height: auto;
        display: block;
        max-width: 100%;
    }
    .llm-plain-text {
        font-family: inherit;
        font-size: inherit;
        font-style: normal;
        color: inherit;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ── Header ──

st.title("Roast My Startup")
st.caption("Submit your startup idea. Five AI judges will roast it, then debate each other.")

idea_store = build_idea_store()

if "user_id" not in st.session_state:
    st.session_state.user_id = get_local_user_id(idea_store)

# ── Sidebar: settings ──

with st.sidebar:
    st.header("\u2699\ufe0f Settings")
    settings = get_settings()
    execution_flow = st.selectbox(
        "Execution flow",
        options=["deterministic", "deepagents"],
        format_func=lambda value: "Deterministic" if value == "deterministic" else "DeepAgents",
    )
    model_runtime = st.selectbox(
        "Model",
        options=["local", "deepseek"],
        format_func=lambda value: (
            f"Local ({settings.local_model})"
            if value == "local"
            else f"DeepSeek API ({settings.deepseek_model})"
        ),
    )
    enable_web_search = st.checkbox(
        "Enable web research (Tavily)",
        value=settings.enable_web_search,
        help=(
            "Runs at most one bounded search pass for market-sensitive ideas. "
            "If heuristic says search is unnecessary, it is skipped."
        ),
    )
    max_rounds = st.slider(
        "Debate rounds", min_value=1, max_value=5, value=settings.max_debate_rounds
    )
    st.divider()
    st.subheader("Memory")
    recent_records = idea_store.list_recent(st.session_state.user_id, limit=5)
    if recent_records:
        for record in recent_records:
            avg = sum(v.score for v in record.roast_panel.verdicts) / len(
                record.roast_panel.verdicts
            )
            st.markdown(
                f"**{record.created_at.date()}** · {avg:.1f}/10  \n"
                f"{idea_display_summary(record.idea_text, max_chars=100)}"
            )
    else:
        st.caption("No previous ideas remembered yet.")
    st.divider()
    active_model = settings.local_model if model_runtime == "local" else settings.deepseek_model
    st.caption(f"Runtime: `{model_runtime}`")
    st.caption(f"Model: `{active_model}`")
    st.caption(f"Flow: `{execution_flow}`")
    st.caption(f"v{get_version()}")

# ── Main input ──

idea_text = st.text_area(
    "Describe your startup idea:",
    height=120,
    placeholder="e.g., An AI-powered journal that tracks your decisions and measures whether your reasoning was correct months later.",
)

with st.expander("Optional details (helps judges roast more precisely)"):
    col_left, col_right = st.columns(2)
    with col_left:
        target_customer = st.text_input(
            "Target customer",
            placeholder="e.g., Solo SaaS founders doing $10k–$100k MRR",
        )
        pricing = st.text_input(
            "Pricing",
            placeholder="e.g., $29/mo per seat, freemium with $99/yr pro tier",
        )
    with col_right:
        traction = st.text_input(
            "Traction",
            placeholder="e.g., 120 paying users, $4.2k MRR, 18% MoM growth",
        )
        competitors_raw = st.text_input(
            "Competitors",
            placeholder="e.g., Notion, Roam Research (comma-separated)",
        )

run_clicked = st.button("\U0001f525 Roast It!", type="primary", use_container_width=True)

# ── Session state initialization ──

if "roast_panel" not in st.session_state:
    st.session_state.roast_panel = None
if "debate_result" not in st.session_state:
    st.session_state.debate_result = None
if "startup_idea_used" not in st.session_state:
    st.session_state.startup_idea_used = None
if "current_record" not in st.session_state:
    st.session_state.current_record = None
if "revised_panel" not in st.session_state:
    st.session_state.revised_panel = None
if "revised_synthesis" not in st.session_state:
    st.session_state.revised_synthesis = None
if "appeal_text_used" not in st.session_state:
    st.session_state.appeal_text_used = None
if "run_metrics" not in st.session_state:
    st.session_state.run_metrics = None

# ── Run the pipeline ──

if run_clicked and idea_text.strip():
    competitors = [part.strip() for part in competitors_raw.split(",") if part.strip()]
    startup_idea = build_startup_idea_context(
        idea_text,
        target_customer=target_customer or None,
        pricing=pricing or None,
        traction=traction or None,
        competitors=competitors or None,
    )
    st.session_state.roast_panel = None
    st.session_state.debate_result = None
    st.session_state.current_record = None
    st.session_state.revised_panel = None
    st.session_state.revised_synthesis = None
    st.session_state.appeal_text_used = None
    st.session_state.run_metrics = None
    st.session_state.startup_idea_used = startup_idea

    try:
        model = build_chat_model(
            model_choice=model_runtime,
            settings=settings,
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
        )
    except ValueError as exc:
        st.error(str(exc))
        st.stop()

    memory_context = build_memory_context(
        records_for_memory(idea_store, st.session_state.user_id, startup_idea, limit=3)
    )
    research_context: str | None = None
    deepagent_web_search_enabled = False
    if enable_web_search:
        tavily_key = os.getenv("TAVILY_API_KEY")
        if not tavily_key:
            st.warning(
                "Web research enabled but TAVILY_API_KEY is missing; continuing without search."
            )
        else:
            with st.status("Web research policy check...", expanded=False) as status:
                try:
                    search_decision = decide_web_search_usage(
                        policy_model=model,
                        startup_idea=startup_idea,
                    )
                    if search_decision.use_search:
                        if execution_flow == "deepagents":
                            deepagent_web_search_enabled = True
                            status.write("Policy allowed search: DeepAgents search tool enabled.")
                            status.update(label="✅ Web search enabled", state="complete")
                        else:
                            research = build_research_context(
                                startup_idea=startup_idea,
                                tavily_client=TavilyHttpClient(tavily_key),
                                max_results=settings.web_search_max_results,
                                enabled=True,
                                decision=search_decision,
                            )
                            if research:
                                research_context = format_research_context(research)
                                status.write(
                                    f"Added {len(research.findings)} cited sources for factual context."
                                )
                                status.update(label="✅ Web research added", state="complete")
                            else:
                                status.write(
                                    "Policy allowed search, but no high-signal sources were returned."
                                )
                                status.update(label="ℹ️ Web research empty", state="complete")
                    else:
                        status.write(f"Skipped by policy: {search_decision.rationale}")
                        status.update(label="ℹ️ Web research skipped", state="complete")
                except Exception as exc:  # noqa: BLE001 - fail-open in UI
                    status.update(
                        label="⚠️ Web research failed; continuing without it", state="error"
                    )
                    st.warning(f"Web research failed: {exc}")

    # ── Phase 1 + 2: Roast panel and debate ──

    st.subheader("Debate")
    debate_container = st.container()

    with st.status("Phase 1: Judges are roasting your idea...", expanded=True) as status:
        try:
            if execution_flow == "deepagents":
                roast_panel = run_deepagent_roast_in_status(
                    model=model,
                    startup_idea=startup_idea,
                    status=status,
                    memory_context=memory_context,
                    research_context=research_context,
                    web_search_enabled=deepagent_web_search_enabled,
                )
                status.update(
                    label="\u2705 Phase 1 complete — all judges have spoken!", state="complete"
                )
                with st.status("Phase 2: Judges are debating...", expanded=True) as debate_status:
                    debate_result = run_debate_in_container(
                        model,
                        startup_idea,
                        roast_panel,
                        max_rounds,
                        debate_container,
                        status=debate_status,
                    )
                    debate_status.update(
                        label="\u2705 Phase 2 complete — debate concluded!", state="complete"
                    )
                st.session_state.run_metrics = None
            else:
                roast_panel, debate_result, run_metrics = run_deterministic_pipeline_in_ui(
                    model=model,
                    startup_idea=startup_idea,
                    max_rounds=max_rounds,
                    status=status,
                    debate_container=debate_container,
                    memory_context=memory_context,
                    research_context=research_context,
                    model_runtime=model_runtime,
                )
                status.update(
                    label="\u2705 Roast and debate complete — all judges have spoken!",
                    state="complete",
                )
                st.session_state.run_metrics = run_metrics
        except (ValidationError, Exception) as exc:
            st.error(f"Pipeline failed: {exc}")
            st.stop()

    st.session_state.roast_panel = roast_panel
    st.session_state.debate_result = debate_result
    record = IdeaRecord(
        user_id=st.session_state.user_id,
        idea_text=startup_idea,
        roast_panel=roast_panel,
        debate_result=debate_result,
    )
    idea_store.save(record)
    st.session_state.current_record = record

elif run_clicked:
    st.warning("Please enter a startup idea first.")

# ── Render results from session state (persists across reruns) ──

roast_panel = st.session_state.roast_panel
debate_result = st.session_state.debate_result
revised_panel = st.session_state.revised_panel
revised_synthesis = st.session_state.revised_synthesis
post_debate_panel = (
    roast_panel_from_state_verdicts(debate_result["revised_verdicts"])
    if debate_result and debate_result.get("revised_verdicts")
    else None
)
effective_panel = post_debate_panel or roast_panel
structured_synthesis = (
    parse_structured_synthesis(debate_result) if debate_result is not None else None
)

if roast_panel is not None:
    if structured_synthesis is not None:
        st.subheader("\U0001f3af Verdict")
        quality = assess_verdict_output_quality(effective_panel, debate_result)
        write_verdict_card(structured_synthesis, effective_panel, quality=quality)
        st.divider()
    elif debate_result is not None:
        synthesis = debate_result.get("final_synthesis", "No synthesis produced.")
        if synthesis and synthesis != "No synthesis produced.":
            quality = assess_verdict_output_quality(effective_panel, debate_result)
            st.subheader("\U0001f3af Final Synthesis")
            if quality.get("low_confidence"):
                st.warning(
                    "Low-confidence verdict — the moderator returned free-text only. "
                    + " ".join(quality.get("reasons") or [])
                )
            write_synthesis(synthesis)
            st.divider()

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
            write_roast_quote(v.roast)
            write_labelled_plain("Key concern:", v.key_concern)
            if v.recommended_fix:
                write_labelled_plain("Recommended fix:", v.recommended_fix)

    # ── Radar chart ──

    chart_path = Path("roast_radar.png")
    generate_radar_chart(effective_panel, output_path=chart_path)

    col_chart, col_summary = st.columns([1, 1])
    with col_chart:
        chart_b64 = base64.b64encode(chart_path.read_bytes()).decode()
        st.markdown(
            f'<img class="radar-chart-img" src="data:image/png;base64,{chart_b64}" '
            f'alt="Judge Scores Radar Chart">',
            unsafe_allow_html=True,
        )
    with col_summary:
        avg = sum(v.score for v in effective_panel.verdicts) / len(effective_panel.verdicts)
        pass_count = sum(1 for v in effective_panel.verdicts if v.verdict.value == "PASS")
        fail_count = sum(1 for v in effective_panel.verdicts if v.verdict.value == "FAIL")
        cond_count = sum(1 for v in effective_panel.verdicts if v.verdict.value == "CONDITIONAL")

        st.metric("Average Score", f"{avg:.1f} / 10")
        st.markdown(
            f"\U0001f7e2 **{pass_count}** Pass &nbsp;&nbsp; "
            f"\U0001f7e1 **{cond_count}** Conditional &nbsp;&nbsp; "
            f"\U0001f534 **{fail_count}** Fail"
        )

    st.divider()

if post_debate_panel is not None and roast_panel is not None:
    st.subheader("Post-Debate Re-Vote")
    st.caption("Scores after the panel heard the full debate. Deltas compare to the initial roast.")
    revote_quality = assess_revote_quality(
        debate_result.get("initial_verdicts") if debate_result else None,
        debate_result.get("revised_verdicts") if debate_result else None,
        max_delta=get_settings().max_revote_score_delta,
    )
    if revote_quality.get("revote_directional_pile_on"):
        direction = revote_quality.get("revote_pile_on_direction", "down")
        st.warning(
            f"Possible debate pile-on — three or more judges moved scores {direction} after the debate. "
            "Treat deltas as discussion-driven, not independent re-scoring."
        )
    if revote_quality.get("revote_herded_deltas"):
        st.warning(
            "Possible score herding — four or more judges moved by the same amount. "
            "Treat deltas as discussion-driven, not independent re-scoring."
        )
    if revote_quality.get("revote_degenerate_panel"):
        st.warning(
            "Revised panel scores are suspiciously uniform. Re-vote output may not reflect "
            "independent judge perspectives."
        )
    if not revote_quality.get("revote_scores_moved"):
        st.info("No judge changed their score after the debate.")
    revote_cols = st.columns(5)
    for i, revised in enumerate(post_debate_panel.verdicts):
        original = next(v for v in roast_panel.verdicts if v.judge.value == revised.judge.value)
        delta = revised.score - original.score
        delta_label = f"{delta:+d}" if delta else "0"
        with revote_cols[i]:
            st.metric(
                label=revised.judge.value.upper(),
                value=f"{revised.score}/10",
                delta=delta_label,
            )
            st.caption(f"was {original.score}/10 · {revised.verdict.value}")
            reason = score_change_reason(original, revised)
            if reason and delta:
                write_labelled_plain("Why it moved:", reason)
            write_roast_quote(revised.roast)
    st.divider()

if debate_result is not None:
    st.subheader("Debate Transcript")

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
            write_plain_text(msg["content"])

    st.divider()

    render_run_metrics_footer(st.session_state.get("run_metrics"))

    # ── Appeal mode ──

    st.subheader("Appeal Mode")
    st.caption(
        "Argue back with concrete evidence. Judges will re-evaluate without rerunning the full debate."
    )
    appeal_text = st.text_area(
        "Your appeal:",
        height=100,
        placeholder="e.g., We already have three signed LOIs worth $180k ARR and pilots in two hospitals.",
    )
    appeal_clicked = st.button("Submit Appeal", type="secondary", use_container_width=True)

    if appeal_clicked:
        if not appeal_text.strip():
            st.warning("Write an appeal first.")
        else:
            try:
                model = build_chat_model(
                    model_choice=model_runtime,
                    settings=settings,
                    deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
                )
            except ValueError as exc:
                st.error(str(exc))
                st.stop()
            current_record = st.session_state.current_record
            startup_idea_used = st.session_state.startup_idea_used or ""
            prior_records = [
                record
                for record in records_for_memory(
                    idea_store,
                    st.session_state.user_id,
                    startup_idea_used,
                    limit=4,
                )
                if current_record is None or record.id != current_record.id
            ][:3]
            try:
                with st.status("Appeal mode: judges are re-evaluating...", expanded=True) as status:
                    status.write("Sending your appeal to all five judges...")
                    appeal_baseline = appeal_baseline_panel(roast_panel, debate_result)
                    appeal_result = run_appeal(
                        model=model,
                        startup_idea=st.session_state.startup_idea_used or "",
                        roast_panel=appeal_baseline,
                        debate_result=debate_result,
                        appeal_text=appeal_text,
                        memory_context=build_memory_context(prior_records),
                    )
                    status.update(
                        label="\u2705 Appeal complete — revised panel ready!", state="complete"
                    )
            except (ValidationError, Exception) as exc:
                st.error(f"Appeal failed: {exc}")
                st.stop()

            st.session_state.revised_panel = appeal_result.revised_panel
            st.session_state.revised_synthesis = appeal_result.revised_synthesis
            st.session_state.appeal_text_used = appeal_text.strip()

            if current_record is not None:
                updated_record = current_record.model_copy(
                    update={
                        "appeal_text": appeal_text,
                        "revised_panel": appeal_result.revised_panel,
                        "revised_synthesis": appeal_result.revised_synthesis,
                    }
                )
                idea_store.save(updated_record)
                st.session_state.current_record = updated_record

            st.rerun()

    if revised_panel is not None:
        st.markdown("#### Revised Verdicts")
        appeal_baseline = appeal_baseline_panel(roast_panel, debate_result)
        revised_cols = st.columns(5)
        for i, v in enumerate(revised_panel.verdicts):
            original = next(
                original_v
                for original_v in appeal_baseline.verdicts
                if original_v.judge.value == v.judge.value
            )
            delta = v.score - original.score
            delta_label = f"{delta:+d}" if delta else "0"
            with revised_cols[i]:
                st.metric(
                    label=v.judge.value.upper(),
                    value=f"{v.score}/10",
                    delta=delta_label,
                )
                st.caption(v.verdict.value)
                write_roast_quote(v.roast)
                write_labelled_plain("Key concern:", v.key_concern)

        if revised_synthesis:
            write_synthesis(revised_synthesis)

    # ── Export ──

    startup_idea_used = st.session_state.startup_idea_used or ""
    transcript_path = export_transcript(
        startup_idea_used,
        roast_panel,
        debate_result,
        appeal_text=st.session_state.appeal_text_used,
        revised_panel=revised_panel,
        revised_synthesis=revised_synthesis,
        run_metrics=st.session_state.get("run_metrics"),
    )
    transcript_content = transcript_path.read_text(encoding="utf-8")

    st.download_button(
        "\U0001f4e5 Download Transcript (.md)",
        data=transcript_content,
        file_name=transcript_path.name,
        mime="text/markdown",
    )
