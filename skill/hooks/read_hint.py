#!/usr/bin/env python3
"""
PreToolUse hook (Read) — W1 hint: whole-file reads of spec artifacts before any
find_spec run in the session get a one-time nudge toward find_spec / limit+offset.
Never blocks, never raises, always exits 0.
"""
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

MARKER_DIR = Path(tempfile.gettempdir()) / "aidd-hooks"
TARGETS = {'spec.md', 'plan.md', 'contracts.md', 'tasks.md', 'events.toon'}


def _is_target(file_path):
    parts = [p for p in re.split(r'[\\/]+', file_path) if p]
    if not parts:
        return None
    name = parts[-1].lower()
    if name not in TARGETS:
        return None
    dirs = [p.lower() for p in parts[:-1]]
    if name == 'events.toon':
        ok = any(dirs[i] == '.aidd' and dirs[i + 1] == 'evidence' for i in range(len(dirs) - 1))
    else:
        ok = 'specs' in dirs
    return parts[-1] if ok else None


def _first_time(session_id, path):
    try:
        MARKER_DIR.mkdir(parents=True, exist_ok=True)
        sid = ''.join(c for c in str(session_id or 'unknown-session') if c.isalnum() or c in '-_') or 'unknown-session'
        digest = hashlib.sha1(path.encode('utf-8')).hexdigest()[:16]
        marker = MARKER_DIR / f'{sid}.rh-{digest}'
        try:
            fd = os.open(str(marker), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True
        except FileExistsError:
            return False
    except Exception:
        return True


def _sql_hint(event, file_path):
    """One nudge per file per session: whole-file read of a .sql file in a project that has a DB graph."""
    sid = event.get('session_id')
    sid = sid if isinstance(sid, str) and sid else 'unknown-session'
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
    import aidd_graphs
    root = None
    for parent in Path(file_path).resolve().parents:
        if (parent / 'charter.md').is_file() or (parent / 'specs').is_dir() or (parent / '.git').exists():
            root = parent
            break
    if root is None or not any(g['kind'] == 'db' for g in aidd_graphs.load_registry(root)):
        return
    if not _first_time(sid, file_path):
        return
    msg = ("AIDD G1: this project has a DB graph. Before reading SQL, ask it: `aidd graphs show db <table-or-column>` "
           "(columns carry their purpose, FKs, and the views/functions that use them), then read only the lines it points to.")
    sys.stdout.write(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "additionalContext": msg}}, ensure_ascii=False) + '\n')


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    sys.path.insert(0, str(Path(__file__).parent))
    from _common import read_event
    event = read_event()
    if not isinstance(event, dict):
        return
    ti = event.get('tool_input')
    if not isinstance(ti, dict):
        return
    file_path = ti.get('file_path')
    if not file_path or not isinstance(file_path, str):
        return
    name = _is_target(file_path)
    if not name:
        if file_path.lower().endswith('.sql') and not (ti.get('limit') or ti.get('offset')):
            _sql_hint(event, file_path)         # G1: a column or table question starts at the graph
        return
    if ti.get('limit') or ti.get('offset'):
        return
    sid = event.get('session_id')
    sid = sid if isinstance(sid, str) and sid else 'unknown-session'
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
    import aidd_evidence
    root = aidd_evidence.known_root(event.get('cwd') or os.getcwd())
    if aidd_evidence.events(root, kind='find_spec', session=sid):
        return
    if not _first_time(sid, file_path):
        return
    msg = (f"AIDD W1: whole-file read of {name}. Prefer `python <AIDD_HOME>/scripts/find_spec.py "
           f"--code <CODE>` (or --tree <spec-id>) or Read with limit/offset.")
    sys.stdout.write(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "additionalContext": msg}}, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        pass
    sys.exit(0)
