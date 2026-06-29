from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from debate.router import JUDGE_ORDER, route_next_speaker
import tests  # noqa: F401


class DebateRouterTest(unittest.TestCase):
    def test_routes_next_speaker_in_order(self):
        state = {"current_speaker_idx": 0, "round": 1, "max_rounds": 3}
        self.assertEqual(route_next_speaker(state), JUDGE_ORDER[0])

        state["current_speaker_idx"] = len(JUDGE_ORDER)
        self.assertEqual(route_next_speaker(state), "advance_round")

    def test_routes_to_revote_after_final_round(self):
        state = {
            "current_speaker_idx": len(JUDGE_ORDER),
            "round": 3,
            "max_rounds": 3,
        }
        self.assertEqual(route_next_speaker(state), "revote")


if __name__ == "__main__":
    unittest.main()
