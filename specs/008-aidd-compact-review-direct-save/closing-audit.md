CLOSING AUDIT [domains: security, functional, performance] [tasks:e2e2d243] [verify:100a2c23]

# Closing audit (T-05): spec 008, compact review page, direct save, `--wait`, owner-chosen review mode

Auditor: the one independent closing auditor (read-only, implemented nothing). Date: 2026-10-05. Python 3.12, Node 24, Windows 11.
Method: `check_spec.py` (0 mechanical gaps), `git status`, the `aidd:FR-3nn` marker map, a code read of the three review modules, `aidd_status.py`, `rule_gate.py` and both templates, and these executed checks. Every scenario ran in a SCRATCH copy: the repo was copied byte for byte to the scratchpad (all changed files compared equal with `cmp`), and the real b1SycLink specs F28, F23, F13 and F15 were copied read-only into scratch projects. Each scenario used its own evidence log (`AIDD_TESTING=1`, `AIDD_EVIDENCE_DIR`). Outputs are in `evidence/audit-0*.txt`.

## Verdict

The security part holds: the review mode cannot be forged or downgraded, and `review.md` alone never approves. Functional: **two red tests in V-1** and three more defects; they are listed under "Findings". The spec cannot close until findings 1 to 4 are fixed (all are medium).

## Findings (all CONFIRMED by execution)

| # | Sev | Domain | Where | Problem | Fix |
|---|---|---|---|---|---|
| 1 | medium | functional | `skill/scripts/aidd_review_state.py:161` | `_cap_comment` joins the lines of a comment that spans several `> ` lines with a space. FR-309(b) and AC-318 require ` / `. Result: `--comments` prints `FR-001: SENTINEL-COMMENT - [x] FR-002`. **V-1 is red:** `test_aidd_review.TestRealModules.test_ac317_states_and_exits_both_ids` (`tests/test_aidd_review.py:1263`) fails. | Join with `'\n'` at l.161 (`comment_lines` already turns `\n` into ` / `). Update the docstring and the T-07 tests, then mirror the file. |
| 2 | medium | functional | `tests/test_aidd_review.py:56`; `specs/008.../spec.md` FR-301 and AC-314; `plan.md:89` | The 5-digit amendment (`API/COMP/CTL/SCREEN-\d{1,5}`) reached `aidd_review_items.CODE_RE`, the page `CODE_RE_SRC` and two test files, but not this test's literal nor the spec and plan (they still say "1 to 4 digits"). **V-1 is red:** `TestRealModules.test_constants_match_contract` (l.1241) fails. | Update the literal at l.56. Amend FR-301, AC-314 and the plan.md "Code grammar" block to `\d{1,5}` for those four prefixes. |
| 3 | medium | functional | `aidd/cli.py:452` (and `p_review` with `spec_dir` first) | `aidd review --summary <spec>` and `aidd review --check <spec>` fail with argparse `unrecognized arguments`, exit 2. That is exactly the FR-313 form written in the spec Interfaces, `SKILL.md:391` and `AIDD.md:534`. Exit 2 also collides with `--check`'s `pending` code. `aidd review <spec> --summary` works. | Add `"review"` to the passthrough tuple at l.452 (`aidd_review.py`'s own parser already accepts flags in any order), or change every doc to `aidd review <spec> --summary`. |
| 4 | medium | functional | `skill/scripts/aidd_review.py:756` (`_item_html`) | The function looks up `fields['answer']` and `fields['decision']` in lowercase, but the extractor emits `Answer` and `Source`. So `.ans` is never rendered. An unanswered question (F28 `Q11`, `Q12`) shows only its question text: no "pending - resolve in Align" text, and the CSS cue `.aidd-item[data-unanswered] .ans` never applies. AC-305 fails, and FR-303's purpose "every answer the owner approves is seen" is weakened. | Look up the answer case-insensitively, render it as `.ans`, and render the text `pending - resolve in Align` when `unanswered` is set. Add a test on the F28 shape. |
| 5 | low | docs | `skill/SKILL.md:389`, `skill/AIDD.md:530` | "When no page exists (sources over the size cap, `too many items`) a bare tagged answer is refused" is false for oversize sources. Their 007 answer-only route is kept by design (O-10), and the scratch run printed `approved through answer`. | Say that only `too many items` refuses, and that sources over the 400 000-char cap keep the answer route. |
| 6 | low | security / robustness | `skill/scripts/aidd_review_state.py:312` vs `skill/scripts/aidd_review.py:1103` | When `review.html` has no parseable blob, `evaluate_review` treats its format as `headings-v1` and skips the item cap, while `review_state` computes compact keys. An over-cap spec with such a page reports `STATE=stale`, not `too_many_items`. The agent cannot exploit it: `review.html` is owner-only, and `cmd_approve` and `rule_gate` still refuse a bare answer because a page exists. | Treat a present page whose `page_meta` is `(None, None, None)` as compact for the cap and for the keys (one rule in both places). |
| 7 | info | performance | `aidd_review.review_wait` | `review_state` runs the whole extraction on every call: about 0.4 s on F15 (732 items), 0.14 s on F13, 0.10 s on a 560-item spec. `--wait` pays that once per 2 s poll, about 20 % of one core while it waits. It is not on a per-edit hook path: `rule_gate` calls it only on an `Approved:` edit, and `aidd status` is not called by any hook. | Optional: cache the extraction by sources digest inside `review_wait`. |

## Security checklist

- FR-313 exact-label route.
  - AC-327, run on F23 and F28 through BOTH `cmd_approve` (subprocess) and `rule_gate._approval_gate`: cases (1) and (1b) approve with `source=summary`, never `answer`. Cases (2) to (8) are refused by both routes and record no `approved` event.
  - Regression: `Approve`, `Aprobar`, `Aprobado` and `Aprobar las tareas` still match `APPROVE_LABEL` in both files. A bare `Approve` with no page approves with `source=answer`. A newer `No` cancels an older summary answer.
  - `_summary_answer` reads only `ev._answer_event` with a case-sensitive pattern, plus the option-offered check. It never uses the typed fallback.
- AC-328: a stale page and a current page both approve with `source=summary`. `review.html` is unchanged (same sha1) and no `review.md` is written.
- AC-329: a current page with a bare `Approve` is refused by both routes.
- AC-330: an agent text, a written file, a subagent description, a `<...>` prompt, or a question with no answer is never accepted.
- AC-310: a complete `review.md` alone is refused. An answer recorded after `review.md` approves as `review+answer`. An answer recorded before a re-save is refused. The typed tag gives `review+prompt`.
- Item cap (AC-303), on 2 007 items for both id styles:
  - the compact page is refused and no `review.html` is written;
  - `too many items` wins over `no review.html`;
  - `--check` and `--wait` exit 3;
  - a bare answer and the summary label are refused by `cmd_approve` and `rule_gate`;
  - `--full` is not capped.
- Escaping and CSP (AC-312): one executable script, and its sha256 equals the CSP hash. `<script>`, `{{TOKENS}}` and the `FR-301"><img` cell stay inert, and that cell is not a code. No inline handlers, no `innerHTML`, no `eval`. `review-full.html` keeps its CSP, `application/octet-stream` and `review.md`.
- Picked-folder check (node, real template JS):
  - the same spec and `tasks_hash` writes and reads back;
  - another spec, no `review.html`, an older hash, or a page without a blob writes nothing and names the folder to pick;
  - `AbortError` is silent;
  - `TypeError` retries once without `id`, then shows "Folder picker failed (TypeError)" and downloads `review.md` as `application/octet-stream`;
  - a broken IndexedDB never blocks the save.
- `--check`, `--wait` and `--comments` are read-only, and the outputs carry no sentinel (AC-319). `REVIEW_MESSAGE` has no `cat`.
- Module split: no import cycle. `aidd_review_items` imports only `aidd_rules` and `check_spec`, lazily. `aidd_review_state` imports only stdlib. Neither does file IO or prints. The facade reaches them only through `_items()` and `_state()`.
- Fail closed when a module is missing: with either module deleted, `--check`, `--wait`, `--comments` and `--summary` exit 3 with the reinstall reason and no traceback, and `aidd rules approve` refuses. The default generate mode still writes the page when only `aidd_review_state.py` is missing; that is not an approval path.
- Mirrors: all three review modules, `aidd_status.py`, `aidd_rules.py` and both templates are byte-identical under `adapters/dot-aidd/` (`cmp`), and `test_dot_aidd_mirror` is green. `~/.claude/skills/aidd/scripts` still holds only the 007 `aidd_review.py`; the owner syncs the install after the build.

## Acceptance cases

| AC | Result | Evidence |
|---|---|---|
| AC-301 | PASS: 175 codes (SUMMARY, Q1..Q12, 40 D, 30 FR, 17 AC, 21 API, 49 T, V-1..V-5), 7 tabs without Pantallas, no warnings, no markdown embedded, links to the source files, second run reports `unchanged` | audit-01, audit-02 |
| AC-302 | PASS: no FR or SCREEN placeholder items, the non-standard header is still extracted, `FR-4.1` is named, an empty source gets a warning on Resumen. Note: the template's own example rows `CTL-001`, `T-01` and `T-02` do become items | audit-05 |
| AC-303 | PASS: F13 168 KB, F15 475 KB, never refused; 2 007 items refused (see Security) | audit-04 |
| AC-304 | PASS: the written summary is capped at 400 chars with `...`; absent or empty gives `generated`; byte-deterministic | audit-05 |
| AC-305 | **FAIL** (finding 4): Q1..Q7 and Q8/Q9 extract correctly and the 14-decision-rows warning is correct, but an unanswered question is not rendered as "pending - resolve in Align" | audit-05, F28 page |
| AC-306 | PASS: a forged `- [x] FR-002` inside a comment checks nothing; the JS collapses newlines into ONE `> ` line | audit-02, audit-06 |
| AC-307 | PASS: `STATE=legacy`, exit 3; `aidd rules approve` exit 1 with the cause and no traceback; `--wait` prints one line, exit 2 | audit-02 |
| AC-308 | PASS (node stubs; the native picker is owner-only) | audit-06 |
| AC-309 | PASS: (a) to (f), timeout lines, `review (1).md` untouched | audit-02 |
| AC-310 | PASS | audit-03 |
| AC-311 | PASS: `--full` + a 007 `review.md` gives `legacy` False; the cross pair gives `legacy` True; switching mode regenerates | audit-02 |
| AC-312 | PASS | audit-04 |
| AC-313 | PASS: the section sits right after the checklist; `check_content` is clean for the template and for legacy 006 | audit-05 |
| AC-314 | PASS: Python/JS parity (11 candidates, pattern strings equal); `FR-4.1` warning. The test literal is stale (finding 2) | audit-06, audit-05 |
| AC-315 | PASS: 40 D items; "29 acceptance rows without an AC code" lands on Resumen; Casos is absent | audit-01 |
| AC-316 | PASS: (a) to (d); `parse_review` never raises | audit-02, audit-05 |
| AC-317 | PASS: exact lines and exits on F28, including `too_many_items` with and without a page | audit-02, audit-04 |
| AC-318 | **FAIL** (finding 1): lines are joined with a space, not ` / ` | audit-02, audit-08 |
| AC-319 | PASS | audit-02 |
| AC-320 | PASS: 174 carried, T-17 pending, `review.md` sha1 and mtime unchanged, `STATE=stale` exit 3 | audit-02 |
| AC-321 | PASS: (a) `unchanged`; (b) 175/175 carried | audit-02 |
| AC-322 | PASS | audit-02 |
| AC-323 | PASS: `Falta: Verificación V-1..V-5`, `Falta: Tareas T-17; Verificación V-1..V-5`, `--check` 170/175 exit 2 | audit-02, audit-06, browser-smoke.md (T-06) |
| AC-324 | PASS (code read plus T-06 browser smoke) | browser-smoke.md |
| AC-325 | PASS: (d) Q4..Q13 and SUMMARY pending, the others carried; (a) to (c) by unit tests | audit-02 |
| AC-326 | **FAIL as specified** (finding 3): `aidd review --summary <spec>` exits 2. Content via `aidd review <spec> --summary`: at most 30 labelled lines, deterministic, no sentinel, writes nothing, exit 3 without tasks.md | audit-04, audit-07 |
| AC-327 | PASS | audit-03 |
| AC-328 | PASS | audit-03 |
| AC-329 | PASS | audit-03, audit-04 |
| AC-330 | PASS | audit-03 |
| AC-331 | PASS on content (both docs, help lists `--summary`); the documented command order is broken (finding 3) | SKILL.md:391, AIDD.md:534 |

## Verification rows

- V-1 `python -m unittest discover -s tests`: **FAIL**, 1747 tests, failures=2 (findings 1 and 2). Evidence: `audit-08-full-suite-V1.txt`.
- V-2: both failures are in `tests.test_aidd_review` (TestRealModules), so V-2 is red too.
- V-3 and V-4: green inside the V-1 run.
- V-5: owned by T-06. The auditor did not run it, to avoid two runners on the same working tree. `e2e-transcript.txt` does not yet contain `ROUNDTRIP OK`.

## Delta audit

Auditor: an independent delta auditor. I implemented nothing. I changed nothing except this section and the `evidence/delta-0*.txt` files. Date: 2026-10-05. Python 3.12, Node 24, Windows 11.

Method:
- I copied the repo (`skill/`, `aidd/`, `adapters/`, `tests/`, later `catalog/`, `commands/`, `docs/`) into the scratchpad. Every file under re-check matched the working tree under `cmp`, both before and after the probes, so nothing changed while I worked.
- I copied the real b1SycLink specs F28 and F23 into scratch projects, read-only.
- Every probe ran with `AIDD_TESTING=1`, a per-scenario `AIDD_EVIDENCE_DIR` and `PYTHONDONTWRITEBYTECODE=1`. Nothing ran against the real `.aidd` log.
- Each `review.md` was built by the generated page's own JS (`buildReviewMd`, run under node).

### Re-check of the closing findings

| Item | Result | Executed evidence |
|---|---|---|
| AC-305 (finding 4) | **PASS** | Real F28 copy: the two unanswered Optional Align rows carry `data-unanswered="1"` and `<span class="ans">pending - resolve in Align</span>`. Answered rows render their answer as `.ans`. The CSS cue `[data-unanswered] .ans` is present. `--summary` lists both under `Open decisions`. The F23 copy with one blanked checklist answer gives Q1..Q7 with only Q4 pending, and `Open decisions` names it. The F23 warning `14 decision rows without a D code...` is intact. The regression test `test_real_extractor_f28_shape` exists. Correction to the closing text: in the real F28 file the unanswered rows are **Q10 and Q11** (Entry route, Target devices); Q12 (contract owner) is answered. This does not affect the verdict. (delta-01, delta-03) |
| AC-318 (finding 1) | **PASS** | A two-line hand-edited comment gives `FR-001: line one / - [x] FR-002`. The forged `- [x] FR-002` line checks nothing (FR-002 unchecked stays `pending 174/175`, exit 2). Exits of `--comments`: complete with no comment: empty, 0. One unchecked: empty, 0. Older `tasks_hash`: empty, 3. Older `sources_digest`: empty, 3. Invalid file: empty, 3. Legacy 007 file: empty, 3. No `review.md`: empty, 3. Note: a newline typed in the page is collapsed to a space by `oneLine` (one `> ` line, by design per AC-306 / FR-304). So ` / ` appears only for multi-`> ` files, which is what FR-309(b) specifies. (delta-01) |
| AC-317 exits per state | **PASS** | `--check`: no `review.md`: `pending 0/175`, exit 2. One unchecked: `pending 174/175`, exit 2. Complete with 2 comments: `complete 175/175 comments=2 ... tag=[tasks:5c3cbb5b]`, exit 0. Older hash: `stale`, exit 3. Legacy: `legacy=yes`, exit 3. No page: `stale approved=0/0`, exit 3. 2 004 items: `too_many_items`, exit 3, with and without a compact page. `--wait`: complete: 0. Stale: timeout, exit 2. No page: 3. (delta-01, delta-03) |
| AC-326 + argument order (finding 3) | **PASS** | Through `python -m aidd.cli`, `aidd review --summary <spec>` and `aidd review <spec> --summary` give the same stdout and exit 0. The same holds for `--check`, `--comments` and `--wait`, including mixed orders such as `--wait --interval 0.5 <spec> --timeout 2`. `--summary` content: 13 labelled lines (at most 30), byte-identical when re-run, and `review.md`/`review.html` sha1 unchanged. Without `tasks.md`, both orders exit 3 and create no file. Argparse errors (`--bogus`, `--check --summary`, a missing spec) now exit **1**, so they no longer collide with the `pending` exit 2. (delta-01) |
| 5-digit CTL codes reviewable (finding 2) | **PASS** | Real F23 copy: all 93 `CTL-23nnn` first cells in the sources become items, with no CTL warning. A complete `review.md` that includes them gives `complete 247/247`, exit 0. `--comments` prints `CTL-23001: ...`. Unchecking `CTL-23001` gives `pending 246/247`, exit 2. Python/JS parity holds on 18 candidates: `CTL-15001`, `API-12345`, `SCREEN-12345` and `COMP-00001-b` are accepted. `CTL-150011`, `FR-00001`, `AC-12345` and `T-12345` are rejected. `FR-4.1`, `FR-٣`, `FR-1\n` and `FR-301"><img` are rejected in both. (delta-02) |
| spec/plan/code/test grammar agree | **PASS** | The `plan.md` `CODE_RE` line, `aidd_review_items.CODE_RE.pattern`, the template's `CODE_RE_SRC` (unescaped) and the `tests/test_aidd_review.py` literal are the same string. FR-301 says "1 to 4 digits (`FR`, `AC`, `T`) or 1 to 5 digits (`API`, `COMP`, `CTL`, `SCREEN`)". AC-314 states the 5/6-digit rule. (delta-02) |
| Docs correction 1 (finding 5: SKILL.md:389, AIDD.md:530) | **PASS** | The text now says only `too many items` refuses, and that sources over 400 000 chars keep the 007 answer route. I checked this by execution. For a 410 440-char `spec.md`, generation is refused, no page is written, and `aidd rules approve` after a bare tagged answer exits 0 with `approved through answer` (`source=answer`); `rule_gate` also lets it through (delta-02 run). For 2 004 items, generation is refused, `aidd rules approve` exits 1 (`a review is required ... too many items`), `rule_gate` blocks, and no `approved` event is recorded. (delta-03) |
| Docs correction 2 (finding 3: documented order `aidd review --summary <spec>` in SKILL.md:391, AIDD.md:534) | **PASS** | The docs were kept as they were. The CLI was fixed instead (passthrough at `aidd/cli.py:456`), so the documented form now works. The help text still lists every flag. |
| Mirrors | **PASS** | `cmp` shows `aidd_review.py`, `aidd_review_items.py`, `aidd_review_state.py`, `aidd_status.py`, `aidd_rules.py`, `templates/review.html`, `templates/review-full.html`, `templates/spec.md`, `templates/qa-audit.md` and `AIDD.md` byte-identical between `skill/` and `adapters/dot-aidd/`. `templates/tasks.md` differs by design: it is a reduced variant, excluded at `tests/test_dot_aidd_mirror.py:123`, and neither copy is modified against HEAD. `test_dot_aidd_mirror` is green. (delta-05) |
| V-1 / V-2 | **PASS** | In the scratch copy: 1 751 tests. The first run had 4 failures, all from my partial copy (`catalog/` and `commands/` were missing, which broke `test_marketplace` and `test_generate_adapters`). The rerun with those folders copied is OK. Every `test_aidd_review` test is green, including `TestRealModules.test_ac317_states_and_exits_both_ids` and `test_constants_match_contract`. (delta-04) |

### New regressions

None reproduced. Still open, unchanged and low (closing finding 6): a blob-less `review.html` on a spec with more than 2 000 items still reports `STATE=stale approved=0/2004` instead of `too_many_items`. The exit code is still 3, and both approval routes still refuse. (delta-03)

### Delta verdict

Findings 1 to 5 are fixed and confirmed by execution. AC-305, AC-318 and AC-326 now PASS. With them, AC-314 and AC-331 lose their caveats. V-1 and V-2 are green. Finding 6 (low) and finding 7 (info) remain as accepted residuals. V-5 is still owned by T-06 and was not run here.
