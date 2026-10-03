# QA Audit — AIDD 006: session attribution, phase-based audits, reliable hook recording

**Audited by:** independent subagents that did not implement the code: security (opus) first pass, delta and re-check; functional/backend (sonnet) first pass, delta, F2 delta, a read-only verification of the evidence files and a read-only spec/code consistency check; performance (sonnet) first pass and F2 delta. Domains: security, functional, backend, performance (the hooks run on every tool call). The Mapper and the single pre-build coherence auditor ran before tasks approval.

## Mapping ledger
| Code | Status | Evidence (file/class/resource id) | PR/Spec ref | Screenshot diff done? |
|---|---|---|---|---|
| FR-001 | ✅ IMPLEMENTED | skill/hooks/rule_gate.py `_write_caller_marker` (:1126), `_invokes_aidd` (:1072); skill/scripts/aidd_status.py `_read_caller_marker` (:105), `_current_session` (:137), `_is_real_prompt` (:128); skill/scripts/aidd_evidence.py `caller_marker_path` (:206) | spec 006 T-01, T-08, T-09, F2 | n/a (no UI) |
| FR-002 | ✅ IMPLEMENTED | skill/scripts/aidd_rules.py `required_domains` (:1404), `DOMAIN_RE`, `_HOT_PATH_RE`; SKILL.md and AIDD.md R7, R8, Step 6 | spec 006 T-06, T-14 | n/a |
| FR-003 | ✅ IMPLEMENTED | skill/scripts/aidd_rules.py `pre_build_audit_done` (:1747), `_evidence_rules` R5 block; skill/hooks/rule_gate.py `_r5_tasks` (uses it at :233) | spec 006 T-06, T-09 | n/a |
| FR-004 | ✅ IMPLEMENTED | skill/scripts/aidd_evidence.py `append`, `_append`, `_spill_row` (:452), `drain_spill` (:512), per-process lock budget; skill/hooks/record_dispatch_pre.py (trail, `phase:'pre'`); skill/hooks/mark_agent_dispatch.py (counting `phase:'post'`); skill/scripts/aidd_rules.py `_is_pre_dispatch` (:1433); skill/scripts/install_hooks.py | spec 006 T-01..T-04, F1, F2 | n/a |
| FR-005 | ✅ IMPLEMENTED | skill/scripts/aidd_evidence.py `open_specs` (an approved spec is open); skill/scripts/aidd_status.py `cmd_close`, `_why_blocked`; skill/hooks/mark_code_edit.py `_lost` | spec 006 T-01, T-05, T-08 | n/a |
| FR-006 | ⚠️ PARTIAL | skill/scripts/aidd_evidence.py `_ask_pair_trusted` (:845); skill/scripts/aidd_status.py `_keep_it_ts` (:681), `_abandon_since` (:703). A typed "No, keep it" cancels a clicked Abandon; incomplete or inconsistent transcript pairs are rejected; a complete and consistent forged pair is still accepted (Open exceptions) | spec 006 T-08, T-10 | n/a |
| FR-007 | ⚠️ PARTIAL | The code path is ready and covered by unit tests (AC-003, AC-007). Real spec 005 still has no recorded spec_closed: it needs the owner's install and a NEW typed "Yes, close [spec:005-aidd-token-planning]" after this file exists | spec 006 | n/a |
| FR-008 | ✅ IMPLEMENTED | skill/SKILL.md and skill/AIDD.md (six planning rules in Step 4, gaps G1-G6), skill/templates/tasks.md and the adapters/dot-aidd copies; skill/scripts/check_spec.py `check_g6_single_owner` (:308); tests/test_check_spec.py `TestG6SingleOwner` (:310) | spec 006 T-18, T-19 | n/a |

| FR-009 | ✅ IMPLEMENTED | skill/scripts/aidd_evidence.py `open_specs(root, include_approved=False)` (:1277, obligation definition back to a recorded plan/tasks edit); skill/scripts/aidd_status.py `cmd_close` (:652), `cmd_abandon` (:730), `build_status(named=...)` (:239-266); hooks stop_gate.py:70 and rule_gate.py:372 and the status listing (:372) stay strict | spec 006 T-22 | n/a |
| FR-010 | ✅ IMPLEMENTED | skill/scripts/aidd_rules.py `pre_build_since` (:1732-1768, `AIDD_R5_FIX_EDITS` default 3, 0 = strict, per-file recorded edits, unrecorded mtime and rebuilt find_spec always strict); R5 sentence in skill/AIDD.md:329, adapters/dot-aidd/AIDD.md:329, skill/SKILL.md:99 and :387 | spec 006 T-25 | n/a |

## Device preflight
Not applicable: no device and no UI. Preflight: no device required (Windows hooks and CLI only).

## Execution evidence
| Code | Kind | Evidence | Verified by |
|---|---|---|---|
| FR-001 | command-output | evidence/F2-functional-delta.txt | agent |
| FR-002 | command-output | evidence/final-fr002-fr003-fr005-rerun.txt | agent |
| FR-003 | command-output | evidence/final-fr002-fr003-fr005-rerun.txt | agent |
| FR-004 | command-output | evidence/T-21-functional-delta-c1-ac004.txt | agent |
| FR-005 | command-output | evidence/final-fr002-fr003-fr005-rerun.txt | agent |
| FR-006 | command-output | evidence/ac-006.txt | agent |
| FR-007 | command-output | evidence/ac-007-close.txt | agent |
| FR-008 | command-output | evidence/full-suite-and-check-spec.txt | agent |
| FR-009 | command-output | evidence/amend-FR009-FR010-functional.txt | agent |
| FR-010 | command-output | evidence/amend-FR009-FR010-functional.txt | agent |
| FR-004 | command-output | evidence/amend-FR009-FR010-functional.txt | agent |

Also executed: the full suite `python -m pytest tests -q -p no:cacheprovider` = 1247 passed, 21 subtests passed, after fix batches F1 and F2 (full-suite-and-check-spec.txt is the earlier run of 1221 passed). The targeted re-run after the last code edit is evidence/final-fr002-fr003-fr005-rerun.txt (90 passed). Timing of 4 contended appends: 5.7 s against the 10 s hook timeout; uncontended 34-49 ms (evidence/T-21-functional-delta-c5-c6.txt). F2 performance delta: PASS, worst rule_gate process about 0.26 s of a 15 s timeout. Evidence strength noted by the read-only verifier: several earlier files show pytest test names rather than assertion text (ac-001-002, ac-006, ac-007-close); the decoy-model case of F2 and the whole dot-aidd mirror are only partially shown (Open exceptions).

## Bug reports
| # | Code | Symptom | Root cause | Fix | Pattern sweep |
|---|---|---|---|---|---|
| 1 | FR-004 | User prompts, Agent dispatches and plan/tasks edits missing from the evidence log; `aidd rules approve/close` refused valid answers; spec 005 showed `[not open]` | `aidd_evidence.append` swallowed lock timeouts (`except Exception: pass`, a 3 s lock shared by all windows) | T-01 retry, spill and `hook_error`; F1 per-process lock budget | grep `except Exception` and `_ev.append(` in skill/hooks and skill/scripts: every recording hook now checks the bool result |

## Resilience check (per code that crosses a boundary — network, DB, disk, external API, hardware)
| Code | Timeout set? | Retry/backoff? | Graceful degradation? | Recoverable trace on failure (where)? |
|---|---|---|---|---|
| FR-004 evidence append (disk, lock) | yes: first append up to about 4.6 s, 0.15 s after the first spill; 4 appends under a held lock take 5-5.7 s in one hook process (under the 10 s timeout) | yes: backoff, then one fast attempt | yes: the row goes to `<log>.spill`, drained on the next locked write or read | `hook_error` event in the session log; the spill file |
| FR-001 caller marker (disk) | n/a (one atomic write) | no (best-effort) | yes: falls back to the newest non-synthetic prompt | none needed; the marker is advisory |

## Backend contract check (per API-nnn touched)
Not applicable: no API-nnn in this spec.

## Database robustness check (per API-nnn/entity that touches a database)
Not applicable: no database. The evidence log is an append-only text file.

## Performance & Best Practices check (Performance & Best Practices Auditor — applies to any code touched, every convergence)
| File/class | OOP/SOLID verified in code? | Interfaces used at real boundaries? | Locking/isolation deliberate for the engine? | Connection pooling verified (not just declared)? | No N+1 / unbatched loop? | No blocking call on hot path? |
|---|---|---|---|---|---|---|
| skill/hooks/rule_gate.py | yes | yes | n/a | n/a | yes | yes: `_invokes_aidd` 0.0006 s on 18000 chars (was 13 s, fixed in F2) |
| skill/scripts/aidd_evidence.py | yes | yes | yes: lock with a budget and spill | n/a | yes: one scan per reader call | yes: happy path 1-5 ms; 4 appends under a held lock about 5.7 s |
| skill/hooks/mark_code_edit.py | yes | yes | yes | n/a | yes: the per-process budget bounds sequential appends | yes: under the 10 s timeout |

## Revision log (append, never overwrite)
```
Rev 1 (2026-10-03) — 75.0% (6/8 FR fully implemented; FR-006 and FR-007 partial, see Open exceptions)
Rev 2 (2026-10-03) — 80.0% (8/10 FR fully implemented: FR-009 and FR-010 added by the owner's amendments; FR-007 done in practice, spec 005 is closed; FR-006 partial; full suite 1260 passed, 21 subtests passed; security, functional and performance audits of the amendments: PASS WITH EXCEPTIONS, no High or Medium findings)
```

## Open exceptions (rows left unresolved on purpose)
| Code | Reason | Approved by |
|---|---|---|
| FR-006 | MEDIUM severity (rated by the final security auditor): `_ask_pair_trusted` accepts a complete, harness-shaped transcript pair with an unseen tool_use_id on purpose (it recovers a click when the hook row was lost); a forged but fully consistent pair passes as an approval, which bypasses an approval gate; the only guard is R9 transcript protection; closing it needs a transcript-owner path check | pending owner decision |
| FR-004 | L5 (LOW, new in the final audit): `_URL_CRED_RE` stops at the first `@` or `/` in the password, so `scheme://u:p@ss@host` leaves `ss@` in clear and a password containing `/` is not redacted | pending owner decision |
| FR-007 | The close of spec 005 requires the owner's install and a new typed answer after this audit | pending owner action |
| FR-001 | Marker planting through an obfuscated python -c that the lexical R9 shell guard does not catch (approve, close and abandon still need a `[spec:X]` answer). L3: a command such as git commit -m "(aidd status)" writes a marker with the caller's own session | pending owner decision |
| FR-004 | L2, POSIX only: a spill row can be lost in a rename race in `_drain_locked`; Windows sharing rules make it fail safe | pending owner decision |
| FR-004 | M1 residual (LOW, plausible): duplicate model keys take the first value and a block scalar resolves to the indicator; fix is to take the last top-level model key and treat block scalars as unresolved | pending owner decision |
| FR-004 | L4 (LOW, confirmed): the bearer or basic pattern plus 8 characters redacts ordinary prose, a tokens number in prompt heads is redacted, and a redacted JSON password loses its closing quote | pending owner decision |
| FR-004 | The INSTALLED hooks (old) lose dispatch events and count scratch files written by auditors through PowerShell as code edits: observed live while closing this spec (a read-only auditor dispatch was not recorded, a code edit at 12:33:37 made finished audits stale and blocked the first writes of this file); the new hooks are not installed yet | pending install |
| FR-004 | Evidence strength: the F2 decoy model case and the dot-aidd mirror are only partially shown in F2-functional-delta.txt (only aidd_evidence.py hashed); ac-001-002, ac-006 and ac-007-close show test names, not assertion text | pending owner decision |
| FR-010 | LOW (security): the R5 gate runs before the current edit is recorded, so the tolerance lets N+1 (4 at the default) edits pass after the audit; `cmd_approve` does not check R5; the approval itself stays bound to the final tasks.md content by the Approved hash, the recorded approved event and the tagged answer | pending owner decision |
| FR-010 | LOW (security, plausible): once a file has any recorded spec_edit its mtime is ignored even with tolerance 0, so an edit whose row was lost stays invisible; `AIDD_R5_FIX_EDITS` is not in `_ENV_NAMES` of the R9 assignment guard (only the advisory CLI report is affected) | pending owner decision |
| FR-004 | LOW (security, F3): `_read_log` reads the spill in the order (dr, sp); (sp, dr) closes a tiny window in which a concurrent drain hides one spilled row from a single read; and a disk failure in the middle of closing the log file could merge a partial line with the retried row | pending owner decision |
| FR-010 | LOW (performance): `pre_build_since` is about 3.5x and `pre_build_audit_done` about 6x slower than HEAD (0.35-0.86 s on a 35k-row log) because `_spec_file_edit_ts` scans the log once per file; scanning once would fix it; it only runs when plan.md or tasks.md is written, under the 15 s timeout | pending owner decision |
| FR-003 | R5 provenance in this spec.md fails `aidd rules check`: one checklist row (requester) is still Proposed and two user quotes are not found in the recorded prompts, because the OLD hooks lost the owner's prompts while this spec was written; it never blocked approval, close or the code gate | pending owner decision |
| FR-008 | Resolved: T-18 now carries `same owner as T-14` and `check_spec.py` reports no G6 gap | none |
| FR-004 | Under sustained contention a hook process spends 5-5.7 s of its 10 s budget and each spilled row writes its own `hook_error` (noisy) | pending owner decision |

A feature is not done while any row above is unresolved without an entry in this table.
