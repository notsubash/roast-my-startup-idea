import json
import os
from typing import Any
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

template_env = Environment(loader=FileSystemLoader("src/prompts"))

load_dotenv()

DEBATE_PERSONAS = os.getenv("DEBATE_PERSONAS").split(",")
JUDGE_ORDER = os.getenv("JUDGE_ORDER").split(",")

def _response_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    return str(content).strip()

def _own_verdict(state: dict, judge: str) -> dict | None:
    for verdict in state["verdicts"]:
        if verdict["judge"] == judge:
            return verdict
    return None

def _recent_transcript(state:dict, limit: int = 8) -> str:
    recent_messages = state["messages"][-limit:]
    if not recent_messages:
        return "No debate messages yet."

    return "\n".join(
        f"Round {msg['round']}: {msg['speaker']}: {msg['content']}"
        for msg in recent_messages
    )

def make_speaker_node(judge:str, model: Any):
    def speaker_node(state:dict) -> dict:
        response = model.invoke(
            [{
                "role": "user",
                "content": template_env.get_template("speaker_node_prompt.jinja2").render(judge=judge, state=state, DEBATE_PERSONAS=DEBATE_PERSONAS)
            }]
        )

        content = _response_text(response)

        return {
            "messages": [
                {
                    "speaker": judge,
                    "round": state["round"],
                    "content": content
                }
            ],
            "current_speaker_idx": JUDGE_ORDER.index(judge) + 1,
        }
    return speaker_node


def make_moderator_node(model: Any):
    def moderator_node(state:dict) -> dict:
        transcript = "\n".join(
            f'Round {msg["round"]}: {msg["speaker"]}: {msg["content"]}'
            for msg in state["messages"]
        )

        response = model.invoke(
            [{
                "role": "user",
                "content": template_env.get_template("moderator_node_prompt.jinja2").render(state=state, transcript=transcript)
            }]
        )

        synthesis = _response_text(response)

        return {
            "final_synthesis": synthesis,
            "messages": [
                {
                    "speaker": "moderator",
                    "round": state["round"],
                    "content": synthesis
                }
            ]
        }

    return moderator_node