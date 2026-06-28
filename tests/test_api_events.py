from datetime import UTC, datetime
from pathlib import Path
import sys
import unittest

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from api.deps import build_idea_preview, build_startup_idea_context
from api.events import (
    pipeline_event_payload,
    pipeline_event_type,
    run_failed_envelope,
    stream_connected_envelope,
    to_api_envelope,
)
from api.schemas import ApiEventEnvelope, CreateRunRequest, RunCreatedResponse
from events import (
    DebateCompleted,
    DebateMessagePublished,
    DebateRoundStarted,
    DebateSpeakerThinking,
    DebateSynthesisPublished,
    DebateTokenDelta,
    JudgesDispatched,
    JudgeVerdictCompleted,
    PhaseStarted,
    PipelineCompleted,
    RoastPanelCompleted,
    RunMetrics,
)
from judges.schemas import RoastPanel, Verdict
import tests  # noqa: F401


def _verdict(judge: str) -> Verdict:
    return Verdict(
        judge=judge,
        verdict="FAIL",
        roast="The go-to-market path is unclear and the wedge is too weak to win attention.",
        score=3,
        key_concern="Weak distribution.",
    )


def _panel() -> RoastPanel:
    return RoastPanel(
        verdicts=[
            _verdict("vc"),
            _verdict("engineer"),
            _verdict("pm"),
            _verdict("customer"),
            _verdict("competitor"),
        ]
    )


class ApiSchemaTest(unittest.TestCase):
    def test_create_run_request_defaults_to_deepseek_deterministic(self):
        request = CreateRunRequest.model_validate(
            {"idea": "An AI journal for startup founders with daily reflection prompts."}
        )
        self.assertEqual(request.model_runtime, "deepseek")
        self.assertEqual(request.execution_flow, "deterministic")
        self.assertEqual(request.max_debate_rounds, 3)
        self.assertFalse(request.enable_web_search)

    def test_create_run_request_requires_idea(self):
        with self.assertRaises(ValidationError):
            CreateRunRequest.model_validate({"idea": "short"})

    def test_create_run_request_rejects_deepagents_execution_flow(self):
        with self.assertRaises(ValidationError):
            CreateRunRequest.model_validate(
                {
                    "idea": "An AI journal for startup founders with daily reflection prompts.",
                    "execution_flow": "deepagents",
                }
            )

    def test_create_run_request_accepts_optional_metadata(self):
        request = CreateRunRequest.model_validate(
            {
                "idea": "An AI journal for startup founders with daily reflection prompts.",
                "target_customer": "Solo founders",
                "competitors": ["Notion", "Reflect"],
            }
        )
        self.assertEqual(request.target_customer, "Solo founders")
        self.assertEqual(request.competitors, ["Notion", "Reflect"])

    def test_run_created_response_shape(self):
        response = RunCreatedResponse(run_id="abc-123")
        self.assertEqual(response.status, "created")
        self.assertEqual(response.model_dump(), {"run_id": "abc-123", "status": "created"})

    def test_api_event_envelope_fields(self):
        created_at = datetime(2026, 6, 24, tzinfo=UTC)
        envelope = ApiEventEnvelope(
            type="phase_started",
            run_id="run-1",
            sequence=0,
            payload={"phase": "roast"},
            created_at=created_at,
        )
        data = envelope.model_dump(mode="json")
        self.assertEqual(data["type"], "phase_started")
        self.assertEqual(data["run_id"], "run-1")
        self.assertEqual(data["sequence"], 0)
        self.assertEqual(data["payload"], {"phase": "roast"})
        self.assertEqual(data["created_at"], "2026-06-24T00:00:00Z")


class ApiEventSerializationTest(unittest.TestCase):
    def test_phase_started_event_type(self):
        self.assertEqual(pipeline_event_type(PhaseStarted(phase="roast")), "phase_started")

    def test_pipeline_completed_maps_to_run_completed(self):
        self.assertEqual(
            pipeline_event_type(
                PipelineCompleted(
                    roast_panel=_panel(),
                    debate_result={"debate_messages": [], "final_synthesis": "summary"},
                )
            ),
            "run_completed",
        )

    def test_judge_verdict_completed_payload_shape(self):
        payload = pipeline_event_payload(
            JudgeVerdictCompleted(
                judge="vc",
                verdict=_verdict("vc"),
                completed=1,
                total=5,
            )
        )
        self.assertEqual(payload["judge"], "vc")
        self.assertEqual(payload["completed"], 1)
        self.assertEqual(payload["total"], 5)
        self.assertEqual(payload["verdict"]["judge"], "vc")
        self.assertEqual(payload["verdict"]["score"], 3)

    def test_debate_message_published_payload_shape(self):
        payload = pipeline_event_payload(
            DebateMessagePublished(
                speaker="vc",
                round=1,
                content="This idea still lacks a durable moat.",
            )
        )
        self.assertEqual(
            payload,
            {
                "speaker": "vc",
                "round": 1,
                "content": "This idea still lacks a durable moat.",
            },
        )

    def test_roast_panel_completed_payload_shape(self):
        payload = pipeline_event_payload(RoastPanelCompleted(panel=_panel()))
        self.assertEqual(len(payload["panel"]["verdicts"]), 5)

    def test_debate_round_started_payload_shape(self):
        payload = pipeline_event_payload(DebateRoundStarted(round=2))
        self.assertEqual(payload, {"round": 2})

    def test_debate_speaker_thinking_payload_shape(self):
        payload = pipeline_event_payload(DebateSpeakerThinking(judge="pm", round=1))
        self.assertEqual(payload, {"judge": "pm", "round": 1})

    def test_debate_token_delta_payload_shape(self):
        payload = pipeline_event_payload(DebateTokenDelta(speaker="vc", round=1, delta="The "))
        self.assertEqual(
            payload,
            {"speaker": "vc", "round": 1, "delta": "The "},
        )

    def test_debate_token_delta_event_type(self):
        self.assertEqual(
            pipeline_event_type(DebateTokenDelta(speaker="vc", round=1, delta="Hi")),
            "debate_token_delta",
        )

    def test_debate_synthesis_published_payload_shape(self):
        payload = pipeline_event_payload(DebateSynthesisPublished(content="Final summary."))
        self.assertEqual(payload, {"content": "Final summary."})

    def test_debate_completed_payload_shape(self):
        payload = pipeline_event_payload(
            DebateCompleted(debate_messages=[{"speaker": "vc"}], final_synthesis="summary")
        )
        self.assertEqual(payload["final_synthesis"], "summary")
        self.assertEqual(len(payload["debate_messages"]), 1)

    def test_run_failed_envelope_shape(self):
        envelope = run_failed_envelope(
            run_id="run-1",
            sequence=3,
            message="Something went wrong.",
        )
        self.assertEqual(envelope.type, "run_failed")
        self.assertEqual(envelope.payload["message"], "Something went wrong.")
        self.assertTrue(envelope.payload["recoverable"])

    def test_stream_connected_envelope_shape(self):
        envelope = stream_connected_envelope(run_id="run-1")
        self.assertEqual(envelope.type, "stream_connected")
        self.assertEqual(envelope.payload, {"status": "connected"})

    def test_run_metrics_payload_shape(self):
        payload = pipeline_event_payload(
            RunMetrics(
                roast_seconds=4.2,
                debate_seconds=11.8,
                total_seconds=16.0,
                input_tokens=2500,
                output_tokens=600,
                total_tokens=3100,
                estimated_cost_usd=0.004,
                model_runtime="deepseek",
                judge_calls=[
                    {"label": "vc", "phase": "roast", "seconds": 0.8, "total_tokens": 120}
                ],
                debate_calls=[
                    {"label": "vc", "phase": "debate", "seconds": 1.2, "total_tokens": 90}
                ],
            )
        )
        self.assertEqual(payload["roast_seconds"], 4.2)
        self.assertEqual(payload["debate_seconds"], 11.8)
        self.assertEqual(payload["total_tokens"], 3100)
        self.assertEqual(payload["estimated_cost_usd"], 0.004)
        self.assertEqual(payload["model_runtime"], "deepseek")

    def test_run_metrics_event_type(self):
        self.assertEqual(
            pipeline_event_type(
                RunMetrics(
                    roast_seconds=1.0,
                    debate_seconds=2.0,
                    total_seconds=3.0,
                    input_tokens=10,
                    output_tokens=5,
                    total_tokens=15,
                    estimated_cost_usd=0.0,
                    model_runtime="local",
                    judge_calls=[],
                    debate_calls=[],
                )
            ),
            "run_metrics",
        )

    def test_to_api_envelope_assigns_sequence_and_run_id(self):
        created_at = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)
        envelope = to_api_envelope(
            JudgesDispatched(total=5),
            run_id="run-42",
            sequence=2,
            created_at=created_at,
        )
        self.assertEqual(envelope.type, "judges_dispatched")
        self.assertEqual(envelope.run_id, "run-42")
        self.assertEqual(envelope.sequence, 2)
        self.assertEqual(envelope.payload, {"total": 5})


class ApiDepsTest(unittest.TestCase):
    def test_build_startup_idea_context_includes_metadata(self):
        request = CreateRunRequest.model_validate(
            {
                "idea": "An AI journal for startup founders with daily reflection prompts.",
                "target_customer": "Solo founders",
                "competitors": ["Notion"],
            }
        )
        context = build_startup_idea_context(request)
        self.assertIn("Target customer: Solo founders", context)
        self.assertIn("Competitors: Notion", context)

    def test_build_idea_preview_truncates_long_text(self):
        preview = build_idea_preview("x" * 200, max_length=50)
        self.assertLessEqual(len(preview), 50)
        self.assertTrue(preview.endswith("..."))


if __name__ == "__main__":
    unittest.main()
