#!/usr/bin/env python3
"""AIDD evidence log: an append-only record of what hooks *observed* (user prompts,
subagent dispatches, questions/answers, code/spec edits, find_spec runs). Hooks write it, gates
read it; the agent never writes it (rule R9). Stdlib only, Windows-safe.

Storage is split by scope (spec 002 Rev 2, D1b/D5):
  SESSION kinds (prompt, subagent, question, answer, find_spec, session_start, hook_error) live in a
    per-session log  <tempdir>/aidd-hooks/evidence/<sanitised-session-id>.toon  (shared
    `unknown-session` file when there is no id) — never inside a project directory.
  PROJECT kinds (spec_edit, code_edit, approved, spec_closed, stop_block, stop_block_exhausted) live in
    <known root>/.aidd/evidence/events.toon  (+ .gitignore '*'), written ONLY when a project root
    (an ancestor with specs/ or .aidd/) exists — nothing is recorded, and no `.aidd` is created,
    otherwise. spec_edit/code_edit are written to EVERY root in project_roots(target).
  <root>/.aidd/active_spec  two lines: spec id, since-ts  (INFORMATIONAL pointer only; no gate reads it)
Rows are AIDD-TOON: ts,session,kind,detail (detail = one-line JSON).

Env `AIDD_EVIDENCE_DIR` is honoured ONLY together with `AIDD_TESTING=1`: session logs then go to
<dir>/sessions/, the project log to <dir>/events.toon and the active_spec pointer to <dir>/.

Concurrency choice: writes take an O_CREAT|O_EXCL lock file (same technique as
aidd_memory._locked) instead of relying on a bare O_APPEND write. Reason: the file also
needs a header on first write and a rewrite on rotation, neither of which is atomic with a
plain append; one short lock makes header + row + rotation a single critical section and
guarantees no lost rows. Cost is ~1 ms uncontended. append() is best-effort: on lock
timeout or any I/O error the row is dropped silently (a hook must never break a session).

Row integrity (B2): every row is passed through sanitize_line and readers split on '\\n' ONLY
(never str.splitlines, which also splits on U+2028/U+0085/VT/FF/FS-RS), so no payload can
forge an extra event.
"""
import contextlib
import csv
import io
import json
import os
import random
import re
import shlex
import tempfile
import time
import unicodedata
from pathlib import Path

EVIDENCE_DIR_REL = Path('.aidd') / 'evidence'
EVENTS_REL = EVIDENCE_DIR_REL / 'events.toon'
ACTIVE_SPEC_REL = Path('.aidd') / 'active_spec'
HEADER = 'version: 1\nevents[*]{ts,session,kind,detail}:\n'

MAX_BYTES = 5 * 1024 * 1024
KEEP_ROWS = 2000
LOCK_TIMEOUT = 3.0
LOCK_STALE = 10.0
MAX_PROMPT_CHARS = 4000


# ---------------------------------------------------------------------------
# Credential redaction (spec 003 T-05, plan Contract 8)
# ---------------------------------------------------------------------------

MAX_REDACT_INPUT = 20000
_SECRET_KEY = (r'password|passwd|pwd|clave|contrase[ñn]a|secret|token|api[_ -]?key')
# keyword, bounded suffix (e.g. db_password, token_value), `=` or `:` (optionally `es`/`is`), then the
# value: quoted (<=200 chars) or a bare run (<=200 chars). Bounded quantifiers only, no nesting.
_SECRET_RE = re.compile(
    r'(' + _SECRET_KEY + r')[\w-]{0,40}[ ]{0,3}(?:(?:es|is)[ ]{1,3})?[=:][ ]{0,3}'
    r'(?:"[^"]{1,200}"|\'[^\']{1,200}\'|[^\s"\',;]{1,200})',
    re.I)
_BEARER_RE = re.compile(r'(bearer)[ ]{1,3}[A-Za-z0-9._~+/=-]{8,500}', re.I)


def _secret_label(raw):
    k = re.sub(r'[ _-]', '', raw.lower())
    return 'apikey' if k == 'apikey' else k


def redact_secrets(text, limit=None):
    """(redacted_text, labels). Order: cap input at 20,000 chars, collapse whitespace, redact
    `<keyword>=<value>` pairs (and `Bearer <token>`) to `label=[redacted]`, THEN truncate to
    MAX_PROMPT_CHARS (or `limit`) so a secret cut by the limit is never left half-exposed.
    Linear time (bounded quantifiers). Never raises: on error returns ('', [])."""
    try:
        s = re.sub(r'\s+', ' ', str('' if text is None else text)[:MAX_REDACT_INPUT]).strip()
        labels = []

        def _sub(m):
            lab = _secret_label(m.group(1))
            if lab not in labels:
                labels.append(lab)
            return lab + '=[redacted]'
        s = _SECRET_RE.sub(_sub, s)
        s = _BEARER_RE.sub(_sub, s)
        return s[:(limit or MAX_PROMPT_CHARS)], labels
    except Exception:
        return '', []


# ---------------------------------------------------------------------------
# Roots and locations
# ---------------------------------------------------------------------------

def find_root(start=None):
    """Nearest ancestor of `start` (default cwd) containing specs/ or .aidd/; else start."""
    cur = Path(start or Path.cwd()).resolve()
    for d in [cur] + list(cur.parents):
        if (d / 'specs').is_dir() or (d / '.aidd').is_dir():
            return d
    return cur


def known_root(start=None):
    """Like find_root but None when no ancestor has specs/ or .aidd/ (no guessing)."""
    try:
        cur = Path(start or Path.cwd()).resolve()
        for d in [cur] + list(cur.parents):
            if (d / 'specs').is_dir() or (d / '.aidd').is_dir():
                return d
    except Exception:
        pass
    return None


SESSION_KINDS = frozenset({'prompt', 'subagent', 'question', 'answer', 'find_spec', 'session_start', 'hook_error'})
PROJECT_KINDS = frozenset({'spec_edit', 'code_edit', 'approved', 'spec_closed', 'stop_block',
                           'stop_block_exhausted'})
HOOKS_TMP = Path(tempfile.gettempdir()) / 'aidd-hooks'


def _test_dir():
    """AIDD_EVIDENCE_DIR, honoured only when AIDD_TESTING=1 is also set."""
    env = os.environ.get('AIDD_EVIDENCE_DIR')
    if env and os.environ.get('AIDD_TESTING') == '1':
        return Path(env)
    return None


def _sessions_dir():
    t = _test_dir()
    return (t / 'sessions') if t is not None else (HOOKS_TMP / 'evidence')


def _safe_sid(session):
    s = re.sub(r'[^\w.-]', '_', str(session or '')).strip('.')[:100]
    if re.match(r'^(con|prn|aux|nul|com\d|lpt\d)(\..*)?$', s, re.I):     # Windows device names
        s = '_' + s
    return s or 'unknown-session'


def _session_path(session):
    return _sessions_dir() / (_safe_sid(session) + '.toon')


def _project_dir(root):
    """Directory of the project log for `root`, or None (no known root => nothing recorded)."""
    t = _test_dir()
    if t is not None:
        return t
    if root is None:
        return None
    r = Path(root)
    if (r / 'specs').is_dir() or (r / '.aidd').is_dir():
        return r / EVIDENCE_DIR_REL
    kr = known_root(r)
    return (kr / EVIDENCE_DIR_REL) if kr is not None else None


def _project_path(root):
    d = _project_dir(root)
    return (d / 'events.toon') if d is not None else None


def _evdir(root):          # kept for callers/tests: the project evidence directory
    return _project_dir(root)


def _events_path(root):    # kept for callers/tests: the project log path
    return _project_path(root)


def _active_path(root):
    t = _test_dir()
    if t is not None:
        return t / 'active_spec'
    return Path(root) / ACTIVE_SPEC_REL


def is_session_log_path(path):
    """True iff `path` (canonical) is at or under <tempdir>/aidd-hooks (R9 support)."""
    try:
        c = canon_path(path)
        b = canon_path(HOOKS_TMP).rstrip('/')
        return c == b or c.startswith(b + '/')
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Sanitising and canonical paths (B2, B3)
# ---------------------------------------------------------------------------

_CTRL_RE = re.compile('[\x00-\x1f\x7f-\x9f  ]')


def sanitize_line(text):
    """Replace every control char and Unicode line/paragraph separator (U+2028/2029/0085,
    VT, FF, FS/GS/RS/US, CR, LF, ...) with a space so a value can never span or forge a row."""
    return _CTRL_RE.sub(' ', '' if text is None else str(text))


def _strip_win_prefix(s):
    if s.startswith('\\\\?\\UNC\\'):
        s = '\\\\' + s[8:]
    elif s.startswith('\\\\?\\') or s.startswith('\\\\.\\'):
        s = s[4:]
    names = ['localhost', r'127\.0\.0\.1', r'\[?::1\]?']
    comp = os.environ.get('COMPUTERNAME')
    if comp:
        names.append(re.escape(comp))
    m = re.match(r'^\\\\(?:' + '|'.join(names) + r')\\([A-Za-z])\$(?:\\(.*))?$', s, re.I)
    if m:
        s = m.group(1) + ':\\' + (m.group(2) or '')
    return s


def _long_name(path):
    """Windows 8.3 -> long names (best effort; for a non-existent tail, resolve the deepest
    existing ancestor and re-append the rest)."""
    if os.name != 'nt':
        return path
    try:
        import ctypes
        fn = ctypes.windll.kernel32.GetLongPathNameW
        fn.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
        fn.restype = ctypes.c_uint

        def conv(p):
            buf = ctypes.create_unicode_buffer(32768)
            n = fn(p, buf, 32768)
            return buf.value if 0 < n < 32768 else None
        tail = []
        cur = path
        for _ in range(64):
            got = conv(cur)
            if got:
                return os.path.join(got, *reversed(tail)) if tail else got
            parent, name = os.path.split(cur)
            if not name or parent == cur:
                break
            tail.append(name)
            cur = parent
    except Exception:
        pass
    return path


def real_path(p, root=None):
    """Resolved absolute path in native case: prefixes/streams/trailing dots+spaces removed,
    `..` resolved, junctions/symlinks followed, 8.3 expanded. Never raises."""
    try:
        s = str(os.fspath(p)).replace('\x00', '')
        nt = os.name == 'nt'
        if nt:
            s = s.replace('/', '\\')
            s = _strip_win_prefix(s)
        drive, rest = os.path.splitdrive(s)
        sep = '\\' if nt else '/'
        segs = []
        for seg in rest.split(sep):
            if seg in ('', '.', '..'):
                segs.append(seg)
                continue
            if nt:
                seg = seg.split(':', 1)[0].rstrip('. ')
                if not seg:
                    continue
            segs.append(seg)
        s = drive + sep.join(segs)
        if not os.path.isabs(s):
            s = os.path.join(str(root) if root is not None else os.getcwd(), s)
        s = os.path.abspath(s)
        s = os.path.realpath(s)
        if nt:
            s = _strip_win_prefix(s)
            s = _long_name(s)
        return Path(s)
    except Exception:
        return Path(str(p))


def canon_path(p, root=None):
    """Comparable absolute path (str): real_path + normcase + forward slashes, no trailing slash."""
    s = os.path.normcase(str(real_path(p, root))).replace('\\', '/')
    if len(s) > 1 and s.endswith('/') and not re.fullmatch(r'[a-z]:/', s):
        s = s.rstrip('/')
    return s


def rel_to_root(path, root):
    """Canonical posix path of `path` relative to `root`; '' for the root itself; None if outside."""
    c = canon_path(path, root)
    r = canon_path(root).rstrip('/')
    if c == r:
        return ''
    if c.startswith(r + '/'):
        return c[len(r) + 1:]
    return None


def project_roots(path):
    """EVERY ancestor dir (nearest first) that contains specs/ or .aidd/."""
    out = []
    try:
        rp = real_path(path)
        start = rp if rp.is_dir() else rp.parent
        for d in [start] + list(start.parents):
            if (d / 'specs').is_dir() or (d / '.aidd').is_dir():
                out.append(d)
    except Exception:
        pass
    return out


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def _locked(d):
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    path = d / '.lock'
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
                if time.time() - path.stat().st_mtime > LOCK_STALE:
                    path.unlink()
                    continue
            except OSError:
                pass
            if time.monotonic() >= deadline:
                raise OSError('evidence lock timeout')
            time.sleep(0.002 + random.random() * 0.01)
    try:
        yield
    finally:
        try:
            path.unlink()
        except OSError:
            pass


_JSON_ESC = {c: '\\u%04x' % ord(c) for c in [chr(i) for i in range(0x7f, 0xa0)] + [' ', ' ']}


def _row(ts, session, kind, detail):
    js = json.dumps(detail, ensure_ascii=False, separators=(',', ':'))
    js = ''.join(_JSON_ESC.get(c, c) for c in js)          # keep the data, as JSON escapes
    buf = io.StringIO()
    csv.writer(buf, lineterminator='').writerow([f'{ts:.3f}', sanitize_line(session), sanitize_line(kind), js])
    return '  ' + sanitize_line(buf.getvalue()) + '\n'      # backstop: always one physical line


def _read_rows(path):
    """Row lines of the log. Splits on '\\n' ONLY (B2)."""
    data = Path(path).read_bytes().decode('utf-8', errors='replace')
    return [ln for ln in data.split('\n') if ln.startswith('  ')]


def _rotate_if_needed(path):
    try:
        if path.stat().st_size <= MAX_BYTES:
            return
        rows = _read_rows(path)[-KEEP_ROWS:]
        tmp = path.with_suffix('.tmp')
        tmp.write_text(HEADER + ''.join(r + '\n' for r in rows), encoding='utf-8', newline='\n')
        os.replace(str(tmp), str(path))
    except OSError:
        pass


def _write_row(directory, path, row):
    gi = Path(directory) / '.gitignore'
    with _locked(directory):
        if not gi.exists():
            gi.write_text('*\n', encoding='utf-8')
        _rotate_if_needed(path)
        new = not path.exists() or path.stat().st_size == 0
        with open(path, 'a', encoding='utf-8', newline='\n') as fh:
            if new:
                fh.write(HEADER)
            fh.write(row)


def append(root, session, kind, **detail):
    """Best-effort append of one event, routed by kind (SESSION_KINDS -> per-session log in the temp
    dir; everything else -> the project log, only if a project root is known). Never raises."""
    try:
        kind = str(kind)
        row = _row(time.time(), str(session or 'unknown-session'), kind, detail)
        if kind in SESSION_KINDS:
            path = _session_path(session)
            _write_row(path.parent, path, row)
        else:
            d = _project_dir(root)
            if d is None:
                return
            _write_row(d, d / 'events.toon', row)
    except Exception:
        pass


def _parse_rows(rows, session, kind, since, out):
    for line in rows:
        try:
            f = next(csv.reader([line[2:]]))
            if len(f) != 4:
                continue
            ts = float(f[0])
            detail = json.loads(f[3])
            if not isinstance(detail, dict):
                continue
        except (csv.Error, ValueError, StopIteration, TypeError):
            continue
        if session is not None and f[1] != session:
            continue
        if kind is not None and f[2] != kind:
            continue
        if ts <= since and since:
            continue
        out.append({'ts': ts, 'session': f[1], 'kind': f[2], 'detail': detail})


def _session_logs(session):
    if session is not None:
        return [_session_path(session)]
    try:
        return sorted(_sessions_dir().glob('*.toon'))
    except OSError:
        return []


def events(root, session=None, kind=None, since=0.0):
    """All events as {'ts','session','kind','detail'}, oldest first. Corrupt rows skipped.
    Reads the log(s) the kind lives in (kind=None merges the session and project logs)."""
    out = []
    paths = []
    if kind is None or kind in SESSION_KINDS:
        paths += _session_logs(session)
    if kind is None or kind not in SESSION_KINDS:
        pp = _project_path(root) if root is not None else None
        if pp is not None:
            paths.append(pp)
    for p in paths:
        try:
            _parse_rows(_read_rows(p), session, kind, since, out)
        except OSError:
            continue
    if len(paths) > 1:
        out.sort(key=lambda e: e['ts'])
    return out


def _project_events(root):
    """Every event of the project log only, in file order."""
    out = []
    try:
        pp = _project_path(root) if root is not None else None
        if pp is not None:
            _parse_rows(_read_rows(pp), None, None, 0.0, out)
    except OSError:
        pass
    return out


def last_event(root, kind, session=None, since=0.0):
    evs = events(root, session=session, kind=kind, since=since)
    return max(evs, key=lambda e: e['ts']) if evs else None


def count(root, kind, **match):
    """Number of `kind` events whose detail (or `session`) equals every key in `match`."""
    n = 0
    sess = match.get('session')
    for e in events(root, kind=kind, session=sess if isinstance(sess, str) else None):
        ok = True
        for k, v in match.items():
            have = e['session'] if k == 'session' else e['detail'].get(k)
            if have != v:
                ok = False
                break
        n += ok
    return n


# ---------------------------------------------------------------------------
# Typed recorders (new kinds)
# ---------------------------------------------------------------------------

def append_answer(root, session, text, pairs, options=None, tool_use_id=None):
    """`pairs` = [[question, answer], ...]; `options` (optional) = [[label, ...], ...] aligned with
    pairs: the option labels the question OFFERED (affirmative_answer requires the chosen answer to
    be one of them). `tool_use_id` (optional) is stored in the detail when given."""
    d = {'text': str(text or '')[:2000], 'pairs': pairs}
    if options is not None:
        d['options'] = options
    if tool_use_id:
        d['tool_use_id'] = str(tool_use_id)
    append(root, session, 'answer', **d)


def append_question(root, session, text, options=None, tool_use_id=None):
    d = {'text': str(text or '')[:4000]}
    if options is not None:
        d['options'] = options
    if tool_use_id:
        d['tool_use_id'] = str(tool_use_id)
    append(root, session, 'question', **d)


# ---------------------------------------------------------------------------
# Transcript sync (AskUserQuestion pairs and queued messages, recovered from the host transcript)
# ---------------------------------------------------------------------------

def _labels_of(q):
    out = []
    try:
        for o in (q.get('options') or []):
            if isinstance(o, dict):
                if isinstance(o.get('label'), str):
                    out.append(o['label'])
            elif isinstance(o, str):
                out.append(o)
    except Exception:
        pass
    return out


def parse_transcript_pairs(path, start_offset=0, pending=None):
    """(pairs, new_offset): AskUserQuestion question/answer pairs found in the JSONL transcript from
    byte `start_offset`; only COMPLETE lines are consumed (new_offset = first unprocessed byte).
    Each pair = {'tool_use_id','questions':[str],'options':[[label]],'pairs':[[q, a]]}.
    `pending` ({tool_use_id: [question dicts]}) carries unanswered AskUserQuestion tool_use entries across
    calls; it is updated in place (answered ids removed, capped to the 20 newest). Never raises."""
    pairs = []
    known = pending if isinstance(pending, dict) else {}
    off = start_offset if isinstance(start_offset, int) and start_offset >= 0 else 0
    try:
        with open(path, 'rb') as fh:
            fh.seek(off)
            while True:
                line = fh.readline()
                if not line or not line.endswith(b'\n'):
                    break
                off += len(line)
                try:
                    obj = json.loads(line.decode('utf-8', 'replace'))
                except ValueError:
                    continue
                try:
                    if not isinstance(obj, dict):
                        continue
                    msg = obj.get('message')
                    content = msg.get('content') if isinstance(msg, dict) else None
                    if not isinstance(content, list):
                        continue
                    for blk in content:
                        if not isinstance(blk, dict):
                            continue
                        if blk.get('type') == 'tool_use' and blk.get('name') == 'AskUserQuestion':
                            qs = (blk.get('input') or {}).get('questions') if isinstance(blk.get('input'), dict) else None
                            qs = [q for q in (qs if isinstance(qs, list) else [])
                                  if isinstance(q, dict) and isinstance(q.get('question'), str)]
                            if qs and isinstance(blk.get('id'), str):
                                known.pop(blk['id'], None)
                                known[blk['id']] = qs
                        elif blk.get('type') == 'tool_result' and blk.get('tool_use_id') in known:
                            tid = blk['tool_use_id']
                            qs = known.pop(tid)
                            qstrs = [q['question'] for q in qs]
                            tur = obj.get('toolUseResult')
                            ans = tur.get('answers') if isinstance(tur, dict) else None
                            if isinstance(ans, dict):
                                pp = []
                                for q, a in ans.items():
                                    if isinstance(a, (list, tuple)):
                                        a = ', '.join(str(x) for x in a)
                                    pp.append([str(q), str(a)])
                            else:
                                pp = parse_answers(blk.get('content'), qstrs)[1]
                            pairs.append({'tool_use_id': tid, 'questions': qstrs,
                                          'options': [_labels_of(q) for q in qs], 'pairs': pp})
                except Exception:
                    continue
    except Exception:
        pass
    try:
        while len(known) > 20:
            known.pop(next(iter(known)))
    except Exception:
        pass
    return pairs, off


def _marker_path(session):
    return HOOKS_TMP / (_safe_sid(session) + '.transcript.json')


def _read_marker(session):
    m = {'offset': 0, 'ids': [], 'queued': [], 'pending': {}}
    try:
        d = json.loads(_marker_path(session).read_text(encoding='utf-8'))
        if isinstance(d, dict):
            if isinstance(d.get('offset'), int) and d['offset'] >= 0:
                m['offset'] = d['offset']
            for k in ('ids', 'queued'):
                if isinstance(d.get(k), list):
                    m[k] = [x for x in d[k] if isinstance(x, str)]
            if isinstance(d.get('pending'), dict):
                m['pending'] = {k: v for k, v in d['pending'].items()
                                if isinstance(k, str) and isinstance(v, list)}
    except Exception:
        pass
    return m


def _write_marker(session, m):
    try:
        p = _marker_path(session)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + '.%d.tmp' % os.getpid())
        tmp.write_text(json.dumps(m), encoding='utf-8')
        os.replace(str(tmp), str(p))
    except Exception:
        pass


def sync_ask_answers(transcript_path, session, root=None):
    """Record AskUserQuestion question+answer events recovered from the transcript. Skips tool_use ids
    already synced and questions already present in the session log (never duplicates the PostToolUse
    hook). Returns the number of pairs recorded. Never raises."""
    try:
        if not transcript_path or not os.path.isfile(str(transcript_path)):
            return 0
        m = _read_marker(session)
        before = json.dumps(m['pending'], sort_keys=True)
        found, new_off = parse_transcript_pairs(transcript_path, m['offset'], m['pending'])
        if not found:
            if new_off != m['offset'] or json.dumps(m['pending'], sort_keys=True) != before:
                m['offset'] = new_off
                _write_marker(session, m)
            return 0
        qevs = events(root, session=session, kind='question')
        # by-text dedupe only against hook-written questions (no tool_use_id), and only when no event
        # with a tool_use_id carries that same text (a re-asked identical question is a NEW question)
        have = ' \n'.join(str(e['detail'].get('text', '')) for e in qevs
                          if not e['detail'].get('tool_use_id'))
        have_ids = {str(e['detail'].get('tool_use_id')) for e in qevs if e['detail'].get('tool_use_id')}
        tagged = ' \n'.join(str(e['detail'].get('text', '')) for e in qevs if e['detail'].get('tool_use_id'))
        n = 0
        for p in found:
            if p['tool_use_id'] in m['ids'] or p['tool_use_id'] in have_ids:
                continue
            m['ids'].append(p['tool_use_id'])
            if any(q and q in have and q not in tagged for q in p['questions']):
                continue
            parts = []
            for q, labs in zip(p['questions'], p['options']):
                parts.append(q)
                parts.extend(labs)
            qtext = redact_secrets(' | '.join(x for x in parts if x), limit=4000)[0]
            append_question(root, session, qtext, options=p['options'], tool_use_id=p['tool_use_id'])
            prs = [[redact_secrets(str(a[0]), limit=1000)[0], redact_secrets(str(a[1]), limit=1000)[0]]
                   for a in p['pairs'] if isinstance(a, (list, tuple)) and len(a) == 2]
            atext = ', '.join('"%s"="%s"' % (a, b) for a, b in prs)
            append_answer(root, session, atext, prs, options=p['options'] if prs else None,
                          tool_use_id=p['tool_use_id'])
            n += 1
        m['offset'] = new_off
        m['ids'] = m['ids'][-200:]
        _write_marker(session, m)
        return n
    except Exception:
        return 0


def record_queued_messages(root, session, queued):
    """Record user messages the host queued mid-turn as 'prompt' events (source='queued'), deduped
    through the transcript marker file. Returns the number recorded. Never raises."""
    try:
        if not isinstance(queued, list):
            return 0
        import hashlib
        m = _read_marker(session)
        n = 0
        for it in queued:
            if not isinstance(it, dict):
                continue
            c = it.get('content')
            role = it.get('role')
            if not isinstance(c, str) or not c.strip() or role not in (None, 'user'):
                continue
            ts = it.get('timestamp')
            key = str(ts) if ts else hashlib.sha1(c.encode('utf-8', 'replace')).hexdigest()[:16]
            if key in m['queued']:
                continue
            m['queued'].append(key)
            append(root, session, 'prompt', text=redact_secrets(c)[0], source='queued')
            n += 1
        if n:
            m['queued'] = m['queued'][-200:]
            _write_marker(session, m)
        return n
    except Exception:
        return 0


def append_approved(root, session, spec, hash):
    append(root, session, 'approved', spec=str(spec), hash=str(hash))


def append_spec_closed(root, session, spec, reason='completed', hash=''):
    """`hash` = approval_hash of tasks.md at close time; later tasks.md edits with the same hash
    (Status/Tracker-ref only) do not re-open the spec. Empty = any later tasks.md edit re-opens."""
    d = {'spec': str(spec), 'reason': str(reason)}
    if hash:
        d['hash'] = str(hash)
    append(root, session, 'spec_closed', **d)


def append_stop_block(root, session, spec, key):
    append(root, session, 'stop_block', spec=str(spec), key=str(key))


def append_stop_block_exhausted(root, session, spec, key=''):
    append(root, session, 'stop_block_exhausted', spec=str(spec), key=str(key))


def append_hook_error(root, session, hook, error):
    append(root, session, 'hook_error', hook=str(hook), error=str(error)[:300])


def append_find_spec(root, session, rebuilt, ok, source):
    append(root, session, 'find_spec', rebuilt=bool(rebuilt), ok=bool(ok), source=str(source))


def record_hook_error(start, session, hook, error):
    """Record a hook_error (a SESSION kind: per-session log, never inside a project). Never raises.
    `start` is accepted for backwards compatibility and ignored."""
    try:
        append_hook_error(None, session if isinstance(session, str) else None, hook, error)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# find_spec detection
# ---------------------------------------------------------------------------

_FIND_SPEC_OK = ('aidd spec search', 'no specs/ folder', 'no spec folders')   # authentic messages only
_PY_RE = re.compile(r'^python(?:3(?:\.\d+)?)?(?:\.exe)?$|^py(?:\.exe)?$', re.I)
_WRAPPERS = {'&', 'call', 'time', 'nohup', 'command', 'exec', 'sudo', 'env', 'builtin'}
_AIDD_SUBS = {'search', 'tree', 'list', 'reindex', 'spec'}
_SHELL_EXES = {'powershell', 'pwsh', 'bash', 'sh', 'zsh', 'cmd'}
_SHELL_CMD_FLAGS = {'-c', '-command', '/c', '/k', '-encodedcommand'}


def find_spec_ok(output):
    o = str(output or '').lower()
    return any(m in o for m in _FIND_SPEC_OK)


def find_spec_rebuilt(output):
    return 'Graph index: rebuilt' in str(output or '')


def _segment_runs_find_spec(seg, depth):
    try:
        toks = shlex.split(seg.strip(), posix=False)
    except ValueError:
        toks = seg.split()
    toks = [t.strip('"\'') for t in toks]
    i, n = 0, len(toks)
    while i < n:
        t = toks[i].lower()
        if re.match(r'^\w+=', toks[i]) or t in _WRAPPERS:
            i += 1
        elif t == 'timeout':
            i += 1
            while i < n and (toks[i].startswith('-') or re.match(r'^\d+(\.\d+)?[smhd]?$', toks[i])):
                i += 1
        elif t in ('uv', 'poetry', 'pipenv') and i + 1 < n and toks[i + 1].lower() == 'run':
            i += 2
        else:
            break
    if i >= n:
        return False
    exe = re.split(r'[\\/]', toks[i])[-1]
    low = re.sub(r'\.exe$', '', exe.lower())
    if low == 'aidd':                       # the CLI: `aidd search|tree|list|reindex` (`aidd spec ...` harmless)
        return i + 1 < n and toks[i + 1].lower() in _AIDD_SUBS
    if low in _SHELL_EXES and depth < 3:
        for j in range(i + 1, n):
            if toks[j].lower() in _SHELL_CMD_FLAGS:
                return runs_find_spec(' '.join(toks[j + 1:]).strip('"\''), depth + 1)
        return False
    if not _PY_RE.match(exe):
        return False
    i += 1
    while i < n and toks[i].startswith('-') and toks[i] != '-':
        if toks[i] == '-m':                 # python -m aidd.cli search|tree|list|reindex ...
            return (i + 2 < n and toks[i + 1].lower() in ('aidd.cli', 'aidd', 'aidd.__main__')
                    and toks[i + 2].lower() in _AIDD_SUBS)
        if toks[i] == '-c':
            return False
        i += 2 if toks[i] in ('-X', '-W', '-Q') else 1
    return i < n and re.split(r'[\\/]', toks[i])[-1].lower() == 'find_spec.py'


def runs_find_spec(command, depth=0):
    """True iff the shell command actually RUNS find_spec (or its `aidd spec ...` wrapper): some
    `&&`/`;`/`|`-separated segment is `[& | VAR=x | time | timeout N | uv run] python|python3|py
    [-u -X utf8 ...] <path>find_spec.py ...`, or `powershell|pwsh|bash -c "<such a command>"`.
    `echo`/`grep`/`cat find_spec.py` mentions do not count."""
    if not isinstance(command, str):
        return False
    if 'find_spec.py' not in command and not re.search(
            r'\baidd(?:\.exe|\.cli|\.__main__)?\s+(?:spec|search|tree|list|reindex)\b', command):
        return False
    return any(_segment_runs_find_spec(seg, depth) for seg in re.split(r'&&|\|\||[;|\n]', command))


def response_text(tool_response):
    """Best-effort text of a tool_response of any shape (str / dict / list / None)."""
    if tool_response is None:
        return ''
    if isinstance(tool_response, str):
        return tool_response
    if isinstance(tool_response, dict):
        parts = []
        for k in ('stdout', 'output', 'content', 'text', 'result', 'message', 'stderr'):
            v = tool_response.get(k)
            if v:
                parts.append(response_text(v))
        return '\n'.join(p for p in parts if p)
    if isinstance(tool_response, list):
        return '\n'.join(p for p in (response_text(x) for x in tool_response) if p)
    return str(tool_response)


# ---------------------------------------------------------------------------
# AskUserQuestion answers
# ---------------------------------------------------------------------------

_PAIR_RE = re.compile(r'"(.+?)"="(.*?)"(?=,\s*"|\.(?:\s|$)|\s*$)', re.S)


def _anchored_text_pairs(text, qs):
    """Pairs from the harness sentence, anchored ONLY on the known question strings, in order.
    None on any ambiguity (a marker missing/duplicated/out of order, a malformed separator)."""
    markers = ['"%s"="' % q for q in qs]
    pos = []
    for m in markers:
        if text.count(m) != 1:
            return None
        pos.append(text.index(m))
    if pos != sorted(pos):
        return None
    pairs = []
    for k, q in enumerate(qs):
        start = pos[k] + len(markers[k])
        if k + 1 < len(qs):
            seg = text[start:pos[k + 1]]
            m = re.search(r'",\s*$', seg)
            if not m:
                return None
            ans = seg[:m.start()]
        else:
            seg = text[start:]
            idx = seg.rfind('". You can now')
            if idx >= 0:
                ans = seg[:idx]
            else:
                m = re.search(r'"\.?\s*$', seg)
                if not m:
                    return None
                ans = seg[:m.start()]
        pairs.append([q[:1000], ans[:1000]])
    return pairs


def anchored_pairs(tool_response, questions):
    """[[question, answer], ...] for the KNOWN `questions` (strings, in order) or [] when the response
    cannot be matched to them unambiguously (D2). Handles the harness sentence (str, or inside a
    dict/list) and the dict form {answers: {<known question>: <answer>}}."""
    qs = [q for q in (questions or []) if isinstance(q, str)]
    if not qs or len(qs) != len(questions or []):
        return []
    try:
        if isinstance(tool_response, dict) and isinstance(tool_response.get('answers'), dict):
            ans = tool_response['answers']
            if any(q not in ans for q in qs):
                return []
            out = []
            for q in qs:
                a = ans[q]
                if isinstance(a, (list, tuple)):
                    a = ', '.join(str(x) for x in a)
                out.append([q[:1000], str(a)[:1000]])
            return out
        text = response_text(tool_response)
        return _anchored_text_pairs(text, qs) or []
    except Exception:
        return []


def parse_answers(tool_response, questions=None):
    """(text, pairs) from an AskUserQuestion tool_response. Real shapes seen:
    * str   `Your questions have been answered: "<q>"="<a>", "<q2>"="<a2>". You can now continue ...`
            (older builds: `User has answered your questions: ...`)
    * dict  {questions:[...], answers:{<q>: <a>}}   (the toolUseResult shape)
    With `questions` (the known question strings, in order) pairs are ANCHORED on them (anchored_pairs;
    [] when ambiguous) — the only mode the hooks use. Without it a tolerant, UNANCHORED guess is made,
    which an attacker-controlled question text can forge: never use that as evidence."""
    if questions is not None:
        try:
            text = response_text(tool_response)
        except Exception:
            text = ''
        return text[:2000], anchored_pairs(tool_response, questions)[:40]
    pairs = []
    text = ''
    try:
        if isinstance(tool_response, dict):
            ans = tool_response.get('answers')
            if isinstance(ans, dict):
                for q, a in ans.items():
                    if isinstance(a, (list, tuple)):
                        a = ', '.join(str(x) for x in a)
                    pairs.append([str(q)[:1000], str(a)[:1000]])
            elif isinstance(ans, list):
                for it in ans:
                    if isinstance(it, dict):
                        q = it.get('question') or it.get('q') or ''
                        a = it.get('answer') or it.get('a') or it.get('selected') or ''
                        if isinstance(a, (list, tuple)):
                            a = ', '.join(str(x) for x in a)
                        pairs.append([str(q)[:1000], str(a)[:1000]])
        text = response_text(tool_response)
        if not pairs and text:
            pairs = [[m.group(1)[:1000], m.group(2)[:1000]] for m in _PAIR_RE.finditer(text)]
        if not text and pairs:
            text = ', '.join('"%s"="%s"' % (q, a) for q, a in pairs)
    except Exception:
        pass
    return text[:2000], pairs[:40]


_AFFIRM_RE = re.compile(r'^(approve|approved|aprobar|aprobado|aprobada|si|yes|ok|confirm|confirmo|proceder|'
                        r'abandon|abandonar|descartar)\b')
_NEG_RE = re.compile(r'\b(no|rechazar|rechazo|rechazado|reject|rejected|cancel|cancelar|not)\b')


_TYPED_NEG_RE = re.compile(r"^(no\b|don't|dont|do not|cancel|keep|cancelar|mantener)")


def _rx(r):
    return r if hasattr(r, 'search') else re.compile(str(r), re.I)


def typed_approval(root, session, since_ts, label_re, must_contain):
    """Fallback when the host never records AskUserQuestion answers (no PostToolUse for it): a
    recorded USER PROMPT that is one short line, starts with the approving label and carries the exact
    `must_contain` tag (e.g. `Approve [tasks:37ed463c]`). Subagent hand-backs and system notices start
    with `<` or `[` and are longer, so an agent cannot produce one. Newest match wins; else None."""
    try:
        if not (label_re and must_contain):
            return None
        lx = _rx(label_re)
        need = re.sub(r'\s+', ' ', str(must_contain)).strip().lower()
        evs = [e for s in {session, 'unknown-session'}
               for e in events(root, kind='prompt', session=s, since=since_ts or 0.0)]
        for e in sorted(evs, key=lambda x: x['ts'], reverse=True):
            text = str(e['detail'].get('text', '')).strip()
            if not text or '\n' in text or len(text) > 120 or text[0] in '<[':
                continue
            if need not in re.sub(r'\s+', ' ', text).lower():
                continue
            if _TYPED_NEG_RE.match(text.lower()) or (_NEG_RE.search(normalise(text)) and not lx.search(text)):
                return None     # the newest tagged typed reply is a refusal: it cancels older approvals
            if lx.search(text):
                return e
    except Exception:
        pass
    return None


def affirmative_answer(root, session, topic_re, since_ts=0.0, label_re=None, must_contain=None):
    """AskUserQuestion answer (see `_answer_event`), else a typed approval (see `typed_approval`)."""
    return (_answer_event(root, session, topic_re, since_ts, label_re, must_contain)
            or typed_approval(root, session, since_ts, label_re, must_contain))


def _answer_event(root, session, topic_re, since_ts=0.0, label_re=None, must_contain=None):
    """The newest `answer` event (same session or 'unknown-session', ts > since_ts) that has a
    question matching `topic_re` (uses `pairs` ONLY, never raw text); returned only if the chosen
    answer matches `label_re` (default: a generic affirmative that contains no negative) AND is one of
    the options the hook recorded for that question (when the event records options). A newer topic
    answer that says no overrides an older yes. When `must_contain` is given, the recorded QUESTION text
    of the matching pair must contain it (case-insensitive, whitespace-normalised) — this binds the
    click to the content being approved (e.g. a `[tasks:<hash8>]` tag). Else None."""
    try:
        rx = _rx(topic_re)
        need = re.sub(r'\s+', ' ', str(must_contain)).strip().lower() if must_contain else None
        lx = _rx(label_re) if label_re is not None else None
        evs = [e for s in {session, 'unknown-session'}
               for e in events(root, kind='answer', session=s, since=since_ts or 0.0)]
        for _i, e in sorted(enumerate(evs), key=lambda t: (t[1]['ts'], t[0]), reverse=True):
            pairs = e['detail'].get('pairs')
            options = e['detail'].get('options')
            if not isinstance(pairs, list):
                continue
            topical = [(i, p) for i, p in enumerate(pairs)
                       if isinstance(p, (list, tuple)) and len(p) == 2 and rx.search(str(p[0]))
                       and (need is None or need in re.sub(r'\s+', ' ', str(p[0])).strip().lower())]
            if not topical:
                continue
            for i, (q, a) in topical:
                a = str(a).strip()
                if isinstance(options, list):
                    offered = options[i] if i < len(options) and isinstance(options[i], (list, tuple)) else []
                    if a.lower() not in {str(o).strip().lower() for o in offered}:
                        continue
                if lx is not None:
                    if lx.search(a):
                        return e
                else:
                    na = normalise(a)
                    if _AFFIRM_RE.match(na) and not _NEG_RE.search(na):
                        return e
            return None
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Open specs / active spec
# ---------------------------------------------------------------------------

def open_specs(root):
    """Spec ids with a `spec_edit` of plan.md OR tasks.md (spec.md alone does not open a spec) and no
    LATER `spec_closed` event (any session). A closed spec re-opens on a later plan/tasks edit, except a
    tasks.md edit whose `hash` equals the closing event's `hash` (status-only edit)."""
    state = {}      # spec -> open?
    closed_hash = {}  # spec -> hash recorded by the closing event ('' = none)
    for e in _project_events(root):
        d = e['detail']
        if e['kind'] == 'spec_edit':
            name = str(d.get('file') or '') or re.split(r'[\\/]', str(d.get('path') or ''))[-1]
            name = name.strip().rstrip('. ').split(':')[0].lower()
            if name in ('tasks.md', 'plan.md') and d.get('spec'):
                sp = str(d['spec'])
                ch = closed_hash.get(sp, '')
                if (name == 'tasks.md' and state.get(sp) is False and ch
                        and str(d.get('hash') or '') == ch):
                    continue            # status-only edit after close: stays closed
                state.pop(sp, None)
                state[sp] = True
        elif e['kind'] == 'spec_closed' and d.get('spec'):
            sp = str(d['spec'])
            state.pop(sp, None)
            state[sp] = False
            closed_hash[sp] = str(d.get('hash') or '')
    return [s for s, o in state.items() if o]


def set_active_spec(root, spec_id):
    """Informational pointer only. Re-setting the same id keeps its original since-ts."""
    try:
        spec_id = str(spec_id).strip()
        if not spec_id or _project_dir(root) is None:   # never create `.aidd` in a project that has none
            return
        path = _active_path(root)
        since = None
        try:
            lines = path.read_text(encoding='utf-8').splitlines()
            if lines and lines[0].strip() == spec_id and len(lines) > 1:
                since = lines[1].strip()
        except OSError:
            pass
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f'active_spec.{os.getpid()}.tmp')
        tmp.write_text(f'{spec_id}\n{since or format(time.time(), ".3f")}\n', encoding='utf-8', newline='\n')
        os.replace(str(tmp), str(path))
    except Exception:
        pass


def get_active_spec(root):
    try:
        lines = _active_path(root).read_text(encoding='utf-8').splitlines()
        return lines[0].strip() or None if lines else None
    except OSError:
        return None


def clear_active_spec(root):
    try:
        _active_path(root).unlink()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Quote verification
# ---------------------------------------------------------------------------

def normalise(text):
    """Lowercase, accent-fold (NFKD), punctuation -> space, whitespace collapsed."""
    s = unicodedata.normalize('NFKD', str(text or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r'[\W_]+', ' ', s).strip()


def quote_in_prompts(root, quote, min_words=3, session=None):
    """True iff the normalised quote has >= min_words words and is a substring of the
    normalised text of some recorded `prompt` event (of `session` when given, else any session)."""
    q = normalise(quote)
    if len(q.split()) < min_words:
        return False
    for e in events(root, kind='prompt', session=session):
        if q in normalise(e['detail'].get('text', '')):
            return True
    return False
