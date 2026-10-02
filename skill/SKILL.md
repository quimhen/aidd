---
name: aidd
description: "AIDD — the default analysis-and-planning pipeline for ANY change in this codebase, of any size, UI or not (backend-only, database/schema, API contract, infra, bugfix, refactor). The visual sub-pipeline (mockup audit, design-system fidelity) only activates when a change has a visual surface with a mockup (HTML prototype, Figma, Stitch, image, PDF wireframe); a backend/API/DB-only change skips straight to align/plan/tasks/build/converge. Decomposes screens into reusable components (COMP-nnn, built once and shared across screens) as well as per-screen codes. Ships real fillable templates for every artifact — screens/components/controls, API contracts, data model, a Master+page-override design system, a project-wide component index — plus a Mermaid flowchart per use case, a small-PR task breakdown with a classify/estimate/decompose/assign rubric, a specialized-agent split with an independent audit agent, a stdlib gap-checking script (check_spec.py) that runs before manual audit, wave-based parallel dispatch, a fast lane for small contained changes, a grep-first reading discipline with fixed `aidd:CODE` source markers, and a project-root STATE.md continuity file. Use for EVERY requirement, feature, bugfix, or change request before writing or editing source — not only when a mockup is mentioned. Use when the user says 'analiza este mockup', 'quiero implementar esta UI', 'necesito planificar una pantalla', 'especificación de UI', 'necesito un diagrama de flujo', 'necesito auditar la implementación', 'contrato de API', 'componentes reutilizables', 'stored procedure', 'swagger', 'arreglar/corregir un bug', 'nuevo endpoint', 'migración de base de datos', 'refactor'."
---

# AIDD — AI-Driven Development

Self-contained: everything needed to run this is in this file. It doesn't require any other skill to be installed, and it doesn't call out to one.

## Environment adaptation — one file, every host

This file is host-agnostic on purpose: the same copy adapts to whichever tool loaded it. Read this block once and apply it to every instruction below.

**0. If your load came back truncated** — you see something like `showing lines 1-318 of 732`, or the body stops mid-sentence — your host caps tool output (about 50 KB, this file is ~110 KB) and **most of this skill never reached you**: everything past that cut includes the whole Pipeline (Steps -2 through 7), Engineering standards, Memory and File structure. Read the remainder of `<AIDD_HOME>/SKILL.md` from the truncation point on, before planning or implementing anything. Do not work from the visible fragment — a half-loaded skill is worse than none, because the missing half is the part that says what to do.

**1. Detect your host from the tools you actually have**, not from the folder you were installed in:

| Your toolset says | You are in | Dispatch a subagent with | Ask the user with |
|---|---|---|---|
| an `AskUserQuestion` tool | Claude Code | `Task` / `Agent` tool | `AskUserQuestion` |
| a `question` tool and a `subagent` tool | OpenCode | `subagent` tool | `question` tool |
| neither | any other agent (Codex, Gemini CLI, Cursor, …) | whatever separate-context mechanism the host offers | plain text in your reply |

From here on, **`AskUserQuestion` means "the host's ask-the-user tool"** and **`Agent tool` / `Task tool` / `Workflow tool` mean "dispatch a separate subagent"** — substitute your row. Step 6's independence rule is about *context isolation*, not about a product feature: a different agent audits what you built; if the host has no subagents, do it as an explicitly separate pass over the diff with the implementer's reasoning withheld.

**2. Resolve `<AIDD_HOME>` before running any command below.** It is the folder containing this `SKILL.md`:

- Claude Code → `~/.claude/skills/aidd`
- OpenCode → the `Base directory for this skill:` line, **if one was printed** — on a skill this size the host truncates the body before it ever reaches the footer, so assume it is missing: check `.opencode/skills/aidd`, then `~/.config/opencode/skills/aidd`, then `~/.claude/skills/aidd` (OpenCode's compatibility source), and keep the first that exists **and** whose `SKILL.md` contains `## Environment adaptation`.
- any other host → wherever you copied this folder

Never paste the literal token `<AIDD_HOME>` into a shell — substitute the resolved path. If no copy can be found, stop and ask where the skill was installed instead of guessing a path.

**3. Enforcement degrades by host; compensate with the CLI, not with memory:**

| Host | What checks the hard rules |
|---|---|
| Claude Code | The ten hooks in "Installation — Claude Code": real `exit 2` gates plus an append-only evidence log. |
| OpenCode | The `aidd.js` plugin nudges once before the first shell command; **nothing blocks you**. Read every "a hook blocks X" below as: run `aidd rules check <spec-dir>` (prints `PASS\|FAIL Rn … → fix`, exits 1 on a violation) **before** the gated write and do not proceed on FAIL, then `aidd status` before ending the session. |
| any other host | The same CLI, run by hand: `aidd status`, `aidd rules check / approve / close / abandon`. |

The rules (R1–R9) are identical on every host — only who checks them changes. Rows and sections marked **Claude Code only** (hooks, evidence log, `SessionStart` / `Stop`) describe machinery that host has; they are not a requirement elsewhere, and their absence does not waive the rule behind them.

## Installation — by host

### Claude Code — full enforcement (recommended, one-time per machine)

AIDD ships with hooks that make it hard to skip. After copying this skill folder to `<AIDD_HOME>` (`~/.claude/skills/aidd`) on any device, run once:

```bash
python <AIDD_HOME>/scripts/install_hooks.py
```

This merges ten hook entries into `~/.claude/settings.json` (idempotent — safe to re-run, never duplicates or touches unrelated hooks already configured there):

| Event | Matcher | Script | Effect |
|---|---|---|---|
| `UserPromptSubmit` | — | `hooks/prompt_trigger.py` | Injects an instruction to invoke AIDD before responding if the user's message mentions requerimiento/levantamiento/plan/planificación/nuevo proyecto/funcionalidad. Also records the prompt in the evidence log. |
| `PreToolUse` | `Write\|Edit\|MultiEdit\|NotebookEdit\|PowerShell\|Bash` | `hooks/rule_gate.py` | Blocks (exit 2): writes to evidence logs (R9); source code before AIDD ran this session; `qa-audit.md` without an independent subagent (R7); `plan.md`/`tasks.md` out of chain order (R5); structurally invalid `spec.md`/`tasks.md` (R1–R3); the `Approved:` line unless the user's recorded answer is "Approve" (R6); writes to code files while ANY open spec lacks a valid approval (R6); Bash/PowerShell commands that write into protected paths (R9). Timeout 15 s. `AIDD_RULES=off\|0\|false\|no\|warn` is honoured. |
| `PostToolUse` | `Skill` | `hooks/mark_invoked.py` | Marks AIDD as invoked for this session once the Skill tool actually runs it. |
| `SessionStart` | — | `hooks/session_start.py` | Resets that marker for each new session; records `session_start` in the evidence log. |
| `PostToolUse` | `Write\|Edit\|MultiEdit\|NotebookEdit\|PowerShell` | `hooks/mark_code_edit.py` | Appends `code_edit` / `spec_edit` events; records `approved{spec,hash}` when `tasks.md` is written with a hash-valid `Approved:` line. Timeout 10 s. |
| `PostToolUse` | `Task\|Agent` | `hooks/mark_agent_dispatch.py` | Timestamps the most recent independent subagent dispatch; appends a `subagent` event. |
| `PostToolUse` | `Bash\|PowerShell` | `hooks/mark_graph_rebuild.py` | Records a `find_spec` event only when the command really RUNS `find_spec.py`. Timeout 10 s. |
| `PostToolUse` | `AskUserQuestion` | `hooks/mark_user_question.py` | Appends a `question` event and an `answer` event with the pairs anchored on the known questions. Timeout 10 s. |
| `Stop` | — | `hooks/stop_gate.py` | Rule R8: refuses (exit 2) to end the session while any OPEN spec has a valid approval, code edits after its `approved` event, and `qa-audit.md` missing. Blocks at most 3 times per (spec, approval hash), then allows. Timeout 15 s. |
| `SessionStart` | `startup\|resume\|clear\|compact` | `hooks/memory_context.py` | Prints a short AIDD Memory digest. Silent when there is no `.aidd/memory/`. Claude Code only. |
| `PreToolUse` | `Read\|Edit\|Write` | `hooks/memory_file_context.py` | **Opt-in** (`install_hooks.py --with-memory-file-hook`). Injects up to 3 memory entries that mention a file the first time it is touched. Claude Code only. |

**Scope: global, every Claude Code session on this machine.** Loosen it by editing `hooks/require_aidd.py`'s `is_code_file` check or `hooks/prompt_trigger.py`'s keyword list.

**Uninstall:** remove the hook entries from `~/.claude/settings.json` by hand.

### OpenCode — nothing to install; discovery is automatic

OpenCode finds this skill by itself and needs no hook registration:

- **Compatibility source:** OpenCode deliberately reads `~/.claude/skills`, so the Claude Code install above is picked up in OpenCode with zero configuration — same folder, same scripts, same paths.
- **Native source (optional):** copy this folder to `~/.config/opencode/skills/aidd/` (global; higher precedence than the compatibility source) or `.opencode/skills/aidd/` (project). Whichever copy ends up loaded becomes `<AIDD_HOME>`.
- **Enforcement layer:** copy `adapters/opencode/plugins/aidd.js` to `.opencode/plugins/aidd.js` and add `".opencode/plugins/aidd.js"` to the `plugin` array of `.opencode/opencode.json`. It injects one reminder before the session's first shell command, and only when the project has `.aidd/AIDD.md`. It **cannot** hard-block a Write/Edit call — OpenCode's plugin API exposes no per-tool write gate. Apply the compensation rule from "Environment adaptation": run `aidd rules check <spec-dir>` before every gated write and `aidd status` before ending the session.

### Codex, Gemini CLI, Cursor, Windsurf, Cline, Copilot — pointer install

No skill folder and no hooks: `pip install aidd-cli && aidd init <project>` drops the portable `.aidd/` bundle (methodology + `find_spec.py` / `check_spec.py`), and `aidd adapters generate <target> <project>` renders that host's native command files from `commands/aidd-*.md`. The always-read layer is `AGENTS.md` (plus `GEMINI.md` for Gemini). See `adapters/README.md`.

## Hard rules — enforced by hooks on Claude Code, self-checked elsewhere

The pipeline's rules used to live only in prose, and a real run skipped most of them. Each is now a rule a hook enforces (contract: `specs/002-aidd-hard-rules/spec.md`):

| Rule | What it blocks | The exact fix |
|---|---|---|
| **R1** estimates are agent time | `tasks.md` with no `## Waves` table, a task lacking `Agent min:` / `Human ref hours:`, a wave time that is not the max of its tasks, a total that is not the sum of the waves, or a `Status` / `Tracker ref` / `PR/Spec ref` cell longer than 60 chars or 8 words | Add `Agent min:` + `Human ref hours:` per task, the Waves table, and `Total agent time (critical path): N min` |
| **R2** route is declared | `spec.md` with no `## Pipeline route` table, a duplicate step row, or a step `waived` without a Reason and `user — "<quote ≥ 3 words>"` | Add the route table (one row each for `-1, 0, 1, 1.5, 2, 3, 4`); ask the user before waiving and quote their words |
| **R3** alignment provenance | The Minimum Requirements Checklist missing any question of the shipped template, or with a blank / `-` Answer; an answer with no valid `Source`; a `repo — <path>` that does not exist, has no `:LINE`, and no `"quote ≥ 3 words found in that file"`; a Proposed marker in ANY column | `user — "<quote>"`, `repo — <existing path>:<LINE>` (or `repo — <path> "<quote from the file>"`), or `[Proposed — unconfirmed]` |
| **R4** visual debt | Waived Steps 0/1/1.5 with `SCREEN-nn` codes and no `## Visual debt` row; a `Blocks spec` that is not an existing spec id; a `resolved` row without a real Mockup source; while a row is `open`, writes under the blocked spec | List the codes in `## Visual debt`, ask the user for the mockup source, run Steps 0/1/1.5, mark the row `resolved` |
| **R5** chain order | `plan.md` without a `find_spec` run this session, an independent subagent after the last `spec.md` edit, no blank checklist Answer, zero `[Proposed` rows, every `user — "quote"` verified, and no open debt; `tasks.md` without `plan.md`, a subagent after the last `plan.md` edit, and a `find_spec` run | Run `find_spec.py`; dispatch the Mapper/Alignment agent; ask the user every open question; dispatch an auditor over `plan.md`; then retry |
| **R6** tasks approval | The `Approved:` line unless the user's recorded answer is "Approve" of an AskUserQuestion about approving the tasks (with the `[tasks:<hash8>]` tag) and `tasks.md` is R1-valid. **Every write to a code file** is blocked while ANY open spec has no valid approval, no hook-recorded `approved{spec,hash}` event, or no `tasks.md` at all | Present the tasks, ask with AskUserQuestion (option "Approve"), then `aidd rules approve specs/<id>` |
| **R7** closing audit per domain | `qa-audit.md` while any required domain (`performance` always, `ui`, `backend`, `database` by what the tasks touch) lacks its OWN subagent after the last code edit | Dispatch one auditor per missing domain, name the domain in its prompt, rewrite `qa-audit.md` |
| **R8** stop gate | Ending the session while ANY open spec has a valid approval, code edits after its `approved` event, and `qa-audit.md` missing or a required domain uncovered | Run the missing auditors and write `qa-audit.md`, then `aidd rules close <id>` |
| **R9** protected paths | The agent writing anything under `.aidd/` EXCEPT `.aidd/memory/**`, or the per-session evidence directory, via Write/Edit; and Bash/PowerShell commands that write into those paths, that import `aidd_evidence\|aidd_rules\|aidd_status`, that contain `AIDD_TESTING`/`AIDD_EVIDENCE_DIR`/`AIDD_SESSION_ID`, or that assign `AIDD_RULES=` | None — those files are written by hooks only |

Every block message names the next action (which artifact, which command, which question to ask the user).

**Evidence, not trust.** Hooks append what they observed (the agent is not supposed to write it). SESSION kinds go to a per-session log under `<tempdir>/aidd-hooks/evidence/<session-id>.toon`; PROJECT kinds go to `<project>/.aidd/evidence/events.toon` (git-ignored, append-only). Rules fail **closed on missing evidence** and **open on a hook crash**.

**Answers are anchored, not guessed.** Approval, close and abandon are accepted only from a recorded answer whose chosen label is one of the options the question OFFERED — **the agent must offer exactly "Approve" (tasks), "Yes, close" (close) or "Abandon" (abandon)**. The approval question must contain the tag `[tasks:<hash8>]` — the first 8 hex chars of the current `approval_hash` of `tasks.md`.

**Open specs, not "the active spec".** A spec is *open* from the first recorded edit of its `plan.md` or `tasks.md` until a `spec_closed` event. R6/R7/R8 apply to EVERY open spec in every project root above the file being written. A spec stops being open only via `aidd rules close <id>` or `aidd rules abandon <id>`.

**Commands (also usable from a terminal or CI):** `aidd status [spec_dir] [--json]` lists ALL open specs with their approval state and WHY blocked lines. `aidd rules check <spec_dir>` prints `PASS\|FAIL Rn message → fix` and exits 1 on any violation. `aidd rules approve <spec_dir>` writes the `Approved:` line only with the user's recorded answer "Approve". `aidd rules close <id>` needs an open spec, a valid recorded approval, `qa-audit.md`, every required domain audited and the recorded answer "Yes, close". `aidd rules abandon <id>` needs the recorded answer "Abandon". `check_spec.py` also reports the static rules (R1–R4, R6) as gaps.

**Escape hatch (owner only):** Claude Code — set `AIDD_RULES` in the `env` block of `~/.claude/settings.json`: `off`, `0`, `false` or `no` disables the gates; `warn` prints messages to stderr and never blocks. Any other host — export the same variable in the session environment: `aidd rules check`, `aidd status` and `check_spec.py` all honour it.

**Limitations.** (1) Bash and PowerShell can still edit code — the code gate covers Write/Edit/MultiEdit/NotebookEdit; the shell tools are only checked for writes into protected paths. (2) Through Bash/PowerShell an agent can try to forge evidence; the guard is lexical, not a sandbox. (3) The gates verify that a subagent ran and a question was answered, not that they were any good. (4) The user's click cannot be cryptographically proven. (5) Hooks fail open on a crash or timeout. (6) R8 relaxes after 3 blocks per approval hash. (7) Session ids and resume behaviour are not verified. (8) A user quote is checked against what was recorded, not for whether it means what the agent claims. (9) A spec stopped at `spec.md` is not open. (10) Code can be planted under exempt locations (`.git/hooks`, `node_modules/`, `specs/`). (11) `repo —` sources only prove that the file exists, not that it is relevant. (12) The shell guard has false positives (`cp … specs/…`): use the Write tool for those. (13) With several concurrent windows the CLI can infer the wrong session; it then fails closed. **In short: the rules stop accidental and self-justified skipping; they do not stop a determined agent.**

## Problem this solves

UI work tends to take several corrective passes instead of landing right the first time. The root cause: the visual truth (mockup / design system) gets pinned down loosely or late, relative to when code gets written. The fix: front-load 100% of the visual truth into stable codes before any implementation task exists, size every task to one small PR pinned to one code + one file, and gate each PR's "done" on three things together (code, mapping row, screenshot diff).

## The code system

Assign these the moment you first read the mockup, and never rename them:

| Code | Grain | Example |
|---|---|---|
| `SCREEN-XX` | One screen / view / modal | `SCREEN-08` = "Client detail sheet" |
| `SCREEN-XX-Fnn` | One discrete, testable behavior of that screen | `SCREEN-08-F03` = "Blocks save when required field is empty" |
| `CTL-nnn` | One control (button/field/link), globally numbered | `CTL-057` = the "Guardar" button |
| `COMP-nnn` | One reusable component — appears on 2+ screens | `COMP-003` = "ClientCard" (used on SCREEN-02 and SCREEN-08) |
| `US-nnn` | The use case the screen serves | `US-004` = "Vendedor registra un pedido nuevo" |
| `API-nnn` | One backend endpoint/contract, globally numbered | `API-012` = `POST /orders` |

**`COMP-nnn` is what's missing if you only track whole screens** — the same card appearing on several screens is one component, built once, referenced by every `SCREEN-XX` that uses it. A `SCREEN-XX` row lists the `COMP-nnn` it's composed of; a `COMP-nnn` row lists which `CTL-nnn` live inside it and which screens use it.

**Full-stack features:** a `CTL-nnn` that triggers a network call cites the `API-nnn` it depends on in the control inventory (Step 1) — that's the traceability link between "this button" and "this contract."

Every later artifact (spec, task, code comment, checklist) cites the code — never a redescription of the UI. If this project's work is already tracked elsewhere under its own codes, use those instead of minting new ones — never run two numbering systems for the same screen.

## Templates

Every artifact below has a real starting skeleton in this skill's own `templates/` folder — don't reconstruct a table from memory each time:

```
<AIDD_HOME>/templates/
├── STATE.md                  # project-root continuity file — copy once per project, read first always
├── mockup-audit.md
├── visual-flow.toon
├── spec.md                   # Step 2 — Minimum Requirements Checklist + functional requirements
├── contracts.md              # API-nnn contracts — only for full-stack features
├── data-model.md             # entities/relationships — only when the feature adds/changes data
├── research.md               # technology decisions worth recording — optional, keep short
├── plan.md
├── tasks.md
├── qa-audit.md
├── comprehensive-documentation.md
├── charter.md            # project-root, not per-feature — see "Project charter" below
└── design-system/
    ├── MASTER.md              # global visual source of truth (Step 0, no-mockup case)
    ├── page-override.md       # per-page/per-screen exception to Master
    └── components-index.md   # project-wide COMP-nnn registry — check before minting a new one

<AIDD_HOME>/scripts/
├── check_spec.py              # mechanical gap-checker — run before the Step 6 Auditor reads by hand
├── check_charter.py      # runs charter.md's checkable rules
├── flowmap.py                 # Step 1.5 — visual-flow.toon → interactive actors×processes HTML + generated pseudocode
├── research_project.py        # [optional, one-time] proposes candidate spec areas on a brownfield project with no specs/ yet
├── aidd_memory.py             # AIDD Memory — code-anchored WHY in .aidd/memory/
├── aidd_memory_import.py      # [optional, one-off] read-only importer from a claude-mem SQLite file
├── tasks_to_issues.py         # turns an approved tasks.md into real tracker issues (dry-run by default)
└── providers/                 # github_provider.py / azure_devops_provider.py / bitbucket_provider.py
```

## Project charter

**One file, project-root, not per-feature.** Copy `templates/charter.md` once per project — it's what every spec inherits without restating it: locked stack decisions, and project-specific rules. The template splits rules into **prose** (judgment calls) and a **Checkable rules table** (`Rule | Type (forbidden/required) | Pattern | Applies to (glob)`) that `scripts/check_charter.py` runs for real — `forbidden` fails if the pattern appears anywhere under the glob, `required` fails if it appears nowhere.

```bash
python <AIDD_HOME>/scripts/check_charter.py [project-root]
```

Run this alongside `check_spec.py` before Step 6 signs off — the charter covers project-wide invariants, `check_spec.py` covers one spec's own internal consistency.

### Research mode — bootstrapping specs when none exist yet

**Run this once, at the same time as copying `templates/charter.md`, on a brownfield project that has real code but no `specs/` folder yet.** Step -1's `find_spec.py` can only search specs that already exist; a project with none has nothing for the spec graph to index.

```bash
python <AIDD_HOME>/scripts/research_project.py [project-root]
```

It's a mechanical, stdlib-only directory scan — no LLM, no file content read — that looks for route/page/screen/controller-like directories and prints a numbered list of candidate `specs/[###-slug]/` areas, largest first. **It never writes a spec or invents content.** Once the list is in hand: drop the noise, then run Step 0 through Step 2 per area kept.

## Spec graph — and why it stays cheap

`find_spec.py`'s index (`specs/index.toon`) **is** AIDD's knowledge graph. It's derived from specs the project already maintains, not from re-reading source code: `find_spec.py` parses `mockup-audit.md`'s own tables into a `US-nnn → SCREEN-XX → COMP-nnn → CTL-nnn → API-nnn` DAG, using plain regex/markdown-table parsing — stdlib only, zero LLM calls, zero tokens. Rebuilding it costs a `stat()` per spec file and, only for files that actually changed, a re-parse of that one file.

**This is a trade, not a strict improvement**: AIDD's graph can only describe what a spec already documents — it has nothing to say about code with no spec behind it. That's exactly what Research mode exists to bootstrap on a brownfield project.

## Graph coherence — multiagent verification

**Cheap and mechanical is not the same as correct.** `find_spec.py` parses `mockup-audit.md`'s tables with regex — it can misread a malformed row, silently drop an edge when a code gets renamed, or carry over a relationship a manual edit meant to remove. A mechanical parser can never catch its own semantic mistakes.

**When it runs, and who runs it:** every time `find_spec.py` reports `Graph index: rebuilt` with a non-empty changed set, dispatch a **Graph Coherence Auditor** — a fork or fresh agent, scoped to just the spec(s) `find_spec.py` named as changed — before Step 3 (`plan.md`) or Step 4 (`tasks.md`) build on the new relationships. Its checklist:
- Every `SCREEN-XX` cites a `COMP-nnn`/`CTL-nnn` that actually exists in that spec's own inventories.
- Every `CTL-nnn` that calls an `API-nnn` has that `API-nnn` actually defined in `contracts.md` (or explicitly flagged `[Not Verified]`).
- No two specs silently claim the same `COMP-nnn`/`CTL-nnn` number for different things.
- The tree `find_spec.py --tree <spec-id>` prints actually matches the use case the spec's `spec.md` describes.

**This is enforced by hooks, not left as a step someone might skip** — writing `plan.md` or `tasks.md` is blocked (exit 2) if the graph was rebuilt this session and no independent subagent has run since.

## Issue tracker integration — GitHub, Azure DevOps, Bitbucket

Once Step 4's task list is approved, `scripts/tasks_to_issues.py` turns each task row into a real tracker issue. Defaults to a dry run; a `.aidd-issues.json` file next to `tasks.md` tracks what's already synced, so re-running never duplicates issues.

**Three trackers, one script, one flag** — `--provider {github,azure_devops,bitbucket}` (default `github`). Each provider is a small stdlib-only module under `scripts/providers/` implementing the same two-function contract (`available()`, `create_issue()`).

```bash
# GitHub (default) — gh CLI must be installed and authenticated (gh auth login)
python <AIDD_HOME>/scripts/tasks_to_issues.py specs/[###-feature]/tasks.md --apply

# Azure DevOps — az CLI + azure-devops extension, az login done ahead of time
python <AIDD_HOME>/scripts/tasks_to_issues.py specs/[###-feature]/tasks.md \
  --provider azure_devops --org https://dev.azure.com/myorg --project MyProject --apply

# Bitbucket Cloud — REST API v2.0 directly (urllib, no extra dependency)
python <AIDD_HOME>/scripts/tasks_to_issues.py specs/[###-feature]/tasks.md \
  --provider bitbucket --workspace myworkspace --repo-slug myrepo --apply
```

`--org`/`--project` (Azure DevOps) and `--workspace`/`--repo-slug` (Bitbucket) also read from `AZURE_DEVOPS_ORG`/`AZURE_DEVOPS_PROJECT`/`BITBUCKET_WORKSPACE`/`BITBUCKET_REPO_SLUG` env vars.

## Speed: what actually cuts time-to-correct-result

### Run the checker before the Auditor reads anything by hand
```bash
python <AIDD_HOME>/scripts/check_spec.py specs/[###-feature]/
```
It greps the spec folder for mechanical gaps — dangling codes, unresolved `[Not Verified]`, empty `PR/Spec ref`, orphaned `COMP-nnn`, missing stored-procedure/exception pairs, blank `qa-audit.md` statuses — in milliseconds, and exits non-zero if it finds any. **Run this first, every time, before Step 6's Auditor spends judgment re-reading the whole spec.**

### Check the project's Component Index before minting a new COMP-nnn
Keep one project-level `design-system/components-index.md` (not per-feature) listing every `COMP-nnn` ever created, its file, and which specs/screens use it. Check it in Step 1 before creating a new component.

### Wave-dispatch approved tasks instead of running them one at a time
Group the approved tasks into waves — same-wave tasks touch disjoint files and have no ordering requirement between them — and dispatch every task in a wave as parallel subagent calls **in one message**, not one call at a time.

### Take the fast lane for a small, contained change
Fast lane conditions (all must hold): touches exactly one existing `SCREEN-XX`, no new `US-nnn`, no new `COMP-nnn`, no navigation change. When they hold: skip `visual-flow.toon` and `comprehensive-documentation.md` entirely, amend `mockup-audit.md` and `qa-audit.md` directly, and run it as a single task with the same four-part Definition of Done. The moment any condition stops holding mid-work, stop and go back to the full pipeline from Step 1.

### Grep first — never read a whole file to check one code
Every code (`SCREEN-XX`, `CTL-nnn`, `COMP-nnn`, `API-nnn`, `US-nnn`) is a search key by design. To check whether a code exists: `grep -n "CTL-057" specs/[###]/mockup-audit.md`, not a full read. To find where a screen is implemented: grep its `PR/Spec ref` cell or the code marker in source. To audit, use `scripts/check_spec.py`'s report as the first source of truth. The one legitimate exception is **Step 1's own audit pass** — it is exhaustive by design, once.

**Code markers — make source code itself greppable.** `aidd:CODE` inside whatever comment syntax the language uses (`// aidd:CTL-057`, `# aidd:SCREEN-08`, `<!-- aidd:COMP-003 -->`). One grep pattern then finds the mockup-audit row, the plan.md mapping, and the exact source line together.

### Keep a per-project STATE.md — don't re-investigate after losing context
One small, always-current file at the project root: `STATE.md`, copied from `templates/STATE.md`. Read it first, in full, before touching anything else. It holds: which spec is active and at which step, the last action taken, the next action to take, and pointers into the spec files that matter right now. Every step that changes what's true updates `STATE.md` with a short edit, not a rewrite.

At the start of each step, copy the matching template into the spec folder and fill it in — don't hand-write the table headers from scratch. `contracts.md`, `data-model.md`, and `research.md` are conditional — copy them only when the feature actually has a backend/data component.

## Specialized agents & workflow

Each step below has a natural agent boundary. **Step 6's Auditor must not be the same agent that did the implementing** — an agent that just wrote code is structurally bad at spotting its own gaps.

| Step | Role | Run as | Independence requirement |
|---|---|---|---|
| -1, 1 | **Mockup Auditor** | Read-only pass (fork or fresh agent for a large/unfamiliar mockup) | None — but must not skip ahead into Step 4/5 |
| 1.5 | **Diagrammer** | Same context as Step 1, or a fresh agent handed the finished mockup-audit.md | None |
| 2 | **Alignment Agent (drafting)** | A fork/fresh agent compiles the full alignment-question list — mechanical, no interaction needed | None |
| 2 | **Ask the user** | Main conversation, using the Alignment Agent's compiled list | — |
| 3 | **Mapper (drafting)** | A fork/fresh agent drafts `plan.md`: inspects the codebase, checks `components-index.md`, fills the maps as a proposal | None |
| 3 | **Approve the plan** | Main conversation presents the Mapper's draft for the user's confirmation | — |
| 4, 5 | **Builder(s)** | One agent per small-PR task; parallelize only when tasks touch disjoint files | None between implementers, but never the same agent as the Auditors |
| 6 | **Auditores de Cierre (QA)** — one per domain touched | Fresh agents/contexts that did NOT implement the PRs | **Mandatory.** Each re-derives its own `qa-audit.md` rows from the code |
| 7 | **Documentador** | Mechanical assembly pass, any agent | None |

This is a description of the discipline, not a requirement to use any specific tool — apply it with whatever mechanism is already in use as long as the Step 6 independence rule holds.

## Engineering standards — restate these in every agent's instructions

### SOLID (applies to any code touched, not only new files)
Single responsibility, open/closed, Liskov substitution, interface segregation, dependency inversion. If a change makes a class do two jobs, split it.

### Naming contract — declared once in `plan.md`, never assumed
Every new class/function/component gets its name from the Mapper's `plan.md` mapping. Never invent a name locally and hope it matches.

### Antifragile / Design for Failure — assume everything can fail
Every external call (network, disk, subprocess) can fail. Handle the failure explicitly — retry with backoff, circuit breaker, or graceful degradation. Never let an unhandled exception crash the user's workflow silently.

### Data access & frontend↔backend communication — fixed rules for full-stack work
- The frontend never constructs SQL or touches the database directly.
- All API calls go through the `API-nnn` contract defined in `contracts.md`.
- Errors from the backend are surfaced to the user in their language, not as raw stack traces.

### Database design, connections & indexing — fixed rules for anything that touches a database
- Use connection pooling; never open a connection per query.
- Every table has a primary key; every foreign key is indexed.
- Migrations are versioned and reversible.
- Stored procedures are verified against the engine's query plan before being called hot.

## Memory — the WHY, anchored to codes

Decisions, rejected options, bug root causes and constraints go into `.aidd/memory/` as curated, code-anchored entries, committed with the code. Search is progressive: `aidd mem search` returns one line per hit, `aidd mem show <id>` the full row.

**Capture points** — the agent runs `aidd mem add ...` (or `python <AIDD_HOME>/scripts/aidd_memory.py add ...`):
- A decision was made and the reason is non-obvious.
- A rejected option that might be proposed again.
- A bug root cause that isn't visible in the code.
- A constraint that shaped the design.

**Automatically, Claude Code only** — `memory_context.py` injects a short digest at session start. `memory_file_context.py` injects entries that mention a file the first time it is touched (opt-in). `aidd mem file <path>` is the on-demand equivalent. Both are silent when there is no `.aidd/memory/`.

## Pipeline

`spec.md` carries a `## Pipeline route` table `| Step | Status | Reason | Confirmation |` with one row each for `-1, 0, 1, 1.5, 2, 3, 4`; `Status` is `run|waived|done`, a `waived` step needs a Reason and `user — "<quote ≥ 3 words>"`. Visual debt (R4) is declared, never silently skipped.

### Step -2 — Project setup (one-time, before the first feature)
Copy `templates/charter.md` to the project root (see "Project charter" above). Run `python <AIDD_HOME>/scripts/check_charter.py [project-root]` alongside `check_spec.py` before Step 6 signs off.

### Step -1 — Intake: classify, then search before creating
```bash
python <AIDD_HOME>/scripts/find_spec.py <keywords or a SCREEN-XX/CTL-nnn/COMP-nnn/API-nnn code>
```
Exit 0 → **amendment** to the top-ranked existing spec under `specs/` — reopen it, never a new folder. Exit 1 → safe to create `specs/[###-feature]/`. `find_spec.py --tree <spec-id>` prints that spec's use-case → screen → component → control → API graph. State the classification before proceeding: `AIDD intake: NEW SPEC | AMENDMENT | AMENDMENT — Fast Lane — <reason>`.

### Step 0 — Visual source of truth (once per feature; skip if no visual surface)
Pin the mockup/design system before any task exists. If the feature has no visual surface, skip entirely.

### Step 1 — Mockup Audit (one pass, mechanical, no prose)
Assign codes the moment you read the mockup, never rename them. Fill `mockup-audit.md`: Screen/Component/Control inventories + `## Visual debt` table. Check the project-level `design-system/components-index.md` before minting a new `COMP-nnn`.

### Step 1.5 — Visual Process Flow (draw it, don't describe it)
```bash
python <AIDD_HOME>/scripts/flowmap.py specs/[###-feature]/visual-flow.toon --open
```
Interactive actors × processes flow with generated pseudocode. The user clicks through it and corrects the flow by node.

### Step 2 — Align (before planning, not during implementation)
Draft `spec.md` from `templates/spec.md`: Minimum Requirements Checklist + functional requirements. Every answered row carries a `Source`: `user — "<exact quote, 3+ words>"`, `repo — <path[:line]>`, or `[Proposed — unconfirmed]`. The agent never self-answers — an answer the agent chose itself is always `[Proposed — unconfirmed]`. Ask the user for every open question, then replace the Source with their own words.

### Step 3 — Plan: the Screen → Code map
Dispatch a Mapper agent (fork/fresh) to draft `plan.md`: inspect the codebase for existing naming conventions, check `components-index.md`, fill the Screen→Code / Component→Code maps as a proposal. Present the draft to the user for confirmation. Run `find_spec.py` first — a rebuilt graph needs a Graph Coherence Auditor before planning.

### Step 4 — Tasks, sized as small PRs
One code, one file, one PR. Each task has `Agent min:` + `Human ref hours:`, a `## Waves` table (`| Wave | Tasks | Agent time (min) | Human ref (h) |`), and `Total agent time (critical path): N min`. Present the dry-run, ask the user to approve (AskUserQuestion with `[tasks:<hash8>]` tag, option "Approve"), then `aidd rules approve specs/<id>`.

### Step 5 — Implement, one PR at a time, gated
Group approved tasks into waves (same-wave tasks touch disjoint files). Dispatch every task in a wave as parallel subagent calls in one message. Thread codes into the code: `aidd:CODE` in comments. Code edits are gated while any open spec lacks a valid approval.

### Step 6 — Converge
Run `python <AIDD_HOME>/scripts/check_spec.py specs/[###-feature]/` before the manual audit. Then dispatch one independent auditor per required domain (`performance` always; `ui`, `backend`, `database` by what the tasks touch) — fresh agents that did NOT implement the PRs. Each re-derives its own `qa-audit.md` rows from the code. The Auditor must not be the same agent that implemented.

### Step 7 — Comprehensive Documentation (handoff)
Copy `templates/comprehensive-documentation.md` and fill it in — mechanical assembly, no new judgment calls.

## File structure

```
<AIDD_HOME>/
├── SKILL.md              # this file
├── AIDD.md               # tool-agnostic methodology core (read for the full "why")
├── scripts/              # stdlib Python — see "Templates" above
├── templates/            # fillable skeletons for every artifact
├── hooks/                # Claude Code enforcement (see "Installation — Claude Code")
└── extensions/           # issue-tracker providers + agent adapters
```

## When to use this skill

Use for EVERY requirement, feature, bugfix, or change request in this codebase before writing or editing any source file — not only when a mockup is mentioned. Use when the user says 'analiza este mockup', 'quiero implementar esta UI', 'necesito planificar una pantalla', 'especificación de UI', 'necesito un diagrama de flujo', 'necesito auditar la implementación', 'contrato de API', 'componentes reutilizables', 'stored procedure', 'swagger', 'arreglar/corregir un bug', 'nuevo endpoint', 'migración de base de datos', 'refactor', or asks to speed up any review-and-handoff cycle, UI or backend.
