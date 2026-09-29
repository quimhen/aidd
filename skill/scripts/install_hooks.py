#!/usr/bin/env python3
"""
aidd hook installer — merges the enforcement hooks into ~/.claude/settings.json.

Run this ONCE after copying the aidd skill into ~/.claude/skills/ on any device:
    python ~/.claude/skills/aidd/scripts/install_hooks.py

What it installs (global scope, per the user's own choice — every Claude Code
session on this machine, not just projects that already use aidd):
  - SessionStart   -> hooks/session_start.py    resets the per-session marker
  - PostToolUse    -> hooks/mark_invoked.py      (matcher: Skill) marks aidd invoked
  - PreToolUse     -> hooks/require_aidd.py   (matcher: Write|Edit) blocks code
                       files until aidd has been invoked this session
  - UserPromptSubmit -> hooks/prompt_trigger.py  nudges aidd on requirement/
                       planning/new-feature language in the user's own message
  - PostToolUse    -> hooks/mark_code_edit.py    (matcher: Write|Edit) timestamps
                       the last code-file edit this session
  - PostToolUse    -> hooks/mark_agent_dispatch.py (matcher: Task|Agent) timestamps
                       the last independent subagent dispatch this session
  - PreToolUse     -> hooks/require_independent_audit.py (matcher: Write|Edit)
                       blocks writing qa-audit.md unless a subagent was
                       dispatched after the last code edit — Step 6's Auditor
                       must never be the same agent that wrote the fix
  - PostToolUse    -> hooks/mark_graph_rebuild.py (matcher: Bash) timestamps
                       the last find_spec.py run that reported "Graph index:
                       rebuilt" this session
  - PreToolUse     -> hooks/require_graph_coherence_audit.py (matcher:
                       Write|Edit) blocks writing plan.md/tasks.md unless a
                       subagent was dispatched after the last graph rebuild —
                       Step 3/4 must never plan/task against a rebuilt-but-
                       unverified graph

Idempotent: safe to run more than once. It only appends an entry if a hook with
the same command isn't already present, and it never touches hooks belonging to
anything else already configured.

Uninstall: remove the "aidd" hook entries from ~/.claude/settings.json by
hand, or delete the whole "hooks" key if aidd's installer was the only thing
that ever wrote to it.
"""
import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SETTINGS_PATH = Path.home() / '.claude' / 'settings.json'

HOOK_DEFS = [
    ('SessionStart', None, SKILL_DIR / 'hooks' / 'session_start.py'),
    ('PostToolUse', 'Skill', SKILL_DIR / 'hooks' / 'mark_invoked.py'),
    ('PreToolUse', 'Write|Edit', SKILL_DIR / 'hooks' / 'require_aidd.py'),
    ('UserPromptSubmit', None, SKILL_DIR / 'hooks' / 'prompt_trigger.py'),
    ('PostToolUse', 'Write|Edit', SKILL_DIR / 'hooks' / 'mark_code_edit.py'),
    ('PostToolUse', 'Task|Agent', SKILL_DIR / 'hooks' / 'mark_agent_dispatch.py'),
    ('PreToolUse', 'Write|Edit', SKILL_DIR / 'hooks' / 'require_independent_audit.py'),
    ('PostToolUse', 'Bash', SKILL_DIR / 'hooks' / 'mark_graph_rebuild.py'),
    ('PreToolUse', 'Write|Edit', SKILL_DIR / 'hooks' / 'require_graph_coherence_audit.py'),
]


def command_for(script_path):
    return f'python "{script_path}"'


def load_settings():
    if SETTINGS_PATH.exists():
        try:
            return json.loads(SETTINGS_PATH.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            print(f"WARNING: {SETTINGS_PATH} exists but isn't valid JSON — "
                  f"not touching it. Fix or back it up, then re-run this installer.")
            sys.exit(1)
    return {}


def already_installed(event_entries, command):
    for entry in event_entries:
        for h in entry.get('hooks', []):
            if h.get('command') == command:
                return True
    return False


def main():
    settings = load_settings()
    settings.setdefault('hooks', {})

    added = []
    for event_name, matcher, script_path in HOOK_DEFS:
        command = command_for(script_path)
        settings['hooks'].setdefault(event_name, [])
        entries = settings['hooks'][event_name]

        if already_installed(entries, command):
            continue

        new_entry = {'hooks': [{'type': 'command', 'command': command}]}
        if matcher:
            new_entry['matcher'] = matcher
        entries.append(new_entry)
        added.append(event_name)

    if not added:
        print("Already installed — no changes made.")
        return

    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f"Installed/updated hooks: {', '.join(added)}")
    print(f"Written to {SETTINGS_PATH}")
    print("Restart Claude Code sessions for the change to take effect.")


if __name__ == '__main__':
    main()
