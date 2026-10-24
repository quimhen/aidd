"""Tests for skill/hooks/read_hint.py (subprocess, stdlib, throwaway evidence dir)."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock
import uuid
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "skill" / "hooks" / "read_hint.py"
sys.path.insert(0, str(ROOT / "skill" / "scripts"))
import aidd_evidence  # noqa: E402


class ReadHintCase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name).resolve()
        (self.root / "specs" / "001-x").mkdir(parents=True)
        (self.root / "skill" / "scripts").mkdir(parents=True)
        (self.root / "skill" / "scripts" / "mod.py").write_text("x = 1\n", encoding="utf-8")
        self.evid = self.root / "evid"
        self.evid.mkdir()
        self.sid = f"test-{uuid.uuid4().hex}"
        self.env = dict(os.environ, AIDD_TESTING="1", AIDD_EVIDENCE_DIR=str(self.evid))
        self.addCleanup(self._cleanup_markers)

    def _cleanup_markers(self):
        d = Path(tempfile.gettempdir()) / "aidd-hooks"
        if d.exists():
            for m in d.glob(f"{self.sid}.rh-*"):
                m.unlink(missing_ok=True)

    def run_hook(self, stdin):
        return subprocess.run(
            [sys.executable, str(HOOK)], input=stdin if isinstance(stdin, str) else json.dumps(stdin),
            capture_output=True, text=True, encoding="utf-8", timeout=15, env=self.env, cwd=str(self.root))

    @contextmanager
    def _env(self):
        keys = ("AIDD_TESTING", "AIDD_EVIDENCE_DIR")
        old = {k: os.environ.get(k) for k in keys}
        os.environ.update({k: self.env[k] for k in keys})
        try:
            yield
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def add_find_spec(self, source, age=0.0):
        """Append a find_spec event to the session log, stamped `age` seconds in the past."""
        with self._env():
            with unittest.mock.patch.object(aidd_evidence.time, "time", return_value=time.time() - age):
                aidd_evidence.append_find_spec(self.root, self.sid, False, True, source)

    def misses(self):
        with self._env():
            return [e["detail"] for e in aidd_evidence.events(self.root, session=self.sid, kind="graph_miss")]

    def tool_ev(self, tool, **ti):
        return {"session_id": self.sid, "cwd": str(self.root), "tool_name": tool, "tool_input": ti}

    def ctx(self, r):
        return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout else ""

    def py(self):
        return str(self.root / "skill" / "scripts" / "mod.py")

    def ev(self, path, **extra):
        ti = {"file_path": path, **extra}
        return {"session_id": self.sid, "cwd": str(self.root), "tool_name": "Read", "tool_input": ti}

    def spec(self):
        return str(self.root / "specs" / "001-x" / "spec.md")

    def test_hint_then_silent(self):
        r = self.run_hook(self.ev(self.spec()))
        self.assertEqual(r.returncode, 0)
        out = json.loads(r.stdout)
        self.assertIn("AIDD W1", out["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("permissionDecision", r.stdout)
        r2 = self.run_hook(self.ev(self.spec()))
        self.assertEqual((r2.returncode, r2.stdout), (0, ""))

    def test_limit_silent(self):
        r = self.run_hook(self.ev(self.spec(), limit=50))
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_non_target_has_no_w1(self):
        # notes.md / src/spec.md are not W1 targets: no W1 message (they are counted code/spec reads instead)
        for f in (self.root / "specs" / "001-x" / "notes.md", self.root / "src" / "spec.md"):
            r = self.run_hook(self.ev(str(f)))
            self.assertEqual(r.returncode, 0)
            self.assertNotIn("AIDD W1", r.stdout)

    def test_outside_root_silent(self):
        with tempfile.TemporaryDirectory() as other:
            r = self.run_hook(self.ev(str(Path(other).resolve() / "x.py")))
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertEqual(self.misses(), [])

    def test_agent_find_spec_event_silences_w1(self):
        self.add_find_spec("test")
        r = self.run_hook(self.ev(self.spec()))
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_hook_find_spec_event_does_not_silence(self):
        # aidd:FR-026 / AC-019: the prompt hook's own find_spec run never silences
        self.add_find_spec("hook")
        r = self.run_hook(self.ev(self.spec()))
        self.assertEqual(r.returncode, 0)
        self.assertIn("AIDD W1", self.ctx(r))

    def test_grep_nudges_despite_hook_find_spec(self):
        self.add_find_spec("hook")
        r = self.run_hook(self.tool_ev("Grep", pattern="code_state", path=str(self.root / "skill" / "scripts")))
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("permissionDecision", r.stdout)
        self.assertIn("aidd graphs show code", self.ctx(r))
        self.assertIn("no code graph yet: run aidd graphs refresh code", self.ctx(r))
        ms = self.misses()
        self.assertEqual([m["silenced"] for m in ms], [False])
        self.assertEqual(ms[0]["tool"], "Grep")

    def test_bash_grep_rn_nudges(self):
        self.add_find_spec("hook")
        r = self.run_hook(self.tool_ev("Bash", command="grep -rn code_state skill/scripts"))
        self.assertEqual(r.returncode, 0)
        self.assertIn("aidd graphs show code", self.ctx(r))
        self.assertEqual([(m["tool"], m["silenced"]) for m in self.misses()], [("Bash", False)])

    def test_py_read_nudges(self):
        r = self.run_hook(self.ev(self.py()))
        self.assertEqual(r.returncode, 0)
        self.assertIn("aidd graphs show code mod", self.ctx(r))
        self.assertEqual(len(self.misses()), 1)

    def test_code_name_hint_for_requirement_code(self):
        r = self.run_hook(self.tool_ev("Grep", pattern="FR-025", path=str(self.root / "skill")))
        self.assertIn("find_spec.py --code FR-025", self.ctx(r))

    def test_ranged_read_and_uncounted_commands_silent(self):
        cases = [
            self.ev(self.py(), limit=20),
            self.ev(self.py(), offset=5),
            self.tool_ev("Bash", command="git grep code_state skill/scripts"),
            self.tool_ev("Bash", command="python skill/scripts/find_spec.py --code FR-025 | grep FR"),
            self.tool_ev("Bash", command="aidd graphs show code foo"),
            self.tool_ev("Bash", command="ls skill"),
            self.tool_ev("Grep", pattern="x", path=str(self.root / ".git")),
            self.tool_ev("Grep", pattern="x", path=str(self.root.parent)),
        ]
        for c in cases:
            r = self.run_hook(c)
            self.assertEqual((r.returncode, r.stdout), (0, ""), c)
        self.assertEqual(self.misses(), [])

    def test_agent_query_silences_within_300s(self):
        # AC-019: source='bash' silences for 300 s
        self.add_find_spec("bash", age=100)
        r = self.run_hook(self.tool_ev("Grep", pattern="code_state", path=str(self.root / "skill")))
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertEqual([m["silenced"] for m in self.misses()], [True])

    def test_agent_query_older_than_300s_does_not_silence(self):
        # AC-019: after 300 s the nudge comes back
        self.add_find_spec("bash", age=400)
        r = self.run_hook(self.tool_ev("Grep", pattern="code_state", path=str(self.root / "skill")))
        self.assertIn("aidd graphs show code", self.ctx(r))
        self.assertEqual([m["silenced"] for m in self.misses()], [False])

    def test_throttle_once_per_300s_but_every_search_recorded(self):
        out = [self.run_hook(self.tool_ev("Grep", pattern="code_state", path=str(self.root / "skill"))).stdout
               for _ in range(3)]
        self.assertTrue(out[0])
        self.assertEqual(out[1:], ["", ""])
        self.assertEqual(len(self.misses()), 3)

    def test_no_project_no_events_no_message(self):
        with tempfile.TemporaryDirectory() as bare:
            bare = Path(bare).resolve()
            (bare / "a.py").write_text("x=1\n", encoding="utf-8")
            for ev in ({"session_id": self.sid, "cwd": str(bare), "tool_name": "Read",
                        "tool_input": {"file_path": str(bare / "a.py")}},
                       {"session_id": self.sid, "cwd": str(bare), "tool_name": "Bash",
                        "tool_input": {"command": "grep -rn x ."}}):
                r = self.run_hook(ev)
                self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertEqual(self.misses(), [])

    def test_ac020_two_misses_of_three_searches(self):
        r1 = self.run_hook(self.tool_ev("Grep", pattern="code_state", path=str(self.root / "skill")))
        r2 = self.run_hook(self.ev(self.py()))
        self.add_find_spec("bash")
        r3 = self.run_hook(self.tool_ev("Bash", command="grep -rn code_state skill/scripts"))
        self.assertTrue(r1.stdout)
        self.assertEqual((r2.returncode, r3.returncode, r3.stdout), (0, 0, ""))
        ms = self.misses()
        self.assertEqual(len(ms), 3)
        self.assertEqual(sum(1 for m in ms if not m["silenced"]), 2)

    def test_ac020_status_line_end_to_end(self):
        import aidd_status
        self.run_hook(self.tool_ev("Grep", pattern="code_state", path=str(self.root / "skill")))
        self.run_hook(self.ev(self.py()))
        self.add_find_spec("bash")
        self.run_hook(self.tool_ev("Bash", command="grep -rn code_state skill/scripts"))
        with self._env(), unittest.mock.patch.object(aidd_status, "_current_session", return_value=self.sid):
            self.assertEqual(aidd_status._graph_first_line(self.root),
                             "graph-first: 2 misses / 3 searches this session")
        with tempfile.TemporaryDirectory() as td:
            empty = Path(td).resolve()
            (empty / "specs").mkdir()
            with self._env(), unittest.mock.patch.object(aidd_status, "_current_session",
                                                         return_value=f"test-{uuid.uuid4().hex}"):
                self.assertEqual(aidd_status._graph_first_line(empty),
                                 "graph-first: 0 misses / 0 searches this session")

    def test_malformed_stdin(self):
        r = self.run_hook("{not json")
        self.assertEqual((r.returncode, r.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
