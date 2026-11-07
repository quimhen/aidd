#!/usr/bin/env python3
"""
PreToolUse hook (matcher: "Task|Agent") — records a `subagent` evidence row with
detail phase='pre' BEFORE the agent runs, so a slow or timed-out PostToolUse
(mark_agent_dispatch.py) cannot lose the attribution trail. The pre row is
ATTRIBUTION ONLY: it runs before the permission check (the dispatch may be denied
or fail) and before model resolution, so it NEVER counts as an audit (R5/R7/R8/R14,
aidd_rules._subagent_counts). The PostToolUse row (resolved model) is the one that counts.

Fail-open: never raises, never blocks, no stdout, always exits 0.
"""
import sys
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).parent))
    sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
    from _common import read_event  # noqa: E402
    import aidd_evidence as _ev  # noqa: E402
except Exception:
    sys.exit(0)

_cwd = None
_sid = None


def _s(v):
    return v if isinstance(v, str) else ''


try:
    event = read_event()
    if not isinstance(event, dict):
        event = {}
    _sid = event.get('session_id') if isinstance(event.get('session_id'), str) else None
    _cwd = event.get('cwd') if isinstance(event.get('cwd'), str) and event.get('cwd') else None
    _ti = event.get('tool_input')
    if not isinstance(_ti, dict):
        _ti = {}
    _tuid = _s(event.get('tool_use_id'))[:_ev.TOOL_USE_ID_MAX]   # never the agent-controlled tool_input
    _detail = dict(phase='pre',
                   type=_s(_ti.get('subagent_type')),
                   model=_s(_ti.get('model')).strip()[:200],
                   model_source='tool_input' if _s(_ti.get('model')).strip() else '',
                   desc=_s(_ti.get('description'))[:200],
                   head=_ev.redact_secrets(_s(_ti.get('prompt')), limit=400)[0])
    if _tuid:
        _detail['tool_use_id'] = _tuid
    if not _ev.append(_ev.find_root(_cwd or Path.cwd()), _sid, 'subagent', **_detail):
        _ev.record_hook_error(_cwd, _sid, 'record_dispatch_pre', 'append returned False')
except Exception as _e:
    try:
        _ev.record_hook_error(_cwd, _sid, 'record_dispatch_pre', _e)
    except Exception:
        pass

sys.exit(0)
