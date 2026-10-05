#!/usr/bin/env python3
"""
aidd review — generate the self-contained `review.html` of a spec and read back the owner's
`review.md` (spec 007 FR-202..FR-204; spec 008 FR-301, FR-303, FR-304, FR-306, FR-309, FR-312,
FR-313).

    aidd_review.py <spec_dir>              generate the compact page specs/<id>/review.html
    aidd_review.py <spec_dir> --full       generate the long 007 page (heading keys) instead
    aidd_review.py <spec_dir> --open       generate (if needed) and open it in the browser
    aidd_review.py <spec_dir> --check      print ONE status line, exit 0 complete / 2 pending /
                                           3 stale, legacy or too many items
    aidd_review.py <spec_dir> --wait       poll silently, then print ONE status line (exit 0
                                           complete / 2 timeout / 3 waiting cannot help)
                                           [--timeout S] [--interval S]
    aidd_review.py <spec_dir> --comments   print `<CODE>: <comment>` for commented codes only
    aidd_review.py <spec_dir> --summary    print the mechanical summary (at most 30 lines)

This file is the facade (aidd:FR-301 aidd:FR-303): IO, the page, `--full`, `--wait` and the CLI.
The logic lives in two pure modules next to it, reached ONLY through `_items()` and `_state()`
(lazy, never at import time; an ImportError fails closed):
- aidd_review_items.py: source markdown -> items, digests, carry-over rule, summary data;
- aidd_review_state.py: review.md grammar -> state, status line, exits, summary text.

Design rules (aidd:FR-202):
- zero LLM tokens; stdlib only; importable alone (`aidd_rules` and the two modules above are
  imported lazily);
- the markdown renderer escapes FIRST and emits a fixed tag set: no raw HTML, never a `style=`
  or `on*=` attribute, every href/src goes through `safe_url`;
- fail closed: a source over MAX_REVIEW_SOURCE_CHARS is refused, never truncated; tasks.md is
  mandatory;
- review state is CONTENT only (aidd:FR-204): nothing in this module approves anything. The
  approval needs a human consent act checked by the callers (`prompt_consent` is one of them).
  `--check`, `--wait`, `--comments` and `--summary` are read-only (aidd:FR-309).
"""
import argparse
import base64
import hashlib
import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
from pathlib import Path

SOURCES = ('spec.md', 'plan.md', 'tasks.md', 'mockup-audit.md', 'contracts.md')
MAX_REVIEW_SOURCE_CHARS = 400_000
REVIEW_HTML = 'review.html'
REVIEW_MD = 'review.md'
TEMPLATE_COMPACT = 'review.html'
TEMPLATE_FULL = 'review-full.html'
TEMPLATE_TOKENS = ('{{TITLE}}', '{{SPEC_ID}}', '{{TASKS_HASH}}', '{{TASKS_HASH8}}',
                   '{{SOURCES_DIGEST}}', '{{GENERATED}}', '{{BODY}}', '{{DATA_JSON}}',
                   '{{SCRIPT_SHA256}}')
# Same values as aidd_review_state.FORMAT_COMPACT / FORMAT_FULL (aidd:FR-304); kept here so that
# reading a page blob never needs the state module (TestRealModules asserts they are equal).
_FMT_COMPACT = 'codes-v2'
_FMT_FULL = 'headings-v1'
# tab id -> the ONE source file its link may point to (always a member of SOURCES; aidd:FR-303)
_TAB_SOURCE = {'summary': 'spec.md', 'questions': 'spec.md', 'fr': 'spec.md', 'ac': 'spec.md',
               'screens': 'mockup-audit.md', 'api': 'contracts.md', 'tasks': 'tasks.md',
               'verification': 'spec.md'}
_SPLIT_REASON = ('aidd_review_items/aidd_review_state is not importable next to aidd_review.py '
                 '(reinstall AIDD)')

_HEADING_RE = re.compile(r'^ {0,3}(#{1,4})[ \t]+(.+?)[ \t]*$')
_HEADING_EMPTY_RE = re.compile(r'^ {0,3}(#{1,4})[ \t]*$')
_FENCE_RE = re.compile(r'^ {0,3}(`{3,}|~{3,})(.*)$')
_HR_RE = re.compile(r'^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$')
_LIST_RE = re.compile(r'^([ \t]*)([-*+]|\d{1,9}[.)])[ \t]+(.*)$')
_TASKBOX_RE = re.compile(r'^\[( |x|X)\][ \t]+(.*)$')
_QUOTE_RE = re.compile(r'^ {0,3}&gt; ?(.*)$')      # applied to the ESCAPED line
_TOKEN_RE = re.compile('|'.join(re.escape(t) for t in TEMPLATE_TOKENS))
_SCRIPT_RE = re.compile(r'<script\b[^>]*\bid="aidd-js"[^>]*>(.*?)</script>', re.S | re.I)
_DATA_RE = re.compile(r'<script\b[^>]*\bid="aidd-data"[^>]*>(.*?)</script>', re.S | re.I)
_HEX8_RE = re.compile(r'[0-9a-f]{8}', re.ASCII)
_APPROVE_WORD_RE = re.compile(r'\b(approve|approved|aprobar|aprobado|apruebo)\b')
_NEGATION_RE = re.compile(r"\b(not|no|don'?t|do not|never|nunca|reject|rechaz\w*)\b")
_PH = '\x00'          # inline placeholder delimiter (NUL is stripped from the input first)


# ---------------------------------------------------------------------------
# The two review modules (lazy; aidd:FR-301 module split)
# ---------------------------------------------------------------------------

def _script_dir_on_path():
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)


def _items():
    """aidd_review_items from this script's own directory, imported lazily (never at import
    time). ImportError propagates: every caller fails closed (reason `_SPLIT_REASON`, exit 3)."""
    _script_dir_on_path()
    import aidd_review_items  # noqa: E402
    return aidd_review_items


def _state():
    """aidd_review_state, same rules as `_items()`."""
    _script_dir_on_path()
    import aidd_review_state  # noqa: E402
    return aidd_review_state



# ---------------------------------------------------------------------------
# Rules library (lazy) and source loading
# ---------------------------------------------------------------------------

def _rules():
    """aidd_rules from this script's own directory; imported lazily so this module stays
    importable alone. Raises ImportError when it is missing (callers fail closed)."""
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    import aidd_rules  # noqa: E402
    return aidd_rules


def _read_text(p):
    """Same reading as aidd_status/aidd_rules (`utf-8`, errors replaced) so hashes agree."""
    return Path(p).read_text(encoding='utf-8', errors='replace')


def _load_sources(spec_dir):
    """[(name, text or None)] in SOURCES order. An unreadable file counts as absent."""
    out = []
    d = Path(spec_dir)
    for name in SOURCES:
        p = d / name
        text = None
        try:
            if p.is_file():
                text = _read_text(p)
        except OSError:
            text = None
        out.append((name, text))
    return out


def _oversize(sources):
    """[(name, chars)] of the sources over MAX_REVIEW_SOURCE_CHARS (aidd:FR-202 fail closed)."""
    return [(n, len(t)) for n, t in sources if t is not None and len(t) > MAX_REVIEW_SOURCE_CHARS]


def _stem(source):
    name = Path(str(source)).name
    return name[:-3] if name.lower().endswith('.md') else name


def _spec_root(spec_dir):
    """Project root of `specs/<id>` (None when the folder is not under a `specs/` dir)."""
    d = Path(spec_dir)
    return d.parent.parent if d.parent.name.lower() == 'specs' else None


# ---------------------------------------------------------------------------
# Headings and keys (aidd:FR-202)
# ---------------------------------------------------------------------------

def slugify(text):
    """NFKD strip accents, lowercase, `[^a-z0-9]+` -> `-`, trim `-`, empty -> `section`."""
    s = unicodedata.normalize('NFKD', str(text or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s or 'section'


def _heading_text(raw):
    """Heading text without an optional closing `#` sequence."""
    t = re.sub(r'[ \t]+#+[ \t]*$', '', raw)
    return '' if re.fullmatch(r'#+', t) else t.strip()


def _iter_headings(md):
    """Yield (level, text, line_no 1-based) for ATX headings level 1-4 outside fenced code."""
    fence = None
    text = str(md or '')
    if text.startswith('﻿'):
        text = text[1:]
    for i, line in enumerate(text.replace('\r\n', '\n').replace('\r', '\n').split('\n'), 1):
        m = _FENCE_RE.match(line)
        if fence is not None:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not m.group(2).strip():
                fence = None
            continue
        if m and not (m.group(1)[0] == '`' and '`' in m.group(2)):
            fence = m.group(1)
            continue
        h = _HEADING_RE.match(line)
        if h:
            yield len(h.group(1)), _heading_text(h.group(2)), i
        elif _HEADING_EMPTY_RE.match(line):
            yield len(_HEADING_EMPTY_RE.match(line).group(1)), '', i


def parse_headings(md, source):
    """[(key, level, text, line_no)] for ATX headings level 1-4 outside fenced code;
    key = '<source-stem>/<slug>', duplicates in one file get -2, -3. Levels 2-3 are reviewable."""
    stem = _stem(source)
    used = {}
    taken = set()
    out = []
    for level, text, line_no in _iter_headings(md):
        base = slugify(text)
        n = used.get(base, 0)
        while True:
            n += 1
            key = f'{stem}/{base}' if n == 1 else f'{stem}/{base}-{n}'
            if key not in taken:
                break
        used[base] = n
        taken.add(key)
        out.append((key, level, text, line_no))
    return out


def _reviewable(headings):
    return [h for h in headings if h[1] in (2, 3)]


def _keys_of(sources):
    keys = []
    for name, text in sources:
        if text is not None:
            keys += [h[0] for h in _reviewable(parse_headings(text, name))]
    return keys



def reviewable_keys(spec_dir, full=False):
    """The reviewable keys of a spec, in item order. aidd:FR-301 aidd:FR-304
    Compact (default): the codes of `aidd_review_items.extract_items` (`SUMMARY` first).
    `full=True`: the 007 heading keys (levels 2-3 over all present sources, same text as rendered).
    ImportError of aidd_review_items propagates (callers fail closed)."""
    sources = _load_sources(spec_dir)
    if full:
        return _keys_of(sources)
    return list(_items().extract_items(dict(sources)).get('order') or [])



def _is_mandatory(source, level, text):
    """spec.md `## Verification` is checked on its own (aidd:FR-202, AC-218)."""
    return _stem(source).lower() == 'spec' and level == 2 and text.strip().lower() == 'verification'


# ---------------------------------------------------------------------------
# URL allow-list (aidd:FR-202, AC-204)
# ---------------------------------------------------------------------------

def _has_dotdot(u):
    return any(seg == '..' for seg in re.split(r'[/?#]', u))


def safe_url(url, image=False):
    """The URL, or None when it is not on the allow-list (see module docstring and FR-202).

    Rejected: any char < 0x20, DEL, whitespace or a backslash; a leading `/`; a `:` before the
    first `/`, `?` or `#` unless the scheme is http/https and `image` is False; a `..` segment
    (raw and after percent-decoding twice); an HTML character reference (`&#106;`, `&colon;`),
    so a decoded attribute can never differ from the checked text."""
    try:
        if not isinstance(url, str) or not url:
            return None
        for c in url:
            if ord(c) < 0x20 or ord(c) == 0x7f or c.isspace() or c == '\\':
                return None
        if url.startswith('/'):
            return None
        if html.unescape(url) != url:
            return None
        cut = len(url)
        for sep in '/?#':
            j = url.find(sep)
            if j != -1:
                cut = min(cut, j)
        colon = url.find(':')
        if colon != -1 and colon < cut:
            if image or url[:colon].lower() not in ('http', 'https'):
                return None
        once = urllib.parse.unquote(url)
        twice = urllib.parse.unquote(once)
        if _has_dotdot(url) or _has_dotdot(once) or _has_dotdot(twice):
            return None
        if '\\' in once or '\\' in twice:
            return None
        return url
    except Exception:  # noqa: BLE001 — a URL we cannot judge is not a link
        return None


# ---------------------------------------------------------------------------
# Markdown renderer: escape first, fixed tag set (aidd:FR-202)
# ---------------------------------------------------------------------------

def _esc(s):
    return html.escape(str(s), quote=True)


class _Inline:
    """Inline transforms on an ALREADY ESCAPED line. Produced tags are parked behind NUL
    placeholders so later passes never re-read them."""

    _CODE = re.compile(r'(`+)(.+?)\1')
    _IMG = re.compile(r'!\[([^\]\x00]*)\]\(([^)\x00]*)\)')
    _LINK = re.compile(r'\[([^\]\x00]*)\]\(([^)\x00]*)\)')
    _STRONG = re.compile(r'\*\*(?=\S)(.+?)(?<=\S)\*\*')
    _EM = re.compile(r'(?<![\w*])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![\w*])')
    _SLOT = re.compile(_PH + r'(\d+)' + _PH)

    def __init__(self):
        self.slots = []

    def _park(self, s):
        self.slots.append(s)
        return f'{_PH}{len(self.slots) - 1}{_PH}'

    def _url(self, escaped_url, image):
        raw = html.unescape(escaped_url)
        return safe_url(raw, image=image)

    def _img(self, m):
        u = self._url(m.group(2), True)
        if u is None:
            return self._park(m.group(0))
        alt = self._SLOT.sub('', m.group(1))     # no parked tag ever lands inside an attribute
        return self._park(f'<img src="{_esc(u)}" alt="{alt}" loading="lazy">')

    def _link(self, m):
        u = self._url(m.group(2), False)
        if u is None:
            return self._park(m.group(0))
        return self._park(f'<a href="{_esc(u)}" rel="noopener noreferrer" target="_blank">'
                          f'{m.group(1)}</a>')

    def render(self, escaped):
        s = self._CODE.sub(lambda m: self._park(f'<code>{m.group(2)}</code>'), escaped)
        s = self._IMG.sub(self._img, s)
        s = self._LINK.sub(self._link, s)
        s = self._STRONG.sub(r'<strong>\1</strong>', s)
        s = self._EM.sub(r'<em>\1</em>', s)
        for _ in range(8):                      # nested slots (code inside link text)
            if _PH not in s:
                break
            s = self._SLOT.sub(lambda m: self.slots[int(m.group(1))], s)
        return s.replace(_PH, '')


def _inline(escaped):
    return _Inline().render(escaped)


def _split_cells(escaped_row):
    """Cells of an escaped table row; `|` inside inline code or escaped as `\\|` stays."""
    s = escaped_row.strip()
    if s.startswith('|'):
        s = s[1:]
    if s.endswith('|') and not s.endswith('\\|'):
        s = s[:-1]
    cells, cur, tick = [], [], 0
    i = 0
    while i < len(s):
        c = s[i]
        if c == '\\' and i + 1 < len(s) and s[i + 1] == '|':
            cur.append('|')
            i += 2
            continue
        if c == '`':
            tick ^= 1
        if c == '|' and not tick:
            cells.append(''.join(cur).strip())
            cur = []
        else:
            cur.append(c)
        i += 1
    cells.append(''.join(cur).strip())
    return cells


def _starts_block(line):
    """A heading or a fence always starts a new block, so the rendered keys and fences match
    `parse_headings` exactly (a list never swallows them as a continuation line)."""
    return bool(_HEADING_RE.match(line) or _HEADING_EMPTY_RE.match(line) or _FENCE_RE.match(line))


def _is_sep_row(cells):
    return bool(cells) and all(re.fullmatch(r':?-{1,}:?', c.replace(' ', '')) for c in cells)


class _Renderer:
    """Block renderer over raw markdown lines. Every raw line is html-escaped before any
    pattern sees it; only fixed tags with fixed attribute names are produced."""

    def __init__(self, source, headings, sections=True):
        self.source = source
        self.sections = sections
        # (level, text) -> queue of keys in document order, to match parse_headings exactly
        self.heads = list(headings or [])
        self.hidx = 0
        self.out = []
        self.in_section = False

    def _next_heading(self, line_no):
        while self.hidx < len(self.heads) and self.heads[self.hidx][3] < line_no:
            self.hidx += 1
        if self.hidx < len(self.heads) and self.heads[self.hidx][3] == line_no:
            h = self.heads[self.hidx]
            self.hidx += 1
            return h
        return None

    def _close_section(self):
        if self.in_section:
            self.out.append('</section>')
            self.in_section = False

    def render(self, lines, offset=0):
        i = 0
        n = len(lines)
        para = []

        def flush():
            if para:
                self.out.append('<p>' + '<br>\n'.join(_inline(_esc(x.strip())) for x in para) + '</p>')
                para.clear()

        while i < n:
            raw = lines[i]
            line_no = offset + i + 1
            fm = _FENCE_RE.match(raw)
            if fm and not (fm.group(1)[0] == '`' and '`' in fm.group(2)):
                flush()
                fence = fm.group(1)
                lang = re.sub(r'[^a-z0-9_-]', '', fm.group(2).strip().split(' ')[0].lower())[:32]
                body = []
                i += 1
                while i < n:
                    m2 = _FENCE_RE.match(lines[i])
                    if m2 and m2.group(1)[0] == fence[0] and len(m2.group(1)) >= len(fence) \
                            and not m2.group(2).strip():
                        i += 1
                        break
                    body.append(lines[i])
                    i += 1
                cls = f' class="lang-{lang}"' if lang else ''
                self.out.append(f'<pre><code{cls}>' + _esc('\n'.join(body)) + '</code></pre>')
                continue
            hm = _HEADING_RE.match(raw) or _HEADING_EMPTY_RE.match(raw)
            if hm:
                flush()
                level = len(hm.group(1))
                text = _heading_text(hm.group(2)) if hm.re is _HEADING_RE else ''
                h = self._next_heading(line_no) if self.sections else None
                if self.sections and level <= 3:
                    self._close_section()
                if h is not None and level in (2, 3):
                    mand = _is_mandatory(self.source, level, text)
                    cls = 'aidd-section mandatory' if mand else 'aidd-section'
                    extra = ' data-mandatory="1"' if mand else ''
                    self.out.append(f'<section class="{cls}" data-key="{_esc(h[0])}" '
                                    f'data-source="{_esc(_stem(self.source))}" '
                                    f'data-level="{level}"{extra}>')
                    self.in_section = True
                self.out.append(f'<h{level}>{_inline(_esc(text))}</h{level}>')
                i += 1
                continue
            if not raw.strip():
                flush()
                i += 1
                continue
            if _HR_RE.match(raw):
                flush()
                self.out.append('<hr>')
                i += 1
                continue
            esc_line = _esc(raw)
            if _QUOTE_RE.match(esc_line):
                flush()
                inner = []
                while i < n and lines[i].strip() and _QUOTE_RE.match(_esc(lines[i])):
                    inner.append(html.unescape(_QUOTE_RE.match(_esc(lines[i])).group(1)))
                    i += 1
                sub = _Renderer(self.source, None, sections=False)
                sub.render(inner)
                self.out.append('<blockquote>' + '\n'.join(sub.out) + '</blockquote>')
                continue
            if raw.lstrip().startswith('|') and i + 1 < n and lines[i + 1].lstrip().startswith('|') \
                    and _is_sep_row(_split_cells(_esc(lines[i + 1]))):
                flush()
                head = _split_cells(esc_line)
                rows = []
                i += 2
                while i < n and lines[i].lstrip().startswith('|'):
                    rows.append(_split_cells(_esc(lines[i])))
                    i += 1
                t = ['<div class="aidd-table"><table><thead><tr>']
                t += [f'<th>{_inline(c)}</th>' for c in head]
                t.append('</tr></thead><tbody>')
                for r in rows:
                    t.append('<tr>' + ''.join(f'<td>{_inline(c)}</td>' for c in r) + '</tr>')
                t.append('</tbody></table></div>')
                self.out.append(''.join(t))
                continue
            if _LIST_RE.match(raw):
                flush()
                items = []
                while i < n and lines[i].strip() and not _starts_block(lines[i]) \
                        and (_LIST_RE.match(lines[i]) or (items and lines[i][:1] in ' \t')):
                    lm = _LIST_RE.match(lines[i])
                    if lm:
                        indent = len(lm.group(1).expandtabs(4))
                        items.append([indent, lm.group(2)[-1] in '.)', lm.group(3)])
                    else:
                        items[-1][2] += ' ' + lines[i].strip()
                    i += 1
                self.out.append(self._list(items))
                continue
            para.append(raw)
            i += 1
        flush()

    def _item(self, text):
        tm = _TASKBOX_RE.match(text)
        if tm:
            checked = ' checked' if tm.group(1) in 'xX' else ''
            return f'<input type="checkbox" disabled{checked}> ' + _inline(_esc(tm.group(2)))
        return _inline(_esc(text))

    def _list(self, items):
        """Nested lists from (indent, ordered, text) items with a stack of open lists."""
        out = []
        stack = []                              # [(indent, tag)]
        for indent, ordered, text in items:
            tag = 'ol' if ordered else 'ul'
            while stack and indent < stack[-1][0]:
                out.append(f'</li></{stack.pop()[1]}>')
            if not stack or indent > stack[-1][0]:
                out.append(f'<{tag}><li>')
                stack.append((indent, tag))
            else:
                out.append('</li><li>')
            out.append(self._item(text))
        while stack:
            out.append(f'</li></{stack.pop()[1]}>')
        return ''.join(out)


def render_markdown(md, source, keys, base_dir):
    """HTML of one source. `keys` is the `parse_headings(md, source)` list (computed when None)
    so the rendered `data-key`s are exactly the reviewable keys. Relative links and images
    resolve next to the page, which lives in the spec folder (`base_dir`, informational)."""
    # NUL is the inline placeholder; other C0 controls and DEL never reach the page raw
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '�', str(md or ''))
    if text.startswith('﻿'):
        text = text[1:]
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    heads = keys if keys is not None else parse_headings(md, source)
    r = _Renderer(source, heads, sections=True)
    r.render(lines)
    r._close_section()
    return '\n'.join(r.out)


# ---------------------------------------------------------------------------
# Digest, template, page (aidd:FR-202, FR-203)
# ---------------------------------------------------------------------------

def _digest_of(sources):
    rules = _rules()
    h = hashlib.sha1()
    for name, text in sources:
        if text is None:
            continue
        if name == 'tasks.md':
            content = rules.approval_hash(text).encode('utf-8')
        else:
            content = text.replace('\r\n', '\n').replace('\r', '\n').encode('utf-8', 'replace')
        h.update(name.encode('utf-8') + b'\0' + content + b'\0')
    return h.hexdigest()[:12]


def sources_digest(spec_dir):
    """sha1[:12] over `name\\0content` of the present sources; tasks.md contributes its
    `approval_hash` (Approved line and Status/Tracker/PR-ref cells are neutral), the others
    their CRLF-normalised UTF-8 bytes. Raises ImportError if aidd_rules is missing."""
    return _digest_of(_load_sources(spec_dir))


def _script_sha256(template):
    found = _SCRIPT_RE.findall(template)
    if len(found) != 1:
        raise ValueError('review template must contain exactly one <script id="aidd-js">')
    if '{{' in found[0]:
        raise ValueError('review template script must be constant (no {{TOKEN}} inside it)')
    return base64.b64encode(hashlib.sha256(found[0].encode('utf-8')).digest()).decode('ascii')


def _json_blob(data):
    s = json.dumps(data, ensure_ascii=True)
    return s.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


def _verification_problems(spec_dir, spec_text):
    """`check_verification` messages for spec.md ([] when the lint is unavailable)."""
    if spec_text is None:
        return []
    try:
        fn = getattr(_rules(), 'check_verification', None)
        if fn is None:
            return []
        out = []
        for v in fn(spec_text, _spec_root(spec_dir)) or []:
            msg = str(v.get('message', '')) if isinstance(v, dict) else str(v)
            fix = str(v.get('fix', '')) if isinstance(v, dict) else ''
            out.append(msg + (f' Fix: {fix}' if fix else ''))
        return out
    except Exception:  # noqa: BLE001 — lint is advisory on the page; approval re-checks it
        return []



def _template_path(full=False):
    """templates/review.html (compact) or templates/review-full.html (`--full`). aidd:FR-303"""
    name = TEMPLATE_FULL if full else TEMPLATE_COMPACT
    return Path(__file__).resolve().parent.parent / 'templates' / name


def _load_template(template_text, full):
    if template_text is not None:
        return template_text
    p = _template_path(full)
    try:
        return _read_text(p)
    except OSError as e:
        raise ValueError(f'review template not readable: {p} ({e})') from e


def _picker_id(spec_id):
    """aidd:FR-305 `'aidd-' + sha1(spec_id)[:8]`: always 13 chars of [a-z0-9-] (the File System
    Access picker id is limited to 32)."""
    return 'aidd-' + hashlib.sha1(str(spec_id).encode('utf-8', 'replace')).hexdigest()[:8]


def _too_many(n, cap):
    """The over-cap sentence (aidd:FR-301); consumers match its `too many items` prefix."""
    return f'too many items ({n} > {cap}): split the spec or run aidd review <spec> --full'


def _checked_texts(d, sources):
    """dict of the sources after the 007 refusals (oversize, no tasks.md): ValueError, never a
    truncation (aidd:FR-202 fail closed)."""
    big = _oversize(sources)
    if big:
        raise ValueError(f'{big[0][0]} is {big[0][1]} chars (limit {MAX_REVIEW_SOURCE_CHARS}): split the spec')
    texts = dict(sources)
    if texts.get('tasks.md') is None:
        raise ValueError(f'tasks.md not found in {d}: nothing to review')
    return texts


def _problems_html(problems):
    if not problems:
        return ''
    return ('<div class="aidd-warning" role="alert"><strong>Verification problems '
            '(approval will be refused until fixed)</strong><ul>'
            + ''.join(f'<li>{_esc(p)}</li>' for p in problems) + '</ul></div>')


def _one(value, n=400):
    """One line of page text: whitespace collapsed, cut at n (the generator's own cap)."""
    s = re.sub(r'\s+', ' ', str(value if value is not None else '')).strip()
    return s if len(s) <= n else s[:n - 3] + '...'


# ---------------------------------------------------------------------------
# --full page: the unchanged 007 heading renderer (aidd:FR-303, AC-311)
# ---------------------------------------------------------------------------

def _full_page(d, sources, prior, problems):
    """(body, blob fields) of the long 007 page; heading keys, `format: headings-v1`."""
    body = [_problems_html(problems)] if problems else []
    keys = []
    for name, text in sources:
        stem = _stem(name)
        if text is None:
            body.append(f'<article class="aidd-source absent" data-source="{_esc(stem)}">'
                        f'<div class="aidd-source-title">{_esc(name)}</div>'
                        f'<p class="aidd-absent">{_esc(name)}: absent</p></article>')
            continue
        heads = parse_headings(text, name)
        for key, level, htext, _line in _reviewable(heads):
            keys.append({'key': key, 'source': stem, 'level': level, 'text': htext,
                         'mandatory': _is_mandatory(name, level, htext)})
        body.append(f'<article class="aidd-source" data-source="{_esc(stem)}" id="src-{_esc(stem)}">'
                    f'<div class="aidd-source-title">{_esc(name)}</div>\n'
                    + render_markdown(text, name, heads, d) + '\n</article>')
    pr = prior if isinstance(prior, dict) else {}
    data = {
        'format': _FMT_FULL,
        'keys': keys,
        'sources': [{'name': n, 'present': t is not None} for n, t in sources],
        # flat {key: {approved, comment}} as read by the page JS (`prior[key]`)
        'prior': pr.get('sections') if isinstance(pr.get('sections'), dict) else {},
        'prior_approved': bool(pr.get('approved')),
        'verification_problems': problems,
    }
    return '\n'.join(body), data


# ---------------------------------------------------------------------------
# Compact page (aidd:FR-303, FR-312): tabs of coded items, no markdown embedded
# ---------------------------------------------------------------------------

_BLOB_ITEM_KEYS = ('code', 'kind', 'text', 'fields', 'edge', 'unanswered', 'mandatory', 'source')


def _tab_items(tab, items):
    """The item dicts of one tab (entries may be dicts or codes looked up in `items`)."""
    out = []
    for it in tab.get('items') or []:
        if isinstance(it, str):
            it = items.get(it)
        if isinstance(it, dict) and isinstance(it.get('code'), str):
            out.append(it)
    return out


def _blob_item(item):
    """The page view of an item: never `canon` (aidd:FR-312: the digest input stays server side)."""
    out = {k: item.get(k) for k in _BLOB_ITEM_KEYS}
    out['fields'] = out['fields'] if isinstance(out['fields'], dict) else {}
    for k in ('edge', 'unanswered', 'mandatory'):
        out[k] = bool(out[k])
    return out


def _item_html(item):
    """`<div class="aidd-item" data-code=...>` with .code/.txt and optional .ans/.fld/.src, every
    value escaped by the generator (the page JS never uses innerHTML with data)."""
    code = str(item.get('code', ''))
    attrs = f' data-code="{_esc(code)}"'
    if item.get('edge'):
        attrs += ' data-edge="1"'
    if item.get('unanswered'):
        attrs += ' data-unanswered="1"'
    if item.get('mandatory'):
        attrs += ' data-mandatory="1"'
    parts = [f'<span class="code">{_esc(code)}</span>',
             f'<span class="txt">{_esc(_one(item.get("text", "")))}</span>']
    fields = item.get('fields') if isinstance(item.get('fields'), dict) else {}
    # the extractor emits `Answer`/`Source` (capitalised): look the answer up case-insensitively
    low = {str(k).lower(): v for k, v in fields.items()}
    ans = low.get('answer') or low.get('decision')
    if item.get('unanswered'):
        # aidd:AC-305 — an unanswered question shows the pending cue, never a blank answer
        ans = 'pending - resolve in Align'
    if ans:
        parts.append(f'<span class="ans">{_esc(_one(ans))}</span>')
    for k, v in fields.items():
        if str(k).lower() in ('answer', 'decision', 'question') or v in (None, '', [], {}):
            continue
        parts.append(f'<span class="fld" data-field="{_esc(k)}">{_esc(k)}: {_esc(_one(v))}</span>')
    if item.get('source'):
        parts.append(f'<span class="src">{_esc(_one(item.get("source")))}</span>')
    return f'<div class="aidd-item"{attrs}>' + ''.join(parts) + '</div>'


def _norm_warnings(raw):
    out = []
    for w in raw or []:
        if isinstance(w, dict) and w.get('text'):
            out.append({'tab': str(w.get('tab') or ''), 'text': _one(w.get('text'), 600)})
    return out


def _compact_body(tabs, items, warnings, texts, problems):
    """Tab panels in generator order; each warning at the top of its tab, warnings of no tab or of
    a dropped tab (and the total count) on Resumen; one link per tab to its fixed source."""
    ids = [str(t.get('id')) for t in tabs]
    home = 'summary' if 'summary' in ids else (ids[0] if ids else '')
    by_tab = {}
    for w in warnings:
        by_tab.setdefault(w['tab'] if w['tab'] in ids else home, []).append(w['text'])
    out = [_problems_html(problems)] if problems else []
    for tab in tabs:
        tid = str(tab.get('id'))
        label = str(tab.get('label') or tid)
        out.append(f'<section role="tabpanel" id="tab-{_esc(tid)}" data-tab="{_esc(tid)}" '
                   f'aria-label="{_esc(label)}">')
        lines = list(by_tab.get(tid, []))
        if tid == home and warnings:
            lines.append(f'{len(warnings)} warning(s) in total')
        if lines:
            out.append('<ul class="aidd-warn" role="status">'
                       + ''.join(f'<li>{_esc(x)}</li>' for x in lines) + '</ul>')
        src = _TAB_SOURCE.get(tid)
        if src in SOURCES and texts.get(src) is not None and safe_url(src):
            out.append(f'<p class="aidd-srclink"><a href="{_esc(src)}" rel="noopener noreferrer" '
                       f'target="_blank">{_esc(src)}</a></p>')
        out += [_item_html(it) for it in _tab_items(tab, items)]
        out.append('</section>')
    return '\n'.join(out)


def _explicit_prior(prior, order):
    """An explicit `prior` argument still wins (as in 007): a flat {code: {approved, comment}} or
    the 007 {'sections': {...}} shape, restricted to the current codes."""
    src = prior.get('sections') if isinstance(prior.get('sections'), dict) else prior
    kept = {}
    for code in order:
        s = src.get(code) if isinstance(src, dict) else None
        if isinstance(s, dict):
            kept[code] = {'approved': bool(s.get('approved')), 'comment': str(s.get('comment') or '')}
    carry = {'carried': len(kept), 'total': len(order), 'pending': [c for c in order if c not in kept]}
    return kept, carry


def _compact_page(d, texts, prior, problems):
    """(body, blob fields) of the compact page. ValueError over MAX_ITEMS (nothing written).
    aidd:FR-301 aidd:FR-303 aidd:FR-312"""
    it = _items()
    ex = it.extract_items(texts)
    order = [c for c in (ex.get('order') or []) if isinstance(c, str)]
    cap = int(it.MAX_ITEMS)
    if len(order) > cap:
        raise ValueError(_too_many(len(order), cap))
    items = ex.get('items') if isinstance(ex.get('items'), dict) else {}
    digests = {}
    for code in order:
        item = items.get(code)
        if not isinstance(item, dict):
            continue
        try:
            d8 = it.item_digest(item)
        except Exception:  # noqa: BLE001 — an item without digest is simply never carried
            continue
        if isinstance(d8, str) and _HEX8_RE.fullmatch(d8):
            digests[code] = d8
    try:
        summary = it.build_summary(texts, ex)
    except Exception:  # noqa: BLE001 — the summary data is informative; SUMMARY stays an item
        summary = {}
    if isinstance(prior, dict):
        pr, carry = _explicit_prior(prior, order)
    else:
        pr, carry = _carry_over(d, order, digests)     # BEFORE the old page is overwritten
    tabs = [t for t in (ex.get('tabs') or []) if isinstance(t, dict) and t.get('id')]
    warnings = _norm_warnings(ex.get('warnings'))
    links = {str(t['id']): _TAB_SOURCE[str(t['id'])] for t in tabs
             if _TAB_SOURCE.get(str(t['id'])) and texts.get(_TAB_SOURCE[str(t['id'])]) is not None}
    data = {
        'format': _FMT_COMPACT,
        'warnings': warnings,
        'tabs': [{'id': str(t['id']), 'label': str(t.get('label') or t['id']),
                  'items': [_blob_item(x) for x in _tab_items(t, items)]} for t in tabs],
        'codes': order,
        'digests': digests,
        'links': links,
        'prior': pr,
        'carry': carry,
        'summary': summary if isinstance(summary, dict) else {},
        'verification_problems': problems,
    }
    return _compact_body(tabs, items, warnings, texts, problems), data


def build_html(spec_dir, prior=None, template_text=None, full=False):
    """The filled page (compact by default, the 007 page with `full=True`). `template_text`
    exists ONLY for tests (never exposed by CLI or env). aidd:FR-303"""
    d = Path(spec_dir)
    sources = _load_sources(d)
    texts = _checked_texts(d, sources)
    rules = _rules()
    tasks_hash = rules.approval_hash(texts['tasks.md'])
    digest = _digest_of(sources)
    spec_id = d.name
    problems = _verification_problems(d, texts.get('spec.md'))
    if full:
        template_text = _load_template(template_text, True)
        script_sha = _script_sha256(template_text)
        body, extra = _full_page(d, sources, prior, problems)
    else:
        body, extra = _compact_page(d, texts, prior, problems)   # the cap refuses first
        template_text = _load_template(template_text, False)
        script_sha = _script_sha256(template_text)
    generated = time.strftime('%Y-%m-%d')
    data = {
        'spec': spec_id,
        'tasks_hash': tasks_hash,
        'sources_digest': digest,
        'tasks_hash8': tasks_hash[:8],
        'generated': generated,
        'picker_id': _picker_id(spec_id),
    }
    data.update(extra)
    values = {
        '{{TITLE}}': _esc(f'Review {spec_id}'),
        '{{SPEC_ID}}': _esc(spec_id),
        '{{TASKS_HASH}}': tasks_hash,
        '{{TASKS_HASH8}}': tasks_hash[:8],
        '{{SOURCES_DIGEST}}': digest,
        '{{GENERATED}}': generated,
        '{{BODY}}': body,
        '{{DATA_JSON}}': _json_blob(data),
        '{{SCRIPT_SHA256}}': script_sha,
    }
    # single pass: substituted values (spec text may mention {{TOKENS}}) are never rescanned
    return _TOKEN_RE.sub(lambda m: values[m.group(0)], template_text)


def _page_blob(page_path):
    """The `aidd-data` JSON of an existing page as a dict, or None on any error."""
    try:
        m = _DATA_RE.search(_read_text(page_path))
        if not m:
            return None
        data = json.loads(m.group(1))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError, AttributeError, TypeError, RecursionError):
        return None


def _page_meta(page_path):
    """(tasks_hash, sources_digest, format) of an existing page, (None, None, None) on any error.
    A blob without `format` (a 007 page) is `headings-v1`. aidd:FR-304"""
    data = _page_blob(page_path)
    if data is None:
        return None, None, None
    th, sd = data.get('tasks_hash'), data.get('sources_digest')
    fmt = data.get('format', _FMT_FULL)
    return ((th if isinstance(th, str) else None), (sd if isinstance(sd, str) else None),
            (fmt if isinstance(fmt, str) else None))


def _page_digests(page_path):
    """{code: d8} of the previous page blob ({} when absent, unparseable or a --full page)."""
    data = _page_blob(page_path) or {}
    dg = data.get('digests')
    if not isinstance(dg, dict):
        return {}
    return {k: v for k, v in dg.items() if isinstance(k, str) and isinstance(v, str) and _HEX8_RE.fullmatch(v)}


def _atomic_write(path, text):
    tmp = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
    try:
        with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def _no_carry(order):
    return {}, {'carried': 0, 'total': len(order), 'pending': list(order)}


def _carry_over(spec_dir, order, digests):
    """aidd:FR-312 IO wrapper of the carry-over rule; reads only, never writes a file.
    The previous review.md counts only when it parses `ok`, is `codes-v2` and names the same spec;
    `parse_review` returns `sections` and `digests` SEPARATELY, `carry_decision` wants ONE map, so
    they are merged here (a code without ` @d8` gets `'digest': None` and is never carried; a
    digest without a section line is ignored). Any error = no carry-over."""
    try:
        order = list(order or [])
    except TypeError:
        order = []
    try:
        d = Path(spec_dir)
        prev_lines = {}
        md = d / REVIEW_MD
        if md.is_file():
            parsed = parse_review(md.read_bytes().decode('utf-8', 'replace'))
            meta = parsed.get('meta') if isinstance(parsed.get('meta'), dict) else {}
            if parsed.get('ok') and parsed.get('format') == _FMT_COMPACT and meta.get('spec') == d.name:
                dg = parsed.get('digests') if isinstance(parsed.get('digests'), dict) else {}
                secs = parsed.get('sections') if isinstance(parsed.get('sections'), dict) else {}
                prev_lines = {code: {'approved': bool(s.get('approved')),
                                     'comment': str(s.get('comment') or ''),
                                     'digest': dg.get(code)}
                              for code, s in secs.items() if isinstance(s, dict)}
        page = d / REVIEW_HTML
        prev_blob = _page_digests(page) if page.is_file() else {}
        res = _items().carry_decision(prev_lines, prev_blob, dict(digests or {}), order)
        prior, carry = res
        if not isinstance(prior, dict) or not isinstance(carry, dict):
            return _no_carry(order)
        return prior, carry
    except Exception:  # noqa: BLE001 — any error = no carry-over, never a traceback
        return _no_carry(order)


def _full_prior(d, tasks_hash, digest):
    """The 007 prior prefill of a --full page: a valid headings-v1 review.md of the same hashes."""
    md = d / REVIEW_MD
    try:
        if not md.is_file():
            return None
        pr = parse_review(_read_text(md))
    except OSError:
        return None
    meta = pr.get('meta') if isinstance(pr.get('meta'), dict) else {}
    if pr.get('ok') and pr.get('format') == _FMT_FULL and meta.get('tasks_hash') == tasks_hash \
            and meta.get('sources_digest') == digest:
        return {'approved': meta.get('approved') is True, 'sections': pr.get('sections', {})}
    return None


def generate(spec_dir, template_text=None, full=False):
    """Write `specs/<id>/review.html` atomically; (path, wrote). Untouched when the existing page
    carries the same sources_digest, tasks_hash AND format (a 007 page without `format` is a
    headings-v1 page). Raises ValueError without tasks.md, over MAX_REVIEW_SOURCE_CHARS or, for
    the compact page, over MAX_ITEMS (nothing written). aidd:FR-303 aidd:FR-312"""
    d = Path(spec_dir).resolve()
    if not d.is_dir():
        raise ValueError(f'spec folder not found: {d}')
    sources = _load_sources(d)
    texts = _checked_texts(d, sources)
    tasks_hash = _rules().approval_hash(texts['tasks.md'])
    digest = _digest_of(sources)
    page = d / REVIEW_HTML
    fmt = _FMT_FULL if full else _FMT_COMPACT
    if page.is_file() and _page_meta(page) == (tasks_hash, digest, fmt):
        return page, False
    prior = _full_prior(d, tasks_hash, digest) if full else None
    # compact: build_html runs _carry_over (reads the OLD review.md/review.html) before the write
    _atomic_write(page, build_html(d, prior=prior, template_text=template_text, full=full))
    return page, True


# ---------------------------------------------------------------------------
# review.md and the approval state (aidd:FR-203, FR-304, FR-309)
# ---------------------------------------------------------------------------

def parse_review(text):
    """aidd_review_state.parse_review with this spec's code grammar (aidd:FR-304): adds `format`
    and `digests` to the 007 shape. Never raises: a missing module is an invalid result."""
    try:
        res = _state().parse_review(text, _items().CODE_RE)
        if isinstance(res, dict):
            return res
        raise TypeError('parse_review returned no dict')
    except Exception as e:  # noqa: BLE001 — fail closed, never a traceback
        err = _SPLIT_REASON if isinstance(e, ImportError) else f'unparseable review.md ({type(e).__name__})'
        return {'ok': False, 'errors': [err], 'warnings': [], 'meta': {}, 'format': None,
                'sections': {}, 'digests': {}}


def _mtime(p):
    try:
        return os.path.getmtime(p)
    except OSError:
        return None


def _blank_state(reason):
    """The review_state shape with nothing true (every 007 field plus the 008 ones)."""
    return {'present': False, 'valid': False, 'hash_ok': False, 'digest_ok': False, 'fresh': False,
            'complete': False, 'missing': [], 'comments': [], 'sha1': '', 'reviewed': '',
            'mtime': 0.0, 'page_current': False, 'reason': reason, 'format': None,
            'page_format': None, 'legacy': False, 'item_count': 0}


def review_state(spec_dir):
    """IO half of the review state (aidd:FR-203 aidd:FR-304): loads the sources, the page meta,
    the mtimes and the review.md bytes, then `aidd_review_state.evaluate_review(inp)` decides.
    `item_count` comes from the compact extraction whenever the page is not a --full page (also
    with no page, so the item cap wins over `no review.html`). `complete` is CONTENT only, never
    sufficient to approve (aidd:FR-204). Never raises."""
    try:
        d = Path(spec_dir)
        sources = _load_sources(d)
        texts = dict(sources)
        big = _oversize(sources)
        try:
            digest = _digest_of(sources)
            tasks_hash = (_rules().approval_hash(texts['tasks.md'])
                          if texts.get('tasks.md') is not None else None)
        except ImportError:
            return _blank_state('aidd_rules is not importable next to aidd_review.py')
        try:
            it = _items()
            sm = _state()
        except ImportError:
            return _blank_state(_SPLIT_REASON)
        page = d / REVIEW_HTML
        md = d / REVIEW_MD
        page_mtime = _mtime(page) if page.is_file() else None
        page_meta = _page_meta(page) if page_mtime is not None else (None, None, None)
        review_bytes, review_error, review_mtime = None, '', 0.0
        if md.is_file():
            try:
                review_bytes = md.read_bytes()
            except OSError as e:
                review_error = f'review.md is not readable ({e})'
            review_mtime = _mtime(md) or 0.0
        keys, item_count = [], 0
        if not big:
            if page_mtime is not None and page_meta[2] == _FMT_FULL:
                keys = _keys_of(sources)
                item_count = len(keys)
            else:
                keys = [c for c in (it.extract_items(texts).get('order') or []) if isinstance(c, str)]
                item_count = len(keys)
        inp = {
            'review_bytes': review_bytes,
            'review_error': review_error,
            'review_mtime': review_mtime,
            'page_mtime': page_mtime,
            'page_meta': page_meta,
            'tasks_hash': tasks_hash,
            'digest': digest,
            'oversize': big[0][0] if big else None,
            'item_count': item_count,
            'max_items': int(it.MAX_ITEMS),
            'keys': keys,
            'code_re': it.CODE_RE,
        }
        res = sm.evaluate_review(inp)
        return res if isinstance(res, dict) else _blank_state('review state unavailable (no result)')
    except Exception as e:  # noqa: BLE001 — pure read, never raises
        return _blank_state(f'review state unavailable ({type(e).__name__})')


def _approval_tag(spec_dir):
    """`[tasks:<h8>]` of the current tasks.md (aidd_status.approval_tag, or the identical
    fallback); None without a readable tasks.md. aidd:FR-309"""
    try:
        p = Path(spec_dir) / 'tasks.md'
        if not p.is_file():
            return None
        text = _read_text(p)
    except OSError:
        return None
    try:
        _script_dir_on_path()
        import aidd_status  # noqa: E402 — lazy: a heavy module, needed only for the tag
        tag = aidd_status.approval_tag(text)
        if isinstance(tag, str) and tag:
            return tag
    except Exception:  # noqa: BLE001 — the fallback below is the same formula
        pass
    try:
        return '[tasks:' + _rules().approval_hash(text)[:8] + ']'
    except Exception:  # noqa: BLE001
        return None


_STALE = {'state': 'stale', 'approved': 0, 'total': 0, 'comments': 0, 'stale': True,
          'legacy': False, 'tag': None}


def approval_state(spec_dir):
    """aidd:FR-309 `{state, approved, total, comments, stale, legacy, tag}`; never raises."""
    try:
        st = _state().derive_approval(review_state(spec_dir), _approval_tag(spec_dir))
        return st if isinstance(st, dict) else dict(_STALE)
    except Exception:  # noqa: BLE001 — unknown is stale (fail closed)
        return dict(_STALE)


def status_line(st):
    """aidd:FR-309 the ONE status line (no file content, item text, comment or reason)."""
    return _state().status_line(st)


def review_comments(spec_dir):
    """aidd:FR-309 (exit, [`<CODE>: <comment>`]); (3, []) on any error."""
    try:
        return _state().comment_lines(review_state(spec_dir))
    except Exception:  # noqa: BLE001
        return 3, []


def summary_lines(spec_dir):
    """aidd:FR-313 the mechanical summary (at most 30 lines); writes nothing."""
    texts = dict(_load_sources(spec_dir))
    tasks = texts.get('tasks.md') or ''
    it = _items()
    return list(_state().summary_lines(it.build_summary(texts), it.target_files(tasks),
                                       it.wave_count(tasks)))


def _wait_cannot_help(rs, st):
    """aidd:FR-306 exit 3: waiting cannot help (the owner cannot fix it by saving review.md)."""
    reason = str(rs.get('reason') or '')
    return (st.get('state') == 'too_many_items'
            or reason.startswith(('too many items', 'no review.html', 'source too large'))
            or 'not importable' in reason
            or not st.get('tag')                       # no tasks.md
            or not rs.get('page_current'))             # the page is not for the current sources


def review_wait(spec_dir, timeout=3600.0, interval=2.0, out=print, sleep=time.sleep,
                clock=time.monotonic):
    """aidd:FR-306 poll `review_state` silently; print exactly ONE `status_line` when exiting:
    0 complete and current, 2 timeout (last state), 3 waiting cannot help. Reads only: never
    writes a file, never approves, never records consent. A legacy, stale (older hash) or
    incomplete review.md keeps polling (the owner can still save from the page)."""
    try:
        sm = _state()
        _items()
    except ImportError:
        return 3
    try:
        timeout = float(timeout)
        interval = float(interval)
    except (TypeError, ValueError):
        timeout, interval = 3600.0, 2.0
    timeout = timeout if timeout >= 0 else 0.0
    interval = interval if interval > 0 else 2.0
    st = dict(_STALE)
    try:
        start = clock()
        while True:
            rs = review_state(spec_dir)
            st = sm.derive_approval(rs, _approval_tag(spec_dir))
            if st.get('state') == 'complete' and not st.get('stale') and not st.get('legacy'):
                out(sm.status_line(st))
                return 0
            if _wait_cannot_help(rs, st):
                out(sm.status_line(st))
                return 3
            if clock() - start >= timeout:
                out(sm.status_line(st))
                return 2
            sleep(interval)
    except Exception:  # noqa: BLE001 — never a traceback; one line when possible
        try:
            out(sm.status_line(st if isinstance(st, dict) else dict(_STALE)))
        except Exception:  # noqa: BLE001
            pass
        return 3


# ---------------------------------------------------------------------------
# Consent by prompt (aidd:FR-204)
# ---------------------------------------------------------------------------

def _norm_prompt(text):
    t = unicodedata.normalize('NFKC', str(text or '')).replace('’', "'").replace('‘', "'")
    return re.sub(r'\s+', ' ', t).strip().lower()


def prompt_consent(ev, root, session, tag, since_ts):
    """The newest hook-recorded `prompt` of `session` (or `unknown-session`) newer than
    `since_ts` that carries `tag`, an approve word and no negation -> {'kind':'prompt','ts'};
    else None. Envelope texts starting with `<` (agent/system notices) never count."""
    try:
        need = _norm_prompt(tag)
        if not need:
            return None
        since = float(since_ts or 0.0)
        sessions = {str(session or 'unknown-session'), 'unknown-session'}
        evs = []
        for s in sessions:
            evs += list(ev.events(root, kind='prompt', session=s, since=since) or [])
        for e in sorted(evs, key=lambda x: float(x.get('ts', 0.0)), reverse=True):
            ts = float(e.get('ts', 0.0))
            if ts <= since or e.get('session') not in sessions:
                continue
            det = e.get('detail') if isinstance(e.get('detail'), dict) else {}
            text = _norm_prompt(det.get('text', ''))
            if not text or text.startswith('<') or need not in text:
                continue
            if _APPROVE_WORD_RE.search(text) and not _NEGATION_RE.search(text):
                return {'kind': 'prompt', 'ts': ts}
        return None
    except Exception:  # noqa: BLE001 — no consent found is the safe answer
        return None



# ---------------------------------------------------------------------------
# CLI (aidd:FR-303 aidd:FR-306 aidd:FR-309 aidd:FR-313)
# ---------------------------------------------------------------------------

class _Parser(argparse.ArgumentParser):
    def error(self, message):           # exit 1, never 2 (2 means "pending" for --check)
        self.print_usage(sys.stderr)
        print(f'aidd review: {message}', file=sys.stderr)
        raise SystemExit(1)


def _parser():
    p = _Parser(prog='aidd review',
                description='Generate review.html for a spec / read the approval state of review.md.')
    p.add_argument('spec_dir')
    p.add_argument('--open', action='store_true', help='open the page in the default browser')
    p.add_argument('--full', action='store_true',
                   help='generate the long page with heading keys (templates/review-full.html)')
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true',
                      help='print ONE status line (exit 0 complete / 2 pending / 3 stale, legacy, too many items)')
    mode.add_argument('--wait', action='store_true',
                      help='poll silently, then print ONE status line (exit 0 complete / 2 timeout / 3 cannot help)')
    mode.add_argument('--comments', action='store_true',
                      help='print `<CODE>: <comment>` for commented codes only')
    mode.add_argument('--summary', action='store_true',
                      help='print the mechanical summary (at most 30 lines); writes nothing')
    p.add_argument('--timeout', type=float, default=3600.0, metavar='S', help='--wait timeout (default 3600)')
    p.add_argument('--interval', type=float, default=2.0, metavar='S', help='--wait poll interval (default 2)')
    return p


def main(argv=None):
    try:
        sys.stdout.reconfigure(errors='replace')
        sys.stderr.reconfigure(errors='replace')
    except (AttributeError, ValueError, OSError):
        pass
    p = _parser()
    a = p.parse_args(sys.argv[1:] if argv is None else argv)
    if not (a.timeout >= 0) or a.timeout == float('inf'):
        p.error('--timeout must be a finite number of seconds >= 0')
    if not (a.interval > 0) or a.interval == float('inf'):
        p.error('--interval must be a finite number of seconds > 0')
    try:
        d = Path(a.spec_dir).resolve()
        if not d.is_dir():
            print(f'aidd review: spec folder not found: {d}', file=sys.stderr)
            return 1
        if a.check or a.wait or a.comments or a.summary:
            _items()
            sm = _state()
            if a.check:
                st = approval_state(d)
                print(sm.status_line(st))
                return sm.exit_for(st.get('state'))
            if a.wait:
                return review_wait(d, timeout=a.timeout, interval=a.interval)
            if a.comments:
                code, lines = review_comments(d)
                for line in lines:
                    print(line)
                return code
            if not (d / 'tasks.md').is_file():
                print(f'aidd review: tasks.md not found in {d}: nothing to summarise', file=sys.stderr)
                return 3
            for line in summary_lines(d):
                print(line)
            return 0
        try:
            path, wrote = generate(d, full=a.full)
        except ValueError as e:
            print(f'aidd review: {e}', file=sys.stderr)
            return 1
        texts = dict(_load_sources(d))
        for prob in _verification_problems(d, texts.get('spec.md')):
            print(f'warning: {prob}', file=sys.stderr)
        print(f"{'wrote' if wrote else 'unchanged'}: {path}")
        print(path.as_uri())
        if a.open:
            try:
                import webbrowser
                if not webbrowser.open(path.as_uri()):
                    print('aidd review: could not open a browser; open the URI above', file=sys.stderr)
            except Exception as e:  # noqa: BLE001
                print(f'aidd review: could not open a browser ({e})', file=sys.stderr)
        return 0
    except ImportError as e:
        print(f'aidd review: {_SPLIT_REASON} ({e})', file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        return 3
    except Exception as e:  # noqa: BLE001 — the CLI never prints a traceback
        print(f'aidd review: failed ({type(e).__name__}: {e})', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
