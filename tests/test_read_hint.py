"""Tests for skill/hooks/read_hint.py (subprocess, stdlib, throwaway evidence dir)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
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

    def test_non_target_silent(self):
        r = self.run_hook(self.ev(str(self.root / "specs" / "001-x" / "notes.md")))
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        r = self.run_hook(self.ev(str(self.root / "src" / "spec.md")))
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_find_spec_event_silent(self):
        aidd_evidence_env = dict(os.environ, AIDD_TESTING="1", AIDD_EVIDENCE_DIR=str(self.evid))
        old = {k: os.environ.get(k) for k in ("AIDD_TESTING", "AIDD_EVIDENCE_DIR")}
        os.environ.update(aidd_evidence_env)
        try:
            aidd_evidence.append_find_spec(self.root, self.sid, False, True, "test")
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        r = self.run_hook(self.ev(self.spec()))
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_malformed_stdin(self):
        r = self.run_hook("{not json")
        self.assertEqual((r.returncode, r.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
