from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from debate.service import stream_debate
from events import DebateMessagePublished, DebateRoundStarted, DebateTokenDelta
from judges.schemas import RoastPanel, Verdict
import tests  # noqa: F401


class FakeChunk:
    def __init__(self, content: str):
        self.content = content


class StreamingFakeModel:
    """Yields fixed chunk sequences per stream() call; invoke() for moderator."""

    def __init__(self):
        self.stream_calls = 0
        self.chunk_groups = [
            ["The ", "moat ", "is ", "weak."],
            ["Build ", "faster."],
            ["Users ", "won't ", "care."],
            ["Too ", "expensive."],
            ["We ", "can ", "copy ", "this."],
        ]

    def stream(self, messages, **_kwargs):
        chunks = self.chunk_groups[self.stream_calls % len(self.chunk_groups)]
        self.stream_calls += 1
        for chunk in chunks:
            yield FakeChunk(chunk)

    def invoke(self, messages, **_kwargs):
        return FakeChunk("Moderator synthesis.")


class InvokeOnlyModel:
    def __init__(self):
        self.calls = 0

    def invoke(self, messages, **_kwargs):
        self.calls += 1
        return FakeChunk(f"Reply {self.calls}")


def _panel() -> RoastPanel:
    judges = ["vc", "engineer", "pm", "customer", "competitor"]
    return RoastPanel(
        verdicts=[
            Verdict(
                judge=judge,
                verdict="FAIL",
                roast="The go-to-market path is unclear and the wedge is too weak.",
                score=3,
                key_concern="Unclear wedge.",
            )
            for judge in judges
        ]
    )


def _token_deltas_by_turn(events) -> dict[tuple[str, int], list[str]]:
    by_turn: dict[tuple[str, int], list[str]] = {}
    for event in events:
        if isinstance(event, DebateTokenDelta):
            by_turn.setdefault((event.speaker, event.round), []).append(event.delta)
    return by_turn


class TestDebateStreaming(unittest.TestCase):
    def test_token_deltas_concatenate_to_final_message_in_order(self):
        model = StreamingFakeModel()
        events = list(
            stream_debate(
                model,
                "AI tool that summarizes privacy policies.",
                _panel(),
                max_rounds=1,
            )
        )

        token_events = [e for e in events if isinstance(e, DebateTokenDelta)]
        self.assertTrue(token_events, "expected debate_token_delta events")

        by_turn = _token_deltas_by_turn(events)
        messages = [e for e in events if isinstance(e, DebateMessagePublished)]
        for message in messages:
            if message.speaker == "moderator":
                continue
            key = (message.speaker, message.round)
            concatenated = "".join(by_turn.get(key, []))
            self.assertEqual(
                concatenated.strip(),
                message.content,
                f"{message.speaker} r{message.round} deltas must match final message",
            )

        vc_tokens = by_turn[("vc", 1)]
        vc_message = next(m for m in messages if m.speaker == "vc" and m.round == 1)
        self.assertEqual("".join(vc_tokens).strip(), "The moat is weak.")
        self.assertEqual(vc_message.content, "The moat is weak.")

        first_vc_token_idx = events.index(
            next(e for e in token_events if e.speaker == "vc" and e.round == 1)
        )
        vc_message_idx = events.index(vc_message)
        self.assertLess(
            first_vc_token_idx,
            vc_message_idx,
            "token deltas must precede the authoritative message event",
        )

    def test_multi_round_deltas_are_keyed_by_speaker_and_round(self):
        model = StreamingFakeModel()
        events = list(
            stream_debate(
                model,
                "AI tool that summarizes privacy policies.",
                _panel(),
                max_rounds=2,
            )
        )

        by_turn = _token_deltas_by_turn(events)
        messages = [
            e for e in events if isinstance(e, DebateMessagePublished) and e.speaker != "moderator"
        ]

        self.assertIn(("vc", 1), by_turn)
        self.assertIn(("vc", 2), by_turn)
        self.assertEqual(len(by_turn[("vc", 1)]), 4)
        self.assertEqual(len(by_turn[("vc", 2)]), 4)

        round_starts = [e.round for e in events if isinstance(e, DebateRoundStarted)]
        self.assertEqual(round_starts, [1, 2])

        for message in messages:
            key = (message.speaker, message.round)
            self.assertEqual(
                "".join(by_turn[key]).strip(),
                message.content,
            )

    def test_invoke_only_model_emits_single_delta_per_turn(self):
        model = InvokeOnlyModel()
        events = list(
            stream_debate(
                model,
                "AI tool that summarizes privacy policies.",
                _panel(),
                max_rounds=1,
            )
        )

        by_turn = _token_deltas_by_turn(events)
        vc_message = next(
            e for e in events if isinstance(e, DebateMessagePublished) and e.speaker == "vc"
        )
        self.assertEqual(by_turn[("vc", 1)], ["Reply 1"])
        self.assertEqual(vc_message.content, "Reply 1")


if __name__ == "__main__":
    unittest.main()
