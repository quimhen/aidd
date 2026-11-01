import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from skill.scripts import aidd_status as status
from skill.scripts.aidd_units import discover_units
from skill.scripts import aidd_rules as rules


class UnitConsent(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.spec = self.root / 'specs' / 's'
        directory = self.spec / 'amendments' / 'a'
        directory.mkdir(parents=True)
        (directory / 'tasks.md').write_text('Task content fully reviewed', encoding='utf-8')
        (directory / 'manifest.json').write_text(json.dumps({
            'schema_version': 1, 'spec_id': 's', 'unit_id': 'a', 'sequence': 1,
            'parents': [], 'paths': ['specs/s/amendments/a/tasks.md'], 'targets': []}), encoding='utf-8')
        self.unit = discover_units(self.root)[0]
        self.package = rules.unit_review_package(self.unit, self.root)
        self.question = rules.unit_consent_question(self.package)
        self.answer = {'session': 'session-1', 'ts': time.time() + .01, 'kind': 'answer',
                       'detail': {'pairs': [[self.question, status.SUMMARY_LABEL]],
                                  'options': [[status.SUMMARY_LABEL, 'No']]}}

    def approve(self, events, append_result=True, session='session-1'):
        with patch.object(status, '_resolve_spec', return_value=self.spec), \
             patch.object(status.ev, 'find_root', return_value=self.root), \
             patch.object(status, '_current_session', return_value=session), \
             patch.object(status.ev, 'events', return_value=events), \
             patch.object(status.ev, 'append', return_value=append_result) as append:
            result = status.cmd_approve_unit(str(self.spec), 'a')
        return result, append

    def test_exact_recorded_consent_appends_once(self):
        result, append = self.approve([self.answer])
        self.assertEqual(0, result)
        self.assertEqual(1, append.call_count)
        self.assertEqual('unit_approved', append.call_args.args[2])

    def test_partial_question_or_missing_option_never_approve(self):
        self.answer['detail']['pairs'][0][0] = self.question.split('\n')[0]
        result, append = self.approve([self.answer])
        self.assertEqual(1, result)
        append.assert_not_called()
        self.answer['detail']['pairs'][0][0] = self.question
        self.answer['detail']['options'] = []
        result, append = self.approve([self.answer])
        self.assertEqual(1, result)
        append.assert_not_called()

    def test_stale_changed_or_wrong_session_cannot_approve(self):
        self.answer['session'] = 'other'
        result, append = self.approve([self.answer])
        self.assertEqual(1, result)
        append.assert_not_called()
        self.answer['session'] = 'session-1'
        (self.spec / 'amendments/a/tasks.md').write_text('changed', encoding='utf-8')
        result, append = self.approve([self.answer])
        self.assertEqual(1, result)
        append.assert_not_called()

    def test_newer_rejection_cancels_and_unknown_session_fails(self):
        later = dict(self.answer, ts=self.answer['ts'] + .01,
                     detail={'pairs': [[self.question, 'No']], 'options': [['No', status.SUMMARY_LABEL]]})
        result, append = self.approve([self.answer, later])
        self.assertEqual(1, result)
        append.assert_not_called()
        result, append = self.approve([self.answer], session='unknown-session')
        self.assertEqual(1, result)
        append.assert_not_called()


if __name__ == '__main__':
    unittest.main()
