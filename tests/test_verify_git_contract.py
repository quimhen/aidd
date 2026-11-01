import hashlib
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skill' / 'scripts'))
import aidd_status as status
import aidd_unit_audit as impact


class GitSelection(unittest.TestCase):
    def test_direct_inputs_select_only_related_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = root / 'specs' / '001-example'
            spec.mkdir(parents=True)
            (spec / 'tasks.md').write_text('| Task | Target file |\n|---|---|\n| T-01 | `a.py` |\n| T-02 | `b.py` |\n')
            (spec / 'spec.md').write_text('## Verification\n| # | Command | Expected | Covers | Inputs |\n|---|---|---|---|---|\n| V-1 | python a.py | exit 0 | T-01 | a.py |\n| V-2 | python b.py | exit 0 | T-02 | b.py |\n')
            with patch.object(impact, 'git_changed_paths', return_value=['a.py', 'other.py']):
                self.assertEqual(status._changed_task_selection(root, '001-example'), ['T-01'])
            with patch.object(impact, 'git_changed_paths', return_value=['other.py']):
                with self.assertRaisesRegex(ValueError, 'no declared task Inputs'):
                    status._changed_task_selection(root, '001-example')
            with patch.object(impact, 'git_changed_paths', return_value=['specs/001-example/spec.md']):
                with self.assertRaisesRegex(ValueError, 'policy changed'):
                    status._changed_task_selection(root, '001-example')


class ContractReuse(unittest.TestCase):
    def test_round_shares_only_identical_inputs_and_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            specs = []
            for name in ('one', 'two'):
                spec = root / 'specs' / name
                spec.mkdir(parents=True)
                (spec / 'tasks.md').write_text('| Task | Target file |\n|---|---|\n| T-01 | `test.py` |\n')
                (spec / 'spec.md').write_text('## Verification\n| # | Command | Expected | Inputs | Reuse | Environment |\n|---|---|---|---|---|---|\n| V1 | python test.py | exit 0 | test.py | hermetic | contract:offline;vars=none;packages=none |\n')
                specs.append(spec)
            (root / 'test.py').write_text('print(1)')
            state, env, inputs, calls = ('git', {'test.py': b'x'}), ['env1'], ['input1'], []
            def run(cmd, _root, output, _timeout):
                calls.append(cmd)
                output.write_text('three assertions passed successfully\n')
                return 0, ''
            with patch.object(status.ev, 'find_root', return_value=root), \
                 patch.object(status, '_resolve_spec', side_effect=lambda name, _root: root / 'specs' / name), \
                 patch.object(status, '_current_session', return_value='session'), \
                 patch.object(status.ev, 'latest_verify_run', return_value=None), \
                 patch.object(status.ev, 'code_state', return_value=state), \
                 patch.object(status.ev, 'state_diff', return_value=[]), \
                 patch.object(status.ev, 'fingerprint_of', return_value='fingerprint'), \
                 patch.object(status.ev, 'worktree_fingerprint', return_value='fp'), \
                 patch.object(status.rules, 'row_input_fingerprint', side_effect=lambda *_: inputs[0]), \
                 patch.object(status.ev, 'append_verify_run', return_value=True), \
                 patch.object(status, '_contract_environment_id', side_effect=lambda *_: env[0]), \
                 patch.object(status, '_run_row', side_effect=run), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(status.cmd_verify_many(['one', 'two']), 0)
                self.assertEqual(len(calls), 1)
                cache = {}
                self.assertEqual(status.cmd_verify('one', wave_cache=cache), 0)
                env[0] = 'env2'
                self.assertEqual(status.cmd_verify('two', wave_cache=cache), 0)
                self.assertEqual(len(calls), 3)
                inputs[0] = 'input2'
                self.assertEqual(status.cmd_verify('two', wave_cache=cache), 0)
                self.assertEqual(len(calls), 4)
                self.assertEqual(status.cmd_verify_many(['one', 'two'], full=True), 0)
                self.assertEqual(len(calls), 6)

    def test_contract_reuses_only_matching_environment_and_full_reruns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = root / 'specs' / 's'
            spec.mkdir(parents=True)
            (root / 'test.py').write_text('print(1)')
            (spec / 'tasks.md').write_text('| Task | Target file |\n|---|---|\n| T-01 | `test.py` |\n')
            (spec / 'spec.md').write_text('## Verification\n| # | Command | Expected | Inputs | Reuse | Environment |\n|---|---|---|---|---|---|\n| V1 | python test.py | exit 0 | test.py | hermetic | contract:offline;vars=none;packages=none |\n')
            prior, calls, env = [None], [], ['env1']
            def run(cmd, _root, output, _timeout):
                calls.append(cmd)
                output.write_text('three assertions passed successfully\n')
                return 0, ''
            def record(_root, _session, _spec, ok, _hash, results, _started, _start, _end, stable, **kw):
                prior[0] = {'ok': ok, 'stable': stable, 'results': results, 'code_fp_end': kw.get('code_fp_end')}
                return True
            state = ('git', {'test.py': b'x'})
            with patch.object(status.ev, 'find_root', return_value=root), \
                 patch.object(status, '_resolve_spec', return_value=spec), \
                 patch.object(status, '_current_session', return_value='session'), \
                 patch.object(status.ev, 'latest_verify_run', side_effect=lambda *_: prior[0]), \
                 patch.object(status.ev, 'code_state', return_value=state), \
                 patch.object(status.ev, 'state_diff', return_value=[]), \
                 patch.object(status.ev, 'fingerprint_of', return_value='fingerprint'), \
                 patch.object(status.ev, 'worktree_fingerprint', return_value='fp'), \
                 patch.object(status.rules, 'row_input_fingerprint', return_value='inputs'), \
                 patch.object(status.ev, 'append_verify_run', side_effect=record), \
                 patch.object(status, '_contract_environment_id', side_effect=lambda *_: env[0]), \
                 patch.object(status, '_run_row', side_effect=run), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(status.cmd_verify(str(spec)), 0)
                self.assertEqual(status.cmd_verify(str(spec)), 0)
                self.assertEqual(len(calls), 1)
                with patch.object(status, '_contract_environment_id', side_effect=['env1', 'env2', 'env2']):
                    self.assertEqual(status.cmd_verify(str(spec)), 0)
                self.assertEqual(len(calls), 2)
                self.assertNotIn('environment_id', prior[0]['results'][0])
                env[0] = 'env2'
                self.assertEqual(status.cmd_verify(str(spec)), 0)
                self.assertEqual(len(calls), 3)
                self.assertEqual(status.cmd_verify(str(spec), full=True), 0)
                self.assertEqual(len(calls), 4)

    def test_requires_explicit_offline_contract_and_safe_command(self):
        self.assertIsNone(status._contract_environment_id('python test.py', ''))
        self.assertIsNone(status._contract_environment_id('python test.py', 'contract:offline'))
        self.assertIsNone(status._contract_environment_id('python test.py && curl example.org', 'contract:offline;vars=none;packages=none'))
        self.assertIsNone(status._contract_environment_id('psql test.sql', 'contract:offline;vars=none;packages=none'))

    def test_only_declared_environment_and_packages_affect_identity(self):
        import os
        class Distribution:
            version = '1'
            files = ['example.py']
            def read_text(self, name):
                return 'metadata' if name == 'METADATA' else None
            def locate_file(self, name):
                return Path(tmp) / name
        calls = []
        def get_dist(name):
            calls.append(name)
            if name != 'example':
                from importlib.metadata import PackageNotFoundError
                raise PackageNotFoundError(name)
            return dist
        declaration = 'contract:offline;vars=AIDD_TEST_DEP;packages=example'
        with tempfile.TemporaryDirectory() as tmp, \
             patch.dict(os.environ, {'AIDD_TEST_DEP': 'first', 'AIDD_TEST_OTHER': 'first'}), \
             patch('importlib.metadata.distribution', side_effect=get_dist):
            dist = Distribution()
            package_file = Path(tmp) / 'example.py'
            package_file.write_text('original code')
            first = status._contract_environment_id('python test.py', declaration)
            self.assertIsNotNone(first)
            os.environ['AIDD_TEST_OTHER'] = 'changed'
            self.assertEqual(first, status._contract_environment_id('python test.py', declaration))
            self.assertEqual(set(calls), {'example'})
            package_file.write_text('changed code')
            self.assertNotEqual(first, status._contract_environment_id('python test.py', declaration))
            package_file.unlink()
            self.assertIsNone(status._contract_environment_id('python test.py', declaration))
            package_file.write_text('original code')
            os.environ['AIDD_TEST_DEP'] = 'changed'
            self.assertNotEqual(first, status._contract_environment_id('python test.py', declaration))
            del os.environ['AIDD_TEST_DEP']
            self.assertIsNone(status._contract_environment_id('python test.py', declaration))
            self.assertIsNone(status._contract_environment_id('python test.py', 'contract:offline;vars=none;packages=missing'))

    def test_evidence_must_be_intact_and_full_disables_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            data = b'# python test.py | exit 0 | now\n3 tests passed successfully\n'
            (d / 'evidence.txt').write_bytes(data)
            row = {'ok': True, 'exit': 0, 'cmd': 'python test.py', 'expected': 'exit 0',
                   'input_globs': ['test.py'], 'input_fp': 'abc', 'reuse_policy': 'hermetic',
                   'environment_id': 'env', 'environment_declaration': 'contract:offline;vars=none;packages=none',
                   'evidence': 'evidence.txt', 'sha1': hashlib.sha1(data).hexdigest()}
            prior = {'stable': True, 'results': [row]}
            self.assertEqual(len(status._reusable_input_rows(d, prior, False)), 1)
            self.assertEqual(status._reusable_input_rows(d, prior, True), {})
            (d / 'evidence.txt').write_text('tampered')
            self.assertEqual(status._reusable_input_rows(d, prior, False), {})


if __name__ == '__main__':
    unittest.main()
