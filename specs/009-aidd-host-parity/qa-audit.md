# QA Audit — AIDD host parity (spec 009)

**Audited by:** independent auditors that did not implement it. Pass 1 `afbc5ccee8c1b0a44` (closing, PASS WITH EXCEPTIONS: 4 medium findings, fixed). Pass 2 `a1a18c1ab5d57151a` (closing, PASS WITH EXCEPTIONS). Pass 3 `aba23524ac0de0a81` (docs delta). Pass 4, one auditor per domain on the final change: security `a62756bc6845f29c7` (PASS), functional `aaf8f250a0bdad969` (PASS WITH EXCEPTIONS), performance `ae4468d1d2a64e120` (PASS WITH EXCEPTIONS), database `a5d0198528b959038` (PASS, not applicable). Pass 5, final closing audit `acd81fb68de2f62f2` (PASS, last edits and the claims below checked true). A security pass `a03eac88cb68a035d` found a real fail-open bypass (padded shell command), fixed and re-verified; a performance pass `a3b561ed028e002d5` measured the gate cost.

## Verification summary
Verification: `aidd verify specs/009-aidd-host-parity` PASSED 5/5 rows on the final code (verify hash ca40f194; V-1 to V-4 targeted, V-5 the full suite, run three times: after the build, after the first fix batch and after the padded-command fix). Evidence: evidence/verify-V-1.txt to evidence/verify-V-5.txt and evidence/verify-summary.md (it lists what was NOT run). After the last run only comments, the byte-identical mirror and the README changed; `tests/test_host_gates.py` and `tests/test_dot_aidd_mirror.py` were re-run (42 passed).

## Domain checklist (filled from the single closing auditor's report)
The closing auditor's first line was `CLOSING AUDIT [domains: database, functional, performance, security] [tasks:7e58423f] [verify:ca40f194]`.

Closing auditor id: acd81fb68de2f62f2

| Domain | Covered by closing auditor? | Result | Key findings |
|---|---|---|---|
| security | yes | PASS | the first audit's S1/S2/S3/S6/F3/F4/F5 are fixed with tests; the padded-shell-command bypass (12 KB, fail-open on the 15 s timeout) is closed: the adapter and the OpenCode plugin now fail closed on a gate timeout, and an event cwd outside the project falls back to the target path's project. Accepted limits stay as exceptions (patch text not scanned for `.env`, two-step shell route, unknown append tool, lexical shell guard, new plugin file at restart) |
| functional | yes | PASS | FR-901..FR-914 and AC-001..AC-006 map to tests or to an explicit exception; seven hook mirrors byte-identical (cmp, final audit); two stale comments corrected; AC-006 is simulated and the real Gemini/OpenCode binaries were never driven |
| performance | yes | PARTIAL | measured: read about 60 ms, gated call about 190 ms; P1 fixed (reads spawn nothing). Exceptions: the lexical shell guard in `rule_gate.py` costs about 2 ms per word on commands that mention a protected path (2 KB about 4 s, about 7 KB reaches the 15 s limit and is now blocked); every gated pre call re-parses the evidence log (about 0.4 s at 5 MB, pre-existing); OpenCode `todowrite` noise; `spawnSync` blocks the host loop during a gate call |
| database | yes | N-A | grep evidence: no SQL, schema or stored data touched; the only persisted data is the existing append-only evidence log, written through `aidd_evidence` and only read (streamed) by the new status and doctor code |

## Mapping ledger
| Code | Status | Evidence (file/class/resource id) | PR/Spec ref | Screenshot diff done? |
|---|---|---|---|---|
| FR-901..FR-903 | ✅ IMPLEMENTED | skill/scripts/install_host.py; tests/test_host_install.py | spec 009 T-04, T-07 | n/a |
| FR-904..FR-908, FR-912 | ✅ IMPLEMENTED | skill/hooks/host_adapter.py, adapters/opencode/plugins/aidd.js; tests/test_host_gates.py | spec 009 T-01, T-03, T-06 | n/a |
| FR-909, FR-910, FR-913 | ✅ IMPLEMENTED | skill/scripts/aidd_doctor.py; tests/test_host_doctor.py | spec 009 T-05, T-08, T-13 | n/a |
| FR-911 | ✅ IMPLEMENTED | skill/hooks/rule_gate.py (HOST_GATE_FILES, ENV_CONTROL_RE); tests/test_host_gates.py | spec 009 T-02 | n/a |
| FR-914 | ✅ IMPLEMENTED | skill/scripts/aidd_status.py; tests/test_aidd_status.py | spec 009 T-14 | n/a |

## Device preflight
Preflight: not applicable (no device); the Gemini and OpenCode binaries exist (gemini 0.42.0, opencode 1.18.30) but were not driven with an authenticated model session.

## Execution evidence
No SCREEN-nn, API-nnn or -Fnn code is claimed ✅ in this spec; the FR rows above are backed by executed test runs (evidence/verify-V-*.txt) and by the auditors' own probes (padded commands, cwd outside the project, `.env` forms), whose scripts live in the session scratchpad.

| Code | Kind | Evidence | Verified by |
|---|---|---|---|

## Bug reports
| # | Code | Symptom | Root cause | Fix | Pattern sweep |
|---|---|---|---|---|---|

## Resilience check (per code that crosses a boundary — network, DB, disk, external API, hardware)
| Code | Timeout set? | Retry/backoff? | Graceful degradation? | Recoverable trace on failure (where)? |
|---|---|---|---|---|
| host_adapter.py (spawns rule_gate, mark_code_edit) | yes, 15 s / 10 s | no | a gate crash or an internal error fails open; a gate timeout fails CLOSED (exit 2 with a message) | `hook_error` in the evidence log |
| aidd.js (spawns the adapter) | yes, 20 s | no | missing python or a spawn error fails open with one console warning; an adapter timeout blocks | exit-2 message is thrown to the host |
| install_host.py (file copy, JSON merge) | n/a | no | a corrupt JSON file is skipped, never overwritten | per-file `written/unchanged/skipped` report |

## Performance & Best Practices check (Performance & Best Practices Auditor — applies to any code touched, every convergence)
| File/class | OOP/SOLID verified in code? | Interfaces used at real boundaries? | Locking/isolation deliberate for the engine? | Connection pooling verified (not just declared)? | No N+1 / unbatched loop? | No blocking call on hot path? |
|---|---|---|---|---|---|---|
| host_adapter.py, aidd.js | yes | yes (stdin JSON, exit codes) | n/a | n/a | yes | partial: one extra process per gated call (about 130 ms), reads cost nothing; `spawnSync` blocks the OpenCode loop; the shell guard is slow on padded commands (exception E1) |

## Revision log (append, never overwrite)
```
Rev 1 (2026-10-13) — 5/5 verification rows, 14/14 tasks; fix batch 1 (S1, S2, S3, P1, S6, F3, F4, F5, FR-913); fix batch 2 (padded-command bypass, cwd fallback); open exceptions below
```

## Open exceptions (rows left unresolved on purpose)
| Code | Reason | Approved by |
|---|---|---|
| E1 | `rule_gate.py` shell tokenizer is about 2 ms per word on commands that mention a protected path (2 KB about 4 s, about 7 KB hits the 15 s limit and is blocked): make `_tokenize`/`_shell_block` linear, or add a length plus marker precheck; follow-up outside this spec (it also affects Claude Code) | pending owner at close |
| E2 | every gated pre call re-parses the evidence log (about 0.4 s at 5 MB, 1.2 s at 50 MB before rotation): cache `open_specs` by log size and mtime; pre-existing in `rule_gate`/`aidd_evidence` | pending owner at close |
| E3 | OpenCode `patch`/`apply_patch` is gated by path only; its text is not scanned for AIDD_* control variables written into `.env` | pending owner at close |
| E4 | `.env` write through a two-step shell route and through an unknown append-style tool (lexical shell guard, same limit as R9); README states it is a bar, not a guarantee | pending owner at close |
| E5 | OpenCode `todowrite` matches the write pattern: two process spawns per call and `unmapped write-like tool` hook_error noise; `spawnSync` blocks the host loop during a gate call | pending owner at close |
| E6 | no test asserts the host-neutral override wording of the rule_gate messages | pending owner at close |
| E7 | a new plugin file under `.opencode/plugins/` can rewrite the gate after a restart (doctor D4 detects it afterwards); shell protection is lexical; deeply nested stdin JSON fails open (low, records no hook_error) | pending owner at close |
| E8 | AC-006: owner approval on these hosts is exercised through the recorded-answer route, not the real review page | pending owner at close |
| E9 | real Gemini CLI and OpenCode binaries were never driven with a model session; manual script in evidence/verify-summary.md; the Gemini hook command path (relative) and OpenCode argument names beyond filePath/command are unconfirmed against a real run | pending owner at close |
| E10 | the Claude Code hook installed under ~/.claude/skills/aidd is a separate copy and does not get the new rule_gate/FR-911 changes until the owner reinstalls it | pending owner at close |
| E11 | four tests were flaky under the load of the full parallel run and passed alone (test_aidd_rules_r10 three times, test_host_gates TestS3UnknownTools once); V-5 recorded 0 failed | pending owner at close |
