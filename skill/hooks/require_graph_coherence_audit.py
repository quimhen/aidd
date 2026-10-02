#!/usr/bin/env python3
"""
PreToolUse hook (legacy standalone; rule_gate.py runs it in-process) — blocks writing/updating plan.md or
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

FAIL-CLOSED (spec 002, rule R5): for `specs/<id>/plan.md` and
`specs/<id>/tasks.md`, having NO `find_spec` event recorded this session now
blocks (previously "no rebuild recorded" was treated as "nothing to verify").
Plan/tasks must be built on a graph the agent actually looked up. Writes to a
plan.md/tasks.md that is NOT under specs/<id>/ keep the legacy semantics.

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

`evaluate(event)` holds the decision logic (used in-process by rule_gate.py);
`main()` is the standalone wrapper.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import (read_event, read_timestamps, is_graph_consumer_file, event_dict, tool_input_of,  # noqa: E402
                     str_field, session_of)

MESSAGE = (
    "aidd: blocking this write to plan.md/tasks.md. The spec graph (find_spec.py's "
    "US-nnn->SCREEN-XX->COMP-nnn->CTL-nnn->API-nnn index) was rebuilt this session, "
    "but no independent subagent (Agent/Task tool) has been dispatched since. Dispatch "
    "a Graph Coherence Auditor first — a fresh/general-purpose subagent, scoped to just "
    "the spec(s) find_spec.py reported as changed, checking for orphaned codes, "
    "contradictory relationships, or stale edges the mechanical parse could have gotten "
    "wrong — then write plan.md/tasks.md reflecting a verified graph, not a rebuilt-but-"
    "unchecked one."
)

NO_FIND_SPEC_MESSAGE = (
    "aidd R5: blocking this write to {name}. {why}, "
    "so the plan/tasks would not be built on the spec graph. Next action: run "
    "`python <aidd skill>/scripts/find_spec.py <spec keywords>` through the Bash tool (the recorder only "
    "counts a command that actually RUNS find_spec.py - `echo find_spec.py`, grep or cat do not count; the "
    "UserPromptSubmit hook's own run does), have the Graph Coherence Auditor subagent check it if the "
    "index was rebuilt, then retry this write."
)


def _spec_dir_of(event):
    """(project_root, 'plan.md'|'tasks.md') when the target is specs/<id>/{plan,tasks}.md, else None.
    Decided on the CANONICAL path (B3: case, trailing dots/spaces, ::$DATA, .., 8.3, junctions)."""
    fp = str_field(tool_input_of(event), 'file_path')
    if not fp:
        return None
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
    import aidd_evidence as ev
    cwd = str_field(event, 'cwd') or None
    c = ev.canon_path(fp, cwd)
    parts = c.split('/')
    if len(parts) >= 4 and parts[-3] == 'specs' and parts[-1] in ('plan.md', 'tasks.md'):
        return Path('/'.join(parts[:-3])), parts[-1]
    return None


def evaluate(event):
    """Return (blocked, message)."""
    event = event_dict(event)
    file_path = str_field(tool_input_of(event), 'file_path')

    if not is_graph_consumer_file(file_path):
        return False, ''

    sid = event.get('session_id')
    session_id = sid if isinstance(sid, str) and sid else None

    spec_target = _spec_dir_of(event)
    if spec_target is not None:
        import aidd_evidence as ev
        root = ev.find_root(spec_target[0])
        allf = ev.events(root, session=str(session_id or 'unknown-session'), kind='find_spec')
        found = [e for e in allf if (e.get('detail') or {}).get('ok') is not False]
        if not found:
            why = ('find_spec ran in this session but its output was not a valid find_spec result (error / empty)'
                   if allf else 'No find_spec run is recorded in this session')
            return True, NO_FIND_SPEC_MESSAGE.format(name=spec_target[1], why=why)

    ts = read_timestamps(session_id)
    last_graph_rebuild = ts.get('last_graph_rebuild_ts')
    last_agent_dispatch = ts.get('last_agent_dispatch_ts')

    if last_graph_rebuild is None:
        # No graph rebuild this session (cache hit, or find_spec.py never ran
        # through Bash) — nothing new to verify.
        return False, ''

    if last_agent_dispatch is not None and last_agent_dispatch > last_graph_rebuild:
        return False, ''

    return True, MESSAGE


def main():
    event = {}
    try:
        event = read_event()
        blocked, message = evaluate(event)
    except Exception as e:
        try:  # never wedge a session; leave a trace when a project root is known (m-c)
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
            import aidd_evidence as ev
            ev.record_hook_error(str_field(event_dict(event), 'cwd') or str(Path.cwd()),
                                 session_of(event), 'require_graph_coherence_audit', e)
        except Exception:
            pass
        sys.exit(0)
    if blocked:
        print(message, file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == '__main__':
    main()
