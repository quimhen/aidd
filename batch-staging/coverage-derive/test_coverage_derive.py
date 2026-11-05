"""Unit tests for the coverage_derive.py prototype (synthetic spec in a temp dir; no DB, Docker or network)."""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import coverage_derive as cd  # noqa: E402

SPEC = """# Spec 001

## Verification

| # | Command | Expected | Covers | Inputs |
|---|---|---|---|---|
| V-1 | `python -m unittest tests.test_a -v` | exit 0 | T-01 | |
| V-2 | `python -m unittest tests.test_b -v` | exit 0 | FR-002 to FR-003 | |
| V-3 | `python -m unittest discover -s tests -v` | exit 0 | full regression | |
| V-4 | `python -m unittest tests.test_x -v` | exit 0 | FR-099 | |
| V-5 | `python eDoc/tools/db_verify.py --tap --only-tests a_` | exit 0 | AC-010 | |
| V-6 | `python -m unittest tests.test_c -v` | exit 0 | FR-004 | extra/keep.py |
"""

TASKS = """# Tasks

| Task | Codes satisfied | Target file | Status |
|---|---|---|---|
| T-01 | FR-001 | `src/a.py` | |
| T-02 | FR-002 | `src/b.py` | |
| T-03 | FR-003, AC-010 | `src/c.sql` | |
| T-04 | FR-004 | `src/d.py` | |

### T-04 — detail
- Cites: AC-010
"""


class CoverageDerive(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / '.aidd').mkdir()
        self.spec = self.root / 'specs' / '001-x'
        self.spec.mkdir(parents=True)
        (self.spec / 'spec.md').write_text(SPEC, encoding='utf-8')
        (self.spec / 'tasks.md').write_text(TASKS, encoding='utf-8')
        for rel in ('src/a.py', 'src/b.py', 'src/c.sql', 'src/d.py', 'extra/keep.py'):
            f = self.root / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text('x = 1\n', encoding='utf-8')
        self.res = cd.derive(self.spec)
        self.rows = {r['n']: r for r in self.res['rows']}

    def tearDown(self):
        self.tmp.cleanup()

    def test_cites_tasks_kept(self):
        r = self.rows['V-1']
        self.assertEqual(r['kind'], 'cites-tasks')
        self.assertEqual(r['tasks'], ['T-01'])
        self.assertEqual(r['inputs'], ['src/a.py'])
        self.assertFalse(r['unconfirmed'])

    def test_range_derived_via_codes(self):
        r = self.rows['V-2']
        self.assertEqual(r['kind'], 'via-fr-ac-api')
        self.assertEqual(r['tasks'], ['T-02', 'T-03'])
        self.assertEqual(r['inputs'], ['src/b.py', 'src/c.sql'])
        self.assertTrue(r['covers'].startswith('FR-002 to FR-003'))   # existing text never dropped

    def test_whole_suite_gets_everything_and_is_unconfirmed(self):
        r = self.rows['V-3']
        self.assertEqual(r['kind'], 'whole-suite')
        self.assertEqual(r['tasks'], ['T-01', 'T-02', 'T-03', 'T-04'])
        self.assertEqual(r['inputs'], ['src/a.py', 'src/b.py', 'src/c.sql', 'src/d.py'])
        self.assertTrue(r['unconfirmed'])

    def test_unresolved_gets_no_inputs(self):
        r = self.rows['V-4']
        self.assertEqual(r['kind'], 'unresolved')
        self.assertEqual(r['tasks'], [])
        self.assertEqual(r['inputs'], [])
        self.assertEqual(r['covers'], 'FR-099')

    def test_database_row_never_reused_and_cites_line_counts(self):
        r = self.rows['V-5']
        self.assertTrue(r['database'])
        self.assertTrue(r['reuse'].startswith('none'))
        self.assertEqual(r['tasks'], ['T-03', 'T-04'])     # T-04 only through its "- Cites:" line

    def test_existing_inputs_never_shrink(self):
        r = self.rows['V-6']
        self.assertIn('extra/keep.py', r['inputs'])
        self.assertIn('src/d.py', r['inputs'])

    def test_summary_counts(self):
        s = self.res['summary']
        self.assertEqual((s['rows'], s['cites-tasks'], s['via-fr-ac-api'], s['whole-suite'], s['unresolved']),
                         (6, 1, 3, 1, 1))
        self.assertEqual(self.res['uncovered_tasks'], [])

    def test_missing_target_marks_unconfirmed(self):
        (self.root / 'src/b.py').unlink()
        r = {x['n']: x for x in cd.derive(self.spec)['rows']}['V-2']
        self.assertTrue(r['unconfirmed'])
        self.assertTrue(any('match no file' in n for n in r['notes']))

    def test_changed_simulation_refuses_with_unresolved_row(self):
        sim = cd.simulate_changed(self.res, ['src/a.py'])
        self.assertEqual(sim['status'], 'refused')
        self.assertEqual(sim['rows_skipped'], 0)

    def test_changed_simulation_skips_unrelated_rows(self):
        self.res['rows'] = [r for r in self.res['rows'] if r['kind'] != 'unresolved']
        sim = cd.simulate_changed(self.res, ['src/a.py'])
        self.assertEqual(sim['status'], 'ok')
        self.assertEqual(sim['selected_tasks'], ['T-01', 'T-02', 'T-03', 'T-04'])   # whole-suite row pulls all
        self.res['rows'] = [r for r in self.res['rows'] if r['kind'] != 'whole-suite']
        sim = cd.simulate_changed(self.res, ['src/a.py'])
        self.assertEqual((sim['selected_tasks'], sim['rows_run'], sim['rows_skipped']), (['T-01'], 1, 3))

    def test_changed_simulation_refuses_on_spec_change(self):
        sim = cd.simulate_changed(self.res, ['specs/001-x/tasks.md'])
        self.assertEqual(sim['reason'], 'spec policy changed')

    def test_dry_run_writes_nothing(self):
        before = (self.spec / 'spec.md').read_bytes()
        files_before = sorted(p for p in self.root.rglob('*'))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            rc = cd.main([str(self.spec)])
        self.assertEqual(rc, 0)
        self.assertIn('DRY-RUN', out.getvalue())
        self.assertEqual((self.spec / 'spec.md').read_bytes(), before)
        self.assertEqual(sorted(p for p in self.root.rglob('*') if '__pycache__' not in p.parts),
                         [p for p in files_before if '__pycache__' not in p.parts])

    def test_apply_to_refuses_spec_and_foreign_file(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cd.main([str(self.spec), '--apply-to', str(self.spec / 'spec.md')]), 2)
            foreign = self.root / 'notes.txt'
            foreign.write_text('mine', encoding='utf-8')
            self.assertEqual(cd.main([str(self.spec), '--apply-to', str(foreign)]), 2)
            self.assertEqual(foreign.read_text(encoding='utf-8'), 'mine')
            target = self.root / 'proposal.md'
            self.assertEqual(cd.main([str(self.spec), '--apply-to', str(target)]), 0)
            self.assertEqual(cd.main([str(self.spec), '--apply-to', str(target)]), 0)   # rewrite own proposal
        self.assertTrue(target.read_text(encoding='utf-8').startswith(cd.PROPOSAL_MARK))
        self.assertEqual((self.spec / 'spec.md').read_text(encoding='utf-8'), SPEC)

    def test_json_output(self):
        import json
        with contextlib.redirect_stdout(io.StringIO()) as out:
            cd.main([str(self.spec), '--json'])
        data = json.loads(out.getvalue())
        self.assertEqual(data['summary']['rows'], 6)


if __name__ == '__main__':
    unittest.main()
