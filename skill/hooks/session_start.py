#!/usr/bin/env python3
"""
SessionStart hook — resets this session's "aidd invoked" marker.

Every new Claude Code session starts without credit for a prior session's work:
the enforcement hook (require_aidd.py) treats aidd as not-yet-invoked until
mark_invoked.py sees it actually run in THIS session.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import read_event, marker_path  # noqa: E402

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
sys.exit(0)
