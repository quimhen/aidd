#!/usr/bin/env python3
"""
PreToolUse hook (Read|Grep|Glob|Bash|PowerShell) — graph-first nudge (aidd:FR-025): searches and
whole-file reads of project code or specs get a one-line pointer to the graph query, unless the agent
ran a graph query (find_spec / aidd graphs / aidd search|tree) in the last 300 s (aidd:FR-026). Every
counted search is recorded as a `graph_miss` session event (aidd:FR-027).
Only advises: never denies, never blocks, never raises, always exits 0.
"""
import hashlib
import json
import os
import re
import shlex
import sys
import tempfile
import time
from pathlib import Path

MARKER_DIR = Path(tempfile.gettempdir()) / "aidd-hooks"
TARGETS = {'spec.md', 'plan.md', 'contracts.md', 'tasks.md', 'events.toon'}

SILENCE_S = 300                                    # aidd:FR-026
CODE_EXTS = {'.py', '.ts', '.tsx', '.js', '.jsx', '.dart', '.sql', '.cs', '.md', '.toon', '.json', '.yml'}
SEARCH_WORDS = {'grep', 'rg', 'cat', 'sed', 'awk', 'head', 'tail', 'type', 'get-content', 'select-string',
                'findstr', 'ack', 'ag', 'gc', 'sls'}
SKIP_WORDS = {'git', 'pip', 'pip3', 'npm', 'npx', 'pnpm', 'yarn', 'aidd'}
GRAPH_QUERY_RE = re.compile(r'find_spec\.py|aidd_graphs\.py|\baidd(?:\.exe)?\s+(?:graphs|search|tree)\b', re.I)
IGNORED_PARTS = {'.git', 'node_modules', '__pycache__', 'scratchpad'}
SECRET_RE = re.compile(r'(?i)(pass(?:word)?|secret|token|api[_-]?key|key)\s*[=:]\s*\S+')


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


def _norm(p):
    return os.path.normcase(os.path.abspath(str(p)))


def _under(path, base):
    try:
        return os.path.commonpath([_norm(path), _norm(base)]) == _norm(base)
    except ValueError:
        return False


def _project_path(path, root, cwd):
    """Absolute path of `path` when it is inside the project and not ignored, else None."""
    try:
        if not path or not isinstance(path, str):
            return None
        p = os.path.abspath(path if os.path.isabs(path) else os.path.join(cwd, path))
        if not _under(p, root):
            return None
        if {x.lower() for x in re.split(r'[\\/]+', p)} & IGNORED_PARTS:
            return None
        for skip in (tempfile.gettempdir(), os.path.join(os.path.expanduser('~'), '.claude')):
            if _under(p, skip) and not _under(root, skip):
                return None
        return p
    except Exception:
        return None


def _is_dir_or_code(p):
    """aidd:FR-025 only code/spec files or a directory search count."""
    return os.path.isdir(p) or os.path.splitext(p)[1].lower() in CODE_EXTS


def _rel(p, root):
    return os.path.relpath(p, str(root)).replace('\\', '/')


def _scrub(text):
    return SECRET_RE.sub(lambda m: m.group(1) + '=***', text or '').replace('\n', ' ')[:120]


def _silenced(ev, root, sid):
    """aidd:FR-026 a graph query by the AGENT (source != 'hook') within the last 300 s silences the nudge."""
    now = time.time()
    for e in ev.events(root, kind='find_spec', session=sid):
        d = e.get('detail') or {}
        if d.get('source') != 'hook' and now - float(e.get('ts') or 0) <= SILENCE_S:
            return True
    return False


def _throttled(sid):
    """True when a search nudge was already emitted for this session in the last 300 s (else stamps it)."""
    try:
        MARKER_DIR.mkdir(parents=True, exist_ok=True)
        clean = ''.join(c for c in sid if c.isalnum() or c in '-_') or 'unknown-session'
        marker = MARKER_DIR / f'{clean}.rh-search'
        now = time.time()
        try:
            if now - marker.stat().st_mtime < SILENCE_S:
                return True
        except OSError:
            pass
        marker.write_text(str(now), encoding='utf-8')
        return False
    except Exception:
        return False


def _command_target(command, root, cwd):
    """Short target when a Bash/PowerShell command searches or prints project code/specs, else None."""
    if not command or GRAPH_QUERY_RE.search(command):
        return None
    for seg in re.split(r'\|\||&&|[|;&\n]', command):
        try:
            toks = shlex.split(seg, posix=False)
        except ValueError:
            toks = seg.split()
        toks = [t.strip('"\'') for t in toks]
        while toks and toks[0].lower() in {'call', 'time', 'sudo', 'command', 'env'}:
            toks = toks[1:]
        if not toks:
            continue
        word = os.path.basename(toks[0].replace('\\', '/')).lower()
        word = word[:-4] if word.endswith('.exe') else word
        if word in SKIP_WORDS:
            return None
        if word not in SEARCH_WORDS:
            continue
        args = [t for t in toks[1:] if t and not t.startswith('-')]
        paths = [p for p in (_project_path(t, root, cwd) for t in args) if p and _is_dir_or_code(p)]
        recursive = word in {'rg', 'ack', 'ag'} or any(re.match(r'^-[a-zA-Z]*[rR][a-zA-Z]*$', t) for t in toks[1:])
        if not paths and recursive and _project_path(cwd, root, cwd):
            paths = [os.path.abspath(cwd)]
        if paths:
            return _rel(paths[0], root)
    return None


def _name_hint(tool, ti, target):
    """The graph query to try first, named for the search at hand."""
    pat = ti.get('pattern') if tool in ('Grep', 'Glob') else None
    if isinstance(pat, str):
        m = re.search(r'\b([A-Z]{1,6}-\d{1,4})\b', pat)
        if m:
            return f'`python <AIDD_HOME>/scripts/find_spec.py --code {m.group(1)}`'
        m = re.search(r'[A-Za-z_][A-Za-z0-9_]{2,}', pat)
        if m:
            return f'`aidd graphs show code {m.group(0)}`'
    stem = os.path.splitext(os.path.basename(str(target or '')))[0]
    if stem and re.match(r'^[A-Za-z_][A-Za-z0-9_.-]*$', stem):
        return f'`aidd graphs show code {stem}`'
    return '`aidd graphs show code <name>` or `find_spec.py --code <CODE>`'


def _graph_first(event, root, sid, ti, tool, ev):
    """aidd:FR-025 aidd:FR-027 count one search, record graph_miss, nudge when not silenced."""
    cwd = event.get('cwd') if isinstance(event.get('cwd'), str) and event.get('cwd') else os.getcwd()
    target = None
    if tool == 'Read':
        fp = ti.get('file_path')
        if not isinstance(fp, str) or ti.get('limit') or ti.get('offset'):
            return                                   # a ranged read is the targeted read the graph points to
        p = _project_path(fp, root, cwd)
        if p and os.path.splitext(p)[1].lower() in CODE_EXTS:
            target = _rel(p, root)
    elif tool in ('Grep', 'Glob'):
        p = _project_path(ti.get('path') or cwd, root, cwd)
        pat = ti.get('pattern') if isinstance(ti.get('pattern'), str) else ''
        if p and tool == 'Glob':
            ext = os.path.splitext(pat)[1].lower()
            if ext and ext not in CODE_EXTS:
                p = None
        if p and _is_dir_or_code(p):
            target = f'{pat} @ {_rel(p, root)}'
    elif tool in ('Bash', 'PowerShell'):
        cmd = ti.get('command')
        target = _command_target(cmd, root, cwd) if isinstance(cmd, str) else None
    if not target:
        return
    silenced = _silenced(ev, root, sid)
    ev.append(root, sid, 'graph_miss', tool=tool, target=_scrub(target), silenced=bool(silenced))
    if silenced or _throttled(sid):
        return
    msg = (f"AIDD graph-first: before searching code or specs, ask the graph: {_name_hint(tool, ti, target)} "
           f"(also `aidd search <text>`), then read only the lines it points to.")
    if not os.path.isfile(os.path.join(str(root), '.aidd', 'graphs', 'code.json')):
        msg += ' no code graph yet: run aidd graphs refresh code'
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
    tool = event.get('tool_name') if isinstance(event.get('tool_name'), str) else 'Read'
    sid = event.get('session_id')
    sid = sid if isinstance(sid, str) and sid else 'unknown-session'
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
    if tool != 'Read':
        import aidd_evidence as ev
        root = ev.known_root(event.get('cwd') or os.getcwd())
        if root is not None:
            _graph_first(event, root, sid, ti, tool, ev)
        return
    file_path = ti.get('file_path')
    if not file_path or not isinstance(file_path, str):
        return
    name = _is_target(file_path)
    if not name:
        if file_path.lower().endswith('.sql') and not (ti.get('limit') or ti.get('offset')):
            _sql_hint(event, file_path)         # G1: a column or table question starts at the graph
            return
        import aidd_evidence as ev
        root = ev.known_root(event.get('cwd') or os.getcwd())
        if root is not None:
            _graph_first(event, root, sid, ti, tool, ev)
        return
    if ti.get('limit') or ti.get('offset'):
        return
    import aidd_evidence as ev
    root = ev.known_root(event.get('cwd') or os.getcwd())
    silenced = root is not None and _silenced(ev, root, sid)     # aidd:FR-026 hook-source never silences
    if root is not None:
        p = _project_path(file_path, root, event.get('cwd') or os.getcwd())
        if p:
            ev.append(root, sid, 'graph_miss', tool='Read', target=_scrub(_rel(p, root)), silenced=bool(silenced))
    if silenced:
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
