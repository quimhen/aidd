import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from skill.scripts import aidd_unit_audit as audit, aidd_status as status, aidd_evidence as evidence


class LocalUnitReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Test', '-c',
                        'user.email=test@example.test', 'commit', '--allow-empty', '-qm', 'baseline'], check=True)
        (self.root / 'specs' / 's').mkdir(parents=True)
        self.unit = SimpleNamespace(spec_id='s', key='s:a', paths=('tasks.md',), targets=('a.py',),
                                    inputs=(), config=(), visual_refs=())
        self.snapshot = {'format': 'aidd-unit-impact-v3', 'unit': 's:a', 'version': 'v1', 'sequence': 1,
                         'files': {'paths': {'tasks.md': 'a' * 64}, 'targets': {'a.py': 'b' * 64},
                                   'inputs': {}, 'config': {}, 'visual': {}}, 'parents': {}, 'visual_refs': []}
        self.snapshot['digest'] = hashlib.sha256(json.dumps(self.snapshot, sort_keys=True,
            separators=(',', ':')).encode()).hexdigest()
        self.units = SimpleNamespace(unit_impact_snapshot=lambda unit, root: self.snapshot,
                                     discover_unit_scope=lambda root, spec, keys: [self.unit])
        self.rows = []
        self.evidence = SimpleNamespace(append=self.append)

    def append(self, root, session, kind, **detail):
        self.rows.append({'kind': kind, 'detail': detail})
        return True

    def run_fake_child(self, verdict):
        real_popen = subprocess.Popen
        events = [{'type': 'thread.started', 'thread_id': 'fresh-review-thread'},
                  {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(verdict)}},
                  {'type': 'turn.completed'}]
        code = 'import sys; sys.stdin.read(); print(' + repr('\n'.join(json.dumps(e) for e in events)) + ')'
        def launch(cmd, **kwargs):
            if cmd[0] == 'git':
                return real_popen(cmd, **kwargs)
            self.assertEqual(cmd[1:6], ['exec', '--ephemeral', '--sandbox', 'read-only', '--json'])
            return real_popen([sys.executable, '-c', code], **kwargs)
        with patch.object(audit.subprocess, 'Popen', side_effect=launch):
            return audit.run_unit_review(self.root, self.unit, ['functional', 'security'], self.units,
                                         self.evidence, executable=Path(sys.executable), environment_id='env')

    def test_real_child_captures_verdict_and_unchanged_scope_reuses_it(self):
        result = self.run_fake_child({'verdicts': {'functional': 'PASS', 'security': 'FAIL'}, 'findings': []})
        self.assertTrue((self.root / result['report_path']).is_file())
        self.assertEqual(len(self.rows), 2)
        for row, status in zip(self.rows, ['current', 'failed']):
            actual = audit.evaluate_audit(self.root, self.snapshot, row['detail']['domain'], 'unit-audit-v1',
                    'env', [row], lambda event: audit.local_runner_provenance(self.root, event))
            self.assertEqual(actual['status'], status)
        self.assertNotEqual(self.rows[0]['detail']['runner']['pid'], os.getpid())
        (self.root / result['report_path']).write_text('tampered', encoding='utf-8')
        actual = audit.evaluate_audit(self.root, self.snapshot, 'functional', 'unit-audit-v1', 'env',
                self.rows, lambda event: audit.local_runner_provenance(self.root, event))
        self.assertEqual(actual['status'], 'indeterminate')

    def test_missing_or_ambiguous_verdict_creates_no_evidence(self):
        with self.assertRaises(ValueError):
            self.run_fake_child({'verdicts': {'functional': 'PASS'}, 'findings': []})
        self.assertEqual(self.rows, [])

    def test_changed_scope_never_records_a_receipt(self):
        calls = []
        def changing(unit, root):
            calls.append(1)
            if len(calls) == 1:
                return self.snapshot
            return dict(self.snapshot, digest='d' * 64)
        self.units.unit_impact_snapshot = changing
        with self.assertRaisesRegex(ValueError, 'scope or Git HEAD changed'):
            self.run_fake_child({'verdicts': {'functional': 'PASS', 'security': 'PASS'}, 'findings': []})
        self.assertEqual(self.rows, [])

    def test_close_reports_only_noncurrent_unit_domains(self):
        states = [{'unit': 's:a', 'domains': {'functional': {'status': 'current'},
                  'security': {'status': 'stale', 'reason': 'scope changed'}}}]
        with patch.object(status, '_unit_audit_states', return_value=states), \
             patch.object(status.rules, 'unit_approval_states', return_value=[]):
            gaps = status._close_gaps(self.root / 'specs' / 's', self.root)
        unit_gaps = [gap for gap in gaps if 'unit s:a' in gap]
        self.assertEqual(len(unit_gaps), 1)
        self.assertIn('security audit is stale', unit_gaps[0])

    def test_real_evidence_store_preserves_scope_and_verdicts(self):
        self.evidence = evidence
        self.run_fake_child({'verdicts': {'functional': 'PASS', 'security': 'PASS'}, 'findings': []})
        rows = evidence.events(self.root, kind='unit_audit')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['detail']['scope'], self.snapshot)
        self.assertEqual(audit.evaluate_audit(self.root, self.snapshot, 'functional', 'unit-audit-v1', 'env',
            rows, lambda event: audit.local_runner_provenance(self.root, event))['status'], 'current')


if __name__ == '__main__':
    unittest.main()
