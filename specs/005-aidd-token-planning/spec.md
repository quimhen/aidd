# 005 — AIDD token planning (tokens, specialized agents, audit model tier)

Extends 002 (R1 estimates are agent time) and 004 (graph-first). Motivation, measured in spec 004 (2026-10-03): estimates were
~10x the real work (5-25 min planned per Medium task versus 0.6-2.8 min measured by the subagent; about 50-75k tokens per
one-file builder task), no task carried a token budget, waves had no named roles, and two audits ran on the lowest model tier.

- **Human hours inflated:** the planner gives many hours where the user has built the same in far less.
- **No token budget:** nothing tells the user how many tokens a task or a wave will cost.
- **Generic agents:** a wave is a list of tasks; nobody says which specialized agent runs each one.
- **Weak auditors:** the gates only check that "a subagent ran", so an audit by the lowest model tier satisfies R5/R7/R8.

## Minimum Requirements Checklist

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | AIDD skill: `skill/scripts/aidd_rules.py` (R1, new rules), `skill/hooks/mark_agent_dispatch.py`, `skill/templates/tasks.md`, `skill/SKILL.md`, `skill/AIDD.md`, `commands/aidd-tasks.md`, adapters mirror | repo — skill/scripts/aidd_rules.py:1 | → Step 2 align question |
| New development or modification of something existing? | Modification of R1 and of the subagent evidence, plus new rules R13 (agent role and model tier per task) and R14 (audit model floor) and a calibration log | repo — specs/002-aidd-hard-rules/spec.md:81 | → Step 2 align question |
| Does it involve an external service, API, or integration? | No. Stdlib only | repo — skill/scripts/aidd_rules.py:1 | → Step 2 align question |
| Who is requesting it? (role/profile, not necessarily the name) | Head of Systems, owner and only user of the skill | repo — specs/004-aidd-graph-first/spec.md:1 | → Step 2 align question |
| Dependencies on other modules or active developments? | 002 rules engine, 004 graph (`find_spec.py --code`), `check_spec.py`, `aidd status`. No other active work | repo — specs/004-aidd-graph-first/spec.md:1 | → Step 2 align question |
| Business objective (1 sentence — what it achieves and why) | Plan work in realistic agent time and tokens, assign specialized agents per wave and guarantee that audits run on a medium or high model | user — "ya te confirmo la spec" | → Step 2 align question |
| Expected visual fidelity level (if there's a mockup): exact \| functional behavior only | No mockup: scripts, hooks and markdown only | repo — specs/004-aidd-graph-first/spec.md:1 | → Step 2 align question |

## Pipeline route

| Step | Status | Reason | Confirmation |
|---|---|---|---|
| -1 | run | find_spec found 002 (R1) as nearest; this extends it with tokens, roles and a model floor | |
| 0 | waived | no visual surface | user — "ya te confirmo la spec" |
| 1 | waived | no mockup | user — "ya te confirmo la spec" |
| 1.5 | waived | no flows to draw | user — "ya te confirmo la spec" |
| 2 | run | | |
| 3 | run | | |
| 4 | run | | |

## Visual debt

No `SCREEN-nn` codes appear in this spec's files; no debt.

## Scope

In: token and agent-minute estimates per task and wave, a calibration log, agent role and model tier per task, a model floor for
auditors, templates, docs, tests, the adapters mirror.
Out: measuring real token usage automatically from the host (the numbers come from the subagent reports the agent records),
changing R2-R12 semantics, hard-coding model names beyond the lowest-tier floor.

## Functional requirements

| FR-nnn | Requirement | Cites |
|---|---|---|
| FR-001 | Each task block in `tasks.md` has `Tokens (est):` in thousands next to `Agent min:`; the Waves table gains a `Tokens (k)` column that is the SUM of its tasks (agents run in parallel, tokens add up); the file ends with `Total tokens (k): N`. R1 validates the arithmetic like it does for minutes | AC-001, AC-002 |
| FR-002 | A calibration table `.aidd/calibration.toon` per project (seeded from `skill/templates/calibration.toon` with the spec 004 data) gives baseline minutes and tokens per effort class (Low, Medium, High); `aidd calibrate record <spec-dir>` appends ONE aggregate row per effort class keyed by (spec, class) with the measured minutes and tokens, so a second run replaces rather than duplicates | AC-006 |
| FR-003 | `Human ref hours` stays in the table for compatibility but is DERIVED: agent min x `human_factor` from the calibration file (default 3), never estimated by hand; the template and SKILL.md say so | AC-001 |
| FR-004 | Each task declares `Agent role:` from a fixed vocabulary (`builder`, `sql`, `tests`, `docs`, `auditor`, `mapper`) and `Model tier:` (valid values are exactly `medium` and `high`; any other value, including `low`, is invalid and an `auditor` with `medium` is valid); new rule R13 blocks writing `tasks.md` when a task lacks either field or carries an invalid value | AC-003 |
| FR-005 | The Waves table groups tasks by role: a new `Roles` column lists the roles of the wave | AC-001 |
| FR-006 | `mark_agent_dispatch.py` records the `model` of each subagent dispatch (from the Agent tool input; absent = inherited); new rule R14: for R5 (plan/tasks chain) and R7/R8 (closing audits) a subagent whose recorded model is the lowest tier does NOT count: the match is case-insensitive on `haiku` and therefore also covers ids such as `claude-haiku-4-5-20251001`; an inherited or unrecorded model counts | AC-004, AC-005 |
| FR-007 | `spec.md` carries `Risk: low \| medium \| high` in its header; SKILL.md and `commands/aidd-converge.md` say: high risk (writes to SAP/DB, security, money) audits on the highest tier, others on medium. Documentation only: it cannot be checked mechanically, so it has no acceptance case | - |
| FR-008 | `aidd status` and `check_spec.py` show the planned total (`~N min, ~Nk tokens`) per spec | AC-001 |
| FR-009 | Legacy exemption: a `tasks.md` that already has a valid recorded approval and no `Tokens` column (specs 001-004) is not failed by the new token and role rules | AC-007 |
| FR-010 | No manual script runs for the user: when the host records no `answer` event after an `AskUserQuestion`, AIDD guidance tells the agent to ask in plain text and accept the user's typed reply; the typed fallback of `typed_approval` also covers close (`Yes, close [spec:<id>]`) and abandon (`Abandon [spec:<id>]`) with the exact spec tag, so the user never runs `aidd rules ...` or scripts by hand | AC-008 |
| FR-012 | Single approval: the user's confirmation of the spec is the approval of everything planned (plan and tasks). Before asking, the agent shows a short summary that lists the objectives the implementation will achieve (one line per goal, with its token and agent-minute cost); ONE confirmation then accepts spec, plan and tasks, and nothing else is asked. When the host does not record popup answers, the confirmation is the shortest typed reply that AIDD can bind to the content hash; the mechanism is decided in the plan after checking what hooks Claude Code actually offers | AC-010 |
| FR-013 | Popup answers are recovered from the host transcript: a function `sync_ask_answers(transcript_path, session)` reads the session transcript (JSONL written by the host), and for every `AskUserQuestion` tool_use/tool_result pair not yet recorded it appends the same `question` and `answer` events a PostToolUse hook would have written (idempotent by tool_use id, incremental by byte offset). It runs from `rule_gate.py` at every PreToolUse and from `prompt_trigger.py`, so by the time `aidd rules approve` runs the click is recorded. The transcript path is added to the protected paths (R9) so an agent cannot edit it. The typed fallback of FR-010 stays for hosts without a transcript | AC-011 |
| FR-014 | `prompt_trigger.py` also records every entry of `queued_messages` (messages typed while the agent was working, delivered on the next UserPromptSubmit) as a `prompt` event, once each | AC-012 |
| FR-011 | R4 does not count screen codes that appear only inside inline code spans (backticks) of SIBLING specs' files (documentation examples); real codes in the spec's own files, plan, contracts or unquoted sibling text still count | AC-009 |

## Acceptance cases

| Case | Real data (id) | Expected | Edge? |
|---|---|---|---|
| AC-001 | `specs/005-aidd-token-planning/tasks.md` itself, written in the new format (Tokens, Roles and tiers); specs 001-004 keep their approved legacy files untouched | the `Total tokens (k)` line equals the sum of the wave `Tokens (k)` cells and of the task `Tokens (est)` values; every wave has a `Roles` cell equal to the roles of its tasks; `aidd status` and `check_spec.py` both print `~N min, ~Nk tokens` with the same numbers; human hours = min x factor / 60 | no |
| AC-002 | a `tasks.md` whose wave tokens do not equal the sum of its tasks | R1 blocks the write naming the wave | no |
| AC-003 | a task without `Agent role:` or `Model tier:`; an `auditor` task with tier `low` | R13 blocks the write and names the task | no |
| AC-004 | a subagent dispatched with `model: haiku` named "performance auditor" after the last code edit | R7 reports the domain as uncovered; the message says the model tier is too low | no |
| AC-005 | the same dispatch with `model: sonnet`, and one with no model field | R7 counts both | yes |
| AC-006 | close of spec 004 with measured minutes and tokens per task | `aidd calibrate record specs/004-aidd-graph-first` appends one row per effort class to `.aidd/calibration.toon` and a second run does not duplicate | yes |
| AC-007 | `specs/002-aidd-hard-rules/tasks.md` (approved, no Tokens column) | `aidd rules check` raises no R1/R13 failure for the missing columns | yes |
| AC-008 | a user-typed prompt `Yes, close [spec:004-aidd-graph-first]` with no recorded `answer` event | `aidd rules close 004-aidd-graph-first` is accepted; the same text typed for another spec id, or sent by a subagent hand-back, is refused | yes |
| AC-010 | this spec 005 at the approval step | the agent prints a summary of objectives with their cost, asks one confirmation, and after the user's single answer `aidd rules approve` succeeds without a second prompt; the user types at most one short line when the popup answer is not recorded | yes |
| AC-011 | the transcript of this very conversation (session 3026cc79-e835-4e1a-8aaf-cd4e2ae37c32) holds the popup click on `Approve these tasks? [tasks:37ed463c]` | after `sync_ask_answers` the session log has the matching `question` and `answer` events with the chosen label `Approve`; a second run adds nothing; a transcript with no AskUserQuestion adds nothing and never raises | yes |
| AC-012 | a user message sent while the agent works, delivered in `queued_messages` | one `prompt` event per queued message, none duplicated when the hook runs again | yes |
| AC-009 | a sibling spec whose plan mentions an example screen code inside backticks, and another sibling that mentions an unquoted real code | the backticked example is ignored by R4; the unquoted real code is still reported | yes |

## Optional Align questions

| Question | Answer | Source |
|---|---|---|
| Which states must each screen/flow handle (empty, loading, error, offline)? | N/A | |
| Who may see or do this (permissions/roles)? | N/A | |
| Entry route: how does the user reach this from the app's start? | `tasks.md` writing gate, `aidd status`, `aidd calibrate` | |
| Target devices (phone, tablet, desktop, orientation)? | N/A | |
| Contract owner and status (who defines the backend contract, is it final or still moving)? | N/A | |
