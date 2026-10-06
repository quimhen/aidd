#!/usr/bin/env python3
"""
aidd status / aidd rules — the mechanical ledger and the rule commands for the AIDD
hard rules (contract: specs/002-aidd-hard-rules/spec.md, incl. the Rev 1 amendments). Stdlib only.

Usage:
    aidd_status.py status [spec_dir] [--json] [--refresh]
                                                ledger from the evidence log + spec files (exit 0 always);
                                                --refresh recomputes git/disk facts (key `derived` in --json)
    aidd_status.py rules check <spec_dir>       PASS|FAIL Rn message -> fix  (exit 1 on any violation)
    aidd_status.py rules approve <spec_dir>     write `Approved: <date> hash:<hash>` in tasks.md + record the
                                                `approved` event and activate the spec (gate pointer); needs an
                                                R1-valid tasks.md, a valid `## Verification` in spec.md and, when
                                                a current review.html exists, a COMPLETE review.md plus one owner
                                                consent act (tagged answer, tagged prompt or typed on a TTY);
                                                without a current page: the recorded answer "Approve" to an
                                                AskUserQuestion carrying the [tasks:<hash8>] tag
    aidd_status.py rules activate <spec_dir>    point the per-spec code gate (.aidd/gate_spec) at an open spec
    aidd_status.py verify <spec_dir>            run every `## Verification` row, save evidence/verify-<n>.txt
                                                and record a `verify_run` event (exit 1 when a row fails)
    aidd_status.py rules close <spec_id>        record spec_closed(completed): needs a valid approval,
                                                qa-audit.md, every required domain audited (spec 007 specs:
                                                plus a fresh passing verify_run) and the user's
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
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import date, datetime
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
# aidd:FR-313 the negative lookahead refuses every label that starts `aprobar con resum...` (any case, typo or extra
# word) in the generic tagged-answer route and its typed fallback: only the exact SUMMARY_LABEL, read by
# `_summary_answer`, mints `source=summary`
APPROVE_LABEL = re.compile(r'^(approve|aprobar|aprobado)\b(?!\s+con\s+resum)', re.I)
SUMMARY_LABEL = 'Aprobar con resumen'
_SUMMARY_EXACT_RE = re.compile(r'\A\s*Aprobar con resumen\s*\Z')      # compiled WITHOUT re.I: case-sensitive
CLOSE_TOPIC = re.compile(r'close|cierr|finaliz', re.I)
CLOSE_LABEL = re.compile(r'^(yes,? close|cerrar|si,? cerrar|sí,? cerrar)', re.I)
ABANDON_TOPIC = re.compile(r'abandon|descart', re.I)
ABANDON_LABEL = re.compile(r'^(abandon|abandonar|descartar)', re.I)
CHECK_MARK, CROSS_MARK = '✔', '✘'


MAX_READ = 4 * 1024 * 1024

RULES_OFF_VALUES = ('off', '0', 'false', 'no')   # same values as hooks/_common.rules_mode
VERIFY_TIMEOUT_DEFAULT = 600
GIT_TIMEOUT = 5


def _review_mod():
    """aidd:FR-204 aidd_review imported lazily (it lives next to this file); None on an old install."""
    try:
        import aidd_review  # noqa: WPS433
        return aidd_review
    except Exception:
        return None


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


def build_status(spec_dir, root=None, named=False, fingerprint=None):
    """Mechanical ledger of one spec as a plain dict (JSON-serialisable). Never raises: a
    pathological spec/tasks file yields a degraded ledger flagged `unparseable` (D14).
    aidd:FR-009 `named=True` (the user named this spec) also reports an approved-only spec as open."""
    try:
        return _build_status(spec_dir, root, named, fingerprint)
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
                # aidd:FR-208 the spec-007 keys exist in the degraded ledger too (same shape, safe values)
                'review': {'page': False, 'page_current': False, 'present': False, 'complete': False,
                           'reason': 'unparseable'},
                'verification': {'declared': False, 'commands': 0, 'status': 'none', 'ts': None},
                'gate': 0, 'code_edits_attributed': None,
                'overrides': _safe(lambda: ev.count(root, 'rules_override'), 0) if root else 0,
                'r5_mode': _safe(rules.r5_audit_mode, 'advisory'),
                'gate_pointer': _safe(lambda: ev.get_gate_spec(root), '') if root else '',
                'gate_pointer_changes': [], 'rules_mode': _rules_mode(),
                'why_blocked': [f'Could not analyse this spec ({type(e).__name__}); check spec.md/tasks.md '
                                'for pathological content (huge, binary or malformed tables).']}


def _safe(fn, default):
    """Call `fn()`; `default` on any exception (status never fails, D14)."""
    try:
        return fn()
    except Exception:
        return default


def _rules_mode():
    """aidd:FR-208 aidd:AC-214 The EFFECTIVE AIDD_RULES this process sees: {'raw', 'mode', 'note'}; mode is
    'off' | 'warn' | 'enforce' exactly like hooks/_common.rules_mode."""
    raw = os.environ.get('AIDD_RULES', '')
    v = raw.strip().lower()
    mode = 'off' if v in RULES_OFF_VALUES else ('warn' if v == 'warn' else 'enforce')
    note = {'off': 'rules disabled', 'warn': 'messages only, nothing is blocked'}.get(mode, '')
    return {'raw': raw, 'mode': mode, 'note': note}


def _review_summary(d):
    """aidd:FR-208 Small JSON-safe view of aidd_review.review_state for the ledger. Never raises."""
    out = {'page': (Path(d) / 'review.html').is_file(), 'page_current': False, 'present': False,
           'complete': False, 'legacy': False, 'reason': ''}
    rv = _review_mod()
    if rv is None:
        out['reason'] = 'aidd_review.py not installed'
        return out
    try:
        rs = rv.review_state(d)
        for k in ('page_current', 'present', 'complete', 'legacy'):     # aidd:FR-304 legacy = other-grammar review.md
            out[k] = bool(rs.get(k))
        out['reason'] = str(rs.get('reason') or '')
        out['missing'] = len(rs.get('missing') or [])
    except Exception as e:
        out['reason'] = f'review state unavailable ({type(e).__name__})'
    return out


def _attributed_edits(root, spec, tasks_text):
    """aidd:FR-208 aidd:FR-209 Code edits stamped `target=<spec>` after the spec's current approval, or None
    when the spec has no recorded approval. Never raises."""
    try:
        a = ev.latest_approved(root, spec, rules.approval_hash(tasks_text)) if tasks_text.strip() else None
        if a is None:
            return None
        return len(ev.code_edits_for(root, spec, float(a.get('ts') or 0.0), include_unstamped=False))
    except Exception:
        return None


def _build_status(spec_dir, root=None, named=False, fingerprint=None):
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
    # aidd:FR-208 spec 007 facts: review, verification, gate version, attributed edits, pointer, modes
    st['review'] = _review_summary(d)
    st['verification'] = _safe(lambda: _verification_state(d, root, fingerprint),
                               {'declared': False, 'commands': 0, 'status': 'none', 'ts': None})
    st['gate'] = _gate_version(root, d, tasks_text) if approval == 'valid' else 0
    st['code_edits_attributed'] = (_attributed_edits(root, d.name, tasks_text)
                                   if st['tasks']['approval_recorded'] else None)
    st['overrides'] = _safe(lambda: ev.count(root, 'rules_override'), 0)
    st['r5_mode'] = _safe(rules.r5_audit_mode, 'advisory')
    st['gate_pointer'] = _safe(lambda: ev.get_gate_spec(root), '')
    st['gate_pointer_changes'] = _safe(lambda: ev.recent_gate_pointer_changes(root, 5), [])
    st['rules_mode'] = _rules_mode()
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
                          '(run `aidd review ' + d.name + '`, then `aidd review ' + d.name + ' --wait` in the background: '
                          'the owner saves review.md from the page and you ask ONE tagged question; or ask the '
                          'user with AskUserQuestion offering the option "Approve"; then `aidd rules approve`).')
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
        # aidd:FR-201 aidd:FR-208 gate pointer + its last changes, warn/off overrides, effective modes
        'gate_pointer': _safe(lambda: ev.get_gate_spec(root), ''),
        'gate_pointer_changes': _safe(lambda: ev.recent_gate_pointer_changes(root, 5), []),
        'overrides': _safe(lambda: ev.count(root, 'rules_override'), 0),
        'rules_mode': _rules_mode(),
        'r5_mode': _safe(rules.r5_audit_mode, 'advisory'),
    }


_DEGRADED_GLOBAL = {'answers': 0, 'questions': 0, 'user_answered': False, 'stop_blocks': {},
                    'stop_block_exhausted': 0, 'hook_errors': 0, 'last_hook_error': None, 'open_specs': [],
                    'gate_pointer': '', 'gate_pointer_changes': [], 'overrides': 0, 'r5_mode': 'advisory'}


def _pointer_changes_text(changes):
    """'F23 -> F22 (activate), none -> F23 (approve)' from recent_gate_pointer_changes (newest first)."""
    parts = []
    for c in changes or []:
        try:
            parts.append(f"{c.get('prev') or 'none'} -> {c.get('spec') or '?'}"
                         + (f" ({c.get('by')})" if c.get('by') else ''))
        except Exception:
            continue
    return ', '.join(parts)


def format_pointer(g):
    """aidd:FR-201 The ONE extra line of the default status: the gate pointer and its last changes."""
    ptr = g.get('gate_pointer') or 'none (the code gate infers its target)'
    ch = _pointer_changes_text(g.get('gate_pointer_changes'))
    return f'gate pointer: {ptr}' + (f' · last changes: {ch}' if ch else '')


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
    extra = _spec007_line(st)
    if extra:
        lines.append(extra)
    for w in st.get('why_blocked') or []:
        lines.append(f'  WHY blocked: {w}')
    return '\n'.join(lines)


def _review_text(r):
    r = r or {}
    if r.get('complete'):
        return 'complete ✔'
    if not r.get('page'):
        return 'no page'
    if r.get('legacy'):          # aidd:FR-307 a review.md of the other grammar: regenerate, it is never migrated
        return 'legacy review.md (regenerate)'
    if not r.get('page_current'):
        return 'page stale (run `aidd review`)'
    if not r.get('present'):
        return 'waiting for owner'          # aidd:FR-307 the page saves review.md; the agent runs `--wait`
    return 'incomplete ✘' + (f" ({r['reason']})" if r.get('reason') else '')


def _verification_text(v):
    v = v or {}
    if not v.get('declared'):
        return 'none declared'
    return f"{v.get('status', 'none')} ({v.get('commands', 0)} command(s))"


def _spec007_line(st):
    """aidd:FR-208 One extra ledger line, only for a spec that uses the spec-007 machinery (a review page,
    a declared Verification or a gate-2 approval): legacy specs print exactly what they printed before."""
    try:
        r, v = st.get('review') or {}, st.get('verification') or {}
        if not (r.get('page') or r.get('present') or v.get('declared') or st.get('gate')):
            return ''
        s = f"Review: {_review_text(r)} · Verification: {_verification_text(v)}"
        s += ' · gate ' + (str(st['gate']) if st.get('gate') else 'legacy')
        if st.get('code_edits_attributed') is not None:
            s += f" · {st['code_edits_attributed']} code edit(s) attributed since approval"
        return s
    except Exception:
        return ''


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
        format_pointer(g),
    ]
    # aidd:FR-208 aidd:AC-214 shown only when they carry information (default output stays as before)
    rm = g.get('rules_mode') or _rules_mode()
    if rm.get('mode') in ('warn', 'off'):
        lines.append(f"AIDD_RULES={rm['mode']} ({rm['note']}) - a last-resort diagnostic, not a workflow")
    if g.get('overrides'):
        lines.append(f"warn overrides: {g['overrides']}")
    return '\n'.join(lines)


def _spec_dirs(root):
    specs = root / 'specs'
    try:
        return sorted(p for p in specs.iterdir() if p.is_dir()) if specs.is_dir() else []
    except Exception:
        return []


def _fingerprint_once():
    """F-2: a FingerprintOnce shared by every spec of one `aidd status` run (None with an older aidd_rules)."""
    cls = getattr(rules, 'FingerprintOnce', None)
    try:
        return cls(ev) if cls is not None else None
    except Exception:
        return None


def _verification_state(d, root, fingerprint=None):
    if fingerprint is None:
        return rules.verification_state(d, root)
    return rules.verification_state(d, root, fingerprint=fingerprint)


def cmd_status(args):
    as_json = '--json' in args
    refresh = '--refresh' in args            # aidd:FR-208 recompute git/disk facts without an LLM
    pos = [a for a in args if not a.startswith('--')]
    root = ev.find_root(Path(pos[0]) if pos else None)
    try:
        g = _global(root)
    except Exception:
        g = dict(_DEGRADED_GLOBAL, rules_mode=_rules_mode())
    derived = None
    fp = _fingerprint_once()            # F-2: one worktree fingerprint per status run, shared by every spec
    if refresh:
        focus = Path(pos[0]).resolve().name if pos and Path(pos[0]).is_dir() else None
        derived = _derived_facts(root, focus, fp)
    if pos:
        spec_dir = Path(pos[0])
        if not spec_dir.is_dir():
            print(f'Not a directory: {spec_dir}')
            return 0
        sts = [build_status(spec_dir, root, named=True, fingerprint=fp)]
    else:
        names = {p.name: p for p in _spec_dirs(root)}
        shown = [names[s] for s in g['open_specs'] if s in names]
        active = ev.get_active_spec(root)
        if active in names and names[active] not in shown:
            shown.append(names[active])
        sts = [build_status(p, root, fingerprint=fp) for p in shown]
        if as_json:
            out = {'open_specs': g['open_specs'], 'specs': sts,
                   'other_specs': sorted(n for n in names if names[n] not in shown), 'evidence': g}
            if derived is not None:
                out['derived'] = derived
            print(json.dumps(out, indent=2, ensure_ascii=False))
            return 0
        if not sts:
            if not names:
                print('No specs found (no open spec and no specs/ folder).')
            else:
                print('No open specs. Specs:')
                for p in names.values():
                    s = build_status(p, root, fingerprint=fp)
                    print(f"  {s['spec']}  tasks: {s['tasks']['approval']} · {s['code_edits']} code edits "
                          f"· qa-audit {'yes' if s['qa_audit'] else 'no'}")
            print(format_global(g))
            if derived is not None:
                print(format_refresh(derived))
            return 0
    if as_json:
        out = dict(sts[0], evidence=g) if pos else {'open_specs': g['open_specs'], 'specs': sts, 'evidence': g}
        if derived is not None:
            out['derived'] = derived
        print(json.dumps(out, indent=2, ensure_ascii=False))
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
    if derived is not None:
        print(format_refresh(derived))
    return 0


# ------------------------------------------------------------- refresh (FR-208)

def _git(root, *args):
    """aidd:FR-208 stdout of `git <args>` run in `root` (list form, 5 s timeout, utf-8), or None on ANY
    failure (git missing, not a repo, non-zero exit, timeout). Never raises."""
    try:
        r = subprocess.run(['git', *args], cwd=str(root), capture_output=True, timeout=GIT_TIMEOUT,
                           stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            return None
        return r.stdout.decode('utf-8', errors='replace')
    except Exception:
        return None


_PROTO_DIR_RE = re.compile(r'proto|mockup', re.I)


def _porcelain_path(line):
    p = line[3:].strip()
    if ' -> ' in p:                       # rename: keep the new path
        p = p.split(' -> ', 1)[1]
    if len(p) >= 2 and p[0] == '"' and p[-1] == '"':
        p = p[1:-1]
    return p.replace('\\', '/')


def _git_facts(root):
    """Branch, last commit, dirty/untracked counts, untracked files under specs/<id>/ and prototype folders;
    {'available': False} when git is unavailable."""
    branch = _git(root, 'rev-parse', '--abbrev-ref', 'HEAD')
    if branch is None:
        return {'available': False}
    out = {'available': True, 'branch': branch.strip(), 'last_commit': '', 'dirty': None, 'untracked': None,
           'untracked_specs': {}, 'untracked_prototypes': []}
    last = _git(root, 'log', '-1', '--format=%h %cs %s')
    out['last_commit'] = (last or '').strip()[:160]
    por = _git(root, 'status', '--porcelain', '-uall')
    if por is None:
        return out
    dirty = untracked = 0
    for line in por.split('\n'):
        if len(line) < 4:
            continue
        if line[:2] != '??':
            dirty += 1
            continue
        untracked += 1
        path = _porcelain_path(line)
        segs = [s for s in path.split('/') if s]
        if len(segs) >= 3 and segs[0] == 'specs':
            out['untracked_specs'].setdefault(segs[1], []).append('/'.join(segs[2:]))
        elif segs and _PROTO_DIR_RE.search(segs[0]) and len(out['untracked_prototypes']) < 50:
            out['untracked_prototypes'].append(path)
    out['dirty'], out['untracked'] = dirty, untracked
    return out


def _approval_state(root, d, tasks_text):
    if not (d / 'tasks.md').exists():
        return 'no-tasks'
    if rules.approval_line(tasks_text) is None:
        return 'pending'
    if not rules.approval_valid(tasks_text):
        return 'invalid'
    return 'approved' if _approval_recorded(root, d.name, tasks_text) else 'approved-unrecorded'


def _derived_facts(root, focus=None, fingerprint=None):
    """aidd:FR-208 aidd:AC-212 Facts recomputed now from git and the disk (no LLM): git facts, specs by
    approval state, per listed spec its review/verification state and attributed code edits, the gate
    pointer and its last changes, the rules_override count, the effective AIDD_RULES and the R5 mode.
    Listed specs: open or approved-and-not-closed ones, the gate pointer's and `focus`. Never raises."""
    facts = {'git': {'available': False}, 'specs_by_approval': {}, 'specs': [], 'other_specs': 0,
             'gate_pointer': '', 'gate_pointer_changes': [], 'overrides': 0, 'rules_mode': _rules_mode(),
             'r5_mode': _safe(rules.r5_audit_mode, 'advisory')}
    facts['git'] = _safe(lambda: _git_facts(root), {'available': False})
    facts['gate_pointer'] = _safe(lambda: ev.get_gate_spec(root), '')
    facts['gate_pointer_changes'] = _safe(lambda: ev.recent_gate_pointer_changes(root, 5), [])
    facts['overrides'] = _safe(lambda: ev.count(root, 'rules_override'), 0)
    listed = set(_safe(lambda: ev.open_specs(root, include_approved=True), []))
    for extra in (facts['gate_pointer'], focus):
        if extra:
            listed.add(extra)
    counts = {}
    untracked_specs = facts['git'].get('untracked_specs') or {}
    for d in _spec_dirs(root)[:500]:
        try:
            t = _read(d / 'tasks.md')
            ap = _approval_state(root, d, t)
            counts[ap] = counts.get(ap, 0) + 1
            if d.name not in listed:
                facts['other_specs'] += 1
                continue
            facts['specs'].append({
                'spec': d.name, 'approval': ap, 'review': _review_summary(d),
                'verification': _safe(lambda: _verification_state(d, root, fingerprint),
                                      {'declared': False, 'commands': 0, 'status': 'none', 'ts': None}),
                'gate': _gate_version(root, d, t) if ap == 'approved' else 0,
                'code_edits_attributed': _attributed_edits(root, d.name, t) if ap == 'approved' else None,
                'untracked': len(untracked_specs.get(d.name, [])),
            })
        except Exception:
            continue
    facts['specs_by_approval'] = counts
    return facts


def format_refresh(facts):
    """aidd:FR-208 Text block of `aidd status --refresh`."""
    f = facts or {}
    g = f.get('git') or {}
    lines = ['Refresh (recomputed now from git and disk, no LLM):']
    if not g.get('available'):
        lines.append('  git: unavailable')
    else:
        dirty = g.get('dirty')
        lines.append(f"  git: branch {g.get('branch') or '?'} · last commit {g.get('last_commit') or 'none'} · "
                     + (f"{dirty} dirty · {g.get('untracked')} untracked" if dirty is not None
                        else 'status unavailable'))
        for sp, files in sorted((g.get('untracked_specs') or {}).items()):
            more = len(files) - 8
            lines.append(f"  untracked under specs/{sp}/: " + ', '.join(files[:8])
                         + (f' (+{more} more)' if more > 0 else ''))
        protos = g.get('untracked_prototypes') or []
        if protos:
            lines.append('  untracked prototype files: ' + ', '.join(protos[:8])
                         + (f' (+{len(protos) - 8} more)' if len(protos) > 8 else ''))
    by = f.get('specs_by_approval') or {}
    lines.append('  specs: ' + (' · '.join(f'{n} {k}' for k, n in sorted(by.items())) or 'none'))
    for s in f.get('specs') or []:
        seg = (f"  {s['spec']}: approval {s.get('approval')} · review {_review_text(s.get('review'))} · "
               f"verification {_verification_text(s.get('verification'))}")
        if s.get('code_edits_attributed') is not None:
            seg += f" · {s['code_edits_attributed']} code edit(s) attributed since approval"
        lines.append(seg)
    if f.get('other_specs'):
        lines.append(f"  (+{f['other_specs']} other spec(s) not open)")
    lines.append('  ' + format_pointer(f))
    rm = f.get('rules_mode') or {}
    lines.append(f"  AIDD_RULES={rm.get('mode', 'enforce')}" + (f" ({rm['note']})" if rm.get('note') else ''))
    lines.append(f"  warn overrides: {f.get('overrides', 0)} · R5 audits: {f.get('r5_mode', 'advisory')}")
    return '\n'.join(lines)


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


def _norm_typed(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip().lower()


def _tty_confirm(tag, isatty=None, reader=input):
    """aidd:FR-204 Consent route (c), CLI only: on an interactive terminal (stdin AND stdout are TTYs) the
    owner types the tag (`approve [tasks:<h8>]` or the bare tag). `isatty` (bool or callable) and `reader`
    are injectable for tests. False on anything else, including EOF / Ctrl-C / any error."""
    try:
        if isatty is None:
            interactive = bool(sys.stdin and sys.stdin.isatty() and sys.stdout and sys.stdout.isatty())
        else:
            interactive = bool(isatty() if callable(isatty) else isatty)
        if not interactive:
            return False
        typed = _norm_typed(reader(f'The review is complete. To approve, type exactly: approve {tag}\n> '))
        want = _norm_typed(tag)
        return bool(want) and typed in (want, 'approve ' + want)
    except (EOFError, KeyboardInterrupt):
        return False
    except Exception:
        return False


def _consent(ev, root, sess, d, tag, rs, tty=None):
    """aidd:FR-204 The owner's consent act for a COMPLETE review, newer than review.md (and tasks.md):
    (a) a recorded AskUserQuestion answer "Approve" whose question carries `tag` (a typed one-line
    `Approve <tag>` found by the same reader counts as a prompt), else (b) a hook-recorded user prompt
    with the tag and an approve word (aidd_review.prompt_consent), else (c) the tag typed on a TTY.
    Returns (kind, ts) with kind 'answer' | 'prompt' | 'tty', or None. `tty` replaces _tty_confirm
    (tests). Never raises."""
    try:
        since = max(_mtime(Path(d) / 'tasks.md') or 0.0, float((rs or {}).get('mtime') or 0.0))
    except Exception:
        since = time.time()          # fail closed: nothing recorded before now counts
    try:
        ans = ev.affirmative_answer(root, sess, APPROVE_TOPIC, since, label_re=APPROVE_LABEL, must_contain=tag)
        if ans:
            return ('prompt' if ans.get('kind') == 'prompt' else 'answer'), float(ans['ts'])
        ans = ev.tagged_answer_any_session(root, sess, APPROVE_TOPIC, since, label_re=APPROVE_LABEL, must_contain=tag)
        if ans:                  # clicked in another window: the [tasks:<h8>] tag binds it to this tasks.md
            return 'answer', float(ans['ts'])
    except Exception:
        pass
    rv = _review_mod()
    if rv is not None:
        try:
            p = rv.prompt_consent(ev, root, sess, tag, since)
            if p:
                return 'prompt', float(p['ts'])
        except Exception:
            pass
    try:
        if (tty or _tty_confirm)(tag):
            return 'tty', time.time()
    except Exception:
        pass
    return None


def _review_approval(d, root, text):
    """aidd:FR-204 review_state of the spec for the approval decision. Fails closed: when aidd_review is
    missing but a review.html exists, or the state cannot be read, the page counts as current and the
    review as incomplete (the answer-only route is then refused). `text` is the tasks.md the caller
    validated: if tasks.md changed while the review was read, the review is not complete."""
    page = Path(d) / 'review.html'
    rv = _review_mod()
    if rv is None:
        if page.is_file():
            return {'page_current': True, 'complete': False,
                    'reason': 'aidd_review.py is not installed next to aidd_status.py (reinstall AIDD)'}
        return {'page_current': False, 'complete': False, 'reason': 'no review page'}
    try:
        rs = dict(rv.review_state(d))
    except Exception as e:
        return {'page_current': page.is_file(), 'complete': False,
                'reason': f'review state unavailable ({type(e).__name__})'}
    try:
        if rs.get('complete') and rules.approval_hash(_read(Path(d) / 'tasks.md')) != rules.approval_hash(text):
            rs['complete'] = False
            rs['reason'] = 'tasks.md changed while the approval ran: run the command again'
    except Exception:
        rs['complete'] = False
    return rs


def _gate_version(root, d, tasks_text):
    """aidd:FR-205 `gate` of the spec's CURRENT approved event (the one for this tasks hash, else the newest);
    0 = legacy (approved before spec 007, or no approved event)."""
    try:
        a = ev.latest_approved(root, d.name, rules.approval_hash(tasks_text)) if tasks_text.strip() else None
        if a is None:
            a = ev.latest_approved(root, d.name)
        return int((a or {}).get('gate') or 0)
    except Exception:
        return 0


def _review_fix(d, tag):
    """aidd:FR-307 The owner flow of spec 008: the page saves review.md itself, the agent only waits and asks ONE
    tagged question. Nothing here tells the owner to move a file or type a line first."""
    return (f'Fix: run `aidd review specs/{d.name} --wait` in the background (it prints one STATE line and nothing '
            f'else; the owner opens specs/{d.name}/review.html, checks the sections and presses `Aprobar y guardar`: '
            f'the page saves review.md itself); when it returns STATE=complete, ask the owner ONE question with the '
            f'tag `{tag}` (option Approve). Typing `approve {tag}` stays a fallback. Never read review.md or '
            f'review.html: use `aidd review specs/{d.name} --check` or `--comments`.')


def _summary_answer(ev, root, session, since, tag):
    """aidd:FR-313 aidd:AC-327 The owner's explicit waiver of the review page: the newest topical hook-recorded
    AskUserQuestion answer whose QUESTION carries `tag` (and `aprobar`/`approve`) and whose chosen label is EXACTLY
    SUMMARY_LABEL (str.strip() equality). Reads answers only through `ev._answer_event` (case-sensitive pattern):
    never `affirmative_answer`, never `typed_approval`, so no typed prompt and no agent text can mint it. A newer
    topical answer with another label cancels it (the newest-answer-wins rule of `_answer_event`). Returns the
    answer event or None; never raises (any error = None, fail closed)."""
    try:
        if not tag:
            return None
        e = ev._answer_event(root, session, APPROVE_TOPIC, since, label_re=_SUMMARY_EXACT_RE, must_contain=tag)
        if not e:
            return None
        need = re.sub(r'\s+', ' ', str(tag)).strip().lower()
        for p in (e.get('detail') or {}).get('pairs') or []:
            if (isinstance(p, (list, tuple)) and len(p) == 2 and APPROVE_TOPIC.search(str(p[0]))
                    and need in re.sub(r'\s+', ' ', str(p[0])).strip().lower()
                    and str(p[1]).strip() == SUMMARY_LABEL):
                return e
    except Exception:
        pass
    return None


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
    # aidd:FR-204 aidd:FR-205 a valid, executable `## Verification` is required for every new approval
    spec_text = _read(d / 'spec.md')
    vbad = rules.check_verification(spec_text, root)
    if vbad:
        for v in vbad[:8]:
            print(f"FAIL {v['rule']} {v['message']} → {v['fix']}")
        print('Refused: spec.md has no valid "## Verification" table, so the tasks cannot be approved (the close '
              'gate runs those commands). Fix the rows above, then ask for approval again.')
        return 1
    tm = _mtime(tasks_p) or 0.0
    sess = _current_session(root)
    tag = approval_tag(text)
    rs = _review_approval(d, root, text)
    review_sha1 = None
    oversize = str(rs.get('reason') or '').startswith('source too large')
    # aidd:FR-204 fail closed: a review page that exists but is stale (sources edited after `aidd review`)
    # still makes the review the route; only "never generated" or "sources over the cap" keep the answer route.
    too_many = str(rs.get('reason') or '').startswith('too many items')
    if too_many:
        # aidd:FR-307 aidd:FR-313 fail closed: a spec the compact page cannot show is never approved by an answer
        # alone (not a bare tagged answer, not the summary label), with or without a review.html
        print(f'Refused: a review is required for {d.name} and the compact page cannot show it. '
              f'Cause: {rs.get("reason")}.\n' + _review_fix(d, tag))
        return 1
    review_route = (bool(rs.get('page_current')) or too_many
                    or ((d / 'review.html').is_file() and not oversize))
    # aidd:FR-313 the exact-label summary answer is checked FIRST, before the review_route split (both branches)
    summary = _summary_answer(ev, root, sess, tm, tag)
    if summary is not None:
        source, consent_ts = 'summary', summary.get('ts')
    elif review_route:
        # aidd:FR-204 a review page exists: review content + owner consent is the ONLY route
        if not rs.get('complete'):
            cause = rs.get('reason') or 'review.md is not complete'
            where = ('is current' if rs.get('page_current')
                     else 'exists but is stale: run `aidd review ' + d.name + '` again')
            print(f'Refused: a review exists for {d.name} (specs/{d.name}/review.html {where}): complete it. '
                  f'Cause: {cause}.\n' + _review_fix(d, tag))
            return 1
        c = _consent(ev, root, sess, d, tag, rs)
        if c is None:
            print(f'Refused: review.md is complete; the owner must confirm: answer the question tagged `{tag}` '
                  f'or type `approve {tag}`.\nFix: run `aidd review specs/{d.name} --wait` in the background; when '
                  f'it returns, ask the owner ONE question with the tag `{tag}` (option Approve): that single '
                  f'click is the consent.' + _session_note(sess))
            return 1
        kind, consent_ts = c
        source = 'review+' + kind
        review_sha1 = rs.get('sha1') or None
    else:
        # aidd:FR-204 no current page (never generated, or the sources exceed the cap): the answer route
        ans = ev.affirmative_answer(root, sess, APPROVE_TOPIC, tm, label_re=APPROVE_LABEL, must_contain=tag)
        if ans is None:
            print('Refused: no recorded user answer "Approve" to a question about the tasks that contains the tag '
                  + tag + ' (it must come from an '
                  'AskUserQuestion answered in this session, after the last change of tasks.md; a question alone, '
                  'a "No" or an answer from another session does not count).\n'
                  'Fix: ' + _ASK_FIX.format(opt='Approve', what='approving the tasks and contain EXACTLY the tag ' + tag
                                      + ' (e.g. "Approve these tasks? ' + tag + '")')
                  + ' If you edit tasks.md afterwards, ask again. (Or run `aidd review ' + d.name + '` and have the '
                  'owner review the page.)' + _session_note(sess))
            return 1
        source, consent_ts = 'answer', ans.get('ts')
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
    extra = rules.approval_evidence(spec_text, source, review_sha1=review_sha1, consent_ts=consent_ts)
    if not ev.append_approved(root, sess, d.name, h, **extra):
        print(line)
        print('Warning: the `approved` event could not be recorded (evidence log not writable); code edits stay '
              'blocked until `aidd rules approve` records it.')
        return 1
    activated = ev.activate_spec(root, d.name, by='approve')
    print(line)
    print(f'approved through {source}' + (' · gate pointer -> ' + d.name if activated else
                                          ' · gate pointer NOT moved (run `aidd rules activate ' + d.name + '`)'))
    for c in (rs.get('comments') or []) if source not in ('answer', 'summary') else []:
        try:
            print(f"note: {c['key']}: {str(c['text'])[:500]}")
        except Exception:
            continue
    return 0


def cmd_activate(spec_arg):
    """aidd:FR-201 `aidd rules activate <spec>`: point the per-spec code gate (.aidd/gate_spec) at an open
    (or approved, not closed) spec; ev.activate_spec is the only writer and logs `gate_pointer`."""
    root = ev.find_root()
    d = _resolve_spec(spec_arg, root)
    if d is None:
        print(f'Not a spec directory: {spec_arg}')
        return 1
    root = ev.find_root(d)
    prev = ev.get_gate_spec(root)
    if not ev.activate_spec(root, d.name, by='activate'):
        print(f'Refused: {d.name} is not an open spec (no plan.md/tasks.md edit or `approved` event recorded, or '
              'already closed), so it cannot be the gate target.')
        return 1
    now = ev.get_gate_spec(root) or d.name
    if prev == now:
        print(f'gate pointer already on {now}.')
    else:
        print(f'gate pointer: {prev or "none"} -> {now}')
    return 0


# ------------------------------------------------------------------- verify (FR-205)

def _verify_timeout():
    try:
        v = int(float(os.environ.get('AIDD_VERIFY_TIMEOUT', '') or VERIFY_TIMEOUT_DEFAULT))
        return v if v > 0 else VERIFY_TIMEOUT_DEFAULT
    except Exception:
        return VERIFY_TIMEOUT_DEFAULT


def _kill_tree(proc):
    """Kill a shell=True command and its children (a timed-out test runner must not linger)."""
    try:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True, timeout=15,
                           stdin=subprocess.DEVNULL)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        pass
    try:
        proc.kill()
    except Exception:
        pass


def _run_row(cmd, root, out_path, timeout):
    """Run one Verification command through the shell in `root`, stdout+stderr into `out_path` (a file, so a
    lingering grandchild can never hang a pipe). Returns (exit_code, note); exit -1 on timeout or spawn error."""
    kw = {'start_new_session': True} if os.name != 'nt' else {}
    try:
        with open(out_path, 'wb') as fh:
            proc = subprocess.Popen(cmd, shell=True, cwd=str(root), stdout=fh, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, **kw)
            try:
                return proc.wait(timeout=timeout), ''
            except subprocess.TimeoutExpired:
                _kill_tree(proc)
                try:
                    proc.wait(timeout=15)
                except Exception:
                    pass
                return -1, f'timeout after {timeout} s'
    except Exception as e:
        return -1, f'could not run ({type(e).__name__}: {e})'


def _row_file_id(n, i):
    s = re.sub(r'[^A-Za-z0-9_-]+', '', str(n or ''))[:20]
    return s or str(i)


def _row_ok(code, body, expected):
    m = re.match(r'^\s*contains\s*:\s*(.+?)\s*$', expected or '', re.I)
    if m:
        return m.group(1) in body
    return code == 0


def _reusable_rows(d, prior, code_fp, full):
    """Amendment to spec 007: {(cmd, expected): (text, result)} of the PRIOR run's passing rows that may be
    reused: the prior run was stable and recorded the same code fingerprint as now, the row passed and its
    evidence file is intact (sha1). Empty with --full, with no prior code fingerprint or when the code changed."""
    out = {}
    try:
        if full or not prior or code_fp is None or prior.get('code_fp_end') != code_fp or prior.get('stable') is not True:
            return out
        base = d.resolve()
        for r in prior.get('results') or []:
            if not isinstance(r, dict) or r.get('ok') is not True or 'expected' not in r:
                continue
            want = str(r.get('sha1') or '').lower()
            p = (base / str(r.get('evidence') or '')).resolve()
            try:
                p.relative_to(base)
                data = p.read_bytes()
            except Exception:
                continue
            if len(want) >= 12 and hashlib.sha1(data).hexdigest().startswith(want):
                out[(rules._norm_cell(r.get('cmd')), rules._norm_cell(r.get('expected')))] = (data, r)
    except Exception:
        return {}
    return out


def cmd_verify(spec_arg, full=False):
    """aidd:FR-205 aidd:AC-209 aidd:AC-216 aidd:AC-218 `aidd verify <spec>`: run every `## Verification` row
    (shell, project root, AIDD_VERIFY_TIMEOUT per row), save `evidence/verify-<n>.txt` (header line
    `# <cmd> | exit <code> | <ISO ts>` + combined output), mark zero-test / too-short output failed,
    fingerprint the tree before the first and after the last row and record `verify_run`. Rows with a
    lint problem are not run. Exit 0 only when every row passed, the tree was stable and the event was
    recorded."""
    root = ev.find_root()
    d = _resolve_spec(spec_arg, root)
    if d is None:
        print(f'Not a spec directory: {spec_arg}')
        return 1
    root = ev.find_root(d)
    spec_text = _read(d / 'spec.md')
    rows = rules.parse_verification(spec_text)
    if not rows:
        for v in rules.check_verification(spec_text, root)[:8]:
            print(f"FAIL {v['rule']} {v['message']} → {v['fix']}")
        print(f'Refused: {d.name}/spec.md has no runnable "## Verification" row - nothing was executed.')
        return 1
    evid = d / 'evidence'
    try:
        evid.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f'Refused: cannot create {evid} ({type(e).__name__}); nothing was executed.')
        return 1
    timeout = _verify_timeout()
    vhash = rules.verification_hash(spec_text)
    sess = _current_session(root)
    started = time.time()
    fp_start = ev.worktree_fingerprint(root)
    scope = rules.verification_scope(spec_text)               # [] = whole tree; else only this spec's files count
    gen = rules.verification_generated(spec_text)             # files the commands rewrite on purpose (outputs)
    st_start = ev.code_state(root, scope=scope)
    prior = ev.latest_verify_run(root, d.name)
    pexcl = (list(prior.get('code_generated') or []) + list(prior.get('code_changed') or [])) if prior else []
    prior_fp = ev.fingerprint_of(st_start, scope, exclude=pexcl) if (prior and st_start) else None
    reuse = _reusable_rows(d, prior, prior_fp, full)        # read BEFORE any evidence file is rewritten
    results = []
    for i, r in enumerate(rows, 1):
        cmd, expected = r['cmd'], (r.get('expected') or 'exit 0')
        n = r.get('n') or str(i)
        fid = _row_file_id(n, i)
        rel = f'evidence/verify-{fid}.txt'
        final = d / rel
        tmp = evid / f'.verify-{fid}.{os.getpid()}.out'
        hit = reuse.get((rules._norm_cell(cmd), rules._norm_cell(expected)))
        if hit is not None:
            try:
                data = hit[0]
                with open(final, 'wb') as fh:
                    fh.write(data)
                one_line = re.sub(r'[\r\n]+', ' ', cmd).strip()
                results.append({'n': str(n), 'cmd': cmd, 'expected': expected, 'exit': hit[1].get('exit', 0), 'ok': True,
                                'evidence': rel, 'sha1': hashlib.sha1(data).hexdigest(), 'reused': True})
                print(f'REUSED row {n}: {one_line[:100]} (passed earlier on the same code) → {rel}')
                continue
            except Exception:
                pass                                         # could not copy the evidence: run the row for real
        problem = rules.verification_command_problem(cmd, expected, root)
        if problem:
            code, note, body = -1, f'not run: {problem}', ''
        else:
            code, note = _run_row(cmd, root, tmp, timeout)
            try:
                body = tmp.read_bytes().decode('utf-8', errors='replace')
            except Exception:
                body = ''
        try:
            tmp.unlink()
        except Exception:
            pass
        one_line = re.sub(r'[\r\n]+', ' ', cmd).strip()
        text = f'# {one_line} | exit {code} | {datetime.now().isoformat(timespec="seconds")}\n'
        if note:
            text += f'[aidd verify] {note}\n'
        text += body.replace('\r\n', '\n')
        ok = (not problem) and code != -1 and _row_ok(code, body, expected)
        why = note
        if ok:
            bad_out = rules.verify_output_problem(text, expected)
            if bad_out:
                ok, why = False, bad_out
        sha1 = ''
        try:
            data = text.encode('utf-8')
            with open(final, 'wb') as fh:
                fh.write(data)
            sha1 = hashlib.sha1(data).hexdigest()
        except Exception as e:
            ok, why = False, f'evidence file not written ({type(e).__name__})'
        res = {'n': str(n), 'cmd': cmd, 'expected': expected, 'exit': code, 'ok': bool(ok), 'evidence': rel, 'sha1': sha1}
        if why and not ok:
            res['problem'] = why
        results.append(res)
        print(f"{'PASS' if ok else 'FAIL'} row {n}: {one_line[:100]} (exit {code})"
              + (f' - {why}' if why and not ok else '') + f' → {rel}')
    fp_end = ev.worktree_fingerprint(root)
    st_end = ev.code_state(root, scope=scope)
    # Files a command rewrote (a graph.json with a timestamp, a report): outputs, not code. Declared in `Generated:`
    # they are fine; undeclared they fail THIS run, but the file list is recorded so adding the `Generated:` line
    # later makes the gate accept the very same run (no re-execution, no edit of the generator).
    changed = ev.state_diff(st_start, st_end) if (st_start and st_end) else []
    unexplained = [c for c in changed if not rules._glob_hit(c, gen)]
    excl = list(gen) + changed
    code_start = ev.fingerprint_of(st_start, scope, exclude=excl) if st_start else None
    code_end = ev.fingerprint_of(st_end, scope, exclude=excl) if st_end else None
    stable = (not unexplained) if (st_start and st_end) else (fp_start == fp_end)       # docs may change meanwhile
    all_ok = all(x['ok'] for x in results) and stable
    # code_since: when this exact code state was first verified; lineage: the table hashes verified on it.
    same_code = bool(prior and prior_fp is not None and prior.get('code_fp_end') == prior_fp)
    code_since = (prior.get('code_since') or prior.get('started')) if same_code else started
    lineage = None
    if same_code:
        lineage = [x for x in (list(prior.get('verify_lineage') or []) + [prior.get('verify_hash')]) if x][-20:]
    recorded = ev.append_verify_run(root, sess, d.name, all_ok, vhash, results, started, fp_start, fp_end, stable,
                                    code_fp_start=code_start, code_fp_end=code_end,
                                    code_since=code_since, verify_lineage=lineage, code_scope=scope or None,
                                    code_changed=changed[:200] or None, code_generated=gen or None)
    if scope:
        print(f'scope: {", ".join(scope)} (edits outside it, e.g. other specs, do not invalidate this verification)')
    if changed and not unexplained:
        print(f'rewritten by the verification and declared Generated: {", ".join(changed[:6])}')
    if not stable and unexplained:
        print(f'FAIL the verification rewrote files: {", ".join(unexplained[:6])}'
              + (f' (+{len(unexplained) - 6} more)' if len(unexplained) > 6 else '') + '.')
        print(f'  They are outputs, not code. Add `Generated: {", ".join(unexplained[:6])}` (globs allowed) under '
              f'`## Verification` in {d.name}/spec.md and the gate accepts THIS run: do NOT re-run it and do NOT edit the generator.')
    elif not stable:
        print('FAIL the working tree changed while verification ran (a command wrote a file outside specs/); '
              're-run `aidd verify ' + d.name + '`.')
    if not recorded:
        print('FAIL the verify_run event could not be recorded (evidence log not writable); close stays refused.')
        return 1
    print(f"verify_run recorded for {d.name}: {'PASSED' if all_ok else 'FAILED'} "
          f"({sum(1 for x in results if x['ok'])}/{len(results)} rows, verify hash {vhash})")
    return 0 if all_ok else 1


def _tasks_hash(d):
    """approval_hash of the current tasks.md ('' when missing) - lets Status-only edits keep a spec closed."""
    if d is None or not (d / 'tasks.md').exists():
        return ''
    return rules.approval_hash(_read(d / 'tasks.md'))


def _fmt_violation(v):
    return f"{v.get('rule', 'R10')} {v.get('message', '')} → {v.get('fix', '')}"


def _close_gaps(d, root):
    """R6/R7 gaps that prevent a completed close (list of 'RULE message → fix' strings).
    aidd:FR-205 aidd:FR-206 A spec whose current `approved` event has `gate: 2` also needs a fresh passing
    verify_run (rules.verification_gaps), auditors newer than max(last code edit, verify_run) and, for a
    closing auditor, its qa-audit.md rows (rules.closing_audit_gaps). Legacy specs keep the old path."""
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
    gate = _gate_version(root, d, tasks_t) if tasks_t.strip() else 0
    if gate >= rules.GATE_VERSION:
        try:
            gaps += [_fmt_violation(v) for v in rules.verification_gaps(ev, root, d)]
        except Exception as e:      # fail closed
            gaps.append(f'R10 the verification check failed ({type(e).__name__}) → run `aidd verify {d.name}` again.')
        run = ev.latest_verify_run(root, d.name) or {}
        rscope = [str(x) for x in (run.get('code_scope') or [])]
        since = max((ev.last_code_edit_ts(root, rscope) if rscope else ev.last_code_edit_ts(root)),
                    float(run.get('code_since') or run.get('ts') or 0.0))
        h8 = rules.approval_hash(tasks_t)[:8] if tasks_t.strip() else '????????'
        v8 = (str(run.get('verify_hash') or '') or '????????')[:8]
        missing = sorted(rules.uncovered_domains(root, None, d.name, since, spec_dir=d))
        if missing:
            doms = ', '.join(sorted(rules.required_domains(d)))
            for dom in missing:
                gaps.append(f'R7 no distinct {dom} auditor subagent ran after the last code edit and the last '
                            f'verify_run → dispatch ONE closing auditor whose prompt starts '
                            f'`CLOSING AUDIT [domains: {doms}] [tasks:{h8}] [verify:{v8}]` (or one auditor per '
                            'domain), then rewrite qa-audit.md.')
        try:
            gaps += [_fmt_violation(v) for v in rules.closing_audit_gaps(ev, root, d)]
        except Exception as e:      # fail closed
            gaps.append(f'R10 the closing-audit check failed ({type(e).__name__}) → re-run the closing audit.')
        return gaps
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
    if ans is None:     # the click may have been recorded under another window's session: the tag binds it
        ans = ev.tagged_answer_any_session(root, sess, CLOSE_TOPIC, _mtime(d / 'qa-audit.md') or 0.0,
                                           label_re=CLOSE_LABEL, must_contain=f'[spec:{d.name}]')
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
        ans = ev.tagged_answer_any_session(root, sess, ABANDON_TOPIC, _abandon_since(root, spec_id, d, sess),
                                           label_re=ABANDON_LABEL, must_contain=f'[spec:{spec_id}]')
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
        if len(argv) == 3 and argv[0] == 'rules' and argv[1] in ('check', 'approve', 'close', 'activate'):
            return {'check': cmd_check, 'approve': cmd_approve, 'close': cmd_close,
                    'activate': cmd_activate}[argv[1]](argv[2])
        if len(argv) in (2, 3) and argv[0] == 'verify' and (len(argv) == 2 or argv[2] == '--full'):
            return cmd_verify(argv[1], full=len(argv) == 3)      # aidd:FR-205 `aidd verify <spec> [--full]`
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
