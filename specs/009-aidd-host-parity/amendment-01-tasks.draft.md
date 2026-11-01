# Draft tasks — amendment 01 host and CI portability

**DRAFT: not merged, not approved.** Source: companion spec and plan; security-sensitive rules R6/R9. Each task owns its file group; no agent runs wave tests or changes unrelated code. No deploy, push, dependency install or disabling enforcement is authorized by this draft.

Mechanical-check limitation for T-21: `D:/Fuentes/b1SycLink/tools/task_precision_check.py` `extract_paths` strips a leading `.` via `strip(".,;:()'\"")`, so it reports `github/workflows/test.yml` missing even though `.github/workflows/test.yml` exists. Preserve the real path; this is a checker false positive, not permission to create a `github/` directory or bypass the pre-build audit.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-15 | FR-915, AC-907 | `tests/test_aidd_readiness.py` | LOGIC | | | other tests |
| T-16 | FR-915, AC-908 | `tests/test_visual_review_binding.py` | LOGIC | | | production review code |
| T-17 | FR-916, AC-911 | `skill/scripts/flowmap.py` | LOGIC | | | HTML changes |
| T-18 | FR-917, AC-909 | `tests/test_cross_platform_paths.py` | LOGIC | | | gate implementation |
| T-19 | FR-917, AC-909 | `skill/hooks/rule_gate.py` | LOGIC | | | fingerprint semantic changes |
| T-20 | FR-918, AC-910 | `skill/scripts/aidd_memory_import.py` | LOGIC | | | external file imports |
| T-21 | FR-915, FR-919, AC-911 | `.github/workflows/test.yml` | LOGIC | | | publishing |
| T-22 | FR-915..FR-919, AC-907..AC-911 | `specs/009-aidd-host-parity/evidence/amendment-01-ci.txt` | LOGIC | | | implementation |
| T-23 | FR-920, AC-912 | `tests/report_guard_portability.py` | LOGIC | | | guard changes or exceptions |
| T-24 | FR-915, FR-919, AC-913 | `tests/test_ci_runner.py` | LOGIC | | | runner implementation |
| T-25 | FR-915, FR-919, AC-913 | `tests/run_parallel.py` | LOGIC | | | workflow or production runtime |
| T-26 | FR-921 | `tests/requirements-test.txt` | LOGIC | | | runtime package dependencies |

## Per-task detail (one block per row above)

### T-15 — preserve readiness tests in unittest discovery
**Classify**
- Nature: INCIDENT
- Kind: LOGIC
**Estimate**
- Agent min: 12
- Human ref hours: 0.60
- Tokens (est): 100k
- Agent role: tests
- Model tier: medium
- Wave: 1
**Detail**
- Size: ~100 changed lines.
- Goal: no `pytest` dependency and no loss of the eight current tests or two parametrized values.
- Cites: FR-915, AC-907.
- Depends on: none.
- Read first: `tests/test_aidd_readiness.py` in full.
- Files to change: `tests/test_aidd_readiness.py` only.
- Naming contract: `unittest.TestCase` class `TestAiddReadiness`; temporary directories via `tempfile.TemporaryDirectory`; mocks via `unittest.mock`. Methods: `test_reports_explicit_line_references_and_real_hashes`, `test_missing_required_artifact_is_not_checked`, `test_changed_input_during_checker_is_unstable`, `test_checker_failures_are_preserved_gaps`, `test_checker_failures_are_preserved_checker_error`, `test_pending_approval_and_implementation_refs_are_deferred`, `test_invalid_approval_is_not_deferred`, `test_cli_does_not_overwrite_existing_output`, `test_real_checker_is_invoked`.
- Behaviour: replace pytest fixture, monkeypatch and parametrization with stdlib fixtures and two separately named test cases for the two return codes; preserve all asserted values, so unittest discovery counts at least nine cases.
- Tests first: run `python -m unittest discover -s tests -p test_aidd_readiness.py -v` in a clean interpreter without pytest; record import error and zero executed pytest functions.
- Verify: `python -m unittest discover -s tests -p test_aidd_readiness.py -v` -> exit 0 and at least nine cases; `python -m py_compile tests/test_aidd_readiness.py` -> exit 0.
- Do NOT: remove scenarios, add pytest, alter production code or claim other test results.
- Done when: focused discovery runs all cases; orchestrator records output.
- Open questions: none.

### T-16 — preserve visual binding tests in unittest discovery
**Classify**
- Nature: INCIDENT
- Kind: LOGIC
**Estimate**
- Agent min: 10
- Human ref hours: 0.50
- Tokens (est): 100k
- Agent role: tests
- Model tier: medium
- Wave: 1
**Detail**
- Size: ~100 changed lines.
- Goal: six existing snapshot and approval-binding test functions execute under unittest without pytest.
- Cites: FR-915, AC-908.
- Depends on: none.
- Read first: `tests/test_visual_review_binding.py` in full.
- Files to change: `tests/test_visual_review_binding.py` only.
- Naming contract: `unittest.TestCase` class `TestVisualReviewBinding`, `tempfile.TemporaryDirectory`, `assertRaisesRegex`, existing `unittest.mock`. Methods: `test_changed_missing_or_unrecorded_snapshot_never_passes`, `test_new_snapshot_changes_all_item_digests`, `test_incomplete_external_and_escape_declarations_are_refused`, `test_legacy_review_digest_is_unchanged`, `test_snapshot_resolution_error_fails_closed`, `test_approval_binding_blocks_code_and_close_after_new_snapshot`.
- Behaviour: translate pytest temp-path and raises usage to unittest, preserving all edge cases and values.
- Tests first: clean-interpreter `python -m unittest discover -s tests -p test_visual_review_binding.py -v` records pytest import failure.
- Verify: `python -m unittest discover -s tests -p test_visual_review_binding.py -v` -> exit 0 and at least six cases; `python -m py_compile tests/test_visual_review_binding.py` -> exit 0.
- Do NOT: skip cases, weaken snapshots, introduce a new dependency or alter product code.
- Done when: all six cases run; orchestrator records output.
- Open questions: none.

### T-17 — make flowmap compatible with Python 3.10 and 3.11
**Classify**
- Nature: INCIDENT
- Kind: LOGIC
**Estimate**
- Agent min: 8
- Human ref hours: 0.40
- Tokens (est): 65k
- Agent role: builder
- Model tier: medium
- Wave: 1
**Detail**
- Size: ~5 changed lines and mirrored copy.
- Goal: preserve HTML output while removing the backslash from an f-string expression.
- Cites: FR-916, AC-911.
- Depends on: none.
- Read first: `skill/scripts/flowmap.py` around line 1468 and `tests/test_flowmap.py`.
- Files to change: `skill/scripts/flowmap.py`, byte-identical `adapters/dot-aidd/scripts/flowmap.py`.
- Naming contract: local `model_json` holds `json.dumps(model).replace('</', '<\\/')` before composing the HTML.
- Behaviour: use `model_json` in the f-string and retain `id="model"`, script closing protection and surrounding markup; regenerate mirror by script after dry-run and post-check.
- Tests first: parse current source using `ast.parse(..., feature_version=(3, 10))` and record the syntax failure.
- Verify: `python -m unittest discover -s tests -p test_flowmap.py -v` -> exit 0 in Python 3.10, 3.11 and 3.12; mirrored file is byte-identical.
- Do NOT: change flow semantics, JS contents, HTML text or unrelated files.
- Done when: focused checks and supported-version matrix pass.
- Open questions: none.

### T-18 — add portable path and guard regression cases
**Classify**
- Nature: INCIDENT
- Kind: LOGIC
**Estimate**
- Agent min: 12
- Human ref hours: 0.60
- Tokens (est): 110k
- Agent role: tests
- Model tier: high
- Wave: 1
**Detail**
- Size: ~140 changed lines.
- Goal: prove R6/R9 deny aliases and permit unrelated native files on both operating systems.
- Cites: FR-917, AC-909, FR-1003.
- Depends on: none.
- Read first: `tests/test_rule_gate.py` TestR9ProtectedPaths, TestB3CanonicalPaths, TestReviewArtifactGuard and TestSpecsShellGuardAnyId; `skill/hooks/rule_gate.py` `_specs_tok`, `_abs_path_raw`, `_locate`.
- Files to change: `tests/test_cross_platform_paths.py` only.
- Naming contract: `test_native_protected_and_unrelated`, `test_drive_unc_extended_tokens`, `test_relative_parent_and_nested_project`, `test_case_and_stream_aliases`, `test_native_symlink_and_windows_junction`; target functions and tools use current signatures; temp project roots created by stdlib tempfile.
- Behaviour: cover POSIX absolute/relative, Windows drive, UNC `\\\\server\\share`, extended UNC `\\\\?\\UNC\\server\\share`, mixed slash/case, `..`, suffix/stream, nested project named specs, native symlink and Windows junction when available. Include protected and unrelated paths, lexical-only and real gate events, and explicitly flag platform-unavailable cases.
- Tests first: create all five named test methods and their real assertions in `tests/test_cross_platform_paths.py`; the orchestrator then runs `python -m unittest discover -s tests -p test_cross_platform_paths.py -v` before T-19 and confirms that every named method was collected and at least one intended assertion fails. Missing module, import error, zero tests or an environment-only skip is not a valid red result.
- Verify: `python -m unittest discover -s tests -p test_cross_platform_paths.py -v` -> exit 0 on Ubuntu and Windows 3.10–3.12 after T-19, without reducing existing gate coverage.
- Do NOT: access a real network share, silence failed denial, assert Windows path denotes a local POSIX file, or use global filesystem writes.
- Done when: coverage and all matrix results recorded by orchestrator.
- Open questions: none.

### T-19 — preserve protected-path gates across hosts
**Classify**
- Nature: INCIDENT
- Kind: LOGIC
**Estimate**
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 130k
- Agent role: builder
- Model tier: high
- Wave: 2
**Detail**
- Size: ~140 changed lines and mirrored copies.
- Goal: make the current security decision semantics portable without weakening R6/R9.
- Cites: FR-917, FR-920, AC-909, AC-912, FR-1003.
- Depends on: T-18, T-23 and integration/freeze of the fingerprint amendment in spec 007 for shared `skill/scripts/aidd_evidence.py`; use the same owner and serialize edits. If T-23 finds old/new decision differences, wait for owner-reviewed, narrowly enumerated spec-010 exceptions before implementing those corrections.
- Read first: `skill/hooks/rule_gate.py` `_specs_tok`, `_abs_path_raw`, `_locate`; `skill/scripts/aidd_evidence.py` `real_path`, `rel_to_root`; T-18 test results and `tests/test_rule_gate_shell_speed.py`.
- Files to change: `skill/hooks/rule_gate.py`, `skill/scripts/aidd_evidence.py` only if native canonical resolution actually requires it; corresponding `adapters/dot-aidd/` mirrors via script.
- Naming contract: retain existing public/helper signatures; native paths use filesystem realpath, foreign drive/UNC spellings are lexical tokens and never converted to a real local path.
- Behaviour: native path resolution remains realpath-aware for symlinks/junctions and containment; detect guarded spec/artifact and `.aidd` aliases conservatively for foreign spellings and mixed separators; allow legitimate unrelated native paths. POSIX case-sensitive native names are distinct filesystem objects; do not assert foreign Windows tokens are native files. Keep Windows canonical handling and caches. Apply only enumerated owner-approved spec-010 exceptions from T-23; retain exact decisions/messages for all other baseline cases. Serialize `aidd_evidence.py` with spec 007.
- Tests first: T-18 red cases are provided by orchestrator before editing.
- Verify: `python -m unittest discover -s tests -p test_cross_platform_paths.py -v`, `python -m unittest discover -s tests -p test_rule_gate.py -v`, `python -m unittest discover -s tests -p test_rule_gate_shell_speed.py -v`, and `python -m unittest discover -s tests -p test_dot_aidd_mirror.py -v` -> exit 0 in coordinated wave on Windows and Linux.
- Do NOT: disable rules, special-case only CI paths, change authorization semantics, rely solely on lexical path prefix for native files, or claim POSIX validates Windows filesystem access.
- Done when: all denial and allow tests, equivalence and mirrors pass; independent security audit completes.
- Open questions: none.

### T-20 — repair Windows memory-import path normalization
**Classify**
- Nature: INCIDENT
- Kind: LOGIC
**Estimate**
- Agent min: 10
- Human ref hours: 0.50
- Tokens (est): 80k
- Agent role: builder
- Model tier: medium
- Wave: 1
**Detail**
- Size: ~80 changed lines and mirrored copy.
- Goal: retain inside-project absolute paths as relative paths on both OSes and retain rejection of outside/sensitive paths.
- Cites: FR-918, AC-910.
- Depends on: none.
- Read first: `skill/scripts/aidd_memory_import.py` `_norm_repo_file` and `_files`; `tests/test_aidd_memory_import.py` `test_files_normalised`, `test_codes_why_files`.
- Files to change: `skill/scripts/aidd_memory_import.py`, its byte-identical `adapters/dot-aidd/scripts/aidd_memory_import.py` mirror, and `tests/test_aidd_memory_import.py` (same owner).
- Naming contract: retain `_norm_repo_file(f, root)` and `_files(modified, read, root)` signatures and POSIX-style output.
- Behaviour: diagnose Windows absolute-in-root conversion and preserve native canonical containment. For nonexistent relative paths, resolve all existing parent symlinks with `Path.resolve(strict=False)` and allow only proven in-root paths. Reject sibling-prefix paths, `..`, foreign absolute drive/UNC paths whose containment cannot be proven, symlink/junction escapes and protected paths; do not treat differently cased POSIX objects as equal. Sanitize before output. If diagnosis contradicts these rules stop and report rather than guess.
- Tests first: add cases to `tests/test_aidd_memory_import.py` for an existing in-root file, sibling prefix, `..`, native symlink/junction pointing outside, foreign drive/UNC spelling, a nonexistent relative path with safe parents and a nonexistent path under an escaping symlink. Record the intended red result with `python -m unittest discover -s tests -p test_aidd_memory_import.py -v` before implementation; unavailable symlink/junction cases are not-verified, not passes.
- Verify: `python -m unittest discover -s tests -p test_aidd_memory_import.py -v` -> exit 0 on both OSes; mirrors byte-identical.
- Do NOT: relax external-path rejection, expose private paths or change storage format.
- Done when: matrix results pass with no privacy regression.
- Open questions: none.

### T-21 — execute complete stdlib CI and pinned guard baseline
**Classify**
- Nature: INCIDENT
- Kind: LOGIC
**Estimate**
- Agent min: 8
- Human ref hours: 0.40
- Tokens (est): 60k
- Agent role: builder
- Model tier: medium
- Wave: 3
**Detail**
- Size: ~20 changed lines.
- Goal: maintain six-cell matrix and prevent silent lack of pinned guard equivalence coverage.
- Cites: FR-915, FR-919, AC-907, AC-908, AC-911.
- Depends on: T-25 and T-26 for execution; execution also depends on T-15, T-16, T-17, T-19 and T-20.
- Read first: `.github/workflows/test.yml`; `tests/test_rule_gate_shell_speed.py` `PINNED_COMMIT` and `load_old_guard`; the T-25 and T-26 contracts below.
- Files to change: `.github/workflows/test.yml` only.
- Naming contract: checkout has `fetch-depth: 0`; run `git cat-file -e '3cf5fccaa395f1dbe709b0ce800d1ad412418d39^{commit}'`; install pinned test-only dependencies with `python -m pip install -r tests/requirements-test.txt`; execute `python tests/run_parallel.py --ci-guard` once; workflow job uses `timeout-minutes: 30` so an overdue cell fails.
- Behaviour: keep Ubuntu and Windows on Python 3.10, 3.11 and 3.12; runner performs actual guard-loader preflight and counts tests, failures and skips from the single discovery. Existing `python -m pytest` verification rows remain supported through the test-only dependency. Do not run separate redundant module discovery in CI.
- Tests first: current workflow lacks history and current clean CI imports fail; cite run 40691930673, do not launch a new workflow.
- Verify: `git cat-file -e '3cf5fccaa395f1dbe709b0ce800d1ad412418d39^{commit}'` -> exit 0 under native Windows PowerShell and native Linux Bash; `python tests/run_parallel.py --ci-guard` -> exit 0 once per verified matrix cell; after authorized push all six GitHub cells must be green and runner output must show named cases and successful loader preflight.
- Do NOT: construct the quoted revision from untrusted input, treat commit presence as sufficient to skip loader preflight, change matrix, disable tests, add pytest to runtime dependencies, publish, push or deploy.
- Done when: full matrix passes, with concrete logs and no missing-baseline skip.
- Open questions: none.

### T-22 — coordinated verification and evidence
**Classify**
- Nature: REQUIREMENT
- Kind: LOGIC
**Estimate**
- Agent min: 20
- Human ref hours: 1.00
- Tokens (est): 60k
- Agent role: tests
- Model tier: high
- Wave: 4
**Detail**
- Size: ~80 changed lines of evidence.
- Goal: execute exactly one coordinated check round and record actual results per OS/version.
- Cites: FR-915..FR-921, AC-907..AC-914.
- Depends on: T-15, T-16, T-17, T-18, T-19, T-20, T-21, T-23, T-24, T-25, T-26.
- Read first: companion plan, current task blocks and `tests/test_dot_aidd_mirror.py`.
- Files to change: `specs/009-aidd-host-parity/evidence/amendment-01-ci.txt` only.
- Naming contract: one block per command with exact command, OS, interpreter, exit code, count and evidence; six matrix cells individually recorded.
- Behaviour: use focused and guard-equivalence evidence from completed waves; compare old pytest V-1–V-4 collection against new unittest discovery by case ID without executing those cases. Execute consolidated V-5 once per OS/interpreter cell through the same CI run. From that run's tracked started and skipped IDs, filter each of the five historical modules listed in T-25 and record per module its collected count, started count, every skipped ID and its reason, or explicitly zero skips. Compare these records to the pre-consolidation collection and existing historical evidence; a missing ID, unreported skip, unavailable skip reason or a skip whose former executed assertion is not covered leaves that check not-verified and prevents declaring its coverage consolidated. Retain any uncovered check as a separate verification row; do not run V-1–V-4 again when their checks are proven covered. Record missing/changed cases and mark unavailable platforms not-verified. Review CI logs only after authorized push; no external write in this task.
- Tests first: not applicable; verification task.
- Verify: `python tests/run_parallel.py --ci-guard` -> exit 0 once in each verified OS/interpreter cell; old/new collection comparison has zero missing cases or an explicitly retained uncovered check; each cell reports all five modules' counts and skipped IDs with reasons (including explicit zero), with uncovered or unknown skip coverage retained separately; all six matrix cells have executed outputs or explicit not-verified; independent security and functional audits follow.
- Do NOT: run parallel builds in same worktree, claim Linux from Windows, repeat full suite per task, edit code or create a database.
- Done when: executed results and limitations are recorded and independently audited.
- Open questions: none.

### T-23 — document old, current and desired portable-path decisions
**Classify**
- Nature: INCIDENT
- Kind: LOGIC
**Estimate**
- Agent min: 12
- Human ref hours: 0.60
- Tokens (est): 120k
- Agent role: tests
- Model tier: high
- Wave: 1
**Detail**
- Size: ~140 changed lines plus focused fixture tests.
- Goal: identify each actual exception to spec 010 FR-1003 without presuming the old guard's decisions.
- Cites: FR-920, AC-912, FR-1003.
- Depends on: none.
- Read first: `tests/test_rule_gate_shell_speed.py` `load_old_guard`, `event`, `old`, `new`, `compare`; `tests/test_rule_gate.py` failing cases from run 40691930673.
- Files to change: `tests/report_guard_portability.py`, `tests/test_guard_portability_report.py` only.
- Naming contract: reporter `collect_cases(root)`, `compare_cases(old_guard, new_guard, cases)` and `main()`; each output row includes OS, input ID, old decision/message, current decision/message and desired deny/allow. The reporter uses temporary project fixtures and the existing old-guard loader.
- Behaviour: report actual path strings and gate events for `D:/proj/specs/F23-eDoc-POS/tasks.md`, `D:/proj/specs/F23-eDoc-POS/review.md`, drive and mixed-case protected files, protected `.aidd` aliases, UNC and extended UNC, a native POSIX protected path and an unrelated native path. Include each distinct reported failing input from the referenced CI tests. Run on Windows and Linux, record loader failure explicitly, and return nonzero if the baseline cannot be loaded. Results are evidence, not permission to change a guard. The orchestrator enumerates each actual deviation from FR-1003; owner review of those exact exceptions and spec-010 reconciliation are prerequisites for T-19.
- Tests first: write `tests/test_guard_portability_report.py` with fake old/new decisions and allow/deny fixtures; run `python -m unittest discover -s tests -p test_guard_portability_report.py -v` before creating the reporter and record import failure, not zero tests.
- Verify: `python -m unittest discover -s tests -p test_guard_portability_report.py -v` -> exit 0; `python tests/report_guard_portability.py` -> exit 0 and includes one old/current/desired row per case on each available OS.
- Do NOT: invent old decisions, change a guard, approve exceptions, access a real UNC share, or claim unavailable OS evidence.
- Done when: actual results and reviewed exception list exist for both OSes; otherwise T-19 remains blocked on that evidence.
- Open questions: none.

### T-24 — prove CI runner fails on missing coverage
**Classify**
- Nature: INCIDENT
- Kind: LOGIC
**Estimate**
- Agent min: 12
- Human ref hours: 0.60
- Tokens (est): 100k
- Agent role: tests
- Model tier: medium
- Wave: 1
**Detail**
- Size: ~140 changed lines.
- Goal: verify CI result counting and preflight without executing the full suite twice.
- Cites: FR-915, FR-919, AC-913.
- Depends on: none.
- Read first: `tests/test_rule_gate_shell_speed.py` `load_old_guard` and three equivalence methods.
- Files to change: `tests/test_ci_runner.py` only.
- Naming contract: `test_required_cases_pass`, `test_missing_case_fails`, `test_renamed_required_case_fails`, `test_required_skip_fails`, `test_failure_or_error_fails`, `test_guard_loader_failure_fails`, `test_collection_error_fails`, `test_instrumentation_error_fails`, `test_zero_cases_fails`, `test_timeout_fails`; import `tests/run_parallel.py` by path.
- Behaviour: use synthetic `unittest.TestSuite` fixtures and a fake guard loader to assert passed, missing, same-count-but-renamed, skipped, failing, crashing and zero-case behavior; assert failure produces nonzero and diagnostics. Make the collector and the result instrumentation fail separately and assert neither failure is omitted or treated as passing. Test preflight loader returning `(None, reason)` separately from a missing Git object. Mock the child invocation to raise `subprocess.TimeoutExpired` and assert the launcher reports timeout and returns 1. No real full-suite subprocess or external resource is needed for these fixture tests.
- Tests first: write the named methods first and run `python -m unittest discover -s tests -p test_ci_runner.py -v`; record the missing `--ci-guard` helpers' attribute or import failure, not a zero-test result.
- Verify: `python -m unittest discover -s tests -p test_ci_runner.py -v` -> exit 0 once T-25 exists.
- Do NOT: run full discovery as part of the synthetic tests, silence skips or permit missing cases.
- Done when: red then green results are recorded by orchestrator.
- Open questions: none.

### T-25 — run one full discovery with verified required coverage
**Classify**
- Nature: INCIDENT
- Kind: LOGIC
**Estimate**
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 90k
- Agent role: builder
- Model tier: high
- Wave: 2
**Detail**
- Size: ~140 changed lines.
- Goal: run the unittest suite once and fail closed on absent required coverage.
- Cites: FR-915, FR-919, AC-907, AC-908, AC-913.
- Depends on: T-24.
- Read first: `tests/test_rule_gate_shell_speed.py` `load_old_guard` and the T-24 named fixture-test contract.
- Files to change: `tests/run_parallel.py` only.
- Naming contract: retain existing `main(argv)` and unchanged default invocation; add `TrackingResult`, `run_suite(suite, stream, required_ids)`, `run_checked(argv, timeout_seconds=1500)`, `load_old_guard()` from the existing shell-speed test module and `--ci-guard`/`--ci-guard-worker` options. Required IDs are exactly the fully qualified 18 names in the list below, not only counts.
- Required IDs: `test_aidd_readiness.TestAiddReadiness.test_reports_explicit_line_references_and_real_hashes`, `test_aidd_readiness.TestAiddReadiness.test_missing_required_artifact_is_not_checked`, `test_aidd_readiness.TestAiddReadiness.test_changed_input_during_checker_is_unstable`, `test_aidd_readiness.TestAiddReadiness.test_checker_failures_are_preserved_gaps`, `test_aidd_readiness.TestAiddReadiness.test_checker_failures_are_preserved_checker_error`, `test_aidd_readiness.TestAiddReadiness.test_pending_approval_and_implementation_refs_are_deferred`, `test_aidd_readiness.TestAiddReadiness.test_invalid_approval_is_not_deferred`, `test_aidd_readiness.TestAiddReadiness.test_cli_does_not_overwrite_existing_output`, `test_aidd_readiness.TestAiddReadiness.test_real_checker_is_invoked`; `test_visual_review_binding.TestVisualReviewBinding.test_changed_missing_or_unrecorded_snapshot_never_passes`, `test_visual_review_binding.TestVisualReviewBinding.test_new_snapshot_changes_all_item_digests`, `test_visual_review_binding.TestVisualReviewBinding.test_incomplete_external_and_escape_declarations_are_refused`, `test_visual_review_binding.TestVisualReviewBinding.test_legacy_review_digest_is_unchanged`, `test_visual_review_binding.TestVisualReviewBinding.test_snapshot_resolution_error_fails_closed`, `test_visual_review_binding.TestVisualReviewBinding.test_approval_binding_blocks_code_and_close_after_new_snapshot`; `test_rule_gate_shell_speed.TestRuleGateShellSpeed.test_equivalence_handwritten`, `test_rule_gate_shell_speed.TestRuleGateShellSpeed.test_equivalence_generated_300`, `test_rule_gate_shell_speed.TestRuleGateShellSpeed.test_equivalence_bare_names_that_are_links`.
- Behaviour: with `--ci-guard`, invoke this same script once with `--ci-guard-worker` via `subprocess.run` using `sys.executable`, captured text stdout/stderr and a 1500-second timeout; forward both streams, return the worker's nonzero result, and catch `TimeoutExpired` to report timeout and return 1. The worker preflight calls the real `load_old_guard()`; `(None, reason)` produces diagnostic and exit 1. Discover all `tests` once, use a `TextTestRunner` result tracking started and skipped case IDs, and report started IDs, skipped IDs and their reasons, and counts without losing failures, so T-22 can attribute every historical case to its module. Require every one of the 18 exact IDs to start and not be skipped; fail on any suite failure/error, missing or renamed required ID, or collector/instrumentation failure. Before replacing existing V-1–V-4, compare `pytest --collect-only -q` IDs for `tests/test_host_install.py`, `tests/test_host_gates.py`, `tests/test_host_doctor.py`, `tests/test_aidd_status.py`, `tests/test_dot_aidd_mirror.py` against this discovery on Windows and Linux without executing cases; normalize path/module separators only. A missing, extra, parametrized or unresolvable ID blocks consolidation until explained, and each case remains enforced. Preserve the default `run_parallel.py` CLI and behavior for every call without `--ci-guard`; the workflow's 30-minute timeout is an additional fail-closed backstop.
- Tests first: T-24 must be red because `--ci-guard` helpers are missing from the existing runner before this change.
- Verify: `python -m unittest discover -s tests -p test_ci_runner.py -v` -> exit 0 in the focused wave; the sole final V-5 `python tests/run_parallel.py --ci-guard` -> exit 0 once per verified OS/interpreter cell.
- Do NOT: run discovery multiple times, accept required skips, trust only `git cat-file`, change tests, write approvals or mark an unavailable platform green.
- Done when: fixture tests, actual preflight and one full discovery pass in every verified matrix cell.
- Open questions: none.

### T-26 — pin the verification-only pytest dependency
**Classify**
- Nature: INCIDENT
- Kind: LOGIC
**Estimate**
- Agent min: 5
- Human ref hours: 0.25
- Tokens (est): 35k
- Agent role: builder
- Model tier: medium
- Wave: 1
**Detail**
- Size: 1 changed line.
- Goal: preserve execution of existing spec 009/010 `python -m pytest` rows without a production dependency.
- Cites: FR-921.
- Depends on: none.
- Read first: `pyproject.toml`, `specs/009-aidd-host-parity/spec.md`, `specs/010-aidd-shell-guard-speed/spec.md` verification rows.
- Files to change: `tests/requirements-test.txt` only.
- Naming contract: exact content `pytest==8.3.5` with newline; Python runtime dependencies in `pyproject.toml` remain unchanged.
- Behaviour: create the test-only requirements file; T-21 installs it in CI. The release runtime remains stdlib-only.
- Tests first: in a clean CI-like environment the existing pytest verification command fails due to missing pytest; use run 40691930673 evidence, not an environment mutation.
- Verify: `python -m pytest --version` -> exit 0 and version 8.3.5 in the prepared test environment; `python -m pip check` -> exit 0.
- Do NOT: add a runtime dependency, install packages globally, change existing verification rows, publish or push.
- Done when: pin is installed only in a test environment and existing verification commands are demonstrably runnable.
- Open questions: none.

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-15, T-16, T-17, T-18, T-20, T-23, T-24, T-26 | tests, builder | 12 | 710 | 0.60 |
| 2 | T-19, T-25 | builder | 15 | 220 | 0.75 |
| 3 | T-21 | builder | 8 | 60 | 0.40 |
| 4 | T-22 | tests | 20 | 60 | 1.00 |

Total agent time (critical path): 55 min
Total tokens (k): 1050
