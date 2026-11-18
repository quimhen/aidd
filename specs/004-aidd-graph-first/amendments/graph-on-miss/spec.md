# Spec — Graph V5 corrective adoption of isolated raw-hash prototype

AIDD intake: AMENDMENT — existing 004 graph-on-miss, corrective adoption proposal only.
Risk: high

## Executive summary
- **Objective:** Resolve the current Graph V4 security/functional audit by hashing the exact raw bytes the parser reads, without running repository clean filters.
- **Scope:** Adopt the pre-existing isolated one-argument prototype and two-case test plus mandatory legacy graph-cache generation repair, mirror mechanically, and prepare a coherent V5 proof/context retaining earlier graph-on-miss behavior.
- **Cost:** Three tasks, 28 agent minutes / 45k tokens, three sequential waves.
- **Risks:** Transitive proof closure and shared kernel identity can stale owner seals; pin actual dependencies and obtain fresh approvals/audits.
- **Open decisions:** Genuine corrective task approval, backend-only visual-step confirmations and eventual exact V5 context owner seal. No historical gate is retroactively asserted.

## Minimum Requirements Checklist
| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | AIDD graph freshness and parse cache | repo — skill/scripts/code_graph.py:197 | |
| New development or modification of something existing? | Corrective adoption of existing isolated draft; Graph V4 remains failed | repo — specs/004-aidd-graph-first/audit-reports/8befd8ecb770453caa2952d8b2920cd2.json | |
| Does it involve an external service, API, or integration? | Local Git argv only; no remote service or DB | repo — skill/scripts/code_graph.py:147 | |
| Who is requesting it? | Repository owner; parent requests proposal only | user — "Autorizar adopción correctiva" | Owner corrective approval |
| Dependencies on other modules or active developments? | Graph V4 plus current five-file 4b kernel pins in dependency-pins.json | repo — specs/004-aidd-graph-first/amendments/graph-on-miss/manifest.json | |
| Business objective (1 sentence — what it achieves and why) | Prevent project filter execution and stale graph lookup | repo — specs/004-aidd-graph-first/audit-reports/8befd8ecb770453caa2952d8b2920cd2.json | |
| Expected visual fidelity level (if there is a mockup) | Backend CLI only; no screen or mockup | user — "Autorizar adopción correctiva" | Confirm visual steps 0/1/1.5 not applicable |

## Pipeline route
| Step | Status | Reason | Confirmation |
|---|---|---|---|
| -1 | run | Existing native graph queried read-only and V4 inspected; no new feature duplication | repo — specs/004-aidd-graph-first/amendments/graph-on-miss/manifest.json |
| 0 | waived | No visual surface; owner confirmation required | user — "Autorizar adopción correctiva" |
| 1 | waived | No visual surface; owner confirmation required | user — "Autorizar adopción correctiva" |
| 1.5 | waived | No visual surface; owner confirmation required | user — "Autorizar adopción correctiva" |
| 2 | run | Corrective adoption and native graph generation migration scope presented for confirmation | user — "Autorizar adopción correctiva" |
| 3 | run | This plan is an approval proposal, not authority to implement | |
| 4 | run | Actual current task approval and fresh independent R5 required | |

## Scope
- Included: code_graph.file_shas one-argv --no-filters adoption, its canonical adapter mirror and existing two-case regression; earlier V4 graph-on-miss/empty-query/running-state behavior frozen and included in the new proof closure.
- Excluded: edits to 4b kernel, schema-format changes or evidence-kernel algorithm changes, global rules, Graphify, B1, DB, installations, merges, owner/audit state mutations and approval transport repair.

## Functional requirements
| FR-nnn | Requirement | Cites (SCREEN-XX-Fnn / CTL-nnn / API-nnn) |
|---|---|---|
| FR-375 | file_shas(root, rels) invokes git hash-object --no-filters --stdin-paths and otherwise preserves byte-identical behavior, including fallback and error handling | API-GR01 |
| FR-379 | Advance code_graph.EXTRACTOR_VERSION from3 to4 and salt builtin-code freshness inputs with current schema/extractor generation; old filtered-hash caches and stamps must rebuild, even if their stored hash equals future raw file bytes. Missing generation must remain stale; non-code/external providers unchanged | API-GR03 |
| FR-376 | Applicable real clean filter never executes; different raw parsed source invalidates cached nodes even if configured filter returns constant output | API-GR01 |
| FR-377 | Retain FR-370..374 behaviors and all original V4 targets/proofs in a fresh V5 closure, with raw source/mirror/test and complete transitive execution inputs added | API-GR02 |
| FR-378 | Prototype RED/GREEN/code-audit remain historical exact-input evidence; no backdated prebuild review, approval or current proof fabricated | API-GR02 |

## Acceptance cases
| Case | Real data (id) | Expected | Edge? |
|---|---|---|---|
| AC-375 | Actual audit8befd8ecb770453caa2952d8b2920cd2 clean-filter defect | Marker absent and digest equals raw Git blob bytes; exact two-case prototype proof preserved | yes |
| AC-376 | Existing graph-on-miss V4 empty-query and active-refresh-lock cases | No unintended dispatch; pending remains uncertain; default unchanged | yes |
| AC-379 | Legacy extractor3 cache contains ASTA with stored hash of future rawB; current source becomesB | First generation4 build parsesB, no legacy reuse; next unchanged generation4 run can reuse; old builtin-code stamp becomes stale without watched file mutation | yes |
| AC-377 | Current V4 digest b5411e5ce4cfd69aff5b185b961a0a5152ef926f8fc689132ad94bba4aa82833 | No old seal reused; V5 requires genuine fresh owner and independent functional/security audit | yes |

## Verification
| # | Command | Expected | Covers | Tier |
|---|---|---|---|---|
| V-GR1 | python -B -m unittest discover -s tests -p test_code_graph_raw_hashes.py | exit 0 | FR-375, FR-376, FR-379 | functional |
| V-GR2 | python -B -m unittest discover -s tests -p test_code_graph.py | exit 0 | FR-375 | functional |
| V-GR3 | python -B -m pytest -q -p no:cacheprovider tests/test_aidd_graphs.py tests/test_aidd_graphs_empty_query.py tests/test_aidd_graphs_running_state.py | exit 0 | FR-377 | functional |
| V-GR4 | python -B -m pytest -q -p no:cacheprovider tests/test_graphs_auto.py | exit 0 | FR-377 | functional |

## Execution and evidence
This is a proposal, not current execution. Root runs each listed targeted suite once only if changed dependency identity makes existing exact-input proof ineligible. If authoritative 4b immutable-proof qualification accepts historical exact inputs, record that actual decision and do not rerun; existence/counts alone never qualify. No skips count as proof of Git behavior. A mismatching/missing prerequisite fails closed. Final full host-spec verification/required performance/independent close remain requirements; no broad suite is launched by this proposal author.

## Contracts
API-GR01: file_shas(root, rels) -> dict[str,str], signature unchanged; _git(root,args,data=None) unchanged.
API-GR03: Existing schema format stays1; extractor generation becomes4. Freshness stamp identity includes builtin-code generation; does not depend on 4b EVIDENCE_ALGORITHM.
API-GR02: V5 manifest retains V4 membership plus the explicit changes and pins; canonical unit tooling computes actual dependency closure/context identity later, never this proposal's invented digest.

## Capacity & test budget
RAM: 1 GB
Heavy runs at a time: 1
Round budget: 120 s
Not verified: No runtime or DB executed for this proposal; production latency and unrelated full-suite behavior remain unverified.

| # | Tier | Est. s | Budget s | Data scale | Scale justification |
|---|---|---|---|---|---|
| V-GR1 | functional | 2 | 15 | minimal | Four focused cases: two real Git filters plus legacy-cache/stamp migration |
| V-GR2 | functional | 10 | 30 | minimal | Existing focused graph tests |
| V-GR3 | functional | 20 | 60 | minimal | Existing graph lifecycle/dispatch tests |
| V-GR4 | functional | 5 | 15 | minimal | Existing auto registry tests |

## Corrective migration evidence (proposal only)
Read-only inspection found no automatic producer module hash or 4b EVIDENCE_ALGORITHM guard in native graph caches. code_graph.py lines867..872 checks only schema/extractor; lines922..944 reuse equal hashes. Main and isolated prototype both retain extractor3. aidd_graphs.py lines405..426 hashes only watched path/hash and lacks producer generation. Therefore a filtered legacy hash can equal future raw bytes while retaining stale AST, and an installed producer outside a consumer watch cannot invalidate that stamp by itself. FR-379 is required before adoption approval, not deferred to a later defect cycle. No source or test execution was performed for this diagnosis.

## Actual corrective adoption authority
user — "Autorizar adopción correctiva"
Native callback call_2a370bc521364f738baf74a52497ff02; exact tasks6e7dec9276b7. Literal native answer authorizes this isolated corrective adoption and backend visual waivers, not installation, original GraphV4 seal, or final GraphV5 owner context. Historical implementation is not backdated as pre-approved.

## V5 retained graph-on-miss contracts
FR-370: opt-in refresh-on-miss preserves no-flag ABI. FR-371: only stale builtin-code miss triggers one registered incremental refresh. FR-372: one reload/requery; preserve locks, timeout/debounce. FR-373: explicit uncertainty on failures/running refresh, never false absence/freshness. FR-374: no refresh-all, Graphify, repository source execution or default hook refresh. Empty-query and active-running corrections remain present. Historical V4 specification/plan/tasks/manifest are preserved byte-for-byte under the declared historical-v4 proof directory, not relabelled as V5 execution.

## Final V5 context workflow
This is corrective adoption of actual isolated code, not retrospective pre-approval. The genuine task6e7dec9276b7 consent authorizes isolated work and backend waivers. This exact V5 unit requires a new real owner seal. Proposed-target payloads and context-lock bind final code/test bytes; active Main targets remain their baseline until real V5 owner consent. Native functional/security unit audit on final Main occurs after controlled source integration and before installation. The existing Root source review is independent code review, not a fabricated official unit_audit PASS. Other unit seals and historical V4 failure are not edited.
