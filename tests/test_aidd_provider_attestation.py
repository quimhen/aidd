import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from skill.scripts import aidd_evidence as evidence, aidd_guard as guard, aidd_rules as rules, aidd_provider_attestation as provider


class ProviderAttestationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.spec = self.root / 'specs' / 's'
        (self.spec / 'evidence').mkdir(parents=True)
        (self.root / 'a.py').write_text('print(1)\n', encoding='utf-8')
        (self.root / 't.py').write_text('print(2)\n', encoding='utf-8')
        self.coverage = {'format': 'aidd-provider-coverage-v1', 'spec': 's', 'unit': 'u1', 'provider': 'sample',
                         'tasks': {'T-01': {'targets': ['a.py'], 'tests': ['t.py'], 'rows': ['V-1']}}}
        (self.root / 'coverage.json').write_text(json.dumps(self.coverage), encoding='utf-8')
        source = '''import hashlib, json, pathlib, sys, os
if os.environ.get('PYTHONPATH') or os.environ.get('PGHOST'): sys.exit(8)
if len(sys.argv) != 2: sys.exit(9)
root = pathlib.Path.cwd()
coverage = json.loads((root / 'coverage.json').read_text())
policy = json.loads((root / 'policy.json').read_text())
files = policy['inputs']
inputs = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files}
artifact = 'specs/s/evidence/synthetic-result.txt'
(root / artifact).write_text('synthetic run passed')
data = {'format':'aidd-provider-observation-v1','provider':'sample','status':'verified',
        'environment':policy['environment'],'inputs':inputs,'tasks':coverage['tasks'],
        'results':[{'row':'V-1','status':'PASS','assertions':1,'skipped':0}],
        'artifacts':{artifact:hashlib.sha256((root / artifact).read_bytes()).hexdigest()}}
pathlib.Path(sys.argv[1]).write_text(json.dumps(data, sort_keys=True))
'''
        (self.root / 'provider.py').write_text(source, encoding='utf-8')
        self.policy = {'format': 'aidd-provider-policy-v1', 'provider': 'sample', 'executable': 'provider.py',
                       'executable_sha256': hashlib.sha256((self.root / 'provider.py').read_bytes()).hexdigest(),
                       'python_sha256': hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
                       'coverage_sha256': hashlib.sha256((self.root / 'coverage.json').read_bytes()).hexdigest(),
                       'environment': {'engine': 'synthetic-1'}, 'variables': {name: hashlib.sha256(os.environ[name].encode()).hexdigest() for name in ('PATH', 'SYSTEMROOT') if name in os.environ}, 'catalogs': [], 'argv': ['{receipt}'],
                       'inputs': ['coverage.json', 'policy.json', 'provider.py', 'a.py', 't.py']}
        (self.root / 'policy.json').write_text(json.dumps(self.policy), encoding='utf-8')
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', '-C', str(self.root), 'config', 'core.autocrlf', 'false'], check=True)
        subprocess.run(['git', '-C', str(self.root), 'add', '.'], check=True)
        self.approval = lambda spec, coverage, policy: spec == 's'

    def run_real_child(self):
        provider.run_provider(self.root, 'coverage.json', 'policy.json', self.approval, evidence)
        return evidence.events(self.root, kind='provider_verify_run')[-1]

    def test_environment_isolated_and_catalog_addition_invalidates(self):
        folder = self.root / 'migrations'
        folder.mkdir()
        (folder / 'one.sql').write_text('one', encoding='utf-8')
        self.policy['inputs'].append('migrations/one.sql')
        self.policy['catalogs'] = [{'directory': 'migrations', 'suffix': '.sql', 'contains': '',
                                    'exclude_suffix': '', 'present': True, 'active': True}]
        (self.root / 'policy.json').write_text(json.dumps(self.policy), encoding='utf-8')
        subprocess.run(['git', '-C', str(self.root), 'add', '.'], check=True)
        with patch.dict(os.environ, {'PYTHONPATH': 'untrusted', 'PGHOST': 'untrusted'}):
            event = self.run_real_child()
        self.assertTrue(provider.evaluate_event(self.root, event, ['a.py'], self.approval)['eligible'])
        (folder / 'two.sql').write_text('two', encoding='utf-8')
        self.assertFalse(provider.evaluate_event(self.root, event, ['a.py'], self.approval)['eligible'])
        subprocess.run(['git', '-C', str(self.root), 'add', '.'], check=True)
        self.assertFalse(provider.evaluate_event(self.root, event, ['a.py'], self.approval)['eligible'])

    def test_failed_evidence_append_leaves_pending_marker(self):
        from types import SimpleNamespace
        self.policy['argv'] = ['{receipt}', 'fail']
        (self.root / 'policy.json').write_text(json.dumps(self.policy), encoding='utf-8')
        subprocess.run(['git', '-C', str(self.root), 'add', 'policy.json'], check=True)
        unavailable = SimpleNamespace(events=lambda *a, **k: [], append=lambda *a, **k: False)
        with self.assertRaises(ValueError):
            provider.run_provider(self.root, 'coverage.json', 'policy.json', self.approval, unavailable)
        self.assertTrue((self.spec / 'evidence' / 'provider-u1.pending').exists())
        self.assertEqual(guard._latest_partial_failure(self.root, self.spec, ['a.py'], unavailable), float('inf'))

    def test_real_runner_receipt_and_exact_index(self):
        event = self.run_real_child()
        self.assertTrue(provider.evaluate_event(self.root, event, ['a.py'], self.approval)['eligible'])
        self.assertFalse(provider.evaluate_event(self.root, event, ['other.py'], self.approval)['eligible'])
        (self.root / 't.py').write_text('changed test\n', encoding='utf-8')
        self.assertFalse(provider.evaluate_event(self.root, event, ['a.py'], self.approval)['eligible'])

    def test_missing_approval_or_changed_policy_rejected(self):
        with self.assertRaisesRegex(ValueError, 'approval'):
            provider.run_provider(self.root, 'coverage.json', 'policy.json', None, evidence)
        self.assertEqual(evidence.events(self.root, kind='provider_verify_run'), [])
        event = self.run_real_child()
        (self.root / 'coverage.json').write_text('{}', encoding='utf-8')
        self.assertFalse(provider.evaluate_event(self.root, event, ['a.py'], self.approval)['eligible'])

    def test_launched_failed_process_records_failure_not_pass(self):
        self.policy['argv'] = ['{receipt}', 'fail']
        (self.root / 'policy.json').write_text(json.dumps(self.policy), encoding='utf-8')
        subprocess.run(['git', '-C', str(self.root), 'add', 'policy.json'], check=True)
        with self.assertRaises(ValueError):
            provider.run_provider(self.root, 'coverage.json', 'policy.json', self.approval, evidence)
        rows = evidence.events(self.root, kind='provider_verify_run')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['detail']['outcome'], 'FAIL')
        self.assertFalse(provider.evaluate_event(self.root, rows[0], ['a.py'], self.approval)['eligible'])

    def test_index_must_match_observed_bytes_for_every_input(self):
        event = self.run_real_child()
        (self.root / 't.py').write_text('different\n', encoding='utf-8')
        subprocess.run(['git', '-C', str(self.root), 'add', 't.py'], check=True)
        self.assertFalse(provider.evaluate_event(self.root, event, ['a.py'], self.approval)['eligible'])

    def test_unchanged_event_is_reused_without_a_second_process(self):
        self.run_real_child()
        result = provider.run_provider(self.root, 'coverage.json', 'policy.json', self.approval, evidence)
        self.assertTrue(result['reused'])
        self.assertEqual(len(evidence.events(self.root, kind='provider_verify_run')), 1)

    def test_receipt_cannot_be_changed(self):
        event = self.run_real_child()
        (self.root / event['detail']['observation_path']).write_text('{}', encoding='utf-8')
        self.assertFalse(provider.evaluate_event(self.root, event, ['a.py'], self.approval)['eligible'])

    def test_result_artifact_cannot_be_changed(self):
        event = self.run_real_child()
        (self.spec / 'evidence' / 'synthetic-result.txt').write_text('changed', encoding='utf-8')
        self.assertFalse(provider.evaluate_event(self.root, event, ['a.py'], self.approval)['eligible'])

    def test_missing_rows_skips_and_v4_are_never_authoritative(self):
        inputs = {name: 'a' * 64 for name in self.policy['inputs']}
        observation = {'format': 'aidd-provider-observation-v1', 'provider': 'sample', 'status': 'verified',
                       'environment': self.policy['environment'], 'inputs': inputs, 'tasks': self.coverage['tasks'],
                       'results': [{'row': 'V-1', 'status': 'PASS', 'assertions': 1, 'skipped': 0}],
                       'artifacts': {'specs/s/evidence/a.txt': 'b' * 64}}
        self.assertTrue(provider._observation_valid(observation, self.coverage, self.policy, inputs))
        observation['results'][0]['skipped'] = 1
        self.assertFalse(provider._observation_valid(observation, self.coverage, self.policy, inputs))
        observation['results'] = []
        self.assertFalse(provider._observation_valid(observation, self.coverage, self.policy, inputs))
        self.assertFalse(provider._observation_valid({'format': 'edoc-db-verify-receipt-v4', 'status': 'verified',
                                                      'guard_reusable': False}, self.coverage, self.policy, {}))

    def test_unit_approval_binds_shown_policy_and_guard_uses_real_runner_event(self):
        unit_dir = self.spec / 'amendments' / 'u1'
        unit_dir.mkdir(parents=True)
        task_name = 'specs/s/amendments/u1/tasks.md'
        manifest_name = 'specs/s/amendments/u1/manifest.json'
        self.policy['inputs'] += [task_name, manifest_name]
        (self.root / 'policy.json').write_text(json.dumps(self.policy), encoding='utf-8')
        canonical = lambda obj: json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(',', ':'))
        (unit_dir / 'tasks.md').write_text('# Approved review content\n| Task | Target file |\n|---|---|\n'
            '| T-01 | `a.py` |\n## T-01\n' + canonical(self.coverage) + '\n' + canonical(self.policy)
            + '\n## Verification\n| # | Command | Expected | Covers |\n|---|---|---|---|\n'
            '| V-1 | `aidd provider run --coverage coverage.json --policy policy.json` | exit 0 | T-01 |\n',
            encoding='utf-8')
        manifest = {'schema_version': 2, 'spec_id': 's', 'unit_id': 'u1', 'sequence': 1, 'parents': [],
                    'paths': [task_name, 'coverage.json', 'policy.json'], 'targets': ['a.py'], 'version': 'v1',
                    'inputs': ['t.py'], 'config': ['provider.py'], 'visual_refs': []}
        (unit_dir / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        subprocess.run(['git', '-C', str(self.root), 'add', '.'], check=True)
        approve = provider.unit_approval_verifier(self.root, 'coverage.json', 'policy.json', evidence)
        with patch.object(rules, 'unit_approval_states', return_value=[{'unit': 'u1', 'approved': True}]):
            provider.run_provider(self.root, 'coverage.json', 'policy.json', approve, evidence)
            self.assertTrue(guard._provider_partial_passes(self.root, self.spec, ['a.py'], evidence, 0))
            base_tasks = self.spec / 'tasks.md'
            base_tasks.write_text('| Task | Target file |\n|---|---|\n| T-02 | `a.py` |\n', encoding='utf-8')
            self.assertFalse(guard._provider_partial_passes(self.root, self.spec, ['a.py'], evidence, 0))
            base_tasks.unlink()
            state = {'spec': 's', 'tasks': {'approval': 'valid', 'approval_recorded': True},
                     'why_blocked': [], 'verification': {'status': 'failed', 'ts': 0}}
            with patch.object(guard, '_light_status', return_value=state):
                self.assertEqual(guard._evaluate_owners(self.root, [(self.spec, ['a.py'])], allow_partial=True), [])
                self.assertTrue(guard._evaluate_owners(self.root, [(self.spec, ['a.py'])], allow_partial=False))
                evidence.append(self.root, 'synthetic', 'task_verify_run', spec='s', tasks=['T-01'], ok=False)
                self.assertTrue(guard._evaluate_owners(self.root, [(self.spec, ['a.py'])], allow_partial=True))
            (unit_dir / 'tasks.md').write_text('# Missing reviewed policy\n', encoding='utf-8')
            self.assertFalse(guard._provider_partial_passes(self.root, self.spec, ['a.py'], evidence, 0))


if __name__ == '__main__':
    unittest.main()
