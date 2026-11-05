"""Tests for skill/hooks/tool_first_hint.py (spec 004 FR-049..FR-054, AC-041..AC-046; subprocess, stdlib,
throwaway evidence dir)."""
import importlib.util
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
HOOK = ROOT / "skill" / "hooks" / "tool_first_hint.py"
sys.path.insert(0, str(ROOT / "skill" / "scripts"))
import aidd_evidence  # noqa: E402

ROW = "| T-{t} | FR-{f} | `eDoc/supabase/migrations/{m}.sql` | LOGIC | | {s} |"
SPECS = ("F36-eDoc-Purchasing", "F37-eDoc-Supplier-Invoice", "F38-eDoc-Import-Costing", "F39-eDoc-X")
OWNER_CALLS = ((91, 12, "3411_pinv_base"), (92, 13, "3412_pinv_ret"), (93, 14, "3413_imc_base"),
               (94, 15, "3414_imc_cost"))
UNRELATED = (("alpha", "beta"), ("x = 1", "x = 2; y"), ("## A", "## B\nmore"), ("foo()", "bar(baz)"))


class ToolFirstHintCase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name).resolve()
        for s in SPECS:
            d = self.root / "specs" / s
            d.mkdir(parents=True)
            (d / "tasks.md").write_text("# tasks\n", encoding="utf-8")
        self.evid = self.root / "evid"
        self.evid.mkdir()
        self.sid = f"test-{uuid.uuid4().hex}"
        self.env = dict(os.environ, AIDD_TESTING="1", AIDD_EVIDENCE_DIR=str(self.evid))
        self.cwd = str(self.root)

    def run_hook(self, stdin):
        return subprocess.run(
            [sys.executable, str(HOOK)], input=stdin if isinstance(stdin, str) else json.dumps(stdin),
            capture_output=True, text=True, encoding="utf-8", timeout=15, env=self.env, cwd=self.cwd)

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

    def edit_ev(self, rel, old, new):
        return {"session_id": self.sid, "cwd": self.cwd, "tool_name": "Edit",
                "tool_input": {"file_path": str(Path(self.cwd) / rel), "old_string": old, "new_string": new}}

    def shell_ev(self, command, tool="Bash"):
        return {"session_id": self.sid, "cwd": self.cwd, "tool_name": tool, "tool_input": {"command": command}}

    def ctx(self, r):
        return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout else ""

    def misses(self):
        with self._env():
            return [e["detail"] for e in aidd_evidence.events(self.root, session=self.sid, kind="tool_miss")]

    def add_query(self, source, age=0.0):
        """Append a tool_query event to the session log, stamped `age` seconds in the past."""
        with self._env():
            with unittest.mock.patch.object(aidd_evidence.time, "time", return_value=time.time() - age):
                aidd_evidence.append(self.root, self.sid, "tool_query", source=source, command="aidd tools x")

    def load_hook(self):
        spec = importlib.util.spec_from_file_location("tool_first_hint", HOOK)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def owner_calls(self):
        """The four AC-046 status edits, one per tasks.md (F36, F37, F38, F39)."""
        out = []
        for spec, (t, f, m) in zip(SPECS, OWNER_CALLS):
            out.append(self.run_hook(self.edit_ev(f"specs/{spec}/tasks.md", ROW.format(t=t, f=f, m=m, s=""),
                                                  ROW.format(t=t, f=f, m=m, s="done"))))
        return out

    def gen_calls(self, ns=(6, 7, 8, 9)):
        return [self.run_hook(self.shell_ev(f"python tools/gen_f3{n}_tests.py --apply specs/F3{n}")) for n in ns]

    def test_shape_normalises_quotes_paths_digits(self):
        mod = self.load_hook()
        self.assertEqual(mod._shape(ROW.format(t=91, f=12, m="3411_pinv_base", s="done")),
                         "| T-<N> | FR-<N> | <Q> | LOGIC | | done |")
        self.assertEqual(mod._shape("python tools/gen_f36_tests.py --apply specs/F36"), "python <P> --apply <P>")
        self.assertEqual(mod._shape('a  "x"\n  \'y\' 7'), "a <Q> <Q> <N>")

    def test_ac046_owner_case_four_status_edits(self):
        rs = self.owner_calls()
        for r in rs[:3]:
            self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertEqual(rs[3].returncode, 0)
        c = self.ctx(rs[3])
        self.assertIn("aidd tools md", c)
        self.assertIn("4 edits with the same shape", c)
        ms = self.misses()
        self.assertEqual(len(ms), 1)
        self.assertEqual(ms[0]["kind"], "same_shape")
        self.assertEqual(ms[0]["count"], 4)

    def test_ac041_one_advisory_only(self):
        self.owner_calls()
        r = self.run_hook(self.edit_ev("specs/F36-eDoc-Purchasing/tasks.md",
                                       ROW.format(t=95, f=16, m="3415_x", s=""),
                                       ROW.format(t=95, f=16, m="3415_x", s="done")))
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertEqual(len(self.misses()), 1)

    def test_ac042_unrelated_shapes_no_advisory(self):
        for spec, (old, new) in zip(SPECS, UNRELATED):
            r = self.run_hook(self.edit_ev(f"specs/{spec}/tasks.md", old, new))
            self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertEqual(self.misses(), [])

    def test_same_file_four_edits_fires_same_file(self):
        rs = [self.run_hook(self.edit_ev("specs/F36-eDoc-Purchasing/tasks.md", old, new)) for old, new in UNRELATED]
        for r in rs[:3]:
            self.assertEqual((r.returncode, r.stdout), (0, ""))
        c = self.ctx(rs[3])
        self.assertTrue(c)
        ms = self.misses()
        self.assertFalse(ms[0]["kind"] == "same_shape")
        self.assertTrue(ms[0]["kind"] == "same_file")
        self.assertIn("specs/F36-eDoc-Purchasing/tasks.md", c)

    def test_window_older_than_900s_does_not_count(self):
        for spec, (t, f, m) in list(zip(SPECS, OWNER_CALLS))[:3]:
            r = self.run_hook(self.edit_ev(f"specs/{spec}/tasks.md", ROW.format(t=t, f=f, m=m, s=""),
                                           ROW.format(t=t, f=f, m=m, s="done")))
            self.assertEqual((r.returncode, r.stdout), (0, ""))
        with self._env():
            path = aidd_evidence.tool_first_state_path(self.sid)
        state = json.loads(path.read_text(encoding="utf-8"))
        for section in ("shapes", "files"):
            state[section] = {k: [ts - 901 for ts in v] for k, v in state[section].items()}
        path.write_text(json.dumps(state), encoding="utf-8")
        t, f, m = OWNER_CALLS[3]
        r = self.run_hook(self.edit_ev(f"specs/{SPECS[3]}/tasks.md", ROW.format(t=t, f=f, m=m, s=""),
                                       ROW.format(t=t, f=f, m=m, s="done")))
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_shell_four_consecutive_same_shape(self):
        rs = self.gen_calls()
        for r in rs[:3]:
            self.assertEqual((r.returncode, r.stdout), (0, ""))
        c = self.ctx(rs[3])
        self.assertIn("4 shell commands in a row with the same shape", c)
        self.assertIn("aidd tools python gen_f39_tests", c)
        self.assertEqual(self.misses()[0]["kind"], "same_command")

    def test_shell_run_broken_by_other_command(self):
        rs = self.gen_calls((6, 7, 8))
        rs.append(self.run_hook(self.shell_ev("python -m unittest -v")))
        rs += self.gen_calls((9,))
        for r in rs:
            self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_read_only_git_never_counts(self):
        rs = [self.run_hook(self.shell_ev("git status")) for _ in range(5)]
        rs += [self.run_hook(self.shell_ev("git log -n 3", tool="PowerShell")) for _ in range(5)]
        for r in rs:
            self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertEqual(self.misses(), [])

    def test_aidd_tools_command_records_tool_query(self):
        r = self.run_hook(self.shell_ev("aidd tools migration"))
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        with self._env():
            qs = aidd_evidence.events(self.root, session=self.sid, kind="tool_query")
        self.assertEqual(len(qs), 1)
        self.assertEqual(qs[0]["detail"]["source"], "agent")

    def test_ac043_tools_query_silences_for_300s(self):
        self.add_query("agent")
        for r in self.owner_calls():
            self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertEqual(self.misses(), [])
        self.sid = f"test-{uuid.uuid4().hex}"
        self.add_query("agent", age=301)
        rs = self.owner_calls()
        self.assertIn("aidd tools md", self.ctx(rs[3]))

    def test_hook_source_query_does_not_silence(self):
        self.add_query("hook")
        rs = self.owner_calls()
        self.assertIn("aidd tools md", self.ctx(rs[3]))

    def test_ac044_corrupt_state_file(self):
        with self._env():
            path = aidd_evidence.tool_first_state_path(self.sid)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\xff{")
        r = self.run_hook(self.edit_ev("specs/F36-eDoc-Purchasing/tasks.md", "alpha", "beta"))
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
        state = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(state["edits"], 1)

    def test_malformed_stdin(self):
        r = self.run_hook("{not json")
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_no_project_root_no_output(self):
        with tempfile.TemporaryDirectory() as bare:
            bare = Path(bare).resolve()
            self.cwd = str(bare)
            for spec, (t, f, m) in zip(SPECS, OWNER_CALLS):
                r = self.run_hook(self.edit_ev(f"specs/{spec}/tasks.md", ROW.format(t=t, f=f, m=m, s=""),
                                               ROW.format(t=t, f=f, m=m, s="done")))
                self.assertEqual((r.returncode, r.stdout), (0, ""))
        with self._env():
            path = aidd_evidence.tool_first_state_path(self.sid)
        self.assertFalse(path.exists())

    def test_edits_counter_counts_every_edit_tool(self):
        f = str(self.root / "specs" / "F36-eDoc-Purchasing" / "tasks.md")
        base = {"session_id": self.sid, "cwd": self.cwd}
        for tool, ti in (("Write", {"file_path": f, "content": "x"}),
                         ("NotebookEdit", {"notebook_path": str(self.root / "n.ipynb"), "new_source": "y"}),
                         ("MultiEdit", {"file_path": f, "edits": [{"old_string": "a", "new_string": "b"}]}),
                         ("Edit", {"file_path": f, "old_string": "c", "new_string": "d"})):
            r = self.run_hook(dict(base, tool_name=tool, tool_input=ti))
            self.assertEqual(r.returncode, 0)
        with self._env():
            self.assertEqual(aidd_evidence.read_tool_first_state(self.sid)["edits"], 4)

    def test_ac045_status_line(self):
        import aidd_status
        self.owner_calls()
        self.gen_calls()
        with self._env(), unittest.mock.patch.object(aidd_status, "_current_session", return_value=self.sid):
            self.assertEqual(aidd_status._tool_first_line(self.root),
                             "tool-first: 2 advisories / 4 edits this session")
        with self._env(), unittest.mock.patch.object(aidd_status, "_current_session",
                                                     return_value=f"test-{uuid.uuid4().hex}"):
            self.assertEqual(aidd_status._tool_first_line(self.root),
                             "tool-first: 0 advisories / 0 edits this session")

    def test_new_kinds_are_session_kinds(self):
        self.assertTrue({"tool_miss", "tool_query"} <= aidd_evidence.SESSION_KINDS)


if __name__ == "__main__":
    unittest.main()
