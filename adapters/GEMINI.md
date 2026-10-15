# AIDD

This project uses AIDD (AI-Driven Development) as its default pipeline for any change: UI or
backend-only, a new feature or a one-line fix.

@.aidd/CORE.md

The line above imports the short core (host detection, how to check the hard rules without hooks,
the pipeline, what "done" means). Read it before planning or editing anything. Do NOT read
`.aidd/AIDD.md` whole: it is ~120 KB and gets truncated; `CORE.md` section 6 shows how to read
only the section you need.

Gate missing or unsure? `aidd doctor --host gemini`; to install it: `aidd install --host gemini`.

Before creating anything new: `python .aidd/scripts/find_spec.py <keywords>` and state
`AIDD intake: NEW SPEC | AMENDMENT | AMENDMENT — Fast Lane — <reason>`.
