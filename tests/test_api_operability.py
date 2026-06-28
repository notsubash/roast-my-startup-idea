import asyncio
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from api.app import create_app
from api.rate_limit import TokenBucketLimiter
from api.run_manager import RunManager
from api.schemas import CreateRunRequest
from config import Settings
from events import PhaseStarted, RoastPanelCompleted
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


class ApiOperabilityTest(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "runs.db"
        self.manager = RunManager(db_path=self.db_path, recover_on_init=False)
        self.client = TestClient(create_app(manager=self.manager))

    def tearDown(self):
        self.manager.close()
        self._tmpdir.cleanup()

    @patch("api.run_manager.build_research_context_for_run", return_value=None)
    @patch("api.run_manager.build_model_for_run")
    @patch("api.run_manager.stream_pipeline")
    def test_cancel_running_run_emits_run_cancelled(
        self,
        stream_pipeline_mock,
        build_model_mock,
        _research_mock,
    ):
        gate = threading.Event()
        build_model_mock.return_value = object()

        def blocked_pipeline(*_args, **_kwargs):
            yield PhaseStarted(phase="roast")
            gate.wait()
            yield RoastPanelCompleted(panel=_panel())

        stream_pipeline_mock.side_effect = blocked_pipeline

        create_response = self.client.post("/api/runs", json={"idea": IDEA})
        run_id = create_response.json()["run_id"]

        def consume_events():
            self.client.get(f"/api/runs/{run_id}/events")

        consumer = threading.Thread(target=consume_events, daemon=True)
        consumer.start()
        time.sleep(0.1)

        cancel_response = self.client.post(f"/api/runs/{run_id}/cancel")
        self.assertEqual(cancel_response.status_code, 200)
        self.assertEqual(cancel_response.json()["status"], "running")

        gate.set()
        consumer.join(timeout=5.0)
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            record = self.manager.get(run_id)
            assert record is not None
            if record.status == "cancelled":
                break
            time.sleep(0.02)
        else:
            self.fail("Run did not reach cancelled status")

        events = self.manager.list_events(run_id)
        self.assertEqual(events[-1].type, "run_cancelled")

    @patch("api.run_manager.build_research_context_for_run", return_value=None)
    @patch("api.run_manager.build_model_for_run")
    @patch("api.run_manager.stream_pipeline")
    def test_cancel_created_run_before_start(
        self,
        stream_pipeline_mock,
        build_model_mock,
        _research_mock,
    ):
        build_model_mock.return_value = object()
        create_response = self.client.post("/api/runs", json={"idea": IDEA})
        run_id = create_response.json()["run_id"]

        cancel_response = self.client.post(f"/api/runs/{run_id}/cancel")
        self.assertEqual(cancel_response.status_code, 200)
        self.assertEqual(cancel_response.json()["status"], "cancelled")
        stream_pipeline_mock.assert_not_called()
        events = self.manager.list_events(run_id)
        self.assertEqual(events[0].type, "stream_connected")
        self.assertEqual(events[-1].type, "run_cancelled")

    def test_cancel_unknown_run_returns_404(self):
        response = self.client.post("/api/runs/missing-run/cancel")
        self.assertEqual(response.status_code, 404)

    @patch("api.run_manager.build_research_context_for_run", return_value=None)
    @patch("api.run_manager.build_model_for_run")
    @patch("api.run_manager.stream_pipeline")
    def test_cancel_terminal_run_returns_409(
        self,
        stream_pipeline_mock,
        build_model_mock,
        _research_mock,
    ):
        from events import PipelineCompleted

        build_model_mock.return_value = object()
        stream_pipeline_mock.return_value = iter(
            [
                PhaseStarted(phase="roast"),
                RoastPanelCompleted(panel=_panel()),
                PipelineCompleted(
                    roast_panel=_panel(),
                    debate_result={"debate_messages": [], "final_synthesis": "done"},
                ),
            ]
        )
        create_response = self.client.post("/api/runs", json={"idea": IDEA})
        run_id = create_response.json()["run_id"]
        self.client.get(f"/api/runs/{run_id}/events")

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            record = self.manager.get(run_id)
            assert record is not None
            if record.status == "completed":
                break
            time.sleep(0.02)

        response = self.client.post(f"/api/runs/{run_id}/cancel")
        self.assertEqual(response.status_code, 409)

    @patch("api.run_manager.build_research_context_for_run", return_value=None)
    @patch("api.run_manager.build_model_for_run")
    @patch("api.run_manager.stream_pipeline")
    def test_double_cancel_on_running_run_is_idempotent(
        self,
        stream_pipeline_mock,
        build_model_mock,
        _research_mock,
    ):
        gate = threading.Event()
        build_model_mock.return_value = object()

        def blocked_pipeline(*_args, **_kwargs):
            yield PhaseStarted(phase="roast")
            gate.wait()
            yield RoastPanelCompleted(panel=_panel())

        stream_pipeline_mock.side_effect = blocked_pipeline

        create_response = self.client.post("/api/runs", json={"idea": IDEA})
        run_id = create_response.json()["run_id"]

        def consume_events():
            self.client.get(f"/api/runs/{run_id}/events")

        consumer = threading.Thread(target=consume_events, daemon=True)
        consumer.start()
        time.sleep(0.1)

        first = self.client.post(f"/api/runs/{run_id}/cancel")
        second = self.client.post(f"/api/runs/{run_id}/cancel")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["status"], "running")
        self.assertEqual(second.json()["status"], "running")

        gate.set()
        consumer.join(timeout=5.0)

    @patch("api.run_manager.build_research_context_for_run", return_value=None)
    @patch("api.run_manager.build_model_for_run")
    @patch("api.run_manager.stream_pipeline")
    def test_completed_run_has_no_run_cancelled_event(
        self,
        stream_pipeline_mock,
        build_model_mock,
        _research_mock,
    ):
        from events import PipelineCompleted

        build_model_mock.return_value = object()
        stream_pipeline_mock.return_value = iter(
            [
                PhaseStarted(phase="roast"),
                RoastPanelCompleted(panel=_panel()),
                PipelineCompleted(
                    roast_panel=_panel(),
                    debate_result={"debate_messages": [], "final_synthesis": "done"},
                ),
            ]
        )

        create_response = self.client.post("/api/runs", json={"idea": IDEA})
        run_id = create_response.json()["run_id"]
        self.client.get(f"/api/runs/{run_id}/events")

        event_types = [envelope.type for envelope in self.manager.list_events(run_id)]
        self.assertEqual(event_types[-1], "run_completed")
        self.assertNotIn("run_cancelled", event_types)

    def test_rate_limit_returns_429(self):
        limited = Settings(
            local_model="ollama:test",
            deepseek_model="test",
            deepseek_base_url="https://example.com",
            embedding_model="ollama:test",
            embedding_dimension=768,
            enable_semantic_memory=False,
            max_debate_rounds=3,
            enable_web_search=False,
            web_search_max_results=3,
            sse_heartbeat_seconds=15,
            stale_run_minutes=30,
            runs_db_path=self.db_path,
            rate_limit_enabled=True,
            rate_limit_requests=1,
            rate_limit_burst=1,
            rate_limit_window_seconds=60,
            max_run_seconds=600,
        )
        with patch("api.app.get_settings", return_value=limited):
            client = TestClient(create_app(manager=self.manager))

        first = client.post("/api/runs", json={"idea": IDEA})
        second = client.post("/api/runs", json={"idea": IDEA})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)

    @patch("api.run_manager.build_research_context_for_run", return_value=None)
    @patch("api.run_manager.build_model_for_run")
    @patch("api.run_manager.stream_pipeline")
    @patch("api.run_manager.run_appeal")
    def test_appeal_rate_limit_returns_429(
        self,
        run_appeal_mock,
        stream_pipeline_mock,
        build_model_mock,
        _research_mock,
    ):
        from appeal.service import AppealResult
        from events import PipelineCompleted
        from tests.test_api_runs import _fetch_sse_events

        build_model_mock.return_value = object()
        completed_events = [
            PhaseStarted(phase="roast"),
            RoastPanelCompleted(panel=_panel()),
            PipelineCompleted(
                roast_panel=_panel(),
                debate_result={"debate_messages": [], "final_synthesis": "summary"},
            ),
        ]
        stream_pipeline_mock.return_value = iter(completed_events)
        run_appeal_mock.return_value = AppealResult(
            revised_panel=_panel(),
            revised_synthesis="Revised synthesis.",
        )

        limited = Settings(
            local_model="ollama:test",
            deepseek_model="test",
            deepseek_base_url="https://example.com",
            embedding_model="ollama:test",
            embedding_dimension=768,
            enable_semantic_memory=False,
            max_debate_rounds=3,
            enable_web_search=False,
            web_search_max_results=3,
            sse_heartbeat_seconds=15,
            stale_run_minutes=30,
            runs_db_path=self.db_path,
            rate_limit_enabled=True,
            rate_limit_requests=30,
            rate_limit_burst=10,
            rate_limit_window_seconds=60,
            rate_limit_appeal_requests=1,
            rate_limit_appeal_burst=1,
            rate_limit_appeal_window_seconds=60,
            max_run_seconds=600,
        )
        with patch("api.app.get_settings", return_value=limited):
            client = TestClient(create_app(manager=self.manager))

        body = {
            "appeal_text": (
                "We completed two university validation studies and signed LOIs "
                "with two NCAA programs."
            ),
        }

        run_ids: list[str] = []
        for _ in range(2):
            create_response = client.post("/api/runs", json={"idea": IDEA})
            run_id = create_response.json()["run_id"]
            run_ids.append(run_id)
            _fetch_sse_events(client, run_id, manager=self.manager)

        first = client.post(f"/api/runs/{run_ids[0]}/appeal", json=body)
        second = client.post(f"/api/runs/{run_ids[1]}/appeal", json=body)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)

    def test_token_bucket_allows_burst_then_blocks(self):
        limiter = TokenBucketLimiter(rate=0.1, capacity=2.0)
        self.assertTrue(limiter.allow("127.0.0.1"))
        self.assertTrue(limiter.allow("127.0.0.1"))
        self.assertFalse(limiter.allow("127.0.0.1"))

    @patch("api.run_manager.build_research_context_for_run", return_value=None)
    @patch("api.run_manager.build_model_for_run")
    @patch("api.run_manager.stream_pipeline")
    def test_wall_clock_budget_fails_run(
        self,
        stream_pipeline_mock,
        build_model_mock,
        _research_mock,
    ):
        build_model_mock.return_value = object()

        def budget_pipeline(*_args, **kwargs):
            abort_check = kwargs.get("abort_check")
            yield PhaseStarted(phase="roast")
            time.sleep(1.1)
            if abort_check:
                reason = abort_check()
                if reason:
                    from run_control import RunAbort

                    raise RunAbort(reason)
            yield RoastPanelCompleted(panel=_panel())

        stream_pipeline_mock.side_effect = budget_pipeline

        settings = Settings(
            local_model="ollama:test",
            deepseek_model="test",
            deepseek_base_url="https://example.com",
            embedding_model="ollama:test",
            embedding_dimension=768,
            enable_semantic_memory=False,
            max_debate_rounds=3,
            enable_web_search=False,
            web_search_max_results=3,
            sse_heartbeat_seconds=15,
            stale_run_minutes=30,
            runs_db_path=self.db_path,
            max_run_seconds=1,
        )

        async def run_budget_scenario():
            record = self.manager.create(
                CreateRunRequest.model_validate({"idea": IDEA, "model_runtime": "local"})
            )
            self.manager.ensure_started(record.run_id, settings)
            task = self.manager._runs[record.run_id].task
            assert task is not None
            await task
            return record.run_id

        run_id = asyncio.run(run_budget_scenario())

        record = self.manager.get(run_id)
        assert record is not None
        self.assertEqual(record.status, "failed")
        events = self.manager.list_events(run_id)
        self.assertEqual(events[-1].type, "run_failed")
        self.assertIn("budget", events[-1].payload["message"].lower())


if __name__ == "__main__":
    unittest.main()
