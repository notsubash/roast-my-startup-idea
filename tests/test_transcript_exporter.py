from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from judges.schemas import RoastPanel, Verdict
import tests  # noqa: F401
from utils.transcript_exporter import export_transcript


def _panel(score: int, concern: str) -> RoastPanel:
    return RoastPanel(
        verdicts=[
            Verdict(
                judge="vc",
                verdict="FAIL",
                roast="Distribution is expensive and the market does not look venture scale.",
                score=score,
                key_concern=concern,
            ),
            Verdict(
                judge="engineer",
                verdict="CONDITIONAL",
                roast="The build is feasible, but reliability will be harder than the demo suggests.",
                score=score,
                key_concern=concern,
            ),
            Verdict(
                judge="pm",
                verdict="FAIL",
                roast="The target user is too broad, so the product will struggle to find a repeatable wedge.",
                score=score,
                key_concern=concern,
            ),
            Verdict(
                judge="customer",
                verdict="FAIL",
                roast="I would not change my workflow unless this saves obvious time immediately.",
                score=score,
                key_concern=concern,
            ),
            Verdict(
                judge="competitor",
                verdict="FAIL",
                roast="This is easy for incumbents to copy once they see any traction.",
                score=score,
                key_concern=concern,
            ),
        ]
    )


class TranscriptExporterTest(unittest.TestCase):
    def test_export_without_appeal_omits_phase_three(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = export_transcript(
                "AI calendar for founders",
                _panel(3, "No urgent buyer."),
                {"final_synthesis": "Too vague to fund.", "debate_messages": []},
                output_dir=Path(tmpdir),
            )
            content = path.read_text(encoding="utf-8")
            self.assertIn("## Phase 1: Individual Roasts", content)
            self.assertIn("## Final Synthesis", content)
            self.assertNotIn("## Phase 3: Appeal", content)

    def test_export_with_appeal_includes_revised_verdicts_and_synthesis(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = export_transcript(
                "AI compliance copilot for hospitals",
                _panel(3, "Sales cycles are long."),
                {"final_synthesis": "Specific but slow to sell.", "debate_messages": []},
                output_dir=Path(tmpdir),
                appeal_text="We have three signed LOIs worth $180k ARR.",
                revised_panel=_panel(5, "Pilot conversion still uncertain."),
                revised_synthesis="The appeal added concrete revenue evidence but did not remove sales-cycle risk.",
            )
            content = path.read_text(encoding="utf-8")
            self.assertIn("## Phase 3: Appeal", content)
            self.assertIn("### Founder Appeal", content)
            self.assertIn("three signed LOIs worth $180k ARR", content)
            self.assertIn("### Revised Verdicts", content)
            self.assertIn("(5/10, was 3/10, +2)", content)
            self.assertIn("### Appeal Synthesis", content)
            self.assertIn("did not remove sales-cycle risk", content)


if __name__ == "__main__":
    unittest.main()
