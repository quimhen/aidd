#!/usr/bin/env python3
"""
PostToolUse hook (matcher: "Write|Edit|MultiEdit|NotebookEdit") — records the timestamp of the
most recent code-file edit this session (legacy marker) and the AIDD evidence:
  * `spec_edit{path,spec,file}` for specs/<id>/{spec,plan,tasks,mockup-audit,contracts,data-model}.md
    (case-insensitive CANONICAL basename, so PLAN.md / plan.md. / plan.md::$DATA / a/../plan.md,
    8.3 and junction forms all count); for tasks.md it stores the current approval_hash as `hash`.
    It NEVER emits `approved{spec,hash}`: only verified paths (rule_gate, `aidd rules approve`) do;
  * `code_edit{path,target,active}` for R6-gated files (is_r6_gated, not is_code_file), in EVERY project root above the file.
`.aidd/active_spec` is only maintained as an informational pointer; gates use open_specs().
`code_edit` carries target=<gate pointer> and active=<informational pointer> (aidd:FR-209). The PowerShell/Bash tools (tool_input.command) are tolerated
but record nothing here: a shell command's file writes cannot be attributed reliably (documented limit).
Always exits 0 — non-dict payloads / non-string fields are tolerated (hook_error recorded).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import read_event, write_timestamp, is_code_file, is_r6_gated  # noqa: E402

SPEC_FILES = {'spec.md', 'plan.md', 'tasks.md', 'mockup-audit.md', 'contracts.md', 'data-model.md'}
MAX_TASKS_BYTES = 2 * 1024 * 1024

event = read_event()
if not isinstance(event, dict):
    event = {}
_sid = event.get('session_id') if isinstance(event.get('session_id'), str) else None
_cwd = event.get('cwd') if isinstance(event.get('cwd'), str) and event.get('cwd') else None


def _paths(tool_input):
    out = []
    if not isinstance(tool_input, dict):
        return out
    for k in ('file_path', 'notebook_path'):
        v = tool_input.get(k)
        if isinstance(v, str) and v.strip():
            out.append(v)
    edits = tool_input.get('edits')
    if isinstance(edits, list):
        for e in edits:
            if isinstance(e, dict):
                for k in ('file_path', 'notebook_path'):
                    v = e.get(k)
                    if isinstance(v, str) and v.strip():
                        out.append(v)
    seen, uniq = set(), []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


_paths_in = _paths(event.get('tool_input'))

try:  # legacy timestamp
    if any(is_code_file(p) for p in _paths_in):
        write_timestamp(_sid, 'last_code_edit_ts')
except Exception:
    pass


try:  # evidence recorder
    sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
    import aidd_evidence as _ev

    def _lost(_kind, _fp):
        try:
            _ev.record_hook_error(_cwd, _sid, 'mark_code_edit', 'append returned False: %s row lost (%s)' % (_kind, _fp))
        except Exception:
            pass

    for _fp in _paths_in:
        _p = Path(_fp)
        if not _p.is_absolute():
            _p = Path(_cwd or Path.cwd()) / _p
        _roots = _ev.project_roots(_p)
        if not _roots:
            continue
        _real = _ev.real_path(_p)
        _base = _real.name.lower()
        _hits = []
        if _base in SPEC_FILES:
            for _r in _roots:
                try:
                    _parts = _real.relative_to(_ev.real_path(_r)).parts
                except ValueError:
                    continue
                if len(_parts) == 3 and _parts[0].lower() == 'specs':
                    _hits.append((_r, _parts[1]))
        if _hits:
            _extra = {}
            # NOTE (N1): this recorder never emits `approved` — only verified paths (rule_gate after
            # checking the answer, `aidd rules approve`) call aidd_evidence.append_approved.
            if _base == 'tasks.md':
                try:
                    import aidd_rules as _rules
                    if _real.stat().st_size <= MAX_TASKS_BYTES:
                        _extra['hash'] = _rules.approval_hash(_real.read_text(encoding='utf-8', errors='replace'))
                except Exception:
                    pass
            for _r, _sp in _hits:
                if _ev.append(_r, _sid, 'spec_edit', path=str(_fp), spec=_sp, file=_base, **_extra) is False:
                    _lost('spec_edit', _fp)
                _ev.set_active_spec(_r, _sp)  # informational pointer only
        else:
            # aidd:FR-209 the R6 predicate (deny-list: .css/.json/.html/web.config are code,
            # .md and specs/ are not) replaces is_code_file here; is_code_file stays for require_aidd.
            try:
                _canon = _ev.canon_path(_p)
                _outer = _ev.rel_to_root(_p, _roots[-1])
                _gated = is_r6_gated(_canon, _outer)
            except Exception:
                _gated = False
            if _gated:
                for _r in _roots:
                    _stamp = {}
                    try:  # a failed pointer read (or an older library) never loses the base event
                        _stamp['target'] = _ev.get_gate_spec(_r) or ''
                        _stamp['active'] = _ev.get_active_spec(_r) or ''
                    except Exception:
                        _stamp = {}
                    if _ev.append(_r, _sid, 'code_edit', path=str(_fp), **_stamp) is False:
                        _lost('code_edit', _fp)
except Exception as _e:
    try:
        _ev.record_hook_error(_cwd, _sid, 'mark_code_edit', _e)
    except Exception:
        pass

sys.exit(0)
