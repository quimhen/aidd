# AIDD4b independent security review — final PASS

Owner: Julio. Wave: AIDD4B. Approved task scope:4e4fde48cb47. **PASS for the physically isolated AIDD4b security package on the final round06 source snapshot.** No unresolved security finding remains in the reviewed bounded scope. The preliminary report and actual failed evidence remain preserved.

This is a package-only verdict. Original/main/installed kernels have not been changed; no installation, controlled publication, original unit seal, owner approval substitution, ERP/application or database success is certified here.

## Final correction and resolved boundaries

The final delta at `runtime/skill/scripts/aidd_status.py:1977` rejects same-spec historical reuse unless the latest prior event has the current top-level `code_algorithm`, in addition to the current Inputs algorithm already required by the shared gate. The two added public plain-verify subcases explicitly keep the Inputs algorithm current while removing or aging only top-level code proof. They assert one actual row execution and no reused result. The preserved RED log ran1 method with2 semantic failures before the predicate; final round06 passes that method and all its four algorithm subcases. This closes the final mixed-proof promotion route without adding Scope-fingerprint equality or changing cache schema/key/version.

The previously inspected corrections remain applicable on the final pins:

- The shared historical gate checks current/prior hermetic declarations, Inputs and algorithm/environment proof. R10 calls its schema-only form against an unambiguous canonical current row, including unknown/untyped historical reuse kinds and dual historical/shared flags. Both historical planners and the final injected-entry consumer supply the existing real offline environment validator. DB/docker/Node/unknown/Python `-m` and shell-composed commands cannot become historically reusable from unchanged files/container identity alone.
- Plan-time unavailable proof means RUN. A previously planned entry that becomes invalid at final consumption fails honestly as not-executed/stale and requires replanning; it never launches an unplanned command or a second coordinated heavy group. `--full`, command/Expected identity, confined intact original artifact, transformed bytes, live Inputs and current offline identity are rechecked. Valid emitted carryover retains proven contract metadata for subsequent reuse.
- Round collection preserves canonical Environment and Regression fields. `Regression: always` forces RUN during planning, matching the consumer. Local same-spec and global store caches are disabled during coordinated amendment/round consumption, preventing hidden cache decisions behind the coordinator.
- Plain same-spec cache eligibility now requires both current top-level code algorithm and current row Inputs algorithm, canonical current command/Expected/policy and the real validator. Missing/old proof executes and gains new metadata only through that actual execution.
- Cross-spec immutable store objects are consumed only after read-only qualification against the genuine latest stable successful source event, current code/input algorithms, one matching PASS result, current contract identity/live Inputs and a confined intact source artifact exactly equal to the object bytes. Missing/failed latest events do not fall back to an older PASS. The public A-to-B test uses the real cold producer and covers one valid case plus six denied source-proof variants; its preserved RED log records6 semantic failures before the guard. Store producer/key/schema/version remain unchanged.
- Dry-run avoids Round-identity and Docker identity probes while retaining ordinary read-only fingerprinting. Raw Git hashing uses `--no-filters`; the semantic algorithm changed explicitly and old/missing proofs are refused. Strict intact full-header recovery handles producer-truncated commands; a shared500-character prefix is insufficient. No historical artifact is rewritten or backfilled to claim new proof.

## Executed final evidence

Reviewed actual round06 logs and receipts without rerunning any command:

| Row | Test methods | Log result | Receipt elapsed seconds |
|---|---:|---|---:|
| V-4B1 historical/security boundaries |14 | OK |45.656 |
| V-4B2 dry-run/raw Git boundaries |4 | OK |4.985 |
| V-4B3 affected round suites |32 | OK |63.016 |
| V-4B4 affected amendment suite |15 | OK |39.625 |
| V-4B5 strict command-recovery suite |13 | OK |3.187 |
| V-4B6 selected gate/wave protections |19 | OK |9.579 |

Total97 methods; the summary `final-verification-round06.json` records all six passing and166.05s outer elapsed time. These are bounded current executions, not recertification of historical123/48 bundles or database suites.

Independent read-only checks confirmed every final log SHA256 against its row receipt; every row's77 Python input hashes are equal before/after and match current files. These include the transitive fixtures and runtime dependencies, rather than only the five changed kernel files. All five internal mirrors match their kernel bytes. All25 original/main/installed protected paths match `protected-kernel-pins.json`. No mismatch was observed.

## Final source SHA256

| Kernel file | SHA256 |
|---|---|
| aidd_rules.py |31ae5f48312776a3c7130229c8cc50fdf9e553d40ed67357bfada3aca0fd8cbe |
| aidd_amendment_verify.py |d398f87437bba00fd834115af37824aad06efe0f803d7a5c36a58847f8565340 |
| aidd_round.py |f6640e4efa20b17610717e2592d51aefb798e4dd642f0f77d1960616fc926caa |
| aidd_status.py |1abfff8cb944ae3fb3be25866ca6dacb3865766b41a782cb903949a8f460a278 |
| aidd_evidence.py |335aacce002f14c7bb6d1975fbbcbbb0bd007ed5544fb3538dcc42ed378cb676 |

## Limits and independence

The offline-hermetic contract is owner-declared and validated against observable interpreter/package/declared-variable identity and declared Inputs. It is not a sandbox or an independent proof that a Python program has no undeclared external dependencies. R10 intentionally checks policy/proof shape without importing the execution runtime or probing current environments; live reuse decisions enforce the environment boundary separately.

Review reused the prior independent source assessment and inspected only the final predicate, added subcases and final evidence/pins. Native graph was queried first during the review; the helper was absent, so targeted known paths were read without graph refresh. This reviewer authored no kernel/test source, performed no tests, builds, database actions, identity probes, installation or evidence repair, and created only the requested review reports. Authentic owner authorization and any subsequent controlled publication remain separate workflow facts.
