"""Regression checks for verification failures observed in b1SycLink."""
import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skill' / 'scripts'))
import aidd_evidence as evidence
import aidd_rules as rules
import aidd_status as status


class VerificationRegressions(unittest.TestCase):
    def test_scoped_scan_after_global_budget_exceeded(self):
        expected = ('git', {'src/a.py': b'a'})
        with patch.object(evidence, '_code_state_scan', side_effect=[evidence._FpOverBudget(), expected]) as scan:
            self.assertEqual(evidence.code_state(Path.cwd(), scope=['src/**'], reuse=True), expected)
            self.assertEqual(scan.call_count, 2)

    def test_scoped_verification_does_not_hash_whole_tree(self):
        expected = ('git', {'src/a.py': b'a'})
        with patch.object(evidence, '_code_state_scan', return_value=expected) as scan:
            self.assertEqual(evidence.code_state(Path.cwd(), scope=['src/**']), expected)
            self.assertIsNotNone(scan.call_args.args[2])
            self.assertEqual(scan.call_count, 1)

    def test_contains_requires_successful_exit(self):
        self.assertFalse(status._row_ok(1, 'expected result', 'contains: expected result'))
        self.assertTrue(status._row_ok(0, 'expected result', 'contains: expected result'))

    def test_empty_pgtap_is_not_success(self):
        self.assertEqual(rules.verify_output_problem('== pgTAP: 0 files via psql\n== RESULT: OK', 'exit 0'),
                         'zero tests ran')

    def test_row_inputs_change_and_missing_inputs_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / 'input.txt'
            f.write_text('first', encoding='utf-8')
            first = rules.row_input_fingerprint(tmp, ['input.txt'])
            self.assertIsNotNone(first)
            f.write_text('second', encoding='utf-8')
            self.assertNotEqual(first, rules.row_input_fingerprint(tmp, ['input.txt']))
            self.assertIsNone(rules.row_input_fingerprint(tmp, ['missing*']))
            self.assertIsNone(rules.row_input_fingerprint(tmp, ['../outside']))

    def test_expected_whitespace_changes_verification_hash(self):
        template = ('## Verification\n| # | Command | Expected | Covers |\n'
                    '|---|---|---|---|\n| V-1 | python test.py | contains: {} | T-1 |\n')
        self.assertNotEqual(rules.verification_hash(template.format('a b')),
                            rules.verification_hash(template.format('a  b')))
        previous = {'code_fp_end': 'code', 'results': [
            {'ok': True, 'cmd': 'python test.py', 'expected': 'contains: a b'}]}
        self.assertTrue(rules._rows_already_executed(template.format('a b'), previous))
        self.assertFalse(rules._rows_already_executed(template.format('a  b'), previous))
