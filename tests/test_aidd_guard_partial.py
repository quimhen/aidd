import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from skill.scripts import aidd_evidence as ev, aidd_guard as guard, aidd_rules as rules, aidd_status as status


class GuardPartialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.spec = self.root / 'specs' / 's'
        self.spec.mkdir(parents=True)
        (self.root / 'a.py').write_text('print("verification passed: " + "x" * 300)\n', encoding='utf-8')
        (self.spec / 'tasks.md').write_text('| Task | Target file |\n|---|---|\n| T-01 | `a.py` |\n', encoding='utf-8')
        (self.spec / 'spec.md').write_text('## Verification\n| # | Command | Expected | Covers | Inputs | Reuse | Environment |\n'
            '|---|---|---|---|---|---|---|\n'
            '| V-1 | python a.py | exit 0 | T-01 | a.py | hermetic | contract:offline;vars=none;packages=none |\n', encoding='utf-8')
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', '-C', str(self.root), 'config', 'core.autocrlf', 'false'], check=True)
        subprocess.run(['git', '-C', str(self.root), 'add', 'a.py'], check=True)

    def run_verify(self):
        with patch.object(status.ev, 'find_root', return_value=self.root), \
             patch.object(status, '_resolve_spec', return_value=self.spec), contextlib.redirect_stdout(io.StringIO()) as out:
            rc = status.cmd_verify(str(self.spec), task_ids=['T-01'])
        self.assertEqual(rc, 0, out.getvalue())
        return ev.events(self.root, kind='task_verify_run')[-1]

    def test_authentic_runner_receipt_accepts_only_exact_staged_blob(self):
        event = self.run_verify()
        self.assertTrue(event['detail']['guard_scope'])
        self.assertFalse(event['detail']['scope_attested'])
        self.assertTrue(guard._partial_passes(self.root, self.spec, ['a.py'], status, ev, rules, 0))
        (self.root / 'a.py').write_text('print("changed")\n', encoding='utf-8')
        subprocess.run(['git', '-C', str(self.root), 'add', 'a.py'], check=True)
        self.assertFalse(guard._partial_passes(self.root, self.spec, ['a.py'], status, ev, rules, 0))

    def test_tampered_report_and_unmapped_paths_are_blocked(self):
        event = self.run_verify()
        self.assertFalse(guard._partial_passes(self.root, self.spec, ['other.py'], status, ev, rules, 0))
        report = self.spec / event['detail']['results'][0]['evidence']
        report.write_text('changed', encoding='utf-8')
        self.assertFalse(guard._partial_passes(self.root, self.spec, ['a.py'], status, ev, rules, 0))

    def test_older_full_failure_does_not_bypass_newer_full_failure(self):
        event = self.run_verify()
        self.assertFalse(guard._partial_passes(self.root, self.spec, ['a.py'], status, ev, rules, event['ts'] + 1))

    def test_newer_failed_affected_task_blocks_but_unrelated_does_not(self):
        self.run_verify()
        self.assertTrue(ev.append(self.root, 'test', 'task_verify_run', spec='s', tasks=['T-02'], ok=False))
        self.assertTrue(guard._partial_passes(self.root, self.spec, ['a.py'], status, ev, rules, 0))
        self.assertTrue(ev.append(self.root, 'test', 'task_verify_run', spec='s', tasks=['T-01'], ok=False))
        self.assertFalse(guard._partial_passes(self.root, self.spec, ['a.py'], status, ev, rules, 0))

    def test_partial_cannot_suppress_other_gates(self):
        state = {'spec': 's', 'tasks': {'approval': 'pending'}, 'why_blocked': [],
                 'verification': {'status': 'failed'}}
        findings = guard._spec_findings(self.root, self.spec, state, ['a.py'], partial_ok=True)
        self.assertIn('R6', {row['rule'] for row in findings})


if __name__ == '__main__':
    unittest.main()
