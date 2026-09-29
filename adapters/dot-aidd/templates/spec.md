# Spec — [feature name]

Produced during Step 2 (Align), from Step 1's mockup-audit.md. Nothing here is guessed —
a blank field is an open alignment question, not a placeholder to fill with a reasonable-sounding
default.

## Minimum Requirements Checklist (fill before Step 3 starts)

| Question | Answer | If unanswered |
|---|---|---|
| Which module/area of the system? | | → Step 2 align question |
| New development or modification of something existing? | | → Step 2 align question |
| Does it involve an external service, API, or integration? | | → Step 2 align question |
| Who is requesting it? (role/profile, not necessarily the name) | | → Step 2 align question |
| Dependencies on other modules or active developments? | | → Step 2 align question |
| Business objective (1 sentence — what it achieves and why) | | → Step 2 align question |
| Expected visual fidelity level (if there's a mockup) | exact \| functional behavior only | → Step 2 align question |

**Step 3 does not start while any row above is blank.** This is the same discipline as
`tasks.md`'s "leave it blank, don't invent" rule, applied one stage earlier — a plan built on
a guessed requirement produces exactly the kind of rework this whole skill exists to avoid.

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
