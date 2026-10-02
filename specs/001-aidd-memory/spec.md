# 001 — AIDD Memory

Replaces the need for an external memory plugin (claude-mem). Curated, code-anchored, git-versioned
memory in AIDD-TOON. **No daemon, no LLM observer, no vectors, stdlib only, hooks in milliseconds.**
This file is the single source of truth for every implementing agent. Stay inside your task's files.

## Minimum Requirements Checklist

| Question | Answer |
|---|---|
| Module / area | `skill/scripts/`, `skill/hooks/`, `aidd/cli.py`, docs |
| New or modification | New feature (+ one modification: `find_spec.py` index) |
| External dependencies | None. Python stdlib only (`sqlite3` only inside the importer) |
| Requester | Project owner |
| Cross-module dependencies | `find_spec.py` (index), `install_hooks.py`, `_common.py` hooks helpers |
| Business objective | Persist the WHY (decisions, bugs, constraints) across sessions, anchored to codes/files, without a fragile daemon |
| In scope | Core lib+CLI, search, progressive disclosure, file/session context hooks, claude-mem importer, compaction, index optimization, docs, tests |
| Explicitly out of scope | Web UI, vector search, cloud sync, an LLM observer on every tool call, any dependency on claude-mem at runtime |

## Storage

Root = nearest ancestor (from cwd) containing `.aidd/`, `specs/` or `.git`; env `AIDD_MEMORY_DIR` overrides
the memory dir itself. Memory dir = `<root>/.aidd/memory/`, committed to git. Files:

- `<scope>.toon` — scope = a spec id (`001-aidd-memory`) or `project`. One file per scope.
- `archive/<YYYY>-Q<q>.toon` — compacted entries (searched only with `include_archive`).

File format (AIDD-TOON, same dialect family as `specs/index.toon`; writer ALWAYS emits `[*]` so two git
branches appending rows never conflict on a counter; reader tolerates `[*]` or `[N]` and does NOT enforce N):

```
version: 1
memory: project
entries[*]{id,date,type,title,codes,files,why,supersedes,source}:
  m-3fa91c02,2026-10-01,decision,Flows use TOON not JSON,US-001|CTL-004,skill/scripts/flowmap.py,"User asked for TOON; matches specs/index.toon",,agent
```

- Rows are indented 2 spaces, CSV-quoted (csv module), ONE line per entry (newlines in text -> ` / `).
- `codes`, `files` are `|`-joined. Files are POSIX, project-relative.
- `type` ∈ `decision bugfix discovery constraint risk rejected open-question state` (closed set; reject others).
- `title` ≤ 120 chars, `why` ≤ 400 chars (truncate with `…`), `source` ∈ `agent user import hook`.
- `id` = `m-` + first 8 hex of `sha1(f"{scope}|{date}|{title}")`; duplicate id => skip (idempotent import/add).
- `supersedes` = id of an older entry this one replaces (that entry is then "superseded": hidden from default
  search/inject, still shown by `show`, moved to archive by `compact`).
- Row order = append order. Never rewrite existing rows except `compact`.

## Core API — `skill/scripts/aidd_memory.py` (library + CLI)

```python
TYPES = ('decision','bugfix','discovery','constraint','risk','rejected','open-question','state')
FIELDS = ('id','date','type','title','codes','files','why','supersedes','source')
def find_root(start=None) -> Path
def memory_dir(root) -> Path
def make_id(scope, date, title) -> str
def load_entries(root, include_archive=False) -> list[dict]   # FIELDS + 'scope'; codes/files are lists
def append_entries(root, scope, entries) -> list[str]         # returns ids actually written (dedupes)
def add_entry(root, *, type, title, why='', codes=(), files=(), scope='project', supersedes='', source='agent', date=None) -> str
def search(root, query='', *, type=None, code=None, file=None, scope=None, limit=10, include_archive=False) -> list[dict]
def show(root, ids) -> list[dict]
def timeline(root, id, window=3) -> list[dict]                # same-scope neighbours by date
def entries_for_file(root, path, limit=3) -> list[dict]
def compact(root, before=None, apply=False) -> dict           # dry-run unless apply; {'moved':n,'superseded':n,'files':[...]}
def inject_text(root, max_chars=1500) -> str                  # '' when there is nothing
def file_context_text(root, path, limit=3, max_chars=600) -> str
def stats(root) -> dict
def main(argv=None) -> int
```

Search = BM25 (stdlib) over: title (x3), codes (x4; an exact code match dominates), files tokens (x2), why (x1).
Tokenizer: lowercase, accent-fold (NFKD), `\w+`, len ≥ 2, ES+EN stopwords, light stemming (plural/verb endings).
Superseded entries excluded by default. Tie-break: newer first. Pure stdlib, no cache file required.

CLI (`python aidd_memory.py <cmd>` and `aidd mem <cmd>`; global option `--root`):

| Command | Behaviour |
|---|---|
| `add --type T --title S [--why S] [--codes A,B] [--files a,b] [--scope X] [--supersedes ID] [--source S]` | prints the new id |
| `search <words...> [--type] [--code] [--file] [--scope] [--limit N] [--archive] [--json]` | **progressive disclosure**: one line per hit `id  date  type  [codes]  title` (~25 tokens each), never `why` |
| `show <id...> [--json]` | full row(s) incl. why/files/supersedes, also superseded/archived |
| `timeline <id> [--window N]` | neighbours |
| `file <path> [--limit N]` | entries mentioning that file |
| `inject [--max-chars N] [--file PATH]` | the text the hooks inject (see below) |
| `compact [--before YYYY-MM-DD] [--apply]` | dry-run by default; moves superseded (+ entries older than `--before`) to `archive/<YYYY>-Q<q>.toon` |
| `stats` | counts by type/scope, bytes |
| `import-claude-mem <db> --project SUBSTR [...]` | implemented in `aidd_memory_import.py` (see below) |

Exit codes: 0 ok, 1 usage/validation error, 2 nothing found for `search`/`show`/`file`.

`inject` (session start): header line `AIDD memory — N entries.` then up to 5 most recent non-superseded
`decision|constraint|risk` entries as `m-id type title`, then footer
`Search: aidd mem search <q> · Detail: aidd mem show <id>`. Hard-capped at `max_chars` (cut whole lines).
`inject --file P`: header `AIDD memory for <P>:` + up to 3 hits as `m-id type title`.

## Importer — `skill/scripts/aidd_memory_import.py`

`import_claude_mem(db_path, root, *, projects, types=DEFAULT_TYPES, include_summaries=True, since=None, scope='project', dry_run=False) -> dict`.
Reads the claude-mem SQLite file **read-only** (`sqlite3.connect("file:...?mode=ro", uri=True)`); never writes to it,
never imports claude-mem code, never starts its worker. Tables used: `observations(id,project,type,title,subtitle,facts,narrative,concepts,files_read,files_modified,created_at,content_hash)`
and `session_summaries(id,project,request,investigated,learned,completed,next_steps,files_read,files_edited,created_at)`.
`facts`/`concepts`/`files_*` are JSON-array text OR plain text — parse tolerantly.

Type mapping (default import set): `decision`→decision; `bugfix|bug-fix|fix|fix-applied|remediation`→bugfix;
`security_alert|security_note|critical|critical-success`→risk. Opt-in via `--include`: `feature|refactor|change|discovery|…`→discovery.
Session summaries → one `discovery` entry each (title=request, why=learned or completed). `codes` = regex
`SCREEN-\d+|CTL-\d+|COMP-\d+|API-\d+|US-\d+` over title+facts+narrative. `why` = narrative (fallback facts), ≤400 chars.
`source=import`. Filter by `project LIKE %SUBSTR%` (repeatable `--project`). Idempotent via `make_id`.
Returns counts per mapped type + skipped. `--dry-run` writes nothing.

## Hooks (`skill/hooks/`) — Claude Code only, registered by `install_hooks.py` (idempotent)

Rules for BOTH: stdlib only, **always exit 0**, never raise, no subprocess, silent (no output) when no `.aidd/memory/`
exists, total runtime ≪ 100 ms, import `aidd_memory` from `../scripts` via `sys.path`.

- `memory_context.py` — `SessionStart` (startup|resume|clear|compact): prints `inject_text(root)` to stdout.
- `memory_file_context.py` — `PreToolUse` matcher `Read|Edit|Write`: reads `tool_input.file_path`, emits ONCE per
  (session, file) (marker under `tempfile.gettempdir()/aidd-hooks/` like `_common.py`) JSON
  `{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"<file_context_text>"}}`; nothing if no hits.

## Index optimization — `skill/scripts/find_spec.py`

`specs/index.toon` `words` today is a bag of every word (≈35 KB for 11 specs, polluted by stopwords such as "como", "cada").
Replace with the top 25 terms per spec ranked by TF-IDF across all specs (accent-folded, ES+EN stopwords incl. the existing
STOPWORDS, len ≥ 4, no pure numbers). Bump index `version` to 3 (older index => automatic rebuild). Search ranking tests must
still pass. After a hit, `find_spec.py` also prints up to 3 `Memory:` lines (`m-id type title`) for the matched
codes when `aidd_memory` is importable and a memory dir exists (best-effort, never fails the search).

## Pipeline integration (docs)

Capture points (agent runs `aidd mem add ...`): end of Step 2 (each resolved alignment decision / rejected option),
Step 5 per PR (non-obvious why), Step 6 (audit findings, bug root cause), any discovered constraint. Read points: Step -1
(after `find_spec.py`), start of any task (`aidd mem search <codes>`), automatically via the two hooks. `STATE.md` stays the
"where am I" pointer; memory is the "why".

## Definition of Done (every task)

Code + unit tests (stdlib `unittest`, run with `python -m unittest discover -s tests`) + no new dependency + Windows-safe paths
(`pathlib`, UTF-8 everywhere, `sys.stdout.reconfigure(encoding='utf-8')`). Do NOT use any claude-mem tool or plugin.

## Amendments after the independent audit (Step 6, Rev 1) — binding

1. **Cache allowed.** `aidd_memory` MAY keep a derived cache under `<memory dir>/.cache/` (gitignored via a `.gitignore` the writer creates), keyed by file `mtime_ns`+`size`; it must be optional, auto-invalidated, safe when missing/corrupt/read-only, and never the source of truth. Targets at 2,000 entries: `search` <= 200 ms total CLI wall, hooks <= ~90 ms wall (interpreter start included); at 20,000 entries `search` <= 1 s. Archive stays excluded by default (keeps the active set small).
2. **Stemming** must be consistent for plural/verb forms incl. words ending in `e` (`table/tables`, `use/used/using`, `file/files`, `rule/rules` all match each other) and keep Spanish working.
3. **Scope names**: `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$` (no leading dot, no `..`); invalid => exit 1 with a message, never a traceback.
4. `add --supersedes ID` must reference an existing id (else exit 1). `inject --max-chars 0` means 0 chars (not default). Malformed-row warnings are emitted once per process per (file,line).
5. `compact --apply` must not silently drop non-row lines: preserve `#` comment lines; if a file contains anything else unparseable (e.g. git conflict markers), refuse to rewrite THAT file (message + exit 1) and leave it untouched.
6. `inject` digest prefers entries with `source != import`; imported entries only fill remaining slots. Injected text is sanitised (control chars stripped, each line <= 160 chars) — memory is committed content, treat as untrusted.
7. **Importer**: `files` keep only plausible repo paths (`^[\w@.+/\\:~-]+$` with an extension, no spaces/parentheses/brackets); absolute paths outside the destination root are dropped; relative paths normalised to POSIX. A **scrub step** replaces `(password|passwd|pwd|secret|token|apikey|api_key|bearer|connectionstring)\s*[:=]\s*\S+`, 32+ hex runs and private/internal IPv4 addresses with `[redacted]` in title and why. A DB without the expected tables/columns => `ValueError("not a claude-mem database: ...")` (CLI prints it, exit 1), never a traceback.
8. **find_spec**: wire the `Memory:` lines into `main()` (after Graph context) and prove it with an end-to-end subprocess test. Add a **full-text fallback**: when the top-25 index finds nothing, scan the spec files' text (accent-folded) for the query words before concluding "no match". Query words shorter than the index minimum are matched by that fallback only.
9. CLI: `aidd mem --root X <cmd>` and `aidd mem --help` must work (forward everything after `mem` verbatim).
10. Docs must cover: `AIDD_MEMORY_DIR`, global `--root`, `add --date`, importer `--since/--scope/--no-summaries/--include`, the cache, the index v3 TF-IDF change + full-text fallback, and the prompt-injection caveat.
