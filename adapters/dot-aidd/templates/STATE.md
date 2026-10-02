# aidd state — [project name]

Read this file FIRST, in full, before anything else — that's the point of it. Keep it small:
pointers (grep targets, file+section), not restated content. Update it at the end of every
step that changes what's true; append/edit, don't let it grow into a second spec.

**Last updated:** [date] by [step/agent — e.g. "Step 5, T-03"]

## Active spec(s)
| Spec folder | Current step | Last revision |
|---|---|---|
| specs/007-checkout/ | Step 5 (implementing) | qa-audit.md Rev 2 |

## Last action
[One or two lines — what was just done, and where. e.g. "T-03 implemented (CTL-078, SCREEN-09) — PR #142, awaiting screenshot diff."]

## Next action
[One line — the next concrete step. e.g. "Run check_spec.py on specs/007-checkout/, then Step 6 converge."]

## Quick pointers (grep targets — don't restate their content here)
| What | Where |
|---|---|
| Naming & File Contract | specs/007-checkout/plan.md — "Naming & File Contract" section |
| Component Index | design-system/components-index.md |
| Open exceptions | specs/007-checkout/qa-audit.md — "Open exceptions" section |

## Rules ledger
Read-only — never hand-edit and never copy its output here (it goes stale). Run `aidd status` for the mechanical
ledger of the hard rules: route, alignment provenance, Mapper/graph evidence, tasks approval, waves/critical path,
code edits and which closing auditors ran.

## Memory pointers
Decisions, rejected options, bug root causes and constraints live in `.aidd/memory/` — not here.
Before touching a code: `aidd mem search <code>`, then `aidd mem show <id>` for the full entry.

## Stale-check
If `check_spec.py` or the actual files contradict something above, fix this file as part of
that session's own update — don't leave a stale pointer for the next reader to trip over.
