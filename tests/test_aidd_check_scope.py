"""Explicit native unit structural checks; no product or database execution."""
import contextlib
import io
import json
import subprocess
from types import SimpleNamespace
from unittest import mock

from tests import test_aidd_status as fixtures
from tests import test_aidd_unit_build_gate as unit_fixtures
import aidd_check_scope as scopes
import aidd_readiness as readiness
import check_spec


class CheckScopeTests(fixtures.EvBase):
    add_unit = unit_fixtures.UnitBuildGate.add_unit
    approve_unit = unit_fixtures.UnitBuildGate.approve_unit

    def setUp(self):
        super().setUp()
        self.tmp, self.root, self.base = fixtures.make_project()
        self.addCleanup(self.tmp.cleanup)
        self.unit = self.add_unit('change', 1)

    def selected(self):
        return scopes.resolve_check_scope(self.base, 'change')

    def test_native_selection_uses_real_root(self):
        scope = self.selected()
        self.assertEqual(scope.root, self.root.resolve())
        self.assertEqual(scope.directory, self.unit.resolve())
        with mock.patch.object(scopes.aidd_rules, 'check_spec_dir', return_value=[]) as check:
            scopes.structural_rules(scope)
        check.assert_called_once_with(self.unit.resolve(), root=self.root.resolve(), static_only=True)

    def test_nested_check_finds_and_observes_project_component_index(self):
        index = self.root / 'design-system' / 'components-index.md'
        index.parent.mkdir(exist_ok=True)
        index.write_text('# Real project component index\n', encoding='utf-8')
        self.assertIn(index, check_spec._component_index_paths(self.unit, self.root))
        scope = self.selected()
        observed = readiness.snapshot(scope.directory, scope)
        self.assertIn('shared-evidence/design-system/components-index.md', observed)

    def test_direct_nested_path_requires_explicit_selection(self):
        with self.assertRaises(ValueError):
            scopes.resolve_check_scope(self.unit)

    def test_unknown_and_escaping_identity_fail(self):
        for name in ('absent', '../change', 'other:change', '/change'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                scopes.resolve_check_scope(self.base, name)

    def test_malformed_or_wrong_manifest_identity_fails(self):
        path = self.unit / 'manifest.json'
        original = path.read_text(encoding='utf-8')
        path.write_text('{broken', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.selected()
        data = json.loads(original)
        data['spec_id'] = 'other'
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(ValueError):
            self.selected()

    def test_manifest_must_seal_required_documents(self):
        path = self.unit / 'manifest.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['paths'] = [name for name in data['paths'] if not name.endswith('/tasks.md')]
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(ValueError):
            self.selected()

    def test_manifest_escape_is_rejected(self):
        path = self.unit / 'manifest.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['inputs'] = ['../outside.md']
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(ValueError):
            self.selected()

    def test_schema_one_does_not_silently_use_legacy_consent(self):
        path = self.unit / 'manifest.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        for name in ('version', 'inputs', 'config', 'visual_refs'):
            data.pop(name)
        data['schema_version'] = 1
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(ValueError):
            self.selected()

    def test_pending_native_consent_is_distinct_and_deferred(self):
        state = scopes.consent_states(self.selected())[0]
        self.assertEqual(state['state'], 'pending')
        output = f"1. R6 Unit {state['unit']} native owner consent pending. → Review it.\n"
        actionable, deferred = readiness.preapproval_findings(output, 'Approved: PENDING')
        self.assertEqual(actionable, [])
        self.assertEqual(len(deferred), 1)

    def test_changed_native_consent_is_invalid_not_deferred(self):
        self.approve_unit('change')
        self.assertEqual(scopes.consent_states(self.selected())[0]['state'], 'approved')
        with (self.unit / 'plan.md').open('a', encoding='utf-8') as stream:
            stream.write('\nChanged behavior.\n')
        self.assertEqual(scopes.consent_states(self.selected())[0]['state'], 'invalid')
        gaps, deferred = readiness.preapproval_findings(
            f'1. R6 Unit {self.base.name}:change native owner consent invalid.\n', 'Approved: PENDING')
        self.assertEqual(len(gaps), 1)
        self.assertEqual(deferred, [])

    def test_sibling_does_not_supply_selected_consent(self):
        self.add_unit('sibling', 2)
        self.approve_unit('sibling')
        self.assertEqual(scopes.consent_states(self.selected())[0]['state'], 'pending')

    def test_native_approval_replaces_only_legacy_r6(self):
        self.approve_unit('change')
        findings = [{'rule': 'R6', 'message': 'legacy'}, {'rule': 'R2', 'message': 'real gap'}]
        with mock.patch.object(scopes.aidd_rules, 'check_spec_dir', return_value=findings):
            self.assertEqual(scopes.structural_rules(self.selected()), findings[1:])

    def test_readiness_forwards_unit_and_fingerprints_manifest(self):
        with mock.patch.object(readiness.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as run:
            report = readiness.report(self.base, 'change')
        self.assertEqual(run.call_args.args[0][-3:], [str(self.base.resolve()), '--unit', 'change'])
        key = f'unit-input/specs/{self.base.name}/amendments/change/manifest.json'
        self.assertEqual(len(report['observed_input_sha256'][key]), 64)
        self.assertEqual(report['scope']['unit'], f'{self.base.name}:change')

    def test_manifest_changed_during_report_is_unstable(self):
        def change(*args, **kwargs):
            path = self.unit / 'manifest.json'
            data = json.loads(path.read_text(encoding='utf-8'))
            data['version'] = 'v2'
            path.write_text(json.dumps(data), encoding='utf-8')
            return subprocess.CompletedProcess([], 0, '', '')
        with mock.patch.object(readiness.subprocess, 'run', side_effect=change):
            report = readiness.report(self.base, 'change')
        self.assertEqual(report['status'], 'unstable')

    def test_invalid_consent_cannot_be_checked_even_with_zero_checker(self):
        self.approve_unit('change')
        with (self.unit / 'plan.md').open('a', encoding='utf-8') as stream:
            stream.write('\nModified after approval.\n')
        with mock.patch.object(readiness.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')):
            report = readiness.report(self.base, 'change')
        self.assertEqual(report['status'], 'gaps')

    def test_pending_parent_is_observed_without_approving_it(self):
        self.add_unit('child', 2, parents=[f'{self.base.name}:change'])
        self.approve_unit('child')
        scope = scopes.resolve_check_scope(self.base, 'child')
        states = {row['unit']: row['state'] for row in scopes.consent_states(scope)}
        self.assertEqual(states[f'{self.base.name}:change'], 'pending')
        self.assertEqual(states[f'{self.base.name}:child'], 'approved')

    def test_base_scope_retains_legacy_rule_findings(self):
        scope = scopes.resolve_check_scope(self.base)
        findings = [{'rule': 'R6', 'message': 'legacy pending'}]
        with mock.patch.object(scopes.aidd_rules, 'check_spec_dir', return_value=findings):
            self.assertEqual(scopes.structural_rules(scope), findings)

    def test_unit_stamp_is_rejected_without_writes(self):
        original = (self.unit / 'tasks.md').read_bytes()
        with mock.patch('sys.argv', ['check_spec.py', str(self.base), '--unit', 'change', '--stamp-contract']), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as exit_code:
                check_spec.main()
        self.assertEqual(exit_code.exception.code, 2)
        self.assertEqual((self.unit / 'tasks.md').read_bytes(), original)

    def test_cli_forwards_exact_unit_to_both_scripts(self):
        from aidd import cli
        args = SimpleNamespace(spec_dir=str(self.base), unit='change', output=None)
        with mock.patch.object(cli, '_run', return_value=0) as run:
            cli.cmd_check(args)
            run.assert_called_once_with('check_spec.py', [str(self.base), '--unit', 'change'])
        with mock.patch.object(cli, '_run', return_value=0) as run:
            cli.cmd_readiness(args)
            run.assert_called_once_with('aidd_readiness.py', [str(self.base), '--unit', 'change'])
