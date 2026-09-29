# QA Audit — [feature name]

**Audited by:** [independent Auditor agent/person — never the same agent that implemented the PR being checked]

## Mapping ledger
| Code | Status | Evidence (file/class/resource id) | PR/Spec ref | Screenshot diff done? |
|---|---|---|---|---|
| SCREEN-01 | ✅ IMPLEMENTED \| ⚠️ PARTIAL \| ❌ MISSING \| 🔄 DIFFERENT | | | ☐ |
| COMP-001 | | | | ☐ (check on every screen it's used in) |
| CTL-001 | | | | ☐ |
| SCREEN-01-F01 | | | | ☐ |

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
