#!/usr/bin/env python3
"""aidd coverage — propose task `Covers` and `Inputs` for a spec's `## Verification` rows (spec 007, amendment 05).

For every Verification row it proposes the task-level `Covers` (T-nn list) and the `Inputs` (root-relative
paths = target files of those tasks) that `aidd verify --changed` / `--tasks` need, and says how each was derived:

  cites-tasks    the row's Covers already names T-nn or a T-a..T-b range (FR/AC/API codes in it add tasks)
  via-fr-ac-api  the row cites FR/AC/API/SCREEN/COMP/CTL/US codes that at least one task cites
  whole-suite    no code in Covers, or a suite word: every task, every target (needs review)
  unresolved     codes present, none cited by any task: Covers unchanged, only the existing Inputs

DRY-RUN by default: the spec is never written. `--apply-to FILE` writes a Markdown proposal that the owner
reviews and copies by hand. Never shrinks an existing Covers/Inputs. Database rows never get a Reuse value.
Git is never called; `--changed-file PATH` simulates `aidd verify --changed` on the proposed values.

Usage: aidd_coverage.py <spec_dir> [--apply-to FILE] [--json] [--changed-file PATH ...]
Exit 0 on success, 2 on refusal (no spec.md, unsafe --apply-to). Stdlib only.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

try:
    import aidd_progress
except Exception:          # fail closed: no task parsing means no proposal
    aidd_progress = None
try:
    import aidd_rules
except Exception:
    aidd_rules = None
try:
    import aidd_evidence
except Exception:
    aidd_evidence = None

REVIEW_MARK = '[Proposed — unconfirmed]'
PROPOSAL_MARK = '<!-- coverage_derive proposal: not part of any spec; review and copy by hand -->'
METADATA = ('spec.md', 'tasks.md', 'plan.md', 'contracts.md', 'mockup-audit.md')
DB_RE = re.compile(r'db_verify|\bpsql\b|\bdocker\b|pg_prove|--tap\b', re.I)
SUITE_RE = re.compile(r'\b(?:todos|toda|todas|suite|completa|complete|regresi[oó]n|regression|all|full|whole)\b', re.I)
TASK_RE = re.compile(r'\bT-(\d+)\b', re.I)
CODE_PREFIXES = r'(?:FR|AC|API|SCREEN|COMP|CTL|US)'
CODE_RE = re.compile(r'\b(' + CODE_PREFIXES + r')-(\d+)((?:-F\d+)?)', re.I)
RANGE_RE = re.compile(r'\b(' + CODE_PREFIXES + r'|T)-(\d+)((?:-F\d+)?)\s*(?:\.\.|…|–|—|\bto\b|\ba\b)\s*'
                      r'(?:(' + CODE_PREFIXES + r'|T)-)?(\d+)\b', re.I)
T_RANGE_RE = re.compile(r'\bT-(\d+)\s*(?:\.\.|–|—|\bto\b)\s*T-(\d+)\b', re.I)   # the forms aidd_status._task_rows accepts
MAX_RANGE = 400
KINDS = ('cites-tasks', 'via-fr-ac-api', 'whole-suite', 'unresolved')
POLICY_REASON = 'spec policy changed'


def _norm(prefix, num, suffix=''):
    return f'{prefix.upper()}-{int(num)}{(suffix or "").upper()}'


def _code_sort(key):
    m = re.match(r'^([A-Z]+)-(\d+)(.*)$', key)
    return (m.group(1), int(m.group(2)), m.group(3)) if m else (key, 0, '')


def _task_num(tid):
    try:
        return int(str(tid)[2:])
    except ValueError:
        return 0


def codes_in(text):
    """{normalised code: code as cited} for FR/AC/API/... codes in text, ranges expanded (`FR-001 to FR-012`,
    `FR-001..FR-012`, `AC-261..268`, en/em dash, `a`; at most MAX_RANGE numbers). The first spelling seen wins;
    expanded members keep the zero padding of the range start. Never raises."""
    out = {}
    try:
        text = text or ''
        for m in CODE_RE.finditer(text):
            pre, num, suf = m.group(1), m.group(2), m.group(3)
            out.setdefault(_norm(pre, num, suf), f'{pre.upper()}-{num}{suf.upper()}')
        for m in RANGE_RE.finditer(text):
            pre, a, suf, pre2, b = m.groups()
            if pre.upper() == 'T' or (pre2 and pre2.upper() != pre.upper()):
                continue
            lo, hi = int(a), int(b)
            if lo < hi and hi - lo <= MAX_RANGE:
                width = len(a)
                for n in range(lo, hi + 1):
                    out.setdefault(_norm(pre, n, suf), f'{pre.upper()}-{str(n).zfill(width)}{suf.upper()}')
    except Exception:
        return out
    return out


def tasks_in(text, known=None):
    """T-nn IDs in text with T-a..T-b ranges expanded. With `known` (IDs as written in tasks.md) each ID maps to
    its written spelling. Never raises."""
    out = set()
    try:
        text = text or ''
        out = {_norm('T', n) for n in TASK_RE.findall(text)}
        for a, b in T_RANGE_RE.findall(text):
            lo, hi = int(a), int(b)
            if lo < hi and hi - lo <= MAX_RANGE:
                out.update(_norm('T', n) for n in range(lo, hi + 1))
        if known is not None:
            canon = {_norm('T', _task_num(t)): t for t in known}
            numbered = {_norm('T', _task_num(t)) for t in out}
            return {canon.get(t, t) for t in numbered}
    except Exception:
        return out
    return out


def _named_tasks(text, known):
    """Tasks named one by one in a Covers text (IDs inside a T-a..T-b range do not count). Never raises."""
    try:
        return tasks_in(T_RANGE_RE.sub(' ', text or ''), known)
    except Exception:
        return set()


def _split(line):
    return [c.strip() for c in line.strip().strip('|').split('|')]


def raw_task_codes(tasks_text):
    """{T-n (normalised): set(normalised codes)} from the raw `Codes satisfied` cell (ranges expanded) and the
    `- Cites:` lines under `### T-nn` headings. Never raises."""
    out = {}
    try:
        lines = (tasks_text or '').splitlines()
        col = None
        for line in lines:
            s = line.strip()
            if not s.startswith('|'):
                col = None
                continue
            cells = _split(s)
            low = [c.lower() for c in cells]
            if any(c.startswith('target file') for c in low):
                col = next((i for i, c in enumerate(low) if 'codes' in c), None)
                continue
            if col is None or col >= len(cells):
                continue
            m = re.match(r'^[`*\s]*(T-\d+)\b', cells[0], re.I)
            if m:
                out.setdefault(_norm('T', m.group(1)[2:]), set()).update(codes_in(cells[col]))
        current = None
        for line in lines:
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
    except Exception:
        return out
    return out


def find_root(spec_dir):
    spec_dir = Path(spec_dir).resolve()
    if spec_dir.parent.name == 'specs':
        return spec_dir.parent.parent
    for p in [spec_dir, *spec_dir.parents]:
        if (p / 'specs').is_dir() and ((p / '.aidd').is_dir() or (p / '.git').exists()):
            return p
    return spec_dir.parent


def _read(path):
    try:
        return Path(path).read_text(encoding='utf-8', errors='replace')
    except (OSError, ValueError):
        return ''


def _safe_rel(p):
    p = str(p or '').replace('\\', '/').strip()
    while p.startswith('./'):
        p = p[2:]
    if not p or p.startswith('/') or ':' in p or '..' in p.split('/') or '\x00' in p:
        return None
    return p


def _rel_of(root, fp):
    """Root-relative POSIX path of an existing file (`<dir>/**` for a directory), or None."""
    try:
        if fp is None:
            return None
        fp = Path(fp)
        if not fp.exists():
            return None
        rel = fp.resolve().relative_to(Path(root).resolve()).as_posix()
        if not rel or rel == '.':
            return None
        return rel.rstrip('/') + '/**' if fp.is_dir() else rel
    except (OSError, ValueError):
        return None
    except Exception:
        return None


def _resolve_target(root, p):
    """aidd:FR-243 the root-relative path of a task target: `root/p`, else `aidd_progress._resolve` (suffix),
    `_renumbered`, `_alias_target` in that order; a directory becomes `<dir>/**`. None when nothing matches."""
    p = _safe_rel(p)
    if p is None:
        return None
    try:
        direct = _rel_of(root, Path(root) / p)
        if direct is not None:
            return direct
        if aidd_progress is None:
            return None
        for fn in (aidd_progress._resolve, aidd_progress._renumbered, aidd_progress._alias_target):
            try:
                found = _rel_of(root, fn(root, p))
            except Exception:
                found = None
            if found is not None:
                return found
    except Exception:
        return None
    return None


def _exists(root, pattern):
    p = _safe_rel(pattern)
    if p is None:
        return False
    try:
        if any(ch in p for ch in '*?['):
            return any(f.is_file() for f in Path(root).glob(p))
        return (Path(root) / p).exists()
    except (ValueError, OSError):
        return False
    except Exception:
        return False


def _matcher(globs):
    """Root-relative path predicate using the canonical scope matcher; malformed globs match nothing."""
    try:
        if aidd_evidence is not None:
            rx = aidd_evidence._scope_re(globs)
            return lambda rel: rx is not None and aidd_evidence.in_scope(rel, rx)
        import fnmatch
        pats = [str(g).replace('\\', '/') for g in globs or []]
        return lambda rel: any(fnmatch.fnmatchcase(rel, g) for g in pats)
    except Exception:
        return lambda rel: False


def _parse_rows(spec_text):
    if aidd_rules is None:
        return []
    try:
        return aidd_rules.parse_verification(spec_text) or []
    except Exception:
        return []


def _empty_result(spec_dir, root):
    return {'spec': Path(spec_dir).name, 'root': str(root), 'rows': [], 'uncovered_tasks': [],
            'missing_targets': [], 'summary': _summary([], set(), [], []), 'task_targets': {}}


def _summary(rows, known, uncovered, missing):
    s = {k: sum(1 for r in rows if r['kind'] == k) for k in KINDS}
    s['rows'] = len(rows)
    s['tasks'] = len(known)
    s['database_rows'] = sum(1 for r in rows if r['database'])
    s['needs_review_rows'] = sum(1 for r in rows if r['needs_review'])
    s['uncovered_tasks'] = len(uncovered)
    s['missing_targets'] = len(missing)
    return s


def derive(spec_dir):
    """{spec, root, rows, uncovered_tasks, missing_targets, summary, task_targets} for one spec dir. Never raises."""
    spec_dir = Path(spec_dir)
    try:
        spec_dir = spec_dir.resolve()
        root = find_root(spec_dir)
    except Exception:
        root = spec_dir.parent
    try:
        return _derive(spec_dir, root)
    except Exception:
        return _empty_result(spec_dir, root)


def _derive(spec_dir, root):
    spec_text = _read(spec_dir / 'spec.md')
    tasks_text = _read(spec_dir / 'tasks.md')
    parsed = aidd_progress.parse_tasks(tasks_text) if aidd_progress is not None else []
    extra = raw_task_codes(tasks_text)
    task_ids, raw_paths, code_to = [], {}, {}
    for t in parsed:
        tid = str(t.get('id') or '').upper()
        if not re.fullmatch(r'T-\d+', tid):
            continue
        if tid not in raw_paths:
            task_ids.append(tid)
            raw_paths[tid] = []
        deleted = set(t.get('delete') or [])
        for p in t.get('paths') or []:
            if p not in deleted and p not in raw_paths[tid]:
                raw_paths[tid].append(p)
        codes = set(codes_in(' '.join(t.get('codes') or []))) | extra.get(_norm('T', _task_num(tid)), set())
        for c in codes:
            code_to.setdefault(c, set()).add(tid)
    known = set(task_ids)
    resolved, missing = {}, set()          # raw target -> resolved rel or None
    for tid in task_ids:
        for p in raw_paths[tid]:
            if p not in resolved:
                resolved[p] = _resolve_target(root, p)
                if resolved[p] is None:
                    missing.add(p)
    task_targets = {tid: sorted({resolved[p] for p in raw_paths[tid] if resolved[p]}) for tid in task_ids}
    rows_out = []
    for i, row in enumerate(_parse_rows(spec_text), 1):
        rows_out.append(_derive_row(i, row, known, task_ids, raw_paths, resolved, code_to, root))
    covered = {t for r in rows_out for t in r['tasks']}
    uncovered = sorted(known - covered, key=_task_num)
    missing_sorted = sorted(missing)
    return {'spec': spec_dir.name, 'root': str(root), 'rows': rows_out, 'uncovered_tasks': uncovered,
            'missing_targets': missing_sorted, 'summary': _summary(rows_out, known, uncovered, missing_sorted),
            'task_targets': task_targets}


def _derive_row(i, row, known, task_ids, raw_paths, resolved, code_to, root):
    covers = str(row.get('covers') or '')
    existing = list(row.get('inputs') or [])
    cited = tasks_in(covers, known)
    unknown = sorted(cited - known, key=_task_num)
    codes = codes_in(covers)
    via, unresolved_codes = set(), []
    for key in sorted(codes, key=_code_sort):
        if key in code_to:
            via |= code_to[key]
        else:
            unresolved_codes.append(codes[key])
    notes = []
    if cited:
        kind, proposed = 'cites-tasks', (cited & known) | via
    elif via:
        kind, proposed = 'via-fr-ac-api', set(via)
    elif not codes or SUITE_RE.search(covers):
        kind, proposed = 'whole-suite', set(known)
    else:
        kind, proposed = 'unresolved', set()
    review = False
    if unknown:
        review = True
        notes.append('Covers names tasks not in tasks.md: ' + ', '.join(unknown))
    if kind in ('cites-tasks', 'via-fr-ac-api') and unresolved_codes:
        review = True
        notes.append('codes no task cites: ' + ', '.join(unresolved_codes))
    if kind == 'whole-suite':
        review = True
        notes.append('no code in Covers (or a suite word); whole spec assumed')
    if kind == 'unresolved':
        notes.append('codes no task cites: ' + ', '.join(unresolved_codes) + '; no Inputs proposed')
    ordered = sorted(proposed, key=_task_num)
    if kind == 'unresolved':
        inputs = list(existing)
    else:
        targets = set()
        for tid in ordered:
            for p in raw_paths.get(tid, []):
                rel = resolved.get(p)
                if rel is None:
                    review = True
                    notes.append(f'target {p} of {tid} matches no file; excluded from Inputs')
                    continue
                if rel != p:
                    review = True
                    notes.append(f'target {p} of {tid} resolved to {rel}')
                targets.add(rel)
        if not targets:
            review = True
            notes.append('selected tasks have no target files')
        inputs = sorted(targets | set(existing))
    absent = [p for p in existing if not _exists(root, p)]
    if absent:
        notes.append('existing Inputs that match no file today (verify would refuse them): ' + ', '.join(absent))
    added = [t for t in ordered if t not in cited]
    cov_text = covers
    if added:
        cov_text = (covers + '; ' if covers else '') + ', '.join(added)
    db = bool(DB_RE.search(str(row.get('cmd') or '')))
    seen = set()
    notes = [n for n in notes if not (n in seen or seen.add(n))]
    return {'n': str(row.get('n') or i), 'cmd': str(row.get('cmd') or ''), 'expected': str(row.get('expected') or ''),
            'kind': kind, 'tasks': ordered, 'covers': cov_text, 'inputs': inputs, 'database': db,
            'reuse': 'none (database row: never reused)' if db else 'not proposed',
            'needs_review': review, 'notes': notes, 'covers_before': covers, 'inputs_before': existing}


def _sim(status, reason, total, selected=(), always=(), run=0, warnings=()):
    return {'status': status, 'reason': reason, 'selected_tasks': list(selected), 'always_rows': list(always),
            'rows_run': run, 'rows_skipped': total - run, 'warnings': list(warnings)}


def simulate_changed(result, changed):
    """aidd:FR-248 the FR-259 `aidd verify --changed` rules applied to the PROPOSED Covers/Inputs. Never raises."""
    try:
        return _simulate(result, changed)
    except Exception as e:
        total = len((result or {}).get('rows') or [])
        return _sim('refused', f'simulation failed ({type(e).__name__})', total, run=total)


def _simulate(result, changed):
    changed = [str(c).replace('\\', '/') for c in changed or []]
    rows = list(result.get('rows') or [])
    total = len(rows)
    targets = result.get('task_targets') or {}
    known = set(targets)
    meta = {f"specs/{result.get('spec')}/{m}".lower() for m in METADATA}
    if any(c.lower() in meta for c in changed):
        return _sim('refused', POLICY_REASON, total, run=total)
    if not rows or not known:
        return _sim('refused', 'no verification rows or no tasks', total, run=total)
    for r in rows:
        if tasks_in(r.get('covers') or '', known) - known:
            return _sim('refused', f"verification row {r['n']} names a task not in tasks.md", total, run=total)
    warnings, always = [], []
    for r in rows:
        if not r.get('inputs') or not r.get('tasks'):
            always.append(r['n'])
            warnings.append(f"warning: verification row {r['n']} declares no Inputs or no task Covers; it always runs")
    named = set()
    for r in rows:
        named |= _named_tasks(r.get('covers') or '', known)
    for tid in sorted(known - named, key=_task_num):
        hit = _matcher(targets.get(tid) or [])
        if not any(hit(c) for c in changed):
            continue
        warnings.append(f'warning: task {tid} is covered by no verification row; whole-suite rows run')
        suite = [r['n'] for r in rows if known <= set(r.get('tasks') or [])]
        for n in (suite or [r['n'] for r in rows]):
            if n not in always:
                always.append(n)
    selected = set()
    for r in rows:
        if r.get('inputs') and r.get('tasks'):
            hit = _matcher(r['inputs'])
            if any(hit(c) for c in changed):
                selected.update(r['tasks'])
    if not selected and not always:
        return _sim('refused', 'no declared task Inputs match the changes (nothing to run)', total, warnings=warnings)
    order = [r['n'] for r in rows]
    always = [n for n in order if n in always]
    run = sum(1 for r in rows if r['n'] in always or selected & set(r.get('tasks') or []))
    return _sim('ok', '', total, sorted(selected, key=_task_num), always, run, warnings)


def render_text(result):
    out = [f"spec {result['spec']}  (root {result['root']})"]
    for r in result['rows']:
        flag = f' {REVIEW_MARK}' if r['needs_review'] else ''
        out.append(f"- row {r['n']} [{r['kind']}]{flag}{'  (database row)' if r['database'] else ''}")
        out.append(f"    Covers: {r['covers'] or '(unchanged, empty)'}")
        out.append(f"    Inputs: {', '.join(r['inputs']) if r['inputs'] else '(none: the row always runs under --changed)'}")
        out.append(f"    Reuse:  {r['reuse']}")
        for n in r['notes']:
            out.append(f'    note: {n}')
    out.append('summary: ' + ', '.join(f'{k}={v}' for k, v in result['summary'].items()))
    if result['uncovered_tasks']:
        out.append('tasks no row covers: ' + ', '.join(result['uncovered_tasks']))
    if result['missing_targets']:
        out.append('targets that match no file (excluded): ' + ', '.join(result['missing_targets']))
    out.append('DRY-RUN: the spec was not written; copy accepted cells by hand.')
    return '\n'.join(out)


def _cell(text):
    return str(text).replace('|', '\\|').replace('\n', ' ')


def render_proposal(result):
    lines = [PROPOSAL_MARK, '', f"# Coverage proposal — {result['spec']}", '',
             'Generated by `aidd coverage`. Review every row; copy accepted cells into the spec by hand.',
             f'Rows marked {REVIEW_MARK} need the owner\'s confirmation. Database rows never get a Reuse declaration.', '',
             '| # | Command | Expected | Covers | Inputs | Derivation | Notes |', '|---|---|---|---|---|---|---|']
    for r in result['rows']:
        kind = r['kind'] + (f' {REVIEW_MARK}' if r['needs_review'] else '')
        lines.append('| ' + ' | '.join(_cell(x) for x in (
            r['n'], '`' + r['cmd'] + '`', r['expected'], r['covers'], ', '.join(r['inputs']), kind,
            '; '.join(r['notes']))) + ' |')
    lines += ['', 'Summary: ' + ', '.join(f'{k}={v}' for k, v in result['summary'].items()), '']
    return '\n'.join(lines)


def safe_target(spec_dir, target):
    """aidd:FR-247 None when `--apply-to target` may be written; else the refusal text."""
    try:
        t = Path(target).resolve()
        if t.name.lower() in METADATA:
            return 'refused: --apply-to cannot be a spec policy file (' + t.name + ')'
        if t.exists():
            if not t.is_file():
                return 'refused: --apply-to target is not a file'
            with t.open('r', encoding='utf-8', errors='replace') as fh:
                head = fh.readline().rstrip('\r\n')
            if head != PROPOSAL_MARK:
                return 'refused: target exists and is not a coverage proposal'
        return None
    except Exception as e:
        return f'refused: cannot check --apply-to target ({type(e).__name__})'


def main(argv=None):
    ap = argparse.ArgumentParser(prog='aidd coverage',
                                 description='Propose task Covers and Inputs for a spec Verification table (dry-run).')
    ap.add_argument('spec_dir')
    ap.add_argument('--apply-to', metavar='FILE', help='write the proposal to FILE (never the spec)')
    ap.add_argument('--json', action='store_true', help='print the full result as JSON')
    ap.add_argument('--changed-file', action='append', default=[], metavar='PATH',
                    help='simulate `aidd verify --changed` with this root-relative changed path (repeatable)')
    a = ap.parse_args(argv)
    spec_dir = Path(a.spec_dir)
    try:
        if not (spec_dir / 'spec.md').is_file():
            print(f'refused: {spec_dir} has no spec.md')
            return 2
    except OSError:
        print(f'refused: {spec_dir} cannot be read')
        return 2
    result = derive(spec_dir)
    if a.changed_file:
        result['changed_simulation'] = simulate_changed(result, a.changed_file)
    if a.apply_to:
        problem = safe_target(spec_dir, a.apply_to)
        if problem:
            print(problem)
            return 2
        try:
            Path(a.apply_to).write_text(render_proposal(result), encoding='utf-8')
        except OSError as e:
            print(f'refused: cannot write {a.apply_to} ({type(e).__name__})')
            return 2
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
