"""4b real tempfile identity and Git-filter security regressions."""
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skill' / 'scripts'))
import aidd_round as rnd
import aidd_status as status
from test_verify_amendment import AmendBase
from test_verify_round import PY


class DryRunIdentitySecurity(AmendBase):
    def marker_spec(self):
        (self.root / 'probe.py').write_text("from pathlib import Path\nPath('identity-marker').write_text('probed')\nprint('identity')\n", encoding='utf-8')
        self.aspec([('V-1', f'{PY} ok.py', 'exit 0', 'src/a.py', '')],
                   extra=f'Round-identity: {PY} probe.py\n')

    def test_01_all_dry_run_routes_skip_real_identity_marker(self):
        self.marker_spec()
        for args in (('A', '--dry-run'), ('A', '--amendment', '01', '--dry-run'),
                     ('--round', 'A', '--dry-run')):
            with self.subTest(args=args):
                marker = self.root / 'identity-marker'
                marker.unlink(missing_ok=True)
                with patch.object(rnd, '_identity_output', wraps=rnd._identity_output) as identity, \
                     patch.object(rnd, '_docker_identity', side_effect=AssertionError('dry run docker probe')) as docker:
                    rc, out = self.verify(*args)
                self.assertEqual((rc, self.runs, self.events), (0, [], []), out)
                self.assertFalse(marker.exists(), 'dry run executed the real identity command')
                self.assertEqual((identity.call_count, docker.call_count), (0, 0), out)
        self.assertFalse((self.root / 'specs/A/evidence').exists())

    def test_02_actual_identity_path_preserved_and_failure_unavailable(self):
        self.marker_spec()
        info = {'identity': [f'{PY} probe.py'], 'vars': []}
        with patch.object(rnd, '_identity_output', wraps=rnd._identity_output) as identity:
            parts = rnd.env_parts(status, self.root, info, [f'{PY} ok.py'])
        self.assertTrue((self.root / 'identity-marker').exists())
        self.assertEqual(identity.call_count, 1)
        self.assertTrue(rnd.row_env_id(parts, f'{PY} ok.py'))
        with patch.object(rnd, '_identity_output', return_value=None):
            failed = rnd.env_parts(status, self.root, info, [f'{PY} ok.py'])
        self.assertIsNone(rnd.row_env_id(failed, f'{PY} ok.py'))


class RawGitIdentitySecurity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.git('init', '-q')
        # Never change original/global Git configuration; marker belongs to this tempfile.
        script = self.root / 'filter.py'
        script.write_text("import sys\nfrom pathlib import Path\nsys.stdin.buffer.read()\nPath(__file__).with_name('filter-marker').write_text('executed')\nsys.stdout.buffer.write(b'CONSTANT\\n')\n", encoding='utf-8')
        command = f'"{sys.executable.replace(chr(92), chr(47))}" "{script.as_posix()}"'
        self.git('config', '--local', 'filter.security.clean', command)
        self.git('config', '--local', 'core.autocrlf', 'false')
        (self.root / '.gitattributes').write_text('target.txt filter=security\n', encoding='utf-8')
        self.target = self.root / 'target.txt'
        self.marker = self.root / 'filter-marker'
        self.target.write_bytes(b'first\r\n')

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.root, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_11_blob_and_code_state_do_not_invoke_clean_filter(self):
        want = hashlib.sha1(b'blob 7\0first\r\n').hexdigest()
        blobs = status.ev.blob_shas(self.root, ['target.txt'])
        state = status.ev.code_state(self.root, scope=['target.txt'])
        self.assertTrue(state)
        self.assertFalse(self.marker.exists(), 'kernel hashing invoked project clean-filter code')
        self.assertEqual(blobs, {'target.txt': want})
        self.assertTrue(status.ev.fingerprint_of(state, ['target.txt']))

    def test_12_raw_bytes_and_crlf_changes_change_public_identity(self):
        first = status.ev.code_fingerprint(self.root, scope=['target.txt'])
        self.target.write_bytes(b'second\r\n')
        second = status.ev.code_fingerprint(self.root, scope=['target.txt'])
        self.target.write_bytes(b'second\n')
        lf = status.ev.code_fingerprint(self.root, scope=['target.txt'])
        self.assertTrue(first and second and lf)
        self.assertNotEqual(first, second, 'constant clean-filter output must not hide raw byte changes')
        self.assertNotEqual(second, lf, 'raw identity distinguishes CRLF from LF')
        self.assertFalse(self.marker.exists())
        self.assertEqual(status.ev.EVIDENCE_ALGORITHM, 'raw-sql-v3-nofilters-glob-v2')


class FullDryRunTrackedFilterSecurity(unittest.TestCase):
    """Exercise real CLI dry runs, a committed dirty file and a real clean filter."""
    def setUp(self):
        import os
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'repo'
        self.root.mkdir()
        self.marker = self.base / 'clean-filter-marker'
        self.git('init', '-q')
        self.git('config', '--local', 'user.name', 'AIDD Fixture')
        self.git('config', '--local', 'user.email', 'fixture@example.invalid')
        self.git('config', '--local', 'core.autocrlf', 'false')
        script = self.root / 'filter.py'
        script.write_text("import sys\nfrom pathlib import Path\ndata=sys.stdin.buffer.read()\n"
                          + f"Path({str(self.marker)!r}).write_text('executed')\n"
                          + "sys.stdout.buffer.write(data)\n", encoding='utf-8')
        command = f'"{sys.executable.replace(chr(92), chr(47))}" "{script.as_posix()}"'
        self.git('config', '--local', 'filter.security.clean', command)
        (self.root / '.gitattributes').write_text('target.txt filter=security\n', encoding='utf-8')
        self.target = self.root / 'target.txt'
        self.target.write_bytes(b'original tracked bytes\n')
        self.git('add', '--', '.gitattributes', 'filter.py', 'target.txt')
        self.git('commit', '-q', '-m', 'Temporary security fixture')
        self.marker.unlink(missing_ok=True)
        self.target.write_bytes(b'changed for explicit real git-diff control\n')
        self.git('diff', 'HEAD', '--', 'target.txt')
        self.assertTrue(self.marker.exists(), 'positive control must execute the real configured clean filter')
        self.marker.unlink()
        self.target.write_bytes(b'dirty again before the actual CLI dry run\n')
        self.spec = self.root / 'specs' / 'A'
        self.spec.mkdir(parents=True)
        (self.spec / 'spec.md').write_text(
            '# A\n\n## Verification\n\nScope: target.txt\n\n'
            '| # | Command | Expected | Covers | Inputs | Tier | Environment |\n'
            '|---|---|---|---|---|---|---|\n'
            '| V-1 | `python check.py` | exit 0 | T-01 | target.txt | functional | contract:offline;vars=;packages= |\n',
            encoding='utf-8')
        (self.spec / 'tasks.md').write_text('# Tasks\n', encoding='utf-8')
        (self.spec / 'tasks-amendment-01.md').write_text('```aidd-files\ntarget.txt\n```\n', encoding='utf-8')
        (self.root / 'check.py').write_text(
            "from pathlib import Path\nPath('verification-marker').write_text('unexpected execution')\n"
            "print('verification command really executed')\n", encoding='utf-8')
        self.env = dict(os.environ, AIDD_TESTING='1', AIDD_EVIDENCE_DIR=str(self.base / 'evidence'))

    def git(self, *args):
        return subprocess.run(['git', '-c', 'core.fsmonitor=false', *args], cwd=self.root,
                              check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def actual_dry_run(self, args):
        executable = Path(__file__).resolve().parents[1] / 'skill/scripts/aidd_status.py'
        run = subprocess.run([sys.executable, str(executable), 'verify', *args], cwd=self.root,
                             env=self.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding='utf-8', errors='replace', timeout=30)
        self.assertEqual(run.returncode, 0, run.stdout)
        self.assertIn('dry run', run.stdout.lower())
        self.assertFalse(self.marker.exists(), 'the actual dry-run route executed repository clean-filter code')
        self.assertFalse((self.root / 'verification-marker').exists(), 'dry run executed a verification command')

    def test_13_actual_amendment_dry_run_does_not_execute_tracked_clean_filter(self):
        self.actual_dry_run([str(self.spec), '--amendment', '01', '--dry-run'])

    def test_14_actual_round_dry_run_does_not_execute_tracked_clean_filter(self):
        self.actual_dry_run(['--round', str(self.spec), '--dry-run'])


if __name__ == '__main__':
    unittest.main()
