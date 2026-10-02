# Spec — [feature name]

Produced during Step 2 (Align), from Step 1's mockup-audit.md. Nothing here is guessed —
a blank field is an open alignment question, not a placeholder to fill with a reasonable-sounding
default.

## Minimum Requirements Checklist (fill before Step 3 starts)

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | | | → Step 2 align question |
| New development or modification of something existing? | | | → Step 2 align question |
| Does it involve an external service, API, or integration? | | | → Step 2 align question |
| Who is requesting it? (role/profile, not necessarily the name) | | | → Step 2 align question |
| Dependencies on other modules or active developments? | | | → Step 2 align question |
| Business objective (1 sentence — what it achieves and why) | | | → Step 2 align question |
| Expected visual fidelity level (if there's a mockup): exact \| functional behavior only | | | → Step 2 align question |

**Source (rule R3) — every answered row needs exactly one of:** `user — "<the user's own words, 3+ words>"` ·
`repo — <path[:line]>` · `[Proposed — unconfirmed]`. An answer YOU chose yourself is always
`[Proposed — unconfirmed]`; draft with it if you must, but planning (Step 3) is blocked until the user
confirms each one and the Source becomes `user — "..."`. Quotes are checked against the recorded prompts.

**Step 3 does not start while any row above is blank.** This is the same discipline as
`tasks.md`'s "leave it blank, don't invent" rule, applied one stage earlier — a plan built on
a guessed requirement produces exactly the kind of rework this whole skill exists to avoid.

## Pipeline route

Declare, for every step, whether it runs. Skipping a step needs the user: `waived` requires a Reason and a
Confirmation of the form `user — "<their words, 3+ words>"` (verified against recorded prompts). Steps 0/1/1.5
may only be waived for a change with no visual surface. Never waive a step on your own initiative.

| Step | Status | Reason | Confirmation |
|---|---|---|---|
| -1 | run | | |
| 0 | run | | |
| 1 | run | | |
| 1.5 | run | | |
| 2 | run | | |
| 3 | run | | |
| 4 | run | | |

<!-- Example of a waived row (only after the user said so):
| 1.5 | waived | backend-only change, no screens | user — "no hace falta el flowmap aqui" |
-->

## Visual debt

Only needed when Step 0/1/1.5 is `waived` and `SCREEN-nn` codes appear anywhere without a mockup-audit row.
While a row is `open`, writes under the blocked spec and its code edits are BLOCKED. `resolved` needs a Mockup source.

<!-- Example (uncomment and fill only if it applies):
| Codes | Blocks spec | Status | Mockup source |
|---|---|---|---|
| SCREEN-04, SCREEN-05 | 007-checkout | open | |
-->

## Scope
- **Included:** [explicit list]
- **Excluded:** [explicit list — as important as what's included; never leave this section empty]

## Functional requirements (cite codes, don't redescribe the UI)

| FR-nnn | Requirement | Cites (SCREEN-XX-Fnn / CTL-nnn / API-nnn) |
|---|---|---|
| FR-001 | | |

Every functional requirement traces to at least one code from `mockup-audit.md` (or `contracts.md`
for a full-stack requirement) — a requirement with no code behind it either belongs in a different
spec or the audit is incomplete.

## Acceptance cases

Real data, written BEFORE building: the cases the user would otherwise discover during their own test.
At least one row, and at least one `edge` (empty, extreme, boundary, legacy or odd data: a 9999 date, a
zero, a user with no rows). `Real data (id)` is a real record id/key from the system, not an invented value.

| Case | Real data (id) | Expected | Edge? |
|---|---|---|---|
| AC-001 | | | |

## Optional Align questions

Not part of the Minimum Requirements Checklist above (those 7 rows stay as they are, and old specs without
this section stay valid). Ask the ones that apply in Step 2 and record the answer with its Source
(`user — "<their words, 3+ words>"` or `repo — <path[:line]>`). Blank = not asked yet, never guessed.

| Question | Answer | Source |
|---|---|---|
| Which states must each screen/flow handle (empty, loading, error, offline)? | | |
| Who may see or do this (permissions/roles)? | | |
| Entry route: how does the user reach this from the app's start? | | |
| Target devices (phone, tablet, desktop, orientation)? | | |
| Contract owner and status (who defines the backend contract, is it final or still moving)? | | |
