# DRAFT — Tasks: amendment units, screen revisions and consent

DRAFT ONLY. Estimates and task boundaries are provisional; no user approval and no implementation permission. Existing approved `tasks.md` remains unchanged.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-350 | FR-350, FR-352 | `skill/scripts/aidd_units.py` | LOGIC | | | Unlisted modules; no manual approvals |
| T-351 | FR-351, FR-355 | `skill/scripts/aidd_rules.py` | LOGIC | | | Unlisted modules; no manual approvals |
| T-352 | FR-353, FR-356 | `skill/scripts/aidd_review.py` | LOGIC | | | Unlisted modules; no manual approvals |
| T-353 | FR-354, FR-356 | `skill/scripts/aidd_status.py` | LOGIC | | | Unlisted modules; no manual approvals |
| T-354 | FR-351, FR-354 | `skill/hooks/rule_gate.py` | LOGIC | | | Unlisted modules; no manual approvals |
| T-355 | FR-352, FR-355 | `skill/scripts/aidd_progress.py` | LOGIC | | | Unlisted modules; no manual approvals |
| T-356 | FR-350, FR-351, FR-352, FR-353, FR-354, FR-355 | `tests/test_aidd_units_integration.py` | LOGIC | | | Unlisted modules; no manual approvals |
| T-357 | FR-350, FR-355 | `tests/test_dot_aidd_mirror.py` | LOGIC | | | No changes to production logic or package metadata |

## Per-task detail

### T-350 — Canonical manifest and ordered resolution
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC
- Size: ~150 changed lines; split into separate approved tasks if this bound cannot be met.
**Estimate**
- Agent min: 20
- Human ref hours: 1
- Tokens (est): 95k
- Agent role: builder
- Model tier: high
**Detail**
- **Goal:** Canonical manifest and ordered resolution.
- **Cites:** FR-350, FR-352
- **Depends on:** none
- **Read first:** `skill/scripts/aidd_rules.py:1352 and skill/scripts/aidd_review.py:627`.
- **Files to change:** create `skill/scripts/aidd_units.py`, create `tests/test_aidd_units.py`, and create the byte-identical shipped mirror `adapters/dot-aidd/scripts/aidd_units.py` using a scripted copy and hash post-check. Do not alter unrelated paths.
- **Naming contract:** Use UTF-8 JSON schema version 1; required keys are exactly `schema_version`, `spec_id`, `unit_id`, `sequence`, `parents`, `paths`, `targets`; Spec IDs and unit IDs match `[A-Za-z0-9][A-Za-z0-9_-]{0,127}` (numeric legacy spec IDs are valid); sequence is a positive non-boolean integer; parents are unique qualified strings `<spec_id>:<unit_id>`; paths and targets are arrays of unique project-relative strings. Define `UnitManifest` immutable record with schema_version:int, spec_id:str, unit_id:str, sequence:int, parents:tuple[str,...], paths:tuple[str,...], targets:tuple[str,...]; expose `load_unit(path: Path, project_root: Path) -> UnitManifest`, `discover_units(project_root: Path) -> tuple[UnitManifest,...]` and `resolve_units(units: Sequence[UnitManifest]) -> tuple[UnitManifest,...]`.
- **Behaviour:** Read at most 1 MiB of UTF-8 JSON; discover unit manifests under `specs/<spec_id>/amendments/<unit_id>/manifest.json` across the project, including drafts, and refuse any unit directory without a manifest. Check manifest IDs against their containing directory, canonicalize paths under project root and reject unknown schema/keys, absolute or escaping paths, duplicate `(spec_id, unit_id)` or sequences within a spec, missing qualified parents and cycles. Resolve parents before children, then by `(sequence, spec_id, unit_id)` deterministically; never write files or approvals.
- **Tests first:** Valid reordered input yields identical order, including qualified cross-spec parents and numeric legacy spec ID `007-aidd-review-html-close-gate`; unit ID A11 in two different specs is valid. Missing manifest or qualified parent, duplicate ID/sequence within one spec, cycle, path traversal, symlink escape and oversized input raise a documented ValueError.
- **Verify:** `python -m unittest tests.test_aidd_units` -> exit 0, all tests passed; orchestrator additionally runs `python -m unittest tests.test_dot_aidd_mirror` -> exit 0 after all mirrors.
- **Do NOT:** manually write approval/evidence, trust unverified host text, remove legacy enforcement, touch unlisted files, execute deploy, or create databases by hand.
- **Done when:** cited acceptance cases and exact verification commands pass, with output saved; independent audit remains a separate coordinated step.
- **Open questions:** none

### T-351 — Unit hashes and legacy gates
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC
- Size: ~150 changed lines; split into separate approved tasks if this bound cannot be met.
**Estimate**
- Agent min: 20
- Human ref hours: 1
- Tokens (est): 95k
- Agent role: builder
- Model tier: high
**Detail**
- **Goal:** Unit hashes and legacy gates.
- **Cites:** FR-351, FR-355
- **Depends on:** T-350
- **Read first:** `skill/scripts/aidd_rules.py:1352 and tests/test_aidd_rules.py:308`.
- **Files to change:** `skill/scripts/aidd_rules.py`, `tests/test_aidd_unit_hash.py`; shipped adapter mirror: `adapters/dot-aidd/scripts/aidd_rules.py`. If required by package mapping and absent, stop; no unrelated paths.
- **Naming contract:** Expose `unit_approval_hash(unit: UnitManifest, project_root: Path) -> str`; return full 64-hex SHA-256 over versioned canonical JSON (UTF-8, sorted keys, compact separators), project-relative dependency paths sorted lexically and each dependency's SHA-256. Preserve existing `approval_hash(tasks_text)` signature and bytes; UI may display a prefix but stores and compares the full digest.
- **Behaviour:** Bind unit ID, full parent-unit digests and resolved project-relative paths plus SHA-256 content per dependency using unambiguous length-delimited fields; reject missing, duplicate, escaping or unreadable inputs; preserve existing single-file behavior and evidence event semantics. Do not treat unrelated file as dependency.
- **Tests first:** Different unit content or declared dependency changes hash; unrelated file does not; legacy fixtures produce same preexisting hashes; missing or unresolvable dependency fails closed.
- **Verify:** `python -m unittest tests.test_aidd_unit_hash` -> exit 0, all tests passed; orchestrator additionally runs `python -m unittest tests.test_dot_aidd_mirror` -> exit 0 after all mirrors.
- **Do NOT:** manually write approval/evidence, trust unverified host text, remove legacy enforcement, touch unlisted files, execute deploy, or create databases by hand.
- **Done when:** cited acceptance cases and exact verification commands pass, with output saved; independent audit remains a separate coordinated step.
- **Open questions:** none

### T-352 — Screen revisions and dependency binding
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC
- Size: ~150 changed lines; split into separate approved tasks if this bound cannot be met.
**Estimate**
- Agent min: 20
- Human ref hours: 1
- Tokens (est): 95k
- Agent role: builder
- Model tier: high
**Detail**
- **Goal:** Screen revisions and dependency binding.
- **Cites:** FR-353, FR-356
- **Depends on:** T-350, T-351
- **Read first:** `skill/scripts/aidd_review.py:574`, `skill/scripts/aidd_review.py:1388`, `tests/test_visual_review_binding.py:33`, and `aidd/cli.py:169`.
- **Files to change:** `skill/scripts/aidd_review.py`, `tests/test_visual_unit_binding.py`; shipped adapter mirror: `adapters/dot-aidd/scripts/aidd_review.py`. If required by package mapping and absent, stop; no unrelated paths.
- **Naming contract:** Expose `visual_revision_binding(spec_dir: Path, revision: Mapping[str, object]) -> str`; required keys are exactly `screen_id`, `revision_id`, `source`, `assets`, `states`, `viewports`, each ID/source a nonempty string and the three arrays unique strings. Return full SHA-256 of canonical JSON and the source/assets' exact byte hashes; viewports use `WIDTHxHEIGHT` positive integers.
- **Behaviour:** Resolve every declared source beneath project root; reject missing, external, escape or altered assets; preserve `_visual_binding` semantics for old audits; do not infer app capture from reference approval. Extend review parser to accept `aidd review <spec> --unit <id> --summary`, rendering only that resolved unit's objective, scope, stable ID, full 64-hex digest, parents, targets, visual revision hashes, risks and open decisions; no write or approval. A missing unit or inconsistent graph exits 1 with a specific error. Review without `--unit` remains byte-compatible.
- **Tests first:** screen fixture sample-124 v1 unchanged after unrelated v2 file; a changed declared image or shell asset invalidates dependent revision; missing asset blocks; `--unit <id> --summary` prints the selected unit and full digest only, no event or file write; a nonexistent unit returns 1; legacy single snapshot and review output remain unchanged.
- **Verify:** `python -m unittest tests.test_visual_unit_binding` -> exit 0, all tests passed; orchestrator additionally runs `python -m unittest tests.test_dot_aidd_mirror` -> exit 0 after all mirrors.
- **Do NOT:** manually write approval/evidence, trust unverified host text, remove legacy enforcement, touch unlisted files, execute deploy, or create databases by hand.
- **Done when:** cited acceptance cases and exact verification commands pass, with output saved; independent audit remains a separate coordinated step.
- **Open questions:** none

### T-353 — Trusted host consent adapter
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC
- Size: ~150 changed lines; split into separate approved tasks if this bound cannot be met.
**Estimate**
- Agent min: 20
- Human ref hours: 1
- Tokens (est): 95k
- Agent role: builder
- Model tier: high
**Detail**
- **Goal:** Trusted host consent adapter.
- **Cites:** FR-354, FR-356
- **Depends on:** T-350, T-351
- **Read first:** `skill/scripts/aidd_status.py:1234 and specs/008-aidd-compact-review-direct-save/spec.md:76`.
- **Files to change:** `skill/scripts/aidd_status.py`, `tests/test_aidd_codex_consent.py`; shipped adapter mirror: `adapters/dot-aidd/scripts/aidd_status.py`. If required by package mapping and absent, stop; no unrelated paths.
- **Naming contract:** Expose `trusted_unit_consent(root: Path, session: str, unit_id: str, digest: str, since: float) -> Mapping[str, object] | None`; construct exact `[unit:<unit_id>:<64-hex-digest>]` and query existing authenticated hook-recorded `ev._answer_event` for topic `approv|aprob`, the exact offered and selected answer `Aprobar con resumen`, and that tag. The recorded question must contain the exact generated unit summary and the owner option list must explicitly offer that label. The unit viewer route remains unsupported until the separate UI work proves a trusted review; preserve the current legacy viewer unchanged. Never infer consent from a generated file. Extend `cmd_approve(spec_arg, unit_id=None)` and accept `aidd rules approve <spec> --unit <id>`; only the existing approve command may append `unit_approved` with spec, unit_id, full digest and consent timestamp through `ev.append`, after all checks. Do not add a file-based or untrusted Codex transport.
- **Behaviour:** Use only owner-answer events from the existing trusted hook evidence boundary with the exact full-digest tag, session and time newer than the unit and dependencies; an authenticated exact summary answer is sufficient, and no HTML is required; the new unit viewer route must report unsupported until its separate trusted review implementation is delivered; reject assistant messages, arbitrary prompt text and stale tags. Never convert arbitrary file contents into answer events; the existing local evidence-log trust boundary is unchanged. If no trusted event exists return None with an actionable diagnostic and do not append any approval. After verified owner consent, append one `unit_approved` event through the existing evidence API; failure to append is an error. Existing `cmd_approve(spec_arg)` follows the unchanged legacy branch. Codex-specific event integration is excluded pending T-358.
- **Tests first:** Existing hook test fixture accepts a fresh exact-tag `Aprobar con resumen` containing the generated summary and explicit matching offered option without HTML, appending exactly one `unit_approved` event. A missing option list, a missing or changed summary, a viewer-only event before its implementation, or an unsupported host is refused; stale tag, forged assistant message, wrong session, tampered dependency and older-than-dependency answer append nothing. No recorded event returns None and CLI exits 1. Legacy `aidd rules approve <spec>` and FR-313 tests remain unchanged.
- **Verify:** `python -m unittest tests.test_aidd_codex_consent` -> exit 0, all tests passed; orchestrator additionally runs `python -m unittest tests.test_dot_aidd_mirror` -> exit 0 after all mirrors.
- **Do NOT:** manually write approval/evidence, trust unverified host text, remove legacy enforcement, touch unlisted files, execute deploy, or create databases by hand.
- **Done when:** cited acceptance cases and exact verification commands pass, with output saved; independent audit remains a separate coordinated step.
- **Open questions:** none

### T-354 — Unit-specific write gate
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC
- Size: ~150 changed lines; split into separate approved tasks if this bound cannot be met.
**Estimate**
- Agent min: 20
- Human ref hours: 1
- Tokens (est): 95k
- Agent role: builder
- Model tier: high
**Detail**
- **Goal:** Unit-specific write gate.
- **Cites:** FR-351, FR-354
- **Depends on:** T-350, T-351, T-353
- **Read first:** `skill/hooks/rule_gate.py:347 and skill/hooks/rule_gate.py:610`.
- **Files to change:** `skill/hooks/rule_gate.py`, `tests/test_aidd_unit_gate.py`; shipped adapter mirror: `adapters/dot-aidd/hooks/rule_gate.py`. If required by package mapping and absent, stop; no unrelated paths.
- **Naming contract:** Extend `_approval_gate` and `_target_violation` without changing existing call signatures. Resolve the requested canonical target by exact match against unit manifest `targets`; among all matching declared units, including unapproved drafts, choose the unique maximal descendant in the declared dependency DAG. Historical ancestor units may name the same target. Multiple incomparable owners, missing mapping, cycle or escaping path refuse. An unapproved descendant is selected but its missing seal blocks the write; never fall back to an approved ancestor. The required evidence event is `unit_approved` with spec, unit_id, full digest and consent timestamp; access additionally needs the current trusted digest and all dependencies.
- **Behaviour:** Select target by explicit validated mapping; find a recorded `unit_approved` event for selected spec/unit whose full digest equals the freshly computed unit digest, whose trusted owner consent is valid and newer than all dependencies; absent, mismatched, ambiguous or stale events refuse. Resolve inherited/symlinked paths securely before mapping; preserve legacy target fallback unchanged and never read/write protected review files by agent.
- **Tests first:** Write blocked for missing unit event, stale unit and stale shared asset; allowed for trusted current unit. Historical A10 and descendant A11 can name the same target and A11 is selected even if A11 is an unapproved draft, which blocks the write; incomparable A11a/A11b owning one target refuse. Unrelated unit retains its seal only if proven independent; path escape refuses; legacy paths unchanged.
- **Verify:** `python -m unittest tests.test_aidd_unit_gate` -> exit 0, all tests passed; orchestrator additionally runs `python -m unittest tests.test_dot_aidd_mirror` -> exit 0 after all mirrors.
- **Do NOT:** manually write approval/evidence, trust unverified host text, remove legacy enforcement, touch unlisted files, execute deploy, or create databases by hand.
- **Done when:** cited acceptance cases and exact verification commands pass, with output saved; independent audit remains a separate coordinated step.
- **Open questions:** none

### T-355 — Unit progress and legacy status
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC
- Size: ~150 changed lines; split into separate approved tasks if this bound cannot be met.
**Estimate**
- Agent min: 20
- Human ref hours: 1
- Tokens (est): 95k
- Agent role: builder
- Model tier: high
**Detail**
- **Goal:** Unit progress and legacy status.
- **Cites:** FR-352, FR-355
- **Depends on:** T-350, T-351
- **Read first:** `skill/scripts/aidd_progress.py:1 and tests/test_aidd_progress.py:1`.
- **Files to change:** `skill/scripts/aidd_progress.py`, `tests/test_aidd_unit_progress.py`; shipped adapter mirror: `adapters/dot-aidd/scripts/aidd_progress.py`. If required by package mapping and absent, stop; no unrelated paths.
- **Naming contract:** Expose `unit_progress(spec_dir: Path) -> tuple[dict[str, object], ...]` and label task presence separately from executed, audited and closed evidence.
- **Behaviour:** Render each declared unit and its independent status; missing/unknown evidence is unknown, never done; legacy spec without manifest retains existing report exactly; no schema migration or legacy approval write.
- **Tests first:** Fixture with draft, approved and stale units exposes distinct states; legacy snapshot output is unchanged; absent provenance cannot become approved.
- **Verify:** `python -m unittest tests.test_aidd_unit_progress` -> exit 0, all tests passed; orchestrator additionally runs `python -m unittest tests.test_dot_aidd_mirror` -> exit 0 after all mirrors.
- **Do NOT:** manually write approval/evidence, trust unverified host text, remove legacy enforcement, touch unlisted files, execute deploy, or create databases by hand.
- **Done when:** cited acceptance cases and exact verification commands pass, with output saved; independent audit remains a separate coordinated step.
- **Open questions:** none

### T-356 — Coordinated integration and independent audit
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC
- Size: ~150 changed lines; split into separate approved tasks if this bound cannot be met.
**Estimate**
- Agent min: 25
- Human ref hours: 1.25
- Tokens (est): 100k
- Agent role: tests
- Model tier: high
**Detail**
- **Goal:** Coordinated integration and independent audit.
- **Cites:** FR-350, FR-351, FR-352, FR-353, FR-354, FR-355
- **Depends on:** T-350, T-351, T-352, T-353, T-354, T-355, T-357
- **Read first:** `tests/test_dot_aidd_mirror.py:1 and tests/test_aidd_review.py:1`.
- **Files to change:** `tests/test_aidd_units_integration.py`, `tests/test_aidd_units_integration.py`; shipped adapter mirror: none. If required by package mapping and absent, stop; no unrelated paths.
- **Naming contract:** Use unittest test case `TestUnitReleaseIntegration` in `tests/test_aidd_units_integration.py`; construct disposable temporary repository fixtures only.
- **Behaviour:** Exercise baseline plus two units, changed contract, tampered visual asset, invalid Codex event and legacy seal; check mirrored shipped modules via existing tests. One independent security/functional audit reviews approved scope after execution.
- **Tests first:** Run the targeted unit integration tests and mirror suite; verify that unrelated unit evidence remains valid only with explicit dependencies and all stale/forged paths fail closed.
- **Verify:** `python -m unittest tests.test_aidd_units_integration` -> exit 0, all tests passed; orchestrator additionally runs `python -m unittest tests.test_dot_aidd_mirror` -> exit 0 after all mirrors.
- **Do NOT:** manually write approval/evidence, trust unverified host text, remove legacy enforcement, touch unlisted files, execute deploy, or create databases by hand.
- **Done when:** cited acceptance cases and exact verification commands pass, with output saved; independent audit remains a separate coordinated step.
- **Open questions:** none

### T-357 — Register shipped unit-module mirror
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC
- Size: ~25 changed lines.
**Estimate**
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 95k
- Agent role: tests
- Model tier: high
**Detail**
- **Goal:** Verify the new unit parser ships identically in skill and adapter.
- **Cites:** FR-350, FR-355
- **Depends on:** T-350
- **Read first:** `tests/test_dot_aidd_mirror.py:58`, `setup.py:18`, `MANIFEST.in:1`.
- **Files to change:** `tests/test_dot_aidd_mirror.py` only.
- **Naming contract:** add `aidd_units.py` to the existing `PAIRS` mapping; retain its existing comparison mechanics.
- **Behaviour:** include the new script in the shipped mirror check; assert modified/missing adapter copy fails, while byte-identical script passes. Package `setup.py` already copies both directories; no modification to package metadata.
- **Tests first:** add a fixture with missing and altered unit module; each must produce a detectable mismatch. Compare identical source and mirror as the positive case.
- **Verify:** `python -m unittest tests.test_dot_aidd_mirror` -> exit 0, all tests passed.
- **Do NOT:** run builds while other lanes build; edit production code, existing package configuration or unrelated mirror mappings.
- **Done when:** positive and negative assertions execute, and the coordinated mirror suite passes.
- **Open questions:** none

## Waves
| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-350 | builder | 20 | 95 | 1.0 |
| 2 | T-351 | builder | 20 | 95 | 1.0 |
| 3 | T-352, T-353, T-355 | builder | 20 | 285 | 1.0 |
| 4 | T-354, T-357 | builder, tests | 20 | 190 | 1.0 |
| 5 | T-356 | tests | 25 | 100 | 1.25 |

Total agent time (critical path): 105 min
Total tokens (k): 765

## Approval gate
No approval: owner must review final units, exact dependency contracts, coverage and hash. Never copy a legacy seal into a new unit.
