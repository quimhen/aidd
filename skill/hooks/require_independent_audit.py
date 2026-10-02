#!/usr/bin/env python3
"""
PreToolUse hook (legacy standalone; rule_gate.py runs it in-process) — blocks writing/updating any
qa-audit.md until a subagent (Task/Agent tool) has been dispatched AFTER
the most recent code-file edit this session.

Why this exists: AIDD's own SKILL.md already says "Step 6's Auditor must not
be the same agent that did the implementing" — but that was only prose. In
practice, a session that just fixed a bug can self-check its own fix, write
qa-audit.md, and call it converged, with nobody catching that the "audit"
never left the implementer's own context. This hook makes that failure mode
a hard stop instead of something that depends on someone asking "did we
actually do that?" after the fact.

Known limitations, stated plainly rather than overclaimed:
- This can't verify the dispatched subagent actually audited the right
  thing, only that SOME subagent ran after the last code edit. A session
  could dispatch an unrelated agent just to satisfy this gate. The hook
  raises the bar from "trivial to skip silently" to "requires a deliberate
  workaround" — it is not a formal proof of a correct independent audit.
- Relies on mark_code_edit.py and mark_agent_dispatch.py having fired
  correctly this session (see mark_agent_dispatch.py's matcher-name note).
  If either hook's matcher doesn't fire in a given Claude Code
  configuration, this hook fails CLOSED (blocks) rather than open — it
  will never silently rubber-stamp missing data as "audit satisfied."

`evaluate(event)` holds the decision logic (used in-process by rule_gate.py);
`main()` is the standalone wrapper.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import read_event, read_timestamps, is_qa_audit_file, event_dict, tool_input_of, str_field  # noqa: E402

MESSAGE = (
    "aidd: blocking this qa-audit.md write. Code was edited this session, but no "
    "independent subagent (Agent/Task tool) has been dispatched since that edit. "
    "Step 6's Auditor must never be the same agent that wrote the fix — dispatch "
    "an independent auditor (Agent tool, a fresh/general-purpose subagent with no "
    "context on how the fix was written) to review the change first, then write "
    "qa-audit.md reflecting ITS findings, not a self-check."
)


def evaluate(event):
    """Return (blocked, message)."""
    event = event_dict(event)
    file_path = str_field(tool_input_of(event), 'file_path')

    if not is_qa_audit_file(file_path):
        return False, ''

    sid = event.get('session_id')
    ts = read_timestamps(sid if isinstance(sid, str) else None)
    last_code_edit = ts.get('last_code_edit_ts')
    last_agent_dispatch = ts.get('last_agent_dispatch_ts')

    if last_code_edit is None:
        # No code edited yet this session — writing a baseline/first-pass
        # qa-audit.md (e.g. "0 implemented") doesn't need an independent audit,
        # since there's nothing yet to self-grade.
        return False, ''

    if last_agent_dispatch is not None and last_agent_dispatch > last_code_edit:
        return False, ''

    return True, MESSAGE


def main():
    try:
        blocked, message = evaluate(read_event())
    except Exception:
        sys.exit(0)  # a crashing hook must never wedge a session (m-c)
    if blocked:
        print(message, file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == '__main__':
    main()
