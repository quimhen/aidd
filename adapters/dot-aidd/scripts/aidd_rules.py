#!/usr/bin/env python3
"""
aidd hard-rules library — pure, stdlib-only checks used by hooks, `aidd rules ...`
and check_spec.py. Contract: specs/002-aidd-hard-rules/spec.md (incl. the Rev 1 amendments).

Rules: R1 estimates (agent time) · R2 pipeline route · R3 alignment provenance ·
R4 visual debt · R5 chain order · R6 tasks approval · R7 closing-audit domains ·
R9 protected paths. (R8 is the Stop hook, not a library concern.)
Spec 003 adds R10 execution evidence at close · R11 root cause on repeat · R12 view-vs-logic tag.
Spec 007 adds the `## Verification` table (lint + executed close gate), the ONE closing auditor
(`CLOSING AUDIT` header) and the advisory R5 mode (AIDD_R5_AUDIT).

Every public function is total: malformed input yields a Violation, never an
exception. A Violation is ``{'rule', 'message', 'fix'}`` where ``fix`` is the exact
next action for the agent (imperative English).

Every regex here is linear and applied to ONE line (or one short cell); artifacts larger than
MAX_CHARS are never scanned (a single "file too large" violation instead).
"""
import hashlib
import os
import posixpath
import re
import shlex
import sys
import time
import unicodedata
from pathlib import Path

RULE_IDS = ('R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'R9', 'R10', 'R11', 'R12', 'R13', 'R14')

AGENT_ROLES = ('builder', 'sql', 'tests', 'docs', 'auditor', 'mapper')
MODEL_TIERS = ('medium', 'high')
LOWEST_TIER_RE = re.compile(r'haiku', re.I)
HUMAN_FACTOR_DEFAULT = 3

ROUTE_STEPS = ('-1', '0', '1', '1.5', '2', '3', '4')
VISUAL_STEPS = ('0', '1', '1.5')

# M-dos: artifacts larger than this are never regex-scanned.
MAX_CHARS = 2 * 1024 * 1024

# M9: word-boundary domain regexes ("rapid"/"capital" never match "api"; "quick"/"build" never "ui").
DOMAIN_RE = {
    'ui': re.compile(r'\b(?:ui|mockups?|screens?|pantallas?|visuals?)\b', re.I),
    'backend': re.compile(r'\b(?:backend|apis?|contracts?|endpoints?)\b', re.I),
    'database': re.compile(r'\b(?:databases?|base de datos|sql|schemas?|migrations?|migraci\w*)\b', re.I),
    'performance': re.compile(r'\b(?:performance|rendimiento|best practices?)\b', re.I),
    'security': re.compile(r'\b(?:security|seguridad|secure|vulnerabilit\w*|threats?)\b', re.I),
    'functional': re.compile(r'\b(?:functional|funcional\w*|acceptance|aceptaci\w*)\b', re.I),
}

# FR-002: tasks touching a hot path also require a performance auditor (with UI / database).
_HOT_PATH_RE = re.compile(r'\bhot[ -]?paths?\b|\blatency\b|\blatencia\b|\bperformance\b|\brendimiento\b', re.I)

_SCREEN_RE = re.compile(r'\bSCREEN-\d+', re.I)
_TASK_ID_RE = re.compile(r'\bT-\d+\b')
_DASH = r'[—–-]+'
_USER_RE = re.compile(r'^user\s*' + _DASH + r'\s*["“](.+)["”]\s*$', re.I | re.S)
_REPO_RE = re.compile(r'^repo\s*' + _DASH + r'\s*\S+', re.I)
_REPO_PATH_RE = re.compile(r'^repo\s*' + _DASH + r'\s*(.+)$', re.I | re.S)
_PROPOSED_RE = re.compile(r'^\[\s*proposed\b[^\]]*\]$', re.I)
_APPROVED_LINE_RE = re.compile(r'\s*approved\s*:', re.I)   # always used with .match on ONE line
_APPROVED_FULL_RE = re.compile(
    r'\s*approved\s*:\s*(\d{4}-\d{2}-\d{2})\s+hash:([0-9a-fA-F]{12})\s*$', re.I)   # ONE line
_HASH_EXCLUDED = ('status', 'tracker ref', 'pr/spec ref')
NEUTRAL_MAX_CHARS = 60
NEUTRAL_MAX_WORDS = 8
_NAMED_LINE_RE = re.compile(r'[\s>*`_-]*(?:status|tracker ref|pr/spec ref)[\s*`_]*:', re.I)
_JUNK_SOURCES = {'n/a', 'na', 'none', 'nil', 'null', 'tbd', 'todo', 'pending', 'unknown', 'later', 'wip',
                 'yes', 'no', 'x', 'ok', 'resolved', 'open'}
_SEP_CELL_RE = re.compile(r':?-+:?$')
_SMALLINT_RE = re.compile(r'[0-9]{1,9}')


# --------------------------------------------------------------------- helpers

def _v(rule, message, fix):
    return {'rule': rule, 'message': message, 'fix': fix}


def _norm_nl(text):
    if not isinstance(text, str):
        return ''
    return text.replace('\r\n', '\n').replace('\r', '\n')


def _strip_comments(s):
    """Remove <!-- ... --> in linear time (an unterminated comment is kept verbatim)."""
    if '<!--' not in s:
        return s
    out, i = [], 0
    while True:
        a = s.find('<!--', i)
        if a < 0:
            out.append(s[i:])
            break
        b = s.find('-->', a + 4)
        if b < 0:
            out.append(s[i:])
            break
        out.append(s[i:a])
        i = b + 3
    return ''.join(out)


def _clean(text):
    """Normalise newlines, drop HTML comments (templates keep examples in comments) and blank lines."""
    s = _strip_comments(_norm_nl(text))
    return '\n'.join(line for line in s.split('\n') if line.strip())


def _too_large(text):
    return isinstance(text, str) and len(text) > MAX_CHARS


def _split_row(line):
    s = line.strip()
    if s.startswith('|'):
        s = s[1:]
    if s.endswith('|') and not s.endswith('\\|'):
        s = s[:-1]
    return [c.replace('\\|', '|').strip() for c in re.split(r'(?<!\\)\|', s)]


def _is_sep(cells):
    return any(c.strip() for c in cells) and all(_SEP_CELL_RE.match(c.strip()) for c in cells if c.strip())


def _table(text, heading):
    """(header_cells, rows) of the first table under a heading matching `heading`
    (regex, case-insensitive, matched on '#' lines only). None if no heading/table.
    M4: the table continues across blank / prose lines until the next heading, so a blank line
    cannot hide rows from a validator."""
    lines = text.split('\n')
    hre = re.compile(r'#{1,6}\s*' + heading, re.I)
    i = 0
    while i < len(lines) and not hre.match(lines[i].strip()):
        i += 1
    i += 1
    header = None
    first = False
    rows = []
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith('#'):
            break
        if s.startswith('|'):
            cells = _split_row(s)
            if header is None:
                header, first = cells, True
            elif first and _is_sep(cells):
                first = False
            elif not any(c.strip() for c in cells):
                first = False
            else:
                first = False
                rows.append(cells)
        i += 1
    return (header, rows) if header is not None else None


def _has_heading(text, heading):
    hre = re.compile(r'#{1,6}\s*' + heading, re.I)
    return any(hre.match(l.strip()) for l in text.split('\n'))


def _hdr(cells, idx):
    return re.sub(r'\s+', ' ', cells[idx]).strip().lower() if idx < len(cells) else ''


def _words(s):
    return len(re.findall(r'\w+', s or ''))


def _user_quote(cell):
    c = (cell or '').strip()
    if len(c) > 20000:
        return None
    m = _USER_RE.match(c)
    return m.group(1).strip() if m else None


def _step_id(cell):
    s = re.sub(r'[`*_]', '', cell or '').strip().lower()
    s = re.sub(r'^step\s*', '', s).replace('−', '-').replace('–', '-')
    return s


def _codes(s):
    return {c.upper() for c in _SCREEN_RE.findall(s or '')}


def _plain(s):
    return re.sub(r'[`*_]', '', s or '').strip()


# --------------------------------------------------------------------------- R1

def _task_blocks(text):
    """{task_id: block_text} for '### T-nn' blocks."""
    blocks, cur, buf = {}, None, []
    for line in text.split('\n'):
        s = line.strip()
        if not s:
            continue
        m = re.match(r'###\s*(T-\d+)\b', s)
        if m or re.match(r'#{1,2}\s', s):
            if cur:
                blocks[cur] = '\n'.join(buf)
            cur, buf = (m.group(1) if m else None), []
            continue
        if cur:
            buf.append(line)
    if cur:
        blocks[cur] = '\n'.join(buf)
    return blocks


_FIELD_PREFIX_RE = re.compile(r'\s*[-*]?\s*')


def _field(block, name):
    """Value of a `Name: value` line (bold/backticks tolerated) — evaluated per line (linear)."""
    nre = re.compile(re.escape(name).replace(r'\ ', r'\s+') + r'\s*:\s*(.*)$', re.I)
    for line in block.split('\n'):
        s = line.replace('*', '').replace('`', '')
        if not s.strip():
            continue
        m = _FIELD_PREFIX_RE.match(s)
        mm = nre.match(s, m.end())
        if mm:
            return mm.group(1).strip()
    return None


def _neutral_cell_violations(t):
    """D10: the hash-neutral cells/lines (Status, Tracker ref, PR/Spec ref) must stay short, so they
    cannot smuggle content past the approval hash."""
    out, excl, lines = [], [], t.split(chr(10))
    for i, line in enumerate(lines):
        st = line.strip()
        if _NAMED_LINE_RE.match(st):
            val = st.split(':', 1)[1].strip() if ':' in st else ''
            if len(val) > NEUTRAL_MAX_CHARS or len(val.split()) > NEUTRAL_MAX_WORDS:
                out.append(_v('R1', f'A "Status:"-style line is too long to be hash-neutral: "{val[:40]}...".',
                              f'Shorten it to at most {NEUTRAL_MAX_CHARS} chars / {NEUTRAL_MAX_WORDS} words; '
                              'move real content to a normal field (it is covered by the approval hash).'))
            continue
        if st.startswith('|'):
            cells = _split_row(st)
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ''
            if nxt.startswith('|') and _is_sep(_split_row(nxt)) and not _is_sep(cells):
                excl = [(j, c) for j, c in enumerate(cells) if _table_exclusions([c])]
            elif excl and not _is_sep(cells):
                for j, c in excl:
                    v = cells[j] if j < len(cells) else ''
                    if len(v) > NEUTRAL_MAX_CHARS or len(v.split()) > NEUTRAL_MAX_WORDS:
                        out.append(_v('R1', f'A "{re.sub(r"[*`_]", "", c).strip()}" cell is too long to be hash-neutral: "{v[:40]}...".',
                                      f'Shorten it to at most {NEUTRAL_MAX_CHARS} chars / {NEUTRAL_MAX_WORDS} words '
                                      '(it is excluded from the approval hash, so it must not carry content).'))
        else:
            excl = []
    return out


_UI_CODE_RE = re.compile(r'\b(?:SCREEN|COMP)-\d+', re.I)
_REUSE_RE = re.compile(r'reutiliza\w*|remapea\w*|envuelve\w*|wrap\w*|reus\w*|rewir\w*', re.I)
_KIND_RE = re.compile(r'\bKind\s*:\s*(.*)$', re.I)
_TASK_CELL_RE = re.compile(r'T-\d+$')


def _kind_values(segments):
    """Remainders (after the first colon) of every `Kind:` found in the given short segments."""
    vals = []
    for seg in segments:
        s = seg.replace('*', '').replace('`', '')
        if len(s) > 4000:
            continue
        m = _KIND_RE.search(s)
        if m:
            vals.append(m.group(1).strip())
    return vals


def _kind_state(vals):
    """'ok' | 'bare' (VIEW-legacy without justification) | 'missing'."""
    bare = False
    for v in vals:
        low = v.lower()
        if low.startswith('view-new') or low.startswith('logic'):
            return 'ok'
        m = re.match(r'view-legacy\s*:\s*(.*)$', v, re.I)
        if m and len(m.group(1).strip()) >= 5:
            return 'ok'
        if low.startswith('view-legacy'):
            bare = True
    return 'bare' if bare else 'missing'


def _check_kind(t, blocks):
    """R12: a task row citing SCREEN-/COMP- with a reuse word needs `Kind: VIEW-new | LOGIC |
    VIEW-legacy: <justification 5+ chars>` (in the row or in its '### T-nn' block)."""
    out = []
    for line in t.split('\n'):
        st = line.strip()
        if not st.startswith('|'):
            continue
        cells = _split_row(st)
        tid = _plain(cells[0]) if cells else ''
        if not _TASK_CELL_RE.match(tid):
            continue
        blk = blocks.get(tid, '')
        joined = st + '\n' + blk
        if not (_UI_CODE_RE.search(joined) and _REUSE_RE.search(joined)):
            continue
        state = _kind_state(_kind_values(cells + blk.split('\n')))
        if state == 'ok':
            continue
        if state == 'bare':
            out.append(_v('R12', f'{tid}: "Kind: VIEW-legacy" has no justification.',
                          f'In {tid} write "Kind: VIEW-legacy: <why the legacy view stays, 5+ chars>", or switch to '
                          '"Kind: VIEW-new" (new faithful view) / "Kind: LOGIC" (data/logic only).'))
        else:
            out.append(_v('R12', f'{tid} cites a SCREEN/COMP code and a reuse word (reutiliza/remapea/envuelve/wrap/reuse/rewire) '
                                 'but has no "Kind:" tag.',
                          f'In the {tid} row or block add "Kind: VIEW-new" (new view, reused logic/data), "Kind: LOGIC", '
                          'or "Kind: VIEW-legacy: <justification 5+ chars>". Default for a redesign is VIEW-new + LOGIC.'))
    return out


_LEGACY_WAVES_HDR = '| Wave | Tasks | Agent time (min) | Human ref (h) |'
_NEW_WAVES_HDR = '| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |'
# column indexes per Waves header variant (FR-001 / FR-005)
_WAVES_IDX = {
    'legacy': {'agent': 2, 'human': 3, 'width': 4},
    'new': {'roles': 2, 'agent': 3, 'tokens': 4, 'human': 5, 'width': 6},
}
_TOKENS_RE = re.compile(r'(\d{1,9})\s*k?', re.I)


def _waves_variant(header):
    """'new' when the Waves header names a 'roles' column, else 'legacy'."""
    return 'new' if any(_hdr(header, i) == 'roles' for i in range(len(header or []))) else 'legacy'


def _waves_header_ok(header, variant):
    if variant == 'new':
        return (len(header) >= 6 and _hdr(header, 0) == 'wave' and _hdr(header, 1) == 'tasks'
                and _hdr(header, 2) == 'roles' and _hdr(header, 3).startswith('agent time')
                and _hdr(header, 4).startswith('tokens') and _hdr(header, 5).startswith('human ref'))
    return (_hdr(header, 0) == 'wave' and _hdr(header, 1) == 'tasks'
            and _hdr(header, 2).startswith('agent time') and _hdr(header, 3).startswith('human ref'))


def _is_legacy_tasks(text):
    """FR-009: True iff the tasks.md approval is valid AND its Waves header has no 'tokens' column.
    Legacy files (specs 001-004) skip every token/role check."""
    try:
        if approval_valid(text) is not True:
            return False
        tbl = _table(_clean(text), r'waves\b')
        header = tbl[0] if tbl else []
        return not any(_hdr(header, i).startswith('tokens') for i in range(len(header)))
    except Exception:  # pragma: no cover - defensive
        return False


def _tokens_k(s):
    """Thousands of tokens in '60k' / '60' / '60 k', else None."""
    m = _TOKENS_RE.fullmatch((s or '').strip())
    return int(m.group(1)) if m else None


def _field_value(blk, name):
    """Field value with a trailing '# comment' removed (template style), lower-cased."""
    v = _field(blk, name)
    if v is None:
        return None
    return v.split('#', 1)[0].strip().lower()


def _check_tokens(blocks, waves, text=''):
    """R1 (FR-001): `- Tokens (est): <N>k` per task; wave Tokens (k) = SUM of its tasks;
    `Total tokens (k): N` = sum of the waves. `waves` are NEW-variant rows padded to 6 cells."""
    out, tok = [], {}
    ix = _WAVES_IDX['new']
    for tid, blk in blocks.items():
        raw = _field(blk, 'tokens (est)')
        n = _tokens_k(raw) if raw is not None else None
        if n is None:
            out.append(_v('R1', f'{tid}: "Tokens (est):" missing or not a number of thousands, got "{raw or ""}".',
                          f'In {tid} add "- Tokens (est): <N>k" (thousands of tokens, e.g. 60k).'))
        else:
            tok[tid] = n
    wave_sums, all_ok = [], True
    for r in waves:
        wid = r[0] or '?'
        ids = _TASK_ID_RE.findall(r[1])
        cell = _tokens_k(r[ix['tokens']])
        if cell is None:
            all_ok = False
            out.append(_v('R1', f'Wave {wid}: "Tokens (k)" must be a whole number of thousands, got "{r[ix["tokens"]]}".',
                          f'Set wave {wid} Tokens (k) to the SUM of its tasks\' "Tokens (est)".'))
            continue
        wave_sums.append(cell)
        if ids and all(i in tok for i in ids):
            exp = sum(tok[i] for i in ids)
            if exp != cell:
                out.append(_v('R1', f'Wave {wid}: Tokens {cell}k != sum of its tasks ({exp}k). '
                                    'Every task in a wave consumes its own tokens, so wave tokens = the sum.',
                              f'Set wave {wid} Tokens (k) to {exp}.'))
    total = _field(text, 'total tokens (k)') if text else None
    if total is None:
        out.append(_v('R1', 'Missing line "Total tokens (k): N".',
                      'Add "Total tokens (k): <sum of wave Tokens>" under the Waves table.'))
    else:
        n = _tokens_k(total)
        if n is None:
            out.append(_v('R1', f'Total tokens line must read "N", got "{total.strip()}".',
                          'Write "Total tokens (k): <N>" with N = sum of wave Tokens (k).'))
        elif all_ok and waves and n != sum(wave_sums):
            out.append(_v('R1', f'Total tokens {n}k != sum of waves ({sum(wave_sums)}k).',
                          f'Set the total to "Total tokens (k): {sum(wave_sums)}".'))
    return out


def _check_roles(blocks):
    """R13 (FR-004): each task needs `- Agent role:` in AGENT_ROLES and `- Model tier:` in MODEL_TIERS."""
    out = []
    roles_s, tiers_s = ' | '.join(AGENT_ROLES), ' | '.join(MODEL_TIERS)
    for tid, blk in blocks.items():
        role = _field_value(blk, 'agent role')
        if role not in AGENT_ROLES:
            out.append(_v('R13', f'{tid}: "Agent role:" must be one of {roles_s}, got "{role or ""}".',
                          f'In {tid} write "- Agent role: <{roles_s}>".'))
        tier = _field_value(blk, 'model tier')
        if tier not in MODEL_TIERS:
            out.append(_v('R13', f'{tid}: "Model tier:" must be one of {tiers_s} (never lower), got "{tier or ""}".',
                          f'In {tid} write "- Model tier: <{tiers_s}>".'))
    return out


def _wave_expected_roles(row, blocks):
    """Set of valid roles of the wave's tasks, or None when a task has no valid role (R13 reports it)."""
    roles = set()
    for i in _TASK_ID_RE.findall(row[1]):
        r = _field_value(blocks.get(i, ''), 'agent role')
        if r not in AGENT_ROLES:
            return None
        roles.add(r)
    return roles


def _wave_roles_ok(row, blocks):
    """FR-005: the wave 'Roles' cell equals the set of its tasks' roles (case-insensitive, order-free)."""
    exp = _wave_expected_roles(row, blocks)
    if exp is None:
        return True
    got = {c.strip().lower() for c in _plain(row[_WAVES_IDX['new']['roles']]).split(',') if c.strip()}
    return got == exp


def derived_human_hours(agent_min, factor=HUMAN_FACTOR_DEFAULT):
    """FR-003: human reference hours DERIVED from agent minutes (non-blocking in v1)."""
    return round(agent_min * factor / 60, 2)


def plan_totals(tasks_text):
    """{'minutes': critical-path total, 'tokens_k': total tokens or None}, both header variants. Never raises."""
    res = {'minutes': None, 'tokens_k': None}
    try:
        t = _clean(tasks_text)
        tbl = _table(t, r'waves\b')
        rows, ix = [], _WAVES_IDX['legacy']
        if tbl:
            ix = _WAVES_IDX[_waves_variant(tbl[0])]
            rows = [r + [''] * (ix['width'] - len(r)) for r in tbl[1]]
        total = _field(t, 'total agent time (critical path)')
        m = re.fullmatch(r'(\d{1,9})\s*min\w*', (total or '').strip(), re.I)
        if m:
            res['minutes'] = int(m.group(1))
        elif rows:
            vals = [int(r[ix['agent']]) for r in rows if re.fullmatch(r'\d{1,9}', r[ix['agent']])]
            res['minutes'] = sum(vals) if vals else None
        tt = _field(t, 'total tokens (k)')
        n = _tokens_k(tt) if tt is not None else None
        if n is not None:
            res['tokens_k'] = n
        elif rows and 'tokens' in ix:
            vals = [_tokens_k(r[ix['tokens']]) for r in rows]
            vals = [v for v in vals if v is not None]
            res['tokens_k'] = sum(vals) if vals else None
    except Exception:  # pragma: no cover - defensive
        pass
    return res


def _check_tasks(text):
    out = []
    t = _clean(text)
    fix_w = (f'Add a "## Waves" section with the table {_NEW_WAVES_HDR} '
             f'(legacy approved files: {_LEGACY_WAVES_HDR}) '
             'and one row per wave (waves run sequentially, tasks inside a wave in parallel).')
    tbl = _table(t, r'waves\b')
    waves = []
    variant = 'legacy'
    # FR-009: ONLY an approved tasks.md (approval_valid) with no tokens column is legacy and exempt
    legacy_ok = _is_legacy_tasks(text)
    if tbl is None:
        out.append(_v('R1', 'tasks.md has no "## Waves" table.', fix_w))
    else:
        header, rows = tbl
        variant = _waves_variant(header)
        if variant == 'legacy' and not legacy_ok:
            out.append(_v('R1', f'Waves table header must be the NEW one {_NEW_WAVES_HDR}; the legacy '
                                f'{_LEGACY_WAVES_HDR} is exempt only while its recorded approval is valid '
                                '(unapproved, or edited after approval).',
                          f'Migrate: rewrite the Waves header as {_NEW_WAVES_HDR}, add "Tokens (est)", "Agent role" '
                          'and "Model tier" to every task block, fill wave Roles/Tokens (k) and '
                          '"Total tokens (k): N", then re-approve.'))
        if not _waves_header_ok(header, variant):
            out.append(_v('R1', f'Waves table header must be exactly {_NEW_WAVES_HDR} (or, legacy, '
                                f'{_LEGACY_WAVES_HDR}) in that column order.',
                          f'Rewrite the Waves table header as {_NEW_WAVES_HDR}.'))
        elif not rows:
            out.append(_v('R1', 'Waves table has no rows.', fix_w))
        else:
            width = _WAVES_IDX[variant]['width']
            for r in rows:
                waves.append(r + [''] * (width - len(r)))
    ix = _WAVES_IDX[variant]
    ai, hi = ix['agent'], ix['human']

    out += _neutral_cell_violations(t)
    blocks = _task_blocks(t)
    out += _check_kind(t, blocks)
    if not blocks:
        out.append(_v('R1', 'tasks.md has no "### T-nn" per-task blocks.',
                      'Add one "### T-nn" block per task with "Agent min:" and "Human ref hours:" lines.'))
    agent = {}
    for tid, blk in blocks.items():
        am, hr = _field(blk, 'agent min'), _field(blk, 'human ref hours')
        if am is None or hr is None:
            legacy = _field(blk, 'estimated hours') is not None
            missing = ' and '.join(n for n, v in (('Agent min:', am), ('Human ref hours:', hr)) if v is None)
            out.append(_v('R1', f'{tid}: missing {missing}' +
                          (' (the legacy single "Estimated hours:" is not accepted — it hides agent time behind human hours).'
                           if legacy else '.'),
                          f'In {tid} add "Agent min: <whole minutes an agent needs>" and '
                          f'"Human ref hours: <hours a human would need>"; remove "Estimated hours:".'))
        if am is not None:
            m = re.fullmatch(r'(\d{1,9})(\s*min\w*)?', am, re.I)
            if m and int(m.group(1)) >= 1:
                agent[tid] = int(m.group(1))
            else:
                out.append(_v('R1', f'{tid}: "Agent min:" must be a whole number of minutes >= 1, got "{am}".',
                              f'Set {tid} "Agent min:" to an integer number of minutes.'))
        if hr is not None and not re.fullmatch(r'\d{1,9}(\.\d{1,9})?(\s*h\w*)?', hr, re.I):
            out.append(_v('R1', f'{tid}: "Human ref hours:" must be a number, got "{hr}".',
                          f'Set {tid} "Human ref hours:" to a number of hours.'))

    wave_times, scheduled = [], set()
    for r in waves:
        wid = r[0] or '?'
        ids = _TASK_ID_RE.findall(r[1])
        scheduled.update(ids)
        if not ids:
            out.append(_v('R1', f'Wave {wid} lists no task ids (T-nn).', f'List the tasks of wave {wid} in the Tasks cell.'))
        if not re.fullmatch(r'\d{1,9}(\.\d{1,9})?', r[hi]):
            out.append(_v('R1', f'Wave {wid}: "Human ref (h)" must be a number, got "{r[hi]}".',
                          f'Fill wave {wid} Human ref (h) with a number.'))
        if not re.fullmatch(r'\d{1,9}', r[ai]):
            out.append(_v('R1', f'Wave {wid}: "Agent time (min)" must be a whole number, got "{r[ai]}".',
                          f'Set wave {wid} Agent time (min) to the max "Agent min" of its tasks.'))
            continue
        wave_times.append(int(r[ai]))
        unknown = [i for i in ids if i not in agent]
        if unknown:
            out.append(_v('R1', f'Wave {wid} cites {", ".join(unknown)} with no valid "Agent min:" block.',
                          f'Add/fix the "### {unknown[0]}" block with "Agent min:" so wave {wid} can be verified.'))
        elif ids and max(agent[i] for i in ids) != int(r[ai]):
            out.append(_v('R1', f'Wave {wid}: Agent time {r[ai]} min != max of its tasks ({max(agent[i] for i in ids)} min). '
                                'Tasks inside a wave run in parallel, so wave time = the longest task.',
                          f'Set wave {wid} Agent time (min) to {max(agent[i] for i in ids)}.'))
    if waves:
        for tid in blocks:
            if tid not in scheduled:
                out.append(_v('R1', f'{tid} has a task block but is not scheduled in any wave.',
                              f'Add {tid} to a row of the Waves table.'))

    total = _field(t, 'total agent time (critical path)')
    if total is None:
        out.append(_v('R1', 'Missing line "Total agent time (critical path): N min".',
                      'Add "Total agent time (critical path): <sum of wave Agent times> min" under the Waves table.'))
    else:
        mm = re.fullmatch(r'(\d{1,9})\s*min\w*', total.strip(), re.I)
        if not mm:
            out.append(_v('R1', f'Total line must read "N min", got "{total.strip()}".',
                          'Write "Total agent time (critical path): <N> min" with N = sum of wave Agent times.'))
        elif len(wave_times) == len(waves) and waves and int(mm.group(1)) != sum(wave_times):
            out.append(_v('R1', f'Total {mm.group(1)} min != sum of waves ({sum(wave_times)} min). '
                                'Waves run sequentially, so the critical path is the sum of wave times.',
                          f'Set the total to "Total agent time (critical path): {sum(wave_times)} min".'))

    # FR-001/004/005/009: token and role checks on every tasks.md except an approved legacy one;
    # wave-level Tokens/Roles cells only exist (and are checked) under the NEW header
    if not legacy_ok:
        new_waves = waves if variant == 'new' else []
        out += _check_tokens(blocks, new_waves, t)
        out += _check_roles(blocks)
        for r in new_waves:
            if not _wave_roles_ok(r, blocks):
                wid = r[0] or '?'
                exp = ', '.join(sorted(_wave_expected_roles(r, blocks) or ()))
                out.append(_v('R1', f'Wave {wid}: Roles "{r[ix["roles"]]}" != roles of its tasks ({exp}).',
                              f'Set wave {wid} Roles to "{exp}".'))
    return out


# ----------------------------------------------------------------- R2 / R3 / R4

def parse_route(text):
    """{step: {'status','reason','confirmation'}} from the Pipeline route table ({} if absent).
    The FIRST row of a step wins (duplicates are reported by R2)."""
    tbl = _table(_clean(text), r'pipeline route\b')
    route = {}
    if tbl:
        for r in tbl[1]:
            r = r + [''] * (4 - len(r))
            route.setdefault(_step_id(r[0]), {'status': _plain(r[1]).lower(),
                                              'reason': r[2], 'confirmation': r[3]})
    return route


def _check_route(t):
    out = []
    tbl = _table(t, r'pipeline route\b')
    if tbl is None:
        return [_v('R2', 'spec.md has no "## Pipeline route" table.',
                   'Add "## Pipeline route" with | Step | Status | Reason | Confirmation | and a row for each of '
                   '-1, 0, 1, 1.5, 2, 3, 4 (Status run|waived). Ask the user before waiving any step.')]
    header, rows = tbl
    if not (_hdr(header, 0) == 'step' and _hdr(header, 1) == 'status' and _hdr(header, 2) == 'reason'
            and _hdr(header, 3) == 'confirmation'):
        return [_v('R2', 'Pipeline route header must be | Step | Status | Reason | Confirmation | in that order.',
                   'Rewrite the Pipeline route header as | Step | Status | Reason | Confirmation |.')]
    seen = set()
    for r in rows:
        sid = _step_id(r[0] if r else '')
        if sid not in ROUTE_STEPS:
            out.append(_v('R2', f'Pipeline route has a row for unknown step "{sid}".',
                          'Remove the row or fix its Step (allowed: -1, 0, 1, 1.5, 2, 3, 4).'))
            continue
        if sid in seen:
            out.append(_v('R2', f'Pipeline route has a duplicate row for step {sid}.',
                          f'Keep exactly one row for step {sid} in the Pipeline route table.'))
        seen.add(sid)
    route = parse_route(t)
    for s in ROUTE_STEPS:
        if s not in route:
            out.append(_v('R2', f'Pipeline route has no row for step {s}.',
                          f'Add a row for step {s} (Status run, or waived with Reason + user confirmation).'))
            continue
        row = route[s]
        if row['status'] not in ('run', 'waived'):
            out.append(_v('R2', f'Step {s}: Status must be "run" or "waived", got "{row["status"]}".',
                          f'Set step {s} Status to run or waived.'))
        elif row['status'] == 'waived':
            q = _user_quote(row['confirmation'])
            if not row['reason'].strip():
                out.append(_v('R2', f'Step {s} is waived without a Reason.',
                              f'Fill the Reason for step {s}, or set it back to run.'))
            if q is None or _words(q) < 3:
                out.append(_v('R2', f'Step {s} is waived without a user confirmation of the form '
                                    'user — "<quote of at least 3 words>".',
                              f'Ask the user (AskUserQuestion) whether to waive step {s}, then write their words as '
                              'user — "<exact quote, 3+ words>" in Confirmation; otherwise set it to run.'))
    return out


# Questions every checklist must contain (D6) — the shipped templates/spec.md rows, matched by
# normalised text (extra rows are allowed). tests/test_aidd_rules.py asserts these equal the template.
REQUIRED_QUESTIONS = (
    'Which module/area of the system?',
    'New development or modification of something existing?',
    'Does it involve an external service, API, or integration?',
    'Who is requesting it? (role/profile, not necessarily the name)',
    'Dependencies on other modules or active developments?',
    'Business objective (1 sentence — what it achieves and why)',
    "Expected visual fidelity level (if there's a mockup): exact | functional behavior only",
)
_BLANK_ANSWERS = {'', '-', '—', '–', '--', 'n/a', 'na', 'tbd', 'todo', '?', '...', '…', 'pending'}


def _qnorm(s):
    return re.sub(r'[\W_]+', ' ', unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()).strip()


def _blank_answer(a):
    return _plain(a).strip().strip('.').lower() in _BLANK_ANSWERS or not re.search(r'\w', a or '')


def _tables_all(text, heading):
    """[(header, rows)] of EVERY table under EVERY heading matching `heading` (repeated same-named
    headings and second tables cannot hide rows)."""
    lines = text.split('\n')
    hre = re.compile(r'#{1,6}\s*' + heading, re.I)
    res, i, n = [], 0, len(lines)
    while i < n:
        if not hre.match(lines[i].strip()):
            i += 1
            continue
        i += 1
        header, rows, first = None, [], False
        while i < n and not lines[i].strip().startswith('#'):
            st = lines[i].strip()
            if st.startswith('|'):
                cells = _split_row(st)
                if header is None:
                    header, first = cells, True
                elif first and _is_sep(cells):
                    first = False
                else:
                    first = False
                    if any(c.strip() for c in cells):
                        rows.append(cells)
            i += 1
        if header is not None:
            res.append((header, rows))
    return res


def _checklist_tables(t):
    return _tables_all(t, r'minimum requirements checklist')


def _checklist_rows(t):
    """(first_header | None, rows) over all checklist tables; separator/repeated-header rows dropped."""
    tabs = _checklist_tables(t)
    if not tabs:
        return None, []
    rows = []
    for _h, rs in tabs:
        for r in rs:
            if _is_sep(r) or (_hdr(r, 0) == 'question' and _hdr(r, 1) == 'answer'):
                continue
            rows.append(r + [''] * (3 - len(r)))
    return tabs[0][0], rows


def _check_checklist(t):
    tabs = _checklist_tables(t)
    if not tabs:
        return [_v('R3', 'spec.md has no "Minimum Requirements Checklist" table.',
                   'Add the Minimum Requirements Checklist with | Question | Answer | Source | If unanswered |.')]
    out = []
    for header, _rs in tabs:
        if not (_hdr(header, 0) == 'question' and _hdr(header, 1) == 'answer' and _hdr(header, 2) == 'source'):
            return [_v('R3', 'Checklist header must start | Question | Answer | Source | ... (Source is the 3rd column).',
                       'Insert a "Source" column right after "Answer" and fill it for every answered row.')]
    _h, rows = _checklist_rows(t)
    if not rows:
        return [_v('R3', 'The Minimum Requirements Checklist table has a header but no rows.',
                   'Copy the question rows from templates/spec.md under the header (answers may stay blank until Step 2).')]
    for r in rows:
        q, ans, src = r[0], r[1], r[2]
        if _blank_answer(ans):
            continue  # open alignment question; completeness is enforced by R5 (_alignment_violations)
        q_user = _user_quote(src)
        ok = ((q_user is not None and _words(q_user) >= 3) or _REPO_RE.match(src.strip())
              or _PROPOSED_RE.match(src.strip()))
        if not ok:
            out.append(_v('R3', f'Checklist row "{q[:50]}" has an answer with invalid Source "{src}".',
                          'Set Source to user — "<quote, 3+ words>", repo — <path:LINE>, or '
                          '[Proposed — unconfirmed] if you chose the answer yourself; ask the user to confirm Proposed ones.'))
    return out


def _repo_ref(src):
    """(path, line, quote) of a `repo — ...` Source; (None, None, None) when it is not a repo source.
    Forms: `path:LINE[-LINE]` or `path "quote"`; a bare path yields line=quote=None."""
    m = _REPO_PATH_RE.match((src or '').strip())
    if not m:
        return None, None, None
    body = m.group(1).strip().strip('`').strip()
    if len(body) > 2000:
        return body[:200], None, None
    q = re.match(r'(.+?)\s+["“](.+)["”]\s*$', body, re.S)
    if q:
        return q.group(1).strip().strip('`"\''), None, q.group(2).strip()
    ln = re.match(r'(.+?)(?::|#L)(\d{1,9})(?:[-–,:](?:L)?(\d{1,9}))?\s*$', body)
    if ln:
        return ln.group(1).strip().strip('`"\''), max(int(ln.group(2)), int(ln.group(3) or 0)), None
    return body.strip('`"\''), None, None


def _repo_path(src):
    return _repo_ref(src)[0]


def _inside_exists(proj, rel, want_file=False):
    """True iff `rel` (relative to proj) exists and resolves inside proj."""
    try:
        base = Path(proj).resolve()
        target = (base / rel.replace('\\', '/')).resolve()
        target.relative_to(base)
        return target.is_file() if want_file else target.exists()
    except Exception:
        return False


def _repo_problem(proj, src):
    """None when the repo Source is valid, else a short reason (D6)."""
    path, line, quote = _repo_ref(src)
    if path is None:
        return None
    try:
        base = Path(proj).resolve()
        target = (base / path.replace('\\', '/')).resolve()
        target.relative_to(base)
    except Exception:
        return f'{path} is not inside the project root'
    if not target.is_file():
        return (f'{path} is not an existing file under the project root' if not target.exists()
                else f'{path} is a directory, not a file')
    if line is None and quote is None:
        return f'{path} has no :LINE or "quote" (cite file:LINE, or file "a quote of 3+ words found in it")'
    try:
        if target.stat().st_size > MAX_CHARS:
            return None   # too big to verify cheaply; existence is enough
        data = target.read_bytes()
    except Exception:
        return f'{path} cannot be read'
    if line is not None:
        count = data.count(b'\n') + (0 if data.endswith(b'\n') or not data else 1)
        if line < 1 or line > count:
            return f'{path} has {count} line(s); :{line} is out of range'
        return None
    if _words(quote) < 3:
        return f'the quote from {path} must have 3+ words'
    if _qnorm(quote) not in _qnorm(data.decode('utf-8', 'replace')):
        return f'the quoted text was not found in {path}'
    return None


def _repo_violations(t, proj):
    """M2/D6: every `repo — ...` Source must point at an existing file with a valid line or quote."""
    out = []
    if proj is None:
        return out
    _h, rows = _checklist_rows(t)
    for r in rows:
        if _blank_answer(r[1]) or _repo_ref(r[2])[0] is None:
            continue
        why = _repo_problem(proj, r[2])
        if why:
            out.append(_v('R3', f'Checklist row "{r[0][:50]}": Source repo — {why}.',
                          'Cite an existing file as repo — path:LINE (LINE within the file) or repo — path "exact '
                          '3+ word quote from it"; if the user told you, use user — "<their words>" instead.'))
    return out


def _is_proposed(row):
    return any('proposed' in (c or '').lower() for c in row)


def _alignment_violations(t):
    """R5 (planning blockers from the checklist): missing questions, unanswered rows (M1/D6) and
    Proposed markers anywhere in a row (M2)."""
    out = []
    _h, rows = _checklist_rows(t)
    if not rows:
        out.append(_v('R5', 'The Minimum Requirements Checklist is missing or has no question rows. Planning is blocked.',
                      'Copy the checklist from templates/spec.md and run Step 2 (align) to answer every row.'))
        return out
    have = [_qnorm(r[0]) for r in rows]
    missing = [q for q in REQUIRED_QUESTIONS if not any(_qnorm(q) in h for h in have)]
    if missing:
        out.append(_v('R5', f'The checklist lacks {len(missing)} required question(s): '
                            f'{"; ".join(m[:45] for m in missing[:3])}{"..." if len(missing) > 3 else ""}. Planning is blocked.',
                      'Restore every question row of templates/spec.md in the Minimum Requirements Checklist '
                      '(extra rows are fine), then answer each one.'))
    blank = [r[0] for r in rows if _blank_answer(r[1])]
    if blank:
        out.append(_v('R5', f'{len(blank)} checklist row(s) are unanswered (blank/"-"/n/a Answer): '
                            f'{"; ".join(b[:40] for b in blank[:4])}{"..." if len(blank) > 4 else ""}. Planning is blocked.',
                      'Run Step 2 (align): ask the user (AskUserQuestion) each open question, fill Answer and a '
                      'user — "<their words>" Source (or repo — <path:LINE>); do not leave rows blank.'))
    n_prop = sum(1 for r in rows if _is_proposed(r))
    if n_prop:
        out.append(_v('R5', f'{n_prop} checklist row(s) are still [Proposed — unconfirmed]; planning is blocked.',
                      'Ask the user (AskUserQuestion) to confirm each Proposed answer, then replace its Source with '
                      'user — "<their words, 3+ words>" and drop "Proposed" everywhere in the row.'))
    return out


# ------------------------------------------------------------------ visual debt

def _junk_source(s):
    v = _plain(s).strip().strip('"\'').lower()
    return (not v) or v in _JUNK_SOURCES or not re.search(r'[a-z0-9]', v) or len(v) < 3


def _debt_table(t):
    """(shape_violations, rows[dict]) — None for the violations when there is no table."""
    tbl = _table(t, r'visual debt\b')
    if tbl is None:
        return None, []
    header, rows = tbl
    if not (_hdr(header, 0) == 'codes' and _hdr(header, 1) == 'blocks spec' and _hdr(header, 2) == 'status'
            and _hdr(header, 3) == 'mockup source'):
        return [_v('R4', 'Visual debt header must be | Codes | Blocks spec | Status | Mockup source |.',
                   'Rewrite the Visual debt header as | Codes | Blocks spec | Status | Mockup source |.')], []
    out, parsed = [], []
    for r in rows:
        r = r + [''] * (4 - len(r))
        d = {'codes': _codes(r[0]), 'blocks_spec': _plain(r[1]), 'status': _plain(r[2]).lower(),
             'source': r[3].strip()}
        parsed.append(d)
        if not d['codes']:
            out.append(_v('R4', f'Visual debt row "{r[0]}" names no SCREEN-nn code.', 'List the SCREEN-nn codes in Codes.'))
        if not d['blocks_spec']:
            out.append(_v('R4', f'Visual debt row {r[0]} has no "Blocks spec".', 'Name the spec id the debt blocks.'))
        if d['status'] not in ('open', 'resolved'):
            out.append(_v('R4', f'Visual debt row {r[0]}: Status must be open|resolved, got "{r[2]}".',
                          'Set Status to open or resolved.'))
        elif d['status'] == 'resolved' and _junk_source(d['source']):
            out.append(_v('R4', f'Visual debt row {r[0]} is resolved without a valid Mockup source '
                                f'(got "{d["source"]}").',
                          'Fill Mockup source with the mockup file path, an http(s):// URL or figma:<ref> that now '
                          'covers these codes, or set Status back to open.'))
    return out, parsed


def open_visual_debt(spec_text):
    """Rows (dicts: codes, blocks_spec, status, source) of the Visual debt table with Status open."""
    if _too_large(spec_text):
        return []
    _shape, rows = _debt_table(_clean(spec_text))
    return [r for r in rows if r['status'] == 'open']


def _waived_visual(t):
    route = parse_route(t)
    return [s for s in VISUAL_STEPS if route.get(s, {}).get('status') == 'waived']


def _missing_debt_violation(waived, missing):
    return _v('R4', f'Step(s) {", ".join(waived)} are waived but {", ".join(missing)} have no mockup audit '
                    'and are not listed in "## Visual debt".',
              'Add a "## Visual debt" table | Codes | Blocks spec | Status | Mockup source | with one row '
              f'(Status open) for {", ".join(missing)}, then ask the user for the mockup source.')


def _debt_static(t, raw, extra_codes=()):
    """Structure + waived-without-listing check (no filesystem). `t` = cleaned text, `raw` =
    newline-normalised text WITH comments (codes hidden in comments still count — m-a)."""
    waived = _waived_visual(t)
    shape, rows = _debt_table(t)
    out = list(shape or [])
    if waived:
        needed = _codes(raw) | {c.upper() for c in extra_codes}
        covered = set().union(*[r['codes'] for r in rows]) if rows else set()
        missing = sorted(needed - covered)
        if missing:
            out.append(_missing_debt_violation(waived, missing))
    return out


def _check_spec(text, extra_codes=()):
    raw = _norm_nl(text)
    t = _clean(text)
    return _check_route(t) + _check_checklist(t) + _debt_static(t, raw, extra_codes)


def _spec_ids(specs_dir):
    try:
        return sorted(p.name for p in Path(specs_dir).iterdir() if p.is_dir())
    except Exception:
        return []


def _match_spec_ref(ref, ids):
    """Spec ids named by a `Blocks spec` cell: exact id or numeric prefix (007 / 7)."""
    out = []
    for tok in re.split(r'[,;/\s]+', _plain(ref).lower()):
        tok = tok.strip('.')
        if not tok:
            continue
        for sid in ids:
            low = sid.lower()
            num = low.split('-')[0]
            if tok == low or (_SMALLINT_RE.fullmatch(tok) and _SMALLINT_RE.fullmatch(num) and int(tok) == int(num)):
                if sid not in out:
                    out.append(sid)
    return out


def _audited_codes(specs_dir, own_name=None, own_audit_text=None):
    """SCREEN codes with a mockup-audit.md TABLE row anywhere under specs/ (`own_audit_text`
    overrides the would-be mockup-audit.md of spec `own_name`)."""
    texts = []
    try:
        files = list(Path(specs_dir).glob('*/mockup-audit.md'))
    except Exception:
        files = []
    for f in files:
        if own_audit_text is not None and f.parent.name == own_name:
            continue
        texts.append(_read(f))
    if own_audit_text is not None:
        texts.append(own_audit_text)
    codes = set()
    for tx in texts:
        for line in _norm_nl(tx).split('\n'):
            if line.lstrip().startswith('|'):
                codes |= _codes(line)
    return codes


def check_debt(root, spec_id, extra_texts=None):
    """R4 for spec `spec_id` under `root`, evaluated on the WOULD-BE content in `extra_texts`
    ({'plan.md': text, 'contracts.md': text, 'spec.md': text, 'mockup-audit.md': text}; keys are
    matched by basename). Includes the root-aware checks: Blocks spec is an existing spec, resolved
    needs a real Mockup source (file under root, http(s):// or figma:) and a mockup-audit.md row
    per code. Returns a list of violations; never raises."""
    try:
        return _check_debt_impl(root, spec_id, extra_texts)
    except Exception as e:  # pragma: no cover - defensive
        return [_v('R4', f'check_debt failed internally ({e}).', 'Report this to the AIDD maintainers.')]


def _strip_code_spans(text):
    """FR-011: drop inline `code spans` so sibling-spec examples do not count as codes."""
    try:
        return re.sub(r'`[^`\n]*`', '', text)
    except Exception:
        return text


def _check_debt_impl(root, spec_id, extra_texts):
    root = Path(root)
    specs = root / 'specs'
    d = specs / str(spec_id)
    texts = {}
    for k, v in (extra_texts or {}).items():
        if isinstance(v, str):
            texts[str(k).replace('\\', '/').split('/')[-1].lower()] = v
    if any(_too_large(v) for v in texts.values()):
        return [_v('R4', 'An artifact is too large (> 2 MB) to be scanned.', 'Shrink the file below 2 MB.')]
    spec_t = texts['spec.md'] if 'spec.md' in texts else _read(d / 'spec.md')
    raw = _norm_nl(spec_t)
    t = _clean(spec_t)

    universe = _codes(raw)
    for n in ('plan.md', 'contracts.md'):
        universe |= _codes(_norm_nl(texts[n] if n in texts else _read(d / n)))
    ids = _spec_ids(specs)
    for sid in ids:
        if sid == d.name:
            continue
        try:
            files = [f for f in (specs / sid).glob('*.md') if f.name != 'mockup-audit.md']
        except Exception:
            files = []
        for f in files:
            universe |= _codes(_strip_code_spans(_norm_nl(_read(f))))
    audited = _audited_codes(specs, d.name, texts.get('mockup-audit.md'))

    out = []
    waived = _waived_visual(t)
    shape, rows = _debt_table(t)
    out += list(shape or [])
    if waived:
        covered = set().union(*[r['codes'] for r in rows]) if rows else set()
        missing = sorted((universe - audited) - covered)
        if missing:
            out.append(_missing_debt_violation(waived, missing))
    for r in rows:
        label = ', '.join(sorted(r['codes'])) or '?'
        if r['blocks_spec'] and ids and not _match_spec_ref(r['blocks_spec'], ids):
            out.append(_v('R4', f'Visual debt row {label}: "Blocks spec" = "{r["blocks_spec"]}" is not an existing spec id.',
                          'Set Blocks spec to the id (or numeric prefix) of an existing specs/<id> folder.'))
        if r['status'] == 'resolved' and not _junk_source(r['source']):
            src = _plain(r['source']).strip('"\'')
            good = bool(re.match(r'(?:https?://\S+|figma:\S+)$', src, re.I)) or _inside_exists(root, src, want_file=True)
            if not good:
                out.append(_v('R4', f'Visual debt row {label} is resolved but Mockup source "{src[:80]}" is not an '
                                    'existing file under the project root, an http(s):// URL or figma:<ref>.',
                              'Point Mockup source at the real mockup (existing file, URL or figma: reference).'))
        if r['status'] == 'resolved':
            lacking = sorted(r['codes'] - audited)
            if lacking:
                out.append(_v('R4', f'Visual debt row {label} is resolved but {", ".join(lacking)} have no '
                                    'mockup-audit.md table row.',
                              f'Run Steps 0/1/1.5 and write a mockup-audit.md row for {", ".join(lacking)} '
                              'before marking the debt resolved.'))
    return _dedup(out)


def open_debt_blocking(root):
    """{spec_id: [rows]} — open Visual-debt rows found in ANY specs/*/spec.md, indexed by the
    existing spec they block (a row in another spec naming X blocks X). Each row dict also
    carries 'in_spec' (the spec whose spec.md lists it). Never raises."""
    res = {}
    try:
        specs = Path(root) / 'specs'
        ids = _spec_ids(specs)
        for name in ids:
            t = _read(specs / name / 'spec.md')
            if not t or 'debt' not in t.lower():
                continue
            for row in open_visual_debt(t):
                for target in _match_spec_ref(row['blocks_spec'], ids):
                    r = dict(row)
                    r['in_spec'] = name
                    res.setdefault(target, []).append(r)
    except Exception:
        pass
    return res


# ----------------------------------------------------------------- public API

_EVID_KINDS = ('screenshot', 'command-output', 'query-result', 'log', 'manual-test', 'not-verified')
_FILE_KINDS = ('screenshot', 'command-output', 'query-result', 'log')
_IMG_EXT = ('.png', '.jpg', '.jpeg', '.webp')
_URL_RE = re.compile(r'https?://\S+$', re.I)
_DRIVE_RE = re.compile(r'[A-Za-z]:')
_CODE_TOKEN_RE = re.compile(r'[A-Z]+-\d+(?:-F\d+)?')
_REDESIGN_REF_RE = re.compile(r'\bT-\d+\b|\b\d{3}-[a-z][\w-]*|\bspec[\s-]*\d{2,3}\b', re.I)


def _needs_evidence(code):
    c = (code or '').upper()
    return bool(re.match(r'SCREEN-\d+', c) or re.match(r'API-\d+', c) or re.search(r'-F\d+$', c))


def _evidence_path(spec_dir, root, rel):
    """(status, path): status 'ok' | 'missing' | 'unchecked' (no base dir given) | 'bad' (escape/absolute).
    Drive letters, UNC, absolute paths and any `..` segment are never evidence."""
    r = (rel or '').strip().strip('`').strip()
    if (not r or len(r) > 1000 or _DRIVE_RE.match(r) or r.startswith(('\\', '/'))
            or '..' in re.split(r'[\\/]+', r)):
        return 'bad', None
    bases = [b for b in (spec_dir, root) if b is not None]
    if not bases:
        return 'unchecked', None
    for b in bases:
        if _inside_exists(b, r, want_file=True):
            try:
                return 'ok', (Path(b).resolve() / r.replace('\\', '/')).resolve()
            except Exception:
                return 'ok', None
    return 'missing', None


def _check_evidence_row(code, kind, evid, who, ledger_ok, spec_dir, root, last_edit_ts):
    out = []
    fix_row = 'Fix the row in "## Execution evidence": | Code | Kind | Evidence | Verified by |.'
    if kind not in _EVID_KINDS:
        return [_v('R10', f'Execution evidence {code}: Kind "{kind}" is not one of {" | ".join(_EVID_KINDS)}.',
                   f'Set Kind of {code} to one of: {" | ".join(_EVID_KINDS)}.')]
    if who not in ('agent', 'user'):
        out.append(_v('R10', f'Execution evidence {code}: "Verified by" must be agent or user, got "{who[:30]}".',
                      f'Set "Verified by" of {code} to agent or user.'))
    ev_plain = evid.strip().strip('`').strip()

    def check_file(rel):
        st, p = _evidence_path(spec_dir, root, rel)
        if st == 'bad':
            return [_v('R10', f'Execution evidence {code}: "{rel[:60]}" is not a path inside the spec dir or project root '
                              '(drive letters, UNC, absolute paths and ".." are not evidence).',
                       f'Point {code} Evidence to a file saved under the spec dir or the project (relative path).')]
        if st == 'missing':
            return [_v('R10', f'Execution evidence {code}: file "{rel[:60]}" does not exist.',
                       f'Run it for real, save the output/screenshot at that path (relative to the spec dir or '
                       f'project root), then rewrite qa-audit.md.')]
        if st == 'ok' and last_edit_ts is not None and p is not None:
            m = _mtime(p)
            if m is not None and m < last_edit_ts:
                return [_v('R10', f'Execution evidence {code}: "{rel[:60]}" is older than the last code edit (stale).',
                           f'Re-run after the last code change and save fresh evidence for {code}, then rewrite qa-audit.md.')]
        return []

    if kind in _FILE_KINDS:
        if _URL_RE.match(ev_plain):
            return out
        if kind == 'screenshot' and not ev_plain.lower().endswith(_IMG_EXT):
            out.append(_v('R10', f'Execution evidence {code}: a screenshot must be .png/.jpg/.jpeg/.webp, got "{ev_plain[:60]}".',
                          f'Save a real screenshot as .png/.jpg/.jpeg/.webp for {code}, or use another Kind.'))
            return out
        return out + check_file(ev_plain)
    if kind == 'manual-test':
        q = _user_quote(ev_plain)
        if q is not None:
            if _words(q) >= 3:
                return out
            out.append(_v('R10', f'Execution evidence {code}: the user quote needs 3+ words.',
                          f'Quote the user\'s own words (3+): user — "<what the user said after testing {code}>".'))
            return out
        return out + check_file(ev_plain) if ev_plain else out + [
            _v('R10', f'Execution evidence {code}: manual-test has no evidence.',
               f'Write user — "<quote 3+ words>" or a path for {code}.')]
    # not-verified
    if ledger_ok:
        out.append(_v('R10', f'{code} is "not-verified" but its Mapping ledger Status is still ✅.',
                      f'Change the Status of {code} to ⚠️ PARTIAL until the user runs the human test script.'))
    st, _p = _evidence_path(spec_dir, root, ev_plain)
    if st in ('bad', 'missing'):
        out.append(_v('R10', f'Execution evidence {code}: not-verified needs the path of an existing human test script '
                             f'("{ev_plain[:60]}" is not).',
                      f'Write the test script the user must run (e.g. specs/<id>/human-test-{code}.md) and cite its path.'))
    return out


def _check_bug_reports(t):
    out = []
    tb = _table(t, r'bug reports\b')
    if tb is None:
        return out
    header, rows = tb
    hn = [_hdr(header, i) for i in range(len(header))]

    def col(name):
        return next((i for i, h in enumerate(hn) if h.startswith(name)), None)
    ci, cr, cf, cs = col('code'), col('root cause'), col('fix'), col('pattern sweep')
    if None in (ci, cr, cf, cs):
        if rows:
            out.append(_v('R11', 'Bug reports table header must be | # | Code | Symptom | Root cause | Fix | Pattern sweep |.',
                          'Rewrite the Bug reports header with those columns, in that order.'))
        return out
    seen = {}
    for r in rows:
        r = r + [''] * (len(header) - len(r))
        code = _plain(r[ci]).upper()
        if not code:
            continue
        n = seen[code] = seen.get(code, 0) + 1
        if n >= 2:
            if _blank_answer(r[cr]):
                out.append(_v('R11', f'Bug report #{n} for {code} has no Root cause (repeat report).',
                              f'Analyse why {code} failed again and write the Root cause (not the symptom) in that row.'))
            if _blank_answer(r[cs]):
                out.append(_v('R11', f'Bug report #{n} for {code} has no Pattern sweep (repeat report).',
                              'Write what you searched and where, e.g. `grep -rn "fmt(" forms/` → 4 hits fixed.'))
        if n >= 3:
            fx = _plain(r[cf])
            if 'redesign' not in fx.lower() or not _REDESIGN_REF_RE.search(fx):
                out.append(_v('R11', f'Bug report #{n} for {code}: from the 3rd report the Fix must state "redesign" '
                                     'with a spec id or task reference.',
                              f'Open a redesign for {code} and write Fix: "redesign — spec <id>" or "redesign — T-nn".'))
    return out


def check_qa(text, spec_dir=None, root=None, last_edit_ts=None):
    """R10 (execution evidence) and R11 (root cause on repeat) over qa-audit.md. Never raises.
    Freshness runs only when `last_edit_ts` is given (hook path). Without spec_dir/root the
    existence of evidence files cannot be verified and is skipped."""
    try:
        if _too_large(text):
            return [_v('R10', 'qa-audit.md file too large (> 2 MB): it is not scanned.', 'Shrink qa-audit.md below 2 MB.')]
        t = _clean(text)
        out = []
        sd = Path(spec_dir) if spec_dir is not None else None
        rt = Path(root) if root is not None else None

        # ledger
        status = {}
        lt = _table(t, r'mapping ledger\b')
        if lt is not None:
            header, rows = lt
            si = next((i for i in range(len(header)) if _hdr(header, i).startswith('status')), 1)
            for r in rows:
                if not r or not _plain(r[0]):
                    continue
                code = _plain(r[0]).upper()
                stt = _plain(r[si]) if si < len(r) else ''
                status[code] = status.get(code, False) or stt.startswith('✅')
        exempt = set()
        for r in (_table(t, r'open exceptions\b') or ([], []))[1]:
            if r:
                exempt.update(_CODE_TOKEN_RE.findall(_plain(r[0]).upper()))
        required = [c for c, g in status.items() if g and _needs_evidence(c) and c not in exempt]

        et = _table(t, r'execution evidence\b')
        ev_rows = {}
        idx = [0, 1, 2, 3]
        if et is not None:
            header, rows = et
            hn = [_hdr(header, i) for i in range(len(header))]
            idx = [hn.index(n) if n in hn else None for n in ('code', 'kind', 'evidence', 'verified by')]
            if None in idx:
                if required or rows:
                    out.append(_v('R10', 'Execution evidence table header must be | Code | Kind | Evidence | Verified by |.',
                                  'Rewrite the header of "## Execution evidence" with exactly those columns.'))
            else:
                for r in rows:
                    r = r + [''] * (len(header) - len(r))
                    code = _plain(r[idx[0]]).upper()
                    if code:
                        ev_rows.setdefault(code, []).append(
                            (_plain(r[idx[1]]).lower(), r[idx[2]], _plain(r[idx[3]]).lower()))
        if None not in idx:
            for code in required:
                if code not in ev_rows:
                    out.append(_v('R10', f'{code} is ✅ in the Mapping ledger but has no row in "Execution evidence"'
                                         + ('' if et is not None else ' (the section does not exist)') + '.',
                                  f'Add "## Execution evidence" with | Code | Kind | Evidence | Verified by | if missing. '
                                  f'Run {code} for real and add | {code} | <kind> | <path or user quote> | agent/user |; '
                                  'if you cannot run it, use Kind not-verified with a human test script and set its Status to ⚠️ PARTIAL.'))
            for code, lst in ev_rows.items():
                if code in exempt:
                    continue
                for kind, evid, who in lst:
                    out += _check_evidence_row(code, kind, evid, who, status.get(code, False), sd, rt, last_edit_ts)
        return out + _check_bug_reports(t)
    except Exception as e:  # pragma: no cover - defensive
        return [_v('R10', f'Could not parse qa-audit.md ({e}).', 'Fix the markdown tables so they parse, then retry.')]


def check_content(kind, text, spec_dir=None, root=None):
    """Structural validity of ONE artifact. kind: spec | tasks | plan | qa. Never raises."""
    try:
        kind = (kind or '').strip().lower()
        if kind in ('spec', 'tasks') and _too_large(text):
            return [_v('R2' if kind == 'spec' else 'R1',
                       f'{kind}.md file too large (> 2 MB): it is not scanned.',
                       f'Shrink {kind}.md (remove blank lines / pasted blobs) below 2 MB.')]
        if kind == 'spec':
            return _check_spec(text)
        if kind == 'tasks':
            return _check_tasks(text)
        if kind == 'qa':
            return check_qa(text, spec_dir, root)
        return []
    except Exception as e:  # pragma: no cover - defensive
        return [_v('R1' if kind == 'tasks' else 'R2', f'Could not parse the {kind} artifact ({e}).',
                   'Fix the markdown tables so they parse, then retry.')]


def _table_exclusions(cells):
    return [i for i, c in enumerate(cells) if re.sub(r'[\s*`_]+', ' ', c).strip().lower() in _HASH_EXCLUDED]


def approval_hash(tasks_text):
    """sha1[:12] of the text with the `Approved:` lines removed, newlines normalised to \\n,
    trailing whitespace stripped (per line and at the end), and (M7) lines/cells named `Status`,
    `Tracker ref`, `PR/Spec ref` excluded so write-back tools do not void an approval."""
    t = _norm_nl(tasks_text)
    if len(t) > MAX_CHARS:  # never scanned: a stable fingerprint of the raw text; never valid
        return hashlib.sha1(t.encode('utf-8', 'replace')).hexdigest()[:12]
    lines = t.split('\n')
    out = []
    excl = []   # excluded column indexes of the table we are in
    n = len(lines)
    for i, line in enumerate(lines):
        s = line.rstrip()
        if not s:
            out.append('')
            continue
        if _APPROVED_LINE_RE.match(s) or _NAMED_LINE_RE.match(s):
            continue
        if s.lstrip().startswith('|'):
            cells = _split_row(s)
            nxt = lines[i + 1].strip() if i + 1 < n else ''
            if nxt.startswith('|') and _is_sep(_split_row(nxt)) and not _is_sep(cells):
                excl = _table_exclusions(cells)      # header row: kept as is
            elif excl and not _is_sep(cells):
                s = '| ' + ' | '.join(c for j, c in enumerate(cells) if j not in excl) + ' |'
        else:
            excl = []
        out.append(s)
    return hashlib.sha1('\n'.join(out).rstrip().encode('utf-8')).hexdigest()[:12]


def _approval_lines(tasks_text):
    """(all `Approved:` lines, [(date, hash)] of the well-formed ones) — per line, linear."""
    t = _norm_nl(tasks_text)
    if len(t) > MAX_CHARS:
        return [], []
    allm, valid = [], []
    for line in t.split('\n'):
        if _APPROVED_LINE_RE.match(line):
            allm.append(line)
            m = _APPROVED_FULL_RE.match(line)
            if m:
                valid.append((m.group(1), m.group(2).lower()))
    return allm, valid


def approval_line(tasks_text):
    """(date, hash) of the FIRST well-formed `Approved:` line, else None."""
    _all, valid = _approval_lines(tasks_text)
    return valid[0] if valid else None


def approval_valid(tasks_text):
    """True iff there is exactly ONE `Approved:` line (duplicates void the approval), it is well
    formed and its hash equals approval_hash(text)."""
    allm, valid = _approval_lines(tasks_text)
    if len(allm) != 1 or len(valid) != 1:
        return False
    return valid[0][1] == approval_hash(tasks_text)


def required_domains(spec_dir):
    """FR-002 closing audits: `security` + `functional` always; `ui` / `backend` / `database` by what
    the tasks touch; `performance` only when the tasks touch a hot path, the database or the UI."""
    doms = {'security', 'functional'}
    try:
        d = Path(spec_dir)
        tasks = _read(d / 'tasks.md')
        if re.search(r'\b(SCREEN|CTL|COMP)-\d+', tasks):
            doms.add('ui')
        if re.search(r'\bAPI-\d+', tasks):
            doms.add('backend')
        if (d / 'data-model.md').exists() or re.search(
                r'stored procedure|migration|\.sql\b|schema', tasks, re.I):
            doms.add('database')
        if doms & {'ui', 'database'} or _HOT_PATH_RE.search(tasks):
            doms.add('performance')
    except Exception:
        pass
    return doms


def is_low_tier(model):
    """True iff the model name is the lowest tier (haiku); empty/None/'inherit' -> False (R14)."""
    try:
        return bool(LOWEST_TIER_RE.search(str(model or '')))
    except Exception:
        return False


def _is_pre_dispatch(event):
    """True iff a `subagent` row was written by the PreToolUse recorder (detail phase=='pre'): an
    attribution trail only — the dispatch may have been denied or failed, and its model unresolved."""
    try:
        return (event.get('detail') or {}).get('phase') == 'pre'
    except Exception:
        return False


def _subagent_counts(event):
    """A subagent evidence event counts for gates unless it is a PreToolUse attribution row
    (phase 'pre', never an audit) or its model is low tier (old events count)."""
    try:
        if _is_pre_dispatch(event):
            return False
        return not is_low_tier((event.get('detail') or {}).get('model'))
    except Exception:
        return True


def _uncovered_reasons(ev, root, session, domains, since_ts, spec_dir=None):
    """{domain: 'tier'|'none'} for uncovered domains: 'tier' when only low-tier subagents match it."""
    try:
        missing = _uncovered(ev, root, session, domains, since_ts, spec_dir=spec_dir)
    except Exception:
        missing = set(domains)
    try:
        low = [e for e in ev.events(root, session, 'subagent')
               if e.get('ts', 0) > since_ts and not _is_pre_dispatch(e) and not _subagent_counts(e)]
    except Exception:
        low = []
    out = {}
    for dom in missing:
        tier = False
        if dom in DOMAIN_RE:
            for e in low:
                det = e.get('detail') or {}
                if DOMAIN_RE[dom].search(f"{det.get('head', '')} {det.get('desc', '')}"):
                    tier = True
                    break
        out[dom] = 'tier' if tier else 'none'
    return out


def _uncovered(ev, root, session, domains, since_ts, spec_dir=None):
    """Domains (subset of `domains`) left without a DISTINCT matching subagent (M9): maximum
    bipartite matching domains -> subagent events; one subagent covers one domain only.

    aidd:FR-206 aidd:AC-210 When `spec_dir` is given, ONE counting subagent after `since_ts` whose
    first line is a valid `CLOSING AUDIT [domains: ...] [tasks:<h8>] [verify:<v8>]` header
    (closing_audit_covers) covers every domain at once (early return). Below it the per-domain
    matching is unchanged, so legacy per-domain auditors keep working."""
    try:
        events = [e for e in ev.events(root, session, 'subagent')
                  if e.get('ts', 0) > since_ts and _subagent_counts(e)]
    except Exception:
        events = []
    if spec_dir is not None and events:
        try:
            gate2 = _is_gate2(ev, root, spec_dir)
            if any(closing_audit_covers(e, spec_dir, domains, gate2, ev, root) for e in events):
                return set()
        except Exception:
            pass   # fail closed: fall through to the per-domain matching
    doms = sorted(d for d in domains if d in DOMAIN_RE)
    unknown = {d for d in domains if d not in DOMAIN_RE}
    texts = [f"{(e.get('detail') or {}).get('head', '')} {(e.get('detail') or {}).get('desc', '')}" for e in events]
    cand = {dom: [i for i, tx in enumerate(texts) if DOMAIN_RE[dom].search(tx)] for dom in doms}
    owner = {}

    def assign(dom, seen):
        for i in cand[dom]:
            if i in seen:
                continue
            seen.add(i)
            if i not in owner or assign(owner[i], seen):
                owner[i] = dom
                return True
        return False

    for dom in sorted(doms, key=lambda x: (len(cand[x]), x)):
        assign(dom, set())
    matched = set(owner.values())
    return {d for d in doms if d not in matched} | unknown


def audit_since(edits):
    """Timestamp an auditor subagent must postdate to cover the code edits.

    The last AIDD_R7_FIX_EDITS (default 3, 0 = strict) code edits are tolerated: small fixes made
    after an audit (typically its own findings) do not force a full re-audit. Larger changes do.
    """
    try:
        tol = max(0, int(os.environ.get('AIDD_R7_FIX_EDITS', '3')))
    except ValueError:
        tol = 3
    ts = sorted(e['ts'] for e in edits)
    if not ts:
        return 0.0
    return ts[-1] if tol == 0 else (ts[-tol - 1] if len(ts) > tol else 0.0)


def uncovered_domains(root, session, spec_id, since_ts, spec_dir=None):
    """M9: required domains of `spec_id` (root/specs/<id>, or `spec_dir`) that still lack a
    DISTINCT subagent event after `since_ts`. Fail-closed: no evidence module => all uncovered."""
    d = Path(spec_dir) if spec_dir else Path(root) / 'specs' / str(spec_id)
    doms = required_domains(d)
    ev = _evidence()
    if ev is None:
        return set(doms)
    try:
        return _uncovered(ev, root, session, doms, since_ts, spec_dir=d)
    except Exception:
        return set(doms)


def domain_covered(root, session, domain, since_ts):
    """Compatibility wrapper: True iff SOME subagent event after since_ts matches the domain
    (no distinctness across domains — use uncovered_domains for the real R7 check)."""
    ev = _evidence()
    if domain not in DOMAIN_RE or ev is None:
        return False
    try:
        return domain not in _uncovered(ev, root, session, {domain}, since_ts)
    except Exception:
        return False


def is_protected_path(path):
    """R9: the evidence log and active_spec pointer are writable only by hooks."""
    try:
        p = posixpath.normpath(str(path).replace('\\', '/')).lower()
    except Exception:
        return False
    return bool(re.search(r'(^|/)\.aidd/evidence(/|$)', p) or re.search(r'(^|/)\.aidd/active_spec$', p)
                or re.search(r'(^|/)\.claude/projects/[^/]+/[^/]+\.jsonl$', p))


# ------------------------------------------------------------- check_spec_dir

def _read(p):
    try:
        pp = Path(p)
        if pp.stat().st_size > MAX_CHARS * 2:   # never even load huge files (callers use _big)
            return ''
        return pp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return ''


def _big(p):
    try:
        return Path(p).stat().st_size > MAX_CHARS
    except Exception:
        return False


def _evidence():
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import aidd_evidence
        return aidd_evidence
    except Exception:
        return None


def _mtime(p):
    try:
        return Path(p).stat().st_mtime
    except Exception:
        return None


def _proj_root(d, root=None):
    d = Path(d)
    if d.parent.name == 'specs':
        return d.parent.parent
    return Path(root) if root else d


def check_spec_dir(spec_dir, root=None, session=None, static_only=False):
    """All static rules + evidence-based rules for a whole spec. `static_only=True` skips
    the evidence log (used by check_spec.py). Never raises."""
    out = []
    try:
        d = Path(spec_dir)
        spec_p, plan_p, tasks_p, qa_p = (d / 'spec.md', d / 'plan.md', d / 'tasks.md', d / 'qa-audit.md')
        proj = _proj_root(d, root)
        spec_big, tasks_big = _big(spec_p), _big(tasks_p)
        spec_t, tasks_t = ('' if spec_big else _read(spec_p)), ('' if tasks_big else _read(tasks_p))
        if not spec_p.exists():
            out.append(_v('R2', f'{d.name}/spec.md does not exist.', 'Create spec.md (templates/spec.md) first.'))
        elif spec_big:
            out.append(_v('R2', 'spec.md file too large (> 2 MB): it is not scanned.', 'Shrink spec.md below 2 MB.'))
        else:
            t = _clean(spec_t)
            out += _check_route(t) + _check_checklist(t) + _repo_violations(t, proj)
            if d.parent.name == 'specs':
                out += check_debt(proj, d.name, {'spec.md': spec_t})
            else:
                out += _debt_static(t, _norm_nl(spec_t))
        if tasks_p.exists():
            if tasks_big:
                out.append(_v('R1', 'tasks.md file too large (> 2 MB): it is not scanned.', 'Shrink tasks.md below 2 MB.'))
            else:
                out += _check_tasks(tasks_t)
                allm, valid = _approval_lines(tasks_t)
                if not valid:
                    out.append(_v('R6', 'tasks.md has no valid "Approved: YYYY-MM-DD hash:<12hex>" line (approval pending).',
                                  'Present the tasks to the user (AskUserQuestion), then run `aidd rules approve <spec_dir>`.'))
                elif len(allm) != 1:
                    out.append(_v('R6', 'tasks.md has several "Approved:" lines — approval is void.',
                                  'Keep exactly one "Approved:" line, re-present the tasks to the user, then run '
                                  '`aidd rules approve <spec_dir>`.'))
                elif valid[0][1] != approval_hash(tasks_t):
                    out.append(_v('R6', 'tasks.md changed after approval (hash mismatch) — approval is void.',
                                  'Re-present the changed tasks to the user, then run `aidd rules approve <spec_dir>`.'))
        if qa_p.exists():
            if _big(qa_p):
                out.append(_v('R10', 'qa-audit.md file too large (> 2 MB): it is not scanned.', 'Shrink qa-audit.md below 2 MB.'))
            else:
                out += check_qa(_read(qa_p), d, proj)
        if static_only:
            return _dedup(out)

        ev = _evidence()
        if ev is None:
            out.append(_v('R5', 'Evidence module unavailable — chain order cannot be verified.',
                          'Restore skill/scripts/aidd_evidence.py (reinstall AIDD hooks).'))
            return _dedup(out)
        root = Path(root) if root else ev.find_root(d)
        out += _evidence_rules(ev, d, root, session, spec_t, tasks_p.exists(), plan_p, tasks_p, qa_p)
    except Exception as e:  # pragma: no cover - defensive
        out.append(_v('R5', f'check_spec_dir failed internally ({e}).', 'Report this to the AIDD maintainers.'))
    return _dedup(out)


def _dedup(vs):
    seen, res = set(), []
    for v in vs:
        k = (v['rule'], v['message'])
        if k not in seen:
            seen.add(k)
            res.append(v)
    return res


# ---------------------------------------------------------------- quote checks

def _norm(ev, text):
    f = getattr(ev, 'normalise', None)
    if callable(f):
        try:
            return f(text)
        except Exception:
            pass
    s = unicodedata.normalize('NFKD', str(text or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r'[\W_]+', ' ', s).strip()


def _answer_texts(detail):
    """The user's ANSWER strings of an `answer` event — from `pairs` ONLY (never raw text, never the
    agent-authored question text)."""
    texts = []
    pairs = detail.get('pairs')
    if isinstance(pairs, (list, tuple)):
        for p in pairs:
            if isinstance(p, dict):
                a = p.get('a', p.get('answer'))
                if a is not None:
                    texts.append(str(a))
            elif isinstance(p, (list, tuple)) and len(p) >= 2:
                texts.append(str(p[-1]))
    elif isinstance(pairs, dict):
        texts.extend(str(v) for v in pairs.values())
    return texts


def spec_first_edit_ts(ev, root, spec_name):
    """ts of the spec's first `spec_edit` event (0.0 when none yet => any ts is acceptable)."""
    try:
        tss = [e['ts'] for e in ev.events(root, None, 'spec_edit') if (e.get('detail') or {}).get('spec') == spec_name]
        return min(tss) if tss else 0.0
    except Exception:
        return 0.0


PRE_BUILD_FILES = ('spec.md', 'plan.md', 'tasks.md')


def _spec_file_edit_ts(ev, root, spec_name, files):
    """ts list of recorded `spec_edit` events of `spec_name` touching one of `files` (any session)."""
    try:
        sn, fs = str(spec_name).lower(), {f.lower() for f in files}
        return [e['ts'] for e in ev.events(root, None, 'spec_edit')
                if str((e.get('detail') or {}).get('spec', '')).lower() == sn
                and str((e.get('detail') or {}).get('file', '')).lower() in fs]
    except Exception:
        return []


def mapper_since(ev, root, spec_dir):
    """FR-002: ts the Mapper/Alignment subagent must postdate — the FIRST recorded draft of spec.md
    (later spec.md edits do not demand a new subagent). Falls back to spec.md's mtime when no edit was
    recorded; None when spec.md does not exist."""
    d = Path(spec_dir)
    tss = _spec_file_edit_ts(ev, root, d.name, ('spec.md',))
    return min(tss) if tss else _mtime(d / 'spec.md')


def pre_build_since(ev, root, spec_dir, session=None):
    """FR-002/FR-003: ts the ONE pre-build coherence audit must postdate: the last change of spec.md,
    plan.md or tasks.md (mtime or recorded `spec_edit`, whichever is later) and the last graph rebuild
    by find_spec in `session` (the pre-build audit absorbs the graph-coherence audit).

    FR-010: the last AIDD_R5_FIX_EDITS (default 3, 0 = strict) RECORDED edits are tolerated. A file
    with recorded edits counts only those (its mtime moves with every edit); a file with none keeps
    its mtime, strict (fail-closed). Graph rebuilds stay strict."""
    d = Path(spec_dir)
    ts, strict = [], []
    for f in PRE_BUILD_FILES:
        rec = _spec_file_edit_ts(ev, root, d.name, (f,))
        m = _mtime(d / f)
        if rec:
            ts += rec
        elif m is not None:
            strict.append(m)
    try:
        tol = max(0, int(os.environ.get('AIDD_R5_FIX_EDITS', '3')))
    except ValueError:
        tol = 3
    ts.sort()
    # Unlike audit_since, a short history keeps ts[0]: an audit must still postdate the first draft.
    since = (ts[-1] if tol == 0 else ts[max(0, len(ts) - tol - 1)]) if ts else 0.0
    try:
        strict += [e['ts'] for e in ev.events(root, session, 'find_spec')
                   if (e.get('detail') or {}).get('rebuilt') and (e.get('detail') or {}).get('ok') is not False]
    except Exception:
        pass
    return max([since] + strict)


def pre_build_audit_done(ev, root, session, spec_dir):
    """FR-003: True iff ONE independent subagent (R14: not low tier) of `session` ran after
    pre_build_since(ev, root, spec_dir, session). Required once before tasks approval, not after
    every spec/plan edit. Fail-closed: False on any error."""
    try:
        since = pre_build_since(ev, root, spec_dir, session)
        return any(e.get('ts', 0) > since and _subagent_counts(e)
                   for e in ev.events(root, session, 'subagent'))
    except Exception:
        return False


def _contains_words(hay, needle):
    return (' ' + needle + ' ') in (' ' + hay + ' ')


def quote_verified(ev, root, quote, since_ts=0.0):
    """M3: `quote` (word-normalised, accent/punctuation-folded) must be found as whole words in a
    `prompt` event (needs >= 5 words) or in a user `answer` (needs >= 2 words), both newer than
    `since_ts`."""
    nq = _norm(ev, quote)
    n = len(nq.split())
    if n < 2:
        return False
    try:
        if n >= 5:
            for e in ev.events(root, None, 'prompt'):
                if e.get('ts', 0) > since_ts and _contains_words(_norm(ev, (e.get('detail') or {}).get('text', '')), nq):
                    return True
        for e in ev.events(root, None, 'answer'):
            if e.get('ts', 0) > since_ts and any(_contains_words(_norm(ev, a), nq)
                                                 for a in _answer_texts(e.get('detail') or {})):
                return True
    except Exception:
        return False
    return False


def _evidence_rules(ev, d, root, session, spec_t, has_tasks, plan_p, tasks_p, qa_p):
    out = []
    t = _clean(spec_t) if not _too_large(spec_t) else ''

    # M1/M2: unanswered or Proposed rows block planning
    out += _alignment_violations(t)

    # R5: every user quote is verified against recorded prompts / answers (M3)
    quotes = []
    for r in (_table(t, r'pipeline route\b') or ([], []))[1]:
        if len(r) > 3 and _user_quote(r[3]):
            quotes.append(_user_quote(r[3]))
    for r in (_table(t, r'minimum requirements checklist') or ([], []))[1]:
        if len(r) > 2 and _user_quote(r[2]):
            quotes.append(_user_quote(r[2]))
    since_q = spec_first_edit_ts(ev, root, d.name)
    for q in quotes:
        try:
            ok = quote_verified(ev, root, q, since_q)
        except Exception:
            ok = False
        if not ok:
            out.append(_v('R5', f'Quote not found in any recorded user prompt/answer: "{q[:60]}".',
                          'Quote the user\'s exact words from a prompt written AFTER spec.md was first drafted '
                          '(5+ words), or ask the user (AskUserQuestion) and quote their answer verbatim '
                          '(2+ words).'))

    # R5 (FR-002/FR-003 phases): find_spec + Mapper once after the FIRST spec.md draft + ONE pre-build
    # coherence audit before tasks approval (no subagent demanded after each spec/plan edit)
    try:
        if not ev.last_event(root, 'find_spec', session):
            out.append(_v('R5', 'No find_spec run recorded in this session.',
                          'Run `python skill/scripts/find_spec.py` (Step -1) before planning.'))
        # aidd:FR-206 aidd:AC-211 advisory (default) stops demanding the Mapper and the pre-build
        # subagent; find_spec, quotes and Proposed rows above/below stay blocking in both modes.
        strict = r5_audit_mode() == 'strict'
        sm = mapper_since(ev, root, d) if strict else None
        if sm is not None and not [e for e in ev.events(root, session, 'subagent') if e['ts'] > sm and _subagent_counts(e)]:
            out.append(_v('R5', 'No independent subagent (Mapper/Alignment) ran after the first draft of spec.md.',
                          'Dispatch a Mapper/Alignment subagent (Agent tool) over spec.md before writing plan.md.'))
        if has_tasks:
            if not plan_p.exists():
                out.append(_v('R5', 'tasks.md exists but plan.md does not.', 'Write plan.md (Step 3) before tasks.md.'))
            elif strict and not approval_valid(_read(tasks_p)) and not pre_build_audit_done(ev, root, session, d):
                out.append(_v('R5', 'No pre-build coherence audit: no independent subagent ran after the last edit '
                                    'of spec.md/plan.md/tasks.md (or the last graph rebuild).',
                              'Dispatch ONE pre-build coherence auditor subagent (medium or high tier, never haiku) '
                              'over spec.md, plan.md, tasks.md, the graph and the estimates, then run '
                              '`aidd rules approve <spec_dir>`.'))
    except Exception as e:
        out.append(_v('R5', f'Evidence log unreadable ({e}).', 'Check .aidd/evidence/events.toon.'))

    # R4: open debt naming THIS spec, listed in ANY spec.md (a row in another spec blocks X)
    try:
        blocking = open_debt_blocking(_proj_root(d, root)).get(d.name, [])
    except Exception:
        blocking = []
    for row in blocking:
        where = f' (listed in specs/{row["in_spec"]}/spec.md)' if row.get('in_spec') != d.name else ''
        out.append(_v('R4', f'Open visual debt for {", ".join(sorted(row["codes"]))} blocks spec {row["blocks_spec"]}{where}.',
                      'Ask the user for the mockup source, run Steps 0/1/1.5 for these codes, then mark the row resolved.'))

    # R7: closing audit domains (a DISTINCT subagent per domain)
    if qa_p.exists():
        try:
            edits = ev.events(root, session, 'code_edit')   # D1: code_edit has no spec attribution
            since = audit_since(edits)
        except Exception:
            since = 0.0
        try:
            missing = _uncovered(ev, root, session, required_domains(d), since, spec_dir=d)
        except Exception:
            missing = set(required_domains(d))
        try:
            reasons = _uncovered_reasons(ev, root, session, required_domains(d), since, spec_dir=d)
        except Exception:
            reasons = {}
        for dom in sorted(missing):
            tier = ' (model tier too low, R14: a haiku auditor does not count)' if reasons.get(dom) == 'tier' else ''
            out.append(_v('R7', f'No {dom} auditor subagent ran after the last code edit.{tier}',
                          f'Dispatch a dedicated {dom} auditor subagent (one subagent per domain) whose '
                          f'prompt/description names "{dom}", then rewrite qa-audit.md.'))
    return out


# ===================================================== spec 007: executed verification (R10)

GATE_VERSION = 2   # aidd:FR-204 stored as `gate` in every `approved` event minted by the new routes

_VERIF_HEADING = r'verification\s*$'
_EXPECT_CONTAINS_RE = re.compile(r'^contains\s*:\s*(.+?)\s*$', re.I)
_EXPECT_EXIT0_RE = re.compile(r'^exit\s+0$', re.I)
_MAX_CMD_CHARS = 2000


def r5_audit_mode():
    """aidd:FR-206 aidd:AC-211 'strict' iff env AIDD_R5_AUDIT is `strict` (trimmed, case-insensitive),
    else 'advisory' (the default: the Mapper / pre-build subagent stop blocking)."""
    try:
        return 'strict' if str(os.environ.get('AIDD_R5_AUDIT', '')).strip().lower() == 'strict' else 'advisory'
    except Exception:
        return 'advisory'


def _strip_ticks(s):
    s = (s or '').strip()
    while len(s) >= 2 and s.startswith('`') and s.endswith('`'):
        s = s[1:-1].strip()
    return s


def _expected_contains(expected):
    """The X of an Expected `contains: X`, else None."""
    m = _EXPECT_CONTAINS_RE.match(_strip_ticks(str(expected or '')))
    return m.group(1) if m else None


def parse_verification(spec_text):
    """aidd:FR-205 Rows of `## Verification` as [{n, cmd, expected, covers}] (cells cleaned, backticks
    around the command stripped). Rows with an empty command (template placeholders) are skipped.
    Never raises ([] on any problem)."""
    try:
        if not isinstance(spec_text, str) or _too_large(spec_text):
            return []
        tb = _table(_clean(spec_text), _VERIF_HEADING)
        if tb is None:
            return []
        header, rows = tb
        hn = [_hdr(header, i) for i in range(len(header))]

        def col(*names):
            return next((i for i, h in enumerate(hn) if h in names), None)
        ni, ci, ei, vi = col('#', 'n', 'no', 'no.'), col('command', 'cmd'), col('expected'), col('covers')
        if ci is None:
            return []
        out = []
        for r in rows:
            r = r + [''] * (len(header) - len(r))
            cmd = _strip_ticks(r[ci])
            if not cmd:
                continue
            out.append({'n': r[ni].strip() if ni is not None else str(len(out) + 1),
                        'cmd': cmd,
                        'expected': _strip_ticks(r[ei]) if ei is not None else '',
                        'covers': r[vi].strip() if vi is not None else ''})
        return out
    except Exception:
        return []


def _verification_globs(spec_text, key):
    """Sorted root-relative globs of the optional `<key>: a/**, b/c.py` line inside `## Verification`; a
    template placeholder (`<...>`) is no value. Never raises ([] on any problem)."""
    try:
        t = _clean(spec_text if isinstance(spec_text, str) else '')
        m = re.search(r'^#{2,3}[ \t]+verification[ \t]*$', t, re.I | re.M)
        if not m:
            return []
        rest = t[m.end():]
        nxt = re.search(r'^#{2,3}[ \t]+\S', rest, re.M)
        sec = rest[:nxt.start()] if nxt else rest
        ln = re.search(r'^[ \t>*_-]*' + key + r'\s*:\s*(.+?)\s*$', sec, re.I | re.M)
        if not ln:
            return []
        globs = {g.strip().strip('`').replace('\\', '/') for g in re.split(r'[,;]', ln.group(1))}
        return sorted(g for g in globs if g and '<' not in g and '>' not in g)
    except Exception:
        return []


def verification_scope(spec_text):
    """`Scope:` globs ([] = none: the whole tree counts). With a scope, only edits to files it covers make
    the verification (and the audits that follow it) stale, so other specs can be built in parallel."""
    return _verification_globs(spec_text, 'scope')


def verification_generated(spec_text):
    """`Generated:` globs: files the verification commands REWRITE (graph.json with a timestamp, reports,
    snapshots). They are outputs, not inputs: a run that rewrote them is stable and they never make it stale."""
    return _verification_globs(spec_text, 'generated')


def _norm_cell(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def verification_hash(spec_text):
    """aidd:FR-205 sha1[:12] of the normalised `n|cmd|expected` rows joined by \\n (prose, Covers
    and blank lines do not change it); '' when the table has no row."""
    try:
        rows = parse_verification(spec_text)
        if not rows:
            return ''
        body = '\n'.join(f"{_norm_cell(r['n'])}|{_norm_cell(r['cmd'])}|{_norm_cell(r['expected'])}" for r in rows)
        return hashlib.sha1(body.encode('utf-8')).hexdigest()[:12]
    except Exception:
        return ''


# --- command lint (aidd:FR-205 aidd:AC-218)

_TRIVIAL_RE = re.compile(r'^\s*@?(?:(?:echo|true|rem|type)\b|exit\s+0\b|:(?:\s|$))', re.I)
_FORBIDDEN_SUBSTR = ('.aidd', 'events.toon', 'active_spec', 'gate_spec', 'review.md')
_FORBIDDEN_RE = re.compile(
    r'(?:\bimport\s+|\bfrom\s+|-m\s*)aidd_(?:evidence|rules|status)\b'          # the evidence/rules library
    r'|\baidd_(?:evidence|rules|status)\.py\b'                                   # its scripts run directly
    r'|\baidd_(?:evidence_dir|testing|session_id|rules)\s*=', re.I)              # env that bends the gates
_AIDD_VERIFY_RE = re.compile(r'(?:^|[\s;&|(])aidd(?:\.exe)?\s+verify\b', re.I)  # recursion
_SEG_SPLIT_RE = re.compile(r'&&|\|\||[;&|\n]')
_PREFIX_CMDS = {'call', 'start', 'exec', 'env', 'time', 'nice', 'sudo', 'command', 'nohup'}
_INTERP_RE = re.compile(r'^(?:python(?:\d+(?:\.\d+)*)?|py|node|nodejs|sh|bash|zsh|dash|ksh|cmd|powershell|pwsh|perl|ruby)$')
_PS_VALUE_OPTS = ('executionpolicy', 'windowstyle', 'version', 'inputformat', 'outputformat',
                  'configurationname', 'workingdirectory', 'settingsfile', 'custompipename')
_MANIFEST_SKIP = {'.git', 'node_modules', 'bin', 'obj', '__pycache__', '.aidd', 'specs', '.venv', 'venv',
                  'dist', 'target', '.idea', '.vs'}


def _unquote(t):
    t = t.strip()
    if len(t) >= 2 and t[0] == t[-1] and t[0] in '"\'':
        return t[1:-1]
    return t


def _tokens(seg):
    try:
        toks = shlex.split(seg, posix=False)   # posix=False: Windows backslashes stay intact
    except ValueError:
        toks = seg.split()
    return [u for u in (_unquote(t) for t in toks) if u]


def _exe(tok):
    b = re.split(r'[\\/]', tok)[-1].lower()
    for ext in ('.exe', '.cmd', '.bat', '.com'):
        if b.endswith(ext):
            return b[:-len(ext)]
    return b


def _cmd_start(toks):
    i = 0
    while i < len(toks) and (_exe(toks[i]) in _PREFIX_CMDS or re.match(r'^[A-Za-z_]\w*=', toks[i])):
        i += 1
    return i


def _interp_kind(exe):
    if exe.startswith('python') or exe == 'py':
        return 'python'
    if exe in ('node', 'nodejs'):
        return 'node'
    if exe in ('sh', 'bash', 'zsh', 'dash', 'ksh'):
        return 'sh'
    return exe   # cmd | powershell | pwsh | perl | ruby


def _cluster_flag(tok, bad, stop, value):
    """Walk a short-option cluster (`-Bc`): a char in `bad` -> inline code; in `stop` -> the rest of the
    command belongs to that option (module/script); in `value` -> the option takes a value (attached or
    the next token). Returns ('bad'|'stop'|'value-next'|'ok')."""
    body = tok[1:]
    for k, ch in enumerate(body):
        if ch in bad:
            return 'bad'
        if ch in stop:
            return 'stop'
        if ch in value:
            return 'value-next' if k == len(body) - 1 else 'ok'
    return 'ok'


def _inline_flag(kind, opts):
    """aidd:FR-205 The interpreter option that runs inline code (`python -c`, `node -e`, `cmd /c`,
    `powershell -Command`, ...), looked for among the interpreter's OWN options only (before its
    first script/module argument). None when there is none."""
    i = 0
    while i < len(opts):
        t = opts[i]
        tl = t.lower()
        if kind == 'cmd':
            if re.match(r'^/[ckr]', tl):
                return t
            if tl.startswith('/'):
                i += 1
                continue
            return None
        if kind in ('powershell', 'pwsh'):
            if tl in ('-', '/c'):
                return t
            if tl.startswith(('-', '/')):
                name = tl.lstrip('-/').split(':')[0]
                if name and ('command'.startswith(name) or 'encodedcommand'.startswith(name)
                             or name in ('e', 'ec', 'enc')):
                    return t
                if name in ('file', 'f'):
                    return None   # -File <script>: the existing-path rule decides
                if name in ('ep', 'ex', 'wd') or any(len(name) >= 2 and o.startswith(name) for o in _PS_VALUE_OPTS):
                    i += 2
                    continue
                i += 1
                continue
            return t if kind == 'powershell' else None   # 5.1 runs a bare argument as -Command
        if tl == '-':
            return t   # program read from stdin
        if tl.startswith('--'):
            if kind == 'node' and re.match(r'^--(?:eval|print)(?:=|$)', tl):
                return t
            if tl == '--':
                return None
            i += 1
            continue
        if not tl.startswith('-') or len(tl) < 2:
            return None   # first non-option: the script (or module) owns the rest
        spec = {'python': ('c', 'm', 'WX'), 'node': ('ep', '', 'r'), 'sh': ('c', '', 'oO'),
                'perl': ('eE', '', 'IMmdDxl0'), 'ruby': ('e', '', 'IrCE')}.get(kind, ('', '', ''))
        res = _cluster_flag(t, *spec)
        if res == 'bad':
            return t
        if res == 'stop':
            return None
        i += 2 if res == 'value-next' else 1
    return None


def _find_manifest(root, patterns, max_depth=3, cap=20000):
    """True iff a file matching one of `patterns` (lowercase fnmatch) exists under `root`, at most
    `max_depth` levels deep, skipping vendor/build/AIDD dirs; bounded to `cap` entries."""
    import fnmatch
    try:
        base = Path(root)
        seen = 0
        for dirpath, dirnames, filenames in os.walk(base):
            depth = len(Path(dirpath).relative_to(base).parts)
            dirnames[:] = [] if depth >= max_depth else [d for d in dirnames if d.lower() not in _MANIFEST_SKIP]
            for f in filenames:
                seen += 1
                if seen > cap:
                    return False
                fl = f.lower()
                if any(fnmatch.fnmatch(fl, p) for p in patterns):
                    return True
    except Exception:
        return False
    return False


def _safe_rel(rel):
    r = (rel or '').strip()
    return bool(r) and not (_DRIVE_RE.match(r) or r.startswith(('/', '\\'))
                            or '..' in re.split(r'[\\/]+', r))


def _rel_dir_exists(root, rel):
    if not _safe_rel(rel):
        return False
    try:
        base = Path(root).resolve()
        target = (base / rel.replace('\\', '/')).resolve()
        target.relative_to(base)
        return target.is_dir()
    except Exception:
        return False


def _module_exists(root, tgt):
    """`tests.test_x` (or `tests.test_x.Case.test_y`) resolves to a .py file under root, or the full
    dotted path is a package dir; a path form (`tests/test_x.py`) must be an existing file."""
    if re.search(r'[\\/]', tgt) or tgt.lower().endswith('.py'):
        return _safe_rel(tgt) and _inside_exists(root, tgt, want_file=True)
    parts = [p for p in tgt.split('.') if p]
    if not parts or not all(re.match(r'^\w+$', p) for p in parts):
        return False
    if _rel_dir_exists(root, '/'.join(parts)):
        return True
    return any(_inside_exists(root, '/'.join(parts[:k]) + '.py', want_file=True) for k in range(len(parts), 0, -1))


def _unittest_problem(args, root):
    """None when `python -m unittest <args>` names something real; else the reason."""
    i, targets, start, discover = 0, [], None, False
    while i < len(args):
        a = args[i]
        if a == 'discover' and not targets and not discover:
            discover = True
        elif a in ('-s', '--start-directory'):
            start = args[i + 1] if i + 1 < len(args) else ''
            i += 1
        elif a in ('-p', '--pattern', '-t', '--top-level-directory', '-k'):
            i += 1
        elif a.startswith('-'):
            pass
        elif discover:
            if start is None:
                start = a
        else:
            targets.append(a)
        i += 1
    if discover:
        if root is None or _rel_dir_exists(root, start or '.'):
            return None
        return f'unittest discover start directory "{(start or ".")[:60]}" does not exist under the project'
    if not targets:
        return 'python -m unittest needs a module or `discover -s <dir>`'
    if root is None:
        return None
    for tgt in targets:
        if not _module_exists(root, tgt):
            return f'unittest module "{tgt[:60]}" not found under the project'
    return None


def _runner(toks, root):
    """None when `toks` is not a known test-runner invocation; True when it is and its manifest exists
    (or `root` is None); otherwise the reason string."""
    exe = _exe(toks[0])
    rl = [t.lower() for t in toks[1:]]
    pyish = _interp_kind(exe) == 'python' and _INTERP_RE.match(exe)
    m_idx = None
    if pyish:
        for k, t in enumerate(rl):
            if t == '-m':
                m_idx = k
                break
            if not t.startswith('-'):
                break
    mod = rl[m_idx + 1] if m_idx is not None and m_idx + 1 < len(rl) else None
    if pyish and mod == 'unittest':
        p = _unittest_problem(toks[1:][m_idx + 2:], root)
        return True if p is None else p
    if exe == 'dotnet' and rl[:1] == ['test']:
        name, pats = 'dotnet test', ('*.sln', '*.csproj', '*.fsproj', '*.vbproj')
    elif exe == 'npm' and (rl[:1] in (['test'], ['t']) or (rl[:1] in (['run'], ['run-script']) and len(rl) > 1)):
        name, pats = 'npm', ('package.json',)
    elif exe == 'pytest' or (pyish and mod == 'pytest'):
        name, pats = 'pytest', ('pyproject.toml', 'pytest.ini', 'setup.cfg', 'tox.ini', 'conftest.py')
    elif exe == 'cargo' and rl[:1] == ['test']:
        name, pats = 'cargo test', ('cargo.toml',)
    elif exe == 'go' and rl[:1] == ['test']:
        name, pats = 'go test', ('go.mod',)
    elif exe in ('mvn', 'mvnw') and 'test' in rl:
        name, pats = 'mvn test', ('pom.xml',)
    elif exe in ('gradle', 'gradlew') and 'test' in rl:
        name, pats = 'gradle test', ('build.gradle', 'build.gradle.kts')
    elif exe == 'msbuild':
        name, pats = 'msbuild', ('*.sln', '*.csproj', '*.proj', '*.vbproj', '*.fsproj')
    else:
        return None
    if root is None or _find_manifest(root, pats):
        return True
    return f'{name} but no {" / ".join(pats)} exists in the project'


def _names_existing_file(toks, root):
    """True iff some token is an existing file of the project (relative, inside root). With root None
    a path-looking token (a separator or an extension) is enough (existence not checkable)."""
    for t in toks:
        cand = t.split('=', 1)[1] if t.startswith('-') and '=' in t else t
        cand = _unquote(cand)
        if not cand or cand.startswith('-'):
            continue
        if root is None:
            if re.search(r'[\\/]', cand) or re.search(r'\.[A-Za-z0-9]{1,5}$', cand):
                return True
            continue
        if _safe_rel(cand) and _inside_exists(root, cand, want_file=True):
            return True
    return False


def verification_command_problem(cmd, expected='exit 0', root=None):
    """aidd:FR-205 aidd:AC-218 Lint of ONE Verification row: the reason it is rejected, or None.
    Rejects trivial commands, protected AIDD state / evidence tooling, interpreter inline code, an
    Expected `contains:` text found in the command itself, and a command that is neither a known test
    runner whose manifest exists nor an invocation of an existing project file. `root=None` skips only
    the existence checks. Never raises (a reason on internal error: fail closed)."""
    try:
        c = _norm_nl(cmd).strip() if isinstance(cmd, str) else ''
        if not c:
            return 'empty command'
        if len(c) > _MAX_CMD_CHARS:
            return f'command longer than {_MAX_CMD_CHARS} characters'
        for line in c.split('\n'):
            if _TRIVIAL_RE.match(line):
                return f'trivial command ("{line.strip()[:30]}") proves nothing'
        low = c.lower()
        hit = next((s for s in _FORBIDDEN_SUBSTR if s in low), None)
        if hit is None:
            m = _FORBIDDEN_RE.search(c) or _AIDD_VERIFY_RE.search(c)
            hit = m.group(0).strip() if m else None
        if hit is None and 'tasks.md' in low and 'approved' in low:
            hit = 'tasks.md + Approved'
        if hit is not None:
            return f'touches protected AIDD state or evidence tooling ({hit[:40]})'
        rootp = Path(root) if root is not None else None
        runner_ok, runner_reason, all_toks = False, None, []
        for seg in _SEG_SPLIT_RE.split(c):
            toks = _tokens(seg)
            toks = toks[_cmd_start(toks):]
            if not toks:
                continue
            all_toks += toks
            exe = _exe(toks[0])
            if _INTERP_RE.match(exe):
                flag = _inline_flag(_interp_kind(exe), toks[1:])
                if flag is not None:
                    return (f'inline code ({exe} {flag[:20]}) is not a test: run a test runner, a test file '
                            'or a script of the project')
            r = _runner(toks, rootp)
            if r is True:
                runner_ok = True
            elif isinstance(r, str):
                runner_reason = r
        x = _expected_contains(expected)
        if x is not None and x.lower() in low:
            return f'Expected "contains: {x[:40]}" is satisfied by the command text itself'
        if runner_ok or _names_existing_file(all_toks, rootp):
            return None
        return runner_reason or ('neither a known test runner with its manifest (dotnet test, npm test, pytest, '
                                 'python -m unittest, cargo/go/mvn/gradle test, msbuild) nor an invocation of an '
                                 'existing project file')
    except Exception as e:  # pragma: no cover - defensive
        return f'command could not be checked ({e})'


def check_verification(spec_text, root=None):
    """aidd:FR-205 aidd:FR-207 R10 violations of the `## Verification` table: missing section, no row,
    empty/unsupported Expected, and verification_command_problem per row. Used at approval (new
    routes) and at close for `gate: 2` specs; NOT part of check_content('spec') (legacy specs pass).
    Never raises."""
    fix_add = ('Add "## Verification" to spec.md as | # | Command | Expected | Covers | with at least one row '
               "that runs the project's own tests (e.g. `python -m unittest discover -s tests`, `dotnet test`, "
               '`npm test`) and Expected `exit 0` or `contains: <text>`.')
    try:
        if _too_large(spec_text):
            return [_v('R10', 'spec.md file too large (> 2 MB): its "## Verification" is not scanned.',
                       'Shrink spec.md below 2 MB.')]
        t = _clean(spec_text)
        if not _has_heading(t, _VERIF_HEADING):
            return [_v('R10', 'spec.md has no "## Verification" section.', fix_add)]
        rows = parse_verification(spec_text)
        if not rows:
            return [_v('R10', '"## Verification" has no row with a command.', fix_add)]
        out = []
        for r in rows:
            n = r['n'] or '?'
            exp = r['expected']
            if not exp:
                out.append(_v('R10', f'Verification row {n}: Expected is empty.',
                              f'Write `exit 0` or `contains: <text>` in the Expected cell of row {n}.'))
            elif not (_EXPECT_EXIT0_RE.match(exp) or _EXPECT_CONTAINS_RE.match(exp)):
                out.append(_v('R10', f'Verification row {n}: Expected "{exp[:40]}" is not `exit 0` or `contains: <text>`.',
                              f'Write `exit 0` or `contains: <text>` in the Expected cell of row {n}.'))
            p = verification_command_problem(r['cmd'], exp or 'exit 0', root)
            if p:
                out.append(_v('R10', f'Verification row {n}: {p}: `{r["cmd"][:80]}`.',
                              f'Replace the command of row {n} with one that runs real tests of this change '
                              '(a test runner of the project or an existing test file/script).'))
        return out
    except Exception as e:  # pragma: no cover - defensive
        return [_v('R10', f'Could not parse "## Verification" ({e}).', fix_add)]


def approval_evidence(spec_text, source, review_sha1=None, consent_ts=None):
    """aidd:FR-204 The extras of a new `approved` event, built in ONE place for every approval route:
    {gate, source, verify_hash, [consent_ts], [review_sha1]}."""
    out = {'gate': GATE_VERSION, 'source': str(source or ''), 'verify_hash': verification_hash(spec_text)}
    if consent_ts is not None:
        try:
            out['consent_ts'] = float(consent_ts)
        except (TypeError, ValueError):
            pass
    if review_sha1:
        out['review_sha1'] = str(review_sha1)
    return out


VERIFY_BAD_OUTPUT_RE = re.compile(
    r'\bRan 0 tests?\b|\bNO TESTS RAN\b|\bNo test is available\b|\bcollected 0 items\b|\bTotal tests:\s*0\b', re.I)
VERIFY_MIN_OUTPUT = 20
_VERIFY_HEADER_RE = re.compile(r'^#\s.*\|\s*exit\s+-?\d+\s*\|')


def verify_output_problem(output, expected):
    """aidd:FR-205 aidd:AC-218 'zero tests ran' | 'output too short' | None for the saved output of one
    row (with or without the `# <cmd> | exit <code> | <ts>` evidence header). A matched `contains:`
    Expected excuses a short output, never a zero-test run. Fail closed on unreadable output."""
    try:
        text = output.decode('utf-8', 'replace') if isinstance(output, (bytes, bytearray)) else str(output or '')
        lines = _norm_nl(text).split('\n')
        body = '\n'.join(lines[1:]) if lines and _VERIFY_HEADER_RE.match(lines[0]) else '\n'.join(lines)
        if VERIFY_BAD_OUTPUT_RE.search(body):
            return 'zero tests ran'
        if len(body.strip().encode('utf-8')) < VERIFY_MIN_OUTPUT:
            x = _expected_contains(expected)
            if x is None or x not in body:
                return 'output too short'
        return None
    except Exception:  # pragma: no cover - defensive
        return 'output could not be read'


def _sha1_file(p):
    h = hashlib.sha1()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _current_approved(ev, root, spec_dir):
    """The `approved` event detail of the CURRENT tasks.md (fallback: the newest one), else None."""
    d = Path(spec_dir)
    f = getattr(ev, 'latest_approved', None)
    if not callable(f):
        return None
    try:
        tasks = _read(d / 'tasks.md')
        a = f(root, d.name, approval_hash(tasks)) if tasks.strip() else None
        return a if a is not None else f(root, d.name)
    except Exception:
        return None


def _is_gate2(ev, root, spec_dir):
    """aidd:FR-205 New-style spec = its current `approved` event carries gate >= 2 (legacy otherwise)."""
    a = _current_approved(ev, root, spec_dir)
    try:
        return isinstance(a, dict) and int(a.get('gate') or 0) >= GATE_VERSION
    except (TypeError, ValueError):
        return False


class FingerprintOnce:
    """aidd:FR-208 Memo of `ev.worktree_fingerprint(root)` for ONE `aidd status` run (closing-audit F-2):
    the fingerprint (up to ~1 s in git, 8 s outside git) is computed lazily, at most once per root, instead
    of once per spec. Freshness: a cached value is served only when it was taken at or after `not_before`
    (the newest of the verify_run's `ts`/`started` and the last code edit being compared) and is younger
    than `ttl` seconds; otherwise it is recomputed. So it never serves a fingerprint older than what it is
    compared against. Never raises (None on any failure, like worktree_fingerprint)."""

    def __init__(self, ev, ttl=30.0, clock=None):
        self.ev = ev
        self.ttl = float(ttl)
        self.clock = clock or time.time
        self.calls = 0
        self._cache = {}                     # str(root) -> (taken_at, fingerprint)

    def __call__(self, root, not_before=0.0):
        try:
            key = str(Path(root).resolve()) if root is not None else ''
        except Exception:
            key = str(root)
        try:
            nb = float(not_before or 0.0)
        except (TypeError, ValueError):
            nb = float('inf')                # unreadable bound: never trust the cache
        now = self.clock()
        hit = self._cache.get(key)
        if hit is not None and hit[0] >= nb and (now - hit[0]) <= self.ttl:
            return hit[1]
        g = getattr(self.ev, 'worktree_fingerprint', None)
        try:
            self.calls += 1
            fp = g(root) if callable(g) else None
        except Exception:
            fp = None
        self._cache[key] = (now, fp)
        return fp


def _glob_hit(rel, globs):
    """True when the root-relative `rel` matches any glob (`**` any depth, `*` inside one segment)."""
    try:
        for g in globs or []:
            g = str(g).strip().strip('`').replace('\\', '/').lstrip('./')
            if not g:
                continue
            rx = re.escape(g).replace(r'\*\*/', '(?:.*/)?').replace(r'\*\*', '.*').replace(r'\*', '[^/]*')
            if re.match('^(?:' + rx + ('.*' if g.endswith('/') else '') + ')$', str(rel).replace('\\', '/')):
                return True
    except Exception:
        pass
    return False


def _rows_already_executed(spec_text, run):
    """Amendment to spec 007: True when the run recorded the code fingerprint and EVERY current table row
    (same command and Expected) already has a passing result in it. A text-only table edit (wording, Covers,
    a corrected note) or a dropped row then keeps the verification valid; no re-execution is demanded."""
    try:
        if run.get('code_fp_end') is None:
            return False
        rows = parse_verification(spec_text)
        if not rows:
            return False
        done = {(_norm_cell(r.get('cmd')), _norm_cell(r.get('expected'))) for r in (run.get('results') or [])
                if isinstance(r, dict) and r.get('ok') is True and 'expected' in r}
        return all((_norm_cell(r['cmd']), _norm_cell(r['expected'])) in done for r in rows)
    except Exception:
        return False


def _run_problems(ev, root, spec_dir, spec_text, run, fingerprint=None):
    """[(state, violation)] for an existing verify_run; state 'failed' | 'stale'. Fail closed.
    `fingerprint`: an optional FingerprintOnce (shared across the specs of one status run); without it the
    fingerprint is computed fresh, as before."""
    d = Path(spec_dir)
    spec = d.name
    rerun = f'Run `aidd verify {spec}` again after the last code change, then close.'
    out = []
    changed = [str(x) for x in (run.get('code_changed') or [])]
    res0 = run.get('results') or []
    rows_ok = bool(res0) and all(isinstance(r, dict) and r.get('ok') is True for r in res0)
    # files the run rewrote are outputs when the spec now declares them `Generated:`: THIS run is accepted
    # as it is (no re-execution, no code edit); the only fix for the old "tree changed" failure is that line.
    gen_now = verification_generated(spec_text)
    explained = bool(changed) and rows_ok and all(_glob_hit(c, gen_now) for c in changed)
    if run.get('ok') is not True and not explained:
        out.append(('failed', _v('R10', f'The last verify_run of {spec} failed.',
                                 f'Fix the failing rows (see specs/{spec}/evidence/verify-<n>.txt), then run '
                                 f'`aidd verify {spec}` again.')))
    if run.get('stable') is not True and not explained:
        if changed and rows_ok:
            shown = ', '.join(changed[:6]) + (f' (+{len(changed) - 6} more)' if len(changed) > 6 else '')
            out.append(('stale', _v('R10', f'The verification itself rewrote files: {shown}.',
                                    f'They are outputs, not code: add `Generated: {", ".join(changed[:6])}` (globs allowed) under '
                                    f'`## Verification` in specs/{spec}/spec.md. AIDD then accepts this same run: do NOT re-run it '
                                    'and do NOT edit the generator.')))
        else:
            out.append(('stale', _v('R10', 'tree changed while verification ran; re-run.', rerun)))
    if str(run.get('verify_hash') or '') != verification_hash(spec_text) and not _rows_already_executed(spec_text, run):
        out.append(('stale', _v('R10', 'The Verification table changed after the last verify_run (a row was added or its command/expected changed).',
                                f'Run `aidd verify {spec}`: it re-runs ONLY the changed rows and reuses the rest while the code is unchanged.')))
    f = getattr(ev, 'last_code_edit_ts', None)
    scope = [str(x) for x in (run.get('code_scope') or [])]
    excl = [str(x) for x in (run.get('code_generated') or [])] + changed      # outputs the run itself rewrote
    try:
        last = ((float(f(root, scope, excl) if (scope or excl) else f(root))) if callable(f) else None)
        started = float(run.get('started') or 0.0)
    except Exception:
        last, started = None, 0.0
    if last is None:
        out.append(('stale', _v('R10', 'Cannot read the code edits of the evidence log (old install).',
                                f'Reinstall AIDD (spec 007 aidd_evidence.py), then run `aidd verify {spec}` again.')))
    elif last > started:
        out.append(('stale', _v('R10', 'A code edit happened after the last verify_run started (verification is stale).', rerun)))
    fp_end = run.get('fingerprint_end')
    cfp_end = run.get('code_fp_end')
    if cfp_end is not None:
        # amendment to spec 007: a run that recorded the code fingerprint is judged ONLY by code changes.
        # Documentation edits, commits, amends and pushes leave it equal, so they never force a re-run.
        g = getattr(ev, 'code_fingerprint', None)
        try:
            cnow = (g(root, scope=scope, exclude=excl) if (scope or excl) else g(root)) if callable(g) else None
        except Exception:
            cnow = None
        if verification_scope(spec_text) != sorted(scope):
            out.append(('stale', _v('R10', 'The Verification `Scope:` line changed after the last verify_run.', rerun)))
        if cnow != cfp_end:
            out.append(('stale', _v('R10', 'A code or data file changed since the last verify_run (documentation edits and commits do not count).',
                                    f'Run `aidd verify {spec}`: unchanged rows are reused only if the code is unchanged, so after a code change it re-runs them all.')))
    elif fp_end is not None:
        now = None
        if callable(fingerprint):
            try:
                nb = max(float(run.get('ts') or 0.0), started, last or 0.0)
            except Exception:
                nb = float('inf')
            try:
                now = fingerprint(root, nb)
            except Exception:
                now = None
        else:
            g = getattr(ev, 'worktree_fingerprint', None)
            try:
                now = g(root) if callable(g) else None
            except Exception:
                now = None
        if now != fp_end:
            out.append(('stale', _v('R10', 'The working tree changed since the last verify_run (fingerprint differs).', rerun)))
    results = run.get('results') or []
    if not isinstance(results, list) or not results:
        out.append(('failed', _v('R10', 'The last verify_run recorded no results.', rerun)))
        return out
    try:
        base = d.resolve()
    except Exception:
        base = d
    for r in results:
        if not isinstance(r, dict):
            out.append(('failed', _v('R10', 'The last verify_run has a malformed result row.', rerun)))
            continue
        n = str(r.get('n', '?'))[:20]
        rel = str(r.get('evidence') or '')
        want = str(r.get('sha1') or '').strip().lower()
        if r.get('ok') is False:
            out.append(('failed', _v('R10', f'Verification row {n} failed in the last verify_run.', rerun)))
        st, p = _evidence_path(base, root, rel)
        inside = False
        if st == 'ok' and p is not None:
            try:
                Path(p).relative_to(base)
                inside = True
            except Exception:
                inside = False
        if not inside:
            out.append(('stale', _v('R10', f'Evidence file of Verification row {n} ("{rel[:60]}") is missing or outside the spec dir.', rerun)))
            continue
        if len(want) < 12 or not re.match(r'^[0-9a-f]+$', want):
            out.append(('stale', _v('R10', f'Verification row {n} has no recorded sha1 for its evidence.', rerun)))
            continue
        try:
            actual = _sha1_file(p)
        except Exception:
            actual = ''
        if not actual.startswith(want):
            out.append(('stale', _v('R10', f'Evidence file of Verification row {n} changed after the run (sha1 differs).', rerun)))
    return out


def verification_gaps(ev, root, spec_dir):
    """aidd:FR-205 aidd:AC-209 aidd:AC-216 Close-time R10 check for a `gate: 2` spec: a valid table; the
    newest verify_run exists, ok and stable; its verify_hash == the table's == the approved event's;
    no code edit after `started`; the fingerprint still equals `fingerprint_end` (when recorded);
    every evidence file exists under the spec dir with its recorded sha1. `ev` is duck-typed. Never
    raises (a violation on internal error: fail closed)."""
    try:
        d = Path(spec_dir)
        spec = d.name
        if _big(d / 'spec.md'):
            return [_v('R10', 'spec.md file too large (> 2 MB): it is not scanned.', 'Shrink spec.md below 2 MB.')]
        spec_text = _read(d / 'spec.md')
        out = list(check_verification(spec_text, root))
        f = getattr(ev, 'latest_verify_run', None)
        if not callable(f):
            return out + [_v('R10', 'The evidence library cannot read verify_run events (old install).',
                             f'Reinstall AIDD (spec 007 aidd_evidence.py), then run `aidd verify {spec}`.')]
        try:
            run = f(root, spec)
        except Exception:
            run = None
        if not run:
            return out + [_v('R10', f'No verify_run recorded for {spec}: the Verification table was never executed.',
                             f'Run `aidd verify {spec}` (it runs every row and saves evidence/verify-<n>.txt), then close.')]
        out += [v for _s, v in _run_problems(ev, root, d, spec_text, run)]
        appr = _current_approved(ev, root, d)
        if appr is None:
            out.append(_v('R10', f'No approved event found for {spec}.', f'Approve the tasks (`aidd rules approve {spec}`) first.'))
        elif str(appr.get('verify_hash') or '') != verification_hash(spec_text):
            out.append(_v('R10', 'The Verification table changed after approval (verify_hash differs from the approved one).',
                          f'Regenerate the review (`aidd review specs/{spec}`), run `aidd review specs/{spec} --wait` in '
                          'the background (the owner presses `Aprobar y guardar` on the page, which saves review.md), '
                          f'ask ONE tagged question and approve again, then run `aidd verify {spec}`.'))
        return _dedup(out)
    except Exception as e:  # pragma: no cover - defensive
        return [_v('R10', f'Verification check failed internally ({e}).', 'Report this to the AIDD maintainers.')]


def verification_state(spec_dir, root=None, fingerprint=None):
    """aidd:FR-208 {declared, commands, status: none|never-run|stale|failed|passed, ts} of a spec's
    Verification (the newest verify_run vs the current table, code edits, fingerprint, evidence).
    `fingerprint`: optional FingerprintOnce shared by the caller across specs (F-2). Never raises."""
    st = {'declared': False, 'commands': 0, 'status': 'none', 'ts': None}
    try:
        d = Path(spec_dir)
        text = '' if _big(d / 'spec.md') else _read(d / 'spec.md')
        st['declared'] = _has_heading(_clean(text), _VERIF_HEADING)
        rows = parse_verification(text)
        st['commands'] = len(rows)
        if not st['declared'] or not rows:
            return st
        st['status'] = 'never-run'
        ev = _evidence()
        if ev is None:
            return st
        if root:
            root = Path(root)
        elif d.parent.name == 'specs':
            root = d.parent.parent
        else:
            root = ev.find_root(d)
        f = getattr(ev, 'latest_verify_run', None)
        run = f(root, d.name) if callable(f) else None
        if not run:
            return st
        st['ts'] = run.get('ts')
        probs = _run_problems(ev, root, d, text, run, fingerprint)
        st['status'] = 'failed' if any(s == 'failed' for s, _v2 in probs) else ('stale' if probs else 'passed')
    except Exception:
        pass
    return st


# ===================================================== spec 007: the ONE closing auditor (R7)

CLOSING_AUDIT_MIN_RESULT = 1500
CLOSING_AUDIT_RE = re.compile(
    r'^\s*CLOSING AUDIT\s*\[\s*domains\s*:\s*([^\]\n]*)\]\s*\[\s*tasks\s*:\s*([0-9a-f]{8})\s*\]'
    r'(?:\s*\[\s*verify\s*:\s*([0-9a-f]{8})\s*\])?', re.I)


def closing_audit_header(event):
    """aidd:FR-206 {domains:set, tasks:str, verify:str} parsed from the FIRST line of the subagent's
    `head` (its prompt; `desc` only when there is no head), else None. Never raises."""
    try:
        det = (event or {}).get('detail') or {}
        src = str(det.get('head') or '').lstrip() or str(det.get('desc') or '').lstrip()
        if not src:
            return None
        m = CLOSING_AUDIT_RE.match(src.split('\n', 1)[0][:1000])
        if not m:
            return None
        doms = {x for x in re.split(r'[\s,;]+', m.group(1).strip().lower()) if x}
        return {'domains': doms, 'tasks': m.group(2).lower(), 'verify': (m.group(3) or '').lower()}
    except Exception:
        return None


def _result_chars(event):
    try:
        rc = (event.get('detail') or {}).get('result_chars')
        if rc is None or isinstance(rc, bool):
            return None
        return int(float(rc))
    except Exception:
        return None


def closing_audit_covers(event, spec_dir, domains, gate2, ev, root):
    """aidd:FR-206 aidd:AC-210 True only for a COUNTING subagent (R14) whose header names every domain
    of `domains`, whose `tasks` tag is approval_hash(tasks.md)[:8], whose recorded final report is at
    least CLOSING_AUDIT_MIN_RESULT chars (absent = does not count) and, for a `gate: 2` spec, whose
    `verify` tag is the newest verify_run's verify_hash[:8] and which postdates that run."""
    try:
        if not _subagent_counts(event):
            return False
        h = closing_audit_header(event)
        if h is None:
            return False
        if not {str(x).lower() for x in domains} <= h['domains']:
            return False
        d = Path(spec_dir)
        tasks = _read(d / 'tasks.md')
        if not tasks.strip() or h['tasks'] != approval_hash(tasks)[:8]:
            return False
        if gate2:
            f = getattr(ev, 'latest_verify_run', None)
            run = f(root, d.name) if callable(f) else None
            if not run:
                return False
            vh = str(run.get('verify_hash') or '').lower()
            # amendment to spec 007: a re-verify of the SAME code (docs/commit/table-wording only) keeps the
            # auditors valid: the tag may name any hash of the run's lineage and the auditor only has to
            # postdate the first verification of this code state (`code_since`), not the latest re-run.
            tags = {vh[:8]} | {str(x).lower()[:8] for x in (run.get('verify_lineage') or []) if x}
            if not vh or h['verify'] not in tags:
                return False
            since = run.get('code_since')
            if since is None:
                since = run.get('ts')
            if float(event.get('ts', 0) or 0) <= float(since or 0):
                return False
        rc = _result_chars(event)
        return rc is not None and rc >= CLOSING_AUDIT_MIN_RESULT
    except Exception:
        return False


def closing_audit_gaps(ev, root, spec_dir):
    """aidd:FR-206 aidd:AC-210 For a `gate: 2` spec covered by a closing auditor: qa-audit.md must hold
    a table row naming each required domain and the auditor's tool_use_id. [] for legacy specs and
    when no closing auditor covers (per-domain auditors: R7 decides). Never raises (fail closed)."""
    try:
        d = Path(spec_dir)
        if not _is_gate2(ev, root, d):
            return []
        doms = required_domains(d)
        try:
            subs = ev.events(root, None, 'subagent')
        except Exception:
            subs = []
        aud = [e for e in subs if closing_audit_covers(e, d, doms, True, ev, root)]
        if not aud:
            return []
        e = max(aud, key=lambda x: x.get('ts', 0) or 0)
        tid = str((e.get('detail') or {}).get('tool_use_id') or '').strip()
        qa_p = d / 'qa-audit.md'
        fix = ('Rewrite qa-audit.md with one checklist row per required domain (' + ', '.join(sorted(doms))
               + ') and the closing auditor\'s tool_use_id' + (f' ({tid})' if tid else '') + '.')
        if not qa_p.exists():
            return [_v('R10', 'qa-audit.md does not exist (closing audit not written down).', fix)]
        if _big(qa_p):
            return [_v('R10', 'qa-audit.md file too large (> 2 MB): it is not scanned.', 'Shrink qa-audit.md below 2 MB.')]
        qa = _clean(_read(qa_p))
        rows = [ln for ln in qa.split('\n') if ln.strip().startswith('|') and not _is_sep(_split_row(ln))]
        out = []
        for dom in sorted(doms):
            rx = re.compile(r'\b' + re.escape(dom) + r'\b', re.I)
            if not any(rx.search(r) for r in rows):
                out.append(_v('R10', f'qa-audit.md has no checklist row for the {dom} domain of the closing audit.', fix))
        if not tid:
            out.append(_v('R10', 'The closing auditor has no recorded tool_use_id.',
                          'Re-dispatch the closing auditor through the Agent tool (the hook records its tool_use_id).'))
        elif tid not in qa:
            out.append(_v('R10', f'qa-audit.md does not cite the closing auditor\'s tool_use_id ({tid[:60]}).', fix))
        return out
    except Exception as e:  # pragma: no cover - defensive
        return [_v('R10', f'Closing-audit check failed internally ({e}).', 'Report this to the AIDD maintainers.')]


if __name__ == '__main__':  # tiny CLI: python aidd_rules.py <spec_dir>
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    vs = check_spec_dir(sys.argv[1])
    for v in vs:
        print(f"FAIL {v['rule']} {v['message']} -> {v['fix']}")
    print('PASS' if not vs else f'{len(vs)} violation(s)')
    sys.exit(1 if vs else 0)
