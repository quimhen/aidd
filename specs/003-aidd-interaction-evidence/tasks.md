# Tasks — 003 AIDD Interaction Evidence

One row = one small PR. Classify, estimate, decompose, assign; presented as a dry-run; nothing is written before approval.

**Every task's implementation prompt restates these standards explicitly (a fresh agent does not inherit them):**
- **Scope: in and out, both stated.** In scope = exactly the files this row names. Out of scope = everything else, including an unrelated bug or style issue the agent notices: that is a note back, never a bundled fix. Touching a file this row does not name is out of scope.
- **If anything needed to proceed is missing or ambiguous, stop and report what is unclear; never guess.**
- **Contract = `spec.md` + `plan.md` of this folder.** Read both first; the plan's "Contracts fixed before building" are binding signatures.
- **Naming:** snake_case functions/variables, `_private` helpers, `TestXxx` test classes, kebab-case `.md` templates. Function-style modules stay function-style.
- **Failure design:** hooks and checks never raise to the model: stay inside the existing try/except, exit 0 on internal error, every block message names the next action. `AIDD_RULES=warn|off` keeps working.
- **Stdlib only, Windows-safe (`pathlib`, UTF-8).** The Bash tool is broken on this machine (Cygwin mount error): use PowerShell, Grep, Read. Tests: `python -m unittest discover -s tests` from `D:\Fuentes\AIDD`.
- **Do not use any claude-mem tool or plugin. Do not commit or push. Do not edit `specs/`** (those are the orchestrator's).

| Task | FRs satisfied | Target file | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|
| T-01 | FR-001, FR-002, FR-003 | `skill/scripts/aidd_rules.py`, `tests/test_aidd_rules_r10.py` (new) | | | rule_gate, aidd_status, check_spec, templates, any existing test file |
| T-03 | FR-004 (headers), FR-005 | `skill/templates/*` (list in plan), `adapters/dot-aidd/templates/*`, template class in `tests/test_aidd_rules.py` | | | any script or hook; docs |
| T-05 | FR-006 | `skill/hooks/prompt_trigger.py`, `mark_user_question.py`, `mark_agent_dispatch.py`, `skill/scripts/aidd_evidence.py`, `tests/test_hooks.py`, `tests/test_evidence.py` | | | rule_gate, aidd_rules, other test files (report, never edit) |
| T-08 | FR-008 | no repo file; `.aidd/memory/` in two other repos | | | staging, committing or changing any other file in those repos |
| T-02 | FR-001, FR-002 (gate, status) | `skill/hooks/rule_gate.py`, `skill/scripts/aidd_status.py`, `tests/gate_fixtures.py`, `tests/test_rule_gate.py`, `tests/test_aidd_status.py` | | | aidd_rules.py, check_spec.py, templates |
| T-04 | FR-004 | `skill/scripts/check_spec.py`, `tests/test_check_spec.py` | | | aidd_rules.py, templates, hooks |
| T-06 | FR-007 (docs) | `skill/SKILL.md`, `skill/AIDD.md`, `adapters/dot-aidd/AIDD.md`, `README.md` | | | any code, template or test |
| T-07 | FR-005, FR-007 (mirror, install) | `adapters/dot-aidd/scripts/{aidd_rules,aidd_evidence,aidd_status,check_spec}.py`, `C:\Users\jquimis\.claude\skills\aidd` | | | editing the sources under `skill/`; any new behaviour |

Order: tasks that other tasks depend on come in earlier waves (T-01 and T-03 before T-04; T-01 before T-02).

## Per-task detail (one block per row above)

### T-01
**Classify**
- Nature: `REQUIREMENT`
- Priority: 1 CRITICAL

**Estimate**
- Effort: High
- Agent min: 30
- Human ref hours: 6

**Decompose**
- Objective: add R10 (execution evidence), R11 (root cause on repeat) and R12 (view/logic tag) to the rules engine, per plan Contracts 1-6.
- Activities:
  1. Extend `check_content(kind, text, spec_dir=None, root=None)`; add `check_qa(text, spec_dir, root, last_edit_ts=None)` parsing `Mapping ledger`, `Execution evidence`, `Open exceptions`, `Bug reports`; add `_check_kind` to `_check_tasks`; add `R10`, `R11`, `R12` to `RULE_IDS`; wire `check_qa` into `check_spec_dir` before the static-only return (file content only).
  2. Write `tests/test_aidd_rules_r10.py`: for each rule a violation test AND a legitimate-path test (✅ SCREEN row without evidence blocked; with an existing png passes; not-verified with script and a non-✅ status passes, with ✅ fails; manual-test quote; path escape `..`, drive letter, UNC rejected; R11 second/third report; R12 reuse word with and without Kind, `VIEW-legacy` bare). Include the raw-template checks for `qa-audit.md` and `tasks.md` as they exist at the end of the wave.
  3. Run the full suite and report any failure outside the owned files without editing them.

**Assign**
- Suggested resource: Builder agent (independent from every Auditor).
- Justification: owns the rules engine file exclusively this wave.

### T-03
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH

**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 4

**Decompose**
- Objective: ship the template changes of the spec in both template trees without breaking the existing template tests.
- Activities:
  1. `qa-audit.md` (+Execution evidence, +Bug reports, +Device preflight line; placeholder ✅ rows inside HTML comments), `mockup-audit.md` (+Destination, Data source, States), `plan.md` (+Entry route, Device targets), `tasks.md` (REPLACE the "New view vs. reuse" column with `View / logic`, add the `Kind:` line to the per-task block, no reuse word beside a SCREEN/COMP code), `spec.md` (+`## Acceptance cases`, +`## Optional Align questions` as a separate section; checklist rows stay the 7), `contracts.md` (+`Contract version:` and `Contract hash: PENDING`), `components-index.md` (+Consumers), `STATE.md` (+Test state), `charter.md` (+SAP pitfalls: checkable XML-comment rule, rest prose), NEW `traceability.md`; apply to `skill/templates/` AND `adapters/dot-aidd/templates/` (spec.md and STATE.md byte-identical across trees; tasks.md differs by design).
  2. Update the template-consistency assertions in `tests/test_aidd_rules.py` (add `traceability.md` and the new needles to both trees). Do not make `REQUIRED_QUESTIONS` or the 7 `→ Step 2 align question` lines change.
  3. Run `python -m unittest tests.test_aidd_rules`; the case asserting the raw tasks template yields only `{'R1'}` depends on T-01's R12 and is re-checked by T-07: note its result, do not edit T-01's files.

**Assign**
- Suggested resource: Builder agent.
- Justification: owns the template files exclusively this wave.

### T-05
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH

**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 3

**Decompose**
- Objective: redact secrets before they are stored and warn the agent, per plan Contract 8.
- Activities:
  1. Add `redact_secrets(text) -> (text, labels)` to `skill/scripts/aidd_evidence.py` (cap 20,000 chars, collapse whitespace, bounded-quantifier regex, then truncate to 4,000); call it in `prompt_trigger.py` (stored prompt) and in `mark_user_question.py` (answers) and `mark_agent_dispatch.py` (prompt head); print the hygiene warning independently of the planning-keyword match; keep `sys.exit(0)`.
  2. Tests in `tests/test_evidence.py` and `tests/test_hooks.py`: password/pwd/clave/contraseña/token/api key/bearer redacted, a 1 MB prompt finishes quickly (linear time), a quote of ordinary text still verifies, a secret cut by the 4,000 limit is not exposed, the hook still exits 0 with a broken evidence dir.
  3. Run the FULL suite; if a test in a file you do not own breaks (`test_rule_gate.py`, `test_aidd_status.py`), report it with the failing name and do not edit it.

**Assign**
- Suggested resource: Builder agent.
- Justification: owns the hook files and the evidence module this wave.

### T-08
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3 MEDIUM

**Estimate**
- Effort: Low
- Agent min: 6
- Human ref hours: 1

**Decompose**
- Objective: import the saved claude-mem memory of two projects into AIDD Memory, scrubbed and read-only on the source.
- Activities:
  1. Source: `D:\Fuentes\BKP\claude-mem-2026-10-02\claude-mem.db` (never write to it). Repos: NominaOne `C:\Proyectos\Nomina\NominaOne` (`--project NominaOne`) and BusProApp `C:\Users\jquimis\OneDrive - IMPORPARIS S.A\Fuentes\Android\eBA-CL\BusProApp` (note `eBA-CL` with a hyphen) (`--project BusProApp`). Both are git repos with uncommitted changes and no `.aidd` folder.
  2. Per repo: `python skill\scripts\aidd_memory.py --root <repo> import-claude-mem <db> --project <name> --dry-run`, show the counts, then run it without `--dry-run`. Verify with `git -C <repo> status --short -- .aidd` that only `.aidd/memory` appeared, and `aidd_memory.py --root <repo> stats`.
  3. Never `git add`, commit, stash or touch any other file. Print no secret, IP or password from the memory; if a scrubbed entry still looks sensitive, report its id only.

**Assign**
- Suggested resource: Builder agent.
- Justification: independent of the repo's code; uses the existing importer unchanged.

### T-02
**Classify**
- Nature: `REQUIREMENT`
- Priority: 1 CRITICAL

**Estimate**
- Effort: High
- Agent min: 30
- Human ref hours: 6

**Decompose**
- Objective: enforce R10 and R11 when `qa-audit.md` is written, and surface them in status, per plan Contracts 10-11.
- Activities:
  1. `rule_gate.py`: add `qa-audit.md` to the `_would_be` list, add a content block mirroring the spec/tasks one (new violations only on Edit, any on whole-file Write) calling `rules.check_content('qa', new_text, d, root)`, placed before/independent of `_qa_gate`'s no-`code_edit` early return; freshness through `last_edit_ts` from `ev.events(root, session, 'code_edit')`.
  2. `aidd_status.py`: `st['qa_evidence']`, a segment in `format_status`, `'R10','R11','R12'` in `_why_blocked`; keep `_close_gaps` unchanged.
  3. Add fixtures to `tests/gate_fixtures.py`; gate tests in `tests/test_rule_gate.py` (block, allow, warn mode, stale evidence, Edit does not re-block old violations); status tests in `tests/test_aidd_status.py`; keep the existing R8 strings in `test_stop_gate.py` untouched.

**Assign**
- Suggested resource: Builder agent.
- Justification: owns the gate, the status module and their tests this wave.

### T-04
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH

**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 5

**Decompose**
- Objective: add static gaps G1-G5 and `--stamp-contract` to `check_spec.py`, per spec and plan Contract 7.
- Activities:
  1. G1 (CTL Destination/Data source/States, only when the columns exist), G2 (`## Acceptance cases` with at least one `edge` row), G3 (`traceability.md` cells), G4 (`Contract hash:` recomputed with the plan's algorithm, stale `API-` tasks listed; `--stamp-contract` writes the line), G5 (`Consumers`); argv parsing keeps exit codes 0/1/2 and a single-argument call unchanged.
  2. Tests in `tests/test_check_spec.py` for each gap (flagged and clean cases, old specs without the columns not flagged, stamp round-trip).
  3. Run the full suite and `tests.test_dot_aidd_mirror` layer 2 (the mirror copy of this file is T-07's job).

**Assign**
- Suggested resource: Builder agent.
- Justification: owns `check_spec.py` this wave; reads T-01 and T-03 outputs.

### T-06
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3 MEDIUM

**Estimate**
- Effort: Low
- Agent min: 10
- Human ref hours: 2

**Decompose**
- Objective: document the new rules and the interaction discipline.
- Activities:
  1. `SKILL.md` and `AIDD.md` (and the dot-aidd copy): rows R10-R12 in the rules table with the exact fixes, DoD "evidence executed, not textual" (screenshot on device or command/query output; `adb devices` preflight before claiming no device; `not-verified` + human test script), root cause + pattern sweep, acceptance cases in Align, credential hygiene, the R10 freshness limits from plan Contract 11, installer table mention if it lists rules.
  2. `README.md`: update the "hard rules R1-R9" mention to R1-R12.

**Assign**
- Suggested resource: Builder agent.
- Justification: owns the docs; reads the final names from waves 1-2.

### T-07
**Classify**
- Nature: `REQUIREMENT`
- Priority: 1 CRITICAL

**Estimate**
- Effort: Low
- Agent min: 10
- Human ref hours: 2

**Decompose**
- Objective: mirror the changed scripts, install the result and prove the whole suite is green.
- Activities:
  1. Copy the four scripts byte-identically to `adapters/dot-aidd/scripts/` (`Copy-Item`), then `python -m unittest discover -s tests` from `D:\Fuentes\AIDD`: all green, including `test_dot_aidd_mirror` and the template case asserting the raw tasks template yields only `{'R1'}`; fix only mirror/copy problems, report anything else.
  2. `Copy-Item -Recurse -Force skill\* C:\Users\jquimis\.claude\skills\aidd\` and prove it with a SHA-256 comparison listing of every file under `skill\` against the installed copy; no new hook file was added, so settings.json needs no change (verify with `install_hooks.py` dry check if it has one).
  3. Report the final test counts (run, failures, errors) verbatim.

**Assign**
- Suggested resource: Builder agent.
- Justification: last wave; depends on every other task.

## Waves

Estimates are **agent time**, not human hours. Waves run one after another; tasks inside a wave run in
parallel, so a wave takes as long as its longest task (`max` of its tasks' `Agent min`) and the critical path is the
sum of the waves.

| Wave | Tasks | Agent time (min) | Human ref (h) |
|---|---|---|---|
| 1 | T-01, T-03, T-05, T-08 | 30 | 14 |
| 2 | T-02, T-04 | 30 | 11 |
| 3 | T-06 | 10 | 2 |
| 4 | T-07 | 10 | 2 |

Total agent time (critical path): 80 min

## Approval gate

**Present the table above as a dry-run and wait for explicit approval before Step 5 starts on any row.**
The approval is the user's and is tamper-evident: ask them (AskUserQuestion) to approve the tasks, then run
`aidd rules approve <spec_dir>`, which replaces the line below with `Approved: <YYYY-MM-DD> hash:<12 hex>`.
Any later edit to this file voids it. Do not write that line by hand.

Approved: PENDING

## Definition of Done (applies to every task above)
1. The change implements exactly the FRs cited, in exactly the files named, following the contracts in `plan.md`; hooks and checks never raise to the model.
2. Tests written for the change (violation AND legitimate path), and `python -m unittest discover -s tests` output reported verbatim (counts and failures); a failure outside the owned files is reported, not edited.
3. Executed evidence, not a textual claim: the command run and its output are part of the report.
4. No file outside the task's list was changed (`git status --short` of the listed paths is part of the report).
