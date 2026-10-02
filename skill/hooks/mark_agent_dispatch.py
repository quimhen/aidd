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
if not isinstance(event, dict):
    event = {}
_sid = event.get('session_id') if isinstance(event.get('session_id'), str) else None
_cwd = event.get('cwd') if isinstance(event.get('cwd'), str) and event.get('cwd') else None


def _s(v):
    return v if isinstance(v, str) else ''


try:
    write_timestamp(_sid, 'last_agent_dispatch_ts')
except Exception:
    pass

try:  # evidence recorder
    sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
    import aidd_evidence as _ev
    _ti = event.get('tool_input')
    if not isinstance(_ti, dict):
        _ti = {}
    _ev.append(_ev.find_root(_cwd or Path.cwd()), _sid, 'subagent',
               type=_s(_ti.get('subagent_type')),
               desc=_s(_ti.get('description'))[:200],
               head=_s(_ti.get('prompt'))[:400])
except Exception as _e:
    try:
        _ev.record_hook_error(_cwd, _sid, 'mark_agent_dispatch', _e)
    except Exception:
        pass

sys.exit(0)
