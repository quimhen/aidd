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

Known limitation: this only sees `find_spec.py` runs made through the Bash
tool. A run through some other shell-escaping path wouldn't be seen — same
caveat require_aidd.py already states for code edits via Bash.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import read_event, write_timestamp  # noqa: E402

event = read_event()
tool_input = event.get('tool_input') or {}
command = str(tool_input.get('command', ''))

if 'find_spec.py' not in command:
    sys.exit(0)

tool_response = event.get('tool_response')
output = ''
if isinstance(tool_response, dict):
    output = str(tool_response.get('stdout') or tool_response.get('output') or '')
elif tool_response is not None:
    output = str(tool_response)

if 'Graph index: rebuilt' in output:
    write_timestamp(event.get('session_id'), 'last_graph_rebuild_ts')

sys.exit(0)
