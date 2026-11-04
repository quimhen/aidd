"""aidd progress task-state resolution (spec 007 amendment 04, T-26): AC-261..AC-268 / FR-230..FR-235."""
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / 'skill' / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import aidd_progress as progress  # noqa: E402

HDR = '| Task | Codes satisfied | Target file | Status |\n|---|---|---|---|\n'
BODY = '-- migration body, long enough to be more than the stub threshold of forty bytes\n'
ALIAS_TOON = ('version: 1\ngenerated: 2026-11-03T00:00:00+00:00\naliases[1]{old,new,scope,reason}:\n'
              '  ordr_table.dart,oped_table.dart,mobile,F30\n')


class TaskStateResolution(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, content):
        fp = self.root / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            fp.write_bytes(content)
        else:
            fp.write_text(content, encoding='utf-8')
        return fp

    def one_task(self, target_cell):
        text = HDR + '| T-01 | FR-230 | %s |  |\n' % target_cell
        tasks = progress.parse_tasks(text)
        self.assertEqual(len(tasks), 1)
        return tasks[0]

    # AC-261 / FR-230 / FR-231
    def test_delete_target_gone_is_present(self):
        task = self.one_task('`src/old_table.dart (delete)`')
        self.assertEqual(task['delete'], ['src/old_table.dart'])
        self.assertEqual(progress.task_state(task, self.root), 'present')

    # AC-262 / FR-231
    def test_delete_target_still_there_is_missing(self):
        self.write('src/old_table.dart', BODY)
        task = self.one_task('`src/old_table.dart (delete)`')
        self.assertEqual(task['delete'], ['src/old_table.dart'])
        self.assertEqual(progress.task_state(task, self.root), 'missing')

    # AC-263 / FR-232 / FR-234
    def test_renumbered_migration_is_renamed(self):
        self.write('migrations/3277_x.sql', BODY)
        task = self.one_task('`migrations/0120_x.sql`')
        self.assertEqual(progress.task_state(task, self.root), 'renamed')

    # AC-264 / FR-232
    def test_ambiguous_renumber_is_missing(self):
        self.write('migrations/3277_x.sql', BODY)
        self.write('migrations/3300_x.sql', BODY)
        task = self.one_task('`migrations/0120_x.sql`')
        self.assertEqual(progress.task_state(task, self.root), 'missing')

    # AC-265 / FR-233 / FR-234
    def test_alias_file_resolves_rename(self):
        self.write('.aidd/graphs/path-aliases.toon', ALIAS_TOON)
        self.write('mobile/tables/oped_table.dart', BODY)
        task = self.one_task('`mobile/tables/ordr_table.dart`')
        self.assertEqual(progress.task_state(task, self.root), 'renamed')

    # AC-266 / FR-233
    def test_bad_alias_is_missing_without_error(self):
        self.write('.aidd/graphs/path-aliases.toon', ALIAS_TOON)      # alias to an absent file
        task = self.one_task('`mobile/tables/ordr_table.dart`')
        self.assertEqual(progress.task_state(task, self.root), 'missing')
        with tempfile.TemporaryDirectory() as other:                  # unreadable / binary alias graph
            other_root = Path(other)
            bad = other_root / '.aidd' / 'graphs' / 'path-aliases.toon'
            bad.parent.mkdir(parents=True)
            bad.write_bytes(b'\xff\x00{')
            new = other_root / 'mobile' / 'tables' / 'oped_table.dart'
            new.parent.mkdir(parents=True)
            new.write_text(BODY, encoding='utf-8')
            self.assertEqual(progress.task_state(task, other_root), 'missing')

    # AC-267 / FR-235
    def test_prose_task_id_is_not_a_task(self):
        self.write('src/a.py', BODY)
        text = (HDR + '| T-01 | FR-230 | `src/a.py` |  |\n'
                '\nA paragraph of prose that mentions the next line.\n'
                '| T-42 | prose |\n')
        ids = [t['id'] for t in progress.parse_tasks(text)]
        self.assertNotIn('T-42', ids)
        self.assertEqual(ids, ['T-01'])

    # AC-268
    def test_project_without_cases_is_unchanged(self):
        self.write('src/plain.py', BODY)
        task = self.one_task('`src/plain.py`')
        self.assertEqual(task['paths'], ['src/plain.py'])
        self.assertEqual(progress.task_state(task, self.root), 'present')


if __name__ == '__main__':
    unittest.main()
