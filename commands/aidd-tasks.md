---
description: AIDD Step 4 — break the plan into small-PR tasks
---

Invoke the `aidd` skill and run **Step 4 (Tasks)** for: $ARGUMENTS

- Copy `templates/tasks.md`.
- Each task = one `SCREEN-XX`, `COMP-nnn`, or `SCREEN-XX-Fnn`, one target file, one PR. Never batch multiple screens into a single task.
- Estimate each task in agent minutes AND tokens from the calibration baselines (roughly 1-3 min and 50-75k tokens per one-file task); human hours are derived = min x 3 / 60.
- Declare `Agent role:` (builder|sql|tests|docs|auditor|mapper) and `Model tier:` (medium|high) per task.
- Use the Waves table with Roles and Tokens (k) columns plus `Total tokens (k)`; organize waves with specialized agents (disjoint files per wave).
- Present the approval as one summary of objectives with cost plus ONE confirmation (`[tasks:<hash8>]`).
- Apply the classify/estimate/decompose/assign rubric and state explicit in/out-of-scope boundaries per task — agents must stop and ask on ambiguity, never guess.
