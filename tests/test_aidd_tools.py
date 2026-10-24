"""Spec 004 (FR-039, FR-042; AC-030, AC-032): tests of skill/scripts/aidd_tools.py (catalog and `size`).

Temp projects only; the real project state is never touched. Stdlib unittest; every subprocess has a timeout.
Run: python -m unittest tests.test_aidd_tools -v
"""
import json
import subprocess
import sys
import shutil
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS = REPO_ROOT / "skill" / "scripts" / "aidd_tools.py"


def run(root, *args, timeout=60):
    return subprocess.run([sys.executable, str(TOOLS), *args, "--root", str(root)],
                          capture_output=True, text=True, timeout=timeout,
                          encoding="utf-8", errors="replace")


def write(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def lines(out):
    return [ln for ln in out.splitlines() if ln.strip()]


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="aidd_tools_")
        self.root = Path(self.tmp)
        write(self.root, "tools/check_x.py", '"""Check things."""\n# supports --check\n')
        write(self.root, "eDoc/tools/db_verify.py", '"""Verify the database."""\n# supports --dry-run\n')
        write(self.root, "eDoc/tools/gen_y.py", '"""Generate the y report."""\n')
        self.cache = self.root / ".aidd" / "graphs" / "tools.cache.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_ac030_db_lists_matching_tool_with_description_and_flag(self):
        r = run(self.root, "db")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("db_verify.py", r.stdout)
        self.assertIn("Verify the database.", r.stdout)
        self.assertIn("--dry-run", r.stdout)
        self.assertNotIn("check_x.py", r.stdout)
        self.assertNotIn("gen_y.py", r.stdout)

    def test_check_flag_detected(self):
        r = run(self.root, "check_x")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("check_x.py", r.stdout)
        self.assertIn("Check things.", r.stdout)
        self.assertIn("--check", r.stdout)

    def test_json_parses(self):
        r = run(self.root, "db", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertIn("db_verify.py", json.dumps(data))

    def test_ac030_cap_40_lines_and_more_line(self):
        for i in range(60):
            write(self.root, "tools/bulk_%02d.py" % i, '"""Bulk tool %d."""\n' % i)
        r = run(self.root, "bulk")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = lines(r.stdout)
        self.assertLessEqual(len(out), 40)
        self.assertTrue(any("... +" in ln and "more" in ln for ln in out), r.stdout)

    def test_ac030_second_run_reuses_cache(self):
        r1 = run(self.root, "db")
        self.assertEqual(r1.returncode, 0, r1.stderr)
        self.assertTrue(self.cache.is_file(), "cache file not written")
        body1 = self.cache.read_bytes()
        mtime1 = self.cache.stat().st_mtime_ns
        r2 = run(self.root, "db")
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertEqual(self.cache.read_bytes(), body1)
        self.assertEqual(self.cache.stat().st_mtime_ns, mtime1, "cache was rewritten (rescan)")
        self.assertEqual(r1.stdout, r2.stdout)

    def test_ac030_changed_tool_invalidates_cache(self):
        run(self.root, "db")
        body1 = self.cache.read_bytes()
        write(self.root, "eDoc/tools/db_verify.py", '"""Verify the database again."""\n# --dry-run\n')
        r = run(self.root, "db")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotEqual(self.cache.read_bytes(), body1)
        self.assertIn("Verify the database again.", r.stdout)


class SizeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="aidd_size_")
        self.root = Path(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def size(self, *files):
        r = run(self.root, "size", "--files", *files)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def cls(self, out):
        for ln in out.splitlines():
            if ln.startswith("Analysis parameters:"):
                return ln.split("size=")[1].split(";")[0].strip()
        self.fail("no 'Analysis parameters:' line in:\n" + out)

    def test_ac032_classes_by_file_count(self):
        self.assertEqual(self.cls(self.size("a.py")), "XS")
        self.assertEqual(self.cls(self.size("a.py", "b.py")), "S")
        self.assertEqual(self.cls(self.size("a.py", "b.py", "c.py", "d.py")), "M")
        self.assertEqual(self.cls(self.size(*["f%d.py" % i for i in range(9)])), "L")

    def test_ac032_sensitive_area_is_L(self):
        for f in ("schema.sql", "skill/hooks/x.py", "aidd/cli.py"):
            self.assertEqual(self.cls(self.size(f)), "L", f)

    def test_ac032_xs_parameters(self):
        out = self.size("a.py")
        low = out.lower()
        self.assertTrue(out.rstrip().splitlines()[-1].startswith("RESULT: ok"), out)
        self.assertIn("run_parallel", out)
        self.assertIn("--changed", out)
        self.assertIn("no refresh", low)
        self.assertIn("auditor", low)
        nc = [ln for ln in out.splitlines() if "not created" in ln.lower()]
        self.assertTrue(nc, out)
        for word in ("graph", "snapshot", "job"):
            self.assertIn(word, nc[0].lower())

    def test_ac032_l_parameters(self):
        out = self.size("skill/hooks/x.py")
        low = out.lower()
        self.assertIn("refresh", low)
        self.assertIn("snapshot", low)
        self.assertIn("auditor", low)
        self.assertIn("domain", low)

    def test_ac032_spec_reads_target_files(self):
        write(self.root, "specs/001-x/tasks.md", "\n".join([
            "# Tasks", "",
            "| Task | Refs | Target | Type | | | Notes |",
            "|---|---|---|---|---|---|---|",
            "| T-01 | FR-001 | skill/scripts/a.py | LOGIC | | | one |",
            "| T-02 | FR-002 | skill/scripts/b.py | LOGIC | | | two |",
            "| T-03 | FR-003 | tests/test_c.py | LOGIC | | | three |",
            "| T-04 | FR-004 | skill/scripts/d.py | LOGIC | | | four |",
            "| T-05 | FR-005 | skill/scripts/a.py (same owner as T-01) | LOGIC | | | dup |",
            "| T-06 | FR-006 | specs/001-x/evidence/out.txt | DOC | | | evidence |",
            ""]))
        r = run(self.root, "size", "--spec", "001-x")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.cls(r.stdout), "M", r.stdout)

    def test_size_json_parses(self):
        r = run(self.root, "size", "--files", "a.py", "b.py", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertIn("S", json.dumps(data))


if __name__ == "__main__":
    unittest.main()
