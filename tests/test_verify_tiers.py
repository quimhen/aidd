"""Amendment 10 (extension b) of spec 007: Tier functional|perf in `aidd verify` and the perf close gap
(aidd:FR-397..FR-400, AC-453..AC-457). stdlib unittest."""
import contextlib
import hashlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skill' / 'scripts'))
import aidd_rules as rules  # noqa: E402
import aidd_status as status  # noqa: E402

LEGACY = ('## Verification\n| # | Command | Expected | Covers |\n|---|---|---|---|\n'
          '| V-1 | python a.py | exit 0 | FR-1 |\n| V-2 | python b.py | exit 0 | FR-2 |\n')
TIERED = ('## Verification\n| # | Command | Expected | Covers | Tier |\n|---|---|---|---|---|\n'
          '| V-1 | python a.py | exit 0 | FR-1 | functional |\n| V-2 | python b.py | exit 0 | FR-2 | perf |\n')


class TierParsing(unittest.TestCase):
    def test_legacy_hash_unchanged(self):
        # pinned with the code before this amendment (same rows, no Tier column, no Perf line)
        body = 'V-1|python a.py|exit 0\nV-2|python b.py|exit 0'
        self.assertEqual(rules.verification_hash(LEGACY), hashlib.sha1(body.encode()).hexdigest()[:12])

    def test_tier_and_perf_line_change_hash(self):
        h1 = rules.verification_hash(TIERED)
        self.assertNotEqual(h1, rules.verification_hash(LEGACY))
        self.assertNotEqual(h1, rules.verification_hash(TIERED.replace('## Verification\n', '## Verification\nPerf: required\n')))

    def test_row_tier_default_and_values(self):
        rows = rules.parse_verification(TIERED)
        self.assertEqual([rules.row_tier(r) for r in rows], ['functional', 'perf'])
        self.assertEqual(rules.row_tier(rules.parse_verification(LEGACY)[0]), 'functional')

    def test_invalid_tier_and_perf_required_without_row(self):
        bad = TIERED.replace('| perf |', '| load |')
        msgs = ' '.join(v['message'] for v in rules.check_verification(bad))
        self.assertIn('is not `functional` or `perf`', msgs)
        req = LEGACY.replace('## Verification\n', '## Verification\nPerf: required\n')
        msgs = ' '.join(v['message'] for v in rules.check_verification(req))
        self.assertIn('no Verification row has `Tier: perf`', msgs)


class TierVerify(unittest.TestCase):
    def _run(self, spec_text, **kw):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = root / 'specs' / 's'
            spec.mkdir(parents=True)
            for f in ('a.py', 'b.py'):
                (root / f).write_text('print(1)', encoding='utf-8')
            (spec / 'spec.md').write_text(spec_text, encoding='utf-8')
            (spec / 'tasks.md').write_text('', encoding='utf-8')
            calls, events = [], []

            def run(cmd, _root, output, _timeout):
                calls.append(cmd)
                output.write_text('ran 3 tests ok, all assertions passed\n', encoding='utf-8')
                return 0, ''

            def append(_root, _s, kind, **detail):
                events.append((kind, detail))
                return True
            with patch.object(status.ev, 'find_root', return_value=root), \
                 patch.object(status, '_resolve_spec', return_value=spec), \
                 patch.object(status, '_current_session', return_value='s'), \
                 patch.object(status.ev, 'code_state', return_value=('git', {})), \
                 patch.object(status.ev, 'state_diff', return_value=[]), \
                 patch.object(status.ev, 'fingerprint_of', return_value='fp'), \
                 patch.object(status.ev, 'worktree_fingerprint', return_value='fp'), \
                 patch.object(status.ev, 'latest_verify_run', return_value=None), \
                 patch.object(status.ev, 'append', side_effect=append), \
                 patch.object(status.ev, 'append_verify_run', return_value=True) as full_event, \
                 patch.object(status, '_run_row', side_effect=run), \
                 contextlib.redirect_stdout(io.StringIO()) as out:
                rc = status.cmd_verify(str(spec), **kw)
            return rc, calls, events, full_event, out.getvalue()

    def test_default_skips_perf_rows(self):
        rc, calls, events, full_event, out = self._run(TIERED)
        self.assertEqual(rc, 0, out)
        self.assertEqual(calls, ['python a.py'])
        self.assertIn('PERF row V-2: not run', out)
        full_event.assert_called_once()

    def test_perf_runs_only_perf_rows_and_own_event(self):
        rc, calls, events, full_event, out = self._run(TIERED, perf=True)
        self.assertEqual(rc, 0, out)
        self.assertEqual(calls, ['python b.py'])
        full_event.assert_not_called()
        self.assertEqual([k for k, _ in events], ['perf_verify_run'])
        self.assertTrue(events[0][1]['results'][0]['evidence'].startswith('evidence/verify-perf-'))

    def test_perf_refusals(self):
        rc, calls, *_ = self._run(LEGACY, perf=True)
        self.assertEqual((rc, calls), (1, []))
        rc, calls, *_ = self._run(TIERED, perf=True, task_ids=['T-01'])
        self.assertEqual((rc, calls), (1, []))
        only_perf = TIERED.replace('| functional |', '| perf |')
        rc, calls, *_ = self._run(only_perf)
        self.assertEqual((rc, calls), (1, []))

    def test_cli_perf_refuses_other_options(self):
        with patch.object(status, 'cmd_verify') as verify, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(status.main(['verify', 's', '--perf', '--full']), 1)
            self.assertEqual(status.main(['verify', 's', 't', '--perf']), 1)
            verify.assert_not_called()
            status.main(['verify', 's', '--perf'])
            verify.assert_called_once_with('s', perf=True)


class PerfCloseGap(unittest.TestCase):
    REQ = TIERED.replace('## Verification\n', '## Verification\nPerf: required\n')

    def _ev(self, runs, last_edit=0.0):
        class Ev:
            def events(self, _root, kind=None):
                return runs if kind == 'perf_verify_run' else []

            def last_code_edit_ts(self, _root, *_a):
                return last_edit
        return Ev()

    def _spec(self, tmp, text):
        d = Path(tmp) / 'specs' / 's'
        (d / 'evidence').mkdir(parents=True)
        (d / 'spec.md').write_text(text, encoding='utf-8')
        (d / 'evidence' / 'verify-perf-V-2.txt').write_bytes(b'ok')
        return d

    def _run(self, text, ok=True, vh=None, sha=None):
        return {'ts': 10.0, 'detail': {'spec': 's', 'ok': ok, 'stable': True, 'started': 5.0,
                                       'verify_hash': vh if vh is not None else rules.verification_hash(text),
                                       'results': [{'evidence': 'evidence/verify-perf-V-2.txt',
                                                    'sha1': sha or hashlib.sha1(b'ok').hexdigest()}]}}

    def test_not_required_never_a_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self._spec(tmp, TIERED)
            self.assertEqual(rules.perf_gaps(self._ev([]), tmp, d, TIERED), [])

    def test_required_missing_stale_failed_and_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self._spec(tmp, self.REQ)
            self.assertEqual(len(rules.perf_gaps(self._ev([]), tmp, d, self.REQ)), 1)
            self.assertEqual(len(rules.perf_gaps(self._ev([self._run(self.REQ, ok=False)]), tmp, d, self.REQ)), 1)
            self.assertEqual(len(rules.perf_gaps(self._ev([self._run(self.REQ, vh='x')]), tmp, d, self.REQ)), 1)
            self.assertEqual(len(rules.perf_gaps(self._ev([self._run(self.REQ, sha='0' * 40)]), tmp, d, self.REQ)), 1)
            self.assertEqual(len(rules.perf_gaps(self._ev([self._run(self.REQ)], last_edit=9.0), tmp, d, self.REQ)), 1)
            self.assertEqual(rules.perf_gaps(self._ev([self._run(self.REQ)], last_edit=1.0), tmp, d, self.REQ), [])


if __name__ == '__main__':
    unittest.main()
