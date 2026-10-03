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
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_aidd_status as tas  # noqa: E402  (helpers only; its test classes are not re-exported)


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


class TestCloseApprovedOnlySpec(tas.EvBase):
    """Spec 006 FR-005: a spec with an `approved` event but no recorded plan/tasks edit is open, so
    `aidd rules close` (through the real CLI) closes it once the user typed/answered "Yes, close"."""

    def aidd(self, *args, cwd):
        env = dict(os.environ, PYTHONPATH=str(REPO_ROOT), PYTHONIOENCODING="utf-8")   # EvBase set the evidence env
        return subprocess.run([sys.executable, "-m", "aidd.cli", *args], cwd=str(cwd), env=env,
                              capture_output=True, text=True, encoding="utf-8")

    def _approved_without_spec_edit(self):
        tmp, root, d = tas.make_project()
        self.prompt(root)
        self.answer(root, self.aq(d, "Approve these tasks?"), "Approve")
        r = tas.run_script("rules", "approve", str(d), cwd=root)
        self.assertEqual(r.returncode, 0, r.stdout)
        tas.backdate(d / "tasks.md", 50)
        self.assertEqual(tas.ev.events(root, kind="spec_edit"), [])        # the edit was never recorded
        return tmp, root, d

    def _ready(self, root, d):
        tas.tick()
        tas.ev.append(root, "s1", "code_edit", path="src/a.py", spec="001-x")
        tas.tick()
        for dom in ("functional", "security", "performance"):
            tas.tick()
            tas.ev.append(root, "s1", "subagent", type="x", desc=f"{dom} auditor", head="best practice")
        (d / "qa-audit.md").write_text("# qa\n", encoding="utf-8")

    def test_approved_only_spec_is_open_and_closes_with_the_recorded_answer(self):
        tmp, root, d = self._approved_without_spec_edit()
        with tmp:
            self.assertEqual(tas.ev.open_specs(root), ["001-x"])
            self._ready(root, d)
            self.answer(root, "Close this spec? [spec:001-x]", "Yes, close")
            r = self.aidd("rules", "close", "001-x", cwd=root)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("closed as completed", r.stdout)
            self.assertEqual(tas.ev.open_specs(root), [])
            self.assertEqual(tas.ev.events(root, kind="spec_closed")[-1]["detail"]["spec"], "001-x")

    def test_close_is_refused_without_the_answer_and_the_spec_stays_open(self):
        tmp, root, d = self._approved_without_spec_edit()
        with tmp:
            self._ready(root, d)
            r = self.aidd("rules", "close", "001-x", cwd=root)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertNotIn("not an open spec", r.stdout)                 # it IS open; the answer is missing
            self.assertEqual(tas.ev.open_specs(root), ["001-x"])

    def test_closed_spec_cannot_be_closed_twice(self):
        tmp, root, d = self._approved_without_spec_edit()
        with tmp:
            self._ready(root, d)
            self.answer(root, "Close this spec? [spec:001-x]", "Yes, close")
            self.assertEqual(self.aidd("rules", "close", "001-x", cwd=root).returncode, 0)
            r = self.aidd("rules", "close", "001-x", cwd=root)
            self.assertEqual(r.returncode, 1)
            self.assertIn("not an open spec", r.stdout)


if __name__ == "__main__":
    unittest.main()
