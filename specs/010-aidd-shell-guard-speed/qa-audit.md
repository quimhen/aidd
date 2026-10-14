# QA Audit — AIDD shell guard speed (spec 010)

**Audited by:** independent auditors that did not implement it. Pre-build coherence audit `a0e5aea82be1efc8e` (FIX FIRST: rejected the lexical prefilter, the plan was rewritten). Closing: security and functional `acca75a3990c3ab70` (PASS), functional `a4e7b32962314711b` (PASS), final claims review `a6b34e1b75a53fa8a` (PASS WITH EXCEPTIONS: plan.md describes FR-1003 but does not cite its id).

## Verification summary
Verification: `aidd verify specs/010-aidd-shell-guard-speed` PASSED 3/3 rows (verify hash d66c2577; V-1 the new test file: 11 passed, 422 subtests; V-2 `test_rule_gate.py` + `test_host_gates.py` + `test_dot_aidd_mirror.py`: 306 passed; V-3 the full suite once: 48 modules, 317 units, 0 failed). Evidence: evidence/verify-V-1.txt to evidence/verify-V-3.txt and evidence/verify-summary.md (before/after timings and what was not run).

## Domain checklist (filled from the single closing auditor's report)
The closing auditor's first line was `CLOSING AUDIT [domains: functional, security] [tasks:9b14e84d] [verify:d66c2577]`.

Closing auditor id: a6b34e1b75a53fa8a

| Domain | Covered by closing auditor? | Result | Key findings |
|---|---|---|---|
| security | yes | PASS | the new guard and the previous one (commit 3cf5fcc) return the same (blocked, message) for 821 differential commands run under three CLAUDE_PROJECT_DIR settings (17 protected targets in 47 templates: rm/mv/cp in every argument position, sed -i, perl -pi, awk -i inplace, find -delete/-exec, git subcommands, xargs, tee, PowerShell cmdlets, nested bash -c), 22 `cd` chains, and the junction and symlink cases; the memo key is complete, `_locate` hands back a copy, no stale memo across two decisions; `_prot_tok` is unchanged and there is no lexical prefilter |
| functional | yes | PASS | FR-1001..FR-1005 and AC-1001..AC-1005 map to tests; mirror byte-identical; 11 tests and 422 subtests pass; the 264 existing `test_rule_gate.py` tests pass unchanged; docstring accurate; a 1000-word command is decided in about 55 ms under the profiler (was 4389 ms) |

## Mapping ledger
| Code | Status | Evidence (file/class/resource id) | PR/Spec ref | Screenshot diff done? |
|---|---|---|---|---|
| FR-1001, FR-1002, FR-1003 | ✅ IMPLEMENTED | skill/hooks/rule_gate.py (`_abs_path`, `_locate`, `_clear_caches`, `any_hit`); tests/test_rule_gate_shell_speed.py | spec 010 T-01, T-02 | n/a |
| FR-1004 | ✅ IMPLEMENTED | tests/test_rule_gate_shell_speed.py (2 KB under 500 ms, 12 KB under 2 s, 400 KB under 5 s) | spec 010 T-02 | n/a |
| FR-1005 | ✅ IMPLEMENTED | skill/hooks/host_adapter.py unchanged; tests/test_host_gates.py `test_padded_shell_command_never_skips_the_gate` | spec 009 | n/a |

## Device preflight
Preflight: not applicable (no device).

## Execution evidence
No SCREEN-nn, API-nnn or -Fnn code is claimed ✅; the rows above are backed by executed test runs (evidence/verify-V-*.txt) and by the auditors' differential probes (scratchpad scripts).

| Code | Kind | Evidence | Verified by |
|---|---|---|---|

## Bug reports
| # | Code | Symptom | Root cause | Fix | Pattern sweep |
|---|---|---|---|---|---|

## Resilience check (per code that crosses a boundary — network, DB, disk, external API, hardware)
| Code | Timeout set? | Retry/backoff? | Graceful degradation? | Recoverable trace on failure (where)? |
|---|---|---|---|---|
| rule_gate.py shell guard (filesystem reads) | n/a (the host adapter keeps its 15 s fail-closed timeout, unchanged) | no | an exception inside the guard allows the call and records a hook error, as before | `hook_error` in the evidence log |

## Performance & Best Practices check (Performance & Best Practices Auditor — applies to any code touched, every convergence)
| File/class | OOP/SOLID verified in code? | Interfaces used at real boundaries? | Locking/isolation deliberate for the engine? | Connection pooling verified (not just declared)? | No N+1 / unbatched loop? | No blocking call on hot path? |
|---|---|---|---|---|---|---|
| skill/hooks/rule_gate.py | yes (memo wrappers keep the original bodies as `_abs_path_raw` / `_locate_raw`) | yes | n/a | n/a | yes: the per-argument resolution loop is now lazy and memoized | yes: 4.3 ms per word became about 0.01 ms per word on padded commands |

## Revision log (append, never overwrite)
```
Rev 1 (2026-10-14) — 3/3 verification rows, 4/4 tasks; 4.4 s to 6 ms for a 1000-word command; open exceptions below
```

## Open exceptions (rows left unresolved on purpose)
| Code | Reason | Approved by |
|---|---|---|
| X1 | pre-existing, not introduced here: a write through a FILE symlink to a protected file (`echo x > lnk`, `lnk` -> `specs/001-x/tasks.md`) is NOT blocked by the previous or the new guard (a folder junction or directory symlink is blocked). Closing it needs a realpath reading of each resolved token in `_host_tok`/`_specs_tok`; belongs in its own spec | pending owner at close |
| X2 | a padded command whose verb consumes protected-path arguments with thousands of DISTINCT tokens (`rm a1 a2 ... a2000`) still costs about one resolution per distinct token; the host adapter's 15 s fail-closed timeout covers it | pending owner at close |
| X3 | the real OpenCode padded-command probe was not re-run after this change; the guard's decisions are covered by the differential tests | pending owner at close |
| X4 | the timing table of evidence/verify-summary.md carries cache state between rows (disclosed there); the in-process tests clear the memo before each call | pending owner at close |
| X5 | the evidence-log re-parse on every gated pre call (spec 009 E2) is unchanged | pending owner at close |
| X6 | plan.md describes the decision-equivalence contract but does not cite FR-1003 by id (spec.md and tasks.md do) | pending owner at close |
