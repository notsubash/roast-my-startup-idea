import json
import time
from typing import Any

from jinja2 import Environment, FileSystemLoader
from langchain_core.messages import AIMessage
from langgraph.config import get_stream_writer

from config import DEBATE_PERSONAS, JUDGE_ORDER, PROMPTS_DIR
from debate.revote import roast_panel_from_state_verdicts, run_revote
from idea_context import wrap_user_idea
from judges.synthesis import Synthesis, synthesis_to_prose
from observability.metrics import RunMetricsCollector

template_env = Environment(loader=FileSystemLoader(PROMPTS_DIR))


def _response_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    return str(content).strip()


def _chunk_delta(chunk: Any) -> str:
    content = getattr(chunk, "content", chunk)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content) if content else ""


def _stream_model_text(
    model: Any,
    messages: list[dict],
    *,
    speaker: str | None = None,
    round_num: int | None = None,
    metrics: RunMetricsCollector | None = None,
    call_label: str | None = None,
) -> str:
    """Stream LLM output; emit debate_token custom events when inside a graph node."""
    started_at = time.perf_counter()
    prompt_text = messages[0]["content"] if messages else ""
    label = call_label or speaker or "debate"
    stream = getattr(model, "stream", None)
    if stream is None:
        response = model.invoke(messages)
        text = _response_text(response)
        writer = get_stream_writer()
        if writer and speaker is not None and text:
            writer(
                {
                    "type": "debate_token",
                    "speaker": speaker,
                    "round": round_num,
                    "delta": text,
                }
            )
        if metrics is not None:
            metrics.record_debate(
                label,
                seconds=time.perf_counter() - started_at,
                response=response,
                prompt_text=prompt_text,
                output_text=text,
            )
        return text

    writer = get_stream_writer()
    parts: list[str] = []
    last_chunk: Any = None
    for chunk in stream(messages):
        last_chunk = chunk
        delta = _chunk_delta(chunk)
        if not delta:
            continue
        parts.append(delta)
        if writer and speaker is not None:
            writer(
                {
                    "type": "debate_token",
                    "speaker": speaker,
                    "round": round_num,
                    "delta": delta,
                }
            )
    text = "".join(parts).strip()
    if metrics is not None:
        metrics.record_debate(
            label,
            seconds=time.perf_counter() - started_at,
            response=last_chunk,
            prompt_text=prompt_text,
            output_text=text,
        )
    return text


def _own_verdict(state: dict, judge: str) -> dict | None:
    for verdict in state["verdicts"]:
        if verdict["judge"] == judge:
            return verdict
    return None


def _recent_transcript(state: dict, limit: int = 8) -> str:
    recent_messages = state["debate_messages"][-limit:]
    if not recent_messages:
        return "No debate messages yet."

    return "\n".join(
        f"Round {msg['round']}: {msg['speaker']}: {msg['content']}" for msg in recent_messages
    )


def make_speaker_node(judge: str, model: Any, metrics: RunMetricsCollector | None = None):
    def speaker_node(state: dict) -> dict:
        # ponytail: LangGraph get_stream_writer + stream_mode="custom" in service.py
        # streams tokens mid-node; graph still owns routing.
        content = _stream_model_text(
            model,
            [
                {
                    "role": "user",
                    "content": template_env.get_template("speaker_node_prompt.jinja2").render(
                        judge=judge,
                        state=state,
                        persona=DEBATE_PERSONAS[judge],
                        startup_idea=wrap_user_idea(state["startup_idea"]),
                        own_verdict=json.dumps(_own_verdict(state, judge), indent=2),
                        other_verdicts=json.dumps(state["verdicts"], indent=2),
                        recent_transcript=_recent_transcript(state),
                    ),
                }
            ],
            speaker=judge,
            round_num=state["round"],
            metrics=metrics,
        )

        return {
            "debate_messages": [{"speaker": judge, "round": state["round"], "content": content}],
            "current_speaker_idx": JUDGE_ORDER.index(judge) + 1,
        }

    return speaker_node


def _format_verdicts_readable(verdicts: list[dict]) -> str:
    parts = []
    for v in verdicts:
        parts.append(
            f"- {v['judge'].upper()} ({v['verdict']}, {v['score']}/10): "
            f"{v.get('key_concern', 'N/A')}"
        )
    return "\n".join(parts)


def _invoke_plain_synthesis(model: Any, prompt: str) -> tuple[str, Any]:
    response = model.invoke([{"role": "user", "content": prompt}])
    return _response_text(response), response


def _invoke_structured_synthesis(model: Any, prompt: str) -> tuple[Synthesis | None, Any | None]:
    structured_factory = getattr(model, "with_structured_output", None)
    if structured_factory is None:
        return None, None
    try:
        structured_model = structured_factory(Synthesis)
        result = structured_model.invoke([{"role": "user", "content": prompt}])
        if result is None:
            return None, None
        return Synthesis.model_validate(result), result
    except Exception:
        # ponytail: local models often miss structured output; legacy prose fallback below.
        return None, None


def _render_moderator_prompt(template_name: str, state: dict, transcript: str) -> str:
    return template_env.get_template(template_name).render(
        state=state,
        startup_idea=wrap_user_idea(state["startup_idea"]),
        original_verdicts=_format_verdicts_readable(state["verdicts"]),
        transcript=transcript,
    )


def make_moderator_node(model: Any, metrics: RunMetricsCollector | None = None):
    def moderator_node(state: dict) -> dict:
        transcript = "\n".join(
            f"Round {msg['round']}: {msg['speaker']}: {msg['content']}"
            for msg in state["debate_messages"]
        )

        prompt = _render_moderator_prompt("moderator_node_prompt.jinja2", state, transcript)
        started_at = time.perf_counter()

        structured, structured_response = _invoke_structured_synthesis(model, prompt)
        if structured is not None:
            synthesis = synthesis_to_prose(structured)
            response_payload = structured
            metrics_response = structured_response
            metrics_prompt = prompt
        else:
            # ponytail: second LLM call only when structured output fails; ceiling is 2x moderator cost.
            prose_prompt = _render_moderator_prompt(
                "moderator_node_prose_prompt.jinja2", state, transcript
            )
            synthesis, metrics_response = _invoke_plain_synthesis(model, prose_prompt)
            response_payload = None
            metrics_prompt = prose_prompt

        if metrics is not None:
            metrics.record_debate(
                "moderator",
                seconds=time.perf_counter() - started_at,
                response=metrics_response,
                prompt_text=metrics_prompt,
                output_text=synthesis,
            )

        return {
            "final_synthesis": synthesis,
            "structured_synthesis": (
                response_payload.model_dump() if response_payload is not None else None
            ),
            "debate_messages": [
                {"speaker": "moderator", "round": state["round"], "content": synthesis}
            ],
            "messages": [AIMessage(content=synthesis)],
        }

    return moderator_node


def make_revote_node(
    model: Any,
    metrics: RunMetricsCollector | None = None,
    abort_check=None,
):
    def revote_node(state: dict) -> dict:
        roast_panel = roast_panel_from_state_verdicts(state["initial_verdicts"])
        revised_panel = run_revote(
            model,
            state["startup_idea"],
            roast_panel,
            state["debate_messages"],
            metrics=metrics,
            abort_check=abort_check,
        )
        return {"verdicts": [v.model_dump() for v in revised_panel.verdicts]}

    return revote_node
