import json
import os
from typing import Any
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

from config import PROMPTS_DIR, JUDGE_ORDER, DEBATE_PERSONAS
template_env = Environment(loader=FileSystemLoader(PROMPTS_DIR))

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
                "content": template_env.get_template("speaker_node_prompt.jinja2").render(
                    judge=judge, 
                    state=state, 
                    personas=DEBATE_PERSONAS[judge],
                    startup_idea=state["startup_idea"],
                    own_verdict=json.dumps(_own_verdict(state, judge), indent=2),
                    other_verdicts=json.dumps(state["verdicts"], indent=2),
                    recent_transcript=_recent_transcript(state)
                )
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
                "content": template_env.get_template("moderator_node_prompt.jinja2").render(
                    state=state, 
                    startup_idea=state["startup_idea"],
                    original_verdicts=json.dumps(state["verdicts"], indent=2),
                    transcript=transcript
                )
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