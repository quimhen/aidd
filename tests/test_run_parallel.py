"""Behavioral checks for the standalone parallel test runner."""
import contextlib
import io
import json
import subprocess
import sys
import time
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from tests import run_parallel as runner


class TestRunner(unittest.TestCase):
    def test_git_error_is_not_an_empty_change_set(self):
        failed = subprocess.CompletedProcess([], 128, '', 'not a repository')
        with patch.object(runner.subprocess, 'run', return_value=failed):
            with self.assertRaises(RuntimeError):
                runner.changed_paths()

    def test_changed_helper_conservatively_selects_all(self):
        with patch.object(runner, 'changed_paths', return_value=['tests/gate_fixtures.py']):
            selected, _ = runner.affected(['test_one', 'test_two'])
        self.assertEqual(selected, ['test_one', 'test_two'])

    def test_empty_test_run_and_timeout_are_failures(self):
        empty = MagicMock(returncode=0)
        empty.communicate.return_value = ('', 'Ran 0 tests in 0.001s\nOK')
        with patch.object(runner.subprocess, 'Popen', return_value=empty):
            self.assertNotEqual(runner.run('tests.example')[1], 0)

    def test_timeout_kills_descendant_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests = root / 'tests'
            tests.mkdir()
            (tests / '__init__.py').write_text('', encoding='utf-8')
            sentinel = root / 'child-finished'
            started = root / 'child-started'
            child = ("import time,pathlib;pathlib.Path(%r).write_text('started');"
                     "time.sleep(3);pathlib.Path(%r).write_text('alive')") % (str(started), str(sentinel))
            (tests / 'test_slow.py').write_text(
                'import unittest,subprocess,sys,time\n'
                'class TestSlow(unittest.TestCase):\n'
                ' def test_timeout(self):\n'
                '  subprocess.Popen([sys.executable,"-c",%r])\n'
                '  time.sleep(30)\n' % child, encoding='utf-8')
            with patch.object(runner, 'ROOT', root):
                self.assertEqual(runner.run('tests.test_slow', 1.5)[1], 124)
            self.assertTrue(started.exists(), 'the child process did not start before timeout')
            time.sleep(3.5)
            self.assertFalse(sentinel.exists(), 'the timed-out runner left a child running')

    def test_module_is_not_split_by_default(self):
        self.assertEqual(runner.targets('test_run_parallel'), ['tests.test_run_parallel'])

    def test_pytest_functions_use_pytest_and_failure_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            tests_dir = Path(tmp) / 'tests'
            tests_dir.mkdir()
            (tests_dir / 'test_sample.py').write_text('def test_one():\n    assert True\n', encoding='utf-8')
            missing = MagicMock(returncode=1)
            missing.communicate.return_value = ('', 'No module named pytest')
            with patch.object(runner, 'ROOT', Path(tmp)), patch.object(runner.subprocess, 'Popen', return_value=missing) as run:
                self.assertEqual(runner.targets('test_sample', True), ['tests.test_sample'])
                self.assertEqual(runner.run('tests.test_sample')[1], 1)
                self.assertIn('pytest', run.call_args.args[0])

    def test_mixed_unittest_and_pytest_classes_use_pytest(self):
        with tempfile.TemporaryDirectory() as tmp:
            tests = Path(tmp) / 'tests'
            tests.mkdir()
            (tests / 'test_mixed.py').write_text(
                'import unittest\nclass TestUnit(unittest.TestCase):\n def test_a(self): pass\n'
                'class Helper: pass\nclass TestPytest(Helper):\n def test_b(self): pass\n', encoding='utf-8')
            with patch.object(runner, 'ROOT', Path(tmp)):
                self.assertTrue(runner.uses_pytest('test_mixed'))
                self.assertEqual(runner.targets('test_mixed', True), ['tests.test_mixed'])

    def test_retry_preserves_original_failure_and_deduplicates(self):
        calls = []

        def fake_run(unit, timeout):
            calls.append(unit)
            return (unit, 1 if len(calls) == 1 else 0, 'first failure' if len(calls) == 1 else 'ok', 0.1)

        out = io.StringIO()
        with patch.object(runner, 'run', side_effect=fake_run), contextlib.redirect_stdout(out):
            rc = runner.main(['--json', '--retry', 'test_example', 'test_example'])
        result = json.loads(out.getvalue())
        self.assertEqual(rc, 1)
        self.assertEqual(calls, ['tests.test_example', 'tests.test_example'])
        self.assertEqual(result['results'][0]['output'], 'first failure')
        self.assertEqual(result['results'][0]['retry']['exit'], 0)
