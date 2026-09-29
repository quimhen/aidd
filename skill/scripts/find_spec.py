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
    version: 2
    generated: <iso timestamp>
    specs[<N>]{id,title,codes,words,tree,files}:
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
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

CODE_RE = re.compile(r'\b(SCREEN-\d+(?:-F\d+)?|CTL-\d+|COMP-\d+|API-\d+|US-\d+)\b', re.IGNORECASE)

SEARCHED_FILES = [
    'spec.md', 'mockup-audit.md', 'plan.md', 'tasks.md',
    'contracts.md', 'data-model.md', 'qa-audit.md',
    'comprehensive-documentation.md', 'visual-flow.md',
]

STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'of', 'to', 'in', 'on', 'for', 'with',
    'this', 'that', 'is', 'it', 'de', 'la', 'el', 'los', 'las', 'un', 'una',
    'que', 'con', 'para', 'del', 'en', 'y', 'o', 'se', 'al', 'es', 'lo',
    'pantalla', 'screen', 'fix', 'bug', 'change', 'cambio',
}

INDEX_FILENAME = 'index.toon'
INDEX_VERSION = 2
TABLE_FIELDS = ['id', 'title', 'codes', 'words', 'tree', 'files']
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
                spec_id, title, codes_raw, words_raw, tree_raw, files_raw = row
                specs[spec_id] = {
                    'path': spec_id,
                    'title': title,
                    'codes': [c for c in codes_raw.split('|') if c],
                    'words': [w for w in words_raw.split('|') if w],
                    'tree': _decode_tree(tree_raw),
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
    words = set()
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
        words |= tokenize_text(text)
        if fname == 'mockup-audit.md':
            mockup_audit_text = text

    tree = build_tree_paths(parse_relationship_edges(mockup_audit_text)) if mockup_audit_text else []

    return {
        'path': spec_dir.name,
        'title': spec_title(spec_dir),
        'codes': sorted(codes),
        'words': sorted(words),
        'tree': tree,
        'files': files_mtime,
    }


def build_index(specs_root: Path, spec_dirs):
    specs = {d.name: build_spec_entry(d) for d in spec_dirs}
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


def is_stale(index: dict, spec_dirs):
    """Cheap staleness check: stat() every searched file that exists, compare
    mtimes against what's recorded — no content reads unless this returns True."""
    indexed_names = set(index.get('specs', {}).keys())
    actual_names = {d.name for d in spec_dirs}
    if indexed_names != actual_names:
        return True
    for d in spec_dirs:
        entry = index['specs'][d.name]
        recorded = entry.get('files', {})
        current_files = {}
        for fname in SEARCHED_FILES:
            fpath = d / fname
            if fpath.exists():
                try:
                    current_files[fname] = fpath.stat().st_mtime
                except OSError:
                    return True
        if set(current_files.keys()) != set(recorded.keys()):
            return True
        for fname, mtime in current_files.items():
            if abs(mtime - recorded.get(fname, -1)) > 0.5:
                return True
    return False


def get_index(specs_root: Path, spec_dirs, force_reindex=False):
    index = None if force_reindex else load_index(specs_root)
    if index is None or is_stale(index, spec_dirs):
        index = build_index(specs_root, spec_dirs)
        save_index(specs_root, index)
    return index


def score_from_index(entry, codes, words):
    entry_codes = set(entry.get('codes', []))
    entry_words = set(entry.get('words', []))
    matched_codes = codes & entry_codes
    matched_words = [w for w in words if w in entry_words]
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
            matched_words = [w for w in words if w in line.lower()]
            if matched_codes:
                hits.append((fname, lineno, line.strip(), 'code'))
            elif matched_words:
                hits.append((fname, lineno, line.strip(), 'word'))
            if len(hits) >= limit:
                return hits
    return hits


def print_tree(entry):
    paths = entry.get('tree', [])
    title = entry.get('title', '')
    print(f"{entry.get('path')}" + (f" — {title}" if title else ""))
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
        sys.exit(0)

    if len(args) == 2 and args[0] == '--tree':
        index = get_index(specs_root, spec_dirs)
        spec_id = args[1]
        entry = index['specs'].get(spec_id)
        if entry is None:
            print(f"No spec named '{spec_id}'. Known specs: {', '.join(sorted(index['specs']))}")
            sys.exit(2)
        print_tree(entry)
        sys.exit(0)

    if args == ['--list']:
        if not spec_dirs:
            print(f"{specs_root}: no spec folders yet.")
            sys.exit(1)
        index = get_index(specs_root, spec_dirs)
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

    index = get_index(specs_root, spec_dirs)

    results = []
    for name, entry in index['specs'].items():
        score = score_from_index(entry, codes, words)
        if score > 0:
            results.append((score, name))
    results.sort(key=lambda r: r[0], reverse=True)

    print(f"aidd spec search — query: {' '.join(args)}")
    print("=" * 60)

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
    if matched_codes:
        relevant_paths = [p for p in top_entry.get('tree', []) if any(c in matched_codes for c in p)]
        if relevant_paths:
            print("\nGraph context (use case -> screen -> component -> control -> API):")
            for p in relevant_paths[:5]:
                print("  " + ' > '.join(p))

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
