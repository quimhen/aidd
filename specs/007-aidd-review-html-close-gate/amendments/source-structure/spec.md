# Spec — Detect source stubs/duplicate definitions and report structural warnings

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

- Objective: Detect source stubs/duplicate definitions and report structural warnings.
- Scope: only the files enumerated in this unit manifest; no B1 or installed skill update.
- Cost: 35 agent minutes, 70k tokens; 4 tasks.
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
| FR-970 | Inspect explicit Python AST without executing it. | plan.md |
| FR-971 | Detect direct lexical duplicate definitions and executable stubs. | plan.md |
| FR-972 | Distinguish overload/abstract/Protocol/property declarations without claiming behavior. | plan.md |
| FR-973 | Unreadable/syntax states fail unknown, not clean. | plan.md |
| FR-974 | Progress carries separate structural warnings without changing task_state/impl_pct or evidence stages. | plan.md |
| FR-975 | No whole-tree scan, DB, services, hook gate or installed write. | plan.md |

## Acceptance cases

| Case | Real data (id) | Expected | Edge? |
|---|---|---|---|
| AC-970-1 | 139-byte Python fixture: real definition followed by same-name NotImplementedError | Duplicate line pair and executable stub, exit1 | yes |
| AC-970-2 | Distinct classes / overload implementation / property setter / abstract declarations | Declarations distinguished; no false duplicate or functional PASS | yes |
| AC-970-3 | Unreadable, SyntaxError or source that raises if imported | Unknown exit2; inspected source never imported | yes |
| AC-970-4 | Existing progress delete/alias/marked/present fixtures | Legacy states and impl_pct unchanged; structure reported separately | yes |

## Verification

| # | Command | Expected | Covers | Tier |
|---|---|---|---|---|
| V-1 | `python -m unittest tests.test_aidd_source_shape tests.test_aidd_progress tests.test_progress_resolution -v` | exit 0 | FR-970, FR-971, FR-972, FR-973, FR-974, FR-975 | functional |
| V-2 | `python -m unittest tests.test_dot_aidd_mirror -v` | exit 0 | FR-970, FR-971, FR-972, FR-973, FR-974, FR-975 | functional |

## Execution contract

One file owner per lane. Native AIDD graphs first, bounded reads and outputs. Mechanical operations use mapping/dry-run/apply/post-check. Builders run static checks only; coordinator executes RED before each body, then the union of checks once after source freeze. Preserve failures and exact inputs; no invented PASS or consent. No Graphify, database, Docker, external API, installed-skill update or B1SyncLink write. Do NOT modify approval/event logs, relax gates, change unrelated local edits, reinterpret presence as behavior, or reuse a DB result from container identity alone. Final full verification and required perf/audit of the host spec remain applicable at official close.

## Approval gate

Pending owner consent through the official unit review package. This file is not an approval. Historical base approval remains independent and unchanged. No production implementation before the exact unit is approved.
