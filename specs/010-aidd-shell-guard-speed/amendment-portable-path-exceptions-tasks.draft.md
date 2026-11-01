# Draft tasks — 010 portable path exceptions

DRAFT / NOT APPROVED. Four proposed exceptions are in `amendment-portable-path-exceptions-spec.draft.md`; no implementation or approval is implied. Tools first; native tests use temporary directories; no manually created databases. Tests-first and verification are coordinated, not duplicated. If an actual guard change requires another file or an ambiguous policy choice, stop and report.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-01 | FR-1003 | tests/test_cross_platform_paths.py | LOGIC | | | any other file, source changes, real UNC network access |
| T-02 | FR-1003 | skill/hooks/rule_gate.py; adapters/dot-aidd/hooks/rule_gate.py | LOGIC | | | other files, changing authorization or disabling R6/R9 |

## Per-task detail

### T-01
**Classify**
- Nature: INCIDENT
- Priority: 1
- Kind: LOGIC
**Estimate**
- Effort: High
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 100k
- Agent role: tests
- Model tier: high
**Decompose**
- Goal: prove the four narrowly scoped Linux differences and guarded boundaries with synthetic events, retaining Windows behavior.
- Cites: FR-1003.
- Size: ~120 changed lines.
- Read first: `tests/test_cross_platform_paths.py`, `tests/report_guard_portability.py`, `specs/010-aidd-shell-guard-speed/amendment-portable-path-exceptions-spec.draft.md`.
- Files to change: `tests/test_cross_platform_paths.py` only; existing Python snake_case and unittest style.
- Naming contract: retain `test_native_protected_and_unrelated(self)`, `test_drive_unc_extended_tokens(self)`, `test_case_and_stream_aliases(self)`; identify each additional subcase using its T-23 ID.
- Depends on: owner review of exact exceptions and approval of merged active tasks; no implementation before both.
- Behaviour:
  1. Extend existing `test_native_protected_and_unrelated`, `test_drive_unc_extended_tokens`, `test_case_and_stream_aliases` with Linux-specific fixture assertions for four desired old→new outcomes. Use actual existing fixture APIs and label each subcase with its T-23 ID.
  2. Check old/current baseline independently where relevant and require drive review tokens to classify as protected without changing their existing full denial/message. Include native lowercase protected paths, unrelated paths, mixed separators/case, source file classification, `..` and existing native link/junction behavior; explicit OS skips, never claim Windows coverage on POSIX.
  3. Run only `python -m unittest discover -s tests -p test_cross_platform_paths.py -v` once for tests-first red under each available host; record which of the four failures actually occurred. Do not count unavailable environments or skipped native-link tests as passed.
- Tests first: this task is the tests-first work; no application changes.
- Verify: orchestrator runs `python -m unittest discover -s tests -p test_cross_platform_paths.py -v` once per available OS in the single post-build round -> exit 0 with no skipped required cases.
- Done when: four exception cases and unaffected boundaries pass on each verified OS, with explicit not-verified for unavailable host/link capabilities.
- Do NOT: weaken equality corpus, fabricate a baseline, access remote UNC or modify unrelated files.
- Open questions: none.

### T-02
**Classify**
- Nature: INCIDENT
- Priority: 1
- Kind: LOGIC
**Estimate**
- Effort: High
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 130k
- Agent role: builder
- Model tier: high
**Decompose**
- Goal: implement only the owner-approved Linux path-classification corrections while preserving all other guard decisions/messages.
- Cites: FR-1003.
- Size: ~140 changed lines.
- Read first: `skill/hooks/rule_gate.py`, `specs/010-aidd-shell-guard-speed/amendment-portable-path-exceptions-spec.draft.md`, T-01 red results.
- Files to change: `skill/hooks/rule_gate.py` and byte-identical `adapters/dot-aidd/hooks/rule_gate.py` only.
- Naming contract: preserve `_specs_tok(tok, cwd_specs=False, cwd_abs=None)`, `_abs_path_raw(tok, base=None)` and `_locate(p)` and all public signatures.
- Depends on: T-01 red, owner review and approved tasks; coordinate with 009 T-19/spec 007 ownership and serialize shared files.
- Behaviour:
  1. Within existing signatures, classify foreign drive and UNC tokens lexically, native paths via realpath; make only the four approved full-gate decision exceptions and drive-review lexical fixes. Honor POSIX path case and preserve applicable R6/R9, native symlink/junction containment and Windows canonical behavior.
  2. Copy the hook to its mirror via `python -c "from pathlib import Path; import shutil; shutil.copyfile(Path('skill/hooks/rule_gate.py'), Path('adapters/dot-aidd/hooks/rule_gate.py'))"`; post-check bytes with `python -c "from pathlib import Path; assert Path('skill/hooks/rule_gate.py').read_bytes() == Path('adapters/dot-aidd/hooks/rule_gate.py').read_bytes()"`.
  3. Perform static inspection only; hand off once to the coordinated targeted verification and one independent security audit.
- Tests first: T-01 reports red for changed cases before this edit; stop if a baseline contradicts draft.
- Verify: orchestrator runs `python -m unittest discover -s tests -p test_rule_gate.py -v`, `python -m unittest discover -s tests -p test_rule_gate_shell_speed.py -v` and `python -m unittest discover -s tests -p test_dot_aidd_mirror.py -v` once each per available OS -> exit 0; T-01 module is run once in the same round.
- Done when: targeted checks and mirror pass, actual exception decisions match approved spec, unchanged corpus decisions and messages match baseline, and independent security audit completes.
- Do NOT: alter `aidd_evidence.py`, tests or other files; fabricate approval; turn off guard; access UNC share; weaken protected gates; broaden exceptions.
- Open questions: none.

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-01 | tests | 15 | 100 | 0.75 |
| 2 | T-02 | builder | 20 | 130 | 1.00 |

Total agent time (critical path): 35 min
Total tokens (k): 230

## Approval gate

Draft only. Owner review and approval occur later; no approval is being requested or recorded here.
