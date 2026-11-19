import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
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

    def future_target(self, name='future.py'):
        self.data['targets'] = [name]
        self.write_manifest()
        return self.root / name

    def assert_no_registration(self):
        self.assertFalse((self.spec / 'amendments/change/manifest.json').exists())
        self.assertFalse((self.spec / 'unit-migration-receipts/change.json').exists())
        self.assertTrue((self.spec / 'amendments/change/tasks.md').is_file())

    def test_absent_leaf_plan_apply_records_typed_absence_without_placeholder(self):
        target = self.future_target()
        plan = units.migration_plan(self.root, 's', self.source)
        self.assertEqual(plan['format'], 'aidd-unit-migration-plan-v2')
        self.assertIsInstance(plan['files']['future.py'], dict)
        self.assertEqual(plan['files']['future.py']['state'], 'ABSENT')
        self.assertEqual(plan['digest'], units.migration_plan(self.root, 's', self.source)['digest'])
        units.migration_apply(self.root, 's', self.source, plan['digest'])
        self.assertFalse(target.exists())
        self.assertTrue((self.spec / 'amendments/change/manifest.json').is_file())
        self.assertTrue((self.spec / 'unit-migration-receipts/change.json').is_file())

    def test_absent_nested_directory_output_does_not_create_parent_directories(self):
        target = self.future_target('new/deep/generated.py')
        plan = units.migration_plan(self.root, 's', self.source)
        self.assertEqual(plan['files']['new/deep/generated.py']['state'], 'ABSENT')
        units.migration_apply(self.root, 's', self.source, plan['digest'])
        self.assertFalse(target.exists())
        self.assertFalse((self.root / 'new').exists())

    def test_absent_empty_and_populated_file_plans_are_distinct(self):
        target = self.future_target()
        absent = units.migration_plan(self.root, 's', self.source)
        target.write_bytes(b'')
        empty = units.migration_plan(self.root, 's', self.source)
        target.write_text('real implementation\n', encoding='utf-8')
        populated = units.migration_plan(self.root, 's', self.source)
        self.assertEqual(len({absent['digest'], empty['digest'], populated['digest']}), 3)
        self.assertNotEqual(absent['files']['future.py'], empty['files']['future.py'])
        self.assertEqual(empty['format'], 'aidd-unit-migration-plan-v1')
        self.assertIsInstance(empty['files']['future.py'], str)

    def test_missing_target_also_declared_in_strict_role_is_rejected(self):
        self.future_target()
        (self.root / 'mock.html').write_text('<main/>', encoding='utf-8')
        visual = {'screen_id': 'SCREEN-01', 'revision_id': 'v1', 'source': 'mock.html',
                  'assets': [], 'states': ['ready'], 'roles': ['admin'], 'viewports': ['1440x900']}
        original = json.loads(json.dumps(self.data))
        for role in ('paths', 'inputs', 'config', 'visual_source', 'visual_asset'):
            with self.subTest(role=role):
                self.data = json.loads(json.dumps(original))
                if role in ('paths', 'inputs', 'config'):
                    self.data[role].append('future.py')
                else:
                    ref = dict(visual)
                    ref['source' if role == 'visual_source' else 'assets'] = 'future.py' if role == 'visual_source' else ['future.py']
                    self.data['visual_refs'] = [ref]
                self.write_manifest()
                with self.assertRaises(ValueError):
                    units.migration_plan(self.root, 's', self.source)
                self.assert_no_registration()

    def test_missing_parent_output_remains_strict_when_child_is_future(self):
        parent = units.migration_plan(self.root, 's', self.source)
        units.migration_apply(self.root, 's', self.source, parent['digest'])
        (self.root / 'code.py').unlink()
        child = self.spec / 'amendments/child'
        child.mkdir()
        (child / 'tasks.md').write_text('child task', encoding='utf-8')
        self.data.update(unit_id='child', sequence=2, parents=['s:change'],
                         paths=['specs/s/amendments/child/tasks.md'], targets=['child-future.py'])
        self.write_manifest()
        with self.assertRaises(ValueError):
            units.migration_plan(self.root, 's', self.source)
        self.assertFalse((child / 'manifest.json').exists())
        self.assertTrue((self.spec / 'amendments/change/manifest.json').is_file())

    def test_output_created_between_plan_and_apply_invalidates_reviewed_digest(self):
        target = self.future_target()
        plan = units.migration_plan(self.root, 's', self.source)
        target.write_bytes(b'')
        with self.assertRaises(ValueError):
            units.migration_apply(self.root, 's', self.source, plan['digest'])
        self.assert_no_registration()
        self.assertEqual(target.read_bytes(), b'')

    def test_future_output_becoming_directory_before_apply_is_rejected(self):
        target = self.future_target()
        plan = units.migration_plan(self.root, 's', self.source)
        target.mkdir()
        with self.assertRaises(ValueError):
            units.migration_apply(self.root, 's', self.source, plan['digest'])
        self.assert_no_registration()
        self.assertTrue(target.is_dir())

    def test_present_output_deleted_between_plan_and_apply_is_not_new_absence(self):
        plan = units.migration_plan(self.root, 's', self.source)
        (self.root / 'code.py').unlink()
        with self.assertRaises(ValueError):
            units.migration_apply(self.root, 's', self.source, plan['digest'])
        self.assert_no_registration()

    def test_missing_directory_chain_changed_before_apply_invalidates_digest(self):
        self.future_target('future/deep/output.py')
        plan = units.migration_plan(self.root, 's', self.source)
        (self.root / 'future').mkdir()
        with self.assertRaises(ValueError):
            units.migration_apply(self.root, 's', self.source, plan['digest'])
        self.assert_no_registration()
        self.assertTrue((self.root / 'future').is_dir())

    def test_existing_ancestor_replaced_before_apply_invalidates_identity(self):
        ancestor = self.root / 'generated'
        ancestor.mkdir()
        self.future_target('generated/output.py')
        plan = units.migration_plan(self.root, 's', self.source)
        ancestor.rename(self.root / 'original-generated')
        ancestor.mkdir()
        with self.assertRaises(ValueError):
            units.migration_apply(self.root, 's', self.source, plan['digest'])
        self.assert_no_registration()

    def test_output_appearing_after_manifest_creation_fails_and_cleans_manifest(self):
        target = self.future_target()
        plan = units.migration_plan(self.root, 's', self.source)
        created = self.spec / 'amendments/change/manifest.json'
        load = units.load_unit
        def after_create(path, root):
            if Path(path) == created:
                target.write_text('concurrent creator\n', encoding='utf-8')
            return load(path, root)
        with patch.object(units, 'load_unit', side_effect=after_create):
            with self.assertRaises(ValueError):
                units.migration_apply(self.root, 's', self.source, plan['digest'])
        self.assert_no_registration()
        self.assertEqual(target.read_text(encoding='utf-8'), 'concurrent creator\n')

    def test_present_output_mutation_after_manifest_creation_fails_and_cleans(self):
        plan = units.migration_plan(self.root, 's', self.source)
        created = self.spec / 'amendments/change/manifest.json'
        load = units.load_unit
        def after_create(path, root):
            if Path(path) == created:
                (self.root / 'code.py').write_text('concurrent mutation\n', encoding='utf-8')
            return load(path, root)
        with patch.object(units, 'load_unit', side_effect=after_create):
            with self.assertRaises(ValueError):
                units.migration_apply(self.root, 's', self.source, plan['digest'])
        self.assert_no_registration()

    def test_absent_directory_chain_appearing_after_manifest_creation_is_rejected(self):
        self.future_target('future/deep/output.py')
        plan = units.migration_plan(self.root, 's', self.source)
        created = self.spec / 'amendments/change/manifest.json'
        load = units.load_unit
        injected = False
        def after_create(path, root):
            nonlocal injected
            if Path(path) == created and not injected:
                injected = True
                (self.root / 'future').mkdir()
            return load(path, root)
        with patch.object(units, 'load_unit', side_effect=after_create):
            with self.assertRaises(ValueError):
                units.migration_apply(self.root, 's', self.source, plan['digest'])
        self.assert_no_registration()
        self.assertTrue((self.root / 'future').is_dir())

    def test_failed_apply_does_not_delete_concurrently_modified_manifest(self):
        plan = units.migration_plan(self.root, 's', self.source)
        created = self.spec / 'amendments/change/manifest.json'
        load = units.load_unit
        def after_create(path, root):
            if Path(path) == created:
                created.write_bytes(created.read_bytes() + b'\n')
                raise ValueError('another writer changed manifest')
            return load(path, root)
        with patch.object(units, 'load_unit', side_effect=after_create):
            with self.assertRaises(ValueError):
                units.migration_apply(self.root, 's', self.source, plan['digest'])
        self.assertTrue(created.is_file())
        self.assertFalse((self.spec / 'unit-migration-receipts/change.json').exists())

    def test_failed_apply_preserves_same_bytes_concurrent_manifest_replacement(self):
        plan = units.migration_plan(self.root, 's', self.source)
        created = self.spec / 'amendments/change/manifest.json'
        load = units.load_unit
        def after_create(path, root):
            if Path(path) == created:
                raw = created.read_bytes()
                created.rename(created.with_name('original-manifest.json'))
                created.write_bytes(raw)
                raise ValueError('another writer replaced manifest')
            return load(path, root)
        with patch.object(units, 'load_unit', side_effect=after_create):
            with self.assertRaises(ValueError):
                units.migration_apply(self.root, 's', self.source, plan['digest'])
        self.assertTrue(created.is_file())
        self.assertFalse((self.spec / 'unit-migration-receipts/change.json').exists())

    def test_future_output_directory_and_file_ancestor_are_rejected(self):
        for name in ('existing-directory', 'code.py/output.py'):
            with self.subTest(name=name):
                (self.root / 'existing-directory').mkdir(exist_ok=True)
                self.future_target(name)
                with self.assertRaises((ValueError, OSError)):
                    units.migration_plan(self.root, 's', self.source)
                self.assert_no_registration()

    def test_case_alias_of_existing_file_is_not_absent(self):
        self.future_target('CODE.py')
        with self.assertRaises(ValueError):
            units.migration_plan(self.root, 's', self.source)
        self.assert_no_registration()

    def test_case_alias_of_existing_ancestor_is_not_absent(self):
        (self.root / 'Actual').mkdir()
        self.future_target('actual/output.py')
        with self.assertRaises(ValueError):
            units.migration_plan(self.root, 's', self.source)
        self.assert_no_registration()

    def test_linked_missing_output_ancestor_is_rejected(self):
        real = self.root / 'real'
        real.mkdir()
        alias = self.root / 'alias'
        try:
            alias.symlink_to(real, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f'directory symlinks unavailable on this platform: {exc}')
        self.future_target('alias/output.py')
        with self.assertRaises(ValueError):
            units.migration_plan(self.root, 's', self.source)
        self.assert_no_registration()

    def test_dangling_output_link_is_not_absent(self):
        target = self.future_target()
        try:
            target.symlink_to(self.root / 'not-created.py')
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f'symlinks unavailable on this platform: {exc}')
        with self.assertRaises(ValueError):
            units.migration_plan(self.root, 's', self.source)
        self.assert_no_registration()

    @unittest.skipUnless(os.name == 'nt', 'junction fixture requires Windows')
    def test_junction_missing_output_ancestor_is_rejected(self):
        real, alias = self.root / 'real-junction-target', self.root / 'junction'
        real.mkdir()
        result = subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(alias), str(real)],
                                capture_output=True, text=True)
        if result.returncode:
            self.skipTest('Windows junction creation unavailable: ' + result.stderr.strip())
        self.future_target('junction/output.py')
        with self.assertRaises(ValueError):
            units.migration_plan(self.root, 's', self.source)
        self.assert_no_registration()

    @unittest.skipUnless(hasattr(os, 'mkfifo') and os.name != 'nt', 'FIFO fixtures are POSIX-only')
    def test_special_output_file_is_not_absent(self):
        target = self.future_target()
        os.mkfifo(target)
        with self.assertRaises((ValueError, OSError)):
            units.migration_plan(self.root, 's', self.source)
        self.assert_no_registration()

    def test_permission_failure_is_not_absence(self):
        target = self.future_target()
        original = Path.stat
        denials = []
        def denied(path, *args, **kwargs):
            if path == target:
                denials.append(path)
                raise PermissionError('fixture denies target metadata')
            return original(path, *args, **kwargs)
        # Simulated OS denial is portable; no claim that chmod denies an elevated process.
        with patch.object(Path, 'stat', denied):
            with self.assertRaises((ValueError, PermissionError)):
                units.migration_plan(self.root, 's', self.source)
        self.assertTrue(denials)
        self.assert_no_registration()

    def test_future_registration_readiness_review_fixture_consent_and_build_before_output(self):
        from tests import test_aidd_status as fixtures
        from tests import test_aidd_unit_build_gate as build_fixtures
        from skill.scripts import aidd_readiness as readiness
        fixture = fixtures.EvBase()
        fixture.setUp()
        def cleanup_evidence():
            try:
                fixture.tearDown()
            finally:
                fixture.doCleanups()
        self.addCleanup(cleanup_evidence)
        temporary, root, base = fixtures.make_project()
        self.addCleanup(temporary.cleanup)
        fixture.approve_legacy(root, base)
        owner = SimpleNamespace(root=root, base=base)
        directory = build_fixtures.UnitBuildGate.add_unit(owner, 'future', 1)
        manifest = directory / 'manifest.json'
        data = json.loads(manifest.read_text(encoding='utf-8'))
        data['targets'] = ['new-feature/output.py']
        candidate = root / 'future-candidate.json'
        candidate.write_text(json.dumps(data), encoding='utf-8')
        manifest.unlink()  # Helper supplied unregistered fixture documents; native migration creates the manifest.
        plan = units.migration_plan(root, base.name, candidate)
        units.migration_apply(root, base.name, candidate, plan['digest'])
        report = readiness.report(base, 'future')
        self.assertNotIn(report['status'], ('checker_error', 'incomplete', 'unstable'))
        self.assertEqual(report['scope']['unit'], base.name + ':future')
        self.assertEqual(report['native_consent'][0]['state'], 'pending')
        unit = next(item for item in units.discover_units(root) if item.unit_id == 'future')
        review = json.loads(fixtures.aidd_rules.unit_review_package(unit, root))
        self.assertIn('new-feature/output.py', review['targets'])
        # Existing native fixture seal helper, confined to EvBase's test evidence store.
        build_fixtures.UnitBuildGate.approve_unit(owner, 'future')
        with contextlib.redirect_stdout(io.StringIO()):
            findings = fixtures.aidd_rules.check_unit_build(base, 'future', root=root,
                                                           targets=['new-feature/output.py'])
        self.assertEqual(findings, [])
        self.assertFalse((root / 'new-feature').exists())


if __name__ == '__main__':
    unittest.main()
