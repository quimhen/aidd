"""Spec 012 (T-05): `aidd next` (FR-1201 / AC-1203). Tests against the CONTRACT of plan.md:

    aidd_next.build_next(spec_dir, root, status=None) -> dict
    aidd_next.format_next(info) -> str            (at most 30 lines, exactly one next-command line)
    aidd_next.main(argv)                          `next [spec_dir] [--write] [--json]`, output file .aidd/NEXT.md

The "next-command line" is the line that starts with `Next` (case-insensitive, after any bullet/bold marks).
Scratch projects and the evidence-dir isolation come from tests/gate_fixtures.py (Base)."""
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_fixtures import Base, REPO, approved_tasks, tasks_text, verified_spec, spec_text  # noqa: E402

sys.path.insert(0, str(REPO / "skill" / "scripts"))
import aidd_next as N  # noqa: E402

STATUS = REPO / "skill" / "scripts" / "aidd_status.py"
NEXT_LINE = re.compile(r"^\W*next\b", re.IGNORECASE)
MAX_LINES = 30


def next_lines(text):
    return [ln for ln in text.splitlines() if NEXT_LINE.match(ln)]


class NextBase(Base):
    def setUp(self):
        super().setUp()
        self.put(".aidd/AIDD.md", "# AIDD\n")
        self._cwd = os.getcwd()
        os.chdir(self.root)

    def tearDown(self):
        os.chdir(self._cwd)
        super().tearDown()

    def rel(self):
        return f"specs/{self.SPEC}"

    def text(self):
        return N.format_next(N.build_next(self.sd, self.root))

    def run_main(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                rc = N.main(list(args))
            except SystemExit as ex:
                rc = ex.code or 0
        return rc, buf.getvalue()

    def verify(self):
        subprocess.run([sys.executable, str(STATUS), "verify", str(self.sd)], cwd=str(self.root),
                       env=dict(self.env), capture_output=True, timeout=90)

    def approve_all(self):
        self.put(f"{self.rel()}/spec.md", verified_spec())
        self.put(f"{self.rel()}/plan.md", "# Plan\n")
        self.put(f"{self.rel()}/tasks.md", approved_tasks())
        self.open_spec()
        self.approve_spec()

    def assertShape(self, text):
        lines = text.rstrip("\n").splitlines()
        self.assertLessEqual(len(lines), MAX_LINES, text)
        self.assertEqual(len(next_lines(text)), 1, text)


class TestEveryStage(NextBase):
    def test_no_spec_md_yet(self):
        self.assertShape(self.text())

    def test_spec_without_plan(self):
        self.put(f"{self.rel()}/spec.md", spec_text())
        self.assertShape(self.text())

    def test_plan_without_tasks(self):
        self.put(f"{self.rel()}/spec.md", spec_text())
        self.put(f"{self.rel()}/plan.md", "# Plan\n")
        self.assertShape(self.text())

    def test_tasks_not_approved(self):
        self.put(f"{self.rel()}/spec.md", verified_spec())
        self.put(f"{self.rel()}/plan.md", "# Plan\n")
        self.put(f"{self.rel()}/tasks.md", tasks_text())
        self.open_spec()
        self.assertShape(self.text())

    def test_approved_with_no_verify(self):
        self.approve_all()
        self.assertShape(self.text())

    def test_verify_failed(self):
        self.approve_all()
        (self.root / "src" / "cart.py").write_text("raise SystemExit(1)\n", encoding="utf-8")
        self.verify()
        self.assertShape(self.text())

    def test_qa_audit_missing(self):
        self.approve_all()
        self.verify()
        self.assertFalse((self.sd / "qa-audit.md").exists())
        self.assertShape(self.text())

    def test_next_command_differs_between_early_and_late_stages(self):
        early = next_lines(self.text())
        self.approve_all()
        late = next_lines(self.text())
        self.assertNotEqual(early, late)


class TestNoOpenSpec(NextBase):
    def test_no_open_spec_names_aidd_search(self):
        self.sd.rmdir()
        rc, out = self.run_main()
        self.assertEqual(rc or 0, 0)
        self.assertIn("aidd search", out)
        self.assertLessEqual(len(out.splitlines()), MAX_LINES)


class TestWriteAndJson(NextBase):
    def setUp(self):
        super().setUp()
        self.put(f"{self.rel()}/spec.md", spec_text())
        self.out = self.root / ".aidd" / "NEXT.md"

    def test_write_creates_then_refreshes_with_the_stdout_text(self):
        self.assertFalse(self.out.exists())
        rc, first = self.run_main(self.rel(), "--write")
        self.assertEqual(rc or 0, 0)
        self.assertTrue(self.out.exists())
        self.assertEqual(self.out.read_text(encoding="utf-8").strip(), first.strip())
        self.put(f"{self.rel()}/plan.md", "# Plan\n")
        rc, second = self.run_main(self.rel(), "--write")
        self.assertEqual(self.out.read_text(encoding="utf-8").strip(), second.strip())
        self.assertNotEqual(first.strip(), second.strip())

    def test_without_write_no_file_is_created(self):
        self.run_main(self.rel())
        self.assertFalse(self.out.exists())

    def test_json_is_valid(self):
        rc, out = self.run_main(self.rel(), "--json")
        self.assertEqual(rc or 0, 0)
        self.assertIsInstance(json.loads(out), dict)


class TestSpeed(NextBase):
    def test_runs_under_two_seconds(self):
        self.approve_all()
        t0 = time.time()
        self.run_main(self.rel())
        self.assertLess(time.time() - t0, 2.0)


if __name__ == "__main__":
    unittest.main()
