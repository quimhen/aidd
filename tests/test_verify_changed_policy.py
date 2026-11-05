"""aidd verify --changed policy (spec 007 amendment 05, AC-285..AC-290, FR-259..FR-261). Temp dirs only; no DB, Docker or network."""
import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skill' / 'scripts'))
import aidd_status as status
import aidd_unit_audit as impact

TASKS = '| Task | Target file |\n|---|---|\n| T-01 | `a.py` |\n| T-02 | `b.py` |\n| T-03 | `c.py` |\n'


def _spec(rows):
    lines = ['## Verification', '| # | Command | Expected | Covers | Inputs |', '|---|---|---|---|---|']
    for n, covers, inputs in rows:
        lines.append(f'| {n} | python {n.lower()}.py | exit 0 | {covers} | {inputs} |')
    return '\n'.join(lines) + '\n'


class VerifyChangedPolicy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.spec = self.root / 'specs' / '001-example'
        self.spec.mkdir(parents=True)
        (self.spec / 'tasks.md').write_text(TASKS)
        for name in ('a.py', 'b.py', 'c.py'):
            (self.root / name).write_text('print(1)\n')

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, rows):
        (self.spec / 'spec.md').write_text(_spec(rows))

    def _select(self, changed):
        with patch.object(impact, 'git_changed_paths', return_value=changed):
            return status._changed_selection(self.root, '001-example')

    def test_row_without_inputs_always_runs(self):
        self._write([('V-1', 'T-01', 'a.py'), ('V-2', 'T-02', ''), ('V-3', 'T-01..T-03', 'a.py, b.py, c.py')])
        tasks, always, warnings = self._select(['a.py'])
        self.assertIn('T-01', tasks)
        self.assertEqual(always, ['V-2'])
        self.assertTrue(any('verification row V-2' in w and 'always runs' in w for w in warnings), warnings)

    def test_uncovered_changed_task_runs_whole_suite(self):
        self._write([('V-1', 'T-01', 'a.py'), ('V-9', 'T-01..T-02', 'a.py, b.py')])
        _, always, warnings = self._select(['c.py'])
        self.assertTrue(any('task T-03 is covered by no verification row' in w for w in warnings), warnings)
        self.assertEqual(always, ['V-1', 'V-9'])
        self._write([('V-1', 'T-01', 'a.py'), ('V-9', 'T-01..T-02', 'a.py, b.py'),
                     ('V-10', 'T-01..T-03', 'a.py, b.py, c.py')])
        _, always, warnings = self._select(['c.py'])
        self.assertEqual(always, ['V-10'])
        self.assertTrue(any('task T-03 is covered by no verification row' in w for w in warnings), warnings)

    def test_uncovered_task_without_whole_suite_runs_all(self):
        self._write([('V-1', 'T-01', 'a.py'), ('V-2', 'T-02', 'b.py')])
        _, always, _ = self._select(['c.py'])
        self.assertEqual(always, ['V-1', 'V-2'])

    def test_malformed_covers_refuses(self):
        self._write([('V-1', 'T-01', 'a.py'), ('V-2', 'T-99', 'b.py')])
        with self.assertRaises(ValueError):
            self._select(['a.py'])
        self._write([('V-1', 'T-01', 'a.py'), ('V-2', 'all except T-02', 'b.py')])
        with self.assertRaises(ValueError):
            self._select(['a.py'])

    def test_inputs_matching_no_file_refuses(self):
        self._write([('V-1', 'T-01', 'a.py'), ('V-2', 'T-02', 'missing/*.py')])
        with self.assertRaises(ValueError):
            self._select(['a.py'])

    def test_missing_literal_input_selected_by_name(self):
        (self.root / 'b.py').unlink()
        self._write([('V-1', 'T-01', 'a.py'), ('V-2', 'T-02', 'b.py')])
        self.assertEqual(self._select(['b.py']), (['T-02'], [], []))
        with self.assertRaisesRegex(ValueError, 'no declared task Inputs'):
            self._select(['other.py'])

    def test_wildcard_input_matching_nothing_refuses(self):
        self._write([('V-1', 'T-01', 'a.py'), ('V-2', 'T-02', 'gone/*.py')])
        with self.assertRaisesRegex(ValueError, 'verification row V-2 has missing or invalid Inputs'):
            self._select(['a.py'])

    def test_fully_declared_spec_unchanged(self):
        (self.spec / 'tasks.md').write_text('| Task | Target file |\n|---|---|\n| T-01 | `a.py` |\n| T-02 | `b.py` |\n')
        (self.spec / 'spec.md').write_text('## Verification\n| # | Command | Expected | Covers | Inputs |\n|---|---|---|---|---|\n| V-1 | python a.py | exit 0 | T-01 | a.py |\n| V-2 | python b.py | exit 0 | T-02 | b.py |\n')
        with patch.object(impact, 'git_changed_paths', return_value=['a.py', 'other.py']):
            self.assertEqual(status._changed_task_selection(self.root, '001-example'), ['T-01'])
        with patch.object(impact, 'git_changed_paths', return_value=['other.py']):
            with self.assertRaisesRegex(ValueError, 'no declared task Inputs'):
                status._changed_task_selection(self.root, '001-example')
        self.assertEqual(self._select(['a.py']), (['T-01'], [], []))

    def test_cmd_verify_runs_always_rows_and_records_them(self):
        self._write([('V-1', 'T-01', 'a.py'), ('V-2', 'T-02', ''), ('V-3', 'T-01..T-03', 'a.py, b.py, c.py')])
        root = self.root
        for name in ('v-1.py', 'v-2.py', 'v-3.py'):
            (root / name).write_text('print(1)\n')
        state, calls, events = ('git', {'a.py': b'x'}), [], []

        def run(cmd, _root, output, _timeout):
            calls.append(cmd)
            output.write_text('three assertions passed successfully\n')
            return 0, ''

        def append(_root, _session, kind, **kw):
            events.append((kind, kw))
            return True
        out = io.StringIO()
        with patch.object(status.ev, 'find_root', return_value=root), \
             patch.object(status, '_resolve_spec', side_effect=lambda name, _root: root / 'specs' / name), \
             patch.object(status, '_current_session', return_value='session'), \
             patch.object(status.ev, 'latest_verify_run', return_value=None), \
             patch.object(status.ev, 'code_state', return_value=state), \
             patch.object(status.ev, 'state_diff', return_value=[]), \
             patch.object(status.ev, 'fingerprint_of', return_value='fingerprint'), \
             patch.object(status.ev, 'worktree_fingerprint', return_value='fp'), \
             patch.object(status.rules, 'row_input_fingerprint', side_effect=lambda *_: 'input1'), \
             patch.object(status.ev, 'append_verify_run', return_value=True), \
             patch.object(status, '_contract_environment_id', side_effect=lambda *_: 'env1'), \
             patch.object(status, '_run_row', side_effect=run), \
             patch.object(status.ev, 'append', side_effect=append), contextlib.redirect_stdout(out):
            status.cmd_verify('001-example', task_ids=['T-01'], always_rows=['V-2'])
        self.assertEqual(sorted(calls), ['python v-1.py', 'python v-2.py', 'python v-3.py'], out.getvalue())
        self.assertIn('always-run row V-2', out.getvalue())
        recorded = [kw for kind, kw in events if kind == 'task_verify_run']
        self.assertEqual(len(recorded), 1, out.getvalue())
        self.assertEqual(recorded[0]['always_rows'], ['V-2'])


class BaseRevision(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _git(self, *args):
        return subprocess.run(['git', *args], cwd=self.root, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()

    def _two_commits(self):
        self._git('init', '-q')
        (self.root / 'first.py').write_text('first', encoding='utf-8')
        self._git('add', '--all')
        self._git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'base')
        (self.root / 'second.py').write_text('second', encoding='utf-8')
        self._git('add', '--all')
        self._git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'second')

    def test_base_accepts_head_tilde(self):
        self._two_commits()
        self.assertEqual(impact.resolve_base(self.root, 'HEAD~1'), self._git('rev-parse', 'HEAD~1'))
        self.assertIn('second.py', impact.git_changed_paths(self.root, 'HEAD~1'))

    def test_base_rejects_option_like_and_unknown(self):
        self._two_commits()
        for bad in ('--all', '', 'a b', 'nosuchrev'):
            with self.assertRaises(ValueError, msg=repr(bad)):
                impact.resolve_base(self.root, bad)


if __name__ == '__main__':
    unittest.main()
