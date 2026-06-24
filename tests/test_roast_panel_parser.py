from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from utils.roast_panel_parser import extract_roast_panel


class FakeMessage:
    def __init__(
        self,
        content: str | None,
        tool_calls: list[dict] | None = None,
        tool_call_id: str | None = None,
    ):
        self.content = content
        self.tool_calls = tool_calls
        self.tool_call_id = tool_call_id


class RoastPanelParserTest(unittest.TestCase):
    def test_extract_roast_panel_from_individual_tool_messages(self):
        result = {
            "messages": [
                FakeMessage(None),
                FakeMessage(
                    """{
                        "judge": "vc",
                        "verdict": "FAIL",
                        "roast": "This is bootstrapping territory, not VC material. CAC in a saturated browser-extension market destroys the subscription upside before this looks fundable.",
                        "score": 3,
                        "key_concern": "Distribution moat is zero because browser stores are saturated with privacy extensions and users will prefer free options from established browser or privacy brands over a new paid player."
                    }"""
                ),
                FakeMessage(
                    """```json
                    {
                        "judge": "engineer",
                        "verdict": "FAIL",
                        "roast": "The technical problem is not summarization, it is reliable extraction, policy-change detection, and avoiding false confidence on legal text across messy websites.",
                        "score": 4,
                        "key_concern": "Modern privacy policies are often dynamically rendered, localized, and revised without clean versioning, so the extension needs resilient extraction and change detection before summaries can be trusted."
                    }
                    ```"""
                ),
                FakeMessage(""),
                FakeMessage(
                    """{
                        "judge": "customer",
                        "verdict": "CONDITIONAL",
                        "roast": "I like the idea until you ask me to trust an AI summary for a legal decision I was already planning to ignore.",
                        "score": 6,
                        "key_concern": "The product must earn trust that its summaries are accurate and neutral, otherwise one missed data-sharing clause destroys user confidence."
                    }"""
                ),
                FakeMessage(
                    """{
                        "judge": "competitor",
                        "verdict": "FAIL",
                        "roast": "Incumbent privacy tools already block trackers in the background while this asks users to read one more thing before doing what they were already going to do.",
                        "score": 3,
                        "key_concern": "There is no durable defensibility against existing privacy extensions and browsers that can add lightweight policy summaries beside stronger native blocking features."
                    }"""
                ),
                FakeMessage(
                    """{
                        "judge": "pm",
                        "verdict": "FAIL",
                        "roast": "This explains the problem instead of removing it, which is why retention will fall once the novelty wears off.",
                        "score": 3,
                        "key_concern": "Users want automated privacy protection in the background, not another recurring decision point at every site visit."
                    }"""
                ),
            ]
        }

        panel = extract_roast_panel(result)

        self.assertEqual(len(panel.verdicts), 5)
        self.assertEqual(
            {verdict.judge.value for verdict in panel.verdicts},
            {"vc", "engineer", "pm", "customer", "competitor"},
        )

    def test_extract_roast_panel_recovers_markdown_tool_response_with_call_id(self):
        result = {
            "messages": [
                FakeMessage(
                    None,
                    tool_calls=[
                        {
                            "id": "pm-call",
                            "args": {"subagent_type": "pm_judge"},
                        }
                    ],
                ),
                FakeMessage(
                    """{
                        "judge": "vc",
                        "verdict": "FAIL",
                        "roast": "This is bootstrapping territory, not VC material. CAC in a saturated browser-extension market destroys the subscription upside before this looks fundable.",
                        "score": 3,
                        "key_concern": "Distribution moat is zero because browser stores are saturated with privacy extensions and users will prefer free options from established browser or privacy brands over a new paid player."
                    }"""
                ),
                FakeMessage(
                    """{
                        "judge": "engineer",
                        "verdict": "CONDITIONAL",
                        "roast": "The technical problem is not summarization, it is reliable extraction, policy-change detection, and avoiding false confidence on legal text across messy websites.",
                        "score": 4,
                        "key_concern": "Modern privacy policies are often dynamically rendered, localized, and revised without clean versioning, so the extension needs resilient extraction and change detection before summaries can be trusted."
                    }"""
                ),
                FakeMessage(
                    """Verdict: **FAIL**

Roast: This idea fails on product-market fit because users are not reading privacy policies out of curiosity; they are clicking accept by default. A tool that only summarizes becomes invisible noise in an already overloaded UI.

Score: **3/10**

Key concern: Without integrating the summary into user behavior flows or offering an actual decision framework, summaries are passive information that users will ignore.""",
                    tool_call_id="pm-call",
                ),
                FakeMessage(
                    """{
                        "judge": "customer",
                        "verdict": "FAIL",
                        "roast": "Users do not actually care about privacy policies; they want to browse without friction and avoid yet another decision point.",
                        "score": 2,
                        "key_concern": "Friction kills adoption because users will not stop to read summaries when they are already in click-accept mode."
                    }"""
                ),
                FakeMessage(
                    """{
                        "judge": "competitor",
                        "verdict": "FAIL",
                        "roast": "Browser vendors and existing privacy tools already control this surface, so a summary-only extension has no durable wedge.",
                        "score": 2,
                        "key_concern": "Browser manufacturers control the distribution channel and can add native privacy summaries beside stronger blocking features."
                    }"""
                ),
            ]
        }

        panel = extract_roast_panel(result)

        self.assertEqual(
            {verdict.judge.value for verdict in panel.verdicts},
            {"vc", "engineer", "pm", "customer", "competitor"},
        )
        pm_verdict = next(verdict for verdict in panel.verdicts if verdict.judge.value == "pm")
        self.assertEqual(pm_verdict.verdict.value, "FAIL")
        self.assertEqual(pm_verdict.score, 3)
