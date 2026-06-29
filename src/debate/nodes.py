import json
import logging
import time
from typing import Any

from jinja2 import Environment, FileSystemLoader
from langchain_core.messages import AIMessage
from langgraph.config import get_stream_writer

from config import DEBATE_PERSONAS, JUDGE_ORDER, PROMPTS_DIR
from debate.revote import roast_panel_from_state_verdicts, run_revote
from idea_context import wrap_user_idea
from judges.synthesis import Synthesis, synthesis_to_prose
from llm_resilience import call_with_llm_retry, is_transient_llm_error
from observability.metrics import RunMetricsCollector

template_env = Environment(loader=FileSystemLoader(PROMPTS_DIR))
logger = logging.getLogger(__name__)


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


def _collect_stream_chunks(stream, messages: list[dict]) -> tuple[str, Any | None, list[str]]:
    """Buffer a model stream; only emit after the full response arrives."""
    parts: list[str] = []
    last_chunk: Any | None = None
    for chunk in stream(messages):
        last_chunk = chunk
        delta = _chunk_delta(chunk)
        if delta:
            parts.append(delta)
    return "".join(parts).strip(), last_chunk, parts


def _emit_debate_tokens(
    writer,
    *,
    speaker: str,
    round_num: int | None,
    parts: list[str],
) -> None:
    for delta in parts:
        writer(
            {
                "type": "debate_token",
                "speaker": speaker,
                "round": round_num,
                "delta": delta,
            }
        )


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
    retry_label = f"debate {label}"
    writer = get_stream_writer()
    stream = getattr(model, "stream", None)

    def _record(response: Any | None, output_text: str) -> str:
        if metrics is not None:
            metrics.record_debate(
                label,
                seconds=time.perf_counter() - started_at,
                response=response,
                prompt_text=prompt_text,
                output_text=output_text,
            )
        return output_text

    if stream is not None:
        last_error: BaseException | None = None
        for attempt in range(3):
            try:
                text, last_chunk, parts = _collect_stream_chunks(stream, messages)
                if writer and speaker is not None and parts:
                    _emit_debate_tokens(
                        writer,
                        speaker=speaker,
                        round_num=round_num,
                        parts=parts,
                    )
                return _record(last_chunk, text)
            except Exception as exc:
                if not is_transient_llm_error(exc):
                    raise
                last_error = exc
                if attempt + 1 >= 3:
                    break
                delay = 0.5 * (attempt + 1)
                logger.warning(
                    "%s stream failed (%s); retrying in %.1fs (%d/3)",
                    retry_label,
                    exc,
                    delay,
                    attempt + 2,
                )
                time.sleep(delay)

        logger.warning(
            "%s stream failed after retries (%s); falling back to invoke",
            retry_label,
            last_error,
        )

    def _invoke_once() -> str:
        response = model.invoke(messages)
        text = _response_text(response)
        if writer and speaker is not None and text:
            writer(
                {
                    "type": "debate_token",
                    "speaker": speaker,
                    "round": round_num,
                    "delta": text,
                }
            )
        return _record(response, text)

    return call_with_llm_retry(_invoke_once, label=f"{retry_label} invoke")


def _own_verdict(state: dict, judge: str) -> dict | None:
    for verdict in state["verdicts"]:
        if verdict["judge"] == judge:
            return verdict
    return None


def _debate_transcript_for_speaker(state: dict) -> str:
    """Round 1 sees recent context; later rounds see full transcript to curb repetition."""
    messages = state["debate_messages"]
    if not messages:
        return "No debate messages yet."
    pool = messages if state["round"] >= 2 else messages[-8:]
    return "\n".join(f"Round {msg['round']}: {msg['speaker']}: {msg['content']}" for msg in pool)


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
                        recent_transcript=_debate_transcript_for_speaker(state),
                        round=state["round"],
                        max_rounds=state["max_rounds"],
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
    def _invoke_once() -> tuple[str, Any]:
        response = model.invoke([{"role": "user", "content": prompt}])
        return _response_text(response), response

    return call_with_llm_retry(_invoke_once, label="moderator synthesis")


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
