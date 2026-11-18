# Spec — Read legacy amendment-NN-tasks.md without changing batch approval identity

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

- Objective: Read legacy amendment-NN-tasks.md without changing batch approval identity.
- Scope: only the files enumerated in this unit manifest; no B1 or installed skill update.
- Cost: 22 agent minutes, 50k tokens; 3 tasks.
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
| FR-980 | Read canonical and reverse legacy amendment task filenames. | plan.md |
| FR-981 | Different candidate contents refuse ambiguity without mutating any file. | plan.md |
| FR-982 | Keep batch discovery and historical approval identity unchanged. | plan.md |
| FR-983 | Keep root Verification and all proof/reuse/DB rules unchanged; no log adoption. | plan.md |

## Acceptance cases

| Case | Real data (id) | Expected | Edge? |
|---|---|---|---|
| AC-980-1 | Existing tasks-amendment-06.md or reverse amendment-06-tasks.md only | Read existing file without creating any new batch | no |
| AC-980-2 | Both forms contain equal bytes / differing bytes | Canonical preferred / ambiguity refused | yes |
| AC-980-3 | Names6/06/006, missing file, escaping symlink, malformed declaration | Existing canonical behavior retained; unsafe/unknown refused | yes |
| AC-980-4 | Historical approval and root Verification before/after dry-run | Approval bytes/hash unchanged; no legacy row omitted or external log adopted | yes |

## Verification

| # | Command | Expected | Covers | Tier |
|---|---|---|---|---|
| V-1 | `python -m unittest tests.test_amendment_file_layout tests.test_verify_amendment -v` | exit 0 | FR-980, FR-981, FR-982, FR-983 | functional |
| V-2 | `python -m unittest tests.test_dot_aidd_mirror -v` | exit 0 | FR-980, FR-981, FR-982, FR-983 | functional |

## Execution contract

One file owner per lane. Native AIDD graphs first, bounded reads and outputs. Mechanical operations use mapping/dry-run/apply/post-check. Builders run static checks only; coordinator executes RED before each body, then the union of checks once after source freeze. Preserve failures and exact inputs; no invented PASS or consent. No Graphify, database, Docker, external API, installed-skill update or B1SyncLink write. Do NOT modify approval/event logs, relax gates, change unrelated local edits, reinterpret presence as behavior, or reuse a DB result from container identity alone. Final full verification and required perf/audit of the host spec remain applicable at official close.

## Approval gate

Pending owner consent through the official unit review package. This file is not an approval. Historical base approval remains independent and unchanged. No production implementation before the exact unit is approved.
