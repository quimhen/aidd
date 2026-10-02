#!/usr/bin/env python3
"""
PostToolUse hook (matcher: "Skill") — marks aidd as invoked for this session
once Claude actually calls the Skill tool with skill == "aidd".

Runs after every Skill tool call; it's a no-op for any skill that isn't aidd.
Tolerates non-dict payloads / non-string fields (exit 0, no traceback).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import read_event, marker_path  # noqa: E402

event = read_event()
if not isinstance(event, dict):
    event = {}
tool_input = event.get('tool_input')
if not isinstance(tool_input, dict):
    tool_input = {}
skill = tool_input.get('skill')
skill_name = skill.strip().lower() if isinstance(skill, str) else ''
_sid = event.get('session_id') if isinstance(event.get('session_id'), str) else None

if skill_name == 'aidd':
    try:
        marker_path(_sid).write_text('invoked', encoding='utf-8')
    except Exception:
        pass

sys.exit(0)
