from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from config import JUDGE_ORDER
from events import PipelineCompleted, RunMetrics
from judges.schemas import RoastPanel, Verdict
from observability.metrics import (
    PhaseTimer,
    RunMetricsCollector,
    estimate_cost_usd,
    estimate_tokens_from_text,
    extract_token_usage,
    format_run_metrics_footer,
    resolve_token_usage,
)
from pipeline import stream_pipeline
import tests  # noqa: F401


class UsageMetadata:
    def __init__(self, input_tokens: int, output_tokens: int):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class FakeUsageResponse:
    def __init__(self, *, input_tokens: int = 0, output_tokens: int = 0, text: str = ""):
        self.usage_metadata = UsageMetadata(input_tokens, output_tokens)
        self.content = text


def _verdict(judge: str) -> Verdict:
    return Verdict(
        judge=judge,
        verdict="FAIL",
        roast="The go-to-market path is unclear and the wedge is too weak to win attention.",
        score=3,
        key_concern="Weak distribution.",
    )


class MetricsHelpersTest(unittest.TestCase):
    def test_extract_token_usage_reads_usage_metadata(self):
        response = FakeUsageResponse(input_tokens=120, output_tokens=45)
        self.assertEqual(extract_token_usage(response), (120, 45))

    def test_resolve_token_usage_falls_back_to_text_estimate(self):
        input_tokens, output_tokens = resolve_token_usage(
            None,
            prompt_text="abcd" * 10,
            output_text="efgh" * 5,
        )
        self.assertEqual(input_tokens, 10)
        self.assertEqual(output_tokens, 5)

    def test_estimate_cost_usd_for_deepseek(self):
        cost = estimate_cost_usd(1_000_000, 1_000_000, model_runtime="deepseek")
        self.assertAlmostEqual(cost, 0.42, places=2)

    def test_estimate_cost_usd_for_local_is_zero(self):
        self.assertEqual(estimate_cost_usd(5000, 5000, model_runtime="local"), 0.0)

    def test_estimate_tokens_from_text(self):
        self.assertEqual(estimate_tokens_from_text("12345678"), 2)

    def test_format_run_metrics_footer(self):
        footer = format_run_metrics_footer(
            {
                "roast_seconds": 4.2,
                "debate_seconds": 11.8,
                "total_tokens": 3100,
                "estimated_cost_usd": 0.004,
            }
        )
        self.assertIn("Roast 4.2s", footer)
        self.assertIn("Debate 11.8s", footer)
        self.assertIn("~3.1k tokens", footer)
        self.assertIn("~$0.004", footer)


class RunMetricsCollectorTest(unittest.TestCase):
    def test_discard_phase_clears_recorded_calls(self):
        collector = RunMetricsCollector(model_runtime="local")
        collector.record_judge("vc", seconds=1.0, prompt_text="abcd", output_text="efgh")
        collector.discard_phase("roast")
        snapshot = collector.snapshot(roast_seconds=1.0, debate_seconds=0.0, total_seconds=1.0)
        self.assertEqual(snapshot["judge_calls"], [])
        self.assertEqual(snapshot["total_tokens"], 0)

    def test_snapshot_aggregates_calls_and_phases(self):
        collector = RunMetricsCollector(model_runtime="deepseek")
        collector.record_judge(
            "vc",
            seconds=1.2,
            response=FakeUsageResponse(input_tokens=100, output_tokens=50),
        )
        collector.record_debate(
            "engineer",
            seconds=2.5,
            response=FakeUsageResponse(input_tokens=200, output_tokens=80),
        )

        snapshot = collector.snapshot(roast_seconds=4.2, debate_seconds=11.8, total_seconds=16.0)

        self.assertEqual(snapshot["roast_seconds"], 4.2)
        self.assertEqual(snapshot["debate_seconds"], 11.8)
        self.assertEqual(snapshot["total_seconds"], 16.0)
        self.assertEqual(snapshot["input_tokens"], 300)
        self.assertEqual(snapshot["output_tokens"], 130)
        self.assertEqual(snapshot["total_tokens"], 430)
        self.assertEqual(snapshot["model_runtime"], "deepseek")
        self.assertEqual(len(snapshot["judge_calls"]), 1)
        self.assertEqual(snapshot["judge_calls"][0]["label"], "vc")
        self.assertEqual(len(snapshot["debate_calls"]), 1)
        self.assertEqual(snapshot["debate_calls"][0]["label"], "engineer")
        self.assertGreater(snapshot["estimated_cost_usd"], 0.0)


class PhaseTimerTest(unittest.TestCase):
    def test_tracks_roast_and_debate_seconds(self):
        timer = PhaseTimer()
        time.sleep(0.01)
        timer.start_debate()
        time.sleep(0.01)
        roast_seconds, debate_seconds, total_seconds = timer.finish(in_debate=True)

        self.assertGreater(roast_seconds, 0.0)
        self.assertGreater(debate_seconds, 0.0)
        self.assertGreaterEqual(total_seconds, roast_seconds + debate_seconds)


class PipelineRunMetricsTest(unittest.TestCase):
    def test_stream_pipeline_yields_run_metrics_event(self):
        panel = RoastPanel(verdicts=[_verdict(judge) for judge in JUDGE_ORDER])

        def fake_stream_roast_panel(_model, _idea, *_args, **kwargs):
            from events import RoastPanelCompleted

            metrics = kwargs.get("metrics")
            if metrics is not None:
                metrics.record_judge(
                    "vc",
                    seconds=0.4,
                    response=FakeUsageResponse(input_tokens=50, output_tokens=25),
                )
            yield RoastPanelCompleted(panel=panel)

        def fake_stream_debate(_model, _idea, _panel, *_args, **kwargs):
            from events import DebateCompleted

            metrics = kwargs.get("metrics")
            if metrics is not None:
                metrics.record_debate(
                    "vc",
                    seconds=1.1,
                    response=FakeUsageResponse(input_tokens=80, output_tokens=30),
                )
            yield DebateCompleted(debate_messages=[], final_synthesis="summary")

        with (
            patch("pipeline.stream_roast_panel", side_effect=fake_stream_roast_panel),
            patch("pipeline.stream_debate", side_effect=fake_stream_debate),
        ):
            events = list(
                stream_pipeline(
                    object(),
                    "An AI journal for startup founders with daily reflection prompts.",
                    max_debate_rounds=1,
                    model_runtime="deepseek",
                )
            )

        self.assertIsInstance(events[-2], RunMetrics)
        self.assertIsInstance(events[-1], PipelineCompleted)
        metrics_event = events[-2]
        self.assertGreaterEqual(metrics_event.roast_seconds, 0.0)
        self.assertGreaterEqual(metrics_event.debate_seconds, 0.0)
        self.assertEqual(metrics_event.total_tokens, 185)
        self.assertEqual(metrics_event.model_runtime, "deepseek")
        self.assertGreater(metrics_event.estimated_cost_usd, 0.0)

    def test_stream_pipeline_revote_events_precede_run_metrics(self):
        from events import (
            DebateCompleted,
            DebateSynthesisPublished,
            RevoteJudgeCompleted,
            RevoteStarted,
            RunMetrics,
        )

        panel = RoastPanel(verdicts=[_verdict(judge) for judge in JUDGE_ORDER])
        initial = [v.model_dump() for v in panel.verdicts]
        revised = [v.model_copy(update={"score": v.score + 1}).model_dump() for v in panel.verdicts]

        def fake_stream_roast_panel(_model, _idea, *_args, **_kwargs):
            from events import RoastPanelCompleted

            yield RoastPanelCompleted(panel=panel)

        def fake_stream_debate(_model, _idea, _panel, *_args, **_kwargs):
            yield RevoteStarted(total=5)
            yield RevoteJudgeCompleted(
                judge="vc",
                verdict=panel.verdicts[0].model_copy(update={"score": 4}),
                original_score=3,
                completed=1,
                total=5,
            )
            yield DebateSynthesisPublished(content="summary")
            yield DebateCompleted(
                debate_messages=[],
                final_synthesis="summary",
                initial_verdicts=initial,
                revised_verdicts=revised,
            )

        with (
            patch("pipeline.stream_roast_panel", side_effect=fake_stream_roast_panel),
            patch("pipeline.stream_debate", side_effect=fake_stream_debate),
        ):
            events = list(
                stream_pipeline(
                    object(),
                    "An AI journal for startup founders with daily reflection prompts.",
                    max_debate_rounds=1,
                    model_runtime="deepseek",
                )
            )

        revote_idx = next(i for i, event in enumerate(events) if isinstance(event, RevoteStarted))
        metrics_idx = next(i for i, event in enumerate(events) if isinstance(event, RunMetrics))
        self.assertLess(revote_idx, metrics_idx)
        synthesis_idx = next(
            i for i, event in enumerate(events) if isinstance(event, DebateSynthesisPublished)
        )
        self.assertLess(revote_idx, synthesis_idx)

    def test_stream_pipeline_save_uses_idea_id(self):
        from pathlib import Path
        import tempfile

        from memory.identity import LOCAL_USER
        from memory.store import IdeaStore

        panel = RoastPanel(verdicts=[_verdict(judge) for judge in JUDGE_ORDER])

        def fake_stream_roast_panel(_model, _idea, *_args, **_kwargs):
            from events import RoastPanelCompleted

            yield RoastPanelCompleted(panel=panel)

        def fake_stream_debate(_model, _idea, _panel, *_args, **_kwargs):
            from events import DebateCompleted

            yield DebateCompleted(debate_messages=[], final_synthesis="summary")

        with tempfile.TemporaryDirectory() as tmpdir:
            with IdeaStore(Path(tmpdir) / "ideas.db") as store:
                with (
                    patch("pipeline.stream_roast_panel", side_effect=fake_stream_roast_panel),
                    patch("pipeline.stream_debate", side_effect=fake_stream_debate),
                ):
                    list(
                        stream_pipeline(
                            object(),
                            "An AI journal for startup founders with daily reflection prompts.",
                            max_debate_rounds=1,
                            user_id=LOCAL_USER,
                            idea_store=store,
                            idea_id="run-persist-123",
                        )
                    )
                saved = store.list_recent(LOCAL_USER, limit=1)
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0].id, "run-persist-123")


if __name__ == "__main__":
    unittest.main()
