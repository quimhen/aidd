import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skill' / 'hooks'))
from codex_subagent import record


class Evidence:
    def __init__(self):
        self.rows = []

    def known_root(self, cwd):
        return Path(cwd) if cwd == '/project' else None

    def events(self, root, session, kind):
        return [row for row in self.rows if row['session'] == session and row['kind'] == kind]

    def append(self, root, session, kind, **detail):
        self.rows.append({'session': session, 'kind': kind, 'detail': detail})
        return True


class CodexSubagentTests(unittest.TestCase):
    def setUp(self):
        self.evidence = Evidence()
        self.event = {'session_id': 's', 'turn_id': 't', 'agent_id': 'a',
                      'agent_type': 'reviewer', 'cwd': '/project', 'model': 'm',
                      'hook_event_name': 'SubagentStart'}

    def test_start_and_stop_record_exact_result_hash_once(self):
        self.assertTrue(record(self.event, self.evidence))
        stop = dict(self.event, hook_event_name='SubagentStop', last_assistant_message='informe íntegro')
        self.assertTrue(record(stop, self.evidence))
        self.assertEqual(self.evidence.rows[-1]['detail']['result_sha256'],
                         hashlib.sha256('informe íntegro'.encode()).hexdigest())
        self.assertFalse(record(stop, self.evidence))

    def test_orphan_wrong_agent_or_type_and_missing_output_rejected(self):
        self.assertFalse(record(dict(self.event, hook_event_name='SubagentStop', last_assistant_message='x'), self.evidence))
        self.assertTrue(record(self.event, self.evidence))
        for overrides in ({'agent_id': 'other'}, {'turn_id': 'other'}, {'agent_type': 'other'},
                          {'last_assistant_message': ''}, {'cwd': '/other'}):
            stop = dict(self.event, hook_event_name='SubagentStop', last_assistant_message='x')
            stop.update(overrides)
            self.assertFalse(record(stop, self.evidence))
