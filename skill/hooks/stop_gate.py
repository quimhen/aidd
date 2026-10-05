#!/usr/bin/env python3
"""
Stop hook — AIDD rule R8: the agent may not end its turn while an approved, implemented spec has
no closing audit.

Obligations derive from the OPEN specs (aidd_evidence.open_specs) of every project root above the
cwd, across ALL sessions (M10): a fresh session cannot dodge another session's unfinished spec. A spec
is an obligation when ALL of these hold:
  - its tasks.md has a valid approval (hash matches);
  - at least one `code_edit` attributed to it (or unstamped, see below) was recorded after the approval.
    "Approved at" comes from the recorded `approved{spec,hash}` events (M7), NEVER from the file mtime: the
    recorder re-emits `approved` on every valid rewrite, so the gate takes the EARLIEST event of the current
    run of the current hash — a hash-neutral rewrite (whitespace, Status column) therefore does not reset it;
  - and qa-audit.md is missing OR some required domain has no covering auditor after the last
    code edit (aidd_rules.uncovered_domains: ONE closing auditor, or the legacy distinct per-domain ones).

Scope (spec 007, FR-206 aidd:FR-206): only the gate TARGET spec(s) (aidd_evidence.gate_target_specs;
ambiguous -> none) BLOCK. Every other approved open spec with unaudited code edits attributed to it
(unstamped edits count only for a target, or for every spec when there is no target) gets ONE non-blocking
reminder per session (`stop_reminder{sid, specs}`): a JSON `systemMessage` on stdout with exit 0 when nothing
blocks, appended to the block message otherwise. In warn/off mode a `rules_override{hook:'stop_gate', mode}`
event is recorded BEFORE returning (aidd:FR-208).

Blocks are counted via `stop_block{spec,key=approval hash}` events: while count < MAX_BLOCKS (env
AIDD_STOP_BLOCKS, default 3, invalid -> 3) the Stop is blocked (exit 2 + checklist) EVEN when the payload
says `stop_hook_active`; once exhausted it is allowed and a `stop_block_exhausted` event is recorded (no
infinite loop, but also no free pass after one block).

Never blocks: without an open obligation, with AIDD_RULES=warn|off|0|false|no (warn prints the checklist,
exits 0 and does not consume the budget), or on any internal error (exit 0 + a `hook_error` event).
"""
import json
import os
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = HOOKS_DIR.parent / 'scripts'
sys.path.insert(0, str(HOOKS_DIR))

from _common import read_event, rules_mode, event_dict, str_field, session_of  # noqa: E402


def _max_blocks():
    """aidd:FR-206 env AIDD_STOP_BLOCKS as an int >= 1; default 3 (invalid, empty or < 1 -> 3)."""
    try:
        n = int(str(os.environ.get('AIDD_STOP_BLOCKS', '')).strip())
        return n if n >= 1 else 3
    except Exception:
        return 3


MAX_BLOCKS = _max_blocks()


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


def _closing_header(ev, rules, root, spec, d):
    """aidd:FR-206 the exact FIRST line the closing auditor's prompt needs. Never raises."""
    try:
        doms = ', '.join(sorted(rules.required_domains(d)))
        tasks = (d / 'tasks.md').read_text(encoding='utf-8', errors='replace')
        h = f'CLOSING AUDIT [domains: {doms}] [tasks:{rules.approval_hash(tasks)[:8]}]'
        try:
            if rules._is_gate2(ev, root, d):
                run = ev.latest_verify_run(root, spec)
                vh = str((run or {}).get('verify_hash') or '')[:8]
                h += f' [verify:{vh or "<v8>"}]'
        except Exception:
            pass
        return h
    except Exception:
        return 'CLOSING AUDIT [domains: ...] [tasks:<h8>]'


def _obligations(ev, rules, roots):
    """aidd:FR-206 [(root, spec, key, edits, missing[list of str], is_target, header)] for every open, approved,
    implemented, unclosed spec. `is_target` = the spec is in gate_target_specs(root) (only those block; the
    others are reminded). Edits are the `code_edit`s attributed to the spec after its approval; unstamped ones
    count for a target and, when there is no target at all, for every spec."""
    out = []
    for root in roots:
        try:
            targets = [str(t).lower() for t in (ev.gate_target_specs(root)[0] or [])]
        except Exception:
            targets = []
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
            is_target = spec.lower() in targets
            edits = ev.code_edits_for(root, spec, at, include_unstamped=(is_target or not targets))
            if not edits:
                continue
            since = rules.audit_since(edits)
            missing = []
            if not (d / 'qa-audit.md').exists():
                missing.append(f'[ ] specs/{spec}/qa-audit.md does not exist - write it from the auditors\' findings.')
            doms = sorted(rules.uncovered_domains(root, None, spec, since, spec_dir=d))
            try:
                reasons = rules._uncovered_reasons(ev, root, None, doms, since) if doms else {}
            except Exception:
                reasons = {}
            for dom in doms:
                tier = reasons.get(dom) == 'tier'
                note = ' (model tier too low, R14: a haiku auditor does not count)' if tier else ''
                model = ' with a medium or high model (model: sonnet or opus)' if tier else ''
                missing.append(f'[ ] no distinct {dom} auditor subagent ran after the last code edit{note} - dispatch an '
                               f'independent {dom} auditor (Agent tool{model}; its description/prompt must name "{dom}"; '
                               'one subagent covers one domain).')
            if missing:
                out.append((root, spec, key, edits, missing, is_target, _closing_header(ev, rules, root, spec, d)))
    return out


def _roots_of(ev, cwd):
    roots = list(ev.project_roots(cwd))
    try:   # D1b: a session started in a PARENT folder of the project(s): look one level down as well
        for child in sorted(Path(cwd).iterdir())[:60]:
            if child.is_dir() and not child.name.startswith('.') and (
                    (child / 'specs').is_dir() or (child / '.aidd').is_dir()):
                roots.append(child)
    except OSError:
        pass
    return roots


def _reminder(ev, others, session, record):
    """aidd:FR-206 text of the once-per-session reminder for `others` [(root, spec, n_edits)], or ''.
    Each (root, session, specs) is emitted once: `stop_reminder{sid, specs}` is the dedupe key."""
    lines = []
    for root in dict.fromkeys(r for r, _s, _n in others):
        mine = [(s, n) for r, s, n in others if r == root]
        specs = ','.join(sorted(s.lower() for s, _n in mine))
        try:
            if ev.count(root, 'stop_reminder', sid=str(session), specs=specs):
                continue
            if record:
                ev.append(root, session, 'stop_reminder', sid=str(session), specs=specs)
        except Exception:
            pass
        try:
            target = ', '.join(ev.gate_target_specs(root)[0]) or 'none'
        except Exception:
            target = 'none'
        lines += [f'AIDD: spec {s} is approved and has {n} code edit(s) with no closing audit; gate target is '
                  f'{target}; see `aidd status`.' for s, n in mine]
    return '\n'.join(lines)


def evaluate(event, mode='enforce'):
    """Return (blocked, message). In 'enforce' mode blocks are recorded (budget); 'warn' never records.
    When not blocked, `message` is the (possibly empty) once-per-session reminder about the other specs."""
    event = event_dict(event)
    ev, rules = _libs()
    cwd = str_field(event, 'cwd') or str(Path.cwd())
    roots = _roots_of(ev, cwd)
    obs = _obligations(ev, rules, roots) if roots else []
    if not obs:
        return False, ''
    session = session_of(event)
    blocking, parts = [], []
    for root, spec, key, edits, missing, is_target, header in obs:
        if not is_target:
            continue
        used = ev.count(root, 'stop_block', spec=spec, key=key)
        if used >= MAX_BLOCKS:
            if mode == 'enforce' and not ev.count(root, 'stop_block_exhausted', spec=spec, key=key):
                ev.append_stop_block_exhausted(root, session, spec, key)
            continue
        blocking.append((root, spec, key, used))
        parts.append(f'aidd R8: spec {spec} not closed ({len(edits)} code edit(s); block {used + 1} of {MAX_BLOCKS}). '
                     'Do not stop yet. Missing:\n' +
                     '\n'.join('  ' + m for m in missing) +
                     f'\nClose it in three steps: (1) run `aidd verify {spec}`; (2) dispatch ONE closing auditor '
                     f'(Agent tool, medium or high model) whose prompt FIRST line is exactly:\n  {header}\n'
                     f'(3) write specs/{spec}/qa-audit.md (a table row per domain + the auditor\'s tool_use_id), '
                     f'then `aidd rules close {spec}` (user agrees) or `aidd rules abandon {spec}` if dropped.')
    others = [(r, s, len(e)) for r, s, _k, e, _m, t, _h in obs if not t]
    note = _reminder(ev, others, session, record=(mode == 'enforce')) if others else ''
    if not blocking:
        return False, note
    if mode == 'enforce':
        for root, spec, key, _used in blocking:
            ev.append_stop_block(root, session, spec, key)
    tail = ('\n' + note) if note else ''
    return True, ('\n'.join(parts) + tail +
                  f'\n(Budget: AIDD_STOP_BLOCKS={MAX_BLOCKS}. Owner-only override: AIDD_RULES=warn|off in settings.json env.)')


def _record_override(event, mode):
    """aidd:FR-208 aidd:AC-214 `rules_override{hook:'stop_gate', mode}` when a project root is known."""
    try:
        ev, _ = _libs()
        roots = ev.project_roots(str_field(event, 'cwd') or str(Path.cwd()))
        if roots:
            ev.append(roots[0], session_of(event), 'rules_override', hook='stop_gate', mode=mode)
    except Exception:
        pass


def main():
    mode = rules_mode()
    event = {}
    if mode == 'off':
        try:
            event = event_dict(read_event())
        except Exception:
            event = {}
        _record_override(event, mode)
        sys.exit(0)
    try:
        event = event_dict(read_event())
        if mode == 'warn':
            _record_override(event, mode)
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
    if msg:
        try:
            sys.stdout.buffer.write((json.dumps({'systemMessage': msg}) + '\n').encode('utf-8', 'replace'))
            sys.stdout.flush()
        except Exception:
            pass
    sys.exit(0)


if __name__ == '__main__':
    main()
