#!/usr/bin/env python3
"""
aidd next -- the ONE next action for the gate-target spec, in at most 30 lines. No LLM. Stdlib only.

Usage:
    aidd_next.py next [spec_dir] [--write] [--json]
        spec_dir  defaults to specs/<gate pointer> of the current root
        --write   also write the same text to <root>/.aidd/NEXT.md
        --json    print the info dict instead of the text
Exit codes: 0 ok (read-only reporter), 2 usage. Never prints a traceback.
"""
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

MAX_LINES = 30
STEP_NAMES = {-1: 'scope (search existing work)', 0: 'scope (source of truth)', 1: 'audit', 2: 'align',
              3: 'plan', 4: 'tasks + approval', 5: 'build', 6: 'converge (audit)', 7: 'doc'}
_VIOLATION = re.compile(r'^(R\d+)\s+(.*?)(?:\s+(?:→|->)\s+(.*))?$')


def _load_status_module():
    """Import aidd_status lazily; None when it cannot be imported."""
    try:
        import aidd_status
        return aidd_status
    except Exception:
        return None


def _find_root(spec_dir):
    """Project root: from the spec dir when given, else from the cwd. None when unknown."""
    try:
        import aidd_evidence as ev
        root = ev.find_root(Path(spec_dir).resolve() if spec_dir else None)
        return Path(root) if root else None
    except Exception:
        return None


def _gate_spec(root):
    try:
        import aidd_evidence as ev
        return ev.get_gate_spec(root) or ''
    except Exception:
        return ''


def _exists(p):
    try:
        return Path(p).exists()
    except Exception:
        return False


def _violations(why_blocked):
    """Open rule violations as [{rule, message, fix}] parsed from the status why_blocked lines."""
    out = []
    for line in why_blocked or []:
        m = _VIOLATION.match(str(line).strip())
        if m:
            out.append({'rule': m.group(1), 'message': m.group(2).strip(), 'fix': (m.group(3) or '').strip()})
    return out


def _verify_result(st):
    s = str((st.get('verification') or {}).get('status') or 'none')
    return s if s in ('passed', 'failed', 'stale') else 'never-run'


def _infer_step(d, st, verify):
    """Current step -1..7 from the artifacts present and the status facts."""
    if not _exists(d / 'spec.md'):
        return 0
    if not _exists(d / 'plan.md'):
        return 3
    approval = (st.get('tasks') or {}).get('approval')
    if approval != 'valid':
        return 4
    if st.get('qa_audit') and verify == 'passed':
        return 7
    if verify == 'passed' and int(st.get('code_edits') or 0) > 0:
        return 6
    return 5


def _next_command(spec_id, step, st, verify, violations):
    approval = (st.get('tasks') or {}).get('approval')
    if step == 0:
        return f'write specs/{spec_id}/spec.md (aidd scope)'
    if step == 3:
        return f'write specs/{spec_id}/plan.md (aidd plan)'
    if step == 4:
        if approval == 'no-tasks':
            return f'write specs/{spec_id}/tasks.md (aidd tasks)'
        return f'aidd review {spec_id}, then aidd rules approve specs/{spec_id}'
    for v in violations:
        if v['fix']:
            return v['fix']
    if verify in ('failed', 'stale', 'never-run'):
        return f'aidd verify specs/{spec_id}'
    if step == 5:
        return f'build the next open task, then aidd verify specs/{spec_id}'
    if step == 6:
        return f'write specs/{spec_id}/qa-audit.md (aidd converge)'
    return f'aidd rules close {spec_id}'


def build_next(spec_dir, root, status=None):
    """Info dict for one spec. `status` (a build_status dict) skips the build_status call. Never raises."""
    info = {'open_spec': False, 'spec': '', 'step': None, 'step_name': '', 'violations': [],
            'approved': 'unknown', 'verify': 'never-run',
            'next': 'aidd search <keywords> (find existing work before a new spec)',
            'note': ''}
    try:
        d = Path(spec_dir) if spec_dir else None
        if d is None or not d.is_dir():
            info['note'] = 'No open spec.' if not spec_dir else f'Spec dir not found: {spec_dir}'
            return info
        st = status
        if st is None:
            mod = _load_status_module()
            if mod is None:
                info['note'] = 'aidd_status unavailable; cannot read the spec state.'
                info['spec'] = d.name
                info['next'] = f'aidd status specs/{d.name}'
                return info
            st = mod.build_status(d, root, named=True)
        verify = _verify_result(st)
        violations = _violations(st.get('why_blocked'))
        step = _infer_step(d, st, verify)
        approval = str((st.get('tasks') or {}).get('approval') or 'unknown')
        info.update({'open_spec': True, 'spec': d.name, 'step': step, 'step_name': STEP_NAMES.get(step, ''),
                     'violations': violations, 'approved': approval, 'verify': verify,
                     'next': _next_command(d.name, step, st, verify, violations)})
    except Exception as e:
        info['note'] = f'Could not read the spec state ({type(e).__name__}).'
    return info


def format_next(info):
    """At most 30 lines of plain text."""
    lines = []
    if not info.get('open_spec'):
        lines.append(info.get('note') or 'No open spec.')
        lines.append('Next: ' + str(info.get('next')))
        return '\n'.join(lines[:MAX_LINES])
    lines.append(f"Spec: {info['spec']}")
    lines.append(f"Step: {info['step']} {info['step_name']}")
    lines.append(f"Approved: {info['approved']}")
    lines.append(f"Last verify: {info['verify']}")
    vs = info.get('violations') or []
    if vs:
        lines.append(f'Open violations ({len(vs)}):')
        for v in vs[:8]:
            lines.append(f"  {v['rule']} {v['message'][:110]}")
            if v['fix']:
                lines.append(f"    fix: {v['fix'][:110]}")
    else:
        lines.append('Open violations: none')
    if info.get('note'):
        lines.append(info['note'])
    lines.append('Next: ' + str(info.get('next')))
    if len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES - 1] + [lines[-1]]
    return '\n'.join(lines)


def _write_next(root, text):
    """Write .aidd/NEXT.md; False when it cannot be written."""
    try:
        if root is None:
            return False
        p = Path(root) / '.aidd' / 'NEXT.md'
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text + '\n', encoding='utf-8')
        return True
    except Exception:
        return False


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == 'next':
        args = args[1:]
    flags = {a for a in args if a.startswith('--')}
    pos = [a for a in args if not a.startswith('--')]
    if flags - {'--write', '--json'} or len(pos) > 1:
        print('usage: aidd next [spec_dir] [--write] [--json]', file=sys.stderr)
        return 2
    spec_dir = pos[0] if pos else ''
    root = _find_root(spec_dir)
    if not spec_dir and root is not None:
        gate = _gate_spec(root)
        if gate and (Path(root) / 'specs' / gate).is_dir():
            spec_dir = str(Path(root) / 'specs' / gate)
    info = build_next(spec_dir, root)
    text = format_next(info)
    if '--write' in flags and not _write_next(root, text):
        print('warning: could not write .aidd/NEXT.md', file=sys.stderr)
    print(json.dumps(info, indent=2, ensure_ascii=False) if '--json' in flags else text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
