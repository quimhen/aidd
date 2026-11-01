#!/usr/bin/env python3
"""
aidd guard — the git-hook gate for hosts with no write hook (spec 012: FR-1202, FR-1203, FR-1207,
FR-1208). Stdlib only, no LLM, no network, no graph rebuild.

Usage:
    aidd_guard.py guard commit [--root DIR]   pre-commit: exit 1 when staged code breaks a blocking rule
    aidd_guard.py guard push [--root DIR]     pre-push: the same findings printed as warnings, exit 0

Blocking findings (only when a code file is staged; docs/specs-only commits always pass):
    R6        the checked spec has no valid, recorded tasks approval
    R5        tasks.md/plan.md out of chain order
    verify    the last `aidd verify` failed, or is stale AND the staged code changed after it ran
    qa-audit  specs/<id>/qa-audit.md has a row with a FAIL token in a verdict column
R4/R7/R10/R11/R12 never block a commit. The specs checked are every open spec whose tasks.md `Target
file` cells own a staged code path, else the gate target; with neither: pass with one warning line.
Light read per spec (approval hash + recorded event, newest verify_run, qa-audit.md): no build_status.

AIDD_GUARD=warn turns blocks into warnings, AIDD_GUARD=off disables the guard; every use is recorded
as a `guard_override {hook, mode, rules}` event. An internal error fails open (exit 0, `hook_error`).
"""
import os
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

SCRIPTS_DIR = Path(__file__).resolve().parent

GUARD_ENV = 'AIDD_GUARD'
NON_CODE_SUFFIXES = ('.md', '.txt', '.toon')
NON_CODE_DIRS = ('specs', 'docs', '.aidd', '.agents', '.opencode', '.gemini')
NON_CODE_NAMES = ('license',)
MAX_QA_READ = 2 * 1024 * 1024
MAX_NAMES_SHOWN = 3

_WHY_RE = re.compile(r'^(R\d+)\s+(.*?)\s+→\s+(.*)$', re.S)
_CHAIN_ORDER_RE = re.compile(r'tasks\.md.*plan\.md|plan\.md.*tasks\.md', re.I | re.S)
_VERDICT_HEAD_RE = re.compile(r'verdict|veredicto|result|resultado|status|estado', re.I)
_FAIL_CELL_RE = re.compile(r'^[^A-Za-z0-9]*fail(?![\w-])', re.I)
_SEPARATOR_CELL_RE = re.compile(r'^\s*:?-{2,}:?\s*$')

USAGE = 'usage: aidd guard commit|push [--root DIR]'


def _libs():
    """(aidd_evidence, aidd_status), imported lazily so an import failure fails open in main()."""
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    import aidd_evidence as ev  # noqa: WPS433
    import aidd_status as status  # noqa: WPS433
    return ev, status


def _split_names(out):
    return [p.replace('\\', '/') for p in (out or '').split('\0') if p.strip()]


def staged_files(root):
    """Root-relative names of the staged files (ONE `git diff --cached --name-only`, 5 s timeout);
    [] on any failure (git missing, not a repo, timeout). Never raises."""
    try:
        _ev, status = _libs()
        return _split_names(status._git(root, 'diff', '--cached', '--name-only', '-z'))
    except Exception:
        return []


def _outgoing_files(root):
    """pre-push: files changed by the commits not yet on the upstream; the last commit's files when no
    upstream is set. [] on any failure. Never raises."""
    try:
        _ev, status = _libs()
        out = status._git(root, 'diff', '--name-only', '-z', '@{upstream}...HEAD')
        if out is None:
            out = status._git(root, 'diff-tree', '--no-commit-id', '--name-only', '-r', '--root', '-z', 'HEAD')
        return _split_names(out)
    except Exception:
        return []


def is_code_file(rel):
    """True unless `rel` is documentation or AIDD state: *.md|*.txt|*.toon, specs/**, docs/**, .aidd/**,
    .agents/**, .opencode/**, .gemini/**, LICENSE. Never raises (False on bad input)."""
    try:
        p = str(rel or '').strip().replace('\\', '/')
        while p.startswith('./'):
            p = p[2:]
        p = p.strip('/')
        if not p:
            return False
        segs = p.split('/')
        name = segs[-1].lower()
        if segs[0].lower() in NON_CODE_DIRS or name in NON_CODE_NAMES:
            return False
        return not name.endswith(NON_CODE_SUFFIXES)
    except Exception:
        return False


def _gate_dir(root, ev):
    """specs/<gate pointer> when the pointer is set and the folder exists, else None."""
    spec = ev.get_gate_spec(root)
    if not spec:
        return None
    d = Path(root) / 'specs' / spec
    return d if d.is_dir() else None


def _finding(rule, message, fix):
    return {'rule': rule, 'message': message, 'fix': fix}


def _approval_findings(spec, status):
    t = status.get('tasks') or {}
    ap = t.get('approval')
    if ap == 'valid' and t.get('approval_recorded'):
        return []
    if ap == 'valid':
        return [_finding('R6', f'aidd R6: tasks.md of {spec} has an Approved: line but no recorded `approved` '
                               'event for its hash (it was not written through `aidd rules approve`).',
                         f'aidd rules approve {spec}')]
    reason = {'no-tasks': 'no tasks.md', 'pending': 'approval pending',
              'invalid': 'approval void: tasks.md changed after approval'}.get(ap, str(ap))
    return [_finding('R6', f'aidd R6: spec {spec} (owner of the staged code) has no valid tasks approval ({reason}).',
                     f'aidd review {spec}, then aidd rules approve {spec} once the owner approves')]


def _chain_findings(status):
    out = []
    for line in status.get('why_blocked') or []:
        m = _WHY_RE.match(str(line))
        if m and m.group(1) == 'R5' and _CHAIN_ORDER_RE.search(m.group(2)):
            out.append(_finding('R5', f'aidd R5: {m.group(2)}', m.group(3)))
    return out


def _changed_since(root, files, ts):
    """Up to MAX_NAMES_SHOWN staged code files modified (or deleted) after `ts`; all unknown -> changed."""
    try:
        cut = float(ts)
    except (TypeError, ValueError):
        return list(files[:MAX_NAMES_SHOWN])
    hit = []
    for rel in files:
        try:
            changed = (Path(root) / rel).stat().st_mtime > cut
        except OSError:
            changed = True                      # staged deletion or unreadable: the code changed
        if changed:
            hit.append(rel)
            if len(hit) >= MAX_NAMES_SHOWN:
                break
    return hit


def _verify_findings(root, spec, status, code, partial_ok=False):
    v = status.get('verification') or {}
    state = v.get('status')
    if partial_ok:
        return []
    if state == 'failed':
        return [_finding('verify', f'aidd verify: the last `aidd verify {spec}` failed.',
                         f'fix the failing rows (specs/{spec}/evidence/verify-<n>.txt), then aidd verify {spec}')]
    if state == 'stale':
        hit = _changed_since(root, code, v.get('ts'))
        if hit:
            return [_finding('verify', f'aidd verify: the last `aidd verify {spec}` is stale for the staged code '
                                       f'(changed after it ran: {", ".join(hit)}).',
                             f'aidd verify {spec}')]
    return []


def _cells(line):
    s = line.strip().replace('\\|', '\0')
    if s.startswith('|'):
        s = s[1:]
    if s.endswith('|'):
        s = s[:-1]
    return [c.replace('\0', '|').strip() for c in s.split('|')]


def _fail_rows(text):
    """First cell of every table row whose verdict column (header Verdict/Result/Status/...) starts with a
    FAIL token (case-insensitive)."""
    rows, cols, prev = [], None, None
    for raw in text.split('\n'):
        line = raw.strip()
        if not line.startswith('|'):
            cols, prev = None, None
            continue
        cells = _cells(line)
        if cells and all(_SEPARATOR_CELL_RE.match(c) for c in cells if c) and any(cells):
            cols = [i for i, h in enumerate(prev or []) if _VERDICT_HEAD_RE.search(h)]
            continue
        if cols and any(i < len(cells) and _FAIL_CELL_RE.search(cells[i]) for i in cols):
            rows.append(cells[0] or '?')
        prev = cells
    return rows


def _qa_findings(d, spec):
    p = Path(d) / 'qa-audit.md'
    try:
        if not p.is_file() or p.stat().st_size > MAX_QA_READ:
            return []
        text = p.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return []
    rows = _fail_rows(text)
    if not rows:
        return []
    shown = ', '.join(rows[:MAX_NAMES_SHOWN]) + (f' (+{len(rows) - MAX_NAMES_SHOWN} more)'
                                                 if len(rows) > MAX_NAMES_SHOWN else '')
    return [_finding('qa-audit', f'aidd qa-audit: specs/{spec}/qa-audit.md has {len(rows)} row(s) with a FAIL '
                                 f'verdict ({shown}).',
                     f'fix the failing items and update specs/{spec}/qa-audit.md after a new audit, '
                     f'then aidd verify {spec}')]


def evaluate(root, files, status=None):
    """Blocking findings [{rule, message, fix}] for the staged `files` against the gate-target spec.
    [] when no code file is staged or no spec applies. The specs checked are every OPEN spec whose
    tasks.md `Target file` cells own a staged code path; the gate target only when none owns any
    (spec 012 Amendment 1). `status`: an optional ledger-shaped dict (keys spec, tasks.approval,
    tasks.approval_recorded, why_blocked, verification) used INSTEAD of reading the specs (tests)."""
    code = [f for f in (files or []) if is_code_file(f)]
    if not code:
        return []
    root = Path(root)
    if status is not None:
        return _spec_findings(root, root / 'specs' / str(status.get('spec') or ''), status, code)
    return _evaluate_owners(root, _owning_specs(root, code))


def _spec_findings(root, d, status, code, partial_ok=False):
    if not status or status.get('unparseable'):
        return []                               # unreadable spec: fail open, never a false block
    spec = str(status.get('spec') or d.name)
    return (_approval_findings(spec, status) + _chain_findings(status)
            + _verify_findings(root, spec, status, code, partial_ok) + _qa_findings(d, spec))


def _evaluate_owners(root, owners, allow_partial=False):
    """Findings of every (spec_dir, staged code files) pair, from ONE light read per spec."""
    if not owners:
        return []
    ev, verify_status, rules = _libs3()
    approved = _safe_list(lambda: ev.events(root, kind='approved'))
    out = []
    for d, files in owners:
        state = _light_status(root, d, ev, rules, approved)
        threshold = (state.get('verification') or {}).get('ts')
        if allow_partial:
            threshold = max(float(threshold or 0), _latest_partial_failure(root, d, files, ev))
        partial = (allow_partial and (_partial_passes(root, d, files, verify_status, ev, rules, threshold)
                                      or _provider_partial_passes(root, d, files, ev, threshold)))
        out += _spec_findings(root, d, state, files, partial)
    return out


# ------------------------------------------------------------ owners and the light read (Amendment 1)

_TARGET_HEAD_RE = re.compile(r'^\s*target\s+files?\b', re.I)
_TRAILING_NOTE_RE = re.compile(r'\s*\([^()]*\)\s*$')


def _libs3():
    ev, status = _libs()
    import aidd_rules as rules  # noqa: WPS433
    return ev, status, rules


def _safe_list(fn):
    try:
        return list(fn() or [])
    except Exception:
        return []


def _read_small(p):
    """Text of `p`, or None when it is missing, unreadable or larger than MAX_QA_READ."""
    try:
        p = Path(p)
        if not p.is_file() or p.stat().st_size > MAX_QA_READ:
            return None
        return p.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return None


def _norm_path(s):
    p = str(s or '').strip().strip('`"\'').strip().replace('\\', '/')
    while p.startswith('./'):
        p = p[2:]
    return p.lstrip('/')


def _target_cell_paths(cell):
    """Paths of one `Target file` cell: trailing `(same owner as ...)` notes stripped, `a, b` split."""
    text = str(cell or '').strip()
    prev = None
    while prev != text:
        prev, text = text, _TRAILING_NOTE_RE.sub('', text)
    out = []
    for part in text.split(','):
        p = _norm_path(_TRAILING_NOTE_RE.sub('', part))
        if p and ('/' in p or '.' in p):
            out.append(p)
    return out


def _target_files(tasks_text):
    """Every path named in a `Target file` column of the tables of a tasks.md text."""
    out, col, prev = [], None, None
    for raw in (tasks_text or '').split('\n'):
        line = raw.strip()
        if not line.startswith('|'):
            col, prev = None, None
            continue
        cells = _cells(line)
        if cells and all(_SEPARATOR_CELL_RE.match(c) for c in cells if c) and any(cells):
            hits = [i for i, h in enumerate(prev or []) if _TARGET_HEAD_RE.search(h)]
            col = hits[0] if hits else None
            continue
        if col is not None and col < len(cells):
            out += _target_cell_paths(cells[col])
        prev = cells
    return out


def _owns(targets, rel, rules):
    if rel in targets:
        return True
    hit = getattr(rules, '_glob_hit', None)
    globs = [t for t in targets if '*' in t or t.endswith('/')]
    return bool(globs) and callable(hit) and hit(rel, globs)


def _task_owners(tasks_text):
    owners, column, previous = {}, None, None
    for raw in tasks_text.split('\n'):
        line = raw.strip()
        if not line.startswith('|'):
            column, previous = None, None
            continue
        cells = _cells(line)
        if cells and all(_SEPARATOR_CELL_RE.match(c) for c in cells if c) and any(cells):
            hits = [i for i, h in enumerate(previous or []) if _TARGET_HEAD_RE.search(h)]
            column = hits[0] if len(hits) == 1 else None
            continue
        match = re.fullmatch(r'[`*\s]*(T-\d+)[`*\s]*', cells[0], re.I) if cells else None
        if match and column is not None and column < len(cells):
            task = match.group(1).upper()
            paths = _target_cell_paths(cells[column])
            if task in owners or not paths:
                raise ValueError('ambiguous task ownership')
            owners[task] = paths
        previous = cells
    return owners


def partial_scope(root, tasks_text, spec_text, task_ids, status, rules):
    """Capture explicit task ownership and test inputs, not transitive proof."""
    selected = {x.upper() for x in task_ids}
    owners = _task_owners(tasks_text)
    if not selected or not selected <= owners.keys():
        raise ValueError('selected tasks lack exact ownership')
    paths = {path for task in selected for path in owners[task]}
    if any(any(ch in path for ch in '*?[]') or path.startswith('/') or '..' in path.split('/')
           or '\\' in path or ':' in path for path in paths):
        raise ValueError('partial guard needs exact relative target paths')
    if any(task not in selected and set(targets) & paths for task, targets in owners.items()):
        raise ValueError('target is owned by another task not selected')
    rows = rules.parse_verification(spec_text)
    mapping = {}
    for task in sorted(selected):
        task_rows = status._task_rows(tasks_text, rows, [task])
        for row in task_rows:
            if (row.get('reuse') != 'hermetic' or not str(row.get('environment') or '').lower().startswith('contract:offline;')
                    or not row.get('inputs') or any(not rules._glob_hit(path, row['inputs']) for path in owners[task])):
                raise ValueError('task row lacks explicit offline coverage of its target files')
        mapping[task] = {'paths': sorted(owners[task]), 'rows': sorted(str(row['n']) for row in task_rows)}
    hashes = {}
    base = Path(root).resolve(strict=True)
    for path in sorted(paths):
        file = base
        for part in path.split('/'):
            file = file / part
            if file.is_symlink():
                raise ValueError('linked target is not eligible')
        file.resolve(strict=True).relative_to(base)
        if not file.is_file():
            raise ValueError('missing target')
        hashes[path] = hashlib.sha256(file.read_bytes()).hexdigest()
    return {'format': 'aidd-guard-partial-v1', 'tasks': mapping, 'files': hashes}


def _staged_hash(root, path):
    # Both the index mode and the blob bytes must match; no worktree mtime shortcut.
    index = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-s', '-z', '--', path], timeout=5)
    entries = [part for part in index.split(b'\0') if part]
    if len(entries) != 1:
        raise ValueError('missing or ambiguous index entry')
    meta, indexed = entries[0].split(b'\t', 1)
    mode, _oid, stage = meta.split()
    if mode not in (b'100644', b'100755') or stage != b'0' or os.fsdecode(indexed).replace('\\', '/') != path:
        raise ValueError('index entry is not a regular file')
    obj = ':' + path
    size = int(subprocess.check_output(['git', '-C', str(root), 'cat-file', '-s', obj], timeout=5))
    if size > 10 * 1024 * 1024:
        raise ValueError('staged blob too large')
    blob = subprocess.check_output(['git', '-C', str(root), 'cat-file', 'blob', obj], timeout=5)
    return hashlib.sha256(blob).hexdigest()


def _partial_passes(root, d, code, status, ev, rules, full_ts):
    """Read the latest relevant runner receipt; unknown coverage cannot bypass verify."""
    try:
        tasks_text, spec_text = _read_small(d / 'tasks.md'), _read_small(d / 'spec.md')
        if tasks_text is None or spec_text is None:
            return False
        owners = _task_owners(tasks_text)
        affected = {task for task, paths in owners.items() if set(paths) & set(code)}
        if not affected or any(not any(path in paths for paths in owners.values()) for path in code):
            return False
        events = [e for e in ev.events(root, kind='task_verify_run') if (e.get('detail') or {}).get('spec') == d.name]
        for event in reversed(events):
            detail = event.get('detail') or {}
            receipt = detail.get('guard_scope') or {}
            recorded_files = receipt.get('files') or {}
            relevant_tasks = {str(x).upper() for x in (detail.get('tasks') or [])} & affected
            if not relevant_tasks:
                continue
            if not set(code) & set(recorded_files):
                return False
            if (float(event.get('ts') or 0) < float(full_ts or 0) or detail.get('ok') is not True
                    or detail.get('stable') is not True or not set(code) <= set(recorded_files)):
                return False
            ids = detail.get('tasks') or []
            current = partial_scope(root, tasks_text, spec_text, ids, status, rules)
            if current != receipt or detail.get('selection_algorithm') != 'aidd-task-selection-v1':
                return False
            if status._task_selection_fingerprint(tasks_text, spec_text, ids) != detail.get('selection_fp_end'):
                return False
            if detail.get('selection_fp_start') != detail.get('selection_fp_end'):
                return False
            if any(_staged_hash(root, path) != recorded_files[path] for path in code):
                return False
            rows = detail.get('results') or []
            expected = {n for task in current['tasks'].values() for n in task['rows']}
            if not rows or {str(row.get('n')) for row in rows} != expected:
                return False
            for row in rows:
                if (row.get('ok') is not True or not row.get('input_globs') or not row.get('input_fp')
                        or not row.get('environment_id') or not row.get('environment_declaration')):
                    return False
                if rules.row_input_fingerprint(root, row['input_globs']) != row['input_fp']:
                    return False
                if status._contract_environment_id(row['cmd'], row['environment_declaration']) != row['environment_id']:
                    return False
                relative = str(row.get('evidence') or '')
                target = (d / relative).resolve(strict=True)
                target.relative_to((d / 'evidence').resolve(strict=True))
                if hashlib.sha1(target.read_bytes()).hexdigest() != row.get('sha1'):
                    return False
            return True
        return False
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        return False


def _latest_partial_failure(root, d, code, evidence):
    """A newer failed relevant partial must supersede any earlier PASS."""
    try:
        pending_dir = d / 'evidence'
        staged_ids = {hashlib.sha256(('aidd-provider-target-v1\0' + path).encode('utf-8')).hexdigest()
                      for path in code}
        if pending_dir.exists():
            if pending_dir.is_symlink():
                return float('inf')
            for marker in pending_dir.glob('provider-*.pending'):
                if marker.is_symlink() or marker.stat().st_size > 1024 * 1024:
                    return float('inf')
                data = json.loads(marker.read_text(encoding='utf-8'))
                values = data.get('targets') if isinstance(data, dict) else None
                if (not isinstance(data, dict) or data.get('format') != 'aidd-provider-pending-v1'
                        or data.get('spec') != d.name or not isinstance(values, list) or not values
                        or any(not isinstance(item, str) or not re.fullmatch(r'[0-9a-f]{64}', item) for item in values)):
                    return float('inf')
                if set(values) & staged_ids:
                    return float('inf')
        owners = _task_owners(_read_small(d / 'tasks.md') or '')
        affected = {task for task, paths in owners.items() if set(paths) & set(code)}
        latest = 0.0
        provider_events = evidence.events(root, kind='provider_verify_run')
        for event in provider_events:
            detail = event.get('detail') or {}
            tasks = detail.get('tasks') or {}
            if detail.get('spec') != d.name:
                continue
            if not isinstance(tasks, dict):
                return float('inf')
            for task_id, task in tasks.items():
                if isinstance(task, dict) and set(task.get('targets') or []) & set(code):
                    affected.add(str(task_id).upper())
        for event in evidence.events(root, kind='task_verify_run'):
            detail = event.get('detail') or {}
            if (detail.get('spec') == d.name and detail.get('ok') is False
                    and affected & {str(task).upper() for task in detail.get('tasks') or []}):
                latest = max(latest, float(event.get('ts') or 0))
        for event in provider_events:
            detail = event.get('detail') or {}
            tasks = detail.get('tasks') or {}
            if not isinstance(tasks, dict):
                return float('inf')
            targets = {path for item in tasks.values() if isinstance(item, dict) for path in item.get('targets') or []}
            if detail.get('spec') == d.name and detail.get('outcome') != 'PASS' and not targets:
                return float('inf')
            if detail.get('spec') == d.name and detail.get('outcome') != 'PASS' and targets & set(code):
                latest = max(latest, float(event.get('ts') or 0))
        return latest + 0.001 if latest else 0.0
    except (OSError, ValueError, TypeError, UnicodeError):
        return float('inf')


def _provider_partial_passes(root, d, code, evidence, full_ts):
    try:
        try:
            from . import aidd_provider_attestation as provider
        except ImportError:
            import aidd_provider_attestation as provider
        events = evidence.events(root, kind='provider_verify_run')
        for event in reversed(events):
            detail = event.get('detail') or {}
            tasks = detail.get('tasks') or {}
            if not isinstance(tasks, dict):
                return False
            targets = {path for item in tasks.values() if isinstance(item, dict) for path in item.get('targets') or []}
            if detail.get('spec') != d.name or not targets & set(code):
                continue
            if detail.get('outcome') != 'PASS' or float(event.get('ts') or 0) < float(full_ts or 0):
                return False
            approve = provider.unit_approval_verifier(root, detail['coverage_path'], detail['policy_path'], evidence)
            return provider.evaluate_event(root, event, code, approve)['eligible'] is True
        return False
    except (OSError, ValueError, TypeError, KeyError, ImportError):
        return False


def _owning_specs(root, code):
    """[(spec_dir, [staged code files it owns])] over the OPEN specs; the gate target with every staged
    code file when no open spec owns any; [] when neither applies."""
    ev, _status, rules = _libs3()
    root = Path(root)
    owners = []
    for spec in _safe_list(lambda: ev.open_specs(root)):
        d = root / 'specs' / str(spec)
        text = _read_small(d / 'tasks.md')
        if not text:
            continue
        targets = set(_target_files(text))
        mine = [f for f in code if _owns(targets, _norm_path(f), rules)]
        if mine:
            owners.append((d, mine))
    if owners:
        return owners
    d = _gate_dir(root, ev)
    return [(d, list(code))] if d is not None else []


def _light_verification(root, d, ev, rules):
    """{'status': never-run|failed|stale, 'ts'} from the newest verify_run alone (no fingerprint): any
    run that did not fail counts as 'stale', so it blocks only when a staged file is newer than it."""
    run = ev.latest_verify_run(root, d.name)
    if not run:
        return {'status': 'never-run', 'ts': None}
    res = run.get('results') or []
    rows_ok = bool(res) and all(isinstance(r, dict) and r.get('ok') is True for r in res)
    changed = [str(x) for x in (run.get('code_changed') or [])]
    explained = False
    if changed and rows_ok:                 # outputs the run rewrote, declared `Generated:` (as _run_problems)
        gen = rules.verification_generated(_read_small(d / 'spec.md') or '')
        explained = all(rules._glob_hit(c, gen) for c in changed)
    failed = not res or (run.get('ok') is not True and not explained)
    return {'status': 'failed' if failed else 'stale', 'ts': run.get('ts')}


def _light_status(root, d, ev, rules, approved):
    """Ledger-shaped dict of ONE spec from its files and three evidence facts (approval hash and its
    recorded `approved` event, the newest verify_run, chain order). No build_status, no graph."""
    tasks_p = d / 'tasks.md'
    status = {'spec': d.name, 'why_blocked': []}
    if not tasks_p.exists():
        ap = 'no-tasks'
    else:
        text = _read_small(tasks_p)
        if text is None:
            return {'spec': d.name, 'unparseable': True}
        if rules.approval_line(text) is None:
            ap = 'pending'
        else:
            ap = 'valid' if rules.approval_valid(text) else 'invalid'
        if not (d / 'plan.md').exists():
            status['why_blocked'].append('R5 tasks.md exists but plan.md does not. → '
                                         'Write plan.md (Step 3) before tasks.md.')
    recorded = False
    if ap == 'valid':
        h = rules.approval_hash(text)
        recorded = any((e.get('detail') or {}).get('spec') == d.name and (e.get('detail') or {}).get('hash') == h
                       for e in approved)
    status['tasks'] = {'approval': ap, 'approval_recorded': recorded}
    status['verification'] = _light_verification(root, d, ev, rules)
    return status


def _guard_mode():
    v = os.environ.get(GUARD_ENV, '').strip().lower()
    return v if v in ('warn', 'off') else 'enforce'


def _record_override(ev, root, mode, rules_hit):
    """guard_override {hook, mode, rules} like rule_gate's rules_override. Best effort, never raises."""
    try:
        ev.append(root, None, 'guard_override', hook='guard', mode=mode, rules=sorted(set(rules_hit)))
    except Exception:
        pass


def _record_error(root, err):
    try:
        ev, _status = _libs()
        ev.append_hook_error(root, None, 'guard', f'{type(err).__name__}: {err}')
    except Exception:
        pass


def _print_findings(findings, label):
    for f in findings:
        print(f"aidd guard: {label} {f['rule']} — {f['message']} -> fix: {f['fix']}")


def _run(action, root, ev):
    mode = _guard_mode()
    if mode == 'off':
        _record_override(ev, root, 'off', [])
        print(f'aidd guard: disabled by {GUARD_ENV}=off (recorded as guard_override).')
        return 0
    files = staged_files(root) if action == 'commit' else _outgoing_files(root)
    code = [f for f in files if is_code_file(f)]
    if not code:
        return 0
    owners = _owning_specs(root, code)
    if not owners:
        print('aidd guard: warning — code is staged but no open spec owns it and there is no gate pointer; '
              'allowed. Run `aidd status` to see the open specs.')
        return 0
    findings = _evaluate_owners(root, owners, allow_partial=action == 'commit')
    if not findings:
        return 0
    if action == 'push' or mode == 'warn':
        _print_findings(findings, 'WARNING')
        if action == 'commit':
            _record_override(ev, root, 'warn', [f['rule'] for f in findings])
            print(f'aidd guard: {GUARD_ENV}=warn — the commit is allowed (recorded as guard_override).')
        return 0
    _print_findings(findings, 'BLOCKED')
    print(f'aidd guard: commit blocked ({len(findings)} finding(s)). Docs/specs-only commits always pass.')
    return 1


def _parse(argv):
    """(action, root_arg) or None on bad usage. Accepts `guard commit|push` and `commit|push`."""
    args = list(argv)
    if args and args[0] == 'guard':
        args = args[1:]
    if not args or args[0] not in ('commit', 'push'):
        return None
    action, rest, root_arg = args[0], args[1:], None
    if rest:
        if len(rest) != 2 or rest[0] != '--root':
            return None
        root_arg = rest[1]
    return action, root_arg


def main(argv=None):
    parsed = _parse(sys.argv[1:] if argv is None else argv)
    if parsed is None:
        print(USAGE)
        return 2
    action, root_arg = parsed
    root = None
    try:
        ev, status = _libs()
        status._sanitize_env()
        root = ev.find_root(Path(root_arg) if root_arg else None)
        return _run(action, root, ev)
    except SystemExit:
        raise
    except Exception as e:
        _record_error(root, e)
        print(f'aidd guard: internal error ({type(e).__name__}); allowed (fail open).')
        return 0


if __name__ == '__main__':
    sys.exit(main())
