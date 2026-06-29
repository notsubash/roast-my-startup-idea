from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from debate.router import JUDGE_ORDER, make_route_next_speaker, route_next_speaker
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

    def test_routes_to_moderator_when_revote_disabled(self):
        state = {
            "current_speaker_idx": len(JUDGE_ORDER),
            "round": 3,
            "max_rounds": 3,
        }
        router = make_route_next_speaker(enable_revote=False)
        self.assertEqual(router(state), "moderator")


if __name__ == "__main__":
    unittest.main()
