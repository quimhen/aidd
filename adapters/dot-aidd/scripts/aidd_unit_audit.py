"""Read-only scoped audit evaluation; never creates or upgrades evidence.

The caller must supply a trusted provenance verifier. Missing provenance or an
incomplete scope is indeterminate, not a passed audit or a mandate to re-audit
unrelated units.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path, PurePosixPath, PureWindowsPath

_HEX = re.compile(r'[0-9a-f]{64}\Z')
_CATEGORIES = frozenset(('paths', 'targets', 'inputs', 'config', 'visual'))
_LEGACY_PATH = re.compile(r'(?<![A-Za-z0-9_./-])(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.[A-Za-z0-9]+')


def _valid_snapshot(value):
    if not isinstance(value, dict) or value.get('format') != 'aidd-unit-impact-v3':
        return False
    if set(value) != {'format', 'unit', 'version', 'sequence', 'files', 'parents', 'visual_refs', 'digest'}:
        return False
    if not isinstance(value.get('unit'), str) or not value['unit'] or not _HEX.fullmatch(str(value.get('digest', ''))):
        return False
    files, parents = value.get('files'), value.get('parents')
    if not isinstance(files, dict) or set(files) != _CATEGORIES or not isinstance(parents, dict):
        return False
    if (not isinstance(value.get('visual_refs'), list) or not isinstance(value.get('version'), str)
            or type(value.get('sequence')) is not int or value['sequence'] <= 0):
        return False
    for mapping in [*files.values(), parents]:
        if not isinstance(mapping, dict):
            return False
        if any(not isinstance(k, str) or not k or not _HEX.fullmatch(str(v)) for k, v in mapping.items()):
            return False
    payload = {k: v for k, v in value.items() if k != 'digest'}
    try:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    except (TypeError, ValueError, UnicodeError):
        return False
    return hashlib.sha256(encoded).hexdigest() == value['digest']


def compare_snapshots(previous, current):
    """List changed declared inputs; invalid or incomparable scope is unknown."""
    if not _valid_snapshot(previous) or not _valid_snapshot(current):
        raise ValueError('incomplete or unsupported snapshot')
    if previous['unit'] != current['unit']:
        raise ValueError('different units')
    changes = []
    if previous['version'] != current['version']:
        changes.append('version')
    for category in sorted(_CATEGORIES):
        a, b = previous['files'][category], current['files'][category]
        changes.extend(f'{category}:{name}' for name in sorted(a.keys() | b.keys()) if a.get(name) != b.get(name))
    a, b = previous['parents'], current['parents']
    changes.extend(f'parent:{name}' for name in sorted(a.keys() | b.keys()) if a.get(name) != b.get(name))
    if previous['visual_refs'] != current['visual_refs']:
        changes.append('visual-context')
    if not changes and previous['digest'] != current['digest']:
        changes.append('snapshot-algorithm-or-metadata')
    return changes


def _report_digest(root, relative):
    """Read an in-project, non-aliased report without trusting caller paths."""
    if not isinstance(relative, str) or not relative or '\\' in relative:
        raise ValueError('invalid report path')
    posix, windows = PurePosixPath(relative), PureWindowsPath(relative)
    if posix.is_absolute() or windows.drive or windows.root or any(x in ('', '.', '..') for x in relative.split('/')):
        raise ValueError('invalid report path')
    base = Path(root).resolve(strict=True)
    candidate = base
    for component in posix.parts:
        candidate = candidate / component
        if candidate.is_symlink():
            raise ValueError('symlink report path')
    path = candidate.resolve(strict=True)
    path.relative_to(base)
    before = path.stat()
    if not path.is_file() or before.st_nlink != 1 or before.st_size > 10 * 1024 * 1024:
        raise ValueError('ambiguous or oversized report')
    data = path.read_bytes()
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError('report changed while reading')
    return hashlib.sha256(data).hexdigest()


def evaluate_audit(root, snapshot, domain, rules_version, environment_id, events, provenance_verifier=None):
    """Evaluate genuine existing unit-audit events without mutating historical evidence.

    A host-owned provenance verifier must authenticate lifecycle, independent
    identities, complete dependency closure and execution context. A manifest
    or self-asserted flag never supplies that proof. Callers without a verifier
    always receive indeterminate.
    """
    if not _valid_snapshot(snapshot) or not domain or not rules_version:
        return {'status': 'indeterminate', 'reason': 'incomplete scope or execution context'}
    candidates = [e for e in events if isinstance(e, dict) and e.get('kind') == 'unit_audit'
                  and isinstance(e.get('detail'), dict) and e['detail'].get('unit') == snapshot['unit']
                  and e['detail'].get('domain') == domain]
    if not candidates:
        return {'status': 'missing', 'reason': 'no recorded unit audit'}
    stale = None
    unknown = 'audit evidence or provenance cannot be verified'
    for event in reversed(candidates):
        detail = event['detail']
        try:
            actor, builders = detail.get('auditor_id'), detail.get('implementer_ids')
            if (not isinstance(actor, str) or not actor or not isinstance(builders, list) or not builders
                    or any(not isinstance(x, str) or not x for x in builders) or actor in builders
                    or not isinstance(detail.get('dispatch_id'), str) or not detail['dispatch_id']):
                unknown = 'independent auditor or implementer identity is unavailable'
                continue
            if provenance_verifier is None:
                unknown = 'trusted provenance verifier is unavailable'
                continue
            proof = provenance_verifier(event)
            if isinstance(proof, dict):
                if proof.get('verified') is not True:
                    unknown = str(proof.get('reason') or 'audit provenance is not verified')
                    continue
            elif proof is not True:
                unknown = 'audit provenance is not verified'
                continue
            try:
                changes = compare_snapshots(detail.get('scope'), snapshot)
            except (ValueError, TypeError):
                return {'status': 'indeterminate', 'reason': 'latest authenticated audit has incomplete scope'}
            if changes:
                stale = {'status': 'stale', 'reason': 'scope changed', 'changes': changes}
                continue
            if detail.get('rules_version') != rules_version:
                stale = {'status': 'stale', 'reason': 'rules or environment changed'}
                continue
            if not environment_id:
                unknown = 'execution environment identity is unavailable'
                continue
            if detail.get('environment_id') != environment_id:
                stale = {'status': 'stale', 'reason': 'rules or environment changed'}
                continue
            want = str(detail.get('report_sha256') or '')
            try:
                intact = bool(_HEX.fullmatch(want)) and _report_digest(root, detail.get('report_path')) == want
            except (OSError, ValueError, TypeError):
                intact = False
            if not intact:
                return {'status': 'indeterminate', 'reason': 'latest authenticated audit report is missing or changed',
                        'dispatch_id': detail['dispatch_id']}
            # The latest authenticated audit of this exact scope is decisive.
            # A failed or missing verdict must never fall back to an older PASS.
            if detail.get('outcome') == 'FAIL':
                return {'status': 'failed', 'reason': 'latest verified audit reported failures',
                        'dispatch_id': detail['dispatch_id']}
            if detail.get('outcome') != 'PASS':
                return {'status': 'indeterminate', 'reason': 'latest verified audit has no explicit PASS verdict',
                        'dispatch_id': detail['dispatch_id']}
            return {'status': 'current', 'reason': 'scope, report and provenance verified',
                    'dispatch_id': detail['dispatch_id']}
        except (OSError, ValueError, TypeError, KeyError):
            continue
        except Exception:
            continue
    return stale or {'status': 'indeterminate', 'reason': unknown}


def codex_provenance(root, event, evidence, identity_attestor=None):
    """Check the host-recorded lifecycle before consulting a trusted assignment attestor.

    SubagentStart/Stop alone do not establish an assigned scope or the identity
    of the code's implementer. Absence of either proof remains indeterminate.
    """
    try:
        detail = event.get('detail') or {}
        session, turn, agent = detail.get('session_id'), detail.get('turn_id'), detail.get('auditor_id')
        if any(not isinstance(value, str) or not value for value in (session, turn, agent)):
            return {'verified': False, 'reason': 'audit session, turn or agent is missing'}
        rows = evidence.events(root, session=session, kind='codex_subagent')
        matched = [row for row in rows if (row.get('detail') or {}).get('turn_id') == turn
                   and (row.get('detail') or {}).get('agent_id') == agent]
        starts = [row for row in matched if row['detail'].get('phase') == 'start']
        stops = [row for row in matched if row['detail'].get('phase') == 'stop']
        if len(starts) != 1 or len(stops) != 1:
            return {'verified': False, 'reason': 'auditor lifecycle is missing or ambiguous'}
        start, stop = starts[0], stops[0]
        sd, ed = start['detail'], stop['detail']
        if (sd.get('agent_type') != ed.get('agent_type') or ed.get('continued') is True
                or float(stop.get('ts', 0)) <= float(start.get('ts', 0))
                or ed.get('result_sha256') != detail.get('report_sha256')):
            return {'verified': False, 'reason': 'auditor result does not match completed lifecycle'}
        if identity_attestor is None or identity_attestor(event, start, stop) is not True:
            return {'verified': False, 'reason': 'scope assignment and implementer identity are not verified by the host'}
        return {'verified': True, 'reason': 'host lifecycle and assignment verified'}
    except (OSError, TypeError, ValueError, KeyError):
        return {'verified': False, 'reason': 'host lifecycle is unreadable'}


def review_environment():
    """Identity of the locally trusted runner, Codex executable and configuration."""
    exe = shutil.which('codex')
    if not exe:
        raise ValueError('codex executable unavailable')
    executable = Path(exe).resolve(strict=True)
    config = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'config.toml'
    values = [hashlib.sha256(executable.read_bytes()).hexdigest(),
              hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              hashlib.sha256(config.read_bytes()).hexdigest() if config.is_file() else 'no-config']
    return executable, hashlib.sha256('\n'.join(values).encode()).hexdigest()


def local_runner_provenance(root, event):
    """Trust boundary: this machine and the AIDD runner, not a Codex hook.

    The runner records its actual fresh child process and captured output. This
    is local operational evidence, not protection against a hostile local user
    able to rewrite the event log or replace the runner.
    """
    d = event.get('detail') or {}
    receipt = d.get('runner') or {}
    try:
        if (receipt.get('provider') != 'aidd-local-codex-v1'
                or receipt.get('checkout') != str(Path(root).resolve(strict=True))
                or receipt.get('sandbox') != 'read-only' or receipt.get('exit_code') != 0
                or type(receipt.get('pid')) is not int or receipt['pid'] <= 0
                or type(receipt.get('parent_pid')) is not int or receipt['pid'] == receipt['parent_pid']
                or not receipt.get('thread_id') or receipt['thread_id'] != d.get('auditor_id')
                or not receipt.get('git_head') or receipt.get('scope_digest') != d.get('scope', {}).get('digest')):
            return {'verified': False, 'reason': 'local reviewer receipt incomplete'}
        return {'verified': True, 'reason': 'trusted local runner captured a separate Codex review'}
    except (OSError, ValueError, TypeError, KeyError):
        return {'verified': False, 'reason': 'local reviewer report is unreadable'}


def run_unit_review(root, unit, domains, units, evidence, *, executable=None, environment_id=None):
    """Run ONE fresh read-only reviewer for affected domains and record its real result."""
    root = Path(root).resolve(strict=True)
    if executable is None or environment_id is None:
        executable, environment_id = review_environment()
    before = units.unit_impact_snapshot(unit, root)
    git = ['git', '-C', str(root), 'rev-parse']
    checkout = subprocess.check_output(git + ['--show-toplevel'], text=True).strip()
    if Path(checkout).resolve(strict=True) != root:
        raise ValueError('project root is not the Git checkout root')
    head = subprocess.check_output(git + ['HEAD'], text=True).strip()
    closure = units.discover_unit_scope(root, unit.spec_id, [unit.key])
    paths = sorted({path for item in closure for path in
                    (*item.paths, *item.targets, *item.inputs, *item.config,
                     *(ref.source for ref in item.visual_refs),
                     *(asset for ref in item.visual_refs for asset in ref.assets))})
    prompt = ('Independently review only this AIDD unit and its declared dependency closure. '
              'Do not modify files or run tests. Inspect the listed files and their relevant relationships. '
              'Assess each requested domain. Return ONLY JSON with keys verdicts and findings; '
              'verdicts must map each requested domain to PASS or FAIL. If evidence is incomplete, '
              'use FAIL and describe the gap. For visual fidelity, a PASS requires real screen capture '
              'and comparison evidence; source inspection alone is insufficient. Do not invent executed checks.\n'
              + json.dumps({'unit': unit.key, 'scope_digest': before['digest'], 'paths': paths,
                            'parents': before['parents'], 'domains': domains}, ensure_ascii=False))
    cmd = [str(executable), 'exec', '--ephemeral', '--sandbox', 'read-only', '--json', '-C', str(root), '-']
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding='utf-8', errors='replace')
    try:
        output, error = process.communicate(prompt, timeout=3600)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise ValueError('review process timed out; no receipt recorded')
    if process.returncode != 0:
        raise ValueError('review process failed: ' + error[-1000:])
    thread = None
    message = None
    completed = False
    for line in output.splitlines():
        row = json.loads(line)
        if row.get('type') == 'thread.started':
            if thread is not None:
                raise ValueError('ambiguous reviewer thread')
            thread = row.get('thread_id')
        if row.get('type') == 'item.completed' and (row.get('item') or {}).get('type') == 'agent_message':
            message = row['item'].get('text')
        if row.get('type') == 'turn.completed':
            completed = True
    if not thread or not completed or not message or process.pid == os.getpid():
        raise ValueError('reviewer did not produce a completed independent result')
    result = json.loads(message)
    verdicts = result.get('verdicts') if isinstance(result, dict) else None
    if (not isinstance(verdicts, dict) or set(verdicts) != set(domains)
            or any(value not in ('PASS', 'FAIL') for value in verdicts.values())
            or not isinstance(result.get('findings'), (str, list))):
        raise ValueError('reviewer verdict is incomplete or invalid')
    if units.unit_impact_snapshot(unit, root) != before or subprocess.check_output(git + ['HEAD'], text=True).strip() != head:
        raise ValueError('scope or Git HEAD changed during review; no receipt recorded')
    dispatch = uuid.uuid4().hex
    report_dir = root / 'specs' / unit.spec_id / 'audit-reports'
    for ancestor in (root / 'specs', root / 'specs' / unit.spec_id, report_dir):
        if ancestor.is_symlink():
            raise ValueError('symlink in report directory')
    report_dir.mkdir(parents=True, exist_ok=True)
    report = report_dir / (dispatch + '.json')
    captured = {'thread_id': thread, 'scope_digest': before['digest'], 'verdicts': verdicts,
                'findings': result['findings'], 'reviewer_output': message}
    report.write_text(json.dumps(captured, ensure_ascii=False, sort_keys=True), encoding='utf-8')
    relative = report.relative_to(root).as_posix()
    digest = _report_digest(root, relative)
    receipt = {'provider': 'aidd-local-codex-v1', 'checkout': str(root), 'sandbox': 'read-only',
               'pid': process.pid, 'parent_pid': os.getpid(), 'exit_code': process.returncode,
               'thread_id': thread, 'git_head': head, 'scope_digest': before['digest']}
    for domain in domains:
        if not evidence.append(root, dispatch, 'unit_audit', unit=unit.key, domain=domain, scope=before,
                rules_version='unit-audit-v1', environment_id=environment_id, report_path=relative,
                report_sha256=digest, auditor_id=thread, implementer_ids=['runner-parent:' + str(os.getpid())],
                dispatch_id=dispatch, outcome=verdicts[domain], runner=receipt):
            raise ValueError('could not record reviewer evidence for ' + domain)
    return {'dispatch_id': dispatch, 'report_path': relative, 'verdicts': verdicts}


def domains_for_unit(unit, rules, spec_dir):
    """Classify only this unit's declared targets and explicit visual references.

    Explicit spec overrides are retained. This is an impact suggestion, not a
    substitute for an auditor's assessment of the declared dependency closure.
    """
    # Preserve the existing R7 minimum for every unit, even when its file
    # names do not identify an explicitly security-sensitive surface.
    domains = {'functional', 'security'}
    declared = set(unit.targets) | set(getattr(unit, 'inputs', ())) | set(getattr(unit, 'config', ()))
    for path in declared:
        name = '/' + path.lower().replace('\\', '/')
        if rules._IMPACT_UI_RE.search(name):
            domains.add('ui')
        if rules._IMPACT_BACKEND_RE.search(name):
            domains.add('backend')
        if rules._IMPACT_DB_RE.search(name):
            domains.add('database')
        if rules._IMPACT_SECURITY_RE.search(name):
            domains.add('security')
    if unit.visual_refs:
        domains.add('ui')
    if 'database' in domains or 'ui' in domains:
        domains.add('performance')
    override = rules.audit_domains_override((Path(spec_dir) / 'spec.md').read_text(encoding='utf-8'))
    if override:
        domains.update(override)
    return sorted(domains)


def _path_key(value):
    # Conservative across Windows and case-insensitive mounts; an ambiguous
    # spelling may select an extra task but never hide a potentially affected one.
    return str(value).replace('\\', '/').casefold()


def _task_candidates(changed_paths, spec_id):
    prefix = _path_key(f'specs/{spec_id}/')
    return [path for path in changed_paths if _path_key(path).startswith(prefix)]


def resolve_base(root, base):
    """aidd:FR-261 the full commit hash Git resolves `base` to (`HEAD~1`, a branch, a short hash ...).
    Refuses (ValueError) an empty, option-like, over-long or whitespace/NUL-bearing value and anything Git cannot
    resolve to exactly one commit."""
    message = 'base is not a uniquely resolvable commit'
    if (not isinstance(base, str) or not base or len(base) > 256 or base.startswith('-')
            or '\x00' in base or any(ch.isspace() for ch in base)):
        raise ValueError(message)
    try:
        check = subprocess.run(['git', 'rev-parse', '--verify', '--end-of-options', base + '^{commit}'],
                               cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               stdin=subprocess.DEVNULL, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        raise ValueError(message) from exc
    out = check.stdout.strip()
    if check.returncode or not re.fullmatch(rb'[0-9a-f]{40}|[0-9a-f]{64}', out):
        raise ValueError(message)
    return out.decode('ascii')


def git_changed_paths(root, base=None):
    """Use Git's NUL-delimited staged, unstaged and untracked paths, not file scans."""
    def run_git(cmd):
        try:
            return subprocess.run(cmd, cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  stdin=subprocess.DEVNULL, timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError('Git changed-path query unavailable or timed out') from exc
    commands = []
    if base is not None:
        resolved = resolve_base(root, base)
        commands.append(['git', 'diff', '--no-ext-diff', '--no-renames', '--name-only', '-z', resolved, 'HEAD', '--'])
    commands.extend((['git', 'diff', '--no-ext-diff', '--no-renames', '--name-only', '-z', '--'],
                     ['git', 'diff', '--cached', '--no-ext-diff', '--no-renames', '--name-only', '-z', '--'],
                     ['git', 'ls-files', '--others', '--exclude-standard', '-z', '--']))
    changed = set()
    for cmd in commands:
        result = run_git(cmd)
        if result.returncode:
            raise ValueError('Git could not determine changed paths')
        for raw in result.stdout.split(b'\0'):
            if not raw:
                continue
            name = os.fsdecode(raw).replace('\\', '/')
            if (not name or PurePosixPath(name).is_absolute() or PureWindowsPath(name).drive
                    or any(part in ('', '.', '..') for part in name.split('/'))):
                raise ValueError('Git returned an unsafe changed path')
            changed.add(name)
    return sorted(changed)


def administrative_only_task_paths(root, changed_paths, rules, base=None):
    """Identify task writeback with equal base/index/worktree semantics.

    This only filters a provisional Git impact view. It never attests an audit
    baseline or a seal, and refuses missing, unreadable or aliased versions.
    """
    task_path = re.compile(r'^specs/[A-Za-z0-9_-]+/(?:amendments/[A-Za-z0-9_-]+/)?'
                           r'tasks(?:-[A-Za-z0-9_-]+)?\.md$', re.I)
    if base is not None:
        try:
            base = resolve_base(root, base)
        except ValueError:
            return set()          # an unresolvable base hides nothing (conservative, as before FR-261)
    base_ref = base or 'HEAD'
    root = Path(root).resolve(strict=True)
    result = set()

    def git_blob(revision):
        try:
            size = subprocess.run(['git', 'cat-file', '-s', revision], cwd=str(root), stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, timeout=30, check=False)
            if size.returncode or not size.stdout.strip().isdigit() or int(size.stdout) > rules.MAX_CHARS * 4:
                return None
            data = subprocess.run(['git', 'cat-file', 'blob', revision], cwd=str(root), stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, timeout=30, check=False)
            return data.stdout if data.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            return None

    for name in changed_paths:
        if not task_path.fullmatch(name):
            continue
        try:
            candidate = root
            for part in PurePosixPath(name).parts:
                candidate = candidate / part
                attributes = getattr(candidate.lstat(), 'st_file_attributes', 0)
                if candidate.is_symlink() or attributes & 0x400:
                    raise ValueError('ambiguous filesystem alias')
            candidate.resolve(strict=True).relative_to(root)
            before = candidate.stat()
            if before.st_size > rules.MAX_CHARS * 4:
                continue
            versions = [git_blob(base_ref + ':' + name), git_blob(':' + name), candidate.read_bytes()]
            if any(data is None for data in versions):
                continue
            after = candidate.stat()
            if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                    != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                    or candidate.read_bytes() != versions[2]
                    or git_blob(base_ref + ':' + name) != versions[0]
                    or git_blob(':' + name) != versions[1]):
                continue
            texts = [data.decode('utf-8') for data in versions]
            projections = [rules.approval_projection(text) for text in texts]
            if any(projection is None for projection in projections) or len(set(projections)) != 1:
                continue
            # Approval lines are deliberately excluded from the projection but
            # changing a seal is not a Status/Tracker writeback.
            approval_lines = [tuple(line.strip() for line in text.splitlines()
                                    if rules._APPROVED_LINE_RE.match(line.rstrip())) for text in texts]
            if len(set(approval_lines)) == 1:
                result.add(name)
        except (OSError, UnicodeError, ValueError, RuntimeError):
            continue
    return result


def legacy_task_map(root, spec_dir, rules, task_id=None, changed_paths=None):
    """Read-only task/target inventory; never turn a legacy audit into a unit seal.

    The current hashes are a proposed baseline only. Existing task rows cannot
    prove historical dependency closure or which bytes an auditor reviewed.
    """
    root = Path(root).resolve(strict=True)
    spec = Path(spec_dir).resolve(strict=True)
    spec.relative_to((root / 'specs').resolve(strict=True))
    text = (spec / 'tasks.md').read_text(encoding='utf-8')
    rows, column, cache = {}, None, {}

    def target_names(cell):
        cell = cell.replace('\\', '/')
        quoted = re.findall(r'`([^`\n]+)`', cell)
        names = []
        for item in quoted:
            if ('/' in item or '.' in item) and not any(c.isspace() for c in item):
                names.append(item)
            else:
                names.extend(_LEGACY_PATH.findall(item))
        if not quoted:
            names.extend(_LEGACY_PATH.findall(cell))
        return sorted(set(name.strip() for name in names if name.strip()))

    # Only a task's own `Files to change` block adds targets. Do not extract
    # paths from Read first, Verify, Do NOT or other tasks' prose.
    detail_targets = {}
    headings = list(re.finditer(r'(?m)^#{1,3}\s+([^\r\n]+)', text))
    for index, heading in enumerate(headings):
        match = re.match(r'(T-\d+)\b', heading.group(1), re.I)
        if not match:
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        block = text[heading.end():end]
        declarations = re.findall(r'(?im)^\s*[-*]\s*(?:\*\*)?Files to change(?::\*\*|\*\*:|:)\s*(.*)$', block)
        if declarations:
            ident = match.group(1).upper()
            detail_targets.setdefault(ident, []).append(sorted(set(
                name for declaration in declarations for name in target_names(declaration))))

    def observed(name):
        if name in cache:
            return cache[name]
        try:
            win, posix = PureWindowsPath(name), PurePosixPath(name)
            if (not name or '\\' in name or win.drive or win.root or posix.is_absolute()
                    or any(part in ('', '.', '..') for part in name.split('/'))):
                raise ValueError('unsafe path')
            low = posix.name.lower()
            if low == '.env' or low.startswith('.env.') or low.endswith(('.pem', '.key', '.p12', '.pfx')):
                raise ValueError('sensitive target not fingerprinted')
            candidate = root
            for part in posix.parts:
                candidate = candidate / part
                attributes = getattr(candidate.lstat(), 'st_file_attributes', 0)
                if candidate.is_symlink() or attributes & 0x400:
                    raise ValueError('target uses an ambiguous filesystem alias')
            path = candidate.resolve(strict=True)
            path.relative_to(root)
            before = path.stat()
            if not path.is_file() or before.st_nlink != 1:
                raise ValueError('not a regular unambiguous file')
            def hash_file():
                digest = hashlib.sha256()
                with path.open('rb') as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b''):
                        digest.update(chunk)
                return digest.hexdigest()
            first = hash_file()
            second = hash_file()
            after = path.stat()
            if first != second or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                    after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
                raise ValueError('target changed while fingerprinting')
            cache[name] = {'sha256': first}
        except (OSError, ValueError, RuntimeError) as exc:
            cache[name] = {'status': 'indeterminate', 'reason': str(exc)}
        return cache[name]

    for line in rules._clean(text).splitlines():
        if not line.strip().startswith('|'):
            column = None
            continue
        cells = rules._split_row(line)
        headers = [re.sub(r'[`*_]', '', cell).strip().lower() for cell in cells]
        if 'target file' in headers:
            column = headers.index('target file')
            continue
        if column is None or not cells or column >= len(cells) or rules._is_sep(cells):
            continue
        match = re.fullmatch(r'[`*\s]*(T-\d+)[`*\s]*', cells[0], re.I)
        if not match:
            continue
        ident = match.group(1).upper()
        if task_id and ident != task_id.upper():
            continue
        names = set(target_names(cells[column]))
        declarations = detail_targets.get(ident, [])
        for declaration in declarations:
            names.update(declaration)
        names = sorted(names)
        if changed_paths is not None and not any(_path_key(name) in changed_paths for name in names):
            continue
        row = {'task': ident, 'targets': {name: observed(name) for name in names},
               'status': 'indeterminate',
               'reason': 'historical task audit, transitive dependencies and environment are not attested'}
        if ident in rows:
            row['reason'] = 'task occurs in multiple tables; attribution is ambiguous'
            row['targets'].update(rows[ident]['targets'])
        elif len({tuple(item) for item in declarations}) > 1:
            row['reason'] = 'task has conflicting Files to change blocks; attribution is ambiguous'
        rows[ident] = row
    return [rows[key] for key in sorted(rows, key=lambda value: int(value[2:]))]


def plan_impact(root, spec_id, events, rules, units_module, *, rules_version='unit-audit-v1',
                environment_id=None, provenance_verifier=None, task_id=None, changed_paths=None, base=None):
    """Build a read-only unit/domain plan; unchanged units never trigger a full spec audit."""
    root = Path(root).resolve(strict=True)
    if not isinstance(spec_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', spec_id):
        raise ValueError('invalid spec identifier')
    spec = (root / 'specs' / spec_id).resolve(strict=True)
    spec.relative_to(root / 'specs')
    changed = {_path_key(path) for path in changed_paths} if changed_paths is not None else None
    changed_info = None if changed is None else {
        'basis': ('user-supplied commit vs HEAD plus worktree/index and untracked; not an authenticated audit baseline'
                  if base else 'provisional worktree/index vs HEAD and untracked; not an audit baseline'),
        'base': base, 'committed_since_audit': 'unknown', 'paths': [],
        'other_changed_count': len(changed_paths), 'complete': False}
    metadata = {f'specs/{spec_id}/{name}' for name in ('spec.md', 'tasks.md', 'plan.md', 'contracts.md', 'mockup-audit.md')}
    changed_metadata = [path for path in (changed_paths or []) if _path_key(path) in {_path_key(x) for x in metadata}]
    unmapped = [path + ' changed; task-level attribution is unknown' for path in changed_metadata]
    entries = []
    if hasattr(units_module, 'list_spec_unit_keys'):
        keys = units_module.list_spec_unit_keys(root, spec_id)
        for key in keys:
            manifest = spec / 'amendments' / key.split(':', 1)[1] / 'manifest.json'
            try:
                entries.append((key, units_module.load_unit(manifest, root), None))
            except (OSError, ValueError) as exc:
                entries.append((key, None, str(exc)))
    else:
        entries = [(u.key, u, None) for u in units_module.discover_units(root) if u.spec_id == spec_id]
    if not entries:
        # A changed spec artifact cannot be assigned safely to a particular
        # task without an authenticated prior snapshot; still show changed
        # code targets that can be mapped, without hashing unrelated targets.
        legacy = legacy_task_map(root, spec, rules, task_id, changed)
        if changed_info is not None:
            related = {_path_key(name) for row in legacy for name in row['targets']} | {_path_key(x) for x in changed_metadata}
            changed_info['paths'] = [path for path in changed_paths if _path_key(path) in related]
            changed_info['other_changed_count'] = len(changed_paths) - len(changed_info['paths'])
        return {'spec': spec_id, 'mode': 'legacy', 'units': [], 'changed': changed_info,
                'legacy_tasks': legacy, 'unmapped_changes': unmapped,
                'note': 'current targets are a proposed baseline, not historical audit evidence; existing rules remain in force'}
    if changed is not None:
        filtered = []
        related = {_path_key(x) for x in changed_metadata}
        for key, unit, entry_error in entries:
            if entry_error:
                filtered.append((key, unit, entry_error))
                continue
            try:
                closure = units_module.discover_unit_scope(root, spec_id, [key])
                relevant = set()
                for item in closure:
                    relevant.update(item.paths)
                    relevant.update(item.targets)
                    relevant.update(item.inputs)
                    relevant.update(item.config)
                    relevant.add(f'specs/{item.spec_id}/amendments/{item.unit_id}/manifest.json')
                    for visual in item.visual_refs:
                        relevant.add(visual.source)
                        relevant.update(visual.assets)
                if any(_path_key(path) in changed for path in relevant):
                    related.update(_path_key(path) for path in relevant)
                    filtered.append((key, unit, entry_error))
            except (OSError, ValueError, TypeError) as exc:
                filtered.append((key, None, 'unit relation cannot be proven: ' + str(exc)))
        entries = filtered
        changed_info['paths'] = [path for path in changed_paths if _path_key(path) in related]
        changed_info['other_changed_count'] = len(changed_paths) - len(changed_info['paths'])
    result = []
    batch_fn = getattr(units_module, 'unit_impact_snapshots', None)
    batch = batch_fn(root, [key for key, unit, _ in entries if unit is not None]) if callable(batch_fn) else None
    for key, unit, entry_error in entries:
        entry = {'unit': key}
        try:
            if entry_error:
                raise ValueError(entry_error)
            if batch is None:
                snapshot = units_module.unit_impact_snapshot(unit, root)
            else:
                error = batch['errors'].get(key)
                if error:
                    raise ValueError(error)
                snapshot = batch['snapshots'][key]
            entry['scope_digest'] = snapshot['digest']
            entry['domains'] = {domain: evaluate_audit(root, snapshot, domain, rules_version,
                                                       environment_id, events, provenance_verifier)
                                for domain in domains_for_unit(unit, rules, spec)}
        except (OSError, ValueError, TypeError, KeyError) as exc:
            entry['status'] = 'indeterminate'
            entry['reason'] = str(exc)
        result.append(entry)
    return {'spec': spec_id, 'mode': 'units', 'units': result, 'changed': changed_info,
            'unmapped_changes': unmapped,
            'note': 'no evidence was created; unknown provenance does not authorize close'}


def resolve_spec_id(root, spec_arg):
    """Accept an ID or a direct in-project spec path; reject traversal and nesting."""
    base = Path(root).resolve(strict=True)
    specs = (base / 'specs').resolve(strict=True)
    argument = Path(spec_arg)
    if len(argument.parts) == 1 and _ID_SPEC.fullmatch(str(spec_arg)):
        candidate = specs / str(spec_arg)
    else:
        candidate = argument if argument.is_absolute() else base / argument
    resolved = candidate.resolve(strict=True)
    relative = resolved.relative_to(specs)
    if len(relative.parts) != 1 or not resolved.is_dir() or not _ID_SPEC.fullmatch(relative.name):
        raise ValueError('spec must be a direct project spec directory')
    return relative.name


_ID_SPEC = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]*\Z')


def main(argv=None):
    """aidd impact <spec-id> [--json]: inspect unit audit impact without running audits."""
    import argparse
    try:
        from . import aidd_evidence as ev, aidd_rules as rules, aidd_units as units
    except ImportError:
        import aidd_evidence as ev
        import aidd_rules as rules
        import aidd_units as units
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('spec_id')
    parser.add_argument('--root', default='.')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--task', help='restrict the legacy inventory to one task ID')
    parser.add_argument('--changed', action='store_true', help='show only working tree changes (provisional, not an audit baseline)')
    parser.add_argument('--base', help='compare a commit hash with HEAD as well (not proof of an audit baseline)')
    parser.add_argument('--run-review', metavar='UNIT', help='launch one fresh independent Codex review for this unit')
    args = parser.parse_args(argv)
    try:
        root = ev.find_root(Path(args.root).resolve())
        if root is None:
            raise ValueError('project root not found')
        try:
            executable, environment_id = review_environment()
        except (OSError, ValueError):
            executable, environment_id = None, None
        verifier = lambda event: (local_runner_provenance(root, event)
                                  if (event.get('detail') or {}).get('runner', {}).get('provider') == 'aidd-local-codex-v1'
                                  else codex_provenance(root, event, ev))
        spec_id = resolve_spec_id(root, args.spec_id)
        if args.run_review:
            if not executable or not environment_id:
                raise ValueError('Codex executable and environment identity are required for review')
            key = spec_id + ':' + args.run_review
            if key not in units.list_spec_unit_keys(root, spec_id):
                raise ValueError('unit not found')
            unit = units.load_unit(root / 'specs' / spec_id / 'amendments' / args.run_review / 'manifest.json', root)
            snapshot = units.unit_impact_snapshot(unit, root)
            rows = ev.events(root, kind='unit_audit')
            domains = [domain for domain in domains_for_unit(unit, rules, root / 'specs' / spec_id)
                       if evaluate_audit(root, snapshot, domain, 'unit-audit-v1', environment_id, rows, verifier)['status'] != 'current']
            review = run_unit_review(root, unit, domains, units, ev, executable=executable, environment_id=environment_id) if domains else {'note': 'all unit domains already have current audit evidence'}
            print(json.dumps(review, ensure_ascii=False, sort_keys=True))
            return 1 if 'FAIL' in review.get('verdicts', {}).values() else 0
        if args.task and not re.fullmatch(r'T-\d+', args.task, re.I):
            raise ValueError('invalid task ID')
        changed_paths = git_changed_paths(root, args.base) if args.changed or args.base else None
        # Never open another spec's tasks file just because Git reports it as
        # changed. Cross-spec parents remain conservatively affected until a
        # proven per-parent baseline is available.
        task_candidates = _task_candidates(changed_paths, spec_id) if changed_paths is not None else []
        administrative = (administrative_only_task_paths(root, task_candidates, rules, args.base)
                          if changed_paths is not None else set())
        effective_paths = [path for path in changed_paths if path not in administrative] if changed_paths is not None else None
        plan = plan_impact(root, spec_id, ev.events(root, kind='unit_audit'), rules, units,
                           environment_id=environment_id, provenance_verifier=verifier, task_id=args.task, changed_paths=effective_paths, base=args.base)
        if plan.get('changed') is not None:
            plan['changed']['administrative_only'] = sorted(administrative)
        if args.json:
            print(json.dumps(plan, ensure_ascii=False, sort_keys=True))
        else:
            print(f"{plan['spec']}: {plan['mode']} — {plan['note']}")
            if plan.get('changed'):
                print('  Provisional Git changes only; committed changes since the last audit are unknown.')
            for item in plan.get('unmapped_changes', []):
                print('  indeterminate:', item)
            for item in plan['units']:
                print(f"  {item['unit']}: {item.get('status', 'scope ' + item.get('scope_digest', '')[:12])}")
                for domain, result in item.get('domains', {}).items():
                    print(f"    {domain}: {result['status']} — {result['reason']}")
            legacy = plan.get('legacy_tasks', [])
            for item in legacy[:25]:
                print(f"  {item['task']}: {item['status']} ({len(item['targets'])} named target(s)) — {item['reason']}")
            if len(legacy) > 25:
                print(f'  ... {len(legacy) - 25} further tasks; use --task or --json for detail')
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(f'impact unavailable: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
