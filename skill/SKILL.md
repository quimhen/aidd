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

From here on, **`AskUserQuestion` means "the host's ask-the-user tool"** and **`Agent tool` / `Task tool` mean "dispatch a separate subagent" (the `Workflow` tool does too, but its subagents are not recorded by AIDD's hooks, so never use it for Step 6 auditors)** — substitute your row. Step 6's independence rule is about *context isolation*, not about a product feature: a different agent audits what you built; if the host has no subagents, do it as an explicitly separate pass over the diff with the implementer's reasoning withheld.

**2. Resolve `<AIDD_HOME>` before running any command below.** It is the folder containing this `SKILL.md`:

- Claude Code → `~/.claude/skills/aidd`
- OpenCode → the `Base directory for this skill:` line, **if one was printed** — on a skill this size the host truncates the body before it ever reaches the footer, so assume it is missing: check `.opencode/skills/aidd`, then `~/.config/opencode/skills/aidd`, then `~/.claude/skills/aidd` (OpenCode's compatibility source), and keep the first that exists **and** whose `SKILL.md` contains `## Environment adaptation`.
- any other host → wherever you copied this folder

Never paste the literal token `<AIDD_HOME>` into a shell — substitute the resolved path. If no copy can be found, stop and ask where the skill was installed instead of guessing a path.

**3. Enforcement degrades by host; compensate with the CLI, not with memory:**

| Host | What checks the hard rules |
|---|---|
| Claude Code | The hooks in "Installation — Claude Code": real `exit 2` gates plus an append-only evidence log. |
| OpenCode | The `aidd.js` plugin nudges once before the first shell command; **nothing blocks you**. Read every "a hook blocks X" below as: run `aidd rules check <spec-dir>` (prints `PASS\|FAIL Rn … → fix`, exits 1 on a violation) **before** the gated write and do not proceed on FAIL, then `aidd status` before ending the session. |
| any other host | The same CLI, run by hand: `aidd status`, `aidd rules check / approve / close / abandon`. |

The rules (R1–R12) are identical on every host — only who checks them changes. Rows and sections marked **Claude Code only** (hooks, evidence log, `SessionStart` / `Stop`) describe machinery that host has; they are not a requirement elsewhere, and their absence does not waive the rule behind them.

## Installation — by host

### Claude Code — full enforcement (recommended, one-time per machine)

AIDD ships with hooks that make it hard to skip. After copying this skill folder to `<AIDD_HOME>` (`~/.claude/skills/aidd`) on any device, run once:

```bash
python <AIDD_HOME>/scripts/install_hooks.py
```

This merges eleven hook entries (twelve with the opt-in memory hook) into `~/.claude/settings.json` (idempotent — safe to re-run, never duplicates or touches unrelated hooks already configured there):

| Event | Matcher | Script | Effect |
|---|---|---|---|
| `UserPromptSubmit` | — | `hooks/prompt_trigger.py` | Injects an instruction to invoke AIDD before responding if the user's message mentions requerimiento/levantamiento/plan/planificación/nuevo proyecto/funcionalidad. Also records the prompt in the evidence log, syncs AskUserQuestion answers from the host transcript (`sync_ask_answers`) and records messages typed while the agent works (`queued_messages`). |
| `PreToolUse` | `Write\|Edit\|MultiEdit\|NotebookEdit\|PowerShell\|Bash` | `hooks/rule_gate.py` | Blocks (exit 2): writes to evidence logs (R9); source code before AIDD ran this session; `qa-audit.md` without an independent subagent (R7); `plan.md`/`tasks.md` out of chain order (R5); structurally invalid `spec.md`/`tasks.md` (R1–R3, R12); a `qa-audit.md` with no execution evidence for a ✅ code or a repeat bug without root cause (R10, R11); the `Approved:` line without a complete `review.md` plus the owner's consent (R6); agent writes of `review.md`/`review.html`; writes to code files while the gate target spec lacks a valid approval (R6; target = `.aidd/gate_spec`, set only by `aidd rules activate`/`approve`, else the only open spec, else the most recently planned one); Bash/PowerShell commands that write into protected paths (R9). Also runs the transcript sync (`sync_ask_answers`, recovering AskUserQuestion clicks and `queued_messages`) before checking approvals. Timeout 15 s. `AIDD_RULES=off\|0\|false\|no\|warn` is honoured as a last-resort diagnostic (recorded, shown by `aidd status`). |
| `PostToolUse` | `Skill` | `hooks/mark_invoked.py` | Marks AIDD as invoked for this session once the Skill tool actually runs it. |
| `SessionStart` | — | `hooks/session_start.py` | Resets that marker for each new session; records `session_start` in the evidence log. |
| `PostToolUse` | `Write\|Edit\|MultiEdit\|NotebookEdit\|PowerShell` | `hooks/mark_code_edit.py` | Appends `code_edit` / `spec_edit` events; records `approved{spec,hash}` when `tasks.md` is written with a hash-valid `Approved:` line. Timeout 10 s. |
| `PreToolUse` | `Task\|Agent` | `hooks/record_dispatch_pre.py` | Records the `subagent` event BEFORE the agent runs (same dedupe key as the PostToolUse recorder, one row per dispatch), so a slow or failed PostToolUse cannot lose it. |
| `PostToolUse` | `Task\|Agent` | `hooks/mark_agent_dispatch.py` | Timestamps the most recent independent subagent dispatch; appends a `subagent` event. |
| `PostToolUse` | `Bash\|PowerShell` | `hooks/mark_graph_rebuild.py` | Records a `find_spec` event only when the command really RUNS `find_spec.py`. Timeout 10 s. |
| `PostToolUse` | `AskUserQuestion` | `hooks/mark_user_question.py` | Appends a `question` event and an `answer` event with the pairs anchored on the known questions. Timeout 10 s. |
| `Stop` | — | `hooks/stop_gate.py` | Rule R8: refuses (exit 2) to end the session while any OPEN spec has a valid approval, code edits after its `approved` event, and `qa-audit.md` missing. Blocks at most 3 times per (spec, approval hash), then allows. Timeout 15 s. |
| `SessionStart` | `startup\|resume\|clear\|compact` | `hooks/memory_context.py` | Prints a short AIDD Memory digest. Silent when there is no `.aidd/memory/`. Claude Code only. |
| `PreToolUse` | `Read\|Edit\|Write` | `hooks/memory_file_context.py` | **Opt-in** (`install_hooks.py --with-memory-file-hook`). Injects up to 3 memory entries that mention a file the first time it is touched. Claude Code only. |

**Evidence durability.** An evidence `append` that cannot take the log lock retries with a short backoff, then spills the row to `<log>.spill` (merged back by the next reader) and records `hook_error`, instead of dropping it. An approved spec counts as open even before any `plan.md`/`tasks.md` edit was recorded, so it can be closed or abandoned.

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
| **R1** estimates are agent time AND tokens | `tasks.md` with no `## Waves` table, a task lacking `Agent min:` / `Tokens (est):`, a wave time that is not the max of its tasks, a wave token count that is not the SUM of its tasks, a total that is not the sum of the waves, a missing `Total tokens (k): N`, or a `Status` / `Tracker ref` / `PR/Spec ref` cell longer than 60 chars or 8 words. Legacy 4-column files that are already approved stay valid | Add `Agent min:` + `Tokens (est):` per task, the Waves table (`\| Wave \| Tasks \| Roles \| Agent time (min) \| Tokens (k) \| Human ref (h) \|`), `Total agent time (critical path): N min` and `Total tokens (k): N`. Human ref hours is DERIVED = Agent min x 3 / 60, never hand-estimated |
| **R2** route is declared | `spec.md` with no `## Pipeline route` table, a duplicate step row, or a step `waived` without a Reason and `user — "<quote ≥ 3 words>"` | Add the route table (one row each for `-1, 0, 1, 1.5, 2, 3, 4`); ask the user before waiving and quote their words |
| **R3** alignment provenance | The Minimum Requirements Checklist missing any question of the shipped template, or with a blank / `-` Answer; an answer with no valid `Source`; a `repo — <path>` that does not exist, has no `:LINE`, and no `"quote ≥ 3 words found in that file"`; a Proposed marker in ANY column | `user — "<quote>"`, `repo — <existing path>:<LINE>` (or `repo — <path> "<quote from the file>"`), or `[Proposed — unconfirmed]` |
| **R4** visual debt | Waived Steps 0/1/1.5 with `SCREEN-nn` codes and no `## Visual debt` row; a `Blocks spec` that is not an existing spec id; a `resolved` row without a real Mockup source; while a row is `open`, writes under the blocked spec | List the codes in `## Visual debt`, ask the user for the mockup source, run Steps 0/1/1.5, mark the row `resolved` |
| **R5** chain order | `plan.md` without a `find_spec` run this session, an independent subagent (Mapper/Alignment) after the FIRST `spec.md` draft (not after every edit), no blank checklist Answer, zero `[Proposed` rows, every `user — "quote"` verified, and no open debt; `tasks.md` without `plan.md`, a `find_spec` run, and ONE independent pre-build coherence audit (spec, plan, graph, estimates) after the last `spec.md`/`plan.md`/`tasks.md` edit or graph rebuild (after that audit up to `AIDD_R5_FIX_EDITS`, default 3, 0 = strict, later recorded edits do not require a fresh audit). Default `AIDD_R5_AUDIT=advisory`: the missing Mapper / pre-build subagent and the dispatch-after-rebuild branch of the graph-coherence audit no longer block (the `find_spec` requirement stays); `AIDD_R5_AUDIT=strict` restores both blocks. After a graph rebuild, demand graph coherence yourself: re-run `find_spec.py` and check that the plan still matches the rebuilt graph. | Run `find_spec.py`; dispatch the Mapper/Alignment agent once; ask the user every open question; dispatch ONE pre-build coherence auditor; then retry |
| **R6** tasks approval | The `Approved:` line unless the user's recorded answer is "Approve" of an AskUserQuestion about approving the tasks (with the `[tasks:<hash8>]` tag) and `tasks.md` is R1-valid. **Every write to a code file** is blocked while ANY open spec has no valid approval, no hook-recorded `approved{spec,hash}` event, or no `tasks.md` at all. The code gate is scoped PER SPEC: it checks only the gate target, held in `.aidd/gate_spec`, which is written ONLY by `aidd rules activate <id>` and `aidd rules approve` (never by the agent; `.aidd/` is protected). Target choice: the pointer when it names an open spec; else the only open spec; else the open spec whose `plan.md`/`tasks.md` was edited most recently; else it is ambiguous and the message lists the open specs and says to run `aidd rules activate <id>`. Approval needs a complete `review.md` (see the review flow in Step 4) plus the owner's consent. | Present the tasks, ask with AskUserQuestion (option "Approve"), then `aidd rules approve specs/<id>` |
| **R7** closing audit per domain | `qa-audit.md` while any required domain (`security` and `functional` always; `ui`, `backend`, `database` by what the tasks touch; `performance` only when the tasks touch hot paths, the database or the UI) lacks its OWN subagent (medium or high tier, never haiku) after the last code edit. Preferred path: run the spec's `## Verification` table with `aidd verify <spec>` (executed, evidence saved, worktree fingerprint), then dispatch ONE closing auditor whose first line is `CLOSING AUDIT [domains: a, b, c] [tasks:<h8>] [verify:<v8>]` naming every required domain, with the domains as a checklist in `qa-audit.md` plus the auditor's id; per-domain auditors are still accepted for specs approved before this flow. | Dispatch one auditor per missing domain, name the domain in its prompt, rewrite `qa-audit.md` |
| **R8** stop gate | Ending the session while ANY open spec has a valid approval, code edits after its `approved` event, and `qa-audit.md` missing or a required domain uncovered. Only the gate target blocks (budget `AIDD_STOP_BLOCKS`, default 3); every other approved open spec with later edits gets ONE non-blocking reminder per session, listed by `aidd status`. | Run the missing auditors and write `qa-audit.md`, then `aidd rules close <id>` |
| **R9** protected paths | The agent writing anything under `.aidd/` EXCEPT `.aidd/memory/**`, or the per-session evidence directory, via Write/Edit; and Bash/PowerShell commands that write into those paths, that import `aidd_evidence\|aidd_rules\|aidd_status`, that contain `AIDD_TESTING`/`AIDD_EVIDENCE_DIR`/`AIDD_SESSION_ID`, or that assign `AIDD_RULES=` | None — those files are written by hooks only |
| **R10** executed evidence | Writing `qa-audit.md` where a ✅ `SCREEN-nn`, `API-nnn` or `-Fnn` code in the Mapping ledger has no row in `## Execution evidence` (`Code \| Kind \| Evidence \| Verified by`); a Kind outside `screenshot \| command-output \| query-result \| log \| manual-test \| not-verified`; an evidence file that does not exist inside the spec dir or project (drive letters, UNC, absolute paths and `..` are not evidence); a screenshot that is not .png/.jpg/.jpeg/.webp; a `manual-test` without `user — "<quote ≥ 3 words>"`; a `not-verified` whose Status is still ✅ or that cites no existing human test script; (best-effort) evidence older than the last recorded code edit. Codes under `Open exceptions` are exempt | Run it for real, save the screenshot/output under the spec dir, add `\| CODE \| <kind> \| <relative path> \| agent \|`, then rewrite `qa-audit.md`. Cannot run it: Kind `not-verified` + a human test script, Status ⚠️ PARTIAL |
| **R11** root cause on repeat | A `## Bug reports` table (`# \| Code \| Symptom \| Root cause \| Fix \| Pattern sweep`) where the 2nd report of the same Code has no Root cause or no Pattern sweep, or the 3rd report's Fix does not say `redesign` with a spec id or `T-nn` | Write why it failed again (cause, not symptom) and what you searched where (e.g. `grep -rn "fmt(" forms/` → 4 hits fixed); on the 3rd, `Fix: redesign — spec <id>` |
| **R13** agent role and model tier | A task in `tasks.md` without `Agent role:` (`builder\|sql\|tests\|docs\|auditor\|mapper`) or without `Model tier:` (`medium\|high`); anything else, including `low`, is invalid | Declare `Agent role:` and `Model tier: medium` or `high` on every task |
| **R14** no haiku auditors | An auditor/Mapper subagent whose recorded model contains `haiku` does NOT count for R5/R7/R8; an absent or inherited model counts | Dispatch auditors with `model: sonnet` or `opus` |
| **R12** view vs logic | A task in `tasks.md` that cites `SCREEN-`/`COMP-` and a reuse word (reutiliza, remapea, envuelve, wrap, reuse, rewire) without `Kind:` | In the task row or its block add `Kind: VIEW-new` (new view, reused logic/data; the default for a redesign), `Kind: LOGIC`, or `Kind: VIEW-legacy: <why, 5+ chars>` |

Every block message names the next action (which artifact, which command, which question to ask the user).

**Evidence, not trust.** Hooks append what they observed (the agent is not supposed to write it). SESSION kinds go to a per-session log under `<tempdir>/aidd-hooks/evidence/<session-id>.toon`; PROJECT kinds go to `<project>/.aidd/evidence/events.toon` (git-ignored, append-only). Rules fail **closed on missing evidence** and **open on a hook crash**.

**Answers are anchored, not guessed.** Approval, close and abandon are accepted only from a recorded answer whose chosen label is one of the options the question OFFERED — **the agent must offer exactly "Approve" (tasks), "Yes, close" (close) or "Abandon" (abandon)**. The approval question must contain the tag `[tasks:<hash8>]` — the first 8 hex chars of the current `approval_hash` of `tasks.md`.

**Open specs, not "the active spec".** A spec is *open* from the first recorded edit of its `plan.md` or `tasks.md` until a `spec_closed` event. R7 and close apply to EVERY open spec in every project root above the file being written; R6 and the blocking part of R8 apply to the gate target (see R6), the other approved open specs only get a one-time reminder. A spec stops being open only via `aidd rules close <id>` or `aidd rules abandon <id>`.

**Commands (also usable from a terminal or CI):** `aidd review <spec_dir>` (generate the compact `review.html`; `--full`, `--wait`, `--check`, `--comments`, `--summary`), `aidd verify <spec_dir>` (execute `## Verification`), `aidd rules activate <id>` (set the gate target), `aidd status [spec_dir] [--json] [--refresh]` lists ALL open specs with their approval state and WHY blocked lines. `aidd rules check <spec_dir>` prints `PASS\|FAIL Rn message → fix` and exits 1 on any violation. `aidd rules approve <spec_dir>` writes the `Approved:` line only with the user's recorded answer "Approve". `aidd rules close <id>` needs an open spec, a valid recorded approval, `qa-audit.md`, every required domain audited and the recorded answer "Yes, close". `aidd rules abandon <id>` needs the recorded answer "Abandon". `check_spec.py` also reports the static rules (R1–R4, R6, R10–R12) as gaps.

**Executed evidence, not textual (Definition of Done, R10).** A ✅ on a screen, API or field means it was RUN: a screenshot on the real device, or the output of the command/query, saved as a file and cited in `## Execution evidence`. Reading the code is not evidence. Before claiming there is no device, run `adb devices` (or the platform equivalent) and record the output in `## Device preflight` of `qa-audit.md`. If it truly cannot be run, write `not-verified`, write a human test script the user can follow, and keep the Status ⚠️ PARTIAL; never claim done.

**Root cause and pattern sweep (R11).** From the second report of the same bug, find why it failed again and sweep the codebase for the same pattern before fixing; the third report is a redesign, not another patch.

**Acceptance cases and Align.** `spec.md` carries `## Acceptance cases` (`Case | Real data (id) | Expected | Edge?`): written before building, with real record ids and at least one `edge`. The optional `## Optional Align questions` (states, permissions, entry route, target devices) sit outside the 7-row checklist; blank means not asked.

**Credential hygiene.** The evidence log stores prompts, answers and subagent prompt heads with `password|token|secret|api key|bearer`-style `key=value` pairs replaced by `key=[redacted]`, and the hook warns when it redacts. Never copy a secret into a file, spec, memory entry, command or log; reference it by variable name.

**R10 freshness is best-effort.** Existence, kind and status checks are firm; freshness is not: (a) edits made through PowerShell/Bash are not recorded, so evidence made stale that way passes; (b) only code extensions are recorded, so edits to `.json/.xml/.html/.css/.yml/.xaml` are invisible; (c) code edits carry no spec attribution, so any recorded code edit in the session makes all file evidence stale; (d) `http(s)://` evidence has no mtime and is not checked; (e) file mtime resets on git checkout or copy.

**`check_spec.py` gaps G1–G6** (each only when the artifact exists): G1 a control with an Action in `mockup-audit.md` needs Destination, Data source and States; G2 `spec.md` needs Acceptance cases with at least one `edge`; G3 every `traceability.md` row needs Mockup field, Room/store, DTO, API, SP and Filled-by; G4 `contracts.md` needs a stamped `Contract hash:` equal to the table's recomputed hash (run `python check_spec.py <spec_dir> --stamp-contract` once the contract is settled; re-stamp after changing it); G5 a component used in a screen needs `Consumers` in `components-index.md`; G6 two task rows name the same Target file unless one says `same owner as T-nn`.

**Compact hook output.** Hook output to the model is intentionally compact: the full pipeline hint is sent once per session and `find_spec` output is reduced to verdict lines.

**Escape hatch (last-resort diagnostic, owner only):** `AIDD_RULES=off|0|false|no|warn` is not a workflow. Set in the `env` block of `~/.claude/settings.json` (Claude Code) or exported in the session environment (any other host), it disables or softens the gates, is recorded as `rules_override` and is shown by `aidd status`, so it stays visible. If you reach for it, fix the scoping instead: `aidd rules activate <id>` for the spec you are working on, `aidd review <id>` then `aidd rules approve <id>` for approval. `aidd status --refresh` recomputes git and disk facts (branch, dirty files, review, verification and gate state) without any LLM. `check_spec.py` prints `STRUCTURAL CHECK ONLY - nothing was executed`: zero gaps there never means the spec works; `aidd verify` is what executes it.

**Limitations.** (1) Bash and PowerShell can still edit code — the code gate covers Write/Edit/MultiEdit/NotebookEdit; the shell tools are only checked for writes into protected paths. (2) Through Bash/PowerShell an agent can try to forge evidence; the guard is lexical, not a sandbox. (3) The gates verify that a subagent ran and a question was answered, not that they were any good. (4) The user's click cannot be cryptographically proven. (5) Hooks fail open on a crash or timeout. (6) R8 relaxes after 3 blocks per approval hash. (7) Session ids and resume behaviour are not verified. (8) A user quote is checked against what was recorded, not for whether it means what the agent claims. (9) A spec stopped at `spec.md` is not open. (10) Code can be planted under exempt locations (`.git/hooks`, `node_modules/`, `specs/`). (11) `repo —` sources only prove that the file exists, not that it is relevant. (12) The shell guard has false positives (`cp … specs/…`): use the Write tool for those. (13) Session attribution is inferred: before any Bash/PowerShell command that invokes `aidd`, `rule_gate` writes a caller marker (`<tmp>/aidd-hooks/caller-<sha1(root)>.json`, `{session, ts}`); the CLI prefers a marker younger than ~120 s for the same root, else the newest non-synthetic prompt (not starting with `<` or `[`). Refusals name the inferred session. With several concurrent windows the inference can still be wrong; it then fails closed. **In short: the rules stop accidental and self-justified skipping; they do not stop a determined agent.**

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

**When it runs, and who runs it:** there is no separate Graph Coherence Auditor any more. The ONE **pre-build coherence audit** — a fork or fresh agent over spec, plan, graph and estimates, dispatched before `tasks.md` is approved — absorbs it, and no subagent is demanded after each `spec.md`/`plan.md` edit. Scope it to the spec(s) `find_spec.py` named as changed. Its graph checklist:
- Every `SCREEN-XX` cites a `COMP-nnn`/`CTL-nnn` that actually exists in that spec's own inventories.
- Every `CTL-nnn` that calls an `API-nnn` has that `API-nnn` actually defined in `contracts.md` (or explicitly flagged `[Not Verified]`).
- No two specs silently claim the same `COMP-nnn`/`CTL-nnn` number for different things.
- The tree `find_spec.py --tree <spec-id>` prints actually matches the use case the spec's `spec.md` describes.

**This is enforced by hooks, not left as a step someone might skip** — writing `tasks.md` is blocked (exit 2) until an independent subagent has run after the last spec/plan/tasks edit or graph rebuild.

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

### S1 — Automation first, parallel agents, never hand-estimate (working rule, applies before ANY estimate or proposal)
Before you quote a duration, a cost or "this needs N hours", run this check and quote the result of it, not the manual path:
1. **Can a tool do the heavy part?** A script, a catalog or metadata query (`information_schema`, `pg_depend`, `git`, the compiler/AST, a parser), a generator, a codegen, an existing runner or the `aidd` CLI. If yes, the estimate is the SCRIPTED path (write the script, run it, check coverage). Work done by hand or by an agent row by row (per column, per file, per record) is the exception and the plan must say why a tool cannot do it.
2. **What is independent?** Everything without a true dependency runs at the same time: dispatch the agents of a wave in ONE message (one owner per file), fan out read-only searches/audits to separate agents, and run long jobs (`aidd verify`, builds, suites, DB extraction) in the background while other independent work continues. Never serialize what has no dependency and never idle-wait on a job you can overlap.
3. **Report wall time, not effort.** Quote the automated, parallel wall time and tokens; keep hand-hours only as the derived `Human ref`. If the user questions a long estimate, that is a signal the check above was skipped: redo it instead of defending the number.
Record the outcome in the spec's `## Optimization brief` (which tool does the heavy lifting, which tasks fan out) and in `tasks.md` (`Agent role:` / waves). This is guidance, not a gate: it never blocks, but a plan that estimates manual work where a tool or parallel agents exist is a defective plan.

### G1 — Structure graphs: use them, keep them fresh in the background (never mandatory, never blocking)
A project may have structure graphs besides the spec graph: a DB schema graph (tables, columns with their purpose, FKs, views, functions and what they read or write), a code graph (`graphify-out/`), a spec/UI graph (`specs/index.toon`). `aidd graphs list` shows which exist and `aidd graphs status` whether they are fresh. Rules:
0. **Automatic, no questions.** `find_spec.py` (Step -1, which the prompt hook runs for you) already starts the background refresh of every project graph that is missing or stale and prints the nodes that match your query, exactly like the spec graph. If the project has a database, its DB graph is therefore part of every lookup; never ask the user whether to use it.
1. **Always validate the graphs first.** To look up a field, a table, a function, a screen or a spec, the FIRST action is the graph tools (`find_spec.py`, `aidd graphs show <name> <name-or-keyword>`: one node and its neighbours in at most 25 lines); only then read the few lines they point to in SQL, migrations or source. Reading files first is the exception and needs a reason. `aidd graphs explorer <name>` writes a single-file HTML explorer for the owner.
2. **Refresh in the background, never wait.** A spec whose tasks touch the database (migrations, tables, functions, RLS) or the UI structure should start `aidd graphs refresh <name> --background` at Step 3 and keep working; a hook also does it when a watched file is edited (`Watch` globs of the charter's `## Graphs` table). Do not poll or block on it; query again when `aidd graphs status` says `fresh`. `AIDD_GRAPHS=off` disables the hook.
3. **No graph declared?** With SQL migrations present, AIDD builds one with no database (`builtin:sql`); otherwise a project can declare its own generator in the charter. Tools first (rule S1): never rebuild by hand what the generator produces.

### W1 — Graph first, filter first (working rule for every agent, subagents included)
Before reading any file, ask the graph and filter; read only what the answer points to.
1. **Graph first:** `python <AIDD_HOME>/scripts/find_spec.py <keywords|code>` and `--tree <spec-id>` return the spec, use case, screen, component, control and API relations without opening any spec file. `python <AIDD_HOME>/scripts/find_spec.py --code <CODE>` returns one node with its neighbours (tasks, requirements, acceptance cases, API, memory) and file:line in at most 25 lines. Memory the same way: `aidd mem search`, then `aidd mem show <id>` for the one hit you need.
2. **Filter, never dump:** `grep -n` / `rg` for a code or symbol, `sed -n 'A,Bp'` or Read with `offset`/`limit` for a range, `| head`, `| cut -c1-200`, `wc -l` before opening. Never `cat` an evidence log (`events.toon`), an index, a `*.sql` or a whole `spec.md`/`plan.md`/`contracts.md` to check one fact.
3. **Whole-file reads are the exception:** only the file you are about to edit, or Step 1's own exhaustive pass. State why in one line.
4. **Auditors get a scope, not the world:** hand each auditor the changed codes, the files in the diff since the last audit and the `check_spec.py` report. It reads the rest through the graph and grep.
5. **Audit once per phase:** collect the fixes first, then run one auditor per required domain. R7 tolerates the last `AIDD_R7_FIX_EDITS` code edits (default 3; `0` = strict), so a small fix after an audit does not force a re-audit. Build phases carry no per-domain audits: audit once, at close, with ONE closing auditor.

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
| 3 | **Mapper (drafting)** | A fork/fresh agent, once after the FIRST `spec.md` draft, drafts `plan.md`: inspects the codebase, checks `components-index.md`, fills the maps as a proposal | None |
| 4 | **Pre-build Auditor** | ONE fresh agent over spec, plan, graph and estimates before tasks approval (absorbs the old Graph Coherence Auditor) | Must not be the Mapper; medium or high tier |
| 3 | **Approve the plan** | Main conversation presents the Mapper's draft for the user's confirmation | — |
| 4, 5 | **Builder(s)** | ONE owner agent per target file (all small changes to it); parallelize only when tasks touch disjoint files; audit fixes resume that owner | None between implementers, but never the same agent as the Auditors |
| 6 | **Auditores de Cierre (QA)** — one per domain touched | Fresh agents/contexts that did NOT implement the PRs | **Mandatory.** Each re-derives its own `qa-audit.md` rows from the code |
| 7 | **Documentador** | Mechanical assembly pass, any agent | None |

This is a description of the discipline, not a requirement to use any specific tool — apply it with whatever mechanism is already in use as long as the Step 6 independence rule holds.

**Step 6 dispatch rule (Claude Code):** launch the closing auditors with the `Agent` tool, all in ONE message so they run in parallel, and only after the full verification has passed (it runs alone, before any auditor). Do NOT use the `Workflow` tool for them: the dispatch hooks match `Task|Agent` only, so workflow-spawned auditors are never recorded and the close gate does not count them.

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
Draft `spec.md` from `templates/spec.md`: Minimum Requirements Checklist + functional requirements. Every answered row carries a `Source`: `user — "<exact quote, 3+ words>"`, `repo — <path[:line]>`, or `[Proposed — unconfirmed]`. The agent never self-answers — an answer the agent chose itself is always `[Proposed — unconfirmed]`. Ask the user for every open question, then replace the Source with their own words. Before planning, fill `## Optimization brief` in `spec.md`: think about what could be better than the literal request and offer 2-3 options with cost (tokens/minutes) and risk plus a recommendation; ask the owner to pick and record `Owner pick:`. Also fill `## Verification` (real runners or existing repo paths; the owner reviews it as a mandatory section).

### Step 3 — Plan: the Screen → Code map
Dispatch a Mapper agent (fork/fresh) to draft `plan.md`: inspect the codebase for existing naming conventions, check `components-index.md`, fill the Screen→Code / Component→Code maps as a proposal. Present the draft to the user for confirmation. Run `find_spec.py` first. The Mapper runs once after the first `spec.md` draft; do not re-dispatch a subagent after each spec/plan edit — the single pre-build coherence audit (Step 4) covers the later changes.

### Step 4 — Tasks, sized as small PRs
One code, one file, one PR. Plan in agent minutes AND tokens using the calibration baselines (`templates/calibration.toon`: roughly 50-75k tokens per one-file task; Low 45k, Medium 62k, High 90k; minutes are REAL wall time: 3-10 min per one-file task, 15-25 min for a coupled task or one running the suite). Each task has `Agent min:` + `Tokens (est):` + `Agent role:` + `Model tier:`, a `## Waves` table (`| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |`; wave tokens = SUM of tasks, Human ref = Agent min x 3 / 60), `Total agent time (critical path): N min` and `Total tokens (k): N`. Organize each wave with specialized agents (role + model tier per task, one file per task, disjoint files per wave). After closing a spec run `aidd calibrate record specs/<id>` to feed the log.

**Seven planning rules (Step 4).**

| # | Rule |
|---|---|
| 1 | ONE owner agent per target file/class, who makes ALL the small changes to it. Two task rows with the same Target file are one task; keep both only with `same owner as T-nn` (the opt-out `check_spec.py` gap G6 understands). One code, one file, one PR is a review-size concern, not an agent split. |
| 2 | Derive waves from an explicit dependency graph. Only a true dependency (needs another task's output or file) goes in a later wave; everything independent (docs, tests against an interface fixed by `plan.md`, read-only audits of already-stable code) goes in the SAME wave. Target 2-3 waves. |
| 3 | `Agent min` is REAL wall time, not ideal agent minutes (measured: one-file task 3-10 min, coupled task or one running the suite 15-25 min). |
| 4 | Subagent tasks run only their own targeted tests; the main agent runs the full suite once per wave. |
| 5 | After audits, fixes go back to the original owner of each file (SendMessage resume), not to a new agent. |
| 6 | A fix batch fixes only CONFIRMED medium+ findings; the rest are documented open exceptions. |
| 7 | Automation first (S1): estimate the scripted/tool path, not manual work; independent tasks go to parallel agents in one message; long jobs run in the background while other work continues. |

**Approval (one confirmation covers spec, plan and tasks).** Before asking, dispatch the ONE pre-build coherence audit (an independent subagent over spec, plan, graph and estimates, medium or high tier, never haiku); rule R5 blocks `tasks.md` until it ran; after it, up to `AIDD_R5_FIX_EDITS` (default 3, 0 = strict) later recorded edits do not require a fresh audit. Then show a short summary listing the objectives the implementation will achieve with their token/minute cost. Then run the review flow below, and ask ONE AskUserQuestion with the tag `[tasks:<hash8>]` (option "Approve"), then `aidd rules approve specs/<id>`.

**Review before approval (Step 4 to Step 5).** Flow (aidd:FR-307): (1) write `## Executive summary` in `spec.md` FIRST (Objective, Scope, Cost, Risks, Open decisions; a few lines, capped; a legacy spec without it gets a mechanical summary), because ANY edit to `spec.md` changes the sources digest and voids the page; (2) run `aidd review specs/<id>`: it writes the compact `review.html` (generated, git-ignored, zero LLM tokens; 8 tabs, one check per code, `Verificación` included; `--full` generates the old long page); (3) run `aidd review specs/<id> --wait` in the background; (4) the owner opens the page, ticks (`Aprobar todo en esta pestaña` per tab; the Verification rows are checked by hand), comments, and presses the ONE final button, which reads `Guardar progreso` until everything is checked and then `Aprobar y guardar`, with a `Falta: ...` list of what is missing. On Chrome and Edge the page saves `review.md` straight into the spec folder (the owner picks the folder once; it is validated by spec id and tasks hash); other browsers download `review.md` and the owner saves it over `specs/<id>/review.md`. Regenerating the page keeps the checks of unchanged items (only changed or new items return to pending; the owner still presses the button and the agent still asks ONE tagged question); (5) `--wait` prints ONE `STATE=complete ... tag=[tasks:<h8>]` line; (6) only when that line says `comments>0` run `aidd review specs/<id> --comments`, and run it BEFORE editing any source file: once a source changes `review.md` is stale and `--comments` prints nothing; (7) ask ONE tagged AskUserQuestion with the `tag=` value, so the consent is NEWER than `review.md` (the owner's click is the consent); (8) `aidd rules approve specs/<id>`. Any edit to spec, plan or tasks voids the review and the page is regenerated. A complete `review.md` ALONE never approves anything; the typed line `approve [tasks:<h8>]` and the TTY confirmation (`aidd rules approve` in your own terminal) are fallbacks only. A legacy `review.md` (old grammar) is rejected with "regenerate": run `aidd review specs/<id>` again. **Agents NEVER Read, `cat`, `type`, grep or open `review.md` or `review.html` (aidd:FR-309):** they only run `aidd review <spec> --check` / `--wait` (one `STATE=` line) and, only when it says `comments>0`, `aidd review <spec> --comments`; when `--wait` returns `STATE=complete` they ask ONE tagged AskUserQuestion with the `tag=` value (the owner's click is the consent; `review.md` alone never approves). Run `aidd review <spec> --comments` BEFORE editing any source file, because once a source changes review.md is stale and `--comments` prints nothing. The agent may not write `review.md` or `review.html`. When no page exists, only `too many items` refuses a bare tagged answer (a review is required); sources over the 400 000-char size cap keep the 007 answer-only route.

**Review mode is the owner's choice (aidd:FR-313, aidd:AC-331).** Before approval ask ONE AskUserQuestion whose QUESTION text contains the word `aprobar` or `approve` next to `[tasks:<h8>]` (for example `¿Aprobar las tareas [tasks:<h8>]?`; the tool matches the approval topic on the question text only, never on the option labels, so a question without that word does not count) with exactly two options: `Revisar en HTML visual` (only then run `aidd review <spec>`, wait with `--wait`, then the one tagged consent click) and `Aprobar con resumen` (run `aidd review --summary <spec>` and show its output INSIDE the question; the owner's click is the approval, recorded with `source=summary`; the label must be exactly `Aprobar con resumen`: any variant starting `aprobar con resum` is refused by every route). Never generate the page unprompted, never choose the option for the owner, never Read review files. Then the CONSENT rules: for close and abandon the question text must contain `[spec:<id>]` (options "Yes, close" / "Abandon"). Claude Code does not fire hooks for AskUserQuestion, so the clicks are recovered from the host transcript (rule_gate and prompt_trigger run `sync_ask_answers`), and messages typed while the agent works are recorded from `queued_messages`. Fallback when nothing was recorded: ask the user to type the one-line reply (`Approve [tasks:<hash8>]`, `Yes, close [spec:<id>]`, `Abandon [spec:<id>]`) as a NEW message while the agent is idle. A typed reply starting with `<` or `[` (subagent hand-backs) is never accepted. R9 also protects host transcripts (`.claude/projects/*/*.jsonl`) from agent writes.

### Step 5 — Implement, one PR at a time, gated
Group approved tasks into waves (same-wave tasks touch disjoint files). Dispatch every task in a wave as parallel subagent calls in one message. Thread codes into the code: `aidd:CODE` in comments. Code edits are gated while the gate target spec lacks a valid approval.

**Think, then propose.** During build, propose improvements and record them in the brief instead of waiting for audits; do not dispatch per-domain audits while building. Validation is concentrated at close (Step 6).

### Step 6 — Converge
Run `python <AIDD_HOME>/scripts/check_spec.py specs/[###-feature]/` before the manual audit. Then execute the verification and close with ONE auditor (details after this paragraph); the domains it must cover are one per required domain (`security` and `functional` always, the functional one with executed evidence per R10; `ui`, `backend`, `database` by what the tasks touch; `performance` only when the change touches hot paths, the database or the UI) — fresh agents that did NOT implement the PRs. Auditors run on a medium or high model tier chosen by the spec's `Risk: low|medium|high` (high = writes to SAP/DB, security, money -> highest tier), never the lowest. Each (or the single closing auditor, covering all of them) re-derives its own `qa-audit.md` rows from the code. The Auditor must not be the same agent that implemented. Each auditor starts from `find_spec.py --code` for every changed code plus the `check_spec.py` report and the diff since the last audit, and reads full files only for what those point to.

**Close = executed verification + ONE closing auditor.** Run `aidd verify specs/<id>` first (no edit after it, or it is stale). Then dispatch a single independent auditor (medium or high tier, never haiku) whose first line is `CLOSING AUDIT [domains: <every required domain>] [tasks:<h8>] [verify:<v8>]`; it re-derives `qa-audit.md`, filling the Verification summary line and the domain checklist table with the domains and its own id. Per-domain auditors remain accepted for specs approved before this flow.

**A management error never forces a re-execution (amendment to spec 007).** A passed `aidd verify` is judged by the CODE fingerprint only (`c2:` hash of every tracked or untracked non-ignored file outside `specs/`, ignoring `.md`/`.markdown`/`.rst`/`.adoc` and the git history): editing documents, committing, amending or pushing never makes it stale; changing a code or data file does. Two safety nets: (1) each run stores the passing result and sha1 of every row, so a Verification-table edit that adds or changes a row is repaired by running `aidd verify specs/<id>` again, which RE-RUNS ONLY the new or changed rows and reuses (`REUSED row n`) the rest while the code is unchanged (`--full` forces all); (2) a closing auditor stays valid across such re-verifies: its `[verify:<v8>]` tag may be any hash of the run's lineage and it only has to postdate the first verification of the current code state (`code_since`). After a real code change everything is re-run and a new closing auditor is required. Never re-run a verification just because documents changed.

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
