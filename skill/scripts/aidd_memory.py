#!/usr/bin/env python3
"""
aidd memory -- curated, code-anchored, git-versioned memory in AIDD-TOON.

No daemon, no LLM observer, no vectors, stdlib only. Memory lives in
`<root>/.aidd/memory/<scope>.toon` (scope = a spec id or `project`) and is
committed to git. Compacted entries go to `archive/<YYYY>-Q<q>.toon`.

File format (writer always emits `[*]` so parallel git branches appending rows
never conflict on a counter; the reader accepts `[*]` or `[N]` and never
enforces N):

    version: 1
    memory: project
    entries[*]{id,date,type,title,codes,files,why,supersedes,source}:
      m-3fa91c02,2026-10-01,decision,Title,US-001|CTL-004,a/b.py,"why, quoted",,agent

Derived cache: `<memory dir>/.cache/` (own .gitignore, keyed by mtime_ns+size, optional,
auto-invalidating, never the source of truth; safe when missing/corrupt/read-only).

Usage: python aidd_memory.py [--root DIR] <add|search|show|timeline|file|inject|compact|stats|import-claude-mem> ...
Exit codes: 0 ok, 1 usage/validation error, 2 nothing found (search/show/file).
"""
import contextlib
import heapq
import marshal
import math
import os
import random
import re
import sys
import time
import unicodedata
from array import array
from itertools import compress
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:  # pragma: no cover
        pass

TYPES = ('decision', 'bugfix', 'discovery', 'constraint', 'risk', 'rejected', 'open-question', 'state')
FIELDS = ('id', 'date', 'type', 'title', 'codes', 'files', 'why', 'supersedes', 'source')
SOURCES = ('agent', 'user', 'import', 'hook')
TITLE_MAX = 120
WHY_MAX = 400
VERSION = 1

CODE_RE = re.compile(r'\b(SCREEN-\d+(?:-F\d+)?|CTL-\d+|COMP-\d+|API-\d+|US-\d+)\b', re.IGNORECASE)
HEADER_RE = re.compile(r'^entries\[(\*|\d+)\]\{([^}]*)\}:\s*$')
SCOPE_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')
DATE_RE = re.compile(r'^(\d{4})-(\d{2})-(\d{2})')
STRICT_DATE_RE = re.compile(r'^(\d{4})-(\d{2})-(\d{2})$')
CONFLICT_RE = re.compile(r'^(<{7}|={7}|>{7})')

STOPWORDS = set("""
the an and or of to in on for with this that is it be are was were as at by from not but if then so
we you they he she its our your their has have had do does did can could should would will may
de la el los las un una unos unas que con para del al y o se es lo por como mas pero sus le les
su sin sobre entre esta este esto estos estas ese esa son fue ser hay muy ya nos mi tu yo si
cada tiene tienen hacer
""".split())


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def find_root(start=None):
    cur = Path(start or Path.cwd()).resolve()
    for d in [cur] + list(cur.parents):
        if (d / '.aidd').is_dir() or (d / 'specs').is_dir() or (d / '.git').exists():
            return d
    return cur


def memory_dir(root):
    env = os.environ.get('AIDD_MEMORY_DIR')
    if env:
        return Path(env)
    return Path(root) / '.aidd' / 'memory'


def make_id(scope, date, title):
    import hashlib
    h = hashlib.sha1(f"{scope}|{date}|{title}".encode('utf-8')).hexdigest()
    return 'm-' + h[:8]


# ---------------------------------------------------------------------------
# AIDD-TOON read / write
# ---------------------------------------------------------------------------

_WARNED = set()


def _warn(msg):
    """Warn once per process per distinct message (file:line included by callers)."""
    if msg in _WARNED:
        return
    _WARNED.add(msg)
    try:
        print(f"aidd-memory: warning: {msg}", file=sys.stderr)
    except Exception:  # pragma: no cover
        pass


def _flat(s):
    return re.sub(r'\s*(?:\r\n|\n|\r)\s*', ' / ', str(s if s is not None else ''))


def _csv_row(values):
    import csv
    import io
    buf = io.StringIO()
    csv.writer(buf, lineterminator='').writerow([_flat(v) for v in values])
    return '  ' + buf.getvalue()


def _entry_values(entry, fields):
    out = []
    for f in fields:
        v = entry.get(f, '')
        if isinstance(v, (list, tuple)):
            v = '|'.join(str(x) for x in v)
        out.append(v)
    return out


def _header(scope, fields):
    return f"version: {VERSION}\nmemory: {scope}\nentries[*]{{{','.join(fields)}}}:\n"


def _valid_date(d):
    m = STRICT_DATE_RE.match(d or '')
    if not m:
        return False
    from datetime import date as _date
    try:
        _date(*(int(x) for x in m.groups()))
    except ValueError:
        return False
    return True


def _parse_lines(text, label=''):
    """-> (meta, items); items = [(lineno, kind, raw_line, entry_or_None)].

    kind: 'blank' | 'comment' | 'header' | 'meta' | 'row' | 'junk'.
    'junk' = a line that is none of the above (git conflict markers, stray text,
    an indented row before any header). Malformed rows are kind 'row' with entry
    None (warned once per process per file:line)."""
    import csv
    meta, items = {}, []
    fields = None
    nf = 0
    lines = text.lstrip('﻿').split('\n')
    for n, raw in enumerate(lines, 1):
        line = raw.rstrip('\r')
        if not line.strip():
            items.append((n, 'blank', line, None))
            continue
        indented = line[0].isspace()
        if line.strip().startswith('#'):
            items.append((n, 'comment', line, None))
            continue
        if not indented:
            m = HEADER_RE.match(line.strip())
            if m:
                fields = [f.strip() for f in m.group(2).split(',')]
                nf = len(fields)
                items.append((n, 'header', line, None))
                continue
            if ':' in line and not CONFLICT_RE.match(line):
                k, _, v = line.partition(':')
                meta[k.strip()] = v.strip()
                fields = None  # a meta line ends any open table
                items.append((n, 'meta', line, None))
                continue
            _warn(f"{label}:{n}: skipped unparseable line")
            items.append((n, 'junk', line, None))
            continue
        if fields is None:
            items.append((n, 'junk', line, None))
            continue
        entry = None
        try:
            row = next(csv.reader([line.strip()]))
            if len(row) != nf:
                raise ValueError('field count')
            entry = {f: '' for f in FIELDS}
            entry.update(zip(fields, row))
            if not entry['id'].strip():
                raise ValueError('empty id')
            if entry['type'] not in TYPES:
                raise ValueError('invalid type')
            if not _valid_date(entry['date']):
                raise ValueError('invalid date')
        except (csv.Error, ValueError, StopIteration):
            _warn(f"{label}:{n}: skipped malformed row")
            entry = None
        items.append((n, 'row', line, entry))
    return meta, items


def _parse_text(text, label=''):
    """-> (meta, items); items = [(raw_line, entry_or_None)] for every row line."""
    meta, items = _parse_lines(text, label)
    return meta, [(raw, e) for _, kind, raw, e in items if kind == 'row']


def _split(s):
    return [x for x in str(s).split('|') if x]


def _finish(entry, scope, archived):
    e = dict(entry)
    e['codes'] = _split(e.get('codes', ''))
    e['files'] = _split(e.get('files', ''))
    e['scope'] = e.get('scope') or scope
    e['archived'] = archived
    e['superseded'] = False
    return e


def _scope_files(root, archived=False):
    d = memory_dir(root)
    if archived:
        d = d / 'archive'
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob('*.toon') if p.is_file())


def _read_file(path):
    try:
        return path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as e:
        _warn(f"{path}: unreadable ({e})")
        return ''


def _load_all(root):
    """Every entry (active + archived), duplicates by id dropped (first wins),
    with `superseded` computed across both."""
    seen, out = set(), []
    for archived in (False, True):
        for p in _scope_files(root, archived):
            meta, items = _parse_text(_read_file(p), str(p))
            scope = p.stem if not archived else (meta.get('memory') or 'archive')
            for _, entry in items:
                if entry is None or entry['id'] in seen:
                    continue
                seen.add(entry['id'])
                out.append(_finish(entry, scope, archived))
    replaced = {e['supersedes'] for e in out if e['supersedes']}
    for e in out:
        e['superseded'] = e['id'] in replaced
    return out


def _known_ids(root):
    """Ids of every row in every memory file (active + archive). A light scan of
    the first column only: cheap, never touches the derived cache."""
    ids = set()
    for archived in (False, True):
        for p in _scope_files(root, archived):
            for line in _read_file(p).split('\n'):
                if not line[:1].isspace() or line.lstrip().startswith('#'):
                    continue
                first = line.strip().split(',', 1)[0].strip('"').strip()
                if first:
                    ids.add(first)
    return ids


def load_entries(root, include_archive=False):
    return [e for e in _load_all(root) if include_archive or not e['archived']]


_RESERVED_NAMES = frozenset(['con', 'prn', 'aux', 'nul'] + [f"com{i}" for i in range(1, 10)]
                            + [f"lpt{i}" for i in range(1, 10)])


def _validate_scope(scope):
    if not scope or not isinstance(scope, str) or not SCOPE_RE.fullmatch(scope):
        raise ValueError(f"invalid scope {str(scope)[:70]!r} (1-64 chars: letters, digits, '.', '-', '_'; "
                         "must start with a letter or digit)")
    if scope.split('.')[0].lower() in _RESERVED_NAMES:
        raise ValueError(f"invalid scope {scope[:70]!r} (reserved device name on Windows)")


def _atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    os.replace(tmp, path)


def _append_rows(path, scope_label, fields, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = ''.join(_csv_row(_entry_values(e, fields)) + '\n' for e in entries)
    if not path.exists() or path.stat().st_size == 0:
        text = _header(scope_label, fields) + rows
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        return
    with open(path, 'rb') as f:
        f.seek(-1, os.SEEK_END)
        needs_nl = f.read(1) != b'\n'
    with open(path, 'a', encoding='utf-8', newline='\n') as f:
        if needs_nl:
            f.write('\n')
        f.write(rows)


LOCK_NAME = '.lock'
LOCK_TIMEOUT = 5.0
LOCK_STALE = 60.0


@contextlib.contextmanager
def _locked(root):
    """Cross-process lock (O_CREAT|O_EXCL lock file in the memory dir) serialising
    every read-modify-write. Retries up to LOCK_TIMEOUT s, removes a lock older than
    LOCK_STALE s, always released; failing to acquire raises OSError (never silent)."""
    d = memory_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    path = d / LOCK_NAME
    deadline = time.monotonic() + LOCK_TIMEOUT
    while True:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, str(os.getpid()).encode('ascii'))
            finally:
                os.close(fd)
            break
        except (FileExistsError, PermissionError):
            try:
                age = time.time() - path.stat().st_mtime
                if age > LOCK_STALE:
                    path.unlink()
                    continue
            except OSError:
                pass
            if time.monotonic() >= deadline:
                raise OSError(f"could not acquire the memory lock {path} within "
                              f"{LOCK_TIMEOUT:g}s (another aidd mem process is writing; "
                              "retry, or delete the lock file if it is stale)")
            time.sleep(0.005 + random.random() * 0.02)
    try:
        yield
    finally:
        try:
            path.unlink()
        except OSError:
            pass


def append_entries(root, scope, entries):
    """Append already-normalised entry dicts to <scope>.toon. Returns ids written
    (entries whose id already exists anywhere, archive included, are skipped).
    Serialised against other writers (and compact --apply) by a lock file."""
    _validate_scope(scope)
    with _locked(root):
        return _append_entries_locked(root, scope, entries)


def _append_entries_locked(root, scope, entries):
    existing = _known_ids(root)
    fresh, written = [], []
    for e in entries:
        eid = e.get('id') or make_id(scope, e.get('date', ''), e.get('title', ''))
        if eid in existing:
            continue
        existing.add(eid)
        e = dict(e)
        e['id'] = eid
        fresh.append(e)
        written.append(eid)
    if fresh:
        _append_rows(memory_dir(root) / f"{scope}.toon", scope, FIELDS, fresh)
    return written


# ---------------------------------------------------------------------------
# Entry construction
# ---------------------------------------------------------------------------

def _trunc(s, n):
    s = _flat(s).strip()
    return s if len(s) <= n else s[:n - 1].rstrip() + '…'


def _norm_date(d):
    from datetime import date as _date
    if d is None or d == '':
        return _date.today().isoformat()
    if hasattr(d, 'isoformat'):
        d = d.isoformat()
    m = DATE_RE.match(str(d).strip())
    if not m:
        raise ValueError(f"invalid date {d!r} (expected YYYY-MM-DD)")
    y, mo, da = (int(x) for x in m.groups())
    try:
        _date(y, mo, da)
    except ValueError:
        raise ValueError(f"invalid date {d!r}")
    return f"{y:04d}-{mo:02d}-{da:02d}"


def _as_list(v):
    if v is None:
        return []
    if isinstance(v, str):
        v = re.split(r'[,|]', v)
    return [str(x).strip() for x in v if str(x).strip()]


def _norm_file(f, root=None):
    f = str(f).strip().replace('\\', '/')
    if root is not None and re.match(r'^([A-Za-z]:)?/', f):
        try:
            f = Path(f).resolve().relative_to(Path(root).resolve()).as_posix()
        except (ValueError, OSError):
            pass
    while f.startswith('./'):
        f = f[2:]
    return f


def add_entry(root, *, type, title, why='', codes=(), files=(), scope='project',
              supersedes='', source='agent', date=None):
    if type not in TYPES:
        raise ValueError(f"invalid type {type!r}; expected one of: {', '.join(TYPES)}")
    if source not in SOURCES:
        raise ValueError(f"invalid source {source!r}; expected one of: {', '.join(SOURCES)}")
    _validate_scope(scope)
    title = _trunc(title, TITLE_MAX)
    if not title:
        raise ValueError("title is required")
    d = _norm_date(date)
    supersedes = str(supersedes or '').strip()
    if supersedes and supersedes not in _known_ids(root):
        raise ValueError(f"--supersedes {supersedes!r}: no memory entry with that id")
    entry = {
        'id': make_id(scope, d, title),
        'date': d,
        'type': type,
        'title': title,
        'codes': [c.upper() if CODE_RE.fullmatch(c) else c for c in _as_list(codes)],
        'files': [_norm_file(f, root) for f in _as_list(files)],
        'why': _trunc(why, WHY_MAX),
        'supersedes': supersedes,
        'source': source,
    }
    append_entries(root, scope, [entry])
    return entry['id']


# ---------------------------------------------------------------------------
# Tokenizer + BM25
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r'\w+', re.UNICODE)


def _fold(s):
    s = str(s)
    if s.isascii():
        return s.lower()
    s = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in s if not unicodedata.combining(c)).lower()


_VOWELS = frozenset('aeiouy')


def _stem_raw(w):
    """Light ES+EN stemmer. A suffix is never stripped when the remaining stem would be
    shorter than 3 characters (or, for -ing/-ed, has no vowel), and a trailing `e` is
    only dropped when >= 4 characters remain, so unrelated short words never collide
    (string/str, mode/mod, top/tope, us/use ...) while table/tables, use/used/using,
    file/files, rule/rules, base/bases, cache/cached/caching, decision/decisiones,
    regla/reglas, query/queries and running/run still match."""
    n = len(w)
    if n > 6 and w.endswith('iones'):
        w = w[:-2]  # decisiones -> decision
    elif n >= 7 and w.endswith('ies'):
        w = w[:-3] + 'y'  # queries -> query
    elif n >= 7 and w.endswith('ied'):
        w = w[:-3] + 'y'  # copied -> copy
    elif n >= 5 and w.endswith('ing') and not w.endswith('eing'):
        r = w[:-3]
        if len(r) >= 3 and any(c in _VOWELS for c in r):
            w = _undouble(r)
        elif len(r) == 2 and r[0] in 'aeiou' and r[1] not in _VOWELS:
            w = r + 'e'  # using -> use
    elif n >= 4 and w.endswith('ed') and not w.endswith('eed'):
        r = w[:-2]
        if len(r) >= 3 and any(c in _VOWELS for c in r):
            w = _undouble(r)
        elif len(r) == 2 and r[0] in 'aeiou' and r[1] not in _VOWELS:
            w = r + 'e'  # used -> use
    elif n > 4 and w.endswith('es'):
        r = w[:-2]
        w = r if (len(r) >= 4 or r.endswith(('x', 'z', 'ch', 'sh'))) else w[:-1]
    elif n > 3 and w.endswith('s') and not w.endswith('ss'):
        w = w[:-1]
    if len(w) >= 5 and w.endswith('e'):
        w = w[:-1]
    return w


def _undouble(r):
    """running -> run, mapped -> map (only when >= 3 characters remain)."""
    if len(r) >= 4 and r[-1] == r[-2] and r[-1] not in 'lszfaeiou':
        return r[:-1]
    return r


_TOKS = {}  # raw word -> stem, or None when it is dropped (too short / stopword)


def _stem(w):
    return _stem_raw(w)


def tokenize(text):
    out = []
    memo = _TOKS
    for raw in _WORD_RE.findall(_fold(text)):
        try:
            s = memo[raw]
        except KeyError:
            s = memo[raw] = None if len(raw) < 2 or raw in STOPWORDS else _stem_raw(raw)
        if s is not None:
            out.append(s)
    return out


W_TITLE, W_CODES, W_FILES, W_WHY = 3, 4, 2, 1
CODE_BONUS = 100.0


def _terms(title, codes, files, why):
    """-> (tf dict, weighted length, folded codes list) for one entry."""
    tf = {}
    get = tf.get
    length = 0
    ctoks, fcodes = [], []
    for c in codes:
        fc = _fold(c)
        fcodes.append(fc)
        ctoks.append(fc)
        ctoks.extend(tokenize(c))
    groups = ((tokenize(title), W_TITLE), (ctoks, W_CODES),
              ([t for f in files for t in tokenize(f)], W_FILES), (tokenize(why), W_WHY))
    for tokens, w in groups:
        length += w * len(tokens)
        for tok in tokens:
            tf[tok] = get(tok, 0) + w
    return tf, length, fcodes


def _doc_terms(e):
    tf, length, _ = _terms(e['title'], e['codes'], e['files'], e['why'])
    return tf, length


def _norm_path_cmp(a, b):
    a, b = a.replace('\\', '/').lower().lstrip('./'), b.replace('\\', '/').lower().lstrip('./')
    return a == b or a.endswith('/' + b) or b.endswith('/' + a)


def _filter(entries, type=None, code=None, file=None, scope=None):
    out = []
    fc = _fold(code) if code else None
    for e in entries:
        if type and e['type'] != type:
            continue
        if scope and e['scope'] != scope:
            continue
        if fc and fc not in {_fold(c) for c in e['codes']}:
            continue
        if file and not any(_norm_path_cmp(f, file) for f in e['files']):
            continue
        out.append(e)
    return out


def _recency_key(item):
    idx, e = item
    return (e['date'], idx)


# ---------------------------------------------------------------------------
# Derived cache (optional, auto-invalidating, never the source of truth)
#
# `<memory dir>/.cache/rows.bin`  parsed active rows (+ ids of archived rows)
# `<memory dir>/.cache/index.bin` BM25 postings, only built when `search` needs it
# Keyed by (name, mtime_ns, size) of every .toon file. A missing, stale, corrupt
# or unwritable cache just means the memory files are parsed again. The cache dir
# carries its own `.gitignore` (`*`), so nothing derived is ever committed.
# ---------------------------------------------------------------------------

CACHE_VERSION = 1
ROW_FIELDS = FIELDS + ('scope',)
KEY_TYPES = frozenset(('decision', 'constraint', 'risk'))
US = chr(31)  # field separator inside a cached row string


def _cache_dir(root):
    return memory_dir(root) / '.cache'


def _signature(root):
    sig = [CACHE_VERSION, tuple(sys.version_info[:2]), array('I').itemsize, sys.byteorder]
    for archived in (False, True):
        for p in _scope_files(root, archived):
            try:
                st = p.stat()
            except OSError:
                continue
            sig.append((archived, p.name, st.st_mtime_ns, st.st_size))
    return tuple(sig)


def _cache_read(root, name, sig):
    try:
        with open(_cache_dir(root) / name, 'rb') as f:
            if marshal.load(f) != sig:
                return None
            return marshal.load(f)
    except Exception:
        return None


def _cache_write(root, name, sig, payload):
    tmp = None
    try:
        d = _cache_dir(root)
        d.mkdir(parents=True, exist_ok=True)
        gi = d / '.gitignore'
        if not gi.exists():
            gi.write_text('*\n', encoding='utf-8')
        tmp = d / f"{name}.{os.getpid()}.tmp"
        with open(tmp, 'wb') as f:
            marshal.dump(sig, f)
            marshal.dump(payload, f)
        os.replace(tmp, d / name)
    except Exception:
        try:
            if tmp is not None and tmp.exists():
                tmp.unlink()
        except Exception:
            pass


def _build_rows(root):
    """Parse every memory file -> (rows, sup, arch_ids). rows = active entries as
    tuples in ROW_FIELDS order; sup = indexes of superseded rows (the superseding
    entry may live in the archive); arch_ids = ids that only exist in the archive."""
    ents = _load_all(root)
    rows, sup, arch = [], [], []
    for e in ents:
        if e['archived']:
            arch.append(e['id'])
            continue
        if e['superseded']:
            sup.append(len(rows))
        vals = (e['id'], e['date'], e['type'], e['title'], '|'.join(e['codes']),
                '|'.join(e['files']), e['why'], e['supersedes'], e['source'], e['scope'])
        rows.append(US.join(str(v).replace(US, ' ') for v in vals))
    return rows, sup, arch


def _build_index(rows):
    dl, postings, codemap = [], {}, {}
    for i, s in enumerate(rows):
        r = s.split(US)
        tf, length, fcodes = _terms(r[3], _split(r[4]), _split(r[5]), r[6])
        dl.append(length)
        for t, f in tf.items():
            lst = postings.get(t)
            if lst is None:
                postings[t] = [i, f]
            else:
                lst.append(i)
                lst.append(f)
        for c in set(fcodes):
            codemap.setdefault(c, []).append(i)
    # packed as bytes: one object per term instead of one per posting (fast marshal load)
    return (array('I', dl).tobytes(),
            {t: array('I', v).tobytes() for t, v in postings.items()},
            {c: array('I', v).tobytes() for c, v in codemap.items()})


def _arr(b):
    a = array('I')
    if b:
        a.frombytes(b)
    return a


class _Corpus:
    """Active (non-archived) entries as compact tuples + lazy BM25 index."""

    def __init__(self, root, sig, rows, sup, arch):
        self.root, self.sig = root, sig
        self.rows, self.sup, self.arch = rows, sup, arch
        self._idx = None

    def index(self):
        if self._idx is None:
            got = _cache_read(self.root, 'index.bin', self.sig)
            if not (isinstance(got, tuple) and len(got) == 3
                    and len(got[0]) == 4 * len(self.rows)):
                got = _build_index(self.rows)
                if len(self.sig) > 4:
                    _cache_write(self.root, 'index.bin', self.sig, got)
            self._idx = got
        return self._idx


def _corpus(root):
    sig = _signature(root)
    if len(sig) == 4:  # no memory files at all: never create anything
        return _Corpus(root, sig, [], [], [])
    got = _cache_read(root, 'rows.bin', sig)
    if not (isinstance(got, tuple) and len(got) == 3):
        got = _build_rows(root)
        _cache_write(root, 'rows.bin', sig, got)
    return _Corpus(root, sig, *got)


def _row_entry(s, superseded=False):
    e = dict(zip(ROW_FIELDS, s.split(US)))
    e['codes'] = _split(e['codes'])
    e['files'] = _split(e['files'])
    e['archived'] = False
    e['superseded'] = superseded
    return e


def _search_fast(root, query, type, code, file, scope, limit):
    cor = _corpus(root)
    rows = cor.rows
    total = len(rows)
    if not total:
        return []
    ok = bytearray([1]) * total
    for i in cor.sup:
        ok[i] = 0
    query = query or ''
    has_query = bool(query.strip())
    qcode_fold = {_fold(m) for m in CODE_RE.findall(query)}
    qraw = {_fold(t).strip('.,;:()[]{}"\'') for t in query.split()}
    qtokens = sorted(set(tokenize(CODE_RE.sub(' ', query))))
    if has_query and not qtokens and not qcode_fold and not qraw:
        return []

    filtered = bool(type or scope or code or file)
    idx = None
    if has_query or code:
        idx = cor.index()
    if type:
        for i in range(total):
            if ok[i] and rows[i].split(US)[2] != type:
                ok[i] = 0
    if scope:
        for i in range(total):
            if ok[i] and rows[i].split(US)[9] != scope:
                ok[i] = 0
    if code:
        allowed = set(_arr(idx[2].get(_fold(code))))
        for i in range(total):
            if ok[i] and i not in allowed:
                ok[i] = 0
    if file:
        for i in range(total):
            if ok[i] and not any(_norm_path_cmp(f, file) for f in _split(rows[i].split(US)[5])):
                ok[i] = 0
    n = ok.count(1) if (filtered or cor.sup) else total
    if not n:
        return []

    if not has_query:
        keyed = ((rows[i].split(US, 2)[1], i) for i in range(total) if ok[i])
        top = heapq.nlargest(limit, keyed) if limit >= 0 else sorted(keyed, reverse=True)[:limit]
        return [_row_entry(rows[i]) for _, i in top]

    dl, postings, codemap = idx
    dl = _arr(dl)
    avgdl = (sum(compress(dl, ok)) / n) or 1.0
    k1, b = 1.2, 0.75
    scores = {}
    for t in qtokens:
        p = _arr(postings.get(t))
        if not p:
            continue
        df = 0
        for k in range(0, len(p), 2):
            if ok[p[k]]:
                df += 1
        if not df:
            continue
        idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
        for k in range(0, len(p), 2):
            i = p[k]
            if ok[i]:
                f = p[k + 1]
                scores[i] = scores.get(i, 0.0) + idf * f * (k1 + 1) / (f + k1 * (1 - b + b * dl[i] / avgdl))
    hits = {}
    for q in qcode_fold | qraw:
        for i in _arr(codemap.get(q)):
            if ok[i]:
                hits[i] = hits.get(i, 0) + 1
    for i, c in hits.items():
        scores[i] = scores.get(i, 0.0) + CODE_BONUS * c
    ranked = ((s, rows[i].split(US, 2)[1], i) for i, s in scores.items() if s > 0)
    top = heapq.nlargest(limit, ranked) if limit >= 0 else sorted(ranked, reverse=True)[:limit]
    return [_row_entry(rows[i]) for _, _, i in top]


def _search_slow(root, query, type, code, file, scope, limit, include_archive):
    """Reference implementation over every entry (also used with the archive)."""
    all_e = _load_all(root)
    pool = [e for e in all_e if (include_archive or not e['archived'])
            and (include_archive or not e['superseded'])]
    cands = _filter(pool, type, code, file, scope)
    if not cands:
        return []
    order = {id(e): i for i, e in enumerate(all_e)}
    query = query or ''
    qcode_fold = {_fold(m) for m in CODE_RE.findall(query)}
    qraw = {_fold(t).strip('.,;:()[]{}"\'') for t in query.split()}
    rest = CODE_RE.sub(' ', query)
    qtokens = sorted(set(tokenize(rest)))
    if not query.strip():
        ranked = sorted(cands, key=lambda e: (e['date'], order[id(e)]), reverse=True)
        return ranked[:limit]
    if not qtokens and not qcode_fold and not qraw:
        return []

    docs = [(e, *_doc_terms(e)) for e in cands]
    n = len(docs)
    avgdl = (sum(d[2] for d in docs) / n) or 1.0
    df = {}
    for _, tf, _ in docs:
        for t in tf:
            df[t] = df.get(t, 0) + 1
    k1, b = 1.2, 0.75
    scored = []
    for e, tf, dl in docs:
        s = 0.0
        for t in qtokens:
            f = tf.get(t, 0)
            if not f:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            s += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * dl / avgdl))
        efold = {_fold(c) for c in e['codes']}
        s += CODE_BONUS * len(efold & (qcode_fold | qraw))
        if s > 0:
            scored.append((s, e['date'], order[id(e)], e))
    scored.sort(key=lambda r: (r[0], r[1], r[2]), reverse=True)
    return [r[3] for r in scored[:limit]]


def search(root, query='', *, type=None, code=None, file=None, scope=None, limit=10,
           include_archive=False):
    if include_archive:
        return _search_slow(root, query, type, code, file, scope, limit, True)
    return _search_fast(root, query, type, code, file, scope, limit)


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

def show(root, ids):
    all_e = _load_all(root)
    by_id = {e['id']: e for e in all_e}
    superseders = {}
    for e in all_e:
        if e['supersedes']:
            superseders.setdefault(e['supersedes'], []).append(e['id'])
    out = []
    for i in ids:
        e = by_id.get(i)
        if e is None:
            hits = [x for x in all_e if x['id'].startswith(i)] if len(i) >= 4 else []
            e = hits[0] if len(hits) == 1 else None
        if e is not None:
            e = dict(e)
            e['superseded_by'] = superseders.get(e['id'], [])
            out.append(e)
    return out


def timeline(root, id, window=3):
    all_e = [e for e in _load_all(root)]
    target = next((e for e in all_e if e['id'] == id), None)
    if target is None:
        return []
    same = [(i, e) for i, e in enumerate(all_e) if e['scope'] == target['scope']]
    same.sort(key=lambda p: (p[1]['date'], p[0]))
    pos = next(k for k, (_, e) in enumerate(same) if e['id'] == id)
    lo, hi = max(0, pos - window), min(len(same), pos + window + 1)
    return [e for _, e in same[lo:hi]]


def _file_hits(rows, supset, path):
    """Indexes of non-superseded rows mentioning `path` (same matching as _norm_path_cmp)."""
    base = path.replace('\\', '/').lower().lstrip('./').rsplit('/', 1)[-1]
    hits = []
    for i, s in enumerate(rows):
        if i in supset or base not in s.lower():
            continue
        if any(_norm_path_cmp(f, path) for f in _split(s.split(US)[5])):
            hits.append(i)
    return hits


def entries_for_file(root, path, limit=3):
    cor = _corpus(root)
    hits = _file_hits(cor.rows, set(cor.sup), path)
    keyed = [(cor.rows[i].split(US, 2)[1], i) for i in hits]
    top = heapq.nlargest(limit, keyed) if limit >= 0 else sorted(keyed, reverse=True)[:limit]
    return [_row_entry(cor.rows[i]) for _, i in top]


def stats(root):
    all_e = _load_all(root)
    by_type, by_scope = {}, {}
    for e in all_e:
        by_type[e['type']] = by_type.get(e['type'], 0) + 1
        by_scope[e['scope']] = by_scope.get(e['scope'], 0) + 1
    size = 0
    for archived in (False, True):
        for p in _scope_files(root, archived):
            try:
                size += p.stat().st_size
            except OSError:
                pass
    return {
        'entries': len(all_e),
        'active': sum(1 for e in all_e if not e['archived'] and not e['superseded']),
        'superseded': sum(1 for e in all_e if e['superseded']),
        'archived': sum(1 for e in all_e if e['archived']),
        'by_type': by_type,
        'by_scope': by_scope,
        'bytes': size,
    }


# ---------------------------------------------------------------------------
# Compaction
# ---------------------------------------------------------------------------

def _quarter(d):
    y, m = d[:4], int(d[5:7])
    return f"{y}-Q{(m - 1) // 3 + 1}"


def _archive_ids(root):
    ids = set()
    for p in _scope_files(root, True):
        _, items = _parse_lines(_read_file(p), str(p))
        ids.update(e['id'] for _, kind, _, e in items if kind == 'row' and e)
    return ids


def compact(root, before=None, apply=False):
    """Move superseded/old entries to the archive (see _compact). `apply` runs under
    the same lock as append_entries, so a concurrent add is never lost."""
    if apply:
        with _locked(root):
            return _compact(root, before, True)
    return _compact(root, before, False)


def _compact(root, before, apply):
    """Move superseded (+ older than `before`) entries to archive/<YYYY>-Q<q>.toon.

    Scope files are rewritten line-by-line (comments, header and every other line
    are preserved; only the moved rows are removed). A scope file holding anything
    unparseable that is not a row (git conflict markers, stray text) is never
    rewritten: its entries stay put and the file is listed in result['refused']."""
    if before:
        before = _norm_date(before)
    all_e = _load_all(root)
    want = {e['id']: e for e in all_e if not e['archived']
            and (e['superseded'] or (before and e['date'] < before))}

    parsed, loc, refused = {}, {}, set()
    for p in _scope_files(root):
        text = _read_file(p)
        _, items = _parse_lines(text, str(p))
        parsed[p] = (text, items)
        if any(kind == 'junk' for _, kind, _, _ in items):
            refused.add(p)
        for n, kind, _, e in items:
            if kind == 'row' and e and e['id'] not in loc:
                loc[e['id']] = (p, n)  # first occurrence = the one _load_all keeps
    moved = [e for i, e in want.items() if i in loc and loc[i][0] not in refused]
    result = {
        'moved': len(moved),
        'superseded': sum(1 for e in moved if e['superseded']),
        'files': sorted({f"archive/{_quarter(e['date'])}.toon" for e in moved}),
        'dry_run': not apply,
        'refused': sorted(p.name for p in refused if any(loc[i][0] == p for i in want if i in loc)),
    }
    if not apply or not moved:
        return result
    mdir = memory_dir(root)
    arch_fields = FIELDS + ('scope',)
    have = _archive_ids(root)
    groups = {}
    for e in moved:
        if e['id'] not in have:
            groups.setdefault(_quarter(e['date']), []).append(e)
    # 1) archive first (never lose a row), 2) then rewrite scope files.
    for q, ents in groups.items():
        path = mdir / 'archive' / f"{q}.toon"
        fields = arch_fields
        if path.exists():
            m = next((HEADER_RE.match(l.strip()) for l in _read_file(path).split('\n')
                      if HEADER_RE.match(l.strip())), None)
            if m:
                fields = tuple(f.strip() for f in m.group(2).split(','))
        _append_rows(path, 'archive', fields, ents)
    drop = {}
    for e in moved:
        p, n = loc[e['id']]
        drop.setdefault(p, set()).add(n)
    for p, lines in drop.items():
        _, items = parsed[p]
        _atomic_write(p, '\n'.join(raw for n, _, raw, _ in items if n not in lines))
    return result


# ---------------------------------------------------------------------------
# Injection text (memory is committed content: treat it as untrusted)
# ---------------------------------------------------------------------------

LINE_MAX = 160
_WS_CTRL_RE = re.compile(r'[\t\r\n\v\f\x1c-\x1f\x85  ]+')


def _clean(s, maxlen=LINE_MAX):
    """Strip control/format characters and cap the line length."""
    s = _WS_CTRL_RE.sub(' ', str(s))
    s = ''.join(ch for ch in s if unicodedata.category(ch)[0] != 'C').strip()
    return s if len(s) <= maxlen else s[:maxlen - 1].rstrip() + '…'


def _cap_lines(header, body, footer, max_chars):
    header = _clean(header)
    body = [_clean(b) for b in body]
    footer = _clean(footer) if footer else ''

    def total():
        parts = [header] + body + ([footer] if footer else [])
        return len('\n'.join(parts))

    while body and total() > max_chars:
        body.pop()
    if total() > max_chars:
        footer = ''
    if total() > max_chars:
        return ''
    return '\n'.join([header] + body + ([footer] if footer else []))


def _line(e):
    return f"{e['id']} {e['type']} {e['title']}"


def inject_text(root, max_chars=1500):
    cor = _corpus(root)
    rows = cor.rows
    sup = set(cor.sup)
    active = len(rows) - len(sup)
    if not active:
        return ''
    own, imported = [], []
    for i, s in enumerate(rows):
        if i in sup:
            continue
        r = s.split(US)
        if r[2] in KEY_TYPES:
            (imported if r[8] == 'import' else own).append((r[1], i))
    pick = heapq.nlargest(5, own)
    if len(pick) < 5:
        pick += heapq.nlargest(5 - len(pick), imported)
    header = f"AIDD memory — {active} entries."
    footer = "Search: aidd mem search <q> · Detail: aidd mem show <id>"
    return _cap_lines(header, [_line(_row_entry(rows[i])) for _, i in pick], footer, max_chars)


def file_context_text(root, path, limit=3, max_chars=600):
    hits = entries_for_file(root, path, limit)
    if not hits:
        return ''
    header = f"AIDD memory for {path}:"
    text = _cap_lines(header, [_line(e) for e in hits], '', max_chars)
    return text if '\n' in text else ''


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parser_class():
    import argparse

    class _Parser(argparse.ArgumentParser):
        def error(self, message):
            self.print_usage(sys.stderr)
            print(f"aidd-memory: error: {message}", file=sys.stderr)
            raise SystemExit(1)

    return _Parser


def _brief(e):
    return f"{e['id']}  {e['date']}  {e['type']}  [{','.join(e['codes'])}]  {e['title']}"


def _public(e, full=False):
    keys = ['id', 'date', 'type', 'title', 'codes', 'scope']
    if full:
        keys = list(FIELDS) + ['scope', 'archived', 'superseded', 'superseded_by']
    return {k: e[k] for k in keys if k in e}


def _print_full(e):
    flag = []
    if e.get('superseded'):
        flag.append('SUPERSEDED')
    if e.get('archived'):
        flag.append('ARCHIVED')
    print(f"{e['id']}  {e['date']}  {e['type']}  scope={e['scope']}" + (f"  ({', '.join(flag)})" if flag else ''))
    print(f"  title: {e['title']}")
    print(f"  codes: {', '.join(e['codes'])}")
    print(f"  files: {', '.join(e['files'])}")
    print(f"  why: {e['why']}")
    if e['supersedes']:
        print(f"  supersedes: {e['supersedes']}")
    if e.get('superseded_by'):
        print(f"  superseded_by: {', '.join(e['superseded_by'])}")
    print(f"  source: {e['source']}")


def _build_parser():
    import argparse
    _Parser = _parser_class()
    common = _Parser(add_help=False)
    common.add_argument('--root', default=argparse.SUPPRESS)
    p = _Parser(prog='aidd_memory', parents=[common],
                description='AIDD memory: curated, code-anchored, git-versioned.')
    sub = p.add_subparsers(dest='cmd', parser_class=_Parser)

    a = sub.add_parser('add', parents=[common])
    a.add_argument('--type', required=True)
    a.add_argument('--title', required=True)
    a.add_argument('--why', default='')
    a.add_argument('--codes', default='')
    a.add_argument('--files', default='')
    a.add_argument('--scope', default='project')
    a.add_argument('--supersedes', default='')
    a.add_argument('--source', default='agent')
    a.add_argument('--date', default=None)

    s = sub.add_parser('search', parents=[common])
    s.add_argument('words', nargs='*')
    s.add_argument('--type')
    s.add_argument('--code')
    s.add_argument('--file')
    s.add_argument('--scope')
    s.add_argument('--limit', type=int, default=10)
    s.add_argument('--archive', action='store_true')
    s.add_argument('--json', action='store_true')

    sh = sub.add_parser('show', parents=[common])
    sh.add_argument('ids', nargs='+')
    sh.add_argument('--json', action='store_true')

    t = sub.add_parser('timeline', parents=[common])
    t.add_argument('id')
    t.add_argument('--window', type=int, default=3)

    f = sub.add_parser('file', parents=[common])
    f.add_argument('path')
    f.add_argument('--limit', type=int, default=3)

    i = sub.add_parser('inject', parents=[common])
    i.add_argument('--max-chars', type=int, default=None)
    i.add_argument('--file', default=None)

    c = sub.add_parser('compact', parents=[common])
    c.add_argument('--before', default=None)
    c.add_argument('--apply', action='store_true')

    sub.add_parser('stats', parents=[common])

    im = sub.add_parser('import-claude-mem', parents=[common])
    im.add_argument('db')
    im.add_argument('--project', action='append', required=True)
    im.add_argument('--include', default='')
    im.add_argument('--since', default=None)
    im.add_argument('--scope', default='project')
    im.add_argument('--no-summaries', action='store_true')
    im.add_argument('--dry-run', action='store_true')
    return p


def _split_csv(s):
    return [x.strip() for x in re.split(r'[,|]', s or '') if x.strip()]


def _cmd_import(ns, root):
    import sqlite3
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import aidd_memory_import as imp
    except ImportError as e:
        print(f"aidd-memory: import-claude-mem unavailable: cannot import aidd_memory_import ({e})",
              file=sys.stderr)
        return 1
    kwargs = dict(projects=ns.project, include_summaries=not ns.no_summaries,
                  since=ns.since, scope=ns.scope, dry_run=ns.dry_run)
    inc = _split_csv(ns.include)
    if inc:
        kwargs['types'] = tuple(getattr(imp, 'DEFAULT_TYPES', ())) + tuple(inc)
    try:
        res = imp.import_claude_mem(ns.db, root, **kwargs)
    except (ValueError, OSError, sqlite3.Error) as e:
        print(f"aidd-memory: import failed: {e}", file=sys.stderr)
        return 1
    for k, v in (res.items() if isinstance(res, dict) else []):
        print(f"{k}: {v}")
    return 0


def main(argv=None):
    parser = _build_parser()
    ns = parser.parse_args(argv)
    if not ns.cmd:
        parser.print_help(sys.stderr)
        return 1
    root = Path(getattr(ns, 'root', None)) if getattr(ns, 'root', None) else find_root()

    if ns.cmd == 'add':
        try:
            existing = _known_ids(root)
            eid = add_entry(root, type=ns.type, title=ns.title, why=ns.why,
                            codes=_split_csv(ns.codes), files=_split_csv(ns.files),
                            scope=ns.scope, supersedes=ns.supersedes, source=ns.source,
                            date=ns.date)
        except (ValueError, OSError) as e:
            print(f"aidd-memory: {e}", file=sys.stderr)
            return 1
        if eid in existing:
            print("aidd-memory: entry already exists (skipped)", file=sys.stderr)
        print(eid)
        return 0

    if ns.cmd == 'search':
        hits = search(root, ' '.join(ns.words), type=ns.type, code=ns.code, file=ns.file,
                      scope=ns.scope, limit=ns.limit, include_archive=ns.archive)
        if not hits:
            print("No memory entries found.", file=sys.stderr)
            return 2
        if ns.json:
            import json
            print(json.dumps([_public(e) for e in hits], ensure_ascii=False, indent=2))
        else:
            for e in hits:
                print(_brief(e))
        return 0

    if ns.cmd == 'show':
        hits = show(root, ns.ids)
        if not hits:
            print("No memory entries found.", file=sys.stderr)
            return 2
        if ns.json:
            import json
            print(json.dumps([_public(e, True) for e in hits], ensure_ascii=False, indent=2))
        else:
            for e in hits:
                _print_full(e)
        return 0

    if ns.cmd == 'timeline':
        hits = timeline(root, ns.id, ns.window)
        if not hits:
            print("No memory entries found.", file=sys.stderr)
            return 2
        for e in hits:
            print(('* ' if e['id'] == ns.id else '  ') + _brief(e))
        return 0

    if ns.cmd == 'file':
        hits = entries_for_file(root, ns.path, ns.limit)
        if not hits:
            print("No memory entries found.", file=sys.stderr)
            return 2
        for e in hits:
            print(_brief(e))
        return 0

    if ns.cmd == 'inject':
        if ns.file:
            text = file_context_text(root, ns.file,
                                     max_chars=600 if ns.max_chars is None else ns.max_chars)
        else:
            text = inject_text(root, 1500 if ns.max_chars is None else ns.max_chars)
        if text:
            print(text)
        return 0

    if ns.cmd == 'compact':
        try:
            r = compact(root, before=ns.before, apply=ns.apply)
        except (ValueError, OSError) as e:
            print(f"aidd-memory: {e}", file=sys.stderr)
            return 1
        mode = 'dry-run' if r['dry_run'] else 'applied'
        print(f"compact ({mode}): moved={r['moved']} superseded={r['superseded']}")
        for fn in r['files']:
            print(f"  -> {fn}")
        if r['dry_run'] and r['moved']:
            print("(nothing written; re-run with --apply)")
        if r.get('refused'):
            print("aidd-memory: not rewritten (unparseable non-row lines, e.g. git conflict markers; "
                  "resolve them first): " + ', '.join(r['refused']), file=sys.stderr)
            return 1
        return 0

    if ns.cmd == 'stats':
        st = stats(root)
        print(f"entries: {st['entries']} (active {st['active']}, superseded {st['superseded']}, archived {st['archived']})")
        print("by_type: " + ', '.join(f"{k}={v}" for k, v in sorted(st['by_type'].items())))
        print("by_scope: " + ', '.join(f"{k}={v}" for k, v in sorted(st['by_scope'].items())))
        print(f"bytes: {st['bytes']}")
        return 0

    if ns.cmd == 'import-claude-mem':
        return _cmd_import(ns, root)

    return 1


if __name__ == '__main__':
    sys.exit(main())
