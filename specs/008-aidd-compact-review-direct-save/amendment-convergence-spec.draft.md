# DRAFT — Unit verification, audit carry-over and consolidated close

DRAFT; no tasks or releases approved. This is a separately reviewable follow-up to the `amendment-units-*` core and fingerprint safety amendment of 007. The dynamic viewer is optional and its UI remains a separate draft; Codex consent transport remains unsupported until proven.

## Scope
Included: execute a selected unit's declared checks, preserve per-unit evidence and stale reasons; reuse independent auditor evidence only when identity, inputs, dependency closure and evidence integrity are established; close the entire declared set only after owner consent and all applicable units pass. Excluded: production deploy, fake owner or auditor events, guessing external environment identity, reusing unstructured legacy audits, or enabling DB/network caches without a separately approved trusted verifier.

## Functional requirements
| FR-nnn | Requirement | Cites (SCREEN-XX-Fnn / CTL-nnn / API-nnn) |
|---|---|---|
| FR-360 | Each unit has a checks file registered among manifest paths; `aidd verify <spec> --unit <id>` executes only its rows and records a versioned unit-specific result without replacing aggregate spec verification. | `skill/scripts/aidd_status.py:1769` |
| FR-361 | A retained domain audit may be reused only when a prior independently recorded auditor, exact unit/dependency scope, rule version, input digests, evidence bytes and execution environment identity all match; unknown or legacy unstructured provenance is stale, not silently passed. | `skill/scripts/aidd_rules.py:1413` |
| FR-362 | Consolidated close requires all declared units and their dependencies to have valid approvals, executed checks and required domain audits; identify missing/ambiguous evidence, require the actual owner's tagged close consent, preserve existing legacy close semantics. No release/deploy is performed. | `specs/007-aidd-review-html-close-gate/spec.md:159` |
| FR-363 | Unit verification executes the requested rows if environment identity is not independently verified, even with a hermetic label; `--full` always executes; audit/verify reuse cannot trust matching command or owner-authored metadata alone. | `specs/007-aidd-review-html-close-gate/amendment-01-fingerprint-spec.draft.md` |

## Acceptance cases
| Case | Real data (id) | Expected | Edge? |
|---|---|---|---|
| AC-360 | A10 passed and A11 declared without approval | A11 checks cannot run as approved and spec close refuses; A10 evidence remains historical. | yes |
| AC-361 | Two units use a shared contract; one file changes | Only an audit with provably disjoint inputs can remain valid; dependent or unknown audits require review. | yes |
| AC-362 | Unit check claims hermetic but has no verified DB/environment identity | Execute when requested; do not mark `REUSED` or `ROUND-REUSED`. | yes |
| AC-363 | All units passing but no current actual owner close event | Consolidated close refuses; no event or seal is manufactured. | yes |
| AC-364 | Legacy spec with no manifest | Existing verify/close outputs and approval semantics stay unchanged. | yes |

## Verification
After implementation: `python -m unittest tests.test_aidd_unit_verify tests.test_aidd_unit_audit tests.test_aidd_unit_close tests.test_aidd_unit_convergence` and existing gate, review and mirror tests; one coordinated full-suite round and independent audit. No runtime PASS is asserted by this draft.
