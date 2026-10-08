#!/usr/bin/env python3
"""aidd progress — implementation % per spec, measured (no LLM, no third-party graph).

Amendment to spec 004 (graph-first). For every `specs/*/tasks.md` it checks each task's `Target file`
on disk and in the sources, and adds the stages AIDD already records in its own evidence log:

  task state   missing   a target file does not exist
               stub      it exists but is (almost) empty
               present   it exists and has content, but carries no `aidd:<code>` marker of the codes the task satisfies
               marked    it exists and carries an `aidd:<code>` (or `aidd:T-nn`) marker  <- strongest signal
               n/a       the cell holds no file path (waves like `W0.a`, prose): not measurable, counted apart
  spec         Impl% = (present+marked)/measurable, Marked% = marked/measurable, plus approved / verify / audit / closed
  graph        .aidd/graphs/progress.json (nodes: spec and T; edges: contains, targets) for `aidd graphs show progress`

Usage:
    python aidd_progress.py [spec_dir ...] [--root DIR] [--json] [--detail] [--no-write] [--quiet]
Exit 0 always (informational); 2 on usage error. Stdlib only. The existence/marker check measures that the
work is there, not that it works: `aidd verify` and the closing audit still decide that.
"""
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

STUB_BYTES = 40
MAX_READ = 2 * 1024 * 1024
CODE_RE = re.compile(r'\b(?:AC|FR|T|API|US|SCREEN|COMP|CTL)-\d+(?:-F\d+)?', re.I)
TASK_ID_RE = re.compile(r'^[`*\s]*([A-Za-z]+-\d+)[`*\s]*$')
WAVE_RE = re.compile(r'^W\d+(\.\w+)?$', re.I)
PATH_TOKEN_RE = re.compile(r'[\w.\-]+(?:/[\w.\-]+)+/?|[\w\-]+\.[A-Za-z0-9]{1,6}\b')
DONE_RE =re.compile(r'\b(done|closed|hecho|complet\w*)\b|[✅✔]', re.I)


def _cells(line):
    return [c.strip() for c in line.strip().strip('|').split('|')]


def _looks_like_path(p):
    if not p or ' ' in p or '<' in p or '>' in p or WAVE_RE.match(p):
        return False
    return bool(re.search(r'[\\/]', p) or re.search(r'\.[A-Za-z0-9]{1,6}$', p))


def parse_tasks(text):
    """[{id, paths, codes, status}] for every row of a table with a 'Target file' column. Never raises."""
    out, cols = [], None
    try:
        for line in text.splitlines():
            s = line.strip()
            if not s.startswith('|'):
                cols = None
                continue
            cells = _cells(s)
            low = [c.lower() for c in cells]
            tcol = next((i for i, c in enumerate(low) if c.startswith('target file')), None)
            if tcol is not None or (low and low[0] in ('task', 'id', '#') and 'status' in low):
                cols = {'target': tcol,
                        'codes': next((i for i, c in enumerate(low) if 'codes' in c), None),
                        'status': next((i for i, c in enumerate(low) if c == 'status'), None)}
                continue
            if cols is None or set(''.join(cells)) <= set('-: '):
                continue
            m = TASK_ID_RE.match(cells[0]) if cells else None
            if not m:
                continue
            tgt = cols['target']
            raw = (cells[tgt] if tgt is not None and tgt < len(cells) else '').replace('`', ' ').replace('\\', '/')
            paths = []
            for p in PATH_TOKEN_RE.findall(raw):
                p = p.strip('.,;:()')
                if _looks_like_path(p) and p not in paths:
                    paths.append(p)
            codes = []
            if cols['codes'] is not None and cols['codes'] < len(cells):
                codes = sorted({c.upper() for c in CODE_RE.findall(cells[cols['codes']])})
            status = cells[cols['status']] if cols['status'] is not None and cols['status'] < len(cells) else ''
            out.append({'id': m.group(1).upper(), 'paths': paths, 'codes': codes, 'status': status})
    except Exception:
        return out
    return out


def _has_marker(path, codes, tid):
    try:
        if path.stat().st_size > MAX_READ:
            return False
        text = path.read_text(encoding='utf-8', errors='replace')
        keys = [re.escape(c) for c in codes] + [re.escape(tid)]
        return bool(re.search(r'aidd:(?:' + '|'.join(keys) + r')\b', text, re.I))
    except Exception:
        return False


_SKIP_DIRS = {'.git', 'node_modules', '.venv', 'venv', '__pycache__', '.aidd', 'bin', 'obj', 'dist', 'build', '.next'}
_INDEX = {}


def _index(root):
    """Sorted root-relative posix paths of the project's files (cached per root, capped), for suffix lookups."""
    key = str(root)
    if key not in _INDEX:
        out = []
        try:
            stack = [Path(root)]
            while stack and len(out) < 100000:
                cur = stack.pop()
                for e in cur.iterdir():
                    if e.is_dir():
                        if e.name not in _SKIP_DIRS:
                            stack.append(e)
                    else:
                        out.append(e.relative_to(root).as_posix())
        except Exception:
            pass
        _INDEX[key] = sorted(out)
    return _INDEX[key]


def _resolve(root, p):
    """The existing file/dir for a task path: `root/p`, else the project file whose path ends with `/p`
    (specs often write paths relative to a sub-folder such as `skill/`). None when there is none."""
    fp = Path(root) / p
    if fp.exists():
        return fp
    tail = '/' + p.strip('/')
    for rel in _index(root):
        if rel.endswith(tail):
            return Path(root) / rel
    return None


def task_state(task, root):
    """missing | stub | present | marked | n/a for one parsed task."""
    paths = task['paths']
    if not paths:
        return 'n/a'
    files = []
    for p in paths:
        fp = _resolve(root, p)
        if fp is None:
            return 'missing'
        files.append(fp)
    if any(f.is_file() and f.stat().st_size < STUB_BYTES for f in files):
        return 'stub'
    if any(f.is_file() and _has_marker(f, task['codes'], task['id']) for f in files):
        return 'marked'
    return 'present'


def _stages(root, d, tasks_text):
    st = {'approved': '?', 'verify': '?', 'audit': '?', 'closed': '?'}
    try:
        import aidd_evidence as ev
        import aidd_rules as rules
    except Exception:
        return st
    try:
        st['approved'] = 'yes' if rules.approval_valid(tasks_text) else 'no'
    except Exception:
        pass
    run = None
    try:
        run = ev.latest_verify_run(root, d.name)
        st['verify'] = 'none' if not run else ('passed' if run.get('ok') else 'failed')
    except Exception:
        pass
    try:
        rscope = [str(x) for x in ((run or {}).get('code_scope') or [])]
        since = max((ev.last_code_edit_ts(root, rscope) if rscope else ev.last_code_edit_ts(root)),
                    float((run or {}).get('code_since') or (run or {}).get('ts') or 0.0))
        req = rules.required_domains(d)
        miss = rules.uncovered_domains(root, None, d.name, since, spec_dir=d)
        st['audit'] = '%d/%d' % (len(req) - len(miss), len(req))
    except Exception:
        pass
    try:
        closed = any(str(e['detail'].get('spec') or '') == d.name for e in ev.events(root, kind='spec_closed'))
        st['closed'] = 'yes' if closed else 'no'
    except Exception:
        pass
    return st


def measure(root, spec_dir):
    d = Path(spec_dir)
    tasks_md = d / 'tasks.md'
    text = tasks_md.read_text(encoding='utf-8', errors='replace') if tasks_md.is_file() else ''
    rows = []
    for t in parse_tasks(text):
        rows.append({**t, 'state': task_state(t, root), 'declared_done': bool(DONE_RE.search(t['status']))})
    n = {k: sum(1 for r in rows if r['state'] == k) for k in ('missing', 'stub', 'present', 'marked', 'n/a')}
    stages = _stages(root, d, text)
    if stages['closed'] == 'yes':
        stages['audit'] = 'closed'      # the closing audit already happened; a later edit is not a pending audit
    measurable = len(rows) - n['n/a']
    impl = n['present'] + n['marked']
    pct = lambda x: round(100.0 * x / measurable, 1) if measurable else None
    return {'spec': d.name, 'tasks': len(rows), 'measurable': measurable, **{k.replace('/', ''): v for k, v in n.items()},
            'impl_pct': pct(impl), 'marked_pct': pct(n['marked']),
            'declared_done': sum(1 for r in rows if r['declared_done']),
            'declared_pct': round(100.0 * sum(1 for r in rows if r['declared_done']) / len(rows), 1) if rows else None,
            'stages': stages, 'rows': rows}


def graph(root, results):
    nodes, edges = [], []
    for r in results:
        sid = 'spec:' + r['spec']
        nodes.append({'id': sid, 'type': 'spec', 'label': r['spec'], 'impl_pct': r['impl_pct'],
                      'marked_pct': r['marked_pct'], 'tasks': r['tasks'], **{'stage_' + k: v for k, v in r['stages'].items()}})
        for t in r['rows']:
            tid = '%s/%s' % (r['spec'], t['id'])
            nodes.append({'id': tid, 'type': 'T', 'label': t['id'], 'state': t['state'], 'status': t['status'],
                          'codes': t['codes']})
            edges.append({'source': sid, 'target': tid, 'relation': 'contains'})
            for p in t['paths']:
                edges.append({'source': tid, 'target': p, 'relation': 'targets'})
    return {'generated': time.time(), 'nodes': nodes, 'edges': edges}


def _pct(v):
    return '  n/a' if v is None else '%5.1f' % v


def render(results, detail=False):
    head = '%-34s %5s %6s %6s %6s %5s %5s %4s %-8s %-7s %-6s %-6s' % (
        'Spec', 'Tasks', 'Impl%', 'Mark%', 'Decl%', 'Miss', 'Stub', 'N/A', 'Approved', 'Verify', 'Audit', 'Closed')
    lines = [head, '-' * len(head)]
    tot = {'tasks': 0, 'measurable': 0, 'impl': 0, 'marked': 0}
    for r in results:
        s = r['stages']
        lines.append('%-34s %5d %6s %6s %6s %5d %5d %4d %-8s %-7s %-6s %-6s' % (
            r['spec'][:34], r['tasks'], _pct(r['impl_pct']), _pct(r['marked_pct']), _pct(r['declared_pct']), r['missing'], r['stub'],
            r['na'], s['approved'], s['verify'], s['audit'], s['closed']))
        tot['tasks'] += r['tasks']
        tot['measurable'] += r['measurable']
        tot['impl'] += r['present'] + r['marked']
        tot['marked'] += r['marked']
    if tot['measurable']:
        lines.append('-' * len(head))
        lines.append('%-34s %5d %6s %6s          (measurable %d of %d tasks)' % (
            'TOTAL', tot['tasks'], _pct(100.0 * tot['impl'] / tot['measurable']),
            _pct(100.0 * tot['marked'] / tot['measurable']), tot['measurable'], tot['tasks']))
    if detail:
        for r in results:
            todo = [t for t in r['rows'] if t['state'] in ('missing', 'stub', 'n/a')]
            if todo:
                lines.append('')
                lines.append('%s: %d task(s) not implemented or not measurable' % (r['spec'], len(todo)))
                for t in todo:
                    lines.append('  %-7s %-8s %s' % (t['id'], t['state'], ', '.join(t['paths'])[:90]))
    lines.append('')
    lines.append('Decl% = tasks whose Status cell says done (hand-written, not measured). Impl% = target files present; '
                 'Mark% = they also carry aidd:<code>. Existence is not correctness: '
                 'aidd verify and the closing audit decide that.')
    return '\n'.join(lines)


def main(argv):
    flags = {a for a in argv if a.startswith('--') and a != '--root'}
    rest, root = [], None
    it = iter(range(len(argv)))
    for i in it:
        a = argv[i]
        if a == '--root':
            if i + 1 >= len(argv):
                print('usage: aidd_progress.py [spec_dir ...] [--root DIR] [--json] [--detail] [--no-write]', file=sys.stderr)
                return 2
            root = Path(argv[i + 1])
            next(it, None)
        elif not a.startswith('--'):
            rest.append(a)
    root = (root or Path.cwd()).resolve()
    dirs = [Path(a) if Path(a).is_dir() else root / 'specs' / a for a in rest] \
        or sorted(p.parent for p in (root / 'specs').glob('*/tasks.md'))
    results = [measure(root, d) for d in dirs if (d / 'tasks.md').is_file()]
    if not results:
        print('No spec with a tasks.md found under %s' % (root / 'specs'), file=sys.stderr)
        return 2
    if '--no-write' not in flags:
        try:
            out = root / '.aidd' / 'graphs' / 'progress.json'
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(graph(root, results), ensure_ascii=False), encoding='utf-8')
        except Exception as ex:
            print('warning: progress graph not written (%s)' % ex, file=sys.stderr)
    if '--quiet' in flags:
        return 0
    if '--json' in flags:
        print(json.dumps([{k: v for k, v in r.items() if k != 'rows'} for r in results], ensure_ascii=False, indent=2))
        return 0
    print(render(results, '--detail' in flags))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
