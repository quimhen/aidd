#!/usr/bin/env python3
"""aidd_memory_import -- one-shot, read-only importer from a claude-mem SQLite DB.

Reads observations / session_summaries and appends curated AIDD-TOON memory entries
(source=import). Never writes to the claude-mem DB, never imports claude-mem code,
never starts its worker. Stdlib only.
"""
import json
import re
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aidd_memory as mem  # noqa: E402

DEFAULT_TYPES = ('decision', 'bugfix', 'bug-fix', 'fix', 'fix-applied', 'remediation',
                 'security_alert', 'security_note', 'critical', 'critical-success')

TYPE_MAP = {
    'decision': 'decision',
    'bugfix': 'bugfix', 'bug-fix': 'bugfix', 'fix': 'bugfix',
    'fix-applied': 'bugfix', 'remediation': 'bugfix',
    'security_alert': 'risk', 'security_note': 'risk',
    'critical': 'risk', 'critical-success': 'risk',
}

IMPORT_CODE_RE = re.compile(r'SCREEN-\d+(?:-F\d+)?|CTL-\d+|COMP-\d+|API-\d+|US-\d+')


def _open_ro(path):
    """Return (connection, tmpdir_or_None). Direct read-only first; copy fallback."""
    p = Path(path)
    if not p.is_file():
        raise ValueError(f"claude-mem db not found: {path}")
    uri = f"file:{p.resolve().as_posix()}?mode=ro"
    try:
        con = sqlite3.connect(uri, uri=True)
        con.execute("select count(*) from sqlite_master").fetchone()
        return con, None
    except sqlite3.Error:
        pass
    tmp = tempfile.mkdtemp(prefix='aidd-import-')
    try:
        for suffix in ('', '-wal', '-shm'):
            src = Path(str(p) + suffix)
            if src.is_file():
                shutil.copy2(src, Path(tmp) / (p.name + suffix))
        con = sqlite3.connect(f"file:{(Path(tmp) / p.name).as_posix()}?mode=ro", uri=True)
        con.execute("select count(*) from sqlite_master").fetchone()
        return con, tmp
    except sqlite3.Error as e:
        shutil.rmtree(tmp, ignore_errors=True)
        raise ValueError(f"cannot open claude-mem db read-only: {e}")


def _parse_list(v):
    """Tolerant: JSON array / JSON scalar / plain text (split on newlines)."""
    if v is None:
        return []
    if isinstance(v, bytes):
        v = v.decode('utf-8', 'replace')
    v = str(v).strip()
    if not v:
        return []
    if v[0] in '[{"':
        try:
            data = json.loads(v)
            if isinstance(data, list):
                out = []
                for x in data:
                    out.append(x if isinstance(x, str) else json.dumps(x, ensure_ascii=False))
                return [x.strip() for x in out if x and x.strip()]
            if isinstance(data, str):
                return [data.strip()] if data.strip() else []
        except ValueError:
            pass
    return [x.strip() for x in re.split(r'[\r\n]+', v) if x.strip()]


def _parse_files(v):
    out = []
    for item in _parse_list(v):
        if '\n' not in item and ',' in item and not item.startswith('['):
            # plain comma-separated text
            out.extend(x.strip() for x in item.split(',') if x.strip())
        else:
            out.append(item)
    return out


def _flat(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def _date_of(created):
    m = re.match(r'(\d{4}-\d{2}-\d{2})', str(created or '').strip())
    return m.group(1) if m else None


def _codes(*texts):
    seen, out = set(), []
    for t in texts:
        for c in IMPORT_CODE_RE.findall(t or ''):
            if c not in seen:
                seen.add(c)
                out.append(c)
    return out


# --- file normalisation (amendment 7) -------------------------------------------------
# Plausible repo path: POSIX chars only (no spaces/parentheses/brackets), last segment has an extension.
_PATH_OK_RE = re.compile(r'^[\w@+.\-]+(?:/[\w@+.\-]+)*\.[A-Za-z0-9]{1,10}$')
_ABS_RE = re.compile(r'^(?:[A-Za-z]:/|/|~/)')
_BAD_FIRST_SEG = frozenset(('users', 'home', 'appdata', 'temp', 'tmp', 'var', 'etc', 'usr', 'opt', 'windows'))
_BAD_SEG_MARKERS = ('/appdata/', '/.claude/', '/scratchpad/', '/node_modules/')


def _norm_repo_file(f, root):
    """Return a project-relative POSIX path, or None when `f` is junk / outside the root."""
    f = str(f or '').strip().strip('\'"`').replace(chr(92), '/')
    if not f or any(c in f for c in ' \t()[]{}<>|*?;,'):
        return None
    while f.startswith('./'):
        f = f[2:]
    if _ABS_RE.match(f):
        r = Path(root).resolve().as_posix().rstrip('/')
        if f.lower() == r.lower() or not f.lower().startswith(r.lower() + '/'):
            return None  # absolute path outside the destination root (plans, scratchpads...)
        f = f[len(r) + 1:]
    if '..' in f.split('/') or not _PATH_OK_RE.match(f):
        return None
    segs = f.split('/')
    if segs[0].lower() in _BAD_FIRST_SEG or segs[0].lower().startswith('program'):
        return None
    wrapped = '/' + f.lower() + '/'
    if any(m in wrapped for m in _BAD_SEG_MARKERS):
        return None
    return f


def _files(modified, read, root):
    fs = _parse_files(modified) or _parse_files(read)
    out = []
    for f in fs:
        nf = _norm_repo_file(f, root)
        if nf and nf not in out:
            out.append(nf)
    return out


# --- scrub step (amendment 7): secrets / internal addresses -> [redacted] ---------------
_KEY = r'[\w-]*(?:password|passwd|pwd|secret|token|api[_-]?key|apikey|connection[_-]?string|connectionstring)[\w-]*'
_PROFILE_RE = re.compile(
    r'(?i)(?<![\w.-])(?:[A-Za-z]:)?[\\/]+(?:users|home)[\\/]+[^\\/\s"\'<>|:*?]+(?:[\\/][^\s"\'<>|]*)?'
    r'|%USERPROFILE%(?:[\\/][^\s"\'<>|]*)?')
_UNC_RE = re.compile(r'(?<![\w\\])\\\\[\w.$-]+(?:\\[^\s\\"\'<>|]+)*')
_URLCRED_RE = re.compile(r'://[^\s/:@]+:[^\s/@]+@')
_AUTH_RE = re.compile(r'(?i)\bauthorization\s*:\s*\S+(?:[ \t]+\S+)?')
_EMAIL_RE = re.compile(r'[\w.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+')


def _profile_sub(m):
    s = m.group(0)
    if s.upper().startswith('%USERPROFILE%'):
        tail = s[len('%USERPROFILE%'):]
    else:
        parts = re.split(r'[\\/]+', re.sub(r'^(?:[A-Za-z]:)?[\\/]+', '', s))
        tail = '/' + '/'.join(parts[2:]) if len(parts) > 2 else ''
    return '~' + tail.replace(chr(92), '/')


_SCRUB_RES = [
    re.compile(r'eyJ[\w-]+\.[\w-]+\.[\w-]+'),
    re.compile(r'\bsk-[\w-]{16,}'),
    re.compile(r'\bghp_\w{20,}'),
    re.compile(r'\bxox[abp]-[\w-]+'),
    re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
    re.compile(r'(?i)\b' + _KEY + r'\s*[:=]\s*(?:"[^"]*"|\'[^\']*\'|[^\s"\',;]+)'),
    re.compile(r'(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}'),
    re.compile(r'(?i)\bbearer\s*[:=]\s*[^\s"\',;]+'),
    re.compile(r'(?<![0-9A-Fa-f])[0-9A-Fa-f]{32,}(?![0-9A-Fa-f])'),
    re.compile(r'(?<![\d.])(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}'
               r'|192\.168\.\d{1,3}\.\d{1,3}|127\.\d{1,3}\.\d{1,3}\.\d{1,3})(?![\d])'),
]


def _scrub(text):
    t = str(text or '')
    t = _PROFILE_RE.sub(_profile_sub, t)
    t = _UNC_RE.sub('[redacted-unc]', t)
    t = _URLCRED_RE.sub('://[redacted]@', t)
    t = _AUTH_RE.sub('Authorization: [redacted]', t)
    t = _EMAIL_RE.sub('[redacted-email]', t)
    for rx in _SCRUB_RES:
        t = rx.sub('[redacted]', t)
    return t


# --- title quality ---------------------------------------------------------------------
# Rule (conservative): a title that is ONLY a generic prefix ("Continuation:", "Analysis of", ...) carries no
# content -> treated as empty (falls back to why, else skipped). A leading "Continuation:"/"Continuacion:" is
# dropped when text remains; a leading "Analysis of " is dropped only when 2+ words remain and they do not start with an article. Nothing else changes.
_GENERIC_ONLY_RE = re.compile(
    r'^(?:continuation|continuaci[oó]n|analysis(?: of)?|an[aá]lisis(?: de)?|request|session|summary|task)'
    r'\s*[:\-–.]*\s*$', re.I)
_CONT_RE = re.compile(r'^(?:continuation|continuaci[oó]n)\s*:\s*', re.I)
_ANALYSIS_RE = re.compile(r'^analysis of\s+(?!(?:the|a|an|this|that|these|those)\b)(?=\S+\s+\S)', re.I)


def _clean_title(t):
    t = _flat(t)
    if not t or _GENERIC_ONLY_RE.match(t):
        return ''
    t2 = _CONT_RE.sub('', t)
    t2 = _ANALYSIS_RE.sub('', t2)
    if t2 != t and t2 and not _GENERIC_ONLY_RE.match(t2):
        t = t2[0].upper() + t2[1:]
    return t


def _title_fallback(*texts):
    for t in texts:
        t = _flat(t)
        if t:
            return ' '.join(t.split(' ')[:12])
    return ''


def _build(scope, root, kind, date, title, why, codes, files):
    title = mem._trunc(_scrub(_clean_title(title)), mem.TITLE_MAX)
    why = mem._trunc(_scrub(why), mem.WHY_MAX)
    if not title:
        title = mem._trunc(_scrub(_clean_title(_title_fallback(why))), mem.TITLE_MAX)
    if not title or (not why and not codes and not files):
        return None
    return {
        'id': mem.make_id(scope, date, title), 'date': date, 'type': kind,
        'title': title, 'codes': codes, 'files': files, 'why': why,
        'supersedes': '', 'source': 'import',
    }


def _columns(con, table):
    return {r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}


def _select(con, table, wanted, required, any_of=()):
    """Build a column list selecting only existing columns (missing optional ones -> NULL)."""
    have = _columns(con, table)
    if not have:
        raise ValueError(f"not a claude-mem database: missing table {table}")
    missing = [c for c in required if c not in have]
    if missing:
        raise ValueError(f"not a claude-mem database: table {table} lacks column(s) {', '.join(missing)}")
    if any_of and not any(c in have for c in any_of):
        raise ValueError(f"not a claude-mem database: table {table} lacks all of {', '.join(any_of)}")
    return ','.join(c if c in have else f"NULL AS {c}" for c in wanted)


def _like_clause(projects):
    esc = lambda s: s.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    clause = ' OR '.join("project LIKE ? ESCAPE '\\'" for _ in projects)
    return f"({clause})", [f"%{esc(p)}%" for p in projects]


def import_claude_mem(db_path, root, *, projects, types=DEFAULT_TYPES,
                      include_summaries=True, since=None, scope='project', dry_run=False):
    if isinstance(projects, str):
        projects = [projects]
    projects = [p for p in (projects or []) if p and p.strip()]
    if not projects:
        raise ValueError("at least one project substring is required")
    mem._validate_scope(scope)
    since_d = mem._norm_date(since) if since else None
    types = tuple(types or ())

    counts = {t: 0 for t in mem.TYPES if t in set(TYPE_MAP.values()) or t == 'discovery'}
    result = {'summaries': 0, 'skipped': 0, 'written': 0, 'dry_run': bool(dry_run)}
    skipped = 0
    candidates = []
    summary_ids = set()

    con, tmp = _open_ro(db_path)
    try:
        con.row_factory = sqlite3.Row
        where, params = _like_clause(projects)
        if types:
            ph = ','.join('?' for _ in types)
            cols = _select(con, 'observations',
                           ('type', 'title', 'subtitle', 'facts', 'narrative', 'files_read',
                            'files_modified', 'created_at'),
                           ('project', 'type', 'title', 'created_at'), any_of=('narrative', 'facts'))
            rows = con.execute(
                f"SELECT {cols} FROM observations WHERE {where} AND type IN ({ph}) "
                f"ORDER BY created_at, rowid", params + list(types)).fetchall()
        else:
            _select(con, 'observations', (), ('project', 'type', 'title', 'created_at'))
            rows = []
        for r in rows:
            date = _date_of(r['created_at'])
            if not date or (since_d and date < since_d):
                if date is None:
                    skipped += 1
                continue
            kind = TYPE_MAP.get(r['type'], 'discovery')
            facts = _parse_list(r['facts'])
            narrative = _flat(r['narrative'])
            title = _clean_title(r['title']) or _title_fallback(r['subtitle'], narrative, ' '.join(facts))
            why = narrative or '; '.join(facts)
            e = _build(scope, root, kind, date, title, why,
                       _codes(title, ' '.join(facts), narrative),
                       _files(r['files_modified'], r['files_read'], root))
            if e is None:
                skipped += 1
                continue
            candidates.append(e)

        if include_summaries:
            scols = _select(con, 'session_summaries',
                            ('request', 'learned', 'completed', 'files_read', 'files_edited', 'created_at'),
                            ('project', 'request', 'created_at'), any_of=('learned', 'completed'))
            srows = con.execute(
                f"SELECT {scols} FROM session_summaries WHERE {where} "
                f"ORDER BY created_at, rowid", params).fetchall()
            for r in srows:
                date = _date_of(r['created_at'])
                if not date:
                    skipped += 1
                    continue
                if since_d and date < since_d:
                    continue
                title = _clean_title(r['request'])
                why = _flat(r['learned']) or _flat(r['completed'])
                if not title:
                    title = _title_fallback(why)
                e = _build(scope, root, 'discovery', date, title, why,
                           _codes(title, why), _files(r['files_edited'], r['files_read'], root))
                if e is None:
                    skipped += 1
                    continue
                e['_summary'] = True
                candidates.append(e)
    finally:
        con.close()
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)

    try:
        existing = {e['id'] for e in mem.load_entries(root, include_archive=True)}
    except Exception:
        existing = set()
    fresh = []
    for e in candidates:
        if e['id'] in existing:
            skipped += 1
            continue
        existing.add(e['id'])
        fresh.append(e)
    for e in fresh:
        counts[e['type']] += 1
        if e.pop('_summary', False):
            result['summaries'] += 1
    for e in fresh:
        e.pop('_summary', None)

    if fresh and not dry_run:
        written = mem.append_entries(root, scope, fresh)
        result['written'] = len(written)
    else:
        result['written'] = 0
    out = dict(counts)
    out.update(result)
    out['skipped'] = skipped
    out['would_write'] = len(fresh)
    return out
