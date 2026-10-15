# Tasks — AIDD host parity (spec 009)

One row = one small PR. Estimates are agent wall time and tokens; the Human ref is derived. Revised after the pre-build coherence audit.

Tasks reference the single pre-build coherence audit (spec, plan, graph, estimates) that runs before this list is approved; there is no per-edit audit.

**Every task's implementation prompt restates these standards explicitly — a fresh agent doesn't inherit them from context:**
- **Scope: in and out, both stated explicitly.** In scope = exactly the codes and target file named by the row (plus the twins and companions the row names), nothing else. Anything else, including an unrelated bug or style issue noticed on the way, is a note back, never a bundled fix.
- **If anything needed to proceed is missing or ambiguous, stop and report it** instead of guessing (a vendor field name, a path, a rule id).
- **SOLID** on any code touched.
- **One class/component per file.**
- **Naming & File Contract from `plan.md`**: snake_case Python, camelCase JS, `host_adapter.py` / `install_host.py` / `aidd_doctor.py` / `aidd.js`; the specific names are in `plan.md`.
- **Antifragile / Design for Failure**: every subprocess, file and JSON read can fail; a hook never wedges the host (fail-open on a crash with a `hook_error`), but a block is never silent.
- **Reuse, do not reimplement**: the rules live in `skill/hooks/rule_gate.py`; new code translates events, spawns it and registers the gate. Never import its `decide()`.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-01 | FR-904, FR-905, FR-906, FR-907, FR-908, FR-912 | skill/hooks/host_adapter.py | LOGIC | | | any other file; rule changes in rule_gate |
| T-02 | FR-911 | skill/hooks/rule_gate.py | LOGIC | | | any other file; any rule beyond the protected set |
| T-03 | FR-905 | adapters/opencode/plugins/aidd.js | LOGIC | | | any other file; the adapter's Python |
| T-04 | FR-901, FR-902, FR-903 | skill/scripts/install_host.py | LOGIC | | | any other file; the CLI wiring; calling cmd_init |
| T-05 | FR-909, FR-911 | skill/scripts/aidd_doctor.py | LOGIC | | | any other file; the CLI wiring |
| T-06 | FR-904, FR-905, FR-906, FR-907, FR-908, FR-911, FR-912 | tests/test_host_gates.py | LOGIC | | | any other file |
| T-07 | FR-901, FR-902, FR-903 | tests/test_host_install.py | LOGIC | | | any other file |
| T-08 | FR-909, FR-910, FR-911 | tests/test_host_doctor.py | LOGIC | | | any other file |
| T-09 | FR-901, FR-909 | aidd/cli.py | LOGIC | | | any other file; the scripts it calls |
| T-10 | FR-901, FR-912 | tests/test_dot_aidd_mirror.py | LOGIC | | | the hooks' own code; mirroring scripts |
| T-11 | FR-906, FR-910, FR-913 | adapters/README.md | LOGIC | | | source code; the spec template and AIDD.md (T-13) |
| T-12 | FR-901, FR-902, FR-903, FR-904, FR-905, FR-906, FR-907, FR-908, FR-909, FR-910, FR-911, FR-912, FR-913, FR-914 | specs/009-aidd-host-parity/evidence/verify-summary.md | LOGIC | | | editing source; fixes go back to the owner; qa-audit.md |
| T-13 | FR-913 | skill/templates/spec.md | LOGIC | | | any other file except its twin and AIDD.md with its twin |
| T-14 | FR-914 | skill/scripts/aidd_status.py | LOGIC | | | any other file except its twin and tests/test_aidd_status.py |

## Per-task detail (one block per row above)

### T-01
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: High
- Agent min: 12
- Human ref hours: 0.6
- Tokens (est): 75k
- Agent role: builder
- Model tier: high

**Decompose**
- Objective: one translation layer so Gemini and OpenCode events run through `rule_gate` and `mark_code_edit` unchanged.
- Activities:
  1. Implement plan Interface 1: CLI, normalisation table, order of checks (no AIDD project exits 0, non-write exits 0, session marker, spawn `rule_gate.py`).
  2. `post` spawns `mark_code_edit.py` with the normalised event; the adapter never imports `decide()`.
  3. Fail-open with `hook_error` on a crash; stdout empty on both phases.

### T-02
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
- Model tier: high

**Decompose**
- Objective: the agent cannot switch the gate off by editing the host registration.
- Activities:
  1. Add `.gemini/settings.json`, `.opencode/opencode.json` and `.opencode/plugins/aidd.js` to the R9 protected set, for file tools and for the shell guard.
  2. Keep every existing behaviour; existing `tests/test_rule_gate.py` stays green.

### T-03
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 8
- Human ref hours: 0.4
- Tokens (est): 45k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: OpenCode plugin that blocks by throwing, using the adapter.
- Activities:
  1. Read the current `@opencode-ai/plugin` types and cite them in the header; fix the handler signature (`input` / `output`).
  2. In `tool.execute.before` build `{sessionID, cwd, tool, args}`, spawn `python .aidd/hooks/host_adapter.py opencode pre`, throw `Error(stderr)` on exit 2; `tool.execute.after` runs `post`.
  3. Keep the once-per-session reminder; the hook is `async`; nothing happens outside an AIDD project.

### T-04
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: High
- Agent min: 12
- Human ref hours: 0.6
- Tokens (est): 80k
- Agent role: builder
- Model tier: high

**Decompose**
- Objective: one idempotent, non-destructive install per host.
- Activities:
  1. Fetch the Gemini hooks reference, cite it, and write the `.gemini/settings.json` merge exactly in its schema.
  2. Implement plan Interface 2: per-file copy of `adapters/dot-aidd/` (located from the package root, never `cmd_init`, never `rmtree`), host files, JSON merge by key, `written` / `unchanged` / `skipped`, `--force`.
  3. Never remove foreign entries (`graphify.js`) or anything in `.aidd/memory/`; print a summary.

### T-05
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3 MEDIUM
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 65k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: a doctor that proves the gate works, not just that files exist.
- Activities:
  1. Implement D1-D7 of plan Interface 2 with `PASS|FAIL id message -> fix` lines, `--json`, exit 1 on D1-D5.
  2. D5 builds a temp fixture project with an unapproved spec and must see exit 2 from the adapter.
  3. Report `rules_override` and the registration hash (D4).

### T-06
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 12
- Human ref hours: 0.6
- Tokens (est): 70k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: tests for the gates on both hosts.
- Activities:
  1. Fixture projects for AC-001 (no approval, blocked), AC-002 (approved, allowed, `code_edit` appended, no "invoke the skill" message), AC-003 (many open specs, only the gate target counts), AC-006 (review-page approval then allowed).
  2. Both host payload shapes and the table's non-write tools; a path with spaces; malformed JSON exits 0; no `.aidd/` exits 0.
  3. FR-907, FR-908, FR-911: `.aidd/` and the host config files are not writable by the agent; `rules_override` is recorded. Add a node-based check of the `aidd.js` throw path, skipped with a stated reason when `node` is absent.

### T-07
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3 MEDIUM
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 8
- Human ref hours: 0.4
- Tokens (est): 55k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: tests for the installer.
- Activities:
  1. Fresh install per host, second run is `unchanged`, a modified file is `skipped` and `--force` overwrites it.
  2. AC-005: an `opencode.json` that already lists `graphify.js` and `aidd.js` is not duplicated and keeps `graphify.js`; entries in `.aidd/memory/` survive.

### T-08
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3 MEDIUM
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 8
- Human ref hours: 0.4
- Tokens (est): 55k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: tests for the doctor and the size guard.
- Activities:
  1. AC-004: no `.aidd/` gives exit 1 with the install command; a healthy install gives exit 0; D4 detects an altered registration (FR-911).
  2. FR-910: `CORE.md` under 12 KB; no pointer says to read `AIDD.md` in full.

### T-09
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3 MEDIUM
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 8
- Human ref hours: 0.4
- Tokens (est): 50k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: `aidd install --host H [root] [--force]` and `aidd doctor [--host H] [--root DIR] [--json]`.
- Activities:
  1. Add the two subcommands as passthroughs to `install_host.py` and `aidd_doctor.py` through `_run`, like `pending`.
  2. Help text; exit codes pass through.

### T-10
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3 MEDIUM
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 8
- Human ref hours: 0.4
- Tokens (est): 45k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: the installed `.aidd/` carries the hooks, and the mirror stays byte-identical.
- Activities:
  1. Copy `host_adapter.py`, `rule_gate.py`, `_common.py`, `require_aidd.py`, `require_independent_audit.py`, `require_graph_coherence_audit.py` and `mark_code_edit.py` into `adapters/dot-aidd/hooks/` (scripts are CLI-only and are not mirrored).
  2. Add a hooks list (`SKILL_HOOKS` / `DOTAIDD_HOOKS`) and a byte-identity test to `tests/test_dot_aidd_mirror.py`.

### T-11
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3 MEDIUM
- Kind: LOGIC

**Estimate**
- Effort: Low
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 55k
- Agent role: docs
- Model tier: medium

**Decompose**
- Objective: documentation matches reality, and every pointer file has an owner.
- Activities:
  1. `adapters/README.md`: install with `aidd install --host`, doctor, gate status per host; remove the superseded claim.
  2. Same owner: `skill/SKILL.md` host sections and quote wording; `adapters/dot-aidd/CORE.md` (add the approval route through `aidd review --wait` and the 5+ / 2+ word quote rule); the pointer files `adapters/GEMINI.md`, `adapters/AGENTS.md.snippet`, `adapters/opencode/skills/aidd/SKILL.md`.

### T-12
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
- Objective: executed proof, once, after all builders.
- Activities:
  1. `aidd verify specs/009-aidd-host-parity`, the full suite once in the background; write the result summary to the target file.
  2. If `gemini` / `opencode` binaries exist, install into a scratch project and run a blocked write for real; otherwise `not-verified` with a manual script.
  3. Save the evidence files that the closing auditor of Step 6 will cite in `qa-audit.md` (R10); the auditor writes `qa-audit.md`, not this task.

### T-13
**Classify**
- Nature: `INCIDENT`
- Priority: 4 LOW
- Kind: LOGIC

**Estimate**
- Effort: Low
- Agent min: 6
- Human ref hours: 0.3
- Tokens (est): 40k
- Agent role: docs
- Model tier: medium

**Decompose**
- Objective: the quote rule reads the same in every document (FR-913).
- Activities:
  1. In `skill/templates/spec.md`, `skill/AIDD.md` and their `adapters/dot-aidd/` twins replace "3+ words" for typed quotes with "5+ words, written after the first spec.md draft", keeping "2+ words" for answers to questions.
  2. Keep each pair byte-identical (the mirror and template tests must stay green).

### T-14
**Classify**
- Nature: `INCIDENT`
- Priority: 4 LOW
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 8
- Human ref hours: 0.4
- Tokens (est): 60k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: an old record never reads as a current alarm (FR-914).
- Activities:
  1. In `skill/scripts/aidd_status.py` print the date of the last hook error and count `rules_override` events only since a stated date (default: the last 7 days, with the total shown separately).
  2. Update `tests/test_aidd_status.py` and keep the `adapters/dot-aidd/scripts/aidd_status.py` twin byte-identical.

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-01, T-02, T-03, T-04, T-05, T-06, T-07, T-08, T-13, T-14 | builder, tests, docs | 12 | 605 | 0.6 |
| 2 | T-09, T-10, T-11 | builder, docs | 10 | 150 | 0.5 |
| 3 | T-12 | tests | 20 | 90 | 1.0 |

Total agent time (critical path): 42 min
Total tokens (k): 845

## Approval gate

**Present the table above as a dry-run and wait for explicit approval before Step 5 starts on any row.**

Approved: 2026-10-13 hash:7e58423f394b

## Definition of Done (applies to every task above)
1. Code implements exactly the codes cited, in exactly the target file, following the plan's Naming & File Contract.
2. Builders only self-check statically (compile / parse); the executed verification runs once, in T-12, after all builders.
3. Every FR has a test or a recorded run (R10); anything not runnable is `not-verified` with a manual script.
