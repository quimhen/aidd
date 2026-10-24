"""Spec 012 (T-03): `aidd guard commit|push` (skill/scripts/aidd_guard.py).

Contract tested here (FR-1202, FR-1203, FR-1207, FR-1208, AC-1201, AC-1202, AC-1207):
  * staged_files(root), is_code_file(rel), evaluate(root, files, status=None) -> [{rule, message, fix}],
    main(argv) with `guard commit|push [--root DIR]`;
  * commit blocks (exit 1) only for R5/R6, a failed verification, a stale one when code is staged, or a FAIL row
    in qa-audit.md, and only when a code file is staged; R4/R7/R10/R11/R12 never block;
  * push never blocks; AIDD_GUARD=warn|off is honoured and recorded as `guard_override`;
  * 0 and 5,000 staged files; internal errors fail open.

Real temp dirs and real scratch git repos, no network. Run: python -m unittest tests.test_aidd_guard -v
"""
import contextlib
import io
import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gate_fixtures import Base, REPO, approved_tasks, tasks_text, verified_spec  # noqa: E402
import aidd_evidence as EV  # noqa: E402

sys.path.insert(0, str(REPO / "skill" / "scripts"))
import aidd_guard  # noqa: E402

HAVE_GIT = shutil.which("git") is not None


def git(root, *args):
    r = subprocess.run(["git", *args], cwd=str(root), capture_output=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"git {args} failed: {r.stderr.decode(errors='replace')}")
    return r.stdout.decode(errors="replace")


def rules_of(findings):
    return {f["rule"] for f in findings}


def fake_status(approval="valid", verification="passed", why=()):
    return {"spec": "001-x", "open": True,
            "tasks": {"approval": approval, "approval_recorded": approval == "valid"},
            "verification": {"declared": True, "commands": 1, "status": verification, "ts": None},
            "why_blocked": list(why)}


class GuardBase(Base):
    """A scratch git repo (self.root) with an open spec 001-x as the gate target and its tasks.md."""

    def setUp(self):
        super().setUp()
        if not HAVE_GIT:
            self.skipTest("git is not available")
        self._old_guard = os.environ.pop("AIDD_GUARD", None)
        git(self.root, "init", "-q")
        (self.sd / "spec.md").write_text(verified_spec(), encoding="utf-8")
        (self.sd / "tasks.md").write_text(tasks_text(), encoding="utf-8")
        (self.sd / "plan.md").write_text("# plan\n", encoding="utf-8")
        self.open_spec()
        self.assertTrue(EV.activate_spec(self.root, self.SPEC, by="test"))

    def tearDown(self):
        if self._old_guard is not None:
            os.environ["AIDD_GUARD"] = self._old_guard
        else:
            os.environ.pop("AIDD_GUARD", None)
        super().tearDown()

    # -- helpers -----------------------------------------------------------
    def stage(self, *rels, text="x = 1\n"):
        for rel in rels:
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists():
                p.write_text(text, encoding="utf-8")
        git(self.root, "add", "--", *rels)

    def approve(self):
        t = approved_tasks()
        (self.sd / "tasks.md").write_text(t, encoding="utf-8")
        self.approve_spec(text=t)

    def guard(self, mode="commit", env=None, root=None):
        """Run main(['guard', mode, '--root', root]); returns (exit code, combined stdout+stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, env or {}), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                rc = aidd_guard.main(["guard", mode, "--root", str(root or self.root)])
            except SystemExit as e:
                rc = e.code
        return (0 if rc is None else rc), out.getvalue() + err.getvalue()

    def overrides(self):
        return [e for e in self.events("guard_override")]


class TestIsCodeFileAndStaged(GuardBase):
    def test_code_files(self):
        for rel in ("src/app.py", "app.js", "lib/x.cs", "Makefile", "config.json", "a/b/c.sql"):
            with self.subTest(rel=rel):
                self.assertTrue(aidd_guard.is_code_file(rel))

    def test_non_code_files(self):
        for rel in ("README.md", "notes.txt", "events.toon", "specs/001-x/tasks.md", "specs/001-x/evidence/a.json",
                    "docs/guide.html", ".aidd/scripts/aidd_guard.py", ".agents/hooks.json",
                    ".opencode/plugins/aidd.js", ".gemini/settings.json", "LICENSE"):
            with self.subTest(rel=rel):
                self.assertFalse(aidd_guard.is_code_file(rel))

    def test_staged_files_lists_only_staged_names(self):
        self.stage("src/app.py", "docs/a.md")
        (self.root / "src" / "other.py").write_text("y = 2\n", encoding="utf-8")   # untracked, not staged
        got = [g.replace("\\", "/") for g in aidd_guard.staged_files(self.root)]
        self.assertEqual(sorted(got), ["docs/a.md", "src/app.py"])

    def test_staged_files_empty(self):
        self.assertEqual(aidd_guard.staged_files(self.root), [])


class TestCommitApproval(GuardBase):
    """AC-1202: unapproved open spec + staged code blocks with R6 and `aidd review <spec>`; approval unblocks."""

    def test_unapproved_spec_with_code_blocks_with_r6_and_review_command(self):
        self.stage("src/app.py")
        rc, text = self.guard("commit")
        self.assertEqual(rc, 1, text)
        self.assertIn("R6", text)
        self.assertIn(f"aidd review {self.SPEC}", text)

    def test_evaluate_reports_r6_with_fix(self):
        fs = aidd_guard.evaluate(self.root, ["src/app.py"])
        r6 = [f for f in fs if f["rule"] == "R6"]
        self.assertTrue(r6, fs)
        self.assertIn(f"aidd review {self.SPEC}", r6[0]["fix"] + r6[0]["message"])
        for f in fs:
            self.assertEqual({"rule", "message", "fix"}, set(f) & {"rule", "message", "fix"})

    def test_same_commit_passes_after_approval(self):
        self.stage("src/app.py")
        self.assertEqual(self.guard("commit")[0], 1)
        self.approve()
        rc, text = self.guard("commit")
        self.assertEqual(rc, 0, text)
        self.assertNotIn("R6", rules_of(aidd_guard.evaluate(self.root, ["src/app.py"])))

    def test_docs_and_specs_only_commit_passes_even_unapproved(self):
        self.stage("docs/readme.md", f"specs/{self.SPEC}/notes.md", "CHANGELOG.md")
        rc, text = self.guard("commit")
        self.assertEqual(rc, 0, text)

    def test_evaluate_ignores_non_code_files(self):
        self.assertEqual(aidd_guard.evaluate(self.root, ["docs/a.md", f"specs/{self.SPEC}/tasks.md"]), [])


class TestCommitOtherFindings(GuardBase):
    def test_qa_audit_fail_row_blocks_ac1201(self):
        self.approve()
        (self.sd / "qa-audit.md").write_text(
            "# QA audit\n\n## Verdict\n\n| Code | Verdict |\n|---|---|\n| SCREEN-01 | FAIL |\n", encoding="utf-8")
        self.stage("src/app.py")
        rc, text = self.guard("commit")
        self.assertEqual(rc, 1, text)
        self.assertIn("qa-audit", text.lower())

    def test_qa_audit_fail_does_not_block_a_specs_only_commit(self):
        self.approve()
        (self.sd / "qa-audit.md").write_text("# QA audit\n\n| Code | Verdict |\n|---|---|\n| S05 | fail |\n",
                                             encoding="utf-8")
        self.stage(f"specs/{self.SPEC}/qa-audit.md")
        self.assertEqual(self.guard("commit")[0], 0)

    def test_failed_verification_blocks(self):
        fs = aidd_guard.evaluate(self.root, ["src/app.py"], status=fake_status(verification="failed"))
        self.assertTrue(fs, "a failed verification must be a finding")
        self.assertIn("verif", " ".join(f["message"] + f["fix"] for f in fs).lower())

    def test_stale_verification_blocks_when_code_is_staged(self):
        fs = aidd_guard.evaluate(self.root, ["src/app.py"], status=fake_status(verification="stale"))
        self.assertTrue(fs, "stale verification with staged code must be a finding")

    def test_stale_verification_does_not_block_when_no_code_is_staged(self):
        fs = aidd_guard.evaluate(self.root, ["docs/a.md"], status=fake_status(verification="stale"))
        self.assertEqual(fs, [])

    def test_passed_and_never_run_verification_do_not_block(self):
        for v in ("passed", "never-run", "none"):
            with self.subTest(v=v):
                self.assertEqual(aidd_guard.evaluate(self.root, ["src/app.py"], status=fake_status(verification=v)), [])

    def test_r4_r7_r10_r11_r12_never_block(self):
        why = [f"{r} something is wrong → fix it" for r in ("R4", "R7", "R10", "R11", "R12")]
        fs = aidd_guard.evaluate(self.root, ["src/app.py"], status=fake_status(why=why))
        self.assertFalse(rules_of(fs) & {"R4", "R7", "R10", "R11", "R12"}, fs)
        self.assertEqual(fs, [])

    def test_r5_and_r6_in_why_blocked_do_block(self):
        why = ["R5 plan.md is newer than tasks.md → redo"]
        fs = aidd_guard.evaluate(self.root, ["src/app.py"], status=fake_status(approval="pending", why=why))
        self.assertTrue({"R5", "R6"} <= rules_of(fs), fs)

    def test_approved_spec_with_open_non_blocking_rules_commits(self):
        self.approve()
        self.stage("src/app.py")
        rc, text = self.guard("commit")
        self.assertEqual(rc, 0, text)

    def test_no_open_spec_with_code_staged_passes_with_one_warning(self):
        (self.root / ".aidd" / "gate_spec").unlink()
        self.close_spec()
        self.stage("src/app.py")
        rc, text = self.guard("commit")
        self.assertEqual(rc, 0, text)
        lines = [ln for ln in text.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, text)
        self.assertIn("warn", lines[0].lower())


class TestPush(GuardBase):
    def test_push_never_blocks_but_prints_the_same_findings(self):
        ident = ("-c", "user.email=t@example.com", "-c", "user.name=t")
        self.stage("docs/base.md")                    # a parent commit, so the pushed range is not a root commit
        git(self.root, *ident, "commit", "-q", "-m", "base")
        self.stage("src/app.py")
        crc, ctext = self.guard("commit")
        git(self.root, "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", "x")
        prc, ptext = self.guard("push")
        self.assertEqual(crc, 1, ctext)
        self.assertEqual(prc, 0, ptext)
        self.assertIn("R6", ptext)
        self.assertIn(f"aidd review {self.SPEC}", ptext)
        self.assertIn("warn", ptext.lower())

    def test_push_with_nothing_wrong_exits_zero(self):
        self.approve()
        self.stage("src/app.py")
        self.assertEqual(self.guard("push")[0], 0)


class TestOverride(GuardBase):
    """FR-1207: AIDD_GUARD=warn|off honoured and recorded as guard_override {hook, mode, rules}."""

    def test_warn_turns_the_block_into_a_warning_and_records_it(self):
        self.stage("src/app.py")
        rc, text = self.guard("commit", env={"AIDD_GUARD": "warn"})
        self.assertEqual(rc, 0, text)
        self.assertIn("R6", text)
        evs = self.overrides()
        self.assertEqual(len(evs), 1, evs)
        d = evs[0]["detail"]
        self.assertEqual(d.get("hook"), "guard")
        self.assertEqual(d.get("mode"), "warn")
        self.assertIn("R6", d.get("rules") or [])

    def test_off_disables_the_guard_and_records_it(self):
        self.stage("src/app.py")
        rc, text = self.guard("commit", env={"AIDD_GUARD": "off"})
        self.assertEqual(rc, 0, text)
        evs = self.overrides()
        self.assertEqual(len(evs), 1, evs)
        self.assertEqual(evs[0]["detail"].get("mode"), "off")
        self.assertEqual(evs[0]["detail"].get("hook"), "guard")

    def test_no_override_event_without_the_variable(self):
        self.stage("src/app.py")
        self.guard("commit")
        self.assertEqual(self.overrides(), [])

    def test_no_override_event_when_nothing_would_block(self):
        self.stage("docs/a.md")
        self.guard("commit", env={"AIDD_GUARD": "warn"})
        self.assertEqual(self.overrides(), [])

    def test_unknown_value_is_ignored(self):
        self.stage("src/app.py")
        rc, text = self.guard("commit", env={"AIDD_GUARD": "banana"})
        self.assertEqual(rc, 1, text)
        self.assertEqual(self.overrides(), [])


class TestSizeAndSpeed(GuardBase):
    """AC-1207 and FR-1208."""

    def test_zero_staged_files_passes_immediately(self):
        t = time.perf_counter()
        rc, text = self.guard("commit")
        self.assertEqual(rc, 0, text)
        self.assertLess(time.perf_counter() - t, 3.0)
        self.assertEqual(aidd_guard.evaluate(self.root, []), [])

    def test_5000_staged_files_answer_under_3_seconds(self):
        for i in range(30):                                   # 30 open specs, only 001-x is the gate target
            d = self.root / "specs" / f"{i + 2:03d}-s"
            d.mkdir(parents=True)
            (d / "spec.md").write_text(verified_spec(), encoding="utf-8")
            (d / "tasks.md").write_text(tasks_text(), encoding="utf-8")
        for i in range(1500):                                 # a realistic events log
            EV.append(self.root, self.session, "code_edit", path=f"src/gen/f{i}.py")
        names = []
        for i in range(5000):
            p = self.root / "src" / "gen" / f"d{i % 50}" / f"f{i}.py"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f"v = {i}\n", encoding="utf-8")
            names.append(p.relative_to(self.root).as_posix())
        git(self.root, "add", "--", "src/gen")
        self.assertEqual(len(aidd_guard.staged_files(self.root)), 5000)
        t = time.perf_counter()
        rc, text = self.guard("commit")
        dt = time.perf_counter() - t
        self.assertEqual(rc, 1, text)                         # unapproved spec + code: still decided correctly
        self.assertIn("R6", text)
        self.assertLess(dt, 3.0, f"guard commit with 5,000 staged files took {dt:.2f}s")
        t = time.perf_counter()
        aidd_guard.evaluate(self.root, names)
        self.assertLess(time.perf_counter() - t, 3.0)


TARGET_HEAD = ("| Task | Codes | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |\n"
               "|---|---|---|---|---|---|---|\n")


class TestOwnerMap(GuardBase):
    """Amendment 1 (AC-1208): the specs owning the staged paths (tasks.md Target file cells) are evaluated; the
    gate target is only the fallback; the guard never calls aidd_status.build_status."""

    def add_spec(self, spec, cells, void=True, qa_fail=True):
        d = self.root / "specs" / spec
        d.mkdir(parents=True, exist_ok=True)
        rows = "".join(f"| T-{i + 1:02d} | COMP-001 | {c} | logic | - | todo | - |\n" for i, c in enumerate(cells))
        t = tasks_text().replace("# Tasks — x\n", "# Tasks — x\n\n" + TARGET_HEAD + rows, 1)
        if void:
            t = t.replace("Approved: PENDING", "Approved: 2026-10-01 hash:000000000000")
        (d / "spec.md").write_text(verified_spec(), encoding="utf-8")
        (d / "tasks.md").write_text(t, encoding="utf-8")
        if qa_fail:
            (d / "qa-audit.md").write_text(
                "# QA audit\n\n## Verdict\n\n| Code | Verdict |\n|---|---|\n| S01 | FAIL |\n| S02 | FAIL |\n",
                encoding="utf-8")
        self.open_spec(spec)
        return d

    def test_staged_target_file_of_another_spec_blocks_naming_it(self):
        self.approve()                                       # the gate target 001-x is clean
        self.add_spec("002-y", ["src/owned.py"])
        self.stage("src/owned.py")
        rc, text = self.guard("commit")
        self.assertEqual(rc, 1, text)
        self.assertIn("002-y", text)
        self.assertIn("R6", text)
        self.assertIn("qa-audit", text.lower())
        self.assertIn("aidd review 002-y", text)

    def test_unowned_code_falls_back_to_the_gate_target(self):
        self.add_spec("002-y", ["src/owned.py"])
        self.stage("src/free.py")
        rc, text = self.guard("commit")
        self.assertEqual(rc, 1, text)                        # 001-x (gate target) is unapproved
        self.assertIn(self.SPEC, text)

    def test_two_owning_specs_are_both_reported(self):
        self.approve()
        self.add_spec("002-y", ["src/a2.py"])
        self.add_spec("003-z", ["src/b3.py"])
        self.stage("src/a2.py", "src/b3.py")
        rc, text = self.guard("commit")
        self.assertEqual(rc, 1, text)
        self.assertIn("002-y", text)
        self.assertIn("003-z", text)

    def test_target_cell_note_and_comma_list_still_map(self):
        self.approve()
        self.add_spec("002-y", ["src/c.py (same owner as T-01)"])
        self.add_spec("003-z", ["src/a.py, src/b.py"])
        self.stage("src/c.py")
        rc, text = self.guard("commit")
        self.assertEqual(rc, 1, text)
        self.assertIn("002-y", text)
        self.assertNotIn("003-z", text)
        git(self.root, "reset", "-q")
        self.stage("src/b.py")
        rc, text = self.guard("commit")
        self.assertEqual(rc, 1, text)
        self.assertIn("003-z", text)
        self.assertNotIn("002-y", text)

    def test_owning_spec_with_pending_approval_is_reported_not_skipped(self):
        self.approve()
        self.add_spec("002-y", ["src/owned.py"], void=False, qa_fail=False)
        self.stage("src/owned.py")
        rc, text = self.guard("commit")
        self.assertEqual(rc, 1, text)
        self.assertIn("002-y", text)

    def test_guard_works_with_build_status_raising(self):
        import aidd_status
        self.approve()
        self.add_spec("002-y", ["src/owned.py"])
        self.stage("src/owned.py")
        with mock.patch.object(aidd_status, "build_status", side_effect=AssertionError("build_status called")):
            rc, text = self.guard("commit")
        self.assertEqual(rc, 1, text)
        self.assertIn("002-y", text)
        self.assertNotIn("build_status called", text)

    def test_70_specs_and_a_2mb_events_log_under_3_seconds(self):
        self.approve()
        for i in range(70):
            self.add_spec(f"{i + 10:03d}-s", [f"src/own{i}.py"], qa_fail=(i == 69))
        for i in range(70):
            (self.root / "src" / f"own{i}.py").write_text("v = 1\n", encoding="utf-8")
        big = "p" * 1200

        def log_bytes():
            return sum(f.stat().st_size for f in self.evdir.rglob("*") if f.is_file())
        n = 0
        while log_bytes() < 2_000_000 and n < 6000:
            for _ in range(200):
                EV.append(self.root, self.session, "code_edit", path=f"src/gen/f{n}.py", note=big)
                n += 1
        for i in range(2000):
            p = self.root / "src" / "gen" / f"d{i % 40}" / f"f{i}.py"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f"v = {i}\n", encoding="utf-8")
        self.stage("src/gen", "src/own69.py")
        t = time.perf_counter()
        rc, text = self.guard("commit")
        dt = time.perf_counter() - t
        self.assertEqual(rc, 1, text)
        self.assertIn("079-s", text)
        self.assertLess(dt, 3.0, f"guard commit with 70 specs and a {log_bytes()}-byte log took {dt:.2f}s")


class TestFailOpen(GuardBase):
    def test_internal_error_in_evaluate_fails_open(self):
        self.stage("src/app.py")
        # Amendment 1: main no longer calls evaluate(); it goes through the owner map (`_owning_specs`).
        with mock.patch.object(aidd_guard, "_owning_specs", side_effect=RuntimeError("boom")):
            rc, text = self.guard("commit")
        self.assertEqual(rc, 0, text)
        self.assertNotIn("Traceback", text)

    def test_internal_error_in_staged_files_fails_open(self):
        with mock.patch.object(aidd_guard, "staged_files", side_effect=OSError("git vanished")):
            rc, text = self.guard("commit")
        self.assertEqual(rc, 0, text)
        self.assertNotIn("Traceback", text)

    def test_not_a_git_repo_fails_open(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            rc, text = self.guard("commit", root=d)
        self.assertEqual(rc, 0, text)


if __name__ == "__main__":
    unittest.main()
