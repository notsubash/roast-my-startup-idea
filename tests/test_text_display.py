import html
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

markdown_calls: list[tuple] = []


def _capture_markdown(*args, **kwargs):
    markdown_calls.append((args, kwargs))
    return None


class _BorderContainer:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


sys.modules.setdefault(
    "streamlit",
    types.SimpleNamespace(
        markdown=_capture_markdown,
        container=lambda border=False: _BorderContainer(),
    ),
)

from ui.text_display import write_labelled_plain, write_plain_text, write_roast_quote, write_synthesis


class TextDisplayTest(unittest.TestCase):
    def setUp(self):
        markdown_calls.clear()

    def test_write_plain_text_escapes_markdown_chars(self):
        write_plain_text("$200 _smartwatch_ `prototype` <sub>200</sub>")

        html_body = markdown_calls[-1][0][0]
        self.assertIn(html.escape("$200 _smartwatch_ `prototype` <sub>200</sub>"), html_body)
        self.assertNotIn("`prototype`", html_body.replace(html.escape("`prototype`"), ""))

    def test_write_roast_quote_wraps_in_italics(self):
        write_roast_quote("Costs $20 per unit")

        html_body = markdown_calls[-1][0][0]
        self.assertIn("font-style:italic", html_body)
        self.assertIn(html.escape("Costs $20 per unit"), html_body)

    def test_write_labelled_plain_escapes_both_parts(self):
        write_labelled_plain("Key concern:", "No path to _price_point_")

        html_body = markdown_calls[-1][0][0]
        self.assertIn("<strong>Key concern:</strong>", html_body)
        self.assertIn(html.escape("No path to _price_point_"), html_body)

    def test_write_synthesis_uses_container_and_plain_text(self):
        write_synthesis("Final verdict: $200 prototype")

        html_body = markdown_calls[-1][0][0]
        self.assertIn(html.escape("Final verdict: $200 prototype"), html_body)


if __name__ == "__main__":
    unittest.main()
