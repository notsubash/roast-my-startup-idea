"""Runnable checks for cooperative run abort."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from run_control import RunAbort, check_abort


class RunControlTest(unittest.TestCase):
    def test_check_abort_raises_with_reason(self):
        with self.assertRaises(RunAbort) as ctx:
            check_abort(lambda: "cancelled")
        self.assertEqual(ctx.exception.reason, "cancelled")

    def test_check_abort_noop_when_clear(self):
        check_abort(lambda: None)


if __name__ == "__main__":
    unittest.main()
