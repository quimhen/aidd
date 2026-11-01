# Tasks — AIDD shell guard speed (spec 010)

One row = one small PR. Estimates are agent wall time and tokens; the Human ref is derived. Revised after the pre-build coherence audit.

Tasks reference the single pre-build coherence audit (spec, plan, graph, estimates) that runs before this list is approved; there is no per-edit audit.

**Every task's implementation prompt restates these standards explicitly — a fresh agent doesn't inherit them from context:**
- **Scope: in and out, both stated explicitly.** In scope = exactly the codes and target file named by the row (plus the twins it names), nothing else. Anything else is a note back, never a bundled fix.
- **If anything needed to proceed is missing or ambiguous, stop and report it** instead of guessing.
- **SOLID** on any code touched.
- **One class/component per file.**
- **Naming & File Contract from `plan.md`**: snake_case Python, private helpers start with `_`.
- **Antifragile / Design for Failure**: the guard is a security gate: no argument is skipped by lexical guesswork, only results that no verb uses are not computed; every cache is cleared per decision call.
- **Decisions never change outside the four enumerated portable-path amendment exceptions**: preserve the previous guard pair (pinned at commit 3cf5fcc) for all other cases.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-01 | FR-1001, FR-1002, FR-1003 | skill/hooks/rule_gate.py | LOGIC | | | any other file; any new rule or message change; any lexical prefilter |
| T-02 | FR-1001, FR-1002, FR-1003, FR-1004 | tests/test_rule_gate_shell_speed.py | LOGIC | | | any other file |
| T-03 | FR-1003 | adapters/dot-aidd/hooks/rule_gate.py | LOGIC | | | editing the hook itself |
| T-04 | FR-1001, FR-1002, FR-1003, FR-1004, FR-1005 | specs/010-aidd-shell-guard-speed/evidence/verify-summary.md | LOGIC | | | editing source; qa-audit.md |
| T-05 | FR-1003 | tests/test_cross_platform_paths.py | LOGIC | | | any other file, source changes, real UNC network access |
| T-06 | FR-1003 | skill/hooks/rule_gate.py; adapters/dot-aidd/hooks/rule_gate.py | LOGIC | | | other files, changing authorization or disabling R6/R9 |

## Per-task detail (one block per row above)

Historical T-01 through T-04 retain their originally approved scope and wording; T-05 and T-06 propose the later exceptions. Neither historical wording nor a proposed amendment expands an exception beyond the specific approved cases.

### T-01
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: High
- Agent min: 12
- Human ref hours: 0.6
- Tokens (est): 70k
- Agent role: builder
- Model tier: high

**Decompose**
- Objective: remove the per-word filesystem resolution from the shell guard without changing any decision.
- Activities:
  1. Memoize `_locate` by path and `_abs_path` by `(token, base)`; add `_clear_caches()` and call it at the start of `decide(event)`.
  2. Make the `prot_args = [a for a in args if hit(a)]` evaluation in `_shell_block` lazy: only for the verbs that consume it, only for the arguments they need; `_prot_tok` unchanged; no lexical prefilter.
  3. Re-profile with the scratchpad script and confirm the per-word cost is gone; run only `python -m pytest tests/test_rule_gate.py -q -x` once.

### T-02
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 12
- Human ref hours: 0.6
- Tokens (est): 55k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: prove decisions are identical and the speed target is met.
- Activities:
  1. Load the guard pinned at commit 3cf5fcc (`git show 3cf5fcc:skill/hooks/rule_gate.py` into a temp module, after `skill/scripts` is on `sys.path`) and compare (blocked, message) with the new guard over the generated command set (AC-1005, including symlink, junction, quoted-fragment and host-folder cases) and AC-1001..AC-1004.
  2. Count `_locate` calls with a monkeypatch: one per repeated token, none for the arguments of `echo` (FR-1001, FR-1002); `_clear_caches()` in `setUp`.
  3. Timing assertions: 2 KB padded under 500 ms, 12 KB under 2 s, 400 KB under 5 s, legitimate read-only heredoc under 500 ms; state in the test how the padding is built (spaced plain words after `echo`); generous margins for slow machines, skip nothing.

### T-03
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3 MEDIUM
- Kind: LOGIC

**Estimate**
- Effort: Low
- Agent min: 4
- Human ref hours: 0.2
- Tokens (est): 15k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: keep the installed copy identical.
- Activities:
  1. Copy `skill/hooks/rule_gate.py` over `adapters/dot-aidd/hooks/rule_gate.py` and confirm with `cmp`.

### T-04
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 14
- Human ref hours: 0.7
- Tokens (est): 50k
- Agent role: tests
- Model tier: high

**Decompose**
- Objective: executed proof once, after the builders.
- Activities:
  1. Run `aidd verify specs/010-aidd-shell-guard-speed` (full suite once, in the background) and write the summary file with the before and after timings.
  2. Re-run the real OpenCode padded-command probe if time allows and record it.



### T-05
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

### T-06
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
- Read first: `skill/hooks/rule_gate.py`, `specs/010-aidd-shell-guard-speed/amendment-portable-path-exceptions-spec.draft.md`, T-05 red results.
- Files to change: `skill/hooks/rule_gate.py` and byte-identical `adapters/dot-aidd/hooks/rule_gate.py` only.
- Naming contract: preserve `_specs_tok(tok, cwd_specs=False, cwd_abs=None)`, `_abs_path_raw(tok, base=None)` and `_locate(p)` and all public signatures.
- Depends on: T-05 red, owner review and approved tasks; coordinate with 009 T-19/spec 007 ownership and serialize shared files.
- Behaviour:
  1. Within existing signatures, classify foreign drive and UNC tokens lexically, native paths via realpath; make only the four approved full-gate decision exceptions and drive-review lexical fixes. Honor POSIX path case and preserve applicable R6/R9, native symlink/junction containment and Windows canonical behavior.
  2. Copy the hook to its mirror via `python -c "from pathlib import Path; import shutil; shutil.copyfile(Path('skill/hooks/rule_gate.py'), Path('adapters/dot-aidd/hooks/rule_gate.py'))"`; post-check bytes with `python -c "from pathlib import Path; assert Path('skill/hooks/rule_gate.py').read_bytes() == Path('adapters/dot-aidd/hooks/rule_gate.py').read_bytes()"`.
  3. Perform static inspection only; hand off once to the coordinated targeted verification and one independent security audit.
- Tests first: T-05 reports red for changed cases before this edit; stop if a baseline contradicts draft.
- Verify: orchestrator runs `python -m unittest discover -s tests -p test_rule_gate.py -v`, `python -m unittest discover -s tests -p test_rule_gate_shell_speed.py -v` and `python -m unittest discover -s tests -p test_dot_aidd_mirror.py -v` once each per available OS -> exit 0; T-05 module is run once in the same round.
- Done when: targeted checks and mirror pass, actual exception decisions match approved spec, unchanged corpus decisions and messages match baseline, and independent security audit completes.
- Do NOT: alter `aidd_evidence.py`, tests or other files; fabricate approval; turn off guard; access UNC share; weaken protected gates; broaden exceptions.
- Open questions: none.


## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-01, T-02 | builder, tests | 12 | 125 | 0.6 |
| 2 | T-03 | builder | 4 | 15 | 0.2 |
| 3 | T-04 | tests | 14 | 50 | 0.7 |
| 4 | T-05 | tests | 15 | 100 | 0.75 |
| 5 | T-06 | builder | 20 | 130 | 1.00 |

Total agent time (critical path): 65 min
Total tokens (k): 420

## Approval gate

**Present the table above as a dry-run and wait for explicit approval before Step 5 starts on any row.**

<!-- Historical approval retained for provenance; it does not approve these amended tasks: 2026-10-13 hash:9b14e84de574. -->

## Definition of Done (applies to every task above)
1. Code implements exactly the codes cited, in exactly the target file, following the plan's Naming & File Contract.
2. Builders only self-check statically; the original executed verification ran in T-04; amendment verification is one coordinated round after T-06 as described in the amendment plan.
3. Every FR has a test or a recorded run (R10); anything not runnable is `not-verified` with a manual script.

Approved: 2026-11-01 hash:e42062c6c2cb
