# Tasks — AIDD 007: review-driven approval, per-spec R6, executed close gate

One row = one owner agent for one file (plus its mirror and its tests). Codes are the FR-2nn of spec.md (no screens). Every builder prompt restates: scope in/out as stated per row; stop and report if anything is ambiguous; SOLID; names exactly as plan.md's Naming & File Contract and "Exact interfaces"; antifragile (every disk/lock/subprocess/git call can fail: timeout, degrade, record `hook_error`, never fail silently); Python stdlib only; UTF-8 and LF on every file IO; match surrounding code style. Source paths are under D:\Fuentes\AIDD\skill unless stated; agents never write `~/.claude` or `.aidd/`.

**Mirror rule (tests/test_dot_aidd_mirror.py):** the owner of `skill/scripts/{aidd_evidence,aidd_rules,aidd_status,check_spec,aidd_review}.py` copies the file byte-identical over `adapters/dot-aidd/scripts/` in the same task; the owner of `templates/review.html` copies it to `adapters/dot-aidd/templates/`; T-09 copies `AIDD.md`, `templates/spec.md`, `templates/qa-audit.md` (NEVER `templates/tasks.md`: the dot-aidd copy is a reduced variant). Hooks have no mirror. The `.aidd/` project install and `~/.claude/skills/aidd` are synced by the owner after the build.

**Test rule:** subagents run only their own test files (`python -m unittest tests.<name>`); the main agent runs `python -m unittest discover -s tests` once at the end of each wave. Only one runner at a time on this working tree. The tests that must be REWRITTEN (not just extended) are named in the owner's task and listed in plan.md "Tests that change".

**Real project ids:** every path/guard test uses BOTH a numeric id (`002-aidd-hard-rules`) and a non-numeric one (`F23-eDoc-POS`), absolute and relative paths.

| Task | Codes satisfied | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-01 | FR-201, FR-204, FR-205, FR-206, FR-208, FR-209 | scripts/aidd_evidence.py + adapters/dot-aidd/scripts/aidd_evidence.py; tests: tests/test_evidence.py | LOGIC | | | any other file; hooks; writing `active_spec` semantics (set_active_spec stays untouched) |
| T-02 | FR-204, FR-205, FR-206, FR-207 | scripts/aidd_rules.py + adapters/dot-aidd/scripts/aidd_rules.py; tests: tests/test_aidd_rules.py, tests/test_r14.py, tests/test_aidd_rules_r10.py | LOGIC | | | any other file; review code (lives in aidd_review.py) |
| T-03 | FR-202, FR-203, FR-204 | scripts/aidd_review.py + adapters/dot-aidd/scripts/aidd_review.py; aidd/cli.py; tests: tests/test_aidd_review.py | LOGIC | | | the real HTML template (T-04 owns it); test_dot_aidd_mirror.py; any other file |
| T-04 | FR-202, FR-203 | templates/review.html + adapters/dot-aidd/templates/review.html; tests: tests/test_review_template.py | VIEW-new | | | aidd_review.py; any markdown rendering (done server-side by T-03) |
| T-05 | FR-201, FR-204, FR-205, FR-206, FR-208 | scripts/aidd_status.py + adapters/dot-aidd/scripts/aidd_status.py; tests: tests/test_aidd_status.py, tests/test_cli_rules.py, tests/test_typed_confirmations.py | LOGIC | | | any other file; STATE.md writing; migration counting |
| T-06 | FR-201, FR-204, FR-206, FR-208 | hooks/rule_gate.py + hooks/_common.py; tests: tests/test_rule_gate.py, tests/gate_fixtures.py | LOGIC | | | stop_gate.py; mark_code_edit.py; require_graph_coherence_audit.py; any other file |
| T-07 | FR-206, FR-208 | hooks/stop_gate.py + hooks/session_start.py + hooks/require_graph_coherence_audit.py; tests: tests/test_stop_gate.py, plus tests/test_hooks.py section for session_start and the graph-coherence hook, same owner as T-12 | LOGIC | | | any other file |
| T-08 | FR-208 | scripts/check_spec.py + adapters/dot-aidd/scripts/check_spec.py; tests: tests/test_check_spec.py | LOGIC | | | any other file; exit codes of check_spec |
| T-09 | FR-206, FR-207, FR-208 | SKILL.md, AIDD.md, templates/spec.md, templates/qa-audit.md + their adapters/dot-aidd copies; tests: tests/test_dot_aidd_mirror.py | LOGIC | | | scripts, hooks, templates/tasks.md, the external skill aidd-converge |
| T-10 | FR-201..FR-209 | audit: ONE closing auditor, domains security + functional + performance as a checklist (no file writes except its report) | LOGIC | | | any code edit |
| T-11 | FR-202, FR-203, FR-204 | tests/e2e_review_roundtrip.py (new) + evidence files under the spec dir | LOGIC | | | any production file |
| T-12 | FR-209 | hooks/mark_code_edit.py + hooks/mark_agent_dispatch.py; tests: recorder section of tests/test_hooks.py | LOGIC | | | any other file; the rule engine |
| T-13 | FR-210, FR-212, FR-213, AC-219..221, AC-224, AC-226..228, AC-231, AC-232 | `skill/scripts/aidd_evidence.py` + `adapters/dot-aidd/scripts/aidd_evidence.py` + `tests/test_evidence.py` + `tests/test_code_fingerprint.py` + `tests/test_verify_regressions.py` | LOGIC | | | SQL semantic parser, row caching, Scope grammar, DB, installed copies |
| T-14 | FR-211, AC-222..225 | `skill/scripts/aidd_evidence.py` + `adapters/dot-aidd/scripts/aidd_evidence.py` + `tests/test_code_fingerprint.py` + `tests/test_verify_regressions.py`, same owner as T-13 | LOGIC | | | new cache policy, changing consuming specs |
| T-15 | FR-211, AC-230, AC-233 | `skill/scripts/aidd_rules.py` + `adapters/dot-aidd/scripts/aidd_rules.py` + `tests/test_aidd_rules.py` + `tests/test_aidd_status.py`, same owner as T-13 | LOGIC | | | DB, approval behavior |
| T-16 | FR-211, FR-212, AC-224, AC-229, AC-233 | `skill/scripts/aidd_status.py` + `adapters/dot-aidd/scripts/aidd_status.py` + `skill/scripts/aidd_rules.py` + `adapters/dot-aidd/scripts/aidd_rules.py` + `tests/test_wave_verification.py` + `tests/test_aidd_status.py`, same owner as T-13 | LOGIC | | | new cache policy, DB |
| T-22 | FR-220, FR-221, FR-222, FR-223, AC-251..AC-258 | `tests/test_contract_store.py` + `tests/test_verify_git_contract.py` | LOGIC | | | any production code; any other test file; any other assertion of test_verify_git_contract.py |
| T-23 | FR-220, FR-221, FR-222, FR-223 | `skill/scripts/aidd_status.py`, same owner as T-16 | LOGIC | | | `round_on`, `_round_*` functions, `aidd_rules.py`, any non-contract row behaviour |
| T-24 | FR-220..FR-223 (mirror) | `adapters/dot-aidd/scripts/aidd_status.py` | LOGIC | | | any change that is not a byte copy of T-23's file |
| T-25 | FR-222 docs | `skill/SKILL.md` | LOGIC | | | any other section of SKILL.md; b1SycLink files |
| T-26 | FR-230..FR-235, AC-261..AC-268 | `tests/test_progress_resolution.py` | LOGIC | | | any production code; any other test file |
| T-27 | FR-230..FR-235 | `skill/scripts/aidd_progress.py` | LOGIC | | | `aidd_pending.py`, `aidd_status.py`, output format of `aidd progress` except the new `renamed` count |
| T-28 | FR-230..FR-235 (mirror) | `adapters/dot-aidd/scripts/aidd_progress.py` | LOGIC | | | any change that is not a byte copy of T-27's file |
| T-29 | FR-231, FR-233 docs | `skill/SKILL.md`, same owner as T-25 | LOGIC | | | any other section; b1SycLink files |
| T-30 | FR-240..FR-249, AC-271..AC-284 | `tests/test_aidd_coverage.py` | LOGIC | | | any production code; any other test file |
| T-43 | FR-259..FR-261, AC-285..AC-290 | `tests/test_verify_changed_policy.py` | LOGIC | | | any production code; any other test file, including `tests/test_verify_git_contract.py` |
| T-31 | FR-240..FR-249 | `skill/scripts/aidd_coverage.py` | LOGIC | | | `aidd_status.py`, `aidd_progress.py`, `aidd_rules.py`, `aidd_evidence.py`; any Git call |
| T-44 | FR-259, FR-260, FR-261 | `skill/scripts/aidd_status.py` + `skill/scripts/aidd_unit_audit.py`, same owner as T-23 | LOGIC | | | `--tasks` and `--wave` behaviour; contract-store code; `aidd_coverage.py` |
| T-32 | FR-240 | `aidd/cli.py` | LOGIC | | | any other subcommand; argument parsing beyond forwarding |
| T-33 | FR-240..FR-249, FR-259..FR-261 (mirror) | `adapters/dot-aidd/scripts/aidd_coverage.py` + `adapters/dot-aidd/scripts/aidd_status.py` + `adapters/dot-aidd/scripts/aidd_unit_audit.py` + `tests/test_dot_aidd_mirror.py` | LOGIC | | | any change that is not a byte copy, except one list entry in the guard test |
| T-34 | FR-240, FR-245, FR-259, FR-261 docs | `skill/SKILL.md`, same owner as T-25 | LOGIC | | | any other section; b1SycLink files |
| T-35 | FR-250..FR-257, AC-291..AC-298 | `tests/test_alias_graph.py` | LOGIC | | | any production code; any other test file |
| T-36 | FR-252, FR-254 | `skill/scripts/alias_graph.py` | LOGIC | | | `aidd_graphs.py`, `graph_explorer.py`, any other module |
| T-37 | FR-250, FR-251 | `skill/scripts/aidd_graphs.py` | LOGIC | | | the `explorer` subcommand branch; any graph other than `aliases` |
| T-38 | FR-253, FR-255, SCREEN-901 | `skill/scripts/graph_explorer.py` + `skill/scripts/unified_graph.py` | VIEW-new | | | the JSON loading path; layer pill, checkbox and colour (registry-generated); every control of the 004 amendment |
| T-39 | FR-256, FR-257 | `skill/scripts/aidd_progress.py`, same owner as T-27 | LOGIC | | | the `renamed` counting and the output format of `aidd progress` |
| T-40 | FR-250..FR-257 (mirror) | `adapters/dot-aidd/scripts/alias_graph.py` + `adapters/dot-aidd/scripts/aidd_graphs.py` + `adapters/dot-aidd/scripts/graph_explorer.py` + `adapters/dot-aidd/scripts/unified_graph.py` + `adapters/dot-aidd/scripts/aidd_progress.py` + `tests/test_dot_aidd_mirror.py`, same owner as T-33 | LOGIC | | | any change that is not a byte copy of the T-36..T-39 files, except one list entry in the guard test |
| T-41 | FR-251, FR-253 docs | `skill/SKILL.md`, same owner as T-25 | LOGIC | | | any other section; b1SycLink files |

FR-205 and FR-206 have no installed effect until the owner installs the new scripts; the close of spec 007 itself goes through the legacy path (it was approved before `gate: 2` existed), see spec.md "Bootstrap".

Amendment 03 (T-22..T-25, cross-spec reuse of offline-contract rows): every task prompt restates: scope in and out exactly as written; stop and report on any ambiguity; one responsibility per function; snake_case Python functions with a leading underscore for module private helpers (the convention of `aidd_status.py`); design for failure (every store read/write in `try/except (OSError, ValueError, TypeError, KeyError)`, fail closed = execute the row); tool-first (bulk mirror sync by `cp`/script, never by hand-typing the file twice); repo rules: no temporary databases, `db_verify.py` is never run, no `aidd verify` by the builder. Analysis parameters: `aidd size --files skill/scripts/aidd_status.py tests/test_contract_store.py` → expected L (gate rules / CLI area).

Amendment 04 (T-26..T-29, task-state resolution): every task prompt restates: scope in and out exactly as written; stop and report on any ambiguity; one responsibility per function; snake_case with a leading underscore for module-private helpers; design for failure (every file read in `try/except (OSError, UnicodeDecodeError, ValueError)`, fail closed = report `missing`); tool-first (mirror sync by `cp`/script, never by hand); no databases, `db_verify.py` never run, no `aidd verify` by the builder. Analysis parameters: `aidd size --files skill/scripts/aidd_progress.py tests/test_progress_resolution.py` → expected M.

Amendment 05 (T-30..T-34, T-43, T-44, coverage derivation and the `--changed` declaration policy; owner decisions D-1..D-3, user — "acepto recomendacion"): every task prompt restates: scope in and out exactly as written; stop and report on any ambiguity; one responsibility per function; snake_case with a leading underscore for module-private helpers; design for failure (every file read in `try/except (OSError, UnicodeDecodeError, ValueError)`, never raise on malformed text in `aidd_coverage.py`; fail closed only on malformed declarations in `aidd_status.py`); tool-first (mirror sync by `cp`, never by hand); no databases, `db_verify.py` never run, no `aidd verify` by the builder. Analysis parameters: `aidd size --files skill/scripts/aidd_coverage.py skill/scripts/aidd_status.py skill/scripts/aidd_unit_audit.py tests/test_aidd_coverage.py tests/test_verify_changed_policy.py` → expected L (verify gate area).

Amendment 06 (T-35..T-41, alias graph registered and drawn by the explorer; re-based on `specs/004-aidd-graph-first/amendment-unified-explorer.draft.md`; former T-42 removed, superseded by T-74..T-76 of the 004 amendment): every task prompt restates: scope in and out exactly as written; stop and report on any ambiguity; one responsibility per function; snake_case with a leading underscore for module-private helpers; design for failure (every file read in `try/except (OSError, UnicodeDecodeError, ValueError)`, fail closed); tool-first (mirrors by `cp`, never by hand); no databases, `db_verify.py` never run, no `aidd verify` by the builder. **UI rule:** T-38 builds a NEW view faithful to the approved SCREEN-901 mockup; it does not reuse legacy presentation. Cross-spec note (not a task dependency): T-35..T-41 start after wave 10 of the 004 amendment, see plan.md "Amendment 06". Analysis parameters: `aidd size --files skill/scripts/alias_graph.py skill/scripts/aidd_graphs.py skill/scripts/graph_explorer.py skill/scripts/unified_graph.py skill/scripts/aidd_progress.py tests/test_alias_graph.py` → expected L (CLI and gate area, more than 8 files with mirrors).

## Per-task detail

### T-01
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC
**Estimate**
- Effort: Medium
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 85k
- Agent role: builder
- Model tier: medium
**Decompose**
- Objective: the evidence library exposes everything the other tasks code against: gate pointer and per-spec gate target, approval extras, verify_run, code-edit attribution, working-tree fingerprint.
- Activities:
  1. Add `'verify_run'`, `'rules_override'`, `'gate_pointer'`, `'stop_reminder'` to `PROJECT_KINDS` (~:143); keep session/project routing intact.
  2. Add `GATE_POINTER_FILE`, `get_gate_spec`, `activate_spec` (the ONLY gate-pointer writer, atomic write, appends `gate_pointer` on change), `recent_gate_pointer_changes`, `gate_target_specs` (3-tuple, `inferred` from the newest plan.md/tasks.md `spec_edit`, never reads `active_spec`), `latest_approved`, `append_verify_run`, `latest_verify_run`, `last_code_edit_ts`, `code_edits_for`, `worktree_fingerprint` exactly as in plan.md; extend `append_approved` (~:954) with `**extra` (backward compatible). `set_active_spec` is NOT changed.
  3. Tests in tests/test_evidence.py: 3 open specs + gate pointer B -> `([B], False, 'pointer')`; no pointer + 3 open + plan edit of C newest -> `inferred` C; the real-data case (`active_spec` = a spec with only `spec.md` edits, not open, 14 open, no gate pointer) never yields that spec; no inference candidates -> `ambiguous`; pointer to a closed or unknown spec falls back; 1 open + no pointer -> `only`; case-insensitive pointer; `activate_spec` refuses an unknown id and writes `gate_pointer` only on change; `set_active_spec` never moves the gate pointer; `append_approved` extras round-trip and an old event without `gate`; verify_run append/latest; `last_code_edit_ts` empty log = 0.0; `code_edits_for` with stamped, empty-stamped and legacy events; `worktree_fingerprint` in a temp git repo (stable twice, changes on a tracked edit, an untracked file and a commit, ignores `specs/` and `.aidd/`), in a non-git dir (mtime fallback), over the file cap (`None`), with git missing (monkeypatched).
  4. Copy byte-identical to adapters/dot-aidd/scripts/ and run `python -m unittest tests.test_evidence tests.test_dot_aidd_mirror`.

### T-02
**Estimate**
- Effort: High
- Agent min: 24
- Human ref hours: 1.2
- Tokens (est): 145k
- Agent role: builder
- Model tier: high
**Decompose**
- Objective: the rule engine knows the Verification table and its lint, the close-time verification check with freshness, the hardened closing-auditor marker and the advisory R5 mode.
- Activities:
  1. Add `GATE_VERSION`, `parse_verification`, `verification_hash`, `verification_command_problem` (all lint rules of plan.md: trivial, forbidden text, interpreter inline-code flags, self-satisfying `contains:`, runner-with-manifest or existing repo path), `check_verification`, `approval_evidence`, `verify_output_problem`, `verification_gaps` (stable, `started`, fingerprint, hashes, evidence sha1), `verification_state` (reuse `_table`, `_clean`, `_hdr`, the evidence-path rule of `_evidence_path`); all pure and never raising; the functions that need the log take `ev` (duck-typed) so tests use a `FakeEv`, never T-01's code.
  2. Add `CLOSING_AUDIT_RE`, `CLOSING_AUDIT_MIN_RESULT`, `closing_audit_header`, `closing_audit_covers` (first-line header, domains, `[tasks:<h8>]`, `[verify:<v8>]` for gate 2, `result_chars` floor, absent = does not count), `closing_audit_gaps` (qa-audit.md domain rows and the auditor `tool_use_id`) and the early return in `_uncovered` (~:1477); per-domain matching stays byte-for-byte as is below it.
  3. Add `r5_audit_mode` and make `_evidence_rules` (~:1802) skip only the Mapper and pre-build subagent violations in advisory mode.
  4. Tests: parser edge cases (placeholder row, backticks, pipes in a command, CRLF), hash ignores prose, lint (every AC-218 row: `python -c "pass"`, `python --version`, `cmd /c exit 0`, `sh -c true`, `python -c "print('PASS')"` + `contains: PASS`, a missing script path; accepted: `python -m unittest tests.test_x` with the file present, `dotnet test` with a `.sln`, `npm test` with `package.json`), `verify_output_problem` (`Ran 0 tests`, `NO TESTS RAN`, short output, `contains:` override), `verification_gaps` via FakeEv (no run, failed run, unstable run, code edit after `started`, fingerprint drift, hash drift against the approved event, evidence file changed or missing), closing-audit coverage (all domains, one missing, haiku, `phase=pre`, stale, stale `[tasks:]` tag, wrong `[verify:]`, header only in `desc`, header not on the first line, `result_chars` 20 / absent / 4000), `closing_audit_gaps`, advisory vs strict R5. REWRITE (pin `AIDD_R5_AUDIT=strict` for the class with `patch.dict(os.environ)` and add advisory twins): `TestCheckSpecDir.test_no_mapper_after_spec_edit` (~L502 'Mapper'), `test_tasks_chain_and_approval` (~L536 pre-build message), `test_graph_rebuilt_needs_subagent_after` (~L550 'pre-build coherence audit'), plus tests/test_r14.py where it asserts the old R5 block. A spec built from the new template passes `check_content('spec')` and a legacy spec without the sections still passes. Grep fixtures for the phrase "closing audit" first.
  5. Copy byte-identical to adapters/dot-aidd/scripts/ and run its three test files plus tests.test_dot_aidd_mirror.

### T-03
**Estimate**
- Effort: High
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 135k
- Agent role: builder
- Model tier: high
**Decompose**
- Objective: `aidd review <spec>` generates the self-contained `review.html` from the spec's markdown and reads back `review.md`; the markdown renderer is safe by construction; review state is content-only and never an approval by itself.
- Activities:
  1. Create `scripts/aidd_review.py` with every function of the plan.md table: `safe_url` (all rules, applied to every href/src), escape-first renderer with no `style=`/`on*=` attribute ever, JSON blob escaping, `sources_digest` with `rules.approval_hash` for tasks.md and CRLF-normalised bytes for the others, `MAX_REVIEW_SOURCE_CHARS` fail-closed refusal, atomic write, idempotent `generate`, `parse_review`, `review_state` (`complete` is content only, `page_current`), `prompt_consent`, `main` with `--open`, `--check`, `--comments` and the exit codes. `build_html`/`generate` take an optional `template_text` used ONLY by tests; the CLI and env never expose it.
  2. Add `cmd_review`, the `review` subparser and the `verify` passthrough (to `aidd_status.py verify <spec>`) in aidd/cli.py; update the `status` help string to mention `--refresh`; `main()` short-circuits `verify`.
  3. tests/test_aidd_review.py (all `build_html`/`generate` tests use a minimal inline `template_text` containing the tokens of `TEMPLATE_TOKENS` and one `<script id="aidd-js">`; the real template is NOT read): slugs (stable, accents, duplicates, headings inside fences ignored), escaping and URL allow-list (every AC-204 string, TAB/CR/LF/C0/DEL inside the scheme, leading C0/space, `JaVaScRiPt:`, `&#106;avascript:`, `/\\evil`, `\\\\host\share`, `//host`, `..` and `%2e%2e`, images with `http(s)`, `</script>` in code, heading with quotes and `-->`, inline code containing `*` and `|`), generate (file created, `tasks_hash` equals `approval_hash(...)`, each reviewable key exactly once as `data-key`, absent sources, CRLF sources, a 450 000-char tasks.md and a 450 000-char plan.md REFUSED with the file and size named and nothing written, `review_state` reports `source too large`, unicode paths, second run does not touch the file, refusal without tasks.md, CSP hash token equals the sha256 of the script text of the template), parse_review (CRLF, bad hash, duplicate blocks, comment containing `---` or `## `), review_state (hash drift, Status-cell-only edit keeps it valid, a rewritten `Approved:` line keeps it valid and `generate` does not rewrite the page, digest drift, review.md older than review.html, missing key after a heading is added, forged complete review.md is `complete` but the test asserts no approval API exists in this module), `prompt_consent` (tag + approve word counts; "do not approve [tasks:x]", wrong tag, older than `since_ts`, other session, no approve word do not), CLI subprocess for `--check` and `--comments` and the exit codes (using a dummy `review.html` written by the test).
  4. Copy aidd_review.py byte-identical to adapters/dot-aidd/scripts/. Do NOT edit tests/test_dot_aidd_mirror.py (T-09 adds the entry). Run `python -m unittest tests.test_aidd_review`.

### T-04
**Estimate**
- Effort: Medium
- Agent min: 13
- Human ref hours: 0.65
- Tokens (est): 85k
- Agent role: builder
- Model tier: medium
**Decompose**
- Objective: the static page shell and its JS: one check and one comment box per `data-key`, progress, check-all buttons that skip mandatory sections, and a Send button that downloads `review.md` in the exact grammar of plan.md and shows the consent line.
- Activities:
  1. Write `templates/review.html` with the nine `{{TOKEN}}`s of plan.md (including `{{SCRIPT_SHA256}}` inside the CSP `script-src 'sha256-...'`), inline CSS (light/dark, 16 px gutter, 360 px minimum width, long tables scroll inside their own box, `.mandatory` highlighted box), CSP meta (`default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; script-src 'sha256-{{SCRIPT_SHA256}}'; base-uri 'none'; form-action 'none'`), ONE `<script id="aidd-js">` with a constant text containing the pure function `buildReviewMd(data)` and the DOM wiring (no inline event handlers, no `eval`, no `innerHTML` with data), "check all"/"Approve all" skipping `data-mandatory` sections, a post-Send banner with the move-the-file instruction and the copyable consent line `approve [tasks:<hash8>]`, localStorage in try/catch, `<noscript>` text, no external resource and no `http(s)://` anywhere.
  2. Copy it to adapters/dot-aidd/templates/review.html.
  3. tests/test_review_template.py: every token present exactly where expected, no `http://`/`https://` in `src`/`href`, CSP has no `unsafe-inline` in `script-src`, no inline `on*=` handler or `eval(`, the script text is constant (no token inside it) and a local recomputation of its sha256 can be substituted into the CSP, JS extracted from `#aidd-js` and, when `node` is on PATH, `buildReviewMd` run on a fixture (every comment line prefixed with `> `, front matter flat, checked and unchecked blocks) and `node --check` on the script; skip with a message when node is missing. Run `python -m unittest tests.test_review_template`. (Tests that render a full page through `aidd_review.build_html` belong to T-11, never to this task.)

### T-05
**Estimate**
- Effort: High
- Agent min: 26
- Human ref hours: 1.3
- Tokens (est): 150k
- Agent role: builder
- Model tier: high
**Decompose**
- Objective: the CLI approves from a complete review PLUS a human consent act, activates a spec, executes the Verification table with a fingerprint, closes only on executed fresh evidence, and refreshes derived facts.
- Activities:
  1. `cmd_approve` (~:556) per the plan.md order: R1 check, `rules.check_verification`, then (a) a current review page + complete review -> `_consent` (tagged answer newer than review.md, else `aidd_review.prompt_consent`, else `_tty_confirm`; none -> refuse with the exact owner instructions: answer the `[tasks:<h8>]` question or type `approve [tasks:<h8>]`), (b) a current page + incomplete review -> refuse naming the cause (the answer-only route is refused while a current page exists), (c) no current page (never generated, or sources over the cap) -> the unchanged answer route with `source=answer`; write the `Approved:` line (EOL preserved), `ev.append_approved(..., **rules.approval_evidence(spec_text, source, review_sha1, consent_ts))`, `ev.activate_spec(root, spec, by='approve')`; print comments of checked headings as notes; refusal messages name the cause (hash mismatch: "review.md was generated for tasks hash X; current is Y: run `aidd review` again"; digest mismatch; older than review.html; missing keys).
  2. `cmd_activate`, `cmd_verify` (shell run with shell=True, project-root cwd, `AIDD_VERIFY_TIMEOUT` per row, evidence files `verify-<n>.txt` with the header line, Expected `exit 0` or `contains: <text>`, `rules.verify_output_problem` marks zero-test/short output rows failed, `started`, `ev.worktree_fingerprint` before the first and after the last row, `stable`, `ev.append_verify_run` with sha1 per file, exit 1 when any row fails or the run is unstable, rows with a `verification_command_problem` are not run) and the dispatch entries `('rules','activate')` and `verify`.
  3. `_close_gaps` (~:618) and `cmd_close`: `gate: 2` specs (via `ev.latest_approved(...).get('gate')`) use `rules.verification_gaps`, `rules.closing_audit_gaps` plus the closing-audit window `since = max(last code edit, verify_run.ts)`; legacy specs keep today's path; the typed "Yes, close" requirement is unchanged.
  4. Status: `review`, `verification`, `overrides` (count of `rules_override`), `r5_mode`, `gate_pointer` and its last 5 changes, `rules_mode` (effective `AIDD_RULES` with a note for warn/off), per approved spec the attributed code-edit count, in `build_status`/`format_status` and the degraded dict; `--refresh` with `_git` (list-form subprocess, 5 s timeout, utf-8, `git: unavailable` on any failure, exit 0), facts per plan.md/FR-208, `--json` key `derived`; output without `--refresh` unchanged except the pointer line.
  5. Tests in test_aidd_status.py, test_cli_rules.py, test_typed_confirmations.py: approve via a complete review.md WITHOUT consent is refused (AC-205); with the tagged answer, with a tagged prompt, and with an injected TTY confirmation each approves with the right `source`; a negated or untagged prompt does not; stale hash, digest drift, `approved:false`, older-than-html, missing key refused; a current page with an incomplete review refuses the answer-only route; no page (and oversize sources) keeps the answer route; Status-cell-only edit stays valid and so does the review right after `approve` rewrote the `Approved:` line; activate (writes the gate pointer, logs the change); verify (pass, fail, timeout, evidence file written, event recorded, zero-test output fails, unstable tree fails, rerun passes); close refusals and success for a `gate: 2` spec and unchanged success for a legacy approved spec; `--refresh` with a temporary git repo, without git, with `--json`; status shows the effective `AIDD_RULES`.
  6. Copy byte-identical to adapters/dot-aidd/scripts/ and run the three test files plus tests.test_dot_aidd_mirror.

### T-06
**Estimate**
- Effort: High
- Agent min: 22
- Human ref hours: 1.1
- Tokens (est): 130k
- Agent role: builder
- Model tier: high
**Decompose**
- Objective: the code gate checks only the target spec, the approval hook needs a complete review AND a consent act, agents cannot write or delete the review artifacts whatever the spec id or path shape, and the new R5 default and warn visibility are wired.
- Activities:
  1. `_code_gate` (~:365): use `ev.gate_target_specs` (3-tuple; fallback to `open_specs` on `AttributeError`/unpack error); ambiguous -> ONE R6 violation listing up to 5 open ids and `aidd rules activate <id>`; otherwise ONE violation naming the target, `how` and the unblock path (`aidd review <id>` then `aidd rules approve <id>`, or `aidd rules activate <other>`); per-spec checks and `_debt_violations` only for the target ids; update the docstring (the gate reads `.aidd/gate_spec`, never `active_spec`; both R9-protected); keep the `AIDD_RULES` handling untouched.
  2. `_approval_gate` (~:277): require `rules.check_verification(spec.md)`; the review route needs `aidd_review.review_state(d)['complete']` AND a consent act newer than review.md (`_affirm` with `since=max(_tasks_last_change, review mtime)` or `aidd_review.prompt_consent`), mint `approved` with `rules.approval_evidence(..., source='review+answer'|'review+prompt', consent_ts=...)`; review.md alone is NEVER enough; no TTY route; when a current review page exists and the review is incomplete the plain `_affirm` route is refused too; update its refusal text to name both consent options and the `[tasks:<h8>]` tag.
  3. `_decide_path`: block Write/Edit/MultiEdit/NotebookEdit to `specs/<any-id>/review.md` and `review.html` after canonicalisation (`REVIEW.MD.`, `review.md::$DATA`, `sub/../review.md`); `_common.py` gets `USER_ONLY_SPEC_FILES`. Bash guard (the finding that `_specs_tok` only accepts `specs/` at index 0 or before `NNN-`): extend `_specs_tok` (~L783-796) so a path with a `specs/<segment>/` pair whose leaf is `review.md` or `review.html` is a specs token for ANY id; add the TEXT-LEVEL rule to `_shell_block` next to the `tasks.md`+`approved` rule (~L979) exactly as plan.md describes (normalise `\` to `/`, match `review.md`/`review.html` anywhere, block when writes/script-write/mover-copier-deleter verb/inline-script interpreter, `aidd` verb exempt without redirection); adding the markers to `BASH_MARKERS` is cosmetic (`specs` is already a marker) and is NOT the fix. `aidd review specs/X [--check]`, `aidd verify specs/X` and `cat specs/X/review.md` through Bash stay allowed.
  4. `_r5_tasks` (~:226): skip the pre-build demand when `rules.r5_audit_mode() == 'advisory'`; warn-mode emit point appends `rules_override` (best effort).
  5. Tests in test_rule_gate.py/gate_fixtures.py: REWRITE `test_b1_every_open_spec_is_checked_not_just_one` (~L720) as the gate-target test, `test_mdl_abandoning_one_spec_unblocks_the_other_dead_end` (~L729; the ambiguous message must list the open ids and the activate fix) and `test_d1_code_gate_never_reads_the_pointer` (~L1344; rename, keep the single-open-spec assertions, add "`active_spec` is never read"); new cases: two open specs A (approved and recorded) and B (PENDING) with gate pointer A allowed and pointer B blocked, no pointer + a plan edit of B inferred, no pointer and no edit ambiguous, `active_spec` on a spec with only spec.md ignored, pointer to a closed spec, R4 debt only blocks the target, nested roots; Edit adding the Approved line with a complete review and NO consent blocked, with a tagged answer allowed and `approved{gate:2, source:review+answer}` minted, with a tagged prompt allowed, stale hash blocked, a current page with an incomplete review blocks the plain answer; review artifact write attempts blocked in ALL variants of AC-207 for a numeric AND a non-numeric id (Write/Edit/MultiEdit/NotebookEdit; Bash: absolute path redirect, `cp`/`mv` from Downloads to an absolute path, `cd <dir> && echo x > review.md`, `tee`, `python -c open(...).write`, `rm review.html`) with `cat` and `aidd review` allowed; add `AIDD_R5_AUDIT=strict` to the env of `gate_fixtures.py` so the old R5 tests (~L1850-1900) keep their meaning, plus advisory/strict tests; warn mode records `rules_override` and still never blocks.
  6. Run `python -m unittest tests.test_rule_gate`.

### T-07
**Estimate**
- Effort: Medium
- Agent min: 12
- Human ref hours: 0.6
- Tokens (est): 90k
- Agent role: builder
- Model tier: medium
**Decompose**
- Objective: the Stop gate blocks only for the target spec but reminds once per session about the other approved specs with unaudited edits, the SessionStart hook makes warn/off visible and tells the model about them, and the legacy graph-coherence hook stops demanding a pre-build audit in advisory mode.
- Activities:
  1. `stop_gate._obligations` (~:66): blocking list from `ev.gate_target_specs(root)` ids (ambiguous -> none); an `others` list = approved open specs outside the target list with `ev.code_edits_for(root, spec, approved_at, include_unstamped=<no target>)` non-empty; `others` is emitted once per session (dedupe through `stop_reminder{sid, specs}`) as stdout JSON `{"systemMessage": ...}` with exit 0 when nothing blocks, and appended to the block message otherwise; `MAX_BLOCKS` from `AIDD_STOP_BLOCKS` (default 3, invalid -> 3); block message lists: run `aidd verify <spec>`, dispatch ONE closing auditor whose prompt's FIRST line is `CLOSING AUDIT [domains: ...] [tasks:<h8>] [verify:<v8>]` (domains from `rules.required_domains`), write qa-audit.md (domain table + the auditor's tool_use_id) then `aidd rules close`; the last gate-pointer changes; keep the old per-domain wording as the legacy line; update the module docstring (M10 now: target blocks, others reminded). In `warn` or `off` mode append `rules_override{hook:'stop_gate', mode}` BEFORE returning.
  2. `session_start.py`: record `rules_override{hook:'session_start', mode}` when `_common.rules_mode()` is not `enforce` and a project root is known; print one context line per `others` spec ("AIDD: spec X is approved and has N code edit(s) with no closing audit; gate target is Y; see `aidd status`"), never failing the hook.
  3. `require_graph_coherence_audit.evaluate`: when `rules.r5_audit_mode() == 'advisory'` skip the `last_agent_dispatch > last_graph_rebuild` branch (the find_spec requirement stays); `strict` unchanged; import `aidd_rules` lazily from the scripts dir, fail open.
  4. Tests: REWRITE `test_two_open_specs_both_count_and_abandoning_one_leaves_the_other` (tests/test_stop_gate.py ~L194) as in plan.md "Tests that change"; `test_m10_*` keep their semantics (only `no distinct ... auditor` wording assertions follow); add scoping (three open specs, pointer on one, attributed edits on another), reminder printed once, ambiguity, `AIDD_STOP_BLOCKS=1`, warn/off record `rules_override`; in a new section of tests/test_hooks.py: session_start lines and `rules_override`, graph-coherence advisory vs strict with a recorded rebuild (AC-211). Run `python -m unittest tests.test_stop_gate tests.test_hooks`.

### T-08
**Estimate**
- Effort: Low
- Agent min: 6
- Human ref hours: 0.3
- Tokens (est): 50k
- Agent role: builder
- Model tier: medium
**Decompose**
- Objective: `check_spec.py` says plainly that it is a structural check until execution evidence exists.
- Activities:
  1. After the `=` rule print `STRUCTURAL CHECK ONLY - nothing was executed. 0 gaps here does NOT mean the spec works.`; when `rules.verification_state(spec_dir, root)['status'] == 'passed'` print the execution-evidence line instead (try/except, default to the structural banner); success line becomes `No mechanical gaps found (structural only). ...` keeping the substring asserted at tests/test_check_spec.py:84; exit codes unchanged; one sentence in the module docstring.
  2. Tests: banner for a clean spec, execution line with a passed run in a scratch evidence dir (`AIDD_TESTING=1`), exit code unchanged. Copy byte-identical to adapters/dot-aidd/scripts/. Run `python -m unittest tests.test_check_spec tests.test_dot_aidd_mirror`.

### T-09
**Estimate**
- Effort: Medium
- Agent min: 16
- Human ref hours: 0.8
- Tokens (est): 95k
- Agent role: docs
- Model tier: medium
**Decompose**
- Objective: the skill text and templates describe exactly what the code now enforces, host-agnostic, and drift between skill and adapter copies is tested.
- Activities:
  1. `templates/spec.md`: add `## Verification` (with the lint rules in one sentence: a real runner or an existing repo path, no inline-code interpreters, no self-satisfying `contains:`) and `## Optimization brief` (wording from spec.md FR-207; tool-agnostic: "ask the owner", never a Claude-only tool name); `templates/qa-audit.md`: a Verification summary line and a domain checklist table (one row per domain, plus the closing auditor's id) filled from the single closing auditor's report; copy both to adapters/dot-aidd/templates/.
  2. SKILL.md and AIDD.md (+ copy of AIDD.md): R5 row (advisory default, `AIDD_R5_AUDIT=strict`, includes the post-rebuild graph-coherence demand), R6 row and the PreToolUse table row (scoped per spec through `.aidd/gate_spec`, `aidd rules activate`, how the target is chosen), R7 row and Step 6 (run `## Verification` with `aidd verify`, then ONE closing auditor whose first line is `CLOSING AUDIT [domains: ...] [tasks:<h8>] [verify:<v8>]`, domains as a checklist, per-domain auditors still accepted), R8 row (target blocks, others reminded once, `AIDD_STOP_BLOCKS`), Step 2/3 (fill `## Optimization brief`, owner picks), Step 5 ("think, then propose; record proposals in the brief; no per-domain audits during build"), the review flow at the Step 4 -> 5 transition (`aidd review <spec>`, open `review.html`, Send, move `review.md` into the spec folder, then the CONSENT: answer the question tagged `[tasks:<h8>]` or type `approve [tasks:<h8>]` (or run `aidd rules approve` in your own terminal), `aidd rules approve`; the agent reads `review.md` comments and edits spec/plan/tasks; `review.html` is generated and git-ignored; a complete review.md alone approves nothing), "Escape hatch" paragraph rewritten as a last-resort diagnostic (`AIDD_RULES=warn|off` is recorded and shown by `aidd status`) with the fix-the-scoping advice, `aidd status --refresh`, and the check_spec "structural only" sentence. Grep tests for text they assert (`AIDD_RULES`) before editing.
  3. tests/test_dot_aidd_mirror.py: add `aidd_review.py` to `VERBATIM_SCRIPTS`, and identity tests for `AIDD.md`, `templates/spec.md`, `templates/qa-audit.md`, `templates/review.html` between skill/ and adapters/dot-aidd/. Run `python -m unittest tests.test_dot_aidd_mirror`.

### T-10
**Estimate**
- Effort: High
- Agent min: 12
- Human ref hours: 0.6
- Tokens (est): 95k
- Agent role: auditor
- Model tier: high
**Decompose**
- Objective: ONE independent closing audit over the final diff, with the domains as a checklist; first line of the prompt is `CLOSING AUDIT [domains: security, functional, performance] [tasks:<h8>]`.
- Activities:
  1. Security checklist: forgery of review.md/review.html (every Write/Edit/MultiEdit/Bash variant with numeric AND non-numeric ids, absolute and relative paths, ADS and trailing-dot names, copy/move/delete) and proof that a forged complete review.md mints NOTHING without the consent act (CLI, hook, prompt, TTY); XSS in the renderer and page (AC-204 list, CSP hash, `safe_url`); truncation/oversize behaviour; `verify_run`/evidence forging through `aidd verify` command text and the lint bypasses of AC-218; `activate` pointer flipping and the stamps; `append_approved` extras; `rules_override` spoofing and the `off` visibility; shell-escape in `cmd_verify`; path traversal in `generate`/`render_markdown` links; `gate_target_specs` fail-open paths; closing-auditor spoofing (header-only dispatch, short report). Findings ranked CONFIRMED vs PLAUSIBLE.
  2. Functional checklist: execute AC-201, AC-202, AC-205..AC-218 in scratch projects (never the real log) and save outputs under specs/007-aidd-review-html-close-gate/evidence/; PASS/FAIL per case.
  3. Performance checklist: cost of `gate_target_specs` (including the `inferred` scan) and `_code_gate` on a synthetic log with 27 specs and 5k events (hot path on every tool call), the added work of `mark_code_edit` (R6 predicate, two pointer reads), `worktree_fingerprint` on a repo of realistic size, `generate` on a spec the size of `F13-eDoc-Emission-Engine` (84 KB tasks.md, 151 headings), `review_state`; flag regressions above 20% or anything near the hook timeouts.
  4. Read-only: report findings; fixes go back to the original owners.

### T-11
**Estimate**
- Effort: Medium
- Agent min: 12
- Human ref hours: 0.6
- Tokens (est): 80k
- Agent role: tests
- Model tier: medium
**Decompose**
- Objective: an executed round trip proves the page, the grammar, the consent and the approval fit together, including a real browser and the XSS fixtures.
- Activities:
  1. Write `tests/e2e_review_roundtrip.py`: build a scratch project with a spec shaped like `F13-eDoc-Emission-Engine` (five sources, ~150 headings, non-numeric id), run `aidd review` (this is the first test that renders through the REAL template: assert the CSP hash equals the sha256 of the script and every token was replaced), extract the JS from `review.html`, build `review.md` through `buildReviewMd` under `node` (skip that step with a printed notice when node is absent), place it newer than the page, assert `aidd rules approve` is REFUSED without a consent, record a tagged answer (scratch evidence dir, `AIDD_TESTING=1`), run `aidd rules approve` and assert the `Approved:` line, the `approved{gate:2, source:review+answer}` event, the gate pointer, and that `aidd review --check` still exits 0 afterwards; finish with `ROUNDTRIP OK`.
  2. Open a generated `review.html` in a real browser with the browser tool: screenshot the page at desktop and 390 px width, tick a few boxes, type a comment, press Send and confirm a `review.md` download with the expected grammar; confirm "Approve all" skips the Verification section; load a page built from the AC-204 fixture and confirm no script runs and no request leaves the page (console and network); confirm a relative screenshot image loads under the CSP from `file://` (otherwise report that `img-src` must become `file: data:`); save screenshots under specs/007-aidd-review-html-close-gate/evidence/ and describe any visual defect.
  3. No production file is edited; report defects to the main agent.

### T-12
**Estimate**
- Effort: Medium
- Agent min: 9
- Human ref hours: 0.45
- Tokens (est): 65k
- Agent role: builder
- Model tier: medium
**Decompose**
- Objective: the recorders give the new gates their facts: every R6-gated edit is a `code_edit` stamped with the gate target and the active spec, and every counting subagent row carries the size and hash of its final report.
- Activities:
  1. Capture the real PostToolUse payload of the Agent tool (keys and the shape of `tool_response`) with a throw-away probe in the scratchpad, report it, then implement `_response_text` for the shapes actually seen plus the documented ones (string, `content[].text`, list); if no text is available record nothing and say so (Open decision O-10).
  2. `mark_code_edit.py`: replace the `elif is_code_file(_fp)` test by the R6 predicate (`_common.is_r6_gated(canon_abs, rel_outermost)` per root; legacy `is_code_file` untouched for `require_aidd`); stamp `target=ev.get_gate_spec(root)` and `active=ev.get_active_spec(root)` on every `code_edit` (guarded: a failed pointer read must still record the base event); keep the spec-file branch as is (informational `active_spec`).
  3. `mark_agent_dispatch.py`: add `result_chars` and `result_sha1` to the counting `subagent` row; the PreToolUse `phase=pre` row is unchanged; dedupe by `tool_use_id` unchanged.
  4. Tests (recorder section of tests/test_hooks.py): `.css`, `.json`, `.html`, `web.config` edits recorded, `.md` and `specs/` edits not; `target`/`active` stamped with and without pointers; old library without `get_gate_spec` still records; `result_chars`/`result_sha1` for each response shape and absent when none. Run `python -m unittest tests.test_hooks`.

### T-13 — SQL raw-byte integrity and fingerprint compatibility
**Classify**
- Nature: `INCIDENT`
- Kind: LOGIC
- Priority: 1
**Estimate**
- Agent min: 25
- Human ref hours: 1.25
- Tokens (est): 150k
- Agent role: builder
- Model tier: high
**Detail**
- Goal: fingerprint every in-scope SQL file by raw bytes and invalidate historical SQL fingerprints whose normalization was unsafe.
- Size: ~150 changed lines.
- Cites: FR-210, FR-212, FR-213, AC-219, AC-220, AC-221, AC-224, AC-226, AC-227, AC-228, AC-231, AC-232.
- Depends on: approved amendment and pre-build coherence audit.
- Read first: `skill/scripts/aidd_evidence.py:1954-2030`, `tests/test_evidence.py:202-245`, `tests/test_code_fingerprint.py:1-80`; the draft plan behavioral contract 1–4 and 7.
- Files to change: canonical evidence module and its listed mirror; `tests/test_evidence.py`, `tests/test_code_fingerprint.py` and `tests/test_verify_regressions.py` only.
- Naming contract: retain `sql_semantic(text) -> str`, `sql_digest(data) -> str`, `comment_only_edit(path, tool_input) -> bool`, `code_state(root, budget_s=8.0, scope=None, reuse=False)`, and `_fp_sql_chunk(root, rel)` two-argument compatibility; version SQL chunk prefix as `sql-raw-v2:` and hash with SHA-256; constant `EVIDENCE_ALGORITHM = 'raw-sql-v2-glob-v2'`, event key `code_algorithm`, and exception `_FpInputUnsafe` distinct from `_FpUnavailable`.
- Behavior: implement raw bytes and fail-closed streaming per plan 2–4; `sql_semantic` returns its input unchanged, `comment_only_edit` returns False, and `sql_digest` computes SHA-256 of bytes. Read SQL twice, compare digests and file metadata before/between/after, enforce budget and refuse instability; this detects observed races but does not prove atomicity against a writer that toggles and restores bytes between observations. Reject missing/unreadable SQL returned by Git enumeration and SQL that disappears/fails stat or read in filesystem walk; reject walk errors rather than silently omitting paths. Raise `_FpInputUnsafe` for unsafe SQL input, not `_FpUnavailable`: the latter alone retains Git-unavailable fallback, while unsafe input propagates without fallback and `code_state` returns `None`. Remove SQL `(path,size,mtime)` digest caching and never fall back to metadata for SQL. Add `EVIDENCE_ALGORITHM = 'raw-sql-v2-glob-v2'` and allow `code_algorithm` in `_VERIFY_EXTRA` for T-16. Synchronize mirror after canonical edit with scripted copy/dry-run/hash check.
- Tests first: add distinct dollar-body inputs, tagged strings containing comment delimiters, doubled quotes, nested block comments, unmatched delimiter, escaped tokens, adjacent quoted literals with newline versus space, byte/encoding differences, files larger than 5 MiB, same-size edits with restored mtime, old/new fingerprint comparison, and SQL listed then missing/inaccessible at isfile/stat/read (git and non-git). Simulate unsafe Git SQL while an otherwise successful non-Git fallback is available: `code_state`/verify must refuse without invoking fallback; simulate genuinely missing Git and prove normal fallback still works. Coordinate a writer mutating bytes during first read and restoring size/mtime; require snapshot/verify refusal. Test budget exhaustion and describe controlled-worktree limitation. Show red failure for dollar collision; revise legacy comment-only-equivalence assertions to raw-byte invalidation. Then implement.
- Verify: orchestrator runs `python -m unittest tests.test_evidence tests.test_code_fingerprint tests.test_verify_regressions tests.test_aidd_rules` -> exit 0 and `python -m unittest tests.test_wave_verification tests.test_aidd_status` -> exit 0; compare mirror SHA-256 -> equal. Builder runs only static Python compile checks of its files; tests first red is coordinated with orchestrator, not a second heavy wave.
- Do NOT: normalize SQL using inferred dialect, weaken collision tests, silently omit a listed SQL input, fall back to size/mtime, memoize by mutable metadata, claim atomicity against an adversarial writer, touch Scope policy, fabricate old evidence, change `.aidd/`, install a parser or broaden caching eligibility.
- Done when: required red and green outputs exist, mirror hashes agree, raw-byte changes invalidate correctly on both backends and large files, incomplete/racy scans fail closed, and an independent audit checks fingerprint soundness and migration.
- Open questions: none.

### T-14 — segment-aware Scope and Generated pattern safety
**Classify**
- Nature: `INCIDENT`
- Kind: LOGIC
- Priority: 1
**Estimate**
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 120k
- Agent role: builder
- Model tier: high
**Detail**
- Goal: implement correct, portable pattern handling without falsely excluding inputs or granting freshness on malformed patterns.
- Size: ~150 changed lines.
- Cites: FR-211, FR-212, AC-222, AC-223, AC-225.
- Depends on: T-13, same owner as T-13.
- Read first: `skill/scripts/aidd_evidence.py:1183-1203,2031-2044,2152-2210`, `skill/scripts/aidd_rules.py:2169-2230`, existing `TestScope` in `tests/test_code_fingerprint.py`, and draft plan 5–7.
- Files to change: canonical evidence module and its mirror; `tests/test_code_fingerprint.py` and `tests/test_verify_regressions.py` only.
- Naming contract: preserve `_scope_re(globs)`, `in_scope(rel, scope_rx)`, `code_state`, `fingerprint_of` and `last_code_edit_ts`; use the precise pattern grammar and failure behavior in plan 5.
- Behavior: compile segment-aware wildcards and character classes; normalize separators; reject unsafe or malformed patterns; test `Generated` and `Scope` separately, including last-edit fallback that cannot return a false-safe zero after a pattern failure. Keep `Inputs` Path.glob as-is and test matching parity for representative patterns. Sync mirror using scripted copy/dry-run/hash check.
- Tests first: P07 bracket-pattern reproducer must fail before the change; add exact positive/negative cases for `*`, `?`, `**`, range, negation, literal brackets, malformed/absolute/traversal patterns, `Generated`, git/non-git and outside/inside scope. Demonstrate invalid patterns refuse a passing verify rather than silently excluding an input.
- Verify: orchestrator runs `python -m unittest tests.test_evidence tests.test_code_fingerprint tests.test_verify_regressions tests.test_aidd_rules` -> exit 0 and `python -m unittest tests.test_wave_verification tests.test_aidd_status` -> exit 0; compare mirror SHA-256 -> equal. Builder runs only static Python compile checks and reports targeted red evidence.
- Do NOT: silently treat invalid Generated as exclude-all, change `Inputs` semantics, mark network/database checks hermetic, edit consuming specs or protected files, or run heavy suites concurrently.
- Done when: all required cases pass, the P07 pattern tracks edits, unknown patterns fail closed, mirror matches and audit finds no false-fresh path.
- Open questions: none.

### T-15 — unify Generated matching across verification consumers
**Classify**
- Nature: `INCIDENT`
- Kind: LOGIC
- Priority: 1
**Estimate**
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 95k
- Agent role: builder
- Model tier: high
**Detail**
- Goal: ensure runtime stability and close evaluation interpret Generated patterns identically to the scoped fingerprint.
- Size: ~100 changed lines.
- Cites: FR-211, AC-230, AC-233.
- Depends on: T-14; same owner as T-13.
- Read first: `skill/scripts/aidd_rules.py:2723-2740,2755-2780`, `skill/scripts/aidd_status.py:1595-1607,1986-1996`, plan behavioral contracts 5–6 and tests for Generated in `tests/test_aidd_status.py` and `tests/test_aidd_rules.py`.
- Files to change: `skill/scripts/aidd_rules.py`, `adapters/dot-aidd/scripts/aidd_rules.py`, `tests/test_aidd_rules.py`, `tests/test_aidd_status.py` only.
- Naming contract: preserve `_glob_hit(rel, globs) -> bool`; delegate to `aidd_evidence._scope_re` and `in_scope` with lazy import if required; no duplicate matcher. On malformed Generated patterns `_glob_hit` returns False and the corresponding fingerprint/verification refuses rather than excluding files.
- Behavior: use canonical matcher for all `Generated` runtime and close paths; handle no patterns as no match, normalize valid paths identically to Scope, fail safely on parser errors. In `_run_problems`, unconditionally validate current Generated even when recorded `code_changed=[]`; a malformed declaration makes the run stale and cannot be bypassed by empty iteration. T-16 implements equivalent JSON-verdict validation. Synchronize mirror by script with dry-run and hash post-check.
- Tests first: add end-to-end verify whose real command rewrites `output/report1.bin` under `Generated: output/report[0-9].bin`; it must be stable, retain evidence and agree with close check. Add unmatched changed output and malformed pattern cases that cannot pass, including an already approved/verified run with `code_changed=[]` after the current declaration becomes malformed. Run red before changing implementation.
- Verify: orchestrator runs `python -m unittest tests.test_aidd_rules tests.test_aidd_status tests.test_code_fingerprint` -> exit 0 and compares mirror SHA-256 -> equal. Builder only static Python compile checks; red run is orchestrated.
- Do NOT: create a second pattern grammar, alter `Inputs` or mark DB tests hermetic, ignore invalid patterns, change unrelated rules, or run heavy checks concurrently.
- Done when: runtime, fingerprint and close evaluate valid/invalid Generated patterns consistently and evidence demonstrates no false-fresh case.
- Open questions: none.

### T-16 — version verification evidence and row-cache eligibility
**Classify**
- Nature: `INCIDENT`
- Kind: LOGIC
- Priority: 1
**Estimate**
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 130k
- Agent role: builder
- Model tier: high
**Detail**
- Goal: distinguish historically unaffected code scopes from unsafe/unknown legacy scopes and prevent row caching without a verifiable execution-environment identity.
- Size: ~150 changed lines.
- Cites: FR-211, FR-212, AC-224, AC-229, AC-233, AC-234, AC-235.
- Depends on: T-15 and T-13; same owner as T-13.
- Read first: `skill/scripts/aidd_status.py:1525-1550,1781-1840,1986-2055,2097-2135`, `skill/scripts/aidd_rules.py:2755-2817`, `skill/scripts/aidd_evidence.py:1112-1155`, plan behavioral contract 8 and `tests/test_wave_verification.py`.
- Files to change: `skill/scripts/aidd_status.py`, `skill/scripts/aidd_rules.py`, corresponding `adapters/dot-aidd/scripts/` mirrors, `tests/test_wave_verification.py` and `tests/test_aidd_status.py` only.
- Naming contract: constant `aidd_evidence.EVIDENCE_ALGORITHM = 'raw-sql-v2-glob-v2'` and `_VERIFY_EXTRA` support are introduced by T-13; event key `code_algorithm`, row key `input_algorithm`; retain `_reusable_input_rows` signature and use the existing verification CLI. Preserve historical event readability.
- Behavior: record `code_algorithm` in aggregate/wave results and `input_algorithm` in executed rows with Inputs. In `_run_problems`, preserve legacy aggregate code freshness only under the exact literal non-SQL Scope/Generated proof in plan 8 and existing fingerprint/evidence checks; empty/global scope, SQL, any glob, unknown version, or inconsistent declarations make affected/unknown evidence stale. In `_json_pass_evidence_problem`, always validate current Generated even when `code_changed=[]`. Do not delete or rewrite history. Neither `_reusable_input_rows` nor in-memory multi-spec wave caching may return a row merely from `input_algorithm`, `Reuse: hermetic`, matching file hashes or command: the current system has no trustworthy environment verifier, so execute requested rows until a future attestation mechanism can prove environment identity and hermeticity. Emit a concise reason; do not claim that re-execution alone supplies such proof. Keep `--full` authoritative. Synchronize status/rules mirrors by script with dry-run/hash post-check.
- Tests first: construct a passing directly executed legacy run with exact non-SQL literal Scope/Generated, intact evidence and matching code fingerprint; prove its historical code portion stays unaffected and event is not rewritten. Change scope to SQL, a glob, empty/global or inconsistent declaration and prove stale. Construct a legacy non-SQL hermetic row with matching byte inputs but no environment identity; prove it does not produce REUSED. Run a second identical verification with a current marker but still no verifiable environment and assert no cache-hit indicator `REUSED`; corrupt evidence, changed input, unknown marker, `--full`, and same-wave multi-spec cache must likewise never produce a hit without proof. Add DB/network rows with absent or changed snapshot/environment identity and assert no hit. For a successful recorded run with `code_changed=[]`, replace current Generated with a malformed pattern and assert JSON refuses PASS; separately prove the close path is stale under T-15.
- Verify: `python -m unittest tests.test_wave_verification tests.test_aidd_status tests.test_verify_regressions tests.test_aidd_rules` -> exit 0; mirrors SHA-256 -> equal; builder runs static Python compile checks only.
- Do NOT: modify protected evidence files manually, delete historical events, apply a global stale decision based only on missing marker, fabricate prior environment attestations, treat current algorithm marker or hermetic label as environment proof, claim a DB check is hermetic without verified matching snapshot identity, or invent a new signing/runner subsystem inside this urgent fix.
- Done when: exact non-SQL historical code scopes are classified without global reset, all affected/unknown cases fail conservatively, no row is returned from cache without independently verifiable environment identity, and an independent audit verifies migration and the explicit temporary runtime cost.
- Open questions: none.

### T-22 — failing tests first
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: S

**Estimate**
- Effort: Medium
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 70k
- Agent role: tests
- Model tier: medium
- Wave: 8

**Detail**
- Goal: encode AC-251..AC-258 as unit tests that fail on the current code.
- Cites: FR-220, FR-221, FR-222, FR-223, AC-251, AC-252, AC-253, AC-254, AC-255, AC-256, AC-257, AC-258.
- Depends on: none.
- Read first: `tests/test_verify_git_contract.py` lines 1-116 (header and class `ContractReuse`); `skill/scripts/aidd_status.py` lines 1663-1753 and 2184-2263.
- Files to change: `tests/test_contract_store.py` (new) and `tests/test_verify_git_contract.py` (exactly two existing tests, see the next bullet).
- Existing tests to update (owner accepted this on 2026-11-03: their old assertions encode the behaviour that FR-221 replaces; line numbers are those before your insertion): in `ContractReuse.test_round_shares_only_identical_inputs_and_environment` insert `self.assertEqual(len(calls), 1)` right after the `status.cmd_verify('one', wave_cache=cache)` assertion (the second invocation now takes the stored PASS from the contract store instead of executing) and change the three later expectations: line 68 `3` to `2`, line 71 `4` to `3`, line 73 `6` to `5`; in `ContractReuse.test_contract_reuses_only_matching_environment_and_full_reruns` change `side_effect=['env1', 'env2', 'env2']` (line 107) to `side_effect=['env1', 'env2', 'env2', 'env2']` because the recheck of T-23 makes a fourth call. No other line of that file changes; the intent of both tests (any change of identity or `--full` forces execution) stays.
- Naming contract: class `CrossSpecContractReuse(unittest.TestCase)` with methods `test_second_invocation_other_spec_reuses`, `test_any_identity_change_executes`, `test_damaged_store_executes`, `test_failure_is_never_stored`, `test_db_runner_has_no_environment_id`, `test_full_and_round_off_disable`, `test_non_contract_rows_unchanged`, `test_store_write_failure_is_a_note`. Store paths asserted: `<tmp>/.aidd/evidence/contract-reuse-v1.json` and `<tmp>/.aidd/evidence/contract-reuse-v1/<sha256>.txt`. Patched production name: `status._contract_store_put`. Production entry points exercised (existing, unchanged signatures): `status.cmd_verify(spec_arg, full=False, bail=False, wave=None, result_sink=None, wave_cache=None, task_ids=None)` called as `cmd_verify('one')`, `cmd_verify('two')`, `cmd_verify('one', full=True)`, with `result_sink` a `dict` that `cmd_verify` fills via `result_sink.update(ok=..., stable=..., results=[...], ...)` (current lines 2512-2562); `wave_cache` is never passed.
- Behaviour:
  1. File header identical to `tests/test_verify_git_contract.py` lines 1-11 (`sys.path.insert(0, <repo>/skill/scripts)`, `import aidd_status as status`).
  2. Each test builds a temporary root with specs `one` and `two` whose `spec.md` holds the row `| V1 | python test.py | exit 0 | test.py | hermetic | contract:offline;vars=none;packages=none |` under `| # | Command | Expected | Inputs | Reuse | Environment |`, and patches exactly the set used in `ContractReuse.test_round_shares_only_identical_inputs_and_environment` (lines 50-61), except `ev.latest_verify_run` returns `None` always, so the existing same-spec path cannot satisfy the test, and NO `wave_cache` is passed (each spec is a separate `status.cmd_verify(name)` call = separate invocation).
  3. `test_second_invocation_other_spec_reuses`: verify `one`, then `two` → `len(calls) == 1`; `sink = {}` passed as `result_sink` for `two` has `sink['results']` with one row with `reused is True`, `cross_spec is True`, `source_spec == 'one'`; `specs/two/evidence/verify-V1.txt` bytes equal the stored object bytes.
  4. `test_any_identity_change_executes`: after a stored PASS from `one`, change in turn (a) the patched input fingerprint, (b) the patched environment id, (c) Expected in `two`'s spec to `contains: passed`, (d) the command to `python test.py -v`; each `cmd_verify('two')` adds exactly one call.
  5. `test_damaged_store_executes`: (a) delete the object file, (b) overwrite it with `b'garbage'`, (c) write `{not json` to the index; each time `cmd_verify('two')` returns 0 and adds one call; no exception escapes.
  6. `test_failure_is_never_stored`: `_run_row` returns `(1, '')` for `one`; the index file is absent or has no entry; `cmd_verify('two')` executes.
  7. `test_db_runner_has_no_environment_id`: call the REAL `status._contract_environment_id` (not patched) with `python eDoc/tools/db_verify.py --psql "docker exec -i x psql -U postgres" --tap` and with `python tools/run.py --tap`, declaration `contract:offline;vars=none;packages=none` → both `assertIsNone`.
  8. `test_full_and_round_off_disable`: `cmd_verify('one', full=True)` and, separately, under `patch.dict(os.environ, {'AIDD_VERIFY_ROUND': 'off'})`, each executes and the index file does not exist afterwards.
  9. `test_non_contract_rows_unchanged`: table `| # | Command | Expected |` with `| V1 | python test.py | exit 0 |`; two invocations → two calls; the index file does not exist.
  10. `test_store_write_failure_is_a_note`: patch `status._contract_store_put` with `side_effect=OSError`; `cmd_verify('one')` returns 0 and captured stdout contains `note: contract store not written`.
- Tests first: this task IS the tests; run `python -m unittest tests.test_contract_store -v` and keep the red output (every test except `test_non_contract_rows_unchanged` fails or errors on the current code).
- Verify: `python -m unittest tests.test_contract_store tests.test_verify_git_contract -v` → red before T-23 (the two updated existing tests fail on the old code); exit 0 after T-23.
- Do NOT: touch production code; use a real database, Docker, `db_verify.py` or the network; weaken an assertion later (the only allowed edits to existing assertions are the ones listed in "Existing tests to update"); pass a shared `wave_cache` dict in the NEW tests (that tests the existing in-round path, not this one).
- Done when: the 8 tests exist with exactly these names, the two existing tests carry exactly the listed edits, and the red run is recorded by the verifier.
- Open questions: none.

### T-23 — store and cross-spec lookup in `aidd_status.py`
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: L (gate/CLI area)

**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.25
- Tokens (est): 120k
- Agent role: builder
- Model tier: high
- Wave: 9

**Detail**
- Goal: implement FR-220..FR-223 with the smallest change to `cmd_verify`.
- Cites: FR-220, FR-221, FR-222, FR-223, AC-251, AC-252, AC-253, AC-254, AC-255, AC-256, AC-257, AC-258.
- Depends on: T-22 (tests red first).
- Read first: `skill/scripts/aidd_status.py` lines 1612-1625 (`_cached_pass_valid`), 1663-1753 (`_contract_environment_id`), 1756-1792 (`_reusable_input_rows`, `ROUND_TTL_DEFAULT`, `_round_enabled`, `_round_paths`), 2184-2263 (`cmd_verify` row loop), 2457-2482 (wave_cache store).
- Files to change: `skill/scripts/aidd_status.py`.
- Naming contract: constants `CONTRACT_STORE_VERSION = 'contract-reuse-v1'`, `CONTRACT_STORE_MAX_ENTRIES = 300`, `_DB_RUNNER_RE = re.compile(r'db_verify|psql|pg_prove|docker|supabase|--tap', re.I)`; functions `_contract_store_paths(root) -> tuple[Path, Path]`, `_contract_store_key(cmd, expected, inputs, input_fp, declaration, environment_id) -> str`, `_contract_store_get(root, key, expected) -> tuple[bytes, dict] | None`, `_contract_store_put(root, key, data, result, spec_name) -> None`; result fields `cross_spec`, `source_spec`, `source_sha256`; stdout prefix `CROSS-REUSED row`; note text `note: contract store not written (<ExceptionType>)`; index JSON `{"version": "contract-reuse-v1", "entries": [{"key", "sha256", "sha1", "cmd", "expected", "exit", "ok", "spec", "ts"}]}`.
- Behaviour:
  1. Add the three constants right after `ROUND_MAX_ENTRIES`.
  2. In `_contract_environment_id`, immediately after the shell-metacharacter check (`if any(c in cmd for c in '|&;<>\n\r`$'): return None`), add `if _DB_RUNNER_RE.search(cmd): return None`. Nothing else in that function changes.
  3. `_contract_store_paths(root)` returns `(Path(root) / '.aidd' / 'evidence' / f'{CONTRACT_STORE_VERSION}.json', Path(root) / '.aidd' / 'evidence' / CONTRACT_STORE_VERSION)`.
  4. `_contract_store_key(...)` returns the sha256 hex of `json.dumps([_verification_key(cmd), _verification_key(expected), sorted(inputs), input_fp, declaration.strip(), environment_id], ensure_ascii=True, separators=(',', ':'))`.
  5. `_contract_store_get(root, key, expected)`: read the index; if `version` differs → `None`; take the LAST entry with that `key`; read `<dir>/<entry['sha256']>.txt`; return `(data, entry)` only if `hashlib.sha256(data).hexdigest() == entry['sha256']` and `_cached_pass_valid(data, entry, expected)`; wrap everything in `try/except Exception: return None`.
  6. `_contract_store_put(root, key, data, result, spec_name)`: create the directory; write the object with mode `'xb'` (ignore `FileExistsError`, never overwrite); load the index (missing or invalid → empty list); remove entries with the same `key`; append the new entry (`exit` 0, `ok` True, `spec` = spec_name, `ts` = `time.time()`, `sha1` = `result['sha1']`); keep the last `CONTRACT_STORE_MAX_ENTRIES`; write `<json>.<os.getpid()>.tmp` then `os.replace` onto the index. Exceptions propagate to the caller.
  7. In `cmd_verify._one`, directly after the existing `hit = ... input_reuse ...` block and before the `rhit = ...` line: when `wave is None and task_ids is None and _round_enabled(full) and inputs and input_fp and env_id and r.get('reuse') == 'hermetic'`, compute the key, call `_contract_store_get`; on a hit re-check `rules.row_input_fingerprint(root, inputs) == input_fp` and `_contract_environment_id(cmd, env_decl) == env_id`; write the bytes to `final`; build `res` exactly like the existing REUSED branch (current lines 2253-2258) plus `cross_spec=True, source_spec=entry['spec'], source_sha256=entry['sha256'], secs=0.0`; print `CROSS-REUSED row {n} (PASS): {one_line[:100]} (passed in {entry['spec']} on the same Inputs and environment) → {rel}`; return `res`. Any exception in this block → fall through to execution.
  8. After the existing `if wave_cache is not None and stable and not full:` block, add a block guarded by `wave is None and task_ids is None and _round_enabled(full) and stable`, iterating `results` with the SAME eligibility checks as that block (original row `reuse == 'hermetic'`, inputs, `ok is True`, `environment_id`, `input_fp` unchanged now, `_contract_environment_id` unchanged now, evidence sha1 intact) plus `not result.get('reused')`; call `_contract_store_put(root, key, data, result, d.name)` inside `try/except (OSError, ValueError, TypeError, KeyError) as e:` that prints `note: contract store not written ({type(e).__name__})`.
- Tests first: T-22 red output must exist before the first edit.
- Verify: `python -m unittest tests.test_contract_store tests.test_verify_git_contract tests.test_wave_verification tests.test_verify_regressions -v` → exit 0 (orchestrator's verifier, once, after the wave).
- Do NOT: change `round_on`, `_round_lookup`, `_round_store`, `_reusable_input_rows` or the `wave_cache` semantics; change any path for rows without the contract; store FAIL, timeout (exit -1) or reused rows; look up or store under `--full`, `--tasks`, `--wave` or `AIDD_VERIFY_ROUND=off`; delete or overwrite an existing object file; write any evidence file other than the current row's own `final` path; add a TTL; import non-standard-library modules; touch `aidd_rules.py`.
- Done when: the Verify command exits 0 and `git diff --stat` lists only `skill/scripts/aidd_status.py` for this task.
- Open questions: none.

### T-24 — adapter mirror
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: XS

**Estimate**
- Effort: Low
- Agent min: 3
- Human ref hours: 0.15
- Tokens (est): 20k
- Agent role: builder
- Model tier: medium
- Wave: 10

**Detail**
- Goal: keep `adapters/dot-aidd/scripts/aidd_status.py` byte-identical to `skill/scripts/aidd_status.py`.
- Cites: FR-220, FR-221, FR-222, FR-223.
- Depends on: T-23.
- Read first: `tests/test_dot_aidd_mirror.py` lines 70-120 (mirrored file list; `skill/scripts/aidd_status.py` is listed at line 76).
- Files to change: `adapters/dot-aidd/scripts/aidd_status.py`.
- Naming contract: no new names; the file is a byte copy.
- Behaviour:
  1. `cp skill/scripts/aidd_status.py adapters/dot-aidd/scripts/aidd_status.py`.
  2. Run the Verify command.
- Tests first: existing `tests/test_dot_aidd_mirror.py` fails after T-23 and before this copy.
- Verify: `python -m unittest tests.test_dot_aidd_mirror -v` → exit 0.
- Do NOT: edit the mirror by hand; touch any other adapter file.
- Done when: the Verify command exits 0.
- Open questions: none.

### T-25 — document the rule in SKILL.md
**Classify**
- Nature: `REQUIREMENT`
- Priority: 4
- Kind: LOGIC
- Size: XS

**Estimate**
- Effort: Low
- Agent min: 5
- Human ref hours: 0.25
- Tokens (est): 20k
- Agent role: docs
- Model tier: medium
- Wave: 9

**Detail**
- Goal: state the cross-spec rule and the database refusal where the offline contract is documented.
- Cites: FR-221, FR-222.
- Depends on: none (text only; ships with T-23).
- Read first: `skill/SKILL.md` line 455 (paragraph starting `**Incremental verification and reusable checks.**`); `tests/test_dot_aidd_mirror.py` lines 115 and 426-436.
- Files to change: `skill/SKILL.md`.
- Naming contract: the appended sentence uses the literal token `CROSS-REUSED` and the runner list `db_verify`, `psql`, `pg_prove`, `docker`, `supabase`, `--tap`.
- Behaviour:
  1. Append to the end of that paragraph, exactly: "A passing contract row is stored once per project; a later `aidd verify` of any spec with the same command, expected result, Inputs and environment takes that stored result instead of running it (`CROSS-REUSED`); database and container runners (`db_verify`, `psql`, `pg_prove`, `docker`, `supabase`, `--tap`) can never use the contract."
- Tests first: none (documentation); the mirror suite is the regression guard.
- Verify: `python -m unittest tests.test_dot_aidd_mirror -v` → exit 0.
- Do NOT: rewrite other sentences; claim savings; touch b1SycLink `AGENTS.md` or any installed skill.
- Done when: the Verify command exits 0 and the sentence appears once.
- Open questions: none.

### T-26 — failing tests first
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: S

**Estimate**
- Effort: Medium
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 70k
- Agent role: tests
- Model tier: medium
- Wave: 8

**Detail**
- Goal: encode AC-261..AC-268 as unit tests that fail on the current code.
- Cites: FR-230..FR-235, AC-261..AC-268.
- Depends on: none.
- Read first: `skill/scripts/aidd_progress.py` lines 31-61 and 69-107 (`parse_tasks`) and 159-187 (`_resolve`, `task_state`); the import header of `tests/test_aidd_progress.py` lines 1-30.
- Files to change: `tests/test_progress_resolution.py` (new).
- Naming contract: class `TaskStateResolution(unittest.TestCase)` with methods `test_delete_target_gone_is_present`, `test_delete_target_still_there_is_missing`, `test_renumbered_migration_is_renamed`, `test_ambiguous_renumber_is_missing`, `test_alias_file_resolves_rename`, `test_bad_alias_is_missing_without_error`, `test_prose_task_id_is_not_a_task`, `test_project_without_cases_is_unchanged`. Production names exercised (signatures unchanged): `progress.parse_tasks(text)`, `progress.task_state(task, root)` where `task` is a dict from `parse_tasks`; new key `task['delete']` (list of str).
- Behaviour:
  1. Header: `sys.path.insert(0, <repo>/skill/scripts)`, `import aidd_progress as progress`, temp project root via `tempfile.TemporaryDirectory`.
  2. Each test writes a `tasks.md` text with the table `| Task | Codes satisfied | Target file | Status |` and calls `parse_tasks` then `task_state(task, root)`.
  3. Expected states: delete gone -> `'present'`; delete still there -> `'missing'`; `migrations/0120_x.sql` cited with only `migrations/3277_x.sql` existing (content > 40 bytes) -> `'renamed'`; with both `3277_x.sql` and `3300_x.sql` -> `'missing'`; alias graph `.aidd/graphs/path-aliases.toon` with the text `version: 1\ngenerated: 2026-11-03T00:00:00+00:00\naliases[1]{old,new,scope,reason}:\n  ordr_table.dart,oped_table.dart,mobile,F30\n` and the new file present -> `'renamed'`; alias to an absent file, or file bytes `b'\xff\x00{'` -> `'missing'` and no exception; a line `| T-42 | prose |` placed after a paragraph, outside any table with a Target column -> not in `parse_tasks` output; a plain existing target -> `'present'` exactly as today.
- Tests first: this task IS the tests; run `python -m unittest tests.test_progress_resolution -v` and keep the red output (all except the last test fail on current code).
- Verify: `python -m unittest tests.test_progress_resolution -v` → red before T-27, exit 0 after.
- Do NOT: touch production code; use a database, Docker or the network; weaken an assertion later.
- Done when: the 8 tests exist with exactly these names and the red run is recorded by the verifier.
- Open questions: none.

### T-27 — resolution logic in `aidd_progress.py`
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: M

**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.25
- Tokens (est): 100k
- Agent role: builder
- Model tier: high
- Wave: 9

**Detail**
- Goal: implement FR-230..FR-235 so T-26 passes with no change to behaviour when none of the cases occurs.
- Cites: FR-230..FR-235.
- Depends on: T-26.
- Read first: `skill/scripts/aidd_progress.py` lines 31-61, 69-107, 134-187; the tests created by T-26 in the file named in T-26's Files to change.
- Files to change: `skill/scripts/aidd_progress.py`.
- Naming contract: new module constants `DELETE_RE = re.compile(r'([\w.\-/]+)\s*\(delete[^)]*\)', re.I)`, `ALIAS_FILE = '.aidd/graphs/path-aliases.toon'`; new helpers `_delete_paths(raw_cell, short)` -> list[str], `_renumbered(root, p)` -> Path | None, `_alias_target(root, p)` -> Path | None, `_load_aliases(root)` -> dict[str, str] (cached per root like `_INDEX`). `parse_tasks` adds key `delete`. `task_state` may return `'renamed'` in addition to its current values. `_resolve` signature and return type unchanged.
- Behaviour:
  1. `parse_tasks`: compute `delete` from the raw Target cell before backticks are stripped; the path tokens themselves are still returned in `paths` as today.
  2. `task_state`: for each path in `task['delete']` -> missing if `_resolve` finds it, else skipped; if every path is in `delete` and none exists, return `'present'`.
  3. `_renumbered`: only when `'/migrations/'` is in `p` or `p` starts with `migrations/`, and the base name matches `^(\d+)_(.+)$`; list files in the same directory name pattern anywhere under root via the existing `_index(root)`; exactly one candidate with the same `(.+)` and a different prefix -> that Path; else None.
  4. `_load_aliases(root)`: read `ALIAS_FILE` as UTF-8 text; ignore every line that does not start with two spaces; split each such line on `,`; keep rows with at least 2 fields as `{old: new}` (base names only). `_alias_target`: if `base` has an alias, return the file with the new base name in the same directory when it exists and is larger than `STUB_BYTES`; any exception (OSError, UnicodeDecodeError, ValueError) -> None. Never raise.
  5. `task_state`: when `_resolve` is None, try `_renumbered` then `_alias_target`; mark the task `renamed` if any path was resolved this way and none is missing/stub.
  6. FR-235: in `parse_tasks`, ignore a row whose cells do not align with a header column set found directly above it in the same table block (the existing `cols` is reset by any non-`|` line; keep that, and additionally require `cols` to have been set by a header that has `target` or `status`).
- Tests first: T-26 must be red before this task; keep it unmodified.
- Verify: `python -m unittest tests.test_progress_resolution tests.test_aidd_progress -v` → exit 0.
- Do NOT: change `aidd_pending.py`; change the `progress.json` graph schema except adding the `renamed` state to the existing state vocabulary; read files larger than `MAX_READ`; guess when there is more than one candidate.
- Done when: all T-26 tests pass and the pre-existing progress and pending tests still pass.
- Open questions: none.

### T-28 — mirror
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
- Wave: 10

**Detail**
- Goal: keep the project bundle identical to the skill source.
- Cites: FR-230..FR-235 (mirror).
- Depends on: T-27.
- Read first: `tests/test_dot_aidd_mirror.py`.
- Files to change: `adapters/dot-aidd/scripts/aidd_progress.py`.
- Naming contract: none new; the target is a byte copy of `skill/scripts/aidd_progress.py`, so every name is the one fixed in T-27.
- Behaviour: byte copy of `skill/scripts/aidd_progress.py` by `cp`; no hand edits.
- Tests first: `tests/test_dot_aidd_mirror.py` already asserts equality; run it before (red after T-27 changes the source) and after (exit 0).
- Verify: `python -m unittest tests.test_dot_aidd_mirror -v` → exit 0.
- Do NOT: edit the file by hand; touch any other mirror.
- Done when: mirror test passes.
- Open questions: none.

### T-29 — document
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
- Wave: 10

**Detail**
- Goal: document delete/rename/renumber resolution and the optional alias file.
- Cites: FR-231, FR-233.
- Depends on: T-27.
- Read first: `skill/SKILL.md` section "Commands" paragraph that describes `aidd progress`.
- Files to change: `skill/SKILL.md`.
- Naming contract: documents exactly these names and no others: target marker `(delete)`, state `renamed`, graph file `.aidd/graphs/path-aliases.toon` (section `aliases[N]{old,new,scope,reason}:`), key `delete` in `parse_tasks`.
- Behaviour: add 4 lines after the `aidd progress` description: `(delete)` targets, the migration renumber rule, `.aidd/graphs/path-aliases.toon` format, the `renamed` state.
- Tests first: no code; the check below exits 1 before this task and 0 after.
- Verify: `python -c "import sys; sys.exit(0 if 'path-aliases.toon' in open('skill/SKILL.md', encoding='utf-8').read() else 1)"` -> exit 0.
- Do NOT: change any other section; mention b1SycLink.
- Done when: the 4 lines exist and the verify command passes.
- Open questions: none.

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
- Tests first: this task IS the tests; run the V-12 command and keep the red output.
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
- Tests first: this task IS the tests; run the V-13 command and keep the red output.
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
  1. Extract `_known_task_ids` and `_covers_task_refs` from `_task_rows` without changing `_task_rows` results or messages (V-14 guards it).
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
- Verify: `python -c "import filecmp, sys; ok = all(filecmp.cmp('skill/scripts/' + n, 'adapters/dot-aidd/scripts/' + n, shallow=False) for n in ('aidd_coverage.py', 'aidd_status.py', 'aidd_unit_audit.py')); sys.exit(0 if ok and '\"aidd_coverage.py\"' in open('tests/test_dot_aidd_mirror.py', encoding='utf-8').read() else 1)"` → exit 0 (the full mirror test V-15 runs after wave 14, when amendment 06's copies exist).
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

### T-35 — failing tests first
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
- Goal: encode AC-291..AC-295 and AC-297..AC-299 as unit tests that fail on the code left by the 004 amendment.
- Cites: FR-250..FR-257, AC-291..AC-295, AC-297..AC-299.
- Depends on: none in this amendment (runs after wave 10 of the 004 amendment).
- Read first: `skill/scripts/aidd_graphs.py` lines 140-181 and 889-917; `specs/004-aidd-graph-first/amendment-unified-explorer.draft.md` (FR-061, FR-067, T-75: the `--graph`, `--kind`, `--layer`, `--root` flags and `TOON_READERS`); `tests/test_aidd_progress.py` lines 1-30.
- Files to change: `tests/test_alias_graph.py` (new).
- Naming contract: class `AliasGraph(unittest.TestCase)` with methods `test_parse_and_load_rows`, `test_bad_file_gives_empty`, `test_to_graph_nodes_edges`, `test_show_prints_neighbours`, `test_registry_has_aliases_only_when_file_exists`, `test_explorer_accepts_toon`, `test_explorer_html_is_self_contained`, `test_unified_explorer_has_alias_layer`, `test_progress_graph_task_state`. Production names exercised: `alias_graph.parse_aliases(text)`, `alias_graph.load_aliases(path)`, `alias_graph.to_graph(rows)`, `alias_graph.show_aliases(root, query, limit=25)`, `aidd_graphs.show(root, name, query, limit=25)`, `aidd_graphs.load_registry(root)` (or the registry function at line 181, whichever the file exposes: read it), `graph_explorer.main(argv)`, `unified_graph.TOON_READERS`; registry-generated ids `metric-aliases`, `layer-cb-aliases`; alias-view ids `legend-aliases`, `insp-scope`, `insp-reason`, `aliases-empty-banner`.
- Behaviour:
  1. Header: `sys.path.insert(0, <repo>/skill/scripts)`, imports of the modules above (`alias_graph` will not exist yet: import it inside each test so each fails individually).
  2. Fixture text: `version: 1\ngenerated: 2026-11-03T00:00:00+00:00\naliases[2]{old,new,scope,reason}:\n  ordr_table.dart,oped_table.dart,mobile,F30\n  ocrd_table.dart,opar_table.dart,mobile,F30\n` written to `<tmp>/.aidd/graphs/path-aliases.toon`.
  3. `test_to_graph_nodes_edges`: those two rows give 4 nodes (ids `old:ordr_table.dart`, `new:oped_table.dart`, `old:ocrd_table.dart`, `new:opar_table.dart`) and 2 edges of type `RENAMED_TO`; a third row `ordr_table.dart,oped_table.dart,mobile,F30` repeated gives no new node and no new edge.
  4. `test_show_prints_neighbours`: `show_aliases(root, 'ordr')` equals `ordr_table.dart -> oped_table.dart [mobile] F30`; `'zzz'` gives `No alias matching 'zzz'.`; missing file and bytes `b'\xff\x00{'` give the FR-251 missing-file message and never raise.
  5. `test_explorer_accepts_toon`: `graph_explorer.main(['--graph', toon, '--kind', 'aliases', '--layer', 'aliases', '--out', html])` returns 0 and the html text contains `RENAMED_TO`, the three legend labels `old name`, `new name`, `renamed in progress`, and the ids `legend-aliases`, `insp-scope`, `insp-reason`, `aliases-empty-banner`.
  6. `test_explorer_html_is_self_contained`: the same html contains none of `http://`, `https://`, `//cdn`, `<script src`, `<link href`.
  7. `test_unified_explorer_has_alias_layer`: a temp project whose charter `## Graphs` table declares `aliases` (kind `aliases`, output `.aidd/graphs/path-aliases.toon`); `graph_explorer.main(['--root', root, '--out', html])` returns 0; the embedded payload has a layer `aliases` with 4 nodes and the html contains `id="metric-aliases"` and `id="layer-cb-aliases"`.
  8. `test_progress_graph_task_state`: a temp project with a `(delete)` task whose file is gone and a renumbered migration task; the progress graph returned by the module's graph writer has `state == 'deleted'` and `state == 'renamed'` on those two task nodes and no `state` key on a normal task.
  9. `test_registry_has_aliases_only_when_file_exists`: registry rows contain `aliases` with the file and do not contain it without.
- Tests first: this task IS the tests; run `python -m unittest discover -s tests -p "test_alias_graph.py" -v` and keep the red output (every test fails or errors on the current code except `test_explorer_html_is_self_contained`).
- Verify: `python -m unittest discover -s tests -p "test_alias_graph.py" -v` → red before T-36; exit 0 after T-39.
- Do NOT: touch production code; use a database, Docker or the network; weaken an assertion later.
- Done when: the 9 tests exist with exactly these names and the red run is recorded by the verifier.
- Size: ~130 changed lines.
- Open questions: none.

### T-36 — the alias reader module
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: S

**Estimate**
- Effort: Medium
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 60k
- Agent role: builder
- Model tier: medium
- Wave: 12

**Detail**
- Goal: one reader and converter for the alias format.
- Cites: FR-252, FR-254.
- Depends on: T-35.
- Read first: the tests created by T-35 in the file named in T-35's Files to change; `skill/scripts/aidd_progress.py` function `_load_aliases` (amendment 04) for the line format.
- Files to change: `skill/scripts/alias_graph.py` (new).
- Naming contract: constant `SECTION_RE = re.compile(r'^aliases\[(\d+)\]\{old,new,scope,reason\}:\s*$')`; functions `parse_aliases(text) -> list[dict]` (keys `old`, `new`, `scope`, `reason`), `load_aliases(path) -> list[dict]`, `to_graph(rows) -> dict`, `show_aliases(root, query, limit=25) -> str`, `is_alias_toon(text) -> bool`.
- Behaviour:
  1. `parse_aliases`: ignore every line that does not start with two spaces; split on `,` with maxsplit 3; keep rows with at least 2 non-empty fields; base names only (reject a field containing `/`, `\\`, NUL or `..`); `scope` and `reason` default to `''`.
  2. `load_aliases`: read UTF-8; any `OSError`, `UnicodeDecodeError` or `ValueError` returns `[]`.
  3. `to_graph`: exactly as FR-254; node ids unique; edges de-duplicated by `(source, target)`.
  4. `show_aliases(root, query, limit)`: path `<root>/.aidd/graphs/path-aliases.toon`; messages exactly as FR-251; at most `limit` lines.
  5. `is_alias_toon(text)`: true when any line matches `SECTION_RE`.
- Tests first: T-35 tests for this module are red before this task.
- Verify: `python -m unittest discover -s tests -p "test_alias_graph.py" -v` → the parse, load, to_graph and show tests pass.
- Do NOT: import from `aidd_graphs.py` or `graph_explorer.py` (they import this module, not the reverse); read any file other than the alias file; raise.
- Done when: the four named functions behave as listed and the related T-35 tests pass.
- Open questions: none.

### T-37 — registry entry and `show`
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: S

**Estimate**
- Effort: Medium
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 60k
- Agent role: builder
- Model tier: medium
- Wave: 13

**Detail**
- Goal: make the alias graph a registered, queryable graph.
- Cites: FR-250, FR-251.
- Depends on: T-36.
- Read first: `skill/scripts/aidd_graphs.py` lines 140-181 (registry builder) and 889-917 (`show`).
- Files to change: `skill/scripts/aidd_graphs.py`.
- Naming contract: no new public names; the registry builder gets one new row and `show` one new branch calling `alias_graph.show_aliases` through the existing helper `_module("alias_graph")` (the pattern used for `component_graph` at line 904).
- Behaviour:
  1. In the registry builder, before `return out`, append the FR-250 row only when `(root / ".aidd" / "graphs" / "path-aliases.toon").is_file()`.
  2. In `show`, after the `ui` branch and before `_load_graph`, add: when `e["kind"] == "aliases"` return `alias_graph.show_aliases(root, query, limit)` (message if the module is missing: `alias_graph module not found`).
  3. No change for any other graph.
- Tests first: the T-35 tests `test_registry_has_aliases_only_when_file_exists` and `test_show_prints_neighbours` are red before this task.
- Verify: `python -m unittest discover -s tests -p "test_alias_graph.py" -v` → those two pass; `python -m unittest tests.test_aidd_graphs -v` → exit 0 (no regression).
- Do NOT: touch the `explorer` branch at lines 1118-1133; change refresh/status logic; add any other graph kind.
- Done when: `aidd graphs list` shows `aliases` only with the file and `show` answers as listed.
- Open questions: none.

### T-38 — explorer reads the alias graph and draws SCREEN-901
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: VIEW-new
- Size: M

**Estimate**
- Effort: High
- Agent min: 30
- Human ref hours: 1.5
- Tokens (est): 120k
- Agent role: builder
- Model tier: high
- Wave: 13

**Detail**
- Goal: the layer `aliases` (already a registry-generated layer of the unified explorer) gets the alias-specific view of the approved SCREEN-901 mockup, and the alias `.toon` gets its dedicated reader.
- Cites: FR-253, FR-255, SCREEN-901.
- Depends on: T-36 (and, outside this amendment, T-76, T-83 and T-84 of the 004 amendment).
- Read first: the APPROVED mockup `specs/007-aidd-review-html-close-gate/prototypes/alias-graph-explorer/alias-graph-explorer.html` lines 1-60 (state tokens), 360-420 (legend, empty banner), 470-510 (details rows) and 800-910 (edge and node drawing), and `specs/007-aidd-review-html-close-gate/prototypes/alias-graph-explorer/alias-graph-explorer.sha256`; `specs/004-aidd-graph-first/amendment-unified-explorer.draft.md` (FR-061, FR-064, FR-067, FR-072, T-76, T-83).
- Files to change: `skill/scripts/unified_graph.py` (one reader and one `TOON_READERS` entry), `skill/scripts/graph_explorer.py` (alias view only).
- Naming contract: in `unified_graph.py` the function `_read_aliases_toon(text)` (calls `_sibling("alias_graph")`, returns `to_graph(parse_aliases(text))`, raises `ValueError` when the module is missing) and the entry `TOON_READERS["aliases"] = _read_aliases_toon`; in `graph_explorer.py` the constant `ALIAS_LEGEND = ("old name", "new name", "renamed in progress")`, the JS function `renderAliasView()`, the CSS variables `--alias-old`, `--alias-new`, `--alias-prog` (dark values `#f85149`, `#3fb950`, `#d29922` in `:root`; light values `#d9383a`, `#1a7f37`, `#bf8700` in `:root.light`, all taken from the mockup tokens), element ids `legend-aliases`, `insp-scope`, `insp-reason`, `aliases-empty-banner`; node types `alias_old`, `alias_new`; edge relation `RENAMED_TO`; task-node attribute `state` (`renamed`, `deleted`). Registry-generated and NOT created here: `metric-aliases`, `layer-cb-aliases`, `--layer-aliases`.
- Behaviour:
  1. Register the reader in `unified_graph.py`; no other change there.
  2. Legend `legend-aliases`: shown only when the payload has a layer of kind `aliases`; exactly the three `ALIAS_LEGEND` labels with swatches `--alias-old`, `--alias-new`, `--alias-prog`, plus the text `Edge type: RENAMED_TO` (mockup lines 360-410 and 443).
  3. Canvas: nodes of type `alias_old` and `alias_new` use `--alias-old` and `--alias-new`; edges with relation `RENAMED_TO` get an arrowhead at the target and a `RENAMED_TO` badge at mid-edge, as in mockup lines 807-882; task nodes with `state` `renamed` use `--alias-prog`, `deleted` use `--alias-old`; other nodes unchanged.
  4. Inspector: for an alias node, two rows `insp-scope` and `insp-reason` filled with `textContent` from the node metadata `scope` and `reason` (mockup lines 470-500); hidden for other nodes.
  5. Empty state: when the `aliases` layer exists with 0 nodes or `missing` true, `aliases-empty-banner` shows "No aliases: the project has not generated .aidd/graphs/path-aliases.toon" (mockup line 415).
  6. Mechanical comparison: a test asserts that the mockup's legend labels, `RENAMED_TO`, the empty-state text and the dark and light state-token values appear in the generated HTML; differences are reported, never ignored. Zoom, fit, centre, copy and theme are NOT touched (004 amendment).
- Tests first: T-35 `test_explorer_accepts_toon` and `test_unified_explorer_has_alias_layer` are red before this task.
- Verify: `python -m unittest discover -s tests -p "test_alias_graph.py" -v` → exit 0; `python -m unittest discover -s tests -p "test_unified_*.py" -v` → exit 0 (no regression of the 004 amendment).
- Do NOT: create the layer pill, checkbox or layer colour (registry-generated); add or change any control; change the JSON input handling, other layers or node types; copy the legacy presentation of another view; add a dependency or CDN; call Stitch at runtime; use `innerHTML`.
- Done when: both Verify commands pass and the mechanical mockup comparison reports no difference.
- Size: ~110 changed lines.
- Open questions: none.

### T-39 — progress graph attributes and a single reader
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: S

**Estimate**
- Effort: Medium
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 60k
- Agent role: builder
- Model tier: medium
- Wave: 13

**Detail**
- Goal: expose resolved states in the progress graph and remove the duplicate alias reader.
- Cites: FR-256, FR-257.
- Depends on: T-36.
- Read first: `skill/scripts/aidd_progress.py` the graph writer that builds the progress graph task nodes (search `"type": "T"`), `_load_aliases` and `task_state`.
- Files to change: `skill/scripts/aidd_progress.py`.
- Naming contract: no new public names; add key `state` to task nodes only when the task state is `renamed` or the task is delete-only and satisfied (`deleted`); `_load_aliases(root)` returns the same `{old: new}` dict as before but obtained from `alias_graph.load_aliases`.
- Behaviour:
  1. Task node gets `state` as above; absent otherwise (a task with no resolution keeps its exact current dict).
  2. `_load_aliases` calls `alias_graph.load_aliases` and builds the dict from the rows; keeps the per-root cache.
- Tests first: T-35 `test_progress_graph_task_state` is red before this task; the amendment-04 tests (`test_progress_resolution.py`) must stay green.
- Verify: `python -m unittest tests.test_aidd_progress tests.test_progress_resolution -v` → exit 0, and the T-35 file → exit 0.
- Do NOT: change `task_state` results or the printed output of `aidd progress`; add dependencies.
- Done when: both commands pass.
- Open questions: none.

### T-40 — mirrors
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
- Wave: 14

**Detail**
- Goal: keep the project bundle identical to the skill source.
- Cites: FR-250..FR-257 (mirror).
- Depends on: T-37, T-38, T-39.
- Read first: `tests/test_dot_aidd_mirror.py`.
- Files to change: `adapters/dot-aidd/scripts/alias_graph.py`, `adapters/dot-aidd/scripts/aidd_graphs.py`, `adapters/dot-aidd/scripts/graph_explorer.py`, `adapters/dot-aidd/scripts/unified_graph.py`, `adapters/dot-aidd/scripts/aidd_progress.py`, `tests/test_dot_aidd_mirror.py`.
- Naming contract: none new; each script target is a byte copy of its `skill/scripts` source; the guard list `VERBATIM_SCRIPTS` gains the entry `"alias_graph.py"`.
- Behaviour: five `cp` commands; then `cmp` each pair; then the one-line list insertion; no other hand edit.
- Tests first: `tests.test_dot_aidd_mirror` fails after T-36..T-39 until the copies exist.
- Verify: `python -m unittest tests.test_dot_aidd_mirror -v` → exit 0.
- Do NOT: edit any copy by hand; touch other mirrors.
- Done when: the mirror test passes.
- Open questions: none.

### T-41 — document
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
- Wave: 14

**Detail**
- Goal: document the registered alias graph and its explorer view.
- Cites: FR-251, FR-253.
- Depends on: T-37, T-38.
- Read first: `skill/SKILL.md` the paragraph titled "Task state in `aidd progress` and `aidd pending`" and the `aidd graphs` description.
- Files to change: `skill/SKILL.md`.
- Naming contract: documents exactly: graph name `aliases`, kind `aliases`, file `.aidd/graphs/path-aliases.toon`, commands `aidd graphs show aliases <name>`, `aidd graphs explorer aliases` and `aidd graphs explorer` (the unified explorer shows it as the layer `aliases`), node types `alias_old` and `alias_new`, edge `RENAMED_TO`.
- Behaviour: add 3 lines after the paragraph named in Read first: registration, the three commands, the node and edge names.
- Tests first: no code; the check below exits 1 before this task and 0 after.
- Verify: `python -c "import sys; sys.exit(0 if 'RENAMED_TO' in open('skill/SKILL.md', encoding='utf-8').read() else 1)"` -> exit 0.
- Do NOT: change any other section; mention b1SycLink.
- Done when: the three lines exist and the check passes.
- Open questions: none.

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-01, T-02, T-03, T-04 | builder | 24 | 450 | 1.2 |
| 2 | T-05, T-06, T-07, T-08, T-09, T-12 | builder, docs | 26 | 580 | 1.3 |
| 3 | T-10, T-11 | auditor, tests | 12 | 175 | 0.6 |
| 4 | T-13 | builder | 25 | 150 | 1.25 |
| 5 | T-14 | builder | 20 | 120 | 1.0 |
| 6 | T-15 | builder | 15 | 95 | 0.75 |
| 7 | T-16 | builder | 20 | 130 | 1.0 |
| 8 | T-22, T-26 | tests | 15 | 140 | 0.75 |
| 9 | T-23, T-25, T-27 | builder, docs | 25 | 240 | 1.25 |
| 10 | T-24, T-28, T-29 | builder, docs | 5 | 70 | 0.25 |
| 11 | T-30, T-35, T-43 | tests | 20 | 240 | 1 |
| 12 | T-31, T-36, T-44 | builder | 30 | 310 | 1.5 |
| 13 | T-32, T-33, T-34, T-37, T-38, T-39 | builder, docs | 30 | 320 | 1.5 |
| 14 | T-40, T-41 | builder, docs | 5 | 50 | 0.25 |

Dependency edges: T-05 and T-06 need T-01, T-02, T-03; T-07 needs T-01, T-02; T-08 needs T-02; T-12 needs T-01; T-10 needs T-01..T-09 and T-12; T-11 needs T-03, T-04, T-05, T-06. T-01..T-04 have no incoming edge: T-03 never reads `templates/review.html` (it tests against a minimal inline `template_text`), T-02 tests against a `FakeEv`, and the real template is first rendered by T-11. T-09 has no code edge; it is in wave 2 only so its prose reads the finished code. Wave 3 audits and executes only what exists; the fix batch (CONFIRMED medium+ findings only, back to each file's original owner via SendMessage, about 15 min) is not counted below.

Total agent time (critical path): 272 min
Total tokens (k): 3070

Amendment 05/06 dependency edges (waves 11-14 recomputed by a scratchpad script from the task blocks: agent time and human hours are the maximum per wave, tokens the sum): T-31 needs T-30 and T-27; T-44 needs T-43; T-32 needs T-31; T-33 and T-34 need T-31 and T-44; T-36 needs T-35; T-37, T-38 and T-39 need T-36; T-40 needs T-37, T-38, T-39; T-41 needs T-37, T-38. Shared files are split across waves: `skill/SKILL.md` T-34 (wave 13) and T-41 (wave 14); `tests/test_dot_aidd_mirror.py` T-33 (wave 13) and T-40 (wave 14). Cross-spec note, not a task dependency: amendment 06 (T-35..T-41) starts only after wave 10 of `specs/004-aidd-graph-first/amendment-unified-explorer.draft.md` (plan.md "Amendment 06"); amendment 05 has no such dependency, so if spec 004 is late, waves 11-13 run with only their amendment 05 tasks. After wave 14 one verifier runs V-12..V-20 of spec.md once.

Amendment 01 dependency chain: T-13 → T-14 → T-15 → T-16; the same owner handles all four shared files. The focalized unittest commands in those tasks are wave checks; V-1 full discovery covers them at final verification and does not add duplicate V-7/V-8 rows.

Amendment 03/04 dependency edges: T-23 needs T-22; T-24 needs T-23; T-27 needs T-26; T-28 and T-29 need T-27; T-25 has no code edge (text only; ships with T-23). Amendments 03 and 04 touch disjoint production files; the two `skill/SKILL.md` edits (T-25 wave 9, T-29 wave 10) are in different waves. After wave 10 one verifier runs V-7..V-11 of spec.md once, then an independent read-only security auditor reviews the diff (domains: security, functional).

## Approval gate

**Present the table above as a dry-run and wait for explicit approval before Step 5 starts on any row.**
The approval is the user's and is tamper-evident: ask them (AskUserQuestion) to approve the tasks, then run `aidd rules approve <spec_dir>`, which replaces the line below with `Approved: <YYYY-MM-DD> hash:<12 hex>`. Any later edit to this file voids it. Do not write that line by hand.

Approved: 2026-11-03 hash:0fc10544afb0

## Definition of Done (applies to every task above)
1. Code implements exactly the FR cited, in exactly the target file, following plan.md's Naming & File Contract, SOLID and the antifragile standard.
2. The owner's own test files pass; mirrors are byte-identical; the full suite passes at the end of each wave (serialized, one runner at a time), including `test_dot_aidd_mirror`.
3. Mapping row and execution evidence added to `qa-audit.md` for every FR touched (R10).
4. No screens: the screenshot item does not apply to the code tasks; the page itself is verified in a real browser by T-11.
