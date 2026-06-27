from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from idea_context import build_startup_idea_context
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


if __name__ == "__main__":
    unittest.main()
