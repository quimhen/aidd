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
path = marker_path(event.get('session_id'))
path.unlink(missing_ok=True)
sys.exit(0)
