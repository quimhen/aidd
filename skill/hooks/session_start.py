#!/usr/bin/env python3
"""
SessionStart hook — resets this session's "aidd invoked" marker.

Every new Claude Code session starts without credit for a prior session's work:
the enforcement hook (require_aidd.py) treats aidd as not-yet-invoked until
mark_invoked.py sees it actually run in THIS session.

Spec 007: when AIDD_RULES is warn/off and a project root is known it records
`rules_override{hook:'session_start', mode}` (aidd:FR-208 aidd:AC-214), and it prints (stdout becomes session
context) one line per approved open spec that is NOT the gate target but has code edits with no closing audit
(aidd:FR-206, same set stop_gate reminds about). Never fails the hook.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import read_event, marker_path, rules_mode  # noqa: E402

event = read_event()
if not isinstance(event, dict):
    event = {}
_sid = event.get('session_id') if isinstance(event.get('session_id'), str) else None
_cwd = event.get('cwd') if isinstance(event.get('cwd'), str) and event.get('cwd') else None

try:
    marker_path(_sid).unlink(missing_ok=True)
except Exception:
    pass

try:  # evidence recorder
    sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
    import aidd_evidence as _ev
    _ev.append(_ev.find_root(_cwd or Path.cwd()), _sid, 'session_start')
except Exception as _e:
    try:
        _ev.record_hook_error(_cwd, _sid, 'session_start', _e)
    except Exception:
        pass

try:  # aidd:FR-208 aidd:AC-214 warn/off made visible (only with a known project root)
    _mode = rules_mode()
    if _mode != 'enforce':
        _roots = _ev.project_roots(_cwd or str(Path.cwd()))
        if _roots:
            _ev.append(_roots[0], _sid, 'rules_override', hook='session_start', mode=_mode)
except Exception as _e:
    try:
        _ev.record_hook_error(_cwd, _sid, 'session_start', _e)
    except Exception:
        pass

try:  # aidd:FR-206 context lines about the other approved specs with unaudited edits
    import stop_gate as _sg
    _lib_ev, _lib_rules = _sg._libs()
    _root = _lib_ev.find_root(_cwd or Path.cwd())
    _targets = [str(t) for t in (_lib_ev.gate_target_specs(_root)[0] or [])]
    for _o in _sg._obligations(_lib_ev, _lib_rules, [_root]):
        if not _o[5]:      # not a gate target
            print(f"AIDD: spec {_o[1]} is approved and has {len(_o[3])} code edit(s) with no closing audit; "
                  f"gate target is {', '.join(_targets) or 'none'}; see `aidd status`")
except Exception as _e:
    try:
        _ev.record_hook_error(_cwd, _sid, 'session_start', _e)
    except Exception:
        pass
sys.exit(0)
