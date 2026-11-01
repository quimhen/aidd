import json
import tempfile
import unittest
from pathlib import Path

from skill.scripts.aidd_rules import unit_consent_question, unit_review_package
from skill.scripts.aidd_units import UnitManifest, discover_units, unit_for_target


class UnitReviewPackage(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / 'specs' / 's' / 'amendments' / 'a'
        self.directory.mkdir(parents=True)
        self.task_path = 'specs/s/amendments/a/tasks.md'
        (self.directory / 'tasks.md').write_text('Complete review text', encoding='utf-8')
        self.manifest([self.task_path])

    def manifest(self, paths):
        (self.directory / 'manifest.json').write_text(json.dumps({
            'schema_version': 1, 'spec_id': 's', 'unit_id': 'a', 'sequence': 1,
            'parents': [], 'paths': paths, 'targets': ['src/a.py']}), encoding='utf-8')

    def unit(self):
        return discover_units(self.root)[0]

    def test_exact_content_and_hash_change(self):
        first = json.loads(unit_review_package(self.unit(), self.root))
        self.assertEqual('Complete review text', first['tasks'][0]['content'])
        (self.directory / 'tasks.md').write_text('changed', encoding='utf-8')
        second = json.loads(unit_review_package(self.unit(), self.root))
        self.assertNotEqual(first['digest'], second['digest'])
        self.assertEqual('changed', second['tasks'][0]['content'])

    def test_missing_task_declaration_and_empty_task_refused(self):
        self.manifest([])
        with self.assertRaisesRegex(ValueError, 'no declared task'):
            unit_review_package(self.unit(), self.root)

    def test_v2_review_shows_version_dependencies_and_visual_metadata(self):
        path = self.directory / 'manifest.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data.update(schema_version=2, version='v3', inputs=['input.py'], config=['config.json'],
                    visual_refs=[{'screen_id': 'SCREEN-1', 'revision_id': 'v2', 'source': 'mock.html',
                                  'assets': [], 'states': ['ready'], 'roles': ['admin'],
                                  'viewports': ['1280x800']}])
        path.write_text(json.dumps(data), encoding='utf-8')
        package = unit_review_package(self.unit(), self.root)
        value = json.loads(package)
        self.assertEqual(value['format'], 'aidd-unit-review-v2')
        self.assertEqual(value['version'], 'v3')
        self.assertEqual(value['inputs'], ['input.py'])
        self.assertEqual(value['config'], ['config.json'])
        self.assertEqual(value['visual_refs'][0]['roles'], ['admin'])
        self.assertIn(package, unit_consent_question(package))
        self.manifest([self.task_path])
        (self.directory / 'tasks.md').write_text('', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'empty'):
            unit_review_package(self.unit(), self.root)

    def test_latest_descendant_and_incomparable_owners(self):
        a = UnitManifest(1, 's', 'a', 1, (), (), ('src/a.py',))
        b = UnitManifest(1, 's', 'b', 2, ('s:a',), (), ('src/a.py',))
        c = UnitManifest(1, 's', 'c', 3, ('s:a',), (), ('src/a.py',))
        self.assertEqual(b, unit_for_target([a, b], self.root, Path('src/A.py')))
        with self.assertRaisesRegex(ValueError, 'incomparable'):
            unit_for_target([a, b, c], self.root, Path('src/a.py'))
        self.assertIsNone(unit_for_target([a], self.root, Path('other.py')))
        with self.assertRaises(ValueError):
            unit_for_target([a], self.root, Path('../outside'))


if __name__ == '__main__':
    unittest.main()
