"""Amendment to spec 007: code_fingerprint is documentation- and commit-proof; `aidd verify` is incremental."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import aidd_evidence as ev  # noqa: E402
import aidd_rules as rules  # noqa: E402


def _git(root, *args):
    return subprocess.run(["git", *args], cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


class TestCodeFingerprint(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
        (self.root / "NOTES.md").write_text("v1\n", encoding="utf-8")
        (self.root / "specs").mkdir()
        (self.root / "specs" / "spec.md").write_text("s\n", encoding="utf-8")

    def tearDown(self):
        self._td.cleanup()

    def _repo(self):
        _git(self.root, "init", "-q")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")
        _git(self.root, "add", "-A")

    def test_prefix_and_none_for_missing_root(self):
        self.assertTrue(str(ev.code_fingerprint(self.root)).startswith("c2:"))
        self.assertIsNone(ev.code_fingerprint(self.root / "nope"))

    def test_doc_and_spec_edits_do_not_change_it_but_code_does(self):
        for use_git in (False, True):
            with self.subTest(git=use_git):
                if use_git:
                    self._repo()
                a = ev.code_fingerprint(self.root)
                (self.root / "NOTES.md").write_text("v2 edited\n", encoding="utf-8")
                (self.root / "specs" / "spec.md").write_text("changed\n", encoding="utf-8")
                (self.root / "extra.md").write_text("new doc\n", encoding="utf-8")
                self.assertEqual(ev.code_fingerprint(self.root), a)
                (self.root / "src" / "a.py").write_text("x = 2\n", encoding="utf-8")
                b = ev.code_fingerprint(self.root)
                self.assertNotEqual(b, a)
                (self.root / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")

    def test_commit_does_not_change_it(self):
        self._repo()
        before = ev.code_fingerprint(self.root)
        (self.root / "NOTES.md").write_text("v2\n", encoding="utf-8")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "docs")
        self.assertEqual(ev.code_fingerprint(self.root), before)
        (self.root / "src" / "a.py").write_text("x = 3\n", encoding="utf-8")
        dirty = ev.code_fingerprint(self.root)
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "code")
        self.assertEqual(ev.code_fingerprint(self.root), dirty)      # the commit of the same content: equal

    def test_untracked_code_file_counts_deleted_file_counts(self):
        self._repo()
        a = ev.code_fingerprint(self.root)
        (self.root / "src" / "new.py").write_text("y = 1\n", encoding="utf-8")
        b = ev.code_fingerprint(self.root)
        self.assertNotEqual(a, b)
        (self.root / "src" / "a.py").unlink()
        self.assertNotEqual(ev.code_fingerprint(self.root), b)


class TestRowsAlreadyExecuted(unittest.TestCase):
    SPEC = ("# S\n\n## Verification\n\n| # | Command | Expected | Covers |\n|---|---|---|---|\n"
            "| V-1 | `python src/a.py` | exit 0 | AC-1 |\n| V-2 | `python src/b.py` | exit 0 | AC-2 |\n")

    def run_of(self, **kw):
        res = [{"n": "V-1", "cmd": "python src/a.py", "expected": "exit 0", "ok": True},
               {"n": "V-2", "cmd": "python src/b.py", "expected": "exit 0", "ok": True}]
        return dict({"code_fp_end": "c2:x", "results": res}, **kw)

    def test_wording_and_covers_edits_are_covered_by_the_run(self):
        spec = self.SPEC.replace("AC-2", "AC-2, AC-3 (corrected note)")
        self.assertTrue(rules._rows_already_executed(spec, self.run_of()))

    def test_changed_command_or_new_row_is_not(self):
        self.assertFalse(rules._rows_already_executed(self.SPEC.replace("src/b.py", "src/c.py"), self.run_of()))
        self.assertFalse(rules._rows_already_executed(
            self.SPEC + "| V-3 | `python src/c.py` | exit 0 | AC-4 |\n", self.run_of()))

    def test_legacy_run_without_code_fingerprint_or_expected_is_not(self):
        self.assertFalse(rules._rows_already_executed(self.SPEC, self.run_of(code_fp_end=None)))
        run = self.run_of()
        del run["results"][0]["expected"]
        self.assertFalse(rules._rows_already_executed(self.SPEC, run))


if __name__ == "__main__":
    unittest.main()
