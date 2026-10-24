"""T-42: tests for skill/scripts/aidd_triage.py (FR-037, AC-028). Temp project, CLI via subprocess."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "skill" / "scripts" / "aidd_triage.py"


def snapshot(root: Path):
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root))] = (p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest())
        else:
            out[str(p.relative_to(root)) + "/"] = None
    return out


def ev(root, spec, row, body, code=1):
    d = root / "specs" / spec / "evidence"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"verify-{row}.txt").write_text(f"# cmd {row} | exit {code} | 2026-01-01\n{body}", encoding="utf-8")


class TriageTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.root = Path(self._t.name)

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args, "--root", str(self.root)],
                              capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")

    def seed(self):
        ev(self.root, "001-a", "V-1", "[FAIL] a.test.sql\n")
        ev(self.root, "002-b", "V-1", "[FAIL] a.test.sql\n[FAIL] b.test.sql\n")
        ev(self.root, "001-a", "V-2", " FAIL  src/x.test.ts > does thing\n")
        ev(self.root, "002-b", "V-3", "FAILED tests/x.py::test_y\n")
        ev(self.root, "002-b", "V-4", "src/m.ts(3,5): error TS2304: cannot find\n")
        ev(self.root, "001-a", "V-5", "all good\n", code=0)

    def test_unittest_format(self):
        body = ("FAIL: test_z (tests.test_x.TestY.test_z)\n" "Traceback\n" "PermissionError: [WinError 5] denied\n" "FAILED (failures=1)\n")
        ev(self.root, "001-a", "V-1", body)
        ev(self.root, "002-b", "V-1", body + "ERROR: test_w (tests.test_x.TestY)\n" "FAILED (failures=1, errors=1)\n")
        r = self.run_cli("--json")
        d = json.loads(r.stdout)
        self.assertEqual(d["shared"], {"unittest:tests.test_x.TestY.test_z": ["001-a", "002-b"]}, r.stdout)
        self.assertEqual(d["own"], {"unittest:tests.test_x.TestY.test_w": ["002-b"]}, r.stdout)

    def test_shared_and_specific(self):
        self.seed()
        r = self.run_cli()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        lines = r.stdout.splitlines()
        a = [ln for ln in lines if "a.test.sql" in ln and ("SHARED" in ln.upper() or "2 specs" in ln)]
        self.assertTrue(a, r.stdout)
        b_lines = [ln for ln in lines if "b.test.sql" in ln]
        self.assertTrue(b_lines, r.stdout)
        self.assertFalse(any("2 specs" in ln or "SHARED" in ln.upper() for ln in b_lines), r.stdout)

    def test_other_kinds_extracted(self):
        self.seed()
        out = self.run_cli().stdout
        self.assertIn("x.test.ts", out)
        self.assertIn("tests/x.py::test_y", out)
        self.assertIn("error TS2304", out)

    def test_result_line_and_exit(self):
        self.seed()
        r = self.run_cli()
        self.assertTrue(r.stdout.rstrip().splitlines()[-1].startswith("RESULT: fail"), r.stdout)

    def test_glob_restricts(self):
        self.seed()
        r = self.run_cli("002-*")
        self.assertIn("b.test.sql", r.stdout)
        self.assertNotIn("x.test.ts", r.stdout)  # only in 001-a
        self.assertNotIn("001-a", r.stdout)
        self.assertFalse(any("a.test.sql" in ln and "SHARED" in ln.upper() and "0 " not in ln
                             for ln in r.stdout.splitlines() if ln.strip().startswith("a.test.sql")))

    def test_json_same_grouping(self):
        self.seed()
        r = self.run_cli("--json")
        data = json.loads(r.stdout)
        self.assertIn("shared", data)
        shared = json.dumps(data["shared"])
        self.assertIn("a.test.sql", shared)
        self.assertIn("001-a", shared)
        self.assertIn("002-b", shared)
        self.assertNotIn("b.test.sql", shared)
        own = json.dumps(data.get("own", {}))
        self.assertIn("b.test.sql", own)
        self.assertIn("002-b", own)

    def test_read_only(self):
        self.seed()
        before = snapshot(self.root)
        self.run_cli()
        self.run_cli("--json")
        self.run_cli("001-*")
        self.assertEqual(before, snapshot(self.root))

    def test_only_passes_exit_zero(self):
        ev(self.root, "001-a", "V-1", "ok\n", code=0)
        ev(self.root, "002-b", "V-1", "ok\n", code=0)
        r = self.run_cli()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stdout.rstrip().splitlines()[-1].startswith("RESULT: ok"), r.stdout)

    def test_empty_or_unreadable_evidence_never_raises(self):
        d = self.root / "specs" / "001-a" / "evidence"
        d.mkdir(parents=True)
        (d / "verify-V-1.txt").write_text("", encoding="utf-8")
        (d / "verify-V-2.txt").write_bytes(b"\xff\xfe\x00garbage\x80\n[FAIL")
        (d / "verify-V-3.txt").mkdir()  # a directory named like evidence
        for args in ([], ["--json"]):
            r = self.run_cli(*args)
            self.assertNotIn("Traceback", r.stderr)
            self.assertIn(r.returncode, (0, 1))
        r = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root / "nope")],
                           capture_output=True, text=True, timeout=60)
        self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()
