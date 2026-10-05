#!/usr/bin/env python3
"""
aidd_review_state — the pure review.md side of `aidd review` (spec 008, T-07).

aidd:FR-304 aidd:FR-306 aidd:FR-309 aidd:FR-312 aidd:FR-313

Owns the two review.md grammars (`codes-v2` of the compact page and the 007 `headings-v1`),
the approval-state decision (`evaluate_review`, fixed early-check order and the legacy rule),
the one-line status protocol, the `--check` exit codes, the `--comments` lines and the
`--summary` text.

Design rules (plan.md "Exact interfaces", rules of the split):
- stdlib only; never imports `aidd_review` or `aidd_review_items`;
- NO file IO and never prints: every input is a parameter, every output a return value;
- the compiled code grammar (`CODE_RE`) is owned by `aidd_review_items` and arrives here as the
  `code_re` parameter; this module never compiles its own copy;
- every public function never raises: a failure degrades to the fail-closed answer.
"""
import hashlib
import re

# ---------------------------------------------------------------------------
# Constants (aidd:FR-304, aidd:FR-309, aidd:FR-313)
# ---------------------------------------------------------------------------

FORMAT_COMPACT = 'codes-v2'
FORMAT_FULL = 'headings-v1'
MAX_REVIEW_MD_BYTES = 2 * 1024 * 1024          # moved from aidd_review.py (spec 007)
MAX_COMMENT = 500
MAX_COMMENT_LINES = 5
STATES = ('complete', 'pending', 'stale', 'legacy', 'too_many_items')
EXIT_BY_STATE = {'complete': 0, 'pending': 2, 'stale': 3, 'legacy': 3, 'too_many_items': 3}
SUMMARY_MAX_LINES = 30

_FORMATS = (FORMAT_COMPACT, FORMAT_FULL)
_HEX12_RE = re.compile(r'^[0-9a-f]{12}$')
# headings-v1 (spec 007), moved here unchanged
_BLOCK_RE = re.compile(r'^##\s+(\S+)\s*(?:<!--.*-->)?$')
_CHECK_RE = re.compile(r'^- \[( |x|X)\] Approved\s*$')
# codes-v2 check line, applied with fullmatch per line (aidd:FR-304)
_CODE_LINE_RE = re.compile(r'- \[( |x|X)\] (\S+)(?: @([0-9a-f]{8}))?[ \t]*', re.ASCII)
_LOOKS_LIKE_CHECK_RE = re.compile(r'^- \[')
_TAG_RE = re.compile(r'\[tasks:[0-9a-f]{8}\]', re.ASCII)
_CTRL_RE = re.compile('[\x00-\x1f\x7f-\x9f\u200e\u200f\u202a-\u202e\u2066-\u2069]')
_WS_RE = re.compile(r'\s+')
_SUMMARY_LINE_MAX = 240
_DEFAULT_MAX_ITEMS = 2000

R_TOO_MANY = 'too many items ({n} > {cap}): split the spec or run aidd review <spec> --full'
R_NO_PAGE = 'no review.html: run aidd review <spec>'
R_LEGACY_OLD = ('review.md uses the old per-heading grammar (spec 007): run aidd review <spec>, '
                'open the page and press Approve again')
R_LEGACY_OTHER = ('review.md was saved from the compact page but review.html is a different page '
                  'type: run aidd review <spec> again')


# ---------------------------------------------------------------------------
# review.md parsing (aidd:FR-304, aidd:FR-312)
# ---------------------------------------------------------------------------

def _new_result():
    return {'ok': False, 'errors': [], 'warnings': [], 'meta': {}, 'format': FORMAT_FULL,
            'sections': {}, 'digests': {}}


def _front_matter(lines, res):
    """Parse the front matter into res['meta'] / res['format']; return the body start index or
    None when the front matter is missing or unclosed (an error is recorded)."""
    if not lines or lines[0].strip() != '---':
        res['errors'].append('missing front matter (first line must be ---)')
        return None
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            end = i
            break
    if end is None:
        res['errors'].append('front matter is not closed (second --- missing)')
        return None
    meta = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        k, sep, v = line.partition(':')
        if not sep:
            res['warnings'].append(f'front matter line ignored: {line.strip()[:60]}')
            continue
        meta[k.strip().lower()] = v.strip()
    for req in ('spec', 'tasks_hash', 'sources_digest', 'approved'):
        if not meta.get(req):
            res['errors'].append(f'front matter: {req} is required')
    for hk in ('tasks_hash', 'sources_digest'):
        if meta.get(hk) and not _HEX12_RE.match(meta[hk]):
            res['errors'].append(f'front matter: {hk} must be 12 lowercase hex characters')
    appr = meta.get('approved', '').lower()
    if appr in ('true', 'false'):
        meta['approved'] = appr == 'true'
    else:
        if meta.get('approved'):
            res['errors'].append('front matter: approved must be true or false')
        meta['approved'] = None
    # aidd:FR-304 — a missing `format:` line is the 007 grammar; any other value is invalid
    fmt = meta.get('format', '')
    if not fmt:
        res['format'] = FORMAT_FULL
    elif fmt in _FORMATS:
        res['format'] = fmt
    else:
        res['format'] = fmt[:40]
        res['errors'].append(f'front matter: unknown format {fmt[:40]!r} '
                             f'(expected {FORMAT_COMPACT} or {FORMAT_FULL})')
    res['meta'] = meta
    return end + 1


def _parse_headings_v1(body, res):
    """The spec 007 `## key` / `- [x] Approved` grammar, unchanged."""
    sections = {}
    cur = None
    state = None                 # per block: {'check': bool|None, 'comment': [..], 'cstate'}
    for line in body:
        bm = _BLOCK_RE.match(line)
        if bm:
            cur = bm.group(1)
            if cur in sections:
                res['warnings'].append(f'duplicate block {cur}: the last one wins')
            state = {'check': None, 'comment': [], 'cstate': 0}
            sections[cur] = state
            continue
        if state is None:
            if line.strip():
                res['warnings'].append(f'text before the first block ignored: {line.strip()[:60]}')
            continue
        cm = _CHECK_RE.match(line)
        if cm and state['check'] is None:
            state['check'] = cm.group(1) in 'xX'
        if line.startswith('>'):
            if state['cstate'] in (0, 1):
                state['comment'].append(line[2:] if line.startswith('> ') else line[1:])
                state['cstate'] = 1
            else:
                res['warnings'].append(f'{cur}: second comment run ignored')
        elif state['cstate'] == 1:
            state['cstate'] = 2
    for key, st in sections.items():
        if st['check'] is None:
            res['warnings'].append(f'{key}: no "- [ ] Approved" line (counts as unchecked)')
        res['sections'][key] = {'approved': bool(st['check']),
                                'comment': '\n'.join(st['comment']).strip()}


def _cap_comment(code, lines, res):
    """aidd:FR-304 — at most MAX_COMMENT_LINES `> ` lines and MAX_COMMENT chars per code.
    The canonical writer (the compact page) emits ONE `> ` line per comment with newlines
    collapsed (the canonical form); a hand-edited file may spread a comment over consecutive
    `> ` lines, which are tolerated and kept as separate lines joined with `\\n` (blank `>`
    lines dropped), so `comment_lines` renders them with ` / ` (FR-309(b), AC-318). A
    single-line comment never holds `\\n`."""
    if len(lines) > MAX_COMMENT_LINES:
        res['warnings'].append(f'{code}: comment longer than {MAX_COMMENT_LINES} lines, '
                               'extra lines dropped')
        lines = lines[:MAX_COMMENT_LINES]
    text = '\n'.join(p for p in (ln.strip() for ln in lines) if p)
    if len(text) > MAX_COMMENT:
        res['warnings'].append(f'{code}: comment longer than {MAX_COMMENT} characters, cut')
        text = text[:MAX_COMMENT].rstrip()
    return text


def _parse_codes_v2(body, res, code_re):
    """aidd:FR-304 / aidd:FR-312 — one `- [x] CODE[ @d8]` line per code, then its comment.
    Canonical comment = ONE `> ` line (the page collapses newlines); consecutive `> ` lines are
    also accepted and kept as lines joined with `\\n` (see `_cap_comment`). A code is a key only when `code_re.fullmatch`
    accepts it; a comment can never open a check line because every comment line starts with
    `>`, so `> ---` or `> - [x] FR-302` always stays comment text."""
    if code_re is None or not hasattr(code_re, 'fullmatch'):
        res['errors'].append('no code grammar given to parse a codes-v2 review.md')
        return
    collected = {}               # code -> {'approved', 'comment': [..], 'digest'}
    cur = None                   # the code the following `>` lines belong to (None = nowhere)
    for line in body:
        if line.startswith('>'):
            if cur is None:
                if line.strip('> \t'):
                    res['warnings'].append('comment line without a valid code line ignored')
                continue
            collected[cur]['comment'].append(line[2:] if line.startswith('> ') else line[1:])
            continue
        m = _CODE_LINE_RE.fullmatch(line)
        if m:
            code = m.group(2)
            if not code_re.fullmatch(code):
                res['warnings'].append(f'not a review code, line ignored: {code[:40]}')
                cur = None
                continue
            if code in collected:
                res['warnings'].append(f'duplicate line {code}: the last one wins')
            collected[code] = {'approved': m.group(1) in 'xX', 'comment': [],
                               'digest': m.group(3)}
            cur = code
            continue
        if not line.strip():
            continue
        if _LOOKS_LIKE_CHECK_RE.match(line):
            res['warnings'].append(f'malformed check line ignored: {line.strip()[:60]}')
        else:
            res['warnings'].append(f'text line ignored: {line.strip()[:60]}')
        cur = None
    for code, c in collected.items():
        res['sections'][code] = {'approved': bool(c['approved']),
                                 'comment': _cap_comment(code, c['comment'], res)}
        if c['digest']:
            res['digests'][code] = c['digest']


def parse_review(text, code_re):
    """Parse review.md by the grammar its `format:` line names. Returns
    `{ok, errors, warnings, meta, format, sections, digests}`. Never raises; refuses text over
    MAX_REVIEW_MD_BYTES. aidd:FR-304 aidd:FR-312"""
    res = _new_result()
    try:
        if not isinstance(text, str):
            res['errors'].append('review.md is not text')
            return res
        if len(text.encode('utf-8', 'replace')) > MAX_REVIEW_MD_BYTES:
            res['errors'].append('review.md is larger than 2 MB')
            return res
        t = text.replace('\r\n', '\n').replace('\r', '\n')
        if t.startswith('\ufeff'):
            t = t[1:]
        lines = t.split('\n')
        start = _front_matter(lines, res)
        if start is None:
            return res
        body = lines[start:]
        if res['format'] == FORMAT_COMPACT:
            _parse_codes_v2(body, res, code_re)
        elif res['format'] == FORMAT_FULL:
            _parse_headings_v1(body, res)
        res['ok'] = not res['errors']
        return res
    except Exception as e:  # noqa: BLE001 — never raises (contract)
        res['ok'] = False
        res['errors'].append(f'unparseable review.md ({type(e).__name__})')
        return res


# ---------------------------------------------------------------------------
# Approval state decision (aidd:FR-304, aidd:FR-301 item cap)
# ---------------------------------------------------------------------------

def _empty_state():
    return {'present': False, 'valid': False, 'hash_ok': False, 'digest_ok': False,
            'fresh': False, 'complete': False, 'missing': [], 'comments': [], 'sha1': '',
            'reviewed': '', 'mtime': 0.0, 'page_current': False, 'reason': '',
            'format': None, 'page_format': None, 'legacy': False, 'item_count': 0}


def _inputs(inp):
    """The documented `inp` keys with their defaults; wrong types degrade to the default."""
    g = inp if isinstance(inp, dict) else {}

    def pick(key, default, types):
        v = g.get(key, default)
        return v if isinstance(v, types) else default

    meta = g.get('page_meta', (None, None, None))
    if not isinstance(meta, (tuple, list)) or len(meta) != 3:
        meta = (None, None, None)
    keys = g.get('keys', [])
    keys = [k for k in keys if isinstance(k, str)] if isinstance(keys, (list, tuple)) else []
    rb = g.get('review_bytes')
    if isinstance(rb, bytearray):
        rb = bytes(rb)
    page_mtime = g.get('page_mtime')
    if isinstance(page_mtime, bool) or not isinstance(page_mtime, (int, float)):
        page_mtime = None
    item_count = g.get('item_count', 0)
    if isinstance(item_count, bool) or not isinstance(item_count, int):
        item_count = 0
    max_items = g.get('max_items', _DEFAULT_MAX_ITEMS)
    if isinstance(max_items, bool) or not isinstance(max_items, int):
        max_items = _DEFAULT_MAX_ITEMS
    review_mtime = g.get('review_mtime', 0.0)
    if isinstance(review_mtime, bool) or not isinstance(review_mtime, (int, float)):
        review_mtime = 0.0
    return {
        'review_bytes': rb if isinstance(rb, bytes) else None,
        'review_error': pick('review_error', '', str),
        'review_mtime': float(review_mtime),
        'page_mtime': None if page_mtime is None else float(page_mtime),
        'page_meta': tuple(meta),
        'tasks_hash': pick('tasks_hash', None, str),
        'digest': pick('digest', None, str),
        'oversize': pick('oversize', None, str),
        'item_count': item_count,
        'max_items': max_items,
        'keys': keys,
        'code_re': g.get('code_re'),
    }


def evaluate_review(inp):
    """Decide the review state from the facts `aidd_review.review_state` gathered (no IO here).
    Every 007 field keeps its meaning; adds `format`, `page_format`, `legacy`, `item_count`.
    Early checks in a FIXED order: (1) item cap, (2) no review.html. Never raises.
    aidd:FR-304 aidd:FR-301"""
    st = _empty_state()
    try:
        x = _inputs(inp)
        page_present = x['page_mtime'] is not None
        page_format = None
        if page_present:
            page_format = x['page_meta'][2] or FORMAT_FULL      # a 007 blob has no format
        st['page_format'] = page_format
        st['item_count'] = x['item_count']

        # (1) item cap FIRST: compact page OR no page at all (aidd:FR-301, aidd:FR-304)
        if page_format != FORMAT_FULL and x['item_count'] > x['max_items']:
            st['reason'] = R_TOO_MANY.format(n=x['item_count'], cap=x['max_items'])
            return st

        big = x['oversize']
        if big:
            st['reason'] = f'source too large: {big}'      # the 007 reason, wins as in 007

        # review.md facts (also reported without a page, as in 007)
        pr = None
        if x['review_bytes'] is not None or x['review_error']:
            st['present'] = True
        if x['review_bytes'] is not None:
            raw = x['review_bytes']
            st['sha1'] = hashlib.sha1(raw).hexdigest()
            st['mtime'] = x['review_mtime'] or 0.0
            if len(raw) > MAX_REVIEW_MD_BYTES:
                pr = _new_result()
                pr['errors'].append('review.md is larger than 2 MB')
            else:
                pr = parse_review(raw.decode('utf-8', 'replace'), x['code_re'])
            meta = pr.get('meta', {}) or {}
            st['format'] = pr.get('format')
            st['valid'] = bool(pr.get('ok'))
            st['reviewed'] = str(meta.get('reviewed', '') or '')
            st['hash_ok'] = x['tasks_hash'] is not None and meta.get('tasks_hash') == x['tasks_hash']
            st['digest_ok'] = x['digest'] is not None and meta.get('sources_digest') == x['digest']

        # (2) no review.html: no keys, nothing missing, never legacy (aidd:FR-304)
        if not page_present:
            st['item_count'] = 0
            if pr is not None:
                secs = pr.get('sections', {}) or {}
                st['comments'] = [{'key': k, 'text': s['comment']}
                                  for k, s in secs.items() if s.get('comment')]
            if not st['reason']:
                st['reason'] = R_NO_PAGE
            return st

        if not big:
            st['page_current'] = x['page_meta'][1] is not None and x['page_meta'][1] == x['digest']
        if not st['present']:
            st['reason'] = st['reason'] or 'no review.md in the spec folder'
            return st
        if pr is None:
            st['reason'] = st['reason'] or f"review.md is not readable ({x['review_error']})"
            return st

        meta = pr.get('meta', {}) or {}
        # legacy: review.md parses and its grammar differs from the page's (aidd:FR-304)
        st['legacy'] = bool(pr.get('ok')) and st['format'] != page_format
        if st['legacy']:
            st['valid'] = False
        st['fresh'] = st['mtime'] > x['page_mtime']
        keys = [] if big else list(x['keys'])
        secs = pr.get('sections', {}) or {}
        if st['legacy']:
            secs = {}
        st['missing'] = [k for k in keys if not secs.get(k, {}).get('approved')]
        order = keys + [k for k in secs if k not in keys]
        st['comments'] = [{'key': k, 'text': secs[k]['comment']}
                          for k in order if k in secs and secs[k].get('comment')]
        compact_ok = True
        if page_format == FORMAT_COMPACT:
            # aidd:FR-304 — a compact page also needs SUMMARY checked and at least one item
            compact_ok = (x['item_count'] >= 1 and 'SUMMARY' in keys
                          and bool(secs.get('SUMMARY', {}).get('approved')))
        st['complete'] = bool(st['valid'] and st['hash_ok'] and st['digest_ok'] and st['fresh']
                              and meta.get('approved') is True and not st['missing'] and not big
                              and keys and compact_ok)
        if st['reason']:
            pass
        elif st['legacy']:
            st['reason'] = R_LEGACY_OLD if page_format == FORMAT_COMPACT else R_LEGACY_OTHER
        elif not st['valid']:
            st['reason'] = 'review.md is invalid: ' + '; '.join(pr.get('errors', []))
        elif not st['hash_ok']:
            st['reason'] = (f'review.md was generated for tasks hash {meta.get("tasks_hash")}; '
                            f'current is {x["tasks_hash"]}: run `aidd review` again')
        elif not st['digest_ok']:
            st['reason'] = (f'review.md was generated for sources digest '
                            f'{meta.get("sources_digest")}; current is {x["digest"]}: '
                            'run `aidd review` again')
        elif not st['fresh']:
            st['reason'] = 'review.md is older than review.html: review the current page and Send again'
        elif meta.get('approved') is not True:
            st['reason'] = 'review.md says approved: false'
        elif st['missing']:
            more = len(st['missing']) - 5
            st['reason'] = ('unchecked sections: ' + ', '.join(st['missing'][:5])
                            + (f' (+{more} more)' if more > 0 else ''))
        elif not keys:
            st['reason'] = 'no reviewable headings in the sources'
        elif not compact_ok:
            st['reason'] = 'SUMMARY is not checked'
        return st
    except Exception as e:  # noqa: BLE001 — pure decision, never raises
        st['complete'] = False
        st['reason'] = st['reason'] or f'review state unavailable ({type(e).__name__})'
        return st


# ---------------------------------------------------------------------------
# Status protocol (aidd:FR-309, aidd:FR-306)
# ---------------------------------------------------------------------------

_NO_TASKS_RE = re.compile(r'no tasks\.md|tasks\.md is (?:missing|required|mandatory)', re.I)


def _is_stale(rs, reason):
    """The FR-309 `stale` test: no page, page not current, sources over the 007 cap, no tasks.md,
    or a present review.md whose tasks hash / sources digest no longer match."""
    if reason.startswith('no review.html') or reason.startswith('source too large'):
        return True
    if _NO_TASKS_RE.search(reason):
        return True
    if not rs.get('page_current'):
        return True
    return bool(rs.get('present')) and not (rs.get('hash_ok') and rs.get('digest_ok'))


def _clean_tag(tag):
    return tag if isinstance(tag, str) and _TAG_RE.fullmatch(tag) else None


def derive_approval(rs, tag):
    """`review_state` dict + tag -> `{state, approved, total, comments, stale, legacy, tag}`.
    Precedence too_many_items > legacy > stale > complete > pending. Never raises.
    aidd:FR-309"""
    safe_tag = _clean_tag(tag)
    try:
        if not isinstance(rs, dict):
            raise TypeError('review state is not a dict')
        reason = str(rs.get('reason') or '')
        legacy = bool(rs.get('legacy'))
        stale = _is_stale(rs, reason)
        if reason.startswith('too many items'):
            state = 'too_many_items'
        elif legacy:
            state = 'legacy'
        elif stale:
            state = 'stale'
        elif rs.get('complete'):
            state = 'complete'
        else:
            state = 'pending'
        total = rs.get('item_count', 0)
        total = total if isinstance(total, int) and not isinstance(total, bool) and total > 0 else 0
        missing = rs.get('missing') or []
        approved = 0
        # checked codes count only for a parsed, current-grammar review.md whose keys were read
        if (rs.get('present') and rs.get('valid') and not legacy
                and not reason.startswith('source too large')):
            approved = max(0, total - len(missing))
        comments = rs.get('comments') or []
        return {'state': state, 'approved': approved, 'total': total,
                'comments': len(comments) if isinstance(comments, (list, tuple)) else 0,
                'stale': stale, 'legacy': legacy, 'tag': safe_tag}
    except Exception:  # noqa: BLE001 — fail closed: stale with zeros
        return {'state': 'stale', 'approved': 0, 'total': 0, 'comments': 0, 'stale': True,
                'legacy': False, 'tag': safe_tag}


def _nat(v):
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else 0


def status_line(st):
    """Exactly `STATE=<state> approved=<a>/<n> comments=<c> stale=<yes|no> legacy=<yes|no>
    tag=<[tasks:h8]|none>`: one line, never any file content, item text, comment or reason.
    aidd:FR-309"""
    try:
        g = st if isinstance(st, dict) else {}
        state = g.get('state') if g.get('state') in STATES else 'stale'
        stale = bool(g.get('stale')) if 'stale' in g else True
        tag = _clean_tag(g.get('tag')) or 'none'
        return (f"STATE={state} approved={_nat(g.get('approved'))}/{_nat(g.get('total'))} "
                f"comments={_nat(g.get('comments'))} stale={'yes' if stale else 'no'} "
                f"legacy={'yes' if g.get('legacy') else 'no'} tag={tag}")
    except Exception:  # noqa: BLE001
        return 'STATE=stale approved=0/0 comments=0 stale=yes legacy=no tag=none'


def exit_for(state):
    """`--check` exit code per FR-309 state; 3 for anything unknown (replaces 007 _check_exit)."""
    try:
        return EXIT_BY_STATE.get(state, 3)
    except Exception:  # noqa: BLE001 — unhashable input
        return 3


def _strip_ctrl(s):
    return _CTRL_RE.sub('', str(s))


def comment_lines(rs):
    """`--comments`: `(0, ['<CODE>: <comment>', ...])` only when review.md is present AND valid
    AND not legacy AND hash_ok AND digest_ok, else `(3, [])`. The exit never depends on the
    state name. A comment kept over several `> ` lines (`\\n` inside) is printed on one line
    with ` / ` between its lines. aidd:FR-309 aidd:AC-318"""
    try:
        if not isinstance(rs, dict):
            return 3, []
        if not (rs.get('present') and rs.get('valid') and not rs.get('legacy')
                and rs.get('hash_ok') and rs.get('digest_ok')):
            return 3, []
        out = []
        for c in rs.get('comments') or []:
            if not isinstance(c, dict):
                continue
            code = _strip_ctrl(c.get('key', '')).strip()
            parts = [_strip_ctrl(p).strip() for p in str(c.get('text') or '').split('\n')]
            text = ' / '.join(p for p in parts if p)
            if not code or not text:
                continue
            out.append(f'{code}: {text}'[:MAX_COMMENT])
        return 0, out
    except Exception:  # noqa: BLE001
        return 3, []


# ---------------------------------------------------------------------------
# --summary text (aidd:FR-313)
# ---------------------------------------------------------------------------

def _one_line(value, n=_SUMMARY_LINE_MAX):
    """One line: control chars dropped, whitespace collapsed, cut at n with `...`."""
    try:
        if value is None:
            return ''
        if isinstance(value, (list, tuple)):
            value = '; '.join(str(v) for v in value if v is not None and str(v).strip())
        s = _WS_RE.sub(' ', _strip_ctrl(_WS_RE.sub(' ', str(value)))).strip()
        if len(s) > n:
            s = s[:max(0, n - 3)].rstrip() + '...'
        return s
    except Exception:  # noqa: BLE001
        return ''


def _num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    if isinstance(v, float) and v != v:            # NaN
        return None
    return int(v) if float(v).is_integer() else round(float(v), 1)


def _top_folder(path):
    parts = [p for p in re.split(r'[\\/]+', path) if p]
    return parts[0] + '/' if len(parts) > 1 else './'


def _change_lines(files, budget):
    """Paths grouped by top folder in first-seen order, one labelled line per group, at most
    `budget` lines (the last one says how many groups were folded)."""
    label = 'Changes by component/file'
    paths = []
    for f in files if isinstance(files, (list, tuple)) else []:
        s = _one_line(f, 200)
        if s and s not in paths:
            paths.append(s)
    if not paths:
        return [f'{label}: n/a']
    groups = {}
    for p in paths:
        groups.setdefault(_top_folder(p), []).append(p)
    names = list(groups)
    out = []
    shown = names if len(names) <= budget else names[:max(0, budget - 1)]
    for g in shown:
        out.append(_one_line(f'{label}: {g} ({len(groups[g])}): ' + ', '.join(groups[g])))
    rest = names[len(shown):]
    if rest:
        n_files = sum(len(groups[g]) for g in rest)
        out.append(_one_line(f'{label}: +{len(rest)} more folders ({n_files} files): '
                             + ', '.join(rest)))
    return out


def summary_lines(summary, files, waves):
    """`aidd review --summary` text: labelled lines Objective, Scope, Changes by component/file,
    Cost, Tasks/waves, Risks, Open decisions; at most SUMMARY_MAX_LINES; `n/a` for a missing
    piece; deterministic; never raises. aidd:FR-313"""
    try:
        s = summary if isinstance(summary, dict) else {}
        counts = s.get('counts') if isinstance(s.get('counts'), dict) else {}

        def field(key):
            return _one_line(s.get(key)) or 'n/a'

        minutes, tokens = _num(s.get('minutes')), _num(s.get('tokens_k'))
        cost = (f"{minutes if minutes is not None else 'n/a'} min / "
                f"{str(tokens) + 'k' if tokens is not None else 'n/a'} tokens")
        if minutes is None and tokens is None:
            cost = 'n/a'
        n_tasks = _num(counts.get('tasks'))
        n_waves = _num(waves)
        tw = (f"{n_tasks if n_tasks is not None else 'n/a'} tasks, "
              f"{n_waves if n_waves is not None else 'n/a'} waves")
        head = [f"Objective: {field('objective')}", f"Scope: {field('scope')}"]
        tail = [f'Cost: {cost}', f'Tasks/waves: {tw}', f"Risks: {field('risks')}",
                f"Open decisions: {field('open_decisions')}"]
        budget = SUMMARY_MAX_LINES - len(head) - len(tail)
        lines = head + _change_lines(files, budget) + tail
        return [_one_line(line) for line in lines][:SUMMARY_MAX_LINES]
    except Exception:  # noqa: BLE001
        return ['Objective: n/a', 'Scope: n/a', 'Changes by component/file: n/a', 'Cost: n/a',
                'Tasks/waves: n/a', 'Risks: n/a', 'Open decisions: n/a']
