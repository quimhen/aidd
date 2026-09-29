---
name: aidd
description: AIDD — the default analysis-and-planning pipeline for ANY change in this codebase, of any size, UI or not (backend-only, database/schema, API contract, infra, bugfix, refactor). Use for EVERY requirement, feature, bugfix, or change request before writing or editing source — not only when a mockup is mentioned. Triggers on "create/modify/update/improve/fix/develop", "requerimiento/modificar/actualizar/mejorar/corregir", "nueva pantalla", "mockup", "spec".
---

# AIDD — AI-Driven Development

Full methodology lives in `.aidd/AIDD.md` (shared across every agent tool in this project, not
duplicated per tool) — **read it in full before planning or implementing anything**. This file
is a thin pointer, not a second copy, so the methodology never drifts between tools.

## Before anything else: search, don't duplicate

```
python .aidd/scripts/find_spec.py <keywords describing the request, or a SCREEN-XX/CTL-nnn/COMP-nnn/API-nnn code>
```

- Exit code 0 → **amendment** to the top-ranked existing spec under `specs/` — reopen it, never a new folder.
- Exit code 1 → safe to create a new `specs/[###-feature]/`.
- `find_spec.py --tree <spec-id>` prints that spec's use-case → screen → component → control → API graph.

State the classification before proceeding: `AIDD intake: NEW SPEC | AMENDMENT | AMENDMENT — Fast Lane — <reason>`.

## Then follow `.aidd/AIDD.md`

Search (above) → Step 0 (visual source, only if the change has a UI) → Step 1/1.5 (mockup audit
+ flow) → Step 2 Align → Step 3 Plan → Step 4 Tasks → Step 5 Build → Step 6 Converge → Step 7
Documentation — or the Fast Lane for a small, contained change. Run
`python .aidd/scripts/check_spec.py specs/[###-feature]/` before a manual audit pass (Step 6).
