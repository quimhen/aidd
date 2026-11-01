import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skill' / 'scripts'))
import aidd_status as status


class TaskVerification(unittest.TestCase):
    tasks = ('| Task | Target file |\n|---|---|\n| T-01 | `a.py` |\n'
             '| T-02 | `b.py` |\n| T-03 | `c.py` |\n')

    def test_range_selection_and_missing_coverage_fail_closed(self):
        rows = [{'n': 'V-1', 'covers': 'T-01..T-03'}, {'n': 'V-2', 'covers': 'T-03'}]
        self.assertEqual(status._task_rows(self.tasks, rows, ['T-02']), rows[:1])
        with self.assertRaisesRegex(ValueError, 'missing verification'):
            status._task_rows(self.tasks, [{'covers': 'T-01'}], ['T-02'])
        with self.assertRaisesRegex(ValueError, 'unknown'):
            status._task_rows(self.tasks, rows, ['T-99'])
        with self.assertRaisesRegex(ValueError, 'descending'):
            status._task_rows(self.tasks, [{'covers': 'T-03..T-01'}], ['T-02'])

    def test_ambiguous_exclusions_and_malformed_ranges_are_refused(self):
        for covers in ('except T-01', 'T-01..T-0x', 'T-01..unknown', 'T-01/T-02', 'T-01/02'):
            with self.subTest(covers=covers), self.assertRaises(ValueError):
                status._task_rows(self.tasks, [{'covers': covers}], ['T-01'])

    def test_partial_runs_only_selected_row_with_separate_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = root / 'specs' / 's'
            spec.mkdir(parents=True)
            (root / 'selected.py').write_text('print("ok")', encoding='utf-8')
            (root / 'other.py').write_text('print("ok")', encoding='utf-8')
            (spec / 'tasks.md').write_text(self.tasks, encoding='utf-8')
            (spec / 'spec.md').write_text(
                '## Verification\n| # | Command | Expected | Covers | Inputs |\n'
                '|---|---|---|---|---|\n'
                '| V-1 | python selected.py | exit 0 | T-01..T-03 | selected.py |\n'
                '| V-2 | python other.py | exit 0 | T-03 | other.py |\n', encoding='utf-8')
            state = ('git', {'selected.py': b'selected'})
            calls, recorded = [], []
            def run(cmd, _root, output, _timeout):
                calls.append(cmd)
                output.write_text('three assertions passed successfully\n', encoding='utf-8')
                return 0, ''
            def append(_root, _session, kind, **detail):
                recorded.append((kind, detail))
                return True
            with patch.object(status.ev, 'find_root', return_value=root), \
                 patch.object(status, '_resolve_spec', return_value=spec), \
                 patch.object(status, '_current_session', return_value='session'), \
                 patch.object(status.ev, 'code_state', return_value=state), \
                 patch.object(status.ev, 'state_diff', return_value=[]), \
                 patch.object(status.ev, 'fingerprint_of', return_value='fingerprint'), \
                 patch.object(status.ev, 'worktree_fingerprint', return_value='fp'), \
                 patch.object(status.rules, 'row_input_fingerprint', return_value='input-fp'), \
                 patch.object(status.ev, 'append', side_effect=append), \
                 patch.object(status.ev, 'append_verify_run') as full_event, \
                 patch.object(status, '_run_row', side_effect=run), contextlib.redirect_stdout(io.StringIO()) as output:
                rc = status.cmd_verify(str(spec), task_ids=['T-02'])
                self.assertEqual(rc, 0, output.getvalue())
            self.assertEqual(calls, ['python selected.py'])
            full_event.assert_not_called()
            self.assertEqual(recorded[0][0], 'task_verify_run')
            self.assertFalse(recorded[0][1]['scope_attested'])
            self.assertEqual(recorded[0][1]['code_scope'], ['selected.py'])
            self.assertIn('T-01..T-03', output.getvalue())
            self.assertTrue((spec / recorded[0][1]['results'][0]['evidence']).is_file())

    def test_cli_rejects_full_and_task_selection_before_running(self):
        with patch.object(status, 'cmd_verify') as verify, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(status.main(['verify', 's', '--tasks', 'T-01', '--full']), 1)
        verify.assert_not_called()

    def test_cli_passes_normalized_unique_task_selection(self):
        with patch.object(status, 'cmd_verify', return_value=0) as verify, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(status.main(['verify', 's', '--tasks', 't-01,T-02']), 0)
        verify.assert_called_once_with('s', task_ids=['T-01', 'T-02'])

    def test_preflight_rejects_any_invalid_row_before_running_other_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = root / 'specs' / 's'
            spec.mkdir(parents=True)
            (root / 'selected.py').write_text('print("ok")', encoding='utf-8')
            (spec / 'tasks.md').write_text(self.tasks, encoding='utf-8')
            (spec / 'spec.md').write_text(
                '## Verification\n| # | Command | Expected | Covers |\n|---|---|---|---|\n'
                '| V-1 | python selected.py | exit 0 | T-01 |\n'
                '| V-2 | echo hello | exit 0 | T-02 |\n', encoding='utf-8')
            with patch.object(status.ev, 'find_root', return_value=root), \
                 patch.object(status, '_resolve_spec', return_value=spec), \
                 patch.object(status, '_run_row') as run, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(status.cmd_verify(str(spec), task_ids=['T-01', 'T-02']), 1)
            run.assert_not_called()

    def test_preflight_refuses_empty_or_unsupported_expected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = root / 'specs' / 's'
            spec.mkdir(parents=True)
            (root / 'selected.py').write_text('print("ok")', encoding='utf-8')
            (spec / 'tasks.md').write_text(self.tasks, encoding='utf-8')
            for expected in ('', 'exit 1', 'anything', 'contains:'):
                with self.subTest(expected=expected):
                    (spec / 'spec.md').write_text(
                        '## Verification\n| # | Command | Expected | Covers |\n|---|---|---|---|\n'
                        f'| V-1 | python selected.py | {expected} | T-01 |\n', encoding='utf-8')
                    with patch.object(status.ev, 'find_root', return_value=root), \
                         patch.object(status, '_resolve_spec', return_value=spec), \
                         patch.object(status, '_run_row') as run, contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(status.cmd_verify(str(spec), task_ids=['T-01']), 1)
                    run.assert_not_called()

    def test_selected_fingerprint_ignores_other_tasks_and_rows(self):
        spec = ('## Verification\n| # | Command | Expected | Covers | Inputs |\n|---|---|---|---|---|\n'
                '| V-1 | python a.py | exit 0 | T-01 | a.py |\n'
                '| V-2 | python b.py | exit 0 | T-02 | b.py |\n')
        baseline = status._task_selection_fingerprint(self.tasks, spec, ['T-01'])
        self.assertEqual(baseline, status._task_selection_fingerprint(
            self.tasks.replace('`b.py`', '`different.py`'), spec.replace('python b.py', 'python other.py'), ['T-01']))
        self.assertNotEqual(baseline, status._task_selection_fingerprint(
            self.tasks.replace('`a.py`', '`changed.py`'), spec, ['T-01']))
        self.assertNotEqual(baseline, status._task_selection_fingerprint(
            self.tasks, spec.replace('T-01 | a.py', 'T-01, T-03 | a.py'), ['T-01']))

    def test_selected_fingerprint_ignores_task_status_writeback(self):
        tasks = ('| Task | Target file | Status | Tracker ref |\n|---|---|---|---|\n'
                 '| T-01 | `a.py` | pending | 1 |\n')
        spec = ('## Verification\n| # | Command | Expected | Covers |\n|---|---|---|---|\n'
                '| V-1 | python a.py | exit 0 | T-01 |\n')
        updated = tasks.replace('| pending | 1 |', '| done | 2 |')
        self.assertEqual(status._task_selection_fingerprint(tasks, spec, ['T-01']),
                         status._task_selection_fingerprint(updated, spec, ['T-01']))

    def test_selected_task_mutation_during_run_is_recorded_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = root / 'specs' / 's'
            spec.mkdir(parents=True)
            (root / 'selected.py').write_text('print("ok")', encoding='utf-8')
            tasks = spec / 'tasks.md'
            tasks.write_text(self.tasks, encoding='utf-8')
            (spec / 'spec.md').write_text(
                '## Verification\n| # | Command | Expected | Covers | Inputs |\n|---|---|---|---|---|\n'
                '| V-1 | python selected.py | exit 0 | T-01 | selected.py |\n', encoding='utf-8')
            state = ('git', {'selected.py': b'selected'})
            recorded = []
            def run(_cmd, _root, output, _timeout):
                output.write_text('three assertions passed successfully\n', encoding='utf-8')
                tasks.write_text(self.tasks.replace('`a.py`', '`changed.py`'), encoding='utf-8')
                return 0, ''
            def append(_root, _session, kind, **detail):
                recorded.append((kind, detail))
                return True
            with patch.object(status.ev, 'find_root', return_value=root), \
                 patch.object(status, '_resolve_spec', return_value=spec), \
                 patch.object(status, '_current_session', return_value='session'), \
                 patch.object(status.ev, 'code_state', return_value=state), \
                 patch.object(status.ev, 'state_diff', return_value=[]), \
                 patch.object(status.ev, 'fingerprint_of', return_value='fp'), \
                 patch.object(status.ev, 'worktree_fingerprint', return_value='fp'), \
                 patch.object(status.rules, 'row_input_fingerprint', return_value='input-fp'), \
                 patch.object(status.ev, 'append', side_effect=append), \
                 patch.object(status, '_run_row', side_effect=run), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(status.cmd_verify(str(spec), task_ids=['T-01']), 1)
            self.assertFalse(recorded[0][1]['ok'])
            self.assertNotEqual(recorded[0][1]['selection_fp_start'], recorded[0][1]['selection_fp_end'])
