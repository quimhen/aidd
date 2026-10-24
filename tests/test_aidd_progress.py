"""aidd progress (amendment to spec 004): implementation % per spec from the tasks' Target files."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / 'skill' / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import aidd_progress as P  # noqa: E402

HDR = '| Task | Description | Codes | Target file | Status |\n|---|---|---|---|---|\n'


class TestProgress(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / 'src').mkdir()
        (self.root / 'src' / 'marked.py').write_text('# aidd:FR-001 implementation of the first requirement\nprint("x" * 50)\n', encoding='utf-8')
        (self.root / 'src' / 'plain.py').write_text('print("hello world, no marker here at all")\n', encoding='utf-8')
        (self.root / 'src' / 'stub.py').write_text('x=1\n', encoding='utf-8')
        self.spec = self.root / 'specs' / '001-x'
        self.spec.mkdir(parents=True)

    def tasks(self, rows):
        (self.spec / 'tasks.md').write_text(HDR + ''.join(rows), encoding='utf-8')
        return P.measure(self.root, self.spec)

    def test_states_and_percentages(self):
        m = self.tasks([
            '| T-01 | a | FR-001 | `src/marked.py` | done |\n',
            '| T-02 | b | FR-002 | `src/plain.py` |  |\n',
            '| T-03 | c | FR-003 | `src/stub.py` |  |\n',
            '| T-04 | d | FR-004 | `src/missing.py` |  |\n',
            '| T-05 | e | FR-005 | W0.a |  |\n',
        ])
        states = {r['id']: r['state'] for r in m['rows']}
        self.assertEqual(states, {'T-01': 'marked', 'T-02': 'present', 'T-03': 'stub', 'T-04': 'missing', 'T-05': 'n/a'})
        self.assertEqual((m['tasks'], m['measurable']), (5, 4))
        self.assertEqual(m['impl_pct'], 50.0)       # marked + present of 4 measurable
        self.assertEqual(m['marked_pct'], 25.0)
        self.assertEqual(m['declared_done'], 1)

    def test_marker_must_name_the_tasks_codes(self):
        m = self.tasks(['| T-01 | a | FR-009 | `src/marked.py` |  |\n'])   # file marks FR-001, task satisfies FR-009
        self.assertEqual(m['rows'][0]['state'], 'present')

    def test_path_relative_to_a_subfolder_resolves_by_suffix(self):
        (self.root / 'skill' / 'scripts').mkdir(parents=True)
        (self.root / 'skill' / 'scripts' / 'tool.py').write_text('# aidd:FR-001 tool implementation text\n' * 3, encoding='utf-8')
        m = self.tasks(['| T-01 | a | FR-001 | `scripts/tool.py` |  |\n', '| T-02 | b | FR-002 | `scripts/nope.py` |  |\n'])
        self.assertEqual([r['state'] for r in m['rows']], ['marked', 'missing'])

    def test_multiple_targets_all_must_exist(self):
        m = self.tasks(['| T-01 | a | FR-001 | `src/marked.py` + `src/missing.py` |  |\n'])
        self.assertEqual(m['rows'][0]['state'], 'missing')

    def test_paths_are_extracted_from_prose_cells(self):
        t = P.parse_tasks(HDR + '| T-01 | a | FR-001 | src/marked.py + src/new.py (new); tests: tests/t.py | |\n')[0]
        self.assertEqual(t['paths'], ['src/marked.py', 'src/new.py', 'tests/t.py'])
        t = P.parse_tasks(HDR + '| T-02 | a | FR-001 | W0.a, any other file | |\n')[0]
        self.assertEqual(t['paths'], [])

    def test_table_without_target_column_counts_tasks_as_not_measurable(self):
        (self.spec / 'tasks.md').write_text(
            '| Task | Packages | Wave | Title | Status |\n|---|---|---|---|---|\n'
            '| T-001 | QA-01 | W0.a | scan | done |\n| T-002 | QA-02 | W0.b | version |  |\n', encoding='utf-8')
        m = P.measure(self.root, self.spec)
        self.assertEqual((m['tasks'], m['measurable'], m['na']), (2, 0, 2))
        self.assertIsNone(m['impl_pct'])
        self.assertEqual(m['declared_pct'], 50.0)

    def test_no_measurable_tasks_gives_none(self):
        m = self.tasks(['| T-01 | a | FR-001 | prose, not a path |  |\n'])
        self.assertIsNone(m['impl_pct'])

    def test_graph_and_cli_write_progress_json(self):
        self.tasks(['| T-01 | a | FR-001 | `src/marked.py` |  |\n'])
        self.assertEqual(P.main(['--root', str(self.root), '--quiet']), 0)
        g = json.loads((self.root / '.aidd' / 'graphs' / 'progress.json').read_text(encoding='utf-8'))
        ids = {n['id'] for n in g['nodes']}
        self.assertIn('spec:001-x', ids)
        self.assertIn('001-x/T-01', ids)
        self.assertIn({'source': '001-x/T-01', 'target': 'src/marked.py', 'relation': 'targets'}, g['edges'])

    def test_declared_path_shorthand_is_expanded(self):
        (self.root / 'Payroll' / 'engine' / 'pkg').mkdir(parents=True)
        (self.root / 'Payroll' / 'engine' / 'pkg' / 'rt.py').write_text('# aidd:FR-001 runtime implementation text\n' * 3, encoding='utf-8')
        (self.spec / 'tasks.md').write_text(
            'Path shorthand: `ENG/` = `Payroll/engine/pkg/` · `SPEC/` = `specs/001-x/`.\n\n' + HDR +
            '| T-01 | a | FR-001 | `ENG/rt.py` (same owner as T-09) |  |\n'
            '| T-02 | b | FR-002 | `ENG/none.py` |  |\n'
            '| T-03 | c | FR-003 | `SPEC/tasks.md` |  |\n', encoding='utf-8')
        m = P.measure(self.root, self.spec)
        self.assertEqual([r['state'] for r in m['rows']], ['marked', 'missing', 'present'])

    def test_leading_dot_directory_is_kept(self):
        t = P.parse_tasks(HDR + '| T-01 | a | FR-001 | `.github/workflows/ci.yml` (new). | |\n')[0]
        self.assertEqual(t['paths'], ['.github/workflows/ci.yml'])

    def test_shorthand_only_from_a_shorthand_line(self):
        self.assertEqual(P.shorthand_map('See `ENG/` = `a/b/` somewhere'), {})
        self.assertEqual(P.shorthand_map('Path shorthand: `ENG/` = `a/b/`'), {'ENG': 'a/b/'})

    def test_pending_agrees_with_progress(self):
        import aidd_pending as PN
        (self.root / 'Payroll' / 'engine' / 'pkg').mkdir(parents=True)
        (self.root / 'Payroll' / 'engine' / 'pkg' / 'rt.py').write_text('x = 1  # runtime implementation text here\n', encoding='utf-8')
        (self.spec / 'tasks.md').write_text(
            'Path shorthand: `ENG/` = `Payroll/engine/pkg/`.\n\n' + HDR +
            '| T-01 | a | FR-001 | `ENG/rt.py` (same owner as T-09) |  |\n'
            '| T-02 | b | FR-002 | `ENG/none.py` |  |\n'
            '| T-03 | c | FR-003 | prose only |  |\n', encoding='utf-8')
        done, pending, unknown = PN.classify(PN.parse((self.spec / 'tasks.md').read_text(encoding='utf-8')), self.root)
        self.assertEqual((done, [t for t, _ in pending], unknown), (['T-01'], ['T-02'], ['T-03']))
        self.assertEqual(pending[0][1], ['Payroll/engine/pkg/none.py'])

    def test_no_specs_is_a_usage_error(self):
        self.assertEqual(P.main(['--root', tempfile.mkdtemp()]), 2)

    def test_registered_as_a_builtin_graph(self):
        import aidd_graphs as G
        self.tasks(['| T-01 | a | FR-001 | `src/marked.py` |  |\n'])
        names = {e['name']: e for e in G._autodetect(self.root)}
        self.assertEqual(names['progress']['refresh'], 'builtin:progress')
        cmd, shell = G._command(self.root, names['progress'])
        self.assertFalse(shell)
        self.assertTrue(str(cmd[1]).endswith('aidd_progress.py'))


if __name__ == '__main__':
    unittest.main()
