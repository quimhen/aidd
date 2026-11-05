# Plan — AIDD 007: review-driven approval, per-spec R6, executed close gate

DRAFT (revision 2) for `specs/007-aidd-review-html-close-gate/plan.md`. Every builder prompt restates the Naming & File Contract below; names are exact and fixed so that tasks in the same wave code against an interface that does not exist yet.

## Naming & File Contract (fill this first — everything below depends on it)

| Item | Convention |
|---|---|
| Classes / components / types | None added (stdlib Python modules; the page is one HTML file) |
| Functions / variables | snake_case; private helpers prefixed `_`; constants UPPER_SNAKE (matches `_code_gate`, `_approval_gate`, `approval_valid`) |
| File names | snake_case `.py`; hooks in `skill/hooks/`, library and CLI logic in `skill/scripts/`, templates in `skill/templates/`, tests `tests/test_<area>.py` |
| Classes per file | One. New files: `skill/scripts/aidd_review.py`, `skill/templates/review.html`, `tests/test_aidd_review.py`, `tests/test_review_template.py`, `tests/e2e_review_roundtrip.py` |
| Style | Python stdlib only, UTF-8 and `newline='\n'` on every file IO, hooks fail open (exit 0 + `hook_error`), CLI never prints a traceback, every disk/subprocess call can fail |
| Markers in source | `aidd:FR-2nn` comments on new functions, as in 006 |

No database objects in this feature.

### Exact interfaces (frozen; owners may add private helpers, never rename these)

**`skill/scripts/aidd_evidence.py` (T-01)**

| Name | Contract |
|---|---|
| `PROJECT_KINDS` | adds `'verify_run'`, `'rules_override'`, `'gate_pointer'`, `'stop_reminder'` |
| `GATE_POINTER_FILE = '.aidd/gate_spec'` | the gate pointer; plain text, one sanitised spec id; R9 already protects `.aidd/` (everything but `memory/`) |
| `get_gate_spec(root) -> str` | content of the file or `''`; never raises |
| `activate_spec(root, spec_id, by='cli') -> bool` | True only if `root/specs/<spec_id>` is a directory and the id is in `open_specs(root, include_approved=True)`; id sanitised like `set_active_spec`; writes the gate pointer file (atomic) and appends `gate_pointer{spec, prev, by}` when the value changed. The ONLY writer of the gate pointer (called by `aidd rules activate` and `aidd rules approve`); `set_active_spec` is untouched and informational |
| `recent_gate_pointer_changes(root, n=5) -> list[dict]` | newest `gate_pointer` details with `ts`, newest first |
| `gate_target_specs(root) -> tuple[list[str], bool, str]` | `(ids, ambiguous, how)`. Let `open = open_specs(root)`. (1) `get_gate_spec` matches (case-insensitive) an id of `open` -> `([it], False, 'pointer')`. (2) `len(open)==1` -> `(open, False, 'only')`; `0` -> `([], False, 'none')`. (3) else the open spec whose newest `spec_edit` event with `file` in `('plan.md','tasks.md')` is the newest of all open specs -> `([it], False, 'inferred')`; a spec with only `spec.md`/other edits is never inferred. (4) else `([], True, 'ambiguous')`. Never reads `active_spec`. Never raises (`([], False, 'none')` on error, fail-open like the other readers) |
| `append_approved(root, session, spec, hash, **extra)` | existing signature plus `extra` merged into the event detail (callers pass `gate=2, source=..., consent_ts=..., verify_hash=..., review_sha1=...`). Backward compatible |
| `latest_approved(root, spec, hash=None) -> dict \| None` | newest `approved` event detail (plus `ts`) for `spec` (and `hash` when given), else None |
| `append_verify_run(root, session, spec, ok, verify_hash, results, started, fingerprint_start, fingerprint_end, stable) -> bool` | appends `verify_run{...}`; bool like `append` |
| `latest_verify_run(root, spec) -> dict \| None` | newest `verify_run` for `spec` as `{ts, ok, verify_hash, started, fingerprint_start, fingerprint_end, stable, results}` |
| `last_code_edit_ts(root) -> float` | newest `code_edit` ts of any spec, `0.0` if none |
| `code_edits_for(root, spec, since_ts, include_unstamped=True) -> list[dict]` | `code_edit` events after `since_ts` whose detail `target` equals `spec` (case-insensitive); events with NO `target` key (legacy) count when `include_unstamped`; a stamped empty `target` counts as unattributed (returned only when `include_unstamped`) |
| `worktree_fingerprint(root, budget_s=8.0) -> str \| None` | git available: sha1[:16] over `git rev-parse HEAD`, `git diff HEAD` (excluding `:(exclude)specs`, `:(exclude).aidd`) and, for each untracked non-ignored path outside `specs/` and `.aidd/` (`git ls-files -o --exclude-standard`), the path plus a content sha1 (files over 1 MB: size + mtime). Not a git repo or git failing: sha1[:16] of the sorted `(relpath, size, mtime_ns)` of project files outside `specs/`, `.aidd/`, `.git/`, `node_modules/`, `bin/`, `obj/`, `__pycache__/`, capped at 20 000 files. Over the cap or over `budget_s`: `None` (callers then rely on the `code_edit` rule only). List-form subprocess, 5 s per git call, never raises |

**`skill/scripts/aidd_rules.py` (T-02)**

| Name | Contract |
|---|---|
| `GATE_VERSION = 2` | value stored as `gate` in new `approved` events |
| `parse_verification(spec_text) -> list[dict]` | rows of `## Verification` as `{n, cmd, expected, covers}`; rows with an empty command (template placeholders) are skipped; cells are `_clean`ed, backticks stripped from `cmd` |
| `verification_hash(spec_text) -> str` | sha1[:12] of the normalised `n\|cmd\|expected` rows joined by `\n` (prose edits do not change it); `''` when there are no rows |
| `verification_command_problem(cmd, expected='exit 0', root=None) -> str \| None` | reason string or None. Rejects: trivial (`^(echo\|true\|exit 0\|:\|rem\|type)\b`, case-insensitive, per line); forbidden text (`.aidd`, `events.toon`, `active_spec`, `gate_spec`, `import aidd_` / `-m aidd_` for `aidd_evidence\|aidd_rules\|aidd_status`, `AIDD_EVIDENCE_DIR=`, `AIDD_TESTING=`, `AIDD_SESSION_ID=`, `AIDD_RULES=`, `review.md`, `tasks.md` together with `Approved`); interpreter inline-code flags (`-c`, `-e`, `/c`, `-Command`, `-EncodedCommand`, `--eval`, `-p`) after `python\|python3\|py\|node\|sh\|bash\|zsh\|cmd\|powershell\|pwsh\|perl\|ruby`; an Expected `contains: X` where X (case-insensitive) occurs in the command text; and a command that is NEITHER a direct runner invocation (`dotnet test`, `npm test`, `npm run <script>`, `pytest`, `python -m unittest <module-or-discover -s <dir>>`, `cargo test`, `go test`, `mvn test`, `gradle test`, `msbuild`) whose manifest exists under `root` (`*.sln`, `*.csproj`, `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `pom.xml`, `build.gradle`, or for `unittest` the named module/dir) NOR an invocation with a token that is an existing path under `root` (script, test file or project). `root=None` skips only the existence checks. Running `python skill/scripts/aidd_review.py ...` is allowed |
| `check_verification(spec_text, root=None) -> list[dict]` | violations (`rule='R10'`, `message`, `fix`): no `## Verification`, no valid row, empty Expected, `verification_command_problem` per row. NOT wired into `_check_spec` (legacy specs unaffected) |
| `approval_evidence(spec_text, source, review_sha1=None, consent_ts=None) -> dict` | `{gate: GATE_VERSION, source, verify_hash: verification_hash(spec_text), [consent_ts], [review_sha1]}` — the ONE place both approval routes build the extras |
| `VERIFY_BAD_OUTPUT_RE`, `verify_output_problem(output, expected) -> str \| None` | `'zero tests ran'` when the output matches `Ran 0 tests`, `NO TESTS RAN`, `No test is available`, `collected 0 items`, `Total tests: 0`; `'output too short'` when fewer than 20 bytes follow the evidence header (unless a `contains:` Expected matched); else None. Used by `aidd_status.cmd_verify` |
| `verification_gaps(ev, root, spec_dir) -> list[dict]` | close-time check for `gate: 2` specs (rule `R10`): `check_verification`; newest `verify_run` exists, `ok` and `stable`; `verify_hash == verification_hash(spec.md) == latest_approved(...).verify_hash`; `ev.last_code_edit_ts(root) <= run.started`; when `run.fingerprint_end` is not None, `ev.worktree_fingerprint(root) == run.fingerprint_end`; each `results[].evidence` file exists under the spec dir and its sha1 equals `results[].sha1` |
| `verification_state(spec_dir, root) -> dict` | `{declared: bool, commands: int, status: 'none'\|'never-run'\|'stale'\|'failed'\|'passed', ts: float \| None}`; never raises |
| `CLOSING_AUDIT_RE`, `CLOSING_AUDIT_MIN_RESULT = 1500`, `closing_audit_header(event) -> dict \| None` | parses the FIRST line of `head` (or `desc`) for `CLOSING AUDIT [domains: a, b] [tasks:<h8>] [verify:<v8>]`; returns `{domains:set, tasks:str, verify:str}` or None |
| `closing_audit_covers(event, spec_dir, domains, gate2, ev, root) -> bool` | True only when the header exists, its domains cover `domains`, its `tasks` tag equals `approval_hash(tasks.md)[:8]`, for `gate2` its `verify` tag equals the newest `verify_run.verify_hash[:8]`, and `event.detail.result_chars >= CLOSING_AUDIT_MIN_RESULT` (absent = does not count) |
| `_uncovered(...)` | early return `set()` when some counting subagent after `since_ts` satisfies `closing_audit_covers`; otherwise the existing per-domain matching, untouched |
| `closing_audit_gaps(ev, root, spec_dir) -> list[dict]` | for `gate: 2` specs closed through a closing auditor (R10): `qa-audit.md` contains a table row naming each required domain and the auditor's `tool_use_id`; not applied when coverage came from per-domain auditors |
| `r5_audit_mode() -> str` | `'strict'` if env `AIDD_R5_AUDIT` is `strict` (trimmed, case-insensitive), else `'advisory'` |
| `_evidence_rules` | when `r5_audit_mode() == 'advisory'` the "No independent subagent (Mapper/Alignment)" and "No pre-build coherence audit" violations are NOT emitted; all other R5 checks unchanged. `mapper_since`, `pre_build_since`, `pre_build_audit_done` stay pure helpers |

**`skill/scripts/aidd_review.py` (T-03)** (new, stdlib only, importable alone; `aidd_rules` imported lazily)

| Name | Contract |
|---|---|
| `SOURCES = ('spec.md','plan.md','tasks.md','mockup-audit.md','contracts.md')` | order of panels; absent files are listed as absent |
| `MAX_REVIEW_SOURCE_CHARS = 400_000` | per source. Over the cap `generate` raises `ValueError('<file> is <n> chars (limit 400000): split the spec')` and nothing is truncated; `review_state` returns `complete False, reason 'source too large: <file>'`; keys and digest are computed from exactly the text rendered |
| `slugify(text) -> str` | NFKD strip accents, lowercase, `[^a-z0-9]+` -> `-`, trim `-`, empty -> `section` |
| `parse_headings(md, source) -> list[tuple[str,int,str,int]]` | `(key, level, text, line_no)` for ATX headings level 1-4 outside fenced code; `key = '<source-stem>/<slug>'`, duplicates in one file get `-2`, `-3`; only levels 2-3 are reviewable |
| `reviewable_keys(spec_dir) -> list[str]` | keys of level 2-3 headings over all present sources, in order (the same text `build_html` renders) |
| `safe_url(url, image=False) -> str \| None` | the URL allow-list: returns the URL or None. None when the URL has any char `< 0x20`, DEL, any `str.isspace()` char or a backslash; starts with `/`; has a `:` before the first `/`, `?` or `#` and the scheme is not `http`/`https` (case-insensitive) or `image` is True; or has a `..` segment (also after `urllib.parse.unquote`, applied twice) |
| `render_markdown(md, source, keys, base_dir) -> str` | escape first (`html.escape` on every raw line AND on every attribute value), fixed tag set, fenced code, ATX headings wrapped in `<section data-key="..">` (spec.md `## Verification` additionally gets `data-mandatory="1"` and class `mandatory`), tables, nested lists, blockquote, hr, paragraphs, source `- [ ]` as disabled inputs, inline `code`, `**`, `*`, links, images; URLs only through `safe_url`, otherwise the text is shown literally; links `rel="noopener noreferrer" target="_blank"`, images `loading="lazy"`; no raw HTML; no `style=`/`on*=` attribute is ever emitted; mermaid shown as code |
| `sources_digest(spec_dir) -> str` | sha1[:12] over `name\0content` of the present sources in `SOURCES` order; for `tasks.md` the content is `rules.approval_hash(text)` (so the `Approved:` line and Status/Tracker/PR-ref cells are neutral); for the others the CRLF-normalised UTF-8 bytes |
| `TEMPLATE_TOKENS` | `{{TITLE}}`, `{{SPEC_ID}}`, `{{TASKS_HASH}}` (12 hex), `{{TASKS_HASH8}}`, `{{SOURCES_DIGEST}}`, `{{GENERATED}}`, `{{BODY}}`, `{{DATA_JSON}}`, `{{SCRIPT_SHA256}}` (base64 sha256 of the exact text between `<script id="aidd-js">` and `</script>`) |
| `build_html(spec_dir, prior=None, template_text=None) -> str` | fills the template (default: the file `Path(__file__).resolve().parent.parent/'templates'/'review.html'`; `template_text` exists ONLY so tests can pass a minimal template, it is never exposed through the CLI or an env var); `str.replace` on the tokens; data blob `<script type="application/json" id="aidd-data">` via `json.dumps(ensure_ascii=True)` with `<`, `>`, `&` replaced by `\u003c`, `\u003e`, `\u0026`; prepends the `check_verification` problems (if any) as a visible warning box in `{{BODY}}` |
| `generate(spec_dir, template_text=None) -> tuple[Path, bool]` | writes `specs/<id>/review.html` atomically (tmp + `os.replace`); returns `(path, wrote)`; `wrote=False` and the file untouched when an existing page already carries the same `sources_digest` and `tasks_hash`; refuses (raises `ValueError`) without tasks.md and over `MAX_REVIEW_SOURCE_CHARS`; pre-fills `prior` from an existing `review.md` only if its `tasks_hash` and `sources_digest` match |
| `parse_review(text) -> dict` | `{'ok', 'errors', 'warnings', 'meta', 'sections': {key: {'approved': bool, 'comment': str}}}`; grammar below; CRLF tolerated; duplicate blocks: last wins + warning; never raises; refuses text > 2 MB |
| `review_state(spec_dir) -> dict` | `{present, valid, hash_ok, digest_ok, fresh, complete, missing[], comments[{key,text}], sha1, reviewed, mtime, page_current, reason}`. `hash_ok`: `meta.tasks_hash == rules.approval_hash(tasks.md)`; `digest_ok`: `meta.sources_digest == sources_digest(spec_dir)`; `fresh`: `review.html` exists and `mtime(review.md) > mtime(review.html)`; `page_current`: `review.html` exists and carries the current `sources_digest`; `complete` = ok and hash_ok and digest_ok and fresh and `meta.approved is True` and every key of `reviewable_keys` is checked and no source is oversize. Pure read. `complete` is CONTENT only: it is never sufficient to approve |
| `prompt_consent(ev, root, session, tag, since_ts) -> dict \| None` | the newest hook-recorded `prompt` event of `session` (or `unknown-session`) with `ts > since_ts` whose normalised text contains `tag.lower()`, matches `\b(approve\|approved\|aprobar\|aprobado\|apruebo)\b` and does not match `\b(not\|no\|don'?t\|do not\|never\|nunca\|reject\|rechaz\w*)\b`; returns `{'kind':'prompt','ts':ts}` else None. Reads only `ev.events(root, kind='prompt', ...)`. The answer route stays in the callers (`_affirm`, `affirmative_answer`) |
| `main(argv) -> int` | `aidd_review.py <spec_dir> [--open] [--check] [--comments]`; default generates (exit 1 with the reason on `ValueError`); `--open` uses `webbrowser`; `--check` prints the state, exit 0 complete / 2 incomplete / 3 stale or invalid; `--comments` prints `<key>: <text>` lines. Prints the path and the `file://` URI |

**review.md grammar (written by the page JS, read by `parse_review`)**

```
---
spec: F23-eDoc-POS
tasks_hash: <12 hex>
sources_digest: <12 hex>
approved: true|false
generated: YYYY-MM-DD
reviewed: YYYY-MM-DDTHH:MM:SS
---
## tasks/t-07-api-endpoints
- [x] Approved
> comment line 1
> comment line 2
```

Front matter: first two `---` lines, flat `key: value`, unknown keys ignored; required `spec`, `tasks_hash` (`^[0-9a-f]{12}$`), `sources_digest` (same), `approved`. Block header `^##\s+(\S+)\s*(?:<!--.*-->)?$`; check `^- \[( |x|X)\] Approved\s*$` (first one after the header wins); comment = consecutive `^>` lines; the JS prefixes EVERY comment line with `> ` so a comment can never open a block or the front matter.

**`skill/templates/review.html` (T-04)**: static shell, inline CSS (light/dark through `prefers-color-scheme`, 16 px gutter, usable at phone width) and ~170 lines of inline JS in ONE `<script id="aidd-js">` whose text is a constant of the template (no per-spec data inside it). CSP meta: `default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; script-src 'sha256-{{SCRIPT_SHA256}}'; base-uri 'none'; form-action 'none'` (no `'unsafe-inline'` for scripts; no inline event handler anywhere; if T-11 shows relative images blocked from `file://`, use `img-src file: data:`). Per section checkbox + textarea keyed by `data-key`; header with spec id, `tasks hash <8>`, progress counter, per-file "check all" and "Approve all" that SKIP `data-mandatory` sections (those are checked one by one and sit in a highlighted box), "Send" (builds the review.md text with a pure function `buildReviewMd(data)` and downloads it as `review.md`), a banner telling the owner to move the file into `specs/<id>/` AND showing the consent line `approve [tasks:<hash8>]` with a copy button (the owner pastes it to the agent, or answers the tagged question); prior state from the data blob; localStorage in try/catch keyed by spec id + tasks hash + digest; no `http(s)://` resource; prints on a `<noscript>` how to review without JS.

**`skill/scripts/aidd_status.py` (T-05)** adds: `cmd_activate(spec_arg)`, `cmd_verify(spec_arg)`, `_review_approval(d, root, text)` (wraps `aidd_review.review_state`), `_consent(ev, root, sess, d, tag, rs, tty=None)` (answer -> prompt -> TTY; returns `(kind, ts)` or None), `_tty_confirm(tag, isatty=None, reader=input)` (requires `stdin.isatty() and stdout.isatty()`; the owner types the tag; injectable for tests), `_gate_version(root, d, tasks_text)`, `_derived_facts(root)`, `_git(root, *args)`, `format_refresh(facts)`; dispatch `('rules','activate')`, `('verify', <spec>)`, flag `--refresh` of `status`. `cmd_approve` order: resolve spec -> `check_content('tasks')` -> `rules.check_verification(spec.md, root)` -> if `review_state.page_current` and the review is `complete`: `_consent` (refuse with the owner instructions when none) and mint `source=review+<kind>`; if `page_current` and not `complete`: refuse naming the cause (the answer-only route is refused while a current page exists); if no current page (never generated, or sources over the cap): the existing answer route, `source=answer` -> write `Approved:` line -> `ev.append_approved(..., **rules.approval_evidence(...))` -> `ev.activate_spec(root, spec, by='approve')`. `cmd_verify` records `started`, `ev.worktree_fingerprint` before the first row and after the last, `stable = fp_start == fp_end` (both None counts as stable), applies `rules.verify_output_problem`, and calls `ev.append_verify_run(...)`. `_close_gaps`: `gate: 2` specs use `rules.verification_gaps`, `rules.closing_audit_gaps` and a closing-audit window `since = max(last code edit, verify_run.ts)`; legacy specs unchanged. `build_status` gains `review`, `verification`, `overrides`, `r5_mode`, `gate_pointer` (+ last changes), `rules_mode` (effective `AIDD_RULES`), per approved spec the count of `ev.code_edits_for(...)`.

**`skill/hooks/rule_gate.py` (T-06)**: `_code_gate` uses `ev.gate_target_specs` (3-tuple; with an `AttributeError`/unpack fallback to `open_specs` for an older mirror); ambiguous -> ONE R6 violation listing up to 5 open ids and `aidd rules activate <id>`; other cases ONE violation naming the target, `how` and the unblock path. `_approval_gate`: `rules.check_verification`; `review_state(d)['complete']` AND a consent act newer than `review.md` (`_affirm(ev, root, session, since=max(tasks_last_change, review_mtime), tag)` or `aidd_review.prompt_consent`), never the TTY route and never review.md alone; mints `approved` with `rules.approval_evidence(..., source='review+answer'|'review+prompt', consent_ts=...)`; when a current page exists and the review is not complete the plain `_affirm` route is refused too; refusal text names both consent options and the tag. `_decide_path`: block Write/Edit/MultiEdit/NotebookEdit of `specs/<any-id>/review.md` and `review.html` (`USER_ONLY_SPEC_FILES`, canonicalised names including trailing dots/spaces and `::$DATA`). Bash: `_specs_tok` additionally returns True for ANY path that contains a `specs/<segment>/` pair when the leaf is `review.md` or `review.html` (non-numeric ids included); `_shell_block` gets a text-level rule next to the `tasks.md`+`approved` one (L979): with `low2 = low.replace('\\','/')`, if `'review.md'` or `'review.html'` is in `low2` and (`ctx['writes']` or `_script_write(low)` or the verb set contains a mover/copier/writer/deleter: `cp mv copy move ren rename del erase rm tee dd install ln rsync xcopy robocopy sed touch truncate copy-item move-item remove-item set-content add-content out-file new-item` or a shell/interpreter verb with an inline script `python -c`, `node -e`, `powershell -command`), return blocked; the `aidd` verb (and `python .../aidd_review.py`) is exempt only when the command has no redirection. `BASH_MARKERS` already contains `specs`; add `review.html` and `review.md` only for completeness (the rule above is what blocks). `_r5_tasks`: skip the pre-build demand when `rules.r5_audit_mode() == 'advisory'`; warn mode appends `rules_override` at each would-be block (best effort). `_common.py` holds `USER_ONLY_SPEC_FILES`.

**`skill/hooks/stop_gate.py`, `skill/hooks/session_start.py`, `skill/hooks/require_graph_coherence_audit.py` (T-07)**: `stop_gate._obligations` iterates `ev.gate_target_specs(root)` ids for the BLOCKING message (ambiguous -> none), and builds a second list `others` = approved open specs not in the target list with `ev.code_edits_for(root, spec, approved_at, include_unstamped=<no target>)` non-empty; `others` is printed ONCE per session (dedupe with `stop_reminder{sid, specs}`) as a JSON `{"systemMessage": ...}` on stdout with exit 0 when nothing blocks (appended to the block message otherwise); `MAX_BLOCKS = int(env AIDD_STOP_BLOCKS or 3)` (invalid -> 3); the block message lists the three closing steps, the `CLOSING AUDIT [domains: ...] [tasks:<h8>] [verify:<v8>]` header built from `rules.required_domains(d)` and the last pointer changes; Stop in `warn` or `off` mode appends `rules_override{hook:'stop_gate', mode}` BEFORE returning. `session_start.py`: records `session_start` as today; when `rules_mode()` is `warn` or `off` appends `rules_override{hook:'session_start', mode}`; prints (stdout, becomes session context) one line per approved open spec in `others` form ("AIDD: spec F21 is approved and has N code edit(s) with no closing audit; target is F23; see `aidd status`"). `require_graph_coherence_audit.evaluate`: when `rules.r5_audit_mode() == 'advisory'` the branch `last_agent_dispatch_ts > last_graph_rebuild_ts` is skipped (return allowed after the find_spec requirement); `strict` keeps today's behaviour.

**`skill/hooks/mark_code_edit.py` and `skill/hooks/mark_agent_dispatch.py` (T-12)**: `mark_code_edit`: the `elif is_code_file(_fp)` branch becomes "is R6-gated" (`_common.is_r6_gated(canon_abs, rel_outermost)` per root; `is_code_file` stays for the legacy `require_aidd` gate) and the appended `code_edit` carries `target=<ev.get_gate_spec(root)>` and `active=<ev.get_active_spec(root)>` (guarded with `getattr` for an older library; failures never lose the base event). The spec-file branch is unchanged (still sets the informational `active_spec`). `mark_agent_dispatch`: on the counting `subagent` row add `result_chars` and `result_sha1` computed by `_response_text(event.get('tool_response'))` (string; dict with `content` list of `{type:'text', text}` or `result`/`output`/`text`; list of those); absent when no text is found. First step of the task: capture the real payload shape from a live PostToolUse of the Agent tool (print the keys to a scratch file) and report it before coding the extractor (Open decision O-10).

**`skill/scripts/check_spec.py` (T-08)**: banner after the `=` rule; success line `No mechanical gaps found (structural only). ...`.

**`aidd/cli.py` (T-03)**: `cmd_review(args)` -> `_run('aidd_review.py', [args.spec_dir, *args.review_flags])`; `review` subparser (`spec_dir` positional + REMAINDER flags); `verify` passthrough to `aidd_status.py verify <spec>` and `p_status` help mentions `--refresh`; `main()` short-circuits `verify` like `status`/`rules`.

### Events, env, files

| Item | Definition |
|---|---|
| `approved` | `{spec, hash, gate: 2, source: 'review+answer'\|'review+prompt'\|'review+tty'\|'answer', consent_ts, verify_hash, review_sha1?}` |
| `verify_run` | `{spec, ok, verify_hash, started, fingerprint_start, fingerprint_end, stable, results: [{n, cmd, exit, ok, evidence, sha1}]}` |
| `rules_override` | `{hook, mode, rules?}` (project kind, only with a known root) |
| `gate_pointer` | `{spec, prev, by}` |
| `stop_reminder` | `{sid, specs}` |
| `code_edit` | `{path, target?, active?}` |
| `subagent` | existing fields plus `result_chars?`, `result_sha1?` |
| Env | `AIDD_R5_AUDIT` (advisory\|strict), `AIDD_STOP_BLOCKS` (3), `AIDD_VERIFY_TIMEOUT` (600) |
| Files | `.aidd/gate_spec`; `specs/<id>/review.html` (generated), `specs/<id>/review.md` (owner answer); `specs/<id>/evidence/verify-<n>.txt`: first line `# <cmd> | exit <code> | <ISO ts>`, then combined stdout+stderr |
| Spec sections | `## Verification` table `| # | Command | Expected | Covers |`; `## Optimization brief` |

## Requirement -> file map (the Screen -> Code equivalent; no screens in this spec)

| FR | File / function | Test file | Task | Notes |
|---|---|---|---|---|
| FR-201 | `aidd_evidence.py` `gate_target_specs`, `get_gate_spec`, `activate_spec`; `rule_gate.py` `_code_gate`; `aidd_status.py` `cmd_activate` + approve activates | `test_evidence.py`, `test_rule_gate.py`, `test_aidd_status.py` | T-01, T-06, T-05 | message names the target, `how`, and `aidd review` / `aidd rules activate` |
| FR-202 | `aidd_review.py` `safe_url`, `parse_headings`, `render_markdown`, `build_html`, `generate`; `templates/review.html`; `aidd/cli.py` `cmd_review` | `test_aidd_review.py`, `test_review_template.py`, `e2e_review_roundtrip.py` | T-03, T-04, T-11 | XSS list (AC-204) in the tests and in a real browser; oversize refusal |
| FR-203 | `aidd_review.py` `sources_digest`, `parse_review`, `review_state`, `main --check/--comments`; page JS `buildReviewMd` | `test_aidd_review.py`, `test_review_template.py` (node serializer), `e2e_review_roundtrip.py` | T-03, T-04, T-11 | grammar above; `approval_hash`-based digest |
| FR-204 | `aidd_review.py` `prompt_consent`; `aidd_status.py` `cmd_approve` / `_consent` / `_tty_confirm`; `rule_gate.py` `_approval_gate`, `_decide_path`, `_specs_tok`, `_shell_block`; `aidd_evidence.py` `append_approved`, `latest_approved`; `aidd_rules.py` `approval_evidence` | `test_aidd_review.py`, `test_aidd_status.py`, `test_rule_gate.py`, `test_evidence.py` | T-03, T-05, T-06, T-01, T-02 | review = content, consent = trust root; AskUserQuestion route unchanged |
| FR-205 | `aidd_rules.py` `parse_verification`, `verification_hash`, `verification_command_problem`, `check_verification`, `verify_output_problem`, `verification_gaps`, `verification_state`; `aidd_evidence.py` `append_verify_run`, `latest_verify_run`, `last_code_edit_ts`, `worktree_fingerprint`; `aidd_status.py` `cmd_verify`, `_close_gaps` | `test_aidd_rules.py`, `test_evidence.py`, `test_aidd_status.py` | T-02, T-01, T-05 | legacy = no `gate` in `approved` |
| FR-206 | `aidd_rules.py` `closing_audit_header`, `closing_audit_covers`, `closing_audit_gaps`, `_uncovered`, `r5_audit_mode`, `_evidence_rules`; `rule_gate.py` `_r5_tasks`; `require_graph_coherence_audit.py` `evaluate`; `stop_gate.py` `_obligations`, `MAX_BLOCKS` | `test_aidd_rules.py`, `test_r14.py`, `test_rule_gate.py`, `test_stop_gate.py`, `test_hooks.py` | T-02, T-06, T-07 | old per-domain tests pin `AIDD_R5_AUDIT=strict` where they test R5 |
| FR-207 | `templates/spec.md`, `templates/qa-audit.md`, `SKILL.md`, `AIDD.md` and their `adapters/dot-aidd` copies | `test_dot_aidd_mirror.py`, `test_aidd_rules.py` (template passes `check_content('spec')`) | T-09, T-02 | legacy spec without the sections stays valid |
| FR-208 | `aidd_status.py` `_derived_facts`, `format_refresh`, `build_status`; `check_spec.py` banner; `session_start.py`, `stop_gate.py`, `rule_gate.py` `rules_override`; docs deprecation text | `test_aidd_status.py`, `test_check_spec.py`, `test_rule_gate.py`, `test_stop_gate.py`, `test_hooks.py` | T-05, T-08, T-06, T-07, T-09 | `git` calls: list form, timeout 5 s |
| FR-209 | `mark_code_edit.py`, `mark_agent_dispatch.py` | `test_hooks.py` | T-12 | write-only and additive; payload shape confirmed first |

Mirror matrix (same owner copies, byte-identical, in the same task): `aidd_evidence.py` T-01, `aidd_rules.py` T-02, `aidd_review.py` T-03, `templates/review.html` T-04, `aidd_status.py` T-05, `check_spec.py` T-08, `AIDD.md` + `templates/spec.md` + `templates/qa-audit.md` T-09 (`templates/tasks.md` of dot-aidd is a REDUCED variant: never copy over it, and this spec does not touch it). `tests/test_dot_aidd_mirror.py` (T-09) adds `aidd_review.py` to `VERBATIM_SCRIPTS`, plus identity checks for `AIDD.md`, `templates/spec.md`, `templates/qa-audit.md`, `templates/review.html`. Hooks have no mirror.

## Component -> Code map / file ownership

No COMP-nnn. One owner per file; tests live with the production file's owner.

| File | Owner task | Test files owned |
|---|---|---|
| `skill/scripts/aidd_evidence.py` (+mirror) | T-01 | `tests/test_evidence.py` |
| `skill/scripts/aidd_rules.py` (+mirror) | T-02 | `tests/test_aidd_rules.py`, `tests/test_r14.py`, `tests/test_aidd_rules_r10.py` |
| `skill/scripts/aidd_review.py` (+mirror), `aidd/cli.py` | T-03 | `tests/test_aidd_review.py` |
| `skill/templates/review.html` (+mirror) | T-04 | `tests/test_review_template.py` |
| `skill/scripts/aidd_status.py` (+mirror) | T-05 | `tests/test_aidd_status.py`, `tests/test_cli_rules.py`, `tests/test_typed_confirmations.py` |
| `skill/hooks/rule_gate.py`, `skill/hooks/_common.py` | T-06 | `tests/test_rule_gate.py`, `tests/gate_fixtures.py` |
| `skill/hooks/stop_gate.py`, `skill/hooks/session_start.py`, `skill/hooks/require_graph_coherence_audit.py` | T-07 | `tests/test_stop_gate.py` (+ the graph-coherence and session_start cases in a new section of `tests/test_hooks.py` owned by T-12, which also writes the T-07 cases; T-07 does not edit that file) |
| `skill/scripts/check_spec.py` (+mirror) | T-08 | `tests/test_check_spec.py` |
| `skill/SKILL.md`, `skill/AIDD.md`, `skill/templates/spec.md`, `skill/templates/qa-audit.md` + dot-aidd copies | T-09 | `tests/test_dot_aidd_mirror.py` |
| `skill/hooks/mark_code_edit.py`, `skill/hooks/mark_agent_dispatch.py` | T-12 | recorder tests in `tests/test_hooks.py` (T-12 is the sole owner of `tests/test_hooks.py` and also writes the graph-coherence and session_start cases that T-07 specifies) |
| `tests/e2e_review_roundtrip.py` (new) | T-11 | -- |

Untouched on purpose: `install_hooks.py` (no new hook), `templates/tasks.md`, the external skill `aidd-converge`, `rule_gate.main()`'s `AIDD_RULES=off` early return (visibility comes from `session_start`/`stop_gate`).

## Dependency graph and wave split

True edges (an arrow means "needs the other task's finished code to run its tests"):

- T-01, T-02, T-03, T-04 need nothing. The ordering problems of draft 1 are removed by contract, not by sequencing: T-03 tests `build_html`/`generate` against a minimal inline `template_text` (so it never reads `templates/review.html`; the real template is exercised by T-04's token tests and by T-11); T-02's `verification_gaps`/`closing_audit_*`/`verification_state` tests inject a duck-typed `FakeEv` (the functions already take `ev`) instead of T-01's real library; T-04 tests only the template file itself and, for the CSP hash, a tiny local recomputation of the script hash.
- T-05 needs T-01, T-02, T-03. T-06 needs T-01, T-02, T-03. T-07 needs T-01 and T-02 (`gate_target_specs`, `code_edits_for`, `r5_audit_mode`). T-08 needs T-02. T-12 needs T-01 (`get_gate_spec`).
- T-09 (docs) has no code dependency; it sits after wave 1 only so its prose reads the finished library code (R5/R6/R7/R8 rows must match what is enforced).
- T-10 (closing audit) needs T-01..T-09 and T-12; T-11 (executed round trip) needs T-03, T-04, T-05, T-06.

| Wave | Scope | Tasks (owners) | Runs |
|---|---|---|---|
| 1 | Libraries and page, all independent by contract | T-01 evidence, T-02 rules, T-03 review module + CLI, T-04 review.html | in parallel; each owner runs only its own targeted tests |
| 2 | Consumers, recorders and docs | T-05 status, T-06 rule_gate, T-07 stop_gate + session_start + graph-coherence, T-08 check_spec, T-09 docs + mirror test, T-12 recorders | in parallel; main agent runs the FULL suite once at the end of the wave (it is red inside wave 1: the new R5 default breaks old R5 tests until T-06/T-07/T-02 pin `strict`) |
| 3 | Independent verification | T-10 ONE closing auditor (checklist: security, functional, performance), T-11 executed round trip incl. a real browser | in parallel; then the fix batch goes back to the original owners via SendMessage, CONFIRMED medium+ findings only |

Only one builder compiles or runs the suite at a time on the shared working tree; subagents run only their own test files (`python -m unittest tests.<file>`), the main agent runs `python -m unittest discover -s tests` once per wave. `tests/test_hooks.py` has a single owner (T-12), who also writes the cases T-07 specifies. Real wall time: wave 1 about 24 min, wave 2 about 26 min, wave 3 about 12 min (62 min critical path), plus about 15 min for the fix batch and the owner's install into `~/.claude/skills/aidd` and the project `.aidd/` (as in 005/006).

## Tests that change (named, so the builders do not discover them by red runs)

| Test | File (approx. line) | Change | Task |
|---|---|---|---|
| `test_no_mapper_after_spec_edit`, `test_tasks_chain_and_approval`, `test_graph_rebuilt_needs_subagent_after` (and any other `TestCheckSpecDir` case asserting 'Mapper', 'plan.md' pre-build or 'pre-build coherence audit') | tests/test_aidd_rules.py ~502, ~536, ~550 | pin `AIDD_R5_AUDIT=strict` for the class (setUp with `patch.dict(os.environ)`); add advisory twins asserting NO R5 violation for the same fixtures | T-02 |
| R5 cases that expect the old block | tests/test_r14.py, tests/test_rule_gate.py ~1850-1900, `gate_fixtures.py` env | pin strict (fixtures env gets `AIDD_R5_AUDIT=strict`) plus advisory/strict tests | T-02, T-06 |
| `test_b1_every_open_spec_is_checked_not_just_one` | tests/test_rule_gate.py ~720 | rewrite as `test_b1_only_the_gate_target_is_checked`: gate pointer on the approved spec -> allowed although the other is PENDING; pointer on the pending one -> blocked naming it | T-06 |
| `test_mdl_abandoning_one_spec_unblocks_the_other_dead_end` | ~729 | fixture sets the gate pointer explicitly (or asserts the ambiguous message): the ambiguous R6 message MUST list the open spec ids (so `001-x` is still asserted) and `aidd rules activate`; after abandoning one spec the single open spec is the target | T-06 |
| `test_d1_code_gate_never_reads_the_pointer` | ~1344 | keep the assertions (single open spec is blocked whatever the pointer says), rename `test_d1_single_open_spec_is_the_target_whatever_active_spec_says`, add: `.aidd/active_spec` is never read by the gate, a spec with only `spec.md` edits is never inferred | T-06 |
| `test_two_open_specs_both_count_and_abandoning_one_leaves_the_other` | tests/test_stop_gate.py ~194 | rewrite: gate pointer on `001-x` -> the Stop message blocks naming only `001-x` and `002-y` appears in the once-per-session reminder; close `001-x` -> `002-y` is the only open spec and blocks; no pointer + two open -> no block, both listed | T-07 |
| `test_m10_*` | tests/test_stop_gate.py | unchanged semantics (MAX_BLOCKS default is still 3); only the `no distinct ... auditor` wording assertions follow the new message | T-07 |
| code_edit recorder tests | tests/test_hooks.py | `.css`/`.json` edits now produce `code_edit` with `target`/`active` | T-12 |

## Pre-build and closing audits for this spec

No separate pre-build subagent is planned: the human approval of the review of this spec (once `aidd review` exists) or the usual AskUserQuestion approval is the gate, and R5 stays strict while this tool is still the old one. The single closing audit is T-10 and it dogfoods the new convention: its prompt's first line is `CLOSING AUDIT [domains: security, functional, performance] [tasks:<h8>]` and lists the domains as a checklist. Tier: opus for the security item, sonnet acceptable for the rest (never haiku).

## Entry route
Not applicable (no app screens). The review page is opened from `aidd review <spec> --open` or by double-clicking `specs/<id>/review.html`.

## Device targets
| Item | Value |
|---|---|
| Target devices | Windows 11, Python 3.10+ (the zero-test heuristics exist because 3.10/3.11 return 0 for an empty `unittest discover`), Chrome/Edge/Firefox for `review.html` |
| Orientation / minimum size | Page usable from 360 px width (16 px gutter) |
| Device preflight command | `python -m unittest discover -s tests` (green after wave 2 and after the fix batch) |

## Design system source (Step 0)
| Item | Value |
|---|---|
| Mockup exists? | no (waived in the spec's Pipeline route, pending Open decision O-3) |
| Approved design-system doc (if any) | None. The page follows the AIDD brand-neutral style already used by `docs/` pages if any; otherwise plain system fonts |
| Fidelity level decided in Clarify | Functional behavior only (to confirm at Align) |


## Amendment 01 — safe SQL fingerprints and Scope patterns

The following behavioral contract supplements the historical plan and prevails for this amendment. T-13 through T-16 share one owner and run sequentially.

### Behavioral contract

1. Keep `sql_semantic(text) -> str`, `sql_digest(data) -> str`, `comment_only_edit(path, tool_input) -> bool`, `_scope_re(globs)`, `in_scope(rel, scope_rx)`, `code_state`, `fingerprint_of` and `last_code_edit_ts` callable with their present signatures. Audit all callers before changing a result representation.
2. SQL files are content-hashed from raw bytes, without decoding, lexical analysis, comment removal, line-ending conversion or assumptions about dialect or PostgreSQL `standard_conforming_strings`. `sql_digest(data)` returns SHA-256 hex of the bytes provided; `sql_semantic(text)` returns the input string unchanged (and retains the legacy empty result for `None`); `comment_only_edit(path, tool_input)` returns `False` conservatively, so the existing hook always records SQL writes/edits as code. Keep signatures stable. Revise the now-obsolete comment-only tests to assert this intentionally more conservative behavior; do not weaken tests of distinct input.
3. `_fp_sql_chunk(root, rel)` streams bytes into SHA-256 without the current 5-MiB cutoff or mtime/size memoization. Perform two complete sequential reads with independent SHA-256 digests, compare them and stat before/between/after (at least size and mtime_ns); if any read, stat, digest comparison or budget check fails, refuse the snapshot. Stat alone is insufficient because a concurrent writer can restore attributes. On Git, do not silently discard an SQL path returned by `git ls-files` merely because `os.path.isfile` returns false; missing/unreadable listed SQL must cause an unavailable snapshot, not disappear from `keep`. On non-Git walks, handle `os.walk` enumeration errors and a listed SQL disappearing or failing `stat` as unavailable, not `continue`. Add a distinct `_FpInputUnsafe` exception, which is **not a subclass of** `_FpUnavailable`: `_code_state_scan` may catch `_FpUnavailable` only for genuinely missing/unusable Git and may then use the non-Git scanner; it must propagate `_FpInputUnsafe` without fallback to `code_state`, which returns `None` so verify refuses. `_code_state_git` and `_code_state_mtimes` must never fall back to size/mtime for SQL. An intentional tracked deletion must be staged so Git no longer lists that path before verification. Hash anew on each fresh scan, not solely by cached `(path,size,mtime_ns)`; preserve explicit `code_state(reuse=True)` only for callers already guaranteeing read-only state. Keep budget enforceable during both reads; an optional deadline may be added without breaking the existing two-argument `_fp_sql_chunk` call.

   **Concurrency boundary:** two matching reads and start/end workspace snapshots detect changes observed by those reads; they cannot prove atomicity against an adversarial writer that toggles and restores content between observations. Verification must use an isolated/controlled worktree or a trusted filesystem snapshot/lock where available. The task must document this limit, not claim absolute concurrent-write safety. Test a coordinated mutation during the first read with restored size/mtime and require refusal; explicitly demonstrate the limitation in documentation.
4. Version the affected fingerprint material, not merely its label: every `.sql` chunk produced by `_fp_sql_chunk` includes `sql-raw-v2:` and the raw SHA-256 digest. Prior c2 evidence that includes SQL must not compare equal to new evidence unless a future separately approved migration can prove equivalence. Files outside scope remain irrelevant. Existing non-SQL chunks and complete `c2:` API remain compatible. Expect one fresh verify for impacted old evidence and a reverify for later SQL comment-only changes; semantic optimization is future work requiring explicit dialect/context and proof.
5. Compile root-relative globs with `/` normalization. `*` and `?` never cross `/`; `**/` matches zero or more segments; `**` may span segments; `[0-4]`, `[!a]`, and `[[]` obey standard glob character-class semantics without matching `/`. Match case-sensitively and do not expand environment variables, symlinks or root paths. Accept literal `./` prefix only; reject absolute paths, drive/UNC names, `..` path segments and malformed classes. Invalid nonempty Scope makes `code_state`/verification refuse; invalid Generated makes `fingerprint_of` refuse and does not exclude any file. `last_code_edit_ts` must use all recorded edits without exclusions on invalid patterns, never return a false-safe `0` solely for a pattern error.
6. Both `Scope` and `Generated` share this grammar across `aidd_evidence._scope_re`/`in_scope` and `aidd_rules._glob_hit`, including runtime verification stability, `fingerprint_of` and close evaluation. Refactor `aidd_rules._glob_hit` to delegate to the canonical compiled matcher (lazy import if needed to avoid cycles); invalid patterns match no Generated output and `fingerprint_of`/verification fails closed. `aidd_rules._run_problems` and `aidd_status._json_pass_evidence_problem` must **unconditionally validate the current `Generated:` declaration** before returning a fresh/PASS verdict, even when the recorded run has `code_changed=[]`; malformed current declarations return stale/error rather than bypassing validation because no changed file is iterated. Validate recorded exclusions safely too. Exercise an actual generated file rewrite under a bracket class end-to-end, and a previously successful run with `changed=[]` followed by malformed current Generated through both close and JSON verdict. Preserve `Inputs` as its existing independent Path.glob implementation for this amendment, with representative parity tests. No implicit DB reuse or automatic `Generated` declarations. Generated excludes outputs exactly as before for valid inputs; classification of which files are outputs remains the spec author's responsibility.
7. `skill/scripts/aidd_evidence.py` is canonical. The same owner synchronizes `adapters/dot-aidd/scripts/aidd_evidence.py` using an existing repo tool if one exists, otherwise a scripted copy with dry-run and byte/hash post-check. Do not edit installed copies or `.aidd/` by hand. Tests write only temporary repositories and never use external DBs.
8. Add canonical constant `EVIDENCE_ALGORITHM = 'raw-sql-v2-glob-v2'` in `aidd_evidence.py`. Add `code_algorithm` to `_VERIFY_EXTRA`, aggregate `verify_run`, wave results/result_sink and JSON validation; add `input_algorithm` to each executed result with `Inputs` and in-memory wave-cache keys. Keep prior events and signatures readable, and do not rewrite old events, delete evidence or approvals.

   **Selective historical code-fingerprint migration:** a run lacking `code_algorithm` is not automatically affected solely by that absence. Existing historical execution evidence can continue through the existing R10 checks only when its recorded nonempty Scope and current Scope are identical lists of literal, safe root-relative paths with no `*`, `?`, `[` or `]`, no `.sql` suffix (case-insensitive), and recorded/current Generated are identical, valid literal-only non-SQL lists or both empty; the current `c2:` fingerprint must still match and evidence integrity and all existing R10 conditions must hold. This narrowly proves only that SQL normalization and glob grammar cannot affect that scope; it does not prove the environment. Empty/global scope, SQL in either list, any glob, missing/inconsistent declaration, unknown algorithm marker or unavailable fingerprint is affected or unknown and the previous result is stale until a fresh run. An intentional invalid Generated declaration is always rejected, per 6. Never claim legacy coverage for files outside its declared scope or infer that this scope includes all true runtime dependencies.

   **Row cache and external-state identity:** `input_algorithm` by itself is never proof of the runtime environment, toolchain, non-secret configuration, database/network/clock state or actual isolation. The current code has no independently verifiable trusted environment attestation; therefore neither pre-upgrade nor current-version rows can be automatically returned as `REUSED` or `ROUND-REUSED` while the required environment identity and hermeticity are unverified. This includes multiple specs in one wave; same command and input bytes are insufficient. Emit a concise reason such as `not reusable: environment identity not verified`, execute the row when requested, and preserve historical evidence. A DB-dependent row must never be eligible without a verified matching DB snapshot identity. `--full` continues to run every selected row. This conservative temporary behavior may increase test runtime, including on a second unchanged run; the separate future attestation/reuse amendment must establish a real trustworthy verifier and measure the benefit before enabling caching. Do not invent a verifier, self-certify an environment or retroactively manufacture metadata in this urgent safety fix.

### Test and compatibility map

| Requirement | Target | Verification |
|---|---|---|
| FR-210, FR-212 | `skill/scripts/aidd_evidence.py`; mirror | `tests.test_evidence`, `tests.test_code_fingerprint`; raw SQL bytes, comment-only conservative classification, unreadable/large/same-size-restored-mtime files, old/new chunk incompatibility |
| FR-211, FR-212 | same owner, same source/mirror | `tests.test_code_fingerprint`, `tests.test_verify_regressions`; matching, invalid patterns, stability and generated behavior |
| FR-211 | `skill/scripts/aidd_rules.py`; mirror | `tests.test_aidd_rules`, `tests.test_aidd_status`; `Generated` rewrite and close evaluation agree with evidence matcher |
| FR-212 | `skill/scripts/aidd_status.py`, `skill/scripts/aidd_rules.py`, and canonical evidence module; mirrors | `tests.test_wave_verification`, `tests.test_aidd_status`; unaffected exact non-SQL historical code scope distinguished from affected/unknown; rows without verified environment execute even on a second request; unknown/tampered markers refused |
| FR-213 | `skill/scripts/aidd_evidence.py`; mirror | `tests.test_code_fingerprint`, `tests.test_verify_regressions`; listing/stat/read errors and coordinated same-size/restored-mtime mutation refuse verified snapshot |
| Compatibility | `tests.test_wave_verification` | Existing hermetic reuse and external-state fail-closed behavior unchanged |

An independent audit verifies soundness, generated-output handling, correctness and migration after executed evidence exists.

## Amendment 03/04 (2026-11-03) — naming contract

Names are exact and frozen (copied from the amendment drafts); owners may add private helpers, never rename these. Python stdlib only; snake_case with a leading underscore for module-private helpers. Mirrors are byte copies made by `cp`, never by hand.

### Amendment 03 — cross-spec reuse of offline-contract rows (T-22..T-25)

| Item | Contract |
|---|---|
| File (production) | `skill/scripts/aidd_status.py` (T-23); byte mirror `adapters/dot-aidd/scripts/aidd_status.py` (T-24); docs `skill/SKILL.md` paragraph `**Incremental verification and reusable checks.**` (T-25) |
| File (tests, new) | `tests/test_contract_store.py` (T-22) |
| Constants | `CONTRACT_STORE_VERSION = 'contract-reuse-v1'`, `CONTRACT_STORE_MAX_ENTRIES = 300`, `_DB_RUNNER_RE = re.compile(r'db_verify\|psql\|pg_prove\|docker\|supabase\|--tap', re.I)` (right after `ROUND_MAX_ENTRIES`) |
| `_contract_store_paths(root) -> tuple[Path, Path]` | `(Path(root) / '.aidd' / 'evidence' / f'{CONTRACT_STORE_VERSION}.json', Path(root) / '.aidd' / 'evidence' / CONTRACT_STORE_VERSION)` |
| `_contract_store_key(cmd, expected, inputs, input_fp, declaration, environment_id) -> str` | sha256 hex of `json.dumps([_verification_key(cmd), _verification_key(expected), sorted(inputs), input_fp, declaration.strip(), environment_id], ensure_ascii=True, separators=(',', ':'))` |
| `_contract_store_get(root, key, expected) -> tuple[bytes, dict] \| None` | last index entry with `key`; object bytes returned only when their sha256 equals `entry['sha256']` and `_cached_pass_valid` accepts them; any exception -> `None` |
| `_contract_store_put(root, key, data, result, spec_name) -> None` | object written with mode `'xb'` (never overwritten); index entry replaced by key, capped at `CONTRACT_STORE_MAX_ENTRIES`, written via `<json>.<pid>.tmp` + `os.replace`; exceptions propagate to the caller |
| `_contract_environment_id` | one added line after the shell-metacharacter check: `if _DB_RUNNER_RE.search(cmd): return None` |
| Store files | `.aidd/evidence/contract-reuse-v1.json` (index `{"version": "contract-reuse-v1", "entries": [{"key", "sha256", "sha1", "cmd", "expected", "exit", "ok", "spec", "ts"}]}`) and `.aidd/evidence/contract-reuse-v1/<sha256>.txt` |
| Result fields | `cross_spec`, `source_spec`, `source_sha256` (plus the existing `reused`) |
| Output text | stdout prefix `CROSS-REUSED row`; note `note: contract store not written (<ExceptionType>)` |
| Existing entry point (signature unchanged) | `cmd_verify(spec_arg, full=False, bail=False, wave=None, result_sink=None, wave_cache=None, task_ids=None)` |
| Test class | `CrossSpecContractReuse(unittest.TestCase)`: `test_second_invocation_other_spec_reuses`, `test_any_identity_change_executes`, `test_damaged_store_executes`, `test_failure_is_never_stored`, `test_db_runner_has_no_environment_id`, `test_full_and_round_off_disable`, `test_non_contract_rows_unchanged`, `test_store_write_failure_is_a_note` |
| SKILL.md tokens | literal `CROSS-REUSED` and the runner list `db_verify`, `psql`, `pg_prove`, `docker`, `supabase`, `--tap` |
| Untouched | `round_on`, `_round_lookup`, `_round_store`, `_reusable_input_rows`, `wave_cache` semantics, `aidd_rules.py` |

### Amendment 04 — task-state resolution in `aidd progress` / `aidd pending` (T-26..T-29)

| Item | Contract |
|---|---|
| File (production) | `skill/scripts/aidd_progress.py` (T-27); byte mirror `adapters/dot-aidd/scripts/aidd_progress.py` (T-28); docs `skill/SKILL.md` after the `aidd progress` description (T-29) |
| File (tests, new) | `tests/test_progress_resolution.py` (T-26) |
| Constants | `DELETE_RE = re.compile(r'([\w.\-/]+)\s*\(delete[^)]*\)', re.I)`, `ALIAS_FILE = '.aidd/graphs/path-aliases.toon'` |
| `_delete_paths(raw_cell, short) -> list[str]` | expanded paths marked `(delete)` in the raw Target cell (before backticks are stripped) |
| `_renumbered(root, p) -> Path \| None` | only for `migrations/` paths whose base name matches `^(\d+)_(.+)$`; exactly one candidate (via `_index(root)`) with the same `(.+)` and a different prefix, else None |
| `_alias_target(root, p) -> Path \| None` | file with the aliased base name in the same directory, when it exists and is larger than `STUB_BYTES`; any exception -> None |
| `_load_aliases(root) -> dict[str, str]` | reads `ALIAS_FILE` as UTF-8; keeps lines starting with two spaces split on `,` with at least 2 fields as `{old: new}`; cached per root like `_INDEX` |
| `parse_tasks(text)` | signature unchanged; adds key `delete` (list of str) per task |
| `task_state(task, root)` | signature unchanged; may also return `'renamed'` (counts as present in `Impl%`) |
| `_resolve` | signature and return type unchanged |
| Alias graph format | `version: 1`, `generated: <iso>`, `aliases[N]{old,new,scope,reason}:`, then N rows indented two spaces |
| Test class | `TaskStateResolution(unittest.TestCase)`: `test_delete_target_gone_is_present`, `test_delete_target_still_there_is_missing`, `test_renumbered_migration_is_renamed`, `test_ambiguous_renumber_is_missing`, `test_alias_file_resolves_rename`, `test_bad_alias_is_missing_without_error`, `test_prose_task_id_is_not_a_task`, `test_project_without_cases_is_unchanged` |
| SKILL.md tokens | target marker `(delete)`, state `renamed`, graph file `.aidd/graphs/path-aliases.toon` (section `aliases[N]{old,new,scope,reason}:`), key `delete` in `parse_tasks` |
| Untouched | `aidd_pending.py`, `aidd_status.py`, the `progress.json` schema except the added `renamed` state |

### Requirement -> file map (amendments 03/04)

| FR | File / function | Test file | Task |
|---|---|---|---|
| FR-220, FR-221, FR-223 | `aidd_status.py` `_contract_store_paths`, `_contract_store_key`, `_contract_store_get`, `_contract_store_put`, `cmd_verify` | `tests/test_contract_store.py` | T-22, T-23, T-24 |
| FR-222 | `aidd_status.py` `_DB_RUNNER_RE`, `_contract_environment_id`; `skill/SKILL.md` | `tests/test_contract_store.py`, `tests/test_dot_aidd_mirror.py` | T-22, T-23, T-25 |
| FR-230, FR-235 | `aidd_progress.py` `parse_tasks`, `_delete_paths`, `DELETE_RE` | `tests/test_progress_resolution.py` | T-26, T-27, T-28 |
| FR-231, FR-232, FR-233, FR-234 | `aidd_progress.py` `task_state`, `_renumbered`, `_alias_target`, `_load_aliases`, `ALIAS_FILE`; `skill/SKILL.md` | `tests/test_progress_resolution.py`, `tests/test_aidd_progress.py` | T-26, T-27, T-28, T-29 |

Waves: amendment 03 and 04 run after wave 7 as waves 8 (T-22, T-26), 9 (T-23, T-25, T-27) and 10 (T-24, T-28, T-29); the two `skill/SKILL.md` edits (T-25, T-29) are in different waves, so no file has two owners in one wave.

## Amendment 05 (2026-11-03) — naming contract (T-30..T-34, T-43, T-44)

Names are exact and frozen (copied from `amendment-05-coverage-derive.draft.md`); owners may add private helpers, never rename these. Python stdlib only; mirrors are byte copies made by `cp`.

| Item | Contract |
|---|---|
| File (production, new) | `skill/scripts/aidd_coverage.py` (T-31); byte mirror `adapters/dot-aidd/scripts/aidd_coverage.py` (T-33) |
| File (production, changed) | `skill/scripts/aidd_status.py` and `skill/scripts/aidd_unit_audit.py` (T-44, same owner as T-23 for `aidd_status.py`); byte mirrors `adapters/dot-aidd/scripts/aidd_status.py`, `adapters/dot-aidd/scripts/aidd_unit_audit.py` (T-33); `aidd/cli.py` (T-32); `skill/SKILL.md` paragraph `**Incremental verification and reusable checks.**` (T-34, same owner as T-25) |
| File (tests) | new `tests/test_aidd_coverage.py` (T-30), new `tests/test_verify_changed_policy.py` (T-43); `tests/test_dot_aidd_mirror.py` list entry `"aidd_coverage.py"` in `VERBATIM_SCRIPTS` (T-33, same owner as T-40) |
| `aidd_coverage` constants | `REVIEW_MARK = '[Proposed — unconfirmed]'`, `PROPOSAL_MARK = '<!-- coverage_derive proposal: not part of any spec; review and copy by hand -->'`, `METADATA = ('spec.md', 'tasks.md', 'plan.md', 'contracts.md', 'mockup-audit.md')`, `DB_RE`, `SUITE_RE`, `RANGE_RE`, `T_RANGE_RE`, `MAX_RANGE = 400` |
| `aidd_coverage` functions | `codes_in(text) -> dict[str, str]`, `tasks_in(text, known=None) -> set[str]`, `raw_task_codes(tasks_text) -> dict[str, set[str]]`, `derive(spec_dir) -> dict`, `simulate_changed(result, changed) -> dict`, `render_text(result) -> str`, `render_proposal(result) -> str`, `safe_target(spec_dir, target) -> str \| None`, `main(argv=None) -> int`; private `_resolve_target(root, p) -> str \| None`, `_exists(root, pattern) -> bool`, `_matcher(globs)` |
| `derive` result | keys `spec, root, rows, uncovered_tasks, missing_targets, summary`; row keys `n, cmd, kind, tasks, covers, inputs, database, reuse, needs_review, notes, covers_before, inputs_before`; kinds `cites-tasks`, `via-fr-ac-api`, `whole-suite`, `unresolved` |
| `simulate_changed` result | keys `status, reason, selected_tasks, always_rows, rows_run, rows_skipped, warnings` |
| `aidd_status` new | `_changed_selection(root, spec, base=None) -> tuple[list[str], list[str], list[str]]`, `_changed_selection_fingerprint(tasks_text, spec_text, task_ids, always_rows) -> str`, `_known_task_ids(tasks_text) -> set[str]`, `_covers_task_refs(covers, known) -> set[str]` |
| `aidd_status` changed (signature) | `cmd_verify(spec_arg, full=False, bail=False, wave=None, result_sink=None, wave_cache=None, task_ids=None, always_rows=None)`; `_changed_task_selection(root, spec, base=None)` unchanged, returns `_changed_selection(...)[0]` |
| Output texts | `warning: verification row <n> declares no Inputs or no task Covers; it always runs`; `warning: task <T> is covered by no verification row; whole-suite rows run`; `always-run row <n>`; `Refused: always_rows requires --changed; nothing was executed.`; event `task_verify_run` field `always_rows` |
| `aidd_unit_audit` new | `resolve_base(root, base) -> str` (`git rev-parse --verify --end-of-options <base>^{commit}`, timeout 30 s; `ValueError('base is not a uniquely resolvable commit')`); used by `git_changed_paths(root, base=None)` and `administrative_only_task_paths(root, changed_paths, rules, base=None)` |
| CLI | tuple `("coverage", "aidd_coverage.py", [], "Propose task Covers and Inputs for a spec's Verification rows (dry-run; never writes the spec) (aidd_coverage.py)")` in the forwarded-script loop of `aidd/cli.py` |
| Test classes | `AiddCoverage` (16 methods) and `CoverageWiring` (`test_cli_registers_coverage`, `test_skill_documents_coverage`) in `tests/test_aidd_coverage.py`; `VerifyChangedPolicy` (7 methods) and `BaseRevision` (2 methods) in `tests/test_verify_changed_policy.py`; exact method names in tasks.md T-30 and T-43 |
| Untouched | `--tasks` and `--wave` selection, contract store, `_round_*`, `aidd_progress.py` (only called), `tests/test_verify_git_contract.py` |

### Requirement -> file map (amendment 05)

| FR | File / function | Test file | Task |
|---|---|---|---|
| FR-240..FR-249 | `aidd_coverage.py` (all functions above); `aidd/cli.py`; `skill/SKILL.md` | `tests/test_aidd_coverage.py` | T-30, T-31, T-32, T-33, T-34 |
| FR-259, FR-260 | `aidd_status.py` `_changed_selection`, `_changed_selection_fingerprint`, `_known_task_ids`, `_covers_task_refs`, `_changed_task_selection`, `cmd_verify`, `--changed` CLI branch | `tests/test_verify_changed_policy.py`, `tests/test_verify_git_contract.py` | T-43, T-44, T-33 |
| FR-261 | `aidd_unit_audit.py` `resolve_base`, `git_changed_paths`, `administrative_only_task_paths` | `tests/test_verify_changed_policy.py`, `tests/test_aidd_unit_audit_incremental.py` | T-43, T-44, T-33 |

Waves: amendment 05 shares waves 11-13 with amendment 06 — 11 (T-30, T-43), 12 (T-31, T-44), 13 (T-32, T-33, T-34); no file has two owners in one wave. Amendment 05 has no dependency on spec 004.

## Amendment 06 (2026-11-03) — naming contract (T-35..T-41)

Names are exact and frozen (copied from `amendment-06-alias-graph.draft.md`, re-based on `specs/004-aidd-graph-first/amendment-unified-explorer.draft.md`). UI rule: T-38 builds a NEW view faithful to the approved SCREEN-901 mockup (`prototypes/alias-graph-explorer/alias-graph-explorer.html`); it does not reuse legacy presentation.

**Cross-spec dependency (note, not a task dependency):** T-35..T-41 run after wave 10 of the 004 amendment (`specs/004-aidd-graph-first/amendment-unified-explorer.draft.md`), whose tasks T-74..T-76, T-83 and T-84 provide the unified explorer, `unified_graph.TOON_READERS`, the `--graph/--kind/--layer/--root` flags, the registry-generated layer ids (`metric-<name>`, `layer-cb-<name>`, `--layer-<name>`) and the adopted controls. Spec 004 carries those tasks; if they are not built, T-35's explorer tests stay red and T-38 must not start.

| Item | Contract |
|---|---|
| File (production, new) | `skill/scripts/alias_graph.py` (T-36); byte mirror `adapters/dot-aidd/scripts/alias_graph.py` (T-40) |
| File (production, changed) | `skill/scripts/aidd_graphs.py` (T-37), `skill/scripts/graph_explorer.py` + `skill/scripts/unified_graph.py` (T-38), `skill/scripts/aidd_progress.py` (T-39, same owner as T-27); byte mirrors of all five under `adapters/dot-aidd/scripts/` (T-40); `skill/SKILL.md` (T-41, same owner as T-25) |
| File (tests) | new `tests/test_alias_graph.py` (T-35); `tests/test_dot_aidd_mirror.py` list entry `"alias_graph.py"` in `VERBATIM_SCRIPTS` (T-40, same owner as T-33) |
| `alias_graph` | `SECTION_RE = re.compile(r'^aliases\[(\d+)\]\{old,new,scope,reason\}:\s*$')`; `parse_aliases(text) -> list[dict]` (keys `old`, `new`, `scope`, `reason`), `load_aliases(path) -> list[dict]`, `to_graph(rows) -> dict`, `show_aliases(root, query, limit=25) -> str`, `is_alias_toon(text) -> bool` |
| Graph shape | node `{"id": "old:<base>"\|"new:<base>", "label", "type": "alias_old"\|"alias_new", "scope", "reason"}`; edge `{"source", "target", "type": "RENAMED_TO"}` |
| Registry row (`aidd_graphs.py`) | `{"name": "aliases", "kind": "aliases", "output": ".aidd/graphs/path-aliases.toon", "refresh": "", "watch": [".aidd/graphs/path-aliases.toon"]}` only when the file exists and the charter declares no `aliases` graph; `show` branch for `e["kind"] == "aliases"` via `_module("alias_graph")`; message `alias_graph module not found` |
| Messages (`show_aliases`) | `old -> new [scope] reason`; `No alias matching '<query>'.`; `Graph 'aliases' is missing; the project must generate .aidd/graphs/path-aliases.toon` |
| `unified_graph.py` | `_read_aliases_toon(text)` (via `_sibling("alias_graph")`; `ValueError` when missing) and `TOON_READERS["aliases"] = _read_aliases_toon` |
| `graph_explorer.py` (alias view) | `ALIAS_LEGEND = ("old name", "new name", "renamed in progress")`; JS `renderAliasView()`; CSS `--alias-old`, `--alias-new`, `--alias-prog` (dark `#f85149`, `#3fb950`, `#d29922` in `:root`; light `#d9383a`, `#1a7f37`, `#bf8700` in `:root.light`); ids `legend-aliases`, `insp-scope`, `insp-reason`, `aliases-empty-banner`; text `Edge type: RENAMED_TO`; empty text `No aliases: the project has not generated .aidd/graphs/path-aliases.toon`. Registry-generated, not created here: `metric-aliases`, `layer-cb-aliases`, `--layer-aliases` |
| `aidd_progress.py` | task node key `state` (`renamed`, `deleted`) only when resolved that way; `_load_aliases(root)` same `{old: new}` result, built from `alias_graph.load_aliases` |
| Test class | `AliasGraph(unittest.TestCase)`: `test_parse_and_load_rows`, `test_bad_file_gives_empty`, `test_to_graph_nodes_edges`, `test_show_prints_neighbours`, `test_registry_has_aliases_only_when_file_exists`, `test_explorer_accepts_toon`, `test_explorer_html_is_self_contained`, `test_unified_explorer_has_alias_layer`, `test_progress_graph_task_state` |
| SKILL.md tokens | graph `aliases`, kind `aliases`, file `.aidd/graphs/path-aliases.toon`, commands `aidd graphs show aliases <name>`, `aidd graphs explorer aliases`, `aidd graphs explorer`, node types `alias_old`, `alias_new`, edge `RENAMED_TO` |
| Untouched | the `explorer` subcommand branch of `aidd_graphs.py`, the explorer JSON path, every control and the layer machinery of the 004 amendment, `task_state` results, the printed output of `aidd progress` |

### Requirement -> file map (amendment 06)

| FR | File / function | Test file | Task |
|---|---|---|---|
| FR-250, FR-251 | `aidd_graphs.py` registry builder, `show` | `tests/test_alias_graph.py` | T-35, T-37, T-40 |
| FR-252, FR-254 | `alias_graph.py` | `tests/test_alias_graph.py` | T-35, T-36, T-40 |
| FR-253, FR-255 | `unified_graph.py` `_read_aliases_toon`, `TOON_READERS`; `graph_explorer.py` alias view (SCREEN-901) | `tests/test_alias_graph.py`, `tests/test_unified_*.py`, `tests/test_explorer_controls*.py` | T-35, T-38, T-40, T-41 |
| FR-256, FR-257 | `aidd_progress.py` graph writer, `_load_aliases` | `tests/test_alias_graph.py`, `tests/test_aidd_progress.py`, `tests/test_progress_resolution.py` | T-35, T-39, T-40 |

Waves: amendment 06 runs in waves 11 (T-35), 12 (T-36), 13 (T-37, T-38, T-39) and 14 (T-40, T-41), shared with amendment 05; the `skill/SKILL.md` edits T-34 (wave 13) and T-41 (wave 14) and the `tests/test_dot_aidd_mirror.py` edits T-33 (wave 13) and T-40 (wave 14) are in different waves.
