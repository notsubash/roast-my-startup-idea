from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
import os
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
from utils.tool_call_tracer import print_trace
from utils.roast_panel_parser import extract_roast_panel
from judges.schemas import RoastPanel
from pydantic import ValidationError

from config import PROMPTS_DIR, get_settings

template_env = Environment(loader=FileSystemLoader(PROMPTS_DIR))

def build_coordinator_agent():
    model = init_chat_model(get_settings().local_model)

    subagents = [
        {
            "name": "vc_judge",
            "description": "A subagent that is responsible for evaluating the startup idea from a venture capital perspective.",
            "system_prompt": template_env.get_template("vc_judge_prompt.jinja2").render()
        },
        {
            "name": "engineer_judge",
            "description": "A subagent that is responsible for evaluating the startup idea from an engineering perspective.",
            "system_prompt": template_env.get_template("engineer_judge_prompt.jinja2").render()
        },
        {
            "name": "pm_judge",
            "description": "A subagent that is responsible for evaluating the startup idea from a product management perspective.",
            "system_prompt": template_env.get_template("pm_judge_prompt.jinja2").render()
        },
        {
            "name": "customer_judge",
            "description": "A subagent that is responsible for evaluating the startup idea from a customer perspective.",
            "system_prompt": template_env.get_template("customer_judge_prompt.jinja2").render()
        },
        {
            "name": "competitor_judge",
            "description": "A subagent that is responsible for evaluating the startup idea from a competitor perspective.",
            "system_prompt": template_env.get_template("competitor_judge_prompt.jinja2").render()
        }
    ]

    return create_deep_agent(
        model = model,
        subagents=subagents,
        response_format=RoastPanel,
        system_prompt=template_env.get_template("startup_orchestrator_prompt.jinja2").render()
    )

def main():
    agent = build_coordinator_agent()

    startup_idea = (
        "A B2B SaaS tool that predicts customer churn from support tickets."
    )

    user_prompt = (
        f"""Evaluate the following startup idea from all five judge's perspectives:

        {startup_idea}

        Return the RoastPanel in valid JSON format.
        """
    )

    result = agent.invoke(
        {"messages":[{"role":"user", "content": user_prompt}]}
    )
    print_trace(result["messages"])

    try:
        roast_panel = extract_roast_panel(result)
    except (ValueError, ValidationError) as e:
        print(f"\nError extracting RoastPanel: {e}")
        return None

    print("\nValidated RoastPanel:\n")
    print(roast_panel.model_dump_json(indent=2))

if __name__ == "__main__":
    main()