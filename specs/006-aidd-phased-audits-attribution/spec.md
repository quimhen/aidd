# Spec — AIDD 006: session attribution, phase-based audits, reliable hook recording

Risk: medium
<!-- medium: changes to the rule engine and hooks of the tool itself; no SAP/DB/money. Audits on sonnet or opus, never haiku -->

## Minimum Requirements Checklist (fill before Step 3 starts)

| Question | Answer | Source |
|---|---|---|
| Which module/area of the system? | `skill/hooks/`, `skill/scripts/` (aidd_status, aidd_evidence, rule_gate, mark_* hooks), `skill/SKILL.md`, `skill/AIDD.md` | repo — skill/scripts/aidd_status.py:90 |
| New development or modification of something existing? | Modification of AIDD specs 002/004/005 behaviour (attribution, audit rules, hook recording) | repo — specs/005-aidd-token-planning/qa-audit.md:1 |
| Does it involve an external service, API, or integration? | No. Local hooks and stdlib Python only | repo — skill/scripts/aidd_status.py:4 |
| Who is requesting it? (role/profile, not necessarily the name) | The AIDD owner, after hitting the bugs in a parallel window (Integraciones) | [Proposed — unconfirmed] |
| Dependencies on other modules or active developments? | Spec 005 installed in `~/.claude/skills/aidd` (done). Spec 005 close is NOT recorded, see FR-007 | repo — specs/005-aidd-token-planning/qa-audit.md:1 |
| Business objective (1 sentence — what it achieves and why) | Fewer approvals and fewer audits, correct session attribution across windows, and evidence that is actually recorded | user — "ubicarla en fases especificas para evitar auditar a cada momento" |
| Expected visual fidelity level (if there's a mockup): exact \| functional behavior only | Not applicable: no visual surface | repo — skill/SKILL.md "If the feature has no visual surface, skip entirely" |

## Pipeline route

| Step | Status | Reason | Confirmation |
|---|---|---|---|
| -1 | run | find_spec matched 002 only by keywords; distinct feature area (follow-up of 004/005), new spec | |
| 0 | waived | no visual surface, tool internals only | user — "adiciona la investigacion en el spec 006 y procedamos" |
| 1 | waived | no visual surface, tool internals only | user — "adiciona la investigacion en el spec 006 y procedamos" |
| 1.5 | waived | no visual surface, tool internals only | user — "adiciona la investigacion en el spec 006 y procedamos" |
| 2 | run | | |
| 3 | run | | |
| 4 | run | | |

## Visual debt

None: no `SCREEN-nn` codes in this spec.

## Scope
- **Included:** caller marker for session attribution; audit phases (R5/R7 rules and SKILL/AIDD prose); hardening of hook recording (Agent dispatch, Write/Edit of plan.md and tasks.md); the close-refusal finding of spec 005; the open items of 005 listed in FR-006.
- **Excluded:** UI of any kind; changes to R1-R4, R10-R14 semantics; the tasks-to-issues providers; other hosts (OpenCode, Codex) beyond keeping the CLI behaviour identical.

## Investigation added by the user (2026-10-03): spec 005 would not close

User asked to add this finding to the spec ("adiciona la investigacion en el spec 006"). Facts, measured on `.aidd/evidence/events.toon`:

- `aidd rules close 005-aidd-token-planning` answered "not an open spec (no tasks.md edit recorded)" after the user typed `Yes, close [spec:005-aidd-token-planning]`. `aidd status` shows `005 [not open]` although tasks are approved and `qa-audit.md` exists.
- The log holds `spec_edit` events for 005 only on `spec.md` (14). There is NO `spec_edit` for `plan.md` or `tasks.md` of 005, yet the `approved` event exists (hash cca39e73eb06, session 3026cc79). 004 has the same shape: `spec.md` 8, `plan.md` 1, no `tasks.md`.
- Conclusion: the PostToolUse recording of Write/Edit on `plan.md`/`tasks.md` is lossy (same family as the dropped Agent dispatches: 6 in spec 005). A spec is "open" only through those events, so a lost event makes an approved, audited spec impossible to close and also silently disables R6/R7/R8 for it.
- Not the cause: `hook_error` has 23 entries, all from `rule_gate` with `unknown-session` and an old `AttributeError('str' has no 'get')`; none from the recording hooks. A timeout does not write `hook_error`, which is why the loss is silent.
- Second real case (pasted by the user from another project, spec `002-actividad-visita-fix`): a Mapper dispatch was not recorded in that session's log, so R5 blocked `plan.md` ("No independent subagent ran after the last edit of spec.md") although the subagent had run. Same family: `aidd_evidence.append` swallows lock timeouts (`except Exception: pass`, lock 3 s, shared by all windows), so the loss is silent. Root cause found by the Mapper in `aidd_evidence.py:401-416`; the fix belongs there (retry, spill, `hook_error`, bool result), not in the matchers.
- Side finding: `aidd status` for 005 still lists R5/R7/R10/R11 as WHY blocked while saying `[not open]`; those are static-rule messages and may mislead once a spec is closed.

## Functional requirements

| FR-nnn | Requirement | Cites |
|---|---|---|
| FR-001 | `rule_gate` writes a caller marker `<tmp>/aidd-hooks/caller-<sha1(root)>.json` `{session, ts}` before any Bash/PowerShell command that invokes `aidd`; `_current_session` prefers a marker newer than ~120 s for the same root, else the newest NON-synthetic prompt (not starting with `<` or `[`); refusals name the inferred session | skill/scripts/aidd_status.py:90 |
| FR-002 | Audits run by phases: Mapper once after the first spec draft; ONE pre-build audit of implementation coherence (spec, plan, graph, estimates) right before tasks approval, absorbing the separate graph-coherence audit; closing audits after coding: security and functional with executed evidence; performance only when the change touches hot paths, DB or UI | SKILL.md Step 6, rule R7 |
| FR-003 | R5 stops requiring a subagent after each spec/plan edit; the R7 fix-edit tolerance (`AIDD_R7_FIX_EDITS`) stays; audits on medium or high, never haiku (R14 unchanged) | rule R5, R14 |
| FR-004 | Recording of EVERY evidence event is lossless under contention, user `prompt`, `question` and `answer` included (observed 2026-10-03: the user's typed messages "listo", "corrige", "Yes, close ..." never reached the session log, so `aidd rules approve` refused a valid click of "Approve" and the spec deadlocked before build). Agent dispatch recording does not depend on a PostToolUse hook finishing under its 10 s timeout: lighter hook and/or record from PreToolUse, and a `hook_error` event is written on timeout or crash | skill/hooks/mark_agent_dispatch.py |
| FR-005 | Recording of `plan.md`/`tasks.md` edits becomes reliable (same hardening as FR-004), and a spec with an `approved` event but no recorded `plan.md`/`tasks.md` edit counts as open so it can be closed or abandoned | skill/scripts/aidd_status.py (close), skill/hooks/mark_code_edit.py |
| FR-006 | Open items of 005: accept transcript answers only if the tool_use_id was also seen by a PostToolUse hook or add a transcript-owner check (`'.cl'+'aude'` gap); a clicked Abandon is cancelled by a later typed "No, keep it"; optional perf (readline limit, skip evidence import on harmless Bash) | specs/005-aidd-token-planning/qa-audit.md |
| FR-008 | Step 4 planning guidance in the skill (SKILL.md, AIDD.md, templates/tasks.md, adapters/dot-aidd copies) and a mechanical gap in `check_spec.py` so the planner cannot repeat the spec 006 mistakes: (a) ONE owner agent per target file/class, who makes ALL the small changes to that file; two task rows with the same target file are one task, never two agents (one-code-one-file-one-PR is a review-size concern, not an agent split); (b) waves are derived from an explicit dependency graph: only a true dependency (needs another task's output or file) goes in a later wave; everything independent, including docs, tests against an interface fixed by the plan and read-only audits of already stable code, goes in the SAME wave; target 2-3 waves; (c) `Agent min` in tasks.md is REAL wall time (measured: one-file task 3-10 min, coupled task or one that runs the suite 15-25 min), not ideal agent minutes; (d) subagent tasks run only their own targeted tests, the full suite runs once per wave by the main agent; (e) after audits, fixes go back to the original owner of each file (SendMessage), not to a new agent; (f) a fix batch fixes only CONFIRMED medium+ findings, the rest become documented open exceptions. `check_spec.py` reports a gap when two rows of the tasks table name the same Target file (gap G6) | feedback-wave-and-file-ownership (memory), SKILL.md Step 4 |
| FR-007 | Close of spec 005 is recorded once FR-005 lands (or by the interim path chosen at approval), without forging the user's answer | investigation above |

## Acceptance cases

| Case | Real data (id) | Expected | Edge? |
|---|---|---|---|
| AC-001 | window A busy (subagent hand-backs), window B approves spec `f177ac1d` tasks in Integraciones | `aidd rules approve` finds B's answer via the caller marker | no |
| AC-002 | marker older than 120 s, newest prompt starts with `<task-notification` | `_current_session` skips the synthetic prompt and uses the newest real one | yes |
| AC-003 | spec `005-aidd-token-planning` (approved hash cca39e73eb06, no plan/tasks `spec_edit`) | `aidd status` shows it open; `aidd rules close` accepts the recorded "Yes, close" | yes |
| AC-004 | 3 agent dispatches under load (spec 005 had 6 unrecorded) | all dispatches appear as `subagent` events; a timeout produces `hook_error` | yes |
| AC-005 | spec edited 5 times before build | no subagent is demanded between edits; one pre-build audit before tasks approval | no |
| AC-006 | clicked Abandon of spec `005-aidd-token-planning`, then typed "No, keep it"; transcript answer whose tool_use_id no PostToolUse hook saw | Abandon is cancelled; an incomplete or inconsistent transcript pair is rejected. A complete, harness-shaped pair whose tool_use_id no hook saw is still accepted on purpose (it lets a lost hook row be recovered); the residual gap is a forged but fully consistent pair, closed only by R9 transcript protection | yes |
| AC-008 | tasks.md with T-01 and T-10 both targeting `skill/scripts/aidd_evidence.py` (the real spec 006 first draft); and a tasks.md whose files are all distinct | `check_spec.py` reports gap G6 naming both rows for the first, no gap for the second; SKILL.md Step 4 states the five planning rules | yes |
| AC-007 | spec `005-aidd-token-planning`, user typed `Yes, close [spec:005-aidd-token-planning]` | `aidd rules close 005-aidd-token-planning` records `spec_closed(completed)` | no |

## Optional Align questions

| Question | Answer | Source |
|---|---|---|
| Which states must each screen/flow handle (empty, loading, error, offline)? | Not applicable | |
| Who may see or do this (permissions/roles)? | Only the user's typed or clicked answers authorize approve/close/abandon | repo — skill/SKILL.md:115 |
| Entry route: how does the user reach this from the app's start? | Not applicable | |
| Target devices (phone, tablet, desktop, orientation)? | Windows 11, Claude Code CLI | |
| Contract owner and status (who defines the backend contract, is it final or still moving)? | Not applicable | |
