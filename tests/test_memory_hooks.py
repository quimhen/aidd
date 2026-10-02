"""Tests for skill/hooks/memory_context.py and memory_file_context.py (subprocess, stdlib)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = ROOT / "skill" / "hooks"
sys.path.insert(0, str(ROOT / "skill" / "scripts"))
sys.path.insert(0, str(HOOKS_DIR))

import aidd_memory  # noqa: E402
import _common  # noqa: E402


def run(name, stdin, cwd=None):
    env = {k: v for k, v in os.environ.items() if k != "AIDD_MEMORY_DIR"}
    return subprocess.run(
        [sys.executable, str(HOOKS_DIR / name)],
        input=stdin if isinstance(stdin, str) else json.dumps(stdin),
        capture_output=True, text=True, encoding="utf-8", timeout=15, env=env, cwd=cwd,
    )


class MemHookCase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name).resolve()
        (self.root / ".git").mkdir()
        self.sid = f"test-{uuid.uuid4().hex}"
        self.addCleanup(self._cleanup_markers)

    def _cleanup_markers(self):
        if _common.MARKER_DIR.exists():
            for m in _common.MARKER_DIR.glob(f"{self.sid}.mem-*"):
                m.unlink(missing_ok=True)

    def seed(self):
        aidd_memory.add_entry(self.root, type="decision", title="Use TOON for flows",
                              why="matches index", codes=["US-001"], files=["src/app.py"])


class TestMemoryContext(MemHookCase):
    def test_injects_digest(self):
        self.seed()
        r = run("memory_context.py", {"cwd": str(self.root), "session_id": self.sid})
        self.assertEqual(r.returncode, 0)
        self.assertIn("AIDD memory", r.stdout)
        self.assertIn("Use TOON for flows", r.stdout)

    def test_silent_without_memory(self):
        r = run("memory_context.py", {"cwd": str(self.root)})
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_silent_from_subdir(self):
        self.seed()
        sub = self.root / "a" / "b"
        sub.mkdir(parents=True)
        r = run("memory_context.py", {"cwd": str(sub)})
        self.assertIn("AIDD memory", r.stdout)

    def test_garbage_stdin_exit_zero(self):
        for payload in ("", "not json", "[1,2]", "null"):
            r = run("memory_context.py", payload, cwd=str(self.root))
            self.assertEqual(r.returncode, 0, payload)

    def test_corrupt_memory_file_exit_zero(self):
        mem = self.root / ".aidd" / "memory"
        mem.mkdir(parents=True)
        (mem / "project.toon").write_bytes(b"\xff\xfe garbage \x00")
        r = run("memory_context.py", {"cwd": str(self.root)})
        self.assertEqual(r.returncode, 0)


class TestMemoryFileContext(MemHookCase):
    def ev(self, fp, **extra):
        d = {"cwd": str(self.root), "session_id": self.sid, "tool_name": "Read",
             "tool_input": {"file_path": fp}}
        d.update(extra)
        return d

    def test_output_shape(self):
        self.seed()
        r = run("memory_file_context.py", self.ev(str(self.root / "src" / "app.py")))
        self.assertEqual(r.returncode, 0)
        out = json.loads(r.stdout)
        h = out["hookSpecificOutput"]
        self.assertEqual(h["hookEventName"], "PreToolUse")
        self.assertIn("Use TOON for flows", h["additionalContext"])

    def test_windows_backslash_path(self):
        self.seed()
        fp = str(self.root / "src" / "app.py").replace("/", "\\")
        r = run("memory_file_context.py", self.ev(fp))
        self.assertEqual(r.returncode, 0)
        self.assertIn("additionalContext", r.stdout)

    def test_once_per_session_and_file(self):
        self.seed()
        fp = str(self.root / "src" / "app.py")
        first = run("memory_file_context.py", self.ev(fp))
        second = run("memory_file_context.py", self.ev(fp))
        self.assertIn("additionalContext", first.stdout)
        self.assertEqual((second.returncode, second.stdout), (0, ""))
        other_session = run("memory_file_context.py", self.ev(fp, session_id=self.sid + "x"))
        try:
            self.assertIn("additionalContext", other_session.stdout)
        finally:
            for m in _common.MARKER_DIR.glob(f"{self.sid}x.mem-*"):
                m.unlink(missing_ok=True)

    def test_no_hits_is_silent_and_not_marked(self):
        self.seed()
        r = run("memory_file_context.py", self.ev(str(self.root / "other.py")))
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_silent_without_memory(self):
        r = run("memory_file_context.py", self.ev(str(self.root / "src" / "app.py")))
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_missing_file_path_and_garbage(self):
        self.seed()
        cases = [
            {"cwd": str(self.root), "tool_input": {}},
            {"cwd": str(self.root)},
            {"cwd": str(self.root), "tool_input": {"file_path": 5}},
            {"cwd": str(self.root), "tool_input": "x"},
            "", "not json", "[]", "null",
        ]
        for c in cases:
            r = run("memory_file_context.py", c, cwd=str(self.root))
            self.assertEqual(r.returncode, 0, c)
            self.assertEqual(r.stdout, "", c)

    def test_readonly_marker_dir_exit_zero(self):
        # Point TEMP at a path that is a regular file so mkdir of the marker dir fails.
        self.seed()
        blocker = self.root / "blocker"
        blocker.write_text("x")
        env = dict(os.environ, TMP=str(blocker), TEMP=str(blocker), TMPDIR=str(blocker))
        env.pop("AIDD_MEMORY_DIR", None)
        r = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "memory_file_context.py")],
            input=json.dumps(self.ev(str(self.root / "src" / "app.py"))),
            capture_output=True, text=True, encoding="utf-8", timeout=15, env=env)
        self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
