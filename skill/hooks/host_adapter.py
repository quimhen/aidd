#!/usr/bin/env python3
"""
Host adapter (spec 009, plan Interface 1; spec 011 adds Antigravity) — runs Gemini CLI, OpenCode and
Antigravity tool events through the same AIDD gates Claude Code uses, unchanged. Stdlib only.

    python <hooks>/host_adapter.py <gemini|opencode|antigravity> <pre|post>

The exit-code contract below is the gemini/opencode one. Antigravity (spec 011) answers on stdout instead:
exit code always 0; stdout is ONE JSON object + newline: `pre` -> {"decision":"deny","reason":"<rule_gate
stderr, trimmed>"} when the gate blocks (or times out: fail-closed), else {"decision":"allow"}; `post` -> {}.
A crash, bad stdin or an unknown payload answers allow ({} for post) and records a hook_error.

stdin  : the host's own JSON event (UTF-8; a BOM or garbage is tolerated -> treated as {}).
exit 0 : allow — also when no `.aidd/AIDD.md` exists in the event cwd or any parent (FR-912), or the
         tool is not a write/shell tool (no gate call at all).
exit 2 : block; stderr = rule_gate's own message, passed through unchanged (names the next action).
stdout : always empty (Gemini parses hook stdout as JSON).

`pre`:  (1) project root = nearest ancestor of the event cwd holding `.aidd/AIDD.md`; none -> exit 0;
        (2) normalise the host event to the Claude shape {tool_name, tool_input, cwd, session_id}
            (table below); not a write/shell tool -> exit 0;
        (3) create the per-session "AIDD invoked" marker (`_common.marker_path`, as mark_invoked.py
            does) so the legacy require_aidd check inside rule_gate does not block with a
            Claude-only instruction (FR-912);
        (4) SPAWN sibling `rule_gate.py` (sys.executable, normalised JSON on stdin, 15 s timeout) and
            return its exit code and stderr.
`post`: same steps (1)-(2), then spawn sibling `mark_code_edit.py` (10 s timeout) so `code_edit` /
        `spec_edit` evidence is recorded (FR-906); always exit 0.

Normalisation:
    Gemini   write_file {file_path, content}               -> Write {file_path, content}
    Gemini   replace {file_path, old_string, new_string}   -> Edit {file_path, old_string, new_string}
    Gemini   run_shell_command {command}                   -> Bash {command}
    OpenCode write {filePath, content}                     -> Write {file_path, content}
    OpenCode edit {filePath, oldString, newString}         -> Edit {file_path, old_string, new_string}
    OpenCode multiedit {filePath, edits[{filePath?, oldString, newString}]}
                                                           -> MultiEdit {file_path, edits[{file_path, old_string, new_string}]}
    OpenCode patch {patchText | filePath(s)}               -> MultiEdit {file_path, edits[{file_path}]} over the
                                                              `*** Add/Update/Delete File:` / `*** Move to:` paths
    OpenCode bash {command}                                -> Bash {command}
    Antigravity write_to_file {TargetFile, CodeContent}    -> Write {file_path, content}
    Antigravity replace_file_content {TargetFile, TargetContent, ReplacementContent}
                                                           -> Edit {file_path, old_string, new_string}
    Antigravity multi_replace_file_content {TargetFile, ReplacementChunks[{TargetContent, ReplacementContent}]}
                                                           -> MultiEdit {file_path, edits[...]}; chunks that are
                                                              not a list (or JSON list) -> path-only MultiEdit
    Antigravity run_command {CommandLine, Cwd}             -> Bash {command}; callee cwd = Cwd if inside the project
    unknown write-like tool (see below)                    -> patch-like / Write fallback
    anything else                                          -> exit 0, no gate call
Unknown tools (S3): a name not mapped above is still GATED when it matches `(write|edit|patch|replace|create|append|insert|save|delete|remove|move|rename)`
(or is a known gated name of the other host) and does not start with read/glob/grep/list/search/fetch/
web/find: a name containing `patch` -> the OpenCode `patch` mapping; otherwise -> Write {file_path, content
or ''} from the first of file_path/filePath/path/filename/file; no path -> exit 0 + hook_error
`unmapped write-like tool <name>`.
Accepted envelope keys: tool name from `tool_name` | `tool`; args from `tool_input` | `args`;
session from `session_id` (Gemini) | `sessionID` (OpenCode), sanitised (S6: chars outside
[A-Za-z0-9_-] -> `_`, max 64) and that same id goes to the marker and both callees; missing -> omitted
so the callee uses 'unknown-session'; cwd from `cwd` | `directory` | `worktree`, else the process cwd. Paths are passed
through verbatim (Windows paths stay intact; relative paths are resolved by the callees against cwd).
Antigravity envelope: tool name `toolCall.name`, args `toolCall.args` (keys read tolerantly), session
`conversationId` (same S6 sanitising); there is no `cwd` (the hook runs in `<project>/.agents`), so the
project root is the nearest `.aidd/AIDD.md` ancestor of a `workspacePaths` entry, else of the absolute
target file, else allow; the normalised `cwd` handed to the callees is that project root.

Audited facts this relies on: rule_gate.main() (not decide()) does the AIDD_RULES off/warn handling,
the `rules_override` record (FR-908), the transcript sync, the caller marker and the fail-open
hook_error — hence it is spawned, never imported; mark_code_edit reads stdin at import time, hence
spawned too; rule_gate/mark_code_edit read `edits[].file_path` for MultiEdit paths; rule_gate's
would-be-content scan skips edits without `old_string`, so a patch is gated by path only.

Fail-open: any internal exception, a gate crash or a `mark_code_edit` timeout -> exit 0 and a best-effort
`aidd_evidence.record_hook_error(cwd, session, 'host_adapter', ...)`; this module never raises.
Fail-CLOSED: a `rule_gate` timeout in the pre phase returns exit 2 ("the gate did not answer"), so padding
a command until the lexical shell guard is too slow can never skip a block.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = HOOKS_DIR.parent / 'scripts'
HOOK_NAME = 'host_adapter'
PRE_TIMEOUT_S = 15
POST_TIMEOUT_S = 10
HOSTS = ('gemini', 'opencode', 'antigravity')
AG = 'antigravity'
PHASES = ('pre', 'post')
_PATCH_PATH_RE = re.compile(r'^\*\*\*\s+(?:Add|Update|Delete)\s+File:\s*(.+?)\s*$|^\*\*\*\s+Move\s+to:\s*(.+?)\s*$',
                            re.MULTILINE)
_KNOWN_GATED = frozenset(('write_file', 'replace', 'run_shell_command', 'write', 'edit', 'multiedit', 'patch', 'bash'))
_WRITE_LIKE_RE = re.compile(r'(write|edit|patch|replace|create|append|insert|save|delete|remove|move|rename)')
_READ_PREFIXES = ('read', 'glob', 'grep', 'list', 'search', 'fetch', 'web', 'find')
_SID_BAD_RE = re.compile(r'[^A-Za-z0-9_-]')
SID_MAX = 64
_AG_PATH_KEYS = ('TargetFile', 'AbsolutePath', 'FilePath', 'file_path', 'path')
_AG_CONTENT_KEYS = ('CodeContent', 'Content', 'content')


# ------------------------------------------------------------------ input

def _read_stdin_event():
    """Host JSON from stdin as a dict; BOM / bad bytes / non-dict JSON -> {}."""
    try:
        raw = sys.stdin.buffer.read()
        text = raw.decode('utf-8', 'replace').lstrip('﻿')
        event = json.loads(text) if text.strip() else {}
    except Exception:
        return {}
    return event if isinstance(event, dict) else {}


def _str(d, *keys):
    """First non-empty string value among `keys` of dict `d`, else ''."""
    if not isinstance(d, dict):
        return ''
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v:
            return v
    return ''


def _text(d, *keys):
    """First string value (empty allowed) among `keys` of dict `d`, else ''."""
    if isinstance(d, dict):
        for k in keys:
            v = d.get(k)
            if isinstance(v, str):
                return v
    return ''


def _call_of(event):
    """Antigravity `toolCall` object as a dict ({} when null or malformed)."""
    v = event.get('toolCall') if isinstance(event, dict) else None
    return v if isinstance(v, dict) else {}


def _sanitize_sid(sid):
    """S6: keep [A-Za-z0-9_-], replace the rest with '_', truncate to 64; '' stays ''."""
    return _SID_BAD_RE.sub('_', sid)[:SID_MAX] if sid else ''


def _session_of(event, host=''):
    if host == AG:
        return _sanitize_sid(_str(event, 'conversationId'))
    return _sanitize_sid(_str(event, 'session_id', 'sessionID'))


def _cwd_of(event):
    return _str(event, 'cwd', 'directory', 'worktree') or os.getcwd()


def _project_root(cwd):
    """Nearest ancestor of `cwd` (inclusive) containing `.aidd/AIDD.md`, else None (FR-912)."""
    try:
        cur = Path(cwd).resolve()
    except Exception:
        return None
    for d in [cur] + list(cur.parents):
        try:
            if (d / '.aidd' / 'AIDD.md').is_file():
                return d
        except OSError:
            continue
    return None


def _ag_root(event, norm):
    """Antigravity project root: from each `workspacePaths` entry, else from the absolute target file."""
    paths = event.get('workspacePaths')
    for p in paths if isinstance(paths, list) else []:
        if isinstance(p, str) and p.strip():
            r = _project_root(p)
            if r is not None:
                return r
    return _root_from_paths(norm)


def _inside(path, root):
    """True when absolute `path` is `root` or lies under it."""
    try:
        if not (isinstance(path, str) and path and os.path.isabs(path)):
            return False
        p = Path(path).resolve()
        return p == root or root in p.parents
    except Exception:
        return False


def _root_from_paths(norm):
    """Project root found by walking up from the ABSOLUTE target path(s) of a normalised event, else None."""
    try:
        ti = (norm or {}).get('tool_input')
        if not isinstance(ti, dict):
            return None
        paths = [ti.get('file_path')]
        for e in ti.get('edits') or []:
            if isinstance(e, dict):
                paths.append(e.get('file_path'))
        for p in paths:
            if isinstance(p, str) and p and os.path.isabs(p):
                r = _project_root(os.path.dirname(p))
                if r is not None:
                    return r
    except Exception:
        pass
    return None


# ------------------------------------------------------------------ normalisation

def _args_of(event, host=''):
    if host == AG:
        v = _call_of(event).get('args')
        return v if isinstance(v, dict) else {}
    for k in ('tool_input', 'args'):
        v = event.get(k)
        if isinstance(v, dict):
            return v
    return {}


def _norm_gemini(tool, args):
    if tool == 'write_file':
        return 'Write', {'file_path': _str(args, 'file_path'), 'content': args.get('content', '')}
    if tool == 'replace':
        return 'Edit', {'file_path': _str(args, 'file_path'),
                        'old_string': args.get('old_string', ''), 'new_string': args.get('new_string', '')}
    if tool == 'run_shell_command':
        return 'Bash', {'command': _str(args, 'command')}
    return None, None


def _patch_paths(args):
    out = []
    text = _str(args, 'patchText', 'patch_text', 'patch')
    for m in _PATCH_PATH_RE.finditer(text):
        p = (m.group(1) or m.group(2) or '').strip()
        if p:
            out.append(p)
    fp = _str(args, 'filePath', 'file_path')
    if fp:
        out.append(fp)
    for k in ('filePaths', 'paths', 'files'):
        v = args.get(k)
        if isinstance(v, list):
            out.extend(x for x in v if isinstance(x, str) and x.strip())
    seen, uniq = set(), []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def _norm_opencode(tool, args):
    if tool == 'write':
        return 'Write', {'file_path': _str(args, 'filePath', 'file_path'), 'content': args.get('content', '')}
    if tool == 'edit':
        return 'Edit', {'file_path': _str(args, 'filePath', 'file_path'),
                        'old_string': args.get('oldString', ''), 'new_string': args.get('newString', '')}
    if tool == 'multiedit':
        top = _str(args, 'filePath', 'file_path')
        edits = []
        raw = args.get('edits')
        for e in raw if isinstance(raw, list) else []:
            if isinstance(e, dict):
                edits.append({'file_path': _str(e, 'filePath', 'file_path') or top,
                              'old_string': e.get('oldString', ''), 'new_string': e.get('newString', '')})
        ti = {'edits': edits}
        if top:
            ti['file_path'] = top
        return 'MultiEdit', ti
    if tool == 'patch':
        paths = _patch_paths(args)
        ti = {'edits': [{'file_path': p} for p in paths]}
        if paths:
            ti['file_path'] = paths[0]
        return 'MultiEdit', ti
    if tool == 'bash':
        return 'Bash', {'command': _str(args, 'command')}
    return None, None


def _ag_chunks(raw):
    """ReplacementChunks as a list of dicts (a JSON string or a single dict tolerated), else None."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return None
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return None
    chunks = [c for c in raw if isinstance(c, dict)]
    return chunks or None


def _norm_antigravity(tool, args):
    fp = _str(args, *_AG_PATH_KEYS)
    if tool == 'write_to_file':
        return 'Write', {'file_path': fp, 'content': _text(args, *_AG_CONTENT_KEYS)}
    if tool == 'replace_file_content':
        return 'Edit', {'file_path': fp, 'old_string': _text(args, 'TargetContent'),
                        'new_string': _text(args, 'ReplacementContent')}
    if tool == 'multi_replace_file_content':
        chunks = _ag_chunks(args.get('ReplacementChunks'))
        if chunks is None:  # unparseable chunks: gate by path only (rule_gate skips edits without old_string)
            edits = [{'file_path': fp}] if fp else []
        else:
            edits = [{'file_path': _str(c, *_AG_PATH_KEYS) or fp, 'old_string': _text(c, 'TargetContent'),
                      'new_string': _text(c, 'ReplacementContent')} for c in chunks]
        ti = {'edits': edits}
        if fp:
            ti['file_path'] = fp
        return 'MultiEdit', ti
    if tool == 'run_command':
        return 'Bash', {'command': _str(args, 'CommandLine', 'command')}
    return None, None


_NORMALISERS = {'gemini': _norm_gemini, 'opencode': _norm_opencode, AG: _norm_antigravity}


def _is_gated(tool):
    """S3: known write/shell name, or write-like name that is not a read/search tool."""
    if tool in _KNOWN_GATED:
        return True
    return bool(_WRITE_LIKE_RE.search(tool)) and not tool.startswith(_READ_PREFIXES)


def _norm_unknown(tool, args):
    """Fallback for a gated name the host table does not map; (None, None) when no path found."""
    if 'patch' in tool:
        paths = _patch_paths(args)
        if not paths:
            return None, None
        return 'MultiEdit', {'file_path': paths[0], 'edits': [{'file_path': p} for p in paths]}
    fp = _str(args, 'file_path', 'filePath', 'path', 'filename', 'file')
    if not fp:
        return None, None
    content = args.get('content', '')
    return 'Write', {'file_path': fp, 'content': content if isinstance(content, str) else ''}


def _norm_unknown_antigravity(tool, args):
    """Unknown gated Antigravity name: the same fallback with Antigravity's argument keys."""
    if 'patch' in tool:
        return _norm_unknown(tool, args)
    fp = _str(args, *(_AG_PATH_KEYS + ('filePath', 'filename', 'file')))
    if not fp:
        return None, None
    return 'Write', {'file_path': fp, 'content': _text(args, *_AG_CONTENT_KEYS)}


def _tool_of(event, host=''):
    if host == AG:
        return _str(_call_of(event), 'name').strip().lower()
    return _str(event, 'tool_name', 'tool').strip().lower()


def unmapped_write_tool(host, event):
    """Name of a gated tool that could not be normalised (no path), else ''."""
    if normalise(host, event) is not None:
        return ''
    tool = _tool_of(event, host)
    return tool if tool and _is_gated(tool) else ''


def normalise(host, event):
    """Claude-shaped event, or None when the tool is not a write/shell tool (or has no path)."""
    tool = _tool_of(event, host)
    args = _args_of(event, host)
    name, ti = _NORMALISERS.get(host, _norm_opencode)(tool, args)
    if not name and tool and _is_gated(tool):
        name, ti = (_norm_unknown_antigravity if host == AG else _norm_unknown)(tool, args)
    if not name:
        return None
    if host == AG:
        # no event cwd: keep only the shell's requested Cwd here; _run_core replaces it with the project
        # root unless it lies inside that root (never the hook's own `.agents` folder)
        cwd = _str(args, 'Cwd', 'cwd') if name == 'Bash' else ''
    else:
        cwd = _cwd_of(event)
    out = {'tool_name': name, 'tool_input': ti, 'cwd': cwd}
    sid = _session_of(event, host)
    if sid:
        out['session_id'] = sid
    return out


# ------------------------------------------------------------------ side effects

def _hook_error(cwd, sid, err):
    try:
        if str(SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_DIR))
        import aidd_evidence as _ev
        _ev.record_hook_error(cwd, sid or None, HOOK_NAME, err)
    except Exception:
        pass


def _mark_invoked(sid):
    """Same marker mark_invoked.py writes after Claude's Skill('aidd') call."""
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    from _common import marker_path
    marker_path(sid or None).write_text('invoked', encoding='utf-8')


def _spawn(script, event, timeout):
    """Run a sibling hook with `event` on stdin. Returns (exit_code, stderr_bytes)."""
    proc = subprocess.run([sys.executable, str(HOOKS_DIR / script)],
                          input=json.dumps(event).encode('utf-8'),
                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                          cwd=event.get('cwd') if os.path.isdir(event.get('cwd') or '') else None,
                          timeout=timeout)
    return proc.returncode, proc.stderr or b''


def _pass_stderr(data):
    if data:
        try:
            sys.stderr.buffer.write(data)
            sys.stderr.flush()
        except Exception:
            pass


# ------------------------------------------------------------------ entry

def _run_core(host, phase, event):
    """(exit_code, stderr_bytes) for one host event; the caller decides how to answer. Never raises."""
    cwd, sid = _cwd_of(event), _session_of(event, host)
    try:
        if host == AG:
            norm = normalise(host, event)
            root = _ag_root(event, norm)
            if root is None:
                return 0, b''
            cwd = str(root)
            if norm is not None and not (norm['tool_name'] == 'Bash' and _inside(norm.get('cwd'), root)):
                norm['cwd'] = cwd  # the project root, never the hook's own `<project>/.agents`
        else:
            root = _project_root(cwd)
            norm = normalise(host, event)
            if root is None:
                # the event cwd can sit outside the project (multi-root workspace, --include-directories):
                # fall back to the project that holds the target file, never skip the gate silently
                root = _root_from_paths(norm)
                if root is None:
                    return 0, b''
                norm['cwd'] = str(root)
        if norm is None:
            unmapped = unmapped_write_tool(host, event)
            if unmapped:
                _hook_error(cwd, sid, 'unmapped write-like tool %s' % unmapped)
            return 0, b''
        if phase == 'post':
            try:
                _spawn('mark_code_edit.py', norm, POST_TIMEOUT_S)
            except subprocess.TimeoutExpired:
                _hook_error(cwd, sid, 'mark_code_edit timed out after %ss' % POST_TIMEOUT_S)
            return 0, b''
        try:
            _mark_invoked(sid)
        except Exception as e:  # a missing marker only means require_aidd may block; keep going
            _hook_error(cwd, sid, 'marker: %r' % (e,))
        try:
            code, err = _spawn('rule_gate.py', norm, PRE_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            # fail CLOSED: a gate that cannot answer in time must not let the call through, otherwise
            # padding a shell command to ~10 KB (the lexical guard is slow on it) would skip every block
            _hook_error(cwd, sid, 'rule_gate timed out after %ss: call blocked' % PRE_TIMEOUT_S)
            return 2, ('aidd: the gate did not answer within %ss (an unusually long command or a very '
                       'large evidence log); the call is blocked. Shorten the command, or ask the owner '
                       'to run `aidd doctor`.' % PRE_TIMEOUT_S).encode('utf-8')
        if code == 2:
            return 2, err
        if code != 0:  # a crashed gate fails open, as on Claude
            _hook_error(cwd, sid, 'rule_gate exit %s: %s' % (code, err.decode('utf-8', 'replace')[-500:]))
            return 0, b''
        return 0, err  # warn-mode notices
    except Exception as e:
        _hook_error(cwd, sid, repr(e))
        return 0, b''


def run(host, phase, event):
    """Exit code for one exit-code host event (gemini/opencode); stderr passed through. Never raises."""
    code, err = _run_core(host, phase, event)
    _pass_stderr(err)
    return code


def _emit_json(obj):
    try:
        sys.stdout.buffer.write((json.dumps(obj) + '\n').encode('utf-8'))
        sys.stdout.flush()
    except Exception:
        pass


def run_antigravity(phase, event):
    """Antigravity answer: one JSON object on stdout; the exit code is always 0. Never raises."""
    code, err = 0, b''
    try:
        if 'toolCall' not in event:  # bad stdin or an unknown payload: allow, but leave a trace
            _hook_error(_cwd_of(event), _session_of(event, AG), 'unknown antigravity payload')
        elif phase in PHASES:
            code, err = _run_core(AG, phase, event)
        else:
            _hook_error(_cwd_of(event), _session_of(event, AG), 'bad phase: %r' % (phase,))
    except Exception as e:
        _hook_error(os.getcwd(), '', repr(e))
        code, err = 0, b''
    if phase == 'post':
        _emit_json({})
    elif code == 2:
        reason = err.decode('utf-8', 'replace').strip() or 'aidd: the call is blocked by the AIDD gate.'
        _emit_json({'decision': 'deny', 'reason': reason})
    else:
        _emit_json({'decision': 'allow'})  # warn-mode notices have no channel in this protocol
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        host = argv[0].strip().lower() if len(argv) > 0 else ''
        phase = argv[1].strip().lower() if len(argv) > 1 else ''
        event = _read_stdin_event()
        if host == AG:
            return run_antigravity(phase, event)
        if host not in HOSTS or phase not in PHASES:
            _hook_error(_cwd_of(event), _session_of(event), 'bad arguments: %r' % (argv,))
            return 0
        return run(host, phase, event)
    except Exception as e:
        _hook_error(os.getcwd(), '', repr(e))
        if argv and str(argv[0]).strip().lower() == AG:  # still answer the protocol
            post = len(argv) > 1 and str(argv[1]).strip().lower() == 'post'
            _emit_json({} if post else {'decision': 'allow'})
        return 0


if __name__ == '__main__':
    sys.exit(main())
