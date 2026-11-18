# Independent legacy dependency contract inspection

Auditor: /root/aidd_independent_final. Inspection time: 2026-11-14T09:42:08.965135+00:00.

## Scope and verdict

PASS for the limited compatibility contracts described below, by independent source inspection. This reviewer did not implement these modules or the current fixes. This is current independent evidence covering the relevant legacy dependency contracts, not a declaration that these files are part of the approved unit closure. It is not a runtime verification, official unit audit receipt, unit approval or close authorization. No tests, application source imports, services or database operations were executed for this inspection.

The expressly authorized scope was aidd_progress plus alias_graph, aidd_rules, aidd_evidence and the two progress test files. Native graph query `aidd graphs show code _alias_target` resolved progress relationships; its stale warning was preserved. Targeted source reads followed. No graph rebuild was requested.

## Content identity

SHA-256 of raw bytes inspected (CRLF/LF differences matter):

| Path | SHA-256 |
|---|---|
| `skill/scripts/aidd_progress.py` | `f78a92171423f7585c45159fcb89453c23951d269e85b6b9dcc5adbd1e90fee3` |
| `skill/scripts/alias_graph.py` | `ebde0c8955fecf3d04c41acd80aa6b2674ee29fcc6655701810d3ec844d82e94` |
| `skill/scripts/aidd_rules.py` | `ff7e82cf4ec02c2d4673e1f1c217602309e08849a3264a9d35d4cdc88ffa3ff0` |
| `skill/scripts/aidd_evidence.py` | `9fde4fd718a3d9f0f87254e1e0909c04f4831498feb4281d7bb79a9bda870866` |
| `tests/test_aidd_progress.py` | `24273a61fb2bce1fa8988cd96aef21e2d840fafb117bc6c15043bf15bdedf92c` |
| `tests/test_progress_resolution.py` | `39bc2437a1b1b71143ef9d2a68a8e530664cd4e3301ea64b8afec4950263d0f9` |

## Contracts inspected

1. Alias resolution: aidd_progress.py:232-265 bounds the optional alias graph to MAX_READ, catches unavailable/binary readers, and caches an empty mapping on failure. alias_graph.py:13-67 requires the alias TOON section, parses rows into basenames, rejects separators/NUL/dot traversal, and returns an empty list on failure. Resolution stays in the requested directory and requires an existing target larger than STUB_BYTES. task_state at progress.py:268-297 preserves deletion, migration ambiguity, alias-rename, presence and marker semantics. The new _source_structure at :334-348 reuses these resolvers but stores a separate result; it does not mutate task state or mark a verification PASS. Tests define deletion/rename/ambiguous/binary cases in test_progress_resolution.py:42-86. These definitions were read, not executed by this reviewer.

2. Batch and approval state: progress.py:351-358 expands existing batches with aidd_rules.with_batches. rules.py:1548-1590 discovers only canonical tasks-<name>.md names, sorts them and combines their text; it does not rename or create files. approval_valid at :1718-1724 requires exactly one well-formed Approved line and equality with approval_hash at :1689-1695. Hashing uses the existing semantic projection; it does not record owner consent. New structure findings have no path into these calculations. Exceptions leave displayed approval unknown or preserve the old base-only fallback; the structural inspector is not used as approval authority.

3. Evidence stage: progress.py:300-329 reads approval, last verification, domain coverage and close events. evidence.py:1195-1218 selects the newest exact-spec verify_run and requires boolean true for ok; no event is synthesized. Missing run is displayed as none, a recorded failure as failed, exceptions remain unknown. Domain coverage uses max(scoped code edit time, verify code_since/ts); rules.py:1915-1928 returns all required domains uncovered if the evidence backend is absent or fails. rules.py:1857-1900 checks post-cutoff counting subagents, supports a separately validated closing-audit header, and otherwise uses distinct matching; pre-dispatch and low-tier events are excluded by :1813-1830. This describes the existing contract, not an assertion that those counting rules prove review quality.

4. Cache boundaries: progress.py:499-509 enables evidence.read_cache only around the reporting command. evidence.py:432-460 restores previous cache state in finally, validates cached file text using size+mtime_ns, and retries direct reads on errors. rules.py:1952-1995 resolves that helper dynamically and preserves direct-read fallback. evidence.py:769-817 filters session/kind/spec consumers and caches parsed logs only with the current size/mtime signature and without pending spill files. Its write paths call forget_read (:512,:531,:605). Cache hits neither append PASS events nor change task approval. Existing alias/path caches are process-local.

5. No false runtime inference from the new feature: progress.py:359-361 stores source_structure separately from state and declared_done; :369-375 derives Impl% only from legacy presence/marker/rename states. Rendering at :442-460 explicitly separates static source structure from integrated functionality/runtime behavior. test_aidd_progress.py:24-48 defines preservation of 100% presence for a structural stub, unknown syntax and no runtime-verified claim. Static clean/findings/unknown do not generate approval, verify or audit events.

## Material limitations preserved, not hidden

- The progress verify column displays the latest recorded ok flag; it does not independently revalidate that run against current input fingerprints or current Verification content. A historical passed label is not a current functional PASS or permission to close. Freshness/enforcement remains the responsibility of the actual verification and gate commands.
- Missing dependencies or batch-read exceptions can leave incomplete reporting. Existing broad exception fallbacks do not establish successful feature execution. No global assurance is given that every dependency is failure-proof.
- events() is not entirely free of maintenance effects: evidence.py:636-663 may drain and merge an already existing spill into its log before reading it. That preserves existing rows; it does not authorize direct ledger editing or fabricate an audit or verification result. This reviewer inspected source without invoking events for this contract pass.
- Cache invalidation uses file size+mtime, not a cryptographic freshness guarantee against adversarial same-signature replacement. Alias caches live for the process. This is appropriate to describe as existing reporting behavior, not as new stronger protection.
- Further helpers reached through existing domain/impact/header calculations were classified as legacy support; this was not an exhaustive security audit of all AIDD code or all transitive imports. No changes to dependency files were made.
- This report supplies current independent source-contract evidence only. Executed evidence must be supplied separately with actual scope fingerprints; this report cannot adopt the earlier 114-test log or create a verify_run. Official fresh unit audit still decides whether this evidence is sufficient.

No approval or unit manifest was altered. No official unit audit runner or installation was invoked during this pass.
