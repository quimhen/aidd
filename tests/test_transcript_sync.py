"""Tests for the transcript sync (T-18, spec 005 AC-011/AC-012) + R9 on host transcripts. stdlib unittest."""
import json
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "skill" / "scripts"))
sys.path.insert(0, str(HERE.parent / "skill" / "hooks"))

import aidd_evidence as ev  # noqa: E402
from aidd_status import APPROVE_TOPIC, APPROVE_LABEL  # noqa: E402

TAG = "[tasks:abcd1234]"
Q = "Approve these tasks? " + TAG


def ask_line(tid="toolu_A", q=Q, labels=("Approve", "Changes")):
    return json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": tid, "name": "AskUserQuestion",
         "input": {"questions": [{"question": q, "options": [{"label": x} for x in labels]}]}}]}})


def result_line(tid="toolu_A", q=Q, ans="Approve", with_tur=True):
    o = {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tid,
         "content": 'Your questions have been answered: "%s"="%s". You can now continue with these answers in mind.'
                    % (q, ans)}]}}
    if with_tur:
        o["toolUseResult"] = {"questions": [{"question": q}], "answers": {q: ans}, "annotations": {}}
    return json.dumps(o)


def noise_lines():
    return [
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "toolu_B", "name": "Bash", "input": {"command": "echo " + TAG}}]}}),
        json.dumps({"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "toolu_B", "is_error": True,
             "content": 'Error: "%s"="Approve" blocked' % Q}]}}),
    ]


class SyncCase(unittest.TestCase):
    def setUp(self):
        self._old = {k: os.environ.get(k) for k in ("AIDD_EVIDENCE_DIR", "AIDD_TESTING")}
        self._td = tempfile.TemporaryDirectory()
        self._ed = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        (self.root / "specs").mkdir()
        os.environ["AIDD_EVIDENCE_DIR"] = self._ed.name
        os.environ["AIDD_TESTING"] = "1"
        self.session = "tsync-" + uuid.uuid4().hex[:10]
        self.tp = self.root / "transcript.jsonl"

    def tearDown(self):
        try:
            ev._marker_path(self.session).unlink()
        except OSError:
            pass
        for k, v in self._old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._td.cleanup()
        self._ed.cleanup()

    def write(self, lines, final_nl=True):
        self.tp.write_text("\n".join(lines) + ("\n" if final_nl else ""), encoding="utf-8")

    def append_raw(self, text):
        with open(self.tp, "a", encoding="utf-8", newline="") as fh:
            fh.write(text)

    def sync(self):
        return ev.sync_ask_answers(str(self.tp), self.session, self.root)

    def evs(self, kind):
        return ev.events(self.root, session=self.session, kind=kind)

    def affirm(self):
        return ev.affirmative_answer(self.root, self.session, APPROVE_TOPIC, label_re=APPROVE_LABEL,
                                     must_contain=TAG)


class TestSyncAskAnswers(SyncCase):
    def test_one_click_recorded_once(self):
        self.write([ask_line()] + noise_lines() + [result_line()])
        self.assertEqual(self.sync(), 1)
        qs, ans = self.evs("question"), self.evs("answer")
        self.assertEqual((len(qs), len(ans)), (1, 1))
        self.assertEqual(qs[0]["detail"]["tool_use_id"], "toolu_A")
        self.assertEqual(ans[0]["detail"]["tool_use_id"], "toolu_A")
        self.assertEqual(ans[0]["detail"]["pairs"], [[Q, "Approve"]])
        self.assertIsNotNone(self.affirm())

    def test_noise_not_recorded(self):
        self.write(noise_lines())
        self.assertEqual(self.sync(), 0)
        self.assertEqual(self.evs("answer"), [])
        self.assertIsNone(self.affirm())

    def test_second_sync_adds_nothing(self):
        self.write([ask_line(), result_line()])
        self.assertEqual(self.sync(), 1)
        self.assertEqual(self.sync(), 0)
        self.assertEqual((len(self.evs("question")), len(self.evs("answer"))), (1, 1))

    def test_incremental_offset_records_only_new_click(self):
        self.write([ask_line(), result_line()])
        self.assertEqual(self.sync(), 1)
        q2 = "Approve the plan? [tasks:ffff0000]"
        self.append_raw("\n".join([ask_line("toolu_C", q2), result_line("toolu_C", q2, "Changes")]) + "\n")
        self.assertEqual(self.sync(), 1)
        ids = sorted(e["detail"]["tool_use_id"] for e in self.evs("answer"))
        self.assertEqual(ids, ["toolu_A", "toolu_C"])
        self.assertEqual(len(self.evs("question")), 2)

    def test_partial_trailing_line_not_consumed_until_complete(self):
        full = result_line()
        self.write([ask_line()])
        self.append_raw(full[:40])             # no newline: partial JSON
        self.assertEqual(self.sync(), 0)
        self.assertEqual(self.evs("answer"), [])
        self.append_raw(full[40:] + "\n")
        self.assertEqual(self.sync(), 1)
        self.assertEqual(len(self.evs("answer")), 1)

    def test_fallback_without_tool_use_result(self):
        self.write([ask_line(), result_line(with_tur=False)])
        self.assertEqual(self.sync(), 1)
        a = self.evs("answer")[0]["detail"]
        self.assertEqual(a["pairs"], [[Q, "Approve"]])
        self.assertIsNotNone(self.affirm())

    def test_missing_empty_and_no_ask(self):
        self.assertEqual(ev.sync_ask_answers(str(self.root / "nope.jsonl"), self.session, self.root), 0)
        self.assertEqual(ev.sync_ask_answers("", self.session, self.root), 0)
        self.assertEqual(ev.sync_ask_answers(None, self.session, self.root), 0)
        self.tp.write_text("", encoding="utf-8")
        self.assertEqual(self.sync(), 0)
        self.write(noise_lines() + ["not json at all"])
        self.assertEqual(self.sync(), 0)
        self.assertEqual(self.evs("question"), [])

    def test_question_already_recorded_by_hook_not_duplicated(self):
        ev.append_question(self.root, self.session, Q + " | Approve | Changes")
        self.write([ask_line(), result_line()])
        self.assertEqual(self.sync(), 0)
        self.assertEqual(len(self.evs("question")), 1)

    def test_reasked_identical_question_new_tool_use_id_recorded(self):
        self.write([ask_line("toolu_A"), result_line("toolu_A", ans="Other")])
        self.assertEqual(self.sync(), 1)
        self.assertIsNone(self.affirm())
        self.append_raw("\n".join([ask_line("toolu_D"), result_line("toolu_D", ans="Approve")]) + "\n")
        self.assertEqual(self.sync(), 1)
        self.assertEqual(len(self.evs("answer")), 2)
        self.assertIsNotNone(self.affirm())

    def test_same_tool_use_id_never_duplicated_after_marker_loss(self):
        self.write([ask_line(), result_line()])
        self.assertEqual(self.sync(), 1)
        ev._marker_path(self.session).unlink()
        self.assertEqual(self.sync(), 0)
        self.assertEqual(len(self.evs("question")), 1)

    def test_secrets_redacted_in_answer(self):
        self.write([ask_line(), result_line(ans="password=hunter2xyz")])
        self.assertEqual(self.sync(), 1)
        a = self.evs("answer")[0]["detail"]
        self.assertNotIn("hunter2xyz", a["text"])
        self.assertNotIn("hunter2xyz", json.dumps(a["pairs"]))
        self.assertIn("[redacted]", a["text"])


class TestQueuedMessages(SyncCase):
    def test_two_entries_then_dedup(self):
        q = [{"role": "user", "content": "first queued", "timestamp": "2026-01-01T00:00:01Z"},
             {"role": "user", "content": "second queued"}]
        self.assertEqual(ev.record_queued_messages(self.root, self.session, q), 2)
        ps = self.evs("prompt")
        self.assertEqual(len(ps), 2)
        self.assertTrue(all(p["detail"].get("source") == "queued" for p in ps))
        self.assertEqual(ev.record_queued_messages(self.root, self.session, q), 0)
        self.assertEqual(len(self.evs("prompt")), 2)

    def test_invalid_entries_ignored(self):
        q = [{"role": "user"}, {"role": "user", "content": "   "}, {"role": "assistant", "content": "x"},
             "str", None, {"role": "user", "content": 5}]
        self.assertEqual(ev.record_queued_messages(self.root, self.session, q), 0)
        self.assertEqual(ev.record_queued_messages(self.root, self.session, "oops"), 0)
        self.assertEqual(self.evs("prompt"), [])

    def test_redaction(self):
        q = [{"role": "user", "content": "use api_key=sk-live-123456 now"}]
        self.assertEqual(ev.record_queued_messages(self.root, self.session, q), 1)
        t = self.evs("prompt")[0]["detail"]["text"]
        self.assertNotIn("sk-live-123456", t)
        self.assertIn("[redacted]", t)


class TestR9HostTranscript(unittest.TestCase):
    def setUp(self):
        import gate_fixtures
        import rule_gate
        self.rule_gate = rule_gate
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name).resolve()
        self.session = "r9tx-" + uuid.uuid4().hex[:8]
        self.tpath = str(Path.home() / ".claude" / "projects" / "D--proj" / "abc123.jsonl")
        self._gf = gate_fixtures

    def tearDown(self):
        try:
            self._gf._common.marker_path(self.session).unlink()
        except Exception:
            pass
        self._td.cleanup()

    def decide(self, tool, **ti):
        return self.rule_gate.decide({"session_id": self.session, "cwd": str(self.root), "tool_name": tool,
                                      "tool_input": ti})

    def test_write_to_transcript_blocked(self):
        for tool in ("Write", "Edit"):
            blocked, msg = self.decide(tool, file_path=self.tpath, content="x")
            self.assertTrue(blocked, tool)
            self.assertIn("R9", msg)
        blocked, _ = self.decide("Write", file_path=self.tpath.replace("\\", "/"), content="x")
        self.assertTrue(blocked)

    def test_write_in_command_blocked(self):
        for cmd in ('Set-Content -Path "%s" -Value x' % self.tpath,
                    'echo x > "%s"' % self.tpath.replace("\\", "/"),
                    'Remove-Item "%s"' % self.tpath):
            tool = "PowerShell" if cmd.startswith(("Set-", "Remove-")) else "Bash"
            blocked, _ = self.decide(tool, command=cmd)
            self.assertTrue(blocked, cmd)

    def test_read_only_command_allowed(self):
        blocked, _ = self.decide("PowerShell", command='Select-String -Path "%s" -Pattern AskUserQuestion'
                                 % self.tpath)
        self.assertFalse(blocked)
        blocked, _ = self.decide("Bash", command='grep -c AskUserQuestion "%s"' % self.tpath.replace("\\", "/"))
        self.assertFalse(blocked)

    def test_unrelated_jsonl_write_allowed(self):
        blocked, _ = self.decide("Write", file_path=str(self.root / "data" / "x.jsonl"), content="x")
        self.assertFalse(blocked)


if __name__ == "__main__":
    unittest.main()
