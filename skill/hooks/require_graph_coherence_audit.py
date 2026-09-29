#!/usr/bin/env python3
"""
PreToolUse hook (matcher: "Write|Edit") — blocks writing/updating plan.md or
tasks.md until an independent subagent (Task/Agent tool) has been dispatched
AFTER the most recent spec-graph rebuild this session.

Why this exists: find_spec.py's graph (US-nnn -> SCREEN-XX -> COMP-nnn ->
CTL-nnn -> API-nnn) is parsed mechanically (regex/markdown-tables) — it can
misparse an edited row, miss a renamed code, or silently carry over a stale
relationship a mockup-audit.md edit meant to remove. Step 3 (plan.md) and
Step 4 (tasks.md) both build directly on that graph — planning or ordering
tasks against a just-rebuilt-but-unverified graph is the same failure shape
Step 6's audit gate already exists to prevent, one step earlier. This hook
makes "dispatch a Graph Coherence Auditor before trusting new edges" (see
SKILL.md 'Graph coherence — multiagent verification') a hard stop instead of
prose an agent could skip under time pressure.

Known limitations, stated plainly rather than overclaimed:
- Like require_independent_audit.py, this can't verify the dispatched
  subagent actually checked graph coherence, only that SOME subagent ran
  after the last rebuild. Raises the bar from "trivial to skip" to "requires
  a deliberate workaround" — not a formal proof.
- Relies on mark_graph_rebuild.py and mark_agent_dispatch.py having fired
  correctly this session. If either hook's matcher doesn't fire in a given
  setup, this hook fails CLOSED (blocks) rather than open.
- Only sees find_spec.py runs made through the Bash tool (see
  mark_graph_rebuild.py's own caveat).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import read_event, read_timestamps, is_graph_consumer_file  # noqa: E402

event = read_event()
tool_input = event.get('tool_input') or {}
file_path = tool_input.get('file_path')

if not is_graph_consumer_file(file_path):
    sys.exit(0)

session_id = event.get('session_id')
ts = read_timestamps(session_id)
last_graph_rebuild = ts.get('last_graph_rebuild_ts')
last_agent_dispatch = ts.get('last_agent_dispatch_ts')

if last_graph_rebuild is None:
    # No graph rebuild this session (cache hit, or find_spec.py never ran
    # through Bash) — nothing new to verify.
    sys.exit(0)

if last_agent_dispatch is not None and last_agent_dispatch > last_graph_rebuild:
    sys.exit(0)

print(
    "aidd: blocking this write to plan.md/tasks.md. The spec graph (find_spec.py's "
    "US-nnn->SCREEN-XX->COMP-nnn->CTL-nnn->API-nnn index) was rebuilt this session, "
    "but no independent subagent (Agent/Task tool) has been dispatched since. Dispatch "
    "a Graph Coherence Auditor first — a fresh/general-purpose subagent, scoped to just "
    "the spec(s) find_spec.py reported as changed, checking for orphaned codes, "
    "contradictory relationships, or stale edges the mechanical parse could have gotten "
    "wrong — then write plan.md/tasks.md reflecting a verified graph, not a rebuilt-but-"
    "unchecked one.",
    file=sys.stderr,
)
sys.exit(2)
