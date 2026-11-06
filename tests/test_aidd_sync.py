"""`aidd sync` (amendment 10 to spec 007, item N, FR-413..FR-418, AC-467..AC-474): whole-tree comparison of the AIDD
source with an installed bundle, and a backed-up, journaled, recoverable apply. Everything runs in temp folders;
nothing touches ~/.claude or a real project.

Run: python -m unittest tests.test_aidd_sync -v
"""
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location('aidd_sync', REPO_ROOT / 'skill' / 'scripts' / 'aidd_sync.py')
sync = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync)

SKILL = {'AIDD.md': b'# AIDD\nline\n', 'SKILL.md': b'skill\n', 'scripts/x.py': b'X = 1\n',
         'hooks/h.py': b'H = 1\n', 'templates/a.html': b'<p>a</p>\n', 'templates/sub/b.md': b'b\n'}
DOT = {'AIDD.md': b'# AIDD\nline\n', 'CORE.md': b'core\n', 'scripts/x.py': b'X = 1\n',
       'templates/t.md': b't\n', 'extensions/e/manifest.json': b'{}\n'}


def _write(root, files):
    for rel, data in files.items():
        path = Path(root) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


class SyncBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name).resolve()
        self.source = self.base / 'src'
        _write(self.source / 'skill', SKILL)
        _write(self.source / 'adapters' / 'dot-aidd', DOT)
        (self.source / 'tools').mkdir()
        shutil.copy2(REPO_ROOT / 'tools' / 'aidd_selective_update.py', self.source / 'tools')
        self.profile = self.base / 'profile' / 'aidd'
        _write(self.profile, SKILL)
        self.project = self.base / 'proj'
        self.dot = self.project / '.aidd'
        _write(self.dot, DOT)
        self.backups = self.base / 'backups'

    def targets(self):
        return sync.resolve_targets(self.source, ['skill', str(self.project)], self.profile)

    def check(self):
        out = io.StringIO()
        rc, reports = sync.run_check(self.targets(), stream=out)
        return rc, {r['target']: r for r in reports}, out.getvalue()

    def snapshot(self):
        return {p.relative_to(self.base).as_posix(): p.read_bytes()
                for root in (self.profile, self.dot) for p in root.rglob('*') if p.is_file()}


class TestCheck(SyncBase):
    def test_equal_trees_exit_zero(self):
        rc, reports, text = self.check()
        self.assertEqual(rc, 0, text)
        self.assertIn('missing=0 differs=0 local-only=0', text)

    def test_missing_file_reported(self):
        (self.dot / 'templates' / 't.md').unlink()
        rc, reports, _ = self.check()
        self.assertEqual(rc, 1)
        self.assertEqual(reports[str(self.dot)]['missing'], ['templates/t.md'])

    def test_differs_reported(self):
        (self.profile / 'scripts' / 'x.py').write_bytes(b'X = 2\n')
        rc, reports, _ = self.check()
        self.assertEqual(rc, 1)
        self.assertEqual(reports['skill']['differs'], ['scripts/x.py'])

    def test_crlf_only_difference_is_equal(self):
        (self.profile / 'AIDD.md').write_bytes(b'# AIDD\r\nline\r\n')
        (self.dot / 'CORE.md').write_bytes(b'core\r\n')
        rc, _, text = self.check()
        self.assertEqual(rc, 0, text)

    def test_local_state_ignored_and_local_only_listed(self):
        _write(self.dot, {'evidence/log.jsonl': b'e', 'memory/m.md': b'm', 'active_spec': b'a', 'gate_spec': b'g',
                          'calibration.toon': b'c', 'graphs/x.json': b'{}', 'sqlcheck-cache.json': b'{}',
                          'scripts/__pycache__/x.cpython-312.pyc': b'p', 'scripts/x.py.bak': b'b', 'NOTES.md': b'n'})
        rc, reports, text = self.check()
        self.assertEqual(rc, 0, text)
        self.assertEqual(reports[str(self.dot)]['local-only'], ['NOTES.md'])

    def test_project_root_or_dot_aidd_both_accepted(self):
        a = sync.resolve_targets(self.source, [str(self.project)])[0][2]
        b = sync.resolve_targets(self.source, [str(self.dot)])[0][2]
        self.assertEqual(a, b)

    def test_relative_paths_give_no_false_differences(self):
        # The measured bug: a comparator with relative paths after `cd` reported 116 false DIFIERE.
        r = subprocess.run([sys.executable, str(REPO_ROOT / 'skill' / 'scripts' / 'aidd_sync.py'), '--check',
                            '--source', 'src', '--target', 'proj/.aidd', '--target', 'skill',
                            '--profile', 'profile/aidd'], cwd=str(self.base), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('differs=0', r.stdout)
        old = os.getcwd()
        try:
            os.chdir(self.base)
            resolved = sync.resolve_targets(Path('src').resolve(), ['proj'], 'profile/aidd')
            os.chdir(self.dot / 'scripts')          # a later `cd` must not change what is compared
            self.assertEqual(sync.run_check(resolved, stream=io.StringIO())[0], 0)
        finally:
            os.chdir(old)

    def test_cli_sync_uses_source_script(self):
        env = dict(os.environ, PYTHONPATH=str(REPO_ROOT))
        r = subprocess.run([sys.executable, '-m', 'aidd.cli', 'sync', '--check', '--source', str(self.source),
                            '--target', str(self.project)], cwd=str(self.base), env=env,
                           capture_output=True, text=True)
        # the fake source has no skill/scripts/aidd_sync.py, so the CLI falls back to the repo's scripts
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        (self.dot / 'CORE.md').write_bytes(b'changed\n')
        r = subprocess.run([sys.executable, '-m', 'aidd.cli', 'sync', '--check', '--source', str(self.source),
                            '--target', str(self.project)], cwd=str(self.base), env=env,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('CORE.md', r.stdout)


class TestApply(SyncBase):
    def drift(self):
        (self.profile / 'scripts' / 'x.py').write_bytes(b'X = 0\n')            # selective (scripts/*.py)
        (self.profile / 'AIDD.md').write_bytes(b'old aidd\n')                   # selective (AIDD.md)
        (self.profile / 'templates' / 'a.html').write_bytes(b'<p>old</p>\n')    # direct copy (template)
        shutil.rmtree(self.profile / 'templates' / 'sub')                        # missing file in a missing folder
        (self.dot / 'CORE.md').write_bytes(b'old core\n')                       # direct copy (CORE.md)
        (self.dot / 'scripts' / 'x.py').unlink()                                # missing, selective
        _write(self.dot, {'evidence/log.jsonl': b'keep', 'NOTES.md': b'mine'})

    def apply(self, **kw):
        return sync.apply(self.source, self.targets(), backup_dir=self.backups, stream=io.StringIO(), **kw)

    def test_dry_run_writes_nothing(self):
        self.drift()
        before = self.snapshot()
        self.assertEqual(self.apply(), 0)
        self.assertEqual(self.apply(yes=True, dry_run=True), 0)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.backups.exists())

    def test_apply_then_recover(self):
        self.drift()
        before = self.snapshot()
        self.assertEqual(self.apply(yes=True), 0)
        self.assertEqual(self.check()[0], 0)
        self.assertEqual((self.profile / 'templates' / 'a.html').read_bytes(), SKILL['templates/a.html'])
        self.assertEqual((self.profile / 'templates' / 'sub' / 'b.md').read_bytes(), SKILL['templates/sub/b.md'])
        self.assertEqual((self.dot / 'CORE.md').read_bytes(), DOT['CORE.md'])
        self.assertEqual((self.dot / 'scripts' / 'x.py').read_bytes(), DOT['scripts/x.py'])
        self.assertEqual((self.dot / 'evidence' / 'log.jsonl').read_bytes(), b'keep')   # local state untouched
        self.assertEqual((self.dot / 'NOTES.md').read_bytes(), b'mine')
        sessions = list(self.backups.iterdir())
        self.assertEqual(len(sessions), 1)
        self.assertTrue((sessions[0] / 'sync-journal.json').is_file())
        self.assertTrue((sessions[0] / 'selective-journal' / 'transaction.json').is_file())
        self.assertEqual(sync.recover(sessions[0], stream=io.StringIO()), 0)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.profile / 'templates' / 'sub').exists())
        self.assertEqual(sync.recover(sessions[0], stream=io.StringIO()), 0)   # idempotent

    def test_template_only_change_is_copied_and_verified(self):
        (self.profile / 'templates' / 'a.html').write_bytes(b'<p>old</p>\n')
        self.assertEqual(self.apply(yes=True), 0)
        self.assertEqual((self.profile / 'templates' / 'a.html').read_bytes(), SKILL['templates/a.html'])

    def test_failure_rolls_back_everything(self):
        self.drift()
        before = self.snapshot()
        real, calls = sync._write_verified, []

        def flaky(dst, data, expected):
            calls.append(dst)
            if len(calls) == 2:
                raise ValueError('simulated disk error')
            return real(dst, data, expected)

        with patch.object(sync, '_write_verified', flaky), patch('sys.stderr', io.StringIO()):
            self.assertEqual(self.apply(yes=True), 1)
        self.assertEqual(self.snapshot(), before)

    def test_recover_refuses_foreign_edit(self):
        (self.dot / 'CORE.md').write_bytes(b'old core\n')
        self.assertEqual(self.apply(yes=True), 0)
        (self.dot / 'CORE.md').write_bytes(b'edited after sync\n')
        session = next(self.backups.iterdir())
        with self.assertRaises(ValueError):
            sync.recover(session, stream=io.StringIO())
        self.assertEqual((self.dot / 'CORE.md').read_bytes(), b'edited after sync\n')

    def test_backup_inside_target_refused(self):
        (self.dot / 'CORE.md').write_bytes(b'old core\n')
        with self.assertRaises(ValueError):
            sync.apply(self.source, self.targets(), yes=True, backup_dir=self.dot / 'bk', stream=io.StringIO())

    def test_cli_apply_needs_yes(self):
        (self.dot / 'CORE.md').write_bytes(b'old core\n')
        args = ['--apply', '--source', str(self.source), '--target', str(self.project),
                '--backup-dir', str(self.backups)]
        with patch('sys.stdout', io.StringIO()):
            self.assertEqual(sync.main(args), 0)
        self.assertEqual((self.dot / 'CORE.md').read_bytes(), b'old core\n')
        with patch('sys.stdout', io.StringIO()), patch('sys.stderr', io.StringIO()):
            self.assertEqual(sync.main(args + ['--yes']), 0)
        self.assertEqual((self.dot / 'CORE.md').read_bytes(), DOT['CORE.md'])


if __name__ == '__main__':
    unittest.main()
