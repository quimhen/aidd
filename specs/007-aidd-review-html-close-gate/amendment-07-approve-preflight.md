# Draft — amendment 07 to spec 007: approval preflight ("AIDD must help, not obstruct")

**DRAFT: not approved, not executable, no `Approved:` line.** Amendment intake: `AMENDMENT` of
`specs/007-aidd-review-html-close-gate` (owner of the approval gate `aidd rules approve`, the review page and R10
Verification, FR-204/FR-205/FR-207). It also touches the compact review of spec 008 (FR-307, FR-309, FR-312, FR-313)
only by CALLING its existing functions; nothing in 008 changes behaviour. `find_spec.py approve preflight review
verification` (2026-11-04) ranked 004, 006, 007, 008 at score 4; 007 is the owner by content (`cmd_approve`,
`check_verification`, `review_state` all cite aidd:FR-204/FR-205).

Owner principle (relayed by the coordinator, 2026-11-04, verbatim): **"aidd debe mejorar no obstruir"**. This quote is
not yet in a recorded prompt of an AIDD-repo session; at merge time it must be re-quoted from a recorded prompt (R5),
which is itself an instance of the problem FR-282 addresses.

## Problem and evidence (b1SycLink, 2026-11-04)

The owner clicked an approval question for 4 specs; `aidd rules approve` refused each one AFTER the click.

| # | Spec | Refusal | Root cause in the AIDD code (read 2026-11-04) | Who could have fixed it before the click |
|---|---|---|---|---|
| E1 | F40, F42 | `spec.md has no valid "## Verification" table` | Rows `same with --only-tests ...` (not a command), `npm --prefix eDoc/web run test -- ...` and Expected `0 FAIL`. `check_verification` (`skill/scripts/aidd_rules.py:2769`) is called ONLY by `cmd_approve` (`aidd_status.py:1434`), the hook's `_approval_gate` (`rule_gate.py:377`) and as an advisory list on the review page (`aidd_review.py:781`); its own docstring says it is "NOT part of check_content('spec')", so no edit of spec.md and no `check_spec.py` run reports it. The `npm --prefix <dir> run test` row is also a **lint false negative**: `_runner` (`aidd_rules.py:2676`) only matches `npm` when the FIRST argument is `test`/`t`/`run`, so `--prefix` first makes it fall through to `_names_existing_file`, which needs a FILE (`eDoc/web` is a directory). | agent |
| E2 | F37 | review incomplete: `review.md was generated for tasks hash <old>` (`aidd_review_state.py:396`) | tasks.md changed after the owner saved the page. `cmd_approve` checks R1, then Verification, then the review, then consent, and **returns on the first failing step** (`aidd_status.py:1413-1497`), so the stale review was only reported after the owner's click; the tag in the question matched the NEW tasks.md, which made the question look valid. | agent (regenerate the page) + owner (press `Aprobar y guardar` again; unchanged items keep their checks, FR-312 carry-over) |
| E3 | F21 | `no recorded user answer "Approve" ... contains the tag` | The question offered the label `Aprobar con resumen`. The generic route accepts `APPROVE_LABEL = ^(approve\|aprobar\|aprobado)\b(?!\s+con\s+resum)` (`aidd_status.py:71`), which deliberately excludes it; the summary route (`_summary_answer`, `aidd_status.py:1282`) accepts it only as the EXACT string `Aprobar con resumen` (case-sensitive, `str.strip()` equality) AND only when the question carries the tag and an approve word. Any drift (a suffix such as ` (Recommended)`, another wording, a missing tag in that specific question) falls to the answer route and is refused. Nothing prints the exact question/labels to use BEFORE asking. The exact recorded label must be re-read from the b1SycLink evidence log during T-100 to pin which drift happened (do not assume). | agent (ask the right question) |
| E4 | several | `aidd rules check` R5 `Quote not found in any recorded user prompt/answer` | `quote_verified` (`aidd_rules.py:2075`) accepts an earlier event only when it belongs to the ACTIVE session; quotes recorded in a previous session fail. Only the owner can produce a new recorded prompt/answer with those words. Not an approval refusal, but it surfaced in the same round and nobody had listed it before. | owner only |

**Cost:** 4 wasted owner clicks, then repeated agent cycles (fix one cause, re-ask, hit the next cause). Same
duplicate-work class as the shared-test optimisation (spec 008 amendment `verification-economy`).

## Minimum Requirements Checklist

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | Approval gate and its inputs: `skill/scripts/aidd_status.py` (`cmd_approve`, argv dispatch), `aidd_rules.py` (`check_verification`, `_runner`), `check_spec.py`, `aidd_review.py` (CLI flag), `skill/hooks/rule_gate.py` (spec.md edit check); new `skill/scripts/aidd_approve_preflight.py`; mirrors under `adapters/dot-aidd/` | repo — `skill/scripts/aidd_status.py:1413` | — |
| New development or modification? | One new module, five modifications, mirrors by byte copy | repo — `tests/test_dot_aidd_mirror.py:61` | — |
| External service, API, integration? | None (stdlib only, no network) | repo — `CONTRIBUTING.md` (stdlib-only test suite) | — |
| Who is requesting it? | Owner, through the b1SycLink coordinator | user (relayed) — "aidd debe mejorar no obstruir" | owner re-quotes at merge (R5) |
| Dependencies? | spec 007 FR-204/FR-205/FR-207; spec 008 FR-307/FR-309/FR-312/FR-313 (called, not changed) | repo — `skill/scripts/aidd_status.py:1198-1532` | — |
| Business objective | Zero owner clicks spent on a question the agent could have made valid; every refusal cause listed at once with its exact fix | user (relayed) — "no gastar un clic del owner en algo que el agente puede resolver" | — |
| Expected visual fidelity | No visual surface (CLI text only); Steps 0/1/1.5 skipped | repo — no SCREEN code touched | — |

## Executive summary

- **Objective:** move every approval refusal BEFORE the owner's click: one read-only `aidd rules approve --preflight`
  that lists all causes at once, a question builder that refuses to print while preflight fails, an R10 Verification
  check at edit/`check_spec` time, a safe `--fix --apply` for the mechanical causes, and an explicit
  agent-fixable / owner-only split.
- **Scope:** CLI and gate scripts above, their mirrors, tests, and the SKILL.md / CORE.md approval paragraph.
- **Not in scope:** changing what counts as consent (the trust root of FR-204 stays), relaxing `quote_verified`
  (open decision OD-4), the hook `_approval_gate` route for hand-written `Approved:` lines (it keeps its own checks).
- **Cost:** 10 tasks (T-100..T-109), about 3 h agent time, about 520k tokens, 4 waves.
- **Risks:** (1) `--fix` edits spec.md: limited to the Verification table, mapping-table driven, dry-run first,
  post-check; (2) preflight and approve could drift: approve CALLS preflight, and a test asserts both report the same
  cause set on every fixture; (3) a relaxed label match would weaken consent: NOT proposed (OD-2 is the owner's).
- **Open decisions:** OD-1..OD-5 below.

## Functional requirements

| Code | Requirement | Source |
|---|---|---|
| FR-270 | **Design rule "help, don't obstruct" (applies to every gate refusal of `aidd rules approve`, and is the rule future gates follow).** (1) A cause is detected at the EARLIEST point where its inputs exist: spec.md edit / `check_spec.py` for Verification rows, `aidd review` generation for review causes, preflight for everything else; never first at `approve`. (2) A refusal lists ALL its causes in ONE run, each with the exact command or edit that fixes it. (3) When a fix is mechanical and safe (FR-275, FR-276, FR-280), AIDD offers it as `--fix` (dry-run) / `--fix --apply` (write + post-check), never silently. (4) No owner click is requested while any agent-fixable cause is open: the question builder (FR-278) refuses to print the question. Owner-only causes are listed apart, grouped into one owner action list. | user (relayed) — "aidd debe mejorar no obstruir" |
| FR-271 | New module `skill/scripts/aidd_approve_preflight.py`, stdlib only, with `preflight(spec_dir, root=None, session=None) -> list[dict]`. It is READ-ONLY (writes nothing: no spec file, no evidence event, no page) and never raises (an internal error becomes one cause `P99`, `owner_only=False`, `blocks='approve'`). Each cause dict has exactly the keys `id` (catalogue id, FR-281), `rule` (`R1`/`R5`/`R6`/`R10`), `owner_only` (bool), `blocks` (`approve` \| `build` \| `advisory`), `message` (one line), `fix` (one exact command or edit instruction), `autofix` (bool). Causes are returned in catalogue order, de-duplicated by `(id, message)`. Consent is NOT a cause: when every other check passes the function returns `[]`. | evidence E1-E4 |
| FR-272 | CLI `aidd rules approve --preflight <spec_dir> [--json]` (dispatched in `aidd_status.main`; `aidd rules` is already a passthrough in `aidd/cli.py:175`). Text output: one line per cause `CAUSE <id> <AGENT\|OWNER> <rule> <message> FIX: <fix>`, then one summary line `PREFLIGHT ready=<yes\|no> agent=<n> owner=<m> advisory=<k> tag=[tasks:<h8>]`. `--json` prints `{"ready": bool, "tag": str, "causes": [...]}`. Exit codes: 0 = `ready` (no cause with `blocks='approve'`; only the owner's consent remains); 1 = at least one `blocks='approve'` cause; 3 = usage error / not a spec dir. `advisory` and `build` causes are printed but never change the exit code. `aidd review <spec_dir> --preflight` is an alias that calls the same function (the existing `--check` line stays byte-identical, FR-309). | brief (a) |
| FR-273 | `cmd_approve` calls `preflight` first. If any `blocks='approve'` cause exists it prints ALL of them in the FR-272 line format, then `Refused: <n> cause(s); fix them, then run \`aidd rules approve --preflight <spec>\` until it exits 0, then ask the question printed by \`aidd rules approve-question <spec>\`.` and exits 1, WITHOUT reading consent. Only when preflight is ready does it evaluate consent (unchanged code from FR-204/FR-313). Invariant: for every fixture, the set of cause ids that make `approve` refuse equals the set `preflight` reports with `blocks='approve'`. | evidence E2 (first-fail return) |
| FR-274 | `aidd rules approve --preflight <spec_dir> --fix` prints the planned changes (dry run, unified diff of spec.md's `## Verification` table and the list of commands it would run) and writes nothing. `--fix --apply` applies ONLY causes with `autofix=True`, in catalogue order, then re-runs `preflight` (post-check) and prints its result as in FR-272; exit code = the post-check's. It never writes `review.md`, an `Approved:` line, `.aidd/` or any evidence event, and never edits any spec.md section other than the cells named in FR-275/FR-276. | owner — "ofrecer un arreglo mecánico automático cuando sea seguro" |
| FR-275 | Expected-cell normalisation (autofix, Verification rows only). Mapping table, matched case-insensitively on the stripped cell after removing surrounding backticks: `0 FAIL`, `0 FAILED`, `0 failures`, `0 errors`, `PASS`, `PASSED`, `OK`, `exit code 0`, `exit 0.`, `returns 0`, `rc=0` → `exit 0`. Any other invalid Expected stays a manual cause (`autofix=False`). The applied mapping is listed in the dry run. (Semantic equivalence `0 FAIL` ≡ `exit 0` holds only when the runner exits non-zero on failure: OD-1.) | evidence E1 |
| FR-276 | "Same command" expansion (autofix). A Command cell matching `^same(?: as (?:row )?(?P<ref>V?-?\d+))?(?: with (?P<args>.+))?$` (case-insensitive, backticks stripped) is replaced by the referenced row's command (default: the nearest previous row whose command passes `verification_command_problem`) followed by one space and `args`, with these limits: when the referenced command already contains an option named in `args` (same leading `--name`), that option and its value are REPLACED, not duplicated; the result must pass `verification_command_problem`, otherwise the cause stays manual (`autofix=False`, message names the reason). | evidence E1 |
| FR-277 | Lint false negative: `_runner` accepts `npm` with `--prefix <dir>` or `--prefix=<dir>` anywhere BEFORE the subcommand (`test`, `t`, `run <script>`, `run-script <script>`), and checks the manifest `<dir>/package.json` (relative, inside root, via `_safe_rel` and `_inside_exists`); a missing `<dir>/package.json` returns `npm --prefix <dir> but <dir>/package.json does not exist`. No other runner changes. | evidence E1 (`aidd_rules.py:2676`) |
| FR-278 | Question builder `aidd rules approve-question <spec_dir> [<spec_dir> ...]` (1 to 4 specs; AskUserQuestion's maximum). For each spec it runs `preflight`; if ANY spec is not ready it prints the causes of every non-ready spec (FR-272 format), prints `Refused: no question printed; fix the causes above first.` and exits 1. When all are ready it prints ONE JSON object `{"questions": [...]}` ready to paste into a single AskUserQuestion call, one question per spec: `question` = `Aprobar las tareas de <spec_id>? <tag>` (exactly one tag, the current `[tasks:<h8>]`), `header` = `<spec_id>` truncated to 12 chars, `multiSelect` false, `options` = `[{"label": "Approve", "description": "Aprueba spec, plan y tareas de <spec_id> con hash <h8>"}, {"label": "No aprobar", "description": "Deja <spec_id> sin aprobar"}]`, plus the waiver option `{"label": "Aprobar con resumen", ...}` ONLY when OD-3 says so and the spec has no review page. It also prints one line `NOTE: copy the labels exactly; do not add (Recommended) or any suffix; one question per spec.` Exit 0. | brief (b); evidence E3 |
| FR-279 | Early detection of R10 rows. (a) `check_spec.py` reports every `check_verification` violation of a spec that has a `tasks.md` as a gap `R10 Verification row <n>: <message>` (exit 1), for approved and unapproved specs alike (legacy specs whose spec.md has no `## Verification` heading AND whose tasks.md carries an `Approved:` line older than gate 2 are exempt, the same exemption `check_verification`'s callers use today). (b) `rule_gate.py`, on a write/edit of a `specs/<id>/spec.md`, blocks only violations the edit INTRODUCES (same before/after set difference already used for `check_content` at `rule_gate.py:923-925`), with the FR-272 fix text; pre-existing violations are never a new block. (c) `aidd review <spec_dir>` (page generation) prints, after its current output, one line `PREFLIGHT ready=... agent=<n> owner=<m>` and the cause lines, without changing its exit code. | brief (c); owner — "detectarse lo antes posible (al promover/editar, no al aprobar)" |
| FR-280 | Stale review (autofix for the agent part, one command for the owner part). When `review_state.reason` starts with `review.md was generated for tasks hash`, `review.md was generated for sources digest`, `review.md is older than review.html`, `no review page` while a `review.md` exists, or `page stale`, preflight emits TWO causes: `P07` (agent, `autofix=True`, fix = `aidd review specs/<id>`, regenerates the page; FR-312 carry-over keeps unchanged items checked) and `P08` (owner, fix = exactly `aidd review specs/<id> --wait` (run by the agent in the background) + `owner: open specs/<id>/review.html and press "Aprobar y guardar"; <n> item(s) changed`). `<n>` = number of items NOT carried over by `carry_decision` (`aidd_review_items.py:980`); when it cannot be computed the text says `changed items: unknown`. No other route regenerates or edits review.md. | brief (d); evidence E2 |
| FR-281 | Cause catalogue (single source, constant `CAUSES` in `aidd_approve_preflight.py`; id → `rule`, `owner_only`, `blocks`, `autofix`): `P01` tasks.md missing (R1, agent, approve, no); `P02` tasks.md not R1-valid, one cause per violation (R1, agent, approve, no); `P03` spec.md has no `## Verification` or no row (R10, agent, approve, no); `P04` Verification Expected invalid (R10, agent, approve, yes iff FR-275 maps it); `P05` Verification command invalid (R10, agent, approve, yes iff FR-276 expands it to a valid command); `P06` visual source error (R4/R6, agent, approve, no); `P07` review page missing/stale for the current sources (R6, agent, approve, yes); `P08` owner must (re)complete the review (R6, owner, approve, no); `P09` review cannot be shown, `too many items` (R6, agent, approve, no; fix = split the spec or `--full`, see OD-5); `P10` R5 quote not recorded in a usable session (R5, owner, build, no); `P11` other `aidd rules check` violations (rule as reported, agent, build, no); `P99` internal error (—, agent, approve, no). `owner_only=True` causes are never auto-applied and never paired with a command the agent runs on the owner's behalf. | owner — "distingue claramente lo que solo el owner puede resolver" |
| FR-282 | R5 cross-session quotes (`P10`): preflight runs the R5 quote check of `check_spec_dir` and, for every failing quote, says whether the exact words exist in a recorded prompt/answer of ANOTHER session (`found in session <first 8 chars> on <date>`) or nowhere; fix text: `owner: say these words again in this session (one message), or confirm in the approval question` only if OD-4 allows confirming quotes inside the approval question; otherwise only the first form. Blocks `build` (as today), never `approve`. | evidence E4 |
| FR-283 | Docs: `skill/SKILL.md` (R6 row and "Approval" / "Review before approval" paragraphs) and `adapters/dot-aidd/CORE.md` (approval paragraph) say, in this order: run `aidd rules approve --preflight specs/<id>` until exit 0 (use `--fix`, then `--fix --apply` for autofix causes); then `aidd rules approve-question specs/<id> [...]` and paste its JSON into ONE AskUserQuestion; never write the approval question by hand; then `aidd rules approve specs/<id>`. `skill/AIDD.md` and `adapters/dot-aidd/AIDD.md` get the same sentence in the Step 4→5 approval section. | brief (a)(b) |

## Acceptance criteria

| Code | Scenario | Expected (measurable) |
|---|---|---|
| AC-401 | Fixture spec with 4 simultaneous causes: tasks.md R1 violation, Expected `0 FAIL`, Command `same with --only-tests x`, stale review (tasks hash differs) | ONE `aidd rules approve --preflight` run prints ≥ 5 `CAUSE` lines (P02, P04, P05, P07, P08), exit 1; `aidd rules approve` on the same fixture prints the same ids and exits 1 |
| AC-402 | Every fixture of the matrix in T-100 (one per catalogue id, plus "all clear") | set of `blocks='approve'` ids from `preflight` == set of ids printed by `cmd_approve` before `Refused:` (FR-273 invariant); 0 mismatches |
| AC-403 | "All clear" fixture + a recorded `Approve` answer to the question built by `approve-question` | `preflight` exit 0, then `aidd rules approve` exit 0 and writes `Approved:`: **0 refusals after a passed preflight** across the matrix |
| AC-404 | Preflight run on any fixture | mtime and sha1 of every file under the fixture's `specs/<id>/` and `.aidd/` are identical before and after (read-only) |
| AC-405 | Every `CAUSE` line in the matrix | has a class (`AGENT`/`OWNER`), a rule and a non-empty `FIX:` text; 100 % of lines |
| AC-406 | `--fix` (dry run) on the AC-401 fixture | prints a diff touching only lines inside `## Verification` and the command `aidd review specs/<id>`; writes nothing (AC-404 check) |
| AC-407 | `--fix --apply` on the AC-401 fixture | afterwards P04, P05, P07 are absent; P02 and P08 remain; spec.md differs from before only inside the `## Verification` table; review.md and tasks.md bytes unchanged |
| AC-408 | FR-275 mapping: each of the 11 listed Expected values; plus `0 FAIL somewhere` | the 11 become `exit 0`; the 12th stays a manual P04 (`autofix` false) |
| AC-409 | FR-276: `same with --only-tests f40_` after row `python tools/db_verify.py --only-tests all`; `same as V-1 with -k foo` ; `same` with no valid previous row | 1st → `python tools/db_verify.py --only-tests f40_` (option replaced, not duplicated); 2nd → V-1 command + ` -k foo`; 3rd stays manual with a reason |
| AC-410 | FR-277: `npm --prefix web run test -- a.test.ts` and `npm --prefix=web test` with `web/package.json` present; same without it | first two: `verification_command_problem` returns None; third: the FR-277 message |
| AC-411 | `approve-question` on a non-ready spec | exit 1, no `{"questions"` text in stdout, cause lines printed |
| AC-412 | `approve-question` on 2 ready specs | exit 0; stdout JSON has 2 questions; each `question` contains exactly one `[tasks:<h8>]` equal to that spec's current tag; each first option label is exactly `Approve`; no label contains `(Recommended)` |
| AC-413 | Recorded answer event built from AC-412's JSON with label `Approve` for both questions | `aidd rules approve` succeeds for both specs (per-question tag binding) |
| AC-414 | `check_spec.py` on a spec with an invalid Verification row and a tasks.md | exit 1 and a gap line starting `R10 Verification row` |
| AC-415 | `rule_gate` on an Edit of spec.md that adds a row `same with x` | blocked with the R10 message; an Edit of an unrelated section of a spec.md that ALREADY has that row is not blocked |
| AC-416 | `aidd review specs/<id>` on the AC-401 fixture | prints the `PREFLIGHT ready=no ...` line; exit code identical to before this amendment |
| AC-417 | Stale-review fixture with 10 items, 3 changed | P08 text says `3 item(s) changed`; P07 `autofix` true; after `--fix --apply`, `aidd review --check` reports a current page (state pending, not stale) |
| AC-418 | R5 fixture: quote present only in a prompt of another session | P10 line says `found in session <8 chars>`, class `OWNER`, blocks `build`; preflight exit 0 if nothing else blocks |
| AC-419 | `aidd review <spec> --check` on all fixtures | byte-identical output and exit code to the pre-amendment version (FR-309 untouched) |
| AC-420 | Mirror | `python -m unittest tests.test_dot_aidd_mirror -v` exit 0 with `aidd_approve_preflight.py` in `VERBATIM_SCRIPTS` |

## Verification

| # | Command | Expected | Covers |
|---|---|---|---|
| V-1 | `python -m unittest discover -s tests -p "test_approve_preflight.py" -v` | exit 0 | T-100..T-105, AC-401..AC-413, AC-416..AC-419 |
| V-2 | `python -m unittest tests.test_aidd_rules_r10 tests.test_check_spec -v` | exit 0 | T-101, T-106, AC-410, AC-414 |
| V-3 | `python -m unittest tests.test_rule_gate tests.test_hooks -v` | exit 0 | T-107, AC-415 |
| V-4 | `python -m unittest tests.test_aidd_status tests.test_aidd_review tests.test_aidd_review_state tests.test_cli_rules -v` | exit 0 | no regression of FR-204/FR-309/FR-313 |
| V-5 | `python -m unittest tests.test_dot_aidd_mirror -v` | exit 0 | T-108, AC-420 |

Synthetic temporary directories only (as `tests/gate_fixtures.py` does); no database, Docker, network or real
evidence log. Heavy full-suite run (`python -m unittest discover -s tests`) only once per round by the verifier, not
per task.

## Out of scope

Changing the consent trust root (what counts as the owner's act); relaxing `APPROVE_LABEL` or `_SUMMARY_EXACT_RE`
(OD-2); relaxing the R5 session rule (OD-4); the hook route for hand-written `Approved:` lines
(`rule_gate._approval_gate`); `aidd rules close` / `abandon`; unit approvals (`--unit`); b1SycLink files.

## Open decisions for the owner

| # | Decision | Default proposed in this draft |
|---|---|---|
| OD-1 | May `--fix` rewrite Expected `0 FAIL`/`PASS`/`OK` to `exit 0` (FR-275)? It is equivalent only when the runner exits non-zero on failure (true for `db_verify.py`, unittest, pytest, npm test). | yes, dry-run first, listed in the diff |
| OD-2 | Should the consent matcher tolerate a host-appended suffix such as ` (Recommended)` on `Approve`/`Aprobar con resumen`? | NO (keeps the trust root strict); the builder prevents the drift instead |
| OD-3 | Should `approve-question` offer the waiver `Aprobar con resumen` (FR-313) when no review page exists? | no; only `Approve` / `No aprobar` |
| OD-4 | R5 quotes recorded in an earlier session: keep "owner repeats the words" (today), or let the approval question carry a quote-confirmation question (counts as a recorded answer)? | keep today's rule; preflight only reports it early |
| OD-5 | FR-279(b): block NEW invalid Verification rows at spec.md edit time, or only warn? | block introduced rows only (same pattern as `check_content`) |
| OD-6 | Code numbering: FR-270..FR-283 continue 007's FR-2xx range; AC-2xx is exhausted (AC-299) and AC-3xx belongs to 008, so this draft uses AC-401..AC-420 and tasks T-100..T-109. | accept |

---

# Tasks — amendment 07

Every task prompt restates: implement only this task; never assume (stop and report on any ambiguity); read the
"Read first" files before writing; tests first (they must fail for the right reason); never weaken a check or a
test; one responsibility per function, snake_case, module-private helpers with a leading underscore; fail closed
(every file read in `try/except (OSError, UnicodeDecodeError, ValueError)`); **tools first**: mirrors by byte copy
(`cp`), bulk edits by script with dry-run / apply / post-check, never by hand; **work databases**: none are used
here, `db_verify.py` is never run and no database is created; no `aidd verify` by the builder; no git commit, push,
stash, checkout or reset; never write `review.md`, `review.html`, an `Approved:` line or anything under `.aidd/`.

Analysis parameters: `aidd size --files skill/scripts/aidd_approve_preflight.py skill/scripts/aidd_status.py
skill/scripts/aidd_rules.py skill/scripts/check_spec.py skill/scripts/aidd_review.py skill/hooks/rule_gate.py
tests/test_approve_preflight.py` → expected L (gate area, mirrors).

| Task | Codes satisfied | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-100 | FR-270..FR-282, AC-401..AC-413, AC-416..AC-419 | `tests/test_approve_preflight.py` | LOGIC | | | any production code |
| T-101 | FR-277, AC-410 | `skill/scripts/aidd_rules.py` + `tests/test_aidd_rules_r10.py` | LOGIC | | | any runner other than `npm`; `check_verification` |
| T-102 | FR-271, FR-281, FR-282, AC-402, AC-404, AC-405, AC-418 | `skill/scripts/aidd_approve_preflight.py` (new) | LOGIC | | | any write; `--fix`; the CLI |
| T-103 | FR-272, FR-273, AC-401..AC-403, AC-419 | `skill/scripts/aidd_status.py` | LOGIC | | | consent code (`_consent`, `_summary_answer`, `affirmative_answer` calls) |
| T-104 | FR-274, FR-275, FR-276, FR-280, AC-406..AC-409, AC-417 | `skill/scripts/aidd_approve_preflight.py` | LOGIC | | | any section of spec.md outside `## Verification`; review.md |
| T-105 | FR-278, AC-411..AC-413 | `skill/scripts/aidd_status.py` | LOGIC | | | the consent matchers (OD-2) |
| T-106 | FR-279(a)(c), AC-414, AC-416 | `skill/scripts/check_spec.py` + `skill/scripts/aidd_review.py` + `tests/test_check_spec.py` | LOGIC | | | `--check`, `--wait`, `--comments` output |
| T-107 | FR-279(b), AC-415 | `skill/hooks/rule_gate.py` + `tests/test_rule_gate.py` | LOGIC | | | `_approval_gate`; any other rule |
| T-108 | mirror of T-101..T-107, AC-420 | `adapters/dot-aidd/scripts/{aidd_approve_preflight,aidd_status,aidd_rules,check_spec,aidd_review}.py` + `adapters/dot-aidd/hooks/rule_gate.py` + `tests/test_dot_aidd_mirror.py` | LOGIC | | | any non-byte-copy change except one list entry |
| T-109 | FR-283 | `skill/SKILL.md` + `skill/AIDD.md` + `adapters/dot-aidd/AIDD.md` + `adapters/dot-aidd/CORE.md` | LOGIC | | | any other section |

Waves: wave 13 = T-100, T-101 (parallel: different files); wave 14 = T-102; wave 15 = T-103, T-104, T-106, T-107
(T-103 and T-105 share `aidd_status.py`: T-105 goes to wave 16); wave 16 = T-105, T-108, T-109.

## Per-task detail

### T-100 — failing tests first
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2
- Kind: LOGIC
- Size: M

**Estimate**
- Effort: Medium
- Agent min: 35
- Human ref hours: 2.0
- Tokens (est): 110k
- Agent role: tests
- Model tier: medium
- Wave: 13

**Detail**
- Goal: encode AC-401..AC-413 and AC-416..AC-419 as unit tests that fail on today's code.
- Cites: FR-270..FR-282, AC-401..AC-413, AC-416..AC-419.
- Depends on: none.
- Read first: `tests/gate_fixtures.py` (whole file: how a temp project, spec dir, evidence log and recorded answers are built); `tests/test_aidd_status.py` classes `EvBase` and `Spec007Base`; `skill/scripts/aidd_status.py` lines 1160-1532; `skill/scripts/aidd_review_state.py` lines 380-420; `skill/scripts/aidd_review_items.py` function `carry_decision` (line 980). Before writing the E3 fixture, read the b1SycLink evidence answer event of F21 ONLY through `aidd status` / the coordinator (do not open b1SycLink files) and record the exact label in the test docstring; if unavailable, test both `Aprobar con resumen (Recommended)` and a question without the tag.
- Files to change: `tests/test_approve_preflight.py` (new).
- Naming contract: class `ApprovePreflight(unittest.TestCase)` with methods `test_all_causes_in_one_run` (AC-401), `test_approve_and_preflight_same_causes` (AC-402), `test_zero_refusals_after_ready` (AC-403), `test_preflight_is_read_only` (AC-404), `test_every_cause_has_class_and_fix` (AC-405), `test_fix_dry_run_writes_nothing` (AC-406), `test_fix_apply_then_postcheck` (AC-407), `test_expected_mapping` (AC-408), `test_same_command_expansion` (AC-409), `test_question_refused_when_not_ready` (AC-411), `test_question_two_specs_exact_labels` (AC-412), `test_question_answer_approves_both` (AC-413), `test_review_generation_prints_preflight` (AC-416), `test_stale_review_counts_changed_items` (AC-417), `test_r5_other_session_is_owner_advisory` (AC-418), `test_review_check_unchanged` (AC-419). Production names exercised: `aidd_approve_preflight.preflight(spec_dir, root=None, session=None)`, `aidd_approve_preflight.CAUSES`, `aidd_approve_preflight.plan_fixes(spec_dir, root=None) -> dict`, `aidd_approve_preflight.apply_fixes(spec_dir, root=None) -> list[dict]`, `aidd_status.main(argv)` with argv `['rules','approve','--preflight',<dir>]`, `['rules','approve','--preflight',<dir>,'--json']`, `['rules','approve','--preflight',<dir>,'--fix']`, `['rules','approve','--preflight',<dir>,'--fix','--apply']`, `['rules','approve-question',<dir>,...]`.
- Behaviour:
  1. Import `aidd_approve_preflight` inside each test (it does not exist yet: each test fails individually).
  2. Matrix helper `_fixture(kind)` builds one temp project per catalogue id P01..P11 plus `clear`, using `gate_fixtures` helpers only.
  3. For AC-402 iterate the matrix; capture `aidd_status.main(['rules','approve',d])` stdout; parse ids from `CAUSE <id>` lines; compare with `{c['id'] for c in preflight(d) if c['blocks']=='approve'}`.
  4. For AC-404 hash (sha1) and stat every file under `specs/` and `.aidd/` before/after.
  5. For AC-419 compare `aidd_review.main([d,'--check'])` stdout/exit with values captured from a frozen expectation written in the test (state line format of FR-309).
- Tests first: this task IS the tests; run V-1 and keep the red output (every test fails or errors on current code).
- Verify: `python -m unittest discover -s tests -p "test_approve_preflight.py" -v` → red before T-102; exit 0 after T-105.
- Do NOT: touch production code; use the real `.aidd/` of the repo, a database, Docker or the network; weaken an assertion later.
- Done when: the 16 tests exist with these names and the red run is recorded by the verifier.
- Size: ~150 changed lines (fixture helpers may go to `tests/gate_fixtures.py` only if T-100 cannot fit; then say so in the report).
- Open questions: none.

### T-101 — `npm --prefix` lint fix
**Classify**
- Nature: `BUG`
- Priority: 2
- Kind: LOGIC
- Size: XS

**Estimate**
- Effort: Low
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 30k
- Agent role: builder
- Model tier: medium
- Wave: 13

**Detail**
- Goal: `npm --prefix <dir> run test` and `npm --prefix=<dir> test` are accepted when `<dir>/package.json` exists.
- Cites: FR-277, AC-410.
- Depends on: none.
- Read first: `skill/scripts/aidd_rules.py` lines 2569-2712 (`_find_manifest`, `_safe_rel`, `_inside_exists`, `_runner`, `_names_existing_file`).
- Files to change: `skill/scripts/aidd_rules.py`; `tests/test_aidd_rules_r10.py` (3 new cases, written first).
- Naming contract: new private helper `_npm_prefix(rl) -> tuple[str|None, list[str]]` returning `(prefix_dir_or_None, rl_without_prefix_tokens)`; `_runner` calls it only when `exe == 'npm'`.
- Behaviour:
  1. Scan `rl` left to right until the first token not starting with `-`; `--prefix <v>` or `--prefix=<v>` sets the prefix and both tokens are removed.
  2. If a prefix is set: the subcommand test of line 2676 runs on the stripped list; manifest check = `_safe_rel(prefix)` and `_inside_exists(root, prefix + '/package.json', want_file=True)`; failure message exactly `npm --prefix <dir> but <dir>/package.json does not exist`.
  3. With `root is None` the prefix form returns True (existence not checkable, as today).
- Tests first: `test_npm_prefix_run_test`, `test_npm_prefix_equals_test`, `test_npm_prefix_missing_manifest` in `tests/test_aidd_rules_r10.py`; red before the change.
- Verify: `python -m unittest tests.test_aidd_rules_r10 -v` → exit 0.
- Do NOT: change any other runner branch, `_TRIVIAL_RE`, `_FORBIDDEN_*` or `check_verification`.
- Done when: the 3 tests pass and the rest of `test_aidd_rules_r10` stays green.
- Open questions: none.

### T-102 — `preflight()` and the cause catalogue (read-only)
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2
- Kind: LOGIC
- Size: M

**Estimate**
- Effort: High
- Agent min: 35
- Human ref hours: 2.5
- Tokens (est): 90k
- Agent role: builder
- Model tier: high
- Wave: 14

**Detail**
- Goal: one read-only function that returns every refusal cause of `aidd rules approve` plus R5/build advisories.
- Cites: FR-271, FR-281, FR-282, AC-402, AC-404, AC-405, AC-418.
- Depends on: T-100, T-101.
- Read first: `skill/scripts/aidd_status.py` lines 1413-1497 (the order of today's checks: this function must reproduce each, without returning early); `skill/scripts/aidd_rules.py` `check_content` (1328), `check_verification` (2769), `check_spec_dir` (1888), `quote_verified` (2075); `skill/scripts/aidd_review.py` `review_state` (1252); `skill/scripts/aidd_review_items.py` `carry_decision` (980).
- Files to change: `skill/scripts/aidd_approve_preflight.py` (new).
- Naming contract: constant `CAUSES: dict[str, dict]` with the 12 ids and fields of FR-281; functions `preflight(spec_dir, root=None, session=None) -> list[dict]`, `_cause(cid, message, fix, autofix=None, rule=None) -> dict`, `_tasks_causes(d)`, `_verification_causes(d, root)`, `_review_causes(d, root, tasks_text)`, `_rules_check_causes(d, root, session)`, `is_ready(causes) -> bool` (no `blocks=='approve'`). Imports of `aidd_rules`, `aidd_review`, `aidd_evidence` are lazy (inside functions) and fall back to cause `P99`.
- Behaviour:
  1. Resolve `root` with `aidd_evidence.find_root(d)` when None, `session` with the same logic as `aidd_status._current_session` (call it lazily; do not copy it).
  2. Run ALL four collectors; concatenate; de-duplicate by `(id, message)`; sort by catalogue order.
  3. Verification rows: for each `check_verification` violation decide P03/P04/P05 by message prefix (`has no`, `Expected`, other); set `autofix` by calling the FR-275/FR-276 planners (stubs returning False until T-104).
  4. Review: map `review_state` exactly as `cmd_approve` does (lines 1445-1473) into P06/P07/P08/P09; `too many items` → P09; stale reasons of FR-280 → P07+P08 with the changed-item count.
  5. R5 quotes → P10 (`blocks='build'`, owner); other `check_spec_dir` violations → P11 (`blocks='build'`).
  6. Never write; never raise (outer `try/except Exception` → `[P99]`).
- Tests first: T-100 tests for this module are red before this task.
- Verify: `python -m unittest discover -s tests -p "test_approve_preflight.py" -v` → AC-404, AC-405, AC-418 tests pass.
- Do NOT: import `aidd_status` at module level (cycle); read `review.md` directly (only through `review_state`); record any evidence event.
- Done when: the listed tests pass; `python -c` import of the module with stdlib only succeeds in a clean interpreter (`python -I`).
- Open questions: none.

### T-103 — CLI `--preflight` and `cmd_approve` reports all causes
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2
- Kind: LOGIC
- Size: S

**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.5
- Tokens (est): 60k
- Agent role: builder
- Model tier: high
- Wave: 15

**Detail**
- Goal: `aidd rules approve --preflight <spec> [--json]` exists, and `aidd rules approve` refuses with every cause at once.
- Cites: FR-272, FR-273, AC-401..AC-403, AC-419.
- Depends on: T-102.
- Read first: `skill/scripts/aidd_status.py` lines 1413-1532 and 3178-3200; `aidd/cli.py` lines 170-180 and 425-435.
- Files to change: `skill/scripts/aidd_status.py`; `aidd/cli.py` (help string of `rules` only).
- Naming contract: `cmd_approve_preflight(spec_arg, as_json=False, fix=False, apply=False) -> int`; `_print_causes(causes, tag) -> None` printing the FR-272 lines; argv forms handled in `main` before the existing `len(argv) == 3` branch: `['rules','approve','--preflight',<spec>]` plus optional `--json`, `--fix`, `--fix --apply` in that order.
- Behaviour:
  1. `cmd_approve`: after resolving `d` and before line 1425, call `preflight(d, root, sess)`; if not `is_ready`, `_print_causes` then the FR-273 `Refused:` line, return 1. Keep the existing checks after it (defence in depth; they now never fire first).
  2. `cmd_approve_preflight` with `fix=False`: print causes and summary; exit 0/1 per FR-272; 3 when not a spec dir.
  3. `fix=True` paths call T-104 functions (until T-104 exists, print `--fix not available` and return 3).
- Tests first: T-100's AC-401..AC-403, AC-419 tests are red before this task.
- Verify: `python -m unittest discover -s tests -p "test_approve_preflight.py" -v` and `python -m unittest tests.test_aidd_status tests.test_cli_rules -v` → exit 0.
- Do NOT: change `_consent`, `_summary_answer`, `_review_fix` texts used by existing tests, or the `Approved:` writing block (1498-1532).
- Done when: listed tests pass and the existing status/cli tests stay green.
- Open questions: none.

### T-104 — `--fix` dry run and `--fix --apply`
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2
- Kind: LOGIC
- Size: M

**Estimate**
- Effort: High
- Agent min: 35
- Human ref hours: 2.5
- Tokens (est): 90k
- Agent role: builder
- Model tier: high
- Wave: 15

**Detail**
- Goal: the safe mechanical causes are fixed by a dry-run / apply / post-check cycle.
- Cites: FR-274, FR-275, FR-276, FR-280, AC-406..AC-409, AC-417.
- Depends on: T-102.
- Read first: `skill/scripts/aidd_rules.py` `parse_verification` (2218) and `_table`/`_split_row` (117-160) to locate the Verification rows by line; `skill/scripts/aidd_review.py` `main` (1507) for regenerating the page in-process.
- Files to change: `skill/scripts/aidd_approve_preflight.py`.
- Naming contract: constant `EXPECTED_EXIT0_ALIASES = ('0 fail', '0 failed', '0 failures', '0 errors', 'pass', 'passed', 'ok', 'exit code 0', 'exit 0.', 'returns 0', 'rc=0')`; regex `SAME_RE = re.compile(r'^same(?: as (?:row )?(?P<ref>V?-?\d+))?(?: with (?P<args>.+))?$', re.I)`; functions `plan_fixes(spec_dir, root=None) -> dict` (keys `spec_diff` str, `commands` list[str], `changes` list[dict]), `apply_fixes(spec_dir, root=None) -> list[dict]` (returns the post-check causes), `_expand_same(cmd, rows, idx) -> str|None`, `_replace_option(base, args) -> str`.
- Behaviour:
  1. `plan_fixes`: read spec.md bytes; for each Verification row compute the new Expected (FR-275) and new Command (FR-276; accept only when `verification_command_problem(new, expected, root)` is None); rebuild ONLY those table lines, preserving EOL, cell padding and every other byte; produce a unified diff (`difflib.unified_diff`, n=0). Add `aidd review specs/<id>` to `commands` when a P07 cause exists.
  2. `apply_fixes`: run `plan_fixes`; refuse (return the causes unchanged, write nothing) if any changed line falls outside the `## Verification` table bounds; write spec.md once (bytes); run the page generator in-process (`aidd_review.main([str(d)])`) for P07; return `preflight(...)`.
  3. Never touch review.md, tasks.md, `.aidd/`.
- Tests first: T-100's AC-406..AC-409, AC-417 tests red before this task.
- Verify: `python -m unittest discover -s tests -p "test_approve_preflight.py" -v` → those tests pass.
- Do NOT: guess a command for `same` without a valid referenced row; normalise any Expected not in the alias list; reformat the table.
- Done when: AC-406..AC-409 and AC-417 pass; a spec.md byte diff after apply is limited to the Verification lines.
- Open questions: none (OD-1 default applies; if the owner rejects OD-1, delete the alias list and the AC-408 test row before building).

### T-105 — question builder `approve-question`
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2
- Kind: LOGIC
- Size: S

**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 50k
- Agent role: builder
- Model tier: medium
- Wave: 16

**Detail**
- Goal: the only approval question text the agent uses is printed by AIDD, and only when every spec is ready.
- Cites: FR-278, AC-411..AC-413.
- Depends on: T-103.
- Read first: `skill/scripts/aidd_status.py` constants lines 60-80 and `approval_tag` (1169); `tests/gate_fixtures.py` helper that records an AskUserQuestion answer event.
- Files to change: `skill/scripts/aidd_status.py`.
- Naming contract: `cmd_approve_question(spec_args) -> int`; `build_approval_questions(spec_dirs) -> dict`; constant `QUESTION_LABEL_APPROVE = 'Approve'`, `QUESTION_LABEL_NO = 'No aprobar'`; argv form `['rules','approve-question', <spec>, ...]` (1..4 specs; 0 or >4 → exit 3 with `Usage: aidd rules approve-question <spec_dir> [<spec_dir> ...] (1 to 4)`).
- Behaviour: exactly FR-278 (texts verbatim); JSON printed with `json.dumps(obj, ensure_ascii=False, indent=2)`; the NOTE line after the JSON.
- Tests first: T-100's AC-411..AC-413 red before this task.
- Verify: `python -m unittest discover -s tests -p "test_approve_preflight.py" -v` → exit 0 (all 16).
- Do NOT: change `APPROVE_LABEL`, `SUMMARY_LABEL`, `_SUMMARY_EXACT_RE` (OD-2); offer `Aprobar con resumen` (OD-3 default).
- Done when: all T-100 tests pass.
- Open questions: none.

### T-106 — early R10 in `check_spec.py` and `aidd review`
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2
- Kind: LOGIC
- Size: S

**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 45k
- Agent role: builder
- Model tier: medium
- Wave: 15

**Detail**
- Goal: invalid Verification rows show up in `check_spec.py` and at page generation, long before approval.
- Cites: FR-279(a)(c), AC-414, AC-416.
- Depends on: T-102.
- Read first: `skill/scripts/check_spec.py` (whole, 699 lines: how gaps are collected and printed); `skill/scripts/aidd_review.py` lines 1470-1611 (`main`, the generation branch).
- Files to change: `skill/scripts/check_spec.py`; `skill/scripts/aidd_review.py`; `tests/test_check_spec.py` (new case `test_r10_verification_rows_are_gaps`, written first).
- Naming contract: `check_spec._verification_gaps(spec_dir) -> list[str]` (lazy import of `aidd_rules`); gap text `R10 Verification row <n>: <message>`; in `aidd_review.py` new private `_print_preflight(spec_dir) -> None` and new mutually-exclusive flag `--preflight` that prints the FR-272 output and returns its exit code.
- Behaviour: `_verification_gaps` applies only when `tasks.md` exists and the legacy exemption of FR-279(a) does not hold; `_print_preflight` is called after successful page generation and never changes the generation exit code.
- Tests first: `test_r10_verification_rows_are_gaps` red; T-100's AC-416/AC-419 red.
- Verify: `python -m unittest tests.test_check_spec tests.test_aidd_review tests.test_aidd_review_state -v` → exit 0.
- Do NOT: alter `--check`, `--wait`, `--comments`, `--summary` output (FR-309).
- Done when: listed tests pass.
- Open questions: none.

### T-107 — block introduced invalid Verification rows on spec.md edit
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: S

**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 45k
- Agent role: builder
- Model tier: high
- Wave: 15

**Detail**
- Goal: an agent cannot add an invalid Verification row to spec.md without being told at once.
- Cites: FR-279(b), AC-415.
- Depends on: T-101.
- Read first: `skill/hooks/rule_gate.py` lines 900-940 (the `check_content` before/after difference).
- Files to change: `skill/hooks/rule_gate.py`; `tests/test_rule_gate.py` (cases `test_spec_edit_adding_bad_verification_row_blocked`, `test_spec_edit_with_preexisting_bad_row_not_blocked`, written first).
- Naming contract: no new public name; private `_verification_introduced(rules, root, cur_text, new_text) -> list[dict]` returning violations in `new` not in `cur` keyed by `(rule, message)`.
- Behaviour: called only when the target is `specs/<id>/spec.md`; violations are appended to the existing list with the FR-272 fix text. With OD-5 = "warn", return them as a non-blocking message instead (the builder applies the owner's answer as written in the approved tasks).
- Tests first: the two cases red.
- Verify: `python -m unittest tests.test_rule_gate tests.test_hooks -v` → exit 0.
- Do NOT: touch `_approval_gate` or any other rule branch.
- Done when: both cases pass and the rest stays green.
- Open questions: none.

### T-108 — mirrors
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: XS

**Estimate**
- Effort: Low
- Agent min: 5
- Human ref hours: 0.25
- Tokens (est): 15k
- Agent role: builder
- Model tier: low
- Wave: 16

**Detail**
- Goal: `adapters/dot-aidd/` carries byte-identical copies.
- Cites: AC-420.
- Depends on: T-101..T-107.
- Read first: `tests/test_dot_aidd_mirror.py` lines 55-140.
- Files to change: byte copies (`cp`) of `skill/scripts/{aidd_approve_preflight,aidd_status,aidd_rules,check_spec,aidd_review}.py` into `adapters/dot-aidd/scripts/` and `skill/hooks/rule_gate.py` into `adapters/dot-aidd/hooks/`; one entry `"aidd_approve_preflight.py",` appended to `VERBATIM_SCRIPTS`.
- Behaviour: copy, then run the verify command; no other edit.
- Tests first: the mirror test fails before the copy once T-102 exists.
- Verify: `python -m unittest tests.test_dot_aidd_mirror -v` → exit 0.
- Do NOT: hand-edit any mirrored file.
- Done when: mirror test green.
- Open questions: none.

### T-109 — docs
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: XS

**Estimate**
- Effort: Low
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 25k
- Agent role: builder
- Model tier: medium
- Wave: 16

**Detail**
- Goal: the approval instructions tell agents to preflight and to use the builder.
- Cites: FR-283.
- Depends on: T-105.
- Read first: `skill/SKILL.md` line 107 (R6 row), 125 (commands), 435-437 (Approval, Review before approval); `adapters/dot-aidd/CORE.md` lines 30-45.
- Files to change: `skill/SKILL.md`, `skill/AIDD.md`, `adapters/dot-aidd/AIDD.md`, `adapters/dot-aidd/CORE.md`.
- Behaviour: insert the FR-283 sentence once in each named place; keep CORE.md under its current size budget (check `tests/` for a size test before editing).
- Tests first: none new; existing doc tests must stay green.
- Verify: `python -m unittest tests.test_dot_aidd_mirror tests.test_generate_adapters -v` → exit 0.
- Do NOT: rewrite surrounding paragraphs.
- Done when: the four files contain `approve --preflight` and `approve-question`.
- Open questions: none.
