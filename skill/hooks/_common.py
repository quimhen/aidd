"""Shared helpers for aidd's enforcement hooks. Stdlib only."""
import json
import sys
import time
import tempfile
from pathlib import Path

MARKER_DIR = Path(tempfile.gettempdir()) / "aidd-hooks"

# Extensions treated as "application source code" — the hook only gates these.
# Anything else (markdown, json/yaml config, txt, spec artifacts) is never blocked,
# so aidd's own planning files (mockup-audit.md, plan.md, etc.) are always writable.
CODE_EXTENSIONS = {
    '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.vue', '.svelte',
    '.dart', '.py', '.java', '.kt', '.kts', '.cs', '.go', '.rb', '.php',
    '.swift', '.c', '.cpp', '.cc', '.h', '.hpp', '.rs', '.scala', '.sql',
}


def read_event():
    """Read the hook event JSON Claude Code sends on stdin. Returns {} on any parse failure
    so a hook never crashes the calling session over a malformed/absent payload."""
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def marker_path(session_id):
    MARKER_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = session_id or 'unknown-session'
    return MARKER_DIR / f'{safe_id}.invoked'


def timestamps_path(session_id):
    """Per-session marker holding two floats: last_code_edit_ts and
    last_agent_dispatch_ts — used to enforce that Step 6's independent
    Auditor pass (a separate Agent/Task tool dispatch) happens AFTER the
    most recent code edit, not just at some point earlier in the session."""
    MARKER_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = session_id or 'unknown-session'
    return MARKER_DIR / f'{safe_id}.timestamps.json'


def read_timestamps(session_id):
    path = timestamps_path(session_id)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}


def write_timestamp(session_id, key):
    """Record `key` (e.g. 'last_code_edit_ts' or 'last_agent_dispatch_ts')
    as now. Best-effort — a write failure here never blocks the calling hook."""
    data = read_timestamps(session_id)
    data[key] = time.time()
    try:
        timestamps_path(session_id).write_text(json.dumps(data), encoding='utf-8')
    except OSError:
        pass


def is_qa_audit_file(file_path):
    if not file_path:
        return False
    return Path(file_path).name == 'qa-audit.md'


def is_code_file(file_path):
    if not file_path:
        return False
    p = Path(file_path)
    if p.suffix.lower() not in CODE_EXTENSIONS:
        return False
    parts_lower = [part.lower() for part in p.parts]
    parts_set = set(parts_lower)
    # Never gate aidd's own artifacts, even if a project puts non-.md files there.
    if 'specs' in parts_set or 'design-system' in parts_set:
        return False
    # Never gate editing an installed skill's own source (~/.claude/skills/<any>/**) —
    # maintaining a skill is not "using" it, and would otherwise be a chicken-and-egg
    # lock (editing aidd's own .py files would require invoking aidd first).
    if '.claude' in parts_lower and 'skills' in parts_lower:
        return False
    return True
