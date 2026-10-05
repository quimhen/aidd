#!/usr/bin/env python3
"""
PostToolUse hook (matcher: "Task|Agent") — records the timestamp of the most
recent subagent dispatch this session. Any dispatch counts (this hook can't
know what the subagent was asked to do) — it's a heuristic, not a formal
proof of a correct independent audit. Paired with mark_code_edit.py and
require_independent_audit.py.

Matcher name note: Claude Code's built-in subagent-dispatch tool is matched
here as "Task|Agent" to cover naming across versions/configurations — if
neither name is right for a given setup, this hook simply never fires, which
fails safe (require_independent_audit.py still blocks qa-audit.md writes;
it just can't be un-blocked by a dispatch it never saw). Adjust the matcher
in settings.json if you confirm the actual tool name differs.
"""
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import read_event, write_timestamp  # noqa: E402

event = read_event()
if not isinstance(event, dict):
    event = {}
_sid = event.get('session_id') if isinstance(event.get('session_id'), str) else None
_cwd = event.get('cwd') if isinstance(event.get('cwd'), str) and event.get('cwd') else None


def _s(v):
    return v if isinstance(v, str) else ''


# R14: the built-in Explore agent runs on the lowest tier (haiku) even with no explicit model.
BUILTIN_AGENT_MODELS = {'explore': 'haiku'}


def _agent_file_model(name, cwd):
    """`model:` from the frontmatter of <cwd>/.claude/agents/<name>.md, then ~/.claude/agents/<name>.md.
    Plugin agents are out of scope. Never raises; '' when unresolved."""
    try:
        if not name or not re.fullmatch(r'[\w.\-]{1,100}', name):
            return ''
        for base in (Path(cwd) if cwd else Path.cwd(), Path.home()):
            f = base / '.claude' / 'agents' / (name + '.md')
            if not f.is_file():
                continue
            lines = f.read_text(encoding='utf-8', errors='replace').splitlines()
            if not lines or lines[0].strip() != '---':
                continue
            for ln in lines[1:60]:
                if ln.strip() == '---':
                    break
                m = re.match(r'model\s*:\s*(.*)$', ln)     # unindented top-level key only (M1)
                if m:
                    return m.group(1).strip().strip('\'"').strip()[:200]
    except Exception:
        pass
    return ''


def _resolve_model(ti, cwd):
    """-> (model, source). Unresolved stays ('', '') which counts as an auditor (fail-open, documented)."""
    explicit = _s(ti.get('model')).strip()
    if explicit:
        return explicit[:200], 'tool_input'
    st = _s(ti.get('subagent_type')).strip()
    if st.lower() in BUILTIN_AGENT_MODELS:
        return BUILTIN_AGENT_MODELS[st.lower()], 'builtin'
    m = _agent_file_model(st, cwd)
    if m:
        return m, 'agent_file'
    return '', ''


def _response_text(resp):
    """aidd:FR-209 Best-effort text of a PostToolUse `tool_response`: a string; a dict with `content`
    (string or list of {type:'text', text}) or `result`/`output`/`text`; a list of those. '' when none.
    Never raises."""
    try:
        if isinstance(resp, str):
            return resp
        if isinstance(resp, list):
            return '\n'.join(t for t in (_response_text(x) for x in resp) if t)
        if isinstance(resp, dict):
            if resp.get('type') == 'text' and isinstance(resp.get('text'), str):
                return resp['text']
            c = resp.get('content')
            if c is not None:
                t = _response_text(c)
                if t:
                    return t
            for k in ('result', 'output', 'text'):
                t = _response_text(resp.get(k)) if not isinstance(resp.get(k), dict) else ''
                if t:
                    return t
    except Exception:
        pass
    return ''


def _record_subagent():
    """FR-004: append the counting `subagent` row FIRST (before any other work), with the model
    always resolved (_resolve_model). The PreToolUse recorder's phase='pre' row is attribution only
    and does NOT suppress this row; dedupe only skips a duplicate POST row with the same tool_use_id.
    A failed append (False) writes a hook_error."""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
        import aidd_evidence as _ev
    except Exception:
        return
    try:
        _ti = event.get('tool_input')
        if not isinstance(_ti, dict):
            _ti = {}
        _root = _ev.find_root(_cwd or Path.cwd())
        _tid = _s(event.get('tool_use_id'))[:_ev.TOOL_USE_ID_MAX]
        if _tid:
            for _e in _ev.events(_root, session=_sid, kind='subagent'):
                _d = _e.get('detail') or {}
                if _d.get('tool_use_id') == _tid and _d.get('phase') != 'pre':
                    return
        try:
            _model, _msrc = _resolve_model(_ti, _cwd)
        except Exception:
            _model, _msrc = _s(_ti.get('model'))[:200], ''
        detail = dict(phase='post',
                      type=_s(_ti.get('subagent_type')),
                      model=_model,
                      model_source=_msrc,
                      desc=_s(_ti.get('description'))[:200],
                      head=_ev.redact_secrets(_s(_ti.get('prompt')), limit=400)[0])
        if _tid:
            detail['tool_use_id'] = _tid
        try:  # aidd:FR-209 size and hash of the final report; absent when the payload has no text
            _txt = _response_text(event.get('tool_response'))
            if _txt.strip():
                detail['result_chars'] = len(_txt)
                detail['result_sha1'] = hashlib.sha1(_txt.encode('utf-8', 'replace')).hexdigest()
        except Exception:
            pass
        if not _ev.append(_root, _sid, 'subagent', **detail):
            _ev.record_hook_error(_cwd, _sid, 'mark_agent_dispatch', 'subagent row not recorded')
    except Exception as _e:
        try:
            _ev.record_hook_error(_cwd, _sid, 'mark_agent_dispatch', _e)
        except Exception:
            pass


_record_subagent()

try:
    write_timestamp(_sid, 'last_agent_dispatch_ts')
except Exception:
    pass

sys.exit(0)
