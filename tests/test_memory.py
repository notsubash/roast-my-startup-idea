from datetime import UTC, datetime
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from judges.schemas import RoastPanel, Verdict
from memory.context import build_memory_context
from memory.factory import build_idea_store
from memory.identity import get_local_user_id
from memory.models import IdeaRecord
from memory.retrieval import records_for_memory
from memory.store import IdeaStore
import tests  # noqa: F401


def _fake_embed_factory(vectors: dict[str, list[float]], *, dimension: int = 3):
    def fake_embed(text: str) -> list[float]:
        lowered = text.lower()
        for key, vector in vectors.items():
            if key in lowered:
                return vector
        return [0.0] * dimension

    return fake_embed


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

    def test_list_similar_returns_nearest_neighbors_for_user(self):
        vectors = {
            "hospital compliance": [1.0, 0.0, 0.0],
            "hospital regulatory": [0.99, 0.01, 0.0],
            "dog walking app": [0.0, 1.0, 0.0],
        }
        fake_embed = _fake_embed_factory(vectors)

        with tempfile.TemporaryDirectory() as tmpdir:
            with IdeaStore(
                Path(tmpdir) / "ideas.db",
                embed_fn=fake_embed,
                embedding_dimension=3,
                enable_semantic=True,
            ) as store:
                if not store.semantic_search_enabled:
                    self.skipTest("sqlite-vector extension unavailable in this environment")

                store.save(
                    IdeaRecord(
                        user_id="user-1",
                        idea_text="AI hospital compliance copilot",
                        roast_panel=_panel(4, "Regulatory drag."),
                        debate_result={"final_synthesis": "Compliance wedge."},
                    )
                )
                store.save(
                    IdeaRecord(
                        user_id="user-1",
                        idea_text="AI hospital regulatory automation",
                        roast_panel=_panel(5, "Long sales cycle."),
                        debate_result={"final_synthesis": "Specific buyer."},
                    )
                )
                store.save(
                    IdeaRecord(
                        user_id="user-1",
                        idea_text="On-demand dog walking app",
                        roast_panel=_panel(2, "No moat."),
                        debate_result={"final_synthesis": "Commodity marketplace."},
                    )
                )
                store.save(
                    IdeaRecord(
                        user_id="user-2",
                        idea_text="AI hospital compliance for payers",
                        roast_panel=_panel(6, "Different user."),
                        debate_result={"final_synthesis": "Other user."},
                    )
                )

                similar = store.list_similar(
                    "user-1",
                    "New AI hospital compliance platform",
                    limit=2,
                )

        self.assertEqual(
            [record.idea_text for record in similar],
            [
                "AI hospital compliance copilot",
                "AI hospital regulatory automation",
            ],
        )

    def test_records_for_memory_falls_back_to_recent_without_semantic_search(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with IdeaStore(Path(tmpdir) / "ideas.db") as store:
                store.save(
                    IdeaRecord(
                        user_id="user-1",
                        idea_text="Older idea",
                        created_at=datetime(2026, 1, 1, tzinfo=UTC),
                        roast_panel=_panel(3, "Old concern."),
                        debate_result={"final_synthesis": "Old synthesis."},
                    )
                )
                store.save(
                    IdeaRecord(
                        user_id="user-1",
                        idea_text="Newer idea",
                        created_at=datetime(2026, 1, 2, tzinfo=UTC),
                        roast_panel=_panel(4, "New concern."),
                        debate_result={"final_synthesis": "New synthesis."},
                    )
                )
                records = records_for_memory(store, "user-1", "unrelated query", limit=2)

        self.assertEqual([record.idea_text for record in records], ["Newer idea", "Older idea"])

    def test_records_for_memory_uses_semantic_search_when_enabled(self):
        vectors = {
            "hospital compliance": [1.0, 0.0, 0.0],
            "dog walking app": [0.0, 1.0, 0.0],
        }
        fake_embed = _fake_embed_factory(vectors)

        with tempfile.TemporaryDirectory() as tmpdir:
            with IdeaStore(
                Path(tmpdir) / "ideas.db",
                embed_fn=fake_embed,
                embedding_dimension=3,
                enable_semantic=True,
            ) as store:
                if not store.semantic_search_enabled:
                    self.skipTest("sqlite-vector extension unavailable in this environment")

                store.save(
                    IdeaRecord(
                        user_id="user-1",
                        idea_text="On-demand dog walking app",
                        created_at=datetime(2026, 1, 3, tzinfo=UTC),
                        roast_panel=_panel(2, "No moat."),
                        debate_result={"final_synthesis": "Commodity marketplace."},
                    )
                )
                store.save(
                    IdeaRecord(
                        user_id="user-1",
                        idea_text="AI hospital compliance copilot",
                        created_at=datetime(2026, 1, 1, tzinfo=UTC),
                        roast_panel=_panel(4, "Regulatory drag."),
                        debate_result={"final_synthesis": "Compliance wedge."},
                    )
                )

                records = records_for_memory(
                    store,
                    "user-1",
                    "New AI hospital compliance platform",
                    limit=1,
                )

        self.assertEqual(
            [record.idea_text for record in records], ["AI hospital compliance copilot"]
        )

    def test_records_for_memory_falls_back_when_vector_search_fails(self):
        vectors = {"hospital compliance": [1.0, 0.0, 0.0]}
        fake_embed = _fake_embed_factory(vectors)

        with tempfile.TemporaryDirectory() as tmpdir:
            with IdeaStore(
                Path(tmpdir) / "ideas.db",
                embed_fn=fake_embed,
                embedding_dimension=3,
                enable_semantic=True,
            ) as store:
                if not store.semantic_search_enabled:
                    self.skipTest("sqlite-vector extension unavailable in this environment")

                store.save(
                    IdeaRecord(
                        user_id="user-1",
                        idea_text="Newer hospital idea",
                        created_at=datetime(2026, 1, 2, tzinfo=UTC),
                        roast_panel=_panel(5, "Sales cycle."),
                        debate_result={"final_synthesis": "Specific."},
                    )
                )

                original_conn = store._conn

                class _ConnWrapper:
                    def __init__(self, conn):
                        self._inner = conn

                    def execute(self, sql, params=()):
                        if "vector_full_scan" in sql:
                            raise sqlite3.OperationalError("vector scan failed")
                        return self._inner.execute(sql, params)

                    def commit(self):
                        return self._inner.commit()

                    def close(self):
                        return self._inner.close()

                store._conn = _ConnWrapper(original_conn)  # type: ignore[assignment]

                records = records_for_memory(
                    store,
                    "user-1",
                    "AI hospital compliance platform",
                    limit=1,
                )

        self.assertEqual([record.idea_text for record in records], ["Newer hospital idea"])

    @patch("memory.factory.build_embedding_fn", side_effect=ValueError("unsupported model"))
    @patch("memory.factory.get_settings")
    def test_build_idea_store_disables_semantic_on_embedder_failure(
        self,
        get_settings_mock,
        _build_embedding_fn_mock,
    ):
        from config import Settings

        get_settings_mock.return_value = Settings(
            local_model="ollama:qwen3.5:9b",
            deepseek_model="deepseek-v4-pro",
            deepseek_base_url="https://api.deepseek.com",
            embedding_model="bad:model",
            embedding_dimension=768,
            enable_semantic_memory=True,
            max_debate_rounds=3,
            enable_web_search=False,
            web_search_max_results=3,
            sse_heartbeat_seconds=15.0,
            stale_run_minutes=30,
            runs_db_path=Path("data/runs.db"),
        )

        store = build_idea_store()
        try:
            self.assertFalse(store.semantic_search_enabled)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
