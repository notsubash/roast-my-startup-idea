"""Optional DeepAgents orchestrator — experimental, not on the production path.

Why this exists:
  DeepAgents provides subagent spawning (task()), filesystem context mgmt,
  write_todos planning, and durable LangGraph execution. These are valuable
  for open-ended agent workflows.

Why we don't use it for roast/debate today:
  1. Local Ollama models often skip or mis-route task() calls to subagents.
  2. Debate requires deterministic turn order — an LLM orchestrator cannot
     reliably guarantee all 5 judges speak in 3 rounds.
  3. Structured output (Verdict schema) is more reliable via direct
     model.with_structured_output() than parsing ToolMessage payloads.

Use stream_pipeline() / run_pipeline() for production. Use this module
when experimenting with DeepAgents capabilities or when running on models
with strong tool-calling (e.g. devstral-2, Claude).
"""

import os

from jinja2 import Environment, FileSystemLoader

try:
    from deepagents import create_deep_agent
except ImportError:
    create_deep_agent = None

from config import JUDGE_ORDER, PROMPTS_DIR, get_settings
from judges.schemas import RoastPanel, Verdict
from judges.service import judge_system_prompt
from research.service import TavilyHttpClient, make_deepagent_search_tool
from utils.roast_panel_parser import extract_roast_panel

template_env = Environment(loader=FileSystemLoader(PROMPTS_DIR))


def _optional_tavily_tool(web_search_enabled: bool, max_results: int):
    if not web_search_enabled:
        return None
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if not tavily_api_key:
        return None
    tavily_client = TavilyHttpClient(tavily_api_key)
    return make_deepagent_search_tool(tavily_client, max_results=max_results)


def build_orchestrator(
    model,
    web_search_enabled: bool = False,
    subagent_response_format: bool = True,
):
    """Create a DeepAgents agent with five judge subagents registered."""
    if create_deep_agent is None:
        raise ImportError("deepagents is required. Install with: pip install deepagents")

    judge_subagents = []
    for judge in JUDGE_ORDER:
        subagent = {
            "name": f"judge-{judge}",
            "description": f"Evaluates startup ideas as the {judge} persona",
            "system_prompt": judge_system_prompt(judge),
        }
        if subagent_response_format:
            subagent["response_format"] = Verdict
        judge_subagents.append(subagent)

    orchestrator_prompt = template_env.get_template("startup_orchestrator_prompt.jinja2").render()
    settings = get_settings()
    tools = []
    tavily_tool = _optional_tavily_tool(
        web_search_enabled=web_search_enabled,
        max_results=settings.web_search_max_results,
    )
    if tavily_tool:
        tools.append(tavily_tool)

    return create_deep_agent(
        model=model,
        tools=tools or None,
        subagents=judge_subagents,
        system_prompt=orchestrator_prompt,
    )


def run_roast_via_orchestrator(
    model,
    startup_idea: str,
    research_context: str | None = None,
    web_search_enabled: bool = False,
) -> RoastPanel:
    """Experimental: delegate Phase 1 to DeepAgents task() tool.

    May fail or return incomplete panels with local models. Falls back to
    extract_roast_panel() which parses ToolMessage payloads.
    """
    user_content = template_env.get_template("deepagent_user_prompt.jinja2").render(
        startup_idea=startup_idea,
        research_context=research_context,
    )
    agent = build_orchestrator(
        model,
        web_search_enabled=web_search_enabled,
        subagent_response_format=True,
    )

    try:
        result = agent.invoke(
            {
                "messages": [{"role": "user", "content": user_content}],
            }
        )
    except Exception as exc:
        if not _is_response_format_unavailable_error(exc):
            raise
        fallback_agent = build_orchestrator(
            model,
            web_search_enabled=web_search_enabled,
            subagent_response_format=False,
        )
        result = fallback_agent.invoke(
            {
                "messages": [{"role": "user", "content": user_content}],
            }
        )

    return extract_roast_panel(result)


def _is_response_format_unavailable_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "response_format" in message and "unavailable" in message
