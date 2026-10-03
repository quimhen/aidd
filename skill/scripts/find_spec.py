#!/usr/bin/env python3
"""
aidd spec finder — mechanical search over specs/*/ so Step -1 ("search before
creating: amend, don't duplicate") is a script call, not a remembered habit.

Run this BEFORE creating any specs/[###-feature]/ folder. It searches every
existing spec for the screen/control/component codes and keywords in your
query and ranks matches, so a follow-up fix or small correction lands as an
amendment to the existing spec (full context, existing codes, existing
history) instead of fragmenting into a fresh, disconnected spec folder.

Backed by a compact TOON index (specs/index.toon) so a normal search does NOT
re-read every file in every spec folder: it loads the index (one small text
file, tabular rows instead of verbose per-item JSON), checks file mtimes with
a cheap stat() per file (no content read) to see if anything changed since the
index was built, and only re-reads content to rebuild the index when
something actually changed — or to pull evidence lines for the single
top-ranked match. Everything else is served from memory.

TOON here is a minimal, self-contained tabular encoding (this script is both
its only writer and only reader — not a general-purpose TOON library):
    version: 3
    generated: <iso timestamp>
    specs[<N>]{id,title,codes,words,tree,files}:
      (words = top MAX_WORDS_PER_SPEC accent-folded terms by TF-IDF across all specs)
      <csv row per spec — codes/words pipe-joined, files as name=mtime;...>

The `tree` field captures the spec's real structure, parsed from
mockup-audit.md's own tables: use case (US-nnn) -> screen (SCREEN-XX) ->
component (COMP-nnn, if any) -> control/action (CTL-nnn) -> API (API-nnn, if
any) — encoded as root-to-leaf paths (`US-001>SCREEN-01>CTL-002`, piped
together). A screen with no use case assigned yet roots under `UNASSIGNED`.
This is what lets a search or an amendment answer "which use case / screen /
action does this belong to", not just "which spec file mentions this word".

Usage:
    python find_spec.py <query words or codes...>
    python find_spec.py --list                  # list every existing spec, no query
    python find_spec.py --tree <spec-id>          # print that spec's use-case/screen/action tree
    python find_spec.py --code <CODE>            # one node: kind/label/file:line + in/out neighbours (<=25 lines)
    python find_spec.py --reindex                # force a full index rebuild, no search

Examples:
    python find_spec.py "boton guardar" login
    python find_spec.py SCREEN-08
    python find_spec.py "fix date picker" CTL-014

Exit code 0 = match(es) found -> amend the top match, do not create a new folder.
Exit code 1 = no match found  -> safe to proceed to Step 0 / create a new spec.
Exit code 2 = usage error.
"""
import csv
import io
import math
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

CODE_RE = re.compile(r'\b(SCREEN-\d+(?:-F\d+)?|CTL-\d+|COMP-\d+|API-\d+|US-\d+)\b', re.IGNORECASE)

SEARCHED_FILES = [
    'spec.md', 'mockup-audit.md', 'plan.md', 'tasks.md',
    'contracts.md', 'data-model.md', 'qa-audit.md',
    'comprehensive-documentation.md', 'visual-flow.md', 'visual-flow.toon',
]

STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'of', 'to', 'in', 'on', 'for', 'with',
    'this', 'that', 'is', 'it', 'de', 'la', 'el', 'los', 'las', 'un', 'una',
    'que', 'con', 'para', 'del', 'en', 'y', 'o', 'se', 'al', 'es', 'lo',
    'pantalla', 'screen', 'fix', 'bug', 'change', 'cambio',
}

# Extra filler dropped from the INDEX only (ES + EN). Entries are accent-folded.
INDEX_STOPWORDS = {
    # code/log noise that leaks into specs and crowds out real vocabulary
    'fixed', 'still', 'doesn', 'const', 'null', 'pass', 'verified', 'checked', 'completed', 'failed',
    'true', 'false', 'return', 'class', 'import', 'string', 'dart',
    # Spanish filler
    'como', 'cada', 'entre', 'desde', 'hasta', 'sobre', 'cuando', 'donde',
    'tambien', 'puede', 'pueden', 'deben', 'debe', 'deber', 'debera', 'deberan',
    'esta', 'estan', 'este', 'estos', 'estas', 'esto', 'esos', 'esas', 'ese',
    'pero', 'porque', 'aunque', 'segun', 'sino', 'solo', 'todo', 'todos', 'toda',
    'todas', 'otro', 'otra', 'otros', 'otras', 'mismo', 'misma', 'mismos',
    'cual', 'cuales', 'quien', 'tiene', 'tienen', 'tener', 'hacer', 'hace',
    'hacen', 'ser', 'sera', 'seran', 'son', 'fue', 'sido', 'siendo', 'estar',
    'esta', 'muy', 'mas', 'menos', 'otro', 'cada', 'sin', 'ante', 'bajo',
    'tras', 'durante', 'mediante', 'cual', 'asi', 'aqui', 'alli', 'ahora',
    'luego', 'antes', 'despues', 'entonces', 'siempre', 'nunca', 'ademas',
    'incluye', 'incluyen', 'cuyo', 'cuya', 'dicho', 'dicha', 'unos', 'unas',
    'hay', 'haya', 'sean', 'cuenta', 'parte', 'forma', 'caso', 'casos',
    # English filler
    'from', 'have', 'been', 'will', 'must', 'should', 'would', 'could', 'also',
    'when', 'where', 'which', 'while', 'their', 'there', 'then', 'than', 'them',
    'they', 'these', 'those', 'what', 'such', 'each', 'into', 'over', 'only',
    'some', 'does', 'done', 'were', 'your', 'ours', 'about', 'after', 'before',
    'being', 'both', 'other', 'more', 'most', 'make', 'made', 'uses', 'used',
    'using', 'with', 'without', 'within', 'any', 'all', 'not', 'are', 'was',
    'can', 'may', 'its', 'has', 'had', 'but', 'via',
}
MAX_WORDS_PER_SPEC = 25
MIN_WORD_LEN = 4

INDEX_FILENAME = 'index.toon'
INDEX_VERSION = 4
TABLE_FIELDS = ['id', 'title', 'codes', 'words', 'tree', 'graph', 'files']
TABLE_HEADER_RE = re.compile(r'^specs\[(\d+)\]\{([^}]*)\}:\s*$')
TABLE_ROW_RE = re.compile(r'^\|(.+)\|\s*$')


# ---------------------------------------------------------------------------
# Minimal TOON tabular encode/decode (own format, own reader — see docstring)
# ---------------------------------------------------------------------------

def _csv_row(fields):
    buf = io.StringIO()
    csv.writer(buf, lineterminator='').writerow(fields)
    return buf.getvalue()


def _parse_csv_row(line):
    return next(csv.reader([line]))


def _encode_files(files_mtime: dict) -> str:
    return ';'.join(f"{name}={round(mtime, 3)}" for name, mtime in sorted(files_mtime.items()))


def _decode_files(raw: str) -> dict:
    if not raw:
        return {}
    out = {}
    for part in raw.split(';'):
        if '=' not in part:
            continue
        name, _, mtime = part.partition('=')
        try:
            out[name] = float(mtime)
        except ValueError:
            continue
    return out


def _encode_tree(paths: list) -> str:
    return '|'.join('>'.join(p) for p in paths)


def _decode_tree(raw: str) -> list:
    if not raw:
        return []
    return [p.split('>') for p in raw.split('|') if p]


def _pct(s) -> str:
    return str(s).replace('%', '%25').replace(':', '%3A').replace(';', '%3B')


def _unpct(s: str) -> str:
    return s.replace('%3A', ':').replace('%3B', ';').replace('%25', '%')


def encode_graph(graph) -> str:
    """Graph -> one TOON cell: ';'-joined records N:id:kind:file:line:label and
    E:src:dst:kind. ':' ';' '%' are percent-encoded inside fields."""
    try:
        recs = []
        for nid, n in sorted(graph.get('nodes', {}).items()):
            label = re.sub(r'[|;:\s]+', ' ', str(n.get('label', ''))).strip()[:60]
            recs.append(':'.join(['N', _pct(nid), _pct(n.get('kind', '')), _pct(n.get('file', '')),
                                  str(int(n.get('line', 0) or 0)), _pct(label)]))
        for src, dst, kind in graph.get('edges', []):
            recs.append(':'.join(['E', _pct(src), _pct(dst), _pct(kind)]))
        return ';'.join(recs)
    except Exception:
        return ''


def decode_graph(cell) -> dict:
    """Inverse of encode_graph. Never raises: a bad cell yields an empty graph."""
    nodes, edges = {}, []
    try:
        for rec in (cell or '').split(';'):
            parts = rec.split(':')
            if parts[0] == 'N' and len(parts) == 6:
                nodes[_unpct(parts[1])] = {'kind': _unpct(parts[2]), 'label': _unpct(parts[5]),
                                           'file': _unpct(parts[3]), 'line': int(parts[4] or 0)}
            elif parts[0] == 'E' and len(parts) == 4:
                edges.append((_unpct(parts[1]), _unpct(parts[2]), _unpct(parts[3])))
    except Exception:
        return {'nodes': {}, 'edges': []}
    return {'nodes': nodes, 'edges': edges}


def dumps_index(index: dict) -> str:
    lines = [f"version: {index['version']}", f"generated: {index['generated']}"]
    specs = index['specs']
    lines.append(f"specs[{len(specs)}]{{{','.join(TABLE_FIELDS)}}}:")
    for spec_id in sorted(specs):
        entry = specs[spec_id]
        row = [
            spec_id,
            entry.get('title', ''),
            '|'.join(entry.get('codes', [])),
            '|'.join(entry.get('words', [])),
            _encode_tree(entry.get('tree', [])),
            entry.get('graph', ''),
            _encode_files(entry.get('files', {})),
        ]
        lines.append('  ' + _csv_row(row))
    return '\n'.join(lines) + '\n'


def loads_index(text: str):
    lines = text.splitlines()
    meta = {}
    specs = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        m = TABLE_HEADER_RE.match(line.strip())
        if m:
            count = int(m.group(1))
            i += 1
            for _ in range(count):
                if i >= len(lines):
                    break
                row = _parse_csv_row(lines[i].strip())
                i += 1
                if len(row) != len(TABLE_FIELDS):
                    continue
                spec_id, title, codes_raw, words_raw, tree_raw, graph_raw, files_raw = row
                specs[spec_id] = {
                    'path': spec_id,
                    'title': title,
                    'codes': [c for c in codes_raw.split('|') if c],
                    'words': [w for w in words_raw.split('|') if w],
                    'tree': _decode_tree(tree_raw),
                    'graph': graph_raw,
                    'files': _decode_files(files_raw),
                }
            continue
        if ':' in line:
            key, _, val = line.partition(':')
            meta[key.strip()] = val.strip()
        i += 1
    return {'version': int(meta.get('version', 0)), 'generated': meta.get('generated', ''), 'specs': specs}


# ---------------------------------------------------------------------------
# Spec scanning
# ---------------------------------------------------------------------------

def find_specs_root(start: Path):
    cur = start.resolve()
    for _ in range(6):
        candidate = cur / 'specs'
        if candidate.is_dir():
            return candidate
        cur = cur.parent
    return None


def fold(text: str) -> str:
    """Lowercase + strip accents (NFKD, drop combining marks): 'Opción' -> 'opcion'."""
    return ''.join(
        c for c in unicodedata.normalize('NFKD', text.lower())
        if not unicodedata.combining(c)
    )


_FOLDED_STOP = {fold(w) for w in STOPWORDS} | {fold(w) for w in INDEX_STOPWORDS}
_HEX_RE = re.compile(r'[0-9a-f]+')


def index_terms(text: str) -> Counter:
    """Accent-folded term counts for the index: len >= MIN_WORD_LEN, no
    stopwords, no pure numbers, no hex-like tokens (hashes, ids)."""
    out = Counter()
    for raw in re.findall(r'\w+', text, re.UNICODE):
        w = fold(raw).strip('_')
        if len(w) < MIN_WORD_LEN or w in _FOLDED_STOP:
            continue
        if w.isdigit() or (_HEX_RE.fullmatch(w) and (any(c.isdigit() for c in w) or len(w) >= 8)):
            continue
        if CODE_RE.fullmatch(raw):
            continue
        out[w] += 1
    return out


def rank_tfidf(tfs: dict, limit: int = MAX_WORDS_PER_SPEC) -> dict:
    """tfs: {spec_id: Counter}. Returns {spec_id: top-`limit` terms by TF-IDF
    across all specs} (ties broken alphabetically, so output is deterministic)."""
    n = len(tfs)
    df = Counter()
    for tf in tfs.values():
        df.update(tf.keys())
    ranked = {}
    for spec_id, tf in tfs.items():
        total = sum(tf.values()) or 1
        scored = [
            (-(c / total) * (math.log((1 + n) / (1 + df[t])) + 1.0), t)
            for t, c in tf.items()
        ]
        scored.sort()
        ranked[spec_id] = [t for _, t in scored[:limit]]
    return ranked


def memory_hits_for(codes, root=None, limit=3):
    """Best-effort `m-id type title` lines from AIDD Memory for the matched
    codes. Never raises and never fails the search: returns [] when there is
    no root, no memory dir, or aidd_memory is not importable."""
    if not codes or root is None:
        return []
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import aidd_memory
        seen, lines = set(), []
        for code in sorted(codes):
            for e in aidd_memory.search(root, '', code=code, limit=limit):
                if e['id'] not in seen:
                    seen.add(e['id'])
                    lines.append(f"{e['id']}  {e['type']}  {e['title']}")
        return lines[:limit]
    except Exception:
        return []


def memory_nodes_for(codes, root=None, limit=3):
    """Best-effort (nodes, edges) for AIDD Memory entries tied to `codes`:
    MEM-<id> nodes plus (MEM-<id>, code, 'mentions') edges. Never raises;
    ([], []) when root, memory dir or aidd_memory is missing."""
    if not codes or root is None:
        return [], []
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import aidd_memory
        nodes, edges, seen = [], [], set()
        for code in sorted(codes):
            for e in aidd_memory.search(root, '', code=code, limit=limit):
                mid = f"MEM-{e['id']}"
                if mid not in seen:
                    if len(seen) >= limit:
                        continue
                    seen.add(mid)
                    nodes.append({'id': mid, 'kind': 'MEM',
                                  'label': f"{e['type']} {e['title']}".strip()[:60],
                                  'file': '.aidd/memory', 'line': 0})
                edges.append((mid, code, 'mentions'))
        return nodes, edges
    except Exception:
        return [], []


def tokenize_query(query_terms):
    """Unicode-aware: \\w+ matches any script's letters (Latin incl. accents,
    Cyrillic, CJK, etc.), not just a hardcoded Latin-accent whitelist — a
    Portuguese/German/etc. query loses no accented words, and a CJK query at
    least matches as a run of characters instead of producing zero tokens."""
    words = []
    codes = set()
    for term in query_terms:
        codes.update(m.upper() for m in CODE_RE.findall(term))
        for raw in re.findall(r'\w+', term, re.UNICODE):
            w = raw.lower().strip()
            if len(w) >= 3 and w not in STOPWORDS and not CODE_RE.fullmatch(raw):
                words.append(w)
    return codes, words


def tokenize_text(text):
    words = set()
    for raw in re.findall(r'\w+', text, re.UNICODE):
        w = raw.lower().strip()
        if len(w) >= 3 and w not in STOPWORDS:
            words.add(w)
    return words


def table_rows(text, header_hint):
    """Cell-lists for the first markdown table following a line containing
    header_hint (a '## Section' heading or the table's own header row)."""
    lines = text.splitlines()
    rows = []
    found_hint = False
    in_table = False
    header_seen = False
    for line in lines:
        if not found_hint:
            if header_hint in line:
                found_hint = True
            continue
        if not in_table:
            stripped = line.strip()
            if stripped.startswith('|'):
                in_table = True
            elif stripped.startswith('#'):
                found_hint = False
                continue
            else:
                continue
        m = TABLE_ROW_RE.match(line.strip())
        if not m:
            if header_seen:
                in_table = False
                found_hint = False
            continue
        cells = [c.strip() for c in m.group(1).split('|')]
        if not header_seen:
            header_seen = True
            continue
        if set(''.join(cells)) <= set('-: '):
            continue
        rows.append(cells)
    return rows


def cell_codes(cell: str):
    seen = []
    for c in CODE_RE.findall(cell or ''):
        cu = c.upper()
        if cu not in seen:
            seen.append(cu)
    return seen


def parse_relationship_edges(mockup_audit_text: str):
    """(parent, child) edges from mockup-audit.md's own tables: US-nnn -> SCREEN-XX
    -> COMP-nnn -> CTL-nnn -> API-nnn. This is the spec's real structure — which
    screen belongs to which use case, which control belongs to which screen/component."""
    edges = set()

    for r in table_rows(mockup_audit_text, 'Screen inventory'):
        if not r or not r[0].upper().startswith('SCREEN-'):
            continue
        screen = r[0].upper()
        uses = r[4] if len(r) > 4 else ''
        use_case = r[5] if len(r) > 5 else ''
        us_codes = cell_codes(use_case)
        if us_codes:
            for us in us_codes:
                edges.add((us, screen))
        else:
            edges.add(('UNASSIGNED', screen))
        for comp in cell_codes(uses):
            edges.add((screen, comp))

    for r in table_rows(mockup_audit_text, 'Component inventory'):
        if not r or not r[0].upper().startswith('COMP-'):
            continue
        comp = r[0].upper()
        used_in = r[2] if len(r) > 2 else ''
        contains = r[3] if len(r) > 3 else ''
        for scr in cell_codes(used_in):
            edges.add((scr, comp))
        for ctl in cell_codes(contains):
            edges.add((comp, ctl))

    for r in table_rows(mockup_audit_text, 'Control inventory'):
        if not r or not r[0].upper().startswith('CTL-'):
            continue
        ctl = r[0].upper()
        parent = r[1] if len(r) > 1 else ''
        parent_codes = cell_codes(parent)
        if parent_codes:
            edges.add((parent_codes[0], ctl))
        calls_api = r[6] if len(r) > 6 else ''
        for api in cell_codes(calls_api):
            edges.add((ctl, api))

    return edges


GRAPH_CODE_RE = re.compile(r'\b(?:AC|FR|T|API|US|SCREEN|COMP|CTL)-\d+(?:-F\d+)?', re.IGNORECASE)
NODE_KINDS = ('US', 'SCREEN', 'COMP', 'CTL', 'AC', 'FR', 'T', 'API', 'MEM')
EDGE_KINDS = ('contains', 'cites', 'satisfies', 'targets', 'mentions')
_GRAPH_LABEL_MAX = 60


def _graph_label(text, limit=_GRAPH_LABEL_MAX):
    s = re.sub(r'[|;:`*]', ' ', text or '')
    return re.sub(r'\s+', ' ', s).strip()[:limit].strip()


def _graph_codes(cell):
    seen = []
    for c in GRAPH_CODE_RE.findall(cell or ''):
        cu = c.upper()
        if cu not in seen:
            seen.append(cu)
    return seen


def _md_tables(text):
    """[(section_heading_lower, header_cells, [(lineno, cells), ...]), ...] for every
    markdown table in text. Never raises."""
    out = []
    heading = ''
    cur = None
    try:
        for i, line in enumerate((text or '').splitlines(), 1):
            s = line.strip()
            m = TABLE_ROW_RE.match(s)
            if not m:
                cur = None
                if s.startswith('#'):
                    heading = s.lstrip('#').strip().lower()
                continue
            cells = [c.strip() for c in m.group(1).split('|')]
            if cur is None:
                cur = (heading, [c.lower() for c in cells], [])
                out.append(cur)
            elif set(''.join(cells)) <= set('-: '):
                continue
            else:
                cur[2].append((i, cells))
    except Exception:
        return []
    return out


def _col(header, *needles):
    for idx, h in enumerate(header):
        if any(n in h for n in needles):
            return idx
    return None


def _cell(cells, idx):
    return cells[idx] if idx is not None and idx < len(cells) else ''


def parse_spec_nodes(spec_md_text):
    """(nodes, edges) from spec.md: AC-nnn rows of '## Acceptance cases' and FR-nnn
    rows of '## Functional requirements'; edges FR -> cited codes ('cites')."""
    nodes, edges = [], []
    try:
        for heading, header, rows in _md_tables(spec_md_text):
            if 'acceptance cases' in heading:
                kind, label_col = 'AC', _col(header, 'real data')
            elif 'functional requirements' in heading:
                kind, label_col = 'FR', _col(header, 'requirement')
            else:
                continue
            cites_col = _col(header, 'cites')
            if label_col is None:
                label_col = 1
            for lineno, cells in rows:
                m = re.match(r'^[`*\s]*((?:AC|FR)-\d+)\b', cells[0] if cells else '', re.IGNORECASE)
                if not m or m.group(1).upper()[:2] != kind:
                    continue
                nid = m.group(1).upper()
                nodes.append({'id': nid, 'kind': kind,
                              'label': _graph_label(_cell(cells, label_col)), 'line': lineno})
                if kind == 'FR':
                    for code in _graph_codes(_cell(cells, cites_col)):
                        if code != nid and code.split('-')[0] in ('AC', 'API', 'SCREEN', 'COMP', 'CTL'):
                            edges.append((nid, code, 'cites'))
    except Exception:
        return [], []
    return nodes, edges


def parse_task_nodes(tasks_md_text):
    """(nodes, edges) from the main task table of tasks.md: T-nn nodes labelled with
    the target file; edges T -> code ('satisfies') and T -> target file ('targets')."""
    nodes, edges = [], []
    try:
        for _heading, header, rows in _md_tables(tasks_md_text):
            codes_col = _col(header, 'codes')
            target_col = _col(header, 'target')
            for lineno, cells in rows:
                m = re.match(r'^[`*\s]*(T-\d+)\s*[`*]*\s*$', cells[0] if cells else '', re.IGNORECASE)
                if not m:
                    continue
                tid = m.group(1).upper()
                target = _cell(cells, target_col).strip().strip('`').strip()
                nodes.append({'id': tid, 'kind': 'T', 'label': _graph_label(target), 'line': lineno})
                for code in _graph_codes(_cell(cells, codes_col)):
                    if code.split('-')[0] in ('FR', 'AC', 'API', 'SCREEN', 'COMP', 'CTL'):
                        edges.append((tid, code, 'satisfies'))
                if target:
                    edges.append((tid, target, 'targets'))
    except Exception:
        return [], []
    return nodes, edges


def parse_contract_nodes(contracts_md_text):
    """(nodes, edges) from contracts.md: each distinct API-nnn at the start of a table
    row's first cell or in a markdown heading. No edges."""
    nodes, seen = [], set()
    try:
        for i, line in enumerate((contracts_md_text or '').splitlines(), 1):
            s = line.strip()
            if s.startswith('#'):
                htext = s.lstrip('#').strip()
                m = re.search(r'\bAPI-\d+\b', htext, re.IGNORECASE)
                if not m:
                    continue
                label = htext[:m.start()] + ' ' + htext[m.end():]
            else:
                rm = TABLE_ROW_RE.match(s)
                if not rm:
                    continue
                cells = [c.strip() for c in rm.group(1).split('|')]
                m = re.match(r'^[`*\s]*(API-\d+)\b', cells[0], re.IGNORECASE)
                if not m:
                    continue
                label = ''
                for c in cells[1:]:
                    if c and not re.fullmatch(r'[\s`*,]*(?:API-\d+[\s`*,]*)+', c, re.IGNORECASE):
                        label = c
                        break
            nid = m.group(0).strip('`* ').upper() if not s.startswith('#') else m.group(0).upper()
            if nid in seen:
                continue
            seen.add(nid)
            nodes.append({'id': nid, 'kind': 'API',
                          'label': _graph_label(label.strip(' -')), 'line': i})
    except Exception:
        return [], []
    return nodes, []


def _read_text(path: Path):
    try:
        return path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return None


def build_graph(spec_dir):
    """{'nodes': {id: {kind,label,file,line}}, 'edges': [(src,dst,kind)]} merging the
    mockup chain ('contains') with spec/tasks/contracts parsers. First definition wins."""
    graph_nodes, graph_edges = {}, []
    try:
        spec_dir = Path(spec_dir)
        audit = _read_text(spec_dir / 'mockup-audit.md')
        if audit:
            try:
                for e in parse_relationship_edges(audit):
                    if len(e) == 2:
                        graph_edges.append((e[0], e[1], 'contains'))
            except Exception:
                pass
        for fname, parser in (('spec.md', parse_spec_nodes), ('tasks.md', parse_task_nodes),
                              ('contracts.md', parse_contract_nodes)):
            text = _read_text(spec_dir / fname)
            if not text:
                continue
            nodes, edges = parser(text)
            for n in nodes:
                if n['id'] not in graph_nodes:
                    graph_nodes[n['id']] = {'kind': n['kind'], 'label': n['label'],
                                            'file': fname, 'line': n['line']}
            graph_edges.extend(edges)
    except Exception:
        pass
    return {'nodes': graph_nodes, 'edges': graph_edges}


def build_tree_paths(edges):
    """Root-to-leaf paths (root = a code that's never a child) — the spec's
    tree: use case -> screen -> component -> control -> API, in whatever
    subset of that chain the spec actually has."""
    children = {}
    all_children = set()
    for parent, child in edges:
        children.setdefault(parent, set()).add(child)
        all_children.add(child)
    roots = sorted(children.keys() - all_children)

    paths = []

    def dfs(node, path, visited):
        kids = children.get(node)
        if not kids:
            paths.append(path)
            return
        for k in sorted(kids):
            if k in visited:
                paths.append(path)  # cycle guard — stop, don't loop
                continue
            dfs(k, path + [k], visited | {k})

    for root in roots:
        dfs(root, [root], {root})
    return paths


def spec_title(spec_dir: Path):
    spec_md = spec_dir / 'spec.md'
    if spec_md.exists():
        try:
            for line in spec_md.read_text(encoding='utf-8').splitlines():
                if line.strip().startswith('#'):
                    return line.strip().lstrip('#').strip()
        except OSError:
            pass
    return ''


def build_spec_entry(spec_dir: Path):
    codes = set()
    tf = Counter()
    files_mtime = {}
    mockup_audit_text = ''
    for fname in SEARCHED_FILES:
        fpath = spec_dir / fname
        if not fpath.exists():
            continue
        try:
            stat = fpath.stat()
            text = fpath.read_text(encoding='utf-8')
        except OSError:
            continue
        files_mtime[fname] = stat.st_mtime
        codes.update(m.upper() for m in CODE_RE.findall(text))
        tf.update(index_terms(text))
        if fname == 'mockup-audit.md':
            mockup_audit_text = text

    tree = build_tree_paths(parse_relationship_edges(mockup_audit_text)) if mockup_audit_text else []

    graph = build_graph(spec_dir)
    try:
        mnodes, medges = memory_nodes_for(set(graph['nodes']), root=Path(spec_dir).resolve().parent.parent)
        for n in mnodes:
            graph['nodes'].setdefault(n['id'], {k: n[k] for k in ('kind', 'label', 'file', 'line')})
        graph['edges'].extend(medges)
    except Exception:
        pass

    return {
        'path': spec_dir.name,
        'title': spec_title(spec_dir),
        'codes': sorted(codes),
        'words': [],  # filled by build_index (TF-IDF needs all specs)
        '_tf': tf,
        'tree': tree,
        'graph': encode_graph(graph),
        'files': files_mtime,
    }


def build_index(specs_root: Path, spec_dirs):
    specs = {d.name: build_spec_entry(d) for d in spec_dirs}
    ranked = rank_tfidf({name: e.pop('_tf') for name, e in specs.items()})
    for name, e in specs.items():
        e['words'] = ranked[name]
    return {
        'version': INDEX_VERSION,
        'generated': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'specs': specs,
    }


def save_index(specs_root: Path, index: dict):
    try:
        (specs_root / INDEX_FILENAME).write_text(dumps_index(index), encoding='utf-8')
    except OSError as e:
        print(f"(warning: could not write {INDEX_FILENAME}: {e})", file=sys.stderr)


def load_index(specs_root: Path):
    idx_path = specs_root / INDEX_FILENAME
    if not idx_path.exists():
        return None
    try:
        data = loads_index(idx_path.read_text(encoding='utf-8'))
    except OSError:
        return None
    if data.get('version') != INDEX_VERSION:
        return None
    return data


def stale_spec_names(index: dict, spec_dirs):
    """Cheap staleness check: stat() every searched file that exists, compare
    mtimes against what's recorded — no content reads unless a name shows up
    here. Returns the set of spec directory names that are new, removed, or
    content-changed (empty set = fully cached, nothing to rebuild). Callers
    that only care about "changed at all" can check `bool(result)`; the
    multiagent Graph Coherence Auditor (see SKILL.md) uses the names
    themselves to scope its re-check to just the specs that actually moved,
    instead of re-validating the whole graph on every rebuild."""
    indexed_names = set(index.get('specs', {}).keys())
    actual_names = {d.name for d in spec_dirs}
    changed = indexed_names ^ actual_names  # added or removed specs
    for d in spec_dirs:
        if d.name in changed:
            continue
        entry = index['specs'][d.name]
        recorded = entry.get('files', {})
        current_files = {}
        broke = False
        for fname in SEARCHED_FILES:
            fpath = d / fname
            if fpath.exists():
                try:
                    current_files[fname] = fpath.stat().st_mtime
                except OSError:
                    changed.add(d.name)
                    broke = True
                    break
        if broke:
            continue
        if set(current_files.keys()) != set(recorded.keys()):
            changed.add(d.name)
            continue
        for fname, mtime in current_files.items():
            if abs(mtime - recorded.get(fname, -1)) > 0.5:
                changed.add(d.name)
                break
    return changed


def get_index(specs_root: Path, spec_dirs, force_reindex=False):
    """Returns (index, rebuilt, changed_names). `changed_names` is the set of
    specs whose SEARCHED_FILES content actually differs from what was last
    indexed — empty on a pure cache hit. `force_reindex` has no cheap way to
    know which subset changed, so it reports every spec name currently on
    disk rather than an understated empty set."""
    index = None if force_reindex else load_index(specs_root)
    if index is None or force_reindex:
        changed = {d.name for d in spec_dirs}
        index = build_index(specs_root, spec_dirs)
        save_index(specs_root, index)
        return index, True, changed
    changed = stale_spec_names(index, spec_dirs)
    if changed:
        index = build_index(specs_root, spec_dirs)
        save_index(specs_root, index)
        return index, True, changed
    return index, False, set()


def charter_warning(specs_root: Path, spec_dirs):
    """A project that already has specs but no project-root charter.md
    skipped Step -2 (see SKILL.md) — the spec graph still works (it only
    depends on mockup-audit.md's own tables), but naming/DB/checkable-rules
    consistency across those specs was never established. Returns None when
    there's nothing to warn about (no specs yet, or charter.md exists)."""
    if not spec_dirs:
        return None
    charter_path = specs_root.parent / 'charter.md'
    if charter_path.exists():
        return None
    return (
        f"WARNING: {len(spec_dirs)} spec(s) exist under {specs_root}, but no "
        f"charter.md at {specs_root.parent} — Step -2 was skipped. The graph below "
        f"still builds (it only reads mockup-audit.md's own tables), but run Step -2 "
        f"(copy templates/charter.md, and scripts/research_project.py if this "
        f"project has more unspecced code than specced) before trusting cross-spec "
        f"consistency."
    )


def report_index_status(rebuilt, changed):
    """One printed line, always — tells the calling agent whether to dispatch
    a Graph Coherence Auditor (see SKILL.md 'Graph coherence — multiagent
    verification') before trusting the tree/relationships just loaded."""
    if not rebuilt:
        print("Graph index: unchanged (cache hit) — no coherence re-check needed.")
        return
    changed_str = ', '.join(sorted(changed)) if changed else '(full rebuild)'
    print(f"Graph index: rebuilt — changed: {changed_str}. If this touched "
          f"US-nnn/SCREEN-XX/COMP-nnn/CTL-nnn/API-nnn relationships, dispatch a Graph "
          f"Coherence Auditor scoped to just these specs before trusting new edges (see "
          f"SKILL.md 'Graph coherence — multiagent verification').")


def score_from_index(entry, codes, words):
    entry_codes = set(entry.get('codes', []))
    entry_words = set(entry.get('words', []))
    matched_codes = codes & entry_codes
    matched_words = [w for w in (fold(w) for w in words) if w in entry_words]
    return 10 * len(matched_codes) + len(matched_words)


def evidence_lines(spec_dir: Path, codes, words, limit=8):
    """Read just this one spec folder's files to show which lines matched —
    only ever called for the single top-ranked result, never for every spec."""
    hits = []
    for fname in SEARCHED_FILES:
        fpath = spec_dir / fname
        if not fpath.exists():
            continue
        try:
            lines = fpath.read_text(encoding='utf-8').splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            line_codes = {c.upper() for c in CODE_RE.findall(line)}
            matched_codes = line_codes & codes
            folded_line = fold(line)
            matched_words = [w for w in words if fold(w) in folded_line]
            if matched_codes:
                hits.append((fname, lineno, line.strip(), 'code'))
            elif matched_words:
                hits.append((fname, lineno, line.strip(), 'word'))
            if len(hits) >= limit:
                return hits
    return hits


def fulltext_fallback(specs_root: Path, spec_dirs, codes, words):
    """Index-miss fallback: score every spec by scanning its searchable files.
    Whole-word, accent-insensitive match; a code hit weighs more than a word."""
    word_res = [re.compile(r'\b' + re.escape(fold(w)) + r'\b') for w in set(words)]
    results = []
    for d in spec_dirs:
        parts = []
        for fname in SEARCHED_FILES:
            fpath = d / fname
            if fpath.exists():
                try:
                    parts.append(fpath.read_text(encoding='utf-8'))
                except OSError:
                    continue
        if not parts:
            continue
        text = '\n'.join(parts)
        folded = fold(text)
        found_codes = {c.upper() for c in CODE_RE.findall(text)} & codes
        score = 3 * len(found_codes) + sum(1 for rx in word_res if rx.search(folded))
        if score > 0:
            results.append((score, d.name))
    results.sort(key=lambda r: r[0], reverse=True)
    return results


def neighbours(graph, code):
    """{'out': [(dst, kind)], 'in': [(src, kind)]} for `code` over a decoded graph."""
    out, inn = [], []
    for src, dst, kind in graph.get('edges', []):
        if src == code:
            out.append((dst, kind))
        if dst == code:
            inn.append((src, kind))
    return {'out': out, 'in': inn}


def locate_in_file(spec_dir, fname, code) -> int:
    """1-based line of the first line of spec_dir/fname containing `code`, else 0. Never raises."""
    try:
        needle = code.lower()
        with open(Path(spec_dir) / fname, encoding='utf-8') as fh:
            for i, line in enumerate(fh, 1):
                if needle in line.lower():
                    return i
    except Exception:
        pass
    return 0


def _node_loc(spec_dir, node):
    fname = node.get('file', '')
    line = node.get('line', 0) or 0
    if fname and not line and spec_dir is not None:
        line = locate_in_file(spec_dir, fname, node.get('_id', ''))
    return f"{fname}:{line}" if fname else ''


def print_code(index, code, specs_root=None, out=print) -> bool:
    """Print one capped block per spec whose graph holds `code`. True if found."""
    want = code.upper()
    hits = []
    for sid in sorted(index.get('specs', {})):
        entry = index['specs'][sid]
        graph = decode_graph(entry.get('graph', ''))
        nid = next((k for k in graph['nodes'] if k.upper() == want), None)
        if nid is not None:
            hits.append((sid, graph, nid))
    if not hits:
        out(f"No node '{code}'")
        m = re.match(r'[A-Za-z]+', code)
        if m:
            pre = m.group(0).upper()
            ids = sorted({k for e in index.get('specs', {}).values()
                          for k in decode_graph(e.get('graph', ''))['nodes']
                          if k.upper().startswith(pre + '-') or k.upper().startswith(pre)})
            if ids:
                out('  similar: ' + ', '.join(ids[:5]))
        return False

    per = 25 if len(hits) == 1 else max(6, 25 // len(hits))
    for sid, graph, nid in hits:
        spec_dir = Path(specs_root) / sid if specs_root is not None else None
        nodes = graph['nodes']

        def desc(i, arrow, kind):
            n = dict(nodes.get(i, {}))
            n['_id'] = i
            loc = _node_loc(spec_dir, n)
            return f"  {arrow} {i} [{kind}] {n.get('label', '')}  {loc}".rstrip()

        node = dict(nodes[nid])
        node['_id'] = nid
        loc = _node_loc(spec_dir, node)
        lines = [f"{nid} {node.get('kind', '')}  {node.get('label', '')}  ({sid}/{loc})"]
        nb = neighbours(graph, nid)
        total_extra = 0
        body = []
        for arrow, key in (('->', 'out'), ('<-', 'in')):
            mem_n = 0
            shown = 0
            for other, kind in nb[key]:
                is_mem = nodes.get(other, {}).get('kind') == 'MEM' or other.startswith('MEM-')
                if is_mem:
                    if mem_n >= 3:
                        total_extra += 1
                        continue
                    mem_n += 1
                elif shown >= 8:
                    total_extra += 1
                    continue
                else:
                    shown += 1
                body.append(desc(other, arrow, kind))
        room = per - 1 - (1 if total_extra else 0)
        if len(body) > room:
            total_extra += len(body) - (per - 2)
            body = body[:per - 2]
        lines.extend(body)
        if total_extra:
            lines.append(f"  ... +{total_extra} more (use --tree {sid})")
        for ln in lines[:per]:
            out(ln)
    return True


_TREE_KINDS = ('contains', 'cites', 'satisfies')


def _unified_children(graph):
    """parent -> sorted children using contains/cites and reversed satisfies."""
    children = {}
    for src, dst, kind in graph.get('edges', []):
        if kind in ('contains', 'cites'):
            p, c = src, dst
        elif kind == 'satisfies':
            p, c = dst, src
        else:
            continue
        if p == c:
            continue
        children.setdefault(p, set()).add(c)
    return children


def print_tree(entry):
    title = entry.get('title', '')
    print(f"{entry.get('path')}" + (f" — {title}" if title else ""))
    graph = decode_graph(entry.get('graph', ''))
    children = _unified_children(graph)
    paths = entry.get('tree', [])
    if children:
        nodes = graph['nodes']
        all_kids = set().union(*children.values())
        roots = sorted(children.keys() - all_kids)
        if not roots:
            roots = sorted(children)

        def label(code):
            lab = nodes.get(code, {}).get('label', '')
            return code + (f"  {lab}" if lab else '')

        def rec_g(code, depth, visited):
            print('  ' * depth + '- ' + label(code))
            for k in sorted(children.get(code, ())):
                if k in visited:
                    continue
                rec_g(k, depth + 1, visited | {k})

        for r in roots:
            rec_g(r, 1, {r})
        return
    if not paths:
        print("  (no structure captured — mockup-audit.md missing, or its Screen/Component/"
              "Control inventory tables have no rows yet)")
        return
    nested = {}
    for p in paths:
        node = nested
        for code in p:
            node = node.setdefault(code, {})

    def rec(node, depth):
        for code in sorted(node):
            print('  ' * depth + '- ' + code)
            rec(node[code], depth + 1)

    rec(nested, 1)


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(2)

    specs_root = find_specs_root(Path.cwd())
    if specs_root is None:
        print("No specs/ folder found walking up from the current directory — "
              "nothing to search. Safe to proceed and create the first spec.")
        sys.exit(1)

    spec_dirs = sorted(p for p in specs_root.iterdir() if p.is_dir())

    if args == ['--reindex']:
        index = build_index(specs_root, spec_dirs)
        save_index(specs_root, index)
        print(f"Rebuilt {specs_root / INDEX_FILENAME} — {len(index['specs'])} spec(s) indexed.")
        warning = charter_warning(specs_root, spec_dirs)
        if warning:
            print(warning)
        report_index_status(True, {d.name for d in spec_dirs})
        sys.exit(0)

    if len(args) == 2 and args[0] == '--tree':
        index, rebuilt, changed = get_index(specs_root, spec_dirs)
        warning = charter_warning(specs_root, spec_dirs)
        if warning:
            print(warning)
        report_index_status(rebuilt, changed)
        spec_id = args[1]
        entry = index['specs'].get(spec_id)
        if entry is None:
            print(f"No spec named '{spec_id}'. Known specs: {', '.join(sorted(index['specs']))}")
            sys.exit(2)
        print_tree(entry)
        sys.exit(0)

    if len(args) == 2 and args[0] == '--code':
        index, rebuilt, changed = get_index(specs_root, spec_dirs)
        found = print_code(index, args[1], specs_root)
        sys.exit(0 if found else 2)

    if args == ['--list']:
        if not spec_dirs:
            print(f"{specs_root}: no spec folders yet.")
            sys.exit(1)
        index, rebuilt, changed = get_index(specs_root, spec_dirs)
        warning = charter_warning(specs_root, spec_dirs)
        if warning:
            print(warning)
        report_index_status(rebuilt, changed)
        print(f"Existing specs under {specs_root} (from index, generated {index['generated']}):")
        for name in sorted(index['specs']):
            entry = index['specs'][name]
            title = entry.get('title', '')
            print(f"  {name}" + (f" — {title}" if title else ""))
        sys.exit(0)

    codes, words = tokenize_query(args)
    if not codes and not words:
        print("Query had no usable codes or keywords after stripping stopwords — "
              "be more specific (a SCREEN-XX/CTL-nnn code, or a few distinct words).")
        sys.exit(2)

    if not spec_dirs:
        print(f"{specs_root}: no spec folders yet. Safe to create the first one.")
        sys.exit(1)

    index, rebuilt, changed = get_index(specs_root, spec_dirs)
    warning = charter_warning(specs_root, spec_dirs)
    if warning:
        print(warning)
    report_index_status(rebuilt, changed)

    results = []
    for name, entry in index['specs'].items():
        score = score_from_index(entry, codes, words)
        if score > 0:
            results.append((score, name))
    results.sort(key=lambda r: r[0], reverse=True)

    used_fallback = False
    if not results:
        # The index only keeps each spec's top-25 terms, so a real word that is in
        # the spec text can miss it. Before declaring "no match" (which invites a
        # duplicate spec), scan the spec files themselves.
        results = fulltext_fallback(specs_root, spec_dirs, codes, words)
        used_fallback = bool(results)

    print(f"aidd spec search — query: {' '.join(args)}")
    print("=" * 60)
    if used_fallback:
        print("(index had no match — results below come from a full-text scan of the spec files)")

    if not results:
        print("No match found in any existing spec.")
        print("-> Safe to proceed to Step 0 and create a new specs/[###-feature]/ folder.")
        sys.exit(1)

    top_score, top_name = results[0]
    top_entry = index['specs'][top_name]
    top_dir = specs_root / top_name
    print(f"Top match: {top_name}  (score {top_score})")
    top_hits = evidence_lines(top_dir, codes, words)
    for fname, lineno, text, kind in top_hits:
        marker = 'CODE' if kind == 'code' else 'kw'
        print(f"  [{marker}] {fname}:{lineno}: {text[:120]}")

    matched_codes = codes & set(top_entry.get('codes', []))
    mem_lines = memory_hits_for(codes, specs_root.parent)
    if matched_codes:
        relevant_paths = [p for p in top_entry.get('tree', []) if any(c in matched_codes for c in p)]
        if relevant_paths:
            print("\nGraph context (use case -> screen -> component -> control -> API):")
            for p in relevant_paths[:5]:
                print("  " + ' > '.join(p))

    if mem_lines:
        print("\nMemory (aidd mem show <id> for the why):")
        for ln in mem_lines:
            print("  " + ln)

    if len(results) > 1:
        print("\nOther candidates:")
        for score, name in results[1:5]:
            print(f"  {name}  (score {score})")

    print(f"\n-> AMEND {top_name}: reopen its spec.md/mockup-audit.md/tasks.md and add to "
          f"them (per Step -1). Do NOT create a new specs/[###-feature]/ folder unless this is "
          f"genuinely a distinct feature area, not a follow-up/fix/phase-2 of this match.")
    sys.exit(0)


if __name__ == '__main__':
    main()
