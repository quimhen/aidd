---
description: AIDD Step 5 — implement one gated PR at a time (renamed from "implement")
---

Invoke the `aidd` skill and run **Step 5 (Build)** for: $ARGUMENTS

- Implement exactly one task from `tasks.md` at a time, gated by its stated scope and Definition of Done.
- Thread `aidd:CODE` markers into the code (e.g. `// aidd:CTL-057`, `# aidd:SCREEN-08`, `<!-- aidd:COMP-003 -->`) so a later grep links the mockup row, the plan, the task, and the implementation.
- Do not start the next task until this one is reviewable as its own small PR.
