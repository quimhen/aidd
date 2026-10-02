#!/usr/bin/env python3
"""
Stop hook — AIDD rule R8: the agent may not end its turn while an approved, implemented spec has
no closing audit.

Obligations derive from the OPEN specs (aidd_evidence.open_specs) of every project root above the
cwd, across ALL sessions (M10): a fresh session cannot dodge another session's unfinished spec. A spec
is an obligation when ALL of these hold:
  - its tasks.md has a valid approval (hash matches);
  - at least one `code_edit` (any session, any spec - D1) was recorded after the approval. "Approved at" comes from
    the recorded `approved{spec,hash}` events (M7), NEVER from the file mtime: the recorder re-emits
    `approved` on every valid rewrite, so the gate takes the EARLIEST event of the current run of the
    current hash — a hash-neutral rewrite (whitespace, Status column) therefore does not reset it;
  - and qa-audit.md is missing OR some required domain has no DISTINCT auditor subagent after the last
    code edit (aidd_rules.uncovered_domains).

Blocks are counted via `stop_block{spec,key=approval hash}` events: while count < 3 the Stop is blocked
(exit 2 + checklist) EVEN when the payload says `stop_hook_active`; once exhausted it is allowed and a
`stop_block_exhausted` event is recorded (no infinite loop, but also no free pass after one block).

Never blocks: without an open obligation, with AIDD_RULES=warn|off|0|false|no (warn prints the checklist,
exits 0 and does not consume the budget), or on any internal error (exit 0 + a `hook_error` event).
"""
import os
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = HOOKS_DIR.parent / 'scripts'
sys.path.insert(0, str(HOOKS_DIR))

from _common import read_event, rules_mode, event_dict, str_field, session_of  # noqa: E402

MAX_BLOCKS = 3


def _emit(msg):
    try:
        sys.stderr.buffer.write((msg.rstrip() + '\n').encode('utf-8', 'replace'))
        sys.stderr.flush()
    except Exception:
        pass


def _libs():
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    import aidd_evidence as ev
    import aidd_rules as rules
    return ev, rules


def _approved_at(ev, root, spec, key):
    """ts of the first `approved` event of the current run of hash `key` for `spec` (0.0 if none)."""
    evs = sorted((e for e in ev.events(root, None, 'approved') if str((e.get('detail') or {}).get('spec', '')).lower()
                  == spec.lower()), key=lambda e: e['ts'])
    run = []
    for e in evs:
        if str((e.get('detail') or {}).get('hash', '')).lower() == key.lower():
            run.append(e['ts'])
        else:
            run = []
    return min(run) if run else 0.0


def _obligations(ev, rules, roots):
    """[(root, spec, key, edits, missing[list of str])] for every open, approved, implemented, unclosed spec."""
    out = []
    for root in roots:
        for spec in ev.open_specs(root):
            d = Path(root) / 'specs' / spec
            try:
                tasks = (d / 'tasks.md').read_text(encoding='utf-8', errors='replace')
            except OSError:
                continue
            if not rules.approval_valid(tasks):
                continue                                   # R6 (the code gate) owns that case
            line = rules.approval_line(tasks)
            key = line[1] if line else ''
            at = _approved_at(ev, root, spec, key)
            # D1: a code_edit carries no spec attribution - ANY code edit after this spec's approval counts
            edits = [e for e in ev.events(root, None, 'code_edit') if e['ts'] > at]
            if not edits:
                continue
            since = max(e['ts'] for e in edits)
            missing = []
            if not (d / 'qa-audit.md').exists():
                missing.append(f'[ ] specs/{spec}/qa-audit.md does not exist - write it from the auditors\' findings.')
            for dom in sorted(rules.uncovered_domains(root, None, spec, since, spec_dir=d)):
                missing.append(f'[ ] no distinct {dom} auditor subagent ran after the last code edit - dispatch an '
                               f'independent {dom} auditor (Agent tool; its description/prompt must name "{dom}"; one '
                               'subagent covers one domain).')
            if missing:
                out.append((root, spec, key, edits, missing))
    return out


def evaluate(event, mode='enforce'):
    """Return (blocked, message). In 'enforce' mode blocks are recorded (budget); 'warn' never records."""
    event = event_dict(event)
    ev, rules = _libs()
    cwd = str_field(event, 'cwd') or str(Path.cwd())
    roots = list(ev.project_roots(cwd))
    try:   # D1b: a session started in a PARENT folder of the project(s): look one level down as well
        for child in sorted(Path(cwd).iterdir())[:60]:
            if child.is_dir() and not child.name.startswith('.') and (
                    (child / 'specs').is_dir() or (child / '.aidd').is_dir()):
                roots.append(child)
    except OSError:
        pass
    obs = _obligations(ev, rules, roots) if roots else []
    if not obs:
        return False, ''
    session = session_of(event)
    blocking, parts = [], []
    for root, spec, key, edits, missing in obs:
        used = ev.count(root, 'stop_block', spec=spec, key=key)
        if used >= MAX_BLOCKS:
            if mode == 'enforce' and not ev.count(root, 'stop_block_exhausted', spec=spec, key=key):
                ev.append_stop_block_exhausted(root, session, spec, key)
            continue
        blocking.append((root, spec, key, used))
        parts.append(f'aidd R8: spec {spec} has approved tasks and {len(edits)} code edit(s) but it is not closed '
                     f'(block {used + 1} of {MAX_BLOCKS}). Do not stop yet. Missing:\n' +
                     '\n'.join('  ' + m for m in missing) +
                     f'\nWhen done and the user agrees, `aidd rules close {spec}` closes it; if the spec was dropped, '
                     f'the user can `aidd rules abandon {spec}`.')
    if not blocking:
        return False, ''
    if mode == 'enforce':
        for root, spec, key, _used in blocking:
            ev.append_stop_block(root, session, spec, key)
    return True, '\n'.join(parts) + '\n(Owner-only override: AIDD_RULES=warn|off in settings.json env.)'


def main():
    mode = rules_mode()
    if mode == 'off':
        sys.exit(0)
    event = {}
    try:
        event = event_dict(read_event())
        blocked, msg = evaluate(event, mode)
    except Exception as e:
        try:
            ev, _ = _libs()
            ev.record_hook_error(str_field(event, 'cwd') or str(Path.cwd()), session_of(event), 'stop_gate', e)
        except Exception:
            pass
        sys.exit(0)
    if blocked:
        if mode == 'warn':
            _emit('[AIDD_RULES=warn, not blocking] ' + msg)
            sys.exit(0)
        _emit(msg)
        sys.exit(2)
    sys.exit(0)


if __name__ == '__main__':
    main()
