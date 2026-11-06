# Amendment 10 to spec 007: retrospective 2026-11-05 — one preflight, row-level re-verification, environment preflight, DB order/contamination checks, task batches, heavy-resource lock, visual RED, and three minor fixes

> **Priority note (read first).** Order = measured cost avoided per hour of work. Size S <= 3 h, M 3-8 h, L > 8 h (agent hours incl. tests).
>
> | Pri | Item | Backlog | Size | Depends on |
> |---|---|---|---|---|
> | 0 | Baseline sync: source repo vs installed bundle have FORKED (see H0) | B13 | S | owner decision |
> | 1 | A `aidd preflight <spec>` (one command before asking the owner) | B14 | M | 0, 8 |
> | 2 | B `aidd verify --rows` + same-spec reuse by declared Inputs | B15 | M | 0 |
> | 3 | C environment preflight (memory, dev server, `Workdir`, single-row retry, env/defect class) | B16 | M | B, F |
> | 4 | G visual RED mandatory for view tasks | B17 | M | 0, F |
> | 5 | D DB checks (redefinition order in sqlcheck; contamination snapshot, unmatched filters, global gate) | B18 | M (AIDD) + M (project) | 0 |
> | 6 | F `aidd lock heavy <res>` | B19 | S | — |
> | 7 | E `aidd tasks archive` + documentation of batches | B20 | M | 0 |
> | 8 | Minor 8: `task_targets` reads unquoted paths; 0 files is not "small" | B21 | S | — |
> | 9 | Minor 9: `aidd rules pause <spec>` (owner consent, R8 only) | B22 | S | — |
> | 10 | Minor 11: agents stop after their final report | B23 | S (text) | — |
>
> Implementation order: 0 → 8 → F → A → B → C → G → D → E → 9 → 11 (11 may go with any text batch).

Intake: `AMENDMENT` of `specs/007-aidd-review-html-close-gate` (owner of `aidd rules check/approve/close`, `aidd verify`,
R8/R10 and E8/E9/E10 text). Follows amendment 08 (FR-290..293), amendment 09 (FR-294..300, backlog B1..B12) and the
draft amendment 07 (FR-270..283, full approval preflight), which it EXTENDS and does not duplicate.
Source: retrospective measured on 2026-11-05 in the client project b1SycLink (8 open specs; about 9 `aidd verify`
rounds of F38), items A-G and minors 8, 9, 11 agreed with the owner, prioritized by return.
Scope: SPECIFICATION and prioritized BACKLOG only. No tool is implemented by this document; no file under `skill/`,
`adapters/`, `aidd/`, `~/.claude/skills/aidd` or any project `.aidd/` is changed by it.
Status: DRAFT, not approved, no `Approved:` line.

FR numbering: the brief asked to continue after FR-300. Checked with
`grep -rhoE "FR-[0-9]{3,4}" specs/ skill/ adapters/ docs/`: FR-301..317 and FR-350..363 are used by spec 008
drafts, FR-901+ by specs 009+. The first free block that leaves room for 008 is **FR-370..FR-399**; this amendment
uses FR-370..FR-392. Acceptance codes AC-401..420 are used; this amendment uses **AC-430..AC-452**.

Legend: **[fact]** = read in the code/files, with `file:line`; **[measured]** = figure from the retrospective
(owner/orchestrator measurement, not re-measured here unless stated); **[inference]** = my reading, not proven.

---

## H0. Baseline finding: the AIDD source repo and the installed bundle have forked

| # | Fact |
|---|---|
| H0.1 | [fact] `skill/scripts/aidd_status.py:1146-1153` (FR-292 approval preflight inside `cmd_check`) exists only in the AIDD working tree, uncommitted (`git diff skill/scripts/aidd_status.py` shows it as `+`; HEAD `cfe1d0f` lacks it). It is **absent** from `D:\Fuentes\b1SycLink\.aidd\scripts\aidd_status.py:1140-1152` and from `~/.claude/skills/aidd/scripts/aidd_status.py` (both 163 586 bytes, written 2026-11-05 08:32). So in b1SycLink `aidd rules check` does NOT run `check_verification`: this alone explains why invalid Verification rows were only seen at review/approve time (item A). |
| H0.2 | [fact] The opposite direction: the installed bundle has `aidd_red.py`, `aidd_close_ledger.py` (B5/B12), `WARN_REVIEW_SOURCE_CHARS = 300_000` (`b1SycLink/.aidd/scripts/aidd_review.py:50`, B6), `with_batches` (TASKS-BATCH-COVERAGE) and `close --check` (B10); `skill/scripts/` and `adapters/dot-aidd/scripts/` have NONE of them (`grep -c "def with_batches" skill/scripts/aidd_rules.py` = 0). They live only as staged diffs in `batch-staging/db-verify-rounds/PATCH-*.diff`. |
| H0.3 | [inference] Every change below must be written against ONE baseline. Writing it against `skill/` today would either lose B5/B6/B10/B11/B12/batches or re-fork. |

**FR-370 (baseline).** Before any task of this amendment, the AIDD source tree (`skill/`, `adapters/dot-aidd/`, `aidd/cli.py`)
contains exactly the code that is installed in `~/.claude/skills/aidd` and `b1SycLink/.aidd` PLUS FR-292, verified by a
script that lists, per file, `source == installed` / `differs`. Applying the staged patches into the source repo is an
owner decision (it is a commit to the AIDD repo).

---

## Problem, change and requirements per item

### A. One `aidd preflight <spec>` before asking the owner

**Measured.** F37 approved 3 times in one day; F38 had 3 review pages because of row V-24.

**Facts.**
- [fact] `cmd_check` (`skill/scripts/aidd_status.py:1140-1165`) runs `rules.check_spec_dir` and, since FR-292 (source only, H0.1), `rules.check_verification` while `tasks.md` has no `Approved:` line.
- [fact] `check_verification` (`skill/scripts/aidd_rules.py:2769-2804`) already calls `verification_command_problem` (`aidd_rules.py:2714-2766`) per row; the messages "inline code (...) is not a test" (`:2750`) and "neither a known test runner ... nor an invocation of an existing project file" (`:2762-2764`) come from there. They are NOT review-only: they appear at `aidd rules check` wherever FR-292 is installed. Contradiction with the hypothesis: the gap in b1SycLink is the missing install (H0.1), not the design.
- [fact] A row passes the lint if ANY token names an existing file (`_names_existing_file`, `aidd_rules.py:2697-2711`). F38 V-18 (`node eDoc/web/node_modules/@playwright/test/cli.js test --config=... import-costing-visual-mocked.spec.ts`) passes because `cli.js` exists even when the spec file the row is about does not exist yet. So "a row that points to a file that does not exist yet" is NOT caught today when a runner path is present; it is caught (as the generic "neither ..." message) only when no token exists.
- [fact] Size: `MAX_REVIEW_SOURCE_CHARS = 400_000` (`skill/scripts/aidd_review.py:49`, refused at `:831`); the 300 000 warning exists only in the installed copy (`b1SycLink/.aidd/scripts/aidd_review.py:50,223-228`).
- [fact] The full preflight with a cause catalogue (`P01..P11`, `aidd_approve_preflight.py`, `--fix`, question builder) is designed in draft amendment 07 (FR-270..283) and NOT implemented.
- [fact] `task_precision_check` is a project tool (`b1SycLink/tools/task_precision_check.py`), not part of AIDD.
- No migration-numbering check exists in AIDD (`grep -n "renumber\|numbering" skill/scripts/aidd_rules.py skill/scripts/check_spec.py` = 0 hits).

**Minimal change.** Implement amendment 07's `preflight` as the command `aidd preflight <spec>` (alias of `aidd rules approve --preflight <spec>`), and add four causes to its catalogue: `P12` planned-file row, `P13` size band, `P14` migration order (from D1), `P15` project extra checks. Nothing in `cmd_approve` changes except that it calls preflight first (FR-273 of amendment 07).

| Code | Requirement |
|---|---|
| FR-371 | `aidd preflight <spec>` prints every cause in the amendment 07 FR-272 line format and exits 0 only when no cause has `blocks='approve'`. It runs, in this order, without stopping at the first failure: (1) `rules.check_spec_dir`; (2) `rules.check_verification`; (3) `P12`; (4) `P13`; (5) `P14`; (6) `P15`; (7) the review state exactly as `cmd_approve` maps it (amendment 07 FR-280: P06..P09). Read-only: writes no file and records no event. |
| FR-372 | `P12` planned-file row: for each Verification row, every token that looks like a test file (regex `\.(test|spec)\.[A-Za-z0-9]+$` or `_test\.py$` or `test_.*\.py$`) and does not exist under the root is reported. If the path is listed in the `Target file` column of some task (via `task_targets`, after item 8) the cause is `P12` severity `note` ("planned by T-nn; row will run after that task"); otherwise `P12` `blocks='approve'` ("row n names `<path>`, which no task creates"). |
| FR-373 | `P13` size: for every review source (spec.md, plan.md, each tasks file) over 300 000 chars a `warn` cause; over 400 000 a `blocks='approve'` cause naming the file, the size and the fix `aidd tasks archive` (item E) or a split by amendment batch. Constants are imported from `aidd_review` (`MAX_REVIEW_SOURCE_CHARS`, `WARN_REVIEW_SOURCE_CHARS`), never duplicated. |
| FR-374 | `P15` project extra checks: commands listed one per line under a `## Preflight` heading of `docs/charter.md` (or the charter path `check_charter.py` already resolves), each a single command where `{spec}` is replaced by `specs/<id>` and `{tasks}` by the space-separated tasks files; each is linted with `verification_command_problem` and run with the `_run_row` policy (root cwd, timeout `AIDD_PREFLIGHT_TIMEOUT`, default 120 s); exit != 0 = `blocks='approve'` with the first 20 output lines. No `## Preflight` heading = no P15 cause. |
| FR-375 | The orchestrator rule (AIDD.md Step 4 end, SKILL.md, CORE.md §5) becomes: run `aidd preflight <spec>` until exit 0, THEN ask the owner. `aidd rules check` keeps FR-292 behaviour (compatibility) and prints `NOTE run aidd preflight <spec> before asking the owner`. |

**Acceptance.**
| Code | Scenario | Command | Expected |
|---|---|---|---|
| AC-430 | fixture with an inline `python -c` row, a 410 000-char tasks file, a row naming a non-existent `x.test.ts` not in any Target file, and a stale review | `python -m unittest tests.test_aidd_preflight -v` | exit 0; the test asserts all 4 causes printed in one run, exit code 1 of `aidd preflight` |
| AC-431 | same fixture but `x.test.ts` is a Target file of T-03 | same | P12 printed as `note`, not blocking |
| AC-432 | for every fixture, causes with `blocks='approve'` == set that makes `aidd rules approve` refuse | same | invariant holds (amendment 07 FR-273) |

**Files.** new `skill/scripts/aidd_approve_preflight.py` (amendment 07), `skill/scripts/aidd_status.py` (`cmd_approve` calls it; `cmd_check` note), `aidd/cli.py` (`preflight` subcommand → `aidd_status.py preflight`), mirrors in `adapters/dot-aidd/`, `skill/AIDD.md`, `skill/SKILL.md`, `adapters/dot-aidd/CORE.md`, new `tests/test_aidd_preflight.py`.
**Risk/compat.** Read-only command; approval hash and verification hash untouched. `cmd_approve` refusing earlier never changes a hash. Existing approvals stay valid (test T-A5).
**Size.** M (6-8 h, most of it is amendment 07's catalogue).

---

### B. `aidd verify --rows V-17,V-18` and real reuse by per-row inputs

**Measured.** Nine F38 rounds (r10..r18, 600-2321 s each) re-ran ALL rows although only one failed; V-2 (full suite) reached 1628 s.

**Facts (why reuse never acted).**
- [fact] Self-reuse of a previous PASS row happens only through `input_reuse` (`aidd_status.py:2383`, `2435-2453`), built by `_reusable_input_rows` (`:1783-1805`), which keeps a row only if it has `reuse_policy == 'hermetic'`, `input_globs`, `input_fp`, `environment_id` and `environment_declaration`.
- [fact] `environment_id` is produced only by `_contract_environment_id` (`:1688-1732`), which returns None unless the row declares `Environment: contract:offline;vars=...;packages=...`, the command is a plain `python <file>.py` of the same interpreter, and **the command does not match `_DB_RUNNER_RE`** (`:1730`, regex at `:1812`: `db_verify|psql|pg_prove|docker|supabase|--tap`).
- [fact] F38 `spec.md` `## Verification`: 16 of 18 rows are `python eDoc/tools/db_verify.py --psql "docker exec ..."`; V-3/V-17 are vitest, V-18 Playwright; NO row declares `Inputs`, `Reuse` or `Environment` (grep of `spec.md:485-513`). Therefore no F38 row was ever eligible: the reuse path is structurally closed for DB, vitest and Playwright rows.
- [fact] `Scope:` (`spec.md:485`, a long explicit list) only decides staleness of the whole run (`aidd_status.py:2357`, `2730`); it plays no role in row reuse. Round cache is off (`round_on = False`, `:2389`). Contradiction with the hypothesis: it was not a too-wide fingerprint nor intermediate edits; the rows simply had no reuse contract and DB runners can never have one.
- [fact] Documentation contradicts itself: `skill/AIDD.md:590` and `:631` say per-row reuse is disabled "even for `Reuse: hermetic` with unchanged Inputs", while `skill/SKILL.md:463` and the code (`:2435-2453`) reuse hermetic offline Python rows. The b1SycLink `AGENTS.md` sentence "the same spec re-verified with unchanged inputs reuses its own passed rows automatically" is true only for those Python rows.
- [fact] A partial selection exists: `--tasks T-01,T-02` (`:2281-2306`, `_task_rows` `:2076-2096`) and `--changed`; they record `task_verify_run`, never the full `verify_run` the close gate needs (`:2735-2764`). No `--rows` flag (`aidd_status.py:3210-3253`).

**Minimal change.**
1. `--rows V-17,V-18`: select rows by their `#` cell; record `rows_verify_run` (partial, like `task_verify_run`; never satisfies close).
2. New per-row reuse policy `Reuse: same-spec` (opt-in in the approved Verification table, so the owner approves it): a later FULL `aidd verify <spec>` carries a previous PASS of that row (same spec, same command, same Expected, same `Inputs` fingerprint, same `verify_hash`, previous run `stable`, evidence sha1 intact) as `CARRIED row n`, WITHOUT running it. Allowed for DB runners because the row's `Inputs` must list the migrations/tests/runner it reads (e.g. `eDoc/supabase/migrations/**, eDoc/supabase/tests/imc_*.test.sql, eDoc/tools/db_verify.py`); external state is reset by the runner from its template (b1SycLink `db_verify.py` clones `edoc_verify_tpl_*`, `evidence/verify-V-2.txt` line 3). Never crosses specs; `--full` disables it; a row without `Inputs` is never carried.
3. Fix the two documentation paragraphs to describe the actual behaviour.

| Code | Requirement |
|---|---|
| FR-376 | `aidd verify <spec> --rows <n>[,<n>...]` runs only the rows whose `#` cell equals one of the values (case-insensitive, `V-` prefix optional), in table order; unknown value = refuse before running (`Refused: unknown rows: ...; nothing was executed.`); records `rows_verify_run{spec, rows, results, verify_hash, code_fp_end}`; prints `rows verification: PASSED|FAILED (k/m rows); not a full-spec verification`. Cannot be combined with `--wave`, `--tasks`, `--changed`. |
| FR-377 | Row attribute `Reuse: same-spec` (column `Reuse`, existing parser `aidd_rules.py:2233-2252`). A full run carries a prior PASS of the row iff: same spec; prior full `verify_run` or `rows_verify_run` of this spec with `stable is True` (for `rows_verify_run`: its `code_fp_end` equals the current run's `st_start` fingerprint of the row's Inputs); same `_verification_key(cmd)` and Expected; non-empty `Inputs`; `row_input_fingerprint` equal now and at end of run; same `verify_hash`; evidence file sha1 equal. Output line `CARRIED row n: <cmd> (passed at <ts> on the same Inputs) → <evidence>`; result has `carried=True, carried_from=<ts>`. |
| FR-378 | The close gate accepts a `verify_run` with carried rows only when each carried row's Inputs fingerprint still matches at close; otherwise the gap message is `R10 row n was carried but its Inputs changed → aidd verify <spec> --rows n`. |
| FR-379 | `verification_hash` (`aidd_rules.py:2427-2440`) is unchanged for every row that does not declare `Reuse: same-spec` (it already appends `|reuse:<value>` only when present), so existing hashes are byte-identical. |
| FR-380 | `skill/AIDD.md:590,631` and `skill/SKILL.md:463` describe one behaviour: hermetic offline Python rows may reuse (as coded); `same-spec` rows may be carried within the spec; DB/container runners only via `same-spec` with Inputs; nothing crosses specs except the offline contract. |

**Acceptance.**
| Code | Scenario | Command | Expected |
|---|---|---|---|
| AC-433 | 3-row fixture, row 2 fails, fix, `--rows 2` passes, full run | `python -m unittest tests.test_verify_rows -v` | full run executes row 1/3 only if they lack `Reuse: same-spec`; with it, prints `CARRIED row 1`, `CARRIED row 3`, runs nothing else |
| AC-434 | carried row whose Inputs file changed | same | row is executed, not carried |
| AC-435 | hash pin over every spec of `tests/gate_fixtures.py` and over a copy of 5 b1SycLink spec.md files stored under `tests/fixtures/am10/` | `python -m unittest tests.test_am10_hash_compat -v` | `verification_hash` and `approval_hash` equal to the pinned values |

**Files.** `skill/scripts/aidd_status.py` (`cmd_verify`, `_reusable_input_rows` sibling `_carriable_rows`, argv parsing `:3210-3253`, `_close_gaps`), `skill/scripts/aidd_rules.py` (accept `same-spec` value), mirrors, `skill/AIDD.md`, `skill/SKILL.md`, tests `tests/test_verify_rows.py`, `tests/test_am10_hash_compat.py`.
**Risk.** A carried DB row trusts that the runner resets its database; that trust is declared by the owner per row (approved table). Mitigation: carry never crosses a change of the row's Inputs; `--full` before close if the owner wants; documented. No existing hash changes (AC-435).
**Size.** M (6-8 h).

---

### C. Environment preflight in `aidd verify`

**Measured.** Vite's esbuild died ("The service was stopped"); e2e fixtures used `process.cwd()` and from the root did not read `eDoc/web/.env.local`: five rounds of V-18; `ImportParamsPage` failed with 865 MB free and passed 3 of 3 alone.

**Facts.**
- [fact] Every row runs with `cwd=str(root)` (`aidd_status.py:1610`); there is no way to set a working directory, and `cd <dir> && ...` is a rejected form (E10(e), FR-298). So a runner that resolves config from `process.cwd()` structurally reads the wrong directory.
- [fact] No memory, server-health or load probe exists in `cmd_verify` (`:2257-2560`); a failed row is final (`_row_ok`, `:1630-1634`); there is no retry and no failure class.

**Minimal change.** Optional row column `Workdir` (relative directory inside root); optional spec-level lines `MinFreeMB:` and `Health:` under `## Verification`; ONE automatic retry of ONLY a failed row when an environment signature is present; class `env`/`defect` in the result and the evidence header.

| Code | Requirement |
|---|---|
| FR-381 | Column `Workdir` (optional): a root-relative existing directory, no `..`, no absolute path; `_run_row` uses `cwd=root/Workdir`. Invalid = refuse before running. Appended to `verification_hash` only when present (`|workdir:<v>`), so existing hashes do not change. |
| FR-382 | Before the first row: free physical memory (Windows `GlobalMemoryStatusEx` via `ctypes`; Linux `/proc/meminfo` `MemAvailable`; otherwise unknown) is compared with `MinFreeMB:` (default env `AIDD_VERIFY_MIN_FREE_MB`, default 1500). Below the threshold: wait up to `AIDD_VERIFY_ENV_WAIT` (default 120 s, poll 5 s); still below = print `ENV-WAIT free <n> MB < <min> MB` and continue (never refuse). Each `Health: <url>` line is fetched (`urllib`, 5 s); failure = refuse `Refused: health check <url> failed; nothing was executed.` |
| FR-383 | Env signatures (constant `ENV_SIGNATURES` in `aidd_status.py`): free memory at failure time < threshold; output matches `The service was stopped|ECONNREFUSED|EADDRINUSE|ENOMEM|JavaScript heap out of memory|Worker terminated due to reaching memory limit`. A FAILED row with a signature is retried ONCE, alone, after the FR-382 wait; the first evidence is kept as `verify-<n>.attempt1.txt`. The result records `class: env` (signature found; retry outcome is the row outcome, `retried: 1`) or `class: defect` (no signature, or retry failed without signature). The evidence header gets `[aidd verify] class: env (<signature>)`. |
| FR-384 | `aidd triage` (`skill/scripts/aidd_triage.py`) groups failures by `class` first. |

**Acceptance.**
| Code | Scenario | Command | Expected |
|---|---|---|---|
| AC-436 | fixture row that reads `./cfg.txt`, `Workdir: sub` | `python -m unittest tests.test_verify_env -v` | passes with Workdir, fails without |
| AC-437 | fake row printing `The service was stopped` on first call, passing on second (state file) | same | one retry, `class: env`, `retried: 1`, both evidence files exist |
| AC-438 | row failing with an assertion | same | no retry, `class: defect` |
| AC-439 | memory probe monkeypatched to 800 MB | same | `ENV-WAIT` printed, run continues |

**Files.** `skill/scripts/aidd_status.py` (`_run_row(cmd, root, out_path, timeout, cwd=None)`, new `_free_mb()`, `_env_signature(body)`), `skill/scripts/aidd_rules.py` (`parse_verification` reads `workdir`; `_verification_globs` keys `minfreemb`, `health`), `skill/scripts/aidd_triage.py`, mirrors, docs E9, `tests/test_verify_env.py`.
**Risk.** Retry could mask a real flaky defect: only one retry, only with a signature, and the class is visible in evidence and triage. No hash change for tables without the new column (AC-435 extended).
**Size.** M (5-7 h).

---

### D. Four mechanical DB checks

**Measured.** A migration that redefines a function was numbered before the last redefiner (3494 < 3510) and overwrote F37's correction; `sales_concurrency` left 1600 confirmed invoices; `--skip-tests` (exact name) / `--only-tests` (substring) silently matched nothing; F39 V-3 `npm test --prefix eDoc/web` runs 5519 tests and is blocked by other specs' tests.

**Facts.**
- [fact] `aidd_sqlcheck.py` only compiles and prints the apply manifest in natural order (`:57-71`, `:215`); no object-level analysis.
- [fact] `sql_graph.py` already parses `CREATE [OR REPLACE] FUNCTION/PROCEDURE/VIEW/TRIGGER/INDEX` (`:244-253`) and stores, per function, only the LAST defining file (`f["file"], f["line"] = self.file, self.line`, `:507`): the history needed for the order check is discarded.
- [fact] `db_verify.py` is a PROJECT tool (b1SycLink `eDoc/tools/db_verify.py`, 1803 lines), not AIDD. `selected_tap_tests` (`:863-871`) filters by substring and exact skip name; `--skip-tests` prints `[SKIP] <name>` for every name given, whether or not a file has that name (`:1573-1576`); a needle of `--only-tests` that matches nothing is not reported (only an empty total is caught by AIDD: `VERIFY_BAD_OUTPUT_RE` `pgTAP:\s*0\s+files`, `aidd_rules.py:2821-2822`).
- [fact] `aidd_triage.py` already classifies failing pgTAP/vitest/pytest files across specs (`:16-24`).
- [inference] On the live (incremental) database the later-written 3494 was applied after 3510 and won; on a fresh rebuild 3510 wins: the two databases disagree, which is worse than either result.

**Minimal change.**
- D1 (AIDD): `aidd sqlcheck --order <migrations_dir> [--new <file>...]`: build the per-object definer list in natural order; a NEW file (given, or untracked/modified per `git status --porcelain`) that defines an object whose latest existing definer has a higher number = ORDER error. Also used as preflight cause `P14`.
- D2 (project contract, implemented in b1SycLink under its own AIDD spec): per test file, snapshot `count(*)` of the tables the test touches (or `pg_stat_user_tables.n_live_tup` of all non-system tables) before/after; delta != 0 after the file's own cleanup = `[CONTAMINATION] <file>: <table> +<n>`, exit 1.
- D3 (project contract): `--skip-tests` names with no file and `--only-tests` needles with no match print `WARN unmatched: <x>` and exit 2 (usage). AIDD adds `\bunmatched:` to `VERIFY_BAD_OUTPUT_RE` so a row that prints it is FAIL even with exit 0.
- D4 (AIDD): row attribute `Gate: global` — such a row (whole-suite `vitest`, `npm test`, full `db_verify`) runs ONCE per round via `aidd verify --global <spec>` in the designated spec; its failures are attributed per spec with `aidd triage` (by mapping each failing test file to the spec whose `Target file` lists it); a spec's close needs its own scoped rows PASS plus the round's global run with ZERO failures attributed to it.

| Code | Requirement |
|---|---|
| FR-385 | `aidd_sqlcheck.py --order DIR [--new FILE ...]`: objects = functions/procedures (name + normalised arg types), views, triggers (name + table), indexes; exit 1 with `ORDER <new_file> redefines <object> but <later_file> (number <n>) defines it later; renumber <new_file> after <n>`; exit 0 otherwise. No `pglast` needed (regex routes of `sql_graph.py:244-253`, imported, not copied). |
| FR-386 | `sql_graph.py` keeps `f["defined_in"] = [(file, line), ...]` in apply order in addition to `file`/`line` (existing keys unchanged). |
| FR-387 | `VERIFY_BAD_OUTPUT_RE` gains `\bunmatched:\s` and `\[CONTAMINATION\]`. E8 text states the D2/D3 runner contract (any engine). |
| FR-388 | Row attribute `Gate: global` (column `Gate`): `aidd verify <spec>` skips it with `GLOBAL row n: runs once per round (aidd verify --global <spec>)`; `aidd verify --global <spec>` runs only those rows and records `global_verify_run{spec, results, attribution}` where `attribution = {spec_id: [failing items]}` from `aidd_triage`; close of spec X requires the latest `global_verify_run` of the round to have no item attributed to X. Appended to `verification_hash` only when present. |

**Acceptance.**
| Code | Scenario | Command | Expected |
|---|---|---|---|
| AC-440 | fixture dir: `3510_a.sql` defines `f(int)`, new `3494_b.sql` redefines `f(int)` | `python -m unittest tests.test_aidd_sqlcheck -v` | exit 1 and the ORDER line; renaming to `3511_b.sql` gives exit 0 |
| AC-441 | evidence body with `WARN unmatched: foo.test.sql` and exit 0 | `python -m unittest tests.test_aidd_rules_r10 -v` | `verify_output_problem` returns a problem |
| AC-442 | two specs, global row with one failing file owned by spec A | `python -m unittest tests.test_verify_global -v` | close gap for A, none for B |

**Files.** `skill/scripts/aidd_sqlcheck.py`, `skill/scripts/sql_graph.py`, `skill/scripts/aidd_rules.py`, `skill/scripts/aidd_status.py`, `skill/scripts/aidd_triage.py`, mirrors, AIDD.md E8; tests above. Project side (b1SycLink, separate spec): `eDoc/tools/db_verify.py`.
**Risk.** D1 false positives on overloads: key includes normalised arg types. D4 changes close requirements only for rows that opt in with `Gate: global`.
**Size.** M for AIDD (D1+D4, 6-8 h); M for the project (D2+D3).

---

### E. Batch policy: `aidd tasks archive` and documentation

**Measured.** F37 tasks.md 449k (now 454 980 bytes, measured `wc -c` 2026-11-05), F38 457k (now 340 623 + `tasks-amendment-07.md` 119 032 + `tasks-amendment-08.md` 55 983: F38 was already split by hand), F36 856 389 bytes — all over 400 000 per file.

**Facts.**
- [fact] The batch rule (`tasks.md` + `tasks-<name>.md`, combined text with `<!-- aidd-batch: <name> -->` markers in sorted order, one `Approved:` line in `tasks.md`, per-file 400 000 limit) is in `batch-staging/db-verify-rounds/PATCH-TASKS-BATCH-COVERAGE.md` and installed in the client bundle, not in `skill/` (H0.2). The patch itself says "docs (`skill/AIDD.md`, `CORE.md`) do not describe the rule yet".
- [fact] Moving a `### T-nn` block from `tasks.md` to a batch changes the combined text (marker + order), so `approval_hash` (`aidd_rules.py:1556-1561`, over the combined text after the patch) changes and the approval becomes void (R6) — an archive is never hash-neutral.

**Minimal change.** `aidd tasks archive <spec> --amendment NN` moves the task blocks (and their Waves rows) whose `Spec id`/heading cites amendment NN to `tasks-amendment-NN.md`, keeping each file's own R1 totals valid. It is allowed only when it cannot void a live approval: the spec is closed (`closed` event after the last approval), or `tasks.md` has no valid approval (drafting the next amendment, which needs a new approval anyway). Otherwise it refuses and says when to run it.

| Code | Requirement |
|---|---|
| FR-389 | `aidd tasks archive <spec> --amendment NN [--dry-run]`: selection = `### T-nn` blocks and task-table rows whose text contains `amendment NN` / `amendment-NN` / `(am. NN)` (case-insensitive) — the dry run prints the list and the resulting sizes per file; apply writes `tasks-amendment-NN.md` (refuse if it exists) and the reduced `tasks.md` via the CLI process (R9 writer), then runs `check_spec_dir` R1 per file and rolls back both files if any R1 violation appears. Refused when `rules.approval_valid(combined)` is true and the spec is not closed: `Refused: archive changes the approval hash; run it after aidd rules close <spec> or while drafting the next amendment (before asking approval).` |
| FR-390 | `skill/AIDD.md` (Step 4), `skill/SKILL.md` and `adapters/dot-aidd/CORE.md` §5 document the batch rule (name pattern, combined hash, single `Approved:` line, per-file 400 000 limit / 300 000 warning, and `aidd tasks archive`). |

**Acceptance.**
| Code | Scenario | Command | Expected |
|---|---|---|---|
| AC-443 | approved, open fixture | `python -m unittest tests.test_tasks_archive -v` | refuse, files unchanged (sha1 equal) |
| AC-444 | closed fixture with amendment 02 blocks | same | `tasks-amendment-02.md` created; R1 passes per file; combined text contains every original task block exactly once |
| AC-445 | `grep -n "tasks-<name>.md" skill/AIDD.md adapters/dot-aidd/CORE.md` | `python -m unittest tests.test_dot_aidd_mirror` | both found; mirror identical |

**Files.** new `skill/scripts/aidd_tasks_archive.py`, `aidd/cli.py` (`tasks archive`), mirrors, docs, `tests/test_tasks_archive.py`.
**Risk.** Never runs under a live approval, so no approval is voided. Depends on H0 (batch coverage in source).
**Size.** M (4-6 h).

---

### F. Heavy-resource mutual exclusion `aidd lock heavy <res>`

**Measured.** Serialization of agents and orchestrator is done by hand today; a verification run concurrently with vitest produced false failures.

**Facts.** [fact] `aidd_job.py` caches/waits one job per command+inputs (`cmd_run` `:508`, `_pid_alive` `:180`) but has no cross-process lock; amendment 09 B3 (Playwright queue) is not implemented. b1SycLink `db_verify.py` serializes runs on the same DB slot itself (AGENTS.md), but not vitest/Playwright.

**Minimal change.** `aidd lock heavy <res> -- <cmd...>`: acquire `.aidd/locks/<res>.lock` (atomic `os.open(O_CREAT|O_EXCL)`; content `pid, host, started, cmd`), FIFO by a ticket file, stale when `_pid_alive(pid)` is false or older than `AIDD_LOCK_MAX_S` (default 3600 s); run the command; release in `finally`; exit code = the command's. `aidd lock status` lists holders/waiters. `aidd verify` wraps a row in the lock when the row has `Lock: <res>`.

| Code | Requirement |
|---|---|
| FR-391 | Resources: free names matching `[a-z0-9-]{1,32}`; documented ones `base`, `playwright`, `vitest-full`. Wait prints `LOCK-WAIT <res> held by pid <p> since <ts>` every 30 s; `--timeout S` (default 1800) then exit 75. Row column `Lock` appended to `verification_hash` only when present. AIDD.md E8/E9: any full DB, full vitest or Playwright run by an agent or the orchestrator goes through `aidd lock heavy`. |

**Acceptance.** AC-446: two subprocesses on the same resource never overlap (timestamps), stale lock of a dead pid is taken over — `python -m unittest tests.test_aidd_lock -v` exit 0.
**Files.** new `skill/scripts/aidd_lock.py`, `aidd/cli.py`, `aidd_status.py` (`Lock` column), mirrors, docs, test.
**Risk.** Dead-lock by a hung holder: max age + pid check. `.aidd/locks/` is written only by the CLI (R9 compatible).
**Size.** S (2-3 h). Enables C's retry (no concurrent heavy run during retry) and G's Playwright serialization (replaces B3).

---

### G. UI with mandatory visual RED

**Measured.** F37 and F38 were redone; F40 106 of 116 cases differed; F42 99 of 117.

**Facts.**
- [fact] Installed `aidd_red.py` (`b1SycLink/.aidd/scripts/aidd_red.py:1-17`) stores a RED receipt `evidence/red-T-nn.txt` and `aidd red --check` lists tasks with `Agent role: tests` without a receipt; it knows nothing about view tasks or visual measurement. It is not in `skill/` (H0.2).
- [fact] Nothing blocks marking a VIEW task done without a measurement: the `Status` column is hash-neutral and no gate reads it for visual evidence. F38 tasks carry a `View / logic` column (`tasks.md:28`), so view tasks are detectable.
- Amendment 09 FR-294 defines the verdict rule (match/differ/not-verified); B1/B2 (contract generator, comparator) are not built.

**Minimal change.** For every task whose `View / logic` cell is `VIEW` (or whose Target file matches `_IMPACT_UI_RE`, `aidd_rules.py:1627`): (1) a RED receipt before implementation (`aidd red`), and (2) a visual verdict stored by the CLI: `aidd red --visual T-nn -- <measure-cmd>` runs a project measurement command that must print one JSON line `{"verdict":"match|differ|not-verified","screen":"SCREEN-XX","cases":n,"differ":k}`; the CLI writes `evidence/visual-T-nn.json`. `aidd red --check` reports `MISSING-VISUAL: T-nn` and `DIFFER: T-nn (k/n)`; `aidd close-ledger` and `aidd rules close` refuse while any view task lacks `match` (or an owner-approved `not-verified` reason line `Visual: not-verified (<reason>)` in the task block).

| Code | Requirement |
|---|---|
| FR-392 | As above; the measurement command is linted with `verification_command_problem`, run under `aidd lock heavy playwright` (F), timeout `AIDD_VISUAL_TIMEOUT` (default 600 s). The close gap reads: `R10 view task T-nn has no visual verdict (aidd red --visual T-nn -- <cmd>)` / `... visual verdict differ k/n`. A view task marked done without `match` makes `aidd preflight` (A) and `aidd rules check` print `FAIL R10` for that task once the spec is approved and building. |

**Acceptance.** AC-447: fixture with two VIEW tasks, one with `match`, one without — `python -m unittest tests.test_aidd_red_visual -v`: `--check` exit 1 with `MISSING-VISUAL: T-02`; close refused; after recording `match`, exit 0.
**Files.** `skill/scripts/aidd_red.py` (after H0), `skill/scripts/aidd_close_ledger.py`, `skill/scripts/aidd_status.py` (`_close_gaps`), `skill/scripts/aidd_rules.py`, mirrors, docs E10(a)/(d), test.
**Risk.** Specs approved before this amendment: the close requirement applies only when `tasks.md` approval date >= the install date of this rule OR the spec declares `Visual-gate: on` — so no current approval is voided and no closing rule changes retroactively without the owner. The approval hash is not touched.
**Size.** M (5-7 h) without B1/B2; the verdict producer stays a project script until B1/B2 exist.

---

### Minor 8. `task_targets` sees only backticked paths

**Measured.** F37/F40/F41/F42 report "0 files"; the R7 note "small change ... needs only functional" underestimates.

**Facts.**
- [fact] `task_targets` (`aidd_rules.py:2341-2364`) takes only `` `...` `` spans of the `Target file` cell (`:2358`). F38 rows have bare paths (`tasks.md:2452`: `| T-100 | ... | eDoc/supabase/migrations/3436_imc_preview_cancel_mode_guard.sql | LOGIC | ...`), so they yield nothing.
- [fact] `impact_summary` (`:1633-1659`) classifies `n <= 2` as `small`, **including n = 0** (`:1642`). `required_domains` guards with `imp['files'] > 0` (`:1616`), but the close note does not.
- [fact] Contradiction with the hypothesis: the message IS in the current source, as an f-string, in `_close_gaps` (`skill/scripts/aidd_status.py:2976`, text at `:3036-3040`: `R7 note: this is a {magnitude} change ({files} target file(s)); it needs only {domains}...`). Literal search for "small change" fails because `small` is interpolated. The same code is in the installed copy (`b1SycLink/.aidd/scripts/__pycache__/aidd_status.cpython-312.pyc`, compiled from the 2026-11-05 install) — not an old version.
- [fact] `task_targets` also feeds `Scope: auto` (`verification_scope`, `:2367-2375`) — bare paths are also missing from auto scopes.

| Code | Requirement |
|---|---|
| FR-393 | `task_targets` also accepts unquoted cell content: split the cell on `+`, `,` and whitespace; keep tokens that contain `/` and end in an extension `\.[A-Za-z0-9]{1,6}$`, without `<`, not under `specs/`, and skip cells that start with `same owner as`. Backticked parsing unchanged. |
| FR-394 | `impact_summary` returns `magnitude: 'unknown'` when `files == 0`; `_close_gaps` prints the R7 note only when `magnitude in ('small','medium','large')` and `files > 0`. |

**Acceptance.** AC-448: `python -m unittest tests.test_aidd_rules -v` with new cases (bare path, `a + b`, `same owner as T-01`, zero files → `unknown`).
**Risk / compat.** `task_targets` is used by `Scope: auto`; a spec with bare paths and `Scope: auto` gets a WIDER scope, which can mark its last verification stale once (never invalidates an approval: approval hash does not use it). Listed in the pending re-verify set; compat test T-8.4 measures which b1SycLink specs use `Scope: auto` (read-only).
**Size.** S (1-2 h).

---

### Minor 9. R8 stop gate blocks 3 times per approved spec under legitimate construction

**Facts.** [fact] `stop_gate.py:24-27,44-53`: up to `AIDD_STOP_BLOCKS` (default 3) blocks per `(spec, approval hash)`; `evaluate` (`:185-222`) blocks a target spec with code edits after approval and no closing audit — which is every spec in the middle of its build. Only `AIDD_RULES=warn|off` (owner, global) skips it.

**Minimal change.** `aidd rules pause <spec> [--hours N]` (N <= 24, default 8), owner consent with the same mechanism as approve (question tag `[pause:<spec>:<h8>]`, option label exactly `Pausar`; `_ASK_FIX` pattern, `aidd_status.py:1172-1174`); records `stop_pause{spec, key, until}`. While valid (same approval hash, `now < until`, no `aidd rules resume <spec>`), `stop_gate.evaluate` does not block that spec and does not consume its budget; it prints one reminder line instead. It never affects R6, R9, R10 or `aidd rules close`.

| Code | Requirement |
|---|---|
| FR-395 | As above. A pause is void when the approval hash changes. `aidd status` shows `paused until <ts>`. Without consent: `Refused` with the question text to ask. |

**Acceptance.** AC-449: `python -m unittest tests.test_stop_gate -v` new cases: paused → not blocked, budget unchanged; expired → blocked; other hash → blocked; close still refused without audit.
**Risk.** Not a hole: owner-consented, time-bounded, hash-bound, R8-only. **Size.** S (2-3 h).

---

### Minor 11. Agents must stop after their final report

**Measured.** One agent re-sent the same report 7 times saying "waiting for my own work".

**Fact.** [fact] `skill/AIDD.md` has no rule about ending a subagent run (`grep -n "final report\|stop after" skill/AIDD.md` = 0 hits).

| Code | Requirement |
|---|---|
| FR-396 | E9 gets item (g): every builder/verifier/auditor brief ends with `When your report is delivered, end your run: do not wait for more work, do not resend the report, do not poll.`; the orchestrator does not reply to a duplicated report and stops an agent that repeats it (host stop tool). Same sentence in SKILL.md and CORE.md §5. |

**Acceptance.** AC-450: grep finds the sentence in `skill/AIDD.md`, `skill/SKILL.md`, `adapters/dot-aidd/CORE.md`; `test_dot_aidd_mirror` passes. **Size.** S (0.5 h).

---

## Extension 2026-11-05 (b): test tiers, capacity budget, light seeding, perf-risk template, psql metacommands

Source: b1SycLink F38, measured by the orchestrator on 2026-11-05 [measured]: seeding 38 000 lines for a load test took
~40 min (the seed goes through the business logic document by document, ~2 min per 2 000 lines, worse with volume);
`aidd verify` of F38 took ~600 s per round (V-2 full `db_verify` 315 s, V-18 Playwright 132 s) and was repeated every
round. The load measurement found a real defect no small functional test sees: plpgsql switches to a generic plan from
the 6th execution and `fe_rpt_import_buildup` goes from ~80 ms to ~950 ms; with `SET plan_cache_mode =
force_custom_plan` it stays at 68-109 ms. That risk is detectable with small data (7 calls in a row, or
`force_generic_plan` and an EXPLAIN check, or an assertion on `pg_proc.proconfig`), as `imc_lock_plan` already does with
20 000 rows. Owner decision (2026-11-05): tests must confirm functionality; load tests exist but not all alike and not in
every round; the machine has no capacity (WSL 3 GB, one heavy run at a time), so the spec's analysis must consider it.

FR numbering continues in the free block: **FR-397..FR-412** (FR-409..412 = item M, compression); acceptance
**AC-453..AC-466** (`grep -rhoE "FR-(39[7-9]|4[0-4][0-9])" specs/ skill/ adapters/ docs/` found only the FR-399
mention of the range note before this extension).
Name check: `grep -rniE "\btier\b|--perf|capacity" skill/scripts/*.py skill/AIDD.md` = no verification-tier concept
exists (`Model tier` of R13 is a different thing; `test_perf_budget.py` measures tool runtime). The new column is `Tier`.

### H. Two test tiers: `functional` (every round) and `perf` (once per spec, before close)

| Code | Requirement |
|---|---|
| FR-397 | Optional Verification column `Tier` with values `functional` (default when empty or absent) or `perf`; any other value is an R10 violation of `check_verification`. Optional line `Perf: required` under `## Verification`. `verification_hash` appends `\|tier:<v>` only when the cell is non-empty and `\nperf:required` only when the line is present, so every existing hash is byte-identical. |
| FR-398 | `aidd verify <spec>` (full, `--tasks`, `--changed`, `--wave`, `--json`) runs only `functional` rows; each `perf` row prints `PERF row n: not run (Tier: perf runs once per spec before close: aidd verify <spec> --perf)`. The recorded `verify_run` keeps the whole-table `verify_hash`, so it still satisfies the close gate for the functional rows. A table with only `perf` rows refuses without `--perf`. |
| FR-399 | `aidd verify <spec> --perf` runs only the `perf` rows (evidence `evidence/verify-perf-<n>.txt`), never reuses or carries a result, and records `perf_verify_run{spec, ok, stable, results, started, verify_hash, code_fp_end, code_scope}`; it never records `verify_run`. Cannot be combined with `--tasks`, `--changed`, `--wave`, `--json` or several specs. No perf row = refuse, nothing executed. |
| FR-400 | Close (`aidd rules close` and `--check`, via `verification_gaps`) requires current perf evidence ONLY when the spec declares `Perf: required`: newest `perf_verify_run` of the spec exists, is ok and stable, its `verify_hash` equals the current table hash, every evidence file has its recorded sha1, and no code edit inside its scope happened after its `started`. Otherwise one R10 gap with the fix `aidd verify <spec> --perf`. `Perf: required` with no `perf` row is an R10 violation. Specs without the line are unaffected. |

### I. Capacity & test budget in the spec analysis

| Code | Requirement |
|---|---|
| FR-401 | Section `## Capacity & test budget` in `spec.md` (template in `templates/spec.md`, mirrored) with lines `RAM: <n> GB\|MB`, `Heavy runs at a time: <n>`, `Round budget: <seconds> s` (sum of functional rows), `Not verified: <what stays unmeasured, or none>`, and a table `\| # \| Tier \| Est. s \| Budget s \| Data scale \| Scale justification \|` with one row per Verification row. |
| FR-402 | The section is REQUIRED (R10 violations in `check_verification`, so `aidd rules check`, approval and close see them) when the spec opts in: a `Tier` column, a `Perf:` line, or the section heading itself. Violations: missing section or line; a Verification row without a budget row; `Est. s` missing or above `Budget s`; the sum of functional `Est. s` above `Round budget`; a `Data scale` of 1 000 or more, or any `perf` row, with an empty justification; a `Tier` that differs from the Verification row's. Legacy specs (no opt-in) get only a non-blocking `check_spec.py` WARNING line. |
| FR-403 | `check_spec.py` prints non-blocking WARNING lines (`capacity_warnings`): no section in a spec with a Verification table; a functional row whose `Est. s` is over half the round budget ("consider `Tier: perf`"); `Heavy runs at a time: 1` together with `Jobs:` > 1. |
| FR-404 | Scale rule (AIDD.md E8/E9 text): the data scale of a row is justified by the risk, not by production volume. A behaviour proven linear with its plan shown at a small N (EXPLAIN without Seq Scan on the hot table, custom/generic plan checked) does not require 200 000 rows; what is not measured is declared under `Not verified:` and reported `not-verified`, never claimed. |

### J. Light seeding

| Code | Requirement |
|---|---|
| FR-405 | Guide + template `templates/perf/seed-generate-series.sql`: seed volume with set-based SQL (`INSERT ... SELECT ... FROM generate_series(1, :n)`), bypassing the business logic per document, inside one transaction, followed by `ANALYZE`; optional reuse of the seeded database as a template (`CREATE DATABASE ... TEMPLATE`) only through the project's DB-pass tool (one-test-DB rule, E8 (d')). The per-document business path stays for the functional tier with minimal data. |

### K. Functional test of a performance risk without volume

| Code | Requirement |
|---|---|
| FR-406 | Template `templates/perf/plan-risk.test.sql` (pgTAP): (1) the hot function declares `plan_cache_mode=force_custom_plan` in `pg_proc.proconfig`, or (2) the function is called N > 5 times in a row (generic-plan switch happens at the 6th execution) and the last call stays within a factor of the first; (3) under `SET plan_cache_mode = force_generic_plan` the EXPLAIN of the hot query has no `Seq Scan` on the hot table; (4) at small scale (`SET enable_seqscan = off` is NOT used) the plan uses the expected index. Each check is a functional-tier row (seconds, not minutes). |

### L. `aidd sqlcheck` and psql metacommands

| Code | Requirement |
|---|---|
| FR-407 | [fact] `pglast` cannot parse psql metacommands (`\set`, `\gset`, `\i`, `\if`, ...) nor `:var` / `:'var'` interpolation; pgTAP files that use them failed as "does not compile". `aidd_sqlcheck.py` (postgres adapter only) blanks backslash metacommand lines, turns a trailing `\gset`/`\gexec`/`\g` into `;`, and, only in files that contain a metacommand, replaces `:'v'` with `'v'`, `:"v"` with `"v"` and `:v` with `0`; line numbers are kept. Prints `note: <file>: psql metacommands ignored (n lines)`. `--cmd` checkers receive the file unchanged. |
| FR-408 | AIDD.md E8 states the limitation: the static compile skips psql metacommands; what they do (variables, includes, conditionals) is checked only by the DB pass. |

### M. AIDD compresses what it embeds (owner order 2026-11-05)

**Measured (2026-11-05, this branch).** `docs/graphs/explorer.html` of the AIDD repo: 10 817 300 bytes with the graph
as plain JSON in `<script id="graph-data">` (gzip -9: 626 KB); regenerated with compression: 903 078 bytes (7 397
nodes; base64 adds ~33 % over gzip). It was TRACKED in git (commit `b559962`). Review page: the compact page (default
since 008) does NOT embed the source files; it embeds extracted items (cap `MAX_ITEMS` = 2000) as rendered HTML plus a
data blob. b1SycLink F36 (1 027 224 source chars) -> 378 921-byte page in 0.2 s; F38 (699 456) -> 340 685 bytes (data
blob 135 776); `--full` page F36 1 451 196 bytes. So the 400 000-char per-file cap [fact: spec 007 FR-202, written
when the page embedded whole files] protected nothing on the compact page and only forced F38 to split tasks.md.
With the data blob compressed: F38 page 342 235 -> 236 049 bytes; a synthetic 1 MB tasks.md -> 102 999 bytes.

| Code | Requirement |
|---|---|
| FR-409 | Shared helper `skill/scripts/aidd_embed.py`: `pack(text)` = base64(gzip level 9, mtime 0) (deterministic), `unpack` its exact inverse (ValueError on a damaged payload), `JS_INFLATE` = the browser decoder (`DecompressionStream('gzip')`). `graph_explorer.py` embeds the graph as `<script id="graph-data" type="application/gzip+base64">` by default and decodes it in an async start-up; without `DecompressionStream` (or on a damaged payload) the page shows a readable alert naming the browsers that work and `--no-compress`; `--no-compress` writes the old plain JSON; `embedded_payload(page)` reads either form. |
| FR-410 | `aidd review` compact page: the `aidd-data` blob keeps the plain header keys (`spec`, `tasks_hash`, `sources_digest`, `tasks_hash8`, `generated`, `picker_id`, `format`, read by the folder check and old readers) plus `encoding: gzip+base64` and `gz` (the whole blob). The page script (still ONE constant script, so the CSP sha256 still covers it) decodes `gz` before wiring; on failure it shows a readable message, leaves the rendered content visible and wires nothing (nothing can be checked or saved by mistake). The rendered body stays plain HTML: compressing it would need HTML-string injection, which FR-202 forbids (data reaches the page through textContent only). `_page_blob` decodes the compressed blob, so carry-over, idempotence and `--check` read both forms. `--no-compress` keeps the plain blob. `--full` keeps the plain blob. |
| FR-411 | `MAX_REVIEW_SOURCE_CHARS` = 2 000 000 per file (below the rules parser's `MAX_CHARS` = 2 MiB, which stays the real ceiling), `WARN_REVIEW_SOURCE_CHARS` = 1 500 000; `check_spec.py` reads both from `aidd_review` (no duplicated literal). Batch files `tasks-<name>.md` stay supported (combined hash unchanged), as an option, not an obligation. AIDD.md/SKILL.md E10(f) and the Step 4 review paragraph state the measured limit. |
| FR-412 | Generated files are never versioned: `templates/gitignore.aidd` (explorer pages, `specs/index.toon`, `specs/*/review.html`, `.aidd/evidence/`, `.aidd/jobs/`, `.aidd/sqlcheck-cache.json`, `graphify-out/`) is appended (missing lines only, idempotent, never untracking) to the project `.gitignore` by `aidd init` and `aidd install` through `aidd_gitignore.py`; the AIDD repo's own `.gitignore` gets the same lines and `docs/graphs/explorer.html` is untracked (`git rm --cached`, file kept on disk). |

**Acceptance (M).**
| Code | Scenario | Command | Expected |
|---|---|---|---|
| AC-463 | `pack`/`unpack` round trip of '', unicode, `</script>`, 1 MB, JSON; same input = same bytes; damaged payload; browser decoder in node | `python -m unittest tests.test_embed_compression -v` | equal byte for byte; ValueError; node output identical |
| AC-464 | spec with a 1 MB tasks.md: compact page builds (no split), compressed blob == plain blob, `_page_blob` decodes it, page smaller | same | pass |
| AC-465 | explorer default compressed, `--no-compress` plain, both payloads equal; browser smoke | `python -m pytest tests/test_graph_explorer.py tests/test_explorer_controls_browser.py` | pass |
| AC-466 | `.gitignore` helper idempotent, keeps lines, dry run writes nothing; repo ignores the generated pages | `python -m unittest tests.test_embed_compression -v` | pass |

| Task | Item | Target file(s) | Wave | Deps | Agent min | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-18 | M | `skill/scripts/aidd_embed.py`, `skill/scripts/graph_explorer.py`, `skill/scripts/aidd_review.py`, `skill/templates/review.html`, `skill/scripts/aidd_gitignore.py`, `skill/templates/gitignore.aidd`, `aidd/cli.py`, `skill/scripts/install_host.py`, `tests/test_embed_compression.py` (+ adapted fixtures in `tests/test_aidd_review.py`, `tests/test_b10_b11_b6.py`, `tests/test_aidd_status.py`, `tests/test_tasks_batch_coverage.py`, `tests/test_graph_explorer.py`, `tests/test_unified_explorer.py`) | 1 | none | 60 | compressing the rendered review body; `--full` page; untracking files in client projects |

**Acceptance.**
| Code | Scenario | Command | Expected |
|---|---|---|---|
| AC-453 | table with rows 1 functional, 2 perf; `cmd_verify` | `python -m unittest tests.test_verify_tiers -v` | only row 1 runs, `PERF row 2` printed, `verify_run` recorded |
| AC-454 | same, `--perf` | same | only row 2 runs, `perf_verify_run` recorded, no `verify_run` |
| AC-455 | `--perf` with `--tasks` / no perf row | same | refused, nothing executed |
| AC-456 | `Perf: required`, no / stale / valid `perf_verify_run` | same | R10 gap / gap / no gap; without the line: never a gap |
| AC-457 | hash of tables without `Tier` and without `Perf:` | same + `tests.test_aidd_rules` | equal to the pre-change hash |
| AC-458 | capacity: missing section with Tier, est > budget, sum > round, unjustified 38 000 seed, tier mismatch | `python -m unittest tests.test_capacity_budget -v` | one violation each; a complete section: none |
| AC-459 | legacy spec without opt-in | same | no violation; one warning |
| AC-460 | pgTAP file with `\set n 7`, `select :n;`, `select 1 \gset` | `python -m unittest tests.test_aidd_sqlcheck -v` | compiles (when `pglast` is installed); helper output keeps line count |
| AC-461 | templates exist and mirror | `python -m unittest tests.test_dot_aidd_mirror -v` | exit 0 |
| AC-462 | owner-run measurement of the light seed in b1SycLink (slot 2) | `python eDoc/tools/db_verify.py --slot 2 ...` | figure reported, or `not-verified` declared |

**Tasks.**
| Task | Item | Target file(s) | Wave | Deps | Agent min | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-13 | H | `skill/scripts/aidd_rules.py`, `skill/scripts/aidd_status.py`, `tests/test_verify_tiers.py` | 1 | none | 60 | carry/reuse of perf rows |
| T-14 | I | `skill/scripts/aidd_rules.py`, `skill/scripts/check_spec.py`, `skill/templates/spec.md`, `tests/test_capacity_budget.py` | 1 | T-13 (same owner as T-13 for aidd_rules.py) | 45 | estimating costs automatically |
| T-15 | J, K | `skill/templates/perf/seed-generate-series.sql`, `skill/templates/perf/plan-risk.test.sql`, `skill/templates/perf/README.md` | 1 | none | 25 | running them against a database |
| T-16 | L | `skill/scripts/aidd_sqlcheck.py`, `tests/test_aidd_sqlcheck.py` | 1 | none | 20 | executing metacommands |
| T-17 | text | `skill/AIDD.md`, `skill/SKILL.md`, `adapters/dot-aidd/CORE.md`, mirrors under `adapters/dot-aidd/` (copied by script) | 2 | T-13..T-16 | 20 | rewording other sections |

Status of this extension: implemented on branch `am10/test-tiers-capacity` of the AIDD repo (not installed, not pushed);
see the branch commit for the file list. AC-462 is `not-verified` unless the owner runs it.

### N. `aidd sync`: installed bundle = source, checked and applied by a tool (2026-11-05)

**Measured (2026-11-05).** Syncing the AIDD source with what is installed (profile `~/.claude/skills/aidd`, each
project's `.aidd/`) needed an ad hoc script every time. A home-made comparator using relative paths after `cd` reported
116 false "differs" with 0 real differences. `tools/aidd_selective_update.py` accepts only `AIDD.md`, `SKILL.md`,
`hooks/*.py`, `scripts/*.py`, `templates/navigator.html` and requires `--baseline` for an existing changed file, so
templates (`templates/**`), `CORE.md` and similar were copied apart by hand. A fixed file list omitted new files
(`aidd_coverage.py`, `unified_graph.py`, `alias_graph.py`) and would have left mixed versions. Extends H0/FR-370 (which
asked for a report only) with a reusable command. Numbering: next free block FR-413..FR-418, AC-467..AC-474, T-19
(`grep -rhoE "FR-41[3-9]|AC-46[7-9]|AC-47[0-9]" specs/ skill/ adapters/ docs/` = none before this item).

| Code | Requirement |
|---|---|
| FR-413 | `aidd sync` (CLI passthrough to `skill/scripts/aidd_sync.py`, mirrored byte-identical in `adapters/dot-aidd/scripts/`). The CLI injects `--source` = the checkout/wheel it runs from when not given, and runs the script from `<source>/skill/scripts/` first, then its own checkout, then the installed scripts, so `aidd sync --source <repo>` works when the installed CLI predates the command. |
| FR-414 | `--check [--target skill\|<.aidd folder or project root>]... [--profile DIR] [--json]` compares the WHOLE tree, never a fixed list: `skill` (default) = `<source>/skill/` vs `$AIDD_HOME` or `~/.claude/skills/aidd`; a path = `<source>/adapters/dot-aidd/` vs that `.aidd`. Paths are resolved to absolute once at start-up and the working directory is never changed. Equality = equal bytes after CRLF->LF normalisation. Never compared or reported: `evidence`, `memory`, `active_spec`, `gate_spec`, `calibration.toon`, `graphs`, `sqlcheck-cache.json`, `__pycache__`, `*.bak`, `*.pyc`. Output per target: `missing`, `differs`, `local-only` (informative, never deleted); exit 0 when no missing/differs, 1 otherwise, 2 on usage/refusal. |
| FR-415 | `--apply` is a dry run (plan printed, nothing written) unless `--yes`; `--dry-run` always wins. With `--yes`: a backup session `<--backup-dir or ~/.aidd-sync/backups>/<YYYYmmdd-HHMMSS>-<pid>/` outside every target (refused otherwise) holds a hash-verified copy of every file to be replaced. |
| FR-416 | Files `aidd_selective_update` accepts (list derived from the diff, never fixed; parent folder present) go through one `make_plan`/`apply_transaction` with `--baseline` = the backup; every other file (templates/**, `CORE.md`, `extensions/**`, new folders) is copied directly (temp file + replace) and its sha256 verified. The tool is loaded from `<source>/tools/aidd_selective_update.py`; absent = apply refused. |
| FR-417 | `sync-journal.json` in the session records state (`prepared`/`applying`/`committed`/`rolled_back`), the selective journal and, per direct copy, before/after sha256, backup and created folders. Any failure rolls back everything written (direct copies + `recover_transaction`). `aidd sync --recover <session>` validates every file first (a file edited after the sync = refusal, nothing restored), restores, removes created empty folders; idempotent. |
| FR-418 | `--apply --yes` ends by running `--check`; its exit code is the command's (must be 0; otherwise it prints the `--recover` command). AIDD.md E11 states the rule: no ad hoc sync scripts or fixed lists. |

**Acceptance (N).**
| Code | Scenario | Command | Expected |
|---|---|---|---|
| AC-467 | identical trees; one file missing; one file differs | `python -m unittest tests.test_aidd_sync -v` | exit 0; exit 1 with the path under `missing`; exit 1 under `differs` |
| AC-468 | CRLF-only difference | same | exit 0 |
| AC-469 | local state (evidence, memory, graphs, active_spec, gate_spec, calibration.toon, sqlcheck-cache.json, __pycache__, *.bak) ignored; extra file listed as `local-only` | same | exit 0, only the extra file listed |
| AC-470 | relative `--source`/`--target` from another cwd, and a later `chdir` | same | exit 0, `differs=0` (no false differences) |
| AC-471 | apply in a temp tree: dry run writes nothing; `--yes` updates selective + direct files, local state untouched, check 0; `--recover` restores the exact bytes and removes created folders; recover twice = no-op | same | pass |
| AC-472 | template-only change copied and verified; simulated write failure rolls everything back; foreign edit after sync blocks recover; backup inside a target refused | same | pass |
| AC-473 | `python -m aidd.cli sync --check --source <tmp>` from a CLI whose installed profile lacks the script | same | runs the checkout's script; exit 0 / 1 |
| AC-474 | mirror byte-identical | `python -m unittest tests.test_dot_aidd_mirror -v` | exit 0 |

| Task | Item | Target file(s) | Wave | Deps | Agent min | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-19 | N | `skill/scripts/aidd_sync.py`, `adapters/dot-aidd/scripts/aidd_sync.py` (mirror, copied by script), `aidd/cli.py`, `skill/AIDD.md` + `adapters/dot-aidd/AIDD.md` (E11), `tests/test_aidd_sync.py`, `tests/test_dot_aidd_mirror.py` | 1 | none | 90 | installing into `~/.claude` or any project; deleting `local-only` files; updating the pip-installed package (`cli.py`/`RECORD`, see `aidd_selective_update.py package-plan`) |

Status of item N: implemented on branch `am10/aidd-sync` of the AIDD repo (not installed, not pushed).

### O. `aidd verify --round`: one verification pass for several specs (2026-11-05)

**Measured (2026-11-05, b1SycLink).** 8 open specs (F21, F36, F37, F38, F40, F41, F42, F56) repeat identical rows
(`python eDoc/tools/db_verify.py --psql "docker exec -i supabase_db_edoc psql -U postgres" --tap --plpgsql-check ...`
full or `--only-tests`, `node .../vitest.mjs run --root eDoc/web <path>`, `npm test --prefix eDoc/web`, tsc,
Playwright); `aidd verify` runs each row per spec, so a full round costs more than 100 min. Cross-spec reuse is OFF
(`aidd_status.py`: `round_on = False`, commit 1cef7ed) because the old `ROUND-REUSED` cache had no database/environment
identity and could give a false PASS; the project works around it by hand (heavy row in ONE designated spec). Owner
order: grouping specs into ONE verification pass is part of the method (Step 6), not a loose option. Design base:
`batch-staging/reuse-front1` (contract store, kept as is: this item is in-invocation only, no cache). Numbering: next
free block FR-419..FR-426, AC-475..AC-484, T-20 of this amendment.

| Code | Requirement |
|---|---|
| FR-419 | `aidd verify --round <spec>...` and `aidd verify --all-open --round` (open = `aidd_evidence.open_specs` with a folder) in `skill/scripts/aidd_round.py` (mirrored byte-identical). Accepts only `--dry-run` and `--full`; `--tasks`, `--changed`, `--wave`, `--perf`, `--json`, `--bail` are refused with nothing executed. |
| FR-420 | Collect the Verification rows of every spec, excluding `Tier: perf` (one note per spec); normalise each command (tokens split on whitespace outside quotes, joined by one space; a double-quoted plain word loses its quotes, single quotes too outside Windows; spaces inside quotes stay significant) and group identical commands per project root. Each row keeps its own Expected. |
| FR-421 | Execute each group ONCE before any bookkeeping: in series; a heavy runner (db_verify, psql, pg_prove, docker, supabase, `--tap`, vitest, Playwright, `npm test`, tsc, npx, pytest, ...) always alone; light groups in parallel only up to the SMALLEST `Jobs:` of the round's specs (default 1; `AIDD_VERIFY_JOBS` overrides). A row with a lint problem is never executed. |
| FR-422 | Each spec records its OWN `verify_run` (same event, rows, evidence paths `evidence/verify-<n>.txt`, verify hash) through `cmd_verify(..., round_shared, round_start)`, which never runs a row in that mode; its code state and worktree fingerprint are the ones taken BEFORE the round, so a code change during the round makes that spec unstable. Same-spec, contract-store and wave reuse are bypassed and nothing is stored. |
| FR-423 | Evidence of every row executed in the round: line 1 the normal header `# <cmd> \| exit <code> \| <ts>`, line 2 `ROUND-SHARED: ejecutado una vez por <spec> fila <n>, huella <hash>, <ISO date>`, then the output. Output checks (zero tests, too short) run on the text WITHOUT that line. The result carries `round_shared{source_spec, source_n, fingerprint, ts}`; only the source row keeps its seconds. |
| FR-424 | Safety. A group of 2+ rows is shared only when the environment fingerprint is identical at the start and at the end of its execution: content fingerprint (`code_state` + `fingerprint_of`) of the union of the group specs' `Scope:` and rows' `Inputs` (the whole code tree outside specs/, .aidd/ and ignored files when a spec has no Scope), excluding the union of `Generated:`; `docker inspect` id + start time of every `docker exec <container>` in the command; sha256 of the stdout of each spec's optional `Round-identity: <command>` line; sha256 of the values of the variables in `Round-vars:` and in the rows' `Environment` `vars=`. Changed or unavailable = `ROUND-INVALIDATED`: every consumer row (the source too) FAILS with that reason and nothing is shared. A failure is never a pass: each row's Expected is evaluated on the shared exit code and output. |
| FR-425 | Methodology (owner order 2026-11-05): `aidd status` (no spec argument) and `aidd next` print one `round:` line with the command and the executions saved when 2+ open specs with pending verification (no passing `verify_run` of the current table) share identical rows; a single `aidd verify <spec>` prints the round command when other open specs share rows with it. Never executes a row, never raises. |
| FR-426 | `--dry-run` prints the plan (specs, functional rows, executions, executions saved, per-group seconds from each spec's previous `verify_run` and the estimated seconds saved) and executes and records nothing. AIDD.md E12 + Step 6 close sequence, SKILL.md E12, `adapters/dot-aidd/CORE.md` §5 and `adapters/AGENTS.md.snippet` state the rule: plan a round, freeze, ONE pass, one round of auditors per spec; spec by spec only with a single spec ready. |

**Acceptance (O).**
| Code | Scenario | Command | Expected |
|---|---|---|---|
| AC-475 | two specs, identical row with different spacing/quotes and different Expected | `python -m unittest tests.test_verify_round -v` | 1 execution for 2 rows; 2 `verify_run`, both PASS; B's evidence line 2 `ROUND-SHARED: ejecutado una vez por A fila V-1, huella <16 hex>, ...` |
| AC-476 | different command (or different text inside quotes) | same | not grouped; one execution each |
| AC-477 | the command edits a file in scope during its execution | same | `INVALIDATED`; every row FAILS with `ROUND-INVALIDATED`; exit 1 |
| AC-478 | shared command exits 1; one spec expects `contains: FAILED` | same | one execution; both rows FAIL |
| AC-479 | `--dry-run` with a previous verify_run of 42 s | same | no execution, no event, no evidence folder; `1 execution(s) saved (~42 s` |
| AC-480 | three rows timestamping start/end, one spec without `Jobs:` | same | intervals never overlap |
| AC-481 | a `Tier: perf` row | same | not executed; `excluded` note |
| AC-482 | `--round` with `--tasks`/`--perf`/`--wave`/`--json`/`--bail`; `--all-open` | same | refused, nothing run; `--all-open` plans the open specs that have a folder |
| AC-483 | 2 open specs sharing a row: `suggestion`, `aidd status`, `aidd verify A`; no shared row or one open spec | same | round line with `aidd verify --round A B` and `1 saved`; the warning names B; '' otherwise |
| AC-484 | regression of the modules touched | `python -m unittest tests.test_verify_tiers tests.test_aidd_status tests.test_aidd_rules_r10 tests.test_check_spec tests.test_cli_rules tests.test_dot_aidd_mirror tests.test_aidd_next tests.test_contract_store tests.test_verify_git_contract tests.test_wave_verification tests.test_verify_regressions tests.test_aidd_task_verify` | exit 0 (pre-existing failures, if any, listed in the branch report) |

| Task | Item | Target file(s) | Wave | Deps | Agent min | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-20 | O | `skill/scripts/aidd_round.py` (new), `skill/scripts/aidd_status.py`, `skill/scripts/aidd_next.py`, mirrors in `adapters/dot-aidd/scripts/` (copied by script), `skill/AIDD.md` + `adapters/dot-aidd/AIDD.md` (E12, Step 6), `skill/SKILL.md` (E12), `adapters/dot-aidd/CORE.md`, `adapters/AGENTS.md.snippet`, `tests/test_verify_round.py`, `tests/test_dot_aidd_mirror.py` | 1 | none | 120 | re-enabling `round_on`; a cross-invocation cache; the `aidd lock heavy` inter-process lock (item F); same-spec reuse inside a round; installing into `~/.claude` or a project |

Status of item O: implemented on branch `am10/verify-round` of the AIDD repo (not installed, not pushed).

---

### P. Same-spec reuse inside `aidd verify --round` (2026-11-06)

**Measured (2026-11-06, b1SycLink).** `aidd verify --all-open --round` over 9 open specs executed EVERY row (105
groups, ~2600 s) although several specs had a recent PASS `verify_run` on unchanged Scope, files and environment.
Item O left it explicitly out of scope ("same-spec reuse inside a round"; FR-422 bypassed every reuse path).

**Facts.**
- [fact] A plain `aidd verify <spec>` reuses a previous PASS only through the offline hermetic contract
  (`_reusable_input_rows`: `Reuse: hermetic` + `Inputs` + `Environment: contract:offline;...`, never DB/docker
  runners); the legacy code-fingerprint reuse (`_reusable_rows`) exists but is not wired (`reuse = {}` since 1cef7ed,
  "a file fingerprint alone does not describe a database"). So "a single verify reuses unchanged rows" holds only for
  hermetic Python rows.
- [fact] Item O already computes, for a round, the observable environment a file fingerprint does not cover:
  `docker exec` container id + start time, `Round-identity:` output, declared variables (`aidd_round.env_fingerprint`).
  Item P reuses that identity per row (`env_id`) so a DB row is reused only on the same container and declared
  identity, not on files alone.

| Code | Requirement |
|---|---|
| FR-427 | `aidd verify --round` / `--all-open --round` decide, per spec, BEFORE grouping and on the code state taken at the start of the round (the same state the per-spec stability check uses), which functional rows are reused from that spec's latest `verify_run`; reused rows are not executed and never enter a group. |
| FR-428 | A row is reused only when ALL hold (fail closed on any doubt): previous run `stable`; `code_algorithm` current and `code_fp_end` present; `Scope:` equal to the recorded `code_scope`; the code fingerprint of that scope now (excluding the run's `code_generated` + `code_changed`) equals `code_fp_end`; same row `#`, same `normalize_command`, same Expected; previous result `ok` and exit 0; no lint problem today; same `Inputs` declaration, `input_algorithm` and `row_input_fingerprint`; environment identity (FR-430) equal; evidence inside the spec folder, full sha1 equal, `_cached_pass_valid` true; the row is not `Reuse: never`. `--full` reuses nothing. `Tier: perf` rows stay out of the round (FR-420). |
| FR-429 | A reused row is recorded in that spec's own `verify_run` with `reused: true`, `reuse_kind: round-same-spec`, `reused_from{spec, n, date, code_fp, verify_hash, secs}`, `secs: 0`; its evidence keeps the original line 1 and gets line 2 `REUSED: PASS del verify_run de <spec> fila <n> del <ISO date>, huella <code fp>, verify hash <hash>; Scope, Inputs, codigo y entorno sin cambios (no ejecutado en esta ronda)` (a previous REUSED line is replaced; a chain keeps the origin of the run that really executed the row). It never carries `round_shared`. Each spec still records ONE complete `verify_run` (executed + reused rows); stability compares the state before the round with the state after it, so R7/R10/close work unchanged. |
| FR-430 | Environment identity `env_id` of a row: '' when the row names no `docker exec` container and its spec declares no `Round-identity:` and no variables (`Round-vars:`, `vars=`); else 16 hex of the container identities, identity-command outputs and variable values; None (not reusable) when one is unavailable. Recorded on every executed row by a round and by a plain full `aidd verify <spec>` only when equal before and after the run; a non-empty current `env_id` must equal the recorded one. |
| FR-431 | `--dry-run` prints per spec `reuse <spec>: k row(s) reused, m to execute`, one line per row (`REUSED <n>: PASS of <date>, huella <fp>, verify hash <h> (~s saved)` or `run <n>: <reason>`), then the plan of the remaining rows and `estimated savings versus running every row: ~S s (k reused row(s) ~R s + g grouped execution(s) ~G s)`; it executes no row and records nothing (only the read-only identity probes run). The round summary adds `<k> row(s) REUSED from the previous verify_run of their own spec`. |
| FR-432 | Row value `Reuse: never` (existing `Reuse` column, no new parser) opts a row out of this reuse; documented in AIDD.md E12, SKILL.md E12 and the AGENTS snippet. `verification_hash` is unchanged for tables that do not add it. |

**Acceptance (P).**
| Code | Scenario | Command | Expected |
|---|---|---|---|
| AC-485 | second round with nothing changed | `python -m unittest tests.test_verify_round_reuse -v` | 0 executions; 2 rows REUSED; complete PASS stable verify_run |
| AC-486 | a file in Scope changed | same | the row runs; reason `code in Scope changed` |
| AC-487 | previous result FAIL | same | the failed row runs again; the passed one is reused |
| AC-488 | new row / changed command | same | the new or changed row runs; the others are reused |
| AC-489 | `--full` | same | every row runs; nothing reused |
| AC-490 | evidence of a reused row; reused row next to an identical row of another spec that must run | same | line 2 `REUSED: PASS del verify_run de A fila V-1 del ...`; the reused row has no `round_shared`; the other spec runs alone |
| AC-491 | `--dry-run` after a PASS | same | no execution, no event, evidence unchanged; per-spec reuse lines and the savings line |
| AC-492 | code fingerprint not computable | same | the row runs (`fail closed`) |
| AC-493 | `Round-identity:` output changed / unavailable | same | the row runs |
| AC-494 | reused and executed rows in the same spec | same | one verify_run with both kinds; overall result from all rows |
| AC-495 | a plain `aidd verify A` feeds the next round | same | `env_id` recorded; the round reuses the row |
| AC-496 | regression | `python -m unittest tests.test_verify_round tests.test_dot_aidd_mirror tests.test_cli_rules tests.test_aidd_status tests.test_aidd_rules_r10 tests.test_verify_tiers` (module by module) | exit 0 |

| Task | Item | Target file(s) | Wave | Deps | Agent min | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-21 | P | `skill/scripts/aidd_round.py`, `skill/scripts/aidd_status.py` (`cmd_verify(round_reused, round_env)`, `env_id` on plain runs), mirrors in `adapters/dot-aidd/scripts/` (copied by script), `skill/AIDD.md` + `adapters/dot-aidd/AIDD.md` (E12), `skill/SKILL.md` (E12), `adapters/AGENTS.md.snippet`, `tests/test_verify_round_reuse.py` | 1 | T-20 | 120 | same-spec reuse in a plain `aidd verify <spec>` (still only the hermetic contract); cross-spec reuse across invocations; re-enabling `round_on`; installing into `~/.claude` or a project |

Status of item P: implemented on branch `am10/round-reuse` of the AIDD repo (not installed, not pushed).

---

### Q. Session lessons: refusals that say what they compared, artifacts out of the fingerprint (2026-11-06)

**Measured (2026-11-06, b1SycLink).** (1) `aidd verify --round` refused with "cannot fingerprint the verification inputs
of <spec>; nothing was executed." because 289 MB of Playwright captures (`eDoc/web/e2e/__screens__`, declared
`Generated:`) spent the 8 s budget, and unlike plain `aidd verify` the message did not name `AIDD_FINGERPRINT_BUDGET`.
(2) `aidd rules close` refused four times ("no recorded user answer \"Yes, close\"") because the question lacked the
`[spec:<id>]` tag that the code requires (`must_contain`), and the message did not name it. (3) A page-route
`aidd rules approve` was refused repeatedly ("review.md is complete; the owner must confirm") after the owner clicked and
typed `approve [tasks:..]`; the probable cause (consent older than review.md, which the open page autosaves) was not
visible. (4) Any text edit of a `tasks-<batch>.md` voids the approval (the hash covers batches), but status said only
"tasks changed after approval". (5) `aidd pending` read only tasks.md and called a task done because its Target
(`router.tsx`, shared) existed. (6) "the verification rewrote files" did not say who wrote them. (7) The first round
after installing reused no DB row, silently (no previous `env_id`). (8) A row with `--slot 1` reset the seeded
`edoc_verify_w1` that another spec's perf row needed.

| Code | Requirement |
|---|---|
| FR-433 | `aidd_evidence.code_state(..., skip=globs)` drops files matching `skip` BEFORE hashing (git and mtime modes); paths with a `node_modules` or `test-results` segment and `.aidd/evidence/**` are always dropped. `aidd verify` and `aidd verify --round` pass the spec's `Generated:` as `skip`; fingerprints computed with `exclude=` the same globs are unchanged. Both commands print ONE refusal text (`aidd_status.fingerprint_refusal`) naming `Scope:`, `Generated:` and `AIDD_FINGERPRINT_BUDGET=<seconds>` (default and current value); a `--dry-run` prints it as a note. |
| FR-434 | Declared `Generated:` outputs written during a run are still reported (`rewritten by the verification and declared Generated:`) by mtime only (stat, walk limited to each glob's literal prefix, 2 s cap). |
| FR-435 | A refused `aidd rules close` (and `close --check`) names the exact tag `[spec:<id>]`, the question shape and the option `Yes, close`, and the typed fallback `Yes, close [spec:<id>]`. |
| FR-436 | It also prints `Compared against: qa-audit.md modified <time>` and `Last close question seen: "<text>" at <time>, answer "<a>"` (any session, preferring one naming the spec) with the reason it does not count (missing tag, older than qa-audit.md, other label). Diagnostic only: never consent. |
| FR-437 | A refused page-route `aidd rules approve` prints `since = max(tasks <t>, review.md <t>)`, the newest tagged consent found at any time (answer or typed prompt, with time) and why it does not count (older than review.md: the open page autosaved; older than tasks), and names the `Aprobar con resumen` alternative. |
| FR-438 | When a verification sees files change, each one gets a `who:` line: the row whose wall-clock execution window holds its mtime (stronger when the command names it; suggests the `Generated:` glob), or `another process or agent` when no row was running (then the advice is to re-run, NOT to declare it), or not determinable. |
| FR-439 | Reuse reason `environment identity not recorded by the previous verify_run (no env_id)` is distinct from `changed`; `--round --dry-run` and the round summary end with the list of such rows and the note that the first round after installing does not reuse database/docker rows. |
| FR-440 | New `approved` events record `segments` (sha1[:12] of the approval projection of tasks.md and each batch file; never part of `approval_hash`). `aidd status` (`approval VOID ✘ (...: <file> (modified <time>))`) and R6 name the changed file; for older events, the task files modified after the approval, by mtime. |
| FR-441 | `aidd pending` reads tasks.md + `tasks-*.md` and reports `unverified` (never `done`) a task whose existing Target is cited by another task, whose Status cell is not done, or that git shows existed before the spec's tasks.md; JSON adds `unverified`, `unverified_why`, `files`. |
| FR-442 | `check_spec.py` prints a WARNING (never a gap) when a row of the spec runs `--slot N` while another spec declares `Protected-slot: N` under `## Verification` (opt-in) or has a `Tier: perf` row with `--slot N` / `_wN`. |

**Acceptance (Q).**
| Code | Scenario | Command | Expected |
|---|---|---|---|
| AC-497 | round refusal names the budget like plain verify | `python -m unittest tests.test_verify_round -v` | both texts contain `AIDD_FINGERPRINT_BUDGET=<seconds>` and `Generated:` |
| AC-498 | 12 screenshots over the file cap: refused without `Generated:`, PASS with it; fingerprint equal | same | rc 1 then rc 0; equal `fingerprint_of` |
| AC-499 | git mode: skipped and artifact files never reach `git hash-object` | `python -m unittest tests.test_session_lessons -v` | only code files hashed |
| AC-500 | close refusal with an untagged question | `python -m unittest tests.test_aidd_status -v` | tag, option, last question, answer, qa-audit time; `--check` too |
| AC-501 | close question older than qa-audit.md | same | `it is older than qa-audit.md` |
| AC-502 | approve consent older than an autosaved review.md | same | `since = max(`, `Last consent found`, `older than review.md`, `Aprobar con resumen` |
| AC-503 | declared Generated output still reported | same | `declared Generated` on a PASS run |
| AC-504 | rewritten file attributed to its row / another process / unknown | `tests.test_session_lessons`, `tests.test_verify_round` | `while row V-2 ran`; `another process or agent` |
| AC-505 | rows without previous env_id listed, then reused | `python -m unittest tests.test_verify_round_reuse -v` | list + first-round note; next round reuses, no note |
| AC-506 | void approval names the batch file | `tests.test_session_lessons` | per-file hash and mtime fallback; status line |
| AC-507 | pending reads batches, shared targets unverified | same | done T-01, pending T-11, unverified T-02,T-10,T-12 |
| AC-508 | slot warning | same | perf heuristic + `Protected-slot`; check_spec WARNING |

| Task | Item | Target file(s) | Wave | Deps | Agent min | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-22 | Q | `skill/scripts/aidd_evidence.py`, `skill/scripts/aidd_status.py`, `skill/scripts/aidd_round.py`, `skill/scripts/aidd_rules.py`, `skill/scripts/aidd_pending.py`, `skill/scripts/check_spec.py`, mirrors in `adapters/dot-aidd/scripts/` (copied by script), `skill/AIDD.md` + `adapters/dot-aidd/AIDD.md` (E13), `skill/SKILL.md` (E13), `tests/test_session_lessons.py`, `tests/test_verify_round.py`, `tests/test_verify_round_reuse.py`, `tests/test_aidd_status.py` | 1 | T-21 | 180 | a preflight command for slots; a process-level writer trace (only mtime vs row windows); changing `approval_hash`; installing into `~/.claude` or a project |

Status of item Q: implemented on branch `am10/session-lessons` of the AIDD repo (not installed, not pushed).

---

## Cross-cutting acceptance

| Code | Requirement | Command | Expected |
|---|---|---|---|
| AC-451 | No existing approval is voided: `approval_hash` and `verification_hash` of every fixture spec and of the copied b1SycLink samples are identical to the values pinned BEFORE the first task | `python -m unittest tests.test_am10_hash_compat -v` | exit 0 |
| AC-452 | Mirrors byte-identical | `python -m unittest tests.test_dot_aidd_mirror -v` | exit 0 |

## Verification

| # | Command | Expected | Covers |
|---|---|---|---|
| 1 | `python -m unittest tests.test_cli_rules tests.test_dot_aidd_mirror` | exit 0 | FR-375, FR-380, FR-390, FR-396 (text) |
| 2 | `python -m unittest tests.test_am10_hash_compat` | exit 0 | FR-379, AC-451 |
| 3 | `python -m unittest tests.test_aidd_preflight tests.test_verify_rows tests.test_verify_env tests.test_aidd_sqlcheck tests.test_verify_global tests.test_tasks_archive tests.test_aidd_lock tests.test_aidd_red_visual tests.test_aidd_rules tests.test_stop_gate` | exit 0 | FR-371..FR-395 |

(Rows 2 and 3 name test modules created by the tasks below; `aidd preflight` P12 would report them as planned.)

---

## Tasks (Gemini-ready; tests first; one PR each)

Rules for every task: TOOLS FIRST (bulk or mechanical edits with a script: mapping, dry-run, apply, post-check; never by
hand) — repeat this in every subagent brief. DB rule: never create databases by hand; `db_verify.py` is the only
creator (up to 3 slots) — repeat in every brief. Write the test first, run it and save the RED with `aidd red ... --task
T-nn`; then implement; then the task's verification. Every Python change in `skill/` is copied byte-identical to
`adapters/dot-aidd/` by the repo's generator (`python skill/scripts/generate_adapters.py`), never by hand. End your run
after your final report (FR-396).

| Task | Item | Target file(s) | Wave | Deps | Agent min | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-00 | H0 | `tools/aidd_bundle_diff.py` (new, report only) | 0 | none | 30 | applying patches, committing |
| T-01 | AC-451 | `tests/test_am10_hash_compat.py`, `tests/fixtures/am10/*` | 0 | T-00 | 40 | any code change |
| T-02 | 8 | `skill/scripts/aidd_rules.py`, `skill/scripts/aidd_status.py`, `tests/test_aidd_rules.py` | 1 | T-01 | 60 | other R7 logic |
| T-03 | F | `skill/scripts/aidd_lock.py`, `aidd/cli.py`, `tests/test_aidd_lock.py` | 1 | T-01 | 120 | queue UI, Playwright specifics |
| T-04 | A | `skill/scripts/aidd_approve_preflight.py`, `skill/scripts/aidd_status.py`, `aidd/cli.py`, `tests/test_aidd_preflight.py` | 2 | T-02 | 360 | `--fix` of amendment 07 (separate task there) |
| T-05 | B | `skill/scripts/aidd_status.py`, `skill/scripts/aidd_rules.py`, `tests/test_verify_rows.py` | 2 | T-01 | 360 | cross-spec reuse, round cache |
| T-06 | C | `skill/scripts/aidd_status.py`, `skill/scripts/aidd_rules.py`, `skill/scripts/aidd_triage.py`, `tests/test_verify_env.py` | 3 | T-03, T-05 | 300 | process kill of dev servers |
| T-07 | G | `skill/scripts/aidd_red.py`, `skill/scripts/aidd_close_ledger.py`, `skill/scripts/aidd_status.py`, `tests/test_aidd_red_visual.py` | 3 | T-00 (owner applied patches), T-03 | 300 | building the comparator (am. 09 B2) |
| T-08 | D1, D3-AIDD | `skill/scripts/aidd_sqlcheck.py`, `skill/scripts/sql_graph.py`, `skill/scripts/aidd_rules.py`, `tests/test_aidd_sqlcheck.py` | 2 | T-01 | 240 | DB connection |
| T-09 | D4 | `skill/scripts/aidd_status.py`, `skill/scripts/aidd_triage.py`, `tests/test_verify_global.py` | 3 | T-05 | 240 | changing existing rows |
| T-10 | E | `skill/scripts/aidd_tasks_archive.py`, `aidd/cli.py`, `tests/test_tasks_archive.py` | 3 | T-00 (batch coverage in source) | 300 | archiving under a live approval |
| T-11 | 9 | `skill/hooks/stop_gate.py`, `skill/scripts/aidd_status.py`, `tests/test_stop_gate.py` | 2 | T-01 | 150 | R6/R9/R10/close |
| T-12 | text | `skill/AIDD.md`, `skill/SKILL.md`, `adapters/dot-aidd/CORE.md`, `adapters/dot-aidd/AIDD.md` | 4 | T-04..T-11 | 90 | rewording other sections |

### T-00 Baseline report (H0)
1. Write `tools/aidd_bundle_diff.py` with `main(argv) -> int`: args `--source D:/Fuentes/AIDD/skill --installed <dir>` (repeatable); for every `*.py` and `*.md` under `scripts/`, `hooks/`, root, print `SAME|DIFF|ONLY-SOURCE|ONLY-INSTALLED <relpath>` (sha256 of LF-normalised bytes); exit 0 always.
2. Test first `tests/test_aidd_bundle_diff.py`: two temp trees with one same, one different, one only-left file → three lines as expected.
3. Run against `~/.claude/skills/aidd` and `D:/Fuentes/b1SycLink/.aidd` and save the output to the task report.
4. Verification: `python -m unittest tests.test_aidd_bundle_diff -v` exit 0.
Do NOT: apply `batch-staging/*.diff`, write into any installed directory, commit. The owner decides how the staged patches enter the source tree.

### T-01 Hash pin (AC-451)
1. Test first: `tests/test_am10_hash_compat.py` with `class HashCompat(unittest.TestCase)`; `test_fixture_hashes_pinned` iterates the specs built by `tests/gate_fixtures.py` and compares `rules.approval_hash(tasks)` and `rules.verification_hash(spec)` with a dict `PINNED` literal written in the file; `test_client_samples_pinned` does the same over `tests/fixtures/am10/<id>/{spec.md,tasks.md}`.
2. Copy (read-only source) the `spec.md` + `tasks.md` of b1SycLink `P01-Payrol-Foundation`, `F38-eDoc-Import-Costing` (with `tasks-amendment-07.md`, `-08.md`), `F21-eDoc-Inventory` (skip if > 2 MB), `F39-eDoc-Inventory-Accounting`, `S04-Select-Interviews-Evaluation` into `tests/fixtures/am10/` with a script (`tools/am10_copy_fixtures.py`, dry-run first).
3. Compute `PINNED` with the CURRENT code before any other task and write it as literals.
4. Verification: `python -m unittest tests.test_am10_hash_compat -v` exit 0. This test must stay green after every later task.
Do NOT: modify b1SycLink; regenerate `PINNED` after T-02.

### T-02 Minor 8
1. Tests first in `tests/test_aidd_rules.py`: `test_task_targets_bare_paths` (cell `eDoc/a/b.sql` → `['eDoc/a/b.sql']`), `test_task_targets_plus_joined_bare` (`a/x.ts + a/y.ts`), `test_task_targets_same_owner_skipped` (`same owner as T-01` → `[]`), `test_impact_zero_files_unknown` (`magnitude == 'unknown'`), and in `tests/test_aidd_status.py` `test_close_gaps_no_r7_note_for_zero_files`.
2. Implement FR-393 inside `task_targets` (keep the backtick branch first; add the bare branch only when the cell has no backticks) and FR-394 in `impact_summary` and `_close_gaps` (`aidd_status.py:3036-3040`).
3. Verification: `python -m unittest tests.test_aidd_rules tests.test_aidd_status tests.test_am10_hash_compat -v` exit 0.
Do NOT: change `required_domains` semantics for files > 0; touch approval hashing.

### T-03 F lock
1. Tests first `tests/test_aidd_lock.py`: `test_mutual_exclusion` (two `subprocess.Popen([sys.executable, aidd_lock.py, 'heavy', 'x', '--', sys.executable, '-c', 'import time; time.sleep(1)'])`, intervals from printed `LOCK-ACQUIRED <ts>`/`LOCK-RELEASED <ts>` do not overlap), `test_stale_pid_taken_over`, `test_exit_code_propagates`, `test_timeout_exit_75`.
2. Implement `skill/scripts/aidd_lock.py`: `acquire(root, res, timeout) -> Path`, `release(path)`, `status(root) -> list[dict]`, `main(argv)`; lock dir `<root>/.aidd/locks/`; reuse `_pid_alive` by importing `aidd_job`.
3. Add `lock` to `aidd/cli.py` as a passthrough like `verify` (`aidd/cli.py:187-189`).
4. Verification: `python -m unittest tests.test_aidd_lock -v` exit 0.
Do NOT: use third-party packages; lock anything in `aidd verify` yet (column `Lock` comes with T-06).

### T-04 A preflight
1. Tests first `tests/test_aidd_preflight.py`: fixtures per AC-430..432 (use `gate_fixtures` helpers only); `test_all_causes_one_run`, `test_planned_file_note`, `test_invariant_with_approve`, `test_charter_preflight_command`, `test_readonly` (no file mtime changes, no event appended).
2. Implement amendment 07 FR-270..283 catalogue in `skill/scripts/aidd_approve_preflight.py` as `preflight(spec_dir, root) -> list[Cause]` with `Cause(id, rule, message, fix, blocks, owner_only, autofix)`; add P12..P15 per FR-372..374; P14 calls T-08's order check if available (import guarded; absent = no P14).
3. `aidd_status.py`: `cmd_preflight(spec_arg)`; `cmd_approve` calls `preflight` first (amendment 07 FR-273); `cmd_check` prints the FR-375 note.
4. Verification: `python -m unittest tests.test_aidd_preflight tests.test_aidd_status tests.test_cli_rules tests.test_am10_hash_compat -v` exit 0.
Do NOT: implement `--fix --apply` (amendment 07 task); change any message of `check_verification`.

### T-05 B rows and same-spec carry
1. Tests first `tests/test_verify_rows.py` (AC-433, AC-434) using a temp project whose rows are `python tests_helpers/row_n.py` scripts writing to a counter file to prove whether a row ran; plus `test_rows_unknown_refused`, `test_rows_not_full_run` (close gate still missing), `test_carry_requires_inputs`, `test_full_disables_carry`.
2. Implement `--rows` in argv parsing (`aidd_status.py:3210-3253`) and `cmd_verify(..., row_ids=None)`; `_carriable_rows(d, root, rows, full)`; record `rows_verify_run`; carry branch placed right after the existing `input_reuse` branch (`:2435-2453`); `_close_gaps` FR-378.
3. Fix docs FR-380 in T-12 (not here).
4. Verification: `python -m unittest tests.test_verify_rows tests.test_aidd_task_verify tests.test_verify_regressions tests.test_am10_hash_compat -v` exit 0.
Do NOT: re-enable `round_on`; allow carry across specs; relax `_contract_environment_id`.

### T-06 C environment
1. Tests first `tests/test_verify_env.py` (AC-436..439); monkeypatch `aidd_status._free_mb`.
2. Implement FR-381..384 and the `Lock` column (FR-391) wrapping `_run_row` in `aidd_lock.acquire/release`.
3. Verification: `python -m unittest tests.test_verify_env tests.test_verify_regressions tests.test_am10_hash_compat -v` exit 0.
Do NOT: retry more than once; retry rows without a signature; kill external processes.

### T-07 G visual RED
Precondition: the owner has brought `aidd_red.py`/`aidd_close_ledger.py` into `skill/scripts/` (T-00 report).
1. Tests first `tests/test_aidd_red_visual.py` (AC-447) plus `test_legacy_spec_not_required` (approval date before the rule and no `Visual-gate: on`).
2. Implement FR-392.
3. Verification: `python -m unittest tests.test_aidd_red_visual tests.test_am10_hash_compat -v` exit 0.
Do NOT: build a comparator; parse screenshots; change the RED receipt format of B5.

### T-08 D1/D3 (AIDD side)
1. Tests first in `tests/test_aidd_sqlcheck.py` (AC-440, overload case `f(int)` vs `f(text)` = no error, view and trigger cases) and in `tests/test_aidd_rules_r10.py` (AC-441, `[CONTAMINATION]`).
2. Implement FR-385..387.
3. Verification: `python -m unittest tests.test_aidd_sqlcheck tests.test_aidd_rules_r10 -v` exit 0.
Do NOT: connect to a database; edit b1SycLink `db_verify.py` (project spec).

### T-09 D4 global gate
1. Tests first `tests/test_verify_global.py` (AC-442).
2. Implement FR-388 using `aidd_triage` parsing (import, do not copy the regexes).
3. Verification: `python -m unittest tests.test_verify_global tests.test_wave_verification tests.test_am10_hash_compat -v` exit 0.
Do NOT: run global rows in normal `aidd verify`.

### T-10 E archive
Precondition: batch coverage is in the source tree (T-00).
1. Tests first `tests/test_tasks_archive.py` (AC-443, AC-444, `--dry-run` writes nothing, existing target refused, rollback on R1 failure).
2. Implement FR-389.
3. Verification: `python -m unittest tests.test_tasks_archive tests.test_tasks_batch_coverage tests.test_am10_hash_compat -v` exit 0.
Do NOT: archive under a valid approval of an open spec; touch the `Approved:` line.

### T-11 Minor 9 pause
1. Tests first in `tests/test_stop_gate.py` (AC-449) and `tests/test_cli_rules.py` (`pause` refused without consent).
2. Implement FR-395: `cmd_pause`, `cmd_resume` in `aidd_status.py`; `stop_gate._paused(ev, root, spec, key) -> bool` used in `evaluate` before the budget check (`stop_gate.py:200`).
3. Verification: `python -m unittest tests.test_stop_gate tests.test_cli_rules -v` exit 0.
Do NOT: change `MAX_BLOCKS`; skip R6/R9/R10; allow N > 24.

### T-12 Text
1. Edit `skill/AIDD.md` (E8 D-contract, E9 (g) FR-396, Step 4 batches FR-390, verification paragraphs `:590`/`:631` FR-380, `aidd preflight` FR-375), `skill/SKILL.md` (`:463` and E-summary), `adapters/dot-aidd/CORE.md` §5; regenerate the mirror with `python skill/scripts/generate_adapters.py`.
2. Verification: `python -m unittest tests.test_cli_rules tests.test_dot_aidd_mirror -v` exit 0.
Do NOT: rewrite E1..E10 beyond the cited sentences.

---

## Open decisions (owner)

| # | Question | Recommendation |
|---|---|---|
| OD-1 | How do the staged patches (B5/B6/B10/B11/B12/batches) enter the source repo, and FR-292 into the installed bundle? (H0) | apply them into `skill/` first, then T-01 pins hashes, then the rest |
| OD-2 | `Reuse: same-spec` for DB rows trusts the runner's template reset. Accept? | yes, per row, approved in the table; `--full` before close stays available |
| OD-3 | Where do project preflight commands live (`## Preflight` in the charter)? | the charter, so one approval covers every spec |
| OD-4 | Visual gate (G) for specs already approved: opt-in `Visual-gate: on` or only new approvals? | only new approvals + opt-in, so no approval or close rule changes retroactively |

## Pending

- Project-side work (b1SycLink, its own AIDD spec, not this repo): D2 contamination snapshot and D3 unmatched filters in `eDoc/tools/db_verify.py`; e2e fixtures reading config relative to their file (not `process.cwd()`) until `Workdir` exists.
- Amendment 07 stays the design source of the cause catalogue; this amendment adds P12..P15 only.
