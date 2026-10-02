# 003 — AIDD Interaction Evidence (close the "it says done, the user finds the bug" loop)

Extends 002 (hard rules). Motivation, measured on the user's own history (3,025 prompts / 239 sessions; two
projects analysed in depth: NominaOne 1,023 prompts, BusProApp 951): the long sessions are not caused by missing
code but by unwritten ambiguity and by work declared done without being run. Counts are regex/reading estimates.

- **Done without running it.** The user is the only one who runs SAP UI/DI or the tablet and finds the error
  (NominaOne ~30-40 rounds; BusProApp "implementado" while the user sees N/D, a legacy screen or a mock).
- **Same SAP error families recur** (UID > 10 chars, `--` inside XML comments, `Invalid item`, invalid `U_` property,
  queries inside a SAP transaction): 5 families, 3-6 sessions each; the user had to say "guardalo como regla".
- **Symptom patched, root cause not analysed** (a lock cost ~45 messages; finiquitos in 8 sessions).
- **Edge cases arrive during the user's test** (extrarol, comision, date 9999) instead of as acceptance cases.
- **Visual wired to nothing / nothing leads to the screen** (N/D cards, "como accedo?", widgets without action).
- **Legacy view wrapped instead of a new faithful view** ("reutiliza/envuelve X" in tasks; spec 019 "capa de presentacion").
- **Shared standard (header, back, logo) re-done per screen** with no list of consumers; tablet vs phone forgotten.
- **Backend contract changes mid-build** and the tasks built on the old one are not marked stale.
- **Secrets pasted in prompts** (28 prompts with a DB password) end up in the evidence log verbatim.

This file is the single source of truth for every implementing agent. Stay inside your task's files.

## Minimum Requirements Checklist

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | AIDD skill: `skill/scripts/` (rules engine, check_spec, evidence), `skill/hooks/` (rule_gate, prompt_trigger), `skill/templates/`, `skill/SKILL.md`, `skill/AIDD.md`, adapters mirror | user — "Confirmar tal cual" | → Step 2 align question |
| New development or modification of something existing? | Modification of 002's engine plus new rules R10 (execution evidence), R11 (root cause on repeat), R12 (view-vs-logic tag), and new/extended templates | user — "Confirmar tal cual" | → Step 2 align question |
| Does it involve an external service, API, or integration? | No. Stdlib only. A one-off read-only import of the saved claude-mem backup into AIDD Memory of two other local projects | user — "Confirmar tal cual" | → Step 2 align question |
| Who is requesting it? (role/profile, not necessarily the name) | Head of Systems (the skill's owner and only user), from his own interaction history | user — "Confirmar tal cual" | → Step 2 align question |
| Dependencies on other modules or active developments? | 002 hard rules (rule_gate, aidd_rules, evidence log); 001 memory (import). No other active work | user — "Confirmar tal cual" | → Step 2 align question |
| Business objective (1 sentence — what it achieves and why) | Cut the correction rounds by making "done" require run evidence and by writing down the data/route/state/acceptance ambiguity before building | user — "Confirmar tal cual" | → Step 2 align question |
| Expected visual fidelity level (if there's a mockup): exact \| functional behavior only | No mockup: this change has no visual surface (scripts, hooks, markdown templates) | user — "Confirmar tal cual" | → Step 2 align question |

**Source (rule R3) — every answered row needs exactly one of:** `user — "<the user's own words, 3+ words>"` ·
`repo — <path[:line]>` · `user — "Confirmar tal cual"`. Answers above were chosen by the agent, so they are Proposed until
the user confirms them.

## Pipeline route

| Step | Status | Reason | Confirmation |
|---|---|---|---|
| -1 | run | | |
| 0 | waived | scripts, hooks and markdown templates only: no visual surface | user — "Sin superficie visual, omitir" |
| 1 | waived | no mockup to audit | user — "Sin superficie visual, omitir" |
| 1.5 | waived | no screens or user flow to draw | user — "Sin superficie visual, omitir" |
| 2 | run | | |
| 3 | run | | |
| 4 | run | | |

## Visual debt

No `SCREEN-nn` codes appear in this spec's files; no debt.

## Scope
- **Included:** the 10 changes below (R10, R11, R12, check_spec gaps, template changes, credential hygiene, docs),
  tests, the adapters mirror, installing the result to `~/.claude/skills/aidd`, and the one-off AIDD Memory import.
- **Excluded:** inspecting what a screenshot depicts (the gate only checks that evidence exists and is fresh);
  forcing `adb`/device access (a template field and a documented step, not a hook); any change to R1-R9 behaviour;
  touching claude-mem (already removed); editing the user's other projects other than adding `.aidd/memory/` entries.

## Binding design

### R10 — execution evidence at close (blocks writing `qa-audit.md`)
`qa-audit.md` must contain `## Execution evidence` with `| Code | Kind | Evidence | Verified by |`.
Every `Mapping ledger` row whose Status starts with ✅ and whose Code is `SCREEN-`, `API-` or ends in `-Fnn` needs a
row there. `Kind` ∈ `screenshot | command-output | query-result | log | manual-test | not-verified`.
- `screenshot|command-output|query-result|log`: Evidence is a path (relative to the spec dir, else the project root)
  to an existing file, or an `http(s)://` URL. A `screenshot` must be `.png|.jpg|.jpeg|.webp`.
- `manual-test`: Evidence is `user — "<quote 3+ words>"` or an existing path.
- `not-verified`: Evidence is the path of an existing human test script; the Mapping ledger Status of that code must
  NOT be ✅ (it is ⚠️ PARTIAL until the user runs it). This is how "I cannot run SAP/the tablet" stays honest.
- `Verified by` ∈ `agent | user`.
- Freshness (hook only, needs the evidence log): a file Evidence older than the last recorded `code_edit` is stale.
- Rows listed in `Open exceptions` are exempt. New violations only on Edit; any violation on a whole-file Write.

### R11 — root cause on repeat
`qa-audit.md` has `## Bug reports` with `| # | Code | Symptom | Root cause | Fix | Pattern sweep |`. For a Code that
appears in 2 or more rows, every row after the first needs a non-blank Root cause and a Pattern sweep (what was
searched and where, e.g. `grep -rn "fmt(" forms/` → 4 hits fixed). From the 3rd row of the same Code, Fix must
state `redesign` and a reference (spec id or task).

### R12 — view vs logic tag
In `tasks.md`, a task row that cites `SCREEN-`/`COMP-` and uses a reuse word (`reutiliza`, `remapea`, `envuelve`,
`wrap`, `reuse`, `rewire`) must carry `Kind: VIEW-new | LOGIC | VIEW-legacy: <justification 5+ chars>`.
A bare `VIEW-legacy` without a justification is a violation. Default for a redesign is `VIEW-new + LOGIC`.

### Static gaps in `check_spec.py` (report-only, exit non-zero like the others)
- G1 `mockup-audit.md` control inventory: when the header has the columns `Destination` and `Data source`, every CTL
  with an Action needs both (or `n/a — <reason>`) and a States cell (empty/loading/error). Old specs without the
  columns are not flagged.
- G2 `spec.md` has no `## Acceptance cases` table (`| Case | Real data (id) | Expected | Edge? |`) with ≥ 1 row and ≥ 1 `edge`.
- G3 `traceability.md` (full-stack): every row has Mockup field, Room/store, DTO, API, SP and Filled-by.
- G4 `contracts.md` carries `Contract hash:`; a mismatch with the recomputed hash of the contract table lists the
  stale `API-` tasks. `check_spec.py <dir> --stamp-contract` writes the hash.
- G5 `components-index.md` rows have a `Consumers` cell; a COMP with a screen in `Used in` but no consumer is flagged.

### Credential hygiene
`prompt_trigger.py` detects `password|pwd|clave|contraseña|token|secret|api key` assignments in the user's prompt and
(a) redacts the value (`[redacted]`) before the prompt is stored in the evidence log, (b) injects a warning:
never copy it into files, specs, memory or commands; use an env var or a connection profile outside the chat.

### Templates
`qa-audit.md` (+Execution evidence, +Bug reports, +Device preflight line), `mockup-audit.md` (+Destination, Data source,
States), `plan.md` (+Entry route, Device targets), `tasks.md` (+Kind tag), `spec.md` (+Acceptance cases; +optional
Align rows: states, permissions, entry route, target devices, contract owner/status), new `traceability.md`,
`contracts.md` (+Contract version/hash), `components-index.md` (+Consumers), `STATE.md` (+Test state),
`charter.md` (+SAP pitfalls: checkable XML-comment rule, prose for the rest).
New optional Align rows are NOT added to `REQUIRED_QUESTIONS` (old specs stay valid).

### Docs
`SKILL.md` and `AIDD.md`: rules table rows R10-R12, DoD "evidence executed, not textual", `adb devices` preflight,
root-cause + pattern sweep, hygiene.

### One-off memory import
`aidd mem import-claude-mem <backup db> --project NominaOne` into the NominaOne repo and `--project BusProApp` into
the BusProApp repo (read-only on the db; scrubs secrets; idempotent). `--dry-run` first.

### Decisions confirmed by the user (Step 2)
- Strictness: R10, R11 and R12 all BLOCK (`AIDD_RULES=warn|off` remains the owner's escape hatch) — user — "Bloquear las tres (Recomendado)".
- Memory import: write into both repos after a dry-run — user — "Sí, importar en ambos".

## Functional requirements

| FR-nnn | Requirement | Cites (SCREEN-XX-Fnn / CTL-nnn / API-nnn) |
|---|---|---|
| FR-001 | R10 blocks a `qa-audit.md` whose ✅ SCREEN/API/Fnn rows lack valid, fresh execution evidence | — (no UI) |
| FR-002 | R11 requires root cause + pattern sweep from the 2nd report of the same code and a redesign from the 3rd | — |
| FR-003 | R12 requires the Kind tag on reuse-worded UI tasks | — |
| FR-004 | check_spec reports G1-G5 and can stamp the contract hash | — |
| FR-005 | Templates carry the new columns/sections without invalidating specs 001/002 | — |
| FR-006 | Secrets in prompts are redacted from the evidence log and trigger a warning | — |
| FR-007 | Docs describe the new rules; adapters mirror and installed skill match the repo | — |
| FR-008 | NominaOne and BusProApp memories imported from the backup, scrubbed | — |

## Definition of Done (every task)

Code + stdlib `unittest` tests (`python -m unittest discover -s tests`) + no new dependency + Windows-safe + hooks always
exit 0 on internal error + every block message names the next action + adversarial tests per rule (try to violate it and
show the gate blocks; try the legitimate path and show it passes). Do NOT use any claude-mem tool/plugin. The Bash tool
is unreliable on this machine (Cygwin mount error): use PowerShell.
