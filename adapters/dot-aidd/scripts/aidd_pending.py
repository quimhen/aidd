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
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ROW_RE = re.compile(r'^\|(.+)\|\s*$')
TASK_ID_RE = re.compile(r'^[A-Za-z]+-\d+$')


def _cells(line):
    return [c.strip() for c in line.strip().strip('|').split('|')]


def parse(text):
    """Yield (task_id, [target paths]) for every table with a 'Target file' column."""
    out, col = [], None
    for line in text.splitlines():
        if not ROW_RE.match(line):
            col = None if not line.strip().startswith('|') else col
            continue
        cells = _cells(line)
        lowered = [c.lower() for c in cells]
        if any(c.startswith('target file') for c in lowered):
            col = next(i for i, c in enumerate(lowered) if c.startswith('target file'))
            continue
        if col is None or set(''.join(cells)) <= set('-: '):
            continue
        if TASK_ID_RE.match(cells[0]) and col < len(cells):
            paths = [p.strip('` ') for p in re.split(r'[;,]|\s+\+\s+', cells[col]) if p.strip('` ')]
            out.append((cells[0], paths))
    return out


def classify(tasks, root):
    done, pending, unknown = [], [], []
    for tid, paths in tasks:
        if not paths or any(' ' in p for p in paths):  # empty or prose, not a path
            unknown.append(tid)
        elif all((root / p).exists() for p in paths):
            done.append(tid)
        else:
            pending.append((tid, paths))
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
