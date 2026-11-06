#!/usr/bin/env python3
"""aidd pending — script prefilter for task orchestration (rule E1).

Reads a spec's tasks.md AND its batch files (`tasks-<name>.md`, the same combined text the approval hash
covers), checks which Target files already exist on disk, and prints done / pending / unverified / unknown
tasks plus the pending ones grouped into lanes (one lane per top-level target folder = one owner agent).
Zero LLM tokens: an orchestrator runs this BEFORE launching any agent, so no agent is spent only to
discover "already done".

aidd:FR-441 An existing Target proves nothing when the file is SHARED or PRE-EXISTING (a router, an index,
a config edited by several tasks): such a task is reported `unverified` (never `done`) when its target is
cited by another task, its Status cell says it is not done, or git shows the file existed before the spec.

Usage:
    python aidd_pending.py <spec_dir|tasks.md> [--root DIR] [--json]
Exit 0 always (informational); 2 on usage error.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import aidd_progress as _progress  # noqa: E402  (same path rules as `aidd progress`, so both agree)

_BATCH_FILE_RE = re.compile(r'tasks-[A-Za-z0-9_-]+\.md')


def parse(text):
    """[(task_id, [target paths])] for every table with a 'Target file' column. Uses aidd_progress.parse_tasks:
    the spec's declared path shorthand (`ENG/` = `real/prefix/`) is expanded, a trailing `(same owner as T-nn)` /
    `(new)` is ignored and a cell with several paths lists them all."""
    return [(t['id'], t['paths'], t) for t in _progress.parse_tasks(text)]


def read_combined(spec_dir):
    """(combined text, [file names read]) of tasks.md + its `tasks-<name>.md` batch files (aidd_rules.with_batches
    when available, else the same combination by hand)."""
    d = Path(spec_dir)
    base = (d / 'tasks.md').read_text(encoding='utf-8') if (d / 'tasks.md').is_file() else ''
    try:
        names = sorted(p.name for p in d.iterdir() if _BATCH_FILE_RE.fullmatch(p.name) and p.is_file())
    except OSError:
        names = []
    try:
        import aidd_rules
        return aidd_rules.with_batches(d, base), ['tasks.md'] + names
    except Exception:
        out = base
        for n in names:
            out += ('' if out.endswith('\n') else '\n') + f'\n<!-- aidd-batch: {n} -->\n' + (d / n).read_text(encoding='utf-8')
        return out, ['tasks.md'] + names


def classify(tasks, root):
    """done = every target exists; pending = a target is missing; unknown = no path in the Target cell."""
    done, pending, unknown = [], [], []
    for tid, paths, task in tasks:
        state = _progress.task_state(task, root)
        if state == 'n/a':
            unknown.append(tid)
        elif state == 'missing':
            pending.append((tid, paths))
        else:
            done.append(tid)
    return done, pending, unknown


def _git_added_ts(root, rel):
    """Unix time of the FIRST commit that added `rel`, or None (not a repo, untracked, git missing)."""
    try:
        r = subprocess.run(['git', 'log', '--diff-filter=A', '--follow', '--format=%ct', '--', rel], cwd=str(root),
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        vals = [int(x) for x in r.stdout.decode('ascii', 'replace').split() if x.isdigit()]
        return min(vals) if r.returncode == 0 and vals else None
    except Exception:
        return None


def shared_targets(tasks, root, spec_dir=None, git=True):
    """aidd:FR-441 {task id: reason} for tasks whose targets all EXIST but whose existence does not prove the task is
    done: the target is cited by another task (shared file), the Status cell says not done, or (git) the file was
    committed before the spec's tasks.md. A task with a code marker (`marked`), a renamed target or a Status cell
    that says done is never listed."""
    cites = {}
    for tid, paths, _t in tasks:
        for p in paths:
            cites.setdefault(p, set()).add(tid)
    spec_ts = None
    if git and spec_dir is not None:
        try:
            spec_ts = _git_added_ts(root, str((Path(spec_dir) / 'tasks.md').resolve().relative_to(Path(root).resolve())).replace('\\', '/'))
        except Exception:
            spec_ts = None
    out = {}
    for tid, paths, task in tasks:
        if not paths or _progress.task_state(task, root) not in ('present', 'stub'):
            continue
        status = str(task.get('status') or '').strip()
        if status and _progress.DONE_RE.search(status):
            continue
        reasons = []
        others = sorted({o for p in paths for o in cites.get(p, ()) if o != tid})
        if others:
            reasons.append(f'target shared with {", ".join(others)}')
        if status:
            reasons.append(f'Status says "{status[:30]}"')
        if spec_ts is not None:
            old = [p for p in paths if (_git_added_ts(root, p) or spec_ts) < spec_ts]
            if old:
                reasons.append(f'{", ".join(old)} existed before the spec (git)')
        if reasons:
            out[tid] = f'{", ".join(paths)}: ' + '; '.join(reasons)
    return out


def lanes(pending):
    groups = {}
    for tid, paths in pending:
        parts = Path(paths[0]).parts
        key = '/'.join(parts[:2]) if len(parts) > 2 else (parts[0] if parts else '?')
        groups.setdefault(key, []).append(tid)
    return groups


def main(argv):
    args = [a for i, a in enumerate(argv) if not a.startswith('--') and not (i and argv[i - 1] == '--root')]
    if not args:
        print(__doc__)
        return 2
    target = Path(args[0])
    tasks_md = target / 'tasks.md' if target.is_dir() else target
    if not tasks_md.is_file():
        print(f'tasks.md not found: {tasks_md}', file=sys.stderr)
        return 2
    root = Path(argv[argv.index('--root') + 1]) if '--root' in argv else tasks_md.resolve().parent.parent.parent
    if tasks_md.name == 'tasks.md':
        text, files = read_combined(tasks_md.parent)
    else:
        text, files = tasks_md.read_text(encoding='utf-8'), [tasks_md.name]
    tasks = parse(text)
    done, pending, unknown = classify(tasks, root)
    shared = shared_targets(tasks, root, tasks_md.parent)
    done = [t for t in done if t not in shared]
    unverified = [t for t, _p, _x in tasks if t in shared]
    lane_map = lanes(pending)
    if '--json' in argv:
        print(json.dumps({'done': done, 'pending': [t for t, _ in pending], 'unverified': unverified,
                          'unverified_why': shared, 'unknown': unknown, 'lanes': lane_map, 'files': files},
                         indent=2))
        return 0
    print(f'done={len(done)} pending={len(pending)} unverified={len(unverified)} unknown={len(unknown)} '
          f'(root={root}; read {", ".join(files)})')
    for key, ids in sorted(lane_map.items()):
        print(f'  lane {key}: {", ".join(ids)}')
    if unverified:
        print('  target exists but is shared or pre-existing - existence does NOT prove the task is done '
              '(check the task itself):')
        for tid in unverified:
            print(f'    {tid}: {shared[tid]}')
    if unknown:
        print(f'  no Target file (needs a human/agent decision): {", ".join(unknown)}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
