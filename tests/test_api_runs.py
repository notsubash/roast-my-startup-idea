import asyncio
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sys
import tempfile
import time
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
    DebateMessagePublished,
    DebateTokenDelta,
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


async def _fetch_sse_events_async(
    app,
    run_id: str,
    *,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], list[dict]]:
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        async with client.stream(
            "GET",
            f"/api/runs/{run_id}/events",
            headers=headers or {},
        ) as response:
            status_code = response.status_code
            response_headers = dict(response.headers)
            body = "".join([chunk async for chunk in response.aiter_text()])
    return status_code, response_headers, _parse_sse_events(body)


def _parse_last_event_id(headers: dict[str, str] | None) -> int:
    if not headers:
        return -1
    raw = headers.get("Last-Event-ID")
    if not raw:
        return -1
    try:
        value = int(raw.strip())
    except ValueError:
        return -1
    if value < 0:
        return -1
    return value


def _wait_for_run_terminal(manager: RunManager, run_id: str, *, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        record = manager.get(run_id)
        if record is None:
            time.sleep(0.005)
            continue
        if record.status in ("completed", "failed"):
            state = manager._runs.get(run_id)
            if state is not None and state.task is not None and not state.task.done():
                time.sleep(0.005)
                continue
            return
        time.sleep(0.005)
    raise TimeoutError(f"Run {run_id} did not reach a terminal state within {timeout}s")


def _events_from_store(manager: RunManager, run_id: str, *, after_sequence: int = -1) -> list[dict]:
    return [
        envelope.model_dump(mode="json")
        for envelope in manager.list_events(run_id)
        if envelope.sequence > after_sequence
    ]


def _fetch_sse_events(
    client: TestClient,
    run_id: str,
    *,
    manager: RunManager | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], list[dict]]:
    status_code, response_headers, events = asyncio.run(
        _fetch_sse_events_async(client.app, run_id, headers=headers)
    )
    if manager is None:
        return status_code, response_headers, events

    # ponytail: Py 3.13 CI can close SSE before the loop drains live events; the
    # durable SQLite log is the source of truth for Phase 3 assertions.
    _wait_for_run_terminal(manager, run_id)
    store_events = _events_from_store(manager, run_id, after_sequence=_parse_last_event_id(headers))
    if len(store_events) > len(events):
        events = store_events
    return status_code, response_headers, events


class ApiRunsTest(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "runs.db"
        self.manager = RunManager(db_path=self.db_path, recover_on_init=False)
        self.client = TestClient(create_app(manager=self.manager))

    def tearDown(self):
        self.manager.close()
        self._tmpdir.cleanup()

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

        status_code, headers, events = _fetch_sse_events(self.client, run_id, manager=self.manager)
        self.assertEqual(status_code, 200)
        lower_headers = {name.lower(): value for name, value in headers.items()}
        for header, value in SSE_HEADERS.items():
            self.assertEqual(lower_headers.get(header.lower()), value)
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
    def test_stream_emits_debate_token_deltas_before_messages(
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
                DebateTokenDelta(speaker="vc", round=1, delta="The "),
                DebateTokenDelta(speaker="vc", round=1, delta="moat."),
                DebateMessagePublished(speaker="vc", round=1, content="The moat."),
                DebateCompleted(debate_messages=[], final_synthesis="summary"),
                PipelineCompleted(
                    roast_panel=_panel(),
                    debate_result={"debate_messages": [], "final_synthesis": "summary"},
                ),
            ]
        )

        create_response = self.client.post("/api/runs", json={"idea": IDEA})
        run_id = create_response.json()["run_id"]

        _status_code, _headers, events = _fetch_sse_events(
            self.client, run_id, manager=self.manager
        )
        event_types = [event["type"] for event in events]
        first_token_idx = event_types.index("debate_token_delta")
        message_idx = event_types.index("debate_message_published")
        self.assertLess(first_token_idx, message_idx)

        token_events = [event for event in events if event["type"] == "debate_token_delta"]
        self.assertEqual(len(token_events), 2)
        self.assertEqual(token_events[0]["payload"]["delta"], "The ")
        self.assertEqual(
            token_events[1]["payload"],
            {"speaker": "vc", "round": 1, "delta": "moat."},
        )

        message_event = next(
            event for event in events if event["type"] == "debate_message_published"
        )
        self.assertEqual(message_event["payload"]["content"], "The moat.")

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

        status_code, _, events = _fetch_sse_events(self.client, run_id, manager=self.manager)
        self.assertEqual(status_code, 200)
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
        _, _, first_events = _fetch_sse_events(self.client, run_id, manager=self.manager)
        _, _, second_events = _fetch_sse_events(self.client, run_id, manager=self.manager)
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

        _, _, all_events = _fetch_sse_events(self.client, run_id, manager=self.manager)
        self.assertGreater(len(all_events), 6)

        _, _, resumed = _fetch_sse_events(
            self.client,
            run_id,
            manager=self.manager,
            headers={"Last-Event-ID": "5"},
        )

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

        _, _, all_events = _fetch_sse_events(self.client, run_id, manager=self.manager)

        for bad_header in ("not-a-number", "-1"):
            with self.subTest(Last_Event_ID=bad_header):
                _, _, replayed = _fetch_sse_events(
                    self.client,
                    run_id,
                    manager=self.manager,
                    headers={"Last-Event-ID": bad_header},
                )
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
            manager = RunManager(db_path=self.db_path, recover_on_init=False)
            record = manager.create(
                CreateRunRequest.model_validate({"idea": IDEA, "model_runtime": "local"})
            )
            manager.ensure_started(record.run_id, get_settings())
            await manager._runs[record.run_id].task
            return manager, record.run_id

        manager, run_id = asyncio.run(scenario())

        try:
            record = manager.get(run_id)
            assert record is not None
            self.assertEqual(record.status, "completed")
            types = [envelope.type for envelope in manager.list_events(run_id)]
            self.assertEqual(types[0], "stream_connected")
            self.assertIn("run_completed", types)
        finally:
            manager.close()

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

        status_code, _, events = _fetch_sse_events(self.client, run_id, manager=self.manager)
        self.assertEqual(status_code, 200)
        self.assertEqual(events[-1]["type"], "run_failed")
        stream_pipeline_mock.assert_not_called()

    @patch("api.run_manager.build_research_context_for_run", return_value=None)
    @patch("api.run_manager.build_model_for_run")
    @patch("api.run_manager.stream_pipeline")
    def test_get_run_status_survives_manager_restart(
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
        _, _, events = _fetch_sse_events(self.client, run_id, manager=self.manager)
        self.assertEqual(events[-1]["type"], "run_completed")

        restarted = RunManager(db_path=self.db_path, recover_on_init=False)
        try:
            restarted_client = TestClient(create_app(manager=restarted))
            status_response = restarted_client.get(f"/api/runs/{run_id}")
            self.assertEqual(status_response.status_code, 200)
            self.assertEqual(status_response.json()["status"], "completed")
        finally:
            restarted.close()

    @patch("api.run_manager.build_research_context_for_run", return_value=None)
    @patch("api.run_manager.build_model_for_run")
    @patch("api.run_manager.stream_pipeline")
    def test_reconnect_after_restart_replays_persisted_events(
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
                RoastPanelCompleted(panel=_panel()),
                PipelineCompleted(
                    roast_panel=_panel(),
                    debate_result={"debate_messages": [], "final_synthesis": "summary"},
                ),
            ]
        )

        create_response = self.client.post("/api/runs", json={"idea": IDEA})
        run_id = create_response.json()["run_id"]
        _, _, all_events = _fetch_sse_events(self.client, run_id, manager=self.manager)

        restarted = RunManager(db_path=self.db_path, recover_on_init=False)
        try:
            restarted_client = TestClient(create_app(manager=restarted))
            _, _, resumed = _fetch_sse_events(
                restarted_client,
                run_id,
                manager=restarted,
                headers={"Last-Event-ID": "2"},
            )
            self.assertEqual(resumed[0]["sequence"], 3)
            self.assertEqual(
                [event["sequence"] for event in resumed],
                [event["sequence"] for event in all_events if event["sequence"] > 2],
            )
        finally:
            restarted.close()

    @patch("api.run_manager.stream_pipeline")
    def test_restart_mid_run_replays_prefix_and_fails_cleanly(
        self,
        stream_pipeline_mock,
    ):
        request = CreateRunRequest.model_validate({"idea": IDEA})
        run_id = "interrupted-run-id"
        recent = datetime.now(UTC) - timedelta(minutes=5)
        self.manager._store._conn.execute(
            """
            INSERT INTO runs (run_id, request_json, status, created_at, updated_at)
            VALUES (?, ?, 'running', ?, ?)
            """,
            (
                run_id,
                request.model_dump_json(),
                recent.isoformat(),
                recent.isoformat(),
            ),
        )
        for sequence, event_type, payload in (
            (0, "stream_connected", {"status": "connected"}),
            (1, "phase_started", {"phase": "roast"}),
            (2, "judges_dispatched", {"total": 5}),
        ):
            self.manager._store._conn.execute(
                """
                INSERT INTO run_events (run_id, sequence, type, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    sequence,
                    event_type,
                    json.dumps(payload),
                    recent.isoformat(),
                ),
            )
        self.manager._store._conn.commit()

        restarted = RunManager(
            db_path=self.db_path,
            recover_on_init=False,
            stale_minutes=30,
        )
        try:
            client = TestClient(create_app(manager=restarted))
            status_code, _, events = _fetch_sse_events(client, run_id, manager=restarted)
            self.assertEqual(status_code, 200)
            types = [event["type"] for event in events]
            self.assertEqual(types[:3], ["stream_connected", "phase_started", "judges_dispatched"])
            self.assertEqual(types[-1], "run_failed")
            self.assertEqual(types.count("stream_connected"), 1)
            self.assertTrue(events[-1]["payload"]["recoverable"])

            status_response = client.get(f"/api/runs/{run_id}")
            self.assertEqual(status_response.json()["status"], "failed")
            stream_pipeline_mock.assert_not_called()
        finally:
            restarted.close()

    def test_stale_running_run_marked_failed_on_startup(self):
        request = CreateRunRequest.model_validate({"idea": IDEA})
        run_id = "stale-run-id"
        stale_time = datetime.now(UTC) - timedelta(minutes=60)
        self.manager._store._conn.execute(
            """
            INSERT INTO runs (run_id, request_json, status, created_at, updated_at)
            VALUES (?, ?, 'running', ?, ?)
            """,
            (
                run_id,
                request.model_dump_json(),
                stale_time.isoformat(),
                stale_time.isoformat(),
            ),
        )
        self.manager._store._conn.execute(
            """
            INSERT INTO run_events (run_id, sequence, type, payload_json, created_at)
            VALUES (?, 0, 'stream_connected', ?, ?)
            """,
            (
                run_id,
                json.dumps({"status": "connected"}),
                stale_time.isoformat(),
            ),
        )
        self.manager._store._conn.commit()

        recovered_manager = RunManager(
            db_path=self.db_path,
            recover_on_init=True,
            stale_minutes=30,
        )
        try:
            record = recovered_manager.get(run_id)
            assert record is not None
            self.assertEqual(record.status, "failed")

            events = recovered_manager.list_events(run_id)
            self.assertEqual(events[0].type, "stream_connected")
            self.assertEqual(events[-1].type, "run_failed")
            self.assertTrue(events[-1].payload["recoverable"])

            client = TestClient(create_app(manager=recovered_manager))
            _, _, parsed = _fetch_sse_events(client, run_id, manager=recovered_manager)
            self.assertEqual(parsed[-1]["type"], "run_failed")
        finally:
            recovered_manager.close()


if __name__ == "__main__":
    unittest.main()
