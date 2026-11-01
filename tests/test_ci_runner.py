"""Fail-closed CI runner contract, exercised with synthetic suites only."""
import importlib.util
import io
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

spec = importlib.util.spec_from_file_location('aidd_parallel_ci', Path(__file__).with_name('run_parallel.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class TestCIRunner(unittest.TestCase):
    class Synthetic(unittest.TestCase):
        def test_pass(self):
            pass

        def test_fail(self):
            self.fail('synthetic failure')

        def test_error(self):
            raise RuntimeError('synthetic error')

        @unittest.skip('synthetic skip')
        def test_skip(self):
            pass

    def check(self, names, required):
        suite = unittest.TestSuite(self.Synthetic(name) for name in names)
        stream = io.StringIO()
        result = runner.run_suite(suite, stream, required)
        return result, stream.getvalue()

    def test_required_cases_pass(self):
        ident = self.Synthetic('test_pass').id()
        rc, output = self.check(['test_pass'], {ident})
        self.assertEqual(rc, 0, output)
        self.assertIn(ident, output)

    def test_missing_case_fails(self):
        rc, output = self.check(['test_pass'], {'missing.Case.test_required'})
        self.assertNotEqual(rc, 0)
        self.assertIn('missing.Case.test_required', output)

    def test_renamed_required_case_fails(self):
        rc, output = self.check(['test_pass'], {self.Synthetic('test_pass').id() + '_renamed'})
        self.assertNotEqual(rc, 0)
        self.assertIn('renamed', output)

    def test_required_skip_fails(self):
        rc, output = self.check(['test_skip'], {self.Synthetic('test_skip').id()})
        self.assertNotEqual(rc, 0)
        self.assertIn('synthetic skip', output)

    def test_failure_or_error_fails(self):
        for name in ('test_fail', 'test_error'):
            with self.subTest(name=name):
                rc, output = self.check([name], {self.Synthetic(name).id()})
                self.assertNotEqual(rc, 0)
                self.assertIn('synthetic', output)

    def test_guard_loader_failure_fails(self):
        stream = io.StringIO()
        with mock.patch.object(runner, 'load_old_guard', return_value=(None, 'loader failed')):
            self.assertEqual(runner.ci_worker(stream=stream), 1)
        self.assertIn('loader failed', stream.getvalue())

    def test_collection_error_fails(self):
        stream = io.StringIO()
        with mock.patch.object(runner, 'load_old_guard', return_value=(object(), None)), \
             mock.patch.object(runner.unittest.TestLoader, 'discover', side_effect=RuntimeError('collector failed')):
            self.assertEqual(runner.ci_worker(stream=stream), 1)
        self.assertIn('collector failed', stream.getvalue())

    def test_instrumentation_error_fails(self):
        stream = io.StringIO()
        with mock.patch.object(runner, 'load_old_guard', return_value=(object(), None)), \
             mock.patch.object(runner.unittest.TestLoader, 'discover', return_value=unittest.TestSuite()), \
             mock.patch.object(runner, 'run_suite', side_effect=RuntimeError('instrumentation failed')):
            self.assertEqual(runner.ci_worker(stream=stream), 1)
        self.assertIn('instrumentation failed', stream.getvalue())

    def test_zero_cases_fails(self):
        rc, output = self.check([], set())
        self.assertNotEqual(rc, 0)
        self.assertIn('0', output)

    def test_timeout_fails(self):
        with mock.patch.object(runner.subprocess, 'run', side_effect=subprocess.TimeoutExpired('worker', 1)), \
             mock.patch('sys.stderr', new_callable=io.StringIO) as err:
            self.assertEqual(runner.run_checked([], timeout_seconds=1), 1)
        self.assertIn('timeout', err.getvalue().lower())

    def test_worker_output_encoding_is_utf8(self):
        completed = subprocess.CompletedProcess([], 0, 'verificación', '')
        with mock.patch.object(runner.subprocess, 'run', return_value=completed) as child, \
             mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            self.assertEqual(runner.run_checked([]), 0)
        self.assertEqual(child.call_args.kwargs['env']['PYTHONIOENCODING'], 'utf-8')
        self.assertIn('verificación', out.getvalue())

    def manifest_case(self, contents, suite=None, digest=None, after=None):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'ids.txt'
            path.write_bytes(contents)
            digest = digest or hashlib.sha256(contents).hexdigest()
            suite = suite or unittest.TestSuite([self.Synthetic('test_pass')])
            module = self.Synthetic('test_pass').id().removeprefix('tests.').split('.')[0]
            stream = io.StringIO()
            with mock.patch.object(runner, 'MANIFEST_DIR', Path(tmp)), \
                 mock.patch.object(runner, 'MANIFEST_MODULES', {module}), \
                 mock.patch.object(runner, 'REQUIRED_IDS', frozenset()), \
                 mock.patch.object(runner, 'REQUIRED_008_NEW_IDS', frozenset()), \
                 mock.patch.object(runner, 'load_old_guard', return_value=(object(), None)), \
                 mock.patch.object(runner.unittest.TestLoader, 'discover', return_value=suite):
                if after is None:
                    return runner.ci_worker(stream, path, digest), stream.getvalue()
                original = runner.run_suite
                def mutate(*args):
                    rc = original(*args)
                    path.write_bytes(after)
                    return rc
                with mock.patch.object(runner, 'run_suite', side_effect=mutate):
                    return runner.ci_worker(stream, path, digest), stream.getvalue()

    def manifest_bytes(self, *names):
        return (''.join(sorted(self.Synthetic(n).id().removeprefix('tests.') + '\n' for n in names))).encode()

    def test_manifest_complete(self):
        self.assertEqual(self.manifest_case(self.manifest_bytes('test_pass'))[0], 0)

    def test_manifest_missing_id(self):
        self.assertEqual(self.manifest_case(self.manifest_bytes('test_fail'))[0], 1)

    def test_manifest_new_id(self):
        suite = unittest.TestSuite([self.Synthetic('test_pass'), self.Synthetic('test_fail')])
        self.assertEqual(self.manifest_case(self.manifest_bytes('test_pass'), suite)[0], 1)

    def test_manifest_duplicate_id(self):
        data = self.manifest_bytes('test_pass') * 2
        self.assertEqual(self.manifest_case(data)[0], 1)

    def test_manifest_required_skip(self):
        self.assertEqual(self.manifest_case(self.manifest_bytes('test_skip'), unittest.TestSuite([self.Synthetic('test_skip')]))[0], 1)
        class Cases(unittest.TestCase):
            def test_subtest(self):
                with self.subTest(i=1): self.skipTest('subtest skip')
            @unittest.expectedFailure
            def test_expected_failure(self): self.fail('expected failure')
        for name in ('test_subtest', 'test_expected_failure'):
            with self.subTest(name=name):
                case = Cases(name)
                stream = io.StringIO()
                self.assertEqual(runner.run_suite(unittest.TestSuite([case]), stream, {case.id()}), 1)

    def test_manifest_class_skip(self):
        @unittest.skip('class skipped')
        class Skipped(unittest.TestCase):
            def test_case(self): pass
        ident = Skipped('test_case').id()
        stream = io.StringIO()
        rc = runner.run_suite(unittest.TestSuite([Skipped('test_case')]), stream, {ident})
        self.assertEqual(rc, 1)
        self.assertIn('class skipped', stream.getvalue())

    def test_manifest_changed(self):
        self.assertEqual(self.manifest_case(self.manifest_bytes('test_pass'), after=b'changed\n')[0], 1)

    def test_manifest_wrong_digest(self):
        self.assertEqual(self.manifest_case(self.manifest_bytes('test_pass'), digest='0' * 64)[0], 1)

    def test_manifest_empty(self):
        self.assertEqual(self.manifest_case(b'')[0], 1)

    def test_manifest_unreadable(self):
        with self.assertRaises(OSError):
            runner.load_coverage_manifest(runner.MANIFEST_DIR / 'missing')

    def test_manifest_malformed(self):
        self.assertEqual(self.manifest_case(b'bad\n')[0], 1)

    def test_manifest_cli_single_worker(self):
        args = ['--ci-guard', '--coverage-manifest', 'x', '--manifest-sha256', 'a' * 64, '--coverage-timeout', '3600']
        with mock.patch.object(runner, 'run_checked', return_value=0) as call:
            self.assertEqual(runner.main(args), 0)
        call.assert_called_once()
        self.assertEqual(call.call_args.kwargs['timeout_seconds'], 3600)

    def test_manifest_worker_single_suite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'ids.txt'
            data = self.manifest_bytes('test_pass')
            path.write_bytes(data)
            suite = unittest.TestSuite([self.Synthetic('test_pass')])
            module = self.Synthetic('test_pass').id().removeprefix('tests.').split('.')[0]
            with mock.patch.object(runner, 'MANIFEST_DIR', Path(tmp)), \
                 mock.patch.object(runner, 'MANIFEST_MODULES', {module}), \
                 mock.patch.object(runner, 'load_old_guard', return_value=(object(), None)), \
                 mock.patch.object(runner.unittest.TestLoader, 'discover', return_value=suite) as discover, \
                 mock.patch.object(runner, 'run_suite', return_value=0) as execute:
                self.assertEqual(runner.ci_worker(io.StringIO(), path, hashlib.sha256(data).hexdigest()), 0)
            discover.assert_called_once()
            execute.assert_called_once()

    def test_manifest_cli_incomplete_options(self):
        with mock.patch.object(runner, 'run_checked') as call:
            self.assertEqual(runner.main(['--ci-guard', '--coverage-manifest', 'x']), 2)
        call.assert_not_called()

    def test_manifest_cli_invalid_combinations(self):
        cases = [
            ['--ci-guard', '--coverage-manifest', 'x', '--manifest-sha256', 'z' * 64, '--coverage-timeout', '1'],
            ['--ci-guard', '--coverage-manifest', 'x', '--manifest-sha256', 'a' * 64, '--coverage-timeout', '0'],
            ['--ci-guard', '--coverage-manifest', 'x', '--manifest-sha256', 'a' * 64, '--coverage-manifest', 'y'],
            ['--coverage-manifest', 'x', '--manifest-sha256', 'a' * 64, '--coverage-timeout', '1'],
            ['--coverage-manifest', '--ci-guard', '--manifest-sha256', '0' * 64, '--coverage-timeout', '1', 'orphan'],
        ]
        with mock.patch.object(runner, 'run_checked') as call:
            for args in cases:
                self.assertEqual(runner.main(args), 2)
        call.assert_not_called()

    def test_manifest_timeout(self):
        with mock.patch.object(runner.subprocess, 'run', side_effect=subprocess.TimeoutExpired('worker', 2)):
            self.assertEqual(runner.run_checked([], 2), 1)

    def test_manifest_loader_failure(self):
        with mock.patch.object(runner, 'load_old_guard', return_value=(None, 'bad')):
            self.assertEqual(runner.ci_worker(io.StringIO(), 'x', 'a' * 64), 1)

    def test_manifest_discovery_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'ids.txt'
            data = self.manifest_bytes('test_pass')
            path.write_bytes(data)
            with mock.patch.object(runner, 'MANIFEST_DIR', Path(tmp)), \
                 mock.patch.object(runner, 'load_old_guard', return_value=(object(), None)), \
                 mock.patch.object(runner.unittest.TestLoader, 'discover', side_effect=RuntimeError('bad')):
                self.assertEqual(runner.ci_worker(io.StringIO(), path, hashlib.sha256(data).hexdigest()), 1)

    def test_legacy_cli_unchanged(self):
        with mock.patch.object(runner, 'run_checked', return_value=0) as call:
            self.assertEqual(runner.main(['--ci-guard']), 0)
        call.assert_called_once_with([])
