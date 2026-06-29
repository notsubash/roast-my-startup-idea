from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from judges.schemas import RoastPanel, Verdict
from judges.synthesis import (
    ConfidenceLevel,
    OverallRecommendation,
    Synthesis,
    parse_structured_synthesis,
    synthesis_compact_summary,
    synthesis_to_prose,
    top_priorities,
)
from memory.context import build_memory_context
from memory.models import IdeaRecord
import tests  # noqa: F401
from utils.transcript_exporter import export_transcript


def _panel(*, recommended_fix: str | None = "Run five buyer interviews this week.") -> RoastPanel:
    return RoastPanel(
        verdicts=[
            Verdict(
                judge="vc",
                verdict="FAIL",
                roast="Distribution is expensive and the market does not look venture scale.",
                score=3,
                key_concern="No urgent buyer.",
                recommended_fix=recommended_fix,
                evidence_to_change_verdict="Three signed LOIs from target buyers.",
            ),
            Verdict(
                judge="engineer",
                verdict="CONDITIONAL",
                roast="The build is feasible, but reliability will be harder than the demo suggests.",
                score=5,
                key_concern="Extraction reliability.",
                recommended_fix="Ship a benchmark on messy real-world documents.",
                evidence_to_change_verdict="A pilot with measured extraction accuracy above 95%.",
            ),
            Verdict(
                judge="pm",
                verdict="FAIL",
                roast="The target user is too broad, so the product will struggle to find a repeatable wedge.",
                score=3,
                key_concern="Unclear wedge.",
                recommended_fix="Pick one narrow ICP and rewrite the pitch around that buyer.",
                evidence_to_change_verdict="One repeatable channel with early conversion data.",
            ),
            Verdict(
                judge="customer",
                verdict="FAIL",
                roast="I would not change my workflow unless this saves obvious time immediately.",
                score=2,
                key_concern="Too much friction.",
                recommended_fix="Prototype the one-click workflow on a single task.",
                evidence_to_change_verdict="Usability test where three users complete the task unaided.",
            ),
            Verdict(
                judge="competitor",
                verdict="FAIL",
                roast="This is easy for incumbents to copy once they see any traction.",
                score=2,
                key_concern="No moat.",
                recommended_fix="Document a proprietary data or distribution advantage.",
                evidence_to_change_verdict="Evidence that incumbents cannot replicate the data source.",
            ),
        ]
    )


def _structured_debate_result() -> dict:
    synthesis = Synthesis(
        overall_recommendation=OverallRecommendation.ITERATE,
        confidence=ConfidenceLevel.MEDIUM,
        top_strengths=["Clear pain point for compliance teams."],
        top_risks=[
            "No proof of buyer urgency yet.",
            "Sales cycles may be too long for the current GTM.",
        ],
        biggest_disagreement="The VC wants a narrower wedge while the PM wants broader TAM.",
    )
    return {
        "debate_messages": [],
        "final_synthesis": synthesis_to_prose(synthesis),
        "structured_synthesis": synthesis.model_dump(),
    }


class SynthesisHelpersTest(unittest.TestCase):
    def test_parse_structured_synthesis_returns_none_for_legacy_records(self):
        self.assertIsNone(parse_structured_synthesis({"final_synthesis": "Too vague to fund."}))

    def test_top_priorities_prefers_structured_risks(self):
        synthesis = Synthesis(
            overall_recommendation=OverallRecommendation.NO_GO,
            confidence=ConfidenceLevel.HIGH,
            top_risks=["Fix buyer proof first.", "Validate pricing."],
            biggest_disagreement="Judges split on timing.",
        )
        priorities = top_priorities(synthesis, _panel())
        self.assertEqual(priorities, ["Fix buyer proof first.", "Validate pricing."])

    def test_top_priorities_falls_back_to_recommended_fixes(self):
        synthesis = Synthesis(
            overall_recommendation=OverallRecommendation.ITERATE,
            confidence=ConfidenceLevel.LOW,
            biggest_disagreement="Engineer and VC disagree on feasibility.",
        )
        priorities = top_priorities(synthesis, _panel())
        self.assertEqual(len(priorities), 3)
        self.assertIn("Run five buyer interviews this week.", priorities)

    def test_synthesis_compact_summary_uses_structured_fields(self):
        summary = synthesis_compact_summary(_structured_debate_result())
        self.assertIn("ITERATE (MEDIUM)", summary)
        self.assertIn("No proof of buyer urgency yet.", summary)

    def test_build_memory_context_uses_structured_summary(self):
        record = IdeaRecord(
            user_id="user-1",
            idea_text="AI compliance copilot for hospitals",
            roast_panel=_panel(),
            debate_result=_structured_debate_result(),
        )
        context = build_memory_context([record])
        self.assertIn("ITERATE (MEDIUM)", context)
        self.assertIn("No proof of buyer urgency yet.", context)


class StructuredTranscriptExportTest(unittest.TestCase):
    def test_export_includes_structured_verdict_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = export_transcript(
                "AI compliance copilot for hospitals",
                _panel(),
                _structured_debate_result(),
                output_dir=Path(tmpdir),
            )
            content = path.read_text(encoding="utf-8")
            self.assertIn("## Final Verdict", content)
            self.assertIn("**Recommendation:** ITERATE", content)
            self.assertIn("**Confidence:** MEDIUM", content)
            self.assertIn("### Top Priorities", content)
            self.assertIn("1. No proof of buyer urgency yet.", content)
            self.assertIn("### Biggest Disagreement", content)
            self.assertIn("VC wants a narrower wedge", content)

    def test_export_structured_verdict_skips_duplicate_top_risks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = export_transcript(
                "AI compliance copilot for hospitals",
                _panel(),
                _structured_debate_result(),
                output_dir=Path(tmpdir),
            )
            content = path.read_text(encoding="utf-8")
            self.assertIn("### Top Priorities", content)
            self.assertNotIn("### Top Risks", content)


if __name__ == "__main__":
    unittest.main()
