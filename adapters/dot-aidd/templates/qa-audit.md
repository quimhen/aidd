# QA Audit — [feature name]

**Audited by:** [independent Auditor agent/person — never the same agent that implemented the PR being checked]

## Mapping ledger
| Code | Status | Evidence (file/class/resource id) | PR/Spec ref | Screenshot diff done? |
|---|---|---|---|---|
<!-- Status values: ✅ IMPLEMENTED | ⚠️ PARTIAL | ❌ MISSING | 🔄 DIFFERENT. A ✅ on a SCREEN-nn, API-nnn or -Fnn code needs a row in "Execution evidence" below.
| SCREEN-01 | ✅ IMPLEMENTED | | | ☐ |
| COMP-001 | | | | ☐ (check on every screen it's used in) |
| CTL-001 | | | | ☐ |
| SCREEN-01-F01 | | | | ☐ |
-->
| SCREEN-01 | | | | ☐ |
| COMP-001 | | | | ☐ (check on every screen it's used in) |
| CTL-001 | | | | ☐ |
| SCREEN-01-F01 | | | | ☐ |

## Device preflight
Before claiming any device/tablet/phone code done: run `adb devices` (or the platform's equivalent) and record the result here. No device listed = the codes that need it stay ⚠️ PARTIAL with a `not-verified` row below.

Preflight: [command run + its output line, or "no device available"]

## Execution evidence
Run, don't read: every ✅ code above of kind SCREEN-nn, API-nnn or -Fnn needs a row here proving it was EXECUTED (not only that the code exists).
`Kind` = `screenshot | command-output | query-result | log | manual-test | not-verified`. `Evidence` = a path to an existing file (a screenshot must be .png/.jpg/.jpeg/.webp) or an http(s) URL; `manual-test` = `user — "<their words, 3+ words>"`; `not-verified` = the path of a human test script, and that code's Status above must then be ⚠️ PARTIAL, not ✅. `Verified by` = `agent | user`.

| Code | Kind | Evidence | Verified by |
|---|---|---|---|

<!-- Example row (delete): | SCREEN-01 | screenshot | evidence/screen-01.png | agent | -->

## Bug reports
One row per bug found after something was declared done. From the 2nd report of the same Code, `Root cause` and `Pattern sweep` (what you searched, where, and what you found, e.g. `grep -rn "fmt(" forms/` → 4 hits fixed) must be filled. From the 3rd, `Fix` must say `redesign` plus a reference (spec id or task).

| # | Code | Symptom | Root cause | Fix | Pattern sweep |
|---|---|---|---|---|---|

## Resilience check (per code that crosses a boundary — network, DB, disk, external API, hardware)
| Code | Timeout set? | Retry/backoff? | Graceful degradation? | Recoverable trace on failure (where)? |
|---|---|---|---|---|

Any "no" here is a gap the same as a missing screenshot — record it as an Open Exception below, not a silent pass.

## Backend contract check (per API-nnn touched)
| API-nnn | Uses stored procedure(s)? | Swagger/OpenAPI matches contracts.md? | Frontend calls it via API only (no direct DB/service bypass)? |
|---|---|---|---|

## Database robustness check (per API-nnn/entity that touches a database)
| Code | Connection pooled (or exception written down)? | Released in guaranteed path (finally/using)? | Connection validated before use? | Transaction boundaries explicit? | Index/plan verified (engine's own plan tool)? |
|---|---|---|---|---|---|

Any "no" in either table above is a gap the same as a missing screenshot — record it as an Open Exception below, not a silent pass.

## Performance & Best Practices check (Performance & Best Practices Auditor — applies to any code touched, every convergence)
| File/class | OOP/SOLID verified in code? | Interfaces used at real boundaries? | Locking/isolation deliberate for the engine? | Connection pooling verified (not just declared)? | No N+1 / unbatched loop? | No blocking call on hot path? |
|---|---|---|---|---|---|---|

Same rule as the tables above: any blank/"no" here is a finding, not a pass. This auditor runs even when no other domain auditor does — it applies to any code at all, not only UI/API/DB-specific work.

## Revision log (append, never overwrite)
```
Rev 1 (YYYY-MM-DD) — X.X% (n/total)
```

## Open exceptions (rows left unresolved on purpose)
| Code | Reason | Approved by |
|---|---|---|

A feature is not done while any row above is unresolved without an entry in this table.
