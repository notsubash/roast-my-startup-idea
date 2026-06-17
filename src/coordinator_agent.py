import concurrent.futures
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from jinja2 import Environment, FileSystemLoader
from pydantic import ValidationError

from judges.schemas import Verdict, RoastPanel
from debate.graph import build_debate_graph
from config import PROMPTS_DIR, JUDGE_ORDER, get_settings

template_env = Environment(loader=FileSystemLoader(PROMPTS_DIR))

_JUDGE_TEMPLATES = {
    "vc":         "vc_judge_prompt.jinja2",
    "engineer":   "engineer_judge_prompt.jinja2",
    "pm":         "pm_judge_prompt.jinja2",
    "customer":   "customer_judge_prompt.jinja2",
    "competitor": "competitor_judge_prompt.jinja2",
}


def _invoke_judge(model, judge: str, startup_idea: str) -> Verdict:
    """Single judge call with structured output enforced via tool-calling."""
    structured_model = model.with_structured_output(Verdict)
    system_prompt = template_env.get_template(_JUDGE_TEMPLATES[judge]).render()

    return structured_model.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Evaluate this startup idea:\n\n{startup_idea}"),
    ])


def run_roast_panel(model, startup_idea: str) -> RoastPanel:
    """Phase 1: Call all 5 judges in parallel, return a validated RoastPanel."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            judge: pool.submit(_invoke_judge, model, judge, startup_idea)
            for judge in JUDGE_ORDER
        }
        verdicts = [futures[judge].result() for judge in JUDGE_ORDER]

    return RoastPanel(verdicts=verdicts)


def run_debate(model, startup_idea: str, roast_panel: RoastPanel, max_rounds: int = 3) -> dict:
    """Phase 2: Run the multi-round debate graph and return the full result dict."""
    debate_graph = build_debate_graph(model)
    return debate_graph.invoke({
        "messages": [HumanMessage(content="Begin the debate.")],
        "startup_idea": startup_idea,
        "verdicts": [v.model_dump() for v in roast_panel.verdicts],
        "debate_messages": [],
        "round": 1,
        "max_rounds": max_rounds,
        "current_speaker_idx": 0,
        "final_synthesis": None,
    })


def main():
    settings = get_settings()
    model = init_chat_model(settings.local_model)

    startup_idea = (
        "Decision Journal — Track decisions and measure whether your reasoning was correct months later."
    )

    # ── Phase 1: Parallel structured judge calls ──
    print("Phase 1 — Calling judges...\n")
    try:
        roast_panel = run_roast_panel(model, startup_idea)
    except (ValidationError, Exception) as e:
        print(f"Error in Phase 1: {e}")
        return

    print("Roast Panel:\n")
    print(roast_panel.model_dump_json(indent=2))

    # ── Phase 2: Debate graph ──
    print("\n\nPhase 2 — Running debate...\n")
    debate_result = run_debate(model, startup_idea, roast_panel, settings.max_debate_rounds)

    synthesis = debate_result.get("final_synthesis", "No synthesis produced.")
    print("Debate Synthesis:\n")
    print(synthesis)


if __name__ == "__main__":
    main()
