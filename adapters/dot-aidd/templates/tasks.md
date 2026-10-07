# Tasks — [feature name]

One row = one small PR. Same rubric as the requirements-analysis workflow this borrows its task
format from: classify → estimate → decompose → assign, then present as a dry-run and wait for
approval before anything gets written.

Tasks reference the single pre-build coherence audit (spec, plan, graph, estimates) that runs before this list is approved; there is no per-edit audit.

**Every task's implementation prompt restates these standards explicitly — a fresh agent doesn't inherit them from context:**
- **Scope: in and out, both stated explicitly.** In scope = exactly the codes and target file(s) this row names, nothing else. Out of scope = everything else, including an unrelated bug or style issue the agent happens to notice — that's a note back, never a bundled fix. Touching a file this row doesn't name is out of scope even if the change is objectively good.
- **If anything needed to proceed is missing or ambiguous, the agent stops and reports what's unclear instead of guessing.** A code that doesn't resolve, a schema that isn't defined, a naming case the contract doesn't cover — none of these get a "reasonable" assumption. Report it; don't implement around it.
- **SOLID** on any code touched (single responsibility, extend don't special-case, substitutable subtypes, no fat interfaces, depend on abstractions across boundaries).
- **One class/component per file** — never bundle several classes into one file. A task whose target file would need a second class is two tasks.
- **Naming & File Contract from `plan.md`** — PascalCase for classes/types, camelCase for functions/variables, the project's own file-naming case. Restate the specific convention here, don't just point at plan.md and assume the agent will look it up.
- **Antifragile / Design for Failure** — assume every operation crossing a boundary (network, DB, disk, external API, hardware) can fail: explicit timeout, retry with backoff, graceful degradation, and a traceable/recoverable record for anything that exhausts retries (dead-letter entry, status field, log with enough context to replay manually). Never fail silently to the user.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Explicitly out of scope |
|---|---|---|---|---|
| T-01 | COMP-001, CTL-001 | | VIEW-new | any other file; any code not listed here |
| T-02 | SCREEN-01, CTL-002 | | VIEW-new \| LOGIC \| VIEW-legacy | any other file; any code not listed here |

`View / logic` says what the task builds: `VIEW-new` = a new presentation faithful to the mockup (data and logic may come from existing code); `LOGIC` = data/state/behaviour only, no presentation; `VIEW-legacy` = the old view is kept as it is, and only with a written justification (5+ characters) in the task's `Kind:` line. The default for a visual redesign is a new view plus the logic behind it. A task that names a SCREEN/COMP code together with a word like reutiliza, remapea, envuelve, wrap, reuse or rewire must carry the `Kind:` line below (`aidd rules` checks it).

Planning rules: ONE owner agent per Target file (two rows with the same Target file are one task, unless a row says `same owner as T-nn`); waves come from an explicit dependency graph (only true dependencies go in a later wave, everything independent shares a wave, target 2-3); `Agent min` is REAL wall time (one-file task 3-10 min, coupled task or one running the suite 15-25 min); subagents run only their targeted tests and the main agent runs the full suite once per spec after its last wave (run `aidd pending <spec>` first; launch agents only for pending tasks, one per lane); audit fixes go back to the original file owner (SendMessage resume) and fix only CONFIRMED medium+ findings, the rest are documented open exceptions.

Order `COMP-nnn` tasks before any `SCREEN-XX` task that uses them — building a component inline inside the first screen that needs it, then extracting it once a second screen needs the same thing, is a second pass on work already reviewed once.

## Per-task detail (one block per row above)

### T-01
**Classify**
- Nature: `REQUIREMENT` (new work/improvement) \| `INCIDENT` (fixes something broken)
- Priority: 1 CRITICAL / 2 HIGH / 3 MEDIUM / 4 LOW — default 3 unless there's a clear blocking/risk signal
- Kind: VIEW-new | LOGIC | VIEW-legacy: [justification, 5+ characters — only for VIEW-legacy]

**Estimate**
- Effort: High / Medium / Low
- Agent min: [whole minutes of REAL wall time an AI agent needs — this is what the plan is scheduled on]
- Human ref hours: [DERIVED = Agent min x 3 / 60 (calibration file), never estimated by hand; reference only, never the schedule]
- Tokens (est): 60k
- Agent role: builder   # builder | sql | tests | docs | auditor | mapper
- Model tier: medium   # medium | high (never lower)

Estimates come from the baselines in adapters/dot-aidd/templates/calibration.toon (about 50-75k tokens per one-file task; minutes are real wall time, 3-10 min per one-file task). Human ref hours is DERIVED (Agent min x 3 / 60), not estimated by hand.

**Decompose**
- Objective: [1 sentence — what it achieves]
- Activities:
  1. [concrete step — analysis]
  2. [concrete step — development]
  3. [concrete step — testing]

**Assign** (if the project has a team; omit for solo work)
- Suggested resource: [name — only actual, assignable people, never a placeholder]
- Justification: [1 line — why this resource, specialty + workload]

A field you can't substantiate → leave it blank, don't invent it.

### T-02
**Estimate**
- Effort: High / Medium / Low
- Agent min: [whole minutes]
- Human ref hours: [derived: Agent min x 3 / 60]
- Tokens (est): [k]
- Agent role: [builder|sql|tests|docs|auditor|mapper]
- Model tier: [medium|high]

[Same Classify / Decompose / Assign sections as T-01.]

## Waves

Estimates are **agent time**, not human hours. Waves run one after another; tasks inside a wave run in
parallel, so a wave takes as long as its longest task (`max` of its tasks' `Agent min`) and the critical path is the
sum of the waves. A task that depends on another goes in a later wave.

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-01 | builder | [MAX Agent min of the wave] | [SUM of tasks' tokens] | [derived] |
| 2 | T-02 | tests | [MAX Agent min of the wave] | [SUM of tasks' tokens] | [derived] |

Total agent time (critical path): [sum of wave Agent times] min
Total tokens (k): [sum of wave tokens]

Legacy: approved files with the 4-column header (Wave | Tasks | Agent time (min) | Human ref (h)) stay valid.

## Approval gate

**Present the table above as a dry-run and wait for explicit approval before Step 5 starts on any row.**
Any mismatch caught here costs one edit to this file; the same mismatch caught after implementation
costs a rewritten PR. Never start implementing a task that wasn't approved.

The approval is the user's and is tamper-evident: ask them (AskUserQuestion) to approve the tasks, then run
`aidd rules approve <spec_dir>`, which replaces the line below with `Approved: <YYYY-MM-DD> hash:<12 hex>`.
Any later edit to this file voids it, and code edits stay blocked until it is re-approved. Do not write that line by hand.

Approved: PENDING

## Definition of Done (applies to every task above)
1. Code implements exactly the codes cited, in exactly the target file, one class per file, following the plan's Naming & File Contract, SOLID, and the Antifragile standard above (timeouts, retry/backoff, graceful degradation, recoverable trace for anything crossing a boundary).
2. Mapping row added/updated in `qa-audit.md` for every code touched, with file/class/resource-id evidence.
3. PR/Spec ref written back into `mockup-audit.md`, `contracts.md` (if applicable), and `plan.md` for every code touched — appended, not overwritten, if the code was already touched by an earlier PR.
4. Executed verification (screenshot vs mockup, run of the SQL/command/query, tests) — NOT per task: verifier agent(s) (`Agent role: tests`; several only if each covers something different) run it once per wave, only after ALL builders of that wave finished, and write the evidence rows (R10) for every code of the wave. A builder only does a static self-check (parse / compile / lint) and never runs the full verification.
