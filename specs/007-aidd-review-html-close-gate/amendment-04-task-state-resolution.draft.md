# Draft — amendment 04 to spec 007: `aidd pending` / `aidd progress` stop over-reporting missing work

**DRAFT: not approved, not executable, no `Approved:` line.** Amendment intake: `AMENDMENT` of
`specs/007-aidd-review-html-close-gate` (verification and evidence accuracy). Sibling of
`amendment-03-reuse-first-increment` (cross-spec reuse). It does not edit `amendment-02-*`.
Owner direction (verbatim, 2026-11-03): "este tipo de mejoras con script que propones son las mejoras que debemos implementar en aidd".

## Minimum Requirements Checklist

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | `skill/scripts/aidd_progress.py` (shared by `aidd progress` and `aidd pending`) | repo — `skill/scripts/aidd_pending.py:23` | — |
| New development or modification? | Modification of `parse_tasks` and `task_state` | repo — `skill/scripts/aidd_progress.py:69`, `:172` | — |
| External service, API, integration? | None | owner brief 2026-11-03 | — |
| Who is requesting it? | Owner (AIDD + b1SycLink) | user — "este tipo de mejoras con script que propones son las mejoras que debemos implementar en aidd" | — |
| Dependencies? | None new; stdlib only | repo — `skill/scripts/aidd_progress.py:20` | — |
| Business objective | A task whose target was deleted on purpose, renamed by a rename spec, or whose migration was renumbered is not reported as missing work | owner brief 2026-11-03 | — |
| Expected visual fidelity | No mockup; CLI only | — | — |

## Executive summary

- **Objective:** make `task_state` understand three situations that today read as `missing`: a `(delete)` target
  that is gone, a target renamed through an optional alias file, and a migration whose numeric prefix changed.
- **Measured (b1SycLink, 2026-11-03, `tools/spec_registry.py`):** 224 tasks were flagged pending; after resolving
  these cases F28 went from 11 false pending to 0 (24 deleted files and 9 renamed tables recognised), and F36/F37
  recognised 9 renumbered migrations. The remaining 65 "pending" were task IDs matched inside prose tables
  (`TASK_ID_RE` accepts any `Letters-digits` cell 0 of a table with a `Status` header).
- **Not in scope:** deciding that work is done (still `aidd verify` + audit), Status-cell edits, any b1SycLink file.
- **Risk:** an alias file maps the wrong names; mitigated because an alias only turns `missing` into `present` when
  the new file exists and has content, and it is reported as `renamed`, never hidden.

## Functional requirements

| Code | Requirement | Source |
|---|---|---|
| FR-230 | `parse_tasks` keeps, per task, `delete`: the list of expanded paths written as `<path> (delete)` in the Target cell. Rows without that marker have `delete == []`. | measured on b1SycLink F28 T-35..T-41 |
| FR-231 | `task_state` treats a `delete` path as satisfied when `_resolve` finds nothing, and as `missing` while the file still exists. A task whose paths are all `delete` and all gone is `present`. | owner brief 2026-11-03 |
| FR-232 | `_resolve` falls back, for a path with a `migrations/` directory and a `<digits>_<name>.<ext>` file name, to the single project file named `<digits>_<name>.<ext>` with a different numeric prefix. Zero or several candidates keep the path unresolved. | measured: F36 1120-1126 -> 3277-3283 |
| FR-233 | Optional graph file `<root>/.aidd/graphs/path-aliases.toon`, same structure as the other `.toon` graphs: lines `version: 1` and `generated: <iso>`, then `aliases[N]{old,new,scope,reason}:` followed by N rows indented two spaces (base names; fields separated by commas; a row with fewer than 2 fields is ignored). When `_resolve` fails and the base name has an alias whose file exists in the same directory, that file is the target. | user — "estamos utilizando los grafos con formato toon, sigue la misma estructura"; measured: F30 `ordr_table.dart` -> `oped_table.dart` |
| FR-234 | `task_state` returns the new value `renamed` (counts as present in `Impl%`) when FR-232/FR-233 resolved the file, so reports can show how many targets moved; `aidd progress --detail` lists them. | owner brief 2026-11-03 |
| FR-235 | `TASK_ID_RE` rows are tasks only when the table header names a `Target file` or has `Task|ID|#` plus `Status`; a row whose first cell is not the first column of such a table is ignored. (Fixes prose IDs counted as tasks.) | measured: 65 prose IDs |

## Acceptance criteria

| Code | Scenario | Expected |
|---|---|---|
| AC-261 | Task `(delete)` target absent | `task_state == 'present'`; counted done |
| AC-262 | Task `(delete)` target still present | `task_state == 'missing'` |
| AC-263 | `migrations/0120_x.sql` cited, only `migrations/3277_x.sql` exists | `renamed` |
| AC-264 | Two files `3277_x.sql` and `3300_x.sql` exist | `missing` (ambiguous, never guessed) |
| AC-265 | `path-aliases.toon` has the row `  ordr_table.dart,oped_table.dart,mobile,F30` and the new file exists | `renamed` |
| AC-266 | Alias target absent, or the `.toon` file malformed/unreadable/binary | `missing`; no exception |
| AC-267 | A prose line `| T-42 | ... |` outside a task table | not returned by `parse_tasks` |
| AC-268 | Project with none of these cases | output identical to current behaviour |

## Verification

| # | Command | Expected | Covers |
|---|---|---|---|
| V-1 | `python -m unittest tests.test_progress_resolution -v` | exit 0 | T-26, T-27, AC-261..AC-268 |
| V-2 | `python -m unittest tests.test_aidd_progress -v` | exit 0 | T-27, AC-268 (no regression) |
| V-3 | `python -m unittest tests.test_dot_aidd_mirror -v` | exit 0 | T-28 |

Synthetic temporary directories only; no database, Docker or network.

## Out of scope

Deciding "done" without verification; editing any tasks.md Status; changing `aidd verify`; b1SycLink files;
changing installed skills; the evidence-table generator and cross-spec reuse (own amendments).

## Open questions

None. Q-1 (alias file location) was answered by the owner on 2026-11-03: use the `.toon` graph format with the same
structure (user — "estamos utilizando los grafos con formato toon, sigue la misma estructura"). A project generates
`.aidd/graphs/path-aliases.toon` from its own rename map; AIDD only reads it.

---

# Tasks — amendment 04

Every task prompt restates: scope in and out exactly as written; stop and report on any ambiguity; one
responsibility per function; snake_case with a leading underscore for module-private helpers; design for failure
(every file read in `try/except (OSError, UnicodeDecodeError, ValueError)`, fail closed = report `missing`); tool-first
(mirror sync by `cp`/script, never by hand); no databases, `db_verify.py` never run, no `aidd verify` by the builder.

Analysis parameters: `aidd size --files skill/scripts/aidd_progress.py tests/test_progress_resolution.py` → expected M.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-26 | FR-230..FR-235, AC-261..AC-268 | `tests/test_progress_resolution.py` | LOGIC | | | any production code; any other test file |
| T-27 | FR-230..FR-235 | `skill/scripts/aidd_progress.py` | LOGIC | | | `aidd_pending.py`, `aidd_status.py`, output format of `aidd progress` except the new `renamed` count |
| T-28 | FR-230..FR-235 (mirror) | `adapters/dot-aidd/scripts/aidd_progress.py` | LOGIC | | | any change that is not a byte copy of T-27's file |
| T-29 | FR-231, FR-233 docs | `skill/SKILL.md` | LOGIC | | | any other section; b1SycLink files |

## Per-task detail

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
- Wave: 1

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
- Wave: 2

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
- Wave: 3

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
- Wave: 3

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

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-26 | tests | 15 | 70 | 0.75 |
| 2 | T-27 | builder | 25 | 100 | 1.25 |
| 3 | T-28, T-29 | builder, docs | 5 | 50 | 0.25 |

Total agent time (critical path): 45 min
Total tokens (k): 220
