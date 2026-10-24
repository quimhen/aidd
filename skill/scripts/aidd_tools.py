#!/usr/bin/env python3
"""aidd tools - catalog of AIDD commands and project tools by task, and `size` (proportional analysis parameters).

Usage:
    python aidd_tools.py [keywords...] [--json] [--root DIR]
    python aidd_tools.py size [--spec ID | --files F...] [--json] [--root DIR]
Catalog (aidd:FR-039): groups verify, graph, db, docs, generate, gate; AIDD commands (static table) plus the project's
own tools (`tools/`, `*/tools/`, `*/scripts/`; .py .ps1 .sh), cached in .aidd/graphs/tools.cache.json by content hash.
Size (aidd:FR-042): classifies XS/S/M/L and prints the analysis parameters of the class. Stdlib only, never raises, exit 0.
"""
import ast
import hashlib
import json
import os
import re
import subprocess
import sys

MAX_LINES = 40
SKIP = {'node_modules', '.git', '.build', '__pycache__', '.aidd', 'build', 'dist'}
EXTS = ('.py', '.ps1', '.sh')
FLAGS = ('--plan', '--check', '--dry-run', '--json')
GROUPS = ('verify', 'graph', 'db', 'docs', 'generate', 'gate')

# (group, name, description)  aidd:FR-039
STATIC = [
    ('verify', 'aidd verify [spec ...] [--bail]', 'runs the verify rows of one or more specs; use it to prove ACs; --bail stops at the first failing row'),
    ('verify', 'aidd triage', 'groups failing test output by cause; use it before reading failures by hand'),
    ('verify', 'aidd job', 'runs a long command detached with a log; use it for anything slow or repetitive'),
    ('verify', 'tests/run_parallel.py --changed', 'runs only the test modules touched by the changes; the default test run for XS/S work'),
    ('verify', 'aidd check <spec>', 'gap-checks a spec (check_spec.py) before a manual audit'),
    ('verify', 'aidd review', 'review status of a spec; read only its status line'),
    ('verify', '--bail', 'flag of aidd verify: stop a spec at its first failing row, rest recorded as not run'),
    ('graph', 'aidd graphs [show|refresh|diff] <name>', 'code/method/sql/spec/progress graphs; use show first, refresh only when stale'),
    ('graph', 'aidd search <text>', 'finds specs and codes by text; use before grepping the repo'),
    ('graph', 'aidd tree', 'spec -> code -> task tree; use it to see what a spec contains'),
    ('graph', 'aidd mem', 'project memory notes; use it to recall decisions across sessions'),
    ('db', 'aidd sqlcheck', 'engine-agnostic static SQL compile; use it on migrations before applying them'),
    ('docs', 'aidd status', 'state of the specs and the pipeline; use it to know where the work stands'),
    ('docs', 'aidd progress', 'measured implementation percent per spec; use it instead of counting tasks by hand'),
    ('docs', 'aidd next', 'next pending step of the pipeline; use it to decide what to do'),
    ('docs', 'aidd pending', 'lists pending items across specs'),
    ('generate', 'aidd tools [keywords]', 'this catalog; run it before doing a repetitive step by hand'),
    ('generate', 'aidd tools size', 'classifies the work XS/S/M/L and prints its analysis parameters'),
    ('gate', 'aidd size', 'alias of `aidd tools size`; paste its Analysis parameters line into prompts'),
    ('gate', 'aidd rules', 'activate/close a spec and run the gate rules; use it at open and close'),
]

# aidd:FR-042 (analysis parameters per class: graph, baseline, tests, verification, audit, agents)
_XS = ('graph: `aidd graphs show` on the existing graph only, no refresh', 'baseline: none',
       'tests: the modules chosen by `tests/run_parallel.py --changed`', 'verification: none beyond those tests',
       "audit: the builder's static check, no auditor", 'agents: one')
PARAMS = {
    'XS': _XS,
    'S': _XS,
    'M': ('graph: incremental refresh of the stale graph', 'baseline: manifest',
          'tests: `tests/run_parallel.py --changed` plus `--deep`', 'verification: `aidd verify --bail` once',
          'audit: one closing auditor', 'agents: one lane per file'),
    'L': ('graph: refresh plus before/after snapshots', 'baseline: manifest plus graph snapshots',
          'tests: `--changed` plus `--deep`, plus the full suite once at close', 'verification: one verify per spec at close',
          'audit: a closing auditor over every required domain', 'agents: waves'),
}
EXCLUDES = {
    'XS': 'a new graph, snapshot, baseline manifest, job, verify run or auditor',
    'S': 'a new graph, snapshot, baseline manifest, job, verify run or auditor',
    'M': 'graph snapshots, the full-suite run and per-domain auditors',
    'L': 'nothing: the full analysis applies',
}
SENSITIVE = (
    ('database', lambda p: p.endswith('.sql') or '/migrations/' in '/' + p or 'supabase' in p.split('/')),
    ('hooks', lambda p: p.startswith('skill/hooks/') or '/skill/hooks/' in p),
    ('CLI', lambda p: p == 'aidd/cli.py' or p.endswith('/aidd/cli.py')),
    ('gate rules', lambda p: os.path.basename(p) in ('aidd_rules.py', 'rule_gate.py')),
)


def _git_hashes(root, paths):
    """Content hashes for `paths` (relative): one git hash-object pass, stdlib blob-sha1 fallback. Never mtime."""
    try:
        r = subprocess.run(['git', 'hash-object', '--stdin-paths'], cwd=root, input='\n'.join(paths) + '\n',
                           capture_output=True, text=True, timeout=60)
        out = r.stdout.split()
        if r.returncode == 0 and len(out) == len(paths):
            return dict(zip(paths, out))
    except Exception:
        pass
    res = {}
    for p in paths:
        try:
            with open(os.path.join(root, p), 'rb') as f:
                d = f.read()
            res[p] = hashlib.sha1(b'blob %d\0' % len(d) + d).hexdigest()
        except Exception:
            res[p] = ''
    return res


def _scan_files(root):
    """Files .py/.ps1/.sh in tools/, */tools/, */scripts/ (depth <= 3), relative with forward slashes."""
    found = []
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if d not in SKIP)
        rel = os.path.relpath(dp, root).replace('\\', '/')
        parts = [] if rel == '.' else rel.split('/')
        if len(parts) >= 3:
            dns[:] = []
        if not parts or len(parts) > 3:
            continue
        if parts[-1] == 'tools' or (parts[-1] == 'scripts' and len(parts) >= 2):
            found += ['/'.join(parts + [fn]) for fn in sorted(fns) if fn.endswith(EXTS)]
    return sorted(set(found))


def _read(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception:
        return ''


def _doc_line(rel, text):
    """First documentation line: module docstring (.py via ast) or first comment/description line (.ps1/.sh)."""
    try:
        if rel.endswith('.py'):
            for ln in (ast.get_docstring(ast.parse(text)) or '').splitlines():
                if ln.strip():
                    return ln.strip()
            return ''
        for ln in text.splitlines()[:40]:
            s = ln.strip()
            if not s or s.startswith('#!') or s in ('<#', '#>', '#', '.SYNOPSIS', '.DESCRIPTION'):
                continue
            if s.startswith('<#'):
                s = s[2:].strip()
                if not s:
                    continue
            elif s.startswith('#'):
                s = s.lstrip('#').strip()
            else:
                break
            if s and not s.startswith('.'):
                return s
    except Exception:
        pass
    return ''


def _group_of(rel, desc):
    t = (rel + ' ' + desc).lower()
    for g, keys in (('db', ('sql', 'db_', 'database', 'migrat', 'supabase', 'pgtap', 'schema')),
                    ('verify', ('verify', 'test', 'check', 'lint', 'validate')),
                    ('graph', ('graph', 'index', 'map')),
                    ('gate', ('gate', 'rule', 'guard')),
                    ('docs', ('doc', 'report', 'readme', 'status'))):
        if any(k in t for k in keys):
            return g
    return 'generate'


def _project_tools(root):
    """Project scan cached by the sha256 of the content hashes of the scanned files (aidd:FR-039)."""
    files = _scan_files(root)
    hashes = _git_hashes(root, files) if files else {}
    key = hashlib.sha256('\n'.join('%s:%s' % (p, hashes.get(p, '')) for p in files).encode('utf-8')).hexdigest()
    cpath = os.path.join(root, '.aidd', 'graphs', 'tools.cache.json')
    try:
        c = json.loads(_read(cpath))
        if c.get('key') == key and isinstance(c.get('tools'), list):
            return c['tools']
    except Exception:
        pass
    tools = []
    for rel in files:
        text = _read(os.path.join(root, rel))
        desc = _doc_line(rel, text)
        tools.append({'group': _group_of(rel, desc), 'name': rel, 'description': desc,
                      'flags': [f for f in FLAGS if f in text]})
    try:
        os.makedirs(os.path.dirname(cpath), exist_ok=True)
        with open(cpath, 'w', encoding='utf-8') as f:
            json.dump({'key': key, 'tools': tools}, f, indent=1, sort_keys=True)
    except Exception:
        pass
    return tools


def catalog(root, keywords, as_json):
    items = [{'group': g, 'name': n, 'description': d, 'flags': [], 'source': 'aidd'} for g, n, d in STATIC]
    for t in _project_tools(root):
        t = dict(t)
        t['source'] = 'project'
        items.append(t)
    kws = [k.lower() for k in keywords]
    if kws:
        items = [i for i in items if all(k in (i['name'] + ' ' + i['group'] + ' ' + i['description']).lower() for k in kws)]
    items.sort(key=lambda i: (GROUPS.index(i['group']) if i['group'] in GROUPS else 99, i['source'] != 'aidd', i['name']))
    if as_json:
        return json.dumps(items, indent=1, sort_keys=True)
    if not items:
        return 'no tools match; try fewer keywords'
    lines, last = [], None
    for i in items:
        if i['group'] != last:
            lines.append('[%s]' % i['group'])
            last = i['group']
        fl = (' (' + ' '.join(i['flags']) + ')') if i['flags'] else ''
        lines.append('  %s - %s%s' % (i['name'], i['description'] or '(no doc line)', fl))
    if len(lines) > MAX_LINES:
        extra = len(lines) - (MAX_LINES - 1)
        lines = lines[:MAX_LINES - 1] + ['... +%d more, narrow with keywords' % extra]
    return '\n'.join(lines)


# ------------------------------------------------------------------------------------------------ size  aidd:FR-042

def _targets_of(path):
    """[(task_id, [files])] from the Target file column of a tasks.md."""
    out = []
    for ln in _read(path).splitlines():
        cells = [c.strip() for c in ln.strip().strip('|').split('|')]
        if len(cells) < 3 or not re.match(r'^T-\d+', cells[0]):
            continue
        cell = re.sub(r'\(same owner as [^)]*\)', '', cells[2])
        files = []
        for part in cell.split(' + '):
            p = part.strip().strip('`').strip()
            if not p or p.startswith('specs/') or ' ' in p or ('/' not in p and '.' not in p):
                continue
            files.append(p.replace('\\', '/'))
        out.append((cells[0], files))
    return out


def _manifest_changed(root, spec):
    """(changed files, affected count, why-not) from graph_snapshot.changed(); (None, None, reason) without baseline."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import graph_snapshot
        r = graph_snapshot.changed(root, spec, 'code')
        if r.get('rc') == 2:
            return None, None, 'no baseline: activate the spec or take a manifest'
        ch = list(r.get('added', [])) + list(r.get('modified', [])) + list(r.get('removed', []))
        return ch, len(r.get('affected', [])), ''
    except Exception:
        return None, None, 'graph_snapshot unavailable'


def classify(root, spec, files):
    root = os.path.abspath(root)
    cross, changed, affected, why = [], None, None, 'no --spec'
    if spec:
        targets = sorted({f for _, fs in _targets_of(os.path.join(root, 'specs', spec, 'tasks.md')) for f in fs})
        other = set()
        sd = os.path.join(root, 'specs')
        try:
            for d in sorted(os.listdir(sd)):
                if d != spec:
                    other.update(f for _, fs in _targets_of(os.path.join(sd, d, 'tasks.md')) for f in fs)
        except Exception:
            pass
        cross = [f for f in targets if f in other]
        changed, affected, why = _manifest_changed(root, spec)
    else:
        targets = sorted({f.replace('\\', '/') for f in files})
    sens = sorted({name for f in targets for name, fn in SENSITIVE if fn(f)})
    if cross:
        sens.append('cross-spec')
    n = len(targets)
    cls = 'L' if (sens or n > 8) else 'M' if n >= 3 else 'S' if n == 2 else 'XS'
    return {'class': cls, 'target_files': n, 'sensitive': sens,
            'changed_since_open': None if changed is None else len(changed), 'affected': affected,
            'spec': spec or '', 'inputs_note': why, 'parameters': list(PARAMS[cls]), 'not_created': EXCLUDES[cls]}


def size_report(res, as_json):
    cls = res['class']
    line = 'Analysis parameters: size=%s; %s' % (cls, '; '.join(res['parameters']))
    if as_json:
        d = dict(res)
        d['analysis_parameters'] = line
        return json.dumps(d, indent=1, sort_keys=True)
    na = lambda v: 'n/a' if v is None else v
    out = ['size: %s' % cls,
           'inputs: target files=%d; changed since open=%s; affected=%s; sensitive areas=%s' % (
               res['target_files'], na(res['changed_since_open']), na(res['affected']),
               ', '.join(res['sensitive']) or 'none') + (' (n/a: %s)' % res['inputs_note'] if res.get('inputs_note') else ''),
           'ANALYSIS PARAMETERS']
    out += ['  ' + p for p in res['parameters']]
    out += [line, 'not created for this size: %s' % res['not_created'], 'RESULT: ok - 1 items - evidence -']
    return '\n'.join(out)


def main(argv=None):
    try:
        args = list(sys.argv[1:] if argv is None else argv)
        if '-h' in args or '--help' in args:
            print(__doc__)
            return 0
        mode = 'tools'
        if args and args[0] == 'size':
            mode, args = 'size', args[1:]
        root, as_json, spec, files, rest, in_files, i = '.', False, '', [], [], False, 0
        while i < len(args):
            a = args[i]
            if a == '--json':
                as_json, in_files = True, False
            elif a in ('--root', '--spec') and i + 1 < len(args):
                if a == '--root':
                    root = args[i + 1]
                else:
                    spec = args[i + 1]
                i, in_files = i + 1, False
            elif a == '--files':
                in_files = True
            elif in_files and not a.startswith('--'):
                files.append(a)
            else:
                rest.append(a)
                in_files = False
            i += 1
        root = os.path.abspath(root)
        if mode == 'size':
            if not spec and not files:
                print('size needs --spec <id> or --files <f...>')
                print('RESULT: ok - 1 items - evidence -')
            else:
                print(size_report(classify(root, spec, files), as_json))
        else:
            print(catalog(root, rest, as_json))
    except Exception as ex:  # never raise
        print('aidd tools: %s' % ex)
    return 0


if __name__ == '__main__':
    sys.exit(main())
