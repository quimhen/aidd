#!/usr/bin/env python3
"""
PostToolUse hook (matcher: "Write|Edit|MultiEdit|NotebookEdit") — after an edit to a file that a
registered project graph watches (e.g. DB migrations), refresh that graph IN THE BACKGROUND.

For each edited path (tool_input.file_path / notebook_path / edits[*]) it finds the project root(s),
asks aidd_graphs.match_watch(root, path) which graphs watch it and calls
aidd_graphs.refresh(root, name, background=True) (lock + 60 s debounce live there; it only spawns a
detached process). Silent: no stdout, writes no evidence rows, never raises, always exits 0.
No-op when aidd_graphs is missing, nothing matches, or env AIDD_GRAPHS=off.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import read_event  # noqa: E402


def _paths(tool_input):
    out = []
    if not isinstance(tool_input, dict):
        return out
    edits = tool_input.get('edits')
    srcs = [tool_input] + [e for e in (edits if isinstance(edits, list) else []) if isinstance(e, dict)]
    for src in srcs:
        for k in ('file_path', 'notebook_path'):
            v = src.get(k)
            if isinstance(v, str) and v.strip() and v not in out:
                out.append(v)
    return out


def _roots(path, ev):
    if ev is not None:
        try:
            r = ev.project_roots(path)
            if r:
                return list(r)
        except Exception:
            pass
    try:
        start = path if path.is_dir() else path.parent
        for d in [start] + list(start.parents):
            if (d / 'charter.md').exists() or (d / 'specs').is_dir() or (d / '.git').exists():
                return [d]
    except Exception:
        pass
    return []


def main():
    event = read_event()
    if not isinstance(event, dict):
        return
    if str(os.environ.get('AIDD_GRAPHS', '')).strip().lower() == 'off':
        return
    paths = _paths(event.get('tool_input'))
    if not paths:
        return
    cwd = event.get('cwd') if isinstance(event.get('cwd'), str) and event.get('cwd') else None
    sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
    try:
        import aidd_graphs
    except ImportError:
        return
    try:
        import aidd_evidence as ev
    except Exception:
        ev = None
    done = set()
    for fp in paths:
        try:
            p = Path(fp)
            if not p.is_absolute():
                p = Path(cwd or Path.cwd()) / p
            for root in _roots(p, ev):
                try:
                    names = aidd_graphs.match_watch(root, p)
                except Exception:
                    continue
                for name in names or []:
                    if (str(root), name) in done:
                        continue
                    done.add((str(root), name))
                    try:
                        aidd_graphs.refresh(root, name, background=True)
                    except Exception:
                        pass
        except Exception:
            pass


try:
    main()
except BaseException:
    pass
sys.exit(0)
