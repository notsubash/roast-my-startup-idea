import json
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
import tests  # noqa: F401

sys.path.insert(0, str(PROJECT_ROOT / "src"))

from evals import BASELINES_DIR
from evals.dataset.baseline_builder import build_smartpatch_baseline
from evals.dataset.loader import filter_ideas, load_golden_ideas
from evals.grader.deepseek_judge import DeepSeekGrader, build_grader_prompt, flatten_grade
from evals.grader.schemas import (
    AppealGrade,
    DebateGrade,
    DimensionScore,
    IdeaAuditGrade,
    RoastPanelGrade,
    SynthesisGrade,
    normalize_grade_payload,
)
from evals.run_audit import run_audit


def _dimension(score: int, rationale: str = "Solid output with minor issues.") -> DimensionScore:
    return DimensionScore(score=score, rationale=rationale)


def _sample_grade() -> IdeaAuditGrade:
    def dim(score: int) -> DimensionScore:
        return DimensionScore(score=score, rationale="Specific and consistent with outputs.")

    return IdeaAuditGrade(
        roast_panel=RoastPanelGrade(
            vc_persona=dim(4),
            engineer_persona=dim(4),
            pm_persona=dim(4),
            customer_persona=dim(4),
            competitor_persona=dim(4),
            roast_specificity=dim(4),
            verdict_score_alignment=True,
        ),
        debate=DebateGrade(
            cross_judge_engagement=dim(4),
            non_repetition=dim(4),
        ),
        synthesis=SynthesisGrade(
            synthesis_faithfulness=dim(4),
            dissent_preservation=True,
        ),
        appeal=AppealGrade(
            evidence_responsiveness=dim(4),
            score_movement_appropriate=True,
        ),
    )


class EvalAuditTest(unittest.TestCase):
    def test_load_and_filter_golden_ideas(self):
        ideas = load_golden_ideas()
        self.assertEqual(len(ideas), 12)
        filtered = filter_ideas(ideas, idea_ids=["smartpatch", "metrics_strong"])
        self.assertEqual(len(filtered), 2)

    def test_build_grader_prompt_uses_jinja_templates(self):
        payload = build_smartpatch_baseline()
        golden = next(i for i in load_golden_ideas() if i.id == "smartpatch")
        system_prompt, user_prompt = build_grader_prompt(payload, golden)
        self.assertIn("multi-agent startup critique system", system_prompt)
        self.assertIn("colorimetric", user_prompt)
        self.assertIn("Phase 1", user_prompt)

    def test_grader_retries_when_structured_output_is_none(self):
        valid = _sample_grade()
        calls = {"count": 0}

        class FakeStructured:
            def invoke(self, messages, **_kwargs):
                calls["count"] += 1
                return None if calls["count"] == 1 else valid

        class FakeModel:
            def with_structured_output(self, schema):
                return FakeStructured()

            def invoke(self, messages, **_kwargs):
                raise AssertionError("JSON fallback should not run when structured succeeds")

        grader = DeepSeekGrader(model=FakeModel())
        payload = build_smartpatch_baseline()
        grade = grader.grade_idea_result(payload)
        self.assertEqual(grade.roast_panel.vc_persona.score, 4)
        self.assertEqual(calls["count"], 2)

    def test_grader_uses_json_fallback_after_repeated_none(self):
        valid_json = _sample_grade().model_dump(mode="json")

        class FakeStructured:
            def invoke(self, messages, **_kwargs):
                return None

        class FakeModel:
            def __init__(self):
                self.fallback_called = False

            def with_structured_output(self, schema):
                return FakeStructured()

            def invoke(self, messages, **_kwargs):
                self.fallback_called = True

                class Response:
                    content = json.dumps(valid_json)

                return Response()

        grader = DeepSeekGrader(model=FakeModel())
        payload = build_smartpatch_baseline()
        grade = grader.grade_idea_result(payload)
        self.assertTrue(grader.model.fallback_called)
        self.assertEqual(grade.debate.cross_judge_engagement.score, 4)

    def test_normalize_grade_payload_accepts_flat_grader_json(self):
        flat_payload = {
            "roast_panel": {
                "vc_score": 5,
                "vc_rationale": "The VC roast is sharp and specific.",
                "engineer_score": 5,
                "engineer_rationale": "The engineer roast covers real-world conditions.",
                "pm_score": 4,
                "pm_rationale": "The PM roast highlights actionable data.",
                "customer_score": 5,
                "customer_rationale": "The customer roast nails adoption blockers.",
                "competitor_score": 5,
                "competitor_rationale": "The competitor roast is grounded.",
                "roast_specificity": 5,
                "roast_specificity_rationale": "Every judge provided specific critiques.",
                "verdict_score_alignment": True,
                "verdict_score_alignment_rationale": "All judge verdicts align with scores.",
            },
            "debate": {
                "cross_judge_engagement": 5,
                "cross_judge_engagement_rationale": "Strong cross-judge engagement.",
                "non_repetition": 3,
                "non_repetition_rationale": "Some repetition by round 3.",
            },
            "synthesis": {
                "synthesis_faithfulness": 5,
                "synthesis_faithfulness_rationale": "The synthesis reflects debate points.",
                "dissent_preservation": True,
                "dissent_preservation_rationale": "Dissent is preserved in synthesis.",
            },
            "appeal": {
                "evidence_responsiveness": 4,
                "evidence_responsiveness_rationale": "Revised panel addresses evidence.",
                "score_movement_appropriate": True,
                "score_movement_appropriate_rationale": "Score movements match evidence strength.",
            },
        }
        grade = IdeaAuditGrade.model_validate(normalize_grade_payload(flat_payload))
        self.assertEqual(grade.roast_panel.vc_persona.score, 5)
        self.assertEqual(grade.debate.non_repetition.score, 3)
        self.assertTrue(grade.roast_panel.verdict_score_alignment)

    def test_normalize_grade_payload_truncates_long_rationales(self):
        long_rationale = "x" * 600
        flat_payload = {
            "roast_panel": {
                "vc_score": 4,
                "vc_rationale": long_rationale,
                "engineer_score": 4,
                "engineer_rationale": "Engineer critique cites technical risks.",
                "pm_score": 4,
                "pm_rationale": "PM critique highlights user workflow gaps.",
                "customer_score": 4,
                "customer_rationale": "Customer critique focuses on adoption pain.",
                "competitor_score": 4,
                "competitor_rationale": "Competitor critique names alternatives.",
                "roast_specificity": 4,
                "roast_specificity_rationale": "Roasts reference concrete product details.",
                "verdict_score_alignment": True,
            },
            "debate": {
                "cross_judge_engagement": 4,
                "cross_judge_engagement_rationale": long_rationale,
                "non_repetition": 4,
                "non_repetition_rationale": "Debate stays mostly non-repetitive.",
            },
            "synthesis": {
                "synthesis_faithfulness": 4,
                "synthesis_faithfulness_rationale": "Synthesis reflects debate content.",
                "dissent_preservation": True,
            },
            "appeal": None,
        }
        grade = IdeaAuditGrade.model_validate(normalize_grade_payload(flat_payload))
        self.assertEqual(len(grade.roast_panel.vc_persona.rationale), 500)
        self.assertEqual(len(grade.debate.cross_judge_engagement.rationale), 500)

    def test_grader_json_fallback_normalizes_flat_payload(self):
        flat_payload = {
            "roast_panel": {
                "vc_score": 4,
                "vc_rationale": "Specific VC critique with market framing.",
                "engineer_score": 4,
                "engineer_rationale": "Engineer critique cites technical risks.",
                "pm_score": 4,
                "pm_rationale": "PM critique highlights user workflow gaps.",
                "customer_score": 4,
                "customer_rationale": "Customer critique focuses on adoption pain.",
                "competitor_score": 4,
                "competitor_rationale": "Competitor critique names alternatives.",
                "roast_specificity": 4,
                "roast_specificity_rationale": "Roasts reference concrete product details.",
                "verdict_score_alignment": True,
            },
            "debate": {
                "cross_judge_engagement": 4,
                "cross_judge_engagement_rationale": "Judges respond to each other's points.",
                "non_repetition": 4,
                "non_repetition_rationale": "Debate stays mostly non-repetitive.",
            },
            "synthesis": {
                "synthesis_faithfulness": 4,
                "synthesis_faithfulness_rationale": "Synthesis reflects debate content.",
                "dissent_preservation": True,
            },
            "appeal": None,
        }

        class FakeStructured:
            def invoke(self, messages, **_kwargs):
                return None

        class FakeModel:
            def with_structured_output(self, schema):
                return FakeStructured()

            def invoke(self, messages, **_kwargs):
                class Response:
                    content = json.dumps(flat_payload)

                return Response()

        grader = DeepSeekGrader(model=FakeModel())
        grade = grader.grade_idea_result(build_smartpatch_baseline())
        self.assertEqual(grade.roast_panel.pm_persona.score, 4)
        self.assertIsNone(grade.appeal)

    def test_audit_baseline_only_filters_to_committed_fixtures(self):
        golden_ideas = load_golden_ideas()
        baseline_fixture_count = sum(
            1 for idea in golden_ideas if (BASELINES_DIR / f"{idea.id}.json").exists()
        )
        self.assertGreater(baseline_fixture_count, 0)

        payload = run_audit(
            reuse_last_local=False,
            refresh_local=False,
            baseline_only=True,
            dry_run=True,
        )
        self.assertEqual(payload["ideas_evaluated"], baseline_fixture_count)
        payload = run_audit(
            reuse_last_local=False,
            refresh_local=False,
            idea_ids=["smartpatch", "metrics_strong"],
            dry_run=True,
        )
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["ideas_evaluated"], 2)
        self.assertGreater(payload["estimated_input_tokens"], 0)

    def test_flatten_grade_extracts_dimensions_and_gates(self):
        grade = IdeaAuditGrade(
            roast_panel=RoastPanelGrade(
                vc_persona=_dimension(4),
                engineer_persona=_dimension(5),
                pm_persona=_dimension(4),
                customer_persona=_dimension(3),
                competitor_persona=_dimension(4),
                roast_specificity=_dimension(4),
                verdict_score_alignment=True,
            ),
            debate=DebateGrade(
                cross_judge_engagement=_dimension(4),
                non_repetition=_dimension(3),
            ),
            synthesis=SynthesisGrade(
                synthesis_faithfulness=_dimension(4),
                dissent_preservation=True,
            ),
            appeal=AppealGrade(
                evidence_responsiveness=_dimension(4),
                score_movement_appropriate=True,
            ),
        )
        flattened = flatten_grade(grade)
        self.assertIn("vc_persona", flattened["dimensions"])
        self.assertTrue(flattened["gates"]["dissent_preservation"])
        self.assertGreater(flattened["composite_dimension_avg"], 0)


if __name__ == "__main__":
    unittest.main()
