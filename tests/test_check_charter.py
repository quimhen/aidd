"""Tests for scripts/check_charter.py — stdlib unittest, no dependencies."""
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import check_charter as cc  # noqa: E402


class TestParseCheckableRules(unittest.TestCase):
    def test_parses_both_rule_types(self):
        md = (
            "## Checkable rules\n"
            "| Rule | Type | Pattern | Applies to (glob) |\n"
            "|---|---|---|---|\n"
            "| No console.log | forbidden | console\\.log\\( | src/**/*.js |\n"
            "| Has rate limit | required | rateLimit\\( | src/api/**/*.js |\n"
        )
        rules = cc.parse_checkable_rules(md)
        self.assertEqual(len(rules), 2)
        self.assertEqual(rules[0]["type"], "forbidden")
        self.assertEqual(rules[1]["type"], "required")

    def test_unknown_type_is_skipped_not_guessed(self):
        md = (
            "## Checkable rules\n"
            "| Rule | Type | Pattern | Applies to (glob) |\n"
            "|---|---|---|---|\n"
            "| Typo row | forbiden | x | src/**/*.js |\n"
        )
        self.assertEqual(cc.parse_checkable_rules(md), [])

    def test_empty_table_is_valid_empty_list(self):
        md = "## Checkable rules\n| Rule | Type | Pattern | Applies to (glob) |\n|---|---|---|---|\n"
        self.assertEqual(cc.parse_checkable_rules(md), [])


class TestExpandGlob(unittest.TestCase):
    def test_brace_expansion(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "src").mkdir()
            (root / "src" / "a.ts").write_text("x", encoding="utf-8")
            (root / "src" / "b.tsx").write_text("x", encoding="utf-8")
            (root / "src" / "c.py").write_text("x", encoding="utf-8")
            files = cc.expand_glob(root, "src/*.{ts,tsx}")
            names = {f.name for f in files}
            self.assertEqual(names, {"a.ts", "b.tsx"})

    def test_plain_glob_without_braces(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.md").write_text("x", encoding="utf-8")
            files = cc.expand_glob(root, "*.md")
            self.assertEqual([f.name for f in files], ["a.md"])


class TestCheckRule(unittest.TestCase):
    def test_forbidden_pattern_found_is_a_violation(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.js").write_text('console.log("x")\n', encoding="utf-8")
            rule = {"rule": "no console.log", "type": "forbidden", "pattern": r"console\.log\(", "glob": "*.js"}
            violations = cc.check_rule(root, rule)
            self.assertEqual(len(violations), 1)
            self.assertIn("a.js:1", violations[0])

    def test_forbidden_pattern_absent_passes(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.js").write_text('logger.debug("x")\n', encoding="utf-8")
            rule = {"rule": "no console.log", "type": "forbidden", "pattern": r"console\.log\(", "glob": "*.js"}
            self.assertEqual(cc.check_rule(root, rule), [])

    def test_required_pattern_present_somewhere_passes(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.js").write_text("rateLimit(100)\n", encoding="utf-8")
            (root / "b.js").write_text("no limit here\n", encoding="utf-8")
            rule = {"rule": "has rate limit", "type": "required", "pattern": r"rateLimit\(", "glob": "*.js"}
            self.assertEqual(cc.check_rule(root, rule), [])

    def test_required_pattern_missing_everywhere_is_a_violation(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.js").write_text("no limit here\n", encoding="utf-8")
            rule = {"rule": "has rate limit", "type": "required", "pattern": r"rateLimit\(", "glob": "*.js"}
            violations = cc.check_rule(root, rule)
            self.assertEqual(len(violations), 1)

    def test_required_with_no_matching_files_is_a_violation(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            rule = {"rule": "has rate limit", "type": "required", "pattern": r"rateLimit\(", "glob": "*.js"}
            violations = cc.check_rule(root, rule)
            self.assertEqual(len(violations), 1)
            self.assertIn("no files matched", violations[0])

    def test_invalid_regex_reported_not_crashed(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            rule = {"rule": "bad pattern", "type": "forbidden", "pattern": "(unclosed", "glob": "*.js"}
            violations = cc.check_rule(root, rule)
            self.assertEqual(len(violations), 1)
            self.assertIn("invalid regex", violations[0])


class TestEndToEnd(unittest.TestCase):
    def _run(self, cwd):
        return subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "check_charter.py"), str(cwd)],
            capture_output=True, text=True, timeout=10,
        )

    def test_no_charter_file_is_a_usage_error(self):
        with TemporaryDirectory() as d:
            result = self._run(d)
            self.assertEqual(result.returncode, 2)

    def test_clean_project_exits_zero(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "charter.md").write_text(
                "## Checkable rules\n| Rule | Type | Pattern | Applies to (glob) |\n|---|---|---|---|\n",
                encoding="utf-8",
            )
            result = self._run(root)
            self.assertEqual(result.returncode, 0)

    def test_violation_exits_one(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "charter.md").write_text(
                "## Checkable rules\n"
                "| Rule | Type | Pattern | Applies to (glob) |\n"
                "|---|---|---|---|\n"
                "| No console.log | forbidden | console\\.log\\( | *.js |\n",
                encoding="utf-8",
            )
            (root / "app.js").write_text('console.log("oops")\n', encoding="utf-8")
            result = self._run(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("app.js", result.stdout)


if __name__ == "__main__":
    unittest.main()
