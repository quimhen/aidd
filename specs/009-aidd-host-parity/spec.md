# Spec — AIDD host parity: install, doctor and write gates for Gemini CLI and OpenCode

Produced during Step 2 (Align). Rows confirmed by the owner's recorded answer "Confirmo filas propuestas".

Risk: high
<!-- high: the change adds gates that block code writes and touches the approval flow (security of the rules). Auditors run on the highest tier. -->

## Minimum Requirements Checklist (fill before Step 3 starts)

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | AIDD cross-host layer: `adapters/`, `aidd/cli.py`, new install/doctor scripts and per-host write gates for Gemini CLI and OpenCode | user — "Confirmo filas propuestas" | → Step 2 align question |
| New development or modification of something existing? | New development: a new spec (`009`), built on the existing `adapters/` tiers and the `aidd rules` CLI; the short core `CORE.md` is already delivered | user — "Confirmo filas propuestas" | → Step 2 align question |
| Does it involve an external service, API, or integration? | Yes, two host integrations: Gemini CLI `BeforeTool` hooks (`settings.json`, exit 2 blocks) and OpenCode `tool.execute.before` (a thrown error blocks). Both from public docs, not yet run here | repo — adapters/README.md:1 | → Step 2 align question |
| Who is requesting it? (role/profile, not necessarily the name) | The project owner (Jefe de Sistemas) who worked a week in b1SycLink with Gemini and OpenCode | user — "Confirmo filas propuestas" | → Step 2 align question |
| Dependencies on other modules or active developments? | Specs 002 (hard rules R1-R14), 006 (session attribution), 008 (review/approval); `aidd rules` CLI; evidence log format | repo — specs/002-aidd-hard-rules/spec.md:1 | → Step 2 align question |
| Business objective (1 sentence — what it achieves and why) | An agent on Gemini or OpenCode must be unable to write code without an approved spec and must not call a task done without executed proof, as Claude Code already enforces, so the Payroll outcome (no task status, no Verify, screens that differ from the mockup) does not repeat | user — "Confirmo filas propuestas" | → Step 2 align question |
| Expected visual fidelity level (if there's a mockup): exact \| functional behavior only | Not applicable: no screens or mockup in this change | user — "Confirmo filas propuestas" | → Step 2 align question |

## Executive summary

- **Objective:** Make AIDD enforce its rules on Gemini CLI and OpenCode (install, verify, block) instead of relying on the model reading instructions.
- **Scope:** `aidd install --host gemini|opencode`, `aidd doctor`, a Gemini `BeforeTool`/`AfterTool` hook set, an OpenCode plugin gate, a host adapter that spawns the existing `rule_gate.py`; two small fixes found while doing it (quote word-count wording, dated status counters). Out: Cursor/Windsurf/Cline/Copilot/Codex gates, Claude Code hook behaviour, methodology changes, gating shell edits of code files (same documented limit as Claude).
- **Cost:** 14 tasks, 3 waves, about 42 min and 845k tokens.
- **Risks:** hooks from public docs behave differently on a real install (mitigated by `aidd doctor` and a real smoke run per host); a gate that blocks the wrong spec (reused per-spec gate target and `aidd rules activate`); approval on these hosts has no AskUserQuestion transcript, so it goes through the review page (AC-006).
- **Open decisions:** none.

## Pipeline route

| Step | Status | Reason | Confirmation |
|---|---|---|---|
| -1 | run | `find_spec.py` ran: no spec covers host parity, nearest is 002 | |
| 0 | waived | no visual surface (CLI, hooks, installer) | user — "Confirmo filas propuestas" |
| 1 | waived | no visual surface (CLI, hooks, installer) | user — "Confirmo filas propuestas" |
| 1.5 | waived | no visual surface (CLI, hooks, installer) | user — "Confirmo filas propuestas" |
| 2 | run | | |
| 3 | run | | |
| 4 | run | | |

## Visual debt

None: no `SCREEN-nn` code appears in this spec.

## Scope
- **Included:** `aidd install --host gemini|opencode` (per-file, never deletes, writes `.aidd/` incl. `CORE.md` and `hooks/`, pointers, hook or plugin registration, idempotent); `aidd doctor` (reads the install and reports pass/fail per check); a Gemini hook and an OpenCode plugin that block code writes without a valid R6 approval for the gate target and record `code_edit` / `spec_edit` evidence; protection of the host registration files; the adapter satisfies the legacy "AIDD invoked" session check itself; docs coherence for quote word counts; dated hook-error and override counters in `aidd status`; unit tests plus one smoke run per host when its binary exists.
- **Excluded:** Cursor, Windsurf, Cline, Copilot and Codex gates; changes to Claude Code hooks beyond the protected-set addition; changing R1-R14 meaning; gating shell commands that edit code files; the Payroll code itself; publishing to package indexes.

## Functional requirements (cite codes, don't redescribe the UI)

| FR-nnn | Requirement | Cites (SCREEN-XX-Fnn / CTL-nnn / API-nnn) |
|---|---|---|
| FR-901 | `aidd install --host gemini` installs `.aidd/` (including `CORE.md` and `hooks/`), a `GEMINI.md` that imports `@.aidd/CORE.md`, and the hook entries in the project `.gemini/settings.json`; re-running changes nothing, never deletes anything under `.aidd/` (memory, evidence, gate pointer) and never removes unrelated entries | — |
| FR-902 | `aidd install --host opencode` installs `.aidd/`, `.opencode/skills/aidd/SKILL.md` and `.opencode/plugins/aidd.js`, and adds the plugin to the `plugin` array of `.opencode/opencode.json` without duplicating it | — |
| FR-903 | Both installs compare each file and report `written`, `unchanged` or `skipped` (modified, kept unless `--force`); they print what they did | — |
| FR-904 | The Gemini hook blocks (exit 2 with the fix text on stderr) a write-type tool call on a code file while the gate target spec has no valid approval; the code gate does not apply under `specs/`, docs and `.aidd/memory/`, while the spec-artifact rules (R1-R12) still apply to `specs/` writes, as on Claude | — |
| FR-905 | The OpenCode plugin does the same by throwing from `tool.execute.before` for edit/write/patch-type tools; shell commands are checked only for protected paths (R9), as on Claude, and shell edits of code files stay a documented, ungated limit | — |
| FR-906 | Both gates append `code_edit` and `spec_edit` events to the project evidence log, so `aidd rules check`, `aidd status` and the close gate see real activity on these hosts; owner approval on these hosts goes through `aidd review --wait` then `aidd rules approve`, documented in `CORE.md` | — |
| FR-907 | Both gates protect `.aidd/` (R9) and read approval only from recorded owner consent, never from anything the agent wrote | — |
| FR-908 | `AIDD_RULES=warn|off` is honoured only from the owner's environment, is recorded as `rules_override` and appears in `aidd status` and in `aidd doctor` | — |
| FR-909 | `aidd doctor [--host H]` checks: `.aidd/` complete and equal to the shipped version, `CORE.md` under 12 KB, pointer files present and importing the core, hook or plugin registered and unaltered, a dry-run of the gate that must return "blocked" for a code write on a fixture spec with no approval; exits 1 with the exact fix per failed check | — |
| FR-910 | A guard test fails when `CORE.md` exceeds 12 KB or when any adapter pointer says to read `AIDD.md` in full | — |
| FR-911 | The files that carry the gate on each host (`.gemini/settings.json`, `.opencode/opencode.json`, `.opencode/plugins/aidd.js`) are protected from agent writes like `.aidd/` (R9); `aidd doctor` reports a missing or altered registration | — |
| FR-912 | The host adapter creates the session "AIDD invoked" marker itself on the first event of an AIDD project (`.aidd/AIDD.md` exists), so the legacy `require_aidd` check does not block with a Claude-only instruction; outside an AIDD project the adapter exits 0 without calling the gate | — |
| FR-913 | The quote rules read the same everywhere: the spec template, `AIDD.md` and `SKILL.md` state that a typed quote needs 5+ words and must postdate the first `spec.md` draft, and an answer to a question needs 2+ words | — |
| FR-914 | `aidd status` shows the date of the last hook error and counts `rules_override` events only since a stated date, so an old record does not read as a current alarm | — |

## Acceptance cases

| Case | Real data (id) | Expected | Edge? |
|---|---|---|---|
| AC-001 | project `D:\Fuentes\b1SycLink`, spec `P10-Payrol-Outputs` (Impl 33%, `Verify: none`, no approval) | with the Gemini hook installed, a write to `Payroll/web/src/App.tsx` is blocked with the R6 message | no |
| AC-002 | same project, after the owner approves `P10-Payrol-Outputs` | the same write is allowed and a `code_edit` event is appended, with no Claude-only "invoke the skill" message | no |
| AC-003 | b1SycLink has 14+ open specs (memory: R6 blocked on ANY open spec) | the gate checks only the gate target; `aidd rules activate <id>` switches it; other specs do not block | yes |
| AC-004 | a fixture project with no `.aidd/` | `aidd doctor` exits 1 and says to run `aidd install --host <h>`; the adapter exits 0 without gating | yes |
| AC-005 | `.opencode/opencode.json` of b1SycLink already lists `graphify.js` and `aidd.js`; its `.aidd/memory/` has entries | install adds nothing twice, keeps `graphify.js` and deletes nothing in `.aidd/memory/` | yes |
| AC-006 | b1SycLink on a Gemini host, tasks of `P10-Payrol-Outputs` reviewed with `aidd review --wait` and approved by the owner | `aidd rules approve` records the approval and the next code write is allowed | no |

## Verification

Scope: auto

| # | Command | Expected | Covers |
|---|---|---|---|
| V-1 | python -m pytest tests/test_host_install.py -q | exit 0 | FR-901, FR-902, FR-903 |
| V-2 | python -m pytest tests/test_host_gates.py -q | exit 0 | FR-904, FR-905, FR-906, FR-907, FR-908, FR-911, FR-912 |
| V-3 | python -m pytest tests/test_host_doctor.py -q | exit 0 | FR-909, FR-910 |
| V-4 | python -m pytest tests/test_aidd_status.py tests/test_dot_aidd_mirror.py -q | exit 0 | FR-913, FR-914 |
| V-5 | python tests/run_parallel.py | exit 0 | FR-901 |

## Optimization brief

Automation / parallelism: the adapter spawns the existing `rule_gate.py` (no second rule engine), `aidd doctor` is a script | install, the two host gates, doctor and the tests are independent lanes in one wave | the full suite runs once, at the end, in the background

| Option | Cost (tokens / min) | Risk | Recommended? |
|---|---|---|---|
| A. Thin host adapter that spawns `rule_gate.py` with the normalised event | about 845k / 42 | medium: one extra process per tool call | yes |
| B. Reimplement the checks in JS for OpenCode and Python for Gemini | about 1100k / 90 | high: two copies drift | no |

Owner pick: A (Recommended), consistent with the owner's recorded answers on scope and on blocking.

## Optional Align questions

| Question | Answer | Source |
|---|---|---|
| Which states must each screen/flow handle (empty, loading, error, offline)? | Not applicable: no screens | user — "Confirmo filas propuestas" |
| Who may see or do this (permissions/roles)? | The owner installs; agents only trigger the gate | user — "Confirmo filas propuestas" |
| Entry route: how does the user reach this from the app's start? | `aidd install --host <h>` and `aidd doctor` | user — "Confirmo filas propuestas" |
| Target devices (phone, tablet, desktop, orientation)? | Windows 11 first (the owner's machine), Linux/macOS best effort | user — "Confirmo filas propuestas" |
| Contract owner and status (who defines the backend contract, is it final or still moving)? | The Gemini hook JSON contract and OpenCode plugin API come from vendors and may move: pin versions in `aidd doctor` | user — "Confirmo filas propuestas" |
