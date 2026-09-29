#!/usr/bin/env python3
"""
PostToolUse hook (matcher: "Write|Edit") — records the timestamp of the most
recent code-file edit this session. Paired with mark_agent_dispatch.py and
require_independent_audit.py to enforce that Step 6's independent Auditor
(a separate Agent/Task dispatch) runs AFTER the last code change, not before
it and not never — see require_independent_audit.py for the actual gate.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import read_event, write_timestamp, is_code_file  # noqa: E402

event = read_event()
tool_input = event.get('tool_input') or {}
file_path = tool_input.get('file_path')

if is_code_file(file_path):
    write_timestamp(event.get('session_id'), 'last_code_edit_ts')

sys.exit(0)
