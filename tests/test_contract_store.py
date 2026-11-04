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

import json
import os

TABLE_HEADER = '## Verification\n| # | Command | Expected | Inputs | Reuse | Environment |\n|---|---|---|---|---|---|\n'
CONTRACT_ROW = '| V1 | {cmd} | {expected} | test.py | hermetic | contract:offline;vars=none;packages=none |\n'


class CrossSpecContractReuse(unittest.TestCase):
    """Amendment 03 of spec 007: cross-spec, cross-invocation reuse of offline-contract rows (AC-251..AC-258)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.calls = []
        self.env = ['env1']
        self.inputs = ['input1']
        self.exit_code = {'one': 0, 'two': 0}
        for name in ('one', 'two'):
            spec = self.root / 'specs' / name
            spec.mkdir(parents=True)
            (spec / 'tasks.md').write_text('| Task | Target file |\n|---|---|\n| T-01 | `test.py` |\n')
            self.write_spec(name)
        (self.root / 'test.py').write_text('print(1)')

    def tearDown(self):
        self._tmp.cleanup()

    def write_spec(self, name, cmd='python test.py', expected='exit 0', contract=True):
        if contract:
            text = TABLE_HEADER + CONTRACT_ROW.format(cmd=cmd, expected=expected)
        else:
            text = '## Verification\n| # | Command | Expected |\n|---|---|---|\n| V1 | {} | {} |\n'.format(cmd, expected)
        (self.root / 'specs' / name / 'spec.md').write_text(text)

    @property
    def index_path(self):
        return self.root / '.aidd' / 'evidence' / 'contract-reuse-v1.json'

    @property
    def object_dir(self):
        return self.root / '.aidd' / 'evidence' / 'contract-reuse-v1'

    def index_entries(self):
        return json.loads(self.index_path.read_text(encoding='utf-8'))['entries']

    def object_path(self, sha256):
        return self.object_dir / f'{sha256}.txt'

    @contextlib.contextmanager
    def patched(self, stdout=None):
        root = self.root
        state = ('git', {'test.py': b'x'})

        def run(cmd, _root, output, _timeout):
            spec = run.current
            self.calls.append((spec, cmd))
            output.write_text('three assertions passed successfully\n')
            return self.exit_code.get(spec, 0), ''
        run.current = None

        def resolve(name, _root):
            run.current = name
            return root / 'specs' / name

        with patch.dict(os.environ, {}), \
             patch.object(status.ev, 'find_root', return_value=root), \
             patch.object(status, '_resolve_spec', side_effect=resolve), \
             patch.object(status, '_current_session', return_value='session'), \
             patch.object(status.ev, 'latest_verify_run', return_value=None), \
             patch.object(status.ev, 'code_state', return_value=state), \
             patch.object(status.ev, 'state_diff', return_value=[]), \
             patch.object(status.ev, 'fingerprint_of', return_value='fingerprint'), \
             patch.object(status.ev, 'worktree_fingerprint', return_value='fp'), \
             patch.object(status.rules, 'row_input_fingerprint', side_effect=lambda *_: self.inputs[0]), \
             patch.object(status.ev, 'append_verify_run', return_value=True), \
             patch.object(status, '_contract_environment_id', side_effect=lambda *_: self.env[0]), \
             patch.object(status, '_run_row', side_effect=run), \
             contextlib.redirect_stdout(stdout if stdout is not None else io.StringIO()):
            os.environ.pop('AIDD_VERIFY_ROUND', None)
            yield

    def test_second_invocation_other_spec_reuses(self):
        with self.patched():
            self.assertEqual(status.cmd_verify('one'), 0)
            sink = {}
            self.assertEqual(status.cmd_verify('two', result_sink=sink), 0)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(sink['results']), 1)
        row = sink['results'][0]
        self.assertIs(row['reused'], True)
        self.assertIs(row['cross_spec'], True)
        self.assertEqual(row['source_spec'], 'one')
        entries = self.index_entries()
        self.assertEqual(len(entries), 1)
        stored = self.object_path(entries[0]['sha256']).read_bytes()
        self.assertEqual(hashlib.sha256(stored).hexdigest(), entries[0]['sha256'])
        self.assertEqual(row['source_sha256'], entries[0]['sha256'])
        self.assertEqual((self.root / 'specs' / 'two' / 'evidence' / 'verify-V1.txt').read_bytes(), stored)

    def test_any_identity_change_executes(self):
        with self.patched():
            self.assertEqual(status.cmd_verify('one'), 0)
            self.assertTrue(self.index_path.is_file())
            self.assertEqual(len(self.calls), 1)
            # (a) input fingerprint
            self.inputs[0] = 'input2'
            self.assertEqual(status.cmd_verify('two'), 0)
            self.assertEqual(len(self.calls), 2)
            self.inputs[0] = 'input1'
            # (b) environment id
            self.env[0] = 'env2'
            self.assertEqual(status.cmd_verify('two'), 0)
            self.assertEqual(len(self.calls), 3)
            self.env[0] = 'env1'
            # (c) Expected
            self.write_spec('two', expected='contains: passed')
            self.assertEqual(status.cmd_verify('two'), 0)
            self.assertEqual(len(self.calls), 4)
            # (d) command
            self.write_spec('two', cmd='python test.py -v')
            self.assertEqual(status.cmd_verify('two'), 0)
            self.assertEqual(len(self.calls), 5)

    def test_damaged_store_executes(self):
        with self.patched():
            self.assertEqual(status.cmd_verify('one'), 0)
            self.assertEqual(len(self.calls), 1)
            # (a) object deleted
            self.object_path(self.index_entries()[-1]['sha256']).unlink()
            self.assertEqual(status.cmd_verify('two'), 0)
            self.assertEqual(len(self.calls), 2)
            # (b) object bytes altered
            self.object_path(self.index_entries()[-1]['sha256']).write_bytes(b'garbage')
            self.assertEqual(status.cmd_verify('two'), 0)
            self.assertEqual(len(self.calls), 3)
            # (c) index corrupted
            self.index_path.write_text('{not json', encoding='utf-8')
            self.assertEqual(status.cmd_verify('two'), 0)
            self.assertEqual(len(self.calls), 4)

    def test_failure_is_never_stored(self):
        self.exit_code['one'] = 1
        with self.patched():
            self.assertEqual(status.cmd_verify('one'), 1)
            self.assertEqual(len(self.calls), 1)
            if self.index_path.exists():
                self.assertEqual([e for e in self.index_entries() if e.get('spec') == 'one'], [])
            self.assertEqual(status.cmd_verify('two'), 0)
            self.assertEqual(len(self.calls), 2)
        # the PASS of `two` is stored; the FAIL of `one` never is
        self.assertEqual([e['spec'] for e in self.index_entries()], ['two'])

    def test_db_runner_has_no_environment_id(self):
        declaration = 'contract:offline;vars=none;packages=none'
        self.assertIsNone(status._contract_environment_id(
            'python eDoc/tools/db_verify.py --psql "docker exec -i x psql -U postgres" --tap', declaration))
        self.assertIsNone(status._contract_environment_id('python tools/run.py --tap', declaration))

    def test_full_and_round_off_disable(self):
        with self.patched():
            self.assertEqual(status.cmd_verify('one', full=True), 0)
            self.assertEqual(len(self.calls), 1)
            self.assertFalse(self.index_path.exists())
            with patch.dict(os.environ, {'AIDD_VERIFY_ROUND': 'off'}):
                self.assertEqual(status.cmd_verify('one'), 0)
            self.assertEqual(len(self.calls), 2)
            self.assertFalse(self.index_path.exists())
            # control: the same row is stored when neither switch is set
            self.assertEqual(status.cmd_verify('one'), 0)
            self.assertEqual(len(self.calls), 3)
            self.assertTrue(self.index_path.is_file())
            # and neither switch looks the stored entry up
            self.assertEqual(status.cmd_verify('two', full=True), 0)
            self.assertEqual(len(self.calls), 4)
            with patch.dict(os.environ, {'AIDD_VERIFY_ROUND': 'off'}):
                self.assertEqual(status.cmd_verify('two'), 0)
            self.assertEqual(len(self.calls), 5)

    def test_non_contract_rows_unchanged(self):
        self.write_spec('one', contract=False)
        self.write_spec('two', contract=False)
        with self.patched():
            self.assertEqual(status.cmd_verify('one'), 0)
            self.assertEqual(status.cmd_verify('two'), 0)
        self.assertEqual(len(self.calls), 2)
        self.assertFalse(self.index_path.exists())

    def test_store_write_failure_is_a_note(self):
        out = io.StringIO()
        with self.patched(stdout=out), patch.object(status, '_contract_store_put', side_effect=OSError):
            self.assertEqual(status.cmd_verify('one'), 0)
        self.assertEqual(len(self.calls), 1)
        self.assertIn('note: contract store not written', out.getvalue())


if __name__ == '__main__':
    unittest.main()
