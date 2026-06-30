from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from judges.service import build_judge_user_prompt, judge_system_prompt
import tests  # noqa: F401


class JudgePromptContextTest(unittest.TestCase):
    def test_build_judge_user_prompt_includes_memory_and_research_context(self):
        prompt = build_judge_user_prompt(
            startup_idea="AI compliance copilot for hospitals",
            memory_context="- Prior pitch avg 4.2/10",
            research_context=(
                "Web research:\n"
                "- Source: https://example.com/compliance-market\n"
                "  Finding: Compliance spend is growing."
            ),
        )

        self.assertIn("Evaluate this startup idea", prompt)
        self.assertIn("Prior user memory", prompt)
        self.assertIn("Web research", prompt)
        self.assertIn("https://example.com/compliance-market", prompt)

    def test_build_judge_user_prompt_flags_structured_claims(self):
        prompt = build_judge_user_prompt(
            startup_idea=(
                "AI journal for founders\n\nTarget customer: Solo founders\n\nPricing: $29/mo"
            ),
        )
        self.assertIn("founder claims to verify skeptically", prompt)
        self.assertIn("<idea>", prompt)
        self.assertIn("recommended_fix", prompt)
        self.assertIn("evidence_to_change_verdict", prompt)

    def test_judge_system_prompt_includes_lens_isolation(self):
        for judge in ("vc", "engineer", "pm", "customer", "competitor"):
            prompt = judge_system_prompt(judge)
            self.assertIn("Lens isolation (mandatory)", prompt, judge)
            self.assertIn("Never overlap another judge", prompt, judge)
            self.assertIn("evidence_to_change_verdict", prompt, judge)


if __name__ == "__main__":
    unittest.main()
