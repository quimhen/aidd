#!/usr/bin/env python3
"""
aidd hook installer — merges the enforcement hooks into ~/.claude/settings.json.

Run this ONCE after copying the aidd skill into ~/.claude/skills/ on any device:
    python ~/.claude/skills/aidd/scripts/install_hooks.py

What it installs (global scope, per the user's own choice — every Claude Code
session on this machine, not just projects that already use aidd). 11 hooks:
  - SessionStart   -> hooks/session_start.py    resets the per-session marker
  - PostToolUse    -> hooks/mark_invoked.py      (matcher: Skill) marks aidd invoked
  - PreToolUse     -> hooks/rule_gate.py (matcher: Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell) THE single gate
                       (spec 002 "Hard Rules"): protected evidence paths (R9), code
                       blocked until aidd is invoked, qa-audit.md needs independent
                       per-domain auditors (R7), plan/tasks chain order (R5), tasks
                       approval by the user (R6), visual debt (R4), content rules.
                       It folds the former require_aidd / require_independent_audit /
                       require_graph_coherence_audit entries into ONE process.
  - UserPromptSubmit -> hooks/prompt_trigger.py  nudges aidd on requirement/
                       planning/new-feature language; records the prompt as evidence
  - PostToolUse    -> hooks/mark_code_edit.py    (matcher: Write|Edit|MultiEdit|NotebookEdit|PowerShell) records code/spec edits
  - PostToolUse    -> hooks/mark_agent_dispatch.py (matcher: Task|Agent) records subagents
  - PostToolUse    -> hooks/mark_graph_rebuild.py (matcher: Bash|PowerShell) records find_spec.py runs
  - SessionStart   -> hooks/memory_context.py (matcher: startup|resume|clear|
                       compact) injects the AIDD memory digest (silent when the
                       project has no .aidd/memory/)
  - PostToolUse    -> hooks/mark_user_question.py (matcher: AskUserQuestion) records
                       that the human was asked (evidence for R6 approvals)
  - Stop           -> hooks/stop_gate.py  R8: no stopping with an approved, implemented
                       spec that has no closing audit
  - PreToolUse     -> hooks/read_hint.py (matcher: Read) W1 hint (spec 004, FR-008):
                       non-blocking nudge toward the graph before reading raw files

MIGRATION: the three old aidd PreToolUse entries (require_aidd.py,
require_independent_audit.py, require_graph_coherence_audit.py) are REMOVED from
settings.json when present — rule_gate.py replaces them. Only entries whose command
points at those aidd hook scripts are removed; any other hook is left alone.

Escape hatch (owner only): set env AIDD_RULES=warn (messages only) or off in
settings.json "env". Default = enforce.

OPT-IN (not installed by default — it spawns one extra process on EVERY Read/
Edit/Write, which is not worth it on machines where hook startup is flaky):
  python install_hooks.py --with-memory-file-hook
  - PreToolUse     -> hooks/memory_file_context.py (matcher: Read|Edit|Write)
                       once per (session, file), adds the memory entries that
                       mention that file; never blocks. Without it, the same
                       lookup is available on demand: `aidd mem file <path>`.

Every entry carries a "timeout" (15 s for rule_gate/stop_gate, 10 s for the rest). Idempotent: safe
to run more than once. It appends an entry if a hook with the same command isn't present; if the aidd
entry exists with an OLD matcher or without a timeout it is UPGRADED in place (replaced); it never
touches hooks belonging to anything else already configured (apart from the migration above).

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
    ('PreToolUse', 'Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell', SKILL_DIR / 'hooks' / 'rule_gate.py'),
    ('UserPromptSubmit', None, SKILL_DIR / 'hooks' / 'prompt_trigger.py'),
    ('PostToolUse', 'Write|Edit|MultiEdit|NotebookEdit|PowerShell', SKILL_DIR / 'hooks' / 'mark_code_edit.py'),
    ('PostToolUse', 'Task|Agent', SKILL_DIR / 'hooks' / 'mark_agent_dispatch.py'),
    ('PostToolUse', 'Bash|PowerShell', SKILL_DIR / 'hooks' / 'mark_graph_rebuild.py'),
    ('SessionStart', 'startup|resume|clear|compact', SKILL_DIR / 'hooks' / 'memory_context.py'),
    ('PostToolUse', 'AskUserQuestion', SKILL_DIR / 'hooks' / 'mark_user_question.py'),
    ('Stop', None, SKILL_DIR / 'hooks' / 'stop_gate.py'),
    ('PreToolUse', 'Read', SKILL_DIR / 'hooks' / 'read_hint.py'),
]

# Seconds a hook may run before Claude Code kills it (a killed gate is a skipped gate, so every
# entry carries one). Gates 15, everything else 10.
HOOK_TIMEOUTS = {'rule_gate.py': 15, 'stop_gate.py': 15}
DEFAULT_TIMEOUT = 10


def timeout_for(script_path):
    return HOOK_TIMEOUTS.get(Path(script_path).name, DEFAULT_TIMEOUT)


# Old aidd entries folded into rule_gate.py; removed on install (migration).
LEGACY_HOOK_NAMES = ('require_aidd.py', 'require_independent_audit.py', 'require_graph_coherence_audit.py')

# Installed only with `--with-memory-file-hook` (see the module docstring).
OPTIONAL_HOOK_DEFS = [
    ('PreToolUse', 'Read|Edit|Write', SKILL_DIR / 'hooks' / 'memory_file_context.py'),
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


def already_installed(event_entries, command, matcher=None, timeout=None):
    """True iff an entry already carries `command` (with, when given, exactly this matcher and timeout)."""
    for entry in event_entries:
        for h in entry.get('hooks', []):
            if h.get('command') == command:
                if matcher is None and timeout is None:
                    return True
                if (entry.get('matcher') or None) == (matcher or None) and h.get('timeout') == timeout:
                    return True
    return False


def drop_command(event_entries, command):
    """Remove `command` from every entry (aidd's own hook only); entries left empty are dropped, any
    other hook sharing the entry is kept. Returns the new list."""
    out = []
    for entry in event_entries:
        hs = entry.get('hooks', [])
        left = [h for h in hs if h.get('command') != command]
        if len(left) == len(hs):
            out.append(entry)
        elif left:
            out.append(dict(entry, hooks=left))
    return out


def _is_legacy_aidd_command(command):
    """True for `python ".../hooks/<old gate>.py"` — an aidd hook that rule_gate.py replaced."""
    c = (command or '').replace(chr(92), '/')
    return any(c.rstrip('" ').endswith('/hooks/' + n) for n in LEGACY_HOOK_NAMES)


def remove_legacy(settings):
    """Drop the old aidd gate commands; prune entries/events left empty. Returns count removed."""
    removed = 0
    hooks = settings.get('hooks') or {}
    for event_name in list(hooks):
        kept = []
        for entry in hooks[event_name]:
            hs = entry.get('hooks', [])
            left = [h for h in hs if not _is_legacy_aidd_command(h.get('command'))]
            removed += len(hs) - len(left)
            if left or not hs:
                entry = dict(entry, hooks=left) if len(left) != len(hs) else entry
                kept.append(entry)
        hooks[event_name] = kept
        if not kept:
            del hooks[event_name]
    return removed


def main(argv=None):
    # Not argparse on purpose: callers (and tests) invoke main() with no args while
    # sys.argv belongs to someone else (e.g. unittest's own flags).
    argv = sys.argv[1:] if argv is None else argv
    defs = list(HOOK_DEFS)
    if '--with-memory-file-hook' in argv:
        defs += OPTIONAL_HOOK_DEFS

    settings = load_settings()
    settings.setdefault('hooks', {})

    removed = remove_legacy(settings)
    settings.setdefault('hooks', {})

    added, upgraded = [], []
    for event_name, matcher, script_path in defs:
        command = command_for(script_path)
        timeout = timeout_for(script_path)
        settings['hooks'].setdefault(event_name, [])
        entries = settings['hooks'][event_name]

        if already_installed(entries, command, matcher, timeout):
            continue
        was_there = already_installed(entries, command)
        if was_there:                      # old matcher / no timeout: REPLACE the aidd entry (foreign hooks stay)
            settings['hooks'][event_name] = entries = drop_command(entries, command)
            upgraded.append(event_name)
        else:
            added.append(event_name)

        new_entry = {'hooks': [{'type': 'command', 'command': command, 'timeout': timeout}]}
        if matcher:
            new_entry['matcher'] = matcher
        entries.append(new_entry)

    if not added and not removed and not upgraded:
        print("Already installed — no changes made.")
        return

    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    if removed:
        print(f"Migrated: removed {removed} old aidd gate entr{'y' if removed == 1 else 'ies'} "
              f"({', '.join(LEGACY_HOOK_NAMES)}) — replaced by rule_gate.py.")
    if upgraded:
        print(f"Upgraded (new matcher / timeout): {', '.join(upgraded)}")
    print(f"Installed/updated hooks: {', '.join(added) or 'none new'}")
    print(f"Written to {SETTINGS_PATH}")
    print("Restart Claude Code sessions for the change to take effect.")


if __name__ == '__main__':
    main()
