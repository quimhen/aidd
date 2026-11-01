# DRAFT — Amendment units, visual revisions and host consent (008 / 007 / 006)

DRAFT: no approval; no code is authorized by this artifact. Candidate amendment to 008 (review and FR-313), coordinated with 007 (R6/R10) and 006 (trusted interaction evidence). See those specs before merging. The user requested numbered independent amendments, screen versions, and avoiding repeated approvals. Design choices below remain proposed until owner review; no fictitious user quotes.

## Executive summary
- Objective: approve independently reviewable change units while preserving valid prior approvals and tracing screen versions.
- Scope: ordered unit manifest, screen revision bindings, consent transport and legacy migration; verification re-use is a separate coordinated workstream.
- Cost: provisional 105 min critical path / 765k tokens; 8 tasks in 5 waves, subject to independent planning audit.
- Risks: missing dependency or forged consent yields an unsafe approval; fail closed, preserve provenance and test host boundaries.
- Open decisions: Codex authenticated transport is excluded from the core and deferred as T-358; review presentation is in the separate navigator draft. A unit is an amendment, and large task files share its approval.

## Scope
Included: an immutable approved unit identity, its ordered parents and dependencies, stable task IDs, visual revision provenance, owner-authenticated consent, legacy compatibility and a generated consolidation view. Excluded: deploy to PRD, rewriting SQL migrations, retroactive fabricated approvals, automatic approval of owner decisions, and treating a mockup approval as implementation validation.

## Functional requirements
| FR-nnn | Requirement | Cites (SCREEN-XX-Fnn / CTL-nnn / API-nnn) |
|---|---|---|
| FR-350 | An amendment unit has immutable approved content, stable ID, deterministic sequence, explicitly cited dependencies, task file(s), contracts and snapshots; dependency ambiguity blocks approval. | specs/007-aidd-review-html-close-gate/spec.md:126 |
| FR-351 | Approve only the owner-reviewed delta through a trusted event tied to unit ID and digest; editing an approved unit or a dependency invalidates affected units, not unrelated units, with conservative full fallback for unknown impact. | specs/008-aidd-compact-review-direct-save/spec.md:76 |
| FR-352 | Consolidated spec is a reproducible read-only view with provenance, never a source of new consent; duplicate IDs, missing parents, cycles and incompatible overrides block it. | specs/003-aidd-interaction-evidence/spec.md:92 |
| FR-353 | Each screen keeps a stable code with version, source/hash and declared dependent assets, states, roles and viewport coverage; owner approval, real capture/comparison and closing audit remain separate evidence. Shared UI changes invalidate impacted screenshots. | skill/scripts/aidd_review.py:574 |
| FR-354 | Codex user consent is accepted only from an authenticated authoritative event source bound to a session, owner, exact unit digest and freshness; ordinary assistant text/files cannot mint consent. If unavailable, refuse and explain; never forge events. | specs/006-aidd-phased-audits-attribution/spec.md:56 |
| FR-355 | Existing single-file approval/review data retain exact legacy semantics; migration imports only verifiable historical seals, never approves drafts, is deterministic and reversible before activation. | skill/scripts/aidd_rules.py:1352 |
| FR-356 | The dynamic viewer is optional for owner approval. A supported authenticated summary route can approve the same exact unit and full digest without opening HTML; both routes preserve equivalent authorization, provenance, staleness and audit requirements. Existing FR-313 remains valid for legacy. No unsupported Codex channel is invented. | specs/008-aidd-compact-review-direct-save/spec.md:76 |

## Acceptance cases
| Case | Real data (id) | Expected | Edge? |
|---|---|---|---|
| AC-350 | F21 baseline A10 and draft A11 | A11 not approved by A10 seal; editing an unrelated unit does not invalidate A10 when independence is proven. | yes |
| AC-351 | P07 T-118 and a shared contract | A unit-only correction requires consent for its new digest; a contract edit invalidates all declared dependents. | yes |
| AC-352 | Codex exact selection versus agent-written file | A trusted owner event can authorize only its target; forged assistant text and stale tags are refused. | yes |
| AC-353 | screen fixture sample-124 two revisions plus changed shared shell | Mockup approval is not execution evidence; affected captures are stale, unaffected ones remain valid only with proven dependency. | yes |
| AC-354 | Old spec with existing Approved line and no units | Legacy approvals behave byte-for-byte as before; no historical approval is invented during migration. | yes |
| AC-355 | Duplicate task IDs, cyclic dependency, changed asset, unknown dependency | Refuse approval/reuse with a specific reason; never assume independence. | yes |
| AC-356 | Same unit reviewed in viewer or by authenticated summary on a supported host | Both require the same full digest, dependency state, owner consent and audit trail; summary works without HTML. Unsupported host fails closed and never fabricates consent. | yes |

## Verification
Commands to be finalized after tests exist: targeted unittest suites of rules, review, rule gate, progress, host consent and visual binding, followed by one coordinated full suite. No external-state-dependent verification is cached without environment identity.
