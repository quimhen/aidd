# Tasks — AIDD 006: session attribution, phase-based audits, reliable hook recording

One row = one small PR. Codes are the FR-nnn of spec.md (no screens). Every builder prompt restates: scope in/out as stated per row; stop and report if anything is ambiguous; SOLID; names exactly as plan.md's Naming contract; antifragile (every disk/lock/subprocess call can fail: retry, spill, record `hook_error`, never fail silently); Python stdlib only; match surrounding code style. Source paths are under D:\Fuentes\AIDD\skill unless stated; agents never write `~/.claude` or `.aidd/`.

**Mirror rule (tests/test_dot_aidd_mirror.py:61-75):** after editing `skill/scripts/{aidd_evidence,aidd_rules,aidd_status}.py`, the same task copies the file byte-identical over `adapters/dot-aidd/scripts/`; T-10 re-copies `aidd_evidence.py` after T-01. `AIDD.md` and `templates/tasks.md` are mirrored to `adapters/dot-aidd/` by T-14. The `.aidd/` project install is synced by the owner in the install step, as in 005.

| Task | Codes satisfied | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-01 | FR-004, FR-005, FR-001 | scripts/aidd_evidence.py + adapters/dot-aidd/scripts/aidd_evidence.py | LOGIC | | | any other file; sync_ask_answers |
| T-02 | FR-004 | hooks/mark_agent_dispatch.py | LOGIC | | | any other file |
| T-03 | FR-004 | hooks/record_dispatch_pre.py (new) | LOGIC | | | any other file |
| T-04 | FR-004 | scripts/install_hooks.py | LOGIC | | | any other file |
| T-05 | FR-005 | hooks/mark_code_edit.py | LOGIC | | | any other file |
| T-06 | FR-002, FR-003 | scripts/aidd_rules.py + adapters/dot-aidd/scripts/aidd_rules.py | LOGIC | | | any other file; rule_gate.py |
| T-08 | FR-001, FR-005, FR-006 | scripts/aidd_status.py + adapters/dot-aidd/scripts/aidd_status.py | LOGIC | | | any other file |
| T-09 | FR-001, FR-003 | hooks/rule_gate.py (R5 functions + main) | LOGIC | | | any other file |
| T-10 | FR-006 | scripts/aidd_evidence.py (sync_ask_answers), same owner as T-01 | LOGIC | | | all other functions of the file |
| T-11 | FR-004, FR-005 | tests: test_evidence.py, test_hooks.py, test_install_hooks.py, test_cli_rules.py | LOGIC | | | production code |
| T-12 | FR-001, FR-006 | tests: test_aidd_status.py, test_rule_gate.py, test_typed_confirmations.py, test_transcript_sync.py, test_r9_transcript.py | LOGIC | | | production code |
| T-13 | FR-002, FR-003 | tests: test_aidd_rules.py, test_r14.py, test_stop_gate.py | LOGIC | | | production code |
| T-14 | FR-002, FR-003 | SKILL.md, AIDD.md, templates/tasks.md + their adapters/dot-aidd copies | LOGIC | | | scripts, hooks |
| T-15 | FR-001..FR-006 | audit: security (no file writes except its report) | LOGIC | | | any code edit |
| T-16 | FR-001..FR-006 | audit: functional with executed AC-001..AC-007 | LOGIC | | | any code edit |
| T-17 | FR-004, FR-001, FR-003 | audit: performance of hook hot paths | LOGIC | | | any code edit |
| T-18 | FR-008 | SKILL.md, AIDD.md, templates/tasks.md + their adapters/dot-aidd copies, same owner as T-14 | LOGIC | | | scripts, hooks |
| T-19 | FR-008 | scripts/check_spec.py + its test file | LOGIC | | | any other file |
| T-20 | FR-008, FR-004 | audit: delta security of F1, T-18, T-19 | LOGIC | | | any code edit |
| T-21 | FR-008, FR-004 | audit: delta functional (AC-004, AC-005, AC-008) | LOGIC | | | any code edit |
| T-22 | FR-009 | scripts/aidd_evidence.py (open_specs), same owner as T-01; scripts/aidd_status.py (cmd_close, cmd_abandon, status of a named spec), same owner as T-08; their adapters/dot-aidd copies; tests/test_evidence.py, tests/test_stop_gate.py, tests/test_cli_rules.py, tests/test_aidd_status.py (incl. an abandon test for an approved-only spec) | LOGIC | | | any other file |
| T-23 | FR-009 | audit: delta security of the open_specs change | LOGIC | | | any code edit |
| T-24 | FR-009, FR-010 | audit: functional delta of AC-009, AC-003, AC-007, AC-010 | LOGIC | | | any code edit |
| T-25 | FR-010 | scripts/aidd_rules.py (pre_build_since), same owner as T-06; its adapters/dot-aidd copy; tests/test_aidd_rules.py, tests/gate_fixtures.py, tests/test_rule_gate.py; the R5 lines of SKILL.md and AIDD.md and adapters/dot-aidd/AIDD.md | LOGIC | | | any other file |
| T-26 | FR-009, FR-010 | audit: performance of the amendments and the F3 hardening | LOGIC | | | any code edit |

FR-007 has no code task: after wave 5 and the owner's install, the owner types `Yes, close [spec:005-aidd-token-planning]` as a new message and the agent runs `aidd rules close 005-aidd-token-planning`.

## Per-task detail

### T-01
**Classify**
- Nature: `INCIDENT` (evidence rows are silently lost)
- Priority: 2 HIGH
- Kind: LOGIC
**Estimate**
- Effort: High
- Agent min: 4
- Human ref hours: 0.2
- Tokens (est): 90k
- Agent role: builder
- Model tier: high
**Decompose**
- Objective: `aidd_evidence.append` stops swallowing lock failures, `open_specs` counts an `approved` spec as open, and the caller-marker helper exists.
- Activities:
  1. In `append` (~401-416): retry the lock with backoff, `_spill_row()` to a spill file when it still fails, write a `hook_error` event, return a bool; add `drain_spill(root)` per plan.md.
  2. In `open_specs` (~1057): a spec with an `approved` event and no recorded plan/tasks edit is open.
  3. Add `caller_marker_path(root)` (unconditional, plan.md Naming contract).
  4. Copy the file byte-identical to adapters/dot-aidd/scripts/.

### T-02
**Estimate**
- Effort: Medium
- Agent min: 2
- Human ref hours: 0.1
- Tokens (est): 62k
- Agent role: builder
- Model tier: medium
**Decompose**
- Objective: the `subagent` row is appended first, deduplicated, and a failed append writes `hook_error`.
- Activities: reorder the hook so `append` runs before any other work; use the T-01 bool result; dedupe by tool_use_id.

### T-03
**Estimate**
- Effort: Medium
- Agent min: 2
- Human ref hours: 0.1
- Tokens (est): 62k
- Agent role: builder
- Model tier: medium
**Decompose**
- Objective: new PreToolUse hook with matcher `Task|Agent` that records the dispatch before the agent runs, so a slow PostToolUse cannot lose it.
- Activities: create `hooks/record_dispatch_pre.py` with the same event shape and dedupe key as T-02, fail-open on crash with a `hook_error`.

### T-04
**Estimate**
- Effort: Low
- Agent min: 1
- Human ref hours: 0.05
- Tokens (est): 50k
- Agent role: builder
- Model tier: medium
**Decompose**
- Objective: `install_hooks.py` registers the new PreToolUse `Task|Agent` hook idempotently (lines ~68-77).
- Activities: add the entry, keep the merge idempotent, update the printed hook count if any.

### T-05
**Estimate**
- Effort: Low
- Agent min: 1
- Human ref hours: 0.05
- Tokens (est): 50k
- Agent role: builder
- Model tier: medium
**Decompose**
- Objective: `mark_code_edit.py` writes `hook_error` when the `spec_edit`/`code_edit` append fails (lines ~77-98).
- Activities: use the bool result of T-01 `append`; no change to the matching logic.

### T-06
**Estimate**
- Effort: High
- Agent min: 4
- Human ref hours: 0.2
- Tokens (est): 90k
- Agent role: builder
- Model tier: high
**Decompose**
- Objective: audits by phases in the rule engine: R5 no longer needs a subagent after each spec/plan edit, ONE pre-build coherence audit is required before tasks approval, R7 domains `security` + `functional` always, `performance` only for hot path/DB/UI tasks, `AIDD_R7_FIX_EDITS` tolerance and R14 untouched.
- Activities: edit `_evidence_rules` (~1714, R5 checks ~1741-1762) and `required_domains` (~1399)/R7 block; expose the exact predicate for the pre-build check as a function T-09 calls; copy byte-identical to adapters/dot-aidd/scripts/.

### T-08
**Estimate**
- Effort: High
- Agent min: 4
- Human ref hours: 0.2
- Tokens (est): 90k
- Agent role: builder
- Model tier: high
**Decompose**
- Objective: `_current_session` (:90) prefers a fresh caller marker and skips synthetic prompts; refusals name the inferred session; `cmd_close` (:574) and the status WHY (:267) use the new open definition; `_abandon_since` (:605) honours a later typed "No, keep it".
- Activities: marker reader (120 s, same root, via T-01 `caller_marker_path`); skip prompts starting with `<` or `[`; messages; copy byte-identical to adapters/dot-aidd/scripts/.

### T-09
**Estimate**
- Effort: High
- Agent min: 3
- Human ref hours: 0.15
- Tokens (est): 75k
- Agent role: builder
- Model tier: medium
**Decompose**
- Objective: rule_gate uses T-06's single pre-build predicate in `_r5_plan` (~200) and `_r5_tasks` (~226), and `main` (:1064) writes `caller-<sha1(root)>.json` `{session, ts}` before any Bash/PowerShell command that invokes `aidd`, ahead of the pre-check exit (:1078).
- Activities: new `_write_caller_marker` (best-effort, never blocks); wire the R5 functions to the T-06 predicate; optional perf item (skip evidence import on harmless Bash).

### T-10
**Estimate**
- Effort: Medium
- Agent min: 2
- Human ref hours: 0.1
- Tokens (est): 62k
- Agent role: builder
- Model tier: medium
**Decompose**
- Objective: `sync_ask_answers` (:644) accepts transcript answers only if the tool_use_id was seen by a PostToolUse hook, or checks transcript ownership (closes the `'.cl'+'aude'` gap).
- Activities: implement the option chosen in plan.md; re-copy the file byte-identical to adapters/dot-aidd/scripts/ after editing.

### T-11
**Estimate**
- Effort: Medium
- Agent min: 3
- Human ref hours: 0.15
- Tokens (est): 68k
- Agent role: tests
- Model tier: medium
**Decompose**
- Objective: tests for T-01..T-05 (lock timeout then spill and `hook_error`, dedupe, approved-only spec is open, install idempotence, CLI close of an approved spec). Covers AC-003, AC-004, AC-007.
- Activities: add cases to the four test files; real fixtures, no mocks of the lock beyond a held lock file.

### T-12
**Estimate**
- Effort: Medium
- Agent min: 3
- Human ref hours: 0.15
- Tokens (est): 68k
- Agent role: tests
- Model tier: medium
**Decompose**
- Objective: tests for T-08..T-10 (marker preferred, stale marker, synthetic prompt skipped, Abandon then "No, keep it", transcript id check). Covers AC-001, AC-002, AC-006.
- Activities: add cases to the five test files.

### T-13
**Estimate**
- Effort: Medium
- Agent min: 2
- Human ref hours: 0.1
- Tokens (est): 62k
- Agent role: tests
- Model tier: medium
**Decompose**
- Objective: tests for T-06/T-09 (no subagent demanded between spec edits, one pre-build audit, R7 domains by task kind, R14 intact, stop gate). Covers AC-005.
- Activities: update existing expectations that encode the old per-edit rule, add new cases.

### T-14
**Estimate**
- Effort: Medium
- Agent min: 2
- Human ref hours: 0.1
- Tokens (est): 62k
- Agent role: docs
- Model tier: medium
**Decompose**
- Objective: SKILL.md, AIDD.md and templates/tasks.md describe the phases (Mapper once, one pre-build audit, closing security + functional, performance when hot path/DB/UI), the caller marker and the new hook; keep the host-agnostic wording; mirror AIDD.md and templates/tasks.md to adapters/dot-aidd/.
- Activities: edit the rule table rows R5/R7, Step 3/4/6 prose and the hook table.

### T-15
**Estimate**
- Effort: Medium
- Agent min: 3
- Human ref hours: 0.15
- Tokens (est): 68k
- Agent role: auditor
- Model tier: high
**Decompose**
- Objective: independent security audit (domain: security) of the diff: forgery of the caller marker, spill-file injection, transcript ownership, shell guard bypass.
- Activities: start from `find_spec.py --code`, `check_spec.py` and the diff; report findings in qa-audit.md rows.

### T-16
**Estimate**
- Effort: Medium
- Agent min: 3
- Human ref hours: 0.15
- Tokens (est): 68k
- Agent role: auditor
- Model tier: medium
**Decompose**
- Objective: independent functional audit (domain: backend/functional) that EXECUTES AC-001..AC-007 and saves command output as evidence (R10).
- Activities: run the test suite and each acceptance case; attach output files under the spec dir.

### T-17
**Estimate**
- Effort: Medium
- Agent min: 3
- Human ref hours: 0.15
- Tokens (est): 68k
- Agent role: auditor
- Model tier: medium
**Decompose**
- Objective: independent performance audit (domain: performance) of the hook hot paths (rule_gate on every tool call, append retry cost, cold start under 10 s).
- Activities: time the hooks before/after on a loaded evidence log; report numbers.

### T-18
**Estimate**
- Effort: Medium
- Agent min: 8
- Human ref hours: 0.4
- Tokens (est): 62k
- Agent role: docs
- Model tier: medium
**Decompose**
- Objective: FR-008 in the skill: SKILL.md Step 4 and "Specialized agents", AIDD.md and templates/tasks.md (with their adapters/dot-aidd copies where tests/test_dot_aidd_mirror.py requires them; the dot-aidd tasks.md is a REDUCED variant, edit it by hand, never copy over it) state the six planning rules: one owner agent per file/class, waves from an explicit dependency graph (everything independent in the same wave, 2-3 waves), `Agent min` is real wall time, subagent tasks run targeted tests and the main agent runs the full suite once per wave, fixes go back to the original file owner, a fix batch fixes only confirmed medium+ findings.
- Activities: edit the Step 4 prose and the tasks template note; one agent owns the three files.

### T-19
**Estimate**
- Effort: Medium
- Agent min: 8
- Human ref hours: 0.4
- Tokens (est): 62k
- Agent role: builder
- Model tier: medium
**Decompose**
- Objective: `check_spec.py` reports gap G6 when two rows of the tasks table name the same Target file (normalised path, ignoring a trailing parenthesis, a `+ mirror` suffix and `tests:` prefixes), unless the row says `same owner as T-nn` pointing at the other row; plus tests for AC-008 in the existing check_spec test file (find it with Glob).
- Activities: one agent owns `skill/scripts/check_spec.py` and its test file; mirror to adapters/dot-aidd/scripts only if the mirror test lists it.

### T-20
**Estimate**
- Effort: Medium
- Agent min: 8
- Human ref hours: 0.4
- Tokens (est): 68k
- Agent role: auditor
- Model tier: high
**Decompose**
- Objective: delta security audit (domain: security) of the fix batch F1 and T-18/T-19 only: pre rows never count, post-only dedupe, redaction, per-process lock budget (can it be abused to force spills?), `_invokes_aidd` recursion (new bypass or false positive), check_spec G6.
- Activities: diff since the first audit; findings ranked, CONFIRMED vs PLAUSIBLE.

### T-21
**Estimate**
- Effort: Medium
- Agent min: 8
- Human ref hours: 0.4
- Tokens (est): 68k
- Agent role: auditor
- Model tier: medium
**Decompose**
- Objective: delta functional audit (domain: functional) that EXECUTES AC-004, AC-005, AC-008 and the denied-dispatch case against the final code, with evidence files under specs/006-aidd-phased-audits-attribution/evidence/, plus a timing check of the contended multi-append case (domain: performance).
- Activities: run, save output, report PASS/FAIL per case.

### T-22
**Estimate**
- Effort: Medium
- Agent min: 12
- Human ref hours: 0.6
- Tokens (est): 70k
- Agent role: builder
- Model tier: high
**Decompose**
- Objective: FR-009. One owner agent for scripts/aidd_evidence.py, scripts/aidd_status.py, their adapters/dot-aidd copies and the four test files. `open_specs` (obligation definition used by the Stop gate R8, the R6 code-edit gate, R7 and obligation listings) goes back to "a recorded plan.md or tasks.md edit and no spec_closed"; an `approved` event alone no longer opens a spec there. Add a separate helper (e.g. `closable_specs` or an `include_approved` parameter) that DOES count approved-only specs, used only by `aidd rules close <id>` and `aidd status <spec_dir>` when the user names the spec. Update the tests that encode the FR-005 behaviour for the gates (tests/test_stop_gate.py `test_an_approved_spec_without_recorded_tasks_edit_is_open`, tests/test_evidence.py TestOpenSpecs approved cases) and add: a legacy approved spec with 117 unrelated code edits does not block the Stop gate (AC-009); `aidd rules close` still closes it when named (keep tests/test_cli_rules.py TestCloseApprovedOnlySpec green); a real plan/tasks edit after approval still blocks.
- Activities: targeted tests only (the files touched plus tests/test_dot_aidd_mirror.py); the main agent runs the full suite once.

### T-23
**Estimate**
- Effort: Medium
- Agent min: 6
- Human ref hours: 0.3
- Tokens (est): 60k
- Agent role: auditor
- Model tier: high
**Decompose**
- Objective: delta security audit (domain: security) of T-22 only: can the narrower obligation definition be abused to hide an open spec from R6/R7/R8 (an agent skipping plan/tasks edit records), and does naming a spec in `aidd rules close` open any new way to close or abandon a spec without the user's tagged answer?
- Activities: read-only; findings ranked, CONFIRMED vs PLAUSIBLE.

### T-24
**Estimate**
- Effort: Medium
- Agent min: 6
- Human ref hours: 0.3
- Tokens (est): 60k
- Agent role: auditor
- Model tier: medium
**Decompose**
- Objective: delta functional audit (domain: functional) that EXECUTES AC-009, AC-003 and AC-007 against the final code with evidence under specs/006-aidd-phased-audits-attribution/evidence/ (in scratch dirs, never the real log).
- Activities: run, save output, report PASS/FAIL per case.

### T-25
**Estimate**
- Effort: Medium
- Agent min: 12
- Human ref hours: 0.6
- Tokens (est): 70k
- Agent role: builder
- Model tier: high
**Decompose**
- Objective: FR-010 (R5 tolerance `AIDD_R5_FIX_EDITS`, default 3, 0 = strict). One owner agent for skill/scripts/aidd_rules.py (`pre_build_since` ~:1732-1744; reuse the pattern of `audit_since` ~:1507-1520: `ts[-1]` if tol is 0, `ts[-tol-1]` if more than tol timestamps, else 0.0), its byte-identical mirror, the tests and the R5 prose. Per-file staleness: for each of spec.md/plan.md/tasks.md that has recorded `spec_edit` events use ONLY those events (never its mtime, which every edit bumps and would defeat the tolerance); for a file with no recorded event keep the mtime as the fail-closed fallback; pool these timestamps, sort, and apply the tolerance over the pool; rebuilt `find_spec` events stay always strict (added to the max after the tolerance step). `pre_build_audit_done`, `rule_gate._r5_tasks` and the fix texts need no edit.
- Tests: pin `AIDD_R5_FIX_EDITS=0` in `TestPhasedAudits` setUp/tearDown (pattern of `AIDD_R7_FIX_EDITS` ~:1282-1289) and add `self.env["AIDD_R5_FIX_EDITS"] = "0"` next to the R7 line in tests/gate_fixtures.py (~:234) so existing rule_gate tests stay strict; adapt `test_pre_build_helpers` (~:1497-1509); add AC-010 tests: 3 recorded tasks.md edits after an audit tolerated, the 4th blocked, strict with 0, mtime-only without recorded events fails closed, a rebuilt graph still demands an audit, and `approval_valid` still binds the final tasks.md content.
- Docs: one sentence about `AIDD_R5_FIX_EDITS` (default 3, 0 = strict) in the R5 text of skill/AIDD.md (~:329) and skill/SKILL.md (~:99, :225, :371, :387), the same line by hand in adapters/dot-aidd/AIDD.md; copy aidd_rules.py byte-identical to adapters/dot-aidd/scripts/ (tests/test_dot_aidd_mirror.py). Targeted tests only; the main agent runs the full suite once.

### T-26
**Estimate**
- Effort: Medium
- Agent min: 6
- Human ref hours: 0.3
- Tokens (est): 60k
- Agent role: auditor
- Model tier: medium
**Decompose**
- Objective: delta performance audit (domain: performance) of FR-009 and FR-010 and the F3 hardening: cost of `open_specs`/`pre_build_since` on a loaded evidence log, `_read_log` with the new read order, and the hooks cold start; flag any regression above 20% or anything approaching the hook timeouts.
- Activities: measure with a synthetic log in a scratch dir; report a table and a verdict.

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-01 | builder | 4 | 90 | 0.2 |
| 2 | T-02, T-03, T-04, T-05, T-06 | builder | 4 | 314 | 0.2 |
| 3 | T-08, T-09, T-10 | builder | 4 | 227 | 0.2 |
| 4 | T-11, T-12, T-13, T-14 | tests, docs | 3 | 260 | 0.15 |
| 5 | T-15, T-16, T-17 | auditor | 3 | 204 | 0.15 |
| 6 | T-18, T-19 | docs, builder | 8 | 124 | 0.4 |
| 7 | T-20, T-21 | auditor | 8 | 136 | 0.4 |
| 8 | T-22 | builder | 12 | 70 | 0.6 |
| 9 | T-25 | builder | 12 | 70 | 0.6 |
| 10 | T-23, T-24, T-26 | auditor | 6 | 180 | 0.3 |

Waves 1-8 are done or in flight (their `Agent min` were ideal estimates in waves 1-7; measured wall time was 2-27 min per task, see FR-008). Waves 9-10 use real wall time. T-23 and T-24 audit FR-009 and FR-010 together, with T-26 for performance.

Total agent time (critical path): 64 min
Total tokens (k): 1675

## Approval gate

Approved: 2026-10-03 hash:bde2d5babfbe

## Definition of Done (applies to every task above)
1. Code implements exactly the FR cited, in exactly the target file, following plan.md's Naming contract, SOLID and the antifragile standard.
2. Tests of the task's area pass; the full suite passes at the end of each wave (serialized, one runner at a time), including `test_dot_aidd_mirror`.
3. Mapping row and execution evidence added to `qa-audit.md` for every FR touched (R10).
4. No screens: the screenshot item does not apply.
