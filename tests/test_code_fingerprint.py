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


class TestScope(unittest.TestCase):
    def test_verification_scope_parsing(self):
        spec = "# S\n\n## Verification\n\nScope: `docs/db-graph/**`, src/a.py ; tools/*.py\n\n| # | Command | Expected |\n|---|---|---|\n| 1 | `pytest` | exit 0 |\n\n## Next\nScope: ignored/**\n"
        self.assertEqual(rules.verification_scope(spec), ["docs/db-graph/**", "src/a.py", "tools/*.py"])
        self.assertEqual(rules.verification_scope("# S\n\n## Verification\n\n| # | Command |\n"), [])
        self.assertEqual(rules.verification_scope("no heading\nScope: x/**\n"), [])
        self.assertEqual(rules.verification_scope(None), [])

    def test_scope_auto_takes_the_task_target_files(self):
        tasks = ("# T\n\n| Task | Codes | Target file | View / logic |\n|---|---|---|---|\n"
                 "| T-01 | FR-1 | `docs/db-graph/a.py` + `docs/db-graph/test_a.py` | LOGIC |\n"
                 "| T-02 | FR-2 | `tools/b.sql` | LOGIC |\n| T-03 | FR-3 | `specs/F1/qa-audit.md` | LOGIC |\n\n"
                 "| Other | Table |\n|---|---|\n| x | `not/a/target.py` |\n")
        self.assertEqual(rules.task_targets(tasks), ["docs/db-graph/a.py", "docs/db-graph/test_a.py", "tools/b.sql"])
        spec = "## Verification\n\nScope: auto, eDoc/supabase/migrations/**\n\n| # | Command |\n|---|---|\n"
        self.assertEqual(rules.verification_scope(spec, tasks),
                         ["docs/db-graph/a.py", "docs/db-graph/test_a.py", "eDoc/supabase/migrations/**", "tools/b.sql"])
        self.assertEqual(rules.verification_scope("## Verification\n\nScope: auto\n", "no table here"), [])   # nothing: whole tree
        self.assertEqual(rules.verification_scope("## Verification\n\nScope: src/**\n", tasks), ["src/**"])

    def test_the_shipped_template_declares_scope_auto_and_it_parses(self):
        tpl = (Path(__file__).resolve().parent.parent / "skill" / "templates" / "spec.md").read_text(encoding="utf-8")
        tasks = "| Task | Target file |\n|---|---|\n| T-01 | `a/b.py` |\n"
        self.assertEqual(rules.verification_scope(tpl, tasks), ["a/b.py"])       # comment ignored, auto expanded
        self.assertEqual(rules.verification_generated(tpl), [])                  # the Generated placeholder is no value

    def test_placeholder_and_empty_scopes_are_never_trusted(self):
        self.assertEqual(rules.verification_scope("## Verification\n\nScope: <globs of the files this spec owns>\n"), [])
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.py").write_text("x = 1\n", encoding="utf-8")
            self.assertIsNone(ev.code_fingerprint(root, scope=["nothing/**"]))        # matches no file: fail closed
            self.assertIsNotNone(ev.code_fingerprint(root, scope=["*.py"]))

    def test_scoped_fingerprint_ignores_other_specs_but_not_its_own_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "mine").mkdir()
            (root / "other").mkdir()
            (root / "mine" / "a.py").write_text("x = 1\n", encoding="utf-8")
            (root / "other" / "b.py").write_text("y = 1\n", encoding="utf-8")
            for use_git in (False, True):
                if use_git:
                    _git(root, "init", "-q")
                scope = ["mine/**"]
                a, whole = ev.code_fingerprint(root, scope=scope), ev.code_fingerprint(root)
                (root / "other" / "b.py").write_text("y = 2\n", encoding="utf-8")
                self.assertEqual(ev.code_fingerprint(root, scope=scope), a)          # another spec: untouched
                self.assertNotEqual(ev.code_fingerprint(root), whole)                # the whole tree did change
                (root / "mine" / "a.py").write_text("x = 2\n", encoding="utf-8")
                self.assertNotEqual(ev.code_fingerprint(root, scope=scope), a)       # its own file: stale
                self.assertNotEqual(ev.code_fingerprint(root, scope=["mine/**", "other/**"]), a)   # scope is part of the hash
                (root / "mine" / "a.py").write_text("x = 1\n", encoding="utf-8")
                (root / "other" / "b.py").write_text("y = 1\n", encoding="utf-8")

    def test_last_code_edit_ts_with_scope(self):
        import os as _os
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as ed:
            root = Path(td)
            (root / "specs").mkdir()
            old = {k: _os.environ.get(k) for k in ("AIDD_EVIDENCE_DIR", "AIDD_TESTING")}
            _os.environ["AIDD_EVIDENCE_DIR"], _os.environ["AIDD_TESTING"] = ed, "1"
            try:
                ev.append(root, "s", "code_edit", path=str(root / "mine" / "a.py"))
                import time as _t
                _t.sleep(0.01)
                ev.append(root, "s", "code_edit", path=str(root / "other" / "b.py"))
                whole, mine, none = (ev.last_code_edit_ts(root), ev.last_code_edit_ts(root, ["mine/**"]),
                                     ev.last_code_edit_ts(root, ["nothing/**"]))
                self.assertGreater(whole, mine)
                self.assertGreater(mine, 0)
                self.assertEqual(none, 0.0)
            finally:
                for k, v in old.items():
                    if v is None:
                        _os.environ.pop(k, None)
                    else:
                        _os.environ[k] = v


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
