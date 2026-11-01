import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from skill.scripts.aidd_units import discover_units
from skill.scripts.aidd_rules import approval_hash, unit_approval_hash


class UnitHash(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.file('parent.txt', 'parent')
        self.file('child.txt', 'child')
        self.manifest('parent', 1, [], ['parent.txt'])
        self.manifest('child', 2, ['s:parent'], ['child.txt'])

    def file(self, name, content):
        (self.root / name).write_text(content, encoding='utf-8')

    def manifest(self, unit, sequence, parents, paths):
        path = self.root / 'specs' / 's' / 'amendments' / unit
        path.mkdir(parents=True, exist_ok=True)
        (path / 'manifest.json').write_text(json.dumps(dict(
            schema_version=1, spec_id='s', unit_id=unit, sequence=sequence,
            parents=parents, paths=paths, targets=[])), encoding='utf-8')

    def digest(self, key):
        unit = next(u for u in discover_units(self.root) if u.unit_id == key)
        return unit_approval_hash(unit, self.root)

    def test_changed_inputs_and_parent_invalidate_only_dependents(self):
        parent, child = self.digest('parent'), self.digest('child')
        self.file('unrelated.txt', 'different')
        self.assertEqual(child, self.digest('child'))
        self.file('child.txt', 'changed')
        self.assertEqual(parent, self.digest('parent'))
        self.assertNotEqual(child, self.digest('child'))
        child = self.digest('child')
        self.file('parent.txt', 'changed')
        self.assertNotEqual(parent, self.digest('parent'))
        self.assertNotEqual(child, self.digest('child'))

    def test_missing_unrelated_input_does_not_block_and_own_input_does(self):
        self.manifest('other', 3, [], ['missing'])
        self.assertEqual(64, len(self.digest('child')))
        (self.root / 'child.txt').unlink()
        with self.assertRaises(ValueError):
            self.digest('child')

    def test_legacy_hash_unchanged(self):
        self.assertEqual(approval_hash('hello\n'), approval_hash('hello\r\n'))
        self.assertEqual(12, len(approval_hash('hello\n')))

    def test_v2_approval_binds_declarations_but_not_target_bytes(self):
        path = self.root / 'specs' / 's' / 'amendments' / 'parent' / 'manifest.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data.update(schema_version=2, version='v1', inputs=['input.txt'],
                    config=[], visual_refs=[], targets=['target.py'])
        path.write_text(json.dumps(data), encoding='utf-8')
        self.file('target.py', 'before')
        first = self.digest('parent')
        self.file('target.py', 'after')
        self.assertEqual(first, self.digest('parent'))
        data['inputs'] = ['other-input.txt']
        path.write_text(json.dumps(data), encoding='utf-8')
        self.assertNotEqual(first, self.digest('parent'))

    def test_v2_equivalent_dataclass_from_top_level_import_is_accepted(self):
        import importlib
        import sys
        path = self.root / 'specs' / 's' / 'amendments' / 'parent' / 'manifest.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data.update(schema_version=2, version='v1', inputs=[], config=[], visual_refs=[])
        path.write_text(json.dumps(data), encoding='utf-8')
        scripts = str(Path(__file__).resolve().parents[1] / 'skill' / 'scripts')
        with patch.object(sys, 'path', [scripts, *sys.path]):
            foreign = importlib.import_module('aidd_units')
            foreign_unit = next(u for u in foreign.discover_units(self.root) if u.unit_id == 'parent')
        self.assertEqual(unit_approval_hash(foreign_unit, self.root), self.digest('parent'))


if __name__ == '__main__':
    unittest.main()
