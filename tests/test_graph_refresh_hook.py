import io
import json
import os
import runpy
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

HOOK = Path(__file__).resolve().parent.parent / "skill" / "hooks" / "graph_refresh.py"
ENV_OFF = "AIDD_" + "GRAPHS"


def run_hook(event, fake, env=None):
    """Run the hook in-process with a fake graphs module; returns (exit_code, stdout)."""
    out = io.StringIO()
    code = None
    payload = event if isinstance(event, str) else json.dumps(event)
    with patch.dict(sys.modules), patch.dict(os.environ, env or {}), \
            patch.object(sys, "stdin", io.StringIO(payload)), patch.object(sys, "stdout", out):
        sys.modules.pop("aidd_graphs", None)
        if fake is not None:
            sys.modules["aidd_graphs"] = fake
        try:
            runpy.run_path(str(HOOK), run_name="__main__")
        except SystemExit as e:
            code = e.code
    return code, out.getvalue()


def make_fake(match=None, boom=False):
    calls = []
    f = types.ModuleType("aidd_graphs")

    def match_watch(root, path):
        if boom:
            raise RuntimeError("x")
        return match(Path(path)) if match else []

    def refresh(root, name, background=False):
        calls.append((str(root), name, background))
        if boom:
            raise RuntimeError("y")
        return {"started": True, "reason": "", "pid": 1, "log": ""}

    f.match_watch, f.refresh, f.calls = match_watch, refresh, calls
    return f


class TestGraphRefreshHook(unittest.TestCase):
    def setUp(self):
        self._td = TemporaryDirectory()
        self.root = Path(self._td.name) / "proj"
        (self.root / "specs").mkdir(parents=True)
        (self.root / "db").mkdir()
        self.mig = self.root / "db" / "001.sql"
        self.mig.write_text("x")

    def tearDown(self):
        self._td.cleanup()

    def ev(self, **ti):
        return {"session_id": "s", "cwd": str(self.root), "tool_name": "Edit", "tool_input": ti}

    @staticmethod
    def match_db(p):
        return ["db"] if p.suffix == ".sql" else []

    def test_matching_path_refreshes_in_background(self):
        f = make_fake(self.match_db)
        code, out = run_hook(self.ev(file_path=str(self.mig)), f)
        self.assertEqual((code, out), (0, ""))
        self.assertEqual(len(f.calls), 1)
        self.assertEqual(f.calls[0][1:], ("db", True))

    def test_non_matching_path_does_nothing(self):
        f = make_fake(self.match_db)
        code, out = run_hook(self.ev(file_path=str(self.root / "a.py")), f)
        self.assertEqual((code, out), (0, ""))
        self.assertEqual(f.calls, [])

    def test_one_refresh_per_matching_name(self):
        f = make_fake(lambda p: ["a", "b"])
        run_hook(self.ev(file_path=str(self.mig)), f)
        self.assertEqual([c[1] for c in f.calls], ["a", "b"])

    def test_exceptions_swallowed(self):
        f = make_fake(boom=True)
        self.assertEqual(run_hook(self.ev(file_path=str(self.mig)), f), (0, ""))
        f2 = make_fake(self.match_db)

        def bad_refresh(*a, **k):
            raise RuntimeError("z")
        f2.refresh = bad_refresh
        self.assertEqual(run_hook(self.ev(file_path=str(self.mig)), f2), (0, ""))

    def test_env_off_disables(self):
        f = make_fake(self.match_db)
        code, out = run_hook(self.ev(file_path=str(self.mig)), f, env={ENV_OFF: "off"})
        self.assertEqual((code, out), (0, ""))
        self.assertEqual(f.calls, [])

    def test_multiple_edits_in_one_event(self):
        m2 = self.root / "db" / "002.sql"
        f = make_fake(lambda p: ["db"] if p.suffix == ".sql" else (["py"] if p.suffix == ".py" else []))
        run_hook(self.ev(file_path=str(self.root / "a.py"),
                         edits=[{"file_path": str(self.mig)}, {"file_path": str(m2)}, "junk"]), f)
        # both migrations hit graph "db": refreshed once per event (deduped), plus "py"
        self.assertEqual(sorted(c[1] for c in f.calls), ["db", "py"])

    def test_notebook_path(self):
        f = make_fake(lambda p: ["nb"] if p.suffix == ".ipynb" else [])
        run_hook(self.ev(notebook_path=str(self.root / "n.ipynb")), f)
        self.assertEqual([c[1] for c in f.calls], ["nb"])

    def test_relative_path_resolved_against_cwd(self):
        seen = []
        f = make_fake(lambda p: seen.append(p) or ["db"])
        run_hook(self.ev(file_path="db/001.sql"), f)
        self.assertTrue(seen and seen[0].is_absolute())
        self.assertEqual(seen[0], self.root / "db" / "001.sql")
        self.assertEqual(len(f.calls), 1)

    def test_missing_module_and_bad_payloads_are_noops(self):
        self.assertEqual(run_hook(self.ev(file_path=str(self.mig)), None)[1], "")
        f = make_fake(self.match_db)
        for bad in ("[]", "null", "not json", {"tool_input": "x"}, {"tool_input": {"file_path": 5}}):
            self.assertEqual(run_hook(bad, f), (0, ""))
        self.assertEqual(f.calls, [])


if __name__ == "__main__":
    unittest.main()
