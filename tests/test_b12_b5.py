"""Amendment 09 backlog B12 (`aidd close-ledger`) and B5 (`aidd red`) - stdlib unittest, fixtures in temp dirs.

B12: read-only draft of the closing audit (heading, verification table from evidence/verify-*.txt, R10 freshness).
B5 : RED receipt `evidence/red-T-nn.txt` written by the CLI (the only writer of evidence/ under R9), plus `--check`.
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS))

SPEC_MD = """# Spec

## Verification

Scope: auto, code/src/**, code/lib/*.py

| # | Command | Expected | Covers |
|---|---|---|---|
| V-1 | `python db_verify.py --tap` | exit 0 | FR-1 |
| V-2 | `python -m pytest tests -q` | exit 0 | FR-2 |
| V-3 | `npm test` | exit 0 | FR-3 |
| V-4 | `npx playwright test` | exit 0 | FR-4 |

## Other
"""

QA = """# QA

## Execution evidence
| Code | Kind | Evidence | Verified by |
|---|---|---|---|
| SCREEN-1 | command-output | specs/S1/evidence/e2e.txt | agent |

## Open exceptions
"""

EVID = {
    "verify-V-1.txt": "# python db_verify.py --tap | exit 0 | 2026-11-04T10:00:00\n[ok] a.test.sql: ok=5 not_ok=0\n[ok] b.test.sql: ok=3 not_ok=0\n== RESULT: OK (0 failing item(s))\n",
    "verify-V-2.txt": "# python -m pytest tests -q | exit 0 | 2026-11-04T10:01:00\n.....\n12 passed, 1 warning in 1s\n",
    "verify-V-3.txt": "# npm test | exit 0 | 2026-11-04T10:02:00\n\x1b[2m      Tests \x1b[22m \x1b[32m254 passed\x1b[39m (254)\n",
    "verify-V-4.txt": "# npx playwright test | exit 0 | 2026-11-04T10:03:00\n  7 passed (3.1s)\n",
}


def make_spec(tmp, code_newer=False, crlf=False):
    root = Path(tmp) / "repo"
    spec = root / "specs" / "S1"
    ev = spec / "evidence"
    ev.mkdir(parents=True)
    (root / "code" / "src").mkdir(parents=True)
    (root / "code" / "lib").mkdir(parents=True)
    code = root / "code" / "src" / "a.ts"
    code.write_text("x")
    (root / "code" / "lib" / "b.py").write_text("y")
    spec_text = SPEC_MD.replace("\n", "\r\n") if crlf else SPEC_MD
    (spec / "spec.md").write_bytes(spec_text.encode())
    (spec / "qa-audit.md").write_text(QA)
    (spec / "tasks.md").write_text("Approved: 2026-11-04 hash:c1b501a5c7a9\n")
    for n, t in EVID.items():
        (ev / n).write_text(t)
    (ev / "e2e.txt").write_text("ok")
    now = time.time()
    for p in list(ev.iterdir()):
        os.utime(p, (now - 100, now - 100))
    os.utime(code, (now + 500, now + 500) if code_newer else (now - 1000, now - 1000))
    os.utime(root / "code" / "lib" / "b.py", (now - 1000, now - 1000))
    return spec


def run_script(name, *args, cwd=None):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, str(SCRIPTS / name), *args], cwd=str(cwd) if cwd else None, env=env,
                          capture_output=True, text=True, encoding="utf-8")


def run_cli(*args, cwd=None):
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT), PYTHONIOENCODING="utf-8", AIDD_HOME=str(REPO_ROOT / "skill"))
    return subprocess.run([sys.executable, "-m", "aidd.cli", *args], cwd=str(cwd) if cwd else None, env=env,
                          capture_output=True, text=True, encoding="utf-8")


class TestCloseLedger(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        import aidd_close_ledger as cl
        self.cl = cl

    def build(self, spec, **kw):
        kw.setdefault("domains", ["x"])
        kw.setdefault("verify_hash", "abcdef012345")
        return self.cl.build(spec, **kw)

    def test_rows_and_summaries(self):
        spec = make_spec(self._t.name, crlf=True)
        data = self.build(spec, domains=["backend", "ui"], verify_hash="5414dd747407")
        self.assertEqual([r["id"] for r in data["rows"]], ["V-1", "V-2", "V-3", "V-4"])
        res = {r["id"]: r["result"] for r in data["rows"]}
        self.assertIn("0 failing", res["V-1"])
        self.assertIn("ok=8", res["V-1"])
        self.assertIn("12 passed", res["V-2"])
        self.assertIn("254 passed", res["V-3"])
        self.assertIn("7 passed", res["V-4"])
        self.assertTrue(all(r["exit"] == "0" for r in data["rows"]))

    def test_header(self):
        spec = make_spec(self._t.name)
        data = self.build(spec, domains=["backend", "ui"], verify_hash="5414dd747407")
        self.assertEqual(data["header"], "CLOSING AUDIT [domains: backend, ui] [tasks:c1b501a5] [verify:5414dd74]")

    def test_domains_default_to_rules_required_domains(self):
        spec = make_spec(self._t.name)
        import aidd_rules
        data = self.cl.build(spec, domains=None, verify_hash="abcdef012345")
        want = ", ".join(sorted(aidd_rules.required_domains(spec)))
        self.assertIn(f"[domains: {want}]", data["header"])

    def test_text_table(self):
        spec = make_spec(self._t.name)
        out = self.cl.render_text(self.build(spec))
        self.assertIn("## Verification summary", out)
        self.assertIn("| # | Command | Exit | Result | Evidence |", out)
        self.assertIn("| V-2 |", out)
        self.assertIn("evidence/verify-V-2.txt", out)

    def test_fresh_ready(self):
        spec = make_spec(self._t.name, code_newer=False)
        data = self.build(spec, check_fresh=True)
        self.assertEqual(data["stale"], [])
        self.assertTrue(data["ready"])
        self.assertIn("LISTO PARA AUDITAR", self.cl.render_text(data))

    def test_stale(self):
        spec = make_spec(self._t.name, code_newer=True)
        data = self.build(spec, check_fresh=True)
        self.assertGreaterEqual(len(data["stale"]), 5)   # 4 verify files + e2e.txt
        self.assertFalse(data["ready"])
        out = self.cl.render_text(data)
        self.assertIn("STALE", out)
        self.assertNotIn("LISTO PARA AUDITAR", out)

    def test_scope_falls_back_to_task_targets(self):
        spec = make_spec(self._t.name)
        text = (spec / "spec.md").read_text().replace("Scope: auto, code/src/**, code/lib/*.py\n", "")
        (spec / "spec.md").write_text(text)
        (spec / "tasks.md").write_text(
            "Approved: 2026-11-04 hash:c1b501a5c7a9\n| T-1 | FR-1 | `code/src/a.ts` | LOGIC | | | |\n")
        now = time.time()
        os.utime(spec.parent.parent / "code" / "src" / "a.ts", (now + 500, now + 500))
        self.assertTrue(self.build(spec, check_fresh=True)["stale"])

    def test_missing_evidence_marked(self):
        spec = make_spec(self._t.name)
        (spec / "evidence" / "verify-V-3.txt").unlink()
        data = self.build(spec, check_fresh=True)
        row = [r for r in data["rows"] if r["id"] == "V-3"][0]
        self.assertIn("FALTA", row["result"])
        self.assertFalse(data["ready"])

    def test_script_json_and_no_writes(self):
        spec = make_spec(self._t.name)
        before = sorted(p.name for p in spec.rglob("*"))
        r = run_script("aidd_close_ledger.py", str(spec), "--check-fresh", "--json", "--domains", "a,b",
                       "--verify-hash", "5414dd747407")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(json.loads(r.stdout)["header"].startswith("CLOSING AUDIT [domains: a, b]"))
        self.assertEqual(sorted(p.name for p in spec.rglob("*")), before)

    def test_cli_registered(self):
        spec = make_spec(self._t.name)
        r = run_cli("close-ledger", str(spec), "--domains", "a", "--verify-hash", "5414dd747407")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("CLOSING AUDIT [domains: a] [tasks:c1b501a5] [verify:5414dd74]", r.stdout)

    def test_missing_spec_exit_two(self):
        r = run_cli("close-ledger", str(Path(self._t.name) / "nope"))
        self.assertEqual(r.returncode, 2)


TASKS = """Approved: 2026-11-04 hash:c1b501a5c7a9

| Task | Codes | Target file | View / logic |
|---|---|---|---|
| T-01 | API-001 | `tests/test_new.py` | LOGIC |
| T-02 | API-002 | `src/impl.py` | LOGIC |
| T-03 | API-003 | `tests/test_old.py` | LOGIC |

### T-01
- Agent role: tests

### T-02
- Agent role: builder

### T-03
- Agent role: tests
- RED: exempt (pure refactor with an existing test)
"""


def make_red_project(tmp):
    root = Path(tmp) / "proj"
    spec = root / "specs" / "001-x"
    spec.mkdir(parents=True)
    (spec / "spec.md").write_text("# spec\n")
    (spec / "tasks.md").write_text(TASKS)
    (root / "tests").mkdir()
    (root / "tests" / "test_new.py").write_text("import unittest\nclass T(unittest.TestCase):\n"
                                                "    def test_a(self):\n        self.assertEqual(1, 2)\n")
    (root / "tests" / "test_green.py").write_text("import unittest\nclass T(unittest.TestCase):\n"
                                                  "    def test_a(self):\n        self.assertEqual(1, 1)\n")
    return root, spec


class TestRed(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.root, self.spec = make_red_project(self._t.name)

    def test_failing_test_writes_receipt(self):
        r = run_cli("red", sys.executable, "-m", "unittest", "tests/test_new.py", "--task", "T-01",
                    "--spec", "001-x", cwd=self.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rec = self.spec / "evidence" / "red-T-01.txt"
        self.assertTrue(rec.is_file())
        text = rec.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# RED T-01 | exit 1 | "), text[:80])
        for key in ("command:", "exit: 1", "first_failure:", "timestamp:", "test_file: tests/test_new.py",
                    "test_file_sha1:"):
            self.assertIn(key, text)
        self.assertIn("test_a", text.split("first_failure:", 1)[1].split("\n", 1)[0])

    def test_passing_test_is_no_red(self):
        r = run_cli("red", sys.executable, "-m", "unittest", "tests/test_green.py", "--task", "T-01",
                    "--spec", "001-x", cwd=self.root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("NO-RED: el test pas", r.stdout)
        self.assertIn("no hay RED", r.stdout)
        self.assertFalse((self.spec / "evidence" / "red-T-01.txt").exists())

    def test_task_is_required_and_validated(self):
        r = run_cli("red", sys.executable, "-c", "raise SystemExit(1)", "--spec", "001-x", cwd=self.root)
        self.assertEqual(r.returncode, 2)
        r = run_cli("red", sys.executable, "-c", "raise SystemExit(1)", "--task", "bogus", "--spec", "001-x",
                    cwd=self.root)
        self.assertEqual(r.returncode, 2)

    def test_single_spec_is_inferred(self):
        r = run_cli("red", sys.executable, "-c", "raise SystemExit(3)", "--task", "T-02", cwd=self.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((self.spec / "evidence" / "red-T-02.txt").is_file())

    def test_check_lists_missing_and_present(self):
        r = run_cli("red", "--check", "001-x", cwd=self.root)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("MISSING: T-01", r.stdout)
        self.assertNotIn("MISSING: T-02", r.stdout)           # builder task
        self.assertIn("EXEMPT: T-03", r.stdout)
        run_cli("red", sys.executable, "-m", "unittest", "tests/test_new.py", "--task", "T-01", "--spec", "001-x",
                cwd=self.root)
        r = run_cli("red", "--check", "001-x", cwd=self.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("OK: T-01", r.stdout)
        self.assertIn("red-T-01.txt", r.stdout)

    def test_check_flags_changed_test_file(self):
        run_cli("red", sys.executable, "-m", "unittest", "tests/test_new.py", "--task", "T-01", "--spec", "001-x",
                cwd=self.root)
        (self.root / "tests" / "test_new.py").write_text("changed\n")
        r = run_cli("red", "--check", "001-x", cwd=self.root)
        self.assertIn("test file changed since the receipt", r.stdout)

    def test_check_unknown_spec_exit_two(self):
        self.assertEqual(run_cli("red", "--check", "999-none", cwd=self.root).returncode, 2)


if __name__ == "__main__":
    unittest.main()
