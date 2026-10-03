#!/usr/bin/env python3
"""
aidd status / aidd rules — the mechanical ledger and the rule commands for the AIDD
hard rules (contract: specs/002-aidd-hard-rules/spec.md, incl. the Rev 1 amendments). Stdlib only.

Usage:
    aidd_status.py status [spec_dir] [--json]   ledger from the evidence log + spec files (exit 0 always)
    aidd_status.py rules check <spec_dir>       PASS|FAIL Rn message -> fix  (exit 1 on any violation)
    aidd_status.py rules approve <spec_dir>     write `Approved: <date> hash:<hash>` in tasks.md + record the
                                                `approved` event; needs the user's recorded answer "Approve" to
                                                an AskUserQuestion about the tasks (newer than tasks.md) and an
                                                R1-valid tasks.md
    aidd_status.py rules close <spec_id>        record spec_closed(completed): needs a valid approval,
                                                qa-audit.md, every required domain audited and the user's
                                                affirmative answer to a "close/finish" question
    aidd_status.py rules abandon <spec_id> [--reason TEXT]
                                                record spec_closed(abandoned): needs the user's affirmative
                                                answer to an "abandon/discard" question (no qa-audit needed)

Exit codes: 0 ok · 1 refused/violations/error · 2 usage. Never prints a traceback.

The CLI cannot see its own session id. The "current session" is the session in the caller marker that
rule_gate writes just before an `aidd` shell command (if under 120 s old, same root), else the session of
the newest recorded user `prompt` event that is not synthetic (text not starting with `<` or `[`) (env AIDD_SESSION_ID / CLAUDE_SESSION_ID / AIDD_EVIDENCE_DIR are ignored unless
AIDD_TESTING=1). Answers recorded under 'unknown-session' are accepted. An answer from another session
is refused. An answer only counts if the user picked the REQUIRED option label of a question that
offered it: "Approve" (tasks), "Yes, close" (close), "Abandon" (abandon).
"""
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aidd_evidence as ev  # noqa: E402
import aidd_rules as rules  # noqa: E402

# Rev 2: topic (on the question text) AND the exact option label the user must have chosen.
APPROVE_TOPIC = re.compile(r'approv|aprob', re.I)
APPROVE_LABEL = re.compile(r'^(approve|aprobar|aprobado)\b', re.I)
CLOSE_TOPIC = re.compile(r'close|cierr|finaliz', re.I)
CLOSE_LABEL = re.compile(r'^(yes,? close|cerrar|si,? cerrar|sí,? cerrar)', re.I)
ABANDON_TOPIC = re.compile(r'abandon|descart', re.I)
ABANDON_LABEL = re.compile(r'^(abandon|abandonar|descartar)', re.I)
CHECK_MARK, CROSS_MARK = '✔', '✘'


MAX_READ = 4 * 1024 * 1024


def _read(p):
    try:
        if Path(p).stat().st_size > MAX_READ:     # pathological/huge file: never loaded (D14)
            return ''
        return Path(p).read_text(encoding='utf-8', errors='replace')
    except Exception:
        return ''


def _mtime(p):
    try:
        return Path(p).stat().st_mtime
    except Exception:
        return None


def _mark(b):
    return CHECK_MARK if b else CROSS_MARK


_TEST_ONLY_ENV = ('AIDD_SESSION_ID', 'CLAUDE_SESSION_ID', 'AIDD_EVIDENCE_DIR')


def _sanitize_env():
    """The CLI ignores the session/evidence overrides unless AIDD_TESTING=1 (an agent must not be able
    to point the CLI at a forged log or impersonate a session by prefixing a command)."""
    if os.environ.get('AIDD_TESTING') != '1':
        for k in _TEST_ONLY_ENV:
            os.environ.pop(k, None)


CALLER_TTL_DEFAULT = 120.0
CALLER_CLOCK_SKEW = 5.0


def _caller_ttl():
    """aidd:FR-001 Marker freshness window in seconds: env AIDD_CALLER_TTL may only SHORTEN the default."""
    try:
        v = float(os.environ.get('AIDD_CALLER_TTL', '') or CALLER_TTL_DEFAULT)
        return v if 0 < v <= CALLER_TTL_DEFAULT else CALLER_TTL_DEFAULT
    except Exception:
        return CALLER_TTL_DEFAULT


def _read_caller_marker(root):
    """aidd:FR-001 Session written by rule_gate in `caller-<sha1(root)>.json` just before this `aidd`
    command, if the marker is fresh (ts within the TTL of now). Missing/corrupt/stale marker -> None."""
    try:
        p = ev.caller_marker_path(root)
        if p.stat().st_size > 4096:
            return None
        m = json.loads(p.read_text(encoding='utf-8', errors='replace'))
        if not isinstance(m, dict):
            return None
        sess, ts = m.get('session'), m.get('ts')
        if not isinstance(sess, str) or not sess.strip() or sess.strip() == 'unknown-session':
            return None
        if isinstance(ts, bool) or not isinstance(ts, (int, float)):
            return None
        age = time.time() - float(ts)
        if -CALLER_CLOCK_SKEW <= age <= _caller_ttl():
            return sess.strip()
    except Exception:
        pass
    return None


def _is_real_prompt(e):
    """A prompt the user typed: not a synthetic notice / subagent hand-back (text starting `<` or `[`)."""
    try:
        text = str((e['detail'] or {}).get('text', '')).strip()
        return bool(text) and text[0] not in '<['
    except Exception:
        return False


def _current_session(root):
    """Session of the caller: (tests only) env override, else the fresh caller marker rule_gate wrote for
    this root, else the session of the newest recorded NON-synthetic user prompt."""
    if os.environ.get('AIDD_TESTING') == '1':
        for k in ('AIDD_SESSION_ID', 'CLAUDE_SESSION_ID'):
            v = os.environ.get(k, '').strip()
            if v:
                return v
    m = _read_caller_marker(root)
    if m:
        return m
    try:
        ps = [e for e in ev.events(root, kind='prompt')
              if e['session'] != 'unknown-session' and _is_real_prompt(e)]
        if ps:
            return max(ps, key=lambda e: e['ts'])['session']
    except Exception:
        pass
    return None


def _session_note(sess):
    """aidd:FR-001 Names the inferred session in a refusal and says how to correct a wrong inference."""
    return ('\nInferred session: ' + (sess or 'none (no recorded user prompt)')
            + '. If that is not this window\'s session, have the user type a short message in this window, then '
              'run the command again (in the normal case the caller marker written by the hook picks this '
              'window\'s session).')


# ------------------------------------------------------------------ ledger

def _route(spec_text, root, since):
    out = {}
    for step, row in rules.parse_route(spec_text).items():
        q = rules._user_quote(row.get('confirmation', ''))
        confirmed = bool(q) and rules.quote_verified(ev, root, q, since)
        out[step] = {'status': row['status'], 'confirmed': confirmed}
    return out


def _alignment(spec_text, root, since):
    t = rules._clean(spec_text)
    proposed = unanswered = unverified = 0
    quotes = []
    for r in (rules._table(t, r'pipeline route\b') or ([], []))[1]:
        if len(r) > 3 and rules._user_quote(r[3]):
            quotes.append(rules._user_quote(r[3]))
    _h, rows = rules._checklist_rows(t)
    for r in rows:
        if not r[1].strip():
            unanswered += 1
            continue
        if rules._is_proposed(r):
            proposed += 1
        elif rules._user_quote(r[2]):
            quotes.append(rules._user_quote(r[2]))
    for q in quotes:
        if not rules.quote_verified(ev, root, q, since):
            unverified += 1
    return {'proposed': proposed, 'unanswered': unanswered, 'unverified_quotes': unverified}


def _waves(tasks_text):
    """(n_waves, critical_path_min, tokens_k_per_wave) - Waves columns read BY HEADER NAME (both variants)."""
    t = rules._clean(tasks_text)
    tbl = rules._table(t, r'waves\b')
    times, toks = [], []
    n = 0
    if tbl:
        hdr = [re.sub(r'[\s*`_]+', ' ', h).strip().lower() for h in tbl[0]]

        def col(prefix):
            return next((i for i, h in enumerate(hdr) if h.startswith(prefix)), None)
        ti, ki = col('agent time'), col('tokens')
        for r in tbl[1]:
            if ti is not None and len(r) > ti and re.fullmatch(r'\d+', r[ti].strip()):
                times.append(int(r[ti].strip()))
            if ki is not None and len(r) > ki and re.fullmatch(r'\d+', r[ki].strip()):
                toks.append(int(r[ki].strip()))
        n = len(tbl[1])
    m = re.search(r'total agent time \(critical path\)\s*:\s*(\d+)', t.replace('*', ''), re.I)
    return n, (int(m.group(1)) if m else (sum(times) if times else None)), toks


def _plan_segment(t):
    mins = t.get('critical_path_min')
    if mins is None:
        return ''
    tk = t.get('tokens_k')
    return f" · ~{mins} min" + (f", ~{tk}k tokens" if tk is not None else '')


def _approval_recorded(root, spec, tasks_text):
    """True iff a hook/CLI-recorded `approved{spec,hash}` event exists for the CURRENT approval hash."""
    try:
        h = rules.approval_hash(tasks_text)
        return any((e['detail'] or {}).get('spec') == spec and (e['detail'] or {}).get('hash') == h
                   for e in ev.events(root, kind='approved'))
    except Exception:
        return False


def build_status(spec_dir, root=None, named=False):
    """Mechanical ledger of one spec as a plain dict (JSON-serialisable). Never raises: a
    pathological spec/tasks file yields a degraded ledger flagged `unparseable` (D14).
    aidd:FR-009 `named=True` (the user named this spec) also reports an approved-only spec as open."""
    try:
        return _build_status(spec_dir, root, named)
    except Exception as e:
        d = Path(spec_dir)
        return {'spec': d.name, 'root': str(root or ''), 'open': False, 'unparseable': True,
                'route': {}, 'alignment': {'proposed': 0, 'unanswered': 0, 'unverified_quotes': 0},
                'mapper': False, 'graph': False, 'plan_audited': False,
                'tasks': {'approval': 'unparseable', 'waves': 0, 'critical_path_min': None,
                          'approval_recorded': False},
                'code_edits': 0, 'auditors': {}, 'qa_audit': (d / 'qa-audit.md').exists(),
                'qa_evidence': {'checked': False, 'r10': 0, 'r11': 0},
                'visual_debt_open': 0, 'debt_blocking': 0, 'active': False,
                'why_blocked': [f'Could not analyse this spec ({type(e).__name__}); check spec.md/tasks.md '
                                'for pathological content (huge, binary or malformed tables).']}


def _build_status(spec_dir, root=None, named=False):
    d = Path(spec_dir).resolve()
    root = Path(root) if root else ev.find_root(d)
    spec_text, tasks_text = _read(d / 'spec.md'), _read(d / 'tasks.md')
    st = {'spec': d.name, 'root': str(root)}
    since = rules.spec_first_edit_ts(ev, root, d.name)

    st['open'] = d.name in ev.open_specs(root, include_approved=named)
    st['route'] = _route(spec_text, root, since)
    st['alignment'] = _alignment(spec_text, root, since)

    sm, pm = _mtime(d / 'spec.md'), _mtime(d / 'plan.md')
    subs = [e for e in ev.events(root, kind='subagent') if rules._subagent_counts(e)]
    st['mapper'] = bool(sm is not None and any(e['ts'] > sm for e in subs))
    fs = ev.events(root, kind='find_spec')
    last_fs = max(fs, key=lambda e: e['ts']) if fs else None
    st['graph'] = bool(last_fs and (not (last_fs['detail'] or {}).get('rebuilt')
                                    or any(e['ts'] > last_fs['ts'] for e in subs)))
    st['plan_audited'] = bool(pm is not None and any(e['ts'] > pm for e in subs))

    if not (d / 'tasks.md').exists():
        approval = 'no-tasks'
    elif rules.approval_line(tasks_text) is None:
        approval = 'pending'
    else:
        approval = 'valid' if rules.approval_valid(tasks_text) else 'invalid'
    waves, critical, _wt = _waves(tasks_text)
    pt = rules.plan_totals(tasks_text)
    st['tasks'] = {'approval': approval, 'waves': waves, 'critical_path_min': critical,
                   'tokens_k': pt.get('tokens_k')}

    # Rev 2 (D1): a code edit carries no spec attribution - it applies to every open spec.
    edits = ev.events(root, kind='code_edit')
    since_edit = max([e['ts'] for e in edits], default=0.0)
    st['code_edits'] = len(edits)
    st['tasks']['approval_recorded'] = _approval_recorded(root, d.name, tasks_text) if approval == 'valid' else False
    doms = sorted(rules.required_domains(d))
    missing = set(rules.uncovered_domains(root, None, d.name, since_edit, spec_dir=d))
    st['auditors'] = {dom: dom not in missing for dom in doms}
    st['qa_audit'] = (d / 'qa-audit.md').exists()
    st['qa_evidence'] = _qa_evidence(d, root, since_edit if edits else None)
    st['visual_debt_open'] = len(rules.open_visual_debt(spec_text)) if spec_text else 0
    st['debt_blocking'] = len(rules.open_debt_blocking(root).get(d.name, []))
    st['active'] = ev.get_active_spec(root) == d.name
    st['why_blocked'] = _why_blocked(d, root, st)
    return st


def _qa_evidence(d, root, last_edit_ts):
    """R10/R11 state of qa-audit.md: {'checked', 'r10', 'r11'} (violation counts). Never raises."""
    out = {'checked': False, 'r10': 0, 'r11': 0}
    try:
        p = d / 'qa-audit.md'
        if not p.exists():
            return out
        vs = rules.check_qa(_read(p), d, root, last_edit_ts)
        out['checked'] = True
        out['r10'] = sum(1 for v in vs if v['rule'] == 'R10')
        out['r11'] = sum(1 for v in vs if v['rule'] == 'R11')
    except Exception:
        pass
    return out


def _was_closed(root, spec_id):
    """True iff a `spec_closed` event (completed or abandoned) was recorded for `spec_id`."""
    try:
        return any((e['detail'] or {}).get('spec') == spec_id for e in ev.events(root, kind='spec_closed'))
    except Exception:
        return False


def _why_blocked(d, root, st):
    """Human-readable lines: what currently blocks this spec and the exact next action."""
    out = []
    try:
        if not st.get('open') and _was_closed(root, d.name):
            return out      # aidd:FR-005 a closed spec is not blocked: no static-rule WHY as if it were open
        for v in rules.check_spec_dir(d, root):
            if v['rule'] in ('R4', 'R5', 'R6', 'R7', 'R10', 'R11', 'R12'):
                out.append(f"{v['rule']} {v['message']} → {v['fix']}")
        ap = st['tasks']['approval']
        if st['open'] and ap == 'no-tasks':
            out.insert(0, 'Step 4 missing: write tasks.md, then get approval. Code edits are BLOCKED while this '
                          'spec is open without an approved tasks.md.')
        elif st['open'] and ap != 'valid':
            out.insert(0, 'Code edits are BLOCKED while this open spec has no valid tasks approval '
                          '(ask the user with AskUserQuestion offering the option "Approve", then `aidd rules approve`).')
        elif st['open'] and not st['tasks'].get('approval_recorded'):
            out.insert(0, 'Code edits are BLOCKED: the Approved: line has no recorded `approved` event for the '
                          'current hash (it was not written through the gate/`aidd rules approve`). '
                          'Run `aidd rules approve` after the user picks "Approve".')
    except Exception:
        pass
    return out[:8]


def _global(root):
    """Evidence-wide counters (not per spec)."""
    answers = ev.events(root, kind='answer')
    errs = ev.events(root, kind='hook_error')
    blocks = {}
    for e in ev.events(root, kind='stop_block'):
        sp = (e['detail'] or {}).get('spec', '?')
        blocks[sp] = blocks.get(sp, 0) + 1
    return {
        'answers': len(answers),
        'questions': ev.count(root, 'question'),
        'user_answered': bool(answers),
        'stop_blocks': blocks,
        'stop_block_exhausted': ev.count(root, 'stop_block_exhausted'),
        'hook_errors': len(errs),
        'last_hook_error': (errs[-1]['detail'] if errs else None),
        'open_specs': ev.open_specs(root),
    }


def _route_summary(route):
    if not route:
        return 'none declared'
    groups = []
    for step in rules.ROUTE_STEPS:
        r = route.get(step)
        if r is None:
            label = 'MISSING'
        elif r['status'] == 'waived':
            label = 'WAIVED(confirmed)' if r['confirmed'] else 'WAIVED(unconfirmed)'
        else:
            label = r['status'] or '?'
        if groups and groups[-1][1] == label:
            groups[-1][0].append(step)
        else:
            groups.append(([step], label))
    return ' · '.join('/'.join(s) + ' ' + lbl for s, lbl in groups)


def _qa_evidence_segment(st):
    q = st.get('qa_evidence') or {}
    if not q.get('checked'):
        return ''
    n10, n11 = q.get('r10', 0), q.get('r11', 0)
    if not (n10 or n11):
        return ' · evidence ✔'
    return f' · evidence ✘ (R10 {n10}, R11 {n11})'


def format_status(st, glob=None):
    a, t = st['alignment'], st['tasks']
    align = (f"{a['proposed']} proposed"
             + (f" · {a['unanswered']} unanswered" if a.get('unanswered') else '')
             + (f" · {a['unverified_quotes']} unverified quote(s)" if a['unverified_quotes'] else '')
             + f" · Mapper {_mark(st['mapper'])} · Graph {_mark(st['graph'])}")
    if t['approval'] == 'valid':
        tk = ('approved ✔ (hash ok, approval recorded)' if t.get('approval_recorded')
              else 'approval line valid but NOT recorded ✘ (no `approved` event)')
    elif t['approval'] == 'invalid':
        tk = 'approval VOID ✘ (tasks changed after approval)'
    elif t['approval'] == 'pending':
        tk = 'approval pending ✘'
    elif t['approval'] == 'unparseable':
        tk = 'unparseable'
    elif st.get('open'):
        tk = 'Step 4 missing ✘ (open spec without tasks.md)'
    else:
        tk = 'no tasks.md yet'
    cp = f"{t['critical_path_min']} min" if t['critical_path_min'] is not None else 'n/a'
    aud = ' '.join(f'{k} {_mark(v)}' for k, v in st['auditors'].items())
    state = 'OPEN' if st.get('open') else 'not open'
    lines = [
        f"{st['spec']} [{state}]  Route: {_route_summary(st['route'])}   Align: {align}",
        f"Tasks: {tk} · Waves: {t['waves']} · critical path {cp}{_plan_segment(t)}   "
        f"Build: {st['code_edits']} code edits · Auditors: {aud}",
        f"Visual debt open: {st['visual_debt_open']} (blocking this spec: {st.get('debt_blocking', 0)}) · "
        f"qa-audit.md: {'yes' if st['qa_audit'] else 'no'}" + _qa_evidence_segment(st)
        + (' · ACTIVE pointer' if st['active'] else ''),
    ]
    for w in st.get('why_blocked') or []:
        lines.append(f'  WHY blocked: {w}')
    return '\n'.join(lines)


def format_global(g):
    stops = ', '.join(f'{k} x{v}' for k, v in sorted(g['stop_blocks'].items())) or 'none'
    lines = [
        f"User answers recorded (AskUserQuestion answered): {g['answers']}"
        + ('' if g['user_answered'] else ' — no approval/close/abandon is possible until the user answers a question')
        + f" · questions asked: {g['questions']}",
        f"Stop blocks: {stops}" + (f" · exhausted: {g['stop_block_exhausted']}" if g['stop_block_exhausted'] else ''),
        f"Hook errors: {g['hook_errors']}"
        + (f" (last: {g['last_hook_error'].get('hook')}: {g['last_hook_error'].get('error')})"
           if g['last_hook_error'] else ''),
    ]
    return '\n'.join(lines)


def _spec_dirs(root):
    specs = root / 'specs'
    try:
        return sorted(p for p in specs.iterdir() if p.is_dir()) if specs.is_dir() else []
    except Exception:
        return []


def cmd_status(args):
    as_json = '--json' in args
    pos = [a for a in args if not a.startswith('--')]
    root = ev.find_root(Path(pos[0]) if pos else None)
    try:
        g = _global(root)
    except Exception:
        g = {'answers': 0, 'questions': 0, 'user_answered': False, 'stop_blocks': {}, 'stop_block_exhausted': 0,
             'hook_errors': 0, 'last_hook_error': None, 'open_specs': []}
    if pos:
        spec_dir = Path(pos[0])
        if not spec_dir.is_dir():
            print(f'Not a directory: {spec_dir}')
            return 0
        sts = [build_status(spec_dir, root, named=True)]
    else:
        names = {p.name: p for p in _spec_dirs(root)}
        shown = [names[s] for s in g['open_specs'] if s in names]
        active = ev.get_active_spec(root)
        if active in names and names[active] not in shown:
            shown.append(names[active])
        sts = [build_status(p, root) for p in shown]
        if as_json:
            print(json.dumps({'open_specs': g['open_specs'], 'specs': sts,
                              'other_specs': sorted(n for n in names if names[n] not in shown),
                              'evidence': g}, indent=2, ensure_ascii=False))
            return 0
        if not sts:
            if not names:
                print('No specs found (no open spec and no specs/ folder).')
            else:
                print('No open specs. Specs:')
                for p in names.values():
                    s = build_status(p, root)
                    print(f"  {s['spec']}  tasks: {s['tasks']['approval']} · {s['code_edits']} code edits "
                          f"· qa-audit {'yes' if s['qa_audit'] else 'no'}")
            print(format_global(g))
            return 0
    if as_json:
        print(json.dumps({'open_specs': g['open_specs'], 'specs': sts, 'evidence': g}, indent=2, ensure_ascii=False)
              if not pos else json.dumps(dict(sts[0], evidence=g), indent=2, ensure_ascii=False))
        return 0
    if not pos:
        print('Open specs: ' + (', '.join(f"{s['spec']} (approval {s['tasks']['approval']})" for s in sts if s.get('open')) or 'none'))
        ghost = [x for x in g['open_specs'] if x not in {s['spec'] for s in sts}]
        if ghost:
            print('Open specs whose folder is missing: ' + ', '.join(ghost)
                  + ' (code edits stay blocked; run `aidd rules abandon <id>` if the user drops them)')
    for s in sts:
        print(format_status(s))
    print(format_global(g))
    return 0


# ------------------------------------------------------------------- rules

def _resolve_spec(arg, root=None):
    p = Path(arg)
    if p.is_dir():
        return p.resolve()
    root = root or ev.find_root()
    q = root / 'specs' / arg
    return q if q.is_dir() else None


def cmd_check(spec_arg):
    d = _resolve_spec(spec_arg)
    if d is None:
        print(f'Not a spec directory: {spec_arg}')
        return 1
    vs = rules.check_spec_dir(d)
    bad = {v['rule'] for v in vs}
    for rid in rules.RULE_IDS:
        if rid not in bad:
            print(f'PASS {rid}')
    for v in vs:
        print(f"FAIL {v['rule']} {v['message']} → {v['fix']}")
    return 1 if vs else 0


def _detect_eol(raw):
    return b'\r\n' if b'\r\n' in raw else b'\n'


_ASK_FIX = ('Ask the user with AskUserQuestion; the question text must mention {what} and the question must OFFER '
            'an option labelled exactly "{opt}" (the user has to pick that option; other labels do not count); '
            'wait for the answer, then run this command again.')


def approval_tag(tasks_text):
    """The tag the approval question must contain: binds the user's answer to THIS version of tasks.md."""
    return '[tasks:' + rules.approval_hash(tasks_text)[:8] + ']'


def cmd_approve(spec_arg):
    d = _resolve_spec(spec_arg)
    if d is None:
        print(f'Not a spec directory: {spec_arg}')
        return 1
    tasks_p = d / 'tasks.md'
    if not tasks_p.exists():
        print(f'{d.name}/tasks.md does not exist - nothing to approve.')
        return 1
    root = ev.find_root(d)
    raw = tasks_p.read_bytes()
    text = raw.decode('utf-8', errors='replace')
    bad = rules.check_content('tasks', text)
    if bad:
        for v in bad[:8]:
            print(f"FAIL {v['rule']} {v['message']} → {v['fix']}")
        print('Refused: tasks.md is not R1-valid, so it cannot be approved. Fix the violations above, then ask '
              'the user for approval.')
        return 1
    tm = _mtime(tasks_p) or 0.0
    sess = _current_session(root)
    tag = approval_tag(text)
    ans = ev.affirmative_answer(root, sess, APPROVE_TOPIC, tm, label_re=APPROVE_LABEL, must_contain=tag)
    if ans is None:
        print('Refused: no recorded user answer "Approve" to a question about the tasks that contains the tag '
              + tag + ' (it must come from an '
              'AskUserQuestion answered in this session, after the last change of tasks.md; a question alone, '
              'a "No" or an answer from another session does not count).\n'
              'Fix: ' + _ASK_FIX.format(opt='Approve', what='approving the tasks and contain EXACTLY the tag ' + tag
                                  + ' (e.g. "Approve these tasks? ' + tag + '")')
              + ' If you edit tasks.md afterwards, ask again.' + _session_note(sess))
        return 1
    eol = _detect_eol(raw)
    h = rules.approval_hash(text)
    line = f'Approved: {date.today().isoformat()} hash:{h}'
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    idx = [i for i, ln in enumerate(lines) if re.match(r'^\s*approved\s*:', ln, re.I)]
    if idx:
        lines[idx[-1]] = line
        for i in reversed(idx[:-1]):
            del lines[i]
    else:
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ['', line, '']
    tasks_p.write_bytes('\n'.join(lines).encode('utf-8').replace(b'\n', eol))
    new = _read(tasks_p)
    if not rules.approval_valid(new):  # pragma: no cover - defensive
        print('Wrote the Approved line but it does not validate; please report this.')
        return 1
    ev.append_approved(root, sess, d.name, h)
    print(line)
    return 0


def _tasks_hash(d):
    """approval_hash of the current tasks.md ('' when missing) - lets Status-only edits keep a spec closed."""
    if d is None or not (d / 'tasks.md').exists():
        return ''
    return rules.approval_hash(_read(d / 'tasks.md'))


def _close_gaps(d, root):
    """R6/R7 gaps that prevent a completed close (list of 'RULE message → fix' strings)."""
    gaps = []
    tasks_t = _read(d / 'tasks.md')
    if not (d / 'tasks.md').exists() or not rules.approval_valid(tasks_t):
        gaps.append('R6 tasks.md has no valid approval → ask the user, then `aidd rules approve <spec_dir>`.')
    elif not _approval_recorded(root, d.name, tasks_t):
        gaps.append('R6 the Approved: line has no recorded `approved` event for the current hash → '
                    'run `aidd rules approve <spec_dir>` after the user picks "Approve".')
    if not (d / 'qa-audit.md').exists():
        gaps.append('R7 qa-audit.md does not exist (Step 6 not done) → dispatch the independent auditors per '
                    'required domain and write qa-audit.md.')
    # D1: a code edit applies to every open spec (no per-spec attribution)
    since = max([e['ts'] for e in ev.events(root, kind='code_edit')], default=0.0)
    for dom in sorted(rules.uncovered_domains(root, None, d.name, since, spec_dir=d)):
        gaps.append(f'R7 no distinct {dom} auditor subagent ran after the last code edit → dispatch one whose '
                    f'prompt/description names "{dom}", then rewrite qa-audit.md.')
    return gaps


def _clear_pointer(root, spec_id):
    if ev.get_active_spec(root) == spec_id:
        ev.clear_active_spec(root)
        return True
    return False


def cmd_close(spec_arg):
    root = ev.find_root()
    d = _resolve_spec(spec_arg, root)
    if d is None:
        print(f'Not a spec directory: {spec_arg}')
        return 1
    root = ev.find_root(d)
    if d.name not in ev.open_specs(root, include_approved=True):   # aidd:FR-009 named spec: closable
        print(f'{d.name} is not an open spec (no plan.md/tasks.md edit and no `approved` event recorded, or '
              'already closed) - nothing to close.')
        return 1
    gaps = _close_gaps(d, root)
    if gaps:
        for g in gaps:
            print(f'FAIL {g}')
        print(f'Refused: {d.name} stays open until these gaps are closed.')
        return 1
    sess = _current_session(root)
    # the answer must postdate qa-audit.md (a stale "yes" from before the audit does not count)
    ans = ev.affirmative_answer(root, sess, CLOSE_TOPIC, _mtime(d / 'qa-audit.md') or 0.0, label_re=CLOSE_LABEL,
                               must_contain=f'[spec:{d.name}]')
    if ans is None:
        print('Refused: no recorded user answer "Yes, close" to a close question (asked after qa-audit.md).\n'
              'Fix: ' + _ASK_FIX.format(opt='Yes, close', what='closing the spec (e.g. "Close spec X as '
                                                         'completed?")')
              + _session_note(sess))
        return 1
    ev.append_spec_closed(root, sess, d.name, reason='completed', hash=_tasks_hash(d))
    cleared = _clear_pointer(root, d.name)
    print(f'{d.name} closed as completed' + (' (active-spec pointer cleared).' if cleared else '.'))
    return 0


KEEP_IT_RE = re.compile(r'^no,?\s+keep\s+it\b', re.I)
_SPEC_TAG_RE = re.compile(r'\[spec:([^\]\s]+)\]', re.I)


def _keep_it_ts(root, spec_id, session=None):
    """aidd:FR-006 ts of the newest typed "No, keep it" (a real user prompt starting with that phrase, in
    `session` or 'unknown-session'; one naming another spec via `[spec:X]` does not count), else 0.0."""
    try:
        sessions = {session, 'unknown-session'} if session else {None}
        best = 0.0
        for s in sessions:
            for e in ev.events(root, kind='prompt', session=s):
                if not _is_real_prompt(e):
                    continue
                text = str((e['detail'] or {}).get('text', '')).strip()
                if not KEEP_IT_RE.match(text):
                    continue
                tags = [t.lower() for t in _SPEC_TAG_RE.findall(text)]
                if tags and str(spec_id).lower() not in tags:
                    continue
                best = max(best, e['ts'])
        return best
    except Exception:
        return 0.0


def _abandon_since(root, spec_id, d, session=None):
    """Timestamp after which an abandon answer counts: the later of the newest typed "No, keep it"
    (it cancels any earlier Abandon answer) and the spec's last `approved` / `spec_closed` (re-open)
    event, else tasks.md mtime, else 0.0."""
    keep = _keep_it_ts(root, spec_id, session)
    try:
        ts = [e['ts'] for k in ('approved', 'spec_closed') for e in ev.events(root, kind=k)
              if (e['detail'] or {}).get('spec') == spec_id]
        if ts:
            return max(max(ts), keep)
    except Exception:
        pass
    try:
        if d is not None:
            return max(_mtime(d / 'tasks.md') or 0.0, keep)
    except Exception:
        pass
    return keep


def cmd_abandon(spec_arg, reason=''):
    root = ev.find_root()
    d = _resolve_spec(spec_arg, root)
    spec_id = d.name if d is not None else Path(str(spec_arg)).name
    if d is not None:
        root = ev.find_root(d)
    if spec_id not in ev.open_specs(root, include_approved=True):   # aidd:FR-009 named spec: closable
        print(f'{spec_id} is not an open spec - nothing to abandon.')
        return 1
    sess = _current_session(root)
    ans = ev.affirmative_answer(root, sess, ABANDON_TOPIC, _abandon_since(root, spec_id, d, sess),
                               label_re=ABANDON_LABEL,
                               must_contain=f'[spec:{spec_id}]')
    if ans is None:
        print('Refused: no recorded user answer "Abandon" to an abandon question in this session (a later '
              'typed "No, keep it" cancels an earlier Abandon).\n'
              'Fix: ' + _ASK_FIX.format(opt='Abandon', what='abandoning the spec (e.g. "Abandon spec X?")')
              + _session_note(sess))
        return 1
    ev.append_spec_closed(root, sess, spec_id, reason='abandoned', hash=_tasks_hash(d))
    cleared = _clear_pointer(root, spec_id)
    print(f'{spec_id} abandoned (no longer open)' + (' (active-spec pointer cleared)' if cleared else '')
          + (f' - reason: {reason.strip()[:200]}' if reason.strip() else '') + '.')
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        _sanitize_env()
        if argv and argv[0] == 'status':
            try:
                return cmd_status(argv[1:])
            except Exception as e:   # status never fails and never reports an "internal error" (D14)
                print(f'aidd status: could not read some state ({type(e).__name__}); nothing was changed.')
                return 0
        if len(argv) == 3 and argv[0] == 'rules' and argv[1] in ('check', 'approve', 'close'):
            return {'check': cmd_check, 'approve': cmd_approve, 'close': cmd_close}[argv[1]](argv[2])
        if len(argv) >= 3 and argv[0] == 'rules' and argv[1] == 'abandon':
            rest = argv[2:]
            reason = ''
            if '--reason' in rest:
                i = rest.index('--reason')
                reason = ' '.join(rest[i + 1:])
                rest = rest[:i]
            if len(rest) == 1:
                return cmd_abandon(rest[0], reason)
        print(__doc__)
        return 2
    except SystemExit:
        raise
    except Exception as e:
        print(f'aidd: internal error ({type(e).__name__}: {e})')
        return 1


if __name__ == '__main__':
    sys.exit(main())
