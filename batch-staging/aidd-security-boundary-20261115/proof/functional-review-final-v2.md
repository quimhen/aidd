# Independent functional review — AIDD4b final v2

Owner: Julio. Wave: AIDD4B. Approved tasks: 4e4fde48. Verdict: PASS for the isolated approved security-boundary runtime at final round06 identity. Both functional-review-round01.md and functional-review-final.md are preserved as evidence for their earlier source scopes. This v2 replaces the earlier PASS only for the final tiny algorithm-parity delta and current coherent execution evidence; all prior reviewed functional controls remain unchanged.

Native graph was queried before bounded source/test/evidence reads. No source authorship, test reruns, builds, DB, installation or remote action by this reviewer. Only mechanical artifact/hash checks and this report write were performed.

## Semantic delta and meaningful proof

_reusable_input_rows in aidd_status.py now refuses a prior run unless its top-level code_algorithm equals ev.EVIDENCE_ALGORITHM, in addition to its existing stable/current-input-algorithm contract checks. This prevents a mixed event with current input_algorithm but missing/old top-level code_algorithm from reaching same-spec local reuse. Refusal causes ordinary plain verification execution and a newly emitted current proof, without mutating the old event. It aligns this path with the already reviewed planner/cross-spec source algorithm boundaries.

The existing public plain-verify test was extended with exactly two subcases: old top code algorithm and missing top code algorithm while explicitly retaining the current input algorithm. Distinct full commands isolate store keys. Each requires one actual executor call, a non-reused result and current emitted input_algorithm. Existing old/missing input-algorithm cases remain. Method count therefore does not increase. Actual preserved RED log V-4B1-plain-top-algorithm-RED.log shows the two top-code subcases failing with zero executions before the predicate, 1 selected method, 4.975s. Final round06 V-4B1 includes the extended method and passes; this reviewer did not rerun either execution.

Mechanical comparison of all 77 round05/round06 pins shows only aidd_status.py, its mirror and tests/test_historical_reuse_security.py changed. The four other approved canonical runtime sources are unchanged. All five current source/mirror pairs are byte-identical. plain-top-algorithm-postcheck.json records the exact before/after status hashes, source frozen, static AST PASS, zero builder tests and 25 protected paths unchanged. This is isolated-package/protected-boundary evidence, not an independent claim that an original installation has been updated.

## Final six actual receipts

| Receipt | Exit | Methods | Receipt elapsed seconds |
|---|---:|---:|---:|
| V-4B1-GREEN-round06.json | 0 | 14 | 45.656 |
| V-4B2-GREEN-round06.json | 0 | 4 | 4.985 |
| V-4B3-GREEN-round06.json | 0 | 32 | 63.016 |
| V-4B4-GREEN-round06.json | 0 | 15 | 39.625 |
| V-4B5-GREEN-round06.json | 0 | 13 | 3.187 |
| V-4B6-GREEN-round06.json | 0 | 19 | 9.579 |

All actual log summaries show OK with the stated nonzero collection counts. These are 97 collected methods across six distinct current focused executions; they are not one combined historical suite or new methods introduced by the two subcases. Receipt wall time includes process/receipt overhead and differs from unittest timing.

Verified mechanically:

- Every receipt's before/after map is identical to final-verification-round06.json sourcePins and to the other five receipts: 77 inputs each.
- All 77 current files match those pins, with zero mismatches.
- All six actual log SHA256 values match both each row receipt and the final summary.
- Five canonical sources and five mirrors match byte-for-byte; only the approved status predicate changed among canonical source files since the preceding functional PASS.

The earlier report's twelve scenario groups, final-sink source/command/Expected/Inputs/environment/artifact checks, actual ROUND-SHARED distinction, coordinated planner-RUN cache bypass fix, dry-run identity controls, long-tail command refusal/strict4a amendment-only positive, same-spec/cross-spec latest source guards and raw --no-filters/new-algorithm migration remain applicable to the unchanged implementation and current successful six-row round. No historical legacy proof is promoted or repaired.

## Current canonical SHA256

- aidd_rules.py: 31ae5f48312776a3c7130229c8cc50fdf9e553d40ed67357bfada3aca0fd8cbe
- aidd_amendment_verify.py: d398f87437bba00fd834115af37824aad06efe0f803d7a5c36a58847f8565340
- aidd_round.py: f6640e4efa20b17610717e2592d51aefb798e4dd642f0f77d1960616fc926caa
- aidd_status.py: 1abfff8cb944ae3fb3be25866ca6dacb3865766b41a782cb903949a8f460a278
- aidd_evidence.py: 335aacce002f14c7bb6d1975fbbcbbb0bd007ed5544fb3538dcc42ed378cb676

No remaining concrete functional blocker in this bounded final scope. Original/main source, installed kernels, controlled publication, dependency-unit gates/seals and owner closure remain separate. final-verification-round06.json explicitly records originalOrInstalledKernelsChanged=false and installationClaim=false. No ERP reaudit, DB or broad 123/48 run was performed or requested here. Future input changes require targeted reassessment.
