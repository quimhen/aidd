# Independent contract review: future native-unit targets

Wave: AIDD-FUTURE-TARGETS. Baseline: source commit `a1b30cc` (0.5.1). Review only; no implementation, test execution, build, database operation, framework write or approval performed. This report is the sole auditor write. Root retains the approval decision and execution ownership.

## Finding and minimal scope

Confirmed functional blocker: `skill/scripts/aidd_units.py` migration_plan flattens candidate paths/targets/inputs/config/visual files and passes every name through `_migration_file`, which requires an existing file. migration_apply repeats that requirement. `_unit_impact_batch.file_hash` independently resolves every declared target strictly, blocking an impact snapshot even after a migration-only fix. These are two necessary parts of one minimal repair.

The bounded contract can allow a genuinely absent **candidate output target** at preparation time. Missing planning artifacts, inputs, config, visual sources/assets, manifests and parent migration files must remain errors. Do not create placeholder source files, infer consent, bypass approval, weaken ownership checks, alter executed verification/reuse, or redesign the cache.

Native graph availability was checked by directed file inventory; no applicable future-target graph was identified. Relevant functions and existing migration/impact/security test names were read with bounded searches. No full methodology or unrelated source tree was dumped.

## Required implementation contract, subject to root approval

1. Preserve roles before flattening filenames. A filename present in any strict role must exist even if also declared as a target. In migration, permit absence only for candidate targets outside its strict paths/inputs/config/visual names. `_migration_parents` stays strict; a parent's missing target is not silently reclassified as an allowed candidate output.
2. Bind absence as an explicit domain-distinct value such as `ABSENT` in the plan's file-state map and canonical digest, rather than omitting the filename, hashing empty bytes or substituting a missing-file exception with success. Existing files retain content fingerprints. Keep the representation consistent in initial plan, apply recomputation and post-create verification. Existing plan format consumers must be considered; a version bump is required if the output contract becomes incompatible.
3. Apply must compare every reviewed state, not merely target membership. ABSENT→file/directory/link and file→ABSENT/content-change invalidate the reviewed digest. Recheck after creating the manifest and before recording a receipt; failure cleans only this invocation's exact created manifest and must not overwrite unrelated files or record success.
4. Genuine absence is distinguished using lstat-style checks from a dangling symlink, junction/reparse point, non-directory ancestor, inaccessible file, loop or other I/O error. Walk existing ancestors, enforce exact canonical spelling/case, reject escaping/linked ancestry, reject existing directory/special-file targets and preserve strict containment. Missing intermediate directories may describe future output paths only when their nearest existing ancestor is a verified in-project directory; do not create them during planning.
5. An existing target that aliases another ownership declaration through hardlinks cannot evade the existing most-derived-owner gate. Future-file handling must not turn link/identity ambiguity into ABSENT. Avoid broadening existing hardlink semantics as an unrelated refactor; test the actual ownership boundary and reject indeterminate identities.
6. Close race windows with state/ancestor identity comparisons at the existing pre/post checkpoints and fail on observed substitution, creation, deletion or mutation. Do not catch arbitrary OSError as absence. This is not a claim of immunity to an adversarial process mutating the filesystem after the final check; retain the existing fail-closed gate boundaries and rechecks.
7. In `_unit_impact_batch`, classify per-name strictness over the entire required closure **before** populating its name-keyed observed cache. First-seen target tolerance must not make a later strict input accept absence. Carry the same policy into the final file_hash recheck and propagate failures only to actual consumers, retaining disjoint-unit behavior and one shared read per phase where applicable. Parent impact entries retain the required strict semantics; do not weaken migration parents merely to make hashing convenient.
8. Distinguish target output state from consent. `unit_approval_hash` already hashes target names, not their bytes; `unit_review_package` exposes those names and hashes actual planning paths. Retain this separation. Target appearance/content changes must change impact state/digest and invalidate stale impact-dependent audit/verification evidence, while not fabricating a new owner approval. No automatic approval or passed execution evidence is introduced.

## Required regression evidence

Root should coordinate one affected execution round after approval and implementation; this reviewer executes none. Add meaningful cases to existing migration/impact suites and run the relevant native review/consent/build/security regressions, without duplicated heavy checks.

- Migration plan/apply succeeds with an absent candidate target (including a new nested output directory), records its explicit absent state, preserves historical documents and never creates the output itself.
- Existing regular target behavior and exact reviewed digest behavior remain intact; absent and empty-file states differ.
- File creation, directory creation, deletion/content mutation and linked-ancestor substitution between plan/apply or during final recheck reject and produce no success receipt.
- Missing strict path/input/config/visual source/asset and parent file still reject. Same name declared as target plus strict role rejects whether strict role occurs first or later and whether the overlap is in a related unit.
- Symlink/dangling-link/junction, case alias, traversal/absolute/drive path, file ancestor, inaccessible path and special-file cases reject rather than become ABSENT. Use platform-aware tests that state skipped capability cases accurately.
- Existing hardlink/most-derived target ownership cases continue to reject ambiguous ownership; no unknown-peer fallback is added.
- Impact snapshot supports the allowed initial absence, is deterministic, and changes when the target is created or altered. A target appearing during either snapshot phase produces a changed/unavailable error. Strict missing consumers fail while disjoint units remain unaffected.
- Readiness → exact review package → explicit consent → build preflight is reachable before code creation for a legitimate future target. Existing base seal, parent consent, document seals and ownership remain enforced. No consent can be produced from migration/readiness alone.
- Creation of future files does not make prior executed verification current: retain current execution/reuse semantics and test the relevant impact-bound audit consumers. Do not assert a structural snapshot itself proves execution.

Existing suites of direct interest: `tests/test_aidd_unit_migration.py`, `test_aidd_unit_impact.py`, `test_aidd_unit_build_gate.py`, `test_aidd_unit_review_package.py`, `test_aidd_unit_consent.py`, `test_aidd_unit_audit_incremental.py`, and their actual dependency-selected security tests. Canonical and adapter mirror parity must be checked through the repository's mapped synchronization process after source review.

## Review disposition

The minimal two-site repair is justified; a migration-only change is insufficient. This document defines review constraints, not authorization to implement. Root should resolve the approved amendment/task scope before code changes. No new permission, consent, verification evidence or framework state is asserted here.
