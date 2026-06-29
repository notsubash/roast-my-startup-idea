from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from debate.revote import (
    _full_transcript,
    appeal_baseline_panel,
    invoke_judge_on_revote,
    run_revote,
)
from judges.guardrails import validate_revote_verdict
from judges.schemas import RoastPanel, Verdict
from observability.metrics import RunMetricsCollector
import tests  # noqa: F401
from verification.invariants import check_score_change_justification

SAMPLE_FIX = "Interview ten target buyers and document their top workflow pain before building."
DEBATE_EVIDENCE = "The engineer's reliability argument in round 2 lowered my confidence."
ORIGINAL_EVIDENCE = "Three signed LOIs from target buyers would change this verdict."


def _verdict(
    judge: str,
    *,
    score: int = 3,
    evidence: str = ORIGINAL_EVIDENCE,
) -> Verdict:
    label = "FAIL" if score <= 3 else "CONDITIONAL" if score <= 6 else "PASS"
    return Verdict(
        judge=judge,
        verdict=label,
        roast=f"The {judge} judge sees material risk in this pitch's execution path.",
        score=score,
        key_concern=f"The {judge} concern is still unresolved.",
        recommended_fix=SAMPLE_FIX,
        evidence_to_change_verdict=evidence,
    )


def _panel(**scores: int) -> RoastPanel:
    judges = ["vc", "engineer", "pm", "customer", "competitor"]
    defaults = {"vc": 3, "engineer": 4, "pm": 3, "customer": 3, "competitor": 2}
    defaults.update(scores)
    return RoastPanel(verdicts=[_verdict(judge, score=defaults[judge]) for judge in judges])


def _judge_from_messages(messages) -> str:
    parts = []
    for message in messages:
        content = getattr(message, "content", message)
        parts.append(content if isinstance(content, str) else str(content))
    prompt = "\n".join(parts)
    for candidate in ["vc", "engineer", "pm", "customer", "competitor"]:
        if (
            f'"{candidate}"' in prompt
            or f"judge field must be exactly {candidate}" in prompt.lower()
        ):
            return candidate
    return "vc"


class FakeStructuredVerdictModel:
    def __init__(self, responses):
        self.responses = responses
        self.calls = 0

    def invoke(self, messages, **_kwargs):
        self.calls += 1
        judge = _judge_from_messages(messages)
        if isinstance(self.responses, dict):
            queue = self.responses.setdefault(judge, [])
            if not queue:
                raise IndexError(f"No fake revote responses left for judge {judge}")
            return queue.pop(0)
        return self.responses.pop(0)


class FakeRevoteModel:
    def __init__(self, responses):
        self.structured_model = FakeStructuredVerdictModel(responses)

    def with_structured_output(self, schema):
        return self.structured_model


class DebateRevoteTest(unittest.TestCase):
    def test_score_change_requires_updated_evidence(self):
        original = _verdict("vc", score=3)
        revised = _verdict("vc", score=5, evidence=ORIGINAL_EVIDENCE)
        check = check_score_change_justification(original, revised)
        self.assertIsNotNone(check)
        self.assertIn("not updated", check.message)

    def test_score_change_with_debate_evidence_passes(self):
        original = _verdict("vc", score=3)
        revised = _verdict("vc", score=5, evidence=DEBATE_EVIDENCE)
        self.assertIsNone(check_score_change_justification(original, revised))
        validate_revote_verdict(original, revised)

    def test_unchanged_score_skips_justification_check(self):
        original = _verdict("vc", score=3)
        revised = _verdict("vc", score=3)
        self.assertIsNone(check_score_change_justification(original, revised))
        validate_revote_verdict(original, revised)

    def test_run_revote_returns_guardrailed_panel(self):
        debate_messages = [
            {"speaker": "engineer", "round": 1, "content": "Reliability is the real blocker."},
            {"speaker": "vc", "round": 1, "content": "Market size still worries me."},
        ]
        responses = {
            "vc": [
                _verdict(
                    "vc",
                    score=4,
                    evidence="Round 1 engineer reliability argument was persuasive.",
                )
            ],
            "engineer": [_verdict("engineer", score=4)],
            "pm": [_verdict("pm", score=3)],
            "customer": [_verdict("customer", score=3)],
            "competitor": [_verdict("competitor", score=2)],
        }
        model = FakeRevoteModel({judge: list(queue) for judge, queue in responses.items()})
        panel = run_revote(model, "AI privacy summarizer.", _panel(), debate_messages)
        self.assertEqual(len(panel.verdicts), 5)
        self.assertEqual(panel.verdicts[0].score, 4)

    def test_degenerate_revote_panel_retries_then_fails_closed(self):
        debate_messages = [{"speaker": "vc", "round": 1, "content": "Still weak."}]
        judges = ["vc", "engineer", "pm", "customer", "competitor"]
        degenerate_panel = RoastPanel(verdicts=[_verdict(judge, score=3) for judge in judges])
        uniform = {judge: [_verdict(judge, score=3), _verdict(judge, score=3)] for judge in judges}
        model = FakeRevoteModel({judge: list(queue) for judge, queue in uniform.items()})
        emitted: list[dict] = []

        def capture(event: dict) -> None:
            emitted.append(event)

        with patch("debate.revote._emit_revote_custom", side_effect=capture):
            with self.assertRaisesRegex(ValueError, "degenerate"):
                run_revote(model, "AI privacy summarizer.", degenerate_panel, debate_messages)
        self.assertEqual(model.structured_model.calls, 10)
        # ponytail: first attempt streams 1 started + 5 judges; retry is silent.
        self.assertEqual(len(emitted), 6)
        self.assertEqual(emitted[0]["type"], "revote_started")
        self.assertTrue(all(item["type"] == "revote_judge" for item in emitted[1:]))

    def test_invoke_judge_on_revote_rejects_score_change_without_new_evidence(self):
        debate_messages = [{"speaker": "engineer", "round": 1, "content": "Reliability risk."}]
        bad = _verdict("vc", score=5, evidence=ORIGINAL_EVIDENCE)
        model = FakeRevoteModel([bad, bad, bad])
        with self.assertRaises(ValueError):
            invoke_judge_on_revote(
                model,
                "vc",
                "AI privacy summarizer.",
                _panel(),
                debate_messages,
            )
        self.assertEqual(model.structured_model.calls, 3)

    def test_full_transcript_wraps_debate_tag(self):
        transcript = _full_transcript(
            [{"speaker": "vc", "round": 1, "content": "The moat is weak."}]
        )
        self.assertTrue(transcript.startswith("<debate>"))
        self.assertTrue(transcript.endswith("</debate>"))

    def test_appeal_baseline_panel_prefers_revised_verdicts(self):
        initial = _panel()
        revised = _verdict("vc", score=6, evidence="Debate moved this judge.")
        debate_result = {
            "revised_verdicts": [
                revised.model_dump(),
                *[v.model_dump() for v in initial.verdicts[1:]],
            ]
        }
        baseline = appeal_baseline_panel(initial, debate_result)
        self.assertEqual(baseline.verdicts[0].score, 6)
        self.assertIs(appeal_baseline_panel(initial, None), initial)

    def test_revote_records_metrics_under_debate_phase(self):
        debate_messages = [{"speaker": "vc", "round": 1, "content": "Still weak."}]
        responses = {
            "vc": [_verdict("vc", score=4, evidence="Round 1 changed my view.")],
            "engineer": [_verdict("engineer", score=4)],
            "pm": [_verdict("pm", score=3)],
            "customer": [_verdict("customer", score=3)],
            "competitor": [_verdict("competitor", score=2)],
        }
        model = FakeRevoteModel({judge: list(queue) for judge, queue in responses.items()})
        collector = RunMetricsCollector(model_runtime="local")
        run_revote(model, "AI privacy summarizer.", _panel(), debate_messages, metrics=collector)
        snapshot = collector.snapshot(roast_seconds=0.0, debate_seconds=1.0, total_seconds=1.0)
        self.assertEqual(len(snapshot["debate_calls"]), 5)
        self.assertEqual(snapshot["judge_calls"], [])
        self.assertTrue(
            all(call["label"].startswith("revote-") for call in snapshot["debate_calls"])
        )


if __name__ == "__main__":
    unittest.main()
