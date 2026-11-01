# DRAFT — Plan: unit verification, audit carry-over and consolidated close

## Naming & File Contract
| Item | Convention |
|---|---|
| Verification source | `specs/<spec-id>/amendments/<unit-id>/checks.md`, exact path must be present in the unit manifest `paths`; parse its `## Verification` with existing `rules.parse_verification`. |
| Unit verify CLI | `aidd verify <spec> --unit <id>`; without `--unit` existing behavior is unchanged. |
| Unit verify event | `unit_verify_run` with `spec`, `unit_id`, full unit digest, verify table hash, rows, output evidence hashes, scope and algorithm version; never count as spec-wide `verify_run`. |
| Unit audit evidence | Each `unit_audit` records actual independent auditor ID/domain, unit digest, rule version, explicit input digests, evidence hashes, outcome and a separately verified execution-environment identity. No owner-authored substitution for an auditor event. |
| Release close | Existing `aidd rules close <spec>` obtains a current owner-tagged close consent and validates every declared unit plus dependencies; it does not deploy. |

## Implementation constraints
1. Implement only after core unit manifest/hash/approval and 007 algorithm changes, with one owner of each shared module. Both unit verify and unit close touch `aidd_status.py`, so T-360 follows T-361; do not build concurrently.
2. A unit's checks file is an exact manifest input, not an inferred filename outside its folder. Validate resolved paths under project root and `rules.check_verification`. Missing, duplicate, changed, invalid or unapproved units block.
3. Store evidence in unit-scoped paths with output hashes. Hash both content and command/expected/inputs and check stability through execution; events are emitted through the existing evidence API, never manually. Unit result alone cannot mark spec-wide verify PASSED.
4. Existing code has no trusted environment attestation verifier. Until a separate reviewed implementation proves equivalence, execute every requested row; do not infer identity from a string or a hermetic flag, including multi-spec/wave and audit carry-over. Display why reuse is blocked. Preservation of historical evidence is not a new PASS.
5. `unit_audit` events must refer to a genuine independent auditor dispatch, exact declared inputs and evidence. If the current host cannot attest auditor origin or environment, treat it as not reusable and require a fresh independent audit; no audit event or evidence is forged.
6. Consolidated close resolves every declared unit and dependency, verifies seals/checks/audit matrix and owner's exact close consent; an unapproved/draft unit blocks rather than selecting its approved ancestor. Reject cycles, missing files, stale snapshots and ambiguous mappings. Do not assume user approved release merely by approving unit tasks.
7. Legacy specs without a unit manifest follow existing R6/R7/R10/close behavior, byte-for-byte where visible. The existing non-unit full verify remains available and separate.

## Open pre-build gap

The current hook records `subagent` dispatch/result metadata, not a unit-scoped `unit_audit` record. Before approving tasks T-360, T-362 or T-363, specify an authenticated, auditable recorder that binds a real independent reviewer, declared unit/dependency scope and evidence without allowing agents to invent events; otherwise retain a full independent audit fallback. No code or approval is authorized by this draft. T-361 remains independently reviewable after its prerequisites.

## Authority and sequencing
T-361 and T-360 both own `skill/scripts/aidd_status.py` and its mirror: same builder, serial waves. T-362 owns `skill/scripts/aidd_rules.py` and its mirror after 007; coordinate with unit-core T-351. T-363 is orchestrated after all code waves. Prototypes and visual capture are part of the separate navigator task, not fabricated here. No code, build or seal is authorized by this draft.
