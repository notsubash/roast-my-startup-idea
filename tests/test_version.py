import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from version import __version__, get_version


class VersionTest(unittest.TestCase):
    def test_version_matches_pyproject(self) -> None:
        self.assertEqual(get_version(), "0.2.0")
        self.assertEqual(__version__, get_version())

    def test_version_is_pep440(self) -> None:
        parts = get_version().split(".")
        self.assertGreaterEqual(len(parts), 2)
        for part in parts:
            self.assertTrue(part.isdigit(), msg=f"non-numeric segment: {part!r}")


if __name__ == "__main__":
    unittest.main()
