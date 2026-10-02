#!/usr/bin/env python3
"""
AIDD Flowmap — from a requirement's `visual-flow.toon` to something the user can
SEE, walk through and correct: an actors x processes swimlane flow, generated
pseudocode, and an actor/process matrix, in one standalone interactive HTML
file (inline SVG, dark/light, no network, no dependencies).

Why it exists: explaining a planned flow in prose is where analysis breaks
down. Flowmap makes the plan visible and clickable before any code exists.

Source format: AIDD-TOON (`.flow.toon`) — the same compact tabular TOON dialect
find_spec.py uses for specs/index.toon, extended for flows. Not JSON, not
Mermaid. The agent writes the TOON; the layout, routing and pseudocode are
derived deterministically, so the agent never hand-places coordinates.

Inspired by the "typed source -> validator -> deterministic renderer ->
standalone HTML" approach of tt-a1i/archify (MIT). This is an independent
Python implementation with its own format, layout and output — no archify
code, schema or template is reused.

Stdlib only.

Usage:
    python flowmap.py <visual-flow.flow.toon>                  # -> .html next to it
    python flowmap.py <file> -o out.html [--open]
    python flowmap.py <file> --check [--spec-dir specs/019-x]  # validate only, exit 1 on errors
    python flowmap.py <file> --pseudo                          # print pseudocode (markdown)
    python flowmap.py <file> --mermaid                         # print Mermaid (markdown-embed fallback)

AIDD-TOON flow file (several flows separated by a line `---`; `#` = comment):

    flow: US-001
    title: Waiter opens a table
    status: draft                      # draft | explicit
    actors[3]{id,label,kind}:          # swimlane rows; kind: human|system|data|external
      waiter,Waiter,human
      pos,POS app,system
      db,SQL Server,data
    processes[2]{id,label}:            # phases (column bands)
      P1,Choose table
      P2,Take order
    steps[5]{id,actor,process,type,code,label,detail}:
      s1,waiter,P1,start,,Enters waiter profile,
      s2,pos,P1,screen,SCREEN-01,Table map,Shows free/occupied tables
      s3,pos,P1,decision,CTL-004,Open table?,Checks open ticket via API-012
      s4,pos,P1,error,,Blocked,Table already has an open ticket
      s5,pos,P2,screen,SCREEN-08,Order ticket,
    links[4]{from,to,label,role}:      # role: main|branch|error|return (optional)
      s1,s2,,main
      s2,s3,,main
      s3,s4,occupied,error
      s3,s5,free,main

step types: start end screen control decision system api error note
"""
import argparse
import csv
import html
import io
import json
import re
import sys
import webbrowser
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

NODE_TYPES = ('start', 'end', 'screen', 'control', 'decision', 'system', 'api', 'error', 'note')
EDGE_ROLES = ('main', 'branch', 'error', 'return')
ACTOR_KINDS = ('human', 'system', 'data', 'external')
CODE_RE = re.compile(r'\b(SCREEN-\d+(?:-F\d+)?|CTL-\d+|COMP-\d+|API-\d+)\b', re.IGNORECASE)
CODE_PREFIX = {
    'screen': ('SCREEN-',), 'control': ('CTL-', 'COMP-'),
    'decision': ('CTL-', 'SCREEN-', 'API-'), 'api': ('API-',),
}
CODE_REQUIRED = ('screen', 'control')
TABLE_RE = re.compile(r'^(\w+)\[(\d+)\]\{([^}]*)\}:\s*$')
SCALAR_RE = re.compile(r'^(\w+):\s*(.*)$')
TABLE_FIELDS = {
    'actors': ('id', 'label', 'kind'),
    'processes': ('id', 'label'),
    'steps': ('id', 'actor', 'process', 'type', 'code', 'label', 'detail'),
    'links': ('from', 'to', 'label', 'role'),
}

# ------------------------------------------------------------ AIDD-TOON parse


def parse_toon(text):
    """Return (flows, errors). Each flow is a normalized dict (see normalize)."""
    flows, errors = [], []
    blocks, cur = [], []
    for raw in text.splitlines():
        if raw.strip() == '---':
            blocks.append(cur)
            cur = []
        else:
            cur.append(raw)
    blocks.append(cur)
    for bi, lines in enumerate(blocks):
        if not any(l.strip() and not l.strip().startswith('#') for l in lines):
            continue
        flow, errs = _parse_block(lines, bi + 1)
        errors += errs
        if flow:
            flows.append(flow)
    return flows, errors


def _parse_block(lines, bi):
    scalars, tables, errs = {}, {}, []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        i += 1
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        m = TABLE_RE.match(s)
        if m:
            name, count, fields = m.group(1), int(m.group(2)), tuple(f.strip() for f in m.group(3).split(','))
            if name not in TABLE_FIELDS:
                errs.append(f'block {bi}: unknown table {name!r}')
            elif fields != TABLE_FIELDS[name]:
                errs.append(f'block {bi}: table {name} header must be {{{",".join(TABLE_FIELDS[name])}}}')
            rows = []
            while i < len(lines) and len(rows) < count:
                if lines[i].strip() and not lines[i][0].isspace():
                    break  # next top-level key: the table has fewer rows than declared
                r = lines[i].strip()
                i += 1
                if not r or r.startswith('#'):
                    continue
                row = next(csv.reader([r]))
                if len(row) != len(fields):
                    errs.append(f'block {bi}: {name} row {len(rows) + 1} has {len(row)} fields, expected {len(fields)}: {r}')
                    row = (row + [''] * len(fields))[:len(fields)]
                rows.append(dict(zip(fields, (c.strip() for c in row))))
            if len(rows) != count:
                errs.append(f'block {bi}: table {name}[{count}] declares {count} rows but {len(rows)} found')
            tables[name] = rows
            continue
        m = SCALAR_RE.match(s)
        if m:
            scalars[m.group(1)] = re.sub(r'\s+#.*$', '', m.group(2)).strip()
        else:
            errs.append(f'block {bi}: cannot parse line: {s}')
    if errs and not scalars and not tables:
        return None, errs
    flow = {
        'id': scalars.get('flow', ''), 'title': scalars.get('title', ''),
        'status': scalars.get('status', 'draft'),
        'actors': tables.get('actors', []), 'processes': tables.get('processes', []),
        'nodes': tables.get('steps', []), 'edges': tables.get('links', []),
    }
    for e in flow['edges']:
        e['role'] = e.get('role') or ''
    return flow, errs


# ---------------------------------------------------------------- validation


def validate(flows, parse_errors=()):
    errors, warnings = list(parse_errors), []
    if not flows:
        errors.append('no flows found (need `flow: US-nnn` blocks, one per use case)')
        return errors, warnings
    seen = set()
    for f in flows:
        tag = f'flow[{f["id"] or "?"}]'
        if not re.fullmatch(r'US-\d+', f['id']):
            errors.append(f'{tag}: `flow:` must look like US-001')
        if f['id'] in seen:
            errors.append(f'{tag}: duplicate flow id')
        seen.add(f['id'])
        if not f['title']:
            errors.append(f'{tag}: `title:` is required')
        if f['status'] not in ('draft', 'explicit'):
            errors.append(f"{tag}: status must be 'draft' or 'explicit'")
        _validate_flow(f, tag, errors, warnings)
    return errors, warnings


def _validate_flow(f, tag, errors, warnings):
    actors = {a['id']: a for a in f['actors']}
    procs = {p['id'] for p in f['processes']}
    if not actors:
        errors.append(f'{tag}: at least one actor is required')
    if len(actors) != len(f['actors']):
        errors.append(f'{tag}: duplicate actor ids')
    for a in f['actors']:
        if a.get('kind') not in ACTOR_KINDS:
            errors.append(f"{tag}: actor {a['id']} kind must be one of {ACTOR_KINDS}")
    if len(procs) != len(f['processes']):
        errors.append(f'{tag}: duplicate process ids')
    ids = {}
    for n in f['nodes']:
        nid, t = n['id'], n['type']
        if not nid or nid in ids:
            errors.append(f'{tag}: missing or duplicate step id {nid!r}')
            continue
        ids[nid] = n
        if t not in NODE_TYPES:
            errors.append(f'{tag}/{nid}: type {t!r} not in {NODE_TYPES}')
        if n['actor'] not in actors:
            errors.append(f"{tag}/{nid}: actor {n['actor']!r} is not declared in actors")
        if n['process'] and n['process'] not in procs:
            errors.append(f"{tag}/{nid}: process {n['process']!r} is not declared in processes")
        if not n['label']:
            errors.append(f'{tag}/{nid}: label is required')
        code = n['code']
        pref = CODE_PREFIX.get(t)
        if code:
            if not CODE_RE.fullmatch(code):
                errors.append(f'{tag}/{nid}: code {code!r} is not SCREEN-XX/CTL-nnn/COMP-nnn/API-nnn')
            elif pref and not code.upper().startswith(pref):
                errors.append(f'{tag}/{nid}: a {t} step cannot cite {code} (expected {" or ".join(pref)})')
        elif t in CODE_REQUIRED:
            errors.append(f'{tag}/{nid}: a {t} step must cite its code — never a redescription')
        elif t == 'decision':
            warnings.append(f'{tag}/{nid}: decision cites no CTL/SCREEN/API code')
    outs, ins = {}, {}
    for e in f['edges']:
        a, b = e['from'], e['to']
        if a not in ids or b not in ids:
            errors.append(f'{tag}: link {a!r} -> {b!r} references an unknown step')
            continue
        if a == b:
            errors.append(f'{tag}: self-link on {a}')
        if e['role'] and e['role'] not in EDGE_ROLES:
            errors.append(f'{tag}: link {a}->{b} role must be one of {EDGE_ROLES}')
        outs.setdefault(a, []).append(e)
        ins.setdefault(b, []).append(e)
    starts = [i for i, n in ids.items() if n['type'] == 'start']
    if not starts:
        errors.append(f"{tag}: no 'start' step")
    if not any(n['type'] in ('end', 'error') for n in ids.values()):
        errors.append(f"{tag}: no 'end' or 'error' step — every flow must terminate")
    for i, n in ids.items():
        t = n['type']
        o = outs.get(i, [])
        if t not in ('end', 'error', 'note') and not o:
            errors.append(f'{tag}/{i}: dead end — no outgoing link')
        if t == 'decision':
            if len(o) < 2:
                errors.append(f'{tag}/{i}: decision needs >= 2 branches (has {len(o)})')
            for e in o:
                if not e['label']:
                    errors.append(f"{tag}/{i}: decision branch to {e['to']} has no condition label")
        if t not in ('start', 'note') and not ins.get(i):
            errors.append(f'{tag}/{i}: orphan — no incoming link')
    seen, stack = set(), list(starts)
    while stack:
        c = stack.pop()
        if c not in seen:
            seen.add(c)
            stack.extend(e['to'] for e in outs.get(c, []) if e['to'] in ids)
    for i, n in ids.items():
        if i not in seen and n['type'] != 'note':
            errors.append(f'{tag}/{i}: unreachable from the start step')
    used = {n['actor'] for n in ids.values()}
    for a in actors:
        if a not in used:
            warnings.append(f'{tag}: actor {a} has no steps')


def cross_check_codes(flows, spec_dir):
    known = set()
    for name in ('mockup-audit.md', 'contracts.md', 'plan.md', 'design-system/components-index.md'):
        p = Path(spec_dir) / name
        if p.exists():
            known |= {c.upper() for c in CODE_RE.findall(p.read_text(encoding='utf-8'))}
    if not known:
        return []
    return [f"{f['id']}/{n['id']}: code {n['code'].upper()} is not defined in the spec's mockup-audit/contracts/plan"
            for f in flows for n in f['nodes'] if n['code'] and n['code'].upper() not in known]


# -------------------------------------------------------------- graph helpers


def analyze(f):
    """Back-edge detection, topological ranks and ordered adjacency."""
    ids = [n['id'] for n in f['nodes']]
    adj = {i: [] for i in ids}
    for e in f['edges']:
        adj[e['from']].append(e)
    starts = [n['id'] for n in f['nodes'] if n['type'] == 'start'] or ids[:1]
    state, back = {}, set()

    def dfs(u):
        state[u] = 1
        for e in adj[u]:
            v = e['to']
            if state.get(v) == 1:
                back.add((u, v))
            elif v not in state:
                dfs(v)
        state[u] = 2
    sys.setrecursionlimit(10000)
    for s in starts:
        if s not in state:
            dfs(s)
    for i in ids:
        if i not in state:
            dfs(i)
    fwd = [e for e in f['edges'] if (e['from'], e['to']) not in back]
    rank = {i: 0 for i in ids}
    for _ in range(len(ids) + 2):
        changed = False
        for e in fwd:
            if rank[e['to']] < rank[e['from']] + 1:
                rank[e['to']] = rank[e['from']] + 1
                changed = True
        cells = {}
        for n in f['nodes']:
            k = (n['actor'], rank[n['id']])
            if k in cells:
                rank[n['id']] += 1
                changed = True
            cells[k] = n['id']
        if not changed:
            break
    return adj, back, rank


# ---------------------------------------------------------------- pseudocode


def pseudocode(f):
    """Deterministic structured pseudocode derived from the flow graph.
    Returns a list of (indent, node_id | None, text)."""
    nodes = {n['id']: n for n in f['nodes']}
    actors = {a['id']: a['label'] for a in f['actors']}
    adj, back, _ = analyze(f)
    out, emitted = [], set()

    def line(ind, nid, text):
        out.append((ind, nid, text))

    def step_text(n):
        code = f" [{n['code']}]" if n['code'] else ''
        who = actors.get(n['actor'], n['actor'])
        verb = {'start': 'START', 'end': 'END', 'error': 'FAIL', 'screen': 'SHOW', 'control': 'ON',
                'system': 'EXEC', 'api': 'CALL', 'note': 'NOTE', 'decision': 'CHECK'}[n['type']]
        txt = f"{verb} {n['label']}{code}  — {who}"
        if n['detail']:
            txt += f"  // {n['detail']}"
        return txt

    def walk(nid, ind):
        while True:
            n = nodes[nid]
            if nid in emitted:
                line(ind, nid, f'GOTO {nid}')
                return
            emitted.add(nid)
            line(ind, nid, f'{nid}: {step_text(n)}')
            o = adj[nid]
            if not o:  # an `error` step that links onward (retry/return) keeps its branch
                return
            if n['type'] == 'decision' or len(o) > 1:
                head = 'IF' if n['type'] == 'decision' else 'PARALLEL'
                for k, e in enumerate(o):
                    cond = e['label'] or 'otherwise'
                    kw = head if k == 0 else ('ELSE IF' if n['type'] == 'decision' else 'AND')
                    if n['type'] == 'decision' and k == len(o) - 1 and k > 0:
                        kw, cond = 'ELSE', cond
                    line(ind + 1, None, f"{kw} {cond}:" if kw != 'ELSE' else f'ELSE ({cond}):')
                    walk(e['to'], ind + 2)
                return
            nid = o[0]['to']
            if o[0]['label']:
                line(ind, None, f"// via: {o[0]['label']}")

    starts = [n['id'] for n in f['nodes'] if n['type'] == 'start'] or [f['nodes'][0]['id']]
    for s in starts:
        walk(s, 0)
    for n in f['nodes']:  # notes / anything not reached
        if n['id'] not in emitted:
            line(0, n['id'], f'{n["id"]}: {step_text(n)}')
    return out


def pseudo_markdown(f):
    lines = [f"### {f['id']} — {f['title']}", '', '```text']
    lines += ['  ' * ind + text for ind, _, text in pseudocode(f)]
    lines.append('```')
    return '\n'.join(lines)


# -------------------------------------------------------------------- layout

COL_W, LANE_H, GUTTER, BAND_H, PAD_X = 196, 120, 130, 30, 18
NODE_W, NODE_H, DEC_W, DEC_H, PILL_W, PILL_H = 160, 66, 176, 92, 140, 44


def _size(t):
    return (DEC_W, DEC_H) if t == 'decision' else ((PILL_W, PILL_H) if t in ('start', 'end') else (NODE_W, NODE_H))


def layout(f, rank):
    lane = {a['id']: i for i, a in enumerate(f['actors'])}
    boxes = {}
    for n in f['nodes']:
        w, h = _size(n['type'])
        cx = GUTTER + rank[n['id']] * COL_W + COL_W / 2
        cy = BAND_H + 8 + lane[n['actor']] * LANE_H + LANE_H / 2
        boxes[n['id']] = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    ncols = max(rank.values()) + 1
    return boxes, GUTTER + ncols * COL_W + PAD_X, BAND_H + 8 + len(f['actors']) * LANE_H + 6


def _hit(p, q, box, m=4):
    x0, y0, x1, y1 = box[0] - m, box[1] - m, box[2] + m, box[3] + m
    sx0, sx1 = sorted((p[0], q[0]))
    sy0, sy1 = sorted((p[1], q[1]))
    return sx1 > x0 and sx0 < x1 and sy1 > y0 and sy0 < y1


def _tidy(pts):
    out = []
    for p in pts:
        if not out or p != out[-1]:
            out.append(p)
    i = 1
    while i < len(out) - 1:
        a, b, c = out[i - 1], out[i], out[i + 1]
        if a[0] == b[0] == c[0] or a[1] == b[1] == c[1]:
            del out[i]
        else:
            i += 1
    return out


def route(a, b, others):
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    acx, acy, bcx, bcy = (ax0 + ax1) / 2, (ay0 + ay1) / 2, (bx0 + bx1) / 2, (by0 + by1) / 2
    cands = []
    for xm in (ax1 + 14, bx0 - 14, (ax1 + bx0) / 2, ax0 - 14, bx1 + 14):
        s = (ax1, acy) if xm > acx else (ax0, acy)
        t = (bx0, bcy) if xm < bcx else (bx1, bcy)
        cands.append([s, (xm, s[1]), (xm, t[1]), t])
    if abs(acx - bcx) < 1:
        cands.append([(acx, ay1), (bcx, by0)] if acy < bcy else [(acx, ay0), (bcx, by1)])
    for ym in ((ay1 + by0) / 2 if acy < bcy else (by1 + ay0) / 2, max(ay1, by1) + 20, min(ay0, by0) - 20):
        s = (acx, ay1) if ym > acy else (acx, ay0)
        t = (bcx, by0) if ym < bcy else (bcx, by1)
        cands.append([s, (s[0], ym), (t[0], ym), t])
    best, bs = None, None
    for c in cands:
        pts = _tidy(c)
        if len(pts) < 2:
            continue
        hits = sum(1 for p, q in zip(pts, pts[1:]) for bx in others if _hit(p, q, bx))
        ln = sum(abs(p[0] - q[0]) + abs(p[1] - q[1]) for p, q in zip(pts, pts[1:]))
        sc = hits * 100000 + (len(pts) - 2) * 40 + ln
        if bs is None or sc < bs:
            best, bs = pts, sc
    return best


def _wrap(text, mx, lines_max):
    words, lines, cur = str(text).split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if len(t) <= mx or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > lines_max:
        lines = lines[:lines_max]
        lines[-1] = lines[-1][:mx - 1].rstrip() + '…'
    return lines


def esc(s):
    return html.escape(str(s), quote=True)


# ----------------------------------------------------------------------- SVG


def render_svg(f):
    adj, back, rank = analyze(f)
    boxes, width, height = layout(f, rank)
    fid = esc(f['id'])
    P = [f'<svg class="flow" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" '
         f'aria-label="{esc(f["id"] + " " + f["title"])}" xmlns="http://www.w3.org/2000/svg"><defs>']
    for r in EDGE_ROLES:
        P.append(f'<marker id="a-{r}-{fid}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                 f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="ar-{r}"/></marker>')
    P.append('</defs>')
    # process bands: x-range of each process's steps
    for pi, p in enumerate(f['processes']):
        xs = [boxes[n['id']] for n in f['nodes'] if n['process'] == p['id']]
        if not xs:
            continue
        x0, x1 = min(b[0] for b in xs) - 14, max(b[2] for b in xs) + 14
        P.append(f'<g class="band band-{pi % 5}" data-process="{esc(p["id"])}"><rect x="{x0:.1f}" y="2" width="{x1 - x0:.1f}" height="{BAND_H - 6}" rx="6"/>'
                 f'<text x="{x0 + 8:.1f}" y="{BAND_H / 2 + 1}" dominant-baseline="middle">{esc(p["id"])} · {esc(_wrap(p["label"], max(8, int((x1 - x0) / 6.4) - 6), 1)[0])}</text>'
                 f'<line x1="{x0:.1f}" x2="{x0:.1f}" y1="{BAND_H - 4}" y2="{height}" class="band-sep"/></g>')
    for i, a in enumerate(f['actors']):
        y = BAND_H + 8 + i * LANE_H
        lab = _wrap(a['label'], 15, 3)
        tsp = ''.join(f'<tspan x="12" dy="{(0 if k else -(len(lab) - 1) * 7)}">{esc(t)}</tspan>' if k == 0 else f'<tspan x="12" dy="14">{esc(t)}</tspan>'
                      for k, t in enumerate(lab))
        P.append(f'<g class="lane lane-{a["kind"]}" data-actor="{esc(a["id"])}"><rect x="0" y="{y}" width="{width}" height="{LANE_H}" class="lane-bg l{i % 2}"/>'
                 f'<rect x="0" y="{y}" width="5" height="{LANE_H}" class="lane-kind"/>'
                 f'<text x="12" y="{y + LANE_H / 2}" class="lane-label" dominant-baseline="middle">{tsp}</text>'
                 f'<text x="12" y="{y + LANE_H - 8}" class="lane-sub">{esc(a["kind"])}</text></g>')
    for e in f['edges']:
        a, b = e['from'], e['to']
        pts = route(boxes[a], boxes[b], [bx for k, bx in boxes.items() if k not in (a, b)])
        role = e['role'] or ('return' if (a, b) in back else 'main')
        d = 'M' + ' L'.join(f'{x:.1f},{y:.1f}' for x, y in pts)
        P.append(f'<g class="eg" data-from="{esc(a)}" data-to="{esc(b)}"><path d="{d}" class="edge e-{role}" fill="none" marker-end="url(#a-{role}-{fid})"/>')
        if e['label']:
            s = max(zip(pts, pts[1:]), key=lambda s: abs(s[0][0] - s[1][0]) + abs(s[0][1] - s[1][1]))
            mx, my = (s[0][0] + s[1][0]) / 2, (s[0][1] + s[1][1]) / 2
            lw = len(e['label']) * 6.1 + 10
            P.append(f'<rect x="{mx - lw / 2:.1f}" y="{my - 9:.1f}" width="{lw:.1f}" height="16" rx="4" class="elb-bg"/>'
                     f'<text x="{mx:.1f}" y="{my + 3:.1f}" text-anchor="middle" class="elb elb-{role}">{esc(e["label"])}</text>')
        P.append('</g>')
    for n in f['nodes']:
        x0, y0, x1, y1 = boxes[n['id']]
        w, h, cx, cy, t = x1 - x0, y1 - y0, (x0 + x1) / 2, (y0 + y1) / 2, n['type']
        P.append(f'<g class="node n-{t}" tabindex="0" data-id="{esc(n["id"])}" data-actor="{esc(n["actor"])}" data-process="{esc(n["process"])}">')
        if t == 'decision':
            P.append(f'<polygon points="{cx},{y0} {x1},{cy} {cx},{y1} {x0},{cy}" class="shape"/>')
            if n['code']:
                P.append(f'<text x="{cx}" y="{cy - 20}" text-anchor="middle" class="code">{esc(n["code"])}</text>')
            ls = _wrap(n['label'], 20, 2)
            for k, ln in enumerate(ls):
                P.append(f'<text x="{cx}" y="{cy + (4 if n["code"] else 0) - (len(ls) - 1) * 6 + k * 12 + 2}" text-anchor="middle" class="lbl sm">{esc(ln)}</text>')
        elif t in ('start', 'end'):
            P.append(f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" rx="{h / 2}" class="shape"/>')
            ls = _wrap(n['label'], 20, 2)
            for k, ln in enumerate(ls):
                P.append(f'<text x="{cx}" y="{cy - (len(ls) - 1) * 6 + k * 12 + 4}" text-anchor="middle" class="lbl">{esc(ln)}</text>')
        else:
            P.append(f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" rx="8" class="shape"/>')
            ty = y0 + 14
            if n['code']:
                P.append(f'<text x="{x0 + 10}" y="{ty}" class="code">{esc(n["code"])}</text>')
                ty += 14
            ls = _wrap(n['label'], 23, 2)
            for k, ln in enumerate(ls):
                P.append(f'<text x="{x0 + 10}" y="{ty + k * 13}" class="lbl">{esc(ln)}</text>')
            if n['detail'] and len(ls) + (1 if n['code'] else 0) <= 2:
                P.append(f'<text x="{x0 + 10}" y="{ty + len(ls) * 13 + 1}" class="sub">{esc(_wrap(n["detail"], 26, 1)[0])}</text>')
        P.append(f'<text x="{x1 - 5}" y="{y0 - 3 if t != "decision" else y0 + 10}" text-anchor="end" class="nid">{esc(n["id"])}</text></g>')
    P.append('</svg>')
    return ''.join(P)


# ---------------------------------------------------------------------- HTML

CSS = """
:root{--bg:#f3f1ec;--panel:#fffdf8;--ink:#1c2430;--muted:#667085;--line:#ddd7c9;--l0:#fffdf8;--l1:#f6f2e8;--acc:#0f766e;--err:#c2410c;--ret:#7c3aed;--br:#6b7280;--sel:#e11d74;
--screen:#e0f2fe;--screen-b:#0369a1;--control:#e7f6e9;--control-b:#15803d;--decision:#fff1c9;--decision-b:#b45309;--system:#efe7ff;--system-b:#6d28d9;--api:#d9f4f2;--api-b:#0f766e;--start:#1c2430;--startink:#fff;--end:#e4e0d4;--error:#ffe4d6;--error-b:#c2410c;--note:#fffdf8;
--b0:#0f766e;--b1:#b45309;--b2:#6d28d9;--b3:#0369a1;--b4:#be185d}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#10141b;--panel:#171d27;--ink:#e8ecf3;--muted:#98a2b3;--line:#2b3442;--l0:#141a23;--l1:#10151d;--acc:#2dd4bf;--err:#fb923c;--ret:#a78bfa;--br:#94a3b8;--sel:#f472b6;
--screen:#10283d;--screen-b:#38bdf8;--control:#12301a;--control-b:#4ade80;--decision:#3a2e0c;--decision-b:#fbbf24;--system:#241b44;--system-b:#a78bfa;--api:#0e3330;--api-b:#2dd4bf;--start:#e8ecf3;--startink:#10141b;--end:#252d3b;--error:#3c1c0e;--error-b:#fb923c;--note:#171d27;
--b0:#2dd4bf;--b1:#fbbf24;--b2:#a78bfa;--b3:#38bdf8;--b4:#f472b6}}
:root[data-theme=dark]{--bg:#10141b;--panel:#171d27;--ink:#e8ecf3;--muted:#98a2b3;--line:#2b3442;--l0:#141a23;--l1:#10151d;--acc:#2dd4bf;--err:#fb923c;--ret:#a78bfa;--br:#94a3b8;--sel:#f472b6;
--screen:#10283d;--screen-b:#38bdf8;--control:#12301a;--control-b:#4ade80;--decision:#3a2e0c;--decision-b:#fbbf24;--system:#241b44;--system-b:#a78bfa;--api:#0e3330;--api-b:#2dd4bf;--start:#e8ecf3;--startink:#10141b;--end:#252d3b;--error:#3c1c0e;--error-b:#fb923c;--note:#171d27;
--b0:#2dd4bf;--b1:#fbbf24;--b2:#a78bfa;--b3:#38bdf8;--b4:#f472b6}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;display:grid;grid-template-columns:250px 1fr;min-height:100vh}
aside{background:var(--panel);border-right:1px solid var(--line);padding:16px 14px;position:sticky;top:0;height:100vh;overflow:auto}
aside h1{font-size:15px;margin:0 0 2px}aside .sub{color:var(--muted);font-size:12px;margin-bottom:14px}
aside h3{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:16px 0 6px}
.flows a{display:block;padding:7px 9px;border-radius:7px;color:var(--ink);text-decoration:none;font-size:13px;border:1px solid transparent}.flows a b{color:var(--acc)}
.flows a.on{background:var(--l1);border-color:var(--line)}.chip{display:inline-flex;gap:5px;align-items:center;margin:2px 3px 2px 0;padding:2px 9px;border:1px solid var(--line);border-radius:999px;font-size:12px;cursor:pointer;background:var(--panel);color:var(--ink)}
.chip.off{opacity:.4;text-decoration:line-through}.chip i{width:8px;height:8px;border-radius:50%;display:inline-block}
input[type=search],button{background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:7px;padding:6px 9px;font:inherit}button{cursor:pointer}input[type=search]{width:100%}
main{padding:18px 22px;min-width:0}.top{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:flex-start}
h2{margin:0;font-size:19px}.badge{font-size:11px;padding:2px 9px;border-radius:999px;border:1px solid;margin-left:8px;vertical-align:middle}.badge.draft{color:var(--decision-b)}.badge.explicit{color:var(--control-b)}
.tabs{display:flex;gap:6px;margin:12px 0}.tabs button.on{background:var(--acc);color:#fff;border-color:var(--acc)}
.legend{display:flex;gap:12px;flex-wrap:wrap;color:var(--muted);font-size:12px;margin-bottom:8px}.legend i{display:inline-block;width:11px;height:11px;border-radius:3px;border:1.5px solid;vertical-align:-2px;margin-right:4px}
.split{display:grid;grid-template-columns:minmax(0,1fr) 400px;gap:14px;align-items:start}@media(max-width:1250px){.split{grid-template-columns:1fr}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}.card>h4{margin:0;padding:8px 12px;font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);border-bottom:1px solid var(--line)}
.scroll{overflow:auto;padding:6px;max-height:78vh}svg.flow{display:block;max-width:none}.scroll.fit svg.flow{width:100%;height:auto}
.card>h4{display:flex;justify-content:space-between;align-items:center}.card>h4 button{padding:1px 9px;font-size:11px}
.lane-bg{fill:var(--l0)}.lane-bg.l1{fill:var(--l1)}.lane-label{fill:var(--ink);font:600 11.5px system-ui,sans-serif}.lane-sub{fill:var(--muted);font:9.5px ui-monospace,Consolas,monospace;text-transform:uppercase}
.lane-kind{fill:var(--br)}.lane-human .lane-kind{fill:var(--b0)}.lane-system .lane-kind{fill:var(--b3)}.lane-data .lane-kind{fill:var(--b1)}.lane-external .lane-kind{fill:var(--b4)}
.band rect{fill:var(--b0);opacity:.16}.band text{font:600 11px system-ui,sans-serif;fill:var(--ink)}.band-sep{stroke:var(--line);stroke-dasharray:3 4}
.band-1 rect{fill:var(--b1)}.band-2 rect{fill:var(--b2)}.band-3 rect{fill:var(--b3)}.band-4 rect{fill:var(--b4)}
.edge{stroke-width:1.8;stroke-linejoin:round}.e-main{stroke:var(--acc);stroke-width:2.4}.e-branch{stroke:var(--br)}.e-error{stroke:var(--err);stroke-dasharray:6 4}.e-return{stroke:var(--ret);stroke-dasharray:2 4}
.ar-main{fill:var(--acc)}.ar-branch{fill:var(--br)}.ar-error{fill:var(--err)}.ar-return{fill:var(--ret)}.elb-bg{fill:var(--panel);opacity:.93}.elb{font:11px system-ui,sans-serif;fill:var(--ink)}.elb-error{fill:var(--err)}
.node{cursor:pointer;outline:none}.node .shape{stroke-width:1.6}
.n-screen .shape{fill:var(--screen);stroke:var(--screen-b)}.n-control .shape{fill:var(--control);stroke:var(--control-b)}.n-decision .shape{fill:var(--decision);stroke:var(--decision-b)}
.n-system .shape{fill:var(--system);stroke:var(--system-b)}.n-api .shape{fill:var(--api);stroke:var(--api-b)}.n-start .shape{fill:var(--start);stroke:var(--start)}.n-end .shape{fill:var(--end);stroke:var(--br)}
.n-error .shape{fill:var(--error);stroke:var(--error-b)}.n-note .shape{fill:var(--note);stroke:var(--br);stroke-dasharray:4 3}
.node .lbl{font:600 12px system-ui,sans-serif;fill:var(--ink)}.node .lbl.sm{font-size:11px}.n-start .lbl{fill:var(--startink)}
.node .code{font:600 10px ui-monospace,Consolas,monospace;fill:var(--muted)}.node .sub{font:10.5px system-ui,sans-serif;fill:var(--muted)}.node .nid{font:9px ui-monospace,Consolas,monospace;fill:var(--muted)}
.node:hover .shape,.node:focus .shape,.node.sel .shape{stroke:var(--sel);stroke-width:3.2}.node.vis .shape{stroke:var(--sel);stroke-width:1.6;stroke-dasharray:none;opacity:.85}
.dim{opacity:.16}.eg.hl .edge{stroke:var(--sel);stroke-width:3.2}
.pseudo{font:12.5px/1.65 ui-monospace,Consolas,monospace;padding:8px 0;max-height:78vh;overflow:auto}
.pl{display:block;padding:1px 12px;border-left:3px solid transparent;cursor:default;white-space:pre-wrap}.pl[data-id]{cursor:pointer}.pl[data-id]:hover{background:var(--l1)}.pl.sel{background:var(--l1);border-left-color:var(--sel)}
.pl .k{color:var(--acc);font-weight:700}.pl .c{color:var(--muted)}.pl .i{color:var(--system-b);font-weight:600}.pl.cm{color:var(--muted)}.pl.dim{opacity:.25}
table.m{border-collapse:collapse;width:100%;font-size:13px}table.m th,table.m td{border:1px solid var(--line);padding:8px 10px;vertical-align:top;text-align:left}table.m th{background:var(--l1);font-size:12px}
table.m td .chip{margin:2px 4px 2px 0;cursor:pointer}
#info{position:sticky;bottom:0;margin-top:14px;padding:10px 14px;background:var(--panel);border:1px solid var(--line);border-radius:10px;font-size:13px;color:var(--muted)}
#info b,#info code{color:var(--ink)}#info code{font-family:ui-monospace,Consolas,monospace;background:var(--l1);padding:1px 6px;border-radius:4px}#info .go{margin-left:6px;cursor:pointer;color:var(--acc);border:1px solid var(--line);padding:1px 8px;border-radius:999px;display:inline-block}
.trail{margin:8px 0 0;color:var(--muted);font-size:12px}.trail span{cursor:pointer;color:var(--acc)}
.hide{display:none}.kbd{font:11px ui-monospace,Consolas,monospace;border:1px solid var(--line);border-radius:4px;padding:0 5px;background:var(--l1)}
@media(max-width:900px){body{grid-template-columns:1fr}aside{position:static;height:auto}}
@media print{aside,.tabs,#info{display:none}body{display:block}.flowsec.hide{display:block}}
"""

JS = r"""
(function(){
var root=document.documentElement,$=function(s,c){return(c||document).querySelector(s)},$$=function(s,c){return Array.prototype.slice.call((c||document).querySelectorAll(s))};
var info=$('#info'),cur=null,hist=[],model=JSON.parse($('#model').textContent);
$('#theme').onclick=function(){var d=root.getAttribute('data-theme')==='dark'||(!root.getAttribute('data-theme')&&matchMedia('(prefers-color-scheme:dark)').matches);root.setAttribute('data-theme',d?'light':'dark')};
function sec(){return $('.flowsec:not(.hide)')}
function show(id,keep){$$('.flowsec').forEach(function(s){s.classList.toggle('hide',s.id!==id)});$$('.flows a').forEach(function(a){a.classList.toggle('on',a.dataset.f===id)});
 if(!keep){clearSel();hist=[];trail();info.textContent='Click a step (diagram, pseudocode or matrix), or press Enter on the diagram and use the arrow keys to walk the flow.'}
 location.hash=id;applyFilters()}
$$('.flows a').forEach(function(a){a.onclick=function(e){e.preventDefault();show(a.dataset.f)}});
function clearSel(){$$('.sel,.hl,.vis').forEach(function(e){e.classList.remove('sel','hl','vis')});$$('.dim').forEach(function(e){e.classList.remove('dim')});cur=null}
function stepOf(fid,id){var f=model[fid];return f&&f.steps[id]}
function select(id,push){var s=sec(),fid=s.id,st=stepOf(fid,id);if(!st)return;if(push&&cur&&cur!==id)hist.push(cur);
 clearSel();cur=id;$$('[data-id="'+id+'"]',s).forEach(function(e){e.classList.add('sel')});
 var linked={};linked[id]=1;$$('.eg',s).forEach(function(g){if(g.dataset.from===id||g.dataset.to===id){g.classList.add('hl');linked[g.dataset.from]=1;linked[g.dataset.to]=1}});
 $$('.node',s).forEach(function(n){if(!linked[n.dataset.id])n.classList.add('dim')});hist.forEach(function(h){$$('.node[data-id="'+h+'"]',s).forEach(function(n){n.classList.remove('dim');n.classList.add('vis')})});
 var sel=$('.pl.sel',s);if(sel&&sel.scrollIntoView)sel.scrollIntoView({block:'nearest'});var nd=$('.node.sel',s);if(nd&&nd.scrollIntoView)nd.scrollIntoView({block:'nearest',inline:'center'});
 var outs=f_out(fid,id);var h='<b>'+fid+' · '+id+'</b> '+(st.code?'<code>'+st.code+'</code> ':'')+esc(st.label)+' <span>('+st.type+' · '+esc(st.actor)+(st.process?' · '+st.process:'')+')</span>'+(st.detail?'<br>'+esc(st.detail):'')+'<br>Ref to cite when correcting: <code>'+fid+'/'+id+'</code>';
 if(outs.length){h+='<br>Next: '+outs.map(function(o,i){return '<span class="go" data-go="'+o.to+'">'+(i+1)+' → '+esc(o.label||o.to)+'</span>'}).join(' ')}
 info.innerHTML=h;$$('.go',info).forEach(function(g){g.onclick=function(e){e.stopPropagation();select(g.dataset.go,true)}});trail()}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function f_out(fid,id){return model[fid].edges.filter(function(e){return e.from===id})}
function trail(){var t=$('.trail',sec());if(!t)return;var p=hist.concat(cur?[cur]:[]);t.innerHTML=p.length?'Path: '+p.map(function(x){return '<span data-t="'+x+'">'+x+'</span>'}).join(' › ')+' &nbsp;<span data-t="__back">⟲ back</span>':'';
 $$('span[data-t]',t).forEach(function(s){s.onclick=function(){if(s.dataset.t==='__back'){back()}else{var i=hist.indexOf(s.dataset.t);if(i>=0)hist=hist.slice(0,i);select(s.dataset.t,false)}}})}
function back(){if(hist.length)select(hist.pop(),false)}
document.addEventListener('click',function(e){var t=e.target.closest('.node,.pl[data-id],.chip[data-id]');if(t&&t.dataset.id){select(t.dataset.id,true);e.stopPropagation()}});
document.addEventListener('keydown',function(e){if(e.target.tagName==='INPUT')return;var s=sec();
 if(e.key==='Enter'&&document.activeElement&&document.activeElement.dataset&&document.activeElement.dataset.id){select(document.activeElement.dataset.id,true);return}
 if(!cur)return;var outs=f_out(s.id,cur);
 if(e.key==='ArrowRight'&&outs[0]){e.preventDefault();select(outs[0].to,true)}
 else if(e.key==='ArrowLeft'||e.key==='Backspace'){e.preventDefault();back()}
 else if(/^[1-9]$/.test(e.key)&&outs[+e.key-1]){select(outs[+e.key-1].to,true)}
 else if(e.key==='Escape'){clearSel();hist=[];trail()}});
$$('.tabs button').forEach(function(b){b.onclick=function(){var s=sec();$$('.tabs button',s).forEach(function(x){x.classList.toggle('on',x===b)});$$('.pane',s).forEach(function(p){p.classList.toggle('hide',p.dataset.pane!==b.dataset.tab)})}});
$$('.fitbtn').forEach(function(b){b.onclick=function(){var s=b.closest('.card').querySelector('.scroll'),on=s.classList.toggle('fit');b.textContent=on?'100% size':'Fit width'}});
var off={actor:{},process:{}};
$$('.chip[data-filter]').forEach(function(c){c.onclick=function(){var k=c.dataset.filter,v=c.dataset.val;off[k][v]=!off[k][v];c.classList.toggle('off',!!off[k][v]);applyFilters()}});
function applyFilters(){var s=sec();if(!s)return;$$('.node',s).forEach(function(n){n.style.opacity=(off.actor[n.dataset.actor]||off.process[n.dataset.process])?'.12':''});
 $$('.pl[data-id]',s).forEach(function(p){var st=stepOf(s.id,p.dataset.id);p.style.opacity=(st&&(off.actor[st.actorId]||off.process[st.process]))?'.2':''})}
$('#q').oninput=function(){var q=this.value.toLowerCase(),s=sec();$$('.node',s).forEach(function(n){var st=stepOf(s.id,n.dataset.id),hay=(n.dataset.id+' '+st.code+' '+st.label+' '+st.detail+' '+st.actor).toLowerCase();n.style.opacity=(q&&hay.indexOf(q)<0)?'.12':''});
 $$('.pl[data-id]',s).forEach(function(p){var st=stepOf(s.id,p.dataset.id),hay=(p.dataset.id+' '+st.code+' '+st.label+' '+st.detail).toLowerCase();p.style.opacity=(q&&hay.indexOf(q)<0)?'.2':''})};
var start=(location.hash||'').slice(1);show(model[start]?start:Object.keys(model)[0],false);
})();
"""

LEGEND = (('screen', 'Screen'), ('control', 'Control'), ('decision', 'Decision'), ('system', 'System step'),
          ('api', 'API / SP'), ('error', 'Error / blocked'))


def _pseudo_html(f):
    rows = []
    for ind, nid, text in pseudocode(f):
        pad = '&nbsp;' * (ind * 3)
        m = re.match(r'^(s?\w+): (\w+) (.*)$', text) if nid else None
        if nid and text.startswith('GOTO'):
            body = f'<span class="k">GOTO</span> <span class="i">{esc(text[5:])}</span>'
        elif m:
            body = f'<span class="i">{esc(m.group(1))}</span> <span class="k">{esc(m.group(2))}</span> {esc(m.group(3)).replace("//", "<span class=c>//") + ("</span>" if "//" in m.group(3) else "")}'
        elif text.startswith('//'):
            body = esc(text)
        else:
            body = f'<span class="k">{esc(text)}</span>'
        cls = 'pl cm' if text.startswith('//') else 'pl'
        attr = f' data-id="{esc(nid)}"' if nid else ''
        rows.append(f'<span class="{cls}"{attr}>{pad}{body}</span>')
    return ''.join(rows)


def _matrix_html(f):
    head = ''.join(f'<th>{esc(a["label"])}<br><span class="kbd">{esc(a["kind"])}</span></th>' for a in f['actors'])
    body = []
    groups = [(p['id'], f'{p["id"]} · {p["label"]}') for p in f['processes']]
    if any(not n['process'] for n in f['nodes']):
        groups.append(('', '(no process)'))
    for pid, plabel in groups:
        cells = []
        for a in f['actors']:
            chips = ''.join(f'<span class="chip" data-id="{esc(n["id"])}">{esc(n["id"])} {esc((n["code"] + " ") if n["code"] else "")}{esc(n["label"])}</span>'
                            for n in f['nodes'] if n['process'] == pid and n['actor'] == a['id'])
            cells.append(f'<td>{chips}</td>')
        body.append(f'<tr><th>{esc(plabel)}</th>{"".join(cells)}</tr>')
    return f'<table class="m"><thead><tr><th>Process \\ Actor</th>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>'


def render_html(flows, title='Flowmap', spec=''):
    model = {}
    for f in flows:
        actor_label = {a['id']: a['label'] for a in f['actors']}
        model[f['id']] = {
            'steps': {n['id']: {'type': n['type'], 'code': n['code'], 'label': n['label'], 'detail': n['detail'],
                                 'actor': actor_label[n['actor']], 'actorId': n['actor'], 'process': n['process']} for n in f['nodes']},
            'edges': [{'from': e['from'], 'to': e['to'], 'label': e['label']} for e in f['edges']]}
    all_actors = {}
    all_procs = {}
    for f in flows:
        for a in f['actors']:
            all_actors.setdefault(a['id'], a['label'])
        for p in f['processes']:
            all_procs.setdefault(p['id'], p['label'])
    P = [f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
         f'<title>{esc(title)}</title><style>{CSS}</style></head><body>']
    P.append(f'<aside><h1>{esc(title)}</h1><div class="sub">{esc(spec)} · AIDD Flowmap</div><input type="search" id="q" placeholder="Search step, code, text…">'
             '<h3>Flows</h3><div class="flows">' + ''.join(
                 f'<a href="#{esc(f["id"])}" data-f="{esc(f["id"])}"><b>{esc(f["id"])}</b> {esc(f["title"])}</a>' for f in flows) + '</div>'
             '<h3>Actors (filter)</h3>' + ''.join(f'<span class="chip" data-filter="actor" data-val="{esc(k)}">{esc(v)}</span>' for k, v in all_actors.items()) +
             '<h3>Processes (filter)</h3>' + ''.join(f'<span class="chip" data-filter="process" data-val="{esc(k)}">{esc(k)} {esc(v)}</span>' for k, v in all_procs.items()) +
             '<h3>Navigate</h3><div class="sub">Click any step · <span class="kbd">→</span> next · <span class="kbd">1-9</span> pick a branch · <span class="kbd">←</span> back · <span class="kbd">Esc</span> clear</div>'
             '<button id="theme" type="button">Light / Dark</button></aside><main>')
    for f in flows:
        st = f['status']
        P.append(f'<div class="flowsec hide" id="{esc(f["id"])}"><div class="top"><h2>{esc(f["id"])} — {esc(f["title"])}'
                 f'<span class="badge {st}">{"explicit" if st == "explicit" else "draft — pending user confirmation"}</span></h2></div>'
                 '<div class="tabs"><button class="on" data-tab="flow" type="button">Flow + Pseudocode</button>'
                 '<button data-tab="matrix" type="button">Actors × Processes</button></div>'
                 '<div class="legend">' + ''.join(f'<span><i style="background:var(--{k});border-color:var(--{k}-b,var(--br))"></i>{v}</span>' for k, v in LEGEND) +
                 '<span style="color:var(--acc)">━ main</span><span>━ branch</span><span style="color:var(--err)">╌ error</span><span style="color:var(--ret)">┈ return / loop</span></div>'
                 f'<div class="pane" data-pane="flow"><div class="split"><div class="card"><h4>Flow by actors and processes<button type="button" class="fitbtn">Fit width</button></h4><div class="scroll">{render_svg(f)}</div></div>'
                 f'<div class="card"><h4>Generated pseudocode</h4><div class="pseudo">{_pseudo_html(f)}</div></div></div></div>'
                 f'<div class="pane hide" data-pane="matrix"><div class="card"><h4>Who does what, in which process</h4><div class="scroll">{_matrix_html(f)}</div></div></div>'
                 '<div class="trail"></div></div>')
    P.append('<div id="info"></div></main>')
    P.append(f'<script type="application/json" id="model">{json.dumps(model).replace("</", "<\\/")}</script><script>{JS}</script></body></html>')
    return ''.join(P)


# ------------------------------------------------------------------- Mermaid


def to_mermaid(f):
    out = ['flowchart TD']
    for n in f['nodes']:
        lab = ((n['code'] + ' ') if n['code'] else '') + n['label']
        lab = lab.replace('"', "'")
        out.append({'start': f'  {n["id"]}(["{lab}"])', 'end': f'  {n["id"]}(["{lab}"])', 'decision': f'  {n["id"]}{{"{lab}"}}'}.get(n['type'], f'  {n["id"]}["{lab}"]'))
    for e in f['edges']:
        lb = e['label'].replace('"', "'")
        out.append(f'  {e["from"]} -- "{lb}" --> {e["to"]}' if lb else f'  {e["from"]} --> {e["to"]}')
    return '\n'.join(out)


# ----------------------------------------------------------------------- CLI


def check_file(path, spec_dir=None):
    """Parse + validate. Returns (flows, errors, warnings)."""
    try:
        text = Path(path).read_text(encoding='utf-8')
    except OSError as exc:
        return [], [f'cannot read {path}: {exc}'], []
    flows, perr = parse_toon(text)
    errors, warnings = validate(flows, perr)
    if not errors and spec_dir:
        warnings += cross_check_codes(flows, spec_dir)
    return flows, errors, warnings


def main(argv=None):
    ap = argparse.ArgumentParser(description='AIDD Flowmap: render a .flow.toon to an interactive HTML flow + pseudocode.')
    ap.add_argument('flow_file')
    ap.add_argument('-o', '--output')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--pseudo', action='store_true', help='print generated pseudocode as markdown')
    ap.add_argument('--mermaid', action='store_true', help='print Mermaid per flow (markdown-embed fallback)')
    ap.add_argument('--spec-dir')
    ap.add_argument('--open', action='store_true')
    a = ap.parse_args(argv)
    flows, errors, warnings = check_file(a.flow_file, a.spec_dir)
    for w in warnings:
        print(f'WARN  {w}')
    for e in errors:
        print(f'ERROR {e}')
    if errors:
        print(f'\n{len(errors)} error(s) — fix the TOON and rerun. Nothing rendered.')
        return 1
    if a.check:
        print(f'OK — {len(flows)} flow(s) valid' + (f', {len(warnings)} warning(s)' if warnings else ''))
        return 0
    if a.pseudo:
        print('\n\n'.join(pseudo_markdown(f) for f in flows))
        return 0
    if a.mermaid:
        for f in flows:
            print(f"## {f['id']} — {f['title']}\n\n```mermaid\n{to_mermaid(f)}\n```\n")
        return 0
    src = Path(a.flow_file)
    out = Path(a.output) if a.output else src.with_name(re.sub(r'\.flow\.toon$|\.toon$', '', src.name) + '.html')
    out.write_text(render_html(flows, title=f"Flowmap — {src.parent.name or src.stem}", spec=src.parent.name), encoding='utf-8')
    print(f'OK — rendered {len(flows)} flow(s) -> {out.resolve()}')
    if a.open:
        webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == '__main__':
    sys.exit(main())
