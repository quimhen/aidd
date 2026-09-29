#!/usr/bin/env python3
"""
PostToolUse hook (matcher: "Task|Agent") — records the timestamp of the most
recent subagent dispatch this session. Any dispatch counts (this hook can't
know what the subagent was asked to do) — it's a heuristic, not a formal
proof of a correct independent audit. Paired with mark_code_edit.py and
require_independent_audit.py.

Matcher name note: Claude Code's built-in subagent-dispatch tool is matched
here as "Task|Agent" to cover naming across versions/configurations — if
neither name is right for a given setup, this hook simply never fires, which
fails safe (require_independent_audit.py still blocks qa-audit.md writes;
it just can't be un-blocked by a dispatch it never saw). Adjust the matcher
in settings.json if you confirm the actual tool name differs.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import read_event, write_timestamp  # noqa: E402

event = read_event()
write_timestamp(event.get('session_id'), 'last_agent_dispatch_ts')

sys.exit(0)
