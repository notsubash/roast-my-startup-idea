from datetime import UTC, datetime
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from judges.schemas import RoastPanel, Verdict
from memory.context import build_memory_context
from memory.identity import get_local_user_id
from memory.models import IdeaRecord
from memory.store import IdeaStore


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


class MemoryTest(unittest.TestCase):
    def test_store_returns_recent_records_for_only_requested_user(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with IdeaStore(Path(tmpdir) / "ideas.db") as store:
                older = IdeaRecord(
                    user_id="user-1",
                    idea_text="AI calendar for founders",
                    created_at=datetime(2026, 1, 1, tzinfo=UTC),
                    roast_panel=_panel(3, "No urgent buyer."),
                    debate_result={"final_synthesis": "Too vague to fund."},
                )
                newer = IdeaRecord(
                    user_id="user-1",
                    idea_text="AI compliance copilot for hospitals",
                    created_at=datetime(2026, 1, 2, tzinfo=UTC),
                    roast_panel=_panel(6, "Sales cycles are long."),
                    debate_result={"final_synthesis": "Specific but slow to sell."},
                )
                other_user = IdeaRecord(
                    user_id="user-2",
                    idea_text="Consumer habit tracker",
                    roast_panel=_panel(2, "No willingness to pay."),
                    debate_result={"final_synthesis": "Weak consumer urgency."},
                )

                store.save(older)
                store.save(newer)
                store.save(other_user)

                records = store.list_recent("user-1", limit=2)

            self.assertEqual(
                [record.idea_text for record in records],
                [
                    "AI compliance copilot for hospitals",
                    "AI calendar for founders",
                ],
            )

    def test_memory_context_summarizes_prior_ideas_without_full_transcripts(self):
        records = [
            IdeaRecord(
                user_id="user-1",
                idea_text="AI privacy policy summarizer for browser users",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                roast_panel=_panel(3, "Users will ignore passive summaries."),
                debate_result={
                    "debate_messages": [
                        {"speaker": "vc", "content": "long transcript that should not leak"}
                    ],
                    "final_synthesis": "The panel agreed passive summaries are too weak.",
                },
            )
        ]

        context = build_memory_context(records)

        self.assertIn("AI privacy policy summarizer", context)
        self.assertIn("avg 3.0/10", context)
        self.assertIn("Users will ignore passive summaries.", context)
        self.assertIn("The panel agreed passive summaries are too weak.", context)
        self.assertNotIn("long transcript that should not leak", context)

    def test_get_local_user_id_persists_across_calls(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            id_path = Path(tmpdir) / "local_user_id"
            db_path = Path(tmpdir) / "ideas.db"

            with patch("memory.identity.LOCAL_USER_ID_PATH", id_path):
                with IdeaStore(db_path) as store:
                    first = get_local_user_id(store)
                    second = get_local_user_id(store)

            self.assertEqual(first, second)
            self.assertEqual(id_path.read_text(encoding="utf-8"), first)

    def test_get_local_user_id_migrates_existing_db_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            id_path = Path(tmpdir) / "local_user_id"
            db_path = Path(tmpdir) / "ideas.db"

            with IdeaStore(db_path) as store:
                store.save(
                    IdeaRecord(
                        user_id="session-a",
                        idea_text="First pitch",
                        roast_panel=_panel(4, "Needs clearer buyer."),
                        debate_result={"final_synthesis": "Needs work."},
                    )
                )
                store.save(
                    IdeaRecord(
                        user_id="session-b",
                        idea_text="Second pitch",
                        roast_panel=_panel(5, "Long sales cycle."),
                        debate_result={"final_synthesis": "Maybe."},
                    )
                )

            with patch("memory.identity.LOCAL_USER_ID_PATH", id_path):
                with IdeaStore(db_path) as store:
                    user_id = get_local_user_id(store)
                    records = store.list_recent(user_id, limit=10)

            self.assertEqual(user_id, "local")
            self.assertEqual(
                {record.idea_text for record in records},
                {"First pitch", "Second pitch"},
            )


if __name__ == "__main__":
    unittest.main()
