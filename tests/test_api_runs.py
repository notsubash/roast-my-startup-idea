import asyncio
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from api.app import create_app
from api.routes.runs import SSE_HEADERS
from api.run_manager import RunManager
from api.schemas import CreateRunRequest
from config import get_settings
from events import (
    DebateCompleted,
    JudgesDispatched,
    JudgeVerdictCompleted,
    PhaseStarted,
    PipelineCompleted,
    RoastPanelCompleted,
)
from judges.schemas import RoastPanel, Verdict
import tests  # noqa: F401

IDEA = "An AI-powered journal for startup founders with daily reflection prompts."


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


def _parse_sse_events(body: str) -> list[dict]:
    events: list[dict] = []
    for chunk in body.split("\n\n"):
        if not chunk.strip() or chunk.lstrip().startswith(":"):
            continue
        event_id = None
        data = None
        for line in chunk.splitlines():
            if line.startswith("id: "):
                event_id = int(line.removeprefix("id: "))
            elif line.startswith("data: "):
                data = json.loads(line.removeprefix("data: "))
        if data is not None:
            if event_id is not None:
                assert data["sequence"] == event_id, (
                    f"SSE id {event_id} != payload sequence {data['sequence']}"
                )
            events.append(data)
    return events


class ApiRunsTest(unittest.TestCase):
    def setUp(self):
        self.manager = RunManager()
        self.client = TestClient(create_app(manager=self.manager))

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_create_run_returns_run_id(self):
        response = self.client.post("/api/runs", json={"idea": IDEA})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "created")
        self.assertTrue(payload["run_id"])

    def test_create_run_rejects_missing_idea(self):
        response = self.client.post("/api/runs", json={})
        self.assertEqual(response.status_code, 422)

    def test_create_run_rejects_deepagents_execution_flow(self):
        response = self.client.post(
            "/api/runs",
            json={"idea": IDEA, "execution_flow": "deepagents"},
        )
        self.assertEqual(response.status_code, 422)

    def test_get_run_status_returns_created_run(self):
        create_response = self.client.post("/api/runs", json={"idea": IDEA})
        run_id = create_response.json()["run_id"]

        status_response = self.client.get(f"/api/runs/{run_id}")
        self.assertEqual(status_response.status_code, 200)
        payload = status_response.json()
        self.assertEqual(payload["run_id"], run_id)
        self.assertEqual(payload["status"], "created")
        self.assertIn("journal", payload["idea_preview"])

    def test_get_unknown_run_returns_404(self):
        response = self.client.get("/api/runs/missing-run")
        self.assertEqual(response.status_code, 404)

    def test_stream_unknown_run_returns_404(self):
        response = self.client.get("/api/runs/missing-run/events")
        self.assertEqual(response.status_code, 404)

    def test_cors_allows_configured_frontend_origin(self):
        response = self.client.options(
            "/api/runs",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"), "http://localhost:3000"
        )

    @patch("api.run_manager.build_research_context_for_run", return_value=None)
    @patch("api.run_manager.build_model_for_run")
    @patch("api.run_manager.stream_pipeline")
    def test_stream_emits_ordered_events_and_run_completed(
        self,
        stream_pipeline_mock,
        build_model_mock,
        _research_mock,
    ):
        build_model_mock.return_value = object()
        stream_pipeline_mock.return_value = iter(
            [
                PhaseStarted(phase="roast"),
                JudgesDispatched(total=5),
                JudgeVerdictCompleted(
                    judge="vc",
                    verdict=_verdict("vc"),
                    completed=1,
                    total=5,
                ),
                RoastPanelCompleted(panel=_panel()),
                PhaseStarted(phase="debate"),
                DebateCompleted(debate_messages=[], final_synthesis="summary"),
                PipelineCompleted(
                    roast_panel=_panel(),
                    debate_result={"debate_messages": [], "final_synthesis": "summary"},
                ),
            ]
        )

        create_response = self.client.post("/api/runs", json={"idea": IDEA})
        run_id = create_response.json()["run_id"]

        stream_response = self.client.get(f"/api/runs/{run_id}/events")
        self.assertEqual(stream_response.status_code, 200)
        for header, value in SSE_HEADERS.items():
            self.assertEqual(stream_response.headers.get(header), value)

        events = _parse_sse_events(stream_response.text)
        self.assertGreaterEqual(len(events), 3)
        self.assertEqual(events[0]["type"], "stream_connected")
        self.assertEqual(events[0]["sequence"], 0)
        self.assertEqual(events[1]["type"], "phase_started")
        self.assertEqual(events[1]["sequence"], 1)
        self.assertEqual(events[-1]["type"], "run_completed")
        self.assertTrue(all(event["run_id"] == run_id for event in events))

        record = self.manager.get(run_id)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.status, "completed")

    @patch("api.run_manager.build_research_context_for_run", return_value=None)
    @patch("api.run_manager.build_model_for_run")
    @patch("api.run_manager.stream_pipeline")
    def test_stream_emits_run_failed_on_pipeline_error(
        self,
        stream_pipeline_mock,
        build_model_mock,
        _research_mock,
    ):
        build_model_mock.return_value = object()
        stream_pipeline_mock.side_effect = RuntimeError("boom")

        create_response = self.client.post("/api/runs", json={"idea": IDEA})
        run_id = create_response.json()["run_id"]

        stream_response = self.client.get(f"/api/runs/{run_id}/events")
        self.assertEqual(stream_response.status_code, 200)

        events = _parse_sse_events(stream_response.text)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["type"], "stream_connected")
        self.assertEqual(events[1]["type"], "run_failed")
        self.assertEqual(events[1]["payload"]["message"], "The roast run failed. Please try again.")
        self.assertTrue(events[1]["payload"]["recoverable"])

        record = self.manager.get(run_id)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.status, "failed")

    @patch("api.run_manager.build_research_context_for_run", return_value=None)
    @patch("api.run_manager.build_model_for_run")
    @patch("api.run_manager.stream_pipeline")
    def test_two_subscribers_see_identical_sequences(
        self,
        stream_pipeline_mock,
        build_model_mock,
        _research_mock,
    ):
        build_model_mock.return_value = object()
        stream_pipeline_mock.return_value = iter(
            [
                PhaseStarted(phase="roast"),
                RoastPanelCompleted(panel=_panel()),
                PhaseStarted(phase="debate"),
                DebateCompleted(debate_messages=[], final_synthesis="summary"),
                PipelineCompleted(
                    roast_panel=_panel(),
                    debate_result={"debate_messages": [], "final_synthesis": "summary"},
                ),
            ]
        )

        create_response = self.client.post("/api/runs", json={"idea": IDEA})
        run_id = create_response.json()["run_id"]

        # The engine runs once into the buffer; a second viewer (e.g. a reopened
        # tab) replays the same buffer with no 409 and no data loss.
        first = self.client.get(f"/api/runs/{run_id}/events")
        second = self.client.get(f"/api/runs/{run_id}/events")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)

        first_events = _parse_sse_events(first.text)
        second_events = _parse_sse_events(second.text)
        self.assertEqual(
            [e["sequence"] for e in first_events],
            [e["sequence"] for e in second_events],
        )
        self.assertEqual(
            [e["type"] for e in first_events],
            [e["type"] for e in second_events],
        )
        self.assertEqual(first_events[-1]["type"], "run_completed")

    @patch("api.run_manager.build_research_context_for_run", return_value=None)
    @patch("api.run_manager.build_model_for_run")
    @patch("api.run_manager.stream_pipeline")
    def test_reconnect_with_last_event_id_resumes_from_offset(
        self,
        stream_pipeline_mock,
        build_model_mock,
        _research_mock,
    ):
        build_model_mock.return_value = object()
        stream_pipeline_mock.return_value = iter(
            [
                PhaseStarted(phase="roast"),
                JudgesDispatched(total=5),
                JudgeVerdictCompleted(
                    judge="vc",
                    verdict=_verdict("vc"),
                    completed=1,
                    total=5,
                ),
                RoastPanelCompleted(panel=_panel()),
                PhaseStarted(phase="debate"),
                DebateCompleted(debate_messages=[], final_synthesis="summary"),
                PipelineCompleted(
                    roast_panel=_panel(),
                    debate_result={"debate_messages": [], "final_synthesis": "summary"},
                ),
            ]
        )

        create_response = self.client.post("/api/runs", json={"idea": IDEA})
        run_id = create_response.json()["run_id"]

        full_response = self.client.get(f"/api/runs/{run_id}/events")
        all_events = _parse_sse_events(full_response.text)
        self.assertGreater(len(all_events), 6)

        resume_response = self.client.get(
            f"/api/runs/{run_id}/events",
            headers={"Last-Event-ID": "5"},
        )
        self.assertEqual(resume_response.status_code, 200)
        resumed = _parse_sse_events(resume_response.text)

        self.assertEqual(resumed[0]["sequence"], 6)
        self.assertEqual(
            [event["sequence"] for event in resumed],
            [event["sequence"] for event in all_events if event["sequence"] > 5],
        )
        self.assertEqual(
            [event["type"] for event in resumed],
            [event["type"] for event in all_events if event["sequence"] > 5],
        )

    @patch("api.run_manager.build_research_context_for_run", return_value=None)
    @patch("api.run_manager.build_model_for_run")
    @patch("api.run_manager.stream_pipeline")
    def test_invalid_last_event_id_replays_from_start(
        self,
        stream_pipeline_mock,
        build_model_mock,
        _research_mock,
    ):
        build_model_mock.return_value = object()
        stream_pipeline_mock.return_value = iter(
            [
                PhaseStarted(phase="roast"),
                PipelineCompleted(
                    roast_panel=_panel(),
                    debate_result={"debate_messages": [], "final_synthesis": "summary"},
                ),
            ]
        )

        create_response = self.client.post("/api/runs", json={"idea": IDEA})
        run_id = create_response.json()["run_id"]

        full_response = self.client.get(f"/api/runs/{run_id}/events")
        all_events = _parse_sse_events(full_response.text)

        for bad_header in ("not-a-number", "-1"):
            with self.subTest(Last_Event_ID=bad_header):
                replay_response = self.client.get(
                    f"/api/runs/{run_id}/events",
                    headers={"Last-Event-ID": bad_header},
                )
                replayed = _parse_sse_events(replay_response.text)
                self.assertEqual(
                    [event["sequence"] for event in replayed],
                    [event["sequence"] for event in all_events],
                )

    @patch("api.run_manager.build_research_context_for_run", return_value=None)
    @patch("api.run_manager.build_model_for_run", return_value=object())
    @patch("api.run_manager.stream_pipeline")
    def test_run_completes_without_any_subscriber(
        self,
        stream_pipeline_mock,
        _build_model_mock,
        _research_mock,
    ):
        stream_pipeline_mock.return_value = iter(
            [
                PhaseStarted(phase="roast"),
                PipelineCompleted(
                    roast_panel=_panel(),
                    debate_result={"debate_messages": [], "final_synthesis": "summary"},
                ),
            ]
        )

        async def scenario():
            manager = RunManager()
            record = manager.create(
                CreateRunRequest.model_validate({"idea": IDEA, "model_runtime": "local"})
            )
            manager.ensure_started(record.run_id, get_settings())
            await manager._runs[record.run_id].task
            return manager, record.run_id

        manager, run_id = asyncio.run(scenario())

        record = manager.get(run_id)
        assert record is not None
        self.assertEqual(record.status, "completed")
        types = [envelope.type for envelope in manager._runs[run_id].events]
        self.assertEqual(types[0], "stream_connected")
        self.assertIn("run_completed", types)

    @patch("api.run_manager.build_model_for_run")
    @patch("api.run_manager.stream_pipeline")
    def test_stream_emits_run_failed_when_model_setup_fails(
        self,
        stream_pipeline_mock,
        build_model_mock,
    ):
        build_model_mock.side_effect = ValueError(
            "DEEPSEEK_API_KEY is required for DeepSeek runtime."
        )

        create_response = self.client.post("/api/runs", json={"idea": IDEA})
        run_id = create_response.json()["run_id"]

        stream_response = self.client.get(f"/api/runs/{run_id}/events")
        self.assertEqual(stream_response.status_code, 200)

        events = _parse_sse_events(stream_response.text)
        self.assertEqual(events[-1]["type"], "run_failed")
        stream_pipeline_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
