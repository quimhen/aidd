"""aidd coverage (spec 007 amendment 05, AC-271..AC-284): synthetic spec in a temp dir; no DB, Docker, Git or network."""
import contextlib
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'skill' / 'scripts'))

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


def _files(root):
    return sorted(str(p) for p in Path(root).rglob('*') if '__pycache__' not in p.parts)


class AiddCoverage(unittest.TestCase):
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

    def tearDown(self):
        self.tmp.cleanup()

    def _derive(self, spec=None):
        import aidd_coverage as cov
        res = cov.derive(spec or self.spec)
        return res, {r['n']: r for r in res['rows']}

    def test_cites_tasks_kept(self):
        _, rows = self._derive()
        r = rows['V-1']
        self.assertEqual(r['kind'], 'cites-tasks')
        self.assertEqual(r['tasks'], ['T-01'])
        self.assertEqual(r['inputs'], ['src/a.py'])
        self.assertFalse(r['needs_review'])

    def test_range_derived_via_codes(self):
        _, rows = self._derive()
        r = rows['V-2']
        self.assertEqual(r['kind'], 'via-fr-ac-api')
        self.assertEqual(r['tasks'], ['T-02', 'T-03'])
        self.assertEqual(r['inputs'], ['src/b.py', 'src/c.sql'])
        self.assertTrue(r['covers'].startswith('FR-002 to FR-003'))

    def test_whole_suite_gets_everything_and_needs_review(self):
        _, rows = self._derive()
        r = rows['V-3']
        self.assertEqual(r['kind'], 'whole-suite')
        self.assertEqual(r['tasks'], ['T-01', 'T-02', 'T-03', 'T-04'])
        self.assertEqual(r['inputs'], ['src/a.py', 'src/b.py', 'src/c.sql', 'src/d.py'])
        self.assertTrue(r['needs_review'])

    def test_unresolved_gets_no_inputs(self):
        _, rows = self._derive()
        r = rows['V-4']
        self.assertEqual(r['kind'], 'unresolved')
        self.assertEqual(r['tasks'], [])
        self.assertEqual(r['inputs'], [])
        self.assertEqual(r['covers'], 'FR-099')

    def test_database_row_never_reused_and_cites_line_counts(self):
        _, rows = self._derive()
        r = rows['V-5']
        self.assertTrue(r['database'])
        self.assertTrue(r['reuse'].startswith('none'))
        self.assertIn('T-04', r['tasks'])
        self.assertEqual(r['tasks'], ['T-03', 'T-04'])

    def test_existing_inputs_never_shrink(self):
        _, rows = self._derive()
        r = rows['V-6']
        self.assertIn('extra/keep.py', r['inputs'])
        self.assertIn('src/d.py', r['inputs'])

    def test_missing_target_is_excluded_and_needs_review(self):
        (self.root / 'src/b.py').unlink()
        res, rows = self._derive()
        r = rows['V-2']
        self.assertNotIn('src/b.py', r['inputs'])
        self.assertIn('src/b.py', res['missing_targets'])
        self.assertTrue(r['needs_review'])
        self.assertTrue(any('src/b.py' in n for n in r['notes']))

    def test_changed_simulation_always_runs_undeclared_row(self):
        import aidd_coverage as cov
        res, _ = self._derive()
        sim = cov.simulate_changed(res, ['src/a.py'])
        self.assertEqual(sim['status'], 'ok')
        self.assertIn('V-4', sim['always_rows'])
        self.assertTrue(any('V-4' in w for w in sim['warnings']))

    def test_changed_simulation_skips_unrelated_rows(self):
        import aidd_coverage as cov
        res, _ = self._derive()
        res['rows'] = [r for r in res['rows'] if r['kind'] not in ('unresolved', 'whole-suite')]
        sim = cov.simulate_changed(res, ['src/a.py'])
        self.assertEqual(sim['status'], 'ok')
        self.assertEqual((sim['selected_tasks'], sim['rows_run'], sim['rows_skipped']), (['T-01'], 1, 3))
        self.assertEqual(sim['always_rows'], [])

    def test_changed_simulation_refuses_on_spec_change(self):
        import aidd_coverage as cov
        res, _ = self._derive()
        sim = cov.simulate_changed(res, ['specs/001-x/tasks.md'])
        self.assertEqual(sim['status'], 'refused')
        self.assertEqual(sim['reason'], 'spec policy changed')

    def test_dry_run_writes_nothing(self):
        import aidd_coverage as cov
        before = (self.spec / 'spec.md').read_bytes()
        files_before = _files(self.root)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            rc = cov.main([str(self.spec)])
        self.assertEqual(rc, 0)
        self.assertIn('DRY-RUN', out.getvalue())
        self.assertEqual((self.spec / 'spec.md').read_bytes(), before)
        self.assertEqual(_files(self.root), files_before)

    def test_apply_to_refuses_spec_and_foreign_file(self):
        import aidd_coverage as cov
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cov.main([str(self.spec), '--apply-to', str(self.spec / 'spec.md')]), 2)
            foreign = self.root / 'notes.txt'
            foreign.write_text('mine', encoding='utf-8')
            self.assertEqual(cov.main([str(self.spec), '--apply-to', str(foreign)]), 2)
            self.assertEqual(foreign.read_text(encoding='utf-8'), 'mine')
            target = self.root / 'proposal.md'
            self.assertEqual(cov.main([str(self.spec), '--apply-to', str(target)]), 0)
            self.assertEqual(cov.main([str(self.spec), '--apply-to', str(target)]), 0)
        self.assertTrue(target.read_text(encoding='utf-8').startswith(cov.PROPOSAL_MARK))
        self.assertEqual((self.spec / 'spec.md').read_text(encoding='utf-8'), SPEC)

    def test_json_output(self):
        import aidd_coverage as cov
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cov.main([str(self.spec), '--json']), 0)
        data = json.loads(out.getvalue())
        self.assertEqual(data['summary']['rows'], 6)

    def test_summary_counts(self):
        res, _ = self._derive()
        s = res['summary']
        self.assertEqual((s['rows'], s['cites-tasks'], s['via-fr-ac-api'], s['whole-suite'], s['unresolved']),
                         (6, 1, 3, 1, 1))
        self.assertEqual(res['uncovered_tasks'], [])

    def test_codes_printed_as_cited(self):
        spec = self.root / 'specs' / '002-y'
        spec.mkdir(parents=True)
        (spec / 'spec.md').write_text(
            '## Verification\n\n| # | Command | Expected | Covers |\n|---|---|---|---|\n'
            '| V-1 | `python -m unittest tests.test_a -v` | exit 0 | FR-014, FR-099 |\n', encoding='utf-8')
        (spec / 'tasks.md').write_text(
            '| Task | Codes satisfied | Target file | Status |\n|---|---|---|---|\n'
            '| T-01 | FR-014 | `src/a.py` | |\n', encoding='utf-8')
        _, rows = self._derive(spec)
        r = rows['V-1']
        notes = ' '.join(r['notes'])
        self.assertIn('FR-099', notes)
        self.assertIsNone(re.search(r'FR-(14|99)(?!\d)', notes + ' ' + r['covers']))

    def test_renumbered_target_resolves(self):
        spec = self.root / 'specs' / '003-z'
        spec.mkdir(parents=True)
        (spec / 'spec.md').write_text(
            '## Verification\n\n| # | Command | Expected | Covers |\n|---|---|---|---|\n'
            '| V-1 | `python -m unittest tests.test_m -v` | exit 0 | T-01 |\n', encoding='utf-8')
        (spec / 'tasks.md').write_text(
            '| Task | Codes satisfied | Target file | Status |\n|---|---|---|---|\n'
            '| T-01 | FR-001 | `migrations/0120_x.sql` | |\n', encoding='utf-8')
        mig = self.root / 'migrations' / '3277_x.sql'
        mig.parent.mkdir(parents=True)
        mig.write_text('-- renumbered migration with enough content to be real\nselect 1;\n', encoding='utf-8')
        _, rows = self._derive(spec)
        self.assertIn('migrations/3277_x.sql', rows['V-1']['inputs'])


class CoverageWiring(unittest.TestCase):
    def test_cli_registers_coverage(self):
        text = (REPO / 'aidd' / 'cli.py').read_text(encoding='utf-8')
        self.assertIn('("coverage", "aidd_coverage.py"', text)

    def test_skill_documents_coverage(self):
        text = (REPO / 'skill' / 'SKILL.md').read_text(encoding='utf-8')
        for needle in ('aidd coverage', 'via-fr-ac-api', 'HEAD~1'):
            self.assertTrue(needle in text, f'skill/SKILL.md lacks {needle!r}')


if __name__ == '__main__':
    unittest.main()
