# Amendment 09 to spec 007: shift-left visual fidelity, shared-surface blast radius, defect fast lane, RED receipt, accepted Verification forms, spec size, executor capacity

Intake: `AMENDMENT` of `specs/007-aidd-review-html-close-gate` (owner of E8/E9 text and the approval gate). Follows
`amendment-08-verification-economy-and-fidelity.md` (FR-290..FR-293), which it references and does NOT duplicate.
Requested by the owner on 2026-11-04: "como evitamos que avancemos hasta este punto y toque repetir todo de nuevo; la
finalidad es que evitemos esto con la metodologia AIDD". Evidence measured in the client project b1SycLink on
2026-11-04. Scope of this amendment: METHODOLOGY TEXT and a tool BACKLOG only; no new script is implemented here.
Status: text APPLIED to `skill/AIDD.md`, `skill/SKILL.md` and the `adapters/dot-aidd/AIDD.md` mirror (new E10); the
installed skill and project bundles are synchronized by the owner. FR numbers 294..300 are the free block between
amendment 08 (FR-290..293) and spec 008 (FR-301..).

## Problem (one line per lesson, with the measurement)

| # | What happened | Measurement |
|---|---|---|
| L1 | The visual task (`T-VISUAL`) sits at the end, so the gap shows up after everything is built | F38: 0 of 32 states matched the prototype; F37: 5 of 53; vitest was green (258 tests) |
| L2 | Parallel specs redefine shared DB objects; defects appear only in the full suite | `fe_acct_link_journal` (3476, F40) broke F41 (TYPE_UNKNOWN); `fe_period_close` (3471, F40) failed 11 of 59 in F21's test (PERIOD_PREV_OPEN); index `OMOV_Aging_ix` (3442, F56) made test 6 of `inventory_plans` demand another index; IdemKey of ACC.PERIOD.CLOSED collided between F21 and F40; `fe_acct_ready(NULL)` in F39 |
| L3 | Build-time defects need migrations outside the approved plan, forcing an amendment and re-approval each | 3 migrations (3482 and 3483 in F41, and one more), one amendment per finding |
| L4 | Builders wrote page and test in the same step (no RED); green tests proved little | several specs; the visual gap above is the consequence |
| L5 | Approvals refused after the owner's click for invalid Verification rows | F38 V-18; F37 V-9/V-10/V-11 (preflight itself is FR-292 / amendment 07) |
| L6 | `aidd review` refuses to build the page above 400 000 chars (`MAX_REVIEW_SOURCE_CHARS`, `aidd_review.py`) | F21 tasks.md 1.26 MB; F38/F37 about 430-460 KB; approval by summary or an amendment moved to a child spec (F56) |
| L7 | One executor ran out of quota mid-round | agy 429 for 112 h; 4 agents died |
| L8 | Load/verification contention | covered by FR-291 (rounds, batches, DB copy); nothing new here |
| L9 | The orchestrator did by hand what a tool can do or check (verification tables, evidence freshness, repeating agent tests) | 2026-11-04 b1SycLink: `qa-audit.md` verification tables and R10 freshness of several specs built by hand; the extra round of six P01 auditors cost about 370k tokens because freshness was not checked with a tool before auditing |

## Functional requirements

| Code | Requirement | Where | Source |
|---|---|---|---|
| FR-294 | **Visual contract shift-left (L1).** Step 1 produces, per screen, a machine-readable VISUAL CONTRACT derived from the prototype: `main[data-screen]`, the `h1` text, the set of `data-ctl`/`data-comp` codes, table columns (ordered), states (loading/empty/error/data...) and the loading skeleton count. Component/page tests are DERIVED from it (one assertion group per contract field), not hand-written from memory. Every view task has a measured comparison against the prototype with a verdict `match` / `differ` / `not-verified` by a FIXED rule (match = every contract field equal or at least; any missing code, column or state = differ; no measurement = not-verified) BEFORE the task is marked done. ONE pilot screen is built and measured end to end (canary) before the rest of the screens are built; if the pilot differs, the contract/pattern is fixed first. Browser measurements are SERIALIZED in a queue (one Playwright at a time). `T-VISUAL` at the end remains the closing proof, not the first detection. | `skill/AIDD.md` + `skill/SKILL.md` E10(a), Step 1 | L1 |
| FR-295 | **Shared surface and blast radius (L2).** The plan declares, per spec, every function/table/index/constraint/idempotency-key namespace it REDEFINES (a `CREATE OR REPLACE` or `ALTER` of an object that already exists or that another spec also touches), under a plan heading `Shared surface`. Before building, the builder queries the graph (`aidd graphs show db <name>`) to list that object's callers and the tests that exercise it. Every migration touching a shared object immediately runs that grouped set (`--only-tests a,b,c` in ONE invocation, FR-291) and not only the spec's own tests. A shared-surface change is announced to the orchestrator (one line: object, migration, callers) so parallel agents see it; two specs redefining the same object in one round are serialized or one of them owns it. | `skill/AIDD.md` + `skill/SKILL.md` E10(b), Step 3/5 | L2 |
| FR-296 | **Defect fast lane (L3).** The plan reserves a CONTINGENCY RANGE of migration numbers per spec (e.g. 10 numbers) and the template of a ONE-PAGE defect amendment (symptom, evidence command + output, object, fix, tests covering it). On a build-time defect the builder STOPS and reports with evidence (no unplanned migration outside the range, no silent fix). The orchestrator groups the defects of a round into ONE amendment per owning spec (never one per finding) and asks ONE approval for it. | `skill/AIDD.md` + `skill/SKILL.md` E10(c) | L3 |
| FR-297 | **RED receipt (L4).** Delivering a test task includes a RED receipt: the saved output of the new test failing (or the new file failing to import) BEFORE the implementation, stored under `specs/<spec>/evidence/` (command, exit code, first failing assertion). The orchestrator rejects a delivery of a NEW test file without the receipt; the targeted check of E9(f) verifies the receipt, it does not rerun the suite. Exception: a pure refactor with an existing test, declared as such. | `skill/AIDD.md` + `skill/SKILL.md` E10(d) | L4 |
| FR-298 | **Accepted and rejected Verification forms (L5).** Documented list, observed in b1SycLink and checked by `aidd rules approve` / `aidd rules check` (FR-292): REJECTED: `npm --prefix <dir> run <script>`, `cd <dir> && ...`, `bash -c "..."`, `same with ...`, any Expected other than `exit 0` (`0 FAIL`, `PASS`, `OK`). ACCEPTED: `node <path>/cli.js test --config=<file>` and `python <path>.py <args>` (an existing file), Expected exactly `exit 0`. A row that needs a rejected form is wrapped in a repo script that exits non-zero on failure and the row calls the script. The orchestrator runs `aidd rules check <spec>` before asking the owner. | `skill/AIDD.md` + `skill/SKILL.md` E10(e) | L5; amendment 07/FR-292 |
| FR-299 | **Spec size (L6).** Warning threshold at 300 000 characters for the sources of one review page (spec + plan + tasks + the files `aidd review` reads), against the 400 000 limit. When the threshold is reached the spec is SPLIT by amendment batches (one amendment file per batch, each with its own tasks) before reaching the limit; the limit is never worked around by approving a summary instead of the page. (The warning itself is backlog B6; until it exists the orchestrator measures `wc -c` of the sources at each round.) | `skill/AIDD.md` + `skill/SKILL.md` E10(f) | L6 |
| FR-300 | **Executor capacity and routing (L7).** The `## Optimization brief` declares per executor a token estimate and an ALTERNATE executor per lane. Before launching a wave, executor capacity is probed with a cheap smoke (one trivial call); a refused/exhausted executor is replaced by its alternate BEFORE launch. Lanes that write the same tree never share an executor unless split by folder. | `skill/AIDD.md` + `skill/SKILL.md` E10(g), Step 2 brief | L7 |
| FR-300 (h) | **Orchestrator tools-first (L9).** No new FR number: 294..300 is exhausted and 301 belongs to spec 008, so the rule lives under FR-300 as item (h). The orchestrator does not do by hand what is mechanical or checkable (verification tables from the evidence, counting, listing, comparing, applying patches, evidence freshness, repeating tests an agent already ran); a repo tool does it (`aidd`, `db_verify`, generators, `check_spec`, `task_precision_check`) or an agent that runs it and returns the output. If the tool does not exist and the step will repeat, it is built first and added to the backlog (B12). The orchestrator only decides, asks the owner, approves with the owner's answer, judges findings and writes conclusions. | `skill/AIDD.md` + `skill/SKILL.md` E10(h) | L9; owner decision 2026-11-04 |

## Acceptance criteria

| Code | Scenario | Expected |
|---|---|---|
| AC-410 | `skill/AIDD.md` contains the E10 item with (a)-(g) and the `adapters/dot-aidd/AIDD.md` mirror is byte-identical | `test_dot_aidd_mirror` passes |
| AC-411 | `skill/SKILL.md` carries the same E10 summary | grep `E10` finds it in both files |
| AC-412 | `skill/AIDD.md` and `skill/SKILL.md` E10 carry item `(h) Orchestrator tools-first` with the 2026-11-04 measurement, and the mirror stays byte-identical | grep `Orchestrator tools-first` finds it in both files; `test_dot_aidd_mirror` passes |

## Verification

| # | Command | Expected | Covers |
|---|---|---|---|
| 1 | `python -m unittest tests.test_cli_rules tests.test_dot_aidd_mirror` | exit 0 | FR-294..FR-300, AC-410, AC-411 |

## Tool backlog (prioritized; size = agent hours including tests; NOT implemented here)

Priority order is by measured cost avoided. "State today" was checked in `skill/scripts/` and `tools/` on 2026-11-04.

| Pri | Tool | Serves | State today | Size |
|---|---|---|---|---|
| B1 | Visual-contract generator from the prototype HTML (`aidd contract <prototype>` -> JSON per screen: data-screen, h1, ctl/comp set, columns, states, skeletons) | FR-294 | Missing. Partial pieces: Step 1 audit is manual/agent; `flowmap.py` and `aidd_review_items.py` parse prototypes for review items; none emits the contract | 6-8 h |
| B2 | Visual comparator with verdict (`aidd visual-diff <contract> <url\|html>` -> match/differ/not-verified per state, fixed rule) | FR-294 | Missing. `aidd_unit_visual.py` is consent/approval of a unit, not measurement; in the client the comparison is a hand-written capture harness | 8-10 h |
| B3 | Playwright queue (one browser measurement at a time, FIFO, shared across agents) | FR-294 | Partial: `aidd_job.py` caches/waits one job per command and inputs; no cross-agent mutual-exclusion queue. Extension: `aidd job run --queue playwright` | 2-3 h |
| B4 | SQL caller graph (`aidd graphs show db <fn>` listing callers and covering tests) | FR-295 | Partial: `aidd_graphs.py` shows callers/callees for the CODE graph (`calls` edges); `sql_graph.py` models tables/columns/functions but has no function-call edges and no function-to-test link | 5-7 h |
| B5 | RED receipt (`aidd red <test-cmd> --task T-nn` stores command, exit code, first failure under `evidence/`; a check that a new test file has one) | FR-297 | Missing. `aidd_evidence.py` records events and `aidd job` stores `verdict.json`/`log.txt` (reusable as storage), but nothing ties a receipt to a new test file | 3-4 h |
| B6 | Spec-size warning at 300 000 chars in `aidd review`/`check_spec` (plus batch-split hint) | FR-299 | Partial: `MAX_REVIEW_SOURCE_CHARS = 400_000` in `aidd_review.py` refuses at the limit; no early warning | 1 h |
| B7 | Shared-surface check: plan `Shared surface` heading validated by `check_spec`, and a migration-vs-declaration cross-check (CREATE OR REPLACE of an object not declared) | FR-295 | Missing (depends on B4) | 3-4 h |
| B8 | Executor capacity smoke (`aidd executors probe`) and alternate-executor field check in the Optimization brief | FR-300 | Missing | 2-3 h |
| B9 | Contingency-range field in the plan template and `templates/amendment-defect.md` | FR-296 | Missing; templates for the other artifacts exist in `skill/templates/` | 1-2 h |
| B10 | Close preflight: `aidd rules close <id> --check` (dry run, no side effects) that runs the SAME gates as `aidd rules close` and lists what is missing, plus a "freeze before audit" order in the close sequence (fixes, fresh R10 evidence and the final `qa-audit.md` first, then ONE auditor per domain, then close) | measured 2026-11-04 on P01: `aidd rules check` printed `PASS R7` while `aidd rules close` refused R7 for all six domains, because fresh evidence and the rewritten documents were recorded after the auditors; it cost a second round of six auditors (about 370k tokens) to confirm that a document matched the code | Missing; `aidd rules check` and `aidd rules close` apply different R7 rules without saying so | 3-4 h |
| B11 | `AIDD_FINGERPRINT_BUDGET` and reuse of the whole-tree scan across the specs of one round: `aidd verify` refuses to run when the fixed 8 s budget of `code_state` is exceeded on a large dirty tree under load ("cannot fingerprint the verification inputs") | measured 2026-11-04: the P01 verification was refused twice before any command ran | Partial; `aidd status` already reuses the scan (`reuse=True`), `aidd verify` does not | 1-2 h |
| B12 | `aidd close-ledger <spec>`: prints to stdout the heading `CLOSING AUDIT [...] [tasks:<h8>] [verify:<v8>]`, the verification table built from `evidence/verify-V-*.txt`, and the R10 evidence freshness check ending in "LISTO PARA AUDITAR" | FR-300 (h) | prototype in the project: `tools/close_ledger.py` of b1SycLink (under construction today) | 4-6 h |

## Pending

- Owner decision: synchronize projects with `python tools/aidd_selective_update.py --help`, as in amendment 08.
- B1/B2 are what make FR-294 mechanical; until they exist the contract is written by the auditor agent and the comparison is a project script, but the verdict rule stays fixed.
