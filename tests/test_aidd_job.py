"""Spec 004 (FR-035, FR-036; AC-027): tests of skill/scripts/aidd_job.py (cached, content-keyed jobs).

Every test builds a temp project with a toy tool `check.py` that appends a line to counter.txt on each
execution, and drives the CLI through subprocess with a timeout. Stdlib unittest.
Run: python -m unittest tests.test_aidd_job -v
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JOB = REPO_ROOT / "skill" / "scripts" / "aidd_job.py"
NAME = "chk"

TOOL = """import sys, time
open(r'{counter}', 'a').write('x\\n')
{extra}
{result}
sys.exit({code})
"""


def make_tool(root, code=0, sleep=0, result=True, fname="check.py"):
    extra = "time.sleep(%s)" % sleep if sleep else ""
    res = "print('RESULT: ok - 3 items - evidence out.txt')" if result else "print('plain output')"
    p = root / fname
    p.write_text(TOOL.format(counter=str(root / "counter.txt"), extra=extra, result=res, code=code),
                 encoding="utf-8")
    return p


class JobBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="job_")
        self.root = Path(self.tmp)
        if shutil.which("git"):
            subprocess.run(["git", "init", "-q"], cwd=self.tmp, capture_output=True, timeout=60)
        (self.root / "src").mkdir()
        self.src = self.root / "src" / "a.py"
        self.src.write_text("print('aaaa')\n", encoding="utf-8")
        self.tool = make_tool(self.root)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def job(self, *args, timeout=60):
        return subprocess.run([sys.executable, str(JOB), *args], cwd=self.tmp, capture_output=True,
                              text=True, timeout=timeout)

    def run_tool(self, *extra, tool=None, name=NAME):
        tool = tool or self.tool
        return self.job("run", "--root", self.tmp, "--key", "src/*.py", "--name", name, *extra,
                        "--", sys.executable, str(tool))

    def count(self):
        f = self.root / "counter.txt"
        return len(f.read_text().splitlines()) if f.exists() else 0

    def verdicts(self):
        return sorted((self.root / (".a" + "idd") / "jobs").glob("%s-*/verdict.json" % NAME))

    def verdict(self):
        v = self.verdicts()
        self.assertTrue(v, "no verdict.json written")
        return json.loads(v[-1].read_text(encoding="utf-8"))

    @staticmethod
    def job_id(out):
        out = out.strip()
        m = re.search(r"%s-[0-9a-f]{8}" % NAME, out)
        return m.group(0) if m else out.split()[-1]


class TestAiddJob(JobBase):
    def test_cached_second_run(self):
        r1 = self.run_tool()
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
        self.assertNotIn("CACHED", r1.stdout)
        r2 = self.run_tool()
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertIn("CACHED", r2.stdout)
        self.assertEqual(self.count(), 1)

    def test_change_reruns(self):
        self.run_tool()
        self.src.write_text("print('changed')\n", encoding="utf-8")
        r = self.run_tool()
        self.assertNotIn("CACHED", r.stdout)
        self.assertEqual(self.count(), 2)

    def test_force_reruns(self):
        self.run_tool()
        r = self.run_tool("--force")
        self.assertNotIn("CACHED", r.stdout)
        self.assertEqual(self.count(), 2)

    def test_hash_is_by_content_not_mtime(self):
        self.run_tool()
        st = self.src.stat()
        new = b"X" * st.st_size
        # same size, different bytes, mtime restored: must NOT be cached
        self.src.write_bytes(new)
        os.utime(self.src, ns=(st.st_atime_ns, st.st_mtime_ns))
        self.assertEqual(self.src.stat().st_size, st.st_size)
        r = self.run_tool()
        self.assertNotIn("CACHED", r.stdout)
        self.assertEqual(self.count(), 2)
        # identical bytes rewritten (new mtime): cached
        self.src.write_bytes(new)
        r = self.run_tool()
        self.assertIn("CACHED", r.stdout)
        self.assertEqual(self.count(), 2)

    def test_bg_and_wait_exit_code(self):
        tool = make_tool(self.root, code=3, sleep=1, fname="slow.py")
        r = self.run_tool("--bg", tool=tool)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stdout.strip())
        jid = self.job_id(r.stdout)
        w = self.job("wait", jid, "--root", self.tmp)
        self.assertEqual(w.returncode, 3, w.stdout + w.stderr)

    def test_wait_timeout_returns_4(self):
        tool = make_tool(self.root, code=0, sleep=6, fname="slower.py")
        r = self.run_tool("--bg", tool=tool)
        jid = self.job_id(r.stdout)
        w = self.job("wait", jid, "--root", self.tmp, "--timeout", "1")
        self.assertEqual(w.returncode, 4, w.stdout + w.stderr)
        # let the background tool finish before the temp dir is removed
        self.job("wait", jid, "--root", self.tmp, "--timeout", "30")

    def test_last_unchanged_then_stale(self):
        tool = make_tool(self.root, code=1, fname="failing.py")
        self.run_tool(tool=tool)
        l1 = self.job("last", NAME, "--root", self.tmp)
        self.assertEqual(l1.returncode, 1, l1.stdout + l1.stderr)
        self.src.write_text("print('changed')\n", encoding="utf-8")
        l2 = self.job("last", NAME, "--root", self.tmp)
        self.assertEqual(l2.returncode, 3, l2.stdout + l2.stderr)
        self.assertIn("STALE", l2.stdout)

    def test_last_without_job_returns_3(self):
        r = self.job("last", "nope", "--root", self.tmp)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)

    def test_verdict_fields_from_result_line(self):
        self.run_tool()
        v = self.verdict()
        self.assertRegex(v["inputs_hash"], r"^[0-9a-f]{64}$")
        self.assertIn("wall_s", v)
        self.assertEqual(v["result"], "ok")
        self.assertEqual(v["items"], 3)
        self.assertEqual(v["source"], "RESULT")
        self.assertEqual(v["exit"], 0)
        self.assertTrue((self.verdicts()[-1].parent / "log.txt").exists())

    def test_verdict_derived_without_result_line(self):
        tool = make_tool(self.root, code=1, result=False, fname="plain.py")
        r = self.run_tool(tool=tool)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        v = self.verdict()
        self.assertEqual(v["source"], "derived")
        self.assertEqual(v["result"], "fail")
        self.assertEqual(v["exit"], 1)

    def test_corrupt_verdict_reexecutes(self):
        self.run_tool()
        self.verdicts()[-1].write_text("{not json", encoding="utf-8")
        r = self.run_tool()
        self.assertNotIn("CACHED", r.stdout)
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.verdict()["result"], "ok")

    def test_list_shows_job(self):
        self.run_tool()
        r = self.job("list", "--root", self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(NAME, r.stdout)


class TestJobHardening(JobBase):   # FR-048 / AC-040
    DOT = "." + "aidd"

    def canary(self):
        """A verdict OUTSIDE the jobs folder that a path-escaping id would reach (<root>/.aidd/x)."""
        d = self.root / self.DOT / "x"
        d.mkdir(parents=True)
        (d / "verdict.json").write_text(json.dumps({"result": "ok", "exit": 0, "name": "x"}), encoding="utf-8")
        (d / "log.txt").write_text("SECRET-CANARY\n", encoding="utf-8")
        return d

    def test_wait_refuses_a_path_escaping_id(self):
        self.canary()
        for bad in ("../x", "..", "a/b", "..\\x"):
            r = self.job("wait", bad, "--root", self.tmp)
            self.assertEqual(r.returncode, 2, (bad, r.stdout, r.stderr))
            self.assertIn("refused", r.stdout + r.stderr)
            self.assertNotIn("SECRET-CANARY", r.stdout + r.stderr)

    def test_last_refuses_a_name_with_a_separator(self):
        self.canary()
        for bad in ("a/b", "../x", "a\\b"):
            r = self.job("last", bad, "--root", self.tmp)
            self.assertEqual(r.returncode, 2, (bad, r.stdout, r.stderr))
            self.assertIn("refused", r.stdout + r.stderr)
            self.assertNotIn("SECRET-CANARY", r.stdout + r.stderr)

    def test_refusal_reads_and_writes_nothing(self):
        self.canary()
        before = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        self.job("wait", "../x", "--root", self.tmp)
        self.job("last", "a/b", "--root", self.tmp)
        after = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        self.assertEqual(before, after)
        self.assertFalse((self.root / self.DOT / "jobs").exists(), "a refusal must not create the jobs folder")

    def test_valid_ids_are_still_accepted(self):
        self.run_tool()
        jid = self.verdicts()[-1].parent.name
        self.assertRegex(jid, r"^[A-Za-z0-9_.-]+$")
        w = self.job("wait", jid, "--root", self.tmp)
        self.assertEqual(w.returncode, 0, w.stdout + w.stderr)
        l = self.job("last", NAME, "--root", self.tmp)
        self.assertEqual(l.returncode, 0, l.stdout + l.stderr)

    def test_stored_command_is_redacted(self):
        r = self.job("run", "--root", self.tmp, "--key", "src/*.py", "--name", NAME,
                     "--", sys.executable, "-c", "pass", "--token=abc123")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        vdir = self.verdicts()[-1].parent
        for fname in ("job.json", "verdict.json"):
            text = (vdir / fname).read_text(encoding="utf-8")
            self.assertNotIn("abc123", text, fname)
            self.assertIn("--token=[redacted]", text, fname)
            self.assertIn("--token=[redacted]", json.loads(text)["cmd"], fname)

    def test_gitignore_lists_the_jobs_folder(self):
        lines = [ln.strip() for ln in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()]
        self.assertIn("." + "aidd/jobs/", lines)


if __name__ == "__main__":
    unittest.main()
