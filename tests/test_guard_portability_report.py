"""Focused fixtures for the spec 009 T-23 portability reporter."""
import sys
from pathlib import Path
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import report_guard_portability as report


class FakeGuard:
    def __init__(self, result):
        self.result = result

    def decide(self, event):
        return self.result


class TestGuardPortabilityReport(unittest.TestCase):
    def test_compare_preserves_decisions_messages_and_desired(self):
        cases = [{"id": "protected", "path": "specs/x/tasks.md", "desired": "deny",
                  "event": {"tool_name": "Bash", "tool_input": {"command": "echo x > specs/x/tasks.md"}}},
                 {"id": "unrelated", "path": "docs/readme.md", "desired": "allow",
                  "event": {"tool_name": "Write", "tool_input": {"file_path": "docs/readme.md"}}}]
        rows = report.compare_cases(FakeGuard((True, "old reason")), FakeGuard((False, "current reason")), cases)
        self.assertEqual([row["id"] for row in rows], ["protected", "unrelated"])
        self.assertEqual(rows[0]["old"], (True, "old reason"))
        self.assertEqual(rows[0]["current"], (False, "current reason"))
        self.assertEqual(rows[0]["desired"], "deny")
        self.assertEqual(rows[1]["desired"], "allow")

    def test_collect_includes_native_foreign_and_unc_without_accessing_share(self):
        with tempfile.TemporaryDirectory() as tmp:
            cases = report.collect_cases(Path(tmp))
        values = [case["path"] for case in cases]
        self.assertTrue(any(path.startswith("D:/proj/specs/") for path in values))
        self.assertTrue(any(path.startswith("\\\\server\\share") for path in values))
        self.assertTrue(any(path.startswith("\\\\?\\UNC\\") for path in values))
        self.assertIn("deny", [case["desired"] for case in cases])
        self.assertIn("allow", [case["desired"] for case in cases])

    def test_loader_failure_is_reported_and_nonzero(self):
        with mock.patch.object(report, "load_old_guard", return_value=(None, "baseline missing")), \
             mock.patch("builtins.print") as printed:
            self.assertNotEqual(report.main(), 0)
        self.assertIn("baseline missing", str(printed.call_args_list))


if __name__ == "__main__":
    unittest.main()
