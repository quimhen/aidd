# Plan — Native future output targets

## Naming & File Contract

| Item | Convention |
|---|---|
| Functions/files | Python snake_case; existing public ABI preserved |
| Types/classes | PascalCase; extend existing test classes, no new production class/helper file |
| Scope | skill/scripts/aidd_units.py, its generated adapter mirror, two existing test modules, two version constants |
| Owner | One production owner; tests lanes separate; root coordinates verification and publication |

## Entry route

Existing native migration-plan→migration-apply→review/consent→build preflight. No alternate
manifest writer, approval importer, fallback legacy path, forced install or fake output files.

## Exact implementation contract

1. Add a private typed file-state helper inside aidd_units.py, reused by migration and impact.
   Walk existing components with lstat; only FileNotFoundError for a genuinely missing component
   permits absence. Existing ancestors must be regular directories in exact canonical spelling,
   inside root, without symlink/junction/reparse substitution. Reject inaccessible paths, loops,
   special files, directories as final target, file-as-ancestor and case aliases. Preserve current
   hardlink ownership resolver; never classify an existing alias as absent.
2. Record absent candidate target as explicit domain marker ABSENT plus nearest existing ancestor
   identity and missing suffix. Hash existing regular bytes with stable stat/read recheck. Bind this
   state in initial migration plan, apply recomputation and post-manifest check. If absent state adds
   incompatible fields, emit migration-plan-v2 for that plan; existing all-present plans retain v1.
   _migration_file remains strict for paths/inputs/config/visual and _migration_parents remains strict.
   A candidate filename declared in any strict role is not eligible for absence.
3. Apply refuses ABSENT→file/directory/link, changed missing-directory chain/ancestor identity,
   file→missing and content mutation before/after manifest creation. Never create output targets.
   Failed apply removes only its exact newly-created manifest and writes no success receipt.
4. _unit_impact_batch gains internal allow_missing_targets=False. Singular unit_impact_snapshot
   keeps False (executed audit/close strict). Plural unit_impact_snapshots uses True only for its
   read-only plan_impact callers. Compute strict-role membership across the complete required
   closure BEFORE the name-keyed observed cache: paths/inputs/config/visual and parent scopes
   remain strict. Same-path strict roles win independently of iteration order or cross-unit location.
   Missing targets produce explicit state in files.targets; final recheck uses same role/state rules.
5. Preserve unit_approval_hash/unit_review_package/check_unit_build behavior: target names are
   already sealed; target bytes are not consent. Creation changes impact digest, not legitimate
   approval. Audit materialization and close use strict singular snapshot and reject missing output.
   No cache/reuse redesign or new evidence event. Keep all-present impact representation stable.
6. Mirror source by fixed mapping with dry-run, apply and byte postcheck; no manual adapter edit.
   Only version0.5.1→0.5.2 changes in pyproject.toml/aidd/__init__.py, then official release by root.

## Tests-first contract

UnitMigrationTests: absent leaf/nested target; absent vs empty; missing strict role/parent;
roles-overlap ordering; case/link/junction/special/inaccessible/file ancestor; race at initial
and final checkpoints; failed-apply cleanup; unchanged present-target behavior. Extend existing
fixtures, never create a production placeholder or rewrite consent records.
UnitImpact: plural allows only eligible output absence, deterministic digest and creation change;
singular strict error; cross-unit strict overlap cache cannot tolerate missing input; ancestry
substitution/race fails; preserve shared input read counts. Use fixture evidence only through
existing native test helpers to prove approval/review/build reachability before output creation
and inability to materialize executed audit with missing targets. Keep prior seals and ownership tests.
Platform-specific unsupported link/FIFO tests explicitly skip with reason, never count as PASS.

## Execution / safety

Native graph first, bounded reads. Mechanical changes use mapping/dry-run/apply/postcheck.
Builders run static checks only; root runs RED before body and one union after freeze, then sends
stable inputs/results to independent audit. No DB, Docker, network or financial app edits.
Future DB work only via official db_verify default/slots1..3; none is required here. Never
modify approval/events, protected project .aidd or installed profiles manually. Missing context
is reported, not guessed. Final host-spec verification/close remains independent.

## Approval gate

Only the official review package can obtain owner consent. Base007 gate PASS is not exact
scope approval. Root registers the candidate via native plan/apply, reviews package, waits
for consent, then runs per-target unit build gate before implementation.
