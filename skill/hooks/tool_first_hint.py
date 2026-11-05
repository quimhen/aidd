#!/usr/bin/env python3
"""
PostToolUse hook (Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell) — tool-first nudge, spec 004
FR-049..FR-054: after 4 edits with the same shape or to the same file within 15 minutes, or 4 shell
commands in a row with the same shape (digits, quoted literals and paths ignored, FR-054), the agent is
advised once per trigger key to run `aidd tools` or write a reusable script (FR-049, FR-050). An
`aidd tools` query run by the agent is recorded as a `tool_query` event and silences the advice for
300 s (FR-051); each advisory is a `tool_miss` event (FR-052). State lives in the per-session evidence
directory, never in the project (FR-053).
Only advises: never denies, never blocks, never raises, always exits 0.
"""
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

N_REPEAT = 4
WINDOW_S = 900
SILENCE_S = 300
MAX_KEYS = 200
EDIT_TOOLS = frozenset({'Edit', 'Write', 'MultiEdit', 'NotebookEdit'})
SHAPE_TOOLS = frozenset({'Edit', 'MultiEdit'})
SHELL_TOOLS = frozenset({'Bash', 'PowerShell'})
READ_ONLY_GIT_RE = re.compile(r'^\s*git\s+(?:status|log|diff)\b', re.I)
TOOLS_QUERY_RE = re.compile(r'\baidd(?:\.exe)?\s+tools\b|aidd_tools\.py', re.I)
QUOTED_RE = re.compile(r'`[^`\n]*`|"[^"\n]*"|\'[^\'\n]*\'')
PATHLIKE_RE = re.compile(r'[^\s<>|]*[\\/][^\s<>|]*')
DIGITS_RE = re.compile(r'\d+')
SECRET_RE = re.compile(r'(?i)(pass(?:word)?|secret|token|api[_-]?key|key)\s*[=:]\s*\S+')
PLACEHOLDERS = frozenset({'<P>', '<Q>', '<N>'})

_ev = None
_sid = None


def _shape(text):
    """aidd:FR-054 quoted literals -> <Q>, path-like tokens -> <P>, digit runs -> <N>, whitespace collapsed."""
    s = str(text)[:4000]
    s = QUOTED_RE.sub('<Q>', s)
    s = PATHLIKE_RE.sub('<P>', s)
    s = DIGITS_RE.sub('<N>', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def _edit_shape(tool, ti):
    """Shape key of an Edit/MultiEdit call (extension + normalised old/new pairs), else None."""
    if tool not in SHAPE_TOOLS:
        return None
    fp = ti.get('file_path')
    if not isinstance(fp, str):
        return None
    if tool == 'Edit':
        o, n = ti.get('old_string'), ti.get('new_string')
        if not isinstance(o, str) or not isinstance(n, str):
            return None
        pairs = [(o, n)]
    else:
        edits = ti.get('edits')
        if not isinstance(edits, list) or not edits:
            return None
        pairs = []
        for e in edits:
            if not isinstance(e, dict):
                return None
            o, n = e.get('old_string'), e.get('new_string')
            if not isinstance(o, str) or not isinstance(n, str):
                return None
            pairs.append((o, n))
    ext = os.path.splitext(fp)[1].lower()
    raw = ext + '\x1f' + '\x1e'.join(_shape(o) + '\x1f' + _shape(n) for o, n in pairs)
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]


def _rel_key(path, root, cwd):
    p = os.path.abspath(path if os.path.isabs(path) else os.path.join(cwd, path))
    r = os.path.abspath(str(root))
    try:
        under = os.path.commonpath([os.path.normcase(p), os.path.normcase(r)]) == os.path.normcase(r)
    except ValueError:
        under = False
    if under:
        return os.path.relpath(p, r).replace('\\', '/')
    return os.path.normcase(p).replace('\\', '/')


def _scrub(text):
    return SECRET_RE.sub(lambda m: m.group(1) + '=***', text or '').replace('\n', ' ')[:120]


def _fresh_state():
    return {"v": 1, "edits": 0, "shapes": {}, "files": {}, "shell": {"key": "", "run": 0}, "advised": []}


def _load_state(path):
    """(state, ok): a missing file is a fresh valid state; unreadable or malformed content is (fresh, False)."""
    if not path.exists():
        return _fresh_state(), True
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, ValueError):
        return _fresh_state(), False
    if (isinstance(data, dict) and isinstance(data.get('edits'), int) and isinstance(data.get('shapes'), dict)
            and isinstance(data.get('files'), dict) and isinstance(data.get('shell'), dict)
            and isinstance(data.get('advised'), list)):
        return data, True
    return _fresh_state(), False


def _save_state(path, state):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
        os.replace(str(tmp), str(path))
    except OSError:
        pass


def _trim(stamps_by_key, now):
    """Drop stamps older than the window and empty keys; keep the MAX_KEYS keys used most recently."""
    out = {}
    for k, v in stamps_by_key.items():
        if not isinstance(v, list):
            continue
        keep = [float(t) for t in v if isinstance(t, (int, float)) and not isinstance(t, bool)
                and float(t) >= now - WINDOW_S]
        if keep:
            out[k] = keep
    if len(out) > MAX_KEYS:
        newest = sorted(out, key=lambda k: max(out[k]), reverse=True)[:MAX_KEYS]
        out = {k: out[k] for k in newest}
    return out


def _update_counters(state, tool, ti, root, cwd, now):
    """aidd:FR-049 count this call; return the triggers (kind, key, count, label) at or above N_REPEAT."""
    fired = []
    shape_key = file_key = label = None
    shell_key = shell_label = None
    if tool in EDIT_TOOLS:
        state['edits'] = state.get('edits', 0) + 1
    if tool in SHAPE_TOOLS:
        fp = ti.get('file_path')
        if isinstance(fp, str):
            label = _rel_key(fp, root, cwd)
            file_key = 'same_file:' + label.lower()
            state['files'].setdefault(file_key, []).append(now)
        shape = _edit_shape(tool, ti)
        if shape:
            shape_key = 'same_shape:' + shape
            state['shapes'].setdefault(shape_key, []).append(now)
    if tool in SHELL_TOOLS:
        cmd = ti.get('command')
        if isinstance(cmd, str) and cmd.strip() and not READ_ONLY_GIT_RE.search(cmd):
            shell_label = _shape(cmd)[:120]
            shell_key = 'same_command:' + hashlib.sha1(_shape(cmd).encode('utf-8')).hexdigest()[:16]
            sh = state.get('shell') if isinstance(state.get('shell'), dict) else {}
            if sh.get('key') == shell_key and isinstance(sh.get('run'), int):
                state['shell'] = {'key': shell_key, 'run': sh['run'] + 1}
            else:
                state['shell'] = {'key': shell_key, 'run': 1}
    state['shapes'] = _trim(state['shapes'], now)
    state['files'] = _trim(state['files'], now)
    if shape_key and len(state['shapes'].get(shape_key, [])) >= N_REPEAT:
        fired.append(('same_shape', shape_key, len(state['shapes'][shape_key]), label or ''))
    if file_key and len(state['files'].get(file_key, [])) >= N_REPEAT:
        fired.append(('same_file', file_key, len(state['files'][file_key]), label or ''))
    if shell_key and state['shell']['run'] >= N_REPEAT:
        fired.append(('same_command', shell_key, state['shell']['run'], shell_label))
    return fired


def _silenced(ev, sid):
    """aidd:FR-051 an `aidd tools` query by the AGENT (source != 'hook') within the last 300 s silences."""
    try:
        now = time.time()
        for e in ev.events(None, session=sid, kind='tool_query'):
            d = e.get('detail') or {}
            if d.get('source') != 'hook' and now - float(e.get('ts') or 0) <= SILENCE_S:
                return True
    except Exception:
        return False
    return False


def _base_stem(token):
    return os.path.splitext(os.path.basename(token.replace('\\', '/')))[0].lower()


def _keywords(kind, label, command=None):
    """aidd:FR-050 search words for `aidd tools`: extension + folder for edits, program + script for shell."""
    if kind == 'same_command':
        toks = str(command if command is not None else label).split()
        if not toks:
            return ''
        words = [_base_stem(toks[0].strip('"\''))]
        for t in toks[1:]:
            if t.startswith('-') or t in PLACEHOLDERS:
                continue
            stem = _base_stem(t.strip('"\''))
            if stem:
                words.append(stem)
            break
        return ' '.join(w for w in words if w)
    parts = str(label).replace('\\', '/').split('/')
    ext = os.path.splitext(parts[-1])[1].lstrip('.').lower()
    parent = parts[-2].lower() if len(parts) > 1 else ''
    return ' '.join(w for w in (ext, parent) if w)


def _advice(kind, count, label, keywords):
    if kind == 'same_shape':
        head = f"AIDD tool-first (T1): {count} edits with the same shape in the last 15 min."
    elif kind == 'same_file':
        head = f"AIDD tool-first (T1): {count} edits to {label} in the last 15 min."
    else:
        head = f"AIDD tool-first (T1): {count} shell commands in a row with the same shape."
    return head + (f" Run `aidd tools {keywords}`; if no tool fits, write a script with dry-run, apply and check "
                   f"and save it under tools/ so `aidd tools` indexes it. Advisory only, nothing was blocked.")


def main():
    global _ev, _sid
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _common import read_event, session_of
    event = read_event()
    if not isinstance(event, dict):
        return
    ti = event.get('tool_input')
    tool = event.get('tool_name')
    if not isinstance(ti, dict) or tool not in (EDIT_TOOLS | SHELL_TOOLS):
        return
    sid = _sid = session_of(event)
    cwd = event.get('cwd') if isinstance(event.get('cwd'), str) and event.get('cwd') else os.getcwd()
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
    import aidd_evidence as ev
    _ev = ev
    root = ev.known_root(cwd)
    if root is None:
        return
    command = ti.get('command') if tool in SHELL_TOOLS else None
    if isinstance(command, str) and TOOLS_QUERY_RE.search(command):
        ev.append(None, sid, 'tool_query', source='agent', command=_scrub(command))
        return
    path = ev.tool_first_state_path(sid)
    state, ok = _load_state(path)
    fired = _update_counters(state, tool, ti, root, cwd, time.time())
    _save_state(path, state)
    if not ok:
        return
    advised = set(state['advised'])
    kept = [t for t in fired if t[1] not in advised]
    if not kept:
        return
    if _silenced(ev, sid):
        return
    for t in kept:
        state['advised'].append(t[1])
    _save_state(path, state)
    kind, _key, count, label = kept[0]
    ev.append(None, sid, 'tool_miss', kind=kind, target=_scrub(label), count=count)
    msg = _advice(kind, count, label, _keywords(kind, label, command))
    sys.stdout.write(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse", "additionalContext": msg}}, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        try:
            if _ev is None:
                sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
                import aidd_evidence as _ev  # noqa: F811
            _ev.record_hook_error(None, _sid, 'tool_first_hint', repr(exc))
        except Exception:
            pass
    sys.exit(0)
