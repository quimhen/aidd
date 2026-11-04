# Draft — amendment 05 to spec 007: `aidd coverage` derives task Covers and Inputs so selective verification can run

**DRAFT: not approved, not executable, no `Approved:` line.** Amendment intake: `AMENDMENT 05` of
`specs/007-aidd-review-html-close-gate` (verification and evidence accuracy). Siblings: `amendment-03-reuse-first-increment`
(cross-spec reuse, which needs `Inputs`) and `amendment-04-task-state-resolution` (renumbered/aliased targets, reused here).
It does not edit `amendment-02-*`, `amendment-04-*`, `spec.md` or `tasks.md`.
Owner direction (verbatim, 2026-11-03): "este tipo de mejoras con script que propones son las mejoras que debemos implementar en aidd".
Prototype (staging only, not shipped): `batch-staging/coverage-derive/coverage_derive.py` + `test_coverage_derive.py` (14 tests, exit 0).

## Minimum Requirements Checklist

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | New `skill/scripts/aidd_coverage.py`, CLI entry in `aidd/cli.py`, mirror in `adapters/dot-aidd/scripts/` | repo — `aidd/cli.py:448-457` (forwarded-script registry) | — |
| New development or modification? | New read-only tool; no change to `aidd verify` selection | repo — `skill/scripts/aidd_status.py:2099-2137` (`_changed_task_selection`) | — |
| External service, API, integration? | None; Git is not called by the tool (changed paths are passed in) | owner brief 2026-11-03 | — |
| Who is requesting it? | Owner (AIDD + b1SycLink) | user — "este tipo de mejoras con script que propones son las mejoras que debemos implementar en aidd" | — |
| Dependencies? | stdlib only; imports `aidd_progress`, `aidd_rules`, `aidd_evidence` from its own directory | repo — `skill/scripts/aidd_progress.py:91` (`parse_tasks`) | — |
| Business objective | Make `aidd verify <spec> --changed` / `--tasks` usable on real projects whose Verification rows cite FR/AC/API instead of T-nn and declare no Inputs | measured 2026-11-03 (below) | — |
| Expected visual fidelity | No mockup; CLI only | — | — |

## Executive summary

- **Problem (measured 2026-11-03 on b1SycLink, read-only, with the prototype):** `--changed` refuses unless EVERY row has
  `Inputs` and a `Covers` naming task IDs (`aidd_status.py:2127-2128`), and `_task_rows` (`:2004-2056`) only selects
  rows whose `Covers` names `T-nn`. In b1SycLink, 51 specs have both `spec.md` and `tasks.md` with a Verification table:
  254 rows, all with `Covers`, only **15** name `T-nn`, **0** have `Inputs`. Selective verification and amendment-03
  reuse cannot run on any of them.
- **Derivation is possible by script:** 15 rows `cites-tasks`, **177** `via-fr-ac-api` (FR/AC/API/SCREEN codes,
  ranges expanded, mapped through each task's `Codes satisfied` cell and `- Cites:` line), 57 `whole-suite` (no code:
  regression / full run), **5** `unresolved` (codes no task cites).
- **Pilot on 6 specs (F12, F21, F36, F37, P03, S01):** 26 rows → 4 cites-tasks, 18 via-fr-ac-api, 3 whole-suite,
  1 unresolved; 17 database rows; 15 rows `[Proposed — unconfirmed]`; average **57.8 tasks per row** (F21 167.8,
  F36 69.7, P03 50.4, F37 44.7, S01 5.7, F12 3.0).
- **What `--changed --base 72025f40` (= HEAD~1) would do with the proposal applied** (semantics read from
  `_changed_task_selection`, not executed): only **4 of 26 rows skipped** (all of F21, which the commit did not touch;
  verify still exits 1 "nothing executed"). F12, P03, S01 refuse: 18, 35 and 27 tasks have no Verification row
  (`_task_rows` raises "tasks missing verification rows"); S01 also has 1 unresolved row. F36 and F37 refuse at the
  Inputs fingerprint: 23 and 16 task targets are renumbered migrations that no longer exist under the cited name.
  Across the 51 specs, 26 have tasks that no row covers.
- **Findings that shape the design:** (1) `--base` accepts only a hex commit (`aidd_unit_audit.py:374`); `HEAD~1` is
  refused. (2) A `whole-suite` row pulls every task, so any target change runs every row — the conservative default
  costs selectivity (F36 without its whole-suite row: 2 of 2 coded rows run; F37: 1 of 2 skipped). (3) The tool must
  resolve renumbered/aliased targets (amendment 04) or the proposal is refused at fingerprint time.
- **Safety argument:** an under-declared `Covers` or `Inputs` makes `--changed` SKIP a test that was needed — a false
  PASS. Hence: dry-run by default; never shrink an explicit `Covers`/`Inputs`; `whole-suite` gets every task and every
  target; `unresolved` gets no Inputs (the spec stays non-selectable, so verify refuses and the full run is required);
  every uncertain row is marked `[Proposed — unconfirmed]`; the tool never writes the spec; the owner reviews the
  proposal file and copies accepted cells by hand. Partial evidence still never closes a spec.
- **Not in scope:** changing `aidd verify` selection, Reuse declarations, editing any spec automatically, creating
  Verification rows for uncovered tasks (reported, not invented).

## Functional requirements

| Code | Requirement | Source |
|---|---|---|
| FR-240 | `aidd coverage <spec_dir> [--apply-to FILE] [--json] [--changed-file PATH ...]` runs `skill/scripts/aidd_coverage.py`. Default is a read-only dry-run that prints, per `## Verification` row (parsed with `aidd_rules.parse_verification`): proposed `Covers`, proposed `Inputs`, derivation kind, `Reuse` note, and notes; then a summary line and the tasks no row covers. Exit 0 on success, 2 on refusal (no `spec.md`, unsafe `--apply-to`). | owner brief 2026-11-03 |
| FR-241 | Derivation kind per row, first match wins: `cites-tasks` (Covers names a `T-nn` or a `T-a..T-b` range in the forms `_task_rows` accepts); `via-fr-ac-api` (Covers cites FR/AC/API/SCREEN/COMP/CTL/US codes that at least one task cites); `whole-suite` (no code in Covers, or a suite word: todos, toda, todas, suite, completa, complete, regresión, regression, all, full, whole); `unresolved` (codes present, none cited by any task). | measured: 15 / 177 / 57 / 5 of 254 rows |
| FR-242 | Task codes come from `aidd_progress.parse_tasks` plus the raw `Codes satisfied` cell and `- Cites:` lines under `### T-nn` headings, with ranges expanded (`FR-001 to FR-012`, `FR-001..FR-012`, `SCREEN-125..128`, en/em dash, `a`), at most 400 numbers per range. Codes compare by prefix + integer value (`FR-001` = `FR-1`); task IDs are emitted exactly as written in tasks.md (upper-cased) because verify compares them literally. | measured: F36 `FR-001 to FR-012`, `SCREEN-125..128` |
| FR-243 | Proposed `Inputs` = union of the target paths of the proposed tasks (`whole-suite`: every target of the spec). A path absent at `root/p` is resolved with `aidd_progress._resolve`, then `_renumbered` and `_alias_target` when present (amendment 04); a directory becomes `<dir>/**`; a `(delete)` target is excluded. A path that still matches no file is kept and noted "matches no file today". | measured: F36 23, F37 16, F21 43 renumbered/absent targets |
| FR-244 | Never shrink: proposed `Covers` = the existing Covers text, then `; ` and the added task IDs in numeric order; proposed `Inputs` ⊇ existing `Inputs`. An `unresolved` row keeps its Covers text and gets only its existing Inputs (none today). | owner brief 2026-11-03 |
| FR-245 | A row gets `needs_review = True` and the review marker text `[Proposed — unconfirmed]` (constant `REVIEW_MARK`) when: it is `whole-suite`; its Covers names a task not in tasks.md; a `cites-tasks`/`via-fr-ac-api` row also cites codes no task cites; any proposed Input matches no file; a target was resolved to another path; or the selected tasks have no targets. | owner brief 2026-11-03 |
| FR-246 | A row whose command matches `db_verify`, `psql`, `docker`, `pg_prove` or `--tap` is a database row: `Reuse` is reported as `none (database row: never reused)`; it gets Covers/Inputs for selection only. No row ever gets a proposed `Reuse` value. | AGENTS.md (b1SycLink) DB rule; SKILL.md "never infer their equivalence" |
| FR-247 | `--apply-to FILE` writes a Markdown proposal whose first line is `<!-- coverage_derive proposal: not part of any spec; review and copy by hand -->`. It refuses (exit 2, nothing written) when FILE is named `spec.md`, `tasks.md`, `plan.md`, `contracts.md` or `mockup-audit.md`, or when FILE exists and its first line is not that marker. | owner brief 2026-11-03 |
| FR-248 | `--changed-file PATH` (repeatable) adds `changed_simulation` = `{status, reason, selected_tasks, rows_run, rows_skipped}` computed with the rules of `_changed_task_selection` and `_task_rows` on the PROPOSED values: refused when a spec policy file changed, a row lacks Inputs or task Covers, a task has no row, no Input matches, or a selected row has an Input matching no file. Pattern matching uses `aidd_evidence._scope_re` / `in_scope`. Git is never called. | measured pilot above |
| FR-249 | Stdlib only; never raises on malformed spec or tasks text (empty table → zero rows); `--json` prints the full result as JSON. | repo convention `skill/scripts/*` |

## Acceptance criteria

| Code | Scenario | Expected |
|---|---|---|
| AC-271 | Row Covers `T-01` | kind `cites-tasks`, tasks `['T-01']`, Inputs = T-01 targets, not unconfirmed |
| AC-272 | Row Covers `FR-002 to FR-003`, tasks T-02 (FR-002) and T-03 (FR-003) | kind `via-fr-ac-api`, tasks `['T-02','T-03']`, Covers starts with `FR-002 to FR-003` |
| AC-273 | Row Covers `full regression` | kind `whole-suite`, every task, every target, unconfirmed |
| AC-274 | Row Covers `FR-099`, no task cites it | kind `unresolved`, tasks `[]`, Inputs `[]`, Covers unchanged |
| AC-275 | Row command contains `db_verify.py --tap`; T-04 cites AC-010 only in its `- Cites:` line | database row, Reuse starts `none`, tasks include T-04 |
| AC-276 | Row with existing Inputs `extra/keep.py` | proposed Inputs still contain `extra/keep.py` |
| AC-277 | A target file removed | the row is unconfirmed and a note says "match no file" |
| AC-278 | Simulation with an unresolved row present | `status == 'refused'`, `rows_skipped == 0` |
| AC-279 | Simulation, rows only T-01 and coded rows, changed `src/a.py` | selected `['T-01']`, 1 row run, others skipped |
| AC-280 | Simulation with `specs/<spec>/tasks.md` changed | refused, reason `spec policy changed` |
| AC-281 | Dry-run | exit 0, output contains `DRY-RUN`, no file created or modified |
| AC-282 | `--apply-to` the spec's `spec.md`, or an existing foreign file | exit 2, file unchanged; an own proposal file can be rewritten |

## Verification

| # | Command | Expected | Covers |
|---|---|---|---|
| V-1 | `python -m unittest discover -s tests -p "test_aidd_coverage.py" -v` | exit 0 | T-30, T-31, AC-271..AC-282 |
| V-2 | `python -m unittest discover -s tests -p "test_dot_aidd_mirror.py" -v` | exit 0 | T-33 |
| V-3 | `python -c "import sys; t=open('aidd/cli.py', encoding='utf-8').read(); sys.exit(0 if '(\"coverage\", \"aidd_coverage.py\"' in t else 1)"` | exit 0 | T-32 |
| V-4 | `python -c "import sys; t=open('skill/SKILL.md', encoding='utf-8').read(); sys.exit(0 if 'aidd coverage' in t and 'via-fr-ac-api' in t else 1)"` | exit 0 | T-34 |

Synthetic temporary directories only; no database, Docker, network, Git or `aidd verify` run. `Inputs` are not declared
here because the test file does not exist yet; once built, this table is itself the first candidate for `aidd coverage`.

## Out of scope

Changing `aidd verify`, `_changed_task_selection` or `_task_rows`; proposing `Reuse`; writing any spec or tasks file;
creating rows for uncovered tasks; b1SycLink files; installed skills; amendment-04 logic (only called when present).

## Open questions (decisions for the owner, not blocking the draft)

- D-1: `unresolved` rows and uncovered tasks make `--changed` refuse for the whole spec (26 of 51 b1SycLink specs have
  uncovered tasks). Keep fail-closed (current), or a later amendment lets rows without Inputs always run instead?
- D-2: `whole-suite` rows pull all tasks and erase selectivity. Accept as safe default, or ask authors to split them?
- D-3: Should `--base` accept `HEAD~N` (resolved to a hash) instead of refusing it?

---

# Tasks — amendment 05

Every task prompt restates: scope in and out exactly as written; stop and report on any ambiguity; one
responsibility per function; snake_case with a leading underscore for module-private helpers; design for failure
(every file read in `try/except (OSError, UnicodeDecodeError, ValueError)`, never raise on malformed text);
tool-first (mirror sync by `cp`, never by hand); no databases, `db_verify.py` never run, no `aidd verify` by the builder,
no Git calls inside the new script.

Analysis parameters: `aidd size --files skill/scripts/aidd_coverage.py tests/test_aidd_coverage.py` → expected M.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-30 | FR-240..FR-249, AC-271..AC-282 | `tests/test_aidd_coverage.py` | LOGIC | | | any production code; any other test file |
| T-31 | FR-240..FR-249 | `skill/scripts/aidd_coverage.py` | LOGIC | | | `aidd_status.py`, `aidd_progress.py`, `aidd_rules.py`, `aidd_evidence.py`; any Git call |
| T-32 | FR-240 | `aidd/cli.py` | LOGIC | | | any other subcommand; argument parsing beyond forwarding |
| T-33 | FR-240..FR-249 (mirror) | `adapters/dot-aidd/scripts/aidd_coverage.py` | LOGIC | | | any change that is not a byte copy of T-31's file |
| T-34 | FR-240, FR-245, FR-247 docs | `skill/SKILL.md` | LOGIC | | | any other section; b1SycLink files |

## Per-task detail

### T-30 — failing tests first
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: S

**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 1
- Tokens (est): 80k
- Agent role: tests
- Model tier: medium
- Wave: 1

**Detail**
- Goal: encode AC-271..AC-282 as unit tests that fail on the current code (module absent).
- Cites: FR-240..FR-249, AC-271..AC-282.
- Depends on: none.
- Read first: `batch-staging/coverage-derive/test_coverage_derive.py` (the prototype tests: copy its synthetic `SPEC` and `TASKS` texts verbatim); `skill/scripts/aidd_progress.py` lines 91-137 (`parse_tasks`); `skill/scripts/aidd_rules.py` lines 2218-2256 (`parse_verification`).
- Files to change: `tests/test_aidd_coverage.py` (new).
- Naming contract: class `AiddCoverage(unittest.TestCase)` with methods `test_cites_tasks_kept`, `test_range_derived_via_codes`, `test_whole_suite_gets_everything_and_needs_review`, `test_unresolved_gets_no_inputs`, `test_database_row_never_reused_and_cites_line_counts`, `test_existing_inputs_never_shrink`, `test_missing_target_needs_review`, `test_changed_simulation_refuses_with_unresolved_row`, `test_changed_simulation_skips_unrelated_rows`, `test_changed_simulation_refuses_on_spec_change`, `test_dry_run_writes_nothing`, `test_apply_to_refuses_spec_and_foreign_file`, `test_json_output`, `test_summary_counts`. Production names exercised: `aidd_coverage.derive(spec_dir) -> dict` with keys `spec, root, rows, uncovered_tasks, missing_targets, summary`; each row dict has keys `n, cmd, kind, tasks, covers, inputs, database, reuse, needs_review, notes, covers_before, inputs_before`; `aidd_coverage.simulate_changed(result, changed_paths) -> dict` with keys `status, reason, selected_tasks, rows_run, rows_skipped`; `aidd_coverage.main(argv) -> int`; constant `aidd_coverage.PROPOSAL_MARK`.
- Behaviour:
  1. Header: `sys.path.insert(0, <repo>/skill/scripts)`, `import aidd_coverage as cov`; `setUp` builds a temp root with `.aidd/`, `specs/001-x/spec.md` and `tasks.md` (prototype texts) and files `src/a.py`, `src/b.py`, `src/c.sql`, `src/d.py`, `extra/keep.py`.
  2. One test per AC-271..AC-282 with the exact expectations of the Acceptance criteria table; `test_summary_counts` asserts `(rows, cites-tasks, via-fr-ac-api, whole-suite, unresolved) == (6, 1, 3, 1, 1)` and `uncovered_tasks == []`.
  3. `test_dry_run_writes_nothing` compares the sorted file list and `spec.md` bytes before and after `cov.main([spec_dir])`, ignoring `__pycache__`.
- Tests first: this task IS the tests; run the V-1 command and keep the red output (ImportError: module absent).
- Verify: `python -m unittest discover -s tests -p "test_aidd_coverage.py" -v` → red before T-31, exit 0 after.
- Do NOT: touch production code; use a database, Docker, Git or the network; weaken an assertion later.
- Done when: the 14 tests exist with exactly these names and the red run is recorded by the verifier.
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
- Wave: 2

**Detail**
- Goal: implement FR-240..FR-249 so T-30 passes.
- Cites: FR-240..FR-249.
- Depends on: T-30.
- Read first: `batch-staging/coverage-derive/coverage_derive.py` (prototype; port it, with the differences below); `skill/scripts/aidd_status.py` lines 2004-2056 (`_task_rows`) and 2099-2137 (`_changed_task_selection`); `skill/scripts/aidd_evidence.py` lines 2029-2080 (`_scope_re`, `in_scope`); the tests created by T-30 in the file named in T-30's Files to change.
- Files to change: `skill/scripts/aidd_coverage.py` (new).
- Naming contract: existing names used unchanged: modules `aidd_progress`, `aidd_rules`, `aidd_evidence`; functions `aidd_progress.parse_tasks`, `aidd_progress._resolve`, `aidd_rules.parse_verification`, `aidd_evidence._scope_re`, `aidd_evidence.in_scope`. Row dict key `needs_review` (bool) as listed in T-30. New module constants `REVIEW_MARK` (the exact marker text written in FR-245), `PROPOSAL_MARK` (FR-247 text), `METADATA = ('spec.md', 'tasks.md', 'plan.md', 'contracts.md', 'mockup-audit.md')`, `DB_RE`, `SUITE_RE`, `RANGE_RE`, `T_RANGE_RE`, `MAX_RANGE = 400`; public functions `codes_in(text) -> set[str]`, `tasks_in(text, known=None) -> set[str]`, `raw_task_codes(tasks_text) -> dict[str, set[str]]`, `derive(spec_dir) -> dict`, `simulate_changed(result, changed) -> dict`, `render_text(result) -> str`, `render_proposal(result) -> str`, `safe_target(spec_dir, target) -> str | None`, `main(argv=None) -> int`; private helpers `_resolve_target(root, p) -> str | None`, `_exists(root, pattern) -> bool`, `_matcher(globs)`.
- Behaviour:
  1. Import `aidd_progress`, `aidd_rules`, `aidd_evidence` from the script's own directory (`HERE = Path(__file__).resolve().parent`), unlike the prototype's project-first loader.
  2. `derive`: parse tasks (`parse_tasks` + `raw_task_codes`), keep task IDs as written, build code → tasks map, then classify each row per FR-241, propose Covers/Inputs per FR-243/FR-244, mark per FR-245, tag database rows per FR-246.
  3. `_resolve_target` (FR-243): try `aidd_progress._resolve`, then `getattr(aidd_progress, '_renumbered', None)` and `_alias_target`; return root-relative POSIX path, `<dir>/**` for a directory, else None; exclude paths listed in the task's `delete` key.
  4. `simulate_changed` (FR-248): in this order — policy file changed → refused; any row without Inputs or tasks → refused; any task in no row → refused; no Input matches → refused with `rows_skipped = total`; a selected row has an Input matching no file → refused; else `ok` with selected tasks, rows run, rows skipped.
  5. Notes print codes as cited in the spec (e.g. `FR-014`), not the internal integer form; the prototype's boolean review-flag key is renamed `needs_review` and its marker constant `REVIEW_MARK`.
  6. `main`: argparse per FR-240; `--apply-to` guarded by `safe_target` (FR-247); `--json` prints the result.
- Tests first: T-30 must be red before this task; keep it unmodified.
- Verify: `python -m unittest discover -s tests -p "test_aidd_coverage.py" -v` → exit 0.
- Do NOT: call Git or any subprocess; write any file other than the `--apply-to` target; propose a `Reuse` value; change any other script.
- Done when: all 14 T-30 tests pass and `python skill/scripts/aidd_coverage.py --help` exits 0.
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
- Wave: 3

**Detail**
- Goal: expose the tool as `aidd coverage`.
- Cites: FR-240.
- Depends on: T-31.
- Read first: `aidd/cli.py` lines 448-457 (the forwarded-script tuple loop).
- Files to change: `aidd/cli.py`.
- Naming contract: one new tuple in that loop, exactly `("coverage", "aidd_coverage.py", [], "Propose task Covers and Inputs for a spec's Verification rows (dry-run; never writes the spec) (aidd_coverage.py)")`.
- Behaviour: append the tuple after the `("size", ...)` entry; no other change.
- Tests first: V-3 exits 1 before this task and 0 after.
- Verify: `python -c "import sys; t=open('aidd/cli.py', encoding='utf-8').read(); sys.exit(0 if '(\"coverage\", \"aidd_coverage.py\"' in t else 1)"` → exit 0.
- Do NOT: change any other subcommand or `main()`; add arguments.
- Done when: the verify command exits 0.
- Open questions: none.

### T-33 — mirror
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
- Wave: 3

**Detail**
- Goal: keep the project bundle identical to the skill source.
- Cites: FR-240..FR-249 (mirror).
- Depends on: T-31.
- Read first: `tests/test_dot_aidd_mirror.py` (`test_verbatim_scripts_match`).
- Files to change: `adapters/dot-aidd/scripts/aidd_coverage.py` (new).
- Naming contract: none new; the target is a byte copy of `skill/scripts/aidd_coverage.py`, so every name is the one fixed in T-31.
- Behaviour: `cp skill/scripts/aidd_coverage.py adapters/dot-aidd/scripts/aidd_coverage.py`; no hand edits.
- Tests first: run the mirror test before (red if it lists the new script) and after (exit 0).
- Verify: `python -m unittest discover -s tests -p "test_dot_aidd_mirror.py" -v` → exit 0.
- Do NOT: edit the file by hand; touch any other mirror.
- Done when: mirror test passes.
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
- Wave: 3

**Detail**
- Goal: document `aidd coverage` next to incremental verification.
- Cites: FR-240, FR-245, FR-247.
- Depends on: T-31.
- Read first: `skill/SKILL.md` line 457 (the paragraph that starts with "**Incremental verification" and describes `aidd verify <spec> --changed`).
- Files to change: `skill/SKILL.md`.
- Naming contract: documents exactly these names and no others: command `aidd coverage <spec_dir> [--apply-to FILE] [--json] [--changed-file PATH]`, kinds `cites-tasks`, `via-fr-ac-api`, `whole-suite`, `unresolved`, and the review marker text exactly as written in FR-245.
- Behaviour: add 4 lines after that paragraph: what the command proposes; the four kinds; that it never writes the spec and the owner copies accepted cells; that an under-declared Covers can skip a needed test, so rows carrying the FR-245 review marker need the owner's review.
- Tests first: no code; V-4 exits 1 before this task and 0 after.
- Verify: `python -c "import sys; t=open('skill/SKILL.md', encoding='utf-8').read(); sys.exit(0 if 'aidd coverage' in t and 'via-fr-ac-api' in t else 1)"` → exit 0.
- Do NOT: change any other section; mention b1SycLink.
- Done when: the 4 lines exist and the verify command passes.
- Open questions: none.

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-30 | tests | 20 | 80 | 1 |
| 2 | T-31 | builder | 30 | 120 | 1.5 |
| 3 | T-32, T-33, T-34 | builder, builder, docs | 5 | 75 | 0.75 |

Total agent time (critical path): 55 min
Total tokens (k): 275
