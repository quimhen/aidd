# Independent security audit — AIDD-FUTURE-TARGETS

2026-11-18. Reviewed source: AIDD 0.5.2, approved future-target repair scope supplied by root. Auditor: aidd_readiness_audit. Execution owner: root.

**Scoped PASS:** no unresolved medium-or-higher security finding in the inspected future-output-absence delta. This assessment does not approve a product unit, grant consent, establish executed product verification or close a product feature.

## Scope and evidence

Reviewed the bounded canonical `skill/scripts/aidd_units.py` diff from source baseline `a1b30cc`, relevant existing approval/review/audit call sites, and the new migration/impact regressions. The prior independent plan supplied the role and security contract; no applicable native future-target graph was identified in the directed inventory. Canonical/mirror hashes were independently read and matched. Version declarations in `pyproject.toml` and `aidd/__init__.py` both read 0.5.2.

No tests, builds, database operations, browser operations, framework writes or implementation edits were performed by this auditor. This report is the sole write for this final audit. Root's real-product smoke is separately owned and is not assumed by this source verdict.

## Security conclusions

- **Role policy:** migration_plan, lines 663–669, computes strict paths/inputs/config/visual names before adding candidate targets. Only names outside strict roles may be absent. Parent migration inputs continue through strict `_migration_file` checks. Impact batching, lines 378–389, computes strict names across its required transitive closure before filling the name-keyed observed cache; parent targets are strict. A target-first encounter cannot suppress a later strict-role failure within that closure.
- **Bound absence:** `_scope_path_state`, line 541 onward, records typed `ABSENT`, nearest existing ancestor, missing suffix and ancestor identities. Absence differs from empty-file and populated-file hashes and remains in the canonical plan digest. Plans containing typed absence use migration-plan-v2; existing-file-only plans retain v1. migration_plan rechecks observed states, and migration_apply recomputes the reviewed plan plus post-creation file/parent states before recording success.
- **Paths and filesystem state:** target spelling is checked before resolve can hide links (`_paths`, lines 84–87). Existing path components are checked for exact case, ambiguous aliases, symlink/junction/reparse state and directory ancestry. Only FileNotFoundError can yield allowed absence; permission and other I/O errors fail. Existing final targets must be exact regular files. Existing hardlink ownership checks remain in place; this repair does not turn hardlink ambiguity into absence or bypass the most-derived owner gate.
- **Observed races:** absent states are checked twice locally and again at enclosing plan/apply or impact checkpoints; ancestor identities are included. Existing file observations compare identity, size, modification time, repeated content and ancestor guards. Tests inspect output appearance, existing output mutation, ancestor replacement and partial directory-chain creation at the relevant checkpoints. This is bounded filesystem observation, not a promise against arbitrary mutation after a final check.
- **Cleanup identity:** migration_apply captures the created manifest identity from its open descriptor (line 716). Failure cleanup requires matching identity and exact bytes, rechecks identity and rejects linked replacements (lines 735–740). A concurrently replaced manifest with identical bytes is preserved; no success receipt is produced for the rejected application. Unrelated output files are not deleted.
- **Preparation versus execution:** plural `unit_impact_snapshots` explicitly enables future output preparation. Singular `unit_impact_snapshot` preserves strict default behavior at line 523; executed unit-audit entry points still call the singular function. The absent state changes impact fingerprints when an output appears. Approval hash/review behavior continues to bind target names and sealed planning material; this repair does not manufacture consent or mark work executed. Existing base/unit consent and ownership checks remain required by build preflight.

## Regression evidence reviewed

Root executed `green-union-v1.log`: 136 methods in 14.955 seconds, with one failure for a legacy diagnostic substring, one error caused by a repeated injection in a fixture, and one Windows skip for a POSIX FIFO fixture. That run is retained as failed history.

After the diagnostic and one-shot fixture corrections, root executed `green-affected-final.log`: 58 methods in 10.985 seconds, **OK (skipped=1)**. The retained skip is the explicitly POSIX-only FIFO case; special-file rejection was inspected statically but not claimed as exercised on Windows. The final log includes a TemporaryDirectory ResourceWarning; it does not alter the recorded unittest outcome.

Root reports that the other 78 methods passed in the first union with their affected inputs unchanged. These are **136 distinct methods covered across rounds**, not one fully green 136-method run. No execution was duplicated by the auditor.

Inspected regressions cover absent leaf/nested outputs without placeholders, distinct empty/absent/content states, strict role overlap, strict parent outputs, case aliases, symlink/dangling-link/junction ancestry, permission denial, observed output/ancestor mutations, manifest cleanup identity, unchanged review/consent after target creation, and prebuild preparation versus strict executed audit behavior. Existing hardlink/unknown-peer ownership regressions remain part of the relevant suite.

## Frozen fingerprints

| File | SHA-256 |
|---|---|
| skill/scripts/aidd_units.py | 61ffffb7caaeb5d3f117e50cc1656557fb88c6d2bb9b8faf55f343c0327362fe |
| adapters/dot-aidd/scripts/aidd_units.py | 61ffffb7caaeb5d3f117e50cc1656557fb88c6d2bb9b8faf55f343c0327362fe |
| tests/test_aidd_unit_migration.py | 87e629d61db60ab6dd6c430f1f68c487b22bfd3a043810fb49e38b54061cee84 |
| tests/test_aidd_unit_impact.py | e39a3eaaa94e1c28d10402cc98aa10d74d0998fb503693c332268c80e0a4c340 |

The source verdict is tied to these bytes. Root's transactional installation and real-product smoke require their own recorded outcomes.
