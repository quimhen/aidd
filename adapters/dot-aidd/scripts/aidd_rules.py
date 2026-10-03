#!/usr/bin/env python3
"""
aidd hard-rules library — pure, stdlib-only checks used by hooks, `aidd rules ...`
and check_spec.py. Contract: specs/002-aidd-hard-rules/spec.md (incl. the Rev 1 amendments).

Rules: R1 estimates (agent time) · R2 pipeline route · R3 alignment provenance ·
R4 visual debt · R5 chain order · R6 tasks approval · R7 closing-audit domains ·
R9 protected paths. (R8 is the Stop hook, not a library concern.)
Spec 003 adds R10 execution evidence at close · R11 root cause on repeat · R12 view-vs-logic tag.

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
import sys
import unicodedata
from pathlib import Path

RULE_IDS = ('R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'R9', 'R10', 'R11', 'R12')

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
}

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


def _check_tasks(text):
    out = []
    t = _clean(text)
    fix_w = ('Add a "## Waves" section with the table | Wave | Tasks | Agent time (min) | Human ref (h) | '
             'and one row per wave (waves run sequentially, tasks inside a wave in parallel).')
    tbl = _table(t, r'waves\b')
    waves = []
    if tbl is None:
        out.append(_v('R1', 'tasks.md has no "## Waves" table.', fix_w))
    else:
        header, rows = tbl
        ok = (_hdr(header, 0) == 'wave' and _hdr(header, 1) == 'tasks'
              and _hdr(header, 2).startswith('agent time') and _hdr(header, 3).startswith('human ref'))
        if not ok:
            out.append(_v('R1', 'Waves table header must be exactly | Wave | Tasks | Agent time (min) | '
                                'Human ref (h) | in that column order.',
                          'Rewrite the Waves table header as | Wave | Tasks | Agent time (min) | Human ref (h) |.'))
        elif not rows:
            out.append(_v('R1', 'Waves table has no rows.', fix_w))
        else:
            for r in rows:
                waves.append(r + [''] * (4 - len(r)))

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
        if not re.fullmatch(r'\d{1,9}(\.\d{1,9})?', r[3]):
            out.append(_v('R1', f'Wave {wid}: "Human ref (h)" must be a number, got "{r[3]}".',
                          f'Fill wave {wid} Human ref (h) with a number.'))
        if not re.fullmatch(r'\d{1,9}', r[2]):
            out.append(_v('R1', f'Wave {wid}: "Agent time (min)" must be a whole number, got "{r[2]}".',
                          f'Set wave {wid} Agent time (min) to the max "Agent min" of its tasks.'))
            continue
        wave_times.append(int(r[2]))
        unknown = [i for i in ids if i not in agent]
        if unknown:
            out.append(_v('R1', f'Wave {wid} cites {", ".join(unknown)} with no valid "Agent min:" block.',
                          f'Add/fix the "### {unknown[0]}" block with "Agent min:" so wave {wid} can be verified.'))
        elif ids and max(agent[i] for i in ids) != int(r[2]):
            out.append(_v('R1', f'Wave {wid}: Agent time {r[2]} min != max of its tasks ({max(agent[i] for i in ids)} min). '
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
            universe |= _codes(_norm_nl(_read(f)))
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
    doms = {'performance'}
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
    except Exception:
        pass
    return doms


def _uncovered(ev, root, session, domains, since_ts):
    """Domains (subset of `domains`) left without a DISTINCT matching subagent (M9): maximum
    bipartite matching domains -> subagent events; one subagent covers one domain only."""
    doms = sorted(d for d in domains if d in DOMAIN_RE)
    unknown = {d for d in domains if d not in DOMAIN_RE}
    try:
        events = [e for e in ev.events(root, session, 'subagent') if e.get('ts', 0) > since_ts]
    except Exception:
        events = []
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
        return _uncovered(ev, root, session, doms, since_ts)
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
    return bool(re.search(r'(^|/)\.aidd/evidence(/|$)', p) or re.search(r'(^|/)\.aidd/active_spec$', p))


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

    # R5: find_spec + independent Mapper after spec.md
    try:
        if not ev.last_event(root, 'find_spec', session):
            out.append(_v('R5', 'No find_spec run recorded in this session.',
                          'Run `python skill/scripts/find_spec.py` (Step -1) before planning.'))
        sm = _mtime(d / 'spec.md')
        if sm is not None and not [e for e in ev.events(root, session, 'subagent') if e['ts'] > sm]:
            out.append(_v('R5', 'No independent subagent (Mapper/Alignment) ran after the last edit of spec.md.',
                          'Dispatch a Mapper/Alignment subagent (Agent tool) over spec.md before writing plan.md.'))
        if has_tasks:
            if not plan_p.exists():
                out.append(_v('R5', 'tasks.md exists but plan.md does not.', 'Write plan.md (Step 3) before tasks.md.'))
            else:
                pm = _mtime(plan_p)
                if not [e for e in ev.events(root, session, 'subagent') if e['ts'] > pm]:
                    out.append(_v('R5', 'No independent subagent ran after the last edit of plan.md.',
                                  'Dispatch an independent auditor subagent over plan.md before writing tasks.md.'))
            lf = ev.last_event(root, 'find_spec', session)
            if lf and (lf.get('detail') or {}).get('rebuilt') and not [
                    e for e in ev.events(root, session, 'subagent') if e['ts'] > lf['ts']]:
                out.append(_v('R5', 'The graph index was rebuilt but no subagent audited it afterwards.',
                              'Dispatch a graph-coherence auditor subagent, then retry.'))
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
            missing = _uncovered(ev, root, session, required_domains(d), since)
        except Exception:
            missing = set(required_domains(d))
        for dom in sorted(missing):
            out.append(_v('R7', f'No {dom} auditor subagent ran after the last code edit.',
                          f'Dispatch a dedicated {dom} auditor subagent (one subagent per domain) whose '
                          f'prompt/description names "{dom}", then rewrite qa-audit.md.'))
    return out


if __name__ == '__main__':  # tiny CLI: python aidd_rules.py <spec_dir>
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    vs = check_spec_dir(sys.argv[1])
    for v in vs:
        print(f"FAIL {v['rule']} {v['message']} -> {v['fix']}")
    print('PASS' if not vs else f'{len(vs)} violation(s)')
    sys.exit(1 if vs else 0)
