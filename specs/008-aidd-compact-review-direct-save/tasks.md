# Tasks — AIDD 008: compact tabbed review, direct save of review.md, `aidd review --wait`

One row = one owner agent for one file set (plus its mirror and its tests). Codes are the FR-3nn of spec.md (no screens). Every builder prompt restates: scope in/out as stated per row; stop and report if anything is ambiguous; SOLID; names exactly as plan.md's Naming & File Contract and "Exact interfaces"; antifragile (every disk call can fail: degrade, never a traceback, never fail silently); Python stdlib only; UTF-8 and LF on every file IO; match surrounding code style. Source paths are under D:\Fuentes\AIDD\skill unless stated; agents never write `~/.claude` or `.aidd/`.

**Mirror rule (tests/test_dot_aidd_mirror.py):** the owner of `skill/scripts/{aidd_review_items,aidd_review_state,aidd_review,aidd_status,aidd_rules}.py` (T-01, T-07, T-08, T-03) copies the file byte-identical over `adapters/dot-aidd/scripts/` in the same task; the owner of `templates/review.html` and `templates/review-full.html` copies them to `adapters/dot-aidd/templates/` (T-02 is the SINGLE owner of tests/test_dot_aidd_mirror.py: it adds the `("templates", "review-full.html")` pair to `PAIRS` and `"aidd_review_items.py"`, `"aidd_review_state.py"` to `VERBATIM_SCRIPTS`: the test lists scripts and templates by name, so the entries are required); T-04 copies `AIDD.md` and `templates/spec.md` (NEVER `templates/tasks.md`: the dot-aidd copy is a reduced variant). `rule_gate.py` has no mirror. The `.aidd/` project install and `~/.claude/skills/aidd` are synced by the owner after the build.

**Test rule:** subagents run only the test files named in their own row of the run-line column below, never `tests.test_dot_aidd_mirror` and never `tests.test_aidd_rules` (the first turns red transiently while another task moves a template or a script, the second checks the spec template that T-04 is editing in the same wave); each owner checks its own mirror copies byte-identical with `cmp`. The main agent runs `tests.test_dot_aidd_mirror` plus the wave's own test files at the end of wave 1 (`tests.test_aidd_review` WITHOUT `AIDD_REVIEW_FAKES_ONLY`, so the `TestRealModules` integration class checks the three review modules together; a red goes back to the owner of the module that breaks the frozen contract before wave 2) and `python -m unittest discover -s tests` once at the end of every later wave. Only one runner at a time on this working tree. The tests that must be REWRITTEN (not just extended) are named in the owner's task and listed in plan.md "Tests that change". `qa-audit.md` (R10) has ONE owner, the main agent at close; no task writes it.

Run lines (subagent): T-01 `python -m unittest tests.test_aidd_review_items`; T-07 `python -m unittest tests.test_aidd_review_state`; T-08 `python -m unittest tests.test_aidd_review` with the environment variable `AIDD_REVIEW_FAKES_ONLY=1`; T-02 `python -m unittest tests.test_review_template`; T-03 `python -m unittest tests.test_aidd_status tests.test_rule_gate`; T-04 none (grep for pinned text, the main agent runs the suite); T-05 none (read-only audit); T-06 `python tests/e2e_review_roundtrip.py`.

**Real project ids:** every path/guard test uses BOTH a numeric id (`002-aidd-hard-rules`) and a non-numeric one (`F23-eDoc-POS`), absolute and relative paths; the real-case fixtures use `F28-DB-Unification-Sync` (tasks hash `5c3cbb5b`).

| Task | Codes satisfied | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-01 | FR-301, FR-302, FR-311, FR-312, FR-313 | NEW scripts/aidd_review_items.py + adapters/dot-aidd/scripts/aidd_review_items.py; tests: NEW tests/test_aidd_review_items.py | LOGIC | | | aidd_review.py, aidd_review_state.py (never imported); any file IO; the HTML templates; any other file |
| T-07 | FR-304, FR-306, FR-309, FR-312, FR-313 | NEW scripts/aidd_review_state.py + adapters/dot-aidd/scripts/aidd_review_state.py; tests: NEW tests/test_aidd_review_state.py | LOGIC | | | aidd_review.py, aidd_review_items.py (never imported); any file IO; any other file |
| T-08 | FR-301, FR-303, FR-304, FR-306, FR-309, FR-312, FR-313 | scripts/aidd_review.py + adapters/dot-aidd/scripts/aidd_review.py; aidd/cli.py (help text only); tests: tests/test_aidd_review.py | LOGIC | | | aidd_review_items.py, aidd_review_state.py (used only through `_items()`/`_state()` and fakes); the HTML templates (T-02 owns them); aidd_status.py; rule_gate.py; any other file |
| T-02 | FR-303, FR-304, FR-305, FR-308, FR-310, FR-311, FR-312 | templates/review.html, templates/review-full.html + adapters/dot-aidd/templates/ copies; tests: tests/test_review_template.py, tests/test_dot_aidd_mirror.py (`PAIRS` entry for review-full.html, `VERBATIM_SCRIPTS` entries for the two new modules) | VIEW-new | | | aidd_review.py, aidd_review_items.py, aidd_review_state.py; any markdown rendering (compact page embeds none; the full page keeps its server-side rendering); any other file |
| T-03 | FR-301, FR-304, FR-307, FR-309, FR-313 | scripts/aidd_status.py, scripts/aidd_rules.py + adapters/dot-aidd/scripts/ copies; hooks/rule_gate.py; tests: tests/test_aidd_status.py (`Spec007Base.review()/page()`), tests/test_rule_gate.py (`make_review`) | LOGIC | | | consent logic, approval hash, R6 gate decisions, verify/close gate (messages, fixtures, the fail-closed `too many items` route and the FR-313 exact-label summary route only); aidd_review.py; tests/gate_fixtures.py, tests/test_cli_rules.py, tests/test_typed_confirmations.py, tests/test_aidd_rules.py (hold no review.md fixture: not edited); any other file |
| T-04 | FR-302, FR-307, FR-308, FR-309, FR-313 | SKILL.md, AIDD.md, templates/spec.md + adapters/dot-aidd copies of AIDD.md and templates/spec.md | LOGIC | | | scripts, hooks, templates/tasks.md, tests/test_dot_aidd_mirror.py (T-02 owns it), the external skill aidd-converge |
| T-05 | FR-301..FR-313 | audit: ONE closing auditor, domains security + functional + performance as a checklist (no file writes except its report) | LOGIC | | | any code edit |
| T-06 | FR-303, FR-304, FR-305, FR-306, FR-309, FR-310, FR-312 | tests/e2e_review_roundtrip.py + evidence files under the spec dir | LOGIC | | | any production file |

T-01, T-07 and T-08 are the former single `aidd_review.py` task split by module (plan.md "Module split"), so wave 1 runs 4 builders in parallel. T-05 and T-06 run after the whole build; the fix batch (CONFIRMED medium+ findings only, back to each file's original owner via SendMessage, about 10 min) is not counted below. The close of spec 008 itself goes through the 007 flow (this spec is approved with the 007 page and a typed or tagged confirmation, because the new flow is not installed yet).

## Per-task detail

### T-01
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC
**Estimate**
- Effort: High
- Agent min: 26
- Human ref hours: 1.3
- Tokens (est): 125k
- Agent role: builder
- Model tier: high
**Decompose**
- Objective: NEW pure module `skill/scripts/aidd_review_items.py`: every code shape real specs use becomes exactly one item in the right tab, nothing coded is dropped silently, plus the executive summary data, the item digests and the carry-over rule (plan.md "Exact interfaces", `aidd_review_items.py` table). No file IO, no print, never imports `aidd_review` or `aidd_review_state`.
- Activities:
  1. Constants and the "Code grammar" block of plan.md (`CODE_RE`, `GENERIC_CODE_RE`, `PLACEHOLDER_RE` anchored `^[A-Z]+-[nNxX]+(?:-F[nNxX]+)?$`, `FIELD_ROW_RE`, every one compiled with `re.ASCII` and used with `fullmatch`; `MAX_ITEMS = 2000` and the other caps; `TAB_ORDER`, `TAB_LABELS`); `_rules()`/`_check_spec()` lazy loaders built like the 007 `_rules()` (`check_spec` optional, local fallback).
  2. `_short`, `_iter_tables` (every table separately, own header, nearest heading; NOT `check_spec._find_table` and NOT `aidd_rules._tables_all`), `_first_token`, `extract_items` exactly as in plan.md (returns `tabs`, `items`, `order` with `SUMMARY` first, `warnings`; rows from every table, first occurrence wins, repeats counted in one line, tasks from table rows plus `### T-nn` blocks, uncoded-row warnings for `acceptance cases` and `decisions` tables, FR-311 `verification` tab from `## Verification` with `V-n` rows `mandatory` and a blank Command = no item), `_questions` (Q rows, then Optional Align rows through `_iter_tables`, then `D<n>` decision rows in the same tab), `_completeness`; every extractor wrapped; warnings are `{tab, text}` and name the skipped codes (first 8); a non-empty source with 0 items adds a Resumen warning; `extract_items` never refuses (the cap is the callers').
  3. `exec_summary_section`, `build_summary` (FR-302); `item_digest` on the full row `canon` (FR-312); `carry_decision(prev_lines, prev_blob_digests, new_digests, order)` (carried only when all three digests are equal; `prev_lines` is the ONE merged map `{code: {'approved', 'comment', 'digest'}}` that T-08's `_carry_over` builds from `parse_review`'s separate `sections` and `digests`; a malformed entry is not carried); `target_files(tasks_text)` and `wave_count(tasks_text)` (FR-313). `aidd:FR-3nn` markers on each function.
  4. tests/test_aidd_review_items.py (NEW) for the T-01 row of plan.md "Tests that change", fixtures rebuilt from the REAL files (not from invented shapes): `F28-DB-Unification-Sync` (Q1..Q12, 40 D, 30 FR with `FR-004b/c`, 17 AC with `AC-007b`, 21 API, 49 T, no Pantallas tab, generated summary, `V-1..V-5`, 175 codes); `F23-eDoc-POS` (Q1..Q7 only, no Optional Align, uncoded decision rows and 29 uncoded acceptance rows reported by warning, Casos tab absent); `F13` shapes (`AC-01`, `AC-25`, `AC-01-b`), `F15` shapes (`AC-01a`, `API-<nnn> fe_param`, `SCREEN-<nn>-F<nn>` field row, two FR tables, a flow table repeating `SCREEN-<nn>`); `T-1`; `FR-4.1` reported by the completeness check; two Optional Align tables; template-only spec; summary written/absent/empty/capped on `002-aidd-hard-rules`; the shared CODE_RE candidate list (`FR-004b`, `AC-01-n`, `V-5`, `D24b`, `FR-4.1`, `FR-٣`, `FR-1\n`, `FR-301"><img`) on the Python side; AC-325, AC-320..AC-322 on `carry_decision`. Both id styles where a path or id appears.
  5. Copy aidd_review_items.py byte-identical to adapters/dot-aidd/scripts/, check it with `cmp`, and run ONLY `python -m unittest tests.test_aidd_review_items` (not the mirror test: see the Test rule).

### T-07
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC
**Estimate**
- Effort: Medium
- Agent min: 22
- Human ref hours: 1.1
- Tokens (est): 90k
- Agent role: builder
- Model tier: high
**Decompose**
- Objective: NEW pure module `skill/scripts/aidd_review_state.py`: the review.md grammars (`codes-v2` and the 007 `headings-v1`), the approval-state decision with the fixed early-check order and the legacy semantics, the one-line status, the exit codes, the comment lines and the FR-313 summary text (plan.md "Exact interfaces", `aidd_review_state.py` table). Stdlib only, no file IO, no print, never imports `aidd_review` or `aidd_review_items`.
- Activities:
  1. Constants (`FORMAT_COMPACT`, `FORMAT_FULL`, `MAX_REVIEW_MD_BYTES` moved from aidd_review.py, `MAX_COMMENT`, `MAX_COMMENT_LINES`, `STATES`, `EXIT_BY_STATE`, `SUMMARY_MAX_LINES`).
  2. `parse_review(text, code_re)`: move the body of the 007 `aidd_review.parse_review` (front matter, `_BLOCK_RE`/`_CHECK_RE` headings-v1 grammar unchanged) and add `format` (missing = `headings-v1`, unknown = error) and the `codes-v2` body (line fullmatch with `re.ASCII`, code accepted only when `code_re.fullmatch` passes, optional ` @d8` into `digests`, `> ` comments capped); never raises, refuses > 2 MB.
  3. `evaluate_review(inp)`: move the decision part of the 007 `review_state` (every 007 field and reason kept) and add `format`, `page_format`, `legacy`, `item_count`, the two legacy reasons and the fixed order (item cap FIRST when the page is not `--full`, then `no review.html`), exactly as in plan.md; it reads only the documented `inp` keys (defaults for missing ones) and never raises.
  4. `derive_approval(rs, tag)`, `status_line(st)` (exact one-line format), `exit_for(state)`, `comment_lines(rs)` (exit 0 only for present AND valid AND not legacy AND `hash_ok` AND `digest_ok`), `summary_lines(summary, files, waves)` (at most 30 labelled lines, `n/a` for missing pieces, deterministic). `aidd:FR-3nn` markers on each function.
  5. tests/test_aidd_review_state.py (NEW) for the T-07 row of plan.md "Tests that change": the 007 `TestParseReview` cases re-pointed here; `code_re` compiled in the test from the "Code grammar" literal (NOT imported from `aidd_review_items`); `inp` dicts built by hand; summary dicts shaped as the `build_summary` contract built by hand; the shared golden review.md string (same text as in tests/test_review_template.py); AC-316 a-d, AC-317 (each state's exact line by the full-line regex and its exit), AC-318, the no-page + 2 001-item order case, AC-326 line shape.
  6. Copy aidd_review_state.py byte-identical to adapters/dot-aidd/scripts/, check it with `cmp`, and run ONLY `python -m unittest tests.test_aidd_review_state`.

### T-08
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC
**Estimate**
- Effort: Medium
- Agent min: 26
- Human ref hours: 1.3
- Tokens (est): 100k
- Agent role: builder
- Model tier: high
**Decompose**
- Objective: `aidd_review.py` becomes the facade over the two new modules: IO, the compact page data blob, `--full` (the unchanged 007 heading renderer), the FR-312 carry-over wiring, `--wait`, and the CLI flags whose output is only the one-line state (FR-309), keeping every public name consumers import (plan.md "Exact interfaces", `aidd_review.py` table).
- Activities:
  1. `_items()`/`_state()` lazy loaders (never imported at module import time; `ImportError` = fail-closed reason and CLI exit 3); wrappers `parse_review(text)`, `status_line`, `review_comments`, `approval_state`, `summary_lines(spec_dir)`; `reviewable_keys(spec_dir, full=False)`; `_page_meta` 3-tuple (missing `format` = `headings-v1`); `_approval_tag`.
  2. `review_state(spec_dir)`: the IO half of the 007 function, building `inp` with exactly the contract keys (`item_count` computed from `_items().extract_items` whenever the page is not `--full`, also with no page; keys for the page format) and returning `_state().evaluate_review(inp)`.
  3. `build_html`/`generate` with `full`: compact reads `templates/review.html`, `full=True` reads `templates/review-full.html` and the unchanged heading renderer; data blob `format`, `picker_id = 'aidd-' + sha1(spec)[:8]`, `tabs`, `codes`, `warnings` (rendered per plan.md), `digests`, `summary`, `prior`/`carry` from `_carry_over` computed BEFORE the old page is overwritten (an explicit `prior` still wins); `_carry_over` does the explicit merge step of plan.md: `parse_review` returns `sections` and `digests` separately, `carry_decision` expects ONE map, so build `prev_lines = {code: {'approved', 'comment', 'digest': digests.get(code)}}` from `sections` (no ` @d8` = `'digest': None`, never carried; `{}` unless `ok`, `codes-v2`, same `spec`) and read the previous blob `digests` before overwriting; idempotence on digest + hash + format; the over-cap `ValueError('too many items (N > 2000): split the spec or run aidd review <spec> --full')`, nothing written; item text through `_esc`, source links only from the fixed `SOURCES` tuple.
  4. `review_wait` (read-only, silent while polling, ONE `status_line` on exit 0/2/3) and `main`: `--full`, `--wait`, `--comments`, `--summary`, `--timeout`, `--interval`; `--check` prints ONLY the status line and exits `exit_for(state)`; `--comments` prints only `<CODE>: <comment>` lines (nothing when there are none); `--summary` writes nothing, exit 3 without tasks.md; remove `_print_state` and `_check_exit`; update the `p_review` help string in `aidd/cli.py` (spec first, then flags).
  5. tests/test_aidd_review.py for the T-08 row of plan.md "Tests that change": retire the 007 `TestParseReview` class (it moves to T-07's file) and keep only facade cases; fakes of `_items()`/`_state()` that return the documented shapes (`mock.patch.object`), never the real unfinished modules; `--full` page and heading grammar (port the 007 cases behind `full=True`); HTML safety; `review_wait` with an injected clock and sleeper for AC-309 (a)-(f); `TestRealModules` written against the frozen contract and skipped when `AIDD_REVIEW_FAKES_ONLY=1` (AC-317 exits, AC-319 sentinel, AC-326 `--summary`, `generate`/`review_state` on F28). Both id styles for every path test.
  6. Copy aidd_review.py byte-identical to adapters/dot-aidd/scripts/, check it with `cmp`, and run ONLY `python -m unittest tests.test_aidd_review` with the environment variable `AIDD_REVIEW_FAKES_ONLY=1` (the main agent runs it without the variable at the end of wave 1).

### T-02
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: VIEW-new
**Estimate**
- Effort: High
- Agent min: 30
- Human ref hours: 1.5
- Tokens (est): 180k
- Agent role: builder
- Model tier: high
**Decompose**
- Objective: the compact tabbed page (owner-confirmed tab list), the direct File System Access save with the always-`review.md` download fallback, and the unchanged long page under its new file name.
- Activities:
  1. Move the current `templates/review.html` to `templates/review-full.html` and apply the three edits of plan.md (Blob type `application/octet-stream`, name `review.md`, `format: headings-v1` in the front matter); keep its CSP and constant script.
  2. Write the new `templates/review.html`: the nine `{{TOKEN}}`s, the unchanged CSP policy string with `{{SCRIPT_SHA256}}`, tabs and item markup contract, per-tab badges and `n / N` progress with `aria-live`, `Approve` (disabled with `N pending`), `Save draft`, per-tab and global bulk checks that skip `data-mandatory`, localStorage keyed spec:tasks_hash:sources_digest in try/catch, `prior` keyed by code, sessionStorage for the last tab in try/catch, phone width 360 px with a scrollable tab bar and 44 px targets, dark theme, print shows all panels, `<noscript>` text describing the new grammar; ONE constant `<script id="aidd-js">` with `CODE_RE_SRC` (the same string as Python `CODE_RE.pattern`), the pure `pickerId` and `buildReviewMd` (exported for node) and `saveReview` exactly as in plan.md (permission and picker first in the click handler; picker `id` = `pickerId(data)`, always 1..32 chars of `[A-Za-z0-9_-]`, never built from the raw slug; non-Abort picker errors retry once without `id` and then show the visible "Folder picker failed (<name>)" line before the download; folder validation by `review.html`, write + read-back + compare, IndexedDB errors mean no memory, `AbortError` silent with the fallback offered, overwrite notice when the existing review.md has another `tasks_hash`); render the per-tab `aidd-warn` lists the generator emits; no `innerHTML` with data, no `eval`, no inline handler, no external URL.
  2b. Owner requirements and critic fixes on the compact page (plan.md "Buttons", `missingSummary`, `folderMatches`): ONE final button `aidd-approve` labelled `Guardar progreso` until every item (V rows included) is checked, then `Aprobar y guardar`; with items missing a click shows `Falta: ...` (`role="alert"`), scrolls to and focuses the first pending item, saves `approved: false` and says `Progreso guardado (a/n): no es una aprobación`; remove `Save draft`, the global bulk control and the text `Approve all (except mandatory)`; per-tab `Aprobar todo en esta pestaña`, disabled on `Verificación` with its one-line explanation, never checking `data-mandatory` (`SUMMARY`, `V-n`); before writing, the picked folder's `review.html` must pass `folderMatches` (same `spec` AND `tasks_hash`), the remembered handle too; `buildReviewMd` writes ` @<digest>` per line; Resumen shows `Arrastrados N de M; pendientes: ...` from `carry`; `CODE_RE_SRC` parity list under node.
  3. Copy both templates to adapters/dot-aidd/templates/ and check them with `cmp`; add the `("templates", "review-full.html")` pair to `PAIRS` and `"aidd_review_items.py"`, `"aidd_review_state.py"` to `VERBATIM_SCRIPTS` in tests/test_dot_aidd_mirror.py (you are its only owner) but do NOT run that test inside the wave (see the Test rule; the main agent runs it at the end of wave 1).
  4. tests/test_review_template.py for both templates: `CODE_RE_SRC` equals the plan.md "Code grammar" literal (and `aidd_review_items.CODE_RE.pattern` when that module is importable: the main agent's end-of-wave run), `pickerId` for `F28-DB-Unification-Sync` (the stub picker throws `TypeError` for an id over 32 chars or outside `[A-Za-z0-9_-]`, like Chromium), `F13-eDoc-Emission-Engine` and a blob without `picker_id`, retry-without-id and visible message when the stub always throws `TypeError`, tokens, exact CSP policy and hash substitution, one executable script of constant text, no external resource, no `text/markdown` download type left, every `showDirectoryPicker`/`indexedDB`/`localStorage`/`sessionStorage` use inside try or a feature test, UI markers (`role="tablist"`, `role="tab"`, `role="tabpanel"`, `aria-selected`, `application/octet-stream`, `maxlength`), mirrors identical, node (skip with a message when missing): `buildReviewMd` golden string shared with test_aidd_review_state, one line per code, `format: codes-v2`, single-line `> ` comments with embedded newlines/CRLF, a comment `---` or `- [x] FR-1` cannot forge a check, empty codes, all checked = `approved: true`, order preserved, `FR-004b` and `D24b` lines kept while a non-code key is dropped, ids `002-aidd-hard-rules` and `F23-eDoc-POS`. Run ONLY `python -m unittest tests.test_review_template`.

### T-03
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC
**Estimate**
- Effort: Medium
- Agent min: 30
- Human ref hours: 1.5
- Tokens (est): 150k
- Agent role: builder
- Model tier: medium
**Decompose**
- Objective: the approval path tells the owner the new flow (page saves review.md, agent waits, ONE tagged question), the two fixtures that really write `review.md` use the new grammar, and a spec the compact page cannot show can never be approved by a bare tagged answer; consent logic is untouched.
- Activities:
  1. `aidd_status.py`: reword `_review_fix`, the `cmd_approve` refusals (complete review without consent: "run `aidd review specs/<id> --wait` in the background; when it returns ask ONE question with the tag <tag>"; legacy review.md: the regenerate message as the Cause), `_review_text` (states `waiting for owner` and `legacy review.md (regenerate)`), `_review_summary` (adds `legacy`), and the WHY-blocked line; `_consent`, `_tty_confirm`, `approval_tag`, evidence fields and the oversize (`source too large`) answer-only route are NOT changed. The ONE logic addition: in `cmd_approve` (~l.1035-1038) `review_route` is also true when the reason starts with `too many items`.
  2. `rule_gate.py`: reword the R6/R10 messages, the USER_ONLY text and the unblock text; in `REVIEW_MESSAGE` (~l.80-86) REMOVE "Reading the files (cat, `aidd review --check`) is fine" and say instead that agents never read review.md/review.html and only run `aidd review <spec> --check`, `--wait` or `--comments` (FR-309 d), with a test that `REVIEW_MESSAGE` does not contain `cat`; keep or update in the same task every substring pinned by tests; the ONE logic addition: `_review_page_blocks_answer` (~l.411-422) returns True for a reason starting `too many items`, before the `source too large` check. `aidd_rules.py`: only the R10 fix string; `approval_evidence` untouched.
  3. Rewrite the two fixtures that really write `review.md`: `Spec007Base.review()`/`page()` in tests/test_aidd_status.py (~l.1367-1390) and `make_review` in tests/test_rule_gate.py (~l.2098; it calls the REAL default template through `AR.generate(self.sd)`, so it needs T-02's finished compact `review.html`) to emit `format: codes-v2` and one `- [x] <code>` line per `reviewable_keys(d)` code, then update the reason-substring assertions. `tests/gate_fixtures.py`, `tests/test_cli_rules.py`, `tests/test_typed_confirmations.py` and `tests/test_aidd_rules.py` contain no review.md fixture: do NOT edit them. New tests: legacy review.md refused with the regenerate Cause and no traceback (cmd_approve exit 1, rule_gate R6, `aidd status --json` field `legacy`), a complete review.md without consent still refused for both id styles, `note: FR-301: <comment>` printed, `aidd review specs/<id> --wait` allowed and `... --wait > specs/<id>/review.md` blocked by rule_gate, and an over-cap spec (2 001 coded rows) NOT approvable by a bare tagged AskUserQuestion answer in `cmd_approve` (with and without a `review.html` in the folder: with none, the `too many items` reason must win over `no review.html`) and blocked by `rule_gate` (`_review_page_blocks_answer`), while a `source too large` spec keeps its 007 answer-only route.
  3b. FR-313, exactly the table of plan.md "FR-313 summary route" (verify the cited lines first: `aidd_status.py` l.62, l.1038, l.1056-1069; `rule_gate.py` l.61, l.335-376; `aidd_evidence.py` l.1305, l.1336-1339, l.1362, l.1370). (i) `aidd_status.py`: `SUMMARY_LABEL = 'Aprobar con resumen'`; `APPROVE_LABEL` gains the negative lookahead `(?!\s+con\s+resum)`; NEW `_summary_answer(ev, root, session, since, tag)` that reads answers only through `ev._answer_event` (case-sensitive exact pattern, never `affirmative_answer`, never `typed_approval`) and returns the event only when a pair has a question matching `APPROVE_TOPIC` with the tag and `str(a).strip() == SUMMARY_LABEL`; in `cmd_approve`, after the `too many items` refusal and BEFORE the `review_route` split, call it with `since = tm` and on a hit approve with `source='summary'`, `consent_ts` = the answer ts, no `review_sha1` (so both the page branch and the no-page branch are covered). (ii) `rule_gate.py`: the same lookahead on the string `APPROVE_LABEL`; NEW delegate `_summary_answer(ev, root, session, since, tag)` (lazy `import aidd_status` from `SCRIPTS_DIR`, any error = None); call it right after `rs` is normalised (~l.335-341), when the reason does not start `too many items`, BEFORE `if rs.get('complete')` (~l.342) and so before `_review_page_blocks_answer(d, rs)` (~l.365); on a hit mint `ev.append_approved(..., **rules.approval_evidence(spec_t, 'summary', consent_ts=...))` and return `[]`. `_review_page_blocks_answer` keeps its signature. Tests in tests/test_aidd_status.py and tests/test_rule_gate.py for AC-327 cases (1)-(8) and AC-328..AC-330, with both `002-aidd-hard-rules` and `F23-eDoc-POS`: exact label (and with outer spaces) approves with `source=summary` in the event, never `answer`; case, typo and extra word refused AND not approved by the generic route or the typed fallback; missing/older tag refused; a tagged question without `aprobar`/`approve` refused; a typed `Aprobar con resumen [tasks:<h8>]` prompt gives no `source=summary`; stale page, current page and complete review.md + exact label approve with `summary`; current page + bare `Approve` refused; over-cap spec refuses the label; delegate returns None when `aidd_status` cannot be imported; agent-forged text (assistant message, a file the agent wrote, a forged evidence line, a Bash echo) not accepted; regression: `Approve`, `Aprobar`, `Aprobado`, `Aprobar las tareas` still match `APPROVE_LABEL` and the no-page bare `Approve` route still approves with `source=answer`.
  4. Copy aidd_status.py and aidd_rules.py byte-identical to adapters/dot-aidd/scripts/, check them with `cmp`, and run ONLY `python -m unittest tests.test_aidd_status tests.test_rule_gate` (not test_aidd_rules nor the mirror test: see the Test rule; the main agent runs the full suite at the end of the wave).

### T-04
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3 MEDIUM
- Kind: LOGIC
**Estimate**
- Effort: Low
- Agent min: 17
- Human ref hours: 0.85
- Tokens (est): 70k
- Agent role: docs
- Model tier: medium
**Decompose**
- Objective: the docs and the spec template describe the executive summary and the new owner flow exactly as the finished code behaves.
- Activities:
  1. `templates/spec.md`: add `## Executive summary` right after the Minimum Requirements Checklist section (a `##` heading so the checklist scan ends before it): labelled bullets Objective, Scope, Cost, Risks, Open decisions, one sentence on caps and on the mechanical fallback for legacy specs; tool-agnostic wording; copy to adapters/dot-aidd/templates/.
  2. `SKILL.md` and `AIDD.md` (+ copy of AIDD.md): the flow of FR-307 (summary BEFORE the first `aidd review`, because any edit to spec.md changes the digest; `aidd review`; `--wait` in the background; the owner presses Approve on the page; the agent asks ONE tagged question after `--wait` returns, so the consent is newer than review.md; `aidd rules approve`), that a complete review.md alone never approves, that typed line and TTY are fallbacks, that a legacy review.md is rejected with "regenerate", that `--full` is the old page, direct save works on Chrome/Edge and other browsers download `review.md`, and the CLI line lists `--full`, `--wait` and `--comments`. FR-309 rule, verbatim in both files: agents NEVER Read, `cat`, `type`, grep or open `review.md` or `review.html`; they only run `aidd review <spec> --check` / `--wait` (one `STATE=` line) and, only when it says `comments>0`, `aidd review <spec> --comments`; when `--wait` returns `STATE=complete` they ask ONE tagged AskUserQuestion with the `tag=` value (the owner's click is the consent; review.md alone never approves). Also, verbatim in both: run `aidd review <spec> --comments` BEFORE editing any source file, because once a source changes review.md is stale and `--comments` prints nothing. Describe the page as the owner sees it: final button `Guardar progreso` / `Aprobar y guardar` with the `Falta: ...` list, `Aprobar todo en esta pestaña`, Verification rows checked by hand, and that regenerating keeps the checks of unchanged items (only changed or new items return to pending; the owner still presses the button and the agent still asks ONE tagged question). Grep tests for text they assert (`approve [tasks:`, `review.md`) before editing.
  2b. FR-313 protocol in `SKILL.md` and `AIDD.md`: before approval ask ONE AskUserQuestion whose QUESTION text contains the word `aprobar` or `approve` next to `[tasks:<h8>]` (for example `¿Aprobar las tareas [tasks:<h8>]?`; say why: the tool matches the approval topic on the question text only, never on the option labels, so a question without that word does not count) with exactly two options `Revisar en HTML visual` (only then run `aidd review <spec>`, wait with `--wait`, then the one tagged consent click) and `Aprobar con resumen` (run `aidd review --summary <spec>` and show its output INSIDE the question; the owner's click is the approval, recorded with `source=summary`; the label must be exactly `Aprobar con resumen`: any variant starting `aprobar con resum` is refused by every route); never generate the page unprompted; never choose the option for the owner; never Read review files. List `--summary` in the CLI line (AC-331).
  3. Copy AIDD.md and templates/spec.md byte-identical to adapters/dot-aidd/ and check them with `cmp`. Do not run any unittest and do not touch tests/test_dot_aidd_mirror.py (T-02 owns it); the main agent runs `tests.test_dot_aidd_mirror` and `tests.test_aidd_rules` (template passes `check_content('spec')`) at the end of the wave.

### T-05
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC
**Estimate**
- Effort: Medium
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 80k
- Agent role: auditor
- Model tier: high
**Decompose**
- Objective: one independent closing audit of the finished change, first line `CLOSING AUDIT [domains: security, functional, performance] [tasks:<h8>] [verify:<v8>]`, never on the lowest tier.
- Activities:
  1. Security checklist: `--wait` and the page never write approval evidence and the agent still cannot write `review.md`; a complete review.md alone approves nothing; consent newer than review.md; escaping, CSP hash and constant script in BOTH templates; hostile code cells and comments; picked-folder validation and read-back; legacy and wrong-format files fail closed with no traceback; an over-cap spec (`too many items`) cannot be approved by a bare tagged answer in `cmd_approve` or `rule_gate`; `aidd_review.py` fails closed (reason + exit 3, never a traceback) when `aidd_review_items.py` or `aidd_review_state.py` is missing; FR-313: only the exact hook-recorded label (`str.strip() == SUMMARY_LABEL`, answers only via `_summary_answer`, no typed fallback) on a question with `aprobar`/`approve` and the current tag mints `source=summary`; near-misses (`aprobar con resumen`, `Aprobar con resumem`, `Aprobar con resumen ya`) are refused by every route, including the generic tagged-answer route and its typed fallback (`APPROVE_LABEL` lookahead in `aidd_status.py` AND `rule_gate.py`), so none approves with `source=answer`; the summary check precedes both `cmd_approve` branches and the complete branch of `rule_gate`; the gate delegate fails closed without `aidd_status`; `_carry_over` merges `sections` + `digests` and never carries a line without ` @d8`.
  2. Functional checklist: every FR-301..FR-313 and AC-301..AC-331 (FR-313: exact-label summary route only for the hook-recorded owner answer, page never generated for mode 2, `--summary` <= 30 lines and writes nothing) (including the carry-over never writing review.md and never carrying a changed/new/re-added code, the folder check by spec + tasks_hash, `V-n` never bulk-checked) (including: `--check`/`--wait` print one status line only, `--comments` only commented codes, the docs rule against reading review.md/review.html) against the code and the tests (no source file written, only the report); both id styles; mirrors identical (all three review modules: `aidd_review.py`, `aidd_review_items.py`, `aidd_review_state.py`, listed in `VERBATIM_SCRIPTS`); module split as frozen in plan.md (`aidd_review_items` and `aidd_review_state` do no file IO, never print, import neither each other nor `aidd_review`; `aidd_review` reaches them only through `_items()`/`_state()`; every public name consumers import still lives in `aidd_review` with its plan.md signature; `TestRealModules` ran green, not skipped, in the main agent's runs); `--full` still works for a 007-era review.md; the code-shape and completeness behaviour against real b1SycLink files read-only (F28, F23, F13, F15: no coded row silently dropped, skipped codes named); the picker `id` is valid for the longest real slugs.
  3. Performance checklist: page size and extraction time on a fixture shaped like `F13-eDoc-Emission-Engine` (151 headings, 84 KB tasks.md) and one shaped like `F15-eDoc-Backoffice-Web` (about 540 coded rows); `MAX_ITEMS` refusal; `review_state` cost per call (it extracts once, and `rule_gate` calls it on edits); `--wait` poll cost.
  4. Report CONFIRMED / PLAUSIBLE findings with file:line; no code edits.

### T-06
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC
**Estimate**
- Effort: Medium
- Agent min: 18
- Human ref hours: 0.9
- Tokens (est): 85k
- Agent role: tests
- Model tier: medium
**Decompose**
- Objective: the whole flow executed end to end on a scratch project, plus one real-browser smoke of the compact page.
- Activities:
  1. Rewrite tests/e2e_review_roundtrip.py: generate a compact page for a scratch `F23-eDoc-POS` and `002-aidd-hard-rules` project, run the real `buildReviewMd` under node (skip with a message when missing), parse with `aidd_review.parse_review`, node DOM stub (or jsdom if present) with a fake `showDirectoryPicker` writing into the scratch spec dir, then `aidd review --wait` as a subprocess whose whole stdout is ONE `STATE=complete ... tag=[tasks:<h8>]` line, `aidd review --comments` printing only the commented codes, and `aidd rules approve` still refused without the consent act and accepted with a recorded tagged answer newer than review.md; fallback cases (no picker: a Blob named `review.md` of type `application/octet-stream`; `AbortError`: nothing written; a picked folder of another spec: nothing written); a partial save (`approved: false`, `--check` exit 2) and a regenerate after editing one `T-n` row (only that code pending in the new blob's `prior`, review.md untouched). Prints `ROUNDTRIP OK` only when every step passed.
  2. One real-browser smoke with the browser tool on `file:///.../review.html` of the scratch project: tabs switch with the keyboard, empty tabs are absent, a code can be checked and commented, the button reads `Guardar progreso` and shows `Falta: Verificación V-...` while V rows are unchecked and `Aprobar y guardar` when all are, `Aprobar todo en esta pestaña` is disabled on Verificación, the fallback download is named `review.md`; save screenshots under `specs/008-aidd-compact-review-direct-save/evidence/` and write a line saying the native folder picker is owner-only.
  3. Run `python tests/e2e_review_roundtrip.py`; no production file is edited (a defect goes back to the owner of the file via SendMessage).

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-01, T-02, T-07, T-08 | builder | 30 | 495 | 1.5 |
| 2 | T-03, T-04 | builder, docs | 30 | 220 | 1.5 |
| 3 | T-05, T-06 | auditor, tests | 18 | 165 | 0.9 |

Dependency edges: T-03 needs T-01, T-07, T-08 and T-02 (its fixtures use `reviewable_keys`/`review_state` of the three review modules, and `make_review` renders the real compact `review.html`); T-05 needs T-01..T-04, T-07, T-08; T-06 needs T-01, T-02, T-03, T-07, T-08. T-01, T-07, T-08 and T-02 have no incoming edge and touch disjoint files: they meet at the frozen contract of plan.md (T-01 and T-07 are pure modules tested with literals and never import each other; T-08 tests the facade with fakes of `_items()`/`_state()` and a minimal inline `template_text`; T-02 tests against a hand-built data blob and the shared golden string). The end-of-wave-1 `TestRealModules` run by the main agent is an integration gate, not an edge. Wave 1 is bounded by T-02 (30 min); the old 45-min T-01 is gone from the critical path. T-04 has no code edge; it is in wave 2 only so its prose reads the finished code. Wave 3 audits and executes only what exists.

Total agent time (critical path): 78 min
Total tokens (k): 880

## Approval gate

Approved: 2026-10-05 hash:e2e2d2437686

## Definition of Done (applies to every task above)
1. Code implements exactly the FR cited, in exactly the target file, following plan.md's Naming & File Contract, SOLID and the antifragile standard.
2. The owner's own test file(s) named in the Test rule run lines pass; mirrors are byte-identical (checked with `cmp` by the owner, then by `test_dot_aidd_mirror` run by the main agent at the end of the wave); the full suite passes at the end of each wave after the first (serialized, one runner at a time), including `test_dot_aidd_mirror` and `test_aidd_rules`.
3. `qa-audit.md` (R10 mapping row and execution evidence for every FR touched) is written ONCE by the main agent at close, after T-05 and T-06, so it has a single owner; no task writes it.
4. No app screens: the review page is verified in a real browser by T-06 (the native folder picker by the owner).
