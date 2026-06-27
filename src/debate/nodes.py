import json
from typing import Any

from jinja2 import Environment, FileSystemLoader
from langchain_core.messages import AIMessage
from langgraph.config import get_stream_writer

from config import DEBATE_PERSONAS, JUDGE_ORDER, PROMPTS_DIR
from idea_context import wrap_user_idea

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
) -> str:
    """Stream LLM output; emit debate_token custom events when inside a graph node."""
    stream = getattr(model, "stream", None)
    if stream is None:
        text = _response_text(model.invoke(messages))
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
        return text

    writer = get_stream_writer()
    parts: list[str] = []
    for chunk in stream(messages):
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
    return "".join(parts).strip()


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


def make_speaker_node(judge: str, model: Any):
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


def make_moderator_node(model: Any):
    def moderator_node(state: dict) -> dict:
        transcript = "\n".join(
            f"Round {msg['round']}: {msg['speaker']}: {msg['content']}"
            for msg in state["debate_messages"]
        )

        response = model.invoke(
            [
                {
                    "role": "user",
                    "content": template_env.get_template("moderator_node_prompt.jinja2").render(
                        state=state,
                        startup_idea=wrap_user_idea(state["startup_idea"]),
                        original_verdicts=_format_verdicts_readable(state["verdicts"]),
                        transcript=transcript,
                    ),
                }
            ]
        )

        synthesis = _response_text(response)

        return {
            "final_synthesis": synthesis,
            "debate_messages": [
                {"speaker": "moderator", "round": state["round"], "content": synthesis}
            ],
            "messages": [AIMessage(content=synthesis)],
        }

    return moderator_node
