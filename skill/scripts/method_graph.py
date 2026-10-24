#!/usr/bin/env python3
"""aidd method graph — the built-in `method` graph: the AIDD methodology itself (stdlib only, no LLM).

Spec 004 amendment 2026-10-24 (aidd:FR-016, aidd:T-13).

Parses skill/SKILL.md, skill/AIDD.md, commands/*.md and skill/templates/*:
  nodes   RULE (rows `| **Rn** ...` of the Hard rules table), STEP (`### Step N` headings), CMD
          (commands/aidd-*.md), TEMPLATE (files under skill/templates), SCRIPT (skill/scripts/<x>.py named in
          the docs), plus FUNC stubs for the functions that enforce a rule.
  edges   uses (STEP -> SCRIPT/TEMPLATE), invokes (CMD -> SCRIPT), cites (STEP -> RULE, the step text names it),
          enforced_by (RULE -> FUNC, `via: mention`: the FUNC docstring/comment carries the token `Rn` or
          `aidd:Rn`, read from the code graph; a mention is a label, not proof).
A RULE with no enforcing FUNC and no `<!-- aidd:self-checked Rn -->` note in the methodology text is
`unlinked: true`. Rules the code mentions but the table lacks (e.g. R8) are reported absent in `warnings`.
The code graph comes from `.aidd/graphs/code.json` when not passed; without it all rules stay unlinked.

Usage:
    python method_graph.py [--root DIR] [--out FILE] [--quiet]
Prints `method graph: R rules (U unlinked), S steps, C commands, T templates, X scripts, warnings W`.
Exit 0 on success (even with warnings), 1 when the graph cannot be written, 2 on usage error.
"""
import argparse
import glob as _glob
import json
import os
import re
import sys
import time
from pathlib import Path

GRAPH_REL = ".aidd/graphs/method.json"  # aidd:FR-016
SCHEMA_VERSION = 1
SOURCES = ("skill/SKILL.md", "skill/AIDD.md", "commands/*.md", "skill/templates/*")
CODE_GRAPH_REL = ".aidd/graphs/code.json"
SELF_CHECKED_RE = re.compile(r'<!--\s*aidd:self-checked\s+(R\d+)\s*-->')
RULE_ROW_RE = re.compile(r'^\| \*\*(R\d+)\*\*\s*(.*?)\s*\|')
STEP_RE = re.compile(r'^### Step (-?\d+(?:\.\d+)?)\s*(?:[—–-]+\s*)?(.*?)\s*$')
HEADING_RE = re.compile(r'^#{1,3} ')
SCRIPT_RE = re.compile(r'(?<![\w.-])([A-Za-z_][\w]*)\.py\b')
RULE_TOKEN_RE = re.compile(r'(?<![\w-])(R\d{1,3})\b')
SCRIPTS_REL = "skill/scripts"
TEMPLATES_REL = "skill/templates"


def _node(nid, typ, label, rel, line):
    return {'id': nid, 'type': typ, 'label': label, 'source_file': rel,
            'source_location': '%s:%d' % (rel, line)}


def _edge(s, t, rel, **kw):
    e = {'source': s, 'target': t, 'relation': rel}
    e.update(kw)
    return e


def _read(path, warnings, rel):
    try:
        return Path(path).read_text(encoding='utf-8', errors='replace')
    except (OSError, ValueError) as ex:
        warnings.append('cannot read %s: %s' % (rel, ex))
        return ''


def parse_rules(text):  # aidd:FR-016
    """Rows `| **Rn** title | ...` -> [(id, title, line)] (1-based line). Never raises."""
    out = []
    try:
        for i, ln in enumerate((text or '').splitlines(), 1):
            m = RULE_ROW_RE.match(ln)
            if m:
                out.append((m.group(1), m.group(2).strip(), i))
    except Exception:
        pass
    return out


def parse_steps(text):  # aidd:FR-016
    """Headings `### Step N — title` -> [(id, title, line)]; id is `-2`, `1.5`, `7`. Never raises."""
    out = []
    try:
        for i, ln in enumerate((text or '').splitlines(), 1):
            m = STEP_RE.match(ln)
            if m:
                out.append((m.group(1), m.group(2).strip(), i))
    except Exception:
        pass
    return out


def _sections(text, steps):
    """step id -> text of its section (heading to the next `#`..`###` heading)."""
    lines = (text or '').splitlines()
    res = {}
    for sid, _t, ln in steps:
        j = ln
        while j < len(lines) and not HEADING_RE.match(lines[j]):
            j += 1
        res[sid] = '\n'.join(lines[ln - 1:j])
    return res


def _list_sources(root):
    root = Path(root)
    found = []
    for pat in SOURCES:
        for p in sorted(_glob.glob(str(root / pat))):
            if os.path.isfile(p):
                found.append(Path(p).relative_to(root).as_posix())
    return sorted(set(found))


def _load_code_graph(root, warnings):
    p = Path(root) / CODE_GRAPH_REL
    if not p.is_file():
        warnings.append('code graph absent (%s): enforcers not linked, all rules unlinked' % CODE_GRAPH_REL)
        return None
    try:
        g = json.loads(p.read_text(encoding='utf-8'))
        if isinstance(g, dict):
            return g
    except (OSError, ValueError) as ex:
        warnings.append('code graph unreadable (%s): %s' % (CODE_GRAPH_REL, ex))
        return None
    warnings.append('code graph malformed (%s)' % CODE_GRAPH_REL)
    return None


def link_enforcers(graph, code_graph):  # aidd:FR-016
    """RULE -> FUNC `enforced_by` edges (`via: mention`) from the FUNC `rule_ids` of the code graph; adds a
    FUNC stub node per linked function; sets `unlinked` on every RULE with no enforcer and no self-check note
    (`graph['_selfchecked']`, set by build). Idempotent."""
    graph['edges'] = [e for e in graph.get('edges', []) if e.get('relation') != 'enforced_by']
    graph['nodes'] = [n for n in graph.get('nodes', []) if n.get('type') != 'FUNC']
    rules = {n['id']: n for n in graph['nodes'] if n.get('type') == 'RULE'}
    selfchecked = set(graph.get('_selfchecked') or ())
    linked = set()
    funcs = {}
    for f in (code_graph or {}).get('nodes', []):
        if f.get('type') != 'FUNC':
            continue
        for rid in f.get('rule_ids') or ():
            if rid in rules:
                graph['edges'].append(_edge(rid, f['id'], 'enforced_by', via='mention'))
                linked.add(rid)
                funcs[f['id']] = f
    for fid, f in funcs.items():
        graph['nodes'].append({'id': fid, 'type': 'FUNC', 'label': f.get('label', fid),
                               'source_file': f.get('source_file', ''),
                               'source_location': f.get('source_location', '')})
    for rid, n in rules.items():
        if rid in linked or rid in selfchecked:
            n.pop('unlinked', None)
        else:
            n['unlinked'] = True
    graph['nodes'].sort(key=lambda n: n['id'])
    graph['edges'].sort(key=lambda e: (e['source'], e['target'], e['relation']))
    return graph


def build(root, code_graph=None):  # aidd:FR-016
    """Build the method graph of `root`. Never raises on unreadable documents (they become warnings)."""
    root = Path(root)
    warnings = []
    texts = {rel: _read(root / rel, warnings, rel) for rel in _list_sources(root)}
    for need in ('skill/SKILL.md', 'skill/AIDD.md'):
        if need not in texts:
            warnings.append('missing methodology document %s' % need)
    nodes, edges = {}, []

    skill = texts.get('skill/SKILL.md', '')
    for rid, title, ln in parse_rules(skill):
        nodes[rid] = _node(rid, 'RULE', '%s %s' % (rid, title), 'skill/SKILL.md', ln)

    scripts_dir = root / SCRIPTS_REL
    existing = {p.name for p in scripts_dir.glob('*.py')} if scripts_dir.is_dir() else set()

    def mentioned_scripts(text):
        return sorted({m + '.py' for m in SCRIPT_RE.findall(text or '') if m + '.py' in existing})

    def ensure_script(name):
        sid = '%s/%s' % (SCRIPTS_REL, name)
        if sid not in nodes:
            nodes[sid] = _node(sid, 'SCRIPT', name, sid, 1)
        return sid

    # templates
    tpl_root = root / TEMPLATES_REL
    templates = {}  # id -> match regex
    if tpl_root.is_dir():
        for p in sorted(tpl_root.rglob('*')):
            if p.is_file():
                rel = p.relative_to(root).as_posix()
                sub = p.relative_to(tpl_root).as_posix()
                key = sub if '/' in sub else p.name
                templates[rel] = re.compile(r'(?<![\w.-])' + re.escape(key) + r'(?![\w])')
                nodes[rel] = _node(rel, 'TEMPLATE', sub, rel, 1)

    # steps (SKILL.md and AIDD.md)
    for doc in ('skill/SKILL.md', 'skill/AIDD.md'):
        text = texts.get(doc, '')
        steps = parse_steps(text)
        secs = _sections(text, steps)
        for sid, title, ln in steps:
            nid = 'STEP:%s' % sid
            if nid in nodes:
                continue
            nodes[nid] = _node(nid, 'STEP', 'Step %s %s' % (sid, title), doc, ln)
            sec = secs.get(sid, '')
            for name in mentioned_scripts(sec):
                edges.append(_edge(nid, ensure_script(name), 'uses'))
            for tid, rx in templates.items():
                if rx.search(sec):
                    edges.append(_edge(nid, tid, 'uses'))
            for rid in sorted(set(RULE_TOKEN_RE.findall(sec))):
                if rid in nodes and nodes[rid]['type'] == 'RULE':
                    edges.append(_edge(nid, rid, 'cites'))

    # commands
    for rel, text in sorted(texts.items()):
        if rel.startswith('commands/aidd-') and rel.endswith('.md'):
            nodes[rel] = _node(rel, 'CMD', Path(rel).stem, rel, 1)
            for name in mentioned_scripts(text):
                edges.append(_edge(rel, ensure_script(name), 'invokes'))

    # scripts mentioned anywhere in the docs
    for text in texts.values():
        for name in mentioned_scripts(text):
            ensure_script(name)

    selfchecked = set()
    for text in texts.values():
        selfchecked.update(SELF_CHECKED_RE.findall(text))

    if code_graph is None:
        code_graph = _load_code_graph(root, warnings)
    for f in (code_graph or {}).get('nodes', []):
        if f.get('type') == 'FUNC':
            for rid in f.get('rule_ids') or ():
                if rid not in nodes:
                    warnings.append('%s mentioned in code (%s) but absent from the Hard rules table'
                                    % (rid, f.get('id')))
    warnings = sorted(set(warnings))

    graph = {'schema': SCHEMA_VERSION, 'nodes': list(nodes.values()), 'edges': edges,
             'warnings': warnings, '_selfchecked': sorted(selfchecked)}
    link_enforcers(graph, code_graph)
    graph.pop('_selfchecked', None)
    uniq = {(e['source'], e['target'], e['relation']): e for e in graph['edges']}
    graph['edges'] = [uniq[k] for k in sorted(uniq)]
    return graph


def _write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name('%s.tmp.%d' % (path.name, os.getpid()))
    try:
        tmp.write_text(text, encoding='utf-8')
        os.replace(str(tmp), str(path))
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def main(argv=None):
    ap = argparse.ArgumentParser(description='Build the AIDD methodology graph (%s).' % GRAPH_REL)
    ap.add_argument('--root', default='.', help='project root (default: cwd)')
    ap.add_argument('--out', default=None, help='output file (default: <root>/%s)' % GRAPH_REL)
    ap.add_argument('--quiet', action='store_true', help='no summary line')
    try:
        a = ap.parse_args(argv)
    except SystemExit as ex:
        return 0 if ex.code in (0, None) else 2
    root = Path(a.root).resolve()
    graph = dict(build(root))
    out = Path(a.out) if a.out else root / GRAPH_REL
    graph['generated'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    try:
        _write_atomic(out, json.dumps(graph, sort_keys=True, indent=1, ensure_ascii=True) + '\n')
    except OSError as ex:
        print('method graph: cannot write %s: %s' % (out, ex), file=sys.stderr)
        return 1
    if not a.quiet:
        cnt = {}
        for n in graph['nodes']:
            cnt[n['type']] = cnt.get(n['type'], 0) + 1
        unl = sum(1 for n in graph['nodes'] if n.get('unlinked'))
        print('method graph: %d rules (%d unlinked), %d steps, %d commands, %d templates, %d scripts, '
              'warnings %d' % (cnt.get('RULE', 0), unl, cnt.get('STEP', 0), cnt.get('CMD', 0),
                               cnt.get('TEMPLATE', 0), cnt.get('SCRIPT', 0), len(graph['warnings'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
