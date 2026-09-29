#!/usr/bin/env python3
"""
PostToolUse hook (matcher: "Skill") — marks aidd as invoked for this session
once Claude actually calls the Skill tool with skill == "aidd".

Runs after every Skill tool call; it's a no-op for any skill that isn't aidd.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import read_event, marker_path  # noqa: E402

event = read_event()
tool_input = event.get('tool_input') or {}
skill_name = str(tool_input.get('skill', '')).strip().lower()

if skill_name == 'aidd':
    marker_path(event.get('session_id')).write_text('invoked', encoding='utf-8')

sys.exit(0)
