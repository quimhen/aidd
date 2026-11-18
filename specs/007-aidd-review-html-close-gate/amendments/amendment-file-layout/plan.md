# Plan — Read legacy amendment-NN-tasks.md without changing batch approval identity

## Naming & File Contract

| Item | Convention |
|---|---|
| Functions and files | snake_case Python; preserve public ABI |
| Types/classes | PascalCase; no production class required |
| Target ownership | One lane per file; mirrors generated, not hand edited |

## Entry route

CLI input → existing parser → targeted read-only operation → bounded explicit verdict. Offline failures never fabricate PASS, consent or freshness.

## Exact implementation contract

Only amendment_file(d,nn) and its bounded discovery error text change. Current canonical precedence remains. New fallback names: amendment-06-tasks.md, amendment-6-tasks.md, amendment-006-tasks.md. If multiple supported candidates exist, compare raw bytes; all equal permits canonical preference, any difference refuses. Never create an alias/batch/rename. Candidate must be a regular file inside spec directory, no escaping symlink. A dry-run still reads Verification from root spec.md and performs no verification/evidence recording.

No change to plan(), prove(), row_env_id, Inputs/Scope, Regression:always, reuse evidence validation, base/unit approval hashes or audited coverage. Files are not content-authority for skipped verification: they only force affected executions. This fixes naming compatibility, not missing historical baseline.

## Execution contract

One file owner per lane. Native AIDD graphs first, bounded reads and outputs. Mechanical operations use mapping/dry-run/apply/post-check. Builders run static checks only; coordinator executes RED before each body, then the union of checks once after source freeze. Preserve failures and exact inputs; no invented PASS or consent. No Graphify, database, Docker, external API, installed-skill update or B1SyncLink write. Do NOT modify approval/event logs, relax gates, change unrelated local edits, reinterpret presence as behavior, or reuse a DB result from container identity alone. Final full verification and required perf/audit of the host spec remain applicable at official close.

## Approval gate

Pending owner consent through the official unit review package. This file is not an approval. Historical base approval remains independent and unchanged. No production implementation before the exact unit is approved.
