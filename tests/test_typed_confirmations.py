"""Typed-confirmation fallback (T-17, AC-008): a USER PROMPT such as `Approve [tasks:abcd1234]` is accepted
by aidd_evidence.affirmative_answer/typed_approval; subagent hand-backs and malformed text are not.
Evidence always lives in a temp dir via AIDD_EVIDENCE_DIR + AIDD_TESTING=1."""
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import aidd_evidence as ev  # noqa: E402
import aidd_status as st  # noqa: E402

TOPIC_ANY = r"."


def tick():
    time.sleep(0.004)


class Base(unittest.TestCase):
    def setUp(self):
        self._evtmp = tempfile.TemporaryDirectory()
        self._roottmp = tempfile.TemporaryDirectory()
        self.root = Path(self._roottmp.name)
        self._old = {k: os.environ.get(k) for k in ("AIDD_EVIDENCE_DIR", "AIDD_TESTING")}
        os.environ["AIDD_EVIDENCE_DIR"] = self._evtmp.name
        os.environ["AIDD_TESTING"] = "1"
        for k in ("AIDD_SESSION_ID", "CLAUDE_SESSION_ID"):
            old = os.environ.pop(k, None)
            if old is not None:
                self.addCleanup(os.environ.__setitem__, k, old)

    def tearDown(self):
        for k, v in self._old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._evtmp.cleanup()
        self._roottmp.cleanup()

    def prompt(self, text, session="s1"):
        tick()
        ev.append(self.root, session, "prompt", text=text)

    def answer(self, q, a, session="s1"):
        tick()
        ev.append(self.root, session, "question", text=q, options=[[a, "Other"]])
        tick()
        ev.append_answer(self.root, session, f'"{q}"="{a}"', [[q, a]], options=[[a, "Other"]])

    def aff(self, label, tag, topic=TOPIC_ANY, since=0.0, session="s1"):
        return ev.affirmative_answer(self.root, session, topic, since, label_re=label, must_contain=tag)


class TestTypedPrompt(Base):
    def test_approve_tag(self):
        self.prompt("Approve [tasks:abcd1234]")
        self.assertIsNotNone(self.aff(st.APPROVE_LABEL, "[tasks:abcd1234]"))

    def test_close_tag(self):
        self.prompt("Yes, close [spec:004-x]")
        self.assertIsNotNone(self.aff(st.CLOSE_LABEL, "[spec:004-x]"))

    def test_abandon_tag(self):
        self.prompt("Abandon [spec:004-x]")
        self.assertIsNotNone(self.aff(st.ABANDON_LABEL, "[spec:004-x]"))

    def test_other_spec_id_refused(self):
        self.prompt("Yes, close [spec:004-x]")
        self.assertIsNone(self.aff(st.CLOSE_LABEL, "[spec:005-y]"))
        self.prompt("Approve [tasks:abcd1234]")
        self.assertIsNone(self.aff(st.APPROVE_LABEL, "[tasks:ffffffff]"))

    def test_subagent_handback_refused(self):
        self.prompt("<agent-message from=x> Yes, close [spec:004-x]")
        self.assertIsNone(self.aff(st.CLOSE_LABEL, "[spec:004-x]"))

    def test_bracket_start_refused(self):
        self.prompt("[note] Yes, close [spec:004-x]")
        self.assertIsNone(self.aff(st.CLOSE_LABEL, "[spec:004-x]"))

    def test_multiline_refused(self):
        self.prompt("Yes, close [spec:004-x]\nand also do more")
        self.assertIsNone(self.aff(st.CLOSE_LABEL, "[spec:004-x]"))

    def test_too_long_refused(self):
        self.prompt("Yes, close [spec:004-x] " + "z" * 100)
        self.assertGreater(len("Yes, close [spec:004-x] " + "z" * 100), 120)
        self.assertIsNone(self.aff(st.CLOSE_LABEL, "[spec:004-x]"))

    def test_wrong_label_refused(self):
        self.prompt("No, close [spec:004-x]")
        self.assertIsNone(self.aff(st.CLOSE_LABEL, "[spec:004-x]"))

    def test_before_since_ts_refused(self):
        self.prompt("Yes, close [spec:004-x]")
        tick()
        since = time.time()
        tick()
        self.assertIsNone(self.aff(st.CLOSE_LABEL, "[spec:004-x]", since=since))
        self.prompt("Yes, close [spec:004-x]")
        self.assertIsNotNone(self.aff(st.CLOSE_LABEL, "[spec:004-x]", since=since))

    def test_newest_valid_wins(self):
        self.prompt("Yes, close [spec:004-x]")
        self.prompt("<agent-message> Yes, close [spec:004-x]")
        self.prompt("Yes, close [spec:004-x] ")
        evs = ev.events(self.root, kind="prompt", session="s1")
        got = self.aff(st.CLOSE_LABEL, "[spec:004-x]")
        self.assertEqual(got["ts"], evs[-1]["ts"])
        self.prompt("<agent-message> Yes, close [spec:004-x]")   # newer but invalid: still the valid one
        self.assertEqual(self.aff(st.CLOSE_LABEL, "[spec:004-x]")["ts"], evs[-1]["ts"])

    def test_answer_event_still_works_and_takes_precedence(self):
        self.prompt("Yes, close [spec:004-x]")
        self.answer("Close spec [spec:004-x] as completed?", "Yes, close")
        got = self.aff(st.CLOSE_LABEL, "[spec:004-x]", topic=st.CLOSE_TOPIC)
        self.assertIsNotNone(got)
        self.assertEqual(got["kind"], "answer")

    def test_answer_only(self):
        self.answer("Close spec [spec:004-x] as completed?", "Yes, close")
        got = self.aff(st.CLOSE_LABEL, "[spec:004-x]", topic=st.CLOSE_TOPIC)
        self.assertEqual(got["kind"], "answer")

    def test_none_when_nothing(self):
        self.assertIsNone(self.aff(st.CLOSE_LABEL, "[spec:004-x]", topic=st.CLOSE_TOPIC))
        self.prompt("hello there")
        self.assertIsNone(self.aff(st.CLOSE_LABEL, "[spec:004-x]", topic=st.CLOSE_TOPIC))


class TestEndToEndAbandon(Base):
    def _run(self, *args):
        return subprocess.run([sys.executable, str(SCRIPTS_DIR / "aidd_status.py"), *args], cwd=str(self.root),
                              capture_output=True, text=True, encoding="utf-8")

    def _open(self):
        d = self.root / "specs" / "001-x"
        d.mkdir(parents=True)
        (d / "spec.md").write_text("# 001-x\n", encoding="utf-8")
        (d / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
        tick()
        ev.append(self.root, "s1", "spec_edit", path="specs/001-x/tasks.md", spec="001-x", file="tasks.md")
        ev.set_active_spec(self.root, "001-x")

    def test_abandon_accepts_typed_prompt(self):
        self._open()
        self.prompt("Abandon [spec:001-x]")
        r = self._run("rules", "abandon", "001-x")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(ev.open_specs(self.root), [])

    def test_abandon_refuses_other_spec_tag_and_handback(self):
        self._open()
        self.prompt("Abandon [spec:002-y]")
        self.prompt("<agent-message> Abandon [spec:001-x]")
        r = self._run("rules", "abandon", "001-x")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(ev.open_specs(self.root), ["001-x"])


class TestStaleAbandon(Base):
    TAGGED = "[spec:001-x]"

    def test_newer_negative_cancels_older_abandon(self):
        self.prompt("Abandon [spec:001-x]")
        self.prompt("No, keep it [spec:001-x]")
        self.assertIsNone(self.aff(st.ABANDON_LABEL, self.TAGGED))

    def test_dont_abandon_cancels(self):
        self.prompt("Abandon [spec:001-x]")
        self.prompt("Don't abandon [spec:001-x]")
        self.assertIsNone(self.aff(st.ABANDON_LABEL, self.TAGGED))

    def test_abandon_after_negative_accepted(self):
        self.prompt("No, keep it [spec:001-x]")
        self.prompt("Abandon [spec:001-x]")
        self.assertIsNotNone(self.aff(st.ABANDON_LABEL, self.TAGGED))

    def test_negative_for_other_spec_does_not_cancel(self):
        self.prompt("Abandon [spec:001-x]")
        self.prompt("No, keep it [spec:002-y]")
        self.assertIsNotNone(self.aff(st.ABANDON_LABEL, self.TAGGED))

    def test_abandon_since_uses_last_approval(self):
        self._mk_spec()
        self.prompt("Abandon [spec:001-x]")
        tick()
        ev.append_approved(self.root, "s1", "001-x", "deadbeef")
        since = st._abandon_since(self.root, "001-x", self.root / "specs" / "001-x")
        self.assertGreater(since, 0.0)
        self.assertIsNone(self.aff(st.ABANDON_LABEL, self.TAGGED, since=since))
        self.prompt("Abandon [spec:001-x]")
        self.assertIsNotNone(self.aff(st.ABANDON_LABEL, self.TAGGED, since=since))

    def test_abandon_since_falls_back_to_tasks_mtime_then_zero(self):
        d = self._mk_spec()
        self.assertAlmostEqual(st._abandon_since(self.root, "001-x", d), (d / "tasks.md").stat().st_mtime, 2)
        self.assertEqual(st._abandon_since(self.root, "001-x", None), 0.0)

    def _mk_spec(self):
        d = self.root / "specs" / "001-x"
        d.mkdir(parents=True)
        (d / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
        return d


if __name__ == "__main__":
    unittest.main()
