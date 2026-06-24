from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from evals.workload import estimate_llm_calls
import tests  # noqa: F401


class EvalWorkloadTest(unittest.TestCase):
    def test_estimate_llm_calls_default_three_idea_smoke(self):
        stats = estimate_llm_calls(
            num_ideas=3,
            max_debate_rounds=3,
            include_appeals=True,
        )
        self.assertEqual(stats["llm_calls_per_idea"], 33)
        self.assertEqual(stats["llm_calls_total"], 99)
        self.assertEqual(stats["sequential_steps_per_idea"], 18)

    def test_estimate_without_appeals(self):
        stats = estimate_llm_calls(
            num_ideas=12,
            max_debate_rounds=3,
            include_appeals=False,
        )
        self.assertEqual(stats["llm_calls_per_idea"], 21)
        self.assertEqual(stats["llm_calls_total"], 252)


if __name__ == "__main__":
    unittest.main()
