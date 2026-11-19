# Explicit native-unit structural readiness

`aidd check specs/<base> --unit <id>` and `aidd readiness specs/<base> --unit <id>`
select the actual schema-2 package. Direct nested folder checking is rejected with an
explicit selection instruction. Unknown, malformed, escaped and wrongly identified
manifests do not fall back to the historical base.

The structural rules receive the resolved project root, so repository citations in
amendment documents are checked against the project rather than the nested unit folder.
Selected package and transitive-parent manifests/documents are validated. Their hashes,
identity and native-consent state are observed by readiness; changes during the checker
produce an unstable report. These fingerprints remain diagnostic, not a complete cache key.

Native unit consent replaces only the unit's legacy tasks Approved-line convention.
No recorded unit consent is pending and may be deferred for a preapproval readiness
report; existing mismatched or malformed consent is invalid and remains a gap. A current
approval is not a build/close authorization from this report. Base checks retain legacy
rules. Parent historical verification must not cause a unit report to claim executed work.

No event, approval, protected evidence or document is written by these read-only checks.
`--stamp-contract` is rejected for a selected unit, preserving its sealed package.
Existing unknown failures, nonzero checker outcomes and output no-overwrite rules remain.

## G8 exact registry evidence

The existing directory heuristic remains the default. A component outside those directories
can pass only through an exact row in the project-level `design-system/components-index.md`
or `components-index.md`. The existing seven-column template is unchanged: COMP-nnn, Name,
File, First defined in, Used in, Consumers, Notes. A nested amendment-local index does not
register a project-wide exception.

The row must have one exact complete COMP identifier, the same canonical contained existing
source file as the plan, an exported symbol matching Name, at least two distinct SCREEN
identifiers declared in the selected/base spec, plan or mockup audit, and at least one
existing production consumer importing that file/symbol and using its imported binding in
JSX. One shared host can serve several screens; two production consumer files are not required.
Duplicate IDs, conflicting IDs for the same source, path escapes, test/fixture-only consumers,
type-only imports, comment/string-shaped imports or JSX, and named/default incompatibility
do not grant exceptions. No row authorizes other files in its directory.

The lexical masks preserve source offsets and physical newlines while removing evidence
inside comments, templates, escaped-newline strings and regular-expression literals.
Import module text is inspected only when its import keyword survives the nonliteral view;
regular expressions containing component-shaped text cannot count as JSX use. Ambiguous
slash syntax remains conservatively unsupported rather than being a full JavaScript parser.

The conservative resolver supports direct relative TS/JS imports and aliases declared in the
nearest plain-JSON tsconfig.json with one unambiguous paths target. Unknown inherited aliases,
barrel reexports, namespace/mixed imports and unsupported declaration syntax remain gaps,
rather than being guessed. This is static structural evidence, not a TS compiler or a proof
that every claimed screen renders the component; executed and independent audits still apply.

Readiness observes the index, source/consumer files, nearest tsconfig files and screen
declarations used by this exception. It detects their changes during checking. G5 still
checks only registered rows for missing consumers; it does not claim this incremental index
contains every component in a project.

## Coordinated verification

The implementer performs static self-review only. The execution owner runs the new
`tests/test_aidd_check_scope.py`, `tests/test_aidd_shared_components.py`, existing readiness/check/component/CLI tests and the
previous unit build-gate/security regression union once. Mirrors are updated by
`tools/sync_unit_readiness_mirrors.py` dry-run, apply, post-check. Installation into a
project uses official transactional sync; no manual `.aidd` modifications.
