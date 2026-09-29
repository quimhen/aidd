"""Tests for scripts/tasks_to_issues.py — stdlib unittest, no `gh` calls.

Anything that would actually create a GitHub issue is exercised only via the
dry-run CLI path (--apply is never passed here) — real issue creation is
deliberately left untested by an automated suite, the same way this script
itself defaults to a dry run rather than acting on external state silently.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import tasks_to_issues as t2i  # noqa: E402

TASKS_MD = """# Tasks — example

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | New view vs. reuse | Explicitly out of scope |
|---|---|---|---|---|
| T-01 | CTL-004 | session_provider.dart | reuse logic only | any other file |
| T-02 | CTL-007 | session_provider.dart | reuse logic only | any other file |

## Per-task detail (one block per row above)

### T-01
**Classify**
- Nature: `INCIDENT`
- Priority: 1 CRITICAL

### T-02
**Classify**
- Nature: `INCIDENT`
- Priority: 2 HIGH
"""


class TestParseTasks(unittest.TestCase):
    def test_extracts_every_task_row(self):
        tasks = t2i.parse_tasks(TASKS_MD)
        ids = [t["id"] for t in tasks]
        self.assertEqual(ids, ["T-01", "T-02"])

    def test_fields_match_columns(self):
        tasks = t2i.parse_tasks(TASKS_MD)
        t01 = tasks[0]
        self.assertEqual(t01["codes"], "CTL-004")
        self.assertEqual(t01["target_file"], "session_provider.dart")
        self.assertEqual(t01["scope_note"], "any other file")

    def test_no_task_table_yields_empty_list(self):
        self.assertEqual(t2i.parse_tasks("# Just a title\n\nNo table here.\n"), [])


class TestFindDetailSection(unittest.TestCase):
    def test_captures_only_that_tasks_own_block(self):
        detail = t2i.find_detail_section(TASKS_MD, "T-01")
        self.assertIn("CRITICAL", detail)
        self.assertNotIn("HIGH", detail)  # that's T-02's line, must not bleed in

    def test_missing_task_returns_empty_string(self):
        self.assertEqual(t2i.find_detail_section(TASKS_MD, "T-99"), "")


class TestSyncMap(unittest.TestCase):
    def test_round_trip(self):
        with TemporaryDirectory() as d:
            path = Path(d) / ".aidd-issues.json"
            data = {"T-01": "https://github.com/x/y/issues/1"}
            t2i.save_sync_map(path, data)
            self.assertEqual(t2i.load_sync_map(path), data)

    def test_missing_file_is_empty_map_not_an_error(self):
        with TemporaryDirectory() as d:
            self.assertEqual(t2i.load_sync_map(Path(d) / "nope.json"), {})

    def test_corrupt_file_is_empty_map_not_a_crash(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "bad.json"
            path.write_text("{not json", encoding="utf-8")
            self.assertEqual(t2i.load_sync_map(path), {})


class TestDryRunCLI(unittest.TestCase):
    """No --apply here on purpose — this must never touch a real GitHub repo."""

    def test_dry_run_lists_tasks_and_creates_nothing(self):
        with TemporaryDirectory() as d:
            tasks_md = Path(d) / "tasks.md"
            tasks_md.write_text(TASKS_MD, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "tasks_to_issues.py"), str(tasks_md)],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("T-01", result.stdout)
            self.assertIn("T-02", result.stdout)
            self.assertIn("Dry run", result.stdout)
            self.assertFalse((Path(d) / ".aidd-issues.json").exists())

    def test_already_synced_task_is_skipped_in_output(self):
        with TemporaryDirectory() as d:
            tasks_md = Path(d) / "tasks.md"
            tasks_md.write_text(TASKS_MD, encoding="utf-8")
            (Path(d) / ".aidd-issues.json").write_text(
                json.dumps({"T-01": "https://github.com/x/y/issues/1"}), encoding="utf-8"
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "tasks_to_issues.py"), str(tasks_md)],
                capture_output=True, text=True, timeout=10,
            )
            self.assertIn("already synced", result.stdout)
            self.assertIn("T-02", result.stdout)

    def test_missing_file_is_a_usage_error(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "tasks_to_issues.py"), "/no/such/tasks.md"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
