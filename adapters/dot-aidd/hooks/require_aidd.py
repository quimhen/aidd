#!/usr/bin/env python3
"""
PreToolUse hook (legacy standalone; rule_gate.py runs it in-process) — blocks writing/editing an application
source file until the aidd skill has been invoked at least once in this session.

Scope, by design:
- Only gates recognized source-code extensions (see _common.CODE_EXTENSIONS) —
  markdown, config, and aidd's own spec/design-system artifacts are never blocked,
  so starting or continuing aidd's own planning work is always unaffected.
- Enforced globally (every Claude Code session on this machine), per the user's own
  choice — not scoped to "projects that already use aidd."
- Does not (and cannot, via this hook alone) catch code written through Bash
  (heredocs, sed, etc.) — Write/Edit is the primary authoring path this covers.

Exit code 2 blocks the tool call and returns this hook's stderr to Claude as the
reason, so Claude sees exactly what to do next (invoke the Skill tool with
skill: "aidd") instead of just failing silently.

`evaluate(event)` holds the decision logic (used in-process by rule_gate.py);
`main()` is the standalone wrapper Claude Code can still invoke directly.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import read_event, marker_path, is_code_file, event_dict, tool_input_of, str_field, session_of  # noqa: E402

MESSAGE = (
    "aidd has not been invoked yet this session. AIDD is the default pipeline "
    "for ANY code change, whether or not it has a visual surface. Before writing "
    "or editing code, invoke the aidd skill (Skill tool, skill: \"aidd\") and "
    "follow its flow (search -> visual audit ONLY if there's a mockup, otherwise "
    "skip to align -> plan -> tasks -> build -> converge). If this change "
    "genuinely doesn't need the full flow, use aidd's 'fast lane' explicitly "
    "instead of skipping the skill."
)


def evaluate(event):
    """Return (blocked, message)."""
    event = event_dict(event)
    file_path = str_field(tool_input_of(event), 'file_path')

    if not is_code_file(file_path):
        return False, ''

    sid = event.get('session_id')
    if marker_path(sid if isinstance(sid, str) else None).exists():
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
