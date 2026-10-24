---
description: AIDD Step 6 — independent, specialized audit (check_spec.py once before the closing audit)
---

Invoke the `aidd` skill and run **Step 6 (Converge)** for: $ARGUMENTS

- Run `python scripts/check_spec.py specs/[###-feature]/` ONCE before the closing audit and after the last spec/plan/tasks edit, not before every pass — let the stdlib gap-checker catch mechanical drift once.
- Closing verification follows rule E9: one `aidd verify` per spec at close and `tests/run_parallel.py --changed` for tests; never the same verification twice on the same code state.
- Start the auditor from the analysis parameters printed by `aidd size --spec <spec-id>` (XS/S/M/L): a small change gets a small audit.
- Dispatch the specialized audit agents per domain (visual fidelity, performance/best-practices, etc.), each with its own checklist and context — never one generic pass.
- The visual-fidelity audit must be a real check (build/run, screenshot each new section, compare directly against the mockup) — never a text-only comparison of code vs. mockup.
- Scope each auditor: start from `find_spec.py --code` for every changed code plus the `check_spec.py` report and the diff since the last audit; read full files only for what those point to.
- Graph-first closing audit: start from `aidd graphs changed --spec <spec-id>` (files whose content hash differs from the `<spec-id>@open` baseline, plus `affected`), then run `find_spec.py --code <CODE>` for the changed codes; both query the `builtin:code` graph.
- To prove a step runs once, use `aidd graphs repeats` and `aidd graphs trace` on `builtin:code`, not a reading of the source.
- Any before/after claim the auditor accepts must cite `aidd graphs diff <A> <B>` and both snapshot hashes; a hand-edited file is not evidence.
- Report any `graph-first: N misses / M searches` line seen in `aidd status`.
- Auditors run on a medium or high model tier chosen by the spec's `Risk:` header (high = writes to SAP/DB, security, money -> highest tier; otherwise medium), never the lowest (haiku): dispatch with `model: sonnet` or `opus`.
- An auditor whose recorded model contains 'haiku' does not satisfy R5/R7/R8 (R14).
- Show the closing question as ONE confirmation with tag `[spec:<id>]` for 'Yes, close'.
- Report findings; do not mark the feature converged until every finding is fixed or explicitly accepted by the user.
