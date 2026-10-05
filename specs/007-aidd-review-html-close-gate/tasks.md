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

FR-205 and FR-206 have no installed effect until the owner installs the new scripts; the close of spec 007 itself goes through the legacy path (it was approved before `gate: 2` existed), see spec.md "Bootstrap".

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

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-01, T-02, T-03, T-04 | builder | 24 | 450 | 1.2 |
| 2 | T-05, T-06, T-07, T-08, T-09, T-12 | builder, docs | 26 | 580 | 1.3 |
| 3 | T-10, T-11 | auditor, tests | 12 | 175 | 0.6 |

Dependency edges: T-05 and T-06 need T-01, T-02, T-03; T-07 needs T-01, T-02; T-08 needs T-02; T-12 needs T-01; T-10 needs T-01..T-09 and T-12; T-11 needs T-03, T-04, T-05, T-06. T-01..T-04 have no incoming edge: T-03 never reads `templates/review.html` (it tests against a minimal inline `template_text`), T-02 tests against a `FakeEv`, and the real template is first rendered by T-11. T-09 has no code edge; it is in wave 2 only so its prose reads the finished code. Wave 3 audits and executes only what exists; the fix batch (CONFIRMED medium+ findings only, back to each file's original owner via SendMessage, about 15 min) is not counted below.

Total agent time (critical path): 62 min
Total tokens (k): 1205

## Approval gate

**Present the table above as a dry-run and wait for explicit approval before Step 5 starts on any row.**
The approval is the user's and is tamper-evident: ask them (AskUserQuestion) to approve the tasks, then run `aidd rules approve <spec_dir>`, which replaces the line below with `Approved: <YYYY-MM-DD> hash:<12 hex>`. Any later edit to this file voids it. Do not write that line by hand.

Approved: 2026-10-05 hash:73c2d22c3ff6

## Definition of Done (applies to every task above)
1. Code implements exactly the FR cited, in exactly the target file, following plan.md's Naming & File Contract, SOLID and the antifragile standard.
2. The owner's own test files pass; mirrors are byte-identical; the full suite passes at the end of each wave (serialized, one runner at a time), including `test_dot_aidd_mirror`.
3. Mapping row and execution evidence added to `qa-audit.md` for every FR touched (R10).
4. No screens: the screenshot item does not apply to the code tasks; the page itself is verified in a real browser by T-11.
