# Plan — AIDD 006: session attribution, phase-based audits, reliable hook recording

## Naming & File Contract (fill this first — everything below depends on it)
| Item | Convention |
|---|---|
| Classes / components / types | Not applicable (stdlib Python modules, no classes added) |
| Functions / variables / methods | snake_case, private helpers prefixed `_` (matches `_current_session`, `_r5_plan`, `_write_row`) |
| File names | snake_case `.py`; hooks in `skill/hooks/`, CLI logic in `skill/scripts/`, tests `tests/test_<area>.py` |
| Classes per file | One. No new files are planned except an optional `skill/hooks/record_dispatch_pre.py` (FR-004) |
| File-path pattern | Caller marker `<tmp>/aidd-hooks/caller-<sha1(root)>.json`; env override `AIDD_R7_FIX_EDITS` stays; new env `AIDD_CALLER_TTL` (default 120) |

No database objects in this feature.

## Root cause of the lost `spec_edit` (verified by reading the code)

`mark_code_edit.py` is correct: it appends `spec_edit` for `specs/<id>/plan.md` and `tasks.md` (lines 77-98) and its path logic matches the spec 005 files. The loss happens one layer down in `aidd_evidence.append` (skill/scripts/aidd_evidence.py:401-416): the whole body is wrapped in `except Exception: pass`, and `_write_row` takes `_locked()` (lines 326-356) whose `LOCK_TIMEOUT = 3.0` s raises `OSError('evidence lock timeout')` under contention (two windows plus every hook share one `.aidd/evidence/.lock`; `LOCK_STALE = 10.0`). That exception is swallowed by `append`, so it never becomes a `hook_error`, which matches the observed silent loss (`mark_code_edit` calls `record_hook_error` only if an exception escapes `append`, and none does). The same swallow explains the dropped `subagent` rows in `mark_agent_dispatch.py:91`. Aggravating factor: the PostToolUse hook does a cold Python start plus `import aidd_evidence` (and `aidd_rules` for the tasks.md hash) inside a 10 s timeout, so a slow start under load kills the process before append (also silent: no `hook_error` on a timeout kill). `approved` survives because it is written by a verified CLI/gate path (`append_approved`) outside the PostToolUse timeout. The spec hypothesis is confirmed in shape, with the precise mechanism: swallowed lock timeout in `append` plus hook timeout kill; neither writes a `hook_error`. The fix lives in `aidd_evidence.py` (retry, spill file, error record), not in the matching logic of `mark_code_edit.py`.

## Screen → Code map
No screens (no `SCREEN-nn` in this spec). FR → code map instead.

| FR | File / function to add or edit | Test file | PR (once opened) | Notes / exception to the convention |
|---|---|---|---|---|
| FR-001 | `skill/hooks/rule_gate.py`: new `_write_caller_marker(event)` called in `main()` after `_sync_transcript(event)` and BEFORE the cheap pre-check exit (line ~1078), only when `tool_name in SHELL_TOOLS` and the command invokes `aidd`. `skill/scripts/aidd_status.py`: `_current_session` (line 90) gets `_read_caller_marker(root)` (marker newer than 120 s, same sha1(root)) before the prompt fallback, and the prompt fallback skips synthetic prompts (text starting `<` or `[`) and `unknown-session`. Refusal messages in `cmd_close` (line ~595) and the approve path name the inferred session. Marker path helper `caller_marker_path(root)` in `skill/scripts/aidd_evidence.py` so hook and CLI agree. | `tests/test_rule_gate.py` (marker written / not written), `tests/test_aidd_status.py` (AC-001, AC-002), `tests/test_typed_confirmations.py` | | `_current_session` also serves approve/abandon: one change covers all |
| FR-002 | `skill/SKILL.md` Step 6 and `skill/AIDD.md` audit prose: phases (Mapper after first draft; ONE pre-build audit before tasks approval absorbing graph coherence; closing security+functional with executed evidence; performance only on hot path/DB/UI). `skill/scripts/aidd_rules.py`: `required_domains(d)` and the R7 block of `_evidence_rules` (line ~1777) match the phases. | `tests/test_aidd_rules.py`, `tests/test_check_spec.py` if prose checks exist | | Doc + R7 domain logic |
| FR-003 | `skill/scripts/aidd_rules.py` `_evidence_rules` (lines 1741-1762): drop "subagent after last spec.md edit", "after last plan.md edit" and the standalone "graph rebuilt but not audited" checks; replace by ONE pre-build check (a counting subagent exists after the find_spec run, before tasks approval). `skill/hooks/rule_gate.py` `_r5_plan` (line 200) and `_r5_tasks` (line 226) mirror it. `audit_since` / `AIDD_R7_FIX_EDITS` (aidd_rules.py:1489) and R14 `_subagent_counts` unchanged. | `tests/test_aidd_rules.py`, `tests/test_rule_gate.py`, `tests/test_r14.py`, `tests/test_stop_gate.py` (AC-005) | | `rule_gate.py` and `aidd_rules.py` duplicate R5 logic: change both in one task |
| FR-004 | `skill/scripts/aidd_evidence.py`: `append` (401) stops swallowing silently: on `_write_row` failure call a safe `_spill_row()` (tmp spill file) and `record_hook_error`; short retry/backoff beyond `LOCK_TIMEOUT`; `drain_spill(root)` merges spilled rows on the next successful append. `skill/hooks/mark_agent_dispatch.py`: append first, resolve model cheaply after (lighter hook), dedupe by `tool_use_id`. PreToolUse recording of dispatches: new `skill/hooks/record_dispatch_pre.py` (matcher `Task|Agent`). `skill/scripts/install_hooks.py` (lines 69-77): register it. | `tests/test_evidence.py` (lock timeout gives `hook_error` + spill), `tests/test_hooks.py` (AC-004), `tests/test_install_hooks.py` | | `aidd_evidence.py` shared with FR-005/006 |
| FR-005 | `skill/scripts/aidd_evidence.py` `open_specs` (line 1057): an `approved` event also opens a spec (until a later `spec_closed`). Recording hardening = the same `append` fix as FR-004 (`append` returns bool). `skill/hooks/mark_code_edit.py`: record `hook_error` when spec hits exist but append failed. `skill/scripts/aidd_status.py` `cmd_close` (574) message; status stops listing static R5/R7/R10/R11 WHY for not-open specs (aidd_status.py:267). | `tests/test_evidence.py` (AC-003), `tests/test_aidd_status.py`, `tests/test_cli_rules.py` | | Lands after FR-004 (same `append` change) |
| FR-006 | `skill/scripts/aidd_evidence.py` `sync_ask_answers`: accept a transcript answer only if its `tool_use_id` was also seen by `skill/hooks/mark_user_question.py`, or owner check on `transcript_path`; `skill/scripts/aidd_status.py` `_abandon_since` (line 605) / abandon: a later typed "No, keep it" cancels a clicked Abandon; optional perf in `rule_gate.py` `main()` (readline limit, skip evidence import on harmless Bash). | `tests/test_transcript_sync.py`, `tests/test_typed_confirmations.py`, `tests/test_r9_transcript.py` | | Optional perf item may be deferred at approval |
| FR-007 | No code. Run `aidd rules close 005-aidd-token-planning` after FR-005 is installed in `~/.claude/skills/aidd`, using the user's own recorded "Yes, close" (never forged). | manual check (AC-003) | | Owner installs the skill first |

Mirror note: `tests/test_dot_aidd_mirror.py` checks the `.aidd` script mirror; any edit of `skill/scripts/*` or `skill/hooks/*` must be synced in the same task.

## Component → Code map
No COMP-nnn. Shared modules (one owner per wave):

| Shared file | FRs touching it | Owner rule |
|---|---|---|
| `skill/scripts/aidd_evidence.py` | FR-001 (marker helper), FR-004, FR-005, FR-006 | one builder at a time |
| `skill/scripts/aidd_status.py` | FR-001, FR-005, FR-006 | serialize |
| `skill/hooks/rule_gate.py` | FR-001, FR-003, FR-006 (perf) | serialize or split by function |
| `skill/scripts/aidd_rules.py` | FR-002, FR-003 | one builder |
| `mark_agent_dispatch.py`, `mark_code_edit.py`, `install_hooks.py` | FR-004, FR-005 | with the evidence wave |
| `skill/SKILL.md`, `skill/AIDD.md` | FR-002, FR-003 (prose) | docs agent only |

## Wave split (disjoint files per wave; one test run at a time on this working tree)
| Wave | Scope | Files owned | Roles |
|---|---|---|---|
| 1 | FR-004 + FR-005 (recording reliability, open_specs) | `aidd_evidence.py`, `mark_agent_dispatch.py`, `mark_code_edit.py`, `install_hooks.py`, `record_dispatch_pre.py`, tests `test_evidence.py`, `test_hooks.py`, `test_install_hooks.py` | builder + tests agent |
| 2 | FR-003 + FR-002 code (R5/R7 engine) | `aidd_rules.py`, `rule_gate.py` (`_r5_plan`, `_r5_tasks` only), tests `test_aidd_rules.py`, `test_r14.py`, `test_stop_gate.py`, `test_rule_gate.py` | builder + tests |
| 3 | FR-001 (caller marker) | `aidd_status.py`, `rule_gate.py` (`main`, marker only), tests `test_aidd_status.py`, `test_typed_confirmations.py` | builder + tests; runs after wave 2 (shares `rule_gate.py`) |
| 4 | FR-006 (+ optional perf) | `aidd_evidence.py` (`sync_ask_answers`), `aidd_status.py` (abandon), `rule_gate.py` perf | builder + tests; after waves 1 and 3 |
| 5 | FR-002 prose + FR-007 | `SKILL.md`, `AIDD.md`, templates, mirror sync | docs agent; FR-007 by owner after install |
| Audits | Pre-build (before tasks approval): spec, plan, graph, estimates, sonnet or opus. Closing: security (marker in tmp, spill file, answer forgery in FR-006, opus) and functional with executed AC-001..AC-005. Performance only if FR-006 perf item is built | read-only | auditors |

Waves 2 and 3 could run in parallel only if `rule_gate.py` edits are merged by one agent; default is serial.

## Entry route
Not applicable (no screens).

## Device targets
| Item | Value |
|---|---|
| Target devices | Windows 11, Claude Code CLI (other hosts keep identical CLI behavior) |
| Orientation / minimum size | Not applicable |
| Device preflight command | `python -m pytest tests -q` (green before and after each wave) |

## Design system source (Step 0)
| Item | Value |
|---|---|
| Mockup exists? | no, waived in spec Pipeline route (tool internals only) |
| Approved design-system doc (if any) | None |
| Fidelity level decided in Clarify | Not applicable |
