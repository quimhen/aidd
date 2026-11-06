# Amendment 11 to spec 007: amendment-scoped verification (`aidd verify <spec> --amendment NN`)

Intake: `AMENDMENT` of `specs/007-aidd-review-html-close-gate` (owner of `aidd verify`, R10 and the close gate).
Follows amendment 10 items O (FR-419..426, `--round`), P (FR-427..432, same-spec reuse inside a round) and Q
(FR-433..442), and amendment 10 item B (FR-376..380, `--rows` / `Reuse: same-spec`, never implemented), whose
"carry a previous PASS by declared Inputs" idea it implements in a narrower, opt-in form.
Status: DRAFT, implemented on branch `am11/amendment-scoped-verify` of the AIDD repo (not installed, not pushed,
not approved: no `Approved:` line). Numbering: next free block FR-450..FR-459, AC-520..AC-533, task T-23.

Legend: **[fact]** read in the code with `file:function`; **[measured]** owner measurement, not re-measured here.

## Problem

- [measured] An amendment that edits 2 test files forces the whole Verification table (e.g. 17 rows, ~40 min) to run
  again before close.
- [fact] A passed `aidd verify` is judged by ONE code fingerprint of the whole spec Scope
  (`aidd_rules._run_problems`, `code_fp_end`); any code edit in Scope stales every row.
- [fact] Reuse today: (a) the offline hermetic contract (`_reusable_input_rows`, Python rows only, never DB);
  (b) same-spec reuse inside `--round` (`aidd_round.reuse_plan`), which requires the WHOLE Scope fingerprint to be
  unchanged, so it never helps after a code edit; (c) `--tasks` / `--changed` record a partial `task_verify_run`
  that never satisfies close.
- [fact] Bug: `aidd verify <spec> --dry-run` (without `--round`) treated `--dry-run` as a second spec name and called
  `cmd_verify_many([spec, '--dry-run'])`, which EXECUTED the spec for real (`aidd_status.main`, `specs = [a for a in
  args if a not in ('--full', '--bail', '--json')]`). Any unknown flag did the same.

## Decisions

| # | Decision | Why |
|---|---|---|
| D-1 | Reuse by per-row `Inputs` is opt-in through `aidd verify <spec> --amendment NN` only. A plain `aidd verify <spec>`, `--round`, `--tasks`, `--changed`, `--wave` and `--perf` keep their behaviour exactly. | No silent change of the default; the owner chooses when to trust declared Inputs. |
| D-2 | The amendment's declared files come from `specs/<id>/tasks-amendment-NN.md` (`NN` zero-padded or not): backticked paths on `Files to change:` lines, the `Target file` table column (outside `specs/`), and an optional machine-readable fenced block ` ```aidd-files ` (one root-relative path per line). Missing file or zero paths = refusal, nothing executed. | Same convention as the existing task files (b1SycLink `tasks-amendment-13.md`), parsed like `aidd_unit_audit` does. |
| D-3 | Declared files only FORCE executions; they never authorise a reuse. Every row not forced is reused only when its reuse is PROVEN by fingerprints (D-4). An undeclared edit therefore cannot produce a false PASS: the row whose Inputs changed runs, with a warning that the amendment does not declare it. | Never a false PASS; a wrong declaration costs time, not correctness. |
| D-4 | Reuse proof, per row, against the spec's latest `verify_run` (fail closed on any doubt): previous run `stable`; the row exists with the same normalised command and Expected; it was a PASS (exit 0) with no lint problem today; not `Reuse: never`, not `Regression: always`; **with `Inputs`**: same Inputs declaration and `input_algorithm`, and `row_input_fingerprint` now equal to the recorded one; **without `Inputs`**: today's whole-Scope rule (same Scope, current code algorithm, Scope fingerprint now equal to `code_fp_end`); environment identity (`env_id`, FR-430) equal when the row names a `docker exec` container or the spec declares `Round-identity:`/vars; evidence file intact (full sha1) and still valid under today's PASS rules. | Same conditions as item P, except that a row with Inputs is judged by its Inputs instead of the whole Scope. |
| D-5 | `Regression: always` is a new optional column `Regression` (value `always`). Such a row is always executed by `--amendment` and never reused by it. It is NOT part of `verification_hash` (no change to approval hashing): it can only add executions, never enable a reuse. Any other non-empty value is an R10 lint error. | Owner request; keeps every existing hash byte-identical. |
| D-6 | `--amendment` records ONE complete `verify_run` (executed + reused rows) through the normal `cmd_verify` path: same evidence files, same stability check (code state taken before the plan and after the last row), extra fields `amendment` and `amendment_files`. Reused rows carry `reused: true`, `reuse_kind: amendment-inputs` or `amendment-scope`, `reused_from{spec, n, date, code_fp, verify_hash, secs}` and evidence line 2 `REUSED: ...`. | The close gate reads it like any other run; nothing in R7/R10 is relaxed. |
| D-7 | Close gate unchanged in strength and slightly stricter: every row of the table still needs a valid PASS in the newest `verify_run`; rows with Inputs are re-fingerprinted at close (existing check); a result marked `reuse_kind: amendment-inputs` without `input_globs`/`input_fp`, or `amendment-scope` without `reused_from.code_fp`, is stale. | Point (4) of the brief: no weakening. |
| D-8 | When a reuse cannot be proven the row RUNS and the plan says why (`cannot prove reuse: ...`: no env_id recorded, identity unavailable, Inputs not fingerprintable). When the Scope cannot be fingerprinted at all (budget) the real run is REFUSED with the existing `fingerprint_refusal` text (names `AIDD_FINGERPRINT_BUDGET`); `--dry-run` prints it as a note. Never a silent skip. | Point (5) of the brief. |
| D-9 | `--dry-run` is accepted with ONE spec (plain or with `--amendment`), prints one line per row `RUN <n>: <reason>` / `REUSED <n>: <reason> (PASS of <date>, ~S s saved)` / `PERF <n>: not run` and a summary, executes no row and records nothing. Any unknown `aidd verify` option is refused before anything runs. | Point (6) and the bug above. |
| D-10 | `--amendment` cannot be combined with `--tasks`, `--changed`, `--base`, `--wave`, `--json`, `--bail`, `--full`, `--perf`, `--round` or several specs (refused, nothing executed). `--full` stays the way to run everything. | Small, auditable surface. |

## Requirements

| Code | Requirement |
|---|---|
| FR-450 | `aidd verify <spec> --amendment NN [--dry-run]` reads the declared files of `tasks-amendment-NN.md` (D-2); refuses `Refused: ...; nothing was executed.` when the file is missing, declares no path, or NN is not 1-3 digits. |
| FR-451 | Plan per functional row (table order): RUN when `Regression: always`; RUN when a declared file matches the row's `Inputs` (glob) or appears literally in its command; else REUSED when D-4 holds; else RUN with the reason. `Tier: perf` rows are skipped as in a plain run. |
| FR-452 | Reused rows are not executed; their evidence is the previous evidence with line 2 `REUSED: PASS del verify_run de <spec> fila <n> del <date>, huella <fp>, verify hash <h>; <basis> sin cambios (no ejecutado: aidd verify --amendment NN)`; a chain keeps the origin of the run that really executed the row. |
| FR-453 | One complete `verify_run` with `amendment`, `amendment_files`; the decision and the stability check use the same code state taken before the first row. Output ends with `amendment NN: k row(s) executed, m REUSED (~S s saved)`. |
| FR-454 | A row whose Inputs changed although the amendment declares none of its Inputs prints `warning: row <n>: its Inputs changed since its last PASS but amendment NN declares none of them`. A row without Inputs that runs because the Scope changed prints the hint to declare `Inputs`. |
| FR-455 | `Regression` column: `always` or empty; anything else is an R10 lint error in `check_verification`; never part of `verification_hash`. |
| FR-456 | Close gate (D-7). |
| FR-457 | Refusals (D-8, D-10). |
| FR-458 | `--dry-run` (D-9) for one spec, plain or with `--amendment`; unknown options refused before execution. |
| FR-459 | Docs: `skill/AIDD.md` E14 + close sequence step 2, mirror `adapters/dot-aidd/AIDD.md`, `aidd verify --help`, `aidd/cli.py` help. |

## Acceptance

| Code | Scenario | Expected |
|---|---|---|
| AC-520 | 3 rows (2 with Inputs, 1 without), amendment 01 declares the Inputs file of row 1 which changed | row 1 runs, row 2 REUSED (`amendment-inputs`), row 3 runs (Scope changed, no Inputs); one complete PASS stable verify_run with `amendment` |
| AC-521 | nothing declared touches a row, nothing changed | every row REUSED, 0 executions |
| AC-522 | `Regression: always` row with unchanged inputs | it runs |
| AC-523 | a row's Inputs changed but are not declared | it runs, with the FR-454 warning |
| AC-524 | `--amendment NN --dry-run` | no execution, no event, evidence untouched; RUN/REUSED lines with reasons and savings |
| AC-525 | `aidd verify <spec> --dry-run` (the bug) | no execution, no event; RUN lines |
| AC-526 | unknown option; `--amendment` with `--full`/`--tasks`; two specs with `--dry-run` | refused, nothing executed |
| AC-527 | missing `tasks-amendment-NN.md`; file without paths | refused, nothing executed |
| AC-528 | close gate on the amendment run | no R10 problem; after editing a reused row's Inputs: stale `inputs changed` |
| AC-529 | reuse that cannot be proven: previous run without env_id on a `Round-identity:` spec; identity changed | the row runs; reason printed (`cannot prove reuse`) |
| AC-530 | Scope cannot be fingerprinted | real run refused with `AIDD_FINGERPRINT_BUDGET`; dry-run note |
| AC-531 | `Regression` lint and hash | bad value = R10; `verification_hash` identical with and without the column |
| AC-532 | forged gate result `amendment-inputs` without `input_globs` | stale |
| AC-533 | regression of touched modules | `python -m unittest tests.test_verify_round tests.test_verify_round_reuse tests.test_aidd_rules_r10 tests.test_verify_tiers tests.test_dot_aidd_mirror` exit 0 |

## Verification

| # | Command | Expected | Covers |
|---|---|---|---|
| 1 | `python -m unittest tests.test_verify_amendment` | exit 0 | FR-450..FR-458, AC-520..AC-532 |
| 2 | `python -m unittest tests.test_verify_round tests.test_verify_round_reuse tests.test_aidd_rules_r10 tests.test_verify_tiers tests.test_dot_aidd_mirror` | exit 0 | AC-533 |

## Tasks

| Task | Item | Target file(s) | Wave | Deps | Agent min | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-23 | FR-450..459 | `skill/scripts/aidd_amendment_verify.py` (new), `skill/scripts/aidd_status.py`, `skill/scripts/aidd_rules.py`, `skill/scripts/aidd_evidence.py`, mirrors in `adapters/dot-aidd/scripts/` (copied by script), `skill/AIDD.md` + `adapters/dot-aidd/AIDD.md`, `aidd/cli.py`, `tests/test_verify_amendment.py`, `tests/test_dot_aidd_mirror.py` | 1 | T-22 | 240 | Inputs reuse in plain `aidd verify`/`--round`; cross-spec reuse; re-enabling `round_on`; changing `approval_hash`/`verification_hash`; installing into `~/.claude` or a project |

### T-23 Amendment-scoped verification
- **Files to change:** `skill/scripts/aidd_amendment_verify.py`, `skill/scripts/aidd_status.py`, `skill/scripts/aidd_rules.py`, `skill/scripts/aidd_evidence.py`, `adapters/dot-aidd/scripts/aidd_amendment_verify.py`, `adapters/dot-aidd/scripts/aidd_status.py`, `adapters/dot-aidd/scripts/aidd_rules.py`, `adapters/dot-aidd/scripts/aidd_evidence.py`, `skill/AIDD.md`, `adapters/dot-aidd/AIDD.md`, `aidd/cli.py`, `tests/test_verify_amendment.py`, `tests/test_dot_aidd_mirror.py`.
1. Tests first: `tests/test_verify_amendment.py` (AC-520..AC-532) on the `ReuseBase` fixture of `tests/test_verify_round_reuse.py`; run it and record the RED.
2. Implement D-1..D-10; copy the changed scripts to `adapters/dot-aidd/scripts/` with a script (byte-identical), add the new module to the mirror list.
3. Verification: rows 1 and 2 above.
Do NOT: change `approval_hash` or `verification_hash`; reuse in a plain `aidd verify`; touch `.aidd/`, `~/.claude` or any project.

Status of T-23: implemented on branch `am11/amendment-scoped-verify` (not installed, not pushed, not approved).
RED `evidence/amendment-11-red.txt` (15/15 failing; the dry-run bug reproduced: spec executed for real), GREEN
`evidence/amendment-11-green.txt`. Pre-existing failure, unchanged: `tests.test_wave_verification`
`test_explicit_inputs_do_not_trigger_round_global_scan` fails identically on HEAD `a7b603d`.

## Not covered / follow-ups

- Inputs-based reuse inside `--round` (it still needs an unchanged whole Scope).
- Transitive dependencies of a row are only as complete as its declared `Inputs` (owner-approved in the table, part
  of `verification_hash`); a row whose Inputs miss a real dependency can be reused after that dependency changed.
  Mitigation: declare Inputs generously, `Regression: always` for whole-suite rows, `--full` before close when in doubt.
