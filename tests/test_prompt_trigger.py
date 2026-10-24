"""Spec 004 amendment (FR-032, FR-040, AC-024): the prompt hook does not re-run find_spec or re-inject Step -1 on every message.

The hook runs in an isolated copy of skill/hooks + skill/scripts in a temp dir where find_spec.py is a fake that
appends one line to a counter file, so the number of real find_spec runs is counted exactly.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / "skill"
STEP_MARK = "Step -1 (find_spec) already ran"
FAKE_FIND_SPEC = (
    "import os, sys\n"
    "with open(os.environ['AIDD_FAKE_COUNT'], 'a', encoding='utf-8') as f:\n"
    "    f.write(' '.join(sys.argv[1:]) + '\\n')\n"
    "print('Match: 001-x (fake)')\n"
)
Q_A = "necesito modificar la pantalla de login"
Q_B = "necesito implementar el endpoint de facturas"


class PromptTriggerCase(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        base = Path(self.td.name)
        self.iso = base / "skill"
        shutil.copytree(SKILL / "hooks", self.iso / "hooks", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(SKILL / "scripts", self.iso / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        (self.iso / "scripts" / "find_spec.py").write_text(FAKE_FIND_SPEC, encoding="utf-8")
        self.root = (base / "proj").resolve()
        (self.root / "specs" / "001-x").mkdir(parents=True)
        self.index = self.root / "specs" / "index.toon"
        self.index.write_text("specs[1]: 001-x\n", encoding="utf-8")
        self.count = base / "count.txt"
        self.evdir = base / "ev"
        self.evdir.mkdir()
        self.sid = f"test-{uuid.uuid4().hex}"
        self.env = dict(os.environ, AIDD_EVIDENCE_DIR=str(self.evdir), AIDD_TESTING="1",
                        AIDD_FAKE_COUNT=str(self.count), PYTHONIOENCODING="utf-8")

    def tearDown(self):
        self.td.cleanup()
        try:
            (Path(tempfile.gettempdir()) / ("aidd_hint_" + re.sub(r"[^A-Za-z0-9_-]", "_", self.sid)[:64])).unlink(missing_ok=True)
            shutil.rmtree(Path(tempfile.gettempdir()) / "aidd-hooks" / self.sid, ignore_errors=True)
        except Exception:
            pass

    def send(self, prompt, sid=None):
        ev = {"session_id": sid or self.sid, "cwd": str(self.root), "prompt": prompt}
        r = subprocess.run([sys.executable, str(self.iso / "hooks" / "prompt_trigger.py")],
                           input=json.dumps(ev).encode("utf-8"), capture_output=True, env=self.env, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
        return r.stdout.decode("utf-8", "replace")

    def runs(self):
        if not self.count.exists():
            return 0
        return len([l for l in self.count.read_text(encoding="utf-8").splitlines() if l.strip()])

    def events(self, kind):
        old = {k: os.environ.get(k) for k in ("AIDD_EVIDENCE_DIR", "AIDD_TESTING")}
        os.environ["AIDD_EVIDENCE_DIR"] = str(self.evdir)
        os.environ["AIDD_TESTING"] = "1"
        sys.path.insert(0, str(SKILL / "scripts"))
        try:
            import aidd_evidence
            return aidd_evidence.events(self.root, kind=kind)
        finally:
            sys.path.remove(str(SKILL / "scripts"))
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def hook_find_spec_events(self):
        return [e for e in self.events("find_spec") if e["detail"].get("source") == "hook"]


class TestSystemMessages(PromptTriggerCase):
    def test_system_and_agent_prefixes_skip_find_spec_and_block(self):
        for p in ("<task-notification>modificar el login</task-notification>",
                  "[Request interrupted] necesito modificar el login",
                  "Another Claude session sent a message: necesito modificar la pantalla de login",
                  "<subagent-result>implementar el endpoint de facturas</subagent-result>"):
            out = self.send(p)
            self.assertNotIn(STEP_MARK, out, p)
            self.assertNotIn("[aidd] This looks like", out, p)
            self.assertNotIn("Requirement/change detected", out, p)
        self.assertEqual(self.runs(), 0)
        self.assertEqual(self.hook_find_spec_events(), [])

    def test_skipped_prompt_is_still_recorded(self):
        self.send("<task-notification>modificar el login</task-notification>")
        e = self.events("prompt")
        self.assertEqual(len(e), 1)
        self.assertIn("task-notification", e[0]["detail"]["text"])

    def test_skipped_prompt_does_not_consume_the_session_hint(self):
        self.send("[note] modificar el login")
        out = self.send(Q_A)
        self.assertIn("aidd tools", out)


class TestDedupe(PromptTriggerCase):
    def test_first_message_runs_and_injects(self):
        out = self.send(Q_A)
        self.assertEqual(self.runs(), 1)
        self.assertIn(STEP_MARK, out)
        self.assertEqual(len(self.hook_find_spec_events()), 1)

    def test_same_terms_unchanged_index_does_not_rerun(self):
        self.send(Q_A)
        out = self.send(Q_A)
        self.assertEqual(self.runs(), 1)
        self.assertNotIn(STEP_MARK, out)
        self.assertEqual(len(self.hook_find_spec_events()), 1)

    def test_changed_index_runs_again(self):
        self.send(Q_A)
        self.index.write_text("specs[2]: 001-x,002-y\n", encoding="utf-8")
        out = self.send(Q_A)
        self.assertEqual(self.runs(), 2)
        self.assertIn(STEP_MARK, out)
        self.assertEqual(len(self.hook_find_spec_events()), 2)

    def test_same_size_content_change_runs_again(self):
        self.send(Q_A)
        self.index.write_text("specs[1]: 001-y\n", encoding="utf-8")   # same length, different content
        self.send(Q_A)
        self.assertEqual(self.runs(), 2)

    def test_touch_without_content_change_does_not_rerun(self):
        self.send(Q_A)
        st = self.index.stat()
        os.utime(self.index, (st.st_atime + 5, st.st_mtime + 5))
        self.send(Q_A)
        self.assertEqual(self.runs(), 1)

    def test_different_terms_run_again(self):
        self.send(Q_A)
        out = self.send(Q_B)
        self.assertEqual(self.runs(), 2)
        self.assertIn(STEP_MARK, out)

    def test_other_session_is_independent(self):
        other = self.sid + "-other"
        self.send(Q_A)
        try:
            out = self.send(Q_A, sid=other)
            self.assertEqual(self.runs(), 2)
            self.assertIn(STEP_MARK, out)
        finally:
            shutil.rmtree(Path(tempfile.gettempdir()) / "aidd-hooks" / other, ignore_errors=True)
            (Path(tempfile.gettempdir()) / ("aidd_hint_" + re.sub(r"[^A-Za-z0-9_-]", "_", other)[:64])).unlink(missing_ok=True)


class TestHint(PromptTriggerCase):
    def test_first_hint_names_the_tools(self):
        out = self.send(Q_A)
        for name in ("aidd tools", "aidd graphs", "aidd job", "aidd triage", "aidd size"):
            self.assertIn(name, out)

    def test_hint_is_once_per_session(self):
        self.send(Q_A)
        out = self.send(Q_B)
        self.assertNotIn("aidd job", out)
        self.assertIn("[aidd]", out)

    def test_exit_zero_on_garbage_input(self):
        for raw in (b"", b"not json", b"[]", json.dumps({"prompt": 5, "session_id": 3}).encode()):
            r = subprocess.run([sys.executable, str(self.iso / "hooks" / "prompt_trigger.py")],
                               input=raw, capture_output=True, env=self.env, timeout=30)
            self.assertEqual(r.returncode, 0)


class TestAC024(PromptTriggerCase):
    def test_ten_messages_at_most_two_runs_and_two_blocks(self):
        msgs = [
            Q_A,                                                              # 1 user, run + block
            "<task-notification>planificar la migracion</task-notification>",  # 2 agent
            "[Request interrupted] modificar el endpoint",                    # 3 agent
            Q_A,                                                              # 4 user, same terms
            "Another Claude session sent a message: crear la funcionalidad",  # 5 agent
            "<subagent-result>implementar el backend</subagent-result>",      # 6 agent
            Q_A,                                                              # 7 user, same terms
            Q_B,                                                              # 8 user, new terms: run + block
            "[hook] arreglar el bug",                                         # 9 agent
            "<system-reminder>actualizar el plan</system-reminder>",          # 10 agent
        ]
        outs = [self.send(m) for m in msgs]
        blocks = sum(1 for o in outs if STEP_MARK in o)
        self.assertLessEqual(self.runs(), 2)
        self.assertLessEqual(blocks, 2)
        self.assertLessEqual(len(self.hook_find_spec_events()), 2)
        self.assertEqual(self.runs(), len(self.hook_find_spec_events()))
        self.assertEqual(len(self.events("prompt")), 10)


def _load(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestFindSpecTimeout(unittest.TestCase):   # FR-047 / AC-039
    def test_find_spec_timeout_is_at_most_8_and_below_the_hook_timeout(self):
        hook = SKILL / "hooks" / "prompt_trigger.py"
        saved = list(sys.path)
        sys.path.insert(0, str(SKILL / "scripts"))
        sys.path.insert(0, str(SKILL / "hooks"))
        try:
            ih = _load("install_hooks_t56", SKILL / "scripts" / "install_hooks.py")
        finally:
            sys.path[:] = saved
        # the hook runs its main at import (sys.exit), so read the constant from its source instead of importing it
        import re
        m = re.search(r"^FIND_SPEC_TIMEOUT\s*=\s*(\d+)", hook.read_text(encoding="utf-8"), re.M)
        self.assertIsNotNone(m, "FIND_SPEC_TIMEOUT is not defined in prompt_trigger.py")
        timeout = int(m.group(1))
        self.assertLessEqual(timeout, 8)
        self.assertGreater(timeout, 0)
        registered = ih.timeout_for(hook)
        self.assertLess(timeout, registered,
                        "the hook is killed at %s s, so find_spec must give up earlier" % registered)

    def test_the_subprocess_call_uses_the_constant(self):
        src = (SKILL / "hooks" / "prompt_trigger.py").read_text(encoding="utf-8")
        self.assertIn("timeout=FIND_SPEC_TIMEOUT", src)
        self.assertEqual(re.findall(r"timeout\s*=\s*\d+", src), [], "no hard-coded timeout may remain")


if __name__ == "__main__":
    unittest.main()
