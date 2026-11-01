import hashlib
import json
import subprocess
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from skill.scripts import aidd_rules
from skill.scripts.aidd_unit_audit import _task_candidates, administrative_only_task_paths, codex_provenance, compare_snapshots, domains_for_unit, evaluate_audit, git_changed_paths, legacy_task_map, plan_impact, resolve_spec_id


class UnitAuditIncrementalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.report = self.root / 'report.txt'
        self.report.write_text('independent report', encoding='utf-8')
        self.snapshot = {'format': 'aidd-unit-impact-v3', 'unit': 's:a', 'version': 'v1', 'sequence': 1,
                         'files': {'targets': {'a.py': 'b' * 64},
                         'paths': {'tasks.md': 'c' * 64}, 'inputs': {}, 'config': {}, 'visual': {}},
                         'parents': {}, 'visual_refs': []}
        self.resign(self.snapshot)
        self.event = {'kind': 'unit_audit', 'detail': {'unit': 's:a', 'domain': 'functional',
                      'scope': self.snapshot, 'rules_version': 'r1', 'environment_id': 'e1',
                      'report_path': 'report.txt', 'report_sha256': hashlib.sha256(self.report.read_bytes()).hexdigest(),
                      'auditor_id': 'agent-a', 'implementer_ids': ['agent-b'],
                      'dispatch_id': 'dispatch-1', 'outcome': 'PASS'}}
        self.attest = lambda e: e is self.event

    def resign(self, value):
        payload = {k: v for k, v in value.items() if k != 'digest'}
        value['digest'] = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                                    separators=(',', ':')).encode()).hexdigest()

    def test_unchanged_scoped_audit_is_retained(self):
        (self.root / 'unrelated.py').write_text('changed', encoding='utf-8')
        self.assertEqual(compare_snapshots(self.snapshot, deepcopy(self.snapshot)), [])
        self.assertEqual(evaluate_audit(self.root, self.snapshot, 'functional', 'r1', 'e1',
                                        [self.event], self.attest)['status'], 'current')

    def test_own_and_parent_changes_are_reported(self):
        changed = deepcopy(self.snapshot)
        changed['files']['targets']['a.py'] = 'd' * 64
        changed['parents']['s:p'] = 'e' * 64
        self.resign(changed)
        self.assertEqual(set(compare_snapshots(self.snapshot, changed)), {'targets:a.py', 'parent:s:p'})
        self.assertEqual(evaluate_audit(self.root, changed, 'functional', 'r1', 'e1',
                                        [self.event], self.attest)['status'], 'stale')

    def test_missing_provenance_and_changed_rules_or_environment_never_pass(self):
        for version, env, verifier in [('r1', 'e1', None), ('r2', 'e1', self.attest),
                                       ('r1', 'e2', self.attest)]:
            with self.subTest(version=version, env=env, verifier=verifier):
                self.assertNotEqual(evaluate_audit(self.root, self.snapshot, 'functional', version, env,
                                                   [self.event], verifier)['status'], 'current')

    def test_untrusted_stale_claim_is_indeterminate_not_a_reaudit_directive(self):
        changed = deepcopy(self.snapshot)
        changed['files']['targets']['a.py'] = 'd' * 64
        self.resign(changed)
        result = evaluate_audit(self.root, changed, 'functional', 'r1', 'e1', [self.event], None)
        self.assertEqual(result['status'], 'indeterminate')

    def test_latest_failure_or_missing_verdict_never_falls_back_to_prior_pass(self):
        for outcome, expected in [('FAIL', 'failed'), (None, 'indeterminate')]:
            latest = deepcopy(self.event)
            if outcome is None:
                latest['detail'].pop('outcome')
            else:
                latest['detail']['outcome'] = outcome
            result = evaluate_audit(self.root, self.snapshot, 'functional', 'r1', 'e1',
                                    [self.event, latest], lambda event: True)
            self.assertEqual(result['status'], expected)

    def test_latest_authenticated_missing_or_tampered_report_blocks_old_pass(self):
        bad_report = self.root / 'tampered.txt'
        bad_report.write_text('different', encoding='utf-8')
        for path in ('missing.txt', 'tampered.txt'):
            with self.subTest(path=path):
                latest = deepcopy(self.event)
                latest['detail'].update(outcome='FAIL', report_path=path, dispatch_id='later')
                result = evaluate_audit(self.root, self.snapshot, 'functional', 'r1', 'e1',
                                        [self.event, latest], lambda event: True)
                self.assertEqual(result['status'], 'indeterminate')
                self.assertEqual(result['dispatch_id'], 'later')

    def test_same_implementer_or_tampered_report_never_passes(self):
        self.event['detail']['implementer_ids'] = ['agent-a']
        self.assertNotEqual(evaluate_audit(self.root, self.snapshot, 'functional', 'r1', 'e1',
                                           [self.event], self.attest)['status'], 'current')
        self.event['detail']['implementer_ids'] = ['agent-b']
        self.report.write_text('tampered', encoding='utf-8')
        self.assertNotEqual(evaluate_audit(self.root, self.snapshot, 'functional', 'r1', 'e1',
                                           [self.event], self.attest)['status'], 'current')

    def test_legacy_or_missing_scope_is_indeterminate(self):
        old = deepcopy(self.snapshot)
        old['format'] = 'legacy'
        self.assertEqual(evaluate_audit(self.root, old, 'functional', 'r1', 'e1',
                                        [self.event], self.attest)['status'], 'indeterminate')

    def test_plan_retains_valid_unit_and_marks_only_changed_descendant(self):
        spec = self.root / 'specs' / 's'
        spec.mkdir(parents=True)
        (spec / 'spec.md').write_text('# spec\n', encoding='utf-8')
        first = SimpleNamespace(spec_id='s', key='s:a', targets=('a.py',), visual_refs=())
        child = SimpleNamespace(spec_id='s', key='s:b', targets=('b.py',), visual_refs=())
        child_snapshot = deepcopy(self.snapshot)
        child_snapshot.update(unit='s:b', parents={'s:a': '1' * 64})
        self.resign(child_snapshot)
        child_event = deepcopy(self.event)
        child_event['detail'].update(unit='s:b', scope=deepcopy(child_snapshot), dispatch_id='dispatch-2')
        snapshots = {'s:a': self.snapshot, 's:b': child_snapshot}
        units = SimpleNamespace(discover_units=lambda root: [first, child],
                                unit_impact_snapshot=lambda unit, root: snapshots[unit.key])
        attest = lambda event: event in (self.event, child_event)
        before = plan_impact(self.root, 's', [self.event, child_event], aidd_rules, units,
                             rules_version='r1', environment_id='e1', provenance_verifier=attest)
        self.assertTrue(all(item['domains']['functional']['status'] == 'current' for item in before['units']))
        changed = deepcopy(child_snapshot)
        changed['parents']['s:a'] = '2' * 64
        self.resign(changed)
        snapshots['s:b'] = changed
        after = plan_impact(self.root, 's', [self.event, child_event], aidd_rules, units,
                            rules_version='r1', environment_id='e1', provenance_verifier=attest)
        self.assertEqual(after['units'][0]['domains']['functional']['status'], 'current')
        self.assertEqual(after['units'][1]['domains']['functional']['status'], 'stale')
        self.assertEqual(after['units'][1]['domains']['functional']['changes'], ['parent:s:a'])

    def test_codex_lifecycle_does_not_prove_assignment_or_independence(self):
        self.event['detail'].update(session_id='session', turn_id='turn')
        start = {'ts': 10, 'detail': {'phase': 'start', 'turn_id': 'turn', 'agent_id': 'agent-a',
                                      'agent_type': 'auditor'}}
        stop = {'ts': 11, 'detail': {'phase': 'stop', 'turn_id': 'turn', 'agent_id': 'agent-a',
                                     'agent_type': 'auditor', 'continued': False,
                                     'result_sha256': self.event['detail']['report_sha256']}}
        evidence = SimpleNamespace(events=lambda root, session, kind: [start, stop])
        outcome = codex_provenance(self.root, self.event, evidence)
        self.assertFalse(outcome['verified'])
        self.assertIn('implementer identity', outcome['reason'])
        trusted = codex_provenance(self.root, self.event, evidence, lambda event, begin, end: True)
        self.assertTrue(trusted['verified'])
        stop['detail']['result_sha256'] = '0' * 64
        self.assertFalse(codex_provenance(self.root, self.event, evidence,
                                          lambda event, begin, end: True)['verified'])

    def test_security_domain_includes_declared_dependency_not_only_target(self):
        spec = self.root / 'specs' / 's'
        spec.mkdir(parents=True)
        (spec / 'spec.md').write_text('# spec\n', encoding='utf-8')
        unit = SimpleNamespace(targets=('logic.py',), inputs=('auth/permissions.py',), config=(), visual_refs=())
        self.assertIn('security', domains_for_unit(unit, aidd_rules, spec))
        unit.inputs = ()
        self.assertIn('security', domains_for_unit(unit, aidd_rules, spec))

    def test_spec_argument_accepts_id_and_project_path_but_rejects_escape(self):
        spec = self.root / 'specs' / 's'
        spec.mkdir(parents=True)
        (spec / 'nested').mkdir()
        self.assertEqual(resolve_spec_id(self.root, 's'), 's')
        self.assertEqual(resolve_spec_id(self.root, 'specs/s'), 's')
        self.assertEqual(resolve_spec_id(self.root, str(spec)), 's')
        with self.assertRaises(ValueError):
            resolve_spec_id(self.root, str(self.root))
        with self.assertRaises(ValueError):
            resolve_spec_id(self.root, 'specs/s/nested')

    def test_legacy_bootstrap_maps_disjoint_tasks_without_claiming_old_audit(self):
        spec = self.root / 'specs' / 's'
        spec.mkdir(parents=True)
        (spec / 'tasks.md').write_text('| Task | Target file | Status |\n|---|---|---|\n'
                                       '| T-1 | `a.py` | done |\n| T-2 | `b.py` | done |\n', encoding='utf-8')
        (self.root / 'a.py').write_text('first', encoding='utf-8')
        (self.root / 'b.py').write_text('second', encoding='utf-8')
        first = legacy_task_map(self.root, spec, aidd_rules)
        self.assertEqual([item['task'] for item in first], ['T-1', 'T-2'])
        self.assertTrue(all(item['status'] == 'indeterminate' for item in first))
        (self.root / 'a.py').write_text('changed', encoding='utf-8')
        second = legacy_task_map(self.root, spec, aidd_rules)
        self.assertNotEqual(first[0]['targets']['a.py'], second[0]['targets']['a.py'])
        self.assertEqual(first[1]['targets']['b.py'], second[1]['targets']['b.py'])
        self.assertEqual([item['task'] for item in legacy_task_map(self.root, spec, aidd_rules, 'T-2')], ['T-2'])

    def test_legacy_bootstrap_does_not_hash_sensitive_targets(self):
        spec = self.root / 'specs' / 's'
        spec.mkdir(parents=True)
        (spec / 'tasks.md').write_text('| Task | Target file |\n|---|---|\n| T-1 | `.env` |\n', encoding='utf-8')
        (self.root / '.env').write_text('SECRET=do-not-expose', encoding='utf-8')
        target = legacy_task_map(self.root, spec, aidd_rules)[0]['targets']['.env']
        self.assertEqual(target['status'], 'indeterminate')
        self.assertNotIn('sha256', target)

    def test_legacy_multi_file_detail_does_not_pull_unrelated_paths(self):
        spec = self.root / 'specs' / 's'
        spec.mkdir(parents=True)
        (spec / 'tasks.md').write_text(
            '| Task | Target file | Status |\n|---|---|---|\n'
            '| T-1 | `a.py` | done |\n| T-2 | `b.py` | done |\n'
            '### T-1 — One\n- **Read first:** `unrelated.py`\n'
            '- **Files to change:** `a.py`, `fixture.py` (create).\n'
            '- **Verify:** `other.py`\n'
            '### T-2 — Two\n- **Files to change:** `b.py`\n', encoding='utf-8')
        for name in ('a.py', 'b.py', 'fixture.py', 'unrelated.py', 'other.py'):
            (self.root / name).write_text(name, encoding='utf-8')
        result = legacy_task_map(self.root, spec, aidd_rules, 'T-1')
        self.assertEqual(set(result[0]['targets']), {'a.py', 'fixture.py'})

    def test_changed_legacy_selection_does_not_read_unaffected_target(self):
        spec = self.root / 'specs' / 's'
        spec.mkdir(parents=True)
        (spec / 'tasks.md').write_text('| Task | Target file |\n|---|---|\n'
                                       '| T-1 | `a.py` |\n| T-2 | `b.py` |\n', encoding='utf-8')
        (self.root / 'a.py').write_text('a', encoding='utf-8')
        (self.root / 'b.py').write_text('b', encoding='utf-8')
        reads = []
        original = Path.open
        def tracked(path, *args, **kwargs):
            reads.append(path)
            return original(path, *args, **kwargs)
        from unittest.mock import patch
        with patch.object(Path, 'open', tracked):
            result = legacy_task_map(self.root, spec, aidd_rules, changed_paths={'a.py'})
        self.assertEqual([entry['task'] for entry in result], ['T-1'])
        self.assertNotIn(self.root / 'b.py', reads)
        self.assertEqual(_task_candidates(['specs/s/tasks.md', 'specs/other/tasks.md'], 's'),
                         ['specs/s/tasks.md'])

    def test_git_changed_detects_commit_stage_delete_rename_and_untracked(self):
        def git(*args):
            return subprocess.run(['git', *args], cwd=self.root, check=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()
        git('init', '-q')
        for name in ('committed.py', 'old.py', 'deleted.py', 'unstaged.py'):
            (self.root / name).write_text(name, encoding='utf-8')
        git('add', '--all')
        git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'base')
        base = git('rev-parse', 'HEAD')
        (self.root / 'committed.py').write_text('changed and committed', encoding='utf-8')
        git('add', 'committed.py')
        git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'second')
        (self.root / 'old.py').rename(self.root / 'new.py')
        (self.root / 'deleted.py').unlink()
        git('add', '--all')
        (self.root / 'unstaged.py').write_text('unstaged', encoding='utf-8')
        (self.root / 'untracked.py').write_text('untracked', encoding='utf-8')
        worktree = set(git_changed_paths(self.root))
        self.assertTrue({'old.py', 'new.py', 'deleted.py', 'unstaged.py', 'untracked.py'} <= worktree)
        self.assertNotIn('committed.py', worktree)
        self.assertIn('committed.py', git_changed_paths(self.root, base))
        with self.assertRaises(ValueError):
            git_changed_paths(self.root, '--all')

    def test_git_status_writeback_is_filtered_without_hiding_real_changes(self):
        def git(*args):
            return subprocess.run(['git', *args], cwd=self.root, check=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()
        git('init', '-q')
        task = self.root / 'specs/s/tasks.md'
        task.parent.mkdir(parents=True)
        baseline = ('Approved: PENDING\n| Task | Requirement | Status | Tracker ref |\n|---|---|---|---|\n'
                    '| T-01 | Build A | pending | old |\n')
        task.write_text(baseline, encoding='utf-8')
        git('add', 'specs/s/tasks.md')
        git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'base')
        base = git('rev-parse', 'HEAD')
        changed = 'specs/s/tasks.md'
        task.write_text(baseline.replace('| pending | old |', '| done | new |'), encoding='utf-8')
        self.assertEqual(administrative_only_task_paths(self.root, [changed], aidd_rules, base), {changed})
        git('add', changed)
        task.write_text(baseline, encoding='utf-8')
        self.assertEqual(administrative_only_task_paths(self.root, [changed], aidd_rules, base), {changed})
        task.write_text(baseline.replace('Build A', 'Build B'), encoding='utf-8')
        self.assertEqual(administrative_only_task_paths(self.root, [changed], aidd_rules, base), set())
        task.write_text(baseline.replace('Approved: PENDING', 'Approved: different'), encoding='utf-8')
        self.assertEqual(administrative_only_task_paths(self.root, [changed], aidd_rules, base), set())
        self.assertEqual(administrative_only_task_paths(self.root, [changed], aidd_rules, 'deadbeef'), set())
