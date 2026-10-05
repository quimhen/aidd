#!/usr/bin/env python3
"""
PreToolUse hook (matcher: "Write|Edit|MultiEdit|NotebookEdit|Bash") — the single AIDD gate
(spec 002 "Hard Rules", Rev 1 amendments).

One process instead of four. For file-writing tools, in order:
  1. R9  the WHOLE `.aidd/` directory (evidence log, active_spec pointer, ...) is never writable by
         the agent, EXCEPT `.aidd/memory/**`
  2. the three legacy gates, in-process (require_aidd, require_independent_audit,
     require_graph_coherence_audit — fail-closed for specs/<id>/plan.md|tasks.md), fed the CANONICAL path
  1b. FR-204: `specs/<any-id>/review.md` and `review.html` are owner-only (USER_ONLY_SPEC_FILES), whatever the id
  3. code gate (R6/R4, FR-201): a write to any file except the non-code deny-list (D11) is BLOCKED while the GATE
     TARGET spec (aidd_evidence.gate_target_specs: the `.aidd/gate_spec` pointer, else the only open spec, else the
     open spec with the newest plan/tasks edit, else ambiguous) has a missing/invalid tasks approval or open visual
     debt. The gate reads `.aidd/gate_spec` and NEVER `.aidd/active_spec` (informational only, D1); both are R9-protected
  4. content rules (R1-R4 structure) on spec.md / tasks.md, evaluated on the WOULD-BE content (Write =>
     content; Edit/MultiEdit => edits applied to the file): only NEW violations block, except a
     whole-file Write of spec.md/tasks.md (any violation blocks); files > 2 MB are rejected unscanned (M-dos)
  5. by target: R5 chain (plan.md / tasks.md), R6 approval line (needs an AFFIRMATIVE user answer, M6),
     R7 per-domain distinct auditors (qa-audit.md, M9), R4 visual debt incl. the would-be plan.md /
     contracts.md / spec.md content (check_debt)

Every path decision uses aidd_evidence.canon_path / rel_to_root (B3): case, trailing dots/spaces,
`::$DATA`, `..`, 8.3 aliases and junctions all resolve to the same canonical file, so `PLAN.md`,
`plan.md.`, `plan.md::$DATA`, `sub/../plan.md`, `AIDD~1\\evidence\\events.toon` are the same targets.

For `tool_name == "Bash"` the hook first does a cheap substring pre-check (it imports nothing and returns
immediately unless the command text mentions `.aidd`, `events.toon`, `active_spec` or `evidence`). When it
does, a command that writes / deletes / moves / copies / redirects / truncates INTO a protected path
(`>`, `>>`, tee, rm/del/rmdir/Remove-Item, mv/move/ren, cp/copy/xcopy/robocopy, Set-Content/Out-File/
Add-Content, sed -i, perl -i, truncate, mklink/ln, find -delete, git clean/checkout/restore/rm, and
python/node/powershell code with write calls) is BLOCKED. Read-only commands (cat, ls, grep, type,
Get-Content, `aidd status`) and the `aidd` CLI itself (`aidd rules ...`, `aidd mem ...`) stay allowed.
RESIDUAL LIMIT (stated, not hidden): the Bash check is lexical. Obfuscation — shell variables or globs
that build the directory name, base64/eval, running a separate script file that does the write, changing
directory and using unrelated relative names — is NOT detected; Bash edits of CODE files remain ungated
(same documented limitation as before). R9 for Bash raises the bar; it is not a sandbox.
Rev 3: any command whose text contains AIDD_TESTING / AIDD_EVIDENCE_DIR / AIDD_SESSION_ID in ANY form is blocked, and
quoted bodies of `powershell -c "..."` / `node -e` are parsed one level deep - still purely lexical (a token
assembled from pieces that never appears whole, or a script file written elsewhere, is not seen). The approval
gate itself mints the `approved` event after verifying the tagged Approve answer ([tasks:<hash8>]).

Environment (owner-only escape hatch, set by the human in settings.json `env`):
  AIDD_RULES=off|0|false|no  do nothing        AIDD_RULES=warn  print what would block, never block
  anything else (trimmed, case-insensitive) enforces.

Fail-open on crashes: ANY internal exception exits 0 and records a `hook_error` event (when a project
root is known). A block is exit 2 with a stderr message that names the exact next action.
"""
import json
import os
import sys

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(os.path.dirname(HOOKS_DIR), 'scripts')

# aidd:FR-204 review.md / review.html are markers too: `echo x > review.md` run with cwd = specs/<id>/ names no other one
BASH_MARKERS = ('.aidd', 'events.toon', 'active_spec', 'evidence', 'aidd_', 'specs', 'tasks.md', 'aidd-hooks',
                'review.md', 'review.html')
SHELL_TOOLS = ('Bash', 'PowerShell')
# aidd:FR-313 same negative lookahead as aidd_status.APPROVE_LABEL: a label starting `aprobar con resum...` never
# matches the generic tagged-answer route (only the exact label, through `_summary_answer`, mints source=summary)
APPROVE_LABEL = r'^(approve|aprobar|aprobado)\b(?!\s+con\s+resum)'
APPROVAL_TOPIC = r'approv|aprob'
# files under specs/X/ that stay writable while visual debt is open (they are how debt is resolved)
DEBT_EXEMPT = {'spec.md', 'mockup-audit.md'}
MAX_LISTED = 6

R9_MESSAGE = ('aidd R9: the `.aidd/` directory (evidence log, active_spec, ...) is written by hooks only; the agent '
              'may not write it (only `.aidd/memory/**` is writable).\nNext action: do not edit these files. If the '
              'evidence log is wrong, ask the user; they can reset it themselves (owner-only: AIDD_RULES=warn|off in '
              'settings.json env).')
R9_BASH_MESSAGE = ('aidd R9 (Bash/PowerShell): this command writes, deletes, moves, copies or redirects into the '
                   'protected `.aidd/` directory (evidence log / active_spec), the per-session evidence logs or '
                   'specs/, imports the aidd evidence libraries, sets AIDD_* control variables or forges the tasks '
                   'approval; only `.aidd/memory/**` and the `aidd` CLI may change these.\nNext action: do not touch these files from the shell either. Read-only commands '
                   '(cat, ls, grep, type, Get-Content, `aidd status`) are fine. If the evidence log is wrong, ask '
                   'the user. Note: this Bash check is lexical - obfuscated forms (variables, globs, base64, a '
                   'separate script) are NOT detected, and Bash edits of code files are not gated; do not rely on '
                   'that. (Owner-only override: AIDD_RULES=warn|off in settings.json env.)')
# aidd:FR-204 aidd:AC-207
REVIEW_MESSAGE = ('aidd R6 (review): `specs/<id>/review.html` is generated only by `aidd review <spec_dir>` and '
                  '`specs/<id>/review.md` is the OWNER\'s answer (the page saves it itself); the agent may not write, '
                  'copy, move or delete either of them.\nNext action: run `aidd review specs/<id>` to (re)generate the '
                  'page, then `aidd review specs/<id> --wait` in the background (the owner presses `Aprobar y guardar` '
                  'on the page); when it returns, ask the owner ONE question with the tag `[tasks:<hash8>]` and run '
                  '`aidd rules approve specs/<id>`. Agents never read review.md/review.html: they only run '
                  '`aidd review <spec> --check`, `--wait` or `--comments`. '
                  '(Owner-only override: AIDD_RULES=warn|off in settings.json env.)')


# ----------------------------------------------------------------------------- utils

def _emit(msg):
    try:
        sys.stderr.buffer.write((msg.rstrip() + '\n').encode('utf-8', 'replace'))
        sys.stderr.flush()
    except Exception:
        pass


def _mode():
    v = os.environ.get('AIDD_RULES', '').strip().lower()
    if v in ('off', '0', 'false', 'no'):
        return 'off'
    return 'warn' if v == 'warn' else 'enforce'


def _libs():
    if SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, SCRIPTS_DIR)
    import aidd_evidence as ev
    import aidd_rules as rules
    return ev, rules


def _ev():
    if SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, SCRIPTS_DIR)
    import aidd_evidence as ev
    return ev


def _read(p, limit=None):
    """Text of a file, None if unreadable. Files bigger than `limit` bytes are not loaded ('' returned)."""
    try:
        if limit is not None and os.path.getsize(p) > limit:
            return ''
        with open(p, 'r', encoding='utf-8', errors='replace', newline=None) as fh:
            return fh.read()
    except OSError:
        return None


def _mtime(p):
    try:
        return os.stat(p).st_mtime
    except OSError:
        return None


def _fmt(rule, header, viols):
    lines = [f'aidd {rule}: {header}']
    for v in viols[:MAX_LISTED]:
        lines.append(f"  - [{v['rule']}] {v['message']}\n    Next action: {v['fix']}")
    if len(viols) > MAX_LISTED:
        lines.append(f'  ... and {len(viols) - MAX_LISTED} more.')
    lines.append('(Owner override: AIDD_RULES=warn|off)')
    return '\n'.join(lines)


def _v(rule, message, fix):
    return {'rule': rule, 'message': message, 'fix': fix}


# ------------------------------------------------------------------ would-be content

def _would_be(ti, path, max_chars):
    """(new_text, is_whole_file_write, current_text|None, too_big). new_text None => cannot compute."""
    edits = ti.get('edits') if isinstance(ti.get('edits'), list) else None
    if 'content' in ti and 'old_string' not in ti and edits is None:
        c = ti.get('content')
        c = c if isinstance(c, str) else ('' if c is None else str(c))
        if len(c) > max_chars:
            return None, True, None, True
        return c, True, _read(path, max_chars * 2), False
    try:
        if os.path.getsize(path) > max_chars:
            return None, False, None, True
    except OSError:
        pass
    cur = _read(path)
    text = cur
    for e in (edits if edits is not None else [ti]):
        if not isinstance(e, dict) or 'old_string' not in e:
            return None, False, cur, False
        old, new = e.get('old_string'), e.get('new_string')
        old = old if isinstance(old, str) else ''
        new = new if isinstance(new, str) else ''
        if text is None:
            if old == '':
                text = new
                continue
            return None, False, cur, False
        if old == '':
            return None, False, cur, False
        if old not in text:
            return None, False, cur, False  # the Edit itself will fail; nothing to judge
        text = text.replace(old, new) if e.get('replace_all') else text.replace(old, new, 1)
        if len(text) > max_chars:
            return None, False, cur, True
    return text, False, cur, False


def _approved_lines(text):
    """Stripped `Approved:` lines — per line, linear (M-dos: no multiline regex over blank runs)."""
    import re
    rx = re.compile(r'approved\s*:', re.I)
    return [ln.strip() for ln in text.replace('\r\n', '\n').replace('\r', '\n').split('\n') if rx.match(ln.lstrip())]


# ---------------------------------------------------------------------------- rules

def _find_spec_state(ev, root, session):
    """'none' (no find_spec event) | 'bad' (events, all with ok=false) | 'ok'; plus the OK events."""
    evs = ev.events(root, session, 'find_spec')
    oks = [e for e in evs if (e.get('detail') or {}).get('ok') is not False]
    return ('ok' if oks else ('bad' if evs else 'none')), oks


FIND_SPEC_FIX = ('Run `python <aidd skill>/scripts/find_spec.py <spec keywords>` through the Bash tool. It is recorded '
                 'only when the command actually RUNS find_spec.py (`echo find_spec.py`, grep or cat do not count; the '
                 'UserPromptSubmit hook\'s own run does), then retry.')


def _r5_plan(ev, rules, d, root, session):
    spec_t = _read(d / 'spec.md', rules.MAX_CHARS * 2) or ''
    static = [v for v in rules.check_spec_dir(d, static_only=True) if v['rule'] in ('R2', 'R3', 'R4')]
    evid = rules._evidence_rules(ev, d, root, session, spec_t, False, d / 'plan.md', d / 'tasks.md',
                                 d / '.no-qa-audit')
    state, _ = _find_spec_state(ev, root, session)
    seen, out = set(), []
    for v in static + evid:
        if v['rule'] == 'R5' and v['message'].startswith('No find_spec run'):
            v = dict(v, fix=FIND_SPEC_FIX)
        k = (v['rule'], v['message'])
        if k not in seen:
            seen.add(k)
            out.append(v)
    if state == 'bad':
        out.append(_v('R5', 'find_spec ran in this session but its output was not a valid find_spec result '
                            '(error / empty).', FIND_SPEC_FIX))
    return out


def _counting_subs(ev, root, session):
    """R14: only subagent events that count as independent (not low-tier) feed R5."""
    _, rules = _libs()
    return [e for e in ev.events(root, session, 'subagent') if rules._subagent_counts(e)]


def _r5_mode(rules):
    """aidd:FR-206 'advisory' (default) | 'strict'. An older aidd_rules without r5_audit_mode keeps the old
    (strict) behaviour; a crash of the reader is treated the same way (fail closed on the demand)."""
    f = getattr(rules, 'r5_audit_mode', None)
    try:
        return f() if callable(f) else 'strict'
    except Exception:
        return 'strict'


def _r5_tasks(ev, d, root, session):
    """R5 before tasks.md: plan.md exists, find_spec ran and (strict only, FR-206) a pre-build audit ran."""
    out = []
    plan = d / 'plan.md'
    if _mtime(plan) is None:
        out.append(_v('R5', 'plan.md does not exist.', f'Write specs/{d.name}/plan.md (Step 3) before tasks.md.'))
    else:
        _, rules = _libs()
        if _r5_mode(rules) == 'strict' and not rules.pre_build_audit_done(ev, root, session, d):
            out.append(_v('R5', 'No pre-build coherence audit: no independent subagent ran after the last edit '
                                'of spec.md/plan.md/tasks.md (or the last graph rebuild).',
                          'Dispatch ONE pre-build coherence auditor subagent (medium or high tier, never haiku) '
                          'over spec.md, plan.md, tasks.md, the graph and the estimates, then retry.'))
    state, _oks = _find_spec_state(ev, root, session)
    if state == 'none':
        out.append(_v('R5', 'No find_spec run recorded in this session.', FIND_SPEC_FIX))
    elif state == 'bad':
        out.append(_v('R5', 'find_spec ran in this session but its output was not a valid find_spec result '
                            '(error / empty).', FIND_SPEC_FIX))
    return out


def _tasks_last_change(ev, root, d, spec_dir_name):
    """Last content change of tasks.md: the later of its mtime and the newest recorded tasks.md edit."""
    t = _mtime(d / 'tasks.md') or 0.0
    try:
        for e in ev.events(root, None, 'spec_edit'):
            dd = e.get('detail') or {}
            if str(dd.get('spec', '')).lower() == spec_dir_name.lower() and str(dd.get('file', '')).lower() == 'tasks.md':
                t = max(t, e['ts'])
    except Exception:
        pass
    return t


def _affirm(ev, root, session, since, tag):
    """The newest affirmative Approve answer whose QUESTION carries `tag` (N4: [tasks:<hash8>]), else None."""
    try:
        e = ev.affirmative_answer(root, session, APPROVAL_TOPIC, since_ts=since, label_re=APPROVE_LABEL,
                                  must_contain=tag)
    except TypeError:       # older library without must_contain: verified below
        try:
            e = ev.affirmative_answer(root, session, APPROVAL_TOPIC, since_ts=since, label_re=APPROVE_LABEL)
        except TypeError:
            e = ev.affirmative_answer(root, session, APPROVAL_TOPIC, since_ts=since)
    if not e:
        return None
    pairs = (e.get('detail') or {}).get('pairs') or []
    qs = [str(p[0]) for p in pairs if isinstance(p, (list, tuple)) and p]
    return e if any(tag.lower() in q.lower() for q in qs) else None


def _approval_gate(ev, rules, d, root, session, new_text, cur_text):
    """R6 / D3: a well-formed `Approved:` line edit must (a) change nothing else
    (approval_hash(current) == approval_hash(would-be)), (b) carry exactly that hash, and (c) follow an
    AFFIRMATIVE user answer (pairs anchored on a recorded question that OFFERED an Approve option) newer
    than the last change of tasks.md.
    aidd:FR-204 (spec 007): also (d) a valid `## Verification` (rules.check_verification) and (e) when a review
    page exists, a COMPLETE review_state AND a consent act newer than review.md (tagged answer or tagged prompt;
    never a TTY, never review.md alone). Mints `approved` with rules.approval_evidence (gate 2)."""
    new_lines = _approved_lines(new_text)
    cur_lines = _approved_lines(cur_text or '')
    line = rules.approval_line(new_text)
    if new_lines == cur_lines or line is None:
        return []  # approval line untouched, or a placeholder such as `Approved: PENDING`
    if cur_text is None or _mtime(d / 'tasks.md') is None:
        return [_v('R6', 'An Approved: line cannot be written together with a brand-new tasks.md.',
                   'Write tasks.md with "Approved: PENDING", present it to the user (AskUserQuestion: approve '
                   'the tasks? with an "Approve" option), then add the approval line by editing tasks.md.')]
    h_new = rules.approval_hash(new_text)
    if rules.approval_hash(cur_text) != h_new:
        return [_v('R6', 'This edit changes tasks.md content AND the Approved: line. An approval edit must change '
                         'nothing else (the hash of the current file and of the result differ).',
                   'First edit the tasks (without an Approved: line), present the result to the user, and only '
                   'then make a SEPARATE edit that only adds the "Approved: <date> hash:<hash>" line.')]
    if line[1].lower() != h_new:
        return [_v('R6', f'The written approval hash {line[1]} is not the hash of tasks.md ({h_new}).',
                   f'Write "Approved: <date> hash:{h_new}" exactly (or run `aidd rules approve <spec_dir>`).')]
    since = _tasks_last_change(ev, root, d, d.name)
    tag = f'[tasks:{h_new[:8]}]'
    # aidd:FR-204 aidd:FR-205 a new approval needs a valid `## Verification` in spec.md (legacy approvals are untouched)
    spec_t = _read(d / 'spec.md', rules.MAX_CHARS * 2) or ''
    vv = rules.check_verification(spec_t, root)
    if vv:
        return vv
    try:
        rs = _review_lib().review_state(d)
    except Exception as e:      # fail closed: without the review reader the review state is unknown
        return [_v('R6', f'The review state of specs/{d.name} cannot be read ({type(e).__name__}: aidd_review.py '
                         'missing or broken next to the hook).',
                   'Reinstall the aidd skill (hooks and scripts together), then retry.')]
    if not isinstance(rs, dict):
        rs = {}
    if not str(rs.get('reason') or '').startswith('too many items'):
        # aidd:FR-313 the owner's exact-label waiver of the review page: checked FIRST (before the complete branch
        # and so before _review_page_blocks_answer), only through the hook-recorded answer; the gate mints the event
        summary = _summary_answer(ev, root, session, since, tag)
        if summary:
            ev.append_approved(root, session, d.name, h_new,
                               **rules.approval_evidence(spec_t, 'summary', consent_ts=summary.get('ts')))
            return []
    if rs.get('complete'):
        # aidd:FR-204 aidd:AC-205 review = content, consent = trust root: review.md alone is NEVER enough
        lo = max(since, _num(rs.get('mtime')))
        kind, cts = None, None
        ans = _affirm(ev, root, session, lo, tag)
        if ans:
            kind, cts = 'answer', ans.get('ts')
        else:
            pc = _prompt_consent(ev, root, session, tag, lo)
            if pc:
                kind, cts = 'prompt', pc.get('ts')
        if kind:
            # N1: PreToolUse is the trusted point - the gate itself mints the `approved` event (mark_code_edit does not)
            ev.append_approved(root, session, d.name, h_new,
                               **rules.approval_evidence(spec_t, f'review+{kind}', review_sha1=rs.get('sha1') or None,
                                                         consent_ts=cts))
            return []
        return [_v('R6', f'review.md is complete; the owner must confirm: answer the question tagged {tag} or type '
                         f'`approve {tag}` (a consent act newer than review.md, recorded in this session, is required; '
                         'review.md alone is never an approval).',
                   f'Run `aidd review specs/{d.name} --wait` in the background; when it returns, ask the owner ONE '
                   f'question with AskUserQuestion: the question text MUST include the tag {tag} and offer an '
                   f'option labelled "Approve" (typing `approve {tag}` stays a fallback). Then add the '
                   '"Approved: <date> hash:<hash>" line (or run `aidd rules approve <spec_dir>`).')]
    if _review_page_blocks_answer(d, rs):
        # aidd:FR-204 a review page exists for this spec: the plain answer route is refused until it is completed
        why = str(rs.get('reason') or 'the review is not complete')
        return [_v('R6', f'A review exists for specs/{d.name} (review.html): complete it. {why}.',
                   f'Run `aidd review specs/{d.name}` if the page is stale (or a legacy review.md needs regenerating), '
                   f'then `aidd review specs/{d.name} --wait` in the background: the owner checks the sections and '
                   'presses `Aprobar y guardar`, the page saves review.md itself; when it returns, ask ONE question '
                   f'tagged {tag} (with an "Approve" option) or the owner types `approve {tag}`.')]
    ans = _affirm(ev, root, session, since, tag)
    if ans:
        # aidd:FR-204 no review page (never generated, or sources over the cap): the answer-only route
        ev.append_approved(root, session, d.name, h_new,
                           **rules.approval_evidence(spec_t, 'answer', consent_ts=ans.get('ts')))
        return []
    return [_v('R6', 'Approval of tasks.md is the user\'s: there is no AFFIRMATIVE user answer to an '
                     f'"approve the tasks" question carrying the tag {tag} (with an Approve option) recorded in this '
                     'session after tasks.md was last changed (asking is not enough; a "No"/other answer, an '
                     'untagged question or a question about other content does not count).',
               f'Present the tasks to the user with AskUserQuestion: the question text MUST include the tag {tag} '
               '(it identifies exactly this version of tasks.md) and it MUST offer an option labelled "Approve". '
               'Wait for their answer, then add the "Approved: <date> hash:<hash>" line (or run '
               f'`aidd rules approve <spec_dir>`). Preferred: `aidd review specs/{d.name}` builds the review page '
               f'the owner checks and answers (then consent: the tagged answer or `approve {tag}`).')]


def _summary_answer(ev, root, session, since, tag):
    """aidd:FR-313 Thin delegate to aidd_status._summary_answer (the one definition of the exact-label route).
    ANY import or call error returns None (fail closed: no summary route, the other routes decide)."""
    try:
        if SCRIPTS_DIR not in sys.path:
            sys.path.insert(0, SCRIPTS_DIR)
        import aidd_status
        return aidd_status._summary_answer(ev, root, session, since, tag)
    except Exception:
        return None


def _review_lib():
    if SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, SCRIPTS_DIR)
    import aidd_review
    return aidd_review


def _num(x):
    try:
        return float(x or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _prompt_consent(ev, root, session, tag, since):
    """aidd:FR-204 consent (b): a hook-recorded user prompt carrying the tag and an approve word. None on error."""
    try:
        return _review_lib().prompt_consent(ev, root, session, tag, since)
    except Exception:
        return None


def _review_page_blocks_answer(d, rs):
    """aidd:FR-204 True when a review page exists (current OR stale: a hash/digest mismatch voids the review and
    asks for `aidd review` again) and the sources are within the cap. The answer-only route stays only when no
    page was ever generated or the sources are over MAX_REVIEW_SOURCE_CHARS (AC-217).
    aidd:FR-307 A spec the compact page cannot show (`too many items`) always blocks, with or without a page."""
    if str(rs.get('reason') or '').startswith('too many items'):
        return True
    if rs.get('page_current'):
        return True
    if str(rs.get('reason') or '').startswith('source too large'):
        return False
    try:
        return (d / 'review.html').is_file()
    except OSError:
        return True


def _qa_gate(ev, rules, d, root, session):
    edits = ev.events(root, session, 'code_edit')   # D1: no spec attribution - any code edit counts
    if not edits:
        return []  # baseline qa-audit.md, nothing implemented yet (same as the legacy gate)
    since = rules.audit_since(edits)
    out = []
    doms = sorted(rules.uncovered_domains(root, session, d.name, since, spec_dir=d))
    try:
        reasons = rules._uncovered_reasons(ev, root, session, doms, since) if doms else {}
    except Exception:
        reasons = {}
    for dom in doms:
        tier = reasons.get(dom) == 'tier'
        note = ' (model tier too low, R14: a haiku auditor does not count)' if tier else ''
        model = ' with a medium or high model (model: sonnet or opus)' if tier else ''
        out.append(_v('R7', f'No distinct {dom} auditor subagent ran after the last code edit of {d.name} '
                            f'(one subagent covers ONE domain){note}.',
                      f'Dispatch an independent {dom} auditor subagent (Agent tool){model} whose description or '
                      f'prompt names "{dom}", then write qa-audit.md from ITS findings.'))
    return out


def _debt_violations(rules, root, spec_id):
    vs = []
    low = spec_id.lower()
    for sid, rows in rules.open_debt_blocking(root).items():
        if sid.lower() != low:
            continue
        for row in rows:
            codes = ', '.join(sorted(row['codes'])) or '?'
            vs.append(_v('R4', f'Open visual debt for {codes} (listed in specs/{row.get("in_spec", spec_id)}/spec.md) '
                               f'blocks spec {spec_id}.',
                         'Ask the user (AskUserQuestion) for the mockup source, run Steps 0/1/1.5 for these codes '
                         f'(write specs/{spec_id}/mockup-audit.md), then set the Visual debt row Status to resolved '
                         'with its Mockup source.'))
    return vs


def _approved_recorded(ev, root, sid, h):
    try:
        for e in ev.events(root, None, 'approved'):
            dd = e.get('detail') or {}
            if str(dd.get('spec', '')).lower() == sid.lower() and str(dd.get('hash', '')).lower() == h.lower():
                return True
    except Exception:
        pass
    return False


MAX_AMBIGUOUS_IDS = 5
_HOW_TEXT = {'pointer': 'the gate pointer .aidd/gate_spec names it',
             'only': 'it is the only open spec',
             'inferred': 'it has the newest plan.md/tasks.md edit of the open specs (no gate pointer set)',
             'all': 'every open spec is checked (older aidd_evidence without gate_target_specs)'}


def _gate_targets(ev, root):
    """aidd:FR-201 (ids, ambiguous, how) for one root. Falls back to EVERY open spec (the pre-007 behaviour,
    how='all') when the library predates gate_target_specs or returns an unexpected shape."""
    try:
        ids, ambiguous, how = ev.gate_target_specs(root)
        return list(ids or []), bool(ambiguous), str(how or '')
    except (AttributeError, TypeError, ValueError):
        pass
    try:
        return list(ev.open_specs(root)), False, 'all'
    except Exception:
        return [], False, 'none'


def _ambiguous_violation(ev, root):
    """aidd:FR-201 aidd:AC-202 ONE violation listing the open ids (first 5, then 'and N more')."""
    try:
        opened = list(ev.open_specs(root))
    except Exception:
        opened = []
    shown = ', '.join(opened[:MAX_AMBIGUOUS_IDS]) or '?'
    more = len(opened) - MAX_AMBIGUOUS_IDS
    if more > 0:
        shown += f' and {more} more'
    first = opened[0] if opened else '<id>'
    return _v('R6', f'Code edits are blocked: {len(opened)} specs are open ({shown}), no gate pointer is set and '
                    'none can be inferred (no open spec has a recorded plan.md/tasks.md edit), so the gate target '
                    'is ambiguous.',
              f'Choose the spec this work belongs to: run `aidd rules activate <id>` (for example '
              f'`aidd rules activate {first}`); `aidd rules approve <id>` also activates the spec it approves. '
              'If a spec was dropped, ask the user and run `aidd rules abandon <id>`.')


def _target_violation(ev, rules, root, sid, how):
    """aidd:FR-201 at most ONE R6 violation for the gate target `sid`, naming it, `how` and the unblock path."""
    d = root / 'specs' / sid
    tasks = _read(d / 'tasks.md', rules.MAX_CHARS * 2)
    why = _HOW_TEXT.get(how, how or 'gate target')
    unblock = (f'Unblock: `aidd review specs/{sid}`, then `aidd review specs/{sid} --wait` in the background (the '
               f'owner presses `Aprobar y guardar` on the page, which saves review.md); ask ONE tagged question, then '
               f'`aidd rules approve specs/{sid}` with the owner\'s consent; or, if this work belongs to another '
               'spec, `aidd rules activate <other>`. If the spec is finished or dropped, ask the user and run '
               f'`aidd rules close {sid}` / `aidd rules abandon {sid}`.')
    head = f'Code edits are blocked: gate target spec {sid} (chosen by {how}: {why})'
    if tasks is None:
        return _v('R6', f'{head} has no tasks.md. Step 4 missing: write tasks.md, then get approval.',
                  f'Write specs/{sid}/tasks.md (Step 4: small-PR tasks with Agent min / Human ref hours), then get '
                  f'it approved. {unblock}')
    if not rules.approval_valid(tasks):
        return _v('R6', f'{head} has no valid tasks approval (missing, duplicated, or tasks.md changed after it was '
                        'approved).',
                  'Present the tasks to the owner (review page, or AskUserQuestion with an "Approve" option), wait '
                  f'for their consent, then add/refresh the "Approved: <date> hash:<hash>" line in '
                  f'specs/{sid}/tasks.md. {unblock}')
    if not _approved_recorded(ev, root, sid, rules.approval_hash(tasks)):
        return _v('R6', f'{head}: the approval line in specs/{sid}/tasks.md was not recorded by a hook (no approved '
                        'event for the current hash) - it was probably written outside Write/Edit.',
                  f'Get the owner\'s consent again, then write the Approved: line with the Edit tool. {unblock}')
    return None


def _code_gate(ev, rules, roots):
    """aidd:FR-201 R6/R4 per spec: in every project root above the file ONLY the gate target spec(s)
    (ev.gate_target_specs: `.aidd/gate_spec` pointer -> only open spec -> newest plan/tasks edit -> ambiguous)
    are checked for a missing tasks.md, an invalid approval, no hook-recorded approval for the CURRENT hash, or
    open visual debt. Ambiguous -> ONE violation listing the open ids and `aidd rules activate <id>`. The gate reads
    `.aidd/gate_spec` and NEVER the informational `.aidd/active_spec` (D1); both are R9-protected."""
    out, seen = [], set()
    for root in roots:
        ids, ambiguous, how = _gate_targets(ev, root)
        if ambiguous:
            key = (str(root), '<ambiguous>')
            if key not in seen:
                seen.add(key)
                out.append(_ambiguous_violation(ev, root))
            continue
        for sid in ids:
            key = (str(root), str(sid).lower())
            if key in seen:
                continue
            seen.add(key)
            v = _target_violation(ev, rules, root, sid, how)
            if v:
                out.append(v)
            out += _debt_violations(rules, root, sid)
    return out


# ----------------------------------------------------------------- file-tool targets

def _protected(ev, cp, segs):
    for i, s in enumerate(segs):
        if s == '.aidd':
            nxt = segs[i + 1] if i + 1 < len(segs) else None
            if nxt == 'memory':
                continue
            return True
    envd = os.environ.get('AIDD_EVIDENCE_DIR')
    if envd and os.environ.get('AIDD_TESTING') == '1':
        cd = ev.canon_path(envd)
        if cp == cd or cp.startswith(cd.rstrip('/') + '/'):
            return True
    return _session_log(ev, cp) or _transcript_path(cp)


def _transcript_path(p):
    """R9: host transcript files (.claude/projects/<proj>/<session>.jsonl) are not agent-writable."""
    import re
    return bool(re.search(r'(^|/)\.claude/projects/[^/]+/[^/]+\.jsonl(:[^/:]*)*$',
                          str(p).replace('\\', '/').lower().rstrip('. ')))


def _session_log(ev, cp):
    """R9 (D5): the per-session log directory (<tempdir>/aidd-hooks/) is not agent-writable."""
    f = getattr(ev, 'is_session_log_path', None)
    try:
        if callable(f):
            return bool(f(cp))
        import tempfile
        base = ev.canon_path(os.path.join(tempfile.gettempdir(), 'aidd-hooks')).rstrip('/')
        return cp == base or cp.startswith(base + '/')
    except Exception:
        return False


def _spec_target(ev, rp, cp, roots):
    """(root, native_spec_id, native_rest_parts, canon_rest_parts) for specs/<id>/<...>, else None."""
    from pathlib import Path
    for root in roots:
        rel = ev.rel_to_root(cp, root)
        if rel:
            cparts = rel.split('/')
            if len(cparts) >= 3 and cparts[0] == 'specs':
                try:
                    nparts = Path(rp).relative_to(ev.real_path(root)).parts
                except ValueError:
                    nparts = tuple(cparts)
                if len(nparts) == len(cparts):
                    return root, nparts[1], list(nparts[2:]), cparts[2:]
    if not roots:   # fresh project: specs/ does not exist yet
        cparts = cp.split('/')
        for i in range(len(cparts) - 3, -1, -1):
            if cparts[i] == 'specs':
                np_ = Path(rp).parts
                if len(np_) == len(cparts):
                    return Path(*np_[:i]) if i else Path(Path(rp).anchor), np_[i + 1], list(np_[i + 2:]), cparts[i + 2:]
                break
    return None


def _decide_path(event, ti, fp):
    import _common as C
    ev = _ev()
    cwd = C.str_field(event, 'cwd') or None
    rp = ev.real_path(fp, cwd)
    cp = ev.canon_path(fp, cwd)
    segs = cp.split('/')
    name = segs[-1]

    # (1) R9
    if _protected(ev, cp, segs):
        return True, R9_MESSAGE

    # (1b) aidd:FR-204 aidd:AC-207 owner-only review artifacts, any spec id, after canonicalisation
    if C.is_user_only_spec_file(cp):
        return True, REVIEW_MESSAGE

    # (2) legacy gates, in-process, on the canonical path
    import require_aidd
    import require_independent_audit
    import require_graph_coherence_audit
    sid_str = C.session_of(event)
    lev = dict(event, session_id=sid_str, tool_input=dict(ti, file_path=cp))
    for mod in (require_aidd, require_independent_audit, require_graph_coherence_audit):
        blocked, msg = mod.evaluate(lev)
        if blocked:
            return True, msg

    roots = ev.project_roots(rp)
    outer_rel = ev.rel_to_root(cp, roots[-1]) if roots else None
    st = _spec_target(ev, rp, cp, roots)
    gated = C.is_r6_gated(cp, outer_rel)
    if st is None and not gated and name not in C.SPEC_ARTIFACT_NAMES:
        return False, ''

    ev, rules = _libs()

    # (3) code gate
    if gated and roots:
        vs = _code_gate(ev, rules, roots)
        if vs:
            return True, _fmt('R6/R4', f'blocking this edit of {name}.', vs)

    if st is None:
        return False, ''

    root, spec_id, rest, crest = st
    d = root / 'specs' / spec_id
    fname = crest[-1] if len(crest) == 1 else None
    session = sid_str

    # R4: writes under specs/X/ while X has open debt
    if not (fname in DEBT_EXEMPT):
        vs = _debt_violations(rules, root, spec_id)
        if vs:
            return True, _fmt('R4', f'blocking this write under specs/{spec_id}/.', vs)

    if fname is None or fname not in C.SPEC_ARTIFACT_NAMES:
        return False, ''

    # (4) content rules on spec.md / tasks.md (+ R4 on the would-be spec/plan/contracts)
    new_text = cur_text = None
    if fname in ('spec.md', 'tasks.md', 'plan.md', 'contracts.md', 'qa-audit.md'):
        new_text, whole, cur_text, too_big = _would_be(ti, rp, rules.MAX_CHARS)
        if too_big and fname == 'qa-audit.md':
            return True, _fmt('content', 'blocking this write to qa-audit.md: file too large.',
                              [_v('R10', 'qa-audit.md would exceed 2 MB, so it cannot be scanned.',
                                  'Shrink qa-audit.md below 2 MB.')])
        if new_text is not None and fname == 'qa-audit.md':
            # R10/R11 (contract 10): independent of _qa_gate's no-code_edit early return; only freshness needs edits
            edits = ev.events(root, session, 'code_edit')   # session-scoped, no spec attribution
            last_ts = max([e['ts'] for e in edits]) if edits else None
            vs = rules.check_qa(new_text, d, root, last_ts)
            if vs and not whole:
                before = {(v['rule'], v['message']) for v in rules.check_qa(cur_text or '', d, root, last_ts)}
                vs = [v for v in vs if (v['rule'], v['message']) not in before]
            if vs:
                return True, _fmt('content', f'blocking this write to qa-audit.md: it introduces '
                                             f'{"" if whole else "new "}violations.', vs)
        if too_big and fname in ('spec.md', 'tasks.md'):
            return True, _fmt('content', f'blocking this write to {fname}: file too large.',
                              [_v('R1' if fname == 'tasks.md' else 'R2',
                                  f'{fname} would exceed 2 MB, so it cannot be scanned.',
                                  f'Shrink {fname} (remove blank lines / pasted blobs) below 2 MB.')])
        if new_text is not None and fname in ('spec.md', 'tasks.md'):
            kind = 'spec' if fname == 'spec.md' else 'tasks'
            vs = rules.check_content(kind, new_text)
            if vs and not whole:
                before = {(v['rule'], v['message']) for v in rules.check_content(kind, cur_text or '')}
                vs = [v for v in vs if (v['rule'], v['message']) not in before]
            if vs:
                return True, _fmt('content', f'blocking this write to {fname}: it introduces '
                                             f'{"" if whole else "new "}violations.', vs)
        if new_text is not None and fname in ('spec.md', 'plan.md', 'contracts.md'):
            after = rules.check_debt(root, spec_id, {fname: new_text})
            before = {(v['rule'], v['message']) for v in rules.check_debt(root, spec_id)}
            vs = [v for v in after if (v['rule'], v['message']) not in before]
            if vs:
                return True, _fmt('R4', f'blocking this write to {fname}: visual debt is not handled.', vs)
        if too_big and fname in ('plan.md', 'contracts.md'):
            return True, _fmt('R4', f'blocking this write to {fname}: file too large.',
                              [_v('R4', f'{fname} would exceed 2 MB, so it cannot be scanned.',
                                  f'Shrink {fname} below 2 MB.')])

    # (5) chain / approval / audit by target
    if fname == 'plan.md':
        vs = _r5_plan(ev, rules, d, root, session)
        if vs:
            return True, _fmt('R5', 'blocking plan.md: the chain order is not satisfied.', vs)
    elif fname == 'tasks.md':
        vs = _r5_tasks(ev, d, root, session)
        if vs:
            return True, _fmt('R5', 'blocking tasks.md: the chain order is not satisfied.', vs)
        if new_text is not None:
            vs = _approval_gate(ev, rules, d, root, session, new_text, cur_text)
            if vs:
                return True, _fmt('R6', 'blocking this edit of the tasks approval.', vs)
    elif fname == 'qa-audit.md':
        vs = _qa_gate(ev, rules, d, root, session)
        if vs:
            return True, _fmt('R7', 'blocking qa-audit.md: not every required domain was audited.', vs)
    return False, ''


def _paths(ti):
    out = []
    for k in ('file_path', 'notebook_path'):
        v = ti.get(k)
        if isinstance(v, str) and v.strip():
            out.append(v)
    edits = ti.get('edits')
    if isinstance(edits, list):
        for e in edits:
            if isinstance(e, dict):
                for k in ('file_path', 'notebook_path'):
                    v = e.get(k)
                    if isinstance(v, str) and v.strip() and v not in out:
                        out.append(v)
    return out


# --------------------------------------------------------------------------- Bash (R9)

_DELETERS = {'rm', 'del', 'erase', 'rmdir', 'rd', 'remove-item', 'ri', 'unlink', 'shred', 'srm', 'truncate'}
_MOVERS = {'mv', 'move', 'ren', 'rename', 'move-item', 'mi', 'rename-item', 'rni'}
_WRITERS = {'tee', 'tee-object', 'export-csv', 'export-clixml', 'touch', 'ni', 'new-item', 'set-content', 'sc', 'out-file', 'add-content', 'ac',
            'clear-content', 'clc', 'set-item', 'mkdir', 'md', 'ln', 'mklink', 'dd', 'patch', 'ed'}
_COPIERS = {'cp', 'copy', 'xcopy', 'robocopy', 'copy-item', 'cpi', 'rsync', 'install', 'scp'}
_SHELLS = {'bash', 'sh', 'zsh', 'dash', 'cmd', 'powershell', 'pwsh', 'wsl', 'busybox'}
_INTERPRETERS = _SHELLS | {'python', 'python3', 'py', 'node', 'deno', 'bun', 'ruby', 'perl', 'php', 'lua',
                           'cscript', 'wscript'}
_WRAPPERS = {'sudo', 'command', 'builtin', 'exec', 'time', 'nohup', 'call', 'start', 'xargs', 'env', 'nice',
             'then', 'do', 'else', 'if', 'while', '!', '&'}
_CHDIRS = {'cd', 'chdir', 'pushd', 'set-location', 'sl'}
_SCRIPT_WRITE_TERMS = ('.write(', 'write_text', 'write_bytes', '.writelines', 'unlink', 'rmtree', 'os.remove',
                       'os.replace', 'os.rename', 'os.truncate', 'shutil.', 'writealltext', 'appendalltext',
                       'writeallbytes', 'writealllines', 'fs.write', 'fs.append', 'fs.rm', 'fs.unlink',
                       'fs.rename', 'fs.copyfile', 'set-content', 'out-file', 'add-content', 'remove-item',
                       'clear-content', 'os.system', 'os.popen', 'subprocess', '.truncate(', 'writefile', 'appendfile',
                       'unlinksync', 'rmsync', 'renamesync', 'copyfilesync', 'createwritestream', 'truncatesync')


def _tokenize(cmd):
    """Quote-aware tokenizer: list of segments (split on ; && || | & newline), each a list of tokens.
    Redirect operators (`>`, `>>`, `2>`, `&>`, ...) are their own tokens. Linear."""
    segs, toks, cur = [], [], []
    has = False
    q = None
    i, n = 0, len(cmd)

    def flush():
        nonlocal has
        if has:
            toks.append(''.join(cur))
        cur.clear()
        has = False

    def endseg():
        flush()
        if toks:
            segs.append(list(toks))
            toks.clear()

    while i < n:
        c = cmd[i]
        if q:
            if c == q:
                q = None
            else:
                cur.append(c)
            i += 1
            continue
        if c in '"\'':
            q = c
            has = True
            i += 1
            continue
        if c == '\\' and i + 1 < n and cmd[i + 1] in '"\'':
            cur.append(cmd[i + 1])
            has = True
            i += 2
            continue
        if c in ' \t\r':
            flush()
            i += 1
            continue
        if c in '\n;':
            endseg()
            i += 1
            continue
        if c in '|&' and not (c == '&' and i + 1 < n and cmd[i + 1] == '>'):
            endseg()
            i += 1
            continue
        if c in '<>' or c == '&':
            prefix = ''
            if c != '&' and cur and ''.join(cur).isdigit() and has:
                prefix = ''.join(cur)
                cur.clear()
                has = False
            else:
                flush()
            j = i
            while j < n and cmd[j] in '<>&|' and (j == i or cmd[j] != '|' or cmd[j - 1] == '>'):
                j += 1
                if cmd[j - 1] == '&' and j - 1 > i and cmd[j - 2] == '>':   # `>&1` / `2>&1` duplicate
                    while j < n and (cmd[j].isdigit() or cmd[j] == '-'):
                        j += 1
                    break
            op = prefix + cmd[i:j]
            toks.append(op)
            i = j
            continue
        cur.append(c)
        has = True
        i += 1
    endseg()
    return segs


def _is_redirect_out(tok):
    t = tok.lstrip('0123456789')
    return t in ('>', '>>', '>|', '&>', '&>>') or (t.startswith('>') and t.rstrip('>|&') == '' and '&' not in t)


def _name(tok):
    base = tok.replace('\\', '/').rstrip('/').split('/')[-1].lower()
    for suf in ('.exe', '.cmd', '.bat', '.ps1', '.com'):
        if base.endswith(suf):
            return base[:-len(suf)]
    return base


def _norm_comp(s):
    return s.split(':', 1)[0].rstrip('. ').lower()


def _mentions(low):
    """True iff the (lowercased) text names a protected path: `.aidd` (not only `.aidd/memory`),
    events.toon, active_spec, or an 8.3 alias of `.aidd`."""
    import re
    if 'events.toon' in low or 'active_spec' in low:
        return True
    if re.search(r'\.claude[\s\S]{0,300}projects[\s\S]{0,300}\.jsonl', low.replace('\\', '/')):
        return True                                            # R9: host transcripts (reads stay allowed in _script_write)
    i = low.find('.aidd')
    while i != -1:
        prev = low[i - 1] if i > 0 else ' '
        j = i + 5
        nxt = low[j] if j < len(low) else ' '
        if not (prev.isalnum() or prev in '_-') and not (nxt.isalnum() or nxt in '_-'):
            if low.startswith('/memory', j) or low.startswith('\\memory', j):
                k = j + 7
                after = low[k] if k < len(low) else ' '
                if not (after.isalnum() or after in '_-'):
                    i = low.find('.aidd', i + 5)
                    continue
            return True
        i = low.find('.aidd', i + 5)
    return bool(re.search(r'(?<![\w-])aidd~\d(?![\w])', low))


def _glob_is_aidd(seg):
    """A segment with glob characters that could expand to `.aidd` (shell globs never match a leading dot
    unless the pattern starts with a literal dot)."""
    if not seg.startswith('.') or not any(c in seg for c in '*?['):
        return False
    import fnmatch
    return fnmatch.fnmatch('.aidd', seg)


def _prot_tok(tok, ctx_aidd, cwd_prot):
    t = tok.lower().replace('\\', '/').strip('"\'` ')
    if t.startswith('-') and ':' in t[:30]:
        t = t.split(':', 1)[1]
    if not t or (t.startswith('-') and not ctx_aidd):
        return False
    segs = [_norm_comp(s) for s in t.split('/') if s]
    if not segs:
        return False
    if segs[-1] in ('events.toon', 'active_spec') or segs[-1].startswith('active_spec.'):
        return True
    if _transcript_path(t):
        return True                                           # host transcripts (R9)
    if 'aidd-hooks' in segs:
        return True                                           # the per-session evidence logs (D5)
    for i, s in enumerate(segs):
        if s == '.aidd' or (len(s) > 5 and s.startswith('aidd~') and s[5:].isdigit()) or _glob_is_aidd(s):
            nxt = segs[i + 1] if i + 1 < len(segs) else None
            if nxt != 'memory':
                return True
    if ctx_aidd and 'evidence' in segs:
        return True
    if cwd_prot and not t.startswith('-') and not (t.startswith('/') or ':' in t[:3]):
        return True   # relative name while the shell sits inside .aidd/
    return False


REVIEW_FILE_NAMES = ('review.md', 'review.html')


def _guarded_leaves():
    """Leaves under specs/<any-id>/ that the shell may never write: the spec artifacts + the owner-only review files."""
    import _common as C
    return set(C.SPEC_ARTIFACT_NAMES) | set(REVIEW_FILE_NAMES)


def _tok_norm(tok):
    """Lowercased, `/`-separated, quote-stripped token with a `-Flag:` prefix removed ('' = not a path)."""
    t = _unquote(tok.lower().replace('\\', '/')).strip()
    if t.startswith('-') and ':' in t[:30]:
        t = t.split(':', 1)[1]
    if not t or t.startswith('-'):
        return ''
    return t


def _is_abs(t):
    return t.startswith('/') or t.startswith('~') or ':' in t[:3]


def _unescape(text):
    """Bash backslash escapes removed (`rev\\iew.html` -> `review.html`, `\\\\` -> `\\`) (closing audit 007 R-2).
    Only a second READING of a token: a Windows path keeps its `\\` -> `/` reading as well."""
    import re
    return re.sub(r'\\(.)', r'\1', text, flags=re.S)


def _leaf_variants(tok):
    """The leaf name of a token as the shell may read it: the `/`-normalised one and the unescaped one."""
    out = set()
    a = _tok_norm(tok)
    if a:
        out.add(_norm_comp(a.rstrip('/').split('/')[-1]))
    b = _unquote(_unescape(tok.lower())).strip()
    if b and not b.startswith('-'):
        out.add(_norm_comp(b.rstrip('/').split('/')[-1]))
    out.discard('')
    return out


def _is_numeric_id(seg):
    return len(seg) > 3 and seg[:3].isdigit() and seg[3] == '-'


def _specs_tok(tok, cwd_specs=False, cwd_abs=None):
    """D8: a path token pointing INTO a specs/ tree (specs/..., or .../specs/<NNN-id>/...).
    aidd:FR-204 also ANY path with a `specs/<segment>/` pair whose leaf is a spec artifact (spec.md, plan.md,
    tasks.md, ...) or review.md / review.html, for ANY id, numeric or not (`D:/proj/specs/F23-eDoc-POS/tasks.md`).
    A RELATIVE token is resolved against the tracked shell cwd `cwd_abs` (hook cwd + every `cd`) and counts when
    it lands in `<project root>/specs/<id>/<artifact>` (closing audit 007 N-1: the root-relative path decides, so
    a project under a folder named `specs`, or `tests/specs`, is not a spec). With no known cwd, `cwd_specs`
    (an earlier `cd specs/...`) makes a relative artifact leaf count (`cd specs/F23-eDoc-POS && echo x > spec.md`)."""
    t = _tok_norm(tok)
    if not t:
        return False
    segs = [_norm_comp(x) for x in t.split('/') if x and x != '.']
    if not segs:
        return False
    leaves = _guarded_leaves()
    for i, x in enumerate(segs):
        if x == 'specs':
            nxt = segs[i + 1] if i + 1 < len(segs) else ''
            if i == 0 or _is_numeric_id(nxt):
                return True
            if segs[-1] in leaves and i + 2 < len(segs) and nxt:
                if _is_abs(t):                         # N-1: decide on the ROOT-relative path when a root exists
                    p = _abs_path(tok)
                    rel = _locate(p) if p else None
                    if rel is not None and not (len(rel) >= 3 and rel[0] == 'specs'):
                        return False                   # `<tmp>/specs/proj/plan.md`: a project under "specs"
                return True
    if _is_abs(t):
        return False
    if cwd_abs:
        p = _abs_path(tok, cwd_abs)
        rel = _locate(p) if p else None
        if rel is None:
            return False
        return len(rel) >= 3 and rel[0] == 'specs' and (rel[-1] in leaves or bool(_leaf_variants(tok) & leaves))
    if cwd_specs and (_leaf_variants(tok) & leaves):
        return True
    return False


def _path_in_specs(path):
    """LEXICAL fallback only (no project root on disk): the path has a `specs` segment followed by another one."""
    t = _tok_norm(path)
    if not t:
        return False
    segs = [_norm_comp(x) for x in t.split('/') if x]
    return any(x == 'specs' and i + 1 < len(segs) for i, x in enumerate(segs))


_PROJECT_MARKERS = frozenset({'.git', 'src', 'build', 'dist', 'node_modules', 'package.json', 'pyproject.toml',
                              'setup.py', 'cargo.toml', 'go.mod', 'pom.xml', '.claude', '.vscode', 'makefile',
                              'requirements.txt', 'tests', 'lib', '.gitignore'})


def _nested_project(d):
    """closing audit 007 N-1: `<root>/specs/<name>` is really a PROJECT living under a folder named specs
    (`<tmp>/specs/proj`), not a spec folder: a non-numeric name, no spec artifact inside, and a project marker
    (src/, .git, package.json, ...). A missing folder or any doubt counts as a spec (stays guarded)."""
    try:
        if _is_numeric_id(d.name.lower()) or not d.is_dir():
            return False
        names = {n.lower() for n in os.listdir(d)[:500]}
        if names & _guarded_leaves():
            return False
        return bool(names & _PROJECT_MARKERS) or any(n.endswith(('.sln', '.csproj')) for n in names)
    except Exception:
        return False


def _abs_path(tok, base=None):
    """Absolute normalised native path of a path token / `cd` target (relative ones joined to `base`), else None
    (a variable, a glob, `-`, or a relative token with no base)."""
    import re
    t = _unquote(tok).strip()
    if t.startswith('-') and ':' in t[:30]:
        t = t.split(':', 1)[1]
    if not t or t.startswith('-') or any(c in t for c in '$*?[{`%'):
        return None
    t = t.replace('\\', '/')
    if t.startswith('~'):
        t = os.path.expanduser(t)
    if os.name == 'nt' and re.match(r'^/[a-zA-Z](/|$)', t):
        t = t[1] + ':/' + t[3:]                           # Git bash /d/proj -> d:/proj
    if os.path.isabs(t) or re.match(r'^[a-zA-Z]:', t):
        return os.path.normpath(t)
    if base:
        return os.path.normpath(os.path.join(base, t))
    return None


def _locate(p):
    """closing audit 007 N-1: the lowercased segments of absolute path `p` RELATIVE TO ITS PROJECT ROOT
    (CLAUDE_PROJECT_DIR when `p` lies under it, else the nearest ancestor with specs/ or .aidd/, re-rooted at a
    nested project under a folder named specs). No root on disk: the segments after the last `specs` segment
    (lexical fallback, prefixed with 'specs'), or [] when there is none."""
    from pathlib import Path
    try:
        ev = _ev()
        root, trusted = None, False
        env_root = os.environ.get('CLAUDE_PROJECT_DIR')
        if env_root and ev.rel_to_root(p, env_root) is not None:
            root, trusted = Path(env_root), True
        if root is None:
            root = ev.known_root(p)
        if root is None:
            segs = [_norm_comp(x) for x in p.replace('\\', '/').split('/') if x]
            idx = [i for i, x in enumerate(segs) if x == 'specs']
            return segs[idx[-1]:] if idx else []
        rel = ev.rel_to_root(p, root)
        if rel is None:
            return None
        raw = [x for x in rel.split('/') if x]
        segs = [_norm_comp(x) for x in raw]
        if not trusted and len(segs) >= 2 and segs[0] == 'specs' and _nested_project(Path(root) / raw[0] / raw[1]):
            return segs[2:]
        return segs
    except Exception:
        return None


def _in_spec_dir(rel):
    """Root-relative segments of a DIRECTORY that sits at or under specs/<id>/."""
    return bool(rel) and len(rel) >= 2 and rel[0] == 'specs'


def _chdir(ctx, target):
    """aidd:FR-204 F-1 / N-1: track the shell cwd through `cd` (relative and absolute) and recompute whether it
    sits inside specs/<id>/ from the ROOT-RELATIVE path; a `cd ..` out of the spec clears the flag."""
    base = ctx.get('cwd_abs')
    p = _abs_path(target, base)
    if p is not None:
        ctx['cwd_abs'] = p
        inside = _in_spec_dir(_locate(p))
    else:
        t = _tok_norm(target)
        segs = [_norm_comp(x) for x in t.split('/') if x and x != '.'] if t else []
        ctx['cwd_abs'] = None                          # unknown from here on: the lexical rules take over
        if not segs:
            inside = ctx.get('cwd_specs', False)
        elif _is_abs(t):
            inside = _path_in_specs(t)
        elif '..' in segs:
            inside = False
        elif segs[0] == 'specs':
            inside = True
        else:
            inside = ctx.get('cwd_specs', False)
    ctx['cwd_specs'] = inside
    if inside:
        ctx['cwd_specs_seen'] = True


_REVIEW_NAME_RE = r'(?<![\w.-])review\.(?:md|html)(?![\w-])'
_QUOTE_CHARS = '"\'`'


def _unquote(text):
    """Remove shell quote / escape characters so `rev''iew.md`, `"review".md` and PowerShell `rev`iew.md`
    read as the name the shell will actually use."""
    return ''.join(c for c in text if c not in _QUOTE_CHARS)


def _readings(low):
    """The two readings of a (lowercased) command text for NAME matching: Windows (`\\` is a path separator)
    and bash (`\\x` is an escaped `x`, closing audit 007 R-2: `rm rev\\iew.html` deletes review.html)."""
    return (_unquote(low.replace('\\', '/')), _unquote(_unescape(low)))


def _names_artifact(low):
    """The (lowercased) text names a spec artifact leaf (spec.md, plan.md, tasks.md, ...) after quote removal."""
    import re
    import _common as C
    alt = '|'.join(re.escape(n) for n in sorted(C.SPEC_ARTIFACT_NAMES))
    return any(re.search(r'(?<![\w.-])(?:%s)(?![\w-])' % alt, r) for r in _readings(low))


def _names_review(low, words=(), cwd_specs=False, cwd_abs=None):
    """aidd:FR-204 aidd:AC-207 the command names review.md / review.html: literally (after quote removal, in the
    Windows or the bash-escape reading) or through a glob / brace token (`review.*`, `revie?.html`,
    `review.{md,html}`) that matches one of them. A glob with no literal name part (`*`, `*.md`) counts only
    inside specs/<id>/: a relative token is resolved against the tracked cwd `cwd_abs` (root-relative, N-1);
    with no known cwd, `cwd_specs` or a `specs` segment in the token's own path decides. So `rm build/*`
    elsewhere is not mistaken for a review deletion."""
    import re
    import fnmatch
    if any(re.search(_REVIEW_NAME_RE, r) for r in _readings(low)):
        return True
    for w in words:
        for path in {_unquote(w.lower().replace('\\', '/')).rstrip('/'), _unquote(_unescape(w.lower())).rstrip('/')}:
            leaf = path.split('/')[-1]
            if not leaf or not any(c in leaf for c in '*?[{'):
                continue
            pat = re.sub(r'\{[^{}]*\}', '*', leaf)
            if not any(fnmatch.fnmatchcase(n, pat) for n in REVIEW_FILE_NAMES):
                continue
            literal = re.sub(r'\[[^\]]*\]|[*?]', '', pat.split('.')[0])
            if literal:
                return True
            dirs = [x for x in path.split('/')[:-1] if x]
            if (cwd_abs or _is_abs(path)) and not any(c in ''.join(dirs) for c in '*?[{$'):
                head = path.rsplit('/', 1)[0] if '/' in path else '.'
                p = _abs_path(head or '/', cwd_abs)
                rel = _locate(p) if p is not None else None
                if rel is not None:
                    if _in_spec_dir(rel):
                        return True
                    continue
            if cwd_specs or 'specs' in [_norm_comp(x) for x in dirs]:
                return True
    return False
_REVIEW_VERBS = _DELETERS | _MOVERS | _WRITERS | _COPIERS | {'sed', 'perl', 'awk', 'gawk', 'truncate'}
_INLINE_FLAGS = ('-c', '-e', '/c', '/k', '-command', '-encodedcommand', '-enc', '-ec', '--eval', '-p', '-r')


def _runs_aidd_review(words):
    """`python .../aidd_review.py ...` (the sanctioned generator) as one segment's words."""
    return bool(words) and _name(words[0]) in _INTERPRETERS and any(
        w.replace('\\', '/').split('/')[-1].lower() == 'aidd_review.py' for w in words[1:4])


def _review_write(cmd, low, ctx, segs, verbs):
    """aidd:FR-204 aidd:AC-207 TEXT-LEVEL rule: the command names review.md / review.html ANYWHERE (any id, absolute
    or relative, after `cd`) and writes (redirection), runs a script writer, uses a mover / copier / writer /
    deleter verb or an interpreter with an inline script. The `aidd` verb and `python .../aidd_review.py` are
    exempt only when nothing is redirected. Lexical by design (a separate script file is not seen); quotes are
    removed and glob / brace tokens are matched against the two names first (F-3)."""
    if not _names_review(low, [w for toks in segs for w in toks], ctx.get('cwd_specs', False), ctx.get('cwd_abs')):
        return False
    seg_words = [[t for t in toks if not _is_redirect_out(t)] for toks in segs]
    sanctioned = all(not w or _name(w[0]) == 'aidd' or _runs_aidd_review(w) for w in seg_words)
    if sanctioned and not ctx.get('writes'):
        return False
    if ctx.get('writes') or _script_write(low) or '<<' in cmd:
        return True
    vs = set(verbs)
    if vs & _REVIEW_VERBS:
        return True
    if vs & _INTERPRETERS:
        for w in seg_words:
            if w and _name(w[0]) in _INTERPRETERS and any(a.lower() in _INLINE_FLAGS for a in w[1:]):
                return True
    return False


def _script_write(low):
    import re
    if any(term in low for term in _SCRIPT_WRITE_TERMS):
        return True
    return bool(re.search(r'open\([^)\n]{0,200}[\'"][wax]\+?[bt]?[\'"]', low))


_ENV_NAMES = ('aidd_evidence_dir', 'aidd_testing', 'aidd_session_id', 'aidd_rules')
_LIB_NAMES = ('aidd_evidence', 'aidd_rules', 'aidd_status')
_FORMS = (('curl', ('-o', '--output', '-O')), ('wget', ('-o', '-O', '--output-document')),
          ('tar', ('-C', '--directory', '-x', '-xf', '-xzf', '-xvf', 'x', 'xf', 'xzf', 'xvf')),
          ('unzip', ('-d',)), ('expand-archive', ()), ('invoke-webrequest', ('-outfile',)), ('iwr', ('-outfile',)),
          ('tee-object', ()), ('export-csv', ()), ('export-clixml', ()), ('eval', ()), ('xargs', ()),
          ('invoke-expression', ()), ('iex', ()), ('start-process', ()), ('7z', ()), ('certutil', ()),
          ('bitsadmin', ()), ('ex', ()), ('vim', ('-c', '-es')), ('ed', ()))
_FORM_SUBSTR = ('[io.file]::', '[io.directory]::', '[system.io.file]::', '[system.io.directory]::', 'git apply',
                'git am ', 'git stash pop', 'git stash apply', 'invoke-expression', 'eval(')
_WRITE_API = ('write', 'append', 'unlink', 'set-content', 'out-file', 'add-content', 'rmtree', 'remove-item',
              'rename', 'truncate', 'copyfile', 'createwritestream')


_ENV_TOKENS = ('aidd_testing', 'aidd_evidence_dir', 'aidd_session_id')   # N1/N2: these may not appear AT ALL


def _env_token(low):
    """True iff the text contains one of the evidence-redirecting variable names in ANY form."""
    return any(t in low for t in _ENV_TOKENS)


def _expand_words(words):
    """Words plus the words INSIDE quoted tokens (powershell -c "...", node -e '...') one level deep."""
    out = list(words)
    for w in words:
        if ' ' in w and len(w) < 20000:
            for toks in _tokenize(w):
                out.extend(toks)
    return out


def _env_assign(low):
    """Any assignment of the AIDD_* control variables (also set/export/$env:/setx/os.environ[...])."""
    for n in _ENV_NAMES:
        i = low.find(n)
        while i != -1:
            j = i + len(n)
            while j < len(low) and low[j] in ' \t\'"]}':
                j += 1
            if j < len(low) and low[j] == '=':
                return True
            i = low.find(n, i + 1)
    if any(n in low for n in _ENV_NAMES):
        if 'setenvironmentvariable' in low or 'putenv' in low or 'os.environ' in low:
            return True
        if 'setx' in low.replace('\n', ' ').split():
            return True
    return False


def _lib_import(low, words):
    """Imports / -m runs of the evidence & rules libraries (a way to forge evidence through the API)."""
    names = [n for n in _LIB_NAMES if n in low]
    if not names:
        return False
    for i, w in enumerate(words[:-1]):
        if w.lower() == '-m' and any(words[i + 1].lower().startswith(n) for n in _LIB_NAMES):
            return True
    if any(t in low for t in ('importlib', '__import__', 'runpy', 'import_module', 'spec_from_file_location',
                              'exec(', 'execfile', 'sys.path')):
        return True
    for n in names:
        i = low.find(n)
        while i != -1:
            before = low[max(0, i - 14):i]
            if 'import ' in before or 'from ' in before or 'import\t' in before:
                return True
            i = low.find(n, i + 1)
    return False


def _shell_block(cmd, ctx, depth=0):
    """True iff the shell command writes into a protected path / tampers with evidence."""
    import re
    low = cmd.lower()
    lown = low.replace('\\', '/')
    ctx_aidd = '.aidd' in lown or ctx['aidd']
    cwd_prot = ctx['cwd_prot']
    segs = _tokenize(cmd)
    all_words = _expand_words([w for toks in segs for w in toks])
    verbs = []
    for toks in segs:
        cwd_specs = ctx.get('cwd_specs', False)     # F-1: the shell sits inside specs/<id>/ (hook cwd or an earlier cd)
        cwd_abs = ctx.get('cwd_abs')                # N-1: the tracked shell cwd (None = unknown, lexical rules)
        # redirects first: they apply whatever the command is
        for i, t in enumerate(toks):
            if _is_redirect_out(t) and i + 1 < len(toks):
                tgt = toks[i + 1]
                if tgt.startswith('&') or _name(tgt) in ('nul', 'null'):
                    continue
                ctx['writes'] = True
                if _prot_tok(tgt, ctx_aidd, cwd_prot) or _specs_tok(tgt, cwd_specs, cwd_abs):
                    return True
        words = [t for t in toks if not _is_redirect_out(t)]
        k = 0
        has_xargs = False
        while k < len(words) and (('=' in words[k] and words[k].split('=')[0].replace('_', 'a').isalnum())
                                  or _name(words[k]) in _WRAPPERS or (k > 0 and words[k].startswith('-'))):
            if _name(words[k]) == 'xargs':
                has_xargs = True
            k += 1
        if k >= len(words):
            continue
        verb = _name(words[k])
        verbs.append(verb)
        args = words[k + 1:]

        def hit(a):
            return _prot_tok(a, ctx_aidd, cwd_prot) or (verb not in ('mkdir', 'md') and _specs_tok(a, cwd_specs, cwd_abs))
        prot_args = [a for a in args if hit(a)]
        pos = [a for a in args if not a.startswith('-') and not (a.startswith('/') and len(a) <= 3)]
        if verb == 'aidd':
            continue                                           # the sanctioned writer
        if verb in _CHDIRS:
            targets = [a for a in args if not a.startswith('-')]
            if any(_prot_tok(a, ctx_aidd, cwd_prot) for a in targets):
                cwd_prot = True                                # later relative names resolve inside .aidd/
            for a in targets:
                _chdir(ctx, a)                                 # F-1 / N-1: root-relative, set AND cleared on every cd
            continue
        if verb in _REVIEW_VERBS and args and _names_review('', args, cwd_specs, cwd_abs):
            ctx['review_named'] = True
            return True                                        # F-3: `rm *` / `rm *.html` while THIS segment sits in specs/<id>/
        if (verb in _DELETERS or verb in _MOVERS) and not pos and (
                ctx_aidd or 'specs' in lown or 'aidd-hooks' in lown):
            return True                                        # `gci .aidd | ri` - the targets come from the pipeline
        if has_xargs and (verb in _DELETERS or verb in _MOVERS or verb in _WRITERS or verb in _COPIERS):
            ctx['writes'] = True
            if ctx_aidd or 'specs' in lown or 'aidd-hooks' in lown:
                return True                                    # `... | xargs rm`: targets come from stdin
        if verb in _DELETERS or verb in _MOVERS or verb in _WRITERS:
            if args:
                ctx['writes'] = True
            if prot_args:
                return True
        elif verb in _COPIERS:
            ctx['writes'] = True
            dest = [a for a in pos[1:] if hit(a)]
            tflag = [args[j + 1] for j, a in enumerate(args[:-1]) if a in ('-t', '--target-directory')
                     and hit(args[j + 1])]
            if dest or tflag:
                return True
        elif verb in ('sed', 'perl', 'awk', 'gawk', 'ruby'):
            inplace = any(a == '--in-place' or a.startswith('--in-place=')
                          or (a.startswith('-') and not a.startswith('--') and 'i' in a[1:] and verb != 'ruby'
                              and len(a) <= 6) or (a == '-i') or (a == 'inplace') for a in args)
            if inplace:
                ctx['writes'] = True
                if prot_args:
                    return True
        elif verb == 'find':
            if '-delete' in args or '-exec' in args or '-fprint' in args or '-ok' in args:
                ctx['writes'] = True
                if prot_args:
                    return True
        elif verb == 'git':
            if prot_args and any(a in ('clean', 'checkout', 'restore', 'rm', 'stash', 'mv') for a in args):
                return True
        if verb in _SHELLS and depth < 3 and len(words) > 1:
            body = list(args)
            while body and (re.match(r'^[-/][a-z]{1,20}$', body[0].lower())
                            or body[0].lower() in ('bypass', 'unrestricted', 'remotesigned')):
                body.pop(0)
            if body and _shell_block(' '.join(body), dict(ctx, cwd_prot=cwd_prot), depth + 1):
                return True
    if depth > 0:
        return False
    # ---- text-level checks (whole command)
    if _env_token(low) or _env_assign(low):
        return True                                            # N1/N2: never let a command touch these variables
    if _lib_import(low, all_words):
        return True
    mention = _mentions(lown) or 'aidd-hooks' in lown or any(_specs_tok(w) for w in all_words)
    if mention and _script_write(low):
        return True
    scripty = bool(set(verbs) & _INTERPRETERS) or '<<' in cmd or 'node -e' in low
    if scripty and ('tasks.md' in low or mention) and any(t in low for t in _WRITE_API):
        return True                                            # node -e / python - / heredoc writing to evidence or tasks
    if 'join-path' in low and ctx.get('writes') and re.search(r"(aidd|-hooks|\.aid)['\"]", low):
        return True                                            # Set-Content (Join-Path $x 'aidd') - path built in pieces
    if 'tasks.md' in low and 'approved' in low and (ctx.get('writes') or _script_write(low)):
        return True                                            # forging the approval line through the shell
    if _review_write(cmd, low, ctx, segs, verbs):
        return True                                            # aidd:FR-204 forging / deleting the owner's review
    if ctx.get('cwd_specs_seen') and _names_artifact(low) and (
            _script_write(low) or (scripty and any(t in low for t in _WRITE_API))):
        return True                                            # F-1: `cd specs/<id> && python -c "open('spec.md','w')"`
    if mention:
        if any(f in lown for f in _FORM_SUBSTR):
            return True
        names = set(verbs) | {_name(w) for w in all_words}
        for form, flags in _FORMS:
            if form in names and (not flags or any(w in flags or w.lower() in flags for w in all_words)):
                return True
    return False


def _needs_check(low, cwd):
    """Cheap pre-check (no imports): can this command text / cwd matter at all?"""
    if any(m in low for m in BASH_MARKERS) or '.aidd' in cwd.lower() or 'specs' in cwd.lower():
        return True                                            # F-1: cwd inside specs/ makes `> spec.md` matter
    if 'join-path' in low and 'aidd' in low:
        return True
    if '.jsonl' in low and '.claude' in low:
        return True                                            # R9: host transcripts
    return any(c in low for c in '*?[') and ('.a' in low or '.*' in low or '.?' in low or '.[' in low)


def _decide_bash(event, ti):
    cmd = ti.get('command')
    if not isinstance(cmd, str):
        return False, ''
    low = cmd.lower()
    cwd = event.get('cwd') if isinstance(event.get('cwd'), str) else ''
    if not _needs_check(low, cwd):
        return False, ''
    cwd_prot = False
    if cwd:
        segs = [_norm_comp(s) for s in cwd.replace('\\', '/').split('/') if s]
        for i, s in enumerate(segs):
            if s == '.aidd' and (segs[i + 1] if i + 1 < len(segs) else None) != 'memory':
                cwd_prot = True
    cwd_abs = _abs_path(cwd) if cwd else None
    if cwd_abs:                                                # N-1: root-relative, not "any `specs` segment"
        in_specs = _in_spec_dir(_locate(cwd_abs))
    else:
        in_specs = bool(cwd) and _path_in_specs(cwd)
    ctx = {'aidd': False, 'cwd_prot': cwd_prot, 'writes': False, 'cwd_specs': in_specs, 'cwd_specs_seen': in_specs,
           'cwd_abs': cwd_abs}
    if _shell_block(cmd, ctx):
        if ctx.get('review_named') or _names_review(low, [w for toks in _tokenize(cmd) for w in toks],
                                                    ctx.get('cwd_specs_seen', False)):
            return True, R9_BASH_MESSAGE + '\n' + REVIEW_MESSAGE
        return True, R9_BASH_MESSAGE
    return False, ''


# ----------------------------------------------------------------------------- core

def decide(event):
    """Return (blocked, message). `event` must be a dict."""
    import _common as C
    ti = C.tool_input_of(event)
    if event.get('tool_name') in SHELL_TOOLS:
        return _decide_bash(event, ti)
    for fp in _paths(ti):
        blocked, msg = _decide_path(event, ti, fp)
        if blocked:
            return True, msg
    return False, ''


def _record_error(event, err):
    try:
        import _common as C
        ev = _ev()
        cwd = C.str_field(event, 'cwd') or os.getcwd()
        ev.record_hook_error(cwd, C.session_of(event), 'rule_gate', repr(err))
    except Exception:
        pass


def _override_root(event):
    """The KNOWN project root of the event (file path first, then cwd), or None: never a guess."""
    import _common as C
    ev = _ev()
    ti = C.tool_input_of(event)
    cwd = C.str_field(event, 'cwd')
    starts = []
    if event.get('tool_name') not in SHELL_TOOLS:
        for fp in _paths(ti):
            try:
                starts.append(os.path.dirname(str(ev.real_path(fp, cwd or None))))
            except Exception:
                continue
    if cwd:
        starts.append(cwd)
    for s in starts:
        try:
            r = ev.known_root(s)
            if r is not None:
                return r
        except Exception:
            continue
    return None


def _record_override(event, msg):
    """aidd:FR-208 aidd:AC-214 AIDD_RULES=warn: every would-be block appends rules_override{hook, mode, rules}
    (project kind, only with a known root). Best effort: never raises, never changes the exit code."""
    try:
        import re
        if HOOKS_DIR not in sys.path:
            sys.path.insert(0, HOOKS_DIR)
        root = _override_root(event)
        if root is None:
            return
        import _common as C
        rules_hit = sorted(set(re.findall(r'\baidd (R[0-9]+(?:/R[0-9]+)*|content)\b', msg or '')))
        _ev().append(root, C.session_of(event), 'rules_override', hook='rule_gate', mode='warn',
                     rules=rules_hit)
    except Exception:
        pass


def _sync_transcript(event):
    """FR-013: incremental transcript sync of AskUserQuestion answers. Never changes exit code/output."""
    try:
        tp = event.get('transcript_path')
        if not isinstance(tp, str) or not tp:
            return
        if HOOKS_DIR not in sys.path:
            sys.path.insert(0, HOOKS_DIR)
        import _common as C
        _ev().sync_ask_answers(tp, C.session_of(event), C.str_field(event, 'cwd') or os.getcwd())
    except Exception as e:
        _record_error(event, e)


_INTERP_VALUE_FLAGS = {'-W', '-X'}        # interpreter flags that take a separate value (python -W ignore)
_INVOKES_MAX_DEPTH = 2
_INVOKES_MAX_CHARS = 2000
_INVOKES_MAX_WORDS = 64


def _aidd_script(w):
    b = w.replace('\\', '/').split('/')[-1].lower()
    return b.startswith('aidd') and b.endswith('.py')


def _invokes_aidd(cmd, depth=0):
    """True iff a segment of the shell command RUNS `aidd` (executable/alias) or an aidd*.py script.
    Recurses (bounded depth) into the body of `bash -c`/`powershell -Command`/`cmd /c` and into
    `( ... )` / `$( ... )` groups; skips interpreter flags (and their values) before the script path.
    H1: linear and bounded (best-effort marker): the command is truncated to _INVOKES_MAX_CHARS, each
    segment to _INVOKES_MAX_WORDS words, and only the FIRST group per segment is recursed into."""
    if not isinstance(cmd, str) or len(cmd) > 20000:
        return False
    cmd = cmd[:_INVOKES_MAX_CHARS]
    if 'aidd' not in cmd.lower():
        return False
    for toks in _tokenize(cmd):
        words = [t for t in toks if not _is_redirect_out(t)][:_INVOKES_MAX_WORDS]
        if depth < _INVOKES_MAX_DEPTH:
            for i, w in enumerate(words):
                if '$(' in w:
                    inner = w.split('$(', 1)[1]
                elif w.startswith('('):
                    inner = w.lstrip('(')
                else:
                    continue
                if _invokes_aidd(' '.join([inner] + words[i + 1:]).replace(')', ' '), depth + 1):
                    return True
                break                                   # only the FIRST group of the segment
        k = 0
        while k < len(words) and (('=' in words[k] and words[k].split('=')[0].replace('_', 'a').isalnum())
                                  or _name(words[k]) in _WRAPPERS or (k > 0 and words[k].startswith('-'))):
            k += 1
        if k >= len(words):
            continue
        if _name(words[k]) == 'aidd':
            return True
        if _name(words[k]) in _SHELLS and depth < _INVOKES_MAX_DEPTH:
            import re
            body = list(words[k + 1:])
            while body and (re.match(r'^[-/][a-z]{1,20}$', body[0].lower())
                            or body[0].lower() in ('bypass', 'unrestricted', 'remotesigned')):
                body.pop(0)
            if body and _invokes_aidd(' '.join(body), depth + 1):
                return True
        if _name(words[k]) in _INTERPRETERS:
            j = k + 1
            while j < len(words) and words[j].startswith('-'):
                j += 2 if words[j] in _INTERP_VALUE_FLAGS else 1
            if j < len(words) and _aidd_script(words[j]):
                return True
            for w in words[k + 1:k + 4]:
                if _aidd_script(w):
                    return True
        elif _name(words[k]).startswith('aidd') and words[k].lower().endswith('.py'):
            return True
    return False


def _write_caller_marker(event):
    """FR-001: before a shell command that invokes `aidd`, record {session, ts} at caller_marker_path(root)
    so the CLI can infer its caller session. Best-effort: never blocks, never raises."""
    try:
        if event.get('tool_name') not in SHELL_TOOLS:
            return
        ti = event.get('tool_input')
        cmd = ti.get('command') if isinstance(ti, dict) else None
        if not isinstance(cmd, str) or not _invokes_aidd(cmd):
            return
        if HOOKS_DIR not in sys.path:
            sys.path.insert(0, HOOKS_DIR)
        import _common as C
        ev = _ev()
        sid = C.session_of(event)
        if not sid:
            return
        cwd = event.get('cwd') if isinstance(event.get('cwd'), str) and event.get('cwd') else os.getcwd()
        path = ev.caller_marker_path(ev.find_root(cwd))
        os.makedirs(os.path.dirname(str(path)), exist_ok=True)
        tmp = f'{path}.{os.getpid()}.tmp'
        import time
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump({'session': sid, 'ts': time.time()}, f)
        os.replace(tmp, str(path))
    except Exception:
        pass


def main():
    mode = _mode()
    if mode == 'off':
        sys.exit(0)
    event = {}
    try:
        try:
            raw = sys.stdin.buffer.read()
            event = json.loads(raw.decode('utf-8', 'replace'))
        except Exception:
            event = {}
        if not isinstance(event, dict):
            event = {}
        _sync_transcript(event)
        blocked, msg = False, ''
        skip = False
        if event.get('tool_name') in SHELL_TOOLS:   # cheap pre-check: import nothing unless it can matter
            ti = event.get('tool_input')
            cmd = ti.get('command') if isinstance(ti, dict) else None
            cwd = event.get('cwd')
            if not isinstance(cmd, str) or not _needs_check(cmd.lower(), cwd if isinstance(cwd, str) else ''):
                skip = True
        if not skip:
            if HOOKS_DIR not in sys.path:
                sys.path.insert(0, HOOKS_DIR)
            blocked, msg = decide(event)            # H1: the R9/shell gate decides BEFORE the marker
    except SystemExit:
        raise
    except Exception as e:  # never wedge a session over a hook bug
        _record_error(event, e)
        sys.exit(0)
    if not blocked or mode == 'warn':
        _write_caller_marker(event)                 # best-effort, only for a command that will run
    if blocked:
        if mode == 'warn':
            _emit('[AIDD_RULES=warn, not blocking] ' + msg)
            _record_override(event, msg)
            sys.exit(0)
        _emit(msg)
        sys.exit(2)
    sys.exit(0)


if __name__ == '__main__':
    main()
