# Approved amendment build preflight

Incident: a project with approved amendment units could not start implementation because the
only documented pre-edit check applied historical alignment and closing-auditor requirements
to its base spec. Re-approving unchanged unit tasks did not resolve that mismatch.

Use the explicit build phase for schema-2 units:

```text
aidd rules check specs/F15-eDoc-Backoffice-Web --unit menu-consistency --phase build --target eDoc/web/src/app/AppShell.tsx
```

Repeat `--target` for every file owned by the implementation lane. A target outside the selected
unit is refused. Omitting the unit or build phase does not fall back to a more permissive check.
Without `--target`, all targets declared by that unit are checked as a unit-level preflight.
The canonical owner resolver checks declarations across the project and must select this unit as
the unique most-derived owner. Incomparable owners in any spec, case/hardlink aliases and
unapproved descendants cannot fall back to its approval. Unrelated invalid manifests are excluded
only when typed identity/target declarations prove them disjoint; unknown or overlapping ownership
fails closed. Missing parents of a disjoint peer do not contaminate the selected build scope.

This read-only gate requires a current recorded base tasks seal and current approval of the
selected unit and every declared transitive parent. It validates each unit's own spec, plan and
task files with the real project root; these files must be declared in the sealed manifest.
Missing files, changed unit documents, unresolved dependencies, legacy manifests and unknown
target ownership fail closed. A unit's seal replaces only the legacy Approved-line convention
inside that unit's tasks file; it never replaces the base seal.

The global `rules check` and `rules close` retain all their historical alignment, verification,
capacity and independent closing-audit checks. A build PASS is not a PASS for those operations,
and no approval, audit, provenance or historical evidence is manufactured by this command.

Regression command:

```text
python -m unittest tests.test_aidd_unit_build_gate -q
```

The fixture approvals in that test live only in temporary test projects and the dedicated
temporary evidence store. No test writes real project approvals.
