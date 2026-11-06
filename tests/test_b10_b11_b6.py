"""Amendment 09 backlog B10 / B11 / B6 (stdlib unittest; evidence in a temp dir through EvBase).

B10 `aidd rules close <id> --check`: dry run that runs the SAME gates as `rules close` and records nothing.
B11 `AIDD_FINGERPRINT_BUDGET`: seconds for `ev.code_state` in `cmd_verify` (default 8).
B6  spec-size warning at 300 000 chars in `aidd review` / `check_spec` (limit stays 400 000).
"""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_aidd_status as tas  # noqa: E402  (helpers only)

SCRIPTS_DIR = tas.SCRIPTS_DIR
import aidd_evidence as ev  # noqa: E402
import aidd_review  # noqa: E402
import aidd_status  # noqa: E402


class TestCloseCheck(tas.EvBase):
    """B10."""

    def project(self):
        return tas.TestRulesClose._approved_project(self)

    def ready(self, root, d):
        return tas.TestRulesClose._ready_to_close(self, root, d)

    def events_closed(self, root):
        return ev.events(root, kind="spec_closed")

    def test_unready_spec_lists_gaps_and_records_nothing(self):
        tmp, root, d = self.project()
        with tmp:
            r = tas.run_script("rules", "close", "001-x", "--check", cwd=root)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("FAIL R7", r.stdout)
            self.assertIn("would be REFUSED", r.stdout)
            self.assertEqual(self.events_closed(root), [])
            self.assertEqual(ev.open_specs(root), ["001-x"])

    def test_lists_gaps_and_the_missing_answer_together(self):
        tmp, root, d = self.project()
        with tmp:
            r = tas.run_script("rules", "close", "001-x", "--check", cwd=root)
            self.assertIn("FAIL R7", r.stdout)
            self.assertIn('"Yes, close"', r.stdout)

    def test_ready_without_answer_is_refused_and_names_the_answer(self):
        tmp, root, d = self.project()
        with tmp:
            self.ready(root, d)
            r = tas.run_script("rules", "close", "001-x", "--check", cwd=root)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn('"Yes, close"', r.stdout)
            self.assertNotIn("FAIL R7", r.stdout)

    def test_ready_with_answer_passes_without_closing_then_real_close_agrees(self):
        tmp, root, d = self.project()
        with tmp:
            self.ready(root, d)
            self.answer(root, "Close this spec? [spec:001-x]", "Yes, close")
            r = tas.run_script("rules", "close", "001-x", "--check", cwd=root)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("close --check: PASS", r.stdout)
            self.assertEqual(self.events_closed(root), [])          # dry run: nothing recorded
            self.assertEqual(ev.get_active_spec(root), "001-x")     # pointer untouched
            self.assertEqual(tas.run_script("rules", "close", "001-x", cwd=root).returncode, 0)
            self.assertEqual(len(self.events_closed(root)), 1)

    def test_check_and_close_exit_codes_agree_on_a_stale_close(self):
        tmp, root, d = self.project()
        with tmp:
            self.ready(root, d)
            self.answer(root, "Close this spec? [spec:001-x]", "Yes, close")
            tas.tick()
            ev.append(root, "s1", "code_edit", path="src/other.py", spec="002-other")   # after the auditors
            chk = tas.run_script("rules", "close", "001-x", "--check", cwd=root)
            real = tas.run_script("rules", "close", "001-x", cwd=root)
            self.assertEqual((chk.returncode, real.returncode), (1, 1))
            self.assertIn("R7", chk.stdout)
            self.assertIn("R7", real.stdout)

    def test_unknown_spec_exit_one(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(tas.run_script("rules", "close", "999-nope", "--check", cwd=t).returncode, 1)

    def test_via_aidd_cli(self):
        tmp, root, d = self.project()
        with tmp:
            env = dict(os.environ, PYTHONPATH=str(tas.REPO_ROOT), PYTHONIOENCODING="utf-8",
                       AIDD_HOME=str(tas.REPO_ROOT / "skill"))   # the repo scripts, not the installed skill
            r = subprocess.run([sys.executable, "-m", "aidd.cli", "rules", "close", "001-x", "--check"],
                               cwd=str(root), env=env, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("close --check", r.stdout)


class TestFingerprintBudget(tas.Spec007Base):
    """B11."""

    def test_budget_default_env_and_bad_values(self):
        os.environ.pop("AIDD_FINGERPRINT_BUDGET", None)
        self.assertEqual(aidd_status._fingerprint_budget(), 8.0)
        for raw, want in (("30", 30.0), ("0.5", 0.5), ("0", 8.0), ("-3", 8.0), ("abc", 8.0), ("", 8.0), ("inf", 8.0),
                          ("nan", 8.0)):
            with self.subTest(raw=raw):
                os.environ["AIDD_FINGERPRINT_BUDGET"] = raw
                self.assertEqual(aidd_status._fingerprint_budget(), want)

    def run_verify_with_refused_scan(self, env_value):
        tmp, root, d = tas.TestVerify.vproject(self, [("python src/check.py", "exit 0")])
        with tmp:
            if env_value is None:
                os.environ.pop("AIDD_FINGERPRINT_BUDGET", None)
            else:
                os.environ["AIDD_FINGERPRINT_BUDGET"] = env_value
            old = os.getcwd()
            os.chdir(root)
            buf = io.StringIO()
            try:
                with mock.patch.object(aidd_status.ev, "code_state", return_value=None) as m, \
                        contextlib.redirect_stdout(buf):
                    rc = aidd_status.cmd_verify("F23-eDoc-POS")
            finally:
                os.chdir(old)
            return rc, m.call_args, buf.getvalue()

    def test_cmd_verify_passes_the_default_budget(self):
        rc, call, out = self.run_verify_with_refused_scan(None)
        self.assertEqual(rc, 1)
        self.assertEqual(call.kwargs.get("budget_s"), 8.0)
        self.assertIn("cannot fingerprint", out)
        self.assertIn("AIDD_FINGERPRINT_BUDGET", out)       # the refusal names the knob

    def test_cmd_verify_passes_the_env_budget(self):
        rc, call, _out = self.run_verify_with_refused_scan("45")
        self.assertEqual(rc, 1)
        self.assertEqual(call.kwargs.get("budget_s"), 45.0)


class TestSpecSizeWarning(unittest.TestCase):
    """B6."""

    W, M = 1_500_000, 2_000_000     # amendment 10 FR-411 (was 300 000 / 400 000 before the measurement)

    def test_constants_and_band(self):
        W, M = self.W, self.M
        self.assertEqual(aidd_review.WARN_REVIEW_SOURCE_CHARS, W)
        self.assertEqual(aidd_review.MAX_REVIEW_SOURCE_CHARS, M)
        src = [("spec.md", "x" * W), ("plan.md", "x" * (W + 1)), ("tasks.md", "x" * M),
               ("mockup-audit.md", "x" * (M + 1)), ("contracts.md", None)]
        w = aidd_review.size_warnings(src)
        self.assertEqual(len(w), 2)                                  # plan.md and tasks.md only
        self.assertTrue(w[0].startswith(f"plan.md is {W + 1} chars"))
        self.assertIn("split the spec by amendment batches", w[0])
        self.assertTrue(w[1].startswith(f"tasks.md is {M} chars"))
        self.assertEqual(aidd_review.size_warnings([("spec.md", "x" * 1000)]), [])

    def test_limit_still_refuses(self):
        M = self.M
        self.assertEqual(aidd_review._oversize([("plan.md", "x" * (M + 1))]), [("plan.md", M + 1)])
        self.assertEqual(aidd_review._oversize([("plan.md", "x" * M)]), [])
        self.assertEqual(aidd_review._oversize([("tasks.md", "x" * 400_001)]), [])   # no forced split any more

    def test_aidd_review_main_warns_on_stderr_and_still_works(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "specs" / "001-x"
            d.mkdir(parents=True)
            (d / "spec.md").write_text("# s\n", encoding="utf-8")
            (d / "plan.md").write_text("x" * 1_600_000, encoding="utf-8")
            (d / "tasks.md").write_text("# t\n", encoding="utf-8")
            err, out = io.StringIO(), io.StringIO()
            with mock.patch.object(aidd_review, "generate", return_value=(d / "review.html", True)), \
                    contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
                rc = aidd_review.main([str(d)])
            self.assertEqual(rc, 0, err.getvalue())
            self.assertIn("warning: plan.md is 1600000 chars", err.getvalue())

    def test_aidd_review_main_silent_below_threshold(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "specs" / "001-x"
            d.mkdir(parents=True)
            (d / "plan.md").write_text("x" * 299_999, encoding="utf-8")
            err = io.StringIO()
            with mock.patch.object(aidd_review, "generate", return_value=(d / "review.html", True)), \
                    contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                aidd_review.main([str(d)])
            self.assertNotIn("chars (warning at", err.getvalue())

    def check_spec_out(self, plan_chars):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "001-x"
            d.mkdir()
            (d / "spec.md").write_text("# s\n", encoding="utf-8")
            (d / "plan.md").write_text("# plan\n" + "x" * plan_chars, encoding="utf-8")
            r = subprocess.run([sys.executable, str(SCRIPTS_DIR / "check_spec.py"), str(d)],
                               capture_output=True, text=True, encoding="utf-8")
            return r

    def test_check_spec_warns_without_changing_the_exit_code(self):
        small = self.check_spec_out(1000)
        big = self.check_spec_out(1_600_000)      # amendment 10 FR-411 band: 1 500 000 < n <= 2 000 000
        self.assertIn("WARNING: plan.md is", big.stdout)
        self.assertNotIn("WARNING: plan.md", small.stdout)
        self.assertEqual(big.returncode, small.returncode)


if __name__ == "__main__":
    unittest.main()
