#!/usr/bin/env python3
"""
SessionStart hook — injects a compact AIDD memory digest (recent decisions,
constraints, risks) into the session. Silent when the project has no
`.aidd/memory/`. Never blocks, never raises, always exits 0.
"""
import os
import sys
from pathlib import Path


def _memory_root(start):
    """Cheap root lookup mirroring aidd_memory.find_root, run BEFORE importing it."""
    env = os.environ.get('AIDD_MEMORY_DIR')
    if env:
        return (Path(start).resolve() if start else None) if Path(env).is_dir() else None
    cur = Path(start).resolve()
    for d in [cur] + list(cur.parents):
        if (d / '.aidd').is_dir() or (d / 'specs').is_dir() or (d / '.git').exists():
            return d if (d / '.aidd' / 'memory').is_dir() else None
    return None


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    sys.path.insert(0, str(Path(__file__).parent))
    from _common import read_event
    event = read_event()
    if not isinstance(event, dict):
        return
    cwd = event.get('cwd') or os.getcwd()
    if _memory_root(cwd) is None:
        return
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
    import aidd_memory
    root = aidd_memory.find_root(cwd)
    text = aidd_memory.inject_text(root)
    if text:
        sys.stdout.write(text + '\n')


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        pass
    sys.exit(0)
