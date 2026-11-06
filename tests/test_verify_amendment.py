"""Amendment 11 of spec 007: `aidd verify <spec> --amendment NN` (aidd:FR-450..FR-459, AC-520..AC-532).

Cheap real commands (python scripts in a temp project); the evidence log is the in-memory store of
`test_verify_round_reuse.ReuseBase`, so a second run sees the first one's `verify_run`. stdlib unittest."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skill' / 'scripts'))
import aidd_rules as rules  # noqa: E402
import aidd_status as status  # noqa: E402
from test_verify_round import PY  # noqa: E402
from test_verify_round_reuse import ReuseBase  # noqa: E402

REUSED_LINE = r'^REUSED: PASS del verify_run de A fila V-2 del \d{4}-\d\d-\d\dT[\d:]+, huella c2:[0-9a-f]{16}, '


def table(rows, extra=''):
    head = ('## Verification\n' + extra
            + '| # | Command | Expected | Covers | Inputs | Regression |\n|---|---|---|---|---|---|\n')
    return head + ''.join(f'| {n} | {c} | {e} | FR-1 | {i} | {g} |\n' for n, c, e, i, g in rows)


TASKS_01 = ('# Tasks amendment 01\n\n### T-01 change the lib\n'
            '- **Files to change:** `lib/b.py` (edit). Nothing else.\n')


class AmendBase(ReuseBase):
    def setUp(self):
        super().setUp()
        (self.root / 'tests').mkdir()
        (self.root / 'tests' / 't1.py').write_text('t = 1\n', encoding='utf-8')

    def aspec(self, rows, scope='src/**, lib/**', extra='', amendment=TASKS_01):
        d = self.root / 'specs' / 'A'
        d.mkdir(parents=True, exist_ok=True)
        (d / 'spec.md').write_text('# A\n\n' + table(rows, f'Scope: {scope}\n' + extra), encoding='utf-8')
        (d / 'tasks.md').write_text('', encoding='utf-8')
        if amendment is not None:
            (d / 'tasks-amendment-01.md').write_text(amendment, encoding='utf-8')
        return d

    def verify(self, *argv):
        self.runs.clear()
        self.events.clear()
        return self.main('verify', *argv)

    def three_rows(self, **kw):
        return self.aspec([('V-1', f'{PY} ok.py', 'exit 0', 'lib/b.py', ''),
                           ('V-2', f'{PY} other.py', 'exit 0', 'src/a.py', ''),
                           ('V-3', f'{PY} ok.py --x', 'exit 0', '', '')], **kw)


class AmendmentScope(AmendBase):
    def test_only_rows_touched_by_the_amendment_run(self):                              # AC-520
        self.three_rows()
        rc, out = self.verify('A')
        self.assertEqual((rc, len(self.runs)), (0, 3), out)
        (self.root / 'lib' / 'b.py').write_text('y = 2\n', encoding='utf-8')
        rc, out = self.verify('A', '--amendment', '01')
        self.assertEqual(rc, 0, out)
        ran = ' '.join(self.runs)
        self.assertEqual(len(self.runs), 2, out)                                         # V-1 and V-3
        self.assertNotIn('other.py', ran, out)
        self.assertIn('REUSED row V-2', out)
        ev = self.events[0]
        self.assertTrue(ev['ok'] and ev['stable'], out)
        self.assertEqual(len(ev['results']), 3)                                          # complete verify_run
        r2 = self.result('A', 'V-2')
        self.assertTrue(r2['reused'] and r2['ok'])
        self.assertEqual(r2['reuse_kind'], 'amendment-inputs')
        self.assertEqual(r2['input_globs'], ['src/a.py'])
        self.assertRegex(self.evidence('A', 'V-2')[1], REUSED_LINE)
        self.assertIn('aidd verify --amendment 01', self.evidence('A', 'V-2')[1])
        self.assertEqual(self.store['A'].get('amendment'), '01')
        self.assertEqual(self.store['A'].get('amendment_files'), ['lib/b.py'])
        self.assertIn('amendment 01: 2 row(s) executed, 1 REUSED', out)

    def test_nothing_changed_reuses_everything(self):                                   # AC-521
        self.three_rows(amendment='### T-01\n- **Files to change:** `docs/x.md`.\n')
        self.verify('A')
        rc, out = self.verify('A', '--amendment', '1')
        self.assertEqual((rc, self.runs), (0, []), out)
        self.assertEqual(self.result('A', 'V-3')['reuse_kind'], 'amendment-scope')

    def test_regression_always_runs(self):                                               # AC-522
        self.aspec([('V-1', f'{PY} ok.py', 'exit 0', 'src/a.py', 'always'),
                    ('V-2', f'{PY} other.py', 'exit 0', 'src/a.py', '')])
        self.verify('A')
        rc, out = self.verify('A', '--amendment', '01')
        self.assertEqual((rc, len(self.runs)), (0, 1), out)
        self.assertIn('ok.py', self.runs[0])
        self.assertIn('Regression: always', out)

    def test_undeclared_input_change_runs_with_warning(self):                           # AC-523
        self.three_rows()
        self.verify('A')
        (self.root / 'src' / 'a.py').write_text('x = 3\n', encoding='utf-8')
        rc, out = self.verify('A', '--amendment', '01')
        self.assertEqual(rc, 0, out)
        self.assertTrue(any('other.py' in c for c in self.runs), out)
        self.assertIn('warning: row V-2: its Inputs changed since its last PASS but amendment 01 declares none', out)

    def test_command_naming_a_declared_file_runs(self):
        self.aspec([('V-1', f'{PY} ok.py lib/b.py', 'exit 0', 'src/a.py', '')])
        self.verify('A')
        rc, out = self.verify('A', '--amendment', '01')
        self.assertEqual((rc, len(self.runs)), (0, 1), out)


class DryRun(AmendBase):
    def test_amendment_dry_run_executes_nothing(self):                                  # AC-524
        self.three_rows()
        self.verify('A')
        before = self.evidence('A', 'V-2')
        (self.root / 'lib' / 'b.py').write_text('y = 2\n', encoding='utf-8')
        rc, out = self.verify('A', '--amendment', '01', '--dry-run')
        self.assertEqual((rc, self.runs, self.events), (0, [], []), out)
        self.assertEqual(self.evidence('A', 'V-2'), before)
        self.assertIn('RUN    V-1: Inputs match amendment file lib/b.py', out)
        self.assertIn('REUSED V-2:', out)
        self.assertIn('RUN    V-3:', out)
        self.assertIn('nothing was executed and nothing was recorded', out)

    def test_plain_dry_run_does_not_execute(self):                                       # AC-525 (the bug)
        self.three_rows()
        rc, out = self.verify('A', '--dry-run')
        self.assertEqual((rc, self.runs, self.events), (0, [], []), out)
        self.assertIn('RUN    V-1', out)
        self.assertIn('nothing was executed and nothing was recorded', out)


class Refusals(AmendBase):
    def test_unknown_option_and_bad_combinations(self):                                 # AC-526
        self.three_rows()
        for argv in (('A', '--bogus'), ('A', '--amendment', '01', '--full'),
                     ('A', '--amendment', '01', '--tasks', 'T-01'), ('A', 'A', '--dry-run'),
                     ('A', '--amendment'), ('A', '--amendment', 'x1'), ('A', '--dry-run', '--json')):
            rc, out = self.verify(*argv)
            self.assertEqual((rc, self.runs, self.events), (1, [], []), (argv, out))
            self.assertIn('Refused', out, argv)

    def test_missing_or_empty_amendment_file(self):                                     # AC-527
        self.three_rows(amendment=None)
        rc, out = self.verify('A', '--amendment', '01')
        self.assertEqual((rc, self.runs), (1, []), out)
        self.assertIn('tasks-amendment-01.md', out)
        (self.root / 'specs' / 'A' / 'tasks-amendment-01.md').write_text('# nothing\n', encoding='utf-8')
        rc, out = self.verify('A', '--amendment', '01')
        self.assertEqual((rc, self.runs), (1, []), out)
        self.assertIn('declares no file', out)

    def test_machine_block_is_read(self):
        self.three_rows(amendment='# T\n```aidd-files\nlib/b.py\n```\n')
        self.verify('A')
        rc, out = self.verify('A', '--amendment', '01', '--dry-run')
        self.assertEqual(rc, 0, out)
        self.assertIn('RUN    V-1: Inputs match amendment file lib/b.py', out)

    def test_fingerprint_budget_refusal(self):                                          # AC-530
        self.three_rows()
        self.verify('A')
        with patch.object(status.ev, 'code_state', return_value=None):
            rc, out = self.verify('A', '--amendment', '01')
            self.assertEqual((rc, self.runs), (1, []), out)
            self.assertIn('AIDD_FINGERPRINT_BUDGET', out)
            rc, out = self.verify('A', '--amendment', '01', '--dry-run')
            self.assertEqual((rc, self.runs), (0, []), out)
            self.assertIn('AIDD_FINGERPRINT_BUDGET', out)


class Environment(AmendBase):
    def test_unprovable_env_runs_with_reason(self):                                     # AC-529
        self.aspec([('V-1', f'{PY} ok.py', 'exit 0', 'src/a.py', '')],
                   extra=f'Round-identity: {PY} ident.py\n')
        self.verify('A')
        for r in self.store['A']['results']:
            r.pop('env_id', None)
        rc, out = self.verify('A', '--amendment', '01')
        self.assertEqual((rc, len(self.runs)), (0, 1), out)
        self.assertIn('cannot prove reuse', out)
        self.assertIn('no env_id', out)
        rc, out = self.verify('A', '--amendment', '01')                                 # env_id now recorded
        self.assertEqual((rc, self.runs), (0, []), out)
        (self.root / 'ident.txt').write_text('template-2\n', encoding='utf-8')
        rc, out = self.verify('A', '--amendment', '01')
        self.assertEqual((rc, len(self.runs)), (0, 1), out)
        self.assertIn('environment identity changed', out)


class CloseGate(AmendBase):
    def problems(self, d):
        run = self.store['A']
        with patch.object(status.ev, 'last_code_edit_ts', return_value=0):
            return [v['message'] for _s, v in
                    rules._run_problems(status.ev, self.root, d, (d / 'spec.md').read_text(encoding='utf-8'), run)]

    def test_gate_accepts_then_stales_on_reused_inputs(self):                           # AC-528
        d = self.three_rows()
        self.verify('A')
        (self.root / 'lib' / 'b.py').write_text('y = 2\n', encoding='utf-8')
        rc, out = self.verify('A', '--amendment', '01')
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.problems(d), [])
        (self.root / 'src' / 'a.py').write_text('x = 9\n', encoding='utf-8')
        self.assertTrue(any('inputs changed' in m for m in self.problems(d)), self.problems(d))

    def test_forged_reused_result_is_stale(self):                                        # AC-532
        d = self.three_rows()
        self.verify('A')
        (self.root / 'lib' / 'b.py').write_text('y = 2\n', encoding='utf-8')
        self.verify('A', '--amendment', '01')
        r2 = next(r for r in self.store['A']['results'] if r['n'] == 'V-2')
        r2.pop('input_globs')
        self.assertTrue(any('reused' in m.lower() for m in self.problems(d)), self.problems(d))


class RegressionColumn(unittest.TestCase):                                               # AC-531
    def test_lint_and_hash(self):
        base = '## Verification\n| # | Command | Expected | Covers |\n|---|---|---|---|\n| V-1 | python -m unittest | exit 0 | FR-1 |\n'
        with_col = ('## Verification\n| # | Command | Expected | Covers | Regression |\n|---|---|---|---|---|\n'
                    '| V-1 | python -m unittest | exit 0 | FR-1 | always |\n')
        self.assertEqual(rules.verification_hash(base), rules.verification_hash(with_col))
        self.assertEqual(rules.parse_verification(with_col)[0].get('regression'), 'always')
        self.assertFalse([v for v in rules.check_verification(with_col) if 'Regression' in v['message']])
        bad = with_col.replace('| always |', '| sometimes |')
        self.assertTrue([v for v in rules.check_verification(bad) if 'Regression' in v['message']])


if __name__ == '__main__':
    unittest.main()
