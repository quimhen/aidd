# AI-Driven Development, one small PR at a time

AIDD is the default pipeline for any change to a codebase — UI or backend-only, a new feature or a
one-line fix — not a UI-specific tool. On every requirement it classifies itself first (new spec,
amendment, or a fast-lane fix) against a searchable graph of every existing spec, then turns the
work into stable codes, an interactive actors×processes flow with generated pseudocode that you correct instead of describe, a task list detailed
with a classify/estimate/decompose/assign rubric, and a per-PR done-checklist audited by an
independent pass. Self-contained: no other skill required.

> **Why it exists.** A palette fixed for 3 pilot screens, then 41 more built before the mismatch
> was caught. A mockup-parity effort that took three audit rounds (97% → 98.7% → 100%) to close,
> because gaps were found by auditing *after* building. A small fix that spawned its own
> disconnected spec folder because nothing checked whether one already existed.
>
> The fix: front-load 100% of the visual truth into codes before any task exists, always search
> the existing spec graph before opening a new one, keep every PR small, and gate "done" on four
> things together — not "looks right."

## Run it

Invoke the skill directly, or reach for one of its eight pipeline-stage commands — each one jumps
straight to that step instead of re-explaining the whole flow:

| Command | Step |
|---|---|
| `/aidd-scope` | −1/0 — search existing specs, pin the visual source of truth |
| `/aidd-audit` | 1/1.5 — mockup audit + visual process flow |
| `/aidd-align` | 2 — resolve ambiguity before planning |
| `/aidd-plan` | 3 — the Screen → Code map |
| `/aidd-tasks` | 4 — break the plan into small-PR tasks |
| `/aidd-build` | 5 — implement one gated PR at a time |
| `/aidd-converge` | 6 — independent, specialized audit |
| `/aidd-doc` | 7 — comprehensive handoff documentation |

Or say nothing special at all: any message that reads like a requirement, change, improvement, or
fix — in English, Spanish, Portuguese, or a handful of literal Chinese trigger terms — engages
AIDD automatically. See [Enforcement hooks](#enforcement-hooks-installed-once-active-every-session)
below.

## The code system

Assigned the moment the mockup is first read. Never renamed. Every later artifact — spec, task,
code comment, checklist — cites the code instead of redescribing the UI.

| Code | Grain | Example |
|---|---|---|
| `SCREEN-XX` | One screen / view / modal | `SCREEN-08` = "Client detail sheet" |
| `SCREEN-XX-Fnn` | One testable behavior of that screen | `SCREEN-08-F03` = "Blocks save when required field is empty" |
| `CTL-nnn` | One control, globally numbered | `CTL-057` = the "Save" button |
| `COMP-nnn` | One reusable component — 2+ screens, like a component design tool | `COMP-003` = "ClientCard" (used on SCREEN-02 and SCREEN-08) |
| `US-nnn` | The use case the screen serves | `US-004` = "Sales rep logs a new order" |
| `API-nnn` | One backend endpoint/contract (full-stack) | `API-012` = `POST /orders` |

**Components close the "rebuilt per screen" gap** — the same card, header, or form appearing on
several screens is built once as a `COMP-nnn` and referenced by every `SCREEN-XX` that uses it, the
same way a component-based design canvas assembles a screen from a library instead of drawing it
from scratch. Full-stack link: a `CTL-nnn` that triggers a network call cites the `API-nnn` it
depends on, and `contracts.md` cites the `CTL-nnn` back — a backend change's blast radius on the UI
becomes a lookup, not a grep.

## Step −1 — Intake: classify before creating

Every requirement, change, modification, update, fix, or improvement request goes through intake
first — before Step 0, before any file is touched. The job is to turn "the user asked for
something" into one of three concrete classifications, from evidence, and say which one out loud
before proceeding.

| Language pattern | Suggests |
|---|---|
| "create", "new screen/module/feature", "something that doesn't exist yet" | New spec |
| "modify", "update", "change", "improve", "add to", "extend" | Amendment to an existing spec |
| "correct", "fix", "doesn't work", "bug", "error in" | Amendment (fix), likely Fast Lane |

That table only pre-loads a hypothesis — wording alone isn't proof. The spec graph search below is
what actually confirms or overturns it.

> **AIDD intake:** `[NEW SPEC | AMENDMENT | AMENDMENT — Fast Lane]` — one-line reason citing the
> search result. Proceeding to the next step.

Decision rule: a match in the spec graph is always an **amendment**, regardless of what the
request's wording suggested — reopen the top-ranked spec, append new codes, never renumber ones
already assigned. If it also meets the Fast Lane conditions (one existing screen, no new use case,
no new component, no navigation change), it's a single task with no full-pipeline ceremony. No
match at all is a **new spec** — justified only when there's genuinely no existing spec covering
the area. A low or ambiguous score is never decided silently: it becomes a question back to the
user.

## The spec graph

Every project accumulates a `specs/index.toon` — a compact tabular index, not JSON, rebuilt
automatically whenever a spec's files change (checked by file `mtime`, no content re-read unless
something actually changed). It holds two things per spec: a searchable set of codes/keywords, and
the spec's real dependency graph, parsed straight from `mockup-audit.md`'s own tables — nothing
re-derived or guessed.

`specs/index.toon` is version 3: each spec's `words` column holds its top 25 terms by TF-IDF across all specs (about 80% smaller than the old full word list). When the index finds nothing, `find_spec.py` falls back to a full-text scan of the spec files (accent-folded) before concluding "no match"; query words shorter than the index minimum are matched only by that fallback.

```
$ python scripts/find_spec.py --tree 001-login
001-login — Login & session
  - US-001
    - SCREEN-01
      - COMP-001
        - CTL-001
          - API-001
        - CTL-002
```

A shared `COMP-nnn` correctly appears under every screen that uses it — this is a DAG, not a flat
tree, matching the "build once, use everywhere" component model. A code-based search prints the
matched code's exact path through the graph ("Graph context") alongside the evidence lines — the
answer to "what does this belong to" is a lookup, not a re-read.

| Command | Does |
|---|---|
| `find_spec.py <keywords or code>` | Ranks every spec by match; exit 0 = amend the top match, exit 1 = safe to create new |
| `find_spec.py --tree <spec-id>` | Prints that spec's full use-case → screen → component → control → API graph |
| `find_spec.py --list` | Lists every spec with its title, from the index — no file reads |
| `find_spec.py --reindex` | Forces a full rebuild — an explicit escape hatch, not a normal step |

Two more things print on every run: a warning if the project has specs but no project-root
`charter.md` (Step −2 was skipped), and whether this run rebuilt the index or hit cache. A rebuild
with a non-empty changed set means dispatch a **Graph Coherence Auditor** — scoped to just the
changed spec(s), never the whole graph — before Step 3/4 build `plan.md`/`tasks.md` on the new
edges. Enforced by `mark_graph_rebuild.py` + `rule_gate.py` (see "Enforcement
hooks" below), not left as a step an agent could skip.

## Two failure patterns it designs against

- **Late-fixed palette** — 3 pilot screens got a palette approved, then 41 more screens were built
  before a mismatch with the real target palette surfaced — full re-migration.
- **After-the-fact auditing** — a parity effort against a mockup took 3 revision rounds to reach
  100% because gaps were discovered by auditing the finished build, not by enumerating every
  element up front.

## Speed — what actually cuts time-to-correct-result

The rest of this skill produces correctness through traceability; these five make it faster to
run, applied by default.

- **Search the spec graph before creating** — `python scripts/find_spec.py <keywords>` replaces a
  remembered grep with a mechanical, indexed lookup.
- **Run the checker before the Auditor reads by hand** —
  `python ~/.claude/skills/aidd/scripts/check_spec.py specs/[###]/` — stdlib-only, catches dangling
  codes, unresolved `[Not Verified]`, empty `PR/Spec ref`, orphaned components, missing
  stored-procedure/exception pairs, missing out-of-scope notes, blank QA statuses. Milliseconds,
  not a manual re-read. The Auditor's judgment goes only to what the script can't check.
- **Check the Component Index before minting a new `COMP-nnn`** — one project-level
  `design-system/components-index.md` listing every component ever created, across every spec — a
  lookup instead of grepping every spec folder the project has accumulated.
- **Wave-dispatch independent tasks** — tasks with no dependency between them (disjoint files, no
  ordering requirement) get dispatched as parallel agent calls **in one message**, not one at a
  time. This is where an agentic workflow actually saves wall-clock time over a linear one.
- **Take the fast lane for small changes** — one existing screen, no new use case, no new
  component, no navigation change → skip `visual-flow.toon` and `comprehensive-documentation.md`,
  amend directly, one task. The full pipeline on a trivial fix is itself a time cost this skill
  exists to eliminate.

Also: when the mockup source has a connected design tool (Figma, Stitch) in the session, Step 1
populates the inventory mechanically from it instead of transcribing a screenshot by eye.

### Grep first — never read a whole file to check one code

Every code is a search key by design. Check whether one exists with `grep -n "CTL-057"
mockup-audit.md`, not a full read; use `check_spec.py`'s report as the first source of truth, not
a manual read-through. The one legitimate full read is Step 1's own audit — exhaustive once, so
everything after it can be a lookup.

**Code markers make source itself greppable:** a fixed `aidd:CODE` tag in whatever comment syntax
the language uses — `// aidd:CTL-057`, `# aidd:SCREEN-08`, `<!-- aidd:COMP-003 -->`. One grep
pattern then finds the mockup row, the plan mapping, and the exact source line together.

### STATE.md — resume without re-investigating

A fresh agent or session has no memory of what a prior one figured out. One small, always-current
file at the project root — **not per-feature** — fixes that: active spec + current step, last
action, next action, and quick pointers (grep targets, not restated content). **Read it first, in
full, before touching anything else.** Every step that changes what's true updates it with a short
edit — append-only, like the revision log, never a full rewrite.

## Templates

Every artifact has a real starting skeleton — nothing is reconstructed from memory each time.

```
~/.claude/skills/aidd/templates/
├── STATE.md                       project-root continuity, read first
├── mockup-audit.md
├── visual-flow.toon
├── contracts.md                    full-stack only
├── data-model.md                   only if persisted data changes
├── research.md                     optional
├── spec.md
├── plan.md
├── tasks.md
├── qa-audit.md
├── comprehensive-documentation.md
├── design-system/
│   ├── MASTER.md                    global visual source of truth
│   ├── components-index.md         project-wide COMP-nnn registry
│   └── page-override.md            per-page exception to Master
└── ../scripts/
    ├── check_spec.py               gap-checker, run before Step 6
    └── find_spec.py                spec graph search + index, run before Step 0
```

## Specialized agents & workflow

Each step has a natural agent boundary. One rule matters more than the rest: **the Step 6 Auditor
must never be the same agent that did the implementing** — an agent that just wrote code is
structurally bad at spotting its own gaps. On Claude Code this is a real gate
(`rule_gate.py`, see [Enforcement hooks](#enforcement-hooks-installed-once-active-every-session)
below), not only a rule stated here.

| Step | Role | Run as | Independence |
|---|---|---|---|
| −1, 1 | Mockup Auditor | Read-only pass | — |
| 1.5 | Diagrammer | Same context, or fresh agent | — |
| 2 | Alignment Agent (drafting) | Fork/fresh agent — compiles the open-question list | — |
| 2 | Ask the user | Main conversation — the one interactive part | — |
| 3 | Mapper (drafting) | Fork/fresh agent — drafts plan.md against the real codebase | — |
| 3 | Approve the plan | Main conversation presents the draft | — |
| 4, 5 | Builder(s) | One per small-PR task | Never the Auditors below |
| 6 | Closing Auditors (QA) — one per domain | Fresh agents/contexts, one per touched domain | **Mandatory** — none implemented what it checks |
| 7 | Documenter | Mechanical assembly, any agent | — |

> **Why this makes UI validation cheap now.** Because every screen/control already carries its
> code and its `PR/Spec ref`, the Auditor's job collapses to "does the file at this ref implement
> what the code says, does its screenshot match the mockup" — a lookup per row, not a rediscovery
> of the feature.

### Scope discipline — every dispatched agent

Every agent prompt (Builder, Auditor, Diagrammer) states exactly what to do **and** exactly what
not to do — and stops instead of guessing when that isn't enough.

- **In scope** — only the codes and target file(s) the approved task names. Nothing else.
- **Out of scope** — everything else. An unrelated bug spotted along the way is a note back, never
  a bundled fix.

> **On ambiguity: stop, don't guess.** A code that doesn't resolve, a missing schema, a naming case
> the contract doesn't cover — the agent reports what's unclear and does not implement a
> "reasonable" interpretation in the meantime. Same weight as the Step 4 approval gate: a guess
> made here is indistinguishable, later, from a requirement.

## Engineering standards — restated in every agent's instructions

A fresh agent doesn't inherit these from a prior task's context, so every Builder and Auditor
prompt (Step 4 onward) carries them explicitly, every time.

- **S** — one reason to change per class/module/widget — not UI + network + validation in one name.
- **O** — extend with new code; don't bend working logic with special-case branches.
- **L** — a subtype must be usable anywhere its base is, with no surprising behavior.
- **I** — split a fat interface a consumer only partially needs.
- **D** — depend on an abstraction across any boundary — network, DB, hardware — never the concrete
  implementation directly.

> **Antifragile / Design for Failure — assume everything can fail.** Every operation crossing a
> boundary (network, DB, disk, external API, hardware) gets an explicit timeout, retry with
> backoff, and a graceful degraded path — never a blank screen.
>
> A failure that exhausts retries must leave a **traceable, recoverable record** — a dead-letter
> entry, a status field, a log with enough context to replay manually — not a caught exception
> that vanishes. Never fail silently to the user.

This isn't a fifth Definition-of-Done item — it's a property of the "Code" item in Step 5's DoD,
and the Step 6 Auditor checks failure paths too, not only happy-path fidelity to the mockup.

### One class per file, and a Naming Contract nobody has to guess

**Never bundle several classes into one file** — it makes editing unsustainable: every unrelated
change touches the same file, diffs stop being reviewable, and two tasks collide on a file that
should've been two. A task whose target file would need a second class is two tasks, not one.

| Item | Convention |
|---|---|
| Classes / components / types | PascalCase |
| Functions / variables / methods | camelCase |
| File names | the project's own convention — stated once, never defaulted |
| Classes per file | **one** |

Declared once in `plan.md`'s Naming & File Contract, before any task is written — an agent unsure
which casing applies to what stops and asks, it never picks one on its own.

### Data access & frontend↔backend communication — fixed rules

- **Stored procedures by default** — every database query goes through a stored procedure, not
  inline/ad-hoc SQL. An exception is written down in `contracts.md`, never silent.
- **API-only frontend↔backend** — the frontend never connects directly to a database or internal
  service. A `CTL-nnn` needing data cites its `API-nnn` — created first, never worked around.
- **Swagger on every API** — not "add it later." If the Swagger spec and `contracts.md` diverge,
  the Swagger spec is what gets corrected — it's what other consumers actually read.

### Database design, connections & indexing

- **Entity → Table/Column mapping** — the ER diagram shows the shape; `data-model.md`'s mapping
  table shows the exact table/column/key code reads and writes. Every entity connects to another
  or is explicitly isolated by design.
- **Database object naming contract** — tables, columns, keys, procedures, indexes, constraints,
  views — declared once in `plan.md`, same rigor as PascalCase/camelCase for code.
- **Pool connections, release in a guaranteed path** — a manual open/close per query is the
  exception, written down. Every connection is released via `finally`/`using`.
- **Validate before trusting, not after failing** — a pooled connection can be stale. Ping it
  (`SELECT 1` or the pool's health check) before the real query.
- **Explicit transaction boundaries** — begin/commit/rollback are visible in code, not implied —
  and the rollback path is exercised, not just assumed.
- **Stored procedures verified against the engine's real plan** — `EXPLAIN ANALYZE`
  (Postgres/MySQL), execution plan (SQL Server), `EXPLAIN PLAN` (Oracle). A full table scan on a
  non-tiny table is a gap, not a detail.

### Modern BaaS (Supabase, Firebase, PlanetScale, Neon) — the rules translated, plus RLS

These platforms swap "app server pools connections, calls stored procedures" for "managed client
SDK talks to an auto-generated API." Most rules above map directly; one has no traditional
equivalent:

- **RLS policies — the primary access-control layer.** A table with no explicit Row Level Security
  policy is fully open or fully locked depending on the platform default. `data-model.md` gets one
  row per table per operation — no table left implicit.
- **Stored procedure → Postgres function via RPC** — same naming contract, same `EXPLAIN ANALYZE`
  verification.
- **Connection pool → one shared client SDK instance** — the mistake to guard against is a new
  client instantiated per request/component.
- **Validate before trusting → session/token refresh** — auth sessions expire; refresh before an
  operation depends on it.
- **Realtime subscriptions need their own resilience** — reconnect with backoff on drop, explicit
  unsubscribe on unmount.

## Enforcement hooks — installed once, active every session

AIDD ships hooks so it doesn't rely on remembering to invoke it. Run `python scripts/install_hooks.py`
once per machine to merge ten entries into `~/.claude/settings.json` (idempotent, never touches
unrelated hooks already there):

| Event | Script | Effect |
|---|---|---|
| `UserPromptSubmit` | `prompt_trigger.py` | Detects change language in EN/ES/PT + literal CJK terms, runs `find_spec.py` against the message itself, and injects the Step −1 verdict inline; also records the prompt in the evidence log (to verify user quotes). |
| `PreToolUse` (`Write\|Edit\|MultiEdit\|NotebookEdit\|PowerShell\|Bash`) | `rule_gate.py` | Blocks (exit 2): writes to the evidence logs (R9); source code before AIDD ran this session; `qa-audit.md` without an independent subagent after the last code edit **and** one distinct auditor per required domain (R7); `plan.md`/`tasks.md` out of chain order, graph check fail-closed (R5); structurally invalid `spec.md`/`tasks.md` (R1–R3); the `Approved:` line unless the user's recorded answer is "Approve" and nothing else changed (R6); writes to code files (deny-list: everything except docs/images/lockfiles and `specs/`, `.git/`, `node_modules/`, …) while ANY open spec lacks a valid, recorded approval or its `tasks.md` (R6), or while visual debt is open (R4); and Bash/PowerShell commands that write into protected paths or touch the evidence libraries/env overrides (R9; a lexical guard, not a sandbox). Timeout 15 s. `AIDD_RULES=off\|0\|false\|no\|warn` is honoured. |
| `PostToolUse` (Skill) | `mark_invoked.py` | Marks AIDD invoked for this session. |
| `SessionStart` | `session_start.py` | Resets that marker for each new session; records `session_start` in the evidence log. |
| `PostToolUse` (`Write\|Edit\|MultiEdit\|NotebookEdit\|PowerShell`) | `mark_code_edit.py` | Appends `code_edit` / `spec_edit` events — to every project root above the file — and the informational active-spec pointer when a `specs/<id>/{spec,plan,tasks,mockup-audit,contracts,data-model}.md` file is written; records `approved{spec,hash}` when `tasks.md` is written with a hash-valid `Approved:` line. Timeout 10 s. |
| `PostToolUse` (Task\|Agent) | `mark_agent_dispatch.py` | Timestamps the most recent independent subagent dispatch this session; appends a `subagent` event. |
| `PostToolUse` (`Bash\|PowerShell`) | `mark_graph_rebuild.py` | Records a `find_spec` event (`rebuilt`, `ok`, `source`) only when the command really RUNS `find_spec.py` (`python`/`py`/`& python`, `-X utf8`, `time`/`timeout` prefixes, `powershell -c "python …"`); `ok` only when the output carries the authentic `aidd spec search` header or a known no-spec message. Timeout 10 s. |
| `PostToolUse` (`AskUserQuestion`) | `mark_user_question.py` | Appends a `question` event (text + offered option labels) **and an `answer` event** with the pairs anchored on the known questions — approvals, closes and abandons are accepted only from a recorded answer that picked the required option ("Approve", "Yes, close", "Abandon"); short user quotes (≥ 2 words) are verified against answers. Timeout 10 s. |
| `Stop` | `stop_gate.py` | Rule R8: refuses (exit 2) to end the session while any OPEN spec (all sessions) has a valid approval, code edits after its `approved` event, and `qa-audit.md` missing or a required domain uncovered. Blocks at most 3 times per (spec, approval hash) (`stop_block` events), then allows and records `stop_block_exhausted`. Silent when no spec is open. Timeout 15 s. |
| `SessionStart` | `memory_context.py` | Prints a short AIDD Memory digest (entry count + the 5 most recent non-superseded decision/constraint/risk entries). Silent without `.aidd/memory/`; always exits 0. |
| `PreToolUse` (Read\|Edit\|Write) | `memory_file_context.py` | **Opt-in** (`install_hooks.py --with-memory-file-hook`; costs a process per Read/Edit/Write). First time a file is touched in a session, injects up to 3 memory entries that mention it. Silent without `.aidd/memory/`; always exits 0, never blocks. |

> **Why the independent-audit gate (`require_independent_audit.py`, run by `rule_gate.py`) exists.** This gate was added after a real session
> self-audited its own bug fix, wrote `qa-audit.md`, and moved on — nobody independent had
> actually checked it. It took a direct question ("did we really use a second agent?") to catch it
> after the fact. This hook makes that failure mode a hard stop instead of something that depends
> on someone asking. It can only verify *some* subagent ran after the last edit, not that it
> audited the right thing — raises the bar from "trivially skipped" to "requires a deliberate
> workaround," not a formal proof.

> **Why the graph-coherence gate (`require_graph_coherence_audit.py`, run by `rule_gate.py`) exists.** Same failure shape, one step earlier: a
> mechanical parser (`find_spec.py`) can misparse an edited row or carry over a stale
> relationship without raising an error — it just produces a graph that looks complete and
> is quietly wrong. Planning against that unverified graph is exactly the "trust the note,
> don't re-check reality" mistake `check_charter.py` exists to prevent one layer up (see "A
> rule nobody re-checks is just a claim" in `docs/WHY-AIDD.md`) — same principle, applied to
> the graph instead of the charter.

> **Language coverage.** The prompt-level nudge covers English, Spanish, Portuguese, and a handful
> of CJK terms — not every language. Even where it stays silent, AIDD still engages: the skill's
> own description is matched semantically by the model in any language, and the hard Write/Edit
> gate never reads the prompt at all.

Scope is global (every session on the machine) by design. Known gap: Bash and PowerShell can still edit code (heredocs, `sed`, `Set-Content`) — only Write/Edit/MultiEdit/NotebookEdit are gated; the shell tools are only checked for writes into protected paths (a lexical guard, not a sandbox).

### Hard rules — enforced by hooks

Rules R1–R9 turn the pipeline's prose requirements into gates. Contract: `specs/002-aidd-hard-rules/spec.md`.

| Rule | What it blocks | The exact fix |
|---|---|---|
| **R1** estimates are agent time | Writing `tasks.md` with no `## Waves` table, a task lacking `Agent min:` / `Human ref hours:` (a bare `Estimated hours:` counts as missing), a wave time that is not the max of its tasks, a total that is not the sum of the waves, or a `Status` / `Tracker ref` / `PR/Spec ref` cell longer than 60 chars or 8 words (those cells are hash-neutral, so they must stay short) | Add `Agent min:` + `Human ref hours:` per task, the Waves table `\| Wave \| Tasks \| Agent time (min) \| Human ref (h) \|`, and `Total agent time (critical path): N min` |
| **R2** route is declared | Writing `spec.md` with no `## Pipeline route` table, a duplicate step row, or a step `waived` without a Reason and `user — "<quote ≥ 3 words>"` (the quote is verified under R5) | Add the route table (one row each for `-1, 0, 1, 1.5, 2, 3, 4`); ask the user (AskUserQuestion) before waiving and quote their words, or set the step back to `run` |
| **R3** alignment provenance | The Minimum Requirements Checklist missing any question of the shipped template (extra rows are fine) or with a blank / `-` Answer; an answer with no valid `Source`; a `repo — <path>` that does not exist under the project root, has no `:LINE` (or a LINE beyond the file) and no `"quote ≥ 3 words found in that file"` (a bare directory, `.` or `README.md` is rejected); a Proposed marker in ANY column (unconfirmed whatever the Source says) | `user — "<quote>"`, `repo — <existing path>:<LINE>` (or `repo — <path> "<quote from the file>"`), or `[Proposed — unconfirmed]` if the agent chose it |
| **R4** visual debt | Waived Steps 0/1/1.5 with `SCREEN-nn` codes (any case, also inside HTML comments; in `spec.md`, `plan.md`, `contracts.md` or another spec) and no `## Visual debt` row; a `Blocks spec` that is not an existing spec id; a `resolved` row without a real Mockup source (existing file, `http(s)://` or `figma:`) and a `mockup-audit.md` row for its codes; while a row is `open`, writes under the blocked spec and code edits for it (evaluated on the would-be content of the write) | List the codes in `## Visual debt`, ask the user for the mockup source, run Steps 0/1/1.5, mark the row `resolved` with the source |
| **R5** chain order | Writing `plan.md` without a `find_spec` run this session, an independent subagent after the last `spec.md` edit, **no blank checklist Answer**, zero `[Proposed` rows, every `user — "quote"` verified (≥ 5 words found in a recorded prompt, or ≥ 2 words found in a recorded answer to an AskUserQuestion — both recorded AFTER the spec's first edit) and no open debt; writing `tasks.md` without `plan.md`, a subagent after the last `plan.md` edit, and (fail-closed) a `find_spec` run, plus a subagent after any graph rebuild | Run `find_spec.py`; dispatch the Mapper/Alignment agent over `spec.md`; ask the user every open question (AskUserQuestion) and quote their answer; dispatch an auditor over `plan.md`; then retry |
| **R6** tasks approval | Writing the `Approved:` line (or running `aidd rules approve`) unless the user's recorded answer is the option **"Approve"** of an AskUserQuestion about approving the tasks (topic `approv|aprob`; asked in this session, newer than the last change of `tasks.md`; the question must OFFER that option and contain the tag `[tasks:<hash8>]` of the current `tasks.md`) and `tasks.md` is R1-valid; the gate allows the edit only if it changes nothing else (`approval_hash` before = after) and the written hash is that hash. **Every write to a code file** — EVERY file except `md markdown txt rst csv tsv log lock png jpg jpeg gif svg ico webp bmp pdf docx xlsx pptx zip` and except `specs/`, `design-system/`, `.aidd/memory/`, `.claude/skills/`, `.git/`, `node_modules/`, `__pycache__/`, `.venv/` (canonical path relative to the outermost project root) — **is blocked while ANY open spec has no valid approval, no hook-recorded `approved{spec,hash}` event for the current hash, or no `tasks.md` at all ("Step 4 missing")**. The hash ignores the `Status`, `Tracker ref` and `PR/Spec ref` columns/lines, so sync/link tools do not void it; any other edit does | Present the tasks, ask with AskUserQuestion (question text with the `[tasks:<hash8>]` tag, option "Approve"), then `aidd rules approve specs/<id>` |
| **R7** closing audit per domain | Writing `qa-audit.md` while any required domain (`performance` always, `ui`, `backend`, `database` by what the tasks touch) lacks its OWN subagent after the last code edit (any code edit — code edits carry no spec attribution) whose description or the first 400 chars of its prompt name it (word-boundary match; one subagent counts for ONE domain only) | Dispatch one auditor per missing domain, name the domain in its prompt, rewrite `qa-audit.md` |
| **R8** stop gate | Ending the session (Stop hook, exit 2) while ANY open spec (across all sessions) has a valid approval, code edits after its `approved` event, and `qa-audit.md` missing or a required domain uncovered. Blocks at most 3 times per (spec, approval hash), then allows and records `stop_block_exhausted` — it is a nudge, not a lock; `stop_hook_active` is not a free pass | Run the missing auditors and write `qa-audit.md`, then `aidd rules close <id>` |
| **R9** protected paths | The agent writing anything under `.aidd/` EXCEPT `.aidd/memory/**`, or the per-session evidence directory (`<tempdir>/aidd-hooks/`), via Write/Edit/MultiEdit/NotebookEdit; and Bash/PowerShell commands that write, delete, move or redirect into those paths, that import or `-m`-run `aidd_evidence|aidd_rules|aidd_status`, that contain `AIDD_TESTING`, `AIDD_EVIDENCE_DIR` or `AIDD_SESSION_ID` anywhere, or assign `AIDD_RULES=`, that write/remove/move under `specs/` (e.g. deleting `tasks.md`), that mention `tasks.md` together with `Approved`, or that use the obfuscation forms the audit found (`xargs rm`, `curl -o`, `tar -C`, `unzip -d`, `Expand-Archive`, `iwr`/`Invoke-WebRequest -OutFile`, `Tee-Object`, `[IO.File]::`, `[IO.Directory]::`, `Export-Csv`, `git apply`, `eval`, glob characters in a `.aidd` path). Paths are canonicalised first (case, `..`, trailing dots/spaces, `::$DATA`, 8.3 names, junctions/symlinks). The Bash/PowerShell guard is a cheap lexical pre-check, not a sandbox | None — those files are written by hooks only |

**Evidence, not trust.** Hooks append what they observed (the agent is not supposed to write it). The evidence is split by scope so a session started in a parent folder, or in a project without AIDD, still works and creates nothing in the project: SESSION kinds (`prompt`, `subagent`, `question`, `answer`, `find_spec{rebuilt,ok,source}`, `session_start`, `hook_error`) go to a per-session log under `<tempdir>/aidd-hooks/evidence/<session-id>.toon`, never inside a project; PROJECT kinds (`spec_edit`, `code_edit`, `approved{spec,hash}`, `spec_closed{spec,reason,hash}`, `stop_block`, `stop_block_exhausted`) go to `<project>/.aidd/evidence/events.toon` (git-ignored, append-only), written only where a project root (a folder with `specs/` or `.aidd/`) is found — `spec_edit`/`code_edit` are written to EVERY root above the edited file, and a project with no root gets no file. The gates read both transparently. R9 blocks the Write/Edit tools and a lexical shell guard from touching them — nothing more; it is not a sandbox. Rules fail **closed on missing evidence** and **open on a hook crash**. `AIDD_EVIDENCE_DIR` relocates the logs only when `AIDD_TESTING=1` is also set (tests); the hooks and the CLI ignore both otherwise.

**Answers are anchored, not guessed.** `mark_user_question` records the question with its offered option labels and the answer pairs, built ONLY by matching the harness response against the known question strings in order; if the count does not match, the answer is stored as unusable. Approval, close and abandon are accepted only from a recorded answer whose chosen label is one of the options the question OFFERED and matches the required label — **the agent must offer exactly "Approve" (tasks), "Yes, close" (close) or "Abandon" (abandon)**; "Yes", "OK" or free text do not count. The approval question must also contain the tag `[tasks:<hash8>]` — the first 8 hex chars of the current `approval_hash` of `tasks.md` (`aidd rules approve` prints the exact tag when it refuses) — so an answer given for an older version of the tasks is void, e.g. `Approve these tasks? [tasks:1a2b3c4d]` with the option `Approve`. User quotes in `spec.md` are verified the same way: ≥ 5 words in a recorded prompt, or ≥ 2 words in a recorded answer, both recorded after the spec's first edit.

**Open specs, not "the active spec".** A spec is *open* from the first recorded edit of its `plan.md` or `tasks.md` (editing `spec.md` alone does not open it) until a `spec_closed` event. R6/R7/R8 and the code gate apply to EVERY open spec in every project root above the file being written (nested roots included); a code edit applies to all of them. An open spec with no `tasks.md` blocks code edits ("Step 4 missing: write tasks.md, then get approval"). Touching or creating another spec cannot switch the gates off. `.aidd/active_spec` is an informational pointer only and no gate reads it. A spec stops being open only via `aidd rules close <id>` (completed: valid, recorded approval + `qa-audit.md` + every required domain audited + the user's recorded "Yes, close") or `aidd rules abandon <id>` (the user's recorded "Abandon"; no `qa-audit.md` needed); a later `tasks.md` edit re-opens it unless the approval hash is unchanged (a Status-only edit).

**Escape hatch (owner only):** set `AIDD_RULES` in the `env` block of `~/.claude/settings.json`: `off`, `0`, `false` or `no` disables the gates; `warn` prints messages to stderr and never blocks; anything else (or unset) enforces (value is trimmed, case-insensitive). The Bash/PowerShell guard also blocks commands that assign `AIDD_RULES=`.

**Commands (also usable from a terminal or CI):** `aidd status [spec_dir] [--json]` lists ALL open specs with their approval state ("Step 4 missing" for an open spec without `tasks.md`) and, per spec, the ledger (route steps and whether each waiver is confirmed, proposed/unanswered/unverified alignment answers, Mapper and graph evidence, approval validity and whether the `approved` event is recorded, waves and critical-path minutes, code edits, per-domain auditor coverage, open visual debt) plus **WHY blocked** lines (rule, message, exact fix); globally: how many AskUserQuestion answers were recorded, `stop_block` counts and hook errors; exit 0 always, even for a pathological `tasks.md`. `aidd rules check <spec_dir>` prints `PASS|FAIL Rn message → fix` and exits 1 on any violation. `aidd rules approve <spec_dir>` writes the `Approved:` line and records the `approved` event only with the user's recorded answer "Approve" (same session, newer than `tasks.md`) and an R1-valid `tasks.md`; otherwise it refuses and prints the exact `[tasks:<hash8>]` tag the question text must contain; the question must also OFFER the option "Approve". `aidd rules close <id>` needs an open spec, a valid recorded approval, `qa-audit.md`, every required domain audited and the recorded answer "Yes, close" (asked after `qa-audit.md`); it records `spec_closed(completed)`. `aidd rules abandon <id> [--reason TEXT]` needs the recorded answer "Abandon" and records `spec_closed(abandoned)`. The CLI cannot see its own session id: it uses the session of the newest recorded user prompt, and ignores `AIDD_SESSION_ID`/`AIDD_EVIDENCE_DIR` unless `AIDD_TESTING=1`. `check_spec.py` also reports the static rules (R1–R4, R6) as gaps.

**Limitations — read this before trusting the rules.** (1) **Bash and PowerShell can still edit code**: heredocs, `sed`, `Set-Content`, scripts — the code gate covers Write/Edit/MultiEdit/NotebookEdit; the shell tools are only checked for writes into protected paths. (2) Through Bash/PowerShell an agent can also **try to forge evidence** by calling the CLI or the libraries; the guard that blocks this is lexical (pattern matching on the command text), not a sandbox, and a determined agent can evade it. (3) The gates verify that a subagent ran and a question was answered, **not that they were any good** — an auditor that rubber-stamps still satisfies R5/R7. (4) The user's click cannot be cryptographically proven: an answer is accepted when the hook recorded the user's response to an anchored question that offered the required option, which is evidence, not proof. (5) Hooks **fail open** on a crash, a launch failure or a timeout (15 s gates, 10 s recorders) and record a `hook_error` only when they can run at all — `aidd status` shows the count. (6) **R8 relaxes after 3 blocks per approval hash**, then lets the session end. (7) Session ids and resume/compact behaviour are not verified: events without a session id are `unknown-session`, and the CLI infers its session from the newest prompt. (8) A user quote is checked against what was recorded as typed or answered, not for whether it means what the agent claims. (9) A spec stopped at `spec.md` (no `plan.md`/`tasks.md` yet) is not open, so it opens no gates. (10) Code can be planted under exempt locations (`.git/hooks`, `node_modules/`, `specs/`) because R6 does not gate them. (11) `repo —` sources only prove that the file (and line) exists, not that it is relevant. (12) The shell guard has false positives (`cp … specs/…`, `git mv specs/…`, `echo x > specs/a.md`): use the Write tool for those. (13) With several concurrent windows the CLI can infer the wrong session; it then fails closed (refuses). (14) A stray legacy marker file may appear in `%TEMP%\aidd-hooks` during tests. (15) `AIDD_TESTING` cannot be detected as "started by the test suite": the CLI honours it as set, and the shell guard blocks any command that contains `AIDD_TESTING`, `AIDD_EVIDENCE_DIR` or `AIDD_SESSION_ID`. **In short: the rules stop accidental and self-justified skipping; they do not stop a determined agent.**

## Memory — the WHY, anchored to codes

`STATE.md` says *where am I*; `specs/index.toon` says *what exists*; neither says **why** something is the way it is — why the flow uses TOON and not JSON, why that option was rejected, what the root cause of that bug was. That reasoning normally dies with the session. **AIDD Memory** keeps it: curated, code-anchored, git-versioned entries in AIDD-TOON (the same dialect family as `specs/index.toon`) under `.aidd/memory/`, committed with the code. **No daemon, no LLM observer on every tool call, no vectors, stdlib only.** An agent writes an entry when it learns something worth keeping; nothing is captured automatically.

**Storage.** `.aidd/memory/<scope>.toon` — scope is a spec id (`001-aidd-memory`) or `project` — plus `archive/<YYYY>-Q<q>.toon` for compacted entries. One row per entry, always on one line; the writer emits `entries[*]` so two branches appending rows never conflict on a counter:

```
version: 1
memory: project
entries[*]{id,date,type,title,codes,files,why,supersedes,source}:
  m-3fa91c02,2026-10-01,decision,Flows use TOON not JSON,US-001|CTL-004,skill/scripts/flowmap.py,"User asked for TOON; matches specs/index.toon",,agent
```

`codes` (`SCREEN-XX`/`CTL-nnn`/`COMP-nnn`/`API-nnn`/`US-nnn`) and `files` (POSIX, project-relative) are `|`-joined — the anchors that make a memory a lookup by code. `title` ≤ 120 chars, `why` ≤ 400. `supersedes` points at the older entry this one replaces; that one stops showing in default search and injection but stays reachable with `show`.

**The 8 entry types** (closed set; anything else is rejected): `decision`, `bugfix`, `discovery`, `constraint`, `risk`, `rejected`, `open-question`, `state`.

**Capture points** — the agent runs `aidd mem add ...` (or `python scripts/aidd_memory.py add ...`):

| When | What to record |
|---|---|
| End of **Step 2** | Each resolved alignment decision, and each option that was considered and rejected (`rejected`) |
| **Step 5**, per PR | A non-obvious *why* — a choice a later reader would otherwise have to rediscover |
| **Step 6** | Audit findings and the root cause of any bug found (`bugfix`, `risk`) |
| Any time | A discovered `constraint` (an engine limit, an upstream contract, a rule nobody wrote down) |

```bash
aidd mem add --type decision --title "Flows use TOON not JSON" \
  --why "User asked for TOON; matches specs/index.toon" --codes US-001,CTL-004 --files skill/scripts/flowmap.py --scope 001-aidd-memory
```

**Read points:**
- **Step -1**, right after `find_spec.py` — on a match it also prints up to 3 `Memory:` lines (`m-id type title`) for the matched codes, when a memory dir exists.
- **Start of any task** — `aidd mem search <codes or words>` before touching the code those codes name.
- **Automatically, Claude Code only** — `memory_context.py` injects a short digest at session start (installed by default). `memory_file_context.py` injects the entries that mention a file the first time it is touched in a session, but it costs a process per Read/Edit/Write, so it is **opt-in** (`python scripts/install_hooks.py --with-memory-file-hook`); `aidd mem file <path>` is the on-demand equivalent. Both are silent when there is no `.aidd/memory/`.

**Progressive disclosure — `search` then `show`.** `aidd mem search <words...>` prints one line per hit (`id  date  type  [codes]  title`, ~25 tokens each) and **never** the `why`; `aidd mem show <id...>` returns the full rows, including superseded and archived ones. Ranking is BM25 over title, codes (an exact code match dominates), file tokens and `why`. Filters: `--type`, `--code`, `--file`, `--scope`, `--limit`, `--archive`; `--json` for scripts. Exit code 2 means nothing found. Also: `aidd mem timeline <id>`, `aidd mem file <path>`, `aidd mem inject`, `aidd mem stats`.

**`compact`.** `aidd mem compact [--before YYYY-MM-DD] [--apply]` — a dry run unless `--apply`; moves superseded entries (and, with `--before`, older ones) to `archive/<YYYY>-Q<q>.toon`. It is the only operation that rewrites existing rows; everything else only appends.

**Location, dates, cache.** `AIDD_MEMORY_DIR` overrides the memory directory (default `.aidd/memory/`). `--root X` is a global option of `aidd mem` and works before or after the command (`aidd mem --root X search login`, `aidd mem search login --root X`). `add --date YYYY-MM-DD` backdates an entry (default today). `search`/`inject` may keep an optional derived cache in `<memory dir>/.cache/` (gitignored by a `.gitignore` the writer creates): invalidated automatically by file mtime/size, safe to delete, never the source of truth. `archive/` is excluded from search and injection by default — run `compact` to keep the active set small, and use `--archive` to search it.

**Importing from claude-mem (one-off, optional).** `aidd mem import-claude-mem <db> --project SUBSTR [--project ...] [--since YYYY-MM-DD] [--scope NAME] [--include TYPES] [--no-summaries] [--dry-run]` (`scripts/aidd_memory_import.py`) reads a claude-mem SQLite file **read-only** and appends mapped entries with `source=import`: `decision` → decision, `bugfix`-like types → bugfix, security/critical types → risk, each session summary → one `discovery` (`--no-summaries` skips them); `--include` opts further observation types in as `discovery`; `--project` is repeatable and `--since` limits by date; `--scope` is the memory scope the entries land in (default `project`); `--dry-run` writes nothing. The import scrubs secrets (`password`/`token`/`apikey`/`bearer`/... assignments, long hex runs) and private/internal IPv4 addresses to `[redacted]` in title and why, and keeps only plausible project-relative POSIX paths in `files` (absolute paths outside the destination root are dropped). It is idempotent (ids are content-derived) and never writes to the claude-mem database, imports its code, or starts its worker. A file that is not a claude-mem database exits 1 with a message. After the import, AIDD Memory has no runtime dependency on claude-mem. Injection prefers non-imported entries; imported ones only fill remaining slots.

**Caution — memory is injected content.** Entries are committed text that hooks and `inject` put into every session. They are sanitised on injection (control characters stripped, lines capped at 160 chars) but remain untrusted: review memory changes in PRs like code, and never treat an entry as an instruction.

**How the three continuity artifacts differ:**

| Artifact | Answers | Written | Size discipline |
|---|---|---|---|
| `STATE.md` | Where am I — active spec, step, next action | Every step, edited in place | One small file, read in full first |
| `specs/index.toon` | What exists — which spec owns this code | Auto-rebuilt by `find_spec.py` | Mechanical, never hand-edited |
| `.aidd/memory/` | Why is it this way — decisions, bugs, constraints | Appended at the capture points above | Searched, not read in full: `search` → `show` |

## Pipeline

### Pipeline route and visual debt — declared, never silently skipped (hard rules R2 / R4)

`spec.md` carries a `## Pipeline route` table `| Step | Status | Reason | Confirmation |` with one row for each of `-1, 0, 1, 1.5, 2, 3, 4`; `Status` is `run` or `waived`. A waived step needs a `Reason` and a `Confirmation` of the form `user — "<exact quote, 3+ words>"` — **ask the user before waiving anything**; the quote must be something they really typed. Steps 0/1/1.5 may be waived only for a change with no visual surface. If they are waived and `SCREEN-nn` codes still appear in the spec's files (or in another spec without a `mockup-audit.md` row), `spec.md` also carries a `## Visual debt` table `| Codes | Blocks spec | Status | Mockup source |` (`open` | `resolved`; `resolved` needs a mockup source). While a debt row is `open`, writing under that spec — and, on Claude Code, editing code while that spec is open — is blocked (the `active_spec` pointer is informational only).

### Step −2 — Project setup (one-time, before the first feature — the Charter phase)

Copy `templates/charter.md` to the project root and fill it in (see "Project charter" below).
On a brownfield project with real code but no `specs/` folder yet, run `scripts/research_project.py`
in this same phase to propose the first candidate spec areas — see "Research mode" in `SKILL.md`.
Everything downstream (the spec graph, every later step) depends on this phase happening first,
not being discovered as missing partway through Step −1.

### Step −1 — Intake & search before creating

Classify the request (New spec / Amendment / Amendment — Fast Lane) against the spec graph. Never
open a new `specs/[###-feature]/` folder without running `find_spec.py` first.

### Step 0 — Establish the visual source of truth — skip entirely if there's no visual surface

A mockup exists → go to Step 1. No mockup yet, but the change touches UI → copy
`design-system/MASTER.md` once per project; add a `page-override.md` only where one screen
genuinely differs. An approved doc already exists → read Master and its override first. **No
visual surface at all** (backend, API, DB, infra, pure refactor) → skip Steps 0/1/1.5 entirely and
go straight to Step 2.

### Step 1 — Mockup Audit — mechanical, no prose

Copy `templates/mockup-audit.md`. One pass, before any task is written: Provenance, Screen
inventory, Component inventory, Control inventory, Navigation map, Behavior list per screen.

→ `specs/[###]/mockup-audit.md`

### Step 1.5 — Visual Process Flow — draw it, don't describe it

**Explaining step-by-step what a user can do on a screen, in prose, is where interaction with the AI usually breaks down** — and the user cannot confirm a plan they cannot see. Replace that with **AIDD Flowmap**: copy `templates/visual-flow.toon` to `specs/[###-feature]/visual-flow.toon` and fill one `flow: US-nnn` block per use case, built mechanically from Step 1's screen inventory, control inventory and navigation map. The source is **AIDD-TOON** (the same tabular TOON dialect as `specs/index.toon`, not JSON, not Mermaid): `actors` (swimlane rows — human / system / data / external), `processes` (phases), `steps` (every screen/control step cites its `SCREEN-XX`/`CTL-nnn` code, never a redescription) and `links` (labeled branches; a decision's every branch must carry its condition). **Never place coordinates** — layout, routing and pseudocode are derived.

```
flow: US-001
title: Waiter opens a table
actors[3]{id,label,kind}:
  waiter,Waiter,human
  pos,POS app,system
  db,SQL Server,data
processes[2]{id,label}:
  P1,Choose table
  P2,Take order
steps[4]{id,actor,process,type,code,label,detail}:
  s1,waiter,P1,start,,Enters waiter profile,
  s2,pos,P1,screen,SCREEN-01,Table map,
  s3,pos,P1,decision,CTL-004,Open table?,Checks open ticket via API-012
  s4,pos,P2,screen,SCREEN-08,Order ticket,
links[3]{from,to,label,role}:
  s1,s2,,main
  s2,s3,,main
  s3,s4,free,main
```

Then run `aidd flow specs/[###-feature]/visual-flow.toon --open` (or `python scripts/flowmap.py ...`). It validates first (dangling links, dead ends, unreachable steps, decision branches without a condition, missing codes — and with `--spec-dir`, codes that do not exist in the spec) and only then writes a standalone interactive `visual-flow.html` with: the **actors × processes swimlane flow**, **generated pseudocode** (IF/ELSE/GOTO derived from the graph, synchronized with the diagram), and an **Actors × Processes matrix**. The user can click any step, walk the flow with the arrow keys, pick a branch with `1-9`, filter by actor or process, and gets the exact reference to cite (`US-001/s3`).

**This is the interaction surface for Step 2**, not a diagram to review passively: show the user the rendered HTML and have them correct the *flow* by node reference ("US-001/s3: missing branch for a reserved table") instead of describing it in words; each correction is one small diff to the TOON followed by a re-render. Keep one `flow:` block per `US-nnn` so a correction stays local. `check_spec.py` validates `visual-flow.toon` automatically.

### Step 2 — Align (Alignment Agent)

A fork/fresh agent compiles the question list first — every `[Not Verified]` row, plus every blank
row in `templates/spec.md`'s Minimum Requirements Checklist — mechanical work, no interaction
needed. Only then does the main conversation ask the user.

> **Gate.** Step 3 does not start while any Minimum Requirements row is blank.

**Alignment provenance (hard rule R3).** Every answered row of the Minimum Requirements Checklist carries a `Source`: `user — "<exact quote, 3+ words>"`, `repo — <path[:line]>`, or `[Proposed — unconfirmed]`. An answer the agent chose itself is **always** `[Proposed — unconfirmed]` — the agent never self-answers an Align question and writes it up as if the user had said it. Drafting `spec.md` with Proposed rows is fine; **planning is not**: Step 3 does not start while any `[Proposed` row is left, and every `user — "..."` quote must be a literal substring of something the user actually typed. Ask the user (AskUserQuestion), then replace the Source with their own words.

→ `specs/[###]/spec.md`

### Step 3 — Plan: the Screen → Code map (Mapper)

A fork/fresh agent drafts this. Copy `templates/plan.md` — fill the Naming & File Contract first,
then two maps: **Screen → Code** and **Component → Code**.

Full-stack feature: also copy `templates/contracts.md`, `data-model.md`, `research.md` only if
actually needed.

→ `specs/[###]/plan.md` (+ contracts.md, data-model.md, research.md)

### Step 4 — Tasks, sized as small PRs

Copy `templates/tasks.md`. One `SCREEN-XX`, `COMP-nnn`, or `SCREEN-XX-Fnn`, one target file, one PR
— never batched. Each task detailed with a four-dimension rubric: **Classify**, **Estimate**,
**Decompose**, **Assign**.

**Estimates are agent time, not human hours (hard rule R1).** Each task states `Agent min:` (whole minutes an agent needs) and `Human ref hours:` (what a human would need, for reference only). `tasks.md` carries a `## Waves` table `| Wave | Tasks | Agent time (min) | Human ref (h) |`: waves run sequentially, tasks inside a wave in parallel, so a wave's agent time is the **maximum** `Agent min` of its tasks and the line `Total agent time (critical path): N min` is the **sum** of the wave times. A bare `Estimated hours:` is not accepted — it is how human effort ends up quoted as if it were agent time.

> **Approval gate.** Present the task list as a dry-run and wait for approval before writing any
> code.

**Approval is the user's, and it is tamper-evident (hard rule R6).** After presenting the dry-run, ask the user with AskUserQuestion (the question must mention approving the tasks AND offer an option labelled exactly "Approve"), wait for the answer, then run `aidd rules approve specs/[###-feature]` — it writes `Approved: <date> hash:<hash>` into `tasks.md` and refuses unless the user's answer "Approve" to an AskUserQuestion about approving the tasks was recorded in this session, newer than `tasks.md`, and `tasks.md` is R1-valid (a question alone, another option such as "Yes", a "No", or another session's answer does not count); it also records the `approved` event the code gate requires. Any later edit to `tasks.md` changes the hash and voids the approval; re-present and re-approve. On Claude Code, writes to code files (everything except docs/images/lockfiles and `specs/`, `.git/`, `node_modules/`, …) are blocked while ANY open spec's approval is missing, void or unrecorded, or its `tasks.md` is missing.

→ `specs/[###]/tasks.md`

### Step 5 — Build — one PR at a time, gated (Builder)

See the [Definition of Done](#definition-of-done--every-ui-pr) below — all four parts, every PR.

### Step 6 — Converge — one specialized Auditor per domain touched (Auditors)

Not one generic "review everything" pass. Dispatch a fresh agent per domain: **UI/Mockup**,
**Backend/API**, **Database**, **Performance & Best Practices**. Copy `templates/qa-audit.md` on
the first pass; every later pass appends.

**One independent auditor per required domain (hard rule R7).** Required domains: `performance` always; `ui` if the tasks cite `SCREEN-`/`CTL-`/`COMP-`; `backend` if they cite `API-`; `database` if `data-model.md` exists or the tasks mention stored procedures, migrations, `.sql` or a schema. Each is a separate subagent dispatched **after the last code edit** whose description or first 400 chars of prompt name its domain (ui/mockup/screen, backend/api/contract, database/sql/schema, performance/best practice — word-boundary match, and one subagent counts for ONE domain only). On Claude Code, writing `qa-audit.md` is blocked until every required domain has one, and the Stop hook refuses to end a session that built code without them (R8). When all of it is done, `aidd rules close <spec-id>` records `spec_closed(completed)` (refused while an R6/R7 gap remains or without the user's recorded "Yes, close" answer); `aidd rules abandon <spec-id>` drops a spec on the user's recorded "Abandon".

→ `specs/[###]/qa-audit.md` updated

### Step 7 — Comprehensive Documentation (handoff) (Documenter)

Copy `templates/comprehensive-documentation.md`. Reassemble, never re-explain.

→ `specs/[###]/comprehensive-documentation.md`

## Definition of Done — every UI PR

All four, together. Not "looks right."

1. **Code** — implements exactly the codes the task cites, in exactly the target file, one class
   per file, following the Naming & File Contract, SOLID, and Antifragile/Design-for-Failure.
2. **Mapping row** — one line per code touched: ✅ IMPLEMENTED / ⚠️ PARTIAL / ❌ MISSING / 🔄
   DIFFERENT — evidence is a file/class/resource id, never a sentence.
3. **PR/Spec ref written back** — as soon as the PR exists, write it into the `PR/Spec ref` column
   of every code it touches. Append on amendment — never overwrite an earlier PR's ref.
4. **Screenshot diff** — run/build, screenshot the changed screen, compare against the mockup — per
   PR, not batched at the end.

## Convergence log

Each close-out pass appends a line; nothing is overwritten:

```
Rev 3 (2026-09-29) — 100.0% (312/312) — Δ vs Rev 2: +4 (login gradient, catalog stepper, toast component)
Rev 2 (2026-09-20) — 98.7% (308/312) — Δ vs Rev 1: +4
Rev 1 (2026-09-19) — 97.4% (304/312)
```

## File structure

```
specs/
├── index.toon            auto-built spec graph
└── [###-feature-name]/
    ├── mockup-audit.md
    ├── visual-flow.toon
    ├── contracts.md      full-stack only
    ├── data-model.md     if data changes
    ├── research.md       optional
    ├── spec.md
    ├── plan.md
    ├── tasks.md
    ├── qa-audit.md
    └── comprehensive-documentation.md

design-system/             project-level, not per-feature
├── MASTER.md
└── pages/
    └── <page>.md

charter.md            project-root — see "Project charter" below

.aidd/memory/              AIDD Memory — see "Memory" above
├── project.toon          scope = project
├── [###-feature-name].toon   scope = a spec id
└── archive/<YYYY>-Q<q>.toon  compacted entries (searched with --archive)
```

If the project already has its own spec-management convention, these files sit inside it as the
UI-specific layer — never force a folder structure the project doesn't use.

## Project charter

One file, project-root, not per-feature. Copy `templates/charter.md` once per project — it's
what every spec inherits without restating it: locked stack decisions, and project-specific rules
a generic AIDD default wouldn't cover.

The difference from a plain principles document: the template splits rules into **prose**
(judgment calls, not mechanically checkable) and a **Checkable rules table**
(`Rule | Type (forbidden/required) | Pattern | Applies to (glob)`) that `scripts/check_charter.py`
runs for real — `forbidden` fails if the pattern appears anywhere under the glob, `required` fails
if it appears nowhere. A rule an agent can only promise to follow is worth less than one a script
actually checks.

```bash
python scripts/check_charter.py [project-root]
```

Run this alongside `check_spec.py` before Step 6 signs off — the charter covers project-wide
invariants, `check_spec.py` covers one spec's own internal consistency.

## Issue tracker integration — GitHub, Azure DevOps, Bitbucket

Once Step 4's task list is approved, `scripts/tasks_to_issues.py` turns each task row into a real
tracker issue, carrying over the row's codes/target file/scope note plus its
Classify/Estimate/Decompose/Assign detail block as the issue body. Defaults to a dry run that only
prints what it would create; a `.aidd-issues.json` file next to `tasks.md` tracks what's already
synced, so re-running after adding new tasks never duplicates issues for ones already created.

`--provider {github,azure_devops,bitbucket}` (default `github`) picks the tracker; each is a small
stdlib-only module auto-discovered from `skill/extensions/<id>/manifest.json` (see
`docs/EXTENDING.md`), implementing the same provider contract.

Beyond one-shot creation, `scripts/sync_issues.py` (`aidd tracker sync`) diffs (or writes, with
`--apply`) `tasks.md`'s Status column against live tracker status, and
`scripts/link_pr_to_task.py` (`aidd tracker link-pr`) attaches an opened PR's URL back to its
task's tracker issue and `tasks.md` row.

```bash
python scripts/tasks_to_issues.py specs/[###-feature]/tasks.md --apply                       # github
python scripts/tasks_to_issues.py specs/[###-feature]/tasks.md --provider azure_devops \
  --org https://dev.azure.com/myorg --project MyProject --apply
python scripts/tasks_to_issues.py specs/[###-feature]/tasks.md --provider bitbucket \
  --workspace myworkspace --repo-slug myrepo --apply
```

## CLI

Everything above is also reachable without any AI agent, from a terminal or CI job:

```bash
pip install -e .   # from a clone of this repo
aidd search "login"
aidd check specs/001-login/
aidd check-charter .
aidd status                                  # hard-rules ledger of all open specs + WHY blocked (--json; exit 0 always)
aidd rules check specs/001-login/            # PASS|FAIL Rn message -> fix; exit 1 on a violation
aidd rules approve specs/001-login/          # writes the tasks.md Approved: line; needs the user's recorded "Approve" answer + R1-valid tasks
aidd rules close 001-login                   # records spec_closed(completed): needs approval + qa-audit.md + auditors + the user's "Yes, close" answer
aidd rules abandon 001-login --reason "dropped" # records spec_closed(abandoned): needs the user's recorded "Abandon"
aidd tasks-to-issues specs/001-login/tasks.md --apply
aidd mem add --type decision --title "Flows use TOON not JSON" --codes US-001 --scope 001-login
aidd mem search login                       # one line per hit, never the why
aidd mem show m-3fa91c02                    # full row
aidd mem compact --before 2026-07-01        # dry run; add --apply to move to archive/
aidd mem import-claude-mem <claude-mem.db> --project myproj --dry-run
```

`aidd` is a thin dispatcher over the same scripts an AI agent's hooks call — one implementation,
two ways to run it.

## When to reach for it

- **Default: any change to this codebase, of any size, UI or not.** A backend-only fix, a new
  endpoint, a schema migration, or a one-line config change goes through AIDD too, via the fast
  lane if it's genuinely small.
- A feature has a visual mockup (HTML, Figma, Stitch, screenshot, wireframe) that code must match.
- UI work needs breaking into small, individually-verifiable PRs instead of one big pass.
- A prior UI deliverable took several corrective rounds and the next one shouldn't.
- Reviewing a screen should mean "look up the code, open the file" — not a search.
- Explaining a flow in words takes many messages and still comes out wrong — correct a diagram
  instead.
- A feature needs a formal handoff document, not just files in a repo.
- The feature is full-stack — UI controls and the API contracts they depend on should be
  traceable to each other.
- The same card, header, or form section shows up on multiple screens and should be built once,
  not rebuilt per screen.
- The request arrives in English, Spanish, or Portuguese — coverage isn't limited to one language.
