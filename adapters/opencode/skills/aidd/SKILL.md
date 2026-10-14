---
name: aidd
description: AIDD — the default analysis-and-planning pipeline for ANY change in this codebase, of any size, UI or not (backend-only, database/schema, API contract, infra, bugfix, refactor). Use for EVERY requirement, feature, bugfix, or change request before writing or editing source — not only when a mockup is mentioned. Triggers on "create/modify/update/improve/fix/develop", "requerimiento/modificar/actualizar/mejorar/corregir", "nueva pantalla", "mockup", "spec".
---

# AIDD — AI-Driven Development

Thin pointer. The short core is `.aidd/CORE.md` (~6 KB): **read it first (it is short)**. The full
methodology `.aidd/AIDD.md` is ~120 KB and OpenCode truncates a read at ~50 KB, so never load it
whole — `CORE.md` section 6 shows how to read one section at a time.

## Before anything else: search, don't duplicate

```
python .aidd/scripts/find_spec.py <keywords describing the request, or a SCREEN-XX/CTL-nnn/COMP-nnn/API-nnn code>
```

- Exit code 0 → **amendment** to the top-ranked existing spec under `specs/` — reopen it, never a new folder.
- Exit code 1 → safe to create a new `specs/[###-feature]/`.

State the classification: `AIDD intake: NEW SPEC | AMENDMENT | AMENDMENT — Fast Lane — <reason>`.

## OpenCode specifics

- Ask the owner with the `question` tool; dispatch independent work with the subagent tool.
- The `aidd.js` plugin gate blocks gated writes once installed (`aidd install --host opencode`;
  verify with `aidd doctor --host opencode`). If it is missing, run the checks yourself
  (`CORE.md` section 2): `aidd rules check specs/<id>` before the first code edit,
  `check_spec.py` after editing spec/plan/tasks, `aidd status` before ending.
- A task is done only when executed (and compared with the mockup for a screen): `CORE.md` section 4.

Pipeline: Step -1 search → 0/1/1.5 visual (only with a mockup) → 2 Align → 3 Plan → 4 Tasks →
5 Build → 6 Converge → 7 Doc, or the Fast Lane for a small contained change.
