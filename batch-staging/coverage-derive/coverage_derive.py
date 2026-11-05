#!/usr/bin/env python3
"""coverage_derive.py - PROTOTYPE (draft amendment 05 to spec 007). Stdlib only.

Proposes, per `## Verification` row of one spec, the task-level `Covers` (T-nn list) and the
`Inputs` (project-relative globs = target files of those tasks) that `aidd verify --changed` and
`aidd verify --tasks` need, and says HOW each proposal was derived:

  cites-tasks    the row's Covers already names T-nn (kept; FR/AC/API codes in it add tasks)
  via-fr-ac-api  the row cites FR/AC/API/SCREEN/COMP/CTL/US codes that tasks.md `Codes satisfied` cites
  whole-suite    the row cites no code (free text / regression / full suite): Covers = all tasks,
                 Inputs = every target of the spec (conservative: runs on any spec change)
  unresolved     the row cites codes no task cites: NO Inputs proposed (the row stays unselectable)

DRY-RUN by default. `--apply-to FILE` writes a proposal file and never the spec itself. Never shrinks an
existing explicit Covers/Inputs (union only). Database rows (db_verify, psql, docker, pg_prove, --tap)
never get a Reuse declaration; they only get Covers/Inputs for selection.

Usage: coverage_derive.py <spec_dir> [--apply-to FILE] [--json] [--changed-file F ...]
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

UNCONFIRMED = '[Proposed — unconfirmed]'
PROPOSAL_MARK = '<!-- coverage_derive proposal: not part of any spec; review and copy by hand -->'
METADATA = ('spec.md', 'tasks.md', 'plan.md', 'contracts.md', 'mockup-audit.md')
DB_RE = re.compile(r'db_verify|\bpsql\b|\bdocker\b|pg_prove|--tap\b', re.I)
SUITE_RE = re.compile(r'\b(?:todos|toda|todas|suite|completa|complete|regresi\w*|regression|all|full|whole)\b', re.I)
TASK_RE = re.compile(r'\bT-(\d+)\b', re.I)
CODE_PREFIXES = r'(?:FR|AC|API|SCREEN|COMP|CTL|US)'
CODE_RE = re.compile(r'\b(' + CODE_PREFIXES + r')-(\d+)((?:-F\d+)?)', re.I)
RANGE_RE = re.compile(r'\b(' + CODE_PREFIXES + r'|T)-(\d+)((?:-F\d+)?)\s*(?:\.\.|…|–|—|\bto\b|\ba\b)\s*'
                      r'(?:(' + CODE_PREFIXES + r'|T)-)?(\d+)\b', re.I)
MAX_RANGE = 400
T_RANGE_RE = re.compile(r'\bT-(\d+)\s*(?:\.\.|–|—|\bto\b)\s*T-(\d+)\b', re.I)   # same forms as aidd_status._task_rows


def _scripts_dirs(root):
    here = Path(__file__).resolve()
    out = []
    env = os.environ.get('AIDD_SCRIPTS')
    if env:
        out.append(Path(env))
    out.append(Path(root) / '.aidd' / 'scripts')
    out.append(here.parents[2] / 'skill' / 'scripts')
    return [p for p in out if (p / 'aidd_progress.py').is_file()]


def load_aidd(root):
    """Import aidd_progress (required) and aidd_rules / aidd_evidence (optional) from the project or AIDD."""
    dirs = _scripts_dirs(root)
    if not dirs:
        raise SystemExit('aidd_progress.py not found (project .aidd/scripts, AIDD skill/scripts or $AIDD_SCRIPTS)')
    sys.path.insert(0, str(dirs[0]))
    import aidd_progress
    mods = {'progress': aidd_progress, 'rules': None, 'evidence': None, 'scripts': str(dirs[0])}
    for key, name in (('rules', 'aidd_rules'), ('evidence', 'aidd_evidence')):
        try:
            mods[key] = __import__(name)
        except Exception:
            mods[key] = None
    return mods


def find_root(spec_dir):
    spec_dir = Path(spec_dir).resolve()
    if spec_dir.parent.name == 'specs':
        return spec_dir.parent.parent
    for p in [spec_dir, *spec_dir.parents]:
        if (p / 'specs').is_dir() and ((p / '.aidd').is_dir() or (p / '.git').exists()):
            return p
    return spec_dir.parent


def _norm(prefix, num, suffix=''):
    return f'{prefix.upper()}-{int(num)}{(suffix or "").upper()}'


def codes_in(text):
    """Normalised FR/AC/API/... codes in text, ranges expanded (FR-001 to FR-012, SCREEN-125..128)."""
    text = text or ''
    out = set()
    for pre, a, suf, pre2, b in RANGE_RE.findall(text):
        if pre.upper() == 'T' or (pre2 and pre2.upper() != pre.upper()):
            continue
        lo, hi = int(a), int(b)
        if lo < hi and hi - lo <= MAX_RANGE:
            out.update(_norm(pre, n, suf) for n in range(lo, hi + 1))
    out.update(_norm(p, n, s) for p, n, s in CODE_RE.findall(text))
    return out


def tasks_in(text, known=None):
    """T-nn ids in text with T-a..T-b ranges expanded against the known ids (or numerically)."""
    text = text or ''
    out = {_norm('T', n) for n in TASK_RE.findall(text)}
    for a, b in T_RANGE_RE.findall(text):
        lo, hi = int(a), int(b)
        if lo < hi and hi - lo <= MAX_RANGE:
            out.update(_norm('T', n) for n in range(lo, hi + 1))
    if known is not None:
        canon = {_norm('T', t[2:]): t for t in known}
        return {canon.get(t, t) for t in out}
    return out


def _split(line):
    return [c.strip() for c in line.strip().strip('|').split('|')]


def raw_task_codes(tasks_text):
    """{task_id: set(codes)} from the raw `Codes satisfied` cell (ranges expanded) and `- Cites:` lines
    under `### T-nn` headings. Complements aidd_progress.parse_tasks, whose CODE_RE does not expand ranges."""
    out = {}
    cols = None
    for line in tasks_text.splitlines():
        s = line.strip()
        if not s.startswith('|'):
            cols = None
            continue
        cells = _split(s)
        low = [c.lower() for c in cells]
        if any(c.startswith('target file') for c in low):
            cols = next((i for i, c in enumerate(low) if 'codes' in c), None)
            continue
        if cols is None or cols >= len(cells):
            continue
        m = re.match(r'^[`*\s]*(T-\d+)\b', cells[0], re.I)
        if m:
            out.setdefault(_norm('T', m.group(1)[2:]), set()).update(codes_in(cells[cols]))
    current = None
    for line in tasks_text.splitlines():
        h = re.match(r'^\s*#{2,4}\s+(T-\d+)\b', line, re.I)
        if h:
            current = _norm('T', h.group(1)[2:])
            continue
        if re.match(r'^\s*#{1,4}\s', line):
            current = None
            continue
        c = re.match(r'^\s*[-*]\s*\**Cites\**\s*:(.*)$', line, re.I)
        if current and c:
            out.setdefault(current, set()).update(codes_in(c.group(1)))
    return out


def parse_rows(spec_text, rules):
    if rules is not None:
        rows = rules.parse_verification(spec_text)
        if rows:
            return rows
    m = re.search(r'(?ms)^#{1,3}\s+Verification\s*\n(.*?)(?=^#{1,3}\s|\Z)', spec_text)
    if not m:
        return []
    lines = [ln for ln in m.group(1).splitlines() if ln.strip().startswith('|')]
    if len(lines) < 3:
        return []
    hdr = [c.lower() for c in _split(lines[0])]

    def col(*names):
        return next((i for i, h in enumerate(hdr) if h in names), None)
    ni, ci, ei, vi, ii = col('#', 'n', 'no', 'no.'), col('command', 'cmd'), col('expected'), col('covers'), col('inputs')
    out = []
    for ln in lines[2:]:
        r = _split(ln) + [''] * len(hdr)
        if ci is None or not r[ci].strip('` '):
            continue
        item = {'n': r[ni] if ni is not None else str(len(out) + 1), 'cmd': r[ci].strip('`'),
                'expected': r[ei].strip('`') if ei is not None else '', 'covers': r[vi] if vi is not None else ''}
        if ii is not None:
            item['inputs'] = sorted({x.strip().strip('`') for x in r[ii].split(',') if x.strip()})
        out.append(item)
    return out


def _exists(root, pattern):
    p = pattern.replace('\\', '/')
    if any(ch in p for ch in '*?['):
        try:
            return any(f.is_file() for f in Path(root).glob(p))
        except (ValueError, OSError):
            return False
    return (Path(root) / p).is_file()


def derive(spec_dir, mods=None):
    """Return {'spec', 'root', 'tasks', 'rows': [...], 'uncovered_tasks', 'summary'} for one spec dir."""
    spec_dir = Path(spec_dir).resolve()
    root = find_root(spec_dir)
    mods = mods or load_aidd(root)
    spec_text = (spec_dir / 'spec.md').read_text(encoding='utf-8', errors='replace')
    try:
        tasks_text = (spec_dir / 'tasks.md').read_text(encoding='utf-8', errors='replace')
    except OSError:
        tasks_text = ''
    tasks = mods['progress'].parse_tasks(tasks_text)
    task_ids = []
    paths = {}
    code_to = {}
    extra = raw_task_codes(tasks_text)
    for t in tasks:
        tid = t['id'].upper() if re.fullmatch(r'T-\d+', t['id'], re.I) else None   # keep the ID as written (verify compares literally)
        if not tid:
            continue
        if tid not in paths:
            task_ids.append(tid)
            paths[tid] = []
        for p in t['paths']:
            if p not in paths[tid]:
                paths[tid].append(p)
        for c in set(codes_in(' '.join(t.get('codes') or []))) | extra.get(_norm('T', tid[2:]), set()):
            code_to.setdefault(c, set()).add(tid)
    known = set(task_ids)
    all_targets = sorted({p for tid in task_ids for p in paths[tid]})
    missing_targets = sorted(p for p in all_targets if not _exists(root, p))
    rows_out = []
    for i, row in enumerate(parse_rows(spec_text, mods.get('rules')), 1):
        covers = row.get('covers') or ''
        existing_inputs = list(row.get('inputs') or [])
        cited_tasks = tasks_in(covers, known)
        unknown_tasks = sorted(cited_tasks - known)
        codes = codes_in(covers)
        via = set()
        resolved_codes, unresolved_codes = set(), set()
        for c in codes:
            if c in code_to:
                via |= code_to[c]
                resolved_codes.add(c)
            else:
                unresolved_codes.add(c)
        notes = []
        if cited_tasks:
            kind = 'cites-tasks'
            proposed = (cited_tasks & known) | via
        elif via:
            kind = 'via-fr-ac-api'
            proposed = set(via)
        elif not codes or SUITE_RE.search(covers):
            kind = 'whole-suite'
            proposed = set(known)
        else:
            kind = 'unresolved'
            proposed = set()
        unconfirmed = False
        if unknown_tasks:
            unconfirmed = True
            notes.append('Covers names tasks not in tasks.md: ' + ', '.join(unknown_tasks))
        if kind in ('cites-tasks', 'via-fr-ac-api') and unresolved_codes:
            unconfirmed = True
            notes.append('codes no task cites: ' + ', '.join(sorted(unresolved_codes)))
        if kind == 'whole-suite':
            unconfirmed = True
            notes.append('no code in Covers; whole spec assumed')
        if kind == 'unresolved':
            notes.append('codes no task cites: ' + ', '.join(sorted(unresolved_codes))
                         + '; no Inputs proposed (row stays unselectable)')
        # Inputs: union of task targets and existing explicit Inputs (never shrink).
        if kind == 'unresolved':
            inputs = list(existing_inputs)
        else:
            inputs = sorted({p for tid in proposed for p in paths.get(tid, [])} | set(existing_inputs))
        absent = [p for p in inputs if not _exists(root, p)]
        if absent:
            unconfirmed = True
            notes.append('Inputs that match no file today (verify would refuse them): ' + ', '.join(absent))
        if kind != 'unresolved' and not inputs:
            unconfirmed = True
            notes.append('selected tasks have no target files')
        ordered = sorted(proposed, key=lambda t: int(t[2:]))
        cov_text = covers
        added = [t for t in ordered if t not in cited_tasks]
        if added:
            cov_text = (covers + '; ' if covers else '') + ', '.join(added)
        db = bool(DB_RE.search(row.get('cmd') or ''))
        rows_out.append({
            'n': row.get('n') or str(i), 'cmd': row.get('cmd') or '', 'expected': row.get('expected') or '',
            'covers_before': covers, 'inputs_before': existing_inputs,
            'kind': kind, 'tasks': ordered, 'covers': cov_text, 'inputs': inputs,
            'database': db, 'reuse': 'none (database row: never reused)' if db else 'not proposed',
            'unconfirmed': unconfirmed, 'notes': notes,
        })
    covered = {t for r in rows_out for t in r['tasks']}
    uncovered = sorted(known - covered, key=lambda t: int(t[2:]))
    summary = {k: sum(1 for r in rows_out if r['kind'] == k)
               for k in ('cites-tasks', 'via-fr-ac-api', 'whole-suite', 'unresolved')}
    with_tasks = [r for r in rows_out if r['tasks']]
    summary['rows'] = len(rows_out)
    summary['tasks'] = len(known)
    summary['avg_tasks_per_row'] = round(sum(len(r['tasks']) for r in with_tasks) / len(with_tasks), 2) if with_tasks else 0
    summary['database_rows'] = sum(1 for r in rows_out if r['database'])
    summary['unconfirmed_rows'] = sum(1 for r in rows_out if r['unconfirmed'])
    summary['uncovered_tasks'] = len(uncovered)
    summary['missing_targets'] = len(missing_targets)
    return {'spec': spec_dir.name, 'root': str(root), 'scripts': mods['scripts'], 'rows': rows_out,
            'uncovered_tasks': uncovered, 'missing_targets': missing_targets, 'summary': summary}


def _matcher(mods, globs):
    ev = mods.get('evidence') if mods else None
    if ev is not None:
        try:
            rx = ev._scope_re(globs)
            return lambda rel: rx is not None and ev.in_scope(rel, rx)
        except (ValueError, re.error):
            return lambda rel: False
    import fnmatch
    return lambda rel: any(fnmatch.fnmatchcase(rel, g) for g in globs)


def simulate_changed(result, changed, mods=None):
    """`aidd verify <spec> --changed` semantics (aidd_status._changed_task_selection + _task_rows) applied to
    the PROPOSED Covers/Inputs. Returns {'status': refused|ok, 'reason', 'selected_tasks', 'rows_run', 'rows_skipped'}."""
    changed = [c.replace('\\', '/') for c in changed]
    spec = result['spec']
    meta = {f'specs/{spec}/{m}'.lower() for m in METADATA}
    total = len(result['rows'])
    if any(c.lower() in meta for c in changed):
        return {'status': 'refused', 'reason': 'spec policy changed', 'selected_tasks': [], 'rows_run': total, 'rows_skipped': 0}
    if not result['rows'] or any(not r['inputs'] or not r['tasks'] for r in result['rows']):
        return {'status': 'refused', 'reason': 'a row has no Inputs or no task Covers',
                'selected_tasks': [], 'rows_run': total, 'rows_skipped': 0}
    if result['uncovered_tasks']:
        return {'status': 'refused', 'reason': 'tasks missing verification rows',
                'selected_tasks': [], 'rows_run': total, 'rows_skipped': 0}
    selected = set()
    for r in result['rows']:
        hit = _matcher(mods, r['inputs'])
        if any(hit(c) for c in changed):
            selected.update(r['tasks'])
    if not selected:
        return {'status': 'refused', 'reason': 'no declared task Inputs match the Git changes (nothing to run)',
                'selected_tasks': [], 'rows_run': 0, 'rows_skipped': total}
    run = [r for r in result['rows'] if selected & set(r['tasks'])]
    return {'status': 'ok', 'reason': '', 'selected_tasks': sorted(selected, key=lambda t: int(t[2:])),
            'rows_run': len(run), 'rows_skipped': total - len(run)}


def render_text(result):
    out = [f"spec {result['spec']}  (root {result['root']}; aidd scripts {result['scripts']})"]
    for r in result['rows']:
        flag = f' {UNCONFIRMED}' if r['unconfirmed'] else ''
        out.append(f"- row {r['n']} [{r['kind']}]{flag}{'  (database row)' if r['database'] else ''}")
        out.append(f"    Covers: {r['covers'] or '(unchanged, empty)'}")
        out.append(f"    Inputs: {', '.join(r['inputs']) if r['inputs'] else '(none: row stays unselectable)'}")
        out.append(f"    Reuse:  {r['reuse']}")
        for n in r['notes']:
            out.append(f'    note: {n}')
    s = result['summary']
    out.append('summary: ' + ', '.join(f'{k}={v}' for k, v in s.items()))
    if result['uncovered_tasks']:
        out.append('tasks no row covers (verify --changed/--tasks would refuse): ' + ', '.join(result['uncovered_tasks']))
    out.append('DRY-RUN: nothing was written.')
    return '\n'.join(out)


def _cell(text):
    return str(text).replace('|', '\\|').replace('\n', ' ')


def render_proposal(result):
    lines = [PROPOSAL_MARK, '', f"# Coverage proposal — {result['spec']}", '',
             'Generated by coverage_derive.py (prototype). Review every row; copy accepted cells into the spec by hand.',
             f'Rows marked {UNCONFIRMED} need the owner\'s confirmation. Database rows never get a Reuse declaration.', '',
             '| # | Command | Expected | Covers | Inputs | Derivation | Notes |', '|---|---|---|---|---|---|---|']
    for r in result['rows']:
        kind = r['kind'] + (f' {UNCONFIRMED}' if r['unconfirmed'] else '')
        lines.append('| ' + ' | '.join(_cell(x) for x in (
            r['n'], '`' + r['cmd'] + '`', r['expected'], r['covers'], ', '.join(r['inputs']), kind, '; '.join(r['notes']))) + ' |')
    lines += ['', 'Summary: ' + ', '.join(f'{k}={v}' for k, v in result['summary'].items()), '']
    return '\n'.join(lines)


def safe_target(spec_dir, target):
    """Refuse writing the spec's own policy files or clobbering a file that is not an earlier proposal."""
    spec_dir = Path(spec_dir).resolve()
    t = Path(target).resolve()
    if t.parent == spec_dir and t.name.lower() in METADATA:
        return 'refused: --apply-to cannot be a spec policy file (' + t.name + ')'
    if t.name.lower() in METADATA:
        return 'refused: --apply-to cannot be named like a spec policy file (' + t.name + ')'
    if t.exists():
        try:
            head = t.read_text(encoding='utf-8', errors='replace').splitlines()[:1]
        except OSError:
            return 'refused: cannot read existing target'
        if head != [PROPOSAL_MARK]:
            return 'refused: target exists and is not a coverage_derive proposal'
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description='Propose task Covers and Inputs for a spec Verification table (dry-run).')
    ap.add_argument('spec_dir')
    ap.add_argument('--apply-to', metavar='FILE', help='write the proposal to FILE (never the spec)')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--changed-file', action='append', default=[], metavar='PATH',
                    help='simulate `aidd verify --changed` with these root-relative changed paths')
    a = ap.parse_args(argv)
    spec_dir = Path(a.spec_dir)
    if not (spec_dir / 'spec.md').is_file():
        print(f'refused: {spec_dir} has no spec.md')
        return 2
    mods = load_aidd(find_root(spec_dir))
    result = derive(spec_dir, mods)
    if a.changed_file:
        result['changed_simulation'] = simulate_changed(result, a.changed_file, mods)
    if a.apply_to:
        problem = safe_target(spec_dir, a.apply_to)
        if problem:
            print(problem)
            return 2
        Path(a.apply_to).write_text(render_proposal(result), encoding='utf-8')
    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_text(result))
        if 'changed_simulation' in result:
            print('changed simulation: ' + json.dumps(result['changed_simulation'], ensure_ascii=False))
        if a.apply_to:
            print(f'proposal written to {a.apply_to} (spec untouched)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
