"""`aidd status` / `aidd rules` must be pure passthroughs to aidd_status.py: options that come
BEFORE the subcommand or spec dir work, and exit codes are forwarded. The evidence log lives in a
temp dir (AIDD_EVIDENCE_DIR) so no test writes <repo>/.aidd."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestAiddRulesCli(unittest.TestCase):
    def setUp(self):
        self._ev = tempfile.TemporaryDirectory()
        self.addCleanup(self._ev.cleanup)

    def aidd(self, *args, cwd=None):
        env = dict(os.environ, PYTHONPATH=str(REPO_ROOT), PYTHONIOENCODING="utf-8",
                   AIDD_EVIDENCE_DIR=self._ev.name, AIDD_TESTING="1")
        return subprocess.run([sys.executable, "-m", "aidd.cli", *args], cwd=str(cwd or REPO_ROOT), env=env,
                              capture_output=True, text=True, encoding="utf-8")

    def test_leading_option_is_forwarded(self):
        with tempfile.TemporaryDirectory() as t:
            r = self.aidd("status", "--json", cwd=t)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_status_exit_zero_without_specs(self):
        with tempfile.TemporaryDirectory() as t:
            r = self.aidd("status", cwd=t)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertNotIn("Traceback", r.stderr)

    def test_rules_usage_errors_exit_two(self):
        self.assertEqual(self.aidd("rules").returncode, 2)
        self.assertEqual(self.aidd("rules", "bogus", "x").returncode, 2)
        self.assertEqual(self.aidd("rules", "check").returncode, 2)
        self.assertEqual(self.aidd("rules", "abandon").returncode, 2)

    def test_rules_check_exit_one_on_violation(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "specs" / "001-y"
            d.mkdir(parents=True)
            (d / "spec.md").write_text("# spec without route\n", encoding="utf-8")
            r = self.aidd("rules", "check", str(d), cwd=t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("FAIL R2", r.stdout)

    def test_rules_close_and_abandon_unknown_spec_exit_one(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(self.aidd("rules", "close", "000-none", cwd=t).returncode, 1)
            self.assertEqual(self.aidd("rules", "abandon", "000-none", cwd=t).returncode, 1)

    def test_rules_approve_refused_without_answer(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "specs" / "001-y"
            d.mkdir(parents=True)
            (d / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
            r = self.aidd("rules", "approve", str(d), cwd=t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertNotIn("Approved:", (d / "tasks.md").read_text(encoding="utf-8"))

    def test_top_level_help_lists_commands(self):
        r = self.aidd("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("status", r.stdout)
        self.assertIn("rules", r.stdout)


if __name__ == "__main__":
    unittest.main()
