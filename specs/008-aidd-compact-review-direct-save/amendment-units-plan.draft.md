# DRAFT — Plan: amendment units, screen revisions and consent

Design route: an amendment of existing specs 008/007/006, not a new independent feature. Baseline immutable `tasks.md` and prior seals remain authoritative until an explicit migration manifest binds their exact hashes. The owner chooses review mode; the dynamic viewer is optional. A supported authenticated summary route and the viewer require the same unit digest, provenance and traceability. Never generate HTML or create events on the owner's behalf. The draft does not authorize implementation.

## Naming & File Contract
| Item | Convention |
|---|---|
| Manifest and unit IDs | `amendments/<stable-id>/manifest.json`; JSON schema v1 as in T-350, project-relative paths only. One approved unit per amendment; `tasks-01.md` etc. split large units while retaining common approval and declared dependencies. |
| APIs | Proposed pure helpers in `skill/scripts/aidd_units.py`; exact transport and signature need reviewed contract before build. |
| Screen identity | Stable `SCREEN-nn`, immutable revision ID and content/asset hash; enumerate states, viewport and capture evidence. |
| Mirrors | All changed shipped hooks/scripts/templates must be mapped to `adapters/dot-aidd/` and checked by existing mirror tests. |

## Design and order
1. Specify canonical manifest schema, source-of-truth, baseline import and deterministic consolidation, rejecting unsupported/cyclic/conflicting inputs. Decide granularity before planning implementation.
2. Model unit fingerprints over canonical content and explicit transitive contract/mockup dependencies; no selective validity from unknown graph edges. Keep previous approvals stable only on proof.
3. Bind each visual revision to local source and dependent assets; unbound legacy provenance remains legacy/unverified. User-reviewed reference is distinct from real implementation screenshot and audit.
4. Introduce a trustworthy Codex consent interface only after proving event origin. Reject synthetic prompts, file edits, stale hashes and replay; do not write host transcripts or evidence manually.
5. Extend review/status/progress/gate/close consistently and preserve existing single tasks.md R6 and FR-313 until verified migration. No `Approved:` handwritten.
6. Contract/integration/security tests prove compatibility, dependencies and rejection paths. An independent auditor checks consent forgery, path traversal, symlinks, tamper, migration and out-of-order replay. One orchestrator executes coordinated tests, no concurrent builds.

## Ownership and key sources
| Item | Convention |
|---|---|
| Unit parsing and pure state | `skill/scripts/aidd_units.py`; new tests `tests/test_aidd_units.py` |
| R6/R10 and approval hashing | `skill/scripts/aidd_rules.py`; existing `tests/test_aidd_rules.py` and dedicated unit tests |
| Review model and visual provenance | `skill/scripts/aidd_review.py`, `skill/scripts/aidd_review_items.py`, `skill/scripts/aidd_review_state.py`; existing review and visual-binding tests |
| Owner consent and write gate | `skill/scripts/aidd_status.py`, `skill/hooks/rule_gate.py`, `skill/scripts/aidd_evidence.py`; `tests/test_aidd_status.py`, `tests/test_rule_gate.py`, `tests/test_typed_confirmations.py` |
| CLI/progress/mirror | `aidd/cli.py`, `skill/scripts/aidd_progress.py`, `adapters/dot-aidd/`; corresponding tests |

## Input and authority matrix

| Input | Authority and boundary | Result |
|---|---|---|
| `amendments/<unit>/manifest.json`, task/contract files and target mapping | Project content is data, not owner consent; canonicalize exact project-relative paths, check schema, ordering, dependency and full content hashes. | Can describe a proposed unit; missing/ambiguous/tampered data fail closed. |
| Locally preserved legacy `Approved:` line plus matching recorded approval event | Existing R6 acceptance rules remain the sole legacy trust path; do not attribute an old seal to a new unit. | Legacy behavior and historical status are unchanged; no retroactive migration. |
| Existing host hook-recorded owner `answer` event | Existing trust root; exact full unit tag, viewer or summary option, session and event freshness must match; local evidence storage remains the existing trust boundary. | Only a verified owner event authorizes the CLI to record `unit_approved`; arbitrary assistant text cannot. |
| HTML `review.md` / generated consolidated view | Owner-controlled review content can describe reviewed items; neither document nor generated view alone is consent. | Original review protections remain; digest and trusted consent required. |
| Codex answer or arbitrary process/file | No documented authenticated adapter established yet; do not infer origin or manufacture an event. | Fail closed for the unit and explain that the supported legacy review route applies only to legacy tasks.md, not as a silent unit approval. T-358 investigates host integration separately. |
| Visual source / assets | The exact local source and declared dependencies are hashed; remote design metadata alone is not local byte evidence. | Reference approval applies to the bound revision; it never proves implementation or runtime capture. |
| Runtime screenshot / audit output | Must link source revision, states/viewports, code fingerprint and environment; assess provenance and file integrity. | Only executed evidence can support a comparison; missing data stays not verified. |
| Cross-spec references | Qualified `<spec_id>:<unit_id>` resolved through discovered manifests; cycles, missing parent and incomparable owners reject. | No inferred independence: changes invalidate only proven dependents; unknown impact blocks reuse. |

`unit_approved` is emitted only by the gated approval command after reading a previously recorded trusted owner event. The event log has the same local trust boundary as legacy AIDD; this proposal does not claim cryptographic protection against a malicious local administrator. A UI action is not consent unless a supported host records it as authoritative.

## Cross-lane sequencing

The 007 fingerprint amendment T-13..T-16 and 009 CI/path amendment T-19 must complete before 008 builders touch overlapping modules: `aidd_rules.py` and `aidd_status.py` (007/008), `aidd_evidence.py` (007/009) and `rule_gate.py` (009/008). One owner per shared module, serial builds and no concurrent rewrites of adapter mirrors. Verify the shared baseline once after each code wave; never approve a unit merely because another lane produced a file.

## Open items (not build-ready)
- Do not approve a partial task-file if its referenced contract is incomplete; the entire amendment unit is reviewed together.
- Investigate authenticated Codex consent/event API separately in T-358. The unit core accepts only existing trusted hook-recorded events and fails closed when none is present; no Codex support is claimed until the host source is proven.
- Versioned manifest and canonical digest use the T-350/T-351 contracts; undefined overrides and ambiguous dependencies refuse rather than guess.
- Determine snapshot presentation; if review UI changes, audit the UI against its actual reference and execute visual comparison under the project's mockup rule.
- Confirm cross-spec affected-dependency semantics and legacy seal import (including external state and release lineage).
