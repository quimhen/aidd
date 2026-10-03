# 002 — AIDD Hard Rules (enforced by hooks)

Turns the pipeline rules that today live only in prose into rules a hook enforces. Motivation: a real AIDD run
(another session) (a) quoted human-effort hours as if they were agent time, (b) skipped Steps 0/1/1.5 without asking and
left screen codes with no mockup bound to any spec, (c) answered its own Align assumptions, (d) wrote spec+contracts+
plan+tasks alone in one pass, (e) never ran the graph-coherence check, (f) never waited for task approval, (g) never
produced `qa-audit.md` or any closing auditor. Every one of those was permitted by the system.
This file is the single source of truth for every implementing agent. Stay inside your task's files.

## Minimum Requirements Checklist

| Question | Answer |
|---|---|
| Module / area | `skill/hooks/`, `skill/scripts/`, `skill/templates/`, `aidd/cli.py`, docs |
| New or modification | New rules engine + new hooks + refactor of the 3 existing PreToolUse gates + template changes |
| External dependencies | None (stdlib only) |
| Business objective | A session cannot skip, reorder or self-certify AIDD steps without a hook stopping it |
| Explicitly out of scope | Preventing writes made through `Bash` (heredoc/sed) — a known, documented limitation shared with the existing hooks; judging whether a subagent *did a good job* |

## Design principles (binding)

1. **Evidence, not trust.** Hooks (never the agent) write an append-only evidence log; gates read it. The agent cannot write that log (rule R9).
2. **Fail-closed on missing evidence, fail-open on hook crashes.** A rule whose required evidence is absent BLOCKS. An internal exception in a hook never wedges a session: it exits 0 and records a `hook_error` event (visible in `aidd status`).
3. **Every block message says exactly what to do next** (which artifact, which command, which question to ask the user).
4. **Owner-only escape hatch:** env `AIDD_RULES=warn` (messages to stderr, never block) or `off`; set in `settings.json` `env` by the human. Default = enforce. The agent has no tool to change a hook process environment.
5. **One spawn.** The three existing PreToolUse `Write|Edit` gates (`require_aidd`, `require_independent_audit`, `require_graph_coherence_audit`) are folded into ONE new entry hook `rule_gate.py` that imports them (each keeps a standalone `main()` so its own tests/CLI still work). Fewer processes per tool call = fewer silent skips when the shell/hook launcher is flaky.
6. **Each hook ≪ 100 ms** beyond interpreter start; no subprocess; stdlib only; Windows-safe (`pathlib`, UTF-8).

## Evidence log — `skill/scripts/aidd_evidence.py`

Project root = nearest ancestor of `cwd` containing `specs/` or `.aidd/` (else `cwd`). Files (created on demand, never committed):

- `<root>/.aidd/evidence/.gitignore` containing `*`
- `<root>/.aidd/evidence/events.toon` — AIDD-TOON, append-only:
  ```
  version: 1
  events[*]{ts,session,kind,detail}:
    1790911234.512,s-abc,subagent,"{""type"":""general-purpose"",""desc"":""Mapper"",""head"":""You are the Mapper...""}"
  ```
  `detail` = one-line JSON (csv-quoted). `ts` = `time.time()` float.
- `<root>/.aidd/active_spec` — two lines: spec id, `since` ts. Written by the recorder, never by the agent.

Kinds and `detail` keys: `session_start{}` · `prompt{text}` (user prompt, whitespace-normalised, ≤4000 chars) · `subagent{type,desc,head}` (head = first 400 chars of the Agent/Task prompt) ·
`question{text}` (all AskUserQuestion question strings joined) · `find_spec{rebuilt:bool}` · `code_edit{path,spec}` · `spec_edit{path,spec}` · `hook_error{hook,error}`.

API:
```python
def find_root(start=None) -> Path
def append(root, session, kind, **detail) -> None          # best-effort, never raises; rotates >5 MB keeping last 2000 rows
def events(root, session=None, kind=None, since=0.0) -> list[dict]   # {'ts':float,'session':str,'kind':str,'detail':dict}
def last_event(root, kind, session=None, since=0.0) -> dict | None
def set_active_spec(root, spec_id) -> None
def get_active_spec(root) -> str | None
def clear_active_spec(root) -> None
def normalise(text) -> str                                   # lowercase, accent-fold, collapse whitespace/punctuation — used to verify quotes
def quote_in_prompts(root, quote, min_words=3) -> bool       # normalised substring of any recorded `prompt`
```

### Recorders (extend existing hooks — NO new spawns, except one tiny new hook)

- `prompt_trigger.py` (UserPromptSubmit): additionally `append(prompt)` — never alters its current output.
- `mark_agent_dispatch.py` (PostToolUse Task|Agent): additionally `append(subagent{type,desc,head})` from `tool_input` (`subagent_type`, `description`, `prompt`).
- `mark_code_edit.py` (PostToolUse Write|Edit): additionally `append(code_edit)` for code files and `append(spec_edit)` + `set_active_spec(id)` when the path is `specs/<id>/{spec,plan,tasks,mockup-audit,contracts,data-model}.md`.
- `mark_graph_rebuild.py` (PostToolUse Bash): additionally `append(find_spec{rebuilt})` whenever the Bash command ran `find_spec.py` (rebuilt = output said `Graph index: rebuilt`).
- NEW `mark_user_question.py` (PostToolUse, matcher `AskUserQuestion`): `append(question{text})`.
- `session_start.py` (SessionStart): additionally `append(session_start)`.

## Rules library — `skill/scripts/aidd_rules.py` (pure functions + CLI core)

```python
RULE_IDS = ('R1','R2','R3','R4','R5','R6','R7','R9')
def check_content(kind, text) -> list[Violation]       # kind in spec|tasks|plan|qa ; structural validity of ONE artifact (R1,R2,R3 structure,R4 structure)
def check_spec_dir(spec_dir, root=None, session=None) -> list[Violation]   # all static rules + evidence-based rules for a whole spec
def approval_hash(tasks_text) -> str                  # sha1[:12] of text with the `Approved:` line removed, newlines normalised
def approval_valid(tasks_text) -> bool
def required_domains(spec_dir) -> set[str]            # subset of {'ui','backend','database','performance'} (performance always)
def domain_covered(root, session, domain, since_ts) -> bool
# Violation = dict(rule, message, fix)  # fix = the exact next action for the agent
```

### R1 — Estimates are agent time, not human hours (tasks.md content)
`tasks.md` must contain a `## Waves` table `| Wave | Tasks | Agent time (min) | Human ref (h) |` with ≥1 row; each task block must have `Agent min:` and `Human ref hours:` (the old single `Estimated hours:` alone is a violation); a line `Total agent time (critical path): N min` where N = sum over waves of the wave's `Agent time` AND each wave's `Agent time` = max of its tasks' `Agent min`. Waves run sequentially; tasks inside a wave in parallel.
### R2 — Pipeline route is declared; skipping a step needs the user (spec.md content)
`spec.md` must contain `## Pipeline route` table `| Step | Status | Reason | Confirmation |` with a row for each of `-1, 0, 1, 1.5, 2, 3, 4`. `Status` ∈ `run | waived`. `waived` requires a non-empty Reason and Confirmation of the form `user — "<quote ≥ 3 words>"`; the quote is verified against recorded `prompt` events by the gate (R5). Steps 0/1/1.5 may be waived only for a change with no visual surface.
### R3 — Alignment provenance (spec.md content; completeness enforced by R5)
The Minimum Requirements Checklist table has a `Source` column; allowed values: `user — "<quote ≥ 3 words>"`, `repo — <path[:line]>`, or `[Proposed — unconfirmed]`. An answer the agent chose itself MUST be `[Proposed — unconfirmed]`. (Drafting with Proposed rows is allowed; planning is not — see R5.)
### R4 — Visual debt (spec.md content + gate)
If Step 0/1/1.5 is `waived` and any `SCREEN-\d+` code appears in the spec's own files (spec.md/plan.md/contracts.md) or in any other `specs/*/` file without a `mockup-audit.md` row, `spec.md` must contain `## Visual debt` table `| Codes | Blocks spec | Status | Mockup source |` listing them; `Status` ∈ `open | resolved` (`resolved` needs a Mockup source). Gate: while any debt row naming spec `X` is `open`, writes under `specs/X/` and code edits while `X` is the active spec are BLOCKED.
### R5 — Chain order (gate on writing plan.md / tasks.md)
- writing `specs/X/plan.md` requires: ≥1 `find_spec` event in this session; ≥1 `subagent` event in this session with `ts` > mtime(`spec.md`) (the independent Mapper/Alignment agent); `spec.md` passes R2 and R3 structure; **no `[Proposed` row left**; every `user — "quote"` (R2 and R3) verified by `quote_in_prompts`; R4 satisfied.
- writing `specs/X/tasks.md` requires: `plan.md` exists; ≥1 `subagent` event in this session with `ts` > mtime(`plan.md`); the existing graph-coherence semantics **fail-closed**: a `find_spec` event exists this session, and if the last `find_spec` event has `rebuilt=true` a `subagent` event follows it.
### R6 — Approval of tasks is the user's and is tamper-evident
`tasks.md` carries a line `Approved: <YYYY-MM-DD> hash:<approval_hash>`. Writing/editing that line requires a `question` event in the current session with `ts` > mtime(tasks.md) and its text mentioning `task`/`tarea`/`aprob`/`approve`. Any later change to the rest of tasks.md changes the hash and invalidates the approval. **Code-file writes (existing `CODE_EXTENSIONS`) are BLOCKED while the active spec has a `tasks.md` whose approval is missing/invalid.** No active spec ⇒ no R6 gate (fast lane and unrelated edits are unaffected).
### R7 — Closing audit covers every domain touched
`required_domains`: always `performance`; `ui` if tasks cite `SCREEN-|CTL-|COMP-`; `backend` if `API-`; `database` if `data-model.md` exists or tasks mention `stored procedure|migration|\.sql|schema`. Writing `qa-audit.md` additionally requires, per required domain, a `subagent` event with `ts` > last `code_edit` of the active spec whose `head`+`desc` matches the domain regex (`ui: ui|mockup|screen|pantalla|visual` · `backend: backend|api|contract|endpoint` · `database: database|base de datos|sql|schema|migraci` · `performance: performance|rendimiento|best practice`). The existing "subagent after last code edit" gate stays.
### R8 — Stop gate (Stop hook `stop_gate.py`)
On Stop: if the active spec has a valid approval, ≥1 `code_edit` after the approval, and (`qa-audit.md` missing OR any required domain uncovered) ⇒ exit 2 with the checklist of what is missing. If the payload has `stop_hook_active` true ⇒ allow (no loop). Never blocks when there is no active spec.
### R9 — Protected paths
Agent `Write|Edit` to `.aidd/evidence/**` or `.aidd/active_spec` is BLOCKED.

## Gate hook — `skill/hooks/rule_gate.py` (PreToolUse, matcher `Write|Edit`)

Single entry. Order: (1) R9; (2) the three legacy gates via their `evaluate(event) -> (blocked: bool, message: str)` (refactored from their `main()`, behaviour identical, graph gate now fail-closed per R5); (3) content rules on the artifact being written: compute the would-be content (Write ⇒ `content`; Edit ⇒ apply `old_string→new_string` (`replace_all`) to the current file) and run `check_content`; a violation blocks only if it is NEW (not already present in the current file) or the call is a whole-file Write of tasks.md/spec.md; (4) R5 chain, R6 approval, R7 audit, R4 debt gates by target path. All exceptions ⇒ exit 0 + `hook_error` event. `AIDD_RULES=warn|off` honoured.

## CLI / status — `skill/scripts/aidd_status.py` + `aidd/cli.py`

- `aidd status [spec_dir]` — mechanical ledger from the evidence log and the spec files, e.g.
  ```
  001-x  Route: -1 run · 0/1/1.5 WAIVED(confirmed) · 2 run …   Align: 0 proposed · Mapper ✔ · Graph ✔
  Tasks: approved ✔ (hash ok) · Waves: 3 · critical path 95 min   Build: 14 code edits · Auditors: ui ✔ backend ✔ database ✘ performance ✔
  Hook errors: 0
  ```
  exit 0 always; `--json`.
- `aidd rules check <spec_dir>` — runs `check_spec_dir`, prints `PASS|FAIL Rn message → fix`, exit 1 on any violation.
- `aidd rules approve <spec_dir>` — writes the `Approved:` line ONLY if a `question` event newer than tasks.md exists (any session, last 60 min); else exit 1 explaining to ask the user.
- `aidd rules close <spec_id>` — `clear_active_spec` after `check_spec_dir` has no R7 gap.
- `check_spec.py` also calls `aidd_rules.check_content/check_spec_dir` (static rules only) and reports violations as gaps.

## Templates (binding shape)

- `templates/spec.md`: Checklist gets the `Source` column; new `## Pipeline route` and `## Visual debt` sections (examples as comments).
- `templates/tasks.md`: per-task `Agent min:` + `Human ref hours:` replace `Estimated hours`; new `## Waves` table, `Total agent time (critical path)` line and an `Approved:` line placeholder (`Approved: PENDING`).
- `templates/STATE.md`: a read-only "Rules ledger" hint pointing to `aidd status`.

## Installer

`install_hooks.py`: default hooks become: session_start, mark_invoked, **rule_gate** (replaces require_aidd + require_independent_audit + require_graph_coherence_audit; the installer REMOVES those three old aidd entries if present), prompt_trigger, mark_code_edit, mark_agent_dispatch, mark_graph_rebuild, memory_context, **mark_user_question** (PostToolUse AskUserQuestion), **stop_gate** (Stop). Idempotent; never touches non-aidd hooks. `memory_file_context` stays opt-in.

## Definition of Done (every task)

Code + stdlib `unittest` tests (`python -m unittest discover -s tests`) + no new dependency + Windows-safe + hooks always exit 0 on internal error (never traceback to the model) + every block message names the next action. Adversarial tests for each rule: try to violate it and show the gate blocks; try the legitimate path and show it passes. Do NOT use any claude-mem tool/plugin.

## Amendments after adversarial audit Rev 1 — binding (B = blocker, M = major, m = minor in the audit)

Evidence API additions (`aidd_evidence.py`; every later task codes against these exact names):
```python
def sanitize_line(text) -> str                 # replace U+2028/2029/0085/000B/000C/001C-001E and all other control chars with a space (B2)
def canon_path(p, root=None) -> str            # comparable absolute path: strip trailing dots/spaces and ::$STREAM per segment, resolve .., os.path.realpath (junctions/symlinks), Windows 8.3->long via GetLongPathNameW (best-effort), normcase, forward slashes (B3)
def rel_to_root(path, root) -> str | None      # canon posix path relative to root, or None if outside
def project_roots(path) -> list[Path]          # EVERY ancestor dir containing specs/ or .aidd/ (nearest first) (M8 nested)
def open_specs(root) -> list[str]              # spec ids that have a `spec_edit` for tasks.md and no LATER `spec_closed` event (any session) (B1)
def affirmative_answer(root, session, topic_re, since_ts=0.0) -> dict | None   # newest `answer` event (same session or 'unknown-session') after since_ts whose question text matches topic_re AND whose chosen answer matches an affirmative label (^(approve|approved|aprobar|aprobado|si|sí|yes|ok|confirm|proceder|abandon|descartar) …) and no negative (no|rechaz|reject|cancel|not) (M6)
def count(root, kind, **match) -> int
```
New event kinds: `answer{text,pairs}` (PostToolUse AskUserQuestion: parse `tool_response` — the harness text looks like `User has answered your questions: "<q>"="<a>", ...`; learn the real shape by grepping ONE existing transcript under `~/.claude/projects/*/*.jsonl` for `answered your questions` (read-only, print nothing else); be tolerant: extract `"q"="a"` pairs by regex, fall back to the raw text ≤2000 chars) · `approved{spec,hash}` (written by the recorder when tasks.md is written/edited with a hash-valid `Approved:` line) · `spec_closed{spec,reason}` (reason completed|abandoned) · `stop_block{spec,key}` · `find_spec{rebuilt,ok,source}` where `ok` = the command's output contained `aidd spec search` / `No specs/ folder` / `no spec folders` / `Graph index`, `source` = bash|hook. Env `AIDD_EVIDENCE_DIR` overrides the evidence dir (tests must use it so no test writes `.aidd/evidence` inside the repo).

Behaviour changes:
- **B1 active spec ≠ agent-switchable.** R6, R7, R8 and the code gate iterate over `open_specs(root)` for EVERY root in `project_roots(path)`: a code write is blocked while ANY open spec has a missing/invalid approval. `.aidd/active_spec` becomes an informational pointer only. A spec stops being open only via a `spec_closed` event (`aidd rules close` after the completed audit, or `aidd rules abandon <id>` — both require `affirmative_answer` for topic `close|cierr|abandon|descart|cancel` and `abandon` records reason=abandoned; no qa-audit needed for abandon) (M-dl).
- **B2** `_row` uses `sanitize_line`; readers split on `\n` only.
- **B3** every path decision (rule_gate, `_common`, legacy gates, R9, R4) goes through `canon_path`; file-name comparisons are case-insensitive on the canonical basename; R9 protects the WHOLE `.aidd/` directory for agent writes EXCEPT `.aidd/memory/**`; `specs/…/PLAN.md`, `plan.md.`, `plan.md::$DATA`, `sub/../plan.md`, 8.3 and junction forms are the same file as `plan.md`.
- **Matchers**: rule_gate and mark_code_edit register for `Write|Edit|MultiEdit|NotebookEdit` (read `notebook_path` too) and **rule_gate also for `Bash`** with a cheap pre-check (no imports unless the command text mentions `.aidd`, `events.toon`, `active_spec`, `evidence`, or `aidd rules`): a Bash command that writes/deletes/moves/redirects into protected paths is BLOCKED (R9 for Bash); everything else in Bash is allowed. Documented residual: Bash code edits remain ungated.
- **M1** R5 blocks planning while ANY checklist row has a blank Answer (unanswered). **M2** `repo — path[:line]` must exist under the root, and an Answer containing `Proposed` is always unconfirmed whatever the Source. **M3** a `user — "quote"` needs ≥5 words found in a `prompt` event, OR ≥2 words found in an `answer` event (answers are short), and in both cases with `ts` > the spec's first `spec_edit` event ts (or any ts when the spec has none yet). **M4** table parsing continues across blank lines until the next heading. **m-e** duplicate Pipeline-route rows are a violation.
- **M5** `Blocks spec` must be an existing spec id (or its numeric prefix); `resolved` needs a Mockup source that is an existing file under the root or an `http(s)://`/`figma:` reference AND the codes must have a `mockup-audit.md` row somewhere; R4 evaluates the WOULD-BE content for plan.md/contracts.md writes, and covers `contracts.md`. **m-a** SCREEN regex is case-insensitive (lower- or mixed-case spellings of a SCREEN code) and also scans codes inside HTML comments (comments are only ignored for table parsing).
- **M6** the `Approved:` line (rule_gate) and `aidd rules approve` require `affirmative_answer(topic task|tarea|aprob|approve)` newer than the last content change of tasks.md; `aidd rules approve` ALSO requires R1-valid tasks.md and a same-session answer.
- **M7** `approval_hash` excludes lines/cells named `Status`, `Tracker ref`, `PR/Spec ref` (so sync_issues/link_pr don't void approval); trailing-whitespace edits stay hash-neutral BUT the stop gate takes "approved at" from the `approved{spec,hash}` event ts, never from mtime.
- **M8** new `R6_GATED_EXTENSIONS` ⊇ CODE_EXTENSIONS plus: .ps1 .sh .bash .bat .cmd .json .yml .yaml .html .htm .css .scss .sass .less .xml .toml .ini .tf .lua .pl .r .ex .exs .gradle .csproj .sln .aspx .razor .cshtml .vb .groovy .zig .vue .svelte and basenames `Dockerfile`, `Makefile`, `Jenkinsfile` (after `canon_path`). The non-code exemption for `specs/` and `design-system/` applies only when the canonical path RELATIVE TO THE PROJECT ROOT starts with those segments. The legacy `require_aidd` extension list stays unchanged (do not widen friction on non-AIDD repos).
- **M9** R7: word-boundary domain regexes, and each domain needs a DISTINCT subagent event (greedy one-to-one assignment); a subagent matching several domains counts for one.
- **M10** `stop_gate`: obligations derive from open specs across ALL sessions; blocks are counted via `stop_block` events (spec,key=approval hash); `stop_hook_active` no longer a free pass: block while count < 3, then allow and record `stop_block_exhausted`.
- **M-fi** `mark_graph_rebuild` records `find_spec` only when the Bash command RUNS find_spec (first token chain: `python|python3|py [-u] <path>find_spec.py` possibly after `cd … &&`), not on `echo`/`grep` mentions, with `ok` computed from the output; `prompt_trigger` (which runs find_spec itself) records a `find_spec{source:hook}` event too.
- **M-dos** every regex in rule_gate/aidd_rules is linear (no `\s*` spanning newlines; process per line); files > 2 MB are not regex-scanned (treated as violation "file too large" for tasks.md/spec.md writes).
- **m-b** `AIDD_RULES`: `off|0|false|no` ⇒ off; `warn` ⇒ warn; anything else ⇒ enforce (trimmed, case-insensitive). **m-c** every hook (recorders and legacy gates standalone) tolerates non-dict payloads / non-string fields: exit 0, record `hook_error` when a root is known. **m-f** tests set `AIDD_EVIDENCE_DIR`. **Installer**: matchers per above, plus a `timeout` of 15 on rule_gate/stop_gate and 10 on recorders.

## Amendments after adversarial audit Rev 2 — binding (D-ids refer to the Rev 2 audit)

**Storage split (D1b, D5).** Evidence kinds are split by scope so a session started in a parent folder, or in a project without AIDD, works and creates nothing in the project:
- SESSION kinds (`prompt, subagent, question, answer, find_spec, session_start, hook_error`) live in a per-session log under `<tempdir>/aidd-hooks/evidence/<sanitised-session-id>.toon` (shared `unknown-session` file when no id), never inside a project directory.
- PROJECT kinds (`spec_edit, code_edit, approved, spec_closed, stop_block, stop_block_exhausted`) live in `<known project root>/.aidd/evidence/events.toon`, written ONLY when `known_root` finds a root (never create a root; no root ⇒ record nothing). `spec_edit`/`code_edit` are written to EVERY root in `project_roots(target path)`.
- `events()/last_event()/count()` keep their signature and transparently read the right log(s) by kind (kind=None merges both). Tests/owner overrides: `AIDD_EVIDENCE_DIR` is honoured ONLY when `AIDD_TESTING=1` is also set (the CLI and hooks must ignore both otherwise — D4); with it set, session logs go to `<dir>/sessions/`, project log to `<dir>/events.toon`. **Every test that sets `AIDD_EVIDENCE_DIR` must also set `AIDD_TESTING=1`.**
- R9 additionally protects the session-log directory (`<tempdir>/aidd-hooks/`) from agent Write/Edit/MultiEdit/NotebookEdit and from the Bash guard.

**Attribution (D1).** `code_edit` carries NO spec attribution: every R6/R7/R8 computation treats a code edit as applying to every open spec (use only `ts`; compare against that spec's approval ts). The `.aidd/active_spec` pointer is purely informational and no gate may read it.

**Answers (D2, D7).** `mark_user_question` receives both `tool_input.questions[]` (question texts + option labels) and `tool_response`. It records `question{text, options:[[labels…]…]}` AND `answer{pairs}` where pairs are built ONLY by anchoring on the KNOWN question strings in order (string form: for each known question q expect `"q"="` then the answer up to the next known `"q'"="` or the closing `". You can now`/`".`/end; dict form: only `answers` keys that equal a known question); if the count doesn't match, record `answer{text, pairs:[]}` (unusable as evidence). `affirmative_answer(root, session, topic_re, since_ts=0.0, label_re=None)` uses `pairs` ONLY (never raw text); the chosen answer must additionally match `label_re` when given and be one of the options recorded for that question. Callers: approval ⇒ topic `approv|aprob` and label `^(approve|aprobar|aprobado)\b`; close ⇒ topic `close|cierr|finaliz` label `^(yes,? close|cerrar|si,? cerrar|sí,? cerrar)`; abandon ⇒ topic `abandon|descart` label `^(abandon|abandonar|descartar)`. A question must OFFER such an option; the gate/CLI tells the agent to include it. The user's quote evidence from answers likewise uses `pairs` only.

**Approval integrity (D3).** The gate allows a well-formed `Approved:` line edit only if `approval_hash(current tasks.md) == approval_hash(would-be tasks.md)` (the approval edit changes nothing else) AND the written hash equals that hash AND the answer rule above holds. R6 additionally requires a hook-recorded `approved{spec,hash}` event for the current hash before code edits are allowed (a Bash-forged line without the event stays blocked; `aidd rules approve` appends it).

**Open specs (D9).** A spec is open from its first `plan.md` OR `tasks.md` `spec_edit` (not spec.md alone) until `spec_closed`. An open spec with NO tasks.md (or a deleted one) blocks code edits with "Step 4 missing: write tasks.md, then get approval".

**R6 coverage (D11).** Invert to a deny-list: every file is code EXCEPT extensions `md markdown txt rst csv tsv log lock png jpg jpeg gif svg ico webp bmp pdf docx xlsx pptx zip`, and except these locations (by canonical path relative to the outermost project root): `specs/`, `design-system/`, `.aidd/memory/`, `.claude/skills/`, `.git/`, `node_modules/`, `__pycache__/`, `.venv/`. (`require_aidd`'s legacy list is untouched.)

**Matchers (D8).** rule_gate, mark_graph_rebuild and mark_code_edit also register for the `PowerShell` tool (command in `tool_input.command`, same parsing as Bash); rule_gate's Bash/PowerShell guard additionally blocks: any command that imports or `-m`-runs `aidd_evidence|aidd_rules|aidd_status`; assigns `AIDD_EVIDENCE_DIR=|AIDD_TESTING=|AIDD_SESSION_ID=|AIDD_RULES=`; writes/removes/moves under `specs/` (deleting tasks.md); mentions `tasks.md` together with `Approved`; and the extra obfuscation forms found by the audit (`xargs rm`, `curl -o`, `tar -C`, `unzip -d`, `Expand-Archive`, `iwr|Invoke-WebRequest -OutFile`, `Tee-Object`, `[IO.File]::`, `[IO.Directory]::`, `Export-Csv`, `git apply`, `eval`, glob characters `*?[` inside a `.aidd` path). The CLI (`aidd status|rules`) ignores `AIDD_SESSION_ID`/`AIDD_EVIDENCE_DIR` unless `AIDD_TESTING=1`.

**Alignment (D6).** R3/R5: the Minimum Requirements Checklist must contain every question of the shipped template (match by normalised question text; extra rows allowed) each answered; `repo — path:LINE` must name an existing file and a line number ≤ the file's line count, or `repo — path "quote ≥3 words found in that file"`; a bare directory/`.`/`README.md` without line is rejected; answer `-`/empty rejected; the same-named heading repeated or a Proposed marker in ANY column is detected.
**Hash-neutral cells (D10).** Status / Tracker ref / PR/Spec ref cells (and `Status:` lines) must be ≤ 60 chars and ≤ 8 words, else R1 violation.
**find_spec evidence (D12).** Recognise `& python …`, `python -X utf8 …`, `time|timeout python …`, `powershell -c "python …"` and the `aidd` CLI wrapper if it exists; `ok` only when the output contains the authentic header `aidd spec search` or one of the known no-spec messages (not merely `Graph index`).
**Robustness (D14).** `mark_invoked.py` and every remaining hook tolerate non-dict payloads (exit 0, no traceback); `aidd status` never prints an internal error for a pathological tasks.md.
**Docs (D15)** must be corrected to match, and the Limitations block must state plainly: Bash and PowerShell can still edit code and, through the CLI/libraries, try to forge evidence (the Bash guard is lexical, not a sandbox); the user's click cannot be cryptographically proven; hooks fail open; R8 relaxes after 3 blocks per approval hash; nothing stops a determined agent — the rules stop accidental and self-justified skipping.
