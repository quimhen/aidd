# Independent functional audit — AIDD future targets

Wave: `AIDD-FUTURE-TARGETS`. Auditor: `/root/amendment_prebuild_audit`. Coordinator: `/root`. Date: 2026-11-18.

**Verdict: PASS for the approved future-target preparation contract; no confirmed medium-or-higher functional findings remain open in this bounded review.** This is not owner consent, a security verdict, permission to close the base specification, or an assertion that future product outputs have been implemented.

## Frozen source and scope

Reviewed the approved `specs/007-aidd-review-html-close-gate/amendments/future-targets/{spec,plan,tasks}.md`, the bounded native units-module diff, the added migration/impact cases in the two existing test modules, and the reported verification results. The six declared implementation targets are the canonical units module, its official mirror, those two tests, and the two version files.

The canonical `skill/scripts/aidd_units.py` and mirror `adapters/dot-aidd/scripts/aidd_units.py` were independently read-hashed during this audit and both matched:

`61ffffb7caaeb5d3f117e50cc1656557fb88c6d2bb9b8faf55f343c0327362fe`.

`pyproject.toml` and `aidd/__init__.py` both declare version `0.5.2`. The native graph query resolved `migration_plan` and its callers; its stale warning was retained and actual source/diff ranges were read directly.

## Contract assessed against implementation

| Requirement | Source behavior inspected | Assessment |
|---|---|---|
| FR-1190: genuine future outputs can be registered | `_scope_path_state` permits only genuine FileNotFoundError absence in the allowed target role. `migration_plan` binds typed ABSENT state, nearest existing ancestor identity and missing suffix; it does not create the output. | Coherent. |
| Required roles and parent scope remain strict | Registration builds strict names from paths/inputs/config/visual files and `_migration_parents` remains strict. Impact computes strict-role membership before the shared name cache, including parent targets. | Coherent; a target name does not override a strict input role. |
| FR-1191: stale reviewed filesystem state is rejected | Plan and apply re-observe file/absence states; exact spelling, case aliases, links/junctions, file type, ancestry and content are checked. Apply compares the post-manifest state with the reviewed plan. Failed cleanup checks the identity and bytes of the manifest created by that invocation. | Coherent. |
| Migration-format compatibility | Plans containing ABSENT markers use migration-plan-v2; all-present plans retain migration-plan-v1 and content hashes. | Coherent; no claim that all impact payloads were renamed v2. |
| FR-1192: preparation differs from executed audit | Plural read-only impact snapshots enable missing targets explicitly. The internal default remains strict, so singular executed snapshots retain required output existence. ABSENT and an empty/populated file have distinct impact state. | Coherent. |
| FR-1193: readiness/review/consent/build before output | Existing consent binds target names rather than output content. New tests exercise native registration, readiness, review, isolated fixture consent and the approved-unit build preflight while output remains absent. Singular audit/materialization still requires real output. | Coherent; future preparation is not executed implementation evidence. |

The change does not introduce an alternate manifest writer, fabricate outputs, alter real approvals, change verification reuse policy, or relax the base/unit ownership and consent checks. The existing canonical permission boundary remains in effect; only preparation distinguishes future target absence from missing mandatory input.

## Execution evidence and its exact limits

The coordinator executed the tests; this auditor did not repeat suites, build, database work or browser work.

- `batch-staging/future-targets/green-union-v1.log` records **136 cases** in 14.955 seconds with one diagnostic-text assertion failure, one one-shot fixture error and one skip. It is not an all-green run.
- After the diagnostic/fixture corrections, `green-affected-final.log` records **58 affected cases, OK, one skip**, in 10.985 seconds. The remaining **78 cases** had passed with unchanged affected source, as reported by the coordinator. This establishes distinct coverage across coordinated rounds, not a claim of a single final green 136-case execution.
- Added cases inspected cover absent leaf/nested output, no placeholder creation, ABSENT/empty/populated distinctions, strict-role precedence, parent strictness, case/link/junction/special-file/permission rejection, ancestor/output substitution, cleanup ownership and preparation-versus-strict-audit behavior. A skipped platform-dependent case is not claimed as executed proof on this host.
- Root reported the real b1SyncLink native smoke: migration-plan-v2 with 120 scoped files, 74 ABSENT future targets and 96 targets; digest `13aa801c887f222ea89eef95e2c81ecb33dd8ff34aae51b9b2ad1331f2e3165f`. Official apply created the native F20 manifest and receipt without creating outputs or granting consent. The product evidence is `native-plan-after-future-target-fix.json` and `native-applied-after-future-target-fix.json`. This integration result was communicated by root, not rerun by this auditor.

The selected product check can now reach its legitimate pending-consent/document checks. Remaining business-document formatting gaps or missing approval are not bypassed by this source change.

## Boundaries

No source was edited by this auditor. No test suite was rerun, no product or SQL implementation was asserted, and no database was created. The coordinator owns publication and its post-checks. This PASS applies to the frozen functional repair and its stated evidence; base-spec closure, final product verification and owner consent remain separate requirements.
