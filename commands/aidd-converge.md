---
description: AIDD Step 6 — independent, specialized audit (run check_spec.py first)
---

Invoke the `aidd` skill and run **Step 6 (Converge)** for: $ARGUMENTS

- Run `python scripts/check_spec.py specs/[###-feature]/` before any manual audit pass — let the stdlib gap-checker catch mechanical drift first.
- Dispatch the specialized audit agents per domain (visual fidelity, performance/best-practices, etc.), each with its own checklist and context — never one generic pass.
- The visual-fidelity audit must be a real check (build/run, screenshot each new section, compare directly against the mockup) — never a text-only comparison of code vs. mockup.
- Scope each auditor: start from `find_spec.py --code` for every changed code plus the `check_spec.py` report and the diff since the last audit; read full files only for what those point to.
- Report findings; do not mark the feature converged until every finding is fixed or explicitly accepted by the user.
