---
description: AIDD Step 5 — implement one gated PR at a time (renamed from "implement")
---

Invoke the `aidd` skill and run **Step 5 (Build)** for: $ARGUMENTS

- Assign each lane owner all its pending tasks in the wave, with exclusive files and their stated scope and Definition of Done.
- Thread `aidd:CODE` markers into the code (e.g. `// aidd:CTL-057`, `# aidd:SCREEN-08`, `<!-- aidd:COMP-003 -->`) so a later grep links the mockup row, the plan, the task, and the implementation.
- Builders run static self-checks only. Once all builders in the wave finish, the orchestrator runs the wave's complete verification as a coordinated round, then dispatches the independent audit over that wave's evidence. Include this rule in every agent's dispatch prompt; no agent repeats a shared run per task.
