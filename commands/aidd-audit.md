---
description: AIDD Step 1/1.5 — mechanical mockup audit + Flowmap (interactive flow + pseudocode)
---

Invoke the `aidd` skill and run **Step 1 (Mockup Audit)** and **Step 1.5 (Flowmap)** for: $ARGUMENTS

- Produce the mechanical, element-by-element mockup audit (no prose) using `templates/mockup-audit.md`.
- Write the flow as AIDD-TOON in `specs/[###-feature]/visual-flow.toon` (`templates/visual-flow.toon`): one `flow: US-nnn` block per use case, actors × processes, every screen/control step citing its code.
- Run `aidd flow specs/[###-feature]/visual-flow.toon --spec-dir specs/[###-feature] --open`, fix any validation errors, and show the user the rendered HTML so they can correct the flow by node reference.
- Stop and report back once both artifacts exist — do not continue into align/plan automatically.
