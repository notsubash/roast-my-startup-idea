import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from research.service import (
    WebSearchDecision,
    build_research_context,
    decide_web_search_usage,
    format_research_context,
)


class FakeTavilyClient:
    def __init__(self):
        self.queries = []

    def search(self, query: str, max_results: int) -> list[dict]:
        self.queries.append((query, max_results))
        return [
            {
                "title": "AI compliance market grows as regulation tightens",
                "url": "https://example.com/compliance-market",
                "content": "Healthcare and fintech compliance spending is rising in regulated markets.",
            },
            {
                "title": "Incumbents add lightweight AI compliance assistants",
                "url": "https://example.com/incumbent-assistants",
                "content": "Major workflow tools now bundle basic compliance copilots.",
            },
        ]


class FakePolicyStructuredModel:
    def __init__(self, decision: WebSearchDecision):
        self.decision = decision
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return self.decision


class FakePolicyStructuredModelFailure:
    def invoke(self, messages):
        raise RuntimeError("Thinking mode does not support this tool_choice")


class FakePolicyModel:
    def __init__(self, decision: WebSearchDecision):
        self.structured_model = FakePolicyStructuredModel(decision)
        self.schema = None

    def with_structured_output(self, schema):
        self.schema = schema
        return self.structured_model


class FakePolicyModelWithFallback:
    def with_structured_output(self, schema):
        return FakePolicyStructuredModelFailure()

    def invoke(self, prompt):
        class Response:
            content = (
                '{"use_search": true, '
                '"rationale": "Need current competitor context.", '
                '"query": "hospital wearable translator competitors pricing 2026"}'
            )

        return Response()


class ResearchServiceTest(unittest.TestCase):
    def test_decide_web_search_usage_uses_policy_model_output(self):
        policy_model = FakePolicyModel(
            WebSearchDecision(
                use_search=True,
                rationale="Needs current competitor and regulation facts.",
                query="AI hospital compliance copilot competitors pricing 2026",
            )
        )
        decision = decide_web_search_usage(
            policy_model=policy_model,
            startup_idea="AI compliance copilot for hospitals",
        )
        self.assertTrue(decision.use_search)
        self.assertIn("competitors pricing", decision.query)
        self.assertEqual(len(policy_model.structured_model.calls), 1)

    def test_decide_web_search_usage_falls_back_when_structured_output_fails(self):
        decision = decide_web_search_usage(
            policy_model=FakePolicyModelWithFallback(),
            startup_idea="Wearable spatial audio translator for deaf users",
        )
        self.assertTrue(decision.use_search)
        self.assertIn("competitor", decision.rationale.lower())
        self.assertIn("competitors pricing 2026", decision.query)

    def test_build_research_context_returns_none_when_policy_says_skip(self):
        client = FakeTavilyClient()
        policy_model = FakePolicyModel(
            WebSearchDecision(
                use_search=False,
                rationale="Idea can be judged without external facts.",
                query=None,
            )
        )
        context = build_research_context(
            startup_idea="A social app for sharing daily writing streaks",
            tavily_client=client,
            max_results=3,
            enabled=True,
            policy_model=policy_model,
        )
        self.assertIsNone(context)
        self.assertEqual(client.queries, [])

    def test_build_research_context_queries_and_formats_sources_when_policy_allows(self):
        client = FakeTavilyClient()
        policy_model = FakePolicyModel(
            WebSearchDecision(
                use_search=True,
                rationale="Requires market and competitor reality check.",
                query="AI compliance copilot hospitals competitors regulation trend",
            )
        )
        context = build_research_context(
            startup_idea="AI compliance copilot for hospitals",
            tavily_client=client,
            max_results=2,
            enabled=True,
            policy_model=policy_model,
        )
        assert context is not None
        rendered = format_research_context(context)
        self.assertIn("Web research", rendered)
        self.assertIn("https://example.com/compliance-market", rendered)
        self.assertIn("https://example.com/incumbent-assistants", rendered)
        self.assertEqual(len(client.queries), 1)


if __name__ == "__main__":
    unittest.main()
