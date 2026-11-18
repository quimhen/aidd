# Spec — Explicit bounded incremental graph refresh after a stale code miss

Risk: medium

## Minimum Requirements Checklist

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | AIDD CLI, local inspection and evidence boundaries | repo — batch-staging/aidd-optimization-20261113/README.md:7 | — |
| New development or modification of something existing? | Modification of the existing host spec, versioned unit | repo — batch-staging/aidd-optimization-20261113/README.md:7 | — |
| Does it involve an external service, API, or integration? | No external service; offline Python and local files only | repo — batch-staging/aidd-optimization-20261113/README.md:7 | — |
| Who is requesting it? (role/profile, not necessarily the name) | AIDD owner through the coordinating root agent | repo — batch-staging/aidd-optimization-20261113/README.md:7 | — |
| Dependencies on other modules or active developments? | Existing CLI/parser/mirror contracts; preserve preexisting edits | repo — batch-staging/aidd-optimization-20261113/README.md:7 | — |
| Business objective (1 sentence — what it achieves and why) | Reduce avoidable rework while preserving approval and proof boundaries | repo — batch-staging/aidd-optimization-20261113/README.md:7 | — |
| Expected visual fidelity level (if there's a mockup): exact \| functional behavior only | No GUI or mockup; inspect actual CLI outputs | repo — batch-staging/aidd-optimization-20261113/README.md:7 | — |

## Executive summary

- Objective: Explicit bounded incremental graph refresh after a stale code miss.
- Scope: only the files enumerated in this unit manifest; no B1 or installed skill update.
- Cost: 30 agent minutes, 60k tokens; 3 tasks.
- Risks: false confidence or changed compatibility; tests preserve prior ABI and separate structural proof from runtime behavior.
- Open decisions: owner task approval only; no undecided technical branch.

## Pipeline route

| Step | Status | Reason | Confirmation |
|---|---|---|---|
| -1 | run | Existing004/007 searched; no new spec | |
| 0 | run | Inspect CLI surface; no visual assets apply | |
| 1 | run | Map command/parser contracts; no GUI screens | |
| 1.5 | run | CLI entry/exit flow and error states defined in plan | |
| 2 | run | Requirements below and observed baseline | |
| 3 | run | Explicit source/test/file contracts | |
| 4 | run | Exact unit review package pending owner approval | |

## Visual debt

None; no SCREEN/GUI scope.

## Scope

- Included: the named unit only, with test-first targeted implementation.
- Excluded: production data, network, database, installed skills, unrelated source, approval and evidence writes, weakening regression policy.

## Functional requirements

| FR-nnn | Requirement | Cites |
|---|---|---|
| FR-370 | Opt-in refresh-on-miss preserves existing no-flag ABI. | plan.md |
| FR-371 | Only stale builtin-code miss triggers one registered incremental refresh. | plan.md |
| FR-372 | Reload/requery once; existing locks, timeout and debounce remain. | plan.md |
| FR-373 | Failures remain explicit uncertainty; no false absence/freshness. | plan.md |
| FR-374 | No refresh-all, Graphify, source execution or default hook refresh. | plan.md |

## Acceptance cases

| Case | Real data (id) | Expected | Edge? |
|---|---|---|---|
| AC-370-1 | Stale builtin code graph missing new function; opt-in flag | One incremental refresh and one reload/requery | no |
| AC-370-2 | No flag / fresh miss / stale hit | Zero refresh; old ABI preserved | yes |
| AC-370-3 | Refresh locked, timed out, failed or still missing | Bounded explicit uncertainty; no infinite retry or false freshness | yes |
| AC-370-4 | CLI flag on non-code graph / concurrent requests | Invalid usage refused / existing lock and debounce respected | yes |

## Verification

| # | Command | Expected | Covers | Tier |
|---|---|---|---|---|
| V-1 | `python -m unittest tests.test_aidd_graphs tests.test_graphs_auto tests.test_code_graph -v` | exit 0 | FR-370, FR-371, FR-372, FR-373, FR-374 | functional |
| V-2 | `python -m unittest tests.test_dot_aidd_mirror -v` | exit 0 | FR-370, FR-371, FR-372, FR-373, FR-374 | functional |

## Execution contract

One file owner per lane. Native AIDD graphs first, bounded reads and outputs. Mechanical operations use mapping/dry-run/apply/post-check. Builders run static checks only; coordinator executes RED before each body, then the union of checks once after source freeze. Preserve failures and exact inputs; no invented PASS or consent. No Graphify, database, Docker, external API, installed-skill update or B1SyncLink write. Do NOT modify approval/event logs, relax gates, change unrelated local edits, reinterpret presence as behavior, or reuse a DB result from container identity alone. Final full verification and required perf/audit of the host spec remain applicable at official close.

## Approval gate

Pending owner consent through the official unit review package. This file is not an approval. Historical base approval remains independent and unchanged. No production implementation before the exact unit is approved.

## V3 convergence delta — 2026-11-14

Official independent audit38082327a8254db7a430c042cfa37a55 found that removing --refresh-on-miss/--limit options could leave an empty required query and reach show/refresh. The fix is three guard lines after option removal, returning usage2 before dispatch. No graph refresh algorithm, shell boundary, cache, timeout or valid-query behavior changes. It is a confirmed medium convergence repair within this feature, not a new feature or approval of other scopes.

Existing123-test/23-subtest evidence remains historical baseline evidence before these three guard lines; it is not relabelled as execution of the new body. New focused RED against the original module was7FAIL/5PASS, and GREEN against the byte-identical staged new module was12PASS. All twelve cases mock show/refresh, cover malformed/empty options and valid dispatch, and execute no graph work. The independent fix review is PASS. Real logs, source before/after hashes and exact diff are included in this V3 package; no previous event/artifact was rewritten. Fresh current-scope audit and owner V3 approval remain required. The genuine V2 owner seal remains historical and is not reused. No B1 or installed-runtime change.

## V4 convergence delta — active refresh status

Official fresh audit80e25b8e245347d09ad6cc77eca322b6 identified that actual status running bypassed stale-only miss handling. The bounded fix reports explicit pending/not-confirmed-fresh for an opt-in builtin-code miss while another refresh is active, without starting a second refresh. Hits and no-flag behavior remain unchanged. The prior empty-query main() guard remains byte-equivalent at AST level; its12 focused cases are not rerun for a change confined to show().

New4-case tests exercise real status, OS guard, livePID lock and graph lookup, stubbing only registry/input hashes and refresh generation. Actual RED1FAIL/3PASS and GREEN4PASS are separately retained; no graph generator, DB or business test executes. Independent code review PASS is included. Existing123/23 and12-case results remain accurately contextual historical evidence, not relabelled runs of this new body. Fresh current unit audit and actual owner V4 approval are required; no V2/V3 seal is reused.
