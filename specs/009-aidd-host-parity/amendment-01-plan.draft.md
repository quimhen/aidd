# Draft plan — amendment 01 host and CI portability

**DRAFT — R6 approval required before implementation.** No UI or database change. Reuse the existing rule gate and path helpers; do not implement a second policy engine. The exact code changes and regression cases are in the companion task draft.

## Naming & File Contract (fill this first — everything below depends on it)
| Item | Convention |
|---|---|
| Classes / components / types | Python PascalCase test classes; existing function-style modules remain function-style |
| Functions / variables / methods | Python snake_case; preserve existing public signatures |
| File names | Existing snake_case paths in `skill/`, `tests/` and `.github/workflows/` |
| Classes per file | Keep existing classes; do not combine unrelated new classes |
| File-path pattern (if one exists) | `skill/` sources and byte-identical required `adapters/dot-aidd/` mirrors; `tests/test_*.py` |

## File ownership and dependencies

| Target | Task | Contract |
|---|---|---|
| `tests/test_aidd_readiness.py` | T-15 | Convert existing eight pytest functions into unittest cases, preserving two parameter values (at least nine cases). |
| `tests/test_visual_review_binding.py` | T-16 | Convert existing six pytest functions into unittest cases with snapshot and gate assertions intact. |
| `skill/scripts/flowmap.py`, mirror | T-17 | Precompute escaped JSON outside f-string expression; preserve rendered output and signature. |
| `tests/test_cross_platform_paths.py` | T-18 | Add native/foreign spelling and deny/allow regression cases; no real network share needed. |
| `skill/hooks/rule_gate.py`, `skill/scripts/aidd_evidence.py`, mirrors | T-19 | Preserve native real-path checks; foreign spelling cannot be mistaken for a local path; keep R6/R9 fail-closed. This overlaps the fingerprint amendment in spec 007: T-19 waits for its `aidd_evidence.py` work to be integrated and frozen, then the same file owner applies T-19 serially; do not start both at once. |
| `skill/scripts/aidd_memory_import.py`, mirror | T-20 | Diagnose absolute path conversion on Windows; preserve inside project relative path and rejection of outside paths. |
| `tests/test_aidd_memory_import.py` | T-20 | Add explicit inside/outside, sibling-prefix, symlink/junction, foreign path and nonexistent-relative cases; same owner as importer. |
| `tests/report_guard_portability.py` | T-23 | Compare old/current/desired for reported guard regressions on each OS before changing the guard; publish the exact proposed exception list for owner review. |
| `tests/test_ci_runner.py` | T-24 | Test runner's exact exit, required-case and skip handling with synthetic stdlib suites. |
| `tests/run_parallel.py` | T-25 | Add `--ci-guard` to the existing runner (default behavior unchanged): load pinned guard, run full discovery once, count named cases and fail on failures, skips of required cases, unavailable baseline, exceptions or timeout. |
| `tests/requirements-test.txt` | T-26 | Pin `pytest==8.3.5` only as test dependency for existing spec 009/010 verification rows; runtime dependencies stay empty. |
| `.github/workflows/test.yml` | T-21 | Keep six-cell matrix, install test-only requirements, run the CI runner once and make the pinned guard available. |
| evidence only | T-22 | Run tests once in coordinated round and record actual matrix results; no invented Linux evidence. |

## Security and verification contract

Path parsing must distinguish native filesystem resolution from lexical recognition of a foreign-platform spelling. Actual symlink/junction targets and `..` containment use native canonical resolution. A foreign Windows drive/UNC string on POSIX must never be asserted to name a real local path merely because it resembles one. Protected spec artifacts or `.aidd` in an ambiguous foreign token are denied; unrelated native files are allowed. POSIX native `.AIDD` and `.aidd`, or names with trailing dots, may be distinct: do not claim they are the same filesystem object. A Windows-style token carries Windows alias semantics and is classified conservatively without granting access. For memory import, allow a nonexistent relative file only if resolving its existing ancestors proves containment; reject foreign absolute paths that cannot be mapped safely, sibling prefixes, traversal and symlink/junction escapes. Existing privacy restrictions remain. Unavailable native link/junction capabilities are explicitly not verified.

Before T-19, T-23 compares pinned and current guards with each reported failing input on Windows and Linux and records `(old, current, desired)`. Any actual deviation from spec 010 FR-1003 is proposed as a named, minimal security correction and requires reconciliation of spec 010 and owner approval; all remaining generated and handwritten cases retain exact decision/message parity. Never broadly waive FR-1003. T-24 then T-25 establish one cross-platform stdlib runner: `tests/run_parallel.py --ci-guard` launches its worker once; the worker calls `load_old_guard()` and fails if it returns `None`, performs one `unittest` discovery and tracks the exact IDs and skips. The parent captures and forwards stdout/stderr, preserves failure and turns a child timeout into a nonzero result; the workflow job has a longer timeout. Required equivalence skips fail; an unavailable native junction is recorded as not verified rather than pass.

Builders use static checks only; the orchestrator executes focused tests once in their respective waves. For final close, 009 V-5 and CI both name `python tests/run_parallel.py --ci-guard`; one actual run per OS/interpreter cell supplies its evidence without rerunning the suite for V-1–V-4. Before consolidating, compare test IDs collected by old V-1–V-4 and new discovery without executing either set; prove identical coverage on both OSes, preserve assertions and report conditional skips. Only if complete may historical V-1–V-4 become traceability records; keep any demonstrably uncovered check separate. Changing the Verification table invalidates its old approval and requires a new one. Python test-only dependencies are pinned in `tests/requirements-test.txt`; runtime dependencies remain empty and spec 010 pytest rows remain unchanged. Six-cell GitHub evidence requires an authorized push or independently verified CI; Windows alone does not prove Ubuntu. Pinned SHA is `3cf5fccaa395f1dbe709b0ce800d1ad412418d39`; CI checks `git cat-file -e '3cf5fccaa395f1dbe709b0ce800d1ad412418d39^{commit}'` under native Windows PowerShell and native Linux Bash. The static quoted argument is not built from untrusted text and does not replace loader preflight.

Pre-build collection-only observation on Windows: the five current V-1–V-4 modules produced 307 case IDs through `pytest --collect-only` and the same 307 IDs through unittest discovery, with zero missing and zero additional IDs. Neither collection executed those tests. This is a baseline for the current checkout only, not evidence of equivalent execution, unchanged behavior after conversion, or Linux coverage; T-25/T-22 must verify those conditions without running another full suite.
