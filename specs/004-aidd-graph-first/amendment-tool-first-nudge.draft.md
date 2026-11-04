# Draft — amendment to spec 004: a tool-first nudge that fires on repeated manual work

**DRAFT: not approved, not executable, no `Approved:` line.** Amendment intake: `AMENDMENT` of
`specs/004-aidd-graph-first` (same family as FR-025..FR-027, the graph-first nudge, and FR-039, the `aidd tools` catalog).
Owner direction (verbatim, 2026-11-03): "tenemos una regla de siempre utilizar herramientas pero en claude no siempre se cumple".

## Problem (observed, not assumed)
Rule T1 (use a tool before doing a repetitive or checkable step by hand) and the catalog `aidd tools` exist, but nothing
makes an agent follow them. In the b1SycLink session of 2026-11-03: OpenCode and agy lanes produced their files with
generator scripts (`gen_f36_tests.py`, `gen_f38_tests.py`, dry-run then apply), while the Claude orchestrator made 14
separate Edit calls to set the same Status cell and ran several one-off searches that a script covers. The catalog already
finds project tools (`aidd tools registry` lists `tools/spec_registry.py`), so discoverability is not the gap: enforcement is.

## Minimum Requirements Checklist

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | Claude Code hooks (`skill/hooks/`) and `aidd status` | repo — `skill/hooks/read_hint.py` | — |
| New development or modification? | New hook `tool_first_hint.py` + a status line; the graph-first hook is the model | repo — `skill/hooks/read_hint.py` | — |
| External service, API, integration? | None | owner brief 2026-11-03 | — |
| Who is requesting it? | Owner | user — "tenemos una regla de siempre utilizar herramientas pero en claude no siempre se cumple" | — |
| Dependencies? | `aidd tools` catalog (FR-039); session evidence events (FR-027 pattern) | repo — `specs/004-aidd-graph-first/spec.md` | — |
| Business objective | Repeated manual edits become a script with dry-run/apply/check, saving time and tokens | user — "opencode y agy utiliza siempre scripts para optimizar tiempos y gestión" | — |
| Expected visual fidelity | No mockup; CLI/hook only | — | — |

## Functional requirements

| Code | Requirement | Source |
|---|---|---|
| FR-049 | A `PostToolUse` hook on `Edit`, `Write`, `MultiEdit`, `NotebookEdit`, `Bash` and `PowerShell` counts repetition per session and emits ONE advisory line when any trigger fires: (a) N or more `Edit`/`MultiEdit` calls whose normalized change is the same (digits and quoted identifiers replaced by placeholders) within 15 minutes; (b) N or more `Edit` calls to one file within 15 minutes; (c) N or more consecutive `Bash`/`PowerShell` commands with the same normalized text, excluding read-only `git status/log/diff`. It only advises, never blocks. | measured: 14 identical Status edits in one session |
| FR-050 | The advice says: run `aidd tools <keywords>`; if no tool fits, write a script with dry-run, apply and check, and save it under `tools/` so the catalog indexes it. Keywords come from the file extension and directory of the repeated change. | user — "opencode y agy utiliza siempre scripts para optimizar tiempos y gestión" |
| FR-051 | Only an `aidd tools` query run BY THE AGENT silences the advice, for 300 s, recorded as a `tool_query` event (same rule as FR-026). Running a script does not silence it. | FR-026 pattern |
| FR-052 | Evidence, not trust: each advisory is a session event `tool_miss{kind,target,count}` and `aidd status` prints `tool-first: N advisories / M edits this session`. | FR-027 pattern |
| FR-053 | Fail open: any error in the hook (state file unreadable, malformed payload) emits nothing and exits 0. State lives in the per-session evidence directory, never in the project tree. | `skill/hooks/_common.py` convention |

## Acceptance criteria

| Code | Scenario | Expected |
|---|---|---|
| AC-041 | N identical-shape `Edit` calls on different files | exactly one advisory, on the Nth call |
| AC-042 | N edits to unrelated shapes | no advisory |
| AC-043 | `aidd tools <kw>` run, then repeated edits within 300 s | no advisory; after 300 s it fires again |
| AC-044 | Corrupt or missing state file | exit 0, no output, no exception |
| AC-045 | `aidd status` after two advisories | prints `tool-first: 2 advisories / M edits` |

## Open questions (owner decides; recommendation first)

- **Q-1 threshold N.** Options: (A) N = 4 (recommended: the session above would have been warned on the 4th of 14 edits); (B) N = 3; (C) N = 6.
- **Q-2 scope.** Options: (A) edits and shell commands (recommended); (B) edits only; (C) also advise on `Grep` loops.

## Tasks (design level; per-task Gemini-ready blocks are written after Q-1 and Q-2 are answered)

| Task | Codes satisfied | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-60 | FR-049..FR-053, AC-041..AC-045 | `tests/test_tool_first_hint.py` | LOGIC | | | any production code |
| T-61 | FR-049, FR-050, FR-051, FR-053 | `skill/hooks/tool_first_hint.py` | LOGIC | | | blocking behaviour; any other hook |
| T-62 | FR-049 (registration) | `skill/scripts/install_hooks.py` | LOGIC | | | any other host adapter |
| T-63 | FR-052 | `skill/scripts/aidd_status.py` | LOGIC | | | the verification and reuse code paths |
| T-64 | FR-050, FR-052 docs | `skill/SKILL.md` | LOGIC | | | any other section |

## Out of scope

Blocking an agent for doing manual work; judging whether a script is good; Codex/OpenCode/agy hosts (they already use
scripts); changing the `aidd tools` catalog itself.
