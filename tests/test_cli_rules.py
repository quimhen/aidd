"""`aidd status` / `aidd rules` must be pure passthroughs to aidd_status.py: options that come
BEFORE the subcommand or spec dir work, and exit codes are forwarded. The evidence log lives in a
temp dir (AIDD_EVIDENCE_DIR) so no test writes <repo>/.aidd."""
import json
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
        """Approved through the real CLI, then the `approved` event is rewritten as a pre-007 one (no
        `gate`): these cases cover the LEGACY close path (spec 007 AC-208)."""
        tmp, root, d = tas.make_project()
        self.prompt(root)
        self.answer(root, self.aq(d, "Approve these tasks?"), "Approve")
        r = tas.run_script("rules", "approve", str(d), cwd=root)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(tas.ev.latest_approved(root, "001-x").get("gate"), 2)
        tas.tick()
        tas.ev.append_approved(root, "s1", "001-x", tas.aidd_rules.approval_hash(
            (d / "tasks.md").read_text(encoding="utf-8")))                   # newest approval: legacy shape
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
            self.assertEqual(tas.ev.open_specs(root), [])                  # FR-009: no obligation for the gates
            self.assertEqual(tas.ev.open_specs(root, include_approved=True), ["001-x"])   # closable when named
            self._ready(root, d)
            self.answer(root, "Close this spec? [spec:001-x]", "Yes, close")
            r = self.aidd("rules", "close", "001-x", cwd=root)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("closed as completed", r.stdout)
            self.assertEqual(tas.ev.open_specs(root, include_approved=True), [])
            self.assertEqual(tas.ev.events(root, kind="spec_closed")[-1]["detail"]["spec"], "001-x")

    def test_close_is_refused_without_the_answer_and_the_spec_stays_open(self):
        tmp, root, d = self._approved_without_spec_edit()
        with tmp:
            self._ready(root, d)
            r = self.aidd("rules", "close", "001-x", cwd=root)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertNotIn("not an open spec", r.stdout)                 # it IS closable; the answer is missing
            self.assertEqual(tas.ev.open_specs(root, include_approved=True), ["001-x"])

    def test_approved_only_spec_abandons_when_named_with_the_recorded_answer(self):
        """FR-009 (c): `aidd rules abandon <id>` abandons a legacy approved-only spec once the user answered."""
        tmp, root, d = self._approved_without_spec_edit()
        with tmp:
            self.answer(root, "Abandon this spec? [spec:001-x]", "Abandon")
            r = self.aidd("rules", "abandon", "001-x", cwd=root)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("abandoned", r.stdout)
            self.assertEqual(tas.ev.open_specs(root, include_approved=True), [])
            last = tas.ev.events(root, kind="spec_closed")[-1]["detail"]
            self.assertEqual((last["spec"], last["reason"]), ("001-x", "abandoned"))

    def test_legacy_approved_spec_is_not_listed_but_named_status_reports_it_open(self):
        """FR-009 (a)/(e): unrelated code edits never list a legacy approved spec as open; naming it does."""
        tmp, root, d = self._approved_without_spec_edit()
        with tmp:
            for i in range(30):
                tas.ev.append(root, "s1", "code_edit", path=f"src/f{i}.py", spec="001-x")
            r = self.aidd("status", "--json", cwd=root)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(json.loads(r.stdout)["open_specs"], [])
            r = self.aidd("status", str(d), "--json", cwd=root)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue(json.loads(r.stdout)["open"])

    def test_closed_spec_cannot_be_closed_twice(self):
        tmp, root, d = self._approved_without_spec_edit()
        with tmp:
            self._ready(root, d)
            self.answer(root, "Close this spec? [spec:001-x]", "Yes, close")
            self.assertEqual(self.aidd("rules", "close", "001-x", cwd=root).returncode, 0)
            r = self.aidd("rules", "close", "001-x", cwd=root)
            self.assertEqual(r.returncode, 1)
            self.assertIn("not an open spec", r.stdout)


class TestSpec007ThroughCli(tas.Spec007Base):
    """Spec 007: `aidd verify`, `aidd rules activate` and `aidd status --refresh` through the real CLI
    (aidd/cli.py forwards to aidd_status.py) with numeric and non-numeric ids, relative and absolute."""

    def aidd(self, *args, cwd):
        env = dict(os.environ, PYTHONPATH=str(REPO_ROOT), PYTHONIOENCODING="utf-8")
        return subprocess.run([sys.executable, "-m", "aidd.cli", *args], cwd=str(cwd), env=env,
                              capture_output=True, text=True, encoding="utf-8")

    def test_activate_verify_and_refresh(self):
        for sid in tas.IDS:
            for form in ("id", "relative", "absolute"):
                with self.subTest(sid=sid, form=form):
                    tmp, root, d = self.project(sid)
                    with tmp:
                        arg = {"id": sid, "relative": f"specs/{sid}", "absolute": str(d)}[form]
                        r = self.aidd("rules", "activate", arg, cwd=root)
                        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                        self.assertEqual(tas.ev.get_gate_spec(root), sid)
                        r = self.aidd("verify", arg, cwd=root)
                        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                        self.assertTrue((d / "evidence" / "verify-1.txt").is_file())
                        self.assertTrue(tas.ev.latest_verify_run(root, sid)["ok"])
                        r = self.aidd("status", "--refresh", cwd=root)
                        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                        self.assertIn(f"gate pointer: {sid}", r.stdout)
                        self.assertIn("verification passed (1 command(s))", r.stdout)

    def test_cli_exit_codes_are_forwarded(self):
        tmp, root, d = self.project("F23-eDoc-POS", spec=tas.spec_with_rows([("python src/billing.py", "exit 0")]))
        with tmp:
            self.assertEqual(self.aidd("verify", "F23-eDoc-POS", cwd=root).returncode, 1)   # output too short
            self.assertEqual(self.aidd("rules", "activate", "999-none", cwd=root).returncode, 1)
            self.assertEqual(self.aidd("verify", "999-none", cwd=root).returncode, 1)


if __name__ == "__main__":
    unittest.main()
