"""CLI entry point for the roast pipeline."""

from langchain.chat_models import init_chat_model
from pydantic import ValidationError

from config import get_settings
from pipeline import run_pipeline


def main():
    settings = get_settings()
    model = init_chat_model(settings.local_model)

    startup_idea = (
        "Decision Journal — Track decisions and measure whether your "
        "reasoning was correct months later."
    )

    print("Phase 1 — Calling judges...\n")
    try:
        roast_panel, debate_result = run_pipeline(model, startup_idea, settings.max_debate_rounds)
    except (ValidationError, Exception) as e:
        print(f"Pipeline failed: {e}")
        return

    print("Roast Panel:\n")
    print(roast_panel.model_dump_json(indent=2))

    synthesis = debate_result.get("final_synthesis", "No synthesis produced.")
    print("\n\nPhase 2 — Debate synthesis:\n")
    print(synthesis)


if __name__ == "__main__":
    main()
