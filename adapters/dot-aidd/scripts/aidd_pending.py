#!/usr/bin/env python3
"""aidd pending — script prefilter for task orchestration (rule E1).

Reads a spec's tasks.md, checks which Target files already exist on disk, and
prints done / pending / unknown tasks plus the pending ones grouped into lanes
(one lane per top-level target folder = one owner agent). Zero LLM tokens: an
orchestrator runs this BEFORE launching any agent, so no agent is spent only to
discover "already done".

Usage:
    python aidd_pending.py <spec_dir|tasks.md> [--root DIR] [--json]
Exit 0 always (informational); 2 on usage error.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import aidd_progress as _progress  # noqa: E402  (same path rules as `aidd progress`, so both agree)


def parse(text):
    """[(task_id, [target paths])] for every table with a 'Target file' column. Uses aidd_progress.parse_tasks:
    the spec's declared path shorthand (`ENG/` = `real/prefix/`) is expanded, a trailing `(same owner as T-nn)` /
    `(new)` is ignored and a cell with several paths lists them all."""
    return [(t['id'], t['paths'], t) for t in _progress.parse_tasks(text)]


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


def lanes(pending):
    groups = {}
    for tid, paths in pending:
        parts = Path(paths[0]).parts
        key = '/'.join(parts[:2]) if len(parts) > 2 else (parts[0] if parts else '?')
        groups.setdefault(key, []).append(tid)
    return groups


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    if not args:
        print(__doc__)
        return 2
    target = Path(args[0])
    tasks_md = target / 'tasks.md' if target.is_dir() else target
    if not tasks_md.is_file():
        print(f'tasks.md not found: {tasks_md}', file=sys.stderr)
        return 2
    root = Path(argv[argv.index('--root') + 1]) if '--root' in argv else tasks_md.resolve().parent.parent.parent
    done, pending, unknown = classify(parse(tasks_md.read_text(encoding='utf-8')), root)
    lane_map = lanes(pending)
    if '--json' in argv:
        print(json.dumps({'done': done, 'pending': [t for t, _ in pending],
                          'unknown': unknown, 'lanes': lane_map}, indent=2))
        return 0
    print(f'done={len(done)} pending={len(pending)} unknown={len(unknown)} (root={root})')
    for key, ids in sorted(lane_map.items()):
        print(f'  lane {key}: {", ".join(ids)}')
    if unknown:
        print(f'  no Target file (needs a human/agent decision): {", ".join(unknown)}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
