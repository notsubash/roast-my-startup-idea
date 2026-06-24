import html
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import tests  # noqa: F401

# Avoid loading Streamlit's server stack during unit tests.
if "streamlit" not in sys.modules:
    sys.modules["streamlit"] = MagicMock()

from ui.text_display import (
    write_labelled_plain,
    write_plain_text,
    write_roast_quote,
    write_synthesis,
)


class _BorderContainer:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _mock_streamlit():
    st = MagicMock()
    st.container.return_value = _BorderContainer()
    return st


class TextDisplayTest(unittest.TestCase):
    def setUp(self):
        self.st_patcher = patch("ui.text_display.st", _mock_streamlit())
        self.st = self.st_patcher.start()

    def tearDown(self):
        self.st_patcher.stop()

    def test_write_plain_text_escapes_markdown_chars(self):
        write_plain_text("$200 _smartwatch_ `prototype` <sub>200</sub>")

        html_body = self.st.markdown.call_args[0][0]
        self.assertIn(html.escape("$200 _smartwatch_ `prototype` <sub>200</sub>"), html_body)
        self.assertNotIn("`prototype`", html_body.replace(html.escape("`prototype`"), ""))

    def test_write_roast_quote_wraps_in_italics(self):
        write_roast_quote("Costs $20 per unit")

        html_body = self.st.markdown.call_args[0][0]
        self.assertIn("font-style:italic", html_body)
        self.assertIn(html.escape("Costs $20 per unit"), html_body)

    def test_write_labelled_plain_escapes_both_parts(self):
        write_labelled_plain("Key concern:", "No path to _price_point_")

        html_body = self.st.markdown.call_args[0][0]
        self.assertIn("<strong>Key concern:</strong>", html_body)
        self.assertIn(html.escape("No path to _price_point_"), html_body)

    def test_write_synthesis_renders_markdown_in_container(self):
        write_synthesis("**1. Overall verdict:** FAIL")

        self.st.container.assert_called_once_with(border=True)
        self.st.markdown.assert_called_once_with("**1. Overall verdict:** FAIL")


if __name__ == "__main__":
    unittest.main()
