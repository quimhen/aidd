"""Tests for scripts/check_spec.py — stdlib unittest, no dependencies.

Run: python -m unittest discover -s tests -v
(from the repo root, or from tests/ with `python -m unittest test_check_spec -v`)
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import check_spec  # noqa: E402


class TestAllCodes(unittest.TestCase):
    def test_finds_every_code_family(self):
        text = "See SCREEN-01, SCREEN-02-F03, CTL-057, COMP-003, API-012, US-004."
        codes = check_spec.all_codes(text)
        self.assertEqual(
            codes,
            {"SCREEN-01", "SCREEN-02-F03", "CTL-057", "COMP-003", "API-012", "US-004"},
        )

    def test_no_false_positive_on_similar_text(self):
        text = "This is SCREENSHOT-01 and CONTROL-5, not real codes."
        self.assertEqual(check_spec.all_codes(text), set())


class TestTableRows(unittest.TestCase):
    def test_parses_rows_under_heading(self):
        md = (
            "## Mapping ledger\n"
            "| Code | Status |\n"
            "|---|---|\n"
            "| SCREEN-01 | OK |\n"
            "| SCREEN-02 | MISSING |\n"
        )
        rows = check_spec.table_rows(md, "Mapping ledger")
        self.assertEqual(rows, [["SCREEN-01", "OK"], ["SCREEN-02", "MISSING"]])

    def test_stops_at_next_section_with_no_table(self):
        md = "## Section A\nNo table here.\n## Section B\n| H |\n|---|\n| x |\n"
        self.assertEqual(check_spec.table_rows(md, "Section A"), [])

    def test_empty_text_returns_no_rows(self):
        self.assertEqual(check_spec.table_rows("", "Anything"), [])


class TestMainGapDetection(unittest.TestCase):
    """End-to-end: run check_spec.py's main() logic against a real temp spec folder."""

    def _run(self, spec_dir):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "check_spec.py"), str(spec_dir)],
            capture_output=True, text=True, timeout=10,
        )
        return result

    def test_clean_spec_exits_zero(self):
        with tempfile.TemporaryDirectory() as d:
            spec_dir = Path(d)
            (spec_dir / "mockup-audit.md").write_text(
                "## Screen inventory\n"
                "| SCREEN-XX | ... | Uses (COMP-nnn list) |\n"
                "|---|---|---|\n"
                "| SCREEN-01 | | |\n"
                "## Control inventory\n"
                "| CTL-nnn | Screen or COMP-nnn | ... | Status | PR/Spec ref |\n"
                "|---|---|---|---|---|\n"
                "| CTL-001 | SCREEN-01 | | Explicit | PR#1 |\n",
                encoding="utf-8",
            )
            (spec_dir / "tasks.md").write_text(
                "| Task | Codes satisfied | Target file | New view vs. reuse | Explicitly out of scope |\n"
                "|---|---|---|---|---|\n"
                "| T-01 | CTL-001 | login_page.dart | new view | everything else |\n",
                encoding="utf-8",
            )
            result = self._run(spec_dir)
            self.assertEqual(result.returncode, 0, msg=result.stdout)
            self.assertIn("No mechanical gaps found", result.stdout)

    def test_not_verified_rows_are_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            spec_dir = Path(d)
            (spec_dir / "mockup-audit.md").write_text(
                "## Control inventory\n"
                "| CTL-nnn | Screen | Status |\n"
                "|---|---|---|\n"
                "| CTL-001 | SCREEN-01 | [Not Verified] |\n"
                "| CTL-002 | SCREEN-01 | [Not Verified] |\n",
                encoding="utf-8",
            )
            result = self._run(spec_dir)
            self.assertEqual(result.returncode, 1)
            self.assertIn("2 row(s) still tagged [Not Verified]", result.stdout)

    def test_dangling_code_in_tasks_is_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            spec_dir = Path(d)
            (spec_dir / "mockup-audit.md").write_text(
                "## Control inventory\n| CTL-nnn |\n|---|\n| CTL-001 |\n",
                encoding="utf-8",
            )
            (spec_dir / "tasks.md").write_text(
                "References CTL-999 which was never audited.\n",
                encoding="utf-8",
            )
            result = self._run(spec_dir)
            self.assertEqual(result.returncode, 1)
            self.assertIn("CTL-999", result.stdout)

    def test_nonexistent_directory_is_a_usage_error(self):
        result = self._run(Path("/no/such/directory/at/all"))
        self.assertEqual(result.returncode, 2)

    def test_wrong_arg_count_prints_usage(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "check_spec.py")],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 2)


class TestHardRulesIntegration(unittest.TestCase):
    """check_spec.py reports the static aidd_rules violations as gaps (R1 ... -> fix)."""

    def _run(self, spec_dir):
        return subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "check_spec.py"), str(spec_dir)],
            capture_output=True, text=True, encoding="utf-8", timeout=20,
        )

    def test_spec_without_route_is_a_gap(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "spec.md").write_text("# spec\n\nNo route here.\n", encoding="utf-8")
            r = self._run(d)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("R2 ", r.stdout)
            self.assertIn("\u2192", r.stdout)

    def test_legacy_estimated_hours_tasks_is_a_gap(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "tasks.md").write_text(
                "# Tasks\n\n### T-01\n- Estimated hours: 4\n", encoding="utf-8")
            r = self._run(d)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("R1 ", r.stdout)

    def test_missing_approval_reported_for_structured_tasks(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "spec.md").write_text("# spec\n", encoding="utf-8")
            (Path(d) / "tasks.md").write_text("# Tasks\n\n## Waves\n", encoding="utf-8")
            r = self._run(d)
            self.assertIn("R6 ", r.stdout)

    def test_artifacts_that_do_not_exist_add_no_rule_gaps(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._run(d)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertNotIn("R2 ", r.stdout)


if __name__ == "__main__":
    unittest.main()
