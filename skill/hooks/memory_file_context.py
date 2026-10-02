#!/usr/bin/env python3
"""
PreToolUse hook (Read|Edit|Write) — once per (session, file), adds the AIDD
memory entries that mention that file as additionalContext. Silent when the
project has no `.aidd/memory/` or no entry matches. Never blocks, never
raises, always exits 0.
"""
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

MARKER_DIR = Path(tempfile.gettempdir()) / "aidd-hooks"


def _memory_root(start):
    """Cheap root lookup mirroring aidd_memory.find_root, run BEFORE importing it."""
    env = os.environ.get('AIDD_MEMORY_DIR')
    if env:
        return Path(start).resolve() if Path(env).is_dir() else None
    cur = Path(start).resolve()
    for d in [cur] + list(cur.parents):
        if (d / '.aidd').is_dir() or (d / 'specs').is_dir() or (d / '.git').exists():
            return d if (d / '.aidd' / 'memory').is_dir() else None
    return None


def _relative(file_path, root, cwd):
    p = str(file_path).replace('\\', '/')
    try:
        pp = Path(p)
        if not pp.is_absolute():
            pp = Path(cwd) / pp
        return pp.resolve().relative_to(Path(root).resolve()).as_posix()
    except Exception:
        return p


def _first_time(session_id, rel):
    """True the first time (session, file) is seen; records a marker. Best-effort."""
    try:
        MARKER_DIR.mkdir(parents=True, exist_ok=True)
        sid = ''.join(c for c in str(session_id or 'unknown-session') if c.isalnum() or c in '-_') or 'unknown-session'
        digest = hashlib.sha1(rel.encode('utf-8')).hexdigest()[:16]
        marker = MARKER_DIR / f'{sid}.mem-{digest}'
        try:
            fd = os.open(str(marker), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True
        except FileExistsError:
            return False
    except Exception:
        return True


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    sys.path.insert(0, str(Path(__file__).parent))
    from _common import read_event
    event = read_event()
    if not isinstance(event, dict):
        return
    tool_input = event.get('tool_input')
    file_path = tool_input.get('file_path') if isinstance(tool_input, dict) else None
    if not file_path or not isinstance(file_path, str):
        return
    cwd = event.get('cwd') or os.getcwd()
    root = _memory_root(cwd)
    if root is None:
        return
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
    import aidd_memory
    root = aidd_memory.find_root(cwd)
    rel = _relative(file_path, root, cwd)
    text = aidd_memory.file_context_text(root, rel)
    if not text:
        return
    if not _first_time(event.get('session_id'), rel):
        return
    sys.stdout.write(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "additionalContext": text}}, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        pass
    sys.exit(0)
