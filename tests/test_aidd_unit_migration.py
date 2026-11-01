import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from skill.scripts import aidd_evidence as evidence, aidd_units as units


class UnitMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.spec = self.root / 'specs' / 's'
        self.spec.mkdir(parents=True)
        unit_dir = self.spec / 'amendments' / 'change'
        unit_dir.mkdir(parents=True)
        (unit_dir / 'tasks.md').write_text('unit tasks', encoding='utf-8')
        (self.spec / 'tasks.md').write_text('legacy tasks and approval', encoding='utf-8')
        (self.root / 'code.py').write_text('answer = 42\n', encoding='utf-8')
        self.source = self.root / 'candidate.json'
        self.data = {'schema_version': 2, 'spec_id': 's', 'unit_id': 'change', 'sequence': 1,
                     'parents': [], 'paths': ['specs/s/amendments/change/tasks.md'], 'targets': ['code.py'],
                     'version': 'v1', 'inputs': [], 'config': [], 'visual_refs': []}
        self.write_manifest()

    def write_manifest(self):
        self.source.write_text(json.dumps(self.data), encoding='utf-8')

    def test_plan_apply_revert_preserves_historical_artifacts(self):
        before = (self.spec / 'tasks.md').read_bytes()
        plan = units.migration_plan(self.root, 's', self.source)
        self.assertFalse((self.spec / 'amendments' / 'change' / 'manifest.json').exists())
        units.migration_apply(self.root, 's', self.source, plan['digest'])
        self.assertEqual(units.list_spec_unit_keys(self.root, 's'), ('s:change',))
        self.assertEqual(evidence.events(self.root, kind='unit_approved'), [])
        self.assertEqual(evidence.events(self.root, kind='unit_audit'), [])
        result = units.migration_revert(self.root, 's', 'change', evidence)
        self.assertTrue(result['reverted'])
        self.assertEqual((self.spec / 'tasks.md').read_bytes(), before)

    def test_changed_input_or_collision_refuses_apply(self):
        plan = units.migration_plan(self.root, 's', self.source)
        (self.root / 'code.py').write_text('different', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'plan changed'):
            units.migration_apply(self.root, 's', self.source, plan['digest'])
        plan = units.migration_plan(self.root, 's', self.source)
        units.migration_apply(self.root, 's', self.source, plan['digest'])
        with self.assertRaisesRegex(ValueError, 'no manifest'):
            units.migration_plan(self.root, 's', self.source)

    def test_missing_or_escaping_input_and_missing_parent_refused(self):
        for key, value in [('targets', ['../outside.py']), ('inputs', ['missing.py']),
                           ('parents', ['s:missing'])]:
            original = self.data[key]
            self.data[key] = value
            self.write_manifest()
            with self.assertRaises(ValueError):
                units.migration_plan(self.root, 's', self.source)
            self.data[key] = original

    def test_modified_unit_and_subsequent_evidence_prevent_revert(self):
        plan = units.migration_plan(self.root, 's', self.source)
        units.migration_apply(self.root, 's', self.source, plan['digest'])
        manifest = self.spec / 'amendments' / 'change' / 'manifest.json'
        raw = manifest.read_bytes()
        manifest.write_bytes(raw + b' ')
        with self.assertRaisesRegex(ValueError, 'manifest changed'):
            units.migration_revert(self.root, 's', 'change', evidence)
        manifest.write_bytes(raw)
        self.assertTrue(evidence.append(self.root, 'actual', 'unit_approved', spec='s', unit_id='change'))
        with self.assertRaisesRegex(ValueError, 'evidence exists'):
            units.migration_revert(self.root, 's', 'change', evidence)
        self.assertTrue(manifest.exists())

    def test_linked_target_is_rejected(self):
        link = self.root / 'linked.py'
        try:
            link.symlink_to(self.root / 'code.py')
        except OSError:
            self.skipTest('symlink creation unavailable')
        self.data['targets'] = ['linked.py']
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'symbolic link'):
            units.migration_plan(self.root, 's', self.source)

    def test_failed_apply_cleans_only_created_unit(self):
        plan = units.migration_plan(self.root, 's', self.source)
        with patch.object(units, 'discover_unit_scope', side_effect=ValueError('interrupted')):
            with self.assertRaisesRegex(ValueError, 'interrupted'):
                units.migration_apply(self.root, 's', self.source, plan['digest'])
        self.assertFalse((self.spec / 'amendments' / 'change' / 'manifest.json').exists())
        self.assertEqual((self.spec / 'tasks.md').read_text(encoding='utf-8'), 'legacy tasks and approval')

    def test_dependent_unit_blocks_revert(self):
        plan = units.migration_plan(self.root, 's', self.source)
        units.migration_apply(self.root, 's', self.source, plan['digest'])
        child_dir = self.spec / 'amendments' / 'child'
        child_dir.mkdir()
        (child_dir / 'tasks.md').write_text('child', encoding='utf-8')
        (self.root / 'child.py').write_text('child', encoding='utf-8')
        self.data.update(unit_id='child', sequence=2, parents=['s:change'],
                         paths=['specs/s/amendments/child/tasks.md'], targets=['child.py'])
        self.write_manifest()
        child = units.migration_plan(self.root, 's', self.source)
        units.migration_apply(self.root, 's', self.source, child['digest'])
        with self.assertRaisesRegex(ValueError, 'depend'):
            units.migration_revert(self.root, 's', 'change', evidence)

    def test_cli_plan_apply_revert(self):
        checkout = Path(__file__).resolve().parents[1]
        environment = dict(os.environ, AIDD_HOME=str(checkout / 'skill'))
        command = [sys.executable, '-m', 'aidd.cli', 'units', '--root', str(self.root)]
        def run(args):
            return subprocess.run(command + args, cwd=checkout, env=environment, text=True,
                                  capture_output=True, check=True)
        plan = json.loads(run(['plan', 's', '--manifest', str(self.source)]).stdout)
        run(['apply', 's', '--manifest', str(self.source), '--digest', plan['digest']])
        self.assertTrue((self.spec / 'amendments' / 'change' / 'manifest.json').is_file())
        self.assertTrue(json.loads(run(['revert', 's', 'change']).stdout)['reverted'])


if __name__ == '__main__':
    unittest.main()
