"""Amendment 10 item P of spec 007: same-spec reuse inside `aidd verify --round` (aidd:FR-427..FR-432,
AC-485..AC-495). Cheap real commands (python scripts in a temp project); the evidence log is an in-memory store
that `latest_verify_run` reads back, so a second round sees the first one's `verify_run`. stdlib unittest."""
import contextlib
import io
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skill' / 'scripts'))
import aidd_round as rnd  # noqa: E402
import aidd_status as status  # noqa: E402
from test_verify_round import PY, RoundBase  # noqa: E402

REUSED_RE = (r'^REUSED: PASS del verify_run de A fila V-1 del \d{4}-\d\d-\d\dT[\d:]+, huella c2:[0-9a-f]{16}, '
             r'verify hash [0-9a-f]{12}; ')


class ReuseBase(RoundBase):
    def setUp(self):
        super().setUp()
        (self.root / 'ident.py').write_text("print(open('ident.txt').read())\n", encoding='utf-8')
        (self.root / 'ident.txt').write_text('template-1\n', encoding='utf-8')
        (self.root / 'lib').mkdir()
        (self.root / 'lib' / 'b.py').write_text('y = 1\n', encoding='utf-8')
        self.store = {}

    def _patches(self, open_specs=(), latest=None):
        stack = super()._patches(open_specs=open_specs, latest=latest)

        def append_verify_run(_root, _s, spec, ok, vhash, results, started, fp_start, fp_end, stable, **kw):
            self.events.append({'spec': spec, 'ok': ok, 'results': results, 'stable': stable})
            self.store[spec] = dict({k: v for k, v in kw.items() if v is not None}, ts=time.time(), ok=bool(ok),
                                    verify_hash=vhash, started=started, stable=bool(stable), results=results)
            return True
        stack.enter_context(patch.object(status.ev, 'append_verify_run', side_effect=append_verify_run))
        stack.enter_context(patch.object(status.ev, 'latest_verify_run', side_effect=lambda r, s: self.store.get(s)))
        return stack

    def round(self, *names, extra=()):
        self.runs.clear()
        self.events.clear()
        return self.main('verify', '--round', *names, *extra)

    def evidence(self, spec, n='V-1'):
        return (self.root / 'specs' / spec / 'evidence' / f'verify-{n}.txt').read_text(encoding='utf-8').splitlines()

    def result(self, spec, n):
        ev = next(e for e in self.events if e['spec'] == spec)
        return next(r for r in ev['results'] if r['n'] == n)


class SameSpecReuse(ReuseBase):
    def test_reuses_only_when_nothing_changed(self):                                   # AC-485, AC-490
        self.spec('A', [('V-1', f'{PY} ok.py', 'exit 0', ''), ('V-2', f'{PY} other.py', 'exit 0', '')])
        rc, out = self.round('A')
        self.assertEqual((rc, len(self.runs)), (0, 2), out)
        rc, out = self.round('A')
        self.assertEqual((rc, self.runs), (0, []), out)
        self.assertIn('REUSED row V-1', out)
        self.assertIn('2 row(s) REUSED', out)
        ev = self.events[0]
        self.assertTrue(ev['ok'] and ev['stable'], out)
        self.assertEqual(len(ev['results']), 2)                                         # complete verify_run
        r1 = self.result('A', 'V-1')
        self.assertTrue(r1['reused'] and r1['ok'])
        self.assertEqual(r1['reuse_kind'], 'round-same-spec')
        self.assertNotIn('round_shared', r1)
        lines = self.evidence('A')
        self.assertIn('| exit 0 |', lines[0])
        self.assertRegex(lines[1], REUSED_RE)
        self.assertIn('all assertions passed', '\n'.join(lines[2:]))
        first_date = r1['reused_from']['date']
        rc, out = self.round('A')                                                       # a chain keeps the origin
        self.assertEqual((rc, self.runs), (0, []), out)
        self.assertEqual(self.result('A', 'V-1')['reused_from']['date'], first_date)
        self.assertEqual(sum(1 for x in self.evidence('A') if x.startswith('REUSED:')), 1)

    def test_scope_file_changed_runs_again(self):                                       # AC-486
        self.spec('A', [('V-1', f'{PY} ok.py', 'exit 0', '')])
        self.round('A')
        (self.root / 'src' / 'a.py').write_text('x = 2\n', encoding='utf-8')
        rc, out = self.round('A')
        self.assertEqual((rc, len(self.runs)), (0, 1), out)
        self.assertIn('code in Scope changed since the previous verify_run', out)
        self.assertFalse(self.result('A', 'V-1').get('reused'))

    def test_previous_fail_is_not_reused_and_mixes_with_reused_rows(self):              # AC-487, AC-494
        self.spec('A', [('V-1', f'{PY} ok.py', 'exit 0', ''), ('V-2', f'{PY} fail.py', 'exit 0', '')])
        rc, _ = self.round('A')
        self.assertEqual(rc, 1)
        rc, out = self.round('A')
        self.assertEqual(rc, 1, out)
        self.assertEqual(len(self.runs), 1, out)
        self.assertIn('fail.py', self.runs[0])
        self.assertIn('previous result was not a PASS', out)
        self.assertTrue(self.result('A', 'V-1')['reused'])
        self.assertFalse(self.result('A', 'V-2')['ok'])

    def test_new_row_runs_and_old_row_is_reused(self):                                  # AC-488, AC-494
        d = self.spec('A', [('V-1', f'{PY} ok.py', 'exit 0', '')])
        self.round('A')
        text = (d / 'spec.md').read_text(encoding='utf-8')
        (d / 'spec.md').write_text(text + f'| V-2 | {PY} other.py | exit 0 | FR-1 |  |\n', encoding='utf-8')
        rc, out = self.round('A')
        self.assertEqual((rc, len(self.runs)), (0, 1), out)
        self.assertIn('other.py', self.runs[0])
        self.assertIn('new row (not in the previous verify_run)', out)
        self.assertTrue(self.result('A', 'V-1')['reused'])
        self.assertFalse(self.result('A', 'V-2').get('reused'))
        self.assertTrue(self.events[0]['ok'])

    def test_changed_command_runs(self):
        d = self.spec('A', [('V-1', f'{PY} ok.py', 'exit 0', '')])
        self.round('A')
        text = (d / 'spec.md').read_text(encoding='utf-8')
        (d / 'spec.md').write_text(text.replace('ok.py', 'other.py'), encoding='utf-8')
        rc, out = self.round('A')
        self.assertEqual((rc, len(self.runs)), (0, 1), out)
        self.assertIn('command changed', out)

    def test_full_runs_everything(self):                                                 # AC-489
        self.spec('A', [('V-1', f'{PY} ok.py', 'exit 0', ''), ('V-2', f'{PY} other.py', 'exit 0', '')])
        self.round('A')
        rc, out = self.round('A', extra=('--full',))
        self.assertEqual((rc, len(self.runs)), (0, 2), out)
        self.assertIn('--full: every row runs', out)
        self.assertFalse(any(r.get('reused') for r in self.events[0]['results']))

    def test_dry_run_reports_reuse_and_executes_nothing(self):                           # AC-491
        self.spec('A', [('V-1', f'{PY} ok.py', 'exit 0', ''), ('V-2', f'{PY} other.py', 'exit 0', '')])
        self.round('A')
        before = self.evidence('A')
        rc, out = self.round('A', extra=('--dry-run',))
        self.assertEqual((rc, self.runs, self.events), (0, [], []), out)
        self.assertIn('reuse A: 2 row(s) reused, 0 to execute', out)
        self.assertIn('REUSED V-1: PASS of', out)
        self.assertIn('estimated savings versus running every row', out)
        self.assertIn('dry run: nothing was executed', out)
        self.assertEqual(self.evidence('A'), before)                                    # nothing rewritten

    def test_unavailable_fingerprint_fails_closed(self):                                 # AC-492
        self.spec('A', [('V-1', f'{PY} ok.py', 'exit 0', '')])
        self.round('A')
        with patch.object(rnd, '_code_fp_now', return_value=None):
            rc, out = self.round('A')
        self.assertEqual((rc, len(self.runs)), (0, 1), out)
        self.assertIn('code fingerprint cannot be computed now (fail closed)', out)

    def test_environment_identity_changed_or_unavailable(self):                          # AC-493
        self.spec('A', [('V-1', f'{PY} ok.py', 'exit 0', '')], extra=f'Round-identity: {PY} ident.py\n')
        self.round('A')
        self.assertRegex(self.store['A']['results'][0].get('env_id') or '', r'^[0-9a-f]{16}$')
        rc, out = self.round('A')
        self.assertEqual((rc, self.runs), (0, []), out)                                  # same identity: reused
        (self.root / 'ident.txt').write_text('template-2\n', encoding='utf-8')
        rc, out = self.round('A')
        self.assertEqual((rc, len(self.runs)), (0, 1), out)
        self.assertIn('environment identity changed', out)
        (self.root / 'ident.txt').unlink()
        rc, out = self.round('A')
        self.assertEqual(len(self.runs), 1, out)
        self.assertIn('environment identity unavailable (fail closed)', out)

    def test_reuse_never_row_always_runs(self):
        d = self.root / 'specs' / 'A'
        d.mkdir(parents=True)
        (d / 'spec.md').write_text('# A\n\n## Verification\nScope: src/**\n| # | Command | Expected | Covers | Reuse |\n'
                                   f'|---|---|---|---|---|\n| V-1 | {PY} ok.py | exit 0 | FR-1 | never |\n'
                                   f'| V-2 | {PY} other.py | exit 0 | FR-1 |  |\n', encoding='utf-8')
        (d / 'tasks.md').write_text('', encoding='utf-8')
        self.round('A')
        rc, out = self.round('A')
        self.assertEqual((rc, len(self.runs)), (0, 1), out)
        self.assertIn('ok.py', self.runs[0])
        self.assertIn('`Reuse: never`', out)

    def test_reused_row_is_never_a_shared_execution(self):                               # AC-490
        self.spec('A', [('V-1', f'{PY} ok.py', 'exit 0', '')], scope='src/**')
        self.spec('B', [('V-1', f'{PY} ok.py', 'exit 0', '')], scope='lib/**')
        rc, _ = self.round('A', 'B')
        self.assertEqual((rc, len(self.runs)), (0, 1))
        (self.root / 'lib' / 'b.py').write_text('y = 2\n', encoding='utf-8')
        rc, out = self.round('A', 'B')
        self.assertEqual((rc, len(self.runs)), (0, 1), out)                              # B runs, A reused
        a, b = self.result('A', 'V-1'), self.result('B', 'V-1')
        self.assertTrue(a['reused'])
        self.assertNotIn('round_shared', a)
        self.assertFalse(b.get('reused'))
        self.assertEqual(b['round_shared']['fingerprint'], 'not-shared')                 # a group of one, B alone
        self.assertEqual(b['round_shared']['source_spec'], 'B')

    def test_plain_verify_run_feeds_the_round(self):                                     # AC-495
        self.spec('A', [('V-1', f'{PY} ok.py', 'exit 0', '')], extra=f'Round-identity: {PY} ident.py\n')
        with self._patches(), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(status.cmd_verify('A'), 0)
        self.assertRegex(self.store['A']['results'][0].get('env_id') or '', r'^[0-9a-f]{16}$')
        rc, out = self.round('A')
        self.assertEqual((rc, self.runs), (0, []), out)

    def test_changed_evidence_is_not_reused(self):
        self.spec('A', [('V-1', f'{PY} ok.py', 'exit 0', '')])
        self.round('A')
        p = self.root / 'specs' / 'A' / 'evidence' / 'verify-V-1.txt'
        p.write_text(p.read_text(encoding='utf-8') + 'tampered\n', encoding='utf-8')
        rc, out = self.round('A')
        self.assertEqual((rc, len(self.runs)), (0, 1), out)
        self.assertIn('previous evidence file missing or changed', out)


if __name__ == '__main__':
    unittest.main()
