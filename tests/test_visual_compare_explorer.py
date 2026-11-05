"""Unittest wrapper of tests/visual_compare_explorer.py (T-VISUAL, aidd:FR-077, AC-066) so V-22 runs through unittest.
Skips visibly when no Chromium is available; never fails for that reason."""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


class VisualCompareExplorer(unittest.TestCase):
    def test_required_checks_match(self):
        import visual_compare_explorer
        report = visual_compare_explorer.compare()
        checks = report["checks"]
        if len(checks) == 1 and checks[0]["status"] == "not-comparable":
            self.skipTest("no Chromium available")
        failing = [c for c in checks if c["required"] and c["status"] == "differ"]
        self.assertEqual(report["summary"]["required_differ"], 0, failing)


if __name__ == "__main__":
    unittest.main()
