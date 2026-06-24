import json
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from evals import BASELINES_DIR
from evals.dataset.baseline_builder import BASELINE_BUILDERS
from evals.dataset.loader import load_golden_ideas
from evals.scorers.composite import score_idea_result


class EvalRegressionTest(unittest.TestCase):
    def test_golden_dataset_has_twelve_ideas(self):
        ideas = load_golden_ideas()
        self.assertEqual(len(ideas), 12)
        self.assertEqual(len({idea.id for idea in ideas}), 12)

    def test_baseline_fixtures_pass_structural_checks(self):
        settings_max_rounds = 2
        for idea_id, builder in BASELINE_BUILDERS.items():
            payload = builder()
            metrics = score_idea_result(
                payload,
                max_debate_rounds=settings_max_rounds,
            )
            self.assertGreaterEqual(
                metrics["reliability"]["judge_parse_success_rate"],
                0.95,
                idea_id,
            )
            self.assertTrue(metrics["reliability"]["panel_complete"], idea_id)
            self.assertTrue(metrics["reliability"]["debate_complete"], idea_id)
            self.assertTrue(metrics["passed"], idea_id)

    def test_committed_baseline_files_match_builders(self):
        for idea_id in BASELINE_BUILDERS:
            path = BASELINES_DIR / f"{idea_id}.json"
            self.assertTrue(path.exists(), f"Missing baseline file: {path}")
            committed = json.loads(path.read_text(encoding="utf-8"))
            built = BASELINE_BUILDERS[idea_id]()
            built.pop("_meta", None)
            self.assertEqual(committed["idea_id"], built["idea_id"])
            self.assertEqual(len(committed["roast_panel"]["verdicts"]), 5)


if __name__ == "__main__":
    unittest.main()
