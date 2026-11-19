"""Build preflight for approved units must not run the parent's closing gate."""
import contextlib
import io
import json
import os
from pathlib import Path
from unittest import mock

from tests import test_aidd_status as fixtures

rules = fixtures.aidd_rules
status = fixtures.aidd_status
ev = fixtures.ev


class UnitBuildGate(fixtures.EvBase):
    def setUp(self):
        super().setUp()
        self.tmp, self.root, self.base = fixtures.make_project()
        self.addCleanup(self.tmp.cleanup)
        self.approve_legacy(self.root, self.base)
        self.unit = self.add_unit('change', 1)
        self.approve_unit('change')

    def add_unit(self, name, sequence, parents=(), spec=None):
        base = spec or self.base
        directory = base / 'amendments' / name
        directory.mkdir(parents=True)
        source = fixtures.SPEC.replace('user — "only the invoices screen"', 'repo — src/billing.py:1')
        (directory / 'spec.md').write_text(source, encoding='utf-8')
        (directory / 'plan.md').write_text('# Plan\nExisting source and interfaces.\n', encoding='utf-8')
        (directory / 'tasks.md').write_text(fixtures.TASKS + '\nApproved: PENDING\n', encoding='utf-8')
        paths = [(directory / f).relative_to(self.root).as_posix()
                 for f in ('spec.md', 'plan.md', 'tasks.md')]
        manifest = dict(schema_version=2, spec_id=base.name, unit_id=name,
                        sequence=sequence, parents=list(parents), paths=paths,
                        targets=['src/billing.py'], version='v1', inputs=[], config=[], visual_refs=[])
        (directory / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        return directory

    def approve_unit(self, name, spec=None):
        import aidd_units
        base = spec or self.base
        key = f'{base.name}:{name}'
        unit = next(u for u in aidd_units.discover_unit_scope(self.root, base.name, [key]) if u.key == key)
        ev.append(self.root, 's1', 'unit_approved', spec=base.name, unit_id=name,
                  digest=rules.unit_approval_hash(unit, self.root), review_sha256='a' * 64)

    def check(self, name='change', targets=()):
        return rules.check_unit_build(self.base, name, root=self.root, targets=targets)

    def test_approved_unit_passes_with_historical_parent_quote_and_closing_debt(self):
        self.assertTrue(any(v['rule'] == 'R5' for v in rules.check_spec_dir(self.base, self.root)))
        self.assertEqual(self.check(targets=['src/billing.py']), [])
        self.assertTrue(any(v['rule'] == 'R5' for v in rules.check_spec_dir(self.base, self.root)))

    def test_unit_changes_invalidate_consent(self):
        with (self.unit / 'plan.md').open('a', encoding='utf-8') as handle:
            handle.write('Changed scope\n')
        self.assertTrue(any(v['rule'] == 'R6' for v in self.check()))

    def test_missing_unit_approval_fails(self):
        self.add_unit('unapproved', 2)
        self.assertTrue(any(v['rule'] == 'R6' for v in self.check('unapproved')))

    def test_missing_base_seal_and_unrecorded_base_seal_fail(self):
        task = self.base / 'tasks.md'
        task.write_text(fixtures.TASKS, encoding='utf-8')
        self.assertTrue(any(v['rule'] == 'R6' for v in self.check()))
        digest = rules.approval_hash(fixtures.TASKS + '\nChanged requirement\n')
        task.write_text(fixtures.TASKS + f'\nChanged requirement\nApproved: 2026-01-01 hash:{digest}\n', encoding='utf-8')
        self.assertTrue(any(v['rule'] == 'R6' for v in self.check()))

    def test_target_outside_unit_or_path_escape_fails(self):
        for target in ('src/check.py', '../outside.py', str(self.root / 'src/billing.py')):
            with self.subTest(target=target):
                self.assertTrue(self.check(targets=[target]))

    def test_incomparable_valid_sibling_cannot_claim_the_same_target(self):
        self.add_unit('sibling', 2)
        self.approve_unit('sibling')
        self.assertTrue(self.check(targets=['src/billing.py']))
        self.assertTrue(self.check())

    def test_unapproved_descendant_never_falls_back_to_approved_ancestor(self):
        self.add_unit('descendant', 2, [f'{self.base.name}:change'])
        self.assertTrue(self.check(targets=['src/billing.py']))

    def test_disjoint_unapproved_or_malformed_peer_does_not_block(self):
        peer = self.add_unit('disjoint', 2)
        path = peer / 'manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        manifest['targets'] = ['src/check.py']
        path.write_text(json.dumps(manifest), encoding='utf-8')
        self.assertEqual(self.check(), [])
        manifest['version'] = []  # Invalid v2, but scope remains provably disjoint.
        path.write_text(json.dumps(manifest), encoding='utf-8')
        self.assertEqual(self.check(), [])

    def test_case_alias_peer_does_not_evade_ownership(self):
        peer = self.add_unit('alias', 2)
        path = peer / 'manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        manifest['targets'] = ['src/BILLING.py']
        path.write_text(json.dumps(manifest), encoding='utf-8')
        self.assertTrue(self.check())

    def test_hardlink_peer_does_not_evade_ownership(self):
        alias = self.root / 'src/alias.py'
        try:
            os.link(self.root / 'src/billing.py', alias)
        except OSError as exc:
            self.skipTest(f'Hardlinks unavailable: {exc}')
        peer = self.add_unit('alias', 2)
        path = peer / 'manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        manifest['targets'] = ['src/alias.py']
        path.write_text(json.dumps(manifest), encoding='utf-8')
        self.assertTrue(self.check())

    def test_incomparable_owner_in_another_spec_is_not_ignored(self):
        foreign = fixtures.add_spec(self.root, '002-y')
        self.add_unit('foreign', 1, spec=foreign)
        self.assertTrue(self.check(targets=['src/billing.py']))

    def test_disjoint_foreign_invalid_input_and_missing_parent_are_irrelevant(self):
        foreign = fixtures.add_spec(self.root, '002-y')
        peer = self.add_unit('foreign', 1, spec=foreign)
        path = peer / 'manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        manifest['targets'] = ['src/check.py']
        manifest['parents'] = ['absent:missing']
        path.write_text(json.dumps(manifest), encoding='utf-8')
        self.assertEqual(self.check(), [])
        manifest['inputs'] = 'invalid typed input'
        path.write_text(json.dumps(manifest), encoding='utf-8')
        self.assertEqual(self.check(), [])

    def test_foreign_invalid_input_cannot_hide_an_overlapping_target(self):
        foreign = fixtures.add_spec(self.root, '002-y')
        peer = self.add_unit('foreign', 1, spec=foreign)
        path = peer / 'manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        manifest['inputs'] = 'invalid typed input'
        path.write_text(json.dumps(manifest), encoding='utf-8')
        self.assertTrue(self.check())

    def test_foreign_unknown_targets_are_indeterminate_not_disjoint(self):
        foreign = fixtures.add_spec(self.root, '002-y')
        peer = self.add_unit('foreign', 1, spec=foreign)
        path = peer / 'manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        manifest['targets'] = {'not': 'an array'}
        path.write_text(json.dumps(manifest), encoding='utf-8')
        self.assertTrue(self.check())

    def test_valid_selected_hardlink_with_disjoint_foreign_peer_passes(self):
        try:
            os.link(self.root / 'src/billing.py', self.root / 'src/unclaimed.py')
        except OSError as exc:
            self.skipTest(f'Hardlinks unavailable: {exc}')
        foreign = fixtures.add_spec(self.root, '002-y')
        peer = self.add_unit('disjoint', 1, spec=foreign)
        path = peer / 'manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        manifest['targets'] = ['src/check.py']
        path.write_text(json.dumps(manifest), encoding='utf-8')
        self.assertEqual(self.check(targets=['src/billing.py']), [])

    def test_cross_spec_unapproved_descendant_does_not_fall_back(self):
        foreign = fixtures.add_spec(self.root, '002-y')
        self.add_unit('descendant', 1, [f'{self.base.name}:change'], spec=foreign)
        self.assertTrue(self.check())

    def test_selected_descendant_of_approved_foreign_ancestor_passes(self):
        foreign = fixtures.add_spec(self.root, '002-y')
        self.approve_legacy(self.root, foreign, spec='002-y')
        self.add_unit('ancestor', 1, spec=foreign)
        self.approve_unit('ancestor', spec=foreign)
        path = self.unit / 'manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        manifest['parents'] = ['002-y:ancestor']
        path.write_text(json.dumps(manifest), encoding='utf-8')
        self.approve_unit('change')
        self.assertEqual(self.check(), [])

    def test_corrupt_manifest_and_missing_declared_input_fail_closed(self):
        path = self.unit / 'manifest.json'
        content = path.read_text(encoding='utf-8')
        path.write_text('{', encoding='utf-8')
        self.assertTrue(self.check())
        manifest = json.loads(content)
        manifest['inputs'] = ['missing/input.py']
        path.write_text(json.dumps(manifest), encoding='utf-8')
        self.assertTrue(self.check())

    def test_real_parent_dependency_needs_approval(self):
        self.add_unit('dependent', 2, [f'{self.base.name}:change'])
        self.approve_unit('dependent')
        self.assertEqual(self.check('dependent'), [])
        with (self.unit / 'plan.md').open('a', encoding='utf-8') as handle:
            handle.write('Changed dependency\n')
        self.assertTrue(self.check('dependent'))

    def test_missing_parent_and_legacy_schema_are_refused(self):
        path = self.unit / 'manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        manifest['parents'] = ['missing:unit']
        path.write_text(json.dumps(manifest), encoding='utf-8')
        self.assertTrue(self.check())
        manifest['parents'] = []
        manifest['schema_version'] = 1
        for key in ('version', 'inputs', 'config', 'visual_refs'):
            manifest.pop(key)
        path.write_text(json.dumps(manifest), encoding='utf-8')
        self.assertTrue(self.check())

    def test_own_static_errors_are_not_ignored(self):
        (self.unit / 'plan.md').unlink()
        self.assertTrue(self.check())

    def test_reapproved_invalid_task_structure_still_blocks(self):
        path = self.unit / 'tasks.md'
        path.write_text(path.read_text(encoding='utf-8').replace('Tokens (est): 60k', 'Tokens (est): missing'),
                        encoding='utf-8')
        self.approve_unit('change')
        self.assertTrue(any(v['rule'] == 'R1' for v in self.check()))

    def test_base_visual_debt_is_not_a_historical_quote_exception(self):
        with (self.base / 'spec.md').open('a', encoding='utf-8') as handle:
            handle.write('\n## Visual debt\n\n| Codes | Blocks spec | Status | Mockup source |\n'
                         '|---|---|---|---|\n| SCREEN-99 | 001-x | open | |\n')
        self.assertTrue(any(v['rule'] == 'R4' for v in self.check()))

    def test_cli_explicit_build_mode_and_no_implicit_global_bypass(self):
        with mock.patch.object(status.ev, 'find_root', return_value=self.root):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                result = status.main(['rules', 'check', str(self.base), '--unit', 'change',
                                      '--phase', 'build', '--target', 'src/billing.py'])
            self.assertEqual(result, 0, output.getvalue())
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(status.main(['rules', 'check', str(self.base), '--unit', 'change']), 2)

