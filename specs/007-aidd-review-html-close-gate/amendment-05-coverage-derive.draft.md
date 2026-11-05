# Draft — amendment 05 to spec 007: `aidd coverage` derives task Covers and Inputs, and `aidd verify --changed` stops refusing missing declarations

**DRAFT: not approved, not executable, no `Approved:` line.** Amendment intake: `AMENDMENT 05` of
`specs/007-aidd-review-html-close-gate` (verification and evidence accuracy). Siblings: amendment 03 (cross-spec reuse,
which needs `Inputs`), amendment 04 (renumbered/aliased targets, reused here), amendment 06 (alias graph; shares waves 11-14).
Owner direction (verbatim, 2026-11-03): "este tipo de mejoras con script que propones son las mejoras que debemos implementar en aidd".
Owner decisions D-1..D-3 (2026-11-03, answer to the question that listed them): user — "acepto recomendacion".
Prototype (staging only, not shipped): `batch-staging/coverage-derive/coverage_derive.py` + `test_coverage_derive.py` (14 tests, exit 0).

## Minimum Requirements Checklist

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | New `skill/scripts/aidd_coverage.py`; `--changed` selection in `skill/scripts/aidd_status.py`; `--base` resolution in `skill/scripts/aidd_unit_audit.py`; CLI entry in `aidd/cli.py`; mirrors | repo — `skill/scripts/aidd_status.py:2099-2137`, `skill/scripts/aidd_unit_audit.py:364-409` | — |
| New development or modification? | One new read-only tool; modification of `--changed` selection and of `--base` parsing | repo — `aidd/cli.py:448-457` | — |
| External service, API, integration? | None; Git only through the existing `git_changed_paths` and one `git rev-parse` | owner brief 2026-11-03 | — |
| Who is requesting it? | Owner (AIDD + b1SycLink) | user — "este tipo de mejoras con script que propones son las mejoras que debemos implementar en aidd" | — |
| Dependencies? | stdlib only; amendment 04 helpers `_resolve`, `_renumbered`, `_alias_target` of `aidd_progress.py` (T-27) | repo — `skill/scripts/aidd_progress.py:189-259` | — |
| Business objective | Make `aidd verify <spec> --changed` usable on real projects whose Verification rows cite FR/AC/API instead of T-nn and declare no Inputs | measured 2026-11-03 (below) | — |
| Expected visual fidelity | No mockup; CLI only | — | — |

## Executive summary

- **Problem (measured 2026-11-03 on b1SycLink, read-only):** `--changed` refuses unless EVERY row has `Inputs` and a
  `Covers` naming task IDs, and `_task_rows` only selects rows whose `Covers` names `T-nn`. In 51 b1SycLink specs with a
  Verification table: 254 rows, all with `Covers`, only 15 name `T-nn`, 0 have `Inputs`; 26 specs have tasks no row covers.
- **Derivation is possible by script:** 15 rows `cites-tasks`, 177 `via-fr-ac-api`, 57 `whole-suite`, 5 `unresolved`.
- **Owner decisions (user — "acepto recomendacion"):** D-1 a row without declarations always runs (warning naming the
  row) and an uncovered task whose target changed prints a warning and runs the whole-suite rows; refusal only for
  malformed Covers/Inputs. D-2 whole-suite rows keep all targets and their warning. D-3 `--base` accepts any revision Git
  resolves to a commit (`HEAD~1`).
- **Pilot with the decisions applied (F12, F21, F36, F37, P03, S01; changes of commit HEAD~1..HEAD; computed, not run):**
  33 rows (F36/F37 tables grew to 5 and 8 rows on 2026-11-03); 19 skipped, 14 run (F36 5, F37 8: the commit changed
  their `pur_*`/`pinv_*` tests and a whole-suite row pulls every task; S01 1 always-run row). Before the decisions every
  spec but F21 refused. Suffix and renumber resolution (`_resolve`, `_renumbered`) recover 23 F21, 12 F36 and 2 F37
  targets; the rest (ranges such as `1105..1118`, files never created) are excluded from Inputs and reported.
- **Safety argument:** an under-declared `Covers` or `Inputs` makes `--changed` SKIP a needed test — a false PASS.
  Hence: `aidd coverage` is a dry-run that never writes the spec; it never shrinks explicit declarations; whole-suite
  rows get every task and target; uncertain rows carry the review marker; the owner reviews and copies cells by hand.
  In `verify`, a missing declaration widens the run (always-run row, whole-suite rows), never narrows it, and a partial
  run never closes a spec.
- **Not in scope:** proposing `Reuse`; editing any spec automatically; creating rows for uncovered tasks.

## Functional requirements

| Code | Requirement | Source |
|---|---|---|
| FR-240 | `aidd coverage <spec_dir> [--apply-to FILE] [--json] [--changed-file PATH ...]` runs `skill/scripts/aidd_coverage.py`. Default is a read-only dry-run that prints, per `## Verification` row (parsed with `aidd_rules.parse_verification`): proposed `Covers`, proposed `Inputs`, derivation kind, `Reuse` note, notes; then a summary line and the tasks no row covers. Exit 0 on success, 2 on refusal (no `spec.md`, unsafe `--apply-to`). | owner brief 2026-11-03 |
| FR-241 | Derivation kind per row, first match wins: `cites-tasks` (Covers names a `T-nn` or a `T-a..T-b` range in the forms `_task_rows` accepts); `via-fr-ac-api` (Covers cites FR/AC/API/SCREEN/COMP/CTL/US codes that at least one task cites); `whole-suite` (no code in Covers, or a suite word: todos, toda, todas, suite, completa, complete, regresión, regression, all, full, whole); `unresolved` (codes present, none cited by any task). | measured: 15 / 177 / 57 / 5 of 254 rows |
| FR-242 | Task codes come from `aidd_progress.parse_tasks` plus the raw `Codes satisfied` cell and `- Cites:` lines under `### T-nn` headings, ranges expanded (`FR-001 to FR-012`, `FR-001..FR-012`, abbreviated end such as `AC-261..268`, en/em dash, `a`), at most 400 numbers per range. Codes compare by prefix + integer value; every printed code (notes, Covers) is written exactly as cited in the source text (`FR-014`, never `FR-14`); task IDs are emitted as written in tasks.md, upper-cased. | measured: prototype printed `FR-14` |
| FR-243 | Proposed `Inputs` = union of the target paths of the proposed tasks (`whole-suite`: every target). A target absent at `root/p` is resolved in this order: `aidd_progress._resolve` (suffix match), `_renumbered`, `_alias_target`; a directory becomes `<dir>/**`; a `(delete)` target is excluded. A target that still matches no file is EXCLUDED from Inputs (a glob matching no file is a malformed declaration that `verify` refuses), listed in the row notes and in `missing_targets`, and the row needs review. | measured: F21 23, F36 12, F37 2 targets recovered |
| FR-244 | Never shrink: proposed `Covers` = the existing Covers text, then `; ` and the added task IDs in numeric order; proposed `Inputs` ⊇ existing `Inputs`. An `unresolved` row keeps its Covers text and only its existing Inputs. | owner brief 2026-11-03 |
| FR-245 | A row gets `needs_review = True` and the review marker text `[Proposed — unconfirmed]` (constant `REVIEW_MARK`) when: it is `whole-suite` (D-2 warning); its Covers names a task not in tasks.md; a `cites-tasks`/`via-fr-ac-api` row also cites codes no task cites; a target was excluded or resolved to another path; or the selected tasks have no targets. | user — "acepto recomendacion" (D-2) |
| FR-246 | A row whose command matches `db_verify`, `psql`, `docker`, `pg_prove` or `--tap` is a database row: `Reuse` is reported as `none (database row: never reused)`; it gets Covers/Inputs for selection only. No row ever gets a proposed `Reuse` value. | SKILL.md "never infer their equivalence" |
| FR-247 | `--apply-to FILE` writes a Markdown proposal whose first line is `<!-- coverage_derive proposal: not part of any spec; review and copy by hand -->`. It refuses (exit 2, nothing written) when FILE is named `spec.md`, `tasks.md`, `plan.md`, `contracts.md` or `mockup-audit.md`, or when FILE exists and its first line is not that marker. | owner brief 2026-11-03 |
| FR-248 | `--changed-file PATH` (repeatable) adds `changed_simulation` = `{status, reason, selected_tasks, always_rows, rows_run, rows_skipped, warnings}` computed with the FR-259 rules on the PROPOSED values. Git is never called by `aidd_coverage.py`. | measured pilot above |
| FR-249 | Stdlib only; never raises on malformed spec or tasks text (empty table gives zero rows); `--json` prints the full result as JSON. | repo convention `skill/scripts/*` |
| FR-259 | New `_changed_selection(root, spec, base=None) -> tuple[list[str], list[str], list[str]]` in `aidd_status.py` returns `(task_ids, always_rows, warnings)`. Refusal (`ValueError`) only for: a changed spec policy file (unchanged rule); no rows or no tasks; a malformed declaration — Covers that `_task_rows` rejects (ambiguous exclusion, invalid identifier or range), Covers naming a task not in tasks.md, or declared Inputs for which `rules.row_input_fingerprint` returns None; or nothing to run (no task selected and no always-run row; existing message). A row without Inputs or without task IDs in Covers is an always-run row with the warning `warning: verification row <n> declares no Inputs or no task Covers; it always runs`. A task no row names whose `parse_tasks` targets match a changed path gives `warning: task <T> is covered by no verification row; whole-suite rows run` and adds every row whose Covers names all tasks; if no such row exists, every row is added. `_changed_task_selection` keeps its signature and returns `_changed_selection(...)[0]`. | user — "acepto recomendacion" (D-1) |
| FR-260 | `cmd_verify` gains the keyword `always_rows=None` (list of row ids), accepted only with `task_ids` (from `--changed`). Rows run = `_task_rows(task_ids)` (skipped when `task_ids` is empty) plus the `always_rows` not already selected, in table order; each such row prints `always-run row <n>`. With always-run rows the partial guard scope is not attested (`guard_scope = None`), the `task_verify_run` event records `always_rows`, and the selection fingerprint covers both parts (`_changed_selection_fingerprint`). The `--changed` CLI prints each warning, then calls `cmd_verify(spec, task_ids=..., always_rows=...)`. | user — "acepto recomendacion" (D-1) |
| FR-261 | New `aidd_unit_audit.resolve_base(root, base) -> str`: a non-empty string of at most 256 characters, not starting with `-`, without whitespace or NUL, resolved by `git rev-parse --verify --end-of-options <base>^{commit}` (timeout 30 s) to a 40- or 64-hex commit; anything else raises `ValueError('base is not a uniquely resolvable commit')`. `git_changed_paths` and `administrative_only_task_paths` use it instead of the hex-only check, so `--base HEAD~1` works. | user — "acepto recomendacion" (D-3) |

## Acceptance criteria

| Code | Scenario | Expected |
|---|---|---|
| AC-271 | Row Covers `T-01` | kind `cites-tasks`, tasks `['T-01']`, Inputs = T-01 targets, no review needed |
| AC-272 | Row Covers `FR-002 to FR-003`, tasks T-02 (FR-002) and T-03 (FR-003) | kind `via-fr-ac-api`, tasks `['T-02','T-03']`, Covers starts with `FR-002 to FR-003` |
| AC-273 | Row Covers `full regression` | kind `whole-suite`, every task, every target, `needs_review` |
| AC-274 | Row Covers `FR-099`, no task cites it | kind `unresolved`, tasks `[]`, Inputs `[]`, Covers unchanged |
| AC-275 | Row command contains `db_verify.py --tap`; T-04 cites AC-010 only in its `- Cites:` line | database row, Reuse starts `none`, tasks include T-04 |
| AC-276 | Row with existing Inputs `extra/keep.py` | proposed Inputs still contain `extra/keep.py` |
| AC-277 | A target file removed | it is not in the proposed Inputs, it is in `missing_targets`, the row has `needs_review` and a note naming it |
| AC-278 | Simulation, a row without Inputs, change `src/a.py` | `status == 'ok'`, that row in `always_rows`, a warning naming it |
| AC-279 | Simulation, rows only T-01 and coded rows, changed `src/a.py` | selected `['T-01']`, 1 row run, others skipped |
| AC-280 | Simulation with `specs/<spec>/tasks.md` changed | refused, reason `spec policy changed` |
| AC-281 | Dry-run | exit 0, output contains `DRY-RUN`, no file created or modified |
| AC-282 | `--apply-to` the spec's `spec.md`, or an existing foreign file | exit 2, file unchanged; an own proposal file can be rewritten |
| AC-283 | Covers `FR-014, FR-099` where only FR-014 is cited by a task | the note reads `codes no task cites: FR-099` and no printed text contains `FR-14` or `FR-99` |
| AC-284 | Task target `migrations/0120_x.sql`, only `migrations/3277_x.sql` exists | proposed Inputs contain `migrations/3277_x.sql`; the note names the resolution |
| AC-285 | `--changed`, row V-2 without Inputs, change matches V-1 only | V-1 and V-2 run; output contains the FR-259 always-run warning for V-2 |
| AC-286 | `--changed`, task T-03 named by no row, its target changed, row V-9 Covers `T-01..T-03` | warning for T-03; V-9 runs |
| AC-287 | Same as AC-286 with no row naming all tasks | every row runs |
| AC-288 | Covers `T-99` (unknown), Covers `all except T-02`, or Inputs `missing/*.py` | refused, nothing executed |
| AC-289 | `--base HEAD~1` in a repo with two commits; `--base --all`; `--base nosuchrev` | the first selects the committed change; the other two raise `ValueError` |
| AC-290 | Every row declares Inputs and task Covers (today's contract) | selection identical to the current `_changed_task_selection`; `tests/test_verify_git_contract.py` unchanged and green |

## Verification

| # | Command | Expected | Covers |
|---|---|---|---|
| V-1 | `python -m unittest discover -s tests -p "test_aidd_coverage.py" -v` | exit 0 | T-30, T-31, AC-271..AC-284 |
| V-2 | `python -m unittest discover -s tests -p "test_verify_changed_policy.py" -v` | exit 0 | T-43, T-44, AC-285..AC-290 |
| V-3 | `python -m unittest tests.test_verify_git_contract tests.test_aidd_unit_audit_incremental tests.test_wave_verification -v` | exit 0 | T-44, AC-290 (no regression) |
| V-4 | `python -m unittest discover -s tests -p "test_dot_aidd_mirror.py" -v` | exit 0 | T-33 |
| V-5 | `python -m unittest discover -s tests -p "test_aidd_coverage.py" -k CoverageWiring -v` | exit 0 | T-32, T-34 |

(The CLI and SKILL.md checks are unit tests, not `python -c` rows: the verification lint rejects inline interpreter code.)

Synthetic temporary directories only (T-43 creates a throwaway Git repository in a temp dir); no database, Docker,
network or `aidd verify` run by the builder.

## Out of scope

Proposing `Reuse`; writing any spec or tasks file; creating rows for uncovered tasks; changing `--tasks` or `--wave`
selection; b1SycLink files; installed skills; amendment-04 logic (only called).

## Open questions

None. D-1..D-3 were answered by the owner on 2026-11-03 (user — "acepto recomendacion").

---

# Tasks — amendment 05

Every task prompt restates: scope in and out exactly as written; stop and report on any ambiguity; one
responsibility per function; snake_case with a leading underscore for module-private helpers; design for failure
(every file read in `try/except (OSError, UnicodeDecodeError, ValueError)`, never raise on malformed text in
`aidd_coverage.py`; fail closed only on malformed declarations in `aidd_status.py`); tool-first (mirror sync by `cp`,
never by hand); no databases, `db_verify.py` never run, no `aidd verify` by the builder.

Analysis parameters: `aidd size --files skill/scripts/aidd_coverage.py skill/scripts/aidd_status.py skill/scripts/aidd_unit_audit.py tests/test_aidd_coverage.py tests/test_verify_changed_policy.py` → expected L (verify gate area).

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-30 | FR-240..FR-249, AC-271..AC-284 | `tests/test_aidd_coverage.py` | LOGIC | | | any production code; any other test file |
| T-43 | FR-259..FR-261, AC-285..AC-290 | `tests/test_verify_changed_policy.py` | LOGIC | | | any production code; any other test file, including `tests/test_verify_git_contract.py` |
| T-31 | FR-240..FR-249 | `skill/scripts/aidd_coverage.py` | LOGIC | | | `aidd_status.py`, `aidd_progress.py`, `aidd_rules.py`, `aidd_evidence.py`; any Git call |
| T-44 | FR-259, FR-260, FR-261 | `skill/scripts/aidd_status.py` + `skill/scripts/aidd_unit_audit.py` | LOGIC | | | `--tasks` and `--wave` behaviour; contract-store code; `aidd_coverage.py` |
| T-32 | FR-240 | `aidd/cli.py` | LOGIC | | | any other subcommand; argument parsing beyond forwarding |
| T-33 | FR-240..FR-249, FR-259..FR-261 (mirror) | `adapters/dot-aidd/scripts/aidd_coverage.py` + `adapters/dot-aidd/scripts/aidd_status.py` + `adapters/dot-aidd/scripts/aidd_unit_audit.py` + `tests/test_dot_aidd_mirror.py` | LOGIC | | | any change that is not a byte copy, except one list entry in the guard test |
| T-34 | FR-240, FR-245, FR-259, FR-261 docs | `skill/SKILL.md` | LOGIC | | | any other section; b1SycLink files |

## Per-task detail

### T-30 — failing tests for `aidd coverage`
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: S

**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 80k
- Agent role: tests
- Model tier: medium
- Wave: 11

**Detail**
- Goal: encode AC-271..AC-284 as unit tests that fail on the current code (module absent).
- Cites: FR-240..FR-249, AC-271..AC-284.
- Depends on: none.
- Read first: `batch-staging/coverage-derive/test_coverage_derive.py` (prototype tests: copy its synthetic `SPEC` and `TASKS` texts verbatim); `skill/scripts/aidd_progress.py` lines 91-137 (`parse_tasks`) and 189-259 (`_resolve`, `_renumbered`, `_alias_target`); `skill/scripts/aidd_rules.py` lines 2218-2256 (`parse_verification`).
- Files to change: `tests/test_aidd_coverage.py` (new).
- Naming contract: class `AiddCoverage(unittest.TestCase)` with methods `test_cites_tasks_kept`, `test_range_derived_via_codes`, `test_whole_suite_gets_everything_and_needs_review`, `test_unresolved_gets_no_inputs`, `test_database_row_never_reused_and_cites_line_counts`, `test_existing_inputs_never_shrink`, `test_missing_target_is_excluded_and_needs_review`, `test_changed_simulation_always_runs_undeclared_row`, `test_changed_simulation_skips_unrelated_rows`, `test_changed_simulation_refuses_on_spec_change`, `test_dry_run_writes_nothing`, `test_apply_to_refuses_spec_and_foreign_file`, `test_json_output`, `test_summary_counts`, `test_codes_printed_as_cited`, `test_renumbered_target_resolves`; class `CoverageWiring(unittest.TestCase)` with methods `test_cli_registers_coverage` and `test_skill_documents_coverage`. Production names exercised: `aidd_coverage.derive(spec_dir) -> dict` with keys `spec, root, rows, uncovered_tasks, missing_targets, summary`; each row dict has keys `n, cmd, kind, tasks, covers, inputs, database, reuse, needs_review, notes, covers_before, inputs_before`; `aidd_coverage.simulate_changed(result, changed_paths) -> dict` with keys `status, reason, selected_tasks, always_rows, rows_run, rows_skipped, warnings`; `aidd_coverage.main(argv) -> int`; constant `aidd_coverage.PROPOSAL_MARK`.
- Behaviour:
  1. Header: `sys.path.insert(0, <repo>/skill/scripts)`, `import aidd_coverage as cov` inside each test (each fails individually); `setUp` builds a temp root with `.aidd/`, `specs/001-x/spec.md` and `tasks.md` (prototype texts) and files `src/a.py`, `src/b.py`, `src/c.sql`, `src/d.py`, `extra/keep.py`.
  2. One test per AC-271..AC-284 with the exact expectations of the Acceptance criteria table; `test_summary_counts` asserts `(rows, cites-tasks, via-fr-ac-api, whole-suite, unresolved) == (6, 1, 3, 1, 1)` and `uncovered_tasks == []`.
  3. `test_codes_printed_as_cited`: a row with Covers `FR-014, FR-099` and a task citing `FR-014`; assert the joined notes contain `FR-099` and the joined notes plus Covers have no match for the regex `FR-(14|99)(?!\d)`.
  4. `test_renumbered_target_resolves`: task target `migrations/0120_x.sql`, only `migrations/3277_x.sql` (content over 40 bytes) exists; assert `migrations/3277_x.sql` in the row Inputs.
  5. `test_dry_run_writes_nothing` compares the sorted file list and `spec.md` bytes before and after `cov.main([spec_dir])`, ignoring `__pycache__`.
  6. `CoverageWiring` reads repo files as UTF-8 text: `test_cli_registers_coverage` asserts `aidd/cli.py` contains `("coverage", "aidd_coverage.py"`; `test_skill_documents_coverage` asserts `skill/SKILL.md` contains `aidd coverage`, `via-fr-ac-api` and `HEAD~1`.
- Tests first: this task IS the tests; run the V-1 command and keep the red output.
- Verify: `python -m unittest discover -s tests -p "test_aidd_coverage.py" -v` → red before T-31; exit 0 after T-34.
- Do NOT: touch production code; use a database, Docker, Git or the network; weaken an assertion later.
- Done when: the 18 tests exist with exactly these names and the red run is recorded by the verifier.
- Open questions: none.

### T-43 — failing tests for the `--changed` policy and `--base`
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2
- Kind: LOGIC
- Size: S

**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 80k
- Agent role: tests
- Model tier: medium
- Wave: 11

**Detail**
- Goal: encode AC-285..AC-290 as unit tests that fail on the current code.
- Cites: FR-259, FR-260, FR-261, AC-285..AC-290.
- Depends on: none.
- Read first: `tests/test_verify_git_contract.py` lines 1-70 (fixtures and the patch list of `ContractReuse`); `tests/test_aidd_unit_audit_incremental.py` lines 235-255 (temp Git repo pattern); `skill/scripts/aidd_status.py` lines 2004-2056 (`_task_rows`), 2099-2137 (`_changed_task_selection`), 3085-3140 (`--changed` CLI branch).
- Files to change: `tests/test_verify_changed_policy.py` (new).
- Naming contract: class `VerifyChangedPolicy(unittest.TestCase)` with methods `test_row_without_inputs_always_runs`, `test_uncovered_changed_task_runs_whole_suite`, `test_uncovered_task_without_whole_suite_runs_all`, `test_malformed_covers_refuses`, `test_inputs_matching_no_file_refuses`, `test_fully_declared_spec_unchanged`, `test_cmd_verify_runs_always_rows_and_records_them`; class `BaseRevision(unittest.TestCase)` with methods `test_base_accepts_head_tilde`, `test_base_rejects_option_like_and_unknown`. Production names exercised: `aidd_status._changed_selection(root, spec, base=None) -> tuple[list[str], list[str], list[str]]`, `aidd_status._changed_task_selection(root, spec, base=None) -> list[str]`, `aidd_status.cmd_verify(spec_arg, ..., task_ids=None, always_rows=None)`, `aidd_unit_audit.resolve_base(root, base) -> str`, `aidd_unit_audit.git_changed_paths(root, base=None)`; evidence event name `task_verify_run` with field `always_rows`.
- Behaviour:
  1. Fixtures as in `GitSelection` of `tests/test_verify_git_contract.py`: temp root, `specs/001-example/tasks.md` with tasks T-01 `a.py`, T-02 `b.py`, T-03 `c.py` (files created), patch `aidd_unit_audit.git_changed_paths` to return the changed list.
  2. `test_row_without_inputs_always_runs` (AC-285): V-1 `T-01` Inputs `a.py`, V-2 `T-02` no Inputs, V-3 `T-01..T-03` Inputs `a.py, b.py, c.py`; change `a.py`; assert tasks contain `T-01`, always rows `['V-2']`, a warning containing `verification row V-2` and `always runs`.
  3. `test_uncovered_changed_task_runs_whole_suite` (AC-286): rows V-1 `T-01` (`a.py`) and V-9 `T-01..T-02` (`a.py, b.py`); T-03 named by no row; change `c.py`; assert a warning containing `task T-03 is covered by no verification row`; since no row names all three tasks, assert every row is in always rows; then add V-10 `T-01..T-03` (`a.py, b.py, c.py`) and assert always rows `['V-10']` plus the warning.
  4. `test_uncovered_task_without_whole_suite_runs_all` (AC-287): rows V-1 `T-01`, V-2 `T-02`; change `c.py`; assert always rows `['V-1', 'V-2']`.
  5. `test_malformed_covers_refuses` (AC-288): Covers `T-99`, then Covers `all except T-02`; assert `ValueError` each time.
  6. `test_inputs_matching_no_file_refuses` (AC-288): Inputs `missing/*.py`; assert `ValueError`.
  7. `test_fully_declared_spec_unchanged` (AC-290): the exact `GitSelection` fixture; `_changed_task_selection` returns `['T-01']` for `a.py` and raises `no declared task Inputs` for `other.py`; `_changed_selection` returns `(['T-01'], [], [])` for `a.py`.
  8. `test_cmd_verify_runs_always_rows_and_records_them` (FR-260): patch exactly the objects patched in `ContractReuse.test_round_shares_only_identical_inputs_and_environment` plus `status.ev.append` (capture kwargs); call `status.cmd_verify('001-example', task_ids=['T-01'], always_rows=['V-2'])`; assert the patched `_run_row` received the commands of V-1, V-3 and V-2, stdout contains `always-run row V-2`, and the captured `task_verify_run` kwargs have `always_rows == ['V-2']`.
  9. `BaseRevision`: temp Git repo with two commits (pattern of `tests/test_aidd_unit_audit_incremental.py`); `resolve_base(root, 'HEAD~1')` equals `git rev-parse HEAD~1`; `git_changed_paths(root, 'HEAD~1')` contains the file of the second commit; `resolve_base` raises `ValueError` for `--all`, `''`, `'a b'` and `nosuchrev`.
- Tests first: this task IS the tests; run the V-2 command and keep the red output.
- Verify: `python -m unittest discover -s tests -p "test_verify_changed_policy.py" -v` → red before T-44, exit 0 after.
- Do NOT: touch production code or `tests/test_verify_git_contract.py`; use a database, Docker or the network; weaken an assertion later.
- Done when: the 9 tests exist with exactly these names and the red run is recorded by the verifier.
- Open questions: none.

### T-31 — `skill/scripts/aidd_coverage.py`
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: M

**Estimate**
- Effort: Medium
- Agent min: 30
- Human ref hours: 1.5
- Tokens (est): 120k
- Agent role: builder
- Model tier: high
- Wave: 12

**Detail**
- Goal: implement FR-240..FR-249 so T-30 passes.
- Cites: FR-240..FR-249.
- Depends on: T-30; T-27 (amendment 04 helpers in `aidd_progress.py`).
- Read first: `batch-staging/coverage-derive/coverage_derive.py` (prototype; port it with the differences below); `skill/scripts/aidd_progress.py` lines 189-259; `skill/scripts/aidd_evidence.py` lines 2029-2080 (`_scope_re`, `in_scope`); the tests created by T-30 in the file named in T-30's Files to change.
- Files to change: `skill/scripts/aidd_coverage.py` (new).
- Naming contract: existing names used unchanged: modules `aidd_progress`, `aidd_rules`, `aidd_evidence`; functions `aidd_progress.parse_tasks`, `aidd_progress._resolve`, `aidd_progress._renumbered`, `aidd_progress._alias_target`, `aidd_rules.parse_verification`, `aidd_evidence._scope_re`, `aidd_evidence.in_scope`. Row dict key `needs_review` (bool) and result keys `missing_targets` and `always_rows` as listed in T-30. New module constants `REVIEW_MARK` (the exact marker text written in FR-245), `PROPOSAL_MARK` (FR-247 text), `METADATA = ('spec.md', 'tasks.md', 'plan.md', 'contracts.md', 'mockup-audit.md')`, `DB_RE`, `SUITE_RE`, `RANGE_RE`, `T_RANGE_RE`, `MAX_RANGE = 400`; public functions `codes_in(text) -> dict[str, str]` (normalised code -> code as cited), `tasks_in(text, known=None) -> set[str]`, `raw_task_codes(tasks_text) -> dict[str, set[str]]`, `derive(spec_dir) -> dict`, `simulate_changed(result, changed) -> dict`, `render_text(result) -> str`, `render_proposal(result) -> str`, `safe_target(spec_dir, target) -> str | None`, `main(argv=None) -> int`; private helpers `_resolve_target(root, p) -> str | None`, `_exists(root, pattern) -> bool`, `_matcher(globs)`.
- Behaviour:
  1. Import `aidd_progress`, `aidd_rules`, `aidd_evidence` from the script's own directory (`HERE = Path(__file__).resolve().parent`), not from the project.
  2. `derive`: parse tasks (`parse_tasks` + `raw_task_codes`), keep task IDs as written, build code → tasks map, then classify each row per FR-241, propose Covers/Inputs per FR-243/FR-244, flag per FR-245, tag database rows per FR-246.
  3. `_resolve_target` (FR-243): try `_resolve`, `_renumbered`, `_alias_target` in that order; return the root-relative POSIX path, `<dir>/**` for a directory, else None. A None result EXCLUDES the target from Inputs and adds it to the row notes and `missing_targets`; a `(delete)` target (task key `delete`) is skipped silently.
  4. `codes_in` keeps, per normalised key, the first spelling seen in the text; every note and Covers addition prints that spelling (FR-242).
  5. `simulate_changed` (FR-248) applies FR-259 in this order: policy file changed → refused; a row naming a task not in tasks.md → refused; rows without Inputs or task IDs → `always_rows` plus warning; uncovered tasks whose targets match a change → warning plus rows naming every task (all rows when none); selected tasks from Inputs hits; nothing to run → refused with `rows_skipped = total`; else `ok`.
  6. `main`: argparse per FR-240; `--apply-to` guarded by `safe_target` (FR-247); `--json` prints the result.
- Tests first: T-30 must be red before this task; keep it unmodified.
- Verify: `python -m unittest discover -s tests -p "test_aidd_coverage.py" -k AiddCoverage -v` → exit 0. The two wiring tests of T-30 turn green only after T-32 and T-34.
- Do NOT: call Git or any subprocess; write any file other than the `--apply-to` target; propose a `Reuse` value; change any other script.
- Done when: all 16 `AiddCoverage` tests pass and `python skill/scripts/aidd_coverage.py --help` exits 0.
- Open questions: none.

### T-44 — `--changed` policy and `--base` resolution
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2
- Kind: LOGIC
- Size: M

**Estimate**
- Effort: High
- Agent min: 30
- Human ref hours: 1.5
- Tokens (est): 130k
- Agent role: builder
- Model tier: high
- Wave: 12

**Detail**
- Goal: implement FR-259..FR-261 so T-43 passes and today's fully declared selection is unchanged.
- Cites: FR-259, FR-260, FR-261.
- Depends on: T-43.
- Read first: `skill/scripts/aidd_status.py` lines 2004-2137 (`_task_rows`, `_task_selection_fingerprint`, `_changed_task_selection`), 2151-2250 and 2530-2640 (`cmd_verify` task branch and its events), 3085-3150 (`--changed` CLI branch); `skill/scripts/aidd_unit_audit.py` lines 364-415 (`git_changed_paths`, `administrative_only_task_paths`); the tests created by T-43 in the file named in T-43's Files to change.
- Files to change: `skill/scripts/aidd_status.py`, `skill/scripts/aidd_unit_audit.py`.
- Naming contract: in `aidd_status.py` new `_changed_selection(root, spec, base=None) -> tuple[list[str], list[str], list[str]]`, `_changed_selection_fingerprint(tasks_text, spec_text, task_ids, always_rows) -> str`, private helpers `_known_task_ids(tasks_text) -> set[str]` and `_covers_task_refs(covers, known) -> set[str]` (extracted from `_task_rows`, raising the same `ValueError` messages); `cmd_verify(..., task_ids=None, always_rows=None)`; `_changed_task_selection` signature unchanged. Existing names changed in body only, signatures unchanged: `cmd_verify` locals `selection_fp_start`, `selection_fp_end`, `guard_scope_start`; `aidd_unit_audit.git_changed_paths(root, base=None)`, `aidd_unit_audit.administrative_only_task_paths(root, changed_paths, rules, base=None)`. In `aidd_unit_audit.py` new `resolve_base(root, base) -> str`. Warning texts exactly as FR-259; stdout line `always-run row <n>`; event field `always_rows`.
- Behaviour:
  1. Extract `_known_task_ids` and `_covers_task_refs` from `_task_rows` without changing `_task_rows` results or messages (V-3 guards it).
  2. `_changed_selection`: steps of FR-259 in this order — changed paths, policy check, rows/tasks present, per-row Covers refs (malformed or unknown task → `ValueError`), per-row Inputs fingerprint when Inputs declared (None → `ValueError('verification row <n> has missing or invalid Inputs')`), always-run rows, selected tasks by `rules._glob_hit`, uncovered tasks via `aidd_progress.parse_tasks` targets and `rules._glob_hit`, nothing-to-run check; return `(sorted tasks, always rows in table order, warnings)`.
  3. `_changed_task_selection` returns `_changed_selection(root, spec, base)[0]`.
  4. `cmd_verify`: `always_rows` without `task_ids` → `Refused: always_rows requires --changed; nothing was executed.` exit 1; with `task_ids == []` skip `_task_selection_fingerprint` and `_task_rows`; rows = task rows + always rows (table order, no duplicates); print `always-run row <n>` per added row; `selection_fp_start`/`_end` use `_changed_selection_fingerprint` when `always_rows` is given; `guard_scope_start = None` when `always_rows` is non-empty; `ev.append(..., 'task_verify_run', ...)` gets `always_rows=sorted(always_rows or [])`.
  5. CLI `--changed`: `task_ids, always_rows, warnings = _changed_selection(root, specs[0], base)`; print each warning; call `cmd_verify(specs[0], task_ids=task_ids, always_rows=always_rows)`.
  6. `resolve_base` per FR-261; `git_changed_paths` calls it instead of the hex regex plus `rev-parse` block; `administrative_only_task_paths` replaces its hex regex check with `base = resolve_base(root, base)` when `base` is not None.
- Tests first: T-43 must be red before this task; keep it unmodified.
- Verify: `python -m unittest discover -s tests -p "test_verify_changed_policy.py" -v` → exit 0; `python -m unittest tests.test_verify_git_contract tests.test_aidd_unit_audit_incremental tests.test_wave_verification -v` → exit 0.
- Do NOT: change `--tasks` or `--wave` selection, the contract store, `_round_*`; refuse a spec for a missing declaration; touch any other file.
- Done when: both Verify commands exit 0.
- Open questions: none.

### T-32 — CLI registration
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: XS

**Estimate**
- Effort: Low
- Agent min: 5
- Human ref hours: 0.25
- Tokens (est): 25k
- Agent role: builder
- Model tier: medium
- Wave: 13

**Detail**
- Goal: expose the tool as `aidd coverage`.
- Cites: FR-240.
- Depends on: T-31.
- Read first: `aidd/cli.py` lines 448-457 (the forwarded-script tuple loop).
- Files to change: `aidd/cli.py`.
- Naming contract: one new tuple in that loop, exactly `("coverage", "aidd_coverage.py", [], "Propose task Covers and Inputs for a spec's Verification rows (dry-run; never writes the spec) (aidd_coverage.py)")`.
- Behaviour: append the tuple after the `("size", ...)` entry; no other change.
- Tests first: the T-30 test `test_cli_registers_coverage` is red before this task.
- Verify: `python -m unittest discover -s tests -p "test_aidd_coverage.py" -k test_cli_registers_coverage -v` → exit 0.
- Do NOT: change any other subcommand or `main()`; add arguments.
- Done when: the verify command exits 0.
- Open questions: none.

### T-33 — mirrors
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: XS

**Estimate**
- Effort: Low
- Agent min: 5
- Human ref hours: 0.25
- Tokens (est): 30k
- Agent role: builder
- Model tier: medium
- Wave: 13

**Detail**
- Goal: keep the project bundle identical to the skill source for this amendment's three scripts.
- Cites: FR-240..FR-249, FR-259..FR-261 (mirror).
- Depends on: T-31, T-44.
- Read first: `tests/test_dot_aidd_mirror.py` lines 61-80 (`VERBATIM_SCRIPTS`) and `test_verbatim_scripts_match`.
- Files to change: `adapters/dot-aidd/scripts/aidd_coverage.py` (new), `adapters/dot-aidd/scripts/aidd_status.py`, `adapters/dot-aidd/scripts/aidd_unit_audit.py`, `tests/test_dot_aidd_mirror.py`.
- Naming contract: none new; each script target is a byte copy of its `skill/scripts` source; the guard list `VERBATIM_SCRIPTS` gains the entry `"aidd_coverage.py"`.
- Behaviour: three `cp` commands; `cmp` each pair; then the one-line list insertion; no other hand edit.
- Tests first: the check below exits 1 before the copies and 0 after.
- Verify: `python -c "import filecmp, sys; ok = all(filecmp.cmp('skill/scripts/' + n, 'adapters/dot-aidd/scripts/' + n, shallow=False) for n in ('aidd_coverage.py', 'aidd_status.py', 'aidd_unit_audit.py')); sys.exit(0 if ok and '\"aidd_coverage.py\"' in open('tests/test_dot_aidd_mirror.py', encoding='utf-8').read() else 1)"` → exit 0 (the full mirror test V-4 runs after wave 14, when amendment 06's copies exist).
- Do NOT: edit any copy by hand; touch other mirrors.
- Done when: the check exits 0.
- Open questions: none.

### T-34 — document
**Classify**
- Nature: `REQUIREMENT`
- Priority: 4
- Kind: LOGIC
- Size: XS

**Estimate**
- Effort: Low
- Agent min: 5
- Human ref hours: 0.25
- Tokens (est): 25k
- Agent role: docs
- Model tier: medium
- Wave: 13

**Detail**
- Goal: document `aidd coverage`, the always-run rule and `--base HEAD~1` next to incremental verification.
- Cites: FR-240, FR-245, FR-259, FR-261.
- Depends on: T-31, T-44.
- Read first: `skill/SKILL.md` line 457 (the paragraph that starts with "**Incremental verification" and describes `aidd verify <spec> --changed`).
- Files to change: `skill/SKILL.md`.
- Naming contract: documents exactly these names and no others: command `aidd coverage <spec_dir> [--apply-to FILE] [--json] [--changed-file PATH]`, kinds `cites-tasks`, `via-fr-ac-api`, `whole-suite`, `unresolved`, the review marker text exactly as written in FR-245, the warning texts of FR-259, `--base HEAD~1`.
- Behaviour: add 5 lines after that paragraph: what the command proposes; the four kinds; that it never writes the spec and the owner copies accepted cells; that a row without declarations always runs and an uncovered changed task runs the whole-suite rows (only malformed declarations refuse); that `--base` takes any revision Git resolves, e.g. `HEAD~1`.
- Tests first: no code; the T-30 test `test_skill_documents_coverage` is red before this task.
- Verify: `python -m unittest discover -s tests -p "test_aidd_coverage.py" -k test_skill_documents_coverage -v` → exit 0.
- Do NOT: change any other section; mention b1SycLink.
- Done when: the 5 lines exist and the verify command passes.
- Open questions: none.

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 11 | T-30, T-43 | tests | 20 | 160 | 1 |
| 12 | T-31, T-44 | builder | 30 | 250 | 1.5 |
| 13 | T-32, T-33, T-34 | builder, docs | 5 | 80 | 0.25 |

Total agent time (critical path): 55 min
Total tokens (k): 490
Total human reference hours: 2.75
Tasks: 7 in 3 waves (computed by `waves05.py` in the scratchpad from the task blocks; agent time and human hours are the
maximum per wave, tokens the sum, as in spec 007's table). In spec 007 waves 11-13 are shared with amendment 06
(waves 11-14); no two tasks of one wave touch the same file. Amendment 05 has no dependency on spec 004; only
amendment 06's tasks wait for wave 10 of the 004 amendment.
