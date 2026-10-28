"""Mechanical wave coverage and input-evidence reuse regressions."""
import hashlib
import contextlib
import io
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skill' / 'scripts'))
import aidd_status as status
from tests import test_aidd_status as fixtures


class WaveVerificationTests(unittest.TestCase):
    tasks = '## Waves\n| Wave | Tasks |\n|---|---|\n| 1 | T-01, T-02 |\n| 2 | T-03 |\n'

    def test_wave_requires_and_selects_every_task(self):
        rows = [{'covers': 'T-01'}, {'covers': 'T-02 T-03'}, {'covers': 'T-03'}]
        self.assertEqual(status._wave_rows(self.tasks, rows, '1'), rows[:2])
        with self.assertRaisesRegex(ValueError, 'T-02'):
            status._wave_rows(self.tasks, rows[:1], '1')
        with self.assertRaisesRegex(ValueError, 'missing or duplicated'):
            status._wave_rows(self.tasks, rows, '9')
        with self.assertRaisesRegex(ValueError, 'unknown wave tasks: T-99'):
            status._wave_rows(self.tasks, rows[:2] + [{'covers': 'T-99'}], '1')

    def test_row_reuse_survives_failed_batch_only_with_intact_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = b'# test | exit 0 | 2026-10-27\nverified: three assertions passed\n'
            (root / 'ok.txt').write_bytes(data)
            sha = hashlib.sha1(data).hexdigest()
            row = {'ok': True, 'exit': 0, 'cmd': 'test', 'expected': 'exit 0', 'input_globs': ['a.py'],
                   'input_fp': 'fingerprint', 'evidence': 'ok.txt', 'sha1': sha}
            prior = {'stable': False, 'results': [row]}
            key = ('test', 'exit 0', ('a.py',), 'fingerprint')
            self.assertIn(key, status._reusable_input_rows(root, prior, False))
            self.assertEqual(status._reusable_input_rows(root, prior, True), {})
            # Removing Inputs is a different contract: the prior per-row
            # evidence must not be treated as a legacy full-scope result.
            self.assertEqual(status._reusable_rows(root, {'stable': True, 'code_fp_end': 'same',
                                                           'results': [row]}, 'same', False), {})
            (root / 'ok.txt').write_text('tampered', encoding='utf-8')
            self.assertEqual(status._reusable_input_rows(root, prior, False), {})

    def test_old_false_passes_are_not_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for body, code, expected in ((b'# test | exit 0 | now\n== pgTAP: 0 files via psql\n== RESULT: OK\n', 0, 'exit 0'),
                                         (b'# test | exit 1 | now\nexpected assertions passed\n', 1, 'contains: expected')):
                (root / 'old.txt').write_bytes(body)
                row = {'ok': True, 'exit': code, 'cmd': 'test', 'expected': expected,
                       'input_globs': ['a.py'], 'input_fp': 'f', 'evidence': 'old.txt',
                       'sha1': hashlib.sha1(body).hexdigest()}
                self.assertFalse(status._cached_pass_valid(body, row, expected))
                self.assertEqual(status._reusable_input_rows(root, {'stable': False, 'results': [row]}, False), {})
                self.assertEqual(status._reusable_rows(root, {'stable': True, 'code_fp_end': 'f',
                                                               'results': [row]}, 'f', False), {})

    def test_wave_id_rejects_path_traversal(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = root / 'spec'
            spec.mkdir()
            (spec / 'spec.md').write_text('## Verification\n| # | Command | Expected | Covers |\n'
                                          '|---|---|---|---|\n| 1 | python check.py | exit 0 | T-01 |\n')
            with patch.object(status.ev, 'find_root', return_value=root), patch.object(status, '_resolve_spec', return_value=spec):
                self.assertEqual(status.cmd_verify(str(spec), wave='../outside'), 1)

    def test_explicit_inputs_do_not_trigger_round_global_scan(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = root / 'spec'
            spec.mkdir()
            (root / 'check.py').write_text('print("test")\n', encoding='utf-8')
            (spec / 'spec.md').write_text(
                '## Verification\n| # | Command | Expected | Covers | Inputs |\n'
                '|---|---|---|---|---|\n| V-1 | python check.py | exit 0 | T-01 | check.py |\n', encoding='utf-8')
            state = ('git', {'check.py': b'check.py\0sha\0'})

            def run(_cmd, _root, output, _timeout):
                output.write_text('three assertions passed successfully\n', encoding='utf-8')
                return 0, ''

            with patch.object(status.ev, 'find_root', return_value=root), \
                 patch.object(status, '_resolve_spec', return_value=spec), \
                 patch.object(status.ev, 'code_state', return_value=state) as scan, \
                 patch.object(status.ev, 'worktree_fingerprint', return_value='fp'), \
                 patch.object(status.ev, 'latest_verify_run', return_value=None), \
                 patch.object(status.ev, 'append_verify_run', return_value=True), \
                 patch.object(status, '_run_row', side_effect=run), \
                 patch.object(status, '_round_load') as round_load:
                self.assertEqual(status.cmd_verify(str(spec)), 0)
                round_load.assert_not_called()
                self.assertEqual(scan.call_count, 2)
                self.assertTrue(all('budget_s' not in call.kwargs for call in scan.call_args_list))

    def test_json_pass_detects_corruption_inputs_and_code_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = root / 'spec'
            spec.mkdir()
            source = root / 'check.py'
            source.write_text('v1', encoding='utf-8')
            evidence = spec / 'result.txt'
            data = b'# test | exit 0 | now\nthree assertions passed successfully\n'
            evidence.write_bytes(data)
            inputs = ['check.py']
            row = {'expected': 'exit 0', 'inputs': inputs}
            result = {'ok': True, 'exit': 0, 'expected': 'exit 0', 'evidence': 'result.txt',
                      'sha1': hashlib.sha1(data).hexdigest(), 'input_globs': inputs,
                      'input_fp': status.rules.row_input_fingerprint(root, inputs)}
            run = {'results': [result], 'code_scope': [], 'code_fp_end': 'code1'}
            with patch.object(status.rules, 'verification_scope', return_value=[]), \
                 patch.object(status.ev, 'code_state', return_value=('git', {'a': b'a'})), \
                 patch.object(status.ev, 'fingerprint_of', return_value='code1') as code_fp:
                self.assertIsNone(status._json_pass_evidence_problem(root, spec, '', [row], run))
                evidence.write_bytes(data + b'corrupted')
                self.assertIn('evidence', status._json_pass_evidence_problem(root, spec, '', [row], run))
                evidence.write_bytes(data)
                source.write_text('v2', encoding='utf-8')
                self.assertIn('input fingerprint', status._json_pass_evidence_problem(root, spec, '', [row], run))
                source.write_text('v1', encoding='utf-8')
                code_fp.return_value = 'code2'
                self.assertIn('code fingerprint', status._json_pass_evidence_problem(root, spec, '', [row], run))

    def test_json_uses_own_result_and_redacts_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = root / 'spec'
            spec.mkdir()
            text = ('## Verification\n| # | Command | Expected | Covers |\n|---|---|---|---|\n'
                    '| V-1 | python check.py | exit 0 | FR-001 |\n')
            (spec / 'spec.md').write_text(text, encoding='utf-8')

            def own_run(_spec, full=False, bail=False, wave=None, result_sink=None):
                print('token=topsecretvalue')
                result_sink.update(started=time.time(), ok=True, stable=True,
                                   verify_hash=status.rules.verification_hash(text),
                                   results=[{'n': 'V-1', 'ok': True, 'exit': 0, 'evidence': 'safe.txt'}])
                return 0

            stdout, stderr = io.StringIO(), io.StringIO()
            with patch.object(status.ev, 'find_root', return_value=root), \
                 patch.object(status, '_resolve_spec', return_value=spec), \
                 patch.object(status, 'cmd_verify', side_effect=own_run), \
                 patch.object(status, '_json_pass_evidence_problem', return_value=None), \
                 patch.object(status.ev, 'latest_verify_run', side_effect=AssertionError('concurrent event')), \
                 contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                self.assertEqual(status.cmd_verify_json(str(spec)), 0)
            self.assertEqual(json.loads(stdout.getvalue())['status'], 'pass')
            self.assertNotIn('topsecretvalue', stderr.getvalue())
            self.assertIn('[redacted]', stderr.getvalue())


class WaveEndToEnd(fixtures.Spec007Base):
    def test_json_wave_reports_manifest_and_refusal_without_stale_event(self):
        spec_text = ('# Spec\n## Verification\n'
                     '| # | Command | Expected | Covers | Inputs |\n|---|---|---|---|---|\n'
                     '| V-1 | `python src/check.py` | exit 0 | T-01 | src/check.py |\n'
                     '| V-2 | `python src/check.py` | exit 0 | T-02 | src/check.py |\n')
        tasks = '# Tasks\n## Waves\n| Wave | Tasks |\n|---|---|\n| 1 | T-01, T-02 |\n'
        tmp, root, spec = self.project('001-wave', spec=spec_text, tasks=tasks)
        with tmp:
            result = fixtures.run_script('verify', '001-wave', '--wave', '1', '--json', cwd=root)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report['status'], 'pass')
            self.assertEqual(report['planned'], ['V-1', 'V-2'])
            self.assertEqual(report['executed'], ['V-1'])
            self.assertEqual(report['deduplicated'], ['V-2'])
            self.assertEqual(report['coverage'], {'V-1': 'T-01', 'V-2': 'T-02'})
            self.assertIn('wave 1: PASSED', result.stderr)
            (root / 'src' / 'check.py').unlink()
            refused = fixtures.run_script('verify', '001-wave', '--wave', '1', '--json', cwd=root)
            self.assertNotEqual(refused.returncode, 0)
            self.assertEqual(json.loads(refused.stdout)['status'], 'error')
            self.assertIn('nothing was executed', refused.stderr)

    def test_quoted_whitespace_is_not_deduplicated(self):
        spec_text = ('# Spec\n## Verification\n'
                     '| # | Command | Expected | Covers | Inputs |\n|---|---|---|---|---|\n'
                     '| V-1 | `python src/check.py "a  b"` | exit 0 | T-01 | src/check.py |\n'
                     '| V-2 | `python src/check.py "a b"` | exit 0 | T-02 | src/check.py |\n')
        tasks = '# Tasks\n## Waves\n| Wave | Tasks |\n|---|---|\n| 1 | T-01, T-02 |\n'
        tmp, root, spec = self.project('001-wave', spec=spec_text, tasks=tasks)
        with tmp:
            (root / 'src' / 'check.py').write_text(
                'from pathlib import Path\np=Path("specs/001-wave/count.txt")\n'
                'p.write_text(str(int(p.read_text())+1) if p.exists() else "1")\n'
                'print("three assertions passed successfully")\n', encoding='utf-8')
            result = fixtures.run_script('verify', '001-wave', '--wave', '1', cwd=root)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertNotIn('DEDUPLICATED', result.stdout)
            self.assertEqual((spec / 'count.txt').read_text(), '2')

    def test_identical_wave_checks_run_once_and_cover_both_tasks(self):
        spec_text = ('# Spec\n## Verification\n'
                     '| # | Command | Expected | Covers | Inputs |\n|---|---|---|---|---|\n'
                     '| V-1 | `python src/check.py` | exit 0 | T-01 | src/check.py |\n'
                     '| V-2 | `python src/check.py` | exit 0 | T-02 | src/check.py |\n')
        tasks = '# Tasks\n## Waves\n| Wave | Tasks |\n|---|---|\n| 1 | T-01, T-02 |\n'
        tmp, root, spec = self.project('001-wave', spec=spec_text, tasks=tasks)
        with tmp:
            check = root / 'src' / 'check.py'
            check.write_text('from pathlib import Path\np=Path("specs/001-wave/count.txt")\n'
                             'p.write_text(str(int(p.read_text())+1) if p.exists() else "1")\n'
                             'print("three assertions passed successfully")\n', encoding='utf-8')
            result = fixtures.run_script('verify', '001-wave', '--wave', '1', cwd=root)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn('DEDUPLICATED row V-2', result.stdout)
            self.assertEqual((spec / 'count.txt').read_text(), '1')
            recorded = status._latest_wave_run(root, '001-wave', '1')
            self.assertEqual([r['covers'] for r in recorded['results']], ['T-01', 'T-02'])
            self.assertEqual(recorded['results'][1]['deduplicated_from'], 'V-1')
            self.assertTrue((spec / recorded['results'][0]['evidence']).is_file())
            self.assertTrue((spec / recorded['results'][1]['evidence']).is_file())

    def test_wave_evidence_reused_without_authorizing_spec_close(self):
        spec_text = ('# Spec\n## Verification\n'
                     '| # | Command | Expected | Covers | Inputs |\n'
                     '|---|---|---|---|---|\n'
                     '| V-1 | `python src/check.py` | exit 0 | T-01 | src/check.py |\n')
        tasks = ('# Tasks\n## Waves\n| Wave | Tasks |\n|---|---|\n| 1 | T-01 |\n')
        tmp, root, spec = self.project('001-wave', spec=spec_text, tasks=tasks)
        with tmp:
            first = fixtures.run_script('verify', '001-wave', '--wave', '1', cwd=root)
            self.assertEqual(first.returncode, 0, first.stdout)
            self.assertIn('wave 1: PASSED', first.stdout)
            self.assertIsNone(fixtures.ev.latest_verify_run(root, '001-wave'))
            self.assertIsNotNone(status._latest_wave_run(root, '001-wave', '1'))
            unrelated = root / 'src' / 'billing.py'
            unrelated.write_text('x = 2\n', encoding='utf-8')
            second = fixtures.run_script('verify', '001-wave', '--wave', '1', cwd=root)
            self.assertEqual(second.returncode, 0, second.stdout)
            self.assertIn('REUSED row V-1', second.stdout)
            check = root / 'src' / 'check.py'
            check.write_text(check.read_text(encoding='utf-8') + '\n# input changed\n', encoding='utf-8')
            third = fixtures.run_script('verify', '001-wave', '--wave', '1', cwd=root)
            self.assertEqual(third.returncode, 0, third.stdout)
            self.assertNotIn('REUSED row V-1', third.stdout)
