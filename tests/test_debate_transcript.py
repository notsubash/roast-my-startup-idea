from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from debate.nodes import _debate_transcript_for_speaker
import tests  # noqa: F401


class DebateTranscriptContextTest(unittest.TestCase):
    def test_round_one_uses_recent_window(self):
        messages = [{"round": 1, "speaker": "vc", "content": f"msg-{index}"} for index in range(10)]
        transcript = _debate_transcript_for_speaker({"round": 1, "debate_messages": messages})
        self.assertNotIn("msg-0", transcript)
        self.assertIn("msg-9", transcript)

    def test_round_two_uses_full_transcript(self):
        messages = [
            {"round": 1, "speaker": "vc", "content": "round-one"},
            {"round": 2, "speaker": "engineer", "content": "round-two"},
        ]
        transcript = _debate_transcript_for_speaker({"round": 2, "debate_messages": messages})
        self.assertIn("round-one", transcript)
        self.assertIn("round-two", transcript)


if __name__ == "__main__":
    unittest.main()
