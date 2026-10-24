# Tasks — AIDD plan adherence on hosts with no write hook (spec 012)

One row = one small PR. Estimates are agent wall time and tokens; the Human ref is derived. Revised after the pre-build coherence audit (auditor af25c04: defects 1-6 are in plan.md items 11-14 and in T-06 to T-09).

Tasks reference the single pre-build coherence audit (spec, plan, graph, estimates) that runs before this list is approved; there is no per-edit audit.

**Every task's implementation prompt restates these standards explicitly — a fresh agent doesn't inherit them from context:**
- **Scope: in and out, both stated explicitly.** In scope = exactly the codes and target file named by the row (plus the companions it names), nothing else. Anything else is a note back, never a bundled fix. Never touch anything under `D:\Fuentes\b1SyCLink` except T-18, and T-18 only after the owner's explicit yes.
- **If anything needed to proceed is missing or ambiguous, stop and report it** instead of guessing (a status field, a path, a git behaviour).
- **SOLID** on any code touched.
- **One class/component per file.**
- **Naming & File Contract from `plan.md`**: snake_case Python files and functions (`aidd_next.py`, `aidd_guard.py`, `build_next`, `format_next`, `staged_files`, `is_code_file`, `evaluate`, `install_githooks`), evidence kind `guard_override`, env var `AIDD_GUARD`, output `.aidd/NEXT.md`, doctor checks D8 and D9.
- **Antifragile / Design for Failure**: every git call, file read and JSON read can fail; the guard fails open on an internal error (and records `hook_error`), never wedges a commit, answers in under 3 s, and never writes through a link in the hooks directory.
- **Reuse, do not reimplement**: the facts come from `build_status` and `verification_state`; the guard filters them to R5, R6, a failed verification and a qa-audit FAIL row. Existing hosts and `rule_gate.py` keep their behaviour byte for byte.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-01 | FR-1202, FR-1203, FR-1207, FR-1208 | skill/scripts/aidd_guard.py | LOGIC | | | any other file except skill/scripts/aidd_status.py (T-02); blocking on R4/R7/R10/R11/R12 |
| T-02 | FR-1207 | skill/scripts/aidd_status.py (same owner as T-01) | LOGIC | | | any other file; changing existing status output lines |
| T-03 | FR-1202, FR-1203, FR-1207, FR-1208 | tests/test_aidd_guard.py | LOGIC | | | any other file |
| T-04 | FR-1201 | skill/scripts/aidd_next.py | LOGIC | | | any other file; calling _derived_facts |
| T-05 | FR-1201 | tests/test_aidd_next.py | LOGIC | | | any other file |
| T-06 | FR-1204, FR-1205 | skill/scripts/install_host.py | LOGIC | | | any other file; removing an existing relative plugin entry |
| T-07 | FR-1204, FR-1205 | tests/test_host_install.py | LOGIC | | | any other file |
| T-08 | FR-1205, FR-1206 | skill/scripts/aidd_doctor.py | LOGIC | | | any other file |
| T-09 | FR-1205, FR-1206 | tests/test_host_doctor.py | LOGIC | | | any other file |
| T-10 | FR-1201, FR-1202, FR-1204 | aidd/cli.py | LOGIC | | | any other file; changing existing subcommands |
| T-11 | FR-1206 | adapters/dot-aidd/CORE.md | LOGIC | | | any other file except adapters/antigravity/rules/aidd.md (T-12); exceeding 12,288 bytes |
| T-12 | FR-1206 | adapters/antigravity/rules/aidd.md (same owner as T-11) | LOGIC | | | any other file |
| T-13 | FR-1204, FR-1205, FR-1207 | adapters/README.md | LOGIC | | | source code; any other file |
| T-14 | FR-1202, FR-1203 | adapters/dot-aidd/scripts/aidd_guard.py | LOGIC | | | editing the script itself; any other file except T-15 and T-16 |
| T-15 | FR-1201 | adapters/dot-aidd/scripts/aidd_next.py (same owner as T-14) | LOGIC | | | editing the script itself |
| T-16 | FR-1207 | adapters/dot-aidd/scripts/aidd_status.py (same owner as T-14) | LOGIC | | | editing the script itself |
| T-17 | FR-1206 | tests/test_dot_aidd_mirror.py | LOGIC | | | any other file |
| T-18 | FR-1201, FR-1202, FR-1203, FR-1204, FR-1205, FR-1206, FR-1207, FR-1208 | specs/012-aidd-plan-adherence-hookless-hosts/evidence/verify-summary.md | LOGIC | | | editing source; qa-audit.md; any b1SyCLink change before the owner's yes |
| T-19 | FR-1202, FR-1208 | skill/scripts/aidd_guard.py (same owner as T-01) | LOGIC | | | any other file; blocking on R4/R7/R10/R11/R12; calling build_status or _derived_facts |
| T-20 | FR-1202, FR-1208 | tests/test_aidd_guard.py (same owner as T-03) | LOGIC | | | any other file |
| T-21 | FR-1202 | adapters/dot-aidd/scripts/aidd_guard.py (same owner as T-14) | LOGIC | | | editing the script itself |
| T-22 | FR-1202, FR-1208 | specs/012-aidd-plan-adherence-hookless-hosts/evidence/amendment-1-summary.md | LOGIC | | | editing source; qa-audit.md; committing or pushing in b1SyCLink |

## Per-task detail (one block per row above)

### T-01
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: High
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 75k
- Agent role: builder
- Model tier: high

**Decompose**
- Objective: `aidd guard commit|push` decides from the gate-target spec's status with no LLM.
- Activities:
  1. `staged_files`, `is_code_file` (everything except `*.md|*.txt|*.toon`, `specs/**`, `docs/**`, `.aidd/**`, `.agents/**`, `.opencode/**`, `.gemini/**`, LICENSE) and `evaluate` returning `{rule, message, fix}` for R5, R6, failed or staged-stale verification, qa-audit FAIL; one `build_status` call, one git diff.
  2. `main`: commit blocks (exit 1), push warns (exit 0), `AIDD_GUARD=warn|off`, no spec open passes with one warning, internal error fails open.

### T-02
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: Low
- Agent min: 4
- Human ref hours: 0.2
- Tokens (est): 40k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: status counts `guard_override` like `rules_override` and lists commits made without approval.
- Activities:
  1. Count `guard_override` in `_override_stats` and print it with the other override lines.
  2. List `commits_without_approval` from at most the last 200 commits, never from `guard commit`.

### T-03
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 8
- Human ref hours: 0.4
- Tokens (est): 55k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: tests for AC-1201, AC-1202, AC-1207 and the override and speed rules.
- Activities:
  1. Scratch git repos: unapproved spec with staged code blocks, approved passes, docs-only passes, qa-audit FAIL blocks, no spec passes with a warning.
  2. `AIDD_GUARD` warn/off recorded; 0 and 5,000 staged files; runtime under 3 s with a realistic events log.

### T-04
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3 MEDIUM
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 8
- Human ref hours: 0.4
- Tokens (est): 60k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: `aidd next` prints the one next action in at most 30 lines.
- Activities:
  1. `build_next` from `build_status` (gate-target spec, step -1..7 from artifacts, open violations with fix, approval, verify result) and `format_next`.
  2. `main` with `[spec_dir] [--write] [--json]`; `--write` writes `.aidd/NEXT.md`; no open spec names `aidd search`.

### T-05
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3 MEDIUM
- Kind: LOGIC

**Estimate**
- Effort: Low
- Agent min: 6
- Human ref hours: 0.3
- Tokens (est): 45k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: tests for AC-1203.
- Activities:
  1. At most 30 lines, exactly one next command, per step of the pipeline.
  2. `--write` creates and refreshes `.aidd/NEXT.md`; no open spec case; runs under 2 s.

### T-06
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: High
- Agent min: 14
- Human ref hours: 0.7
- Tokens (est): 80k
- Agent role: builder
- Model tier: high

**Decompose**
- Objective: `aidd install --githooks` and the opencode install without the relative plugin entry.
- Activities:
  1. `install_githooks`, `GITHOOK_MARKER`, `GITHOOK_NAMES`: hooks dir from `git rev-parse --git-path hooks`, POSIX sh with marker, portable command (`aidd guard` or `.aidd/scripts/aidd_guard.py`), append once to a foreign hook, idempotent, refuse a linked hooks dir, fail open when neither exists.
  2. `install_opencode` stops adding the relative entry and never removes an existing one; `--githooks` alone and offered after `--host opencode|antigravity`.

### T-07
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 60k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: installer tests for AC-1204, AC-1205 and the reversed plugin behaviour.
- Activities:
  1. Rewrite the asserts of the relative plugin entry (lines 161 and 184-208) to the new rule.
  2. Foreign hook kept, run twice changes nothing, worktree hooks dir, linked hooks dir refused.

### T-08
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 60k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: doctor reports the truth for opencode 2.x and checks the new layer.
- Activities:
  1. D4 accepts the plugin entry present or absent; reads `opencode --version` and prints "write gate: none, enforcement: git guard" for 2.x.
  2. D8 git hooks point at `aidd guard`, D9 `.aidd/NEXT.md` and the "run aidd next" line in `CORE.md` and the Antigravity rule; D6 counts `guard_override`.

### T-09
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 8
- Human ref hours: 0.4
- Tokens (est): 50k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: doctor tests for AC-1206.
- Activities:
  1. Rewrite the D4 asserts (lines 117-135) to the new rule.
  2. D8 and D9 pass and fail cases; 2.x line present.

### T-10
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3 MEDIUM
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 8
- Human ref hours: 0.4
- Tokens (est): 55k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: the CLI exposes the new commands.
- Activities:
  1. `cmd_next`, `cmd_guard` and their `add_parser` blocks; `install --githooks` flag with `--host` optional.
  2. Keep `--help` output of existing subcommands unchanged.

### T-11
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3 MEDIUM
- Kind: LOGIC

**Estimate**
- Effort: Low
- Agent min: 5
- Human ref hours: 0.3
- Tokens (est): 35k
- Agent role: docs
- Model tier: medium

**Decompose**
- Objective: the always-read core tells the agent to run `aidd next` before each step.
- Activities:
  1. Add the one-line instruction and the opencode 2.x limit to `CORE.md`, staying under 12,288 bytes.

### T-12
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3 MEDIUM
- Kind: LOGIC

**Estimate**
- Effort: Low
- Agent min: 3
- Human ref hours: 0.2
- Tokens (est): 20k
- Agent role: docs
- Model tier: medium

**Decompose**
- Objective: the Antigravity always-on rule carries the same instruction.
- Activities:
  1. Add the line to `adapters/antigravity/rules/aidd.md` under the 24,000-byte limit.

### T-13
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3 MEDIUM
- Kind: LOGIC

**Estimate**
- Effort: Low
- Agent min: 5
- Human ref hours: 0.3
- Tokens (est): 35k
- Agent role: docs
- Model tier: medium

**Decompose**
- Objective: document the guard, its limits and the opencode 2.x finding.
- Activities:
  1. `aidd next`, `aidd guard`, `--githooks`, `AIDD_GUARD`, `--no-verify` bypass, no write gate on opencode 2.x, plugin shape.

### T-14
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3 MEDIUM
- Kind: LOGIC

**Estimate**
- Effort: Low
- Agent min: 3
- Human ref hours: 0.2
- Tokens (est): 25k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: byte-identical mirror of `aidd_guard.py`.
- Activities:
  1. Copy the final script to `adapters/dot-aidd/scripts/` once T-01 and T-02 are final.

### T-15
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3 MEDIUM
- Kind: LOGIC

**Estimate**
- Effort: Low
- Agent min: 2
- Human ref hours: 0.1
- Tokens (est): 15k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: byte-identical mirror of `aidd_next.py`.
- Activities:
  1. Copy the final script to `adapters/dot-aidd/scripts/`.

### T-16
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3 MEDIUM
- Kind: LOGIC

**Estimate**
- Effort: Low
- Agent min: 2
- Human ref hours: 0.1
- Tokens (est): 15k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: re-mirror `aidd_status.py` after the T-02 edit.
- Activities:
  1. Copy the edited script over its mirror.

### T-17
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3 MEDIUM
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 4
- Human ref hours: 0.2
- Tokens (est): 40k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: the mirror test knows the two new scripts.
- Activities:
  1. Add `aidd_next.py` and `aidd_guard.py` to `VERBATIM_SCRIPTS` and confirm the mirror test passes.

### T-18
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: High
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 90k
- Agent role: tests
- Model tier: high

**Decompose**
- Objective: run the full verification once and prove the guard on real data.
- Activities:
  1. Run `python tests/run_parallel.py` once, in the background; write the summary with the real outputs (R10 evidence).
  2. With the owner's explicit yes, run `aidd install --githooks` in b1SyCLink and try AC-1201 there (a commit with S05 code staged must be refused); without the yes, record `not-verified` with a human test script.

### T-19
**Classify**
- Nature: `INCIDENT`
- Priority: 1 CRITICAL
- Kind: LOGIC

**Estimate**
- Effort: High
- Agent min: 14
- Human ref hours: 0.7
- Tokens (est): 90k
- Agent role: builder
- Model tier: high

**Decompose**
- Objective: the guard checks the spec that owns the staged files, in under 3 s on a real repo (plan items 15-16).
- Activities:
  1. Owner map from the open specs' `tasks.md` Target file cells (trailing parenthesised note stripped), matched against the staged paths; every owning open spec is evaluated; gate target only as the fallback; no owner and no gate target passes with one warning.
  2. Replace the `build_status` call by a light read per spec (approval hash and recorded event, `verification_state`, FAIL rows of qa-audit); no graph code; measure on D:\Fuentes\b1SyCLink with a read-only timing run and report the seconds.

### T-20
**Classify**
- Nature: `INCIDENT`
- Priority: 1 CRITICAL
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 60k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: tests for AC-1208 and the light read.
- Activities:
  1. A scratch repo where the gate pointer names a clean spec and the staged file is a Target file of another spec with a void approval and FAIL rows: commit blocks naming that spec; two owning specs; a Target cell with a `(same owner as ...)` note.
  2. The guard does not import or call `build_status` (assert by patching it to raise); a 70-spec scratch repo with a 2 MB events log answers under 3 s.

### T-21
**Classify**
- Nature: `INCIDENT`
- Priority: 1 CRITICAL
- Kind: LOGIC

**Estimate**
- Effort: Low
- Agent min: 2
- Human ref hours: 0.1
- Tokens (est): 15k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: byte-identical mirror of the fixed `aidd_guard.py`.
- Activities:
  1. Copy the final script to `adapters/dot-aidd/scripts/` and verify with `cmp`.

### T-22
**Classify**
- Nature: `INCIDENT`
- Priority: 1 CRITICAL
- Kind: LOGIC

**Estimate**
- Effort: High
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 70k
- Agent role: tests
- Model tier: high

**Decompose**
- Objective: re-prove AC-1201 and AC-1208 on b1SyCLink and re-run the targeted tests once.
- Activities:
  1. Run the guard and mirror tests, then the full suite once in the background (the suite is the one heavy job).
  2. On b1SyCLink (hooks already installed with the owner's yes): index empty first, stage `Selection/supabase/migrations/3097_sl_hire_selection_fix.sql`, run `aidd guard commit` (exit 1 naming S05) and `aidd guard push`, unstage at once and confirm the index is empty; record the seconds. Never commit or push.

## Waves

Estimates are **agent time**, not human hours. Waves run one after another; tasks inside a wave run in
parallel, so a wave takes as long as its longest task (`max` of its tasks' `Agent min`) and the critical path is the
sum of the waves. A task that depends on another goes in a later wave.

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-01, T-02, T-03, T-04, T-05, T-06, T-07, T-08, T-09 | builder, tests | 14 | 525 | 0.7 |
| 2 | T-10, T-11, T-12, T-13 | builder, docs | 8 | 145 | 0.4 |
| 3 | T-14, T-15, T-16, T-17, T-18 | builder, tests | 20 | 185 | 1.0 |
| 4 | T-19, T-20 | builder, tests | 14 | 150 | 0.7 |
| 5 | T-21, T-22 | builder, tests | 15 | 85 | 0.75 |

Total agent time (critical path): 71 min
Total tokens (k): 1090

## Approval gate

**Present the table above as a dry-run and wait for explicit approval before Step 5 starts on any row.**
Any mismatch caught here costs one edit to this file; the same mismatch caught after implementation
costs a rewritten PR. Never start implementing a task that wasn't approved.

The approval is the user's and is tamper-evident: ask them (AskUserQuestion) to approve the tasks, then run
`aidd rules approve <spec_dir>`, which replaces the line below with `Approved: <YYYY-MM-DD> hash:<12 hex>`.
Any later edit to this file voids it, and code edits stay blocked until it is re-approved. Do not write that line by hand.

Approved: 2026-10-21 hash:391493a74c0e

## Definition of Done (applies to every task above)
1. Code implements exactly the codes cited, in exactly the target file, one class per file, following the plan's Naming & File Contract, SOLID, and the Antifragile standard above (timeouts, retry/backoff, graceful degradation, recoverable trace for anything crossing a boundary).
2. Mapping row added/updated in `qa-audit.md` for every code touched, with file/class/resource-id evidence.
3. Executed verification (run of the commands and tests) — NOT per task: verifier agent(s) (`Agent role: tests`) run it once, only after ALL builders finished, and write the evidence rows (R10) for every code of the spec. A builder only does a static self-check (parse / compile / lint) and never runs the full verification.
