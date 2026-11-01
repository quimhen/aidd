"""Exercise real question hook with long questions in isolated projects."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from skill.scripts import aidd_rules as rules
from skill.scripts import aidd_status as status
from skill.scripts.aidd_units import discover_units

HOOK = Path(__file__).resolve().parents[1] / 'skill/hooks/mark_user_question.py'


class LongUnitQuestionHook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.spec = self.root / 'specs' / 'example'
        unitdir = self.spec / 'amendments' / 'a'
        unitdir.mkdir(parents=True)
        self.tasks = unitdir / 'tasks.md'
        self.tasks.write_text('Task reviewed.\n' + ('Specific behavior.\n' * 120), encoding='utf-8')
        (unitdir / 'manifest.json').write_text(json.dumps({
            'schema_version': 1, 'spec_id': 'example', 'unit_id': 'a', 'sequence': 1,
            'parents': [], 'paths': ['specs/example/amendments/a/tasks.md'], 'targets': []}), encoding='utf-8')
        self.session = 'test-unit-' + uuid.uuid4().hex
        self.env = {'AIDD_TESTING': '1', 'AIDD_EVIDENCE_DIR': str(self.root / 'evidence')}

    def ask_through_hook(self, question, answer):
        event = {'cwd': str(self.root), 'session_id': self.session,
                 'tool_input': {'questions': [{'question': question,
                    'options': [{'label': status.SUMMARY_LABEL}, {'label': 'No'}]}]},
                 'tool_response': {'answers': {question: answer}}}
        proc = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event),
                              text=True, encoding='utf-8', capture_output=True,
                              env={**os.environ, **self.env}, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def approve(self, spec=None):
        with patch.dict(os.environ, self.env), patch.object(status, '_current_session', return_value=self.session):
            return status.cmd_approve_unit(str(spec or self.spec), 'a')

    def question(self):
        return rules.unit_consent_question(rules.unit_review_package(discover_units(self.root)[0], self.root))

    def test_long_question_and_changed_tasks(self):
        question = self.question()
        self.assertGreater(len(question), 1000)
        self.ask_through_hook(question, status.SUMMARY_LABEL)
        self.assertEqual(self.approve(), 0)
        self.tasks.write_text('Changed after the owner answer.', encoding='utf-8')
        self.assertEqual(self.approve(), 1)

    def test_altered_question_and_rejection(self):
        question = self.question()
        self.ask_through_hook(question + ' altered', status.SUMMARY_LABEL)
        self.assertEqual(self.approve(), 1)
        self.ask_through_hook(question, 'No')
        self.assertEqual(self.approve(), 1)

    def test_other_checkout_is_not_approved(self):
        self.ask_through_hook(self.question(), status.SUMMARY_LABEL)
        second = self.root / 'other-checkout'
        shutil.copytree(self.spec, second / 'specs' / 'example')
        self.assertEqual(self.approve(second / 'specs' / 'example'), 1)

    def test_admin_updates_do_not_revoke_but_requirement_changes_do(self):
        manifest = self.spec / 'amendments/a/manifest.json'
        data = json.loads(manifest.read_text(encoding='utf-8'))
        data.update(schema_version=2, version='v1', inputs=[], config=[], visual_refs=[], targets=['service.py'])
        manifest.write_text(json.dumps(data), encoding='utf-8')
        before = '| Task | Status | Tracker ref | Requirement |\n| --- | --- | --- | --- |\n| T-1 | pending | 42 | verify total |\n'
        self.tasks.write_text(before, encoding='utf-8')
        self.ask_through_hook(self.question(), status.SUMMARY_LABEL)
        self.tasks.write_text(before.replace('pending', 'done').replace('42', '93'), encoding='utf-8')
        self.assertEqual(self.approve(), 0)
        self.tasks.write_text(before.replace('verify total', 'skip verification'), encoding='utf-8')
        self.assertEqual(self.approve(), 1)

    def test_new_rejection_and_manifest_change_remain_authoritative(self):
        manifest = self.spec / 'amendments/a/manifest.json'
        data = json.loads(manifest.read_text(encoding='utf-8'))
        data.update(schema_version=2, version='v1', inputs=[], config=[], visual_refs=[], targets=['service.py'])
        manifest.write_text(json.dumps(data), encoding='utf-8')
        task = '| Task | Status | Tracker ref | Requirement |\n| --- | --- | --- | --- |\n| T-1 | pending | 42 | verify total |\n'
        self.tasks.write_text(task, encoding='utf-8')
        self.ask_through_hook(self.question(), status.SUMMARY_LABEL)
        self.tasks.write_text(task.replace('pending', 'done'), encoding='utf-8')
        self.ask_through_hook(self.question(), 'No')
        self.assertEqual(self.approve(), 1)
        data['version'] = 'v2'
        manifest.write_text(json.dumps(data), encoding='utf-8')
        self.assertEqual(self.approve(), 1)
