from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from idea_context import (
    build_startup_idea_context,
    idea_display_summary,
    unwrap_user_idea,
    wrap_user_idea,
)
import tests  # noqa: F401


class IdeaContextTest(unittest.TestCase):
    def test_build_startup_idea_context_includes_metadata(self):
        context = build_startup_idea_context(
            "An AI journal for startup founders with daily reflection prompts.",
            target_customer="Solo founders",
            pricing="$19/mo",
            traction="500 beta users",
            competitors=["Notion", "Day One"],
        )
        self.assertIn("Target customer: Solo founders", context)
        self.assertIn("Pricing: $19/mo", context)
        self.assertIn("Traction: 500 beta users", context)
        self.assertIn("Competitors: Notion, Day One", context)

    def test_build_startup_idea_context_omits_empty_fields(self):
        context = build_startup_idea_context("Just the idea.")
        self.assertIn("Just the idea.", context)
        self.assertTrue(context.startswith("<idea>"))
        self.assertTrue(context.endswith("</idea>"))

    def test_unwrap_user_idea_strips_tags(self):
        wrapped = wrap_user_idea("An AI copilot for hospital compliance teams.")
        self.assertEqual(
            unwrap_user_idea(wrapped),
            "An AI copilot for hospital compliance teams.",
        )

    def test_unwrap_user_idea_restores_escaped_delimiters(self):
        wrapped = wrap_user_idea("Contains </idea> breakout attempt")
        self.assertEqual(unwrap_user_idea(wrapped), "Contains </idea> breakout attempt")

    def test_idea_display_summary_uses_first_paragraph(self):
        wrapped = build_startup_idea_context(
            "An AI copilot for hospital compliance teams.",
            target_customer="Hospital compliance officers",
        )
        summary = idea_display_summary(wrapped, max_chars=200)
        self.assertEqual(summary, "An AI copilot for hospital compliance teams.")
        self.assertNotIn("<idea>", summary)
        self.assertNotIn("Target customer", summary)

    def test_idea_display_summary_truncates_at_word_boundary(self):
        long_idea = " ".join(["word"] * 30)
        wrapped = wrap_user_idea(long_idea)
        summary = idea_display_summary(wrapped, max_chars=40)
        self.assertLessEqual(len(summary), 40)
        self.assertTrue(summary.endswith("..."))
        self.assertNotIn("<idea>", summary)


if __name__ == "__main__":
    unittest.main()
