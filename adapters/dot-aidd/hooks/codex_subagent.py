#!/usr/bin/env python3
"""Record documented Codex subagent lifecycle without inventing audit verdicts."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import read_event


def record(event, evidence):
    if not isinstance(event, dict):
        return False
    phase = event.get('hook_event_name')
    fields = [event.get(name) for name in ('session_id', 'turn_id', 'agent_id', 'agent_type', 'cwd')]
    if phase not in ('SubagentStart', 'SubagentStop') or any(
        not isinstance(value, str) or not value or len(value) > 512 for value in fields
    ):
        return False
    session, turn, agent, agent_type, cwd = fields
    root = evidence.known_root(cwd)
    if root is None:
        return False
    try:
        previous = evidence.events(root, session=session, kind='codex_subagent')
        matching = [row for row in previous if (row.get('detail') or {}).get('agent_id') == agent
                    and (row.get('detail') or {}).get('turn_id') == turn]
        detail = {'phase': 'start' if phase == 'SubagentStart' else 'stop',
                  'turn_id': turn, 'agent_id': agent, 'agent_type': agent_type,
                  'model': event.get('model') if isinstance(event.get('model'), str) else ''}
        if phase == 'SubagentStart':
            if matching:
                return False
        else:
            if len(matching) != 1 or (matching[0].get('detail') or {}).get('phase') != 'start':
                return False
            if (matching[0].get('detail') or {}).get('agent_type') != agent_type:
                return False
            message = event.get('last_assistant_message')
            if not isinstance(message, str) or not message.strip():
                return False
            detail['result_sha256'] = hashlib.sha256(message.encode('utf-8')).hexdigest()
            detail['result_bytes'] = len(message.encode('utf-8'))
            detail['continued'] = event.get('stop_hook_active') is True
        return bool(evidence.append(root, session, 'codex_subagent', **detail))
    except (OSError, TypeError, ValueError, KeyError):
        return False


def main():
    sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
    try:
        import aidd_evidence
        record(read_event(), aidd_evidence)
    except Exception:
        pass
    # Codex requires JSON output for SubagentStop; an absent record is not an audit.
    print(json.dumps({}))


if __name__ == '__main__':
    main()
