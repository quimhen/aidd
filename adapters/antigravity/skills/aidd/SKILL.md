---
name: aidd
description: AIDD, the default analysis-and-planning pipeline for ANY change in this codebase. Applies to every requirement, feature, bugfix or change request before writing or editing source, UI or not (backend, database, API, infra, refactor). Triggers on "create/modify/fix/develop", "requerimiento, modificar, corregir, nueva pantalla, spec", "mockup".
---

# AIDD - AI-Driven Development

Thin pointer, not the methodology. Read `.aidd/CORE.md` in full (it is short). Never load `.aidd/AIDD.md` whole (120 KB); CORE.md section 6 shows how to read one section.

## Before anything else: search, do not duplicate

```
python .aidd/scripts/find_spec.py <keywords, or a SCREEN-XX/CTL-nnn/COMP-nnn/API-nnn code>
```

- Exit 0: amendment to the top-ranked spec under `specs/`. Exit 1: safe to create a new `specs/[###-feature]/`.
- State: `AIDD intake: NEW SPEC | AMENDMENT | AMENDMENT — Fast Lane — <reason>`.

## Pipeline

Step -1 search -> 0/1/1.5 visual (only with a mockup) -> 2 Align -> 3 Plan -> 4 Tasks -> 5 Build -> 6 Converge -> 7 Doc, or the Fast Lane for a small contained change.

## Checks and approval

- If no hook answered, run by hand: `aidd rules check specs/<id>` before the first code edit, `aidd status` before ending.
- The owner approves the tasks, never the agent.
- A task is done only when executed (and compared with its mockup for a screen): CORE.md section 4.
- Verify the install with `aidd doctor --host antigravity`.

This skill must NOT be a symlink to the repo's skill folder (it would load a 70 KB file).
