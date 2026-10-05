#!/usr/bin/env python3
"""
aidd_review_items — the source markdown of a spec turned into reviewable ITEMS (spec 008).

Pure module (aidd:FR-301 aidd:FR-302 aidd:FR-311 aidd:FR-312 aidd:FR-313):
- no file IO, never prints; every input is a parameter (texts, dicts), every output a return value;
- never imports `aidd_review` or `aidd_review_state`; `aidd_rules` and `check_spec` are loaded
  lazily and are optional (a local fallback keeps every function working without them);
- every public function degrades instead of raising: an extractor failure becomes a per-tab
  warning, a missing piece becomes an empty value, so a coded row is never dropped silently.

The compiled `CODE_RE` defined here is THE code grammar: `aidd_review_state` receives it as a
parameter and the compact page JS carries the same pattern string (`CODE_RE_SRC`).
"""
import hashlib
import json
import re
import sys
from pathlib import Path

# --------------------------------------------------------------------------- caps (aidd:FR-301)
MAX_ITEMS = 2000
MAX_ITEM_TEXT = 240
MAX_SUMMARY = 2000
MAX_SUMMARY_FIELD = 400
MAX_WARN_NAMES = 8

# --------------------------------------------------------------------------- code grammar (aidd:FR-301)
# All compiled with re.ASCII and applied with fullmatch (never match/search: `$` would accept a
# trailing newline, and a Unicode digit would pass `\d` without re.ASCII).
# SCREEN/COMP/CTL/API take 1 to 5 digits: real mockup audits number controls per spec
# (F15 CTL-15001.., F23 CTL-23001..); FR/AC/T keep 1 to 4.
CODE_RE = re.compile(
    r'^(SUMMARY|Q\d{1,3}|D\d{1,3}(?:-?[a-z])?|V-\d{1,3}|(?:FR|AC|T)-\d{1,4}(?:-?[a-z])?|'
    r'(?:API|COMP|CTL|SCREEN)-\d{1,5}(?:-?[a-z])?)$',
    re.ASCII)
GENERIC_CODE_RE = re.compile(r'^(FR|AC|API|T|SCREEN|COMP|CTL|V)-\S+', re.ASCII)
PLACEHOLDER_RE = re.compile(r'^[A-Z]+-[nNxX]+(?:-F[nNxX]+)?$', re.ASCII)
FIELD_ROW_RE = re.compile(r'^(?:SCREEN|COMP)-\d+-F\d+$', re.ASCII)

# --------------------------------------------------------------------------- tabs (aidd:FR-301 aidd:FR-311)
TAB_ORDER = ('summary', 'questions', 'fr', 'ac', 'screens', 'api', 'tasks', 'verification')
TAB_LABELS = {
    'summary': 'Resumen',
    'questions': 'Preguntas',
    'fr': 'Requisitos',
    'ac': 'Casos',
    'screens': 'Pantallas',
    'api': 'API',
    'tasks': 'Tareas',
    'verification': 'Verificación',
}
_TAB_SOURCE = {
    'summary': 'spec.md', 'questions': 'spec.md', 'fr': 'spec.md', 'ac': 'spec.md',
    'verification': 'spec.md', 'screens': 'mockup-audit.md', 'api': 'contracts.md',
    'tasks': 'tasks.md',
}
_TAB_PREFIXES = {
    'fr': ('FR',), 'ac': ('AC',), 'screens': ('SCREEN', 'COMP', 'CTL'), 'api': ('API',),
    'tasks': ('T',), 'questions': ('Q', 'D'), 'verification': ('V',),
}
_PREFIX_TAB = {'FR': 'fr', 'AC': 'ac', 'SCREEN': 'screens', 'COMP': 'screens', 'CTL': 'screens',
               'API': 'api', 'T': 'tasks', 'Q': 'questions', 'D': 'questions', 'V': 'verification'}
_PREFIX_KIND = {'FR': 'fr', 'AC': 'ac', 'SCREEN': 'screen', 'COMP': 'comp', 'CTL': 'ctl',
                'API': 'api', 'T': 'task', 'Q': 'question', 'D': 'decision', 'V': 'verification'}
# Sources whose table rows are reviewable, with the code prefixes the completeness check counts.
_SOURCE_PREFIXES = (
    ('spec.md', ('FR', 'AC', 'V')),
    ('mockup-audit.md', ('SCREEN', 'COMP', 'CTL')),
    ('contracts.md', ('API',)),
    ('tasks.md', ('T',)),
)
_ITEM_SOURCES = ('spec.md', 'mockup-audit.md', 'contracts.md', 'tasks.md')

_WARN_NAME_CHARS = 21          # a skipped row's title in a warning ("Payment one cent s...")
_WARN_CODE_CHARS = 40
_HEADING_RE = re.compile(r'^ {0,3}#{1,6}[ \t]+(.*?)[ \t#]*$')
_FENCE_OPEN_RE = re.compile(r'^ {0,3}(`{3,}|~{3,})')
_COMMENT_RE = re.compile(r'<!--.*?-->', re.S)
_CELL_SPLIT_RE = re.compile(r'(?<!\\)\|')
_SEP_CELL_RE = re.compile(r'^:?-+:?$')
_PREFIX_RE = re.compile(r'^[A-Z]+', re.ASCII)
_EXPLICIT_Q_RE = re.compile(r'^Q(\d{1,3})(?![\w-])[\s:.)\-]*', re.ASCII)
_EMPH_RE = re.compile(r'[`*_]')
_LOCAL_BLANK_ANSWERS = {'', '-', '—', '–', '--', 'n/a', 'na', 'tbd', 'todo', '?', '...', '…', 'pending'}
_EDGE_YES = ('yes', 'y', 'si', 'sí', 'true', 'x', 'edge')
_SUMMARY_LABELS = (
    ('objective', ('objective', 'objetivo')),
    ('scope', ('scope', 'alcance')),
    ('cost', ('cost', 'costo', 'coste')),
    ('risks', ('risks', 'risk', 'riesgos', 'riesgo')),
    ('open_decisions', ('open decisions', 'decisiones abiertas', 'decisiones pendientes')),
)
_SUMMARY_HEADING_RE = re.compile(r'^(executive summary|resumen ejecutivo)\b', re.I)
_BULLET_RE = re.compile(r'^\s*[-*+]\s+(.*)$')


# --------------------------------------------------------------------------- lazy optional helpers

_LAZY = {}


def _script_dir_on_path():
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)


def _rules():
    """aidd_rules from this script's own directory, imported lazily (as the 007 `_rules()` of
    aidd_review). Raises ImportError when it is missing; every caller here catches it and falls
    back to a local equivalent or an empty value."""
    mod = _LAZY.get('rules')
    if mod is None:
        _script_dir_on_path()
        import aidd_rules as mod  # noqa: E402
        _LAZY['rules'] = mod
    return mod


def _check_spec():
    """check_spec from this script's own directory, or None (optional: local fallbacks)."""
    if 'check_spec' not in _LAZY:
        try:
            _script_dir_on_path()
            import check_spec  # noqa: E402
            _LAZY['check_spec'] = check_spec
        except Exception:
            _LAZY['check_spec'] = None
    return _LAZY['check_spec']


def _col(header, name):
    """Index of the first header cell starting with `name` (case-insensitive), -1 if none."""
    cs = _check_spec()
    plain = [_plain(h) for h in (header or [])]
    try:
        if cs is not None:
            return cs._col(plain, name)
    except Exception:
        pass
    low = name.lower()
    for i, h in enumerate(plain):
        if h.strip().lower().startswith(low):
            return i
    return -1


def _cell(row, i):
    cs = _check_spec()
    try:
        if cs is not None:
            return cs._cell(row, i)
    except Exception:
        pass
    return row[i].strip() if 0 <= i < len(row) else ''


def _blank(v):
    cs = _check_spec()
    try:
        if cs is not None:
            return cs._blank(v)
    except Exception:
        pass
    return (v or '').strip() in ('', '-')


# --------------------------------------------------------------------------- text helpers

def _norm(text):
    """Text with LF newlines, no BOM, HTML comments blanked (their newlines kept)."""
    if isinstance(text, bytes):
        text = text.decode('utf-8', errors='replace')
    if not isinstance(text, str):
        return ''
    s = text.replace('\r\n', '\n').replace('\r', '\n')
    if s.startswith('﻿'):
        s = s[1:]
    return _COMMENT_RE.sub(lambda m: '\n' * m.group(0).count('\n'), s)


def _plain(s):
    """Cell text without backticks, `*` and `_`, whitespace collapsed (the canon of a cell)."""
    return ' '.join(_EMPH_RE.sub('', str(s or '')).split())


def _display(s):
    """Cell text for the page: backticks and `*` emphasis removed, whitespace collapsed
    (underscores kept: they are part of identifiers such as fe_param)."""
    return ' '.join(re.sub(r'[`*]', '', str(s or '')).split())


def _short(text, n=MAX_ITEM_TEXT):
    """One line (whitespace collapsed), cut at `n` characters with `...`. aidd:FR-301"""
    try:
        s = ' '.join(str(text if text is not None else '').split())
        n = max(4, int(n))
        if len(s) > n:
            return s[:n - 3].rstrip() + '...'
        return s
    except Exception:
        return ''


def _first_token(cell):
    """First whitespace token of a cell after stripping backticks, `*` and `_`, trailing
    `, ; : .` dropped: the code of a row. aidd:FR-301"""
    try:
        s = _EMPH_RE.sub('', str(cell or '')).strip()
        if not s:
            return ''
        return s.split()[0].rstrip(',;:.')
    except Exception:
        return ''


def _prefix(code):
    m = _PREFIX_RE.match(code or '')
    return m.group(0) if m else ''


def _is_code(token, prefixes):
    """True when `token` is a CODE_RE code whose prefix is one of `prefixes`."""
    return bool(token) and CODE_RE.fullmatch(token) is not None and _prefix(token) in prefixes


def _canon_row(cells):
    return ' | '.join(_plain(c) for c in cells)


def _names(values, limit_chars, sep):
    vals = [_short(v, limit_chars) for v in values]
    shown = vals[:MAX_WARN_NAMES]
    out = sep.join(shown)
    if len(vals) > MAX_WARN_NAMES:
        out += sep + '...'
    return out


def _plural(n, word):
    return f'{n} {word}' + ('' if n == 1 else 's')


# --------------------------------------------------------------------------- tables (aidd:FR-301)

def _split_cells(line):
    s = line.strip()
    if s.startswith('|'):
        s = s[1:]
    if s.endswith('|') and not s.endswith('\\|'):
        s = s[:-1]
    return [c.replace('\\|', '|').strip() for c in _CELL_SPLIT_RE.split(s)]


def _is_sep(cells):
    filled = [c.strip() for c in cells if c.strip()]
    return bool(filled) and all(_SEP_CELL_RE.match(c.replace(' ', '')) for c in filled)


def _iter_lines(text):
    """(kind, payload) for every line outside fenced code: ('heading', text), ('row', line),
    ('other', None)."""
    fence = None
    for line in _norm(text).split('\n'):
        if fence is not None:
            m = re.match(r'^ {0,3}(`{3,}|~{3,})[ \t]*$', line)
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= fence[1]:
                fence = None
            yield ('other', None)
            continue
        m = _FENCE_OPEN_RE.match(line)
        if m:
            fence = (m.group(1)[0], len(m.group(1)))
            yield ('other', None)
            continue
        h = _HEADING_RE.match(line)
        if h:
            yield ('heading', _plain(h.group(1)))
            continue
        if line.strip().startswith('|'):
            yield ('row', line)
            continue
        yield ('other', None)


def _iter_tables(text):
    """[(heading, header, rows)] for EVERY table of a source, each one separately: fenced code
    and HTML comments skipped, header = first row, separator row dropped, rows equal to the
    header dropped, each table keeps its own header and the nearest preceding heading text.
    A block of rows with no separator right after a table of the same section (a blank line
    inside one table) continues that table instead of losing its first row as a header.
    Never raises. aidd:FR-301"""
    out = []
    try:
        heading, hid = '', 0
        cur = None

        def close(c):
            if c is None:
                return
            if (not c['sep'] and out and out[-1]['hid'] == c['hid'] and out[-1]['last']):
                prev = out[-1]
                hdr = [x.lower() for x in prev['header']]
                for r in [c['header']] + c['rows']:
                    if [x.lower() for x in r] != hdr and any(x for x in r):
                        prev['rows'].append(r)
                return
            for t in out:
                t['last'] = False
            c['last'] = True
            out.append(c)

        for kind, payload in _iter_lines(text):
            if kind == 'row':
                cells = _split_cells(payload)
                if cur is None:
                    cur = {'heading': heading, 'hid': hid, 'header': cells, 'rows': [], 'n': 1,
                           'sep': False, 'last': False}
                    continue
                cur['n'] += 1
                if _is_sep(cells):
                    if cur['n'] == 2:
                        cur['sep'] = True
                    continue
                if [c.lower() for c in cells] == [h.lower() for h in cur['header']]:
                    continue
                if any(c for c in cells):
                    cur['rows'].append(cells)
                continue
            if cur is not None:
                close(cur)
                cur = None
            if kind == 'heading':
                heading, hid = payload, hid + 1
                for t in out:
                    t['last'] = False
        close(cur)
    except Exception:
        pass
    return [(t['heading'], t['header'], t['rows']) for t in out]


def _iter_table_rows(text):
    """Independent row scan for the completeness check: (cells) of every table line outside
    fenced code and comments, header and separator rows included (a header never starts with a
    real code, and the caller filters by GENERIC_CODE_RE)."""
    for kind, payload in _iter_lines(text):
        if kind == 'row':
            cells = _split_cells(payload)
            if not _is_sep(cells):
                yield cells


def _is_template_row(prefix, header, cells):
    """An untouched template row: nothing but the code (or, for V-n, a blank Command cell)."""
    if prefix == 'V':
        ci = _col(header, 'command') if header else -1
        return _blank(_cell(cells, ci if ci >= 0 else 1))
    return all(_blank(c) for c in cells[1:])


# --------------------------------------------------------------------------- per-tab extraction

def _text_of(cells, header, names):
    """Display text of a row: the first named column that exists, else the 2nd cell, else the
    other non-blank cells joined."""
    for nm in names:
        ci = _col(header, nm)
        if ci > 0 and not _blank(_cell(cells, ci)):
            return _display(_cell(cells, ci))
    if not _blank(_cell(cells, 1)):
        return _display(_cell(cells, 1))
    return _display(' '.join(c for c in cells[1:] if not _blank(c)))


def _field_of(cells, header, name):
    ci = _col(header, name)
    if ci > 0 and not _blank(_cell(cells, ci)):
        return _short(_display(_cell(cells, ci)))
    return ''


def _is_edge(v):
    s = _plain(v).lower()
    return bool(s) and (s in _EDGE_YES or s.split()[0].rstrip('.,;:') in _EDGE_YES)


def _item(code, kind, text, source, canon, fields=None, edge=False, unanswered=False, mandatory=False):
    return {
        'code': code, 'kind': kind, 'text': _short(text),
        'fields': {k: v for k, v in (fields or {}).items() if v},
        'edge': bool(edge), 'unanswered': bool(unanswered), 'mandatory': bool(mandatory),
        'source': source, 'canon': canon,
    }


def _coded_rows(text, prefixes):
    """[(code, header, cells)] of every row of every table whose first token is a CODE_RE code
    of one of `prefixes`, untouched template rows excluded."""
    out = []
    for _heading, header, rows in _iter_tables(text):
        for cells in rows:
            tok = _first_token(_cell(cells, 0))
            if not _is_code(tok, prefixes):
                continue
            if _is_template_row(_prefix(tok), header, cells):
                continue
            out.append((tok, header, cells))
    return out


def _unique(tab, entries, warnings):
    """First occurrence of a code wins; repeats are reported in ONE counted line per tab."""
    seen, kept, repeats = set(), [], []
    for code, payload in entries:
        if code in seen:
            repeats.append(code)
            continue
        seen.add(code)
        kept.append((code, payload))
    if repeats:
        distinct = list(dict.fromkeys(repeats))
        n = len(repeats)
        word = 'repeated code' + ('' if n == 1 else 's')
        warnings.append({'tab': tab, 'text': f'{n} {word} skipped (first row wins): '
                                             f'{_names(distinct, _WARN_CODE_CHARS, ", ")}'})
    return kept


def _row_item(tab, code, header, cells, source, blocks=None):
    """aidd:FR-301 aidd:FR-311 aidd:FR-312: one item per coded row; canon = the FULL row."""
    prefix = _prefix(code)
    kind = _PREFIX_KIND.get(prefix, tab)
    canon = _canon_row(cells)
    if tab == 'fr':
        return _item(code, kind, _text_of(cells, header, ('requirement',)), source, canon)
    if tab == 'ac':
        ci = _col(header, 'edge')
        return _item(code, kind, _text_of(cells, header, ('real data',)), source, canon,
                     fields={'Expected': _field_of(cells, header, 'expected')},
                     edge=ci > 0 and _is_edge(_cell(cells, ci)))
    if tab == 'screens':
        return _item(code, kind, _text_of(cells, header, ('name', 'visible text')), source, canon,
                     fields={'Destination': _field_of(cells, header, 'destination')})
    if tab == 'api':
        return _item(code, kind, _text_of(cells, header, ('method',)), source, canon)
    if tab == 'verification':
        return _item(code, kind, _text_of(cells, header, ('command',)), source, canon,
                     fields={'Expected': _field_of(cells, header, 'expected'),
                             'Covers': _field_of(cells, header, 'covers')},
                     mandatory=True)
    if tab == 'tasks':
        minutes, tokens = _block_numbers((blocks or {}).get(code))
        return _item(code, kind, _text_of(cells, header, ('codes',)), source, canon,
                     fields={'Target file': _field_of(cells, header, 'target file'),
                             'Minutes': minutes, 'Tokens': tokens})
    return _item(code, kind, _text_of(cells, header, ()), source, canon)


def _ex_rows(tab, src, warnings):
    text = src.get(_TAB_SOURCE[tab])
    if not text:
        return []
    entries = [(code, (header, cells)) for code, header, cells in _coded_rows(text, _TAB_PREFIXES[tab])]
    return [_row_item(tab, code, h, c, _TAB_SOURCE[tab]) for code, (h, c) in _unique(tab, entries, warnings)]


def _task_blocks(text):
    try:
        return _rules()._task_blocks(_norm(text))
    except Exception:
        return {}


def _block_field(block, name):
    try:
        return _rules()._field(block, name)
    except Exception:
        return None


def _block_numbers(block):
    """(minutes, tokens) display strings of a `### T-nn` block ('' when unknown)."""
    if not block:
        return '', ''
    minutes = _block_field(block, 'agent min') or ''
    m = re.match(r'\s*(\d{1,9})', minutes)
    minutes = m.group(1) if m else ''
    tokens = ''
    raw = _block_field(block, 'tokens (est)')
    try:
        n = _rules()._tokens_k(raw) if raw is not None else None
        tokens = f'{n}k' if n is not None else ''
    except Exception:
        tokens = ''
    return minutes, tokens


def _ex_tasks(src, warnings):
    """Table rows first (target file from the Target file column), then `### T-nn` blocks that
    are not in the table; minutes/tokens from the blocks. aidd:FR-301"""
    text = src.get('tasks.md')
    if not text:
        return []
    blocks = _task_blocks(text)
    entries = [(code, ('row', header, cells)) for code, header, cells in _coded_rows(text, ('T',))]
    in_table = {code for code, _p in entries}
    for tid, blk in blocks.items():
        if tid in in_table or not CODE_RE.fullmatch(tid):
            continue
        entries.append((tid, ('block', None, blk)))
    out = []
    for code, (what, header, payload) in _unique('tasks', entries, warnings):
        if what == 'row':
            out.append(_row_item('tasks', code, header, payload, 'tasks.md', blocks))
            continue
        blk = payload or ''
        objective = _block_field(blk, 'objective') or ''
        first = next((ln for ln in blk.split('\n') if ln.strip()), '')
        minutes, tokens = _block_numbers(blk)
        target = _block_field(blk, 'target file') or ''
        out.append(_item(code, 'task', _display(objective or first), 'tasks.md',
                         ' '.join(_plain(blk).split()),
                         fields={'Target file': _short(_display(target)), 'Minutes': minutes,
                                 'Tokens': tokens}))
    return out


def _blank_answer(a):
    try:
        return bool(_rules()._blank_answer(a or ''))
    except Exception:
        s = _plain(a).strip().strip('.').lower()
        return s in _LOCAL_BLANK_ANSWERS or not re.search(r'\w', a or '')


def _checklist_rows(text):
    """[cells] of the Minimum Requirements Checklist (aidd_rules._checklist_rows; local
    fallback through _iter_tables when aidd_rules is not importable)."""
    try:
        r = _rules()
        _h, rows = r._checklist_rows(r._clean(text))
        return [list(x) for x in rows]
    except Exception:
        rows = []
        for heading, _header, rs in _iter_tables(text):
            if 'minimum requirements checklist' in heading.lower():
                rows.extend(rs)
        return rows


def _questions(spec_text):
    """Q items (checklist rows, then Optional Align rows of EVERY table under an `optional
    align` heading, each table with its own header), then D items (rows of every table under a
    heading starting `decisions` whose first token is a D code). Positional `Qn` unless the
    Question cell starts with an explicit `Qn`. Never raises. aidd:FR-301"""
    out = []
    try:
        text = _norm(spec_text)
        if not text.strip():
            return out
        rows = [r for r in _checklist_rows(text)]
        for heading, _header, rs in _iter_tables(text):
            if 'optional align' in heading.lower():
                rows.extend(rs)
        used, pos = set(), 0
        for r in rows:
            q, a, s = _cell(r, 0), _cell(r, 1), _cell(r, 2)
            if _blank(q):
                continue
            pos += 1
            qd = _display(q)
            m = _EXPLICIT_Q_RE.match(_plain(q))
            code = None
            if m and f'Q{int(m.group(1))}' not in used and 1 <= int(m.group(1)) <= 999:
                code = f'Q{int(m.group(1))}'
                qd = _display(_plain(q)[m.end():]) or qd
            if code is None:
                n = pos
                while f'Q{n}' in used and n < 999:
                    n += 1
                code = f'Q{n}'
            if code in used or not CODE_RE.fullmatch(code):
                continue
            used.add(code)
            out.append({'code': code, 'kind': 'question', 'question': qd, 'answer': _display(a),
                        'source': _display(s), 'unanswered': _blank_answer(a),
                        'canon': ' | '.join((_plain(q), _plain(a), _plain(s)))})
        for heading, header, rs in _iter_tables(text):
            if not heading.lower().startswith('decisions'):
                continue
            for cells in rs:
                tok = _first_token(_cell(cells, 0))
                if not _is_code(tok, ('D',)):
                    continue
                dci = _col(header, 'decision')
                sci = _col(header, 'source')
                dec = _cell(cells, dci if dci > 0 else 1)
                src = _cell(cells, sci if sci > 0 else 2)
                out.append({'code': tok, 'kind': 'decision', 'decision': _display(dec),
                            'source': _display(src), 'canon': _canon_row(cells)})
    except Exception:
        pass
    return out


def _ex_questions(src, warnings):
    text = src.get('spec.md')
    if not text:
        return []
    entries = [(q['code'], q) for q in _questions(text)]
    out = []
    for code, q in _unique('questions', entries, warnings):
        if q.get('kind') == 'decision':
            out.append(_item(code, 'decision', q.get('decision', ''), 'spec.md', q.get('canon', ''),
                             fields={'Source': _short(q.get('source', ''))}))
        else:
            out.append(_item(code, 'question', q.get('question', ''), 'spec.md', q.get('canon', ''),
                             fields={'Answer': _short(q.get('answer', '')),
                                     'Source': _short(q.get('source', ''))},
                             unanswered=q.get('unanswered', False)))
    return out


def _uncoded_warnings(src, warnings):
    """Rows of Acceptance cases / Decisions tables with no code of their kind: ONE warning per
    tab, never a synthetic code. aidd:FR-301"""
    text = src.get('spec.md')
    if not text:
        return
    groups = (('ac', 'acceptance cases', ('AC',), 'acceptance', 'an AC'),
              ('questions', 'decisions', ('D',), 'decision', 'a D'))
    tables = _iter_tables(text)
    for tab, head, prefixes, noun, art in groups:
        names = []
        for heading, _header, rows in tables:
            if not heading.lower().startswith(head):
                continue
            for cells in rows:
                first = _cell(cells, 0)
                tok = _first_token(first)
                if _blank(first) or _is_code(tok, prefixes) or PLACEHOLDER_RE.fullmatch(tok or ''):
                    continue
                if GENERIC_CODE_RE.fullmatch(tok or ''):
                    continue        # a malformed code: the completeness check names it
                names.append(_display(first))
        if names:
            n = len(names)
            warnings.append({'tab': tab, 'text': f'{n} {noun} row{"" if n == 1 else "s"} without '
                                                 f'{art} code {"is" if n == 1 else "are"} not reviewable: '
                                                 f'{_names(names, _WARN_NAME_CHARS, "; ")}'})


def _completeness(sources, items):
    """Independent count (own regex, own row scan): per source and prefix, the distinct coded
    first cells (GENERIC_CODE_RE, minus placeholders, field rows and untouched template rows)
    compared with the extracted codes of that source; any difference is a per-tab warning that
    names the skipped codes (`FR: 1 coded row skipped: FR-4.1`). Returns the warnings list.
    Never raises. aidd:FR-301"""
    out = []
    try:
        src = _norm_sources(sources)
        have = {}
        for it in (items.values() if isinstance(items, dict) else items or []):
            if isinstance(it, dict):
                have.setdefault(it.get('source'), set()).add(it.get('code'))
        for name, prefixes in _SOURCE_PREFIXES:
            text = src.get(name)
            if not text:
                continue
            found = {}
            header = None
            for cells in _iter_table_rows(text):
                tok = _first_token(_cell(cells, 0))
                m = GENERIC_CODE_RE.fullmatch(tok or '')
                if not m:
                    header = cells
                    continue
                pre = m.group(1)
                if pre not in prefixes or PLACEHOLDER_RE.fullmatch(tok) or FIELD_ROW_RE.fullmatch(tok):
                    continue
                if _is_template_row(pre, header, cells):
                    continue
                found.setdefault(pre, [])
                if tok not in found[pre]:
                    found[pre].append(tok)
            got = have.get(name, set())
            for pre in prefixes:
                missing = [t for t in found.get(pre, []) if t not in got]
                if missing:
                    n = len(missing)
                    out.append({'tab': _PREFIX_TAB[pre],
                                'text': f'{pre}: {_plural(n, "coded row")} skipped: '
                                        f'{_names(missing, _WARN_CODE_CHARS, ", ")}'})
    except Exception:
        pass
    return out


def _norm_sources(sources):
    """{name: text or None} from a dict or a list of (name, text) pairs."""
    out = {}
    try:
        pairs = sources.items() if isinstance(sources, dict) else list(sources or [])
        for name, text in pairs:
            if isinstance(text, bytes):
                text = text.decode('utf-8', errors='replace')
            out[str(name)] = text if isinstance(text, str) else None
    except Exception:
        pass
    return out


_EXTRACTORS = (
    ('questions', _ex_questions),
    ('fr', lambda s, w: _ex_rows('fr', s, w)),
    ('ac', lambda s, w: _ex_rows('ac', s, w)),
    ('screens', lambda s, w: _ex_rows('screens', s, w)),
    ('api', lambda s, w: _ex_rows('api', s, w)),
    ('tasks', _ex_tasks),
    ('verification', lambda s, w: _ex_rows('verification', s, w)),
)


def _extract_core(src, warnings):
    """{tab: [items]} for every tab but `summary`; each extractor wrapped."""
    tabs = {}
    for tab, fn in _EXTRACTORS:
        try:
            tabs[tab] = fn(src, warnings)
        except Exception as e:  # pragma: no cover - defensive
            tabs[tab] = []
            warnings.append({'tab': tab, 'text': f'{TAB_LABELS[tab]}: extraction failed '
                                                 f'({type(e).__name__}); items of this tab may be missing'})
    return tabs


def extract_items(sources):
    """aidd:FR-301 aidd:FR-311 aidd:FR-312. `sources` = {name: text-or-None}. Returns
    {'tabs': [{'id','label','items'}], 'items': {code: item}, 'order': ['SUMMARY', ...],
    'warnings': [{'tab','text'}]}. Never raises, never refuses (the MAX_ITEMS cap is the
    callers')."""
    warnings = []
    src = _norm_sources(sources)
    tabs = _extract_core(src, warnings)
    try:
        _uncoded_warnings(src, warnings)
    except Exception:  # pragma: no cover - defensive
        pass
    flat = {}
    for tab in TAB_ORDER:
        for it in tabs.get(tab, []):
            flat.setdefault(it['code'], it)
    warnings.extend(_completeness(src, flat))
    for name in _ITEM_SOURCES:
        text = src.get(name)
        if text and _norm(text).strip() and not any(it.get('source') == name for it in flat.values()):
            warnings.append({'tab': 'summary', 'text': f'{name}: the file has content but no '
                                                       f'reviewable item was found (0 items)'})
    try:
        summary = build_summary(src, {'items': flat})
    except Exception:  # pragma: no cover - defensive
        summary = _empty_summary()
    canon = json.dumps(summary, sort_keys=True, separators=(',', ':'))
    cost = summary.get('cost') or _cost_text(summary.get('minutes'), summary.get('tokens_k'))
    s_item = _item('SUMMARY', 'summary', summary.get('objective') or 'n/a', 'spec.md', canon,
                   fields={'Scope': _short(summary.get('scope', '')), 'Cost': _short(cost),
                           'Risks': _short(summary.get('risks', '')),
                           'Open decisions': _short('; '.join(summary.get('open_decisions') or []))},
                   mandatory=True)
    tabs['summary'] = [s_item]
    items = {'SUMMARY': s_item}
    order = ['SUMMARY']
    out_tabs = []
    for tab in TAB_ORDER:
        kept = []
        for it in tabs.get(tab, []):
            if it['code'] in items and tab != 'summary':
                continue
            items[it['code']] = it
            if tab != 'summary':
                order.append(it['code'])
            kept.append(it)
        if kept:
            out_tabs.append({'id': tab, 'label': TAB_LABELS[tab], 'items': kept})
    return {'tabs': out_tabs, 'items': items, 'order': order, 'warnings': warnings}


# --------------------------------------------------------------------------- summary (aidd:FR-302)

def _empty_summary():
    return {'objective': '', 'scope': '', 'cost': '', 'risks': '', 'open_decisions': [],
            'counts': {k: 0 for k in ('fr', 'ac', 'edge_ac', 'screens', 'comps', 'ctls', 'apis',
                                      'tasks', 'questions', 'unanswered')},
            'minutes': None, 'tokens_k': None, 'source': 'generated'}


def _cost_text(minutes, tokens_k):
    if minutes is None and tokens_k is None:
        return ''
    m = f'{minutes} min' if minutes is not None else 'n/a min'
    t = f'{tokens_k}k tokens' if tokens_k is not None else 'n/a tokens'
    return f'{m} / {t}'


def exec_summary_section(spec_text):
    """aidd:FR-302. The `## Executive summary` (or `## Resumen ejecutivo`) labelled bullets of
    spec.md -> {objective, scope, cost, risks, open_decisions[]} capped (MAX_SUMMARY_FIELD per
    field, MAX_SUMMARY in all); None when the section is absent or every field is empty.
    Never raises."""
    try:
        lines = []
        level, inside, fence = 0, False, False
        for line in _norm(spec_text).split('\n'):
            if _FENCE_OPEN_RE.match(line):
                fence = not fence
                if inside:
                    lines.append('')
                continue
            if fence:
                continue
            h = re.match(r'^ {0,3}(#{1,6})[ \t]+(.*?)[ \t#]*$', line)
            if h:
                if inside and len(h.group(1)) <= level:
                    break
                if not inside and _SUMMARY_HEADING_RE.match(_plain(h.group(2))):
                    inside, level = True, len(h.group(1))
                    continue
            if inside:
                lines.append(line)
        if not inside:
            return None
        fields, cur = {}, None
        for line in lines:
            b = _BULLET_RE.match(line)
            if b:
                body = b.group(1)
                lm = re.match(r'^\**\s*([^:*]{1,40}?)\s*\**\s*:\s*\**\s*(.*)$', body)
                cur = None
                if lm:
                    label = _plain(lm.group(1)).lower()
                    for key, names in _SUMMARY_LABELS:
                        if label in names:
                            cur = key
                            fields[key] = _display(lm.group(2))
                            break
                continue
            if cur and line.strip() and line[:1] in (' ', '\t'):
                fields[cur] = (fields[cur] + ' ' + _display(line)).strip()
            elif not line.strip():
                continue
            else:
                cur = None
        res = {'objective': '', 'scope': '', 'cost': '', 'risks': '', 'open_decisions': []}
        budget = MAX_SUMMARY
        for key, _names_ in _SUMMARY_LABELS:
            v = fields.get(key, '')
            v = _short(v, min(MAX_SUMMARY_FIELD, max(4, budget))) if v and budget > 3 else ''
            budget -= len(v)
            if key == 'open_decisions':
                res[key] = [v] if v else []
            else:
                res[key] = v
        if not any(res[k] for k in ('objective', 'scope', 'cost', 'risks')) and not res['open_decisions']:
            return None
        return res
    except Exception:
        return None


def _business_objective(spec_text):
    try:
        for r in _checklist_rows(_norm(spec_text)):
            if _plain(_cell(r, 0)).lower().startswith('business objective'):
                a = _cell(r, 1)
                return '' if _blank_answer(a) else _display(a)
    except Exception:
        pass
    return ''


def _visual_debt_open(spec_text):
    out = []
    try:
        for heading, header, rows in _iter_tables(spec_text):
            if not heading.lower().startswith('visual debt'):
                continue
            si = _col(header, 'status')
            for cells in rows:
                if si > 0 and _plain(_cell(cells, si)).lower() == 'open' and not _blank(_cell(cells, 0)):
                    out.append('Visual debt: ' + _display(_cell(cells, 0)))
    except Exception:
        pass
    return out


def _cap_list(values, limit=MAX_SUMMARY_FIELD):
    out, used = [], 0
    for i, v in enumerate(values):
        v = _short(v, 120)
        if used + len(v) + 2 > limit:
            out.append(f'+{len(values) - i} more')
            break
        out.append(v)
        used += len(v) + 2
    return out


def _plan_totals(tasks_text):
    try:
        res = _rules().plan_totals(tasks_text or '')
        return res.get('minutes'), res.get('tokens_k')
    except Exception:
        return None, None


def build_summary(sources, extracted=None):
    """aidd:FR-302. {objective, scope, cost, risks, open_decisions[], counts{...}, minutes,
    tokens_k, source}. The written `## Executive summary` when present and non-empty, else a
    mechanical one (`source: 'generated'`); the mechanical counts and plan totals are ALWAYS
    filled. Deterministic. Never raises."""
    res = _empty_summary()
    try:
        src = _norm_sources(sources)
        if isinstance(extracted, dict) and isinstance(extracted.get('items'), dict):
            items = [it for c, it in extracted['items'].items() if c != 'SUMMARY' and isinstance(it, dict)]
        else:
            core = _extract_core(src, [])
            items = [it for tab in core.values() for it in tab]
        kinds = {}
        for it in items:
            kinds.setdefault(it.get('kind'), []).append(it)
        c = res['counts']
        c['fr'] = len(kinds.get('fr', []))
        c['ac'] = len(kinds.get('ac', []))
        c['edge_ac'] = sum(1 for it in kinds.get('ac', []) if it.get('edge'))
        c['screens'] = len(kinds.get('screen', []))
        c['comps'] = len(kinds.get('comp', []))
        c['ctls'] = len(kinds.get('ctl', []))
        c['apis'] = len(kinds.get('api', []))
        c['tasks'] = len(kinds.get('task', []))
        c['questions'] = len(kinds.get('question', []))
        c['unanswered'] = sum(1 for it in kinds.get('question', []) if it.get('unanswered'))
        res['minutes'], res['tokens_k'] = _plan_totals(src.get('tasks.md'))
        spec = src.get('spec.md') or ''
        generated_open = _cap_list([it.get('text', '') for it in kinds.get('question', [])
                                    if it.get('unanswered')] + _visual_debt_open(spec))
        written = exec_summary_section(spec)
        if written:
            res.update({k: written[k] for k in ('objective', 'scope', 'cost', 'risks', 'open_decisions')})
            res['source'] = 'spec.md#executive-summary'
            if not res['objective']:
                res['objective'] = _short(_business_objective(spec), MAX_SUMMARY_FIELD)
            if not res['cost']:
                res['cost'] = _cost_text(res['minutes'], res['tokens_k'])
        else:
            res['objective'] = _short(_business_objective(spec), MAX_SUMMARY_FIELD)
            res['cost'] = _cost_text(res['minutes'], res['tokens_k'])
            res['open_decisions'] = generated_open
            res['source'] = 'generated'
    except Exception:  # pragma: no cover - defensive
        pass
    return res


# --------------------------------------------------------------------------- digests (aidd:FR-312)

def item_digest(item):
    """aidd:FR-312. sha1(kind + '\\x1f' + code + '\\x1f' + canon).hexdigest()[:8]; canon is the
    FULL source row (before the 240-char cut). Never raises."""
    try:
        it = item if isinstance(item, dict) else {}
        raw = '\x1f'.join(str(it.get(k) if it.get(k) is not None else '') for k in ('kind', 'code', 'canon'))
        return hashlib.sha1(raw.encode('utf-8', errors='replace')).hexdigest()[:8]
    except Exception:
        return hashlib.sha1(b'').hexdigest()[:8]


def carry_decision(prev_lines, prev_blob_digests, new_digests, order):
    """aidd:FR-312, the carry-over RULE. A code keeps its previous approved/comment only when
    prev_lines[code]['digest'] == new_digests[code] == prev_blob_digests[code] (all three
    present). Returns (prior, carry). Never raises (any error = nothing carried)."""
    try:
        codes = list(order or [])
    except Exception:
        codes = []
    try:
        prev_lines = prev_lines if isinstance(prev_lines, dict) else {}
        blob = prev_blob_digests if isinstance(prev_blob_digests, dict) else {}
        new = new_digests if isinstance(new_digests, dict) else {}
        prior, pending = {}, []
        for code in codes:
            entry = prev_lines.get(code)
            ok = False
            if isinstance(entry, dict) and all(k in entry for k in ('approved', 'comment', 'digest')):
                d_line, d_new, d_blob = entry.get('digest'), new.get(code), blob.get(code)
                ok = (isinstance(d_line, str) and isinstance(d_new, str) and isinstance(d_blob, str)
                      and bool(d_line) and d_line == d_new == d_blob)
            if ok:
                prior[code] = {'approved': bool(entry.get('approved')),
                               'comment': str(entry.get('comment') or '')}
            else:
                pending.append(code)
        return prior, {'carried': len(prior), 'total': len(codes), 'pending': pending}
    except Exception:
        return {}, {'carried': 0, 'total': len(codes), 'pending': list(codes)}


# --------------------------------------------------------------------------- tasks facts (aidd:FR-313)

def target_files(tasks_text):
    """aidd:FR-313. Distinct paths of the Target file column of the tasks.md task table,
    first-seen order (cells split on `;`, `,` and ` + `, backticks stripped, blanks dropped);
    [] when there is no such column. Never raises."""
    out = []
    try:
        for _heading, header, rows in _iter_tables(tasks_text):
            ti = _col(header, 'target file')
            if ti < 0:
                continue
            for cells in rows:
                if not _is_code(_first_token(_cell(cells, 0)), ('T',)):
                    continue
                for part in re.split(r';|,| \+ ', _cell(cells, ti)):
                    p = ' '.join(part.replace('`', '').split())
                    if p and not _blank(p) and p not in out:
                        out.append(p)
    except Exception:
        pass
    return out


def wave_count(tasks_text):
    """aidd:FR-313. Number of data rows of the `## Waves` table; 0 when absent. Never raises."""
    try:
        for heading, _header, rows in _iter_tables(tasks_text):
            if heading.lower().startswith('waves'):
                return sum(1 for r in rows if any(not _blank(c) for c in r))
    except Exception:
        pass
    return 0
