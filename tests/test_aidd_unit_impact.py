import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from skill.scripts import aidd_rules, aidd_units
from skill.scripts.aidd_unit_audit import plan_impact
from skill.scripts.aidd_units import discover_unit_scope, discover_units, unit_for_target, unit_impact_snapshot, unit_impact_snapshots


class UnitImpact(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for path in ('first.py', 'second.py', 'shared.json',
                     'runner.py', 'screen.html', 'asset.png'):
            (self.root / path).write_bytes(('content:' + path).encode())
        self.write_unit('a', 1, [], ['specs/s/amendments/a/tasks.md'], ['first.py'], ['shared.json'], ['runner.py'], [])
        self.write_unit('b', 2, ['s:a'], ['specs/s/amendments/b/tasks.md'], ['second.py'], [], [], [{
            'screen_id': 'SCREEN-1', 'revision_id': 'v1', 'source': 'screen.html',
            'assets': ['asset.png'], 'states': ['loading'], 'roles': ['admin'], 'viewports': ['1280x800']}])

    def write_unit(self, name, sequence, parents, paths, targets, inputs, config, visual):
        directory = self.root / 'specs' / 's' / 'amendments' / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'tasks.md').write_text('task '+name, encoding='utf-8')
        (directory / 'manifest.json').write_text(json.dumps({
            'schema_version': 2, 'spec_id': 's', 'unit_id': name, 'sequence': sequence,
            'parents': parents, 'paths': paths, 'targets': targets, 'version': 'v1',
            'inputs': inputs, 'config': config, 'visual_refs': visual}), encoding='utf-8')

    def snapshot(self, name):
        unit = next(x for x in discover_units(self.root) if x.unit_id == name)
        return unit_impact_snapshot(unit, self.root)

    def test_targets_inputs_and_parents_affect_only_declared_consumers(self):
        parent, child = self.snapshot('a'), self.snapshot('b')
        (self.root / 'unrelated').write_text('new')
        self.assertEqual(child, self.snapshot('b'))
        (self.root / 'second.py').write_bytes(b'changed')
        self.assertEqual(parent, self.snapshot('a'))
        self.assertNotEqual(child['digest'], self.snapshot('b')['digest'])
        child = self.snapshot('b')
        (self.root / 'shared.json').write_bytes(b'new input')
        self.assertNotEqual(parent['digest'], self.snapshot('a')['digest'])
        self.assertNotEqual(child['digest'], self.snapshot('b')['digest'])

    def test_task_status_and_tracker_do_not_invalidate_impact_or_approval(self):
        task = self.root / 'specs/s/amendments/a/tasks.md'
        task.write_text('| Task | Requirement | Status | Tracker ref |\n|---|---|---|---|\n'
                        '| T-1 | Implement A | todo | x |\n', encoding='utf-8')
        unit = next(u for u in discover_units(self.root) if u.unit_id == 'a')
        before_impact = unit_impact_snapshot(unit, self.root)['digest']
        before_approval = aidd_rules.unit_approval_hash(unit, self.root)
        task.write_text('| Task | Requirement | Status | Tracker ref |\n|---|---|---|---|\n'
                        '| T-1 | Implement A | done | y |\n', encoding='utf-8')
        self.assertEqual(before_impact, unit_impact_snapshot(unit, self.root)['digest'])
        self.assertEqual(before_approval, aidd_rules.unit_approval_hash(unit, self.root))
        task.write_text('| Task | Requirement | Status | Tracker ref |\n|---|---|---|---|\n'
                        '| T-1 | Implement B | done | y |\n', encoding='utf-8')
        self.assertNotEqual(before_impact, unit_impact_snapshot(unit, self.root)['digest'])
        self.assertNotEqual(before_approval, aidd_rules.unit_approval_hash(unit, self.root))

    def test_visual_content_role_state_and_viewport_are_bound(self):
        original = self.snapshot('b')
        (self.root / 'asset.png').write_bytes(b'new bitmap')
        self.assertNotEqual(original['digest'], self.snapshot('b')['digest'])
        manifest = self.root / 'specs/s/amendments/b/manifest.json'
        data = json.loads(manifest.read_text())
        for key, value in (('roles', ['approver']), ('states', ['error']), ('viewports', ['767x800'])):
            old = self.snapshot('b')['digest']
            data['visual_refs'][0][key] = value
            manifest.write_text(json.dumps(data), encoding='utf-8')
            self.assertNotEqual(old, self.snapshot('b')['digest'])

    def test_visual_set_order_does_not_change_approval_or_impact(self):
        manifest = self.root / 'specs/s/amendments/b/manifest.json'
        data = json.loads(manifest.read_text(encoding='utf-8'))
        ref = data['visual_refs'][0]
        ref.update(roles=['admin', 'consult'], states=['loading', 'ready'],
                   viewports=['1280x800', '767x800'], assets=['asset.png', 'screen.html'])
        data['visual_refs'].append({**ref, 'screen_id': 'SCREEN-2', 'revision_id': 'v2'})
        manifest.write_text(json.dumps(data), encoding='utf-8')
        unit = next(u for u in discover_units(self.root) if u.unit_id == 'b')
        approval = aidd_rules.unit_approval_hash(unit, self.root)
        impact = unit_impact_snapshot(unit, self.root)['digest']
        data = json.loads(manifest.read_text(encoding='utf-8'))
        for item in data['visual_refs']:
            for key in ('roles', 'states', 'viewports', 'assets'):
                item[key].reverse()
        data['visual_refs'].reverse()
        manifest.write_text(json.dumps(data), encoding='utf-8')
        reordered = next(u for u in discover_units(self.root) if u.unit_id == 'b')
        self.assertEqual(approval, aidd_rules.unit_approval_hash(reordered, self.root))
        self.assertEqual(impact, unit_impact_snapshot(reordered, self.root)['digest'])

    def test_missing_files_and_legacy_scope_fail_closed(self):
        (self.root / 'runner.py').unlink()
        with self.assertRaises(ValueError):
            self.snapshot('b')
        path = self.root / 'specs/s/amendments/a/manifest.json'
        data = json.loads(path.read_text())
        for key in ('version', 'inputs', 'config', 'visual_refs'):
            data.pop(key)
        data['schema_version'] = 1
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'legacy'):
            self.snapshot('b')

    def test_batch_hashes_shared_inputs_once_per_phase(self):
        expected = {key: self.snapshot(key) for key in ('a', 'b')}
        counts = {}
        original = Path.read_bytes
        def counted(path):
            counts[str(path)] = counts.get(str(path), 0) + 1
            return original(path)
        with patch.object(Path, 'read_bytes', counted):
            result = unit_impact_snapshots(self.root, ['s:a', 's:b'])
        self.assertFalse(result['errors'])
        self.assertEqual(result['snapshots'], {'s:a': expected['a'], 's:b': expected['b']})
        # Initial stability check + final stability check: two reads each, not
        # one pair per consumer plus one pair per consumer's parent.
        self.assertEqual(counts[str(self.root / 'shared.json')], 4)

    def test_batch_preserves_disjoint_units_on_missing_or_changed_input(self):
        (self.root / 'third.py').write_text('third', encoding='utf-8')
        self.write_unit('c', 3, [], ['specs/s/amendments/c/tasks.md'], ['third.py'], [], [], [])
        (self.root / 'shared.json').unlink()
        result = unit_impact_snapshots(self.root, ['s:a', 's:b', 's:c'])
        self.assertEqual(set(result['errors']), {'s:a', 's:b'})
        self.assertEqual(set(result['snapshots']), {'s:c'})
        (self.root / 'shared.json').write_text('initial', encoding='utf-8')
        original = Path.read_bytes
        count = 0
        def mutate_on_final_check(path):
            nonlocal count
            if path == self.root / 'shared.json':
                count += 1
                if count == 3:
                    path.write_text('mutated', encoding='utf-8')
            return original(path)
        with patch.object(Path, 'read_bytes', mutate_on_final_check):
            result = unit_impact_snapshots(self.root, ['s:a', 's:b', 's:c'])
        self.assertEqual(set(result['errors']), {'s:a', 's:b'})
        self.assertEqual(set(result['snapshots']), {'s:c'})

    def test_unrelated_malformed_spec_does_not_block_unit_scope(self):
        (self.root / 'specs' / 'unrelated' / 'amendments' / 'draft').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'missing unit manifest'):
            discover_units(self.root)
        units = discover_unit_scope(self.root, 's')
        unit = next(u for u in units if u.unit_id == 'a')
        self.assertEqual(unit_impact_snapshot(unit, self.root)['unit'], 's:a')
        batch = unit_impact_snapshots(self.root, ['s:a', 's:b', 'unrelated:draft'])
        self.assertEqual(set(batch['snapshots']), {'s:a', 's:b'})
        self.assertIn('manifest', batch['errors']['unrelated:draft'])
        (self.root / 'specs/s/spec.md').write_text('# spec\n', encoding='utf-8')
        plan = plan_impact(self.root, 's', [], aidd_rules, aidd_units)
        self.assertEqual({entry['unit'] for entry in plan['units']}, {'s:a', 's:b'})
        self.assertTrue(all('scope_digest' in entry for entry in plan['units']))

    def test_changed_plan_selects_consumers_and_avoids_disjoint_file_reads(self):
        (self.root / 'third.py').write_text('third', encoding='utf-8')
        self.write_unit('c', 3, [], ['specs/s/amendments/c/tasks.md'], ['third.py'], [], [], [])
        (self.root / 'specs/s/spec.md').write_text('# spec\n', encoding='utf-8')
        reads = []
        original = Path.read_bytes
        def counted(path):
            reads.append(path)
            return original(path)
        with patch.object(Path, 'read_bytes', counted):
            plan = plan_impact(self.root, 's', [], aidd_rules, aidd_units, changed_paths=['first.py'])
        self.assertEqual({entry['unit'] for entry in plan['units']}, {'s:a', 's:b'})
        self.assertNotIn(self.root / 'third.py', reads)
        self.assertFalse(plan['changed']['complete'])
        self.assertEqual(plan['changed']['committed_since_audit'], 'unknown')

    def test_invalid_disjoint_sibling_does_not_invalidate_valid_units(self):
        (self.root / 'third.py').write_text('third', encoding='utf-8')
        self.write_unit('c', 3, [], ['specs/s/amendments/c/tasks.md'], ['third.py'], [], [], [])
        manifest = self.root / 'specs/s/amendments/c/manifest.json'
        data = json.loads(manifest.read_text(encoding='utf-8'))
        del data['version']
        manifest.write_text(json.dumps(data), encoding='utf-8')
        batch = unit_impact_snapshots(self.root, ['s:a', 's:b', 's:c'])
        self.assertEqual(set(batch['snapshots']), {'s:a', 's:b'})
        self.assertIn('invalid manifest', batch['errors']['s:c'])
        (self.root / 'specs/s/spec.md').write_text('# spec\n', encoding='utf-8')
        plan = plan_impact(self.root, 's', [], aidd_rules, aidd_units)
        by_key = {item['unit']: item for item in plan['units']}
        self.assertIn('scope_digest', by_key['s:a'])
        self.assertIn('scope_digest', by_key['s:b'])
        self.assertEqual(by_key['s:c']['status'], 'indeterminate')
        # Once the invalid sibling claims the same target, its ownership can no
        # longer be proven disjoint, so the affected branch cannot become PASS.
        data['targets'] = ['first.py']
        manifest.write_text(json.dumps(data), encoding='utf-8')
        batch = unit_impact_snapshots(self.root, ['s:a', 's:b'])
        self.assertEqual(set(batch['errors']), {'s:a', 's:b'})
        self.assertTrue(all('ownership indeterminate' in value for value in batch['errors'].values()))

    def test_invalid_sibling_with_unknown_targets_is_indeterminate(self):
        (self.root / 'specs/s/amendments/broken').mkdir(parents=True)
        batch = unit_impact_snapshots(self.root, ['s:a'])
        self.assertIn('ownership indeterminate', batch['errors']['s:a'])

    def test_regular_readme_is_not_treated_as_a_unit(self):
        (self.root / 'specs/s/amendments/README.md').write_text('notes', encoding='utf-8')
        self.assertIn('s:a', unit_impact_snapshots(self.root, ['s:a'])['snapshots'])
        self.assertEqual({u.key for u in discover_units(self.root)}, {'s:a', 's:b'})

    def test_duplicate_or_unknown_sibling_sequence_never_produces_scope(self):
        (self.root / 'third.py').write_text('third', encoding='utf-8')
        self.write_unit('c', 3, [], ['specs/s/amendments/c/tasks.md'], ['third.py'], [], [], [])
        manifest = self.root / 'specs/s/amendments/c/manifest.json'
        original = json.loads(manifest.read_text(encoding='utf-8'))
        for invalid in (False, True):
            data = dict(original, sequence=1)
            if invalid:
                data.pop('version')
            manifest.write_text(json.dumps(data), encoding='utf-8')
            with self.subTest(invalid=invalid):
                batch = unit_impact_snapshots(self.root, ['s:a'])
                self.assertNotIn('s:a', batch['snapshots'])
                self.assertIn('s:a', batch['errors'])
        unknown = dict(original)
        unknown.pop('sequence')
        manifest.write_text(json.dumps(unknown), encoding='utf-8')
        self.assertIn('s:a', unit_impact_snapshots(self.root, ['s:a'])['errors'])

    def test_invalid_sibling_hardlink_target_is_indeterminate(self):
        alias = self.root / 'alias-target.py'
        try:
            os.link(self.root / 'first.py', alias)
        except OSError:
            self.skipTest('hardlinks unavailable')
        self.write_unit('c', 3, [], ['specs/s/amendments/c/tasks.md'], ['alias-target.py'], [], [], [])
        manifest = self.root / 'specs/s/amendments/c/manifest.json'
        data = json.loads(manifest.read_text(encoding='utf-8'))
        del data['version']
        manifest.write_text(json.dumps(data), encoding='utf-8')
        batch = unit_impact_snapshots(self.root, ['s:a'])
        self.assertIn('ownership indeterminate', batch['errors']['s:a'])

    def test_malformed_related_parent_does_not_affect_disjoint_spec(self):
        (self.root / 'specs' / 'unrelated' / 'amendments' / 'draft').mkdir(parents=True)
        parent = self.root / 'specs/s/amendments/a/manifest.json'
        data = json.loads(parent.read_text(encoding='utf-8'))
        data['parents'] = ['unrelated:draft']
        parent.write_text(json.dumps(data), encoding='utf-8')
        other = self.root / 'specs/t/amendments/c'
        other.mkdir(parents=True)
        (other / 'tasks.md').write_text('task', encoding='utf-8')
        (self.root / 'third.py').write_text('third', encoding='utf-8')
        (other / 'manifest.json').write_text(json.dumps({
            'schema_version': 2, 'spec_id': 't', 'unit_id': 'c', 'sequence': 1,
            'parents': [], 'paths': ['specs/t/amendments/c/tasks.md'], 'targets': ['third.py'],
            'version': 'v1', 'inputs': [], 'config': [], 'visual_refs': []}), encoding='utf-8')
        batch = unit_impact_snapshots(self.root, ['s:a', 's:b', 't:c'])
        self.assertEqual(set(batch['errors']), {'s:a', 's:b'})
        self.assertEqual(set(batch['snapshots']), {'t:c'})

    def test_hardlink_alias_owner_and_unknown_fail_closed(self):
        source = self.root / 'first.py'
        alias = self.root / 'alias.py'
        try:
            os.link(source, alias)
        except OSError:
            self.skipTest('hardlinks unavailable')
        units = discover_units(self.root)
        self.assertEqual(unit_for_target(units, self.root, alias).unit_id, 'a')
        unrelated = self.root / 'orphan.py'
        unrelated.write_text('orphan')
        os.link(unrelated, self.root / 'orphan-alias.py')
        with self.assertRaisesRegex(ValueError, 'unknown ownership'):
            unit_for_target(units, self.root, unrelated)

    def test_empty_scope_or_missing_tasks_cannot_produce_snapshot(self):
        path = self.root / 'specs/s/amendments/a/manifest.json'
        data = json.loads(path.read_text())
        data.update(paths=[], targets=[], inputs=[], config=[], visual_refs=[])
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'task file'):
            self.snapshot('a')
        data['paths'] = ['specs/s/amendments/a/tasks.md']
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'execution scope'):
            self.snapshot('a')
