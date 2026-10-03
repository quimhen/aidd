"""Tests for skill/hooks/stop_gate.py (rule R8, Rev 1: M7 / M10 / B1). Real hook as a subprocess against synthetic
projects; AIDD_EVIDENCE_DIR points at a scratch dir (gate_fixtures.Base).

Run: python -m unittest tests.test_stop_gate -v
"""
import io
import json
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gate_fixtures import Base, EV, R, approved_tasks, tasks_text  # noqa: E402
import stop_gate  # noqa: E402

TASKS = "specs/001-x/tasks.md"
QA = "specs/001-x/qa-audit.md"


class StopBase(Base):
    def stop(self, env=None, session=None, **extra):
        ev = {"session_id": session or self.session, "cwd": str(self.root), "hook_event_name": "Stop"}
        ev.update(extra)
        return self.run_hook("stop_gate.py", ev, env=env)

    def approved_event(self, tasks=None):
        t = tasks if tasks is not None else approved_tasks()
        self.ev("approved", spec="001-x", hash=R.approval_hash(t))

    def implemented(self, tasks=None):
        """Open spec with approved tasks, the recorded approval, then one code edit after it."""
        t = tasks if tasks is not None else approved_tasks()
        self.put(TASKS, t, age=100)
        self.open_spec()
        self.approved_event(t)
        self.ev("code_edit", path="src/app.py", spec="001-x")

    def close_audits(self):
        """FR-002: one DISTINCT auditor per required domain (approved_tasks cites COMP-001 => ui + performance,
        plus security and functional, which are always required)."""
        self.subagent("Perf", "performance review")
        self.subagent("UI", "mockup check")
        self.subagent("Security", "security review")
        self.subagent("Functional", "functional acceptance review")


class TestR8(StopBase):
    def test_blocks_with_checklist_when_unaudited(self):
        self.implemented()
        r = self.stop()
        self.assertEqual(r.returncode, 2, r.err)
        for needle in ("R8", "qa-audit.md", "performance", "ui", "[ ]", "block 1 of 3"):
            self.assertIn(needle, r.err)
        self.assertNotIn("Traceback", r.err)

    def test_allows_when_closed_properly(self):
        self.implemented()
        self.put(QA, "# qa")
        self.close_audits()
        r = self.stop()
        self.assertEqual(r.returncode, 0, r.err)

    def test_qa_audit_written_but_domain_uncovered_still_blocks(self):
        self.implemented()
        self.put(QA, "# qa")
        self.subagent("Perf", "performance review")
        r = self.stop()
        self.assertEqual(r.returncode, 2)
        self.assertIn("no distinct ui auditor", r.err)
        self.assertNotIn("no distinct performance auditor", r.err)
        self.assertNotIn("does not exist", r.err)

    def test_auditors_but_no_qa_audit_md_blocks(self):
        self.implemented()
        self.subagent("Perf", "performance review")
        self.subagent("UI", "mockup check")
        r = self.stop()
        self.assertEqual(r.returncode, 2)
        self.assertIn("qa-audit.md does not exist", r.err)

    def test_auditors_that_ran_before_the_last_code_edit_do_not_count(self):
        self.put(TASKS, approved_tasks())
        self.open_spec()
        self.approved_event()
        self.subagent("Perf", "performance review")
        self.subagent("UI", "mockup check")
        self.put(QA, "# qa")
        self.ev("code_edit", path="src/app.py", spec="001-x")
        self.assertEqual(self.stop().returncode, 2)

    def test_m9_one_subagent_cannot_cover_two_domains(self):
        self.implemented()
        self.put(QA, "# qa")
        self.subagent("Both", "performance and ui mockup review")
        r = self.stop()
        self.assertEqual(r.returncode, 2)
        self.assertIn("distinct", r.err)

    # ---- M10: bounded blocking, no free pass from stop_hook_active ---------------------------
    def test_m10_blocks_three_times_even_when_stop_hook_active_then_allows(self):
        self.implemented()
        codes = [self.stop().returncode,
                 self.stop(stop_hook_active=True).returncode,
                 self.stop(stop_hook_active=True).returncode,
                 self.stop(stop_hook_active=True).returncode,
                 self.stop().returncode]
        self.assertEqual(codes, [2, 2, 2, 0, 0])
        self.assertEqual(len(self.events("stop_block")), 3)
        ex = self.events("stop_block_exhausted")
        self.assertEqual(len(ex), 1)           # recorded once, the log does not grow on every later Stop
        self.assertEqual(ex[0]["detail"]["spec"], "001-x")

    def test_m10_the_block_message_counts_up(self):
        self.implemented()
        self.assertIn("block 1 of 3", self.stop().err)
        self.assertIn("block 2 of 3", self.stop().err)
        self.assertIn("block 3 of 3", self.stop().err)

    def test_m10_a_different_session_is_still_blocked_by_the_obligation(self):
        self.implemented()                      # code edit recorded by self.session
        r = self.stop(session="a-brand-new-session")
        self.assertEqual(r.returncode, 2, r.err)
        self.assertIn("R8", r.err)

    def test_m10_budget_is_shared_across_sessions(self):
        self.implemented()
        self.assertEqual([self.stop(session="A").returncode, self.stop(session="B").returncode,
                          self.stop(session="A").returncode, self.stop(session="B").returncode], [2, 2, 2, 0])

    def test_m10_a_new_approval_hash_gets_a_fresh_budget(self):
        self.implemented()
        for _ in range(3):
            self.stop()
        self.assertEqual(self.stop().returncode, 0)
        t2 = approved_tasks(a1=31, w1=31, total=51)           # tasks re-planned and re-approved
        self.put(TASKS, t2)
        self.approved_event(t2)
        self.ev("code_edit", path="src/app.py", spec="001-x")
        self.assertEqual(self.stop().returncode, 2)

    def test_m10_when_the_audit_is_completed_the_stop_is_free_again(self):
        self.implemented()
        self.assertEqual(self.stop().returncode, 2)
        self.put(QA, "# qa")
        self.close_audits()
        self.assertEqual(self.stop().returncode, 0)

    # ---- B1: open specs, not the (informational) active pointer -----------------------------
    def test_the_active_pointer_alone_creates_no_obligation(self):
        self.put(TASKS, approved_tasks())
        EV.set_active_spec(self.root, "001-x")                  # pointer only: no approval, no recorded edit
        self.ev("code_edit", path="src/app.py", spec="001-x")
        self.assertEqual(self.stop().returncode, 0)

    def test_an_approved_spec_without_recorded_tasks_edit_creates_no_obligation(self):
        """FR-009 / AC-009 (spec 006): a legacy approved spec nobody amends (no recorded plan/tasks edit) never
        nags the Stop gate, however many unrelated code edits follow."""
        self.put(TASKS, approved_tasks())
        self.approved_event()
        EV.set_active_spec(self.root, "001-x")
        for i in range(120):
            self.ev("code_edit", path=f"src/f{i}.py", spec="001-x")
        r = self.stop()
        self.assertEqual(r.returncode, 0, r.err)
        self.assertNotIn("001-x", r.err)

    def test_a_real_tasks_edit_after_approval_blocks(self):
        """FR-009 (d): amending the approved spec (recorded plan/tasks edit) makes it an obligation again."""
        self.put(TASKS, approved_tasks())
        self.approved_event()
        self.open_spec()
        self.ev("code_edit", path="src/app.py", spec="001-x")
        r = self.stop()
        self.assertEqual(r.returncode, 2, r.err)
        self.assertIn("001-x", r.err)

    def test_switching_the_pointer_does_not_hide_an_open_spec(self):
        self.implemented()
        (self.root / "specs" / "zzz").mkdir()
        self.spec_edit("mockup-audit.md", spec="zzz")
        EV.set_active_spec(self.root, "zzz")
        self.assertEqual(self.stop().returncode, 2)

    def test_closed_spec_is_no_longer_an_obligation(self):
        self.implemented()
        self.assertEqual(self.stop().returncode, 2)
        self.close_spec(reason="completed")
        self.assertEqual(self.stop().returncode, 0)

    def test_two_open_specs_both_count_and_abandoning_one_leaves_the_other(self):
        (self.root / "specs" / "002-y").mkdir()
        self.implemented()
        t = approved_tasks()
        self.put("specs/002-y/tasks.md", t)
        self.open_spec("002-y")
        self.ev("approved", spec="002-y", hash=R.approval_hash(t))
        self.ev("code_edit", path="src/b.py", spec="002-y")
        r = self.stop()
        self.assertEqual(r.returncode, 2)
        self.assertIn("001-x", r.err)
        self.assertIn("002-y", r.err)
        self.close_spec("001-x")
        r = self.stop()
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("spec 001-x", r.err)
        self.assertIn("spec 002-y", r.err)

    # ---- M7: approval time comes from the approved event, never mtime -----------------------
    def test_m7_hash_neutral_rewrite_does_not_reset_the_obligation(self):
        self.implemented()
        # trailing-whitespace rewrite: hash-neutral, newer mtime, and the recorder re-emits `approved`
        t = approved_tasks()
        self.put(TASKS, t.replace("Waves", "Waves  "), age=-50)
        self.assertTrue(R.approval_valid((self.root / TASKS).read_text(encoding="utf-8")))
        self.approved_event(t)
        self.assertEqual(self.stop().returncode, 2)

    def test_m7_status_column_edit_does_not_reset_the_obligation(self):
        base = tasks_text().replace("### T-01\n", "### T-01\n- Status: open\n")
        t = base.replace("Approved: PENDING", f"Approved: 2026-10-01 hash:{R.approval_hash(base)}")
        self.implemented(t)
        done = t.replace("- Status: open", "- Status: done")
        self.put(TASKS, done, age=-50)                       # sync_issues write-back: newer mtime, same hash
        self.assertTrue(R.approval_valid(done))
        self.ev("approved", spec="001-x", hash=R.approval_hash(done))
        self.assertEqual(self.stop().returncode, 2)

    def test_m7_mtime_is_not_used(self):
        """Old behaviour: approved_at = mtime(tasks.md). A future mtime must NOT hide the code edit."""
        self.implemented()
        self.put(TASKS, approved_tasks(), age=-1000)
        self.assertEqual(self.stop().returncode, 2)

    def test_m7_code_edits_before_the_approval_event_do_not_count(self):
        t = approved_tasks()
        self.put(TASKS, t)
        self.open_spec()
        self.ev("code_edit", path="src/old.py", spec="001-x")
        self.approved_event(t)                                # approval is newer than every code edit
        self.assertEqual(self.stop().returncode, 0)

    def test_m7_re_approval_with_a_new_hash_restarts_the_clock(self):
        self.implemented()
        t2 = approved_tasks(a1=31, w1=31, total=51)
        self.put(TASKS, t2)
        self.approved_event(t2)                               # new hash, no code since
        self.assertEqual(self.stop().returncode, 0)

    # ---- never blocks ---------------------------------------------------------------------
    def test_no_open_spec_never_blocks(self):
        self.put(TASKS, approved_tasks())
        self.ev("code_edit", path="src/app.py", spec="")
        self.assertEqual(self.stop().returncode, 0)

    def test_no_evidence_dir_never_blocks(self):
        self.assertEqual(self.stop().returncode, 0)

    def test_unapproved_tasks_do_not_trigger_r8(self):
        self.put(TASKS, tasks_text())
        self.open_spec()
        self.ev("code_edit", path="src/app.py", spec="001-x")
        self.assertEqual(self.stop().returncode, 0)

    def test_open_spec_without_tasks_file(self):
        self.open_spec()
        self.assertEqual(self.stop().returncode, 0)

    def test_tasks_changed_after_approval_is_not_r8(self):
        t = approved_tasks()
        self.put(TASKS, t.replace("Human ref hours: 8", "Human ref hours: 9"))
        self.open_spec()
        self.approved_event(t)
        self.ev("code_edit", path="src/app.py", spec="001-x")
        self.assertEqual(self.stop().returncode, 0)  # R6 (the code gate) owns that case, not R8

    def test_d1_a_code_edit_attributed_to_another_spec_still_counts(self):
        """Rev 2 D1: code_edit carries no spec attribution - ANY code edit counts for every open spec."""
        t = approved_tasks()
        self.put(TASKS, t)
        self.open_spec()
        self.approved_event(t)
        self.ev("code_edit", path="src/other.py", spec="002-other")
        self.assertEqual(self.stop().returncode, 2)

    def test_d1_repro_touch_zzz_then_code_edit_then_stop_still_blocks(self):
        t = approved_tasks()
        self.put(TASKS, t)
        self.open_spec()
        self.approved_event(t)
        (self.root / "specs" / "zzz").mkdir()
        self.spec_edit("mockup-audit.md", spec="zzz")        # the recorder flips the informational pointer to zzz
        EV.set_active_spec(self.root, "zzz")
        self.ev("code_edit", path="src/app.py")              # no attribution
        r = self.stop()
        self.assertEqual(r.returncode, 2, r.err)
        self.assertIn("001-x", r.err)

    def test_d1b_session_started_in_a_parent_folder_is_still_enforced(self):
        import shutil
        import tempfile
        parent = Path(tempfile.mkdtemp(prefix="aidd-stop-parent-")).resolve()
        try:
            proj = parent / "proj"
            (proj / "specs" / "001-x").mkdir(parents=True)
            t = approved_tasks()
            (proj / "specs" / "001-x" / "tasks.md").write_text(t, encoding="utf-8")
            for kind, d in (("spec_edit", {"path": "x", "spec": "001-x", "file": "tasks.md"}),
                            ("approved", {"spec": "001-x", "hash": R.approval_hash(t)}),
                            ("code_edit", {"path": "src/a.py"})):
                time.sleep(0.015)
                EV.append(proj, self.session, kind, **d)
            r = self.run_hook("stop_gate.py", {"session_id": self.session, "cwd": str(parent)})
            self.assertEqual(r.returncode, 2, r.err)
        finally:
            shutil.rmtree(parent, ignore_errors=True)

    # ---- env + robustness -----------------------------------------------------------------
    def test_warn_mode_prints_checklist_allows_and_does_not_consume_the_budget(self):
        self.implemented()
        for _ in range(5):
            r = self.stop(env={"AIDD_RULES": "warn"})
            self.assertEqual(r.returncode, 0)
            self.assertIn("R8", r.err)
        self.assertEqual(self.events("stop_block"), [])
        self.assertEqual(self.stop().returncode, 2)            # enforcing still has its full budget

    def test_off_variants_silent(self):
        self.implemented()
        for v in ("off", "OFF", "0", "false", "no", " No "):
            r = self.stop(env={"AIDD_RULES": v})
            self.assertEqual((r.returncode, r.err.strip()), (0, ""), v)

    def test_unknown_mode_enforces(self):
        self.implemented()
        self.assertEqual(self.stop(env={"AIDD_RULES": "maybe"}).returncode, 2)

    def test_garbage_stdin(self):
        for raw in (b"not json", b"", b"[]", b"null", b'"s"', b"42", b"\xff\xfe",
                    b'{"session_id": {"a": 1}, "cwd": [], "stop_hook_active": "x"}'):
            r = self.run_hook("stop_gate.py", None, raw=raw)
            self.assertEqual(r.returncode, 0, raw)
            self.assertNotIn("Traceback", r.err)

    def test_unreadable_cwd_type(self):
        r = self.run_hook("stop_gate.py", {"session_id": self.session, "cwd": 123})
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.err)

    def test_internal_error_exits_zero_and_records_hook_error(self):
        payload = json.dumps({"session_id": self.session, "cwd": str(self.root)}).encode()
        with mock.patch.object(stop_gate, "evaluate", side_effect=RuntimeError("kaboom")), \
                mock.patch.object(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(payload))):
            # read_event uses json.load(sys.stdin): give it a text stream
            with mock.patch.object(sys, "stdin", io.StringIO(payload.decode())):
                with self.assertRaises(SystemExit) as cm:
                    stop_gate.main()
        self.assertEqual(cm.exception.code, 0)
        errs = self.events("hook_error")
        self.assertEqual([e["detail"]["hook"] for e in errs], ["stop_gate"])
        self.assertIn("kaboom", errs[0]["detail"]["error"])


if __name__ == "__main__":
    unittest.main()
