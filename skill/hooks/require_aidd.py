#!/usr/bin/env python3
"""
PreToolUse hook (matcher: "Write|Edit") — blocks writing/editing an application
source file until the aidd skill has been invoked at least once in this session.

Scope, by design:
- Only gates recognized source-code extensions (see _common.CODE_EXTENSIONS) —
  markdown, config, and aidd's own spec/design-system artifacts are never blocked,
  so starting or continuing aidd's own planning work is always unaffected.
- Enforced globally (every Claude Code session on this machine), per the user's own
  choice — not scoped to "projects that already use aidd."
- Does not (and cannot, via this hook alone) catch code written through Bash
  (heredocs, sed, etc.) — Write/Edit is the primary authoring path this covers.

Exit code 2 blocks the tool call and returns this hook's stderr to Claude as the
reason, so Claude sees exactly what to do next (invoke the Skill tool with
skill: "aidd") instead of just failing silently.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import read_event, marker_path, is_code_file  # noqa: E402

event = read_event()
tool_input = event.get('tool_input') or {}
file_path = tool_input.get('file_path')

if not is_code_file(file_path):
    sys.exit(0)

marker = marker_path(event.get('session_id'))
if marker.exists():
    sys.exit(0)

print(
    "aidd has not been invoked yet this session. AIDD is the default pipeline "
    "for ANY code change, whether or not it has a visual surface. Before writing "
    "or editing code, invoke the aidd skill (Skill tool, skill: \"aidd\") and "
    "follow its flow (search -> visual audit ONLY if there's a mockup, otherwise "
    "skip to align -> plan -> tasks -> build -> converge). If this change "
    "genuinely doesn't need the full flow, use aidd's 'fast lane' explicitly "
    "instead of skipping the skill.",
    file=sys.stderr,
)
sys.exit(2)
