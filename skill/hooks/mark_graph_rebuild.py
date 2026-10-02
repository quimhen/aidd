#!/usr/bin/env python3
"""
PostToolUse hook (matcher: "Bash") — records the timestamp of the most recent
spec-graph rebuild this session, i.e. a `find_spec.py` invocation whose own
output said "Graph index: rebuilt" (see find_spec.py's report_index_status()).
A cache-hit run ("unchanged") does not count — nothing new to verify.

Paired with require_graph_coherence_audit.py: that hook blocks writing
plan.md/tasks.md unless an independent subagent (Task/Agent tool — tracked by
mark_agent_dispatch.py, already installed for Step 6's audit gate) was
dispatched AFTER this rebuild. Together they make "Graph coherence —
multiagent verification" (SKILL.md) a hard stop instead of a step an agent
could silently skip, the same way require_independent_audit.py already does
for Step 6.

Evidence (spec 002): a `find_spec{rebuilt,ok,source:bash}` event is recorded only when the
command actually RUNS find_spec.py (`python|python3|py [-u] <path>find_spec.py`, possibly after
`cd … &&`) — an `echo`/`grep`/`cat` that merely mentions the name records nothing.

Also registered for the PowerShell tool (same `tool_input.command`). Recognised: `& python ...`,
`python -X utf8 ...`, `time|timeout N python ...`, `powershell|pwsh|bash -c "python ..."` and the
`aidd spec ...` CLI wrapper. `ok` requires the authentic `aidd spec search` / no-spec message.

Known limitation: this only sees `find_spec.py` runs made through the Bash
tool. A run through some other shell-escaping path wouldn't be seen — same
caveat require_aidd.py already states for code edits via Bash.
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
tool_input = event.get('tool_input')
command = tool_input.get('command') if isinstance(tool_input, dict) else ''
command = command if isinstance(command, str) else ''

if 'find_spec.py' not in command and 'aidd' not in command:
    sys.exit(0)

tool_response = event.get('tool_response')
output = ''
try:
    if isinstance(tool_response, dict):
        output = str(tool_response.get('stdout') or tool_response.get('output') or '')
    elif tool_response is not None:
        output = str(tool_response)
except Exception:
    output = ''

try:  # legacy timestamp behaviour (unchanged)
    if 'find_spec.py' in command and 'Graph index: rebuilt' in output:
        write_timestamp(_sid, 'last_graph_rebuild_ts')
except Exception:
    pass

try:  # evidence recorder
    sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
    import aidd_evidence as _ev
    if _ev.runs_find_spec(command):
        if not output and tool_response is not None:
            output = _ev.response_text(tool_response)
        _ev.append_find_spec(_ev.find_root(_cwd or Path.cwd()), _sid,
                             rebuilt=_ev.find_spec_rebuilt(output), ok=_ev.find_spec_ok(output), source='bash')
except Exception as _e:
    try:
        _ev.record_hook_error(_cwd, _sid, 'mark_graph_rebuild', _e)
    except Exception:
        pass

sys.exit(0)
