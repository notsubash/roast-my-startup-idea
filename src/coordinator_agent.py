from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
import os
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
from utils.tool_call_tracer import print_trace

load_dotenv()

MODEL_NAME = os.getenv("LOCAL_MODEL")

template_env = Environment(loader=FileSystemLoader("src/prompts/coordinator-agent"))

def build_coordinator_agent():
    model = init_chat_model(MODEL_NAME)

    subagents = [
        {
            "name": "math_checker",
            "description": "A subagent that is responsible for checking the math and logic.",
            "system_prompt": template_env.get_template("math_subagent_prompt.jinja2").render()
        }
    ]

    return create_deep_agent(
        model = model,
        subagents=subagents,
        system_prompt=template_env.get_template("orchestrator_prompt.jinja2").render()
    )

def main():
    agent = build_coordinator_agent()

    user_prompt = (
        """Delegate to math_checker: estimate 15% of 260"""
        "Then return only the final answer."
    )

    result = agent.invoke(
        {"messages":[{"role":"user", "content": user_prompt}]}
    )
    print_trace(result["messages"])

    final_message = result["messages"][-1]
    print(getattr(final_message, "content", final_message))

if __name__ == "__main__":
    main()