# Draft — amendment to spec 004: a tool-first nudge that fires on repeated manual work

**DRAFT: not approved, not executable, no `Approved:` line.** Amendment intake: `AMENDMENT` of
`specs/004-aidd-graph-first` (same family as FR-025..FR-027, the graph-first nudge, and FR-039, the `aidd tools` catalog).
Owner direction (verbatim, 2026-11-03): "tenemos una regla de siempre utilizar herramientas pero en claude no siempre se cumple".

## Problem (observed, not assumed)
Rule T1 (use a tool before doing a repetitive or checkable step by hand) and the catalog `aidd tools` exist, but nothing
makes an agent follow them. In the b1SycLink session of 2026-11-03: OpenCode and agy lanes produced their files with
generator scripts (`gen_f36_tests.py`, `gen_f38_tests.py`, dry-run then apply), while the Claude orchestrator made 14
separate Edit calls to set the same Status cell and ran several one-off searches that a script covers. The catalog already
finds project tools (`aidd tools registry` lists `tools/spec_registry.py`), so discoverability is not the gap: enforcement is.

## Minimum Requirements Checklist

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | Claude Code hooks (`skill/hooks/`) and `aidd status` | repo — `skill/hooks/read_hint.py` | — |
| New development or modification? | New hook `tool_first_hint.py` + a status line; the graph-first hook is the model | repo — `skill/hooks/read_hint.py` | — |
| External service, API, integration? | None | owner brief 2026-11-03 | — |
| Who is requesting it? | Owner | user — "tenemos una regla de siempre utilizar herramientas pero en claude no siempre se cumple" | — |
| Dependencies? | `aidd tools` catalog (FR-039); session evidence events (FR-027 pattern) | repo — `specs/004-aidd-graph-first/spec.md` | — |
| Business objective | Repeated manual edits become a script with dry-run/apply/check, saving time and tokens | user — "opencode y agy utiliza siempre scripts para optimizar tiempos y gestión" | — |
| Expected visual fidelity | No mockup; CLI/hook only | — | — |
| Threshold N | 4 | user — "N = 4 (Recommended)" (answer to Q-1, 2026-11-03) | — |
| Scope of counted tools | Edit, Write, MultiEdit, NotebookEdit, Bash, PowerShell; not Grep loops | user — "Ediciones y comandos de shell (Recommended)" (answer to Q-2, 2026-11-03) | — |

## Repo facts the tasks rely on (read 2026-11-03)

- `skill/hooks/read_hint.py` (295 lines) is the model: `SILENCE_S = 300` (line 22), `SECRET_RE` (line 29), `_scrub`
  (lines 122-123), `_silenced` (lines 126-133: an event whose `detail.source != 'hook'` within 300 s silences), events via
  `ev.append(root, sid, 'graph_miss', ...)` (line 226), output as `{"hookSpecificOutput": {"hookEventName": ...,
  "additionalContext": msg}}` (lines 233-234), `main()` wrapped in `try/except BaseException: pass` then `sys.exit(0)`
  (lines 290-295). Not mirrored in `adapters/dot-aidd/hooks/`.
- `skill/hooks/_common.py`: `read_event()` (lines 99-105) returns `{}` on a malformed payload; `session_of(event)`
  (lines 123-126).
- `skill/scripts/aidd_evidence.py`: `known_root(start)` (lines 134-143); `SESSION_KINDS` (lines 147-148, includes
  `graph_miss`); `_sessions_dir()` (lines 166-168: `AIDD_EVIDENCE_DIR/sessions` under `AIDD_TESTING=1`, else
  `<tempdir>/aidd-hooks/evidence`); `_safe_sid(session)` (line 171); `_session_path` (lines 178-179); `append(root,
  session, kind, **detail)` (line 710); `events(root, session, kind, since)` (line 754); `record_hook_error(start,
  session, hook, error)` (line 1284).
- `skill/scripts/aidd_status.py`: `_current_session(root)` (line 173); `_graph_first_line(root=None)` (lines 710-725)
  prints `graph-first: N misses / M searches this session`; `format_global(g)` (line 728) calls it at line 740.
- `skill/scripts/install_hooks.py`: `HOOK_DEFS` (lines 71-85, 13 entries), docstring hook list (lines 8-37),
  `DEFAULT_TIMEOUT = 10` (line 90). `tests/test_install_hooks.py` asserts 13 entries (lines 80, 87), 14 with the
  optional hook (line 138) and the exact name list (lines 141-146).
- `tests/test_evidence.py` lines 394-408 append one event of every kind and assert `len(ev.events(...)) == 19`.
- Mirrors: `adapters/dot-aidd/scripts/aidd_evidence.py` and `adapters/dot-aidd/scripts/aidd_status.py` are byte copies
  checked by `tests/test_dot_aidd_mirror.py` (lines 74, 76). `install_hooks.py` and `read_hint.py` have no mirror.
- `aidd tools` is dispatched by `aidd/cli.py` line 642-645 to `aidd_tools.py`.

## Functional requirements

| Code | Requirement | Source |
|---|---|---|
| FR-049 | A `PostToolUse` hook on `Edit`, `Write`, `MultiEdit`, `NotebookEdit`, `Bash` and `PowerShell` counts repetition per session and emits ONE advisory line when any trigger fires: (a) N or more `Edit`/`MultiEdit` calls whose normalized change is the same (digits and quoted identifiers replaced by placeholders) within 15 minutes; (b) N or more `Edit` calls to one file within 15 minutes; (c) N or more consecutive `Bash`/`PowerShell` commands with the same normalized text, excluding read-only `git status/log/diff`. It only advises, never blocks. | measured: 14 identical Status edits in one session |
| FR-050 | The advice says: run `aidd tools <keywords>`; if no tool fits, write a script with dry-run, apply and check, and save it under `tools/` so the catalog indexes it. Keywords come from the file extension and directory of the repeated change. | user — "opencode y agy utiliza siempre scripts para optimizar tiempos y gestión" |
| FR-051 | Only an `aidd tools` query run BY THE AGENT silences the advice, for 300 s, recorded as a `tool_query` event (same rule as FR-026). Running a script does not silence it. | FR-026 pattern |
| FR-052 | Evidence, not trust: each advisory is a session event `tool_miss{kind,target,count}` and `aidd status` prints `tool-first: N advisories / M edits this session`. | FR-027 pattern |
| FR-053 | Fail open: any error in the hook (state file unreadable, malformed payload) emits nothing and exits 0. State lives in the per-session evidence directory, never in the project tree. | `skill/hooks/_common.py` convention |
| FR-054 | Shape normalisation. The "same shape" of a change is computed by `_shape(text)` in this order: (1) every backtick-, double- or single-quoted literal on one line becomes `<Q>`; (2) every remaining token that contains `/` or `\` becomes `<P>`; (3) every run of digits becomes `<N>`; (4) runs of whitespace become one space and the result is stripped. An `Edit` shape is the file extension plus `_shape(old_string)` plus `_shape(new_string)`; the file name and directory are NOT part of it. A `MultiEdit` shape joins the shapes of its `edits` in order. A shell shape is `_shape(command)`. Examples from the owner's case (14 Edit calls that differ only in the file name and the replaced path): `old_string` `` \| T-91 \| FR-12 \| `eDoc/supabase/migrations/3411_pinv_base.sql` \| LOGIC \| \| \| `` in `specs/F36-eDoc-Purchasing/tasks.md` and `` \| T-94 \| FR-15 \| `eDoc/supabase/migrations/3414_imc_base.sql` \| LOGIC \| \| \| `` in `specs/F38-eDoc-Import-Costing/tasks.md` both normalise to `\| T-<N> \| FR-<N> \| <Q> \| LOGIC \| \| \|`, and their `new_string` (same row with `done` in the Status cell) both normalise to `\| T-<N> \| FR-<N> \| <Q> \| LOGIC \| \| done \|`, so the two calls have one shape. Shell: `python tools/gen_f36_tests.py --apply specs/F36` and `python tools/gen_f37_tests.py --apply specs/F37` both normalise to `python <P> --apply <P>`. | user — the 14 Status edits of 2026-11-03 (Problem section) |

## Acceptance criteria

| Code | Scenario | Expected |
|---|---|---|
| AC-041 | N identical-shape `Edit` calls on different files | exactly one advisory, on the Nth call |
| AC-042 | N edits to unrelated shapes | no advisory |
| AC-043 | `aidd tools <kw>` run, then repeated edits within 300 s | no advisory; after 300 s it fires again |
| AC-044 | Corrupt or missing state file | exit 0, no output, no exception |
| AC-045 | `aidd status` after two advisories | prints `tool-first: 2 advisories / M edits` |
| AC-046 | The owner's shape: 4 `Edit` calls on `specs/F36-eDoc-Purchasing/tasks.md`, `specs/F37-eDoc-Supplier-Invoice/tasks.md`, `specs/F38-eDoc-Import-Costing/tasks.md`, `specs/F39-eDoc-X/tasks.md`, each setting `done` in the Status cell of one row that differs only in the task id, the FR number and the backticked migration path | calls 1-3 print nothing; call 4 prints one advisory that contains `aidd tools md` and `4 edits with the same shape`; one `tool_miss` event with `kind == 'same_shape'` and `count == 4`; a 5th call of the same shape prints nothing |

## Verification

| # | Command | Expected | Covers |
|---|---|---|---|
| V-1 | `python -m unittest tests.test_tool_first_hint -v` | exit 0 | T-60, T-61, T-63, T-65, AC-041..AC-046 |
| V-2 | `python -m unittest tests.test_evidence tests.test_install_hooks tests.test_read_hint tests.test_aidd_status -v` | exit 0 | T-62, T-65 (no regression) |
| V-3 | `python -m unittest tests.test_dot_aidd_mirror -v` | exit 0 | T-66 |

Synthetic temporary directories only; no database, Docker or network.

## Out of scope

Blocking an agent for doing manual work; judging whether a script is good; Codex/OpenCode/agy hosts (they already use
scripts); changing the `aidd tools` catalog itself; counting `Grep`/`Glob`/`Read` loops (Q-2 answer).

## Open questions

None. Q-1 (threshold) answered by the owner on 2026-11-03: N = 4 (user — "N = 4 (Recommended)"). Q-2 (scope) answered
by the owner on 2026-11-03: edits and shell commands, that is `Edit`, `Write`, `MultiEdit`, `NotebookEdit`, `Bash`,
`PowerShell`, not `Grep` loops (user — "Ediciones y comandos de shell (Recommended)").

---

# Tasks — tool-first nudge

Every task prompt restates: scope in and out exactly as written; stop and report on any ambiguity; one
responsibility per function; snake_case with a leading underscore for module-private helpers; design for failure
(every file read in `try/except (OSError, UnicodeDecodeError, ValueError)`, the hook fails open = no output, exit 0);
tool-first (mirror sync by `cp`, bulk edits by script with dry-run/apply/check, never by hand); at most 3 work
databases and none is needed here: `db_verify.py` is never run, no `aidd verify` by the builder.

Analysis parameters: `aidd size --files skill/hooks/tool_first_hint.py skill/scripts/aidd_evidence.py skill/scripts/aidd_status.py skill/scripts/install_hooks.py skill/SKILL.md tests/test_tool_first_hint.py` → expected M.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-60 | FR-049..FR-054, AC-041..AC-046 | `tests/test_tool_first_hint.py` | LOGIC | | | any production code; any other test file |
| T-61 | FR-049, FR-050, FR-051, FR-053, FR-054 | `skill/hooks/tool_first_hint.py` | LOGIC | | | blocking behaviour; any other hook |
| T-62 | FR-049 (registration) | `skill/scripts/install_hooks.py` | LOGIC | | | any other host adapter |
| T-63 | FR-052 | `skill/scripts/aidd_status.py` | LOGIC | | | the verification and approval lines of `format_global`; `_graph_first_line` |
| T-64 | FR-050, FR-052 docs | `skill/SKILL.md` | LOGIC | | | any other section |
| T-65 | FR-051, FR-052, FR-053 (evidence kinds and state path) | `skill/scripts/aidd_evidence.py` | LOGIC | | | any other event kind; rotation and spill logic |
| T-66 | FR-052, FR-053 (mirror) | `adapters/dot-aidd/scripts/aidd_evidence.py`, `adapters/dot-aidd/scripts/aidd_status.py` | LOGIC | | | any change that is not a byte copy |

## Per-task detail

### T-60 — failing tests first
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: S

**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.0
- Tokens (est): 90k
- Agent role: tests
- Model tier: medium
- Wave: 1

**Detail**
- Goal: encode AC-041..AC-046 and the FR-054 normalisation as unit tests that fail on the current code.
- Cites: FR-049..FR-054, AC-041..AC-046.
- Depends on: none.
- Read first: `tests/test_read_hint.py` lines 1-80 (`ReadHintCase.setUp`, `run_hook`, `_env`, `add_find_spec`, `ctx`) and lines 211-227 (`test_ac020_status_line_end_to_end`); `skill/scripts/aidd_evidence.py` lines 147-179 and 710-770; `skill/scripts/aidd_status.py` lines 173-190 and 710-725.
- Files to change: `tests/test_tool_first_hint.py` (new).
- Naming contract: `HOOK = ROOT / "skill" / "hooks" / "tool_first_hint.py"`; class `ToolFirstHintCase(unittest.TestCase)` with helpers `run_hook(self, stdin)`, `_env(self)` (context manager, copy of `ReadHintCase._env`), `edit_ev(self, rel, old, new)` -> dict with `tool_name='Edit'`, `shell_ev(self, command, tool='Bash')` -> dict, `ctx(self, r)` -> str, `misses(self)` -> list of `tool_miss` details, `add_query(self, source, age=0.0)` (appends a `tool_query` event with `aidd_evidence.time.time` patched to `time.time() - age`), `load_hook(self)` -> module loaded with `importlib.util.spec_from_file_location("tool_first_hint", HOOK)`. Test methods: `test_shape_normalises_quotes_paths_digits`, `test_ac046_owner_case_four_status_edits`, `test_ac041_one_advisory_only`, `test_ac042_unrelated_shapes_no_advisory`, `test_same_file_four_edits_fires_same_file`, `test_window_older_than_900s_does_not_count`, `test_shell_four_consecutive_same_shape`, `test_shell_run_broken_by_other_command`, `test_read_only_git_never_counts`, `test_aidd_tools_command_records_tool_query`, `test_ac043_tools_query_silences_for_300s`, `test_hook_source_query_does_not_silence`, `test_ac044_corrupt_state_file`, `test_malformed_stdin`, `test_no_project_root_no_output`, `test_edits_counter_counts_every_edit_tool`, `test_ac045_status_line`, `test_new_kinds_are_session_kinds`. Production names exercised: `tool_first_hint._shape(text) -> str`; `aidd_evidence.tool_first_state_path(session) -> Path`; `aidd_evidence.read_tool_first_state(session) -> dict`; `aidd_status._tool_first_line(root=None) -> str`; event kinds `tool_miss`, `tool_query`. Hook payload keys used (Claude Code `PostToolUse` schema): `session_id`, `cwd`, `tool_name`, `tool_input`; `tool_input` keys `file_path`, `old_string`, `new_string`, `edits`, `content`, `notebook_path`, `new_source`, `command`.
- Behaviour:
  1. `setUp`: temp root with `specs/F36-eDoc-Purchasing`, `specs/F37-eDoc-Supplier-Invoice`, `specs/F38-eDoc-Import-Costing`, `specs/F39-eDoc-X` directories, each with a `tasks.md`; `self.evid = root/"evid"`; `self.sid = f"test-{uuid.uuid4().hex}"`; `self.env = dict(os.environ, AIDD_TESTING="1", AIDD_EVIDENCE_DIR=str(self.evid))`; `run_hook` runs `[sys.executable, str(HOOK)]` with `cwd=str(self.root)`, `timeout=15`.
  2. Row text used by AC-046: `ROW = "| T-{t} | FR-{f} | `eDoc/supabase/migrations/{m}.sql` | LOGIC | | {s} |"`; the four calls use `(t, f, m)` = `(91, 12, "3411_pinv_base")`, `(92, 13, "3412_pinv_ret")`, `(93, 14, "3413_imc_base")`, `(94, 15, "3414_imc_cost")`, `old` with `s=""` and `new` with `s="done"`, one file each in the order F36, F37, F38, F39.
  3. `test_shape_normalises_quotes_paths_digits`: `_shape(ROW.format(t=91, f=12, m="3411_pinv_base", s="done")) == "| T-<N> | FR-<N> | <Q> | LOGIC | | done |"`; `_shape("python tools/gen_f36_tests.py --apply specs/F36") == "python <P> --apply <P>"`; `_shape('a  "x"\n  \'y\' 7') == "a <Q> <Q> <N>"`.
  4. `test_ac046_owner_case_four_status_edits`: calls 1-3 → `stdout == ""`; call 4 → `ctx` contains `aidd tools md` and `4 edits with the same shape`; `misses()` has one item with `kind == "same_shape"` and `count == 4`; `test_ac041_one_advisory_only` adds a 5th call with `t=95` on `specs/F36-eDoc-Purchasing/tasks.md` → `stdout == ""` and still one `tool_miss`.
  5. `test_ac042_unrelated_shapes_no_advisory`: 4 Edit calls on the 4 different files with `old`/`new` `("alpha", "beta")`, `("x = 1", "x = 2; y")`, `("## A", "## B\nmore")`, `("foo()", "bar(baz)")` → all `stdout == ""`, `misses() == []`.
  6. `test_same_file_four_edits_fires_same_file`: the 4 calls of step 5 all on `specs/F36-eDoc-Purchasing/tasks.md` → call 4 advises, `misses()[0]["kind"] == "same_shape"` is false and `== "same_file"` is true, `ctx` contains `specs/F36-eDoc-Purchasing/tasks.md`.
  7. `test_window_older_than_900s_does_not_count`: run calls 1-3 of step 2, then rewrite the state file (path from `aidd_evidence.tool_first_state_path(self.sid)` inside `_env`) subtracting 901 from every timestamp in `shapes` and `files`, then call 4 → `stdout == ""`.
  8. `test_shell_four_consecutive_same_shape`: 4 Bash calls `python tools/gen_f3{n}_tests.py --apply specs/F3{n}` for n = 6..9 → 4th has `ctx` containing `4 shell commands in a row with the same shape` and `aidd tools python gen_f39_tests`; `misses()[0]["kind"] == "same_command"`. `test_shell_run_broken_by_other_command`: 3 such calls, then `python -m unittest -v`, then a 4th such call → all `stdout == ""`.
  9. `test_read_only_git_never_counts`: 5 Bash calls `git status` then 5 PowerShell calls `git log -n 3` → all `stdout == ""`, `misses() == []`.
  10. `test_aidd_tools_command_records_tool_query`: Bash `aidd tools migration` → `stdout == ""`; one `tool_query` event in the session with `detail["source"] == "agent"`.
  11. `test_ac043_tools_query_silences_for_300s`: `add_query("agent")`, then the 4 calls of step 2 → no output, `misses() == []`; new session id, `add_query("agent", age=301)`, the 4 calls → call 4 advises. `test_hook_source_query_does_not_silence`: `add_query("hook")`, the 4 calls → call 4 advises.
  12. `test_ac044_corrupt_state_file`: inside `_env`, write bytes `b"\xff{"` to `tool_first_state_path(self.sid)` (create parent dirs), run one Edit → `(returncode, stdout, stderr) == (0, "", "")`; the state file is now valid JSON with `edits == 1`. `test_malformed_stdin`: stdin `"{not json"` → `(0, "")`. `test_no_project_root_no_output`: a second temp dir with no `specs/` and no `.aidd/`, the 4 calls of step 2 with that `cwd` → all `stdout == ""` and no state file for the session.
  13. `test_edits_counter_counts_every_edit_tool`: one `Write` (`file_path`, `content`), one `NotebookEdit` (`notebook_path`, `new_source`), one `MultiEdit` (`file_path`, `edits=[{"old_string":"a","new_string":"b"}]`), one `Edit` → `aidd_evidence.read_tool_first_state(self.sid)["edits"] == 4`.
  14. `test_ac045_status_line`: the 4 calls of step 2 then the 4 shell calls of step 8 → with `_env()` and `unittest.mock.patch.object(aidd_status, "_current_session", return_value=self.sid)`: `aidd_status._tool_first_line(self.root) == "tool-first: 2 advisories / 4 edits this session"`; with a fresh session id → `"tool-first: 0 advisories / 0 edits this session"`.
  15. `test_new_kinds_are_session_kinds`: `{"tool_miss", "tool_query"} <= aidd_evidence.SESSION_KINDS`.
- Tests first: this task IS the tests; run `python -m unittest tests.test_tool_first_hint -v` and keep the red output (every test fails or errors on current code because the hook file and helpers do not exist).
- Verify: `python -m unittest tests.test_tool_first_hint -v` → red before T-61/T-63/T-65, exit 0 after.
- Do NOT: touch production code; use a database, Docker or the network; write outside the temp dirs; weaken an assertion later.
- Done when: the 18 tests exist with exactly these names and the red run is recorded by the verifier.
- Open questions: none.

### T-65 — evidence kinds and state path in `aidd_evidence.py`
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: S

**Estimate**
- Effort: Low
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 50k
- Agent role: builder
- Model tier: medium
- Wave: 2

**Detail**
- Goal: route `tool_miss` and `tool_query` to the per-session log and give the hook and `aidd status` one shared path for the per-session state file.
- Cites: FR-051, FR-052, FR-053.
- Depends on: T-60.
- Read first: `skill/scripts/aidd_evidence.py` lines 134-179; `tests/test_evidence.py` lines 390-410.
- Files to change: `skill/scripts/aidd_evidence.py`; `tests/test_evidence.py` (lines 398-408 only).
- Naming contract: `SESSION_KINDS` gains `'tool_miss'` and `'tool_query'` with the comment `# aidd:FR-051 aidd:FR-052 tool_query / tool_miss: the tool-first hook (per-session evidence)`; new `def tool_first_state_path(session) -> Path` returning `_sessions_dir() / (_safe_sid(session) + '.tool-first.json')`; new `def read_tool_first_state(session) -> dict` returning the parsed JSON object or `{}`.
- Behaviour:
  1. Tests first in `tests/test_evidence.py`: after line 398 add `ev.append(self.root, "s", "tool_miss", kind="same_shape", target="x", count=4)` and `ev.append(self.root, "s", "tool_query", source="agent", command="aidd tools x")`; change both `19` on lines 407-408 to `21`; run it red.
  2. Add the two kinds to the `SESSION_KINDS` frozenset literal on lines 147-148.
  3. Add `tool_first_state_path` and `read_tool_first_state` directly after `_session_path` (line 179). `read_tool_first_state`: `json.loads(path.read_text(encoding='utf-8'))`; return it only when it is a `dict`; on `(OSError, UnicodeDecodeError, ValueError)` return `{}`. Never raises.
- Tests first: step 1; `python -m unittest tests.test_evidence -v` red before step 2.
- Verify: `python -m unittest tests.test_evidence -v` → exit 0; `python -m unittest tests.test_tool_first_hint.ToolFirstHintCase.test_new_kinds_are_session_kinds -v` → exit 0.
- Do NOT: change `PROJECT_KINDS`, rotation, spill or lock code; write the state file from this module; touch `adapters/` (T-66 does the mirror).
- Done when: both verify commands pass.
- Open questions: none.

### T-61 — the hook `skill/hooks/tool_first_hint.py`
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: M

**Estimate**
- Effort: High
- Agent min: 40
- Human ref hours: 2.0
- Tokens (est): 140k
- Agent role: builder
- Model tier: high
- Wave: 3

**Detail**
- Goal: implement FR-049..FR-051, FR-053 and FR-054 so the hook tests of T-60 pass; the hook only advises and always exits 0.
- Cites: FR-049, FR-050, FR-051, FR-053, FR-054.
- Depends on: T-60, T-65.
- Read first: `skill/hooks/read_hint.py` lines 1-30, 122-151, 226-295; `skill/hooks/_common.py` lines 99-126; `skill/scripts/aidd_evidence.py` lines 134-179 (after T-65), 710-720, 1284-1290; the tests created by T-60 in the file named in T-60's Files to change.
- Files to change: `skill/hooks/tool_first_hint.py` (new).
- Naming contract: constants `N_REPEAT = 4`, `WINDOW_S = 900`, `SILENCE_S = 300`, `MAX_KEYS = 200`, `EDIT_TOOLS = frozenset({'Edit', 'Write', 'MultiEdit', 'NotebookEdit'})`, `SHAPE_TOOLS = frozenset({'Edit', 'MultiEdit'})`, `SHELL_TOOLS = frozenset({'Bash', 'PowerShell'})`, `READ_ONLY_GIT_RE = re.compile(r'^\s*git\s+(?:status|log|diff)\b', re.I)`, `TOOLS_QUERY_RE = re.compile(r'\baidd(?:\.exe)?\s+tools\b|aidd_tools\.py', re.I)`, `QUOTED_RE = re.compile(r'`[^`\n]*`|"[^"\n]*"|\'[^\'\n]*\'')`, `PATHLIKE_RE = re.compile(r'[^\s<>|]*[\\/][^\s<>|]*')`, `DIGITS_RE = re.compile(r'\d+')`, `SECRET_RE` (copy of read_hint.py line 29). Functions: `_shape(text) -> str`; `_edit_shape(tool, ti) -> str | None`; `_rel_key(path, root, cwd) -> str`; `_scrub(text) -> str` (copy of read_hint.py lines 122-123); `_fresh_state() -> dict`; `_load_state(path) -> tuple[dict, bool]`; `_save_state(path, state) -> None`; `_trim(stamps_by_key, now) -> dict`; `_update_counters(state, tool, ti, root, cwd, now) -> list[tuple[str, str, int, str]]` (kind, key, count, label); `_silenced(ev, sid) -> bool`; `_keywords(kind, label) -> str`; `_advice(kind, count, label, keywords) -> str`; `main() -> None`. Event kinds written: `tool_query{source:'agent', command}`, `tool_miss{kind, target, count}`. Trigger kinds: `same_shape`, `same_file`, `same_command`. State JSON: `{"v": 1, "edits": int, "shapes": {key: [ts...]}, "files": {key: [ts...]}, "shell": {"key": str, "run": int}, "advised": [key...]}`. Hook payload keys read (Claude Code `PostToolUse` schema): `session_id`, `cwd`, `tool_name`, `tool_input`; `tool_input` keys `file_path`, `old_string`, `new_string`, `edits`, `command`.
- Behaviour:
  1. `_shape(text)`: `str(text)[:4000]`; `QUOTED_RE` → `<Q>`; `PATHLIKE_RE` → `<P>`; `DIGITS_RE` → `<N>`; `re.sub(r'\s+', ' ', ...)`; `.strip()`. Order exactly as FR-054.
  2. `_edit_shape(tool, ti)`: only for `SHAPE_TOOLS`. `Edit`: needs `old_string` and `new_string` as str, else None. `MultiEdit`: `ti['edits']` list of dicts with str `old_string`/`new_string`, else None. Value = `hashlib.sha1((ext + '\x1f' + '\x1e'.join(_shape(o) + '\x1f' + _shape(n) for o, n in pairs)).encode('utf-8')).hexdigest()[:16]` where `ext = os.path.splitext(ti['file_path'])[1].lower()`.
  3. `_rel_key(path, root, cwd)`: absolute path (joined to `cwd` when relative); when under `root` → `os.path.relpath(...).replace('\\', '/')`, else `os.path.normcase(abs).replace('\\', '/')`.
  4. `_load_state(path)`: missing file → `(_fresh_state(), True)`; read+`json.loads` returning a dict with int `edits`, dict `shapes`, dict `files`, dict `shell`, list `advised` → `(state, True)`; any other content or `(OSError, UnicodeDecodeError, ValueError)` → `(_fresh_state(), False)`. `_save_state`: `path.parent.mkdir(parents=True, exist_ok=True)`, write `path.with_suffix('.tmp')`, then `os.replace`; swallow `OSError`.
  5. `_trim(stamps_by_key, now)`: drop timestamps older than `now - WINDOW_S`, drop empty keys, then keep only the `MAX_KEYS` keys with the newest last timestamp.
  6. `_update_counters`: `EDIT_TOOLS` → `edits += 1`. `SHAPE_TOOLS` with a shape → append `now` to `shapes['same_shape:' + shape]`; with a str `file_path` → append `now` to `files['same_file:' + _rel_key(...).lower()]`. `SHELL_TOOLS`: str `command`, non-empty after strip, not `READ_ONLY_GIT_RE` → key `'same_command:' + sha1(_shape(command))[:16]`; same key as `shell['key']` → `run += 1`, else `{'key': key, 'run': 1}`; an excluded command leaves `shell` unchanged. Then `_trim` both dicts. Return, in this order, every trigger with count ≥ `N_REPEAT` among: the current call's shape key (`same_shape`, label = the rel path), its file key (`same_file`, label = the rel path), the shell key (`same_command`, label = `_shape(command)[:120]`).
  7. `_silenced(ev, sid)`: True when `ev.events(None, session=sid, kind='tool_query')` has an event with `detail.source != 'hook'` and `now - ts <= SILENCE_S`; any exception → False.
  8. `_keywords(kind, label)`: edits → extension without dot plus the parent directory base name, lowercased, joined by one space (`specs/F39-eDoc-X/tasks.md` → `md f39-edoc-x`); `same_command` → the first token's base name without extension plus the first later token that does not start with `-` and is not `<P>`/`<Q>`/`<N>`, taken from the ORIGINAL command's same token, base name without extension (`python tools/gen_f39_tests.py --apply specs/F39` → `python gen_f39_tests`).
  9. `_advice(kind, count, label, keywords)` returns exactly: `same_shape` → `f"AIDD tool-first (T1): {count} edits with the same shape in the last 15 min."`; `same_file` → `f"AIDD tool-first (T1): {count} edits to {label} in the last 15 min."`; `same_command` → `f"AIDD tool-first (T1): {count} shell commands in a row with the same shape."`; each followed by `f" Run `aidd tools {keywords}`; if no tool fits, write a script with dry-run, apply and check and save it under tools/ so `aidd tools` indexes it. Advisory only, nothing was blocked."`.
  10. `main()`: `sys.stdout.reconfigure(encoding='utf-8')` when available; `event = read_event()`; not a dict, `tool_input` not a dict or `tool_name` not in `EDIT_TOOLS | SHELL_TOOLS` → return. `sid = session_of(event)`; `cwd` from the event else `os.getcwd()`; import `aidd_evidence as ev` from `<skill>/scripts`; `root = ev.known_root(cwd)`; None → return. Shell command matching `TOOLS_QUERY_RE` → `ev.append(None, sid, 'tool_query', source='agent', command=_scrub(command))`, return. `path = ev.tool_first_state_path(sid)`; `state, ok = _load_state(path)`; `fired = _update_counters(...)`; `_save_state(path, state)`; `not ok` → return. Keep triggers whose key is not in `state['advised']`; none → return. `_silenced(ev, sid)` → return (keys are NOT marked advised). Add every kept key to `advised`, `_save_state`; first trigger → `ev.append(None, sid, 'tool_miss', kind=kind, target=_scrub(label), count=count)`; write `json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": _advice(...)}}, ensure_ascii=False) + '\n'`.
  11. Module bottom: `if __name__ == '__main__':` `try: main()` `except BaseException:` try `ev.record_hook_error(None, sid-or-None, 'tool_first_hint', repr(exc))` inside its own `try/except Exception: pass`; then `sys.exit(0)`. Module docstring names FR-049..FR-054 and says "Only advises: never denies, never blocks, never raises, always exits 0."
- Tests first: T-60 must be red before this task; keep it unmodified.
- Verify: `python -m unittest tests.test_read_hint -v` → exit 0; `python -m unittest tests.test_tool_first_hint -v` → every test passes except the status-line test, which waits for T-63.
- Do NOT: print anything to stderr; deny or block a tool call; write state inside the project tree; read the edited file from disk; count `Grep`, `Glob` or `Read`; import anything outside the stdlib, `_common` and `aidd_evidence`; edit `read_hint.py`.
- Done when: every hook test of T-60 passes and the read_hint tests still pass.
- Open questions: none.

### T-62 — register the hook in `install_hooks.py`
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: XS

**Estimate**
- Effort: Low
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 40k
- Agent role: builder
- Model tier: medium
- Wave: 3

**Detail**
- Goal: install `tool_first_hint.py` as a `PostToolUse` hook on every Claude Code machine through the existing installer.
- Cites: FR-049.
- Depends on: T-60.
- Read first: `skill/scripts/install_hooks.py` lines 1-95; `tests/test_install_hooks.py` lines 76-155.
- Files to change: `tests/test_install_hooks.py`; `skill/scripts/install_hooks.py`.
- Naming contract: new `HOOK_DEFS` entry `('PostToolUse', 'Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell', SKILL_DIR / 'hooks' / 'tool_first_hint.py')` appended as the last element; timeout from `DEFAULT_TIMEOUT` (10); test method `test_registers_thirteen_hooks_with_session_memory_only_by_default` renamed `test_registers_fourteen_hooks_with_session_memory_only_by_default`.
- Behaviour:
  1. Tests first in `tests/test_install_hooks.py`: line 80 `13` → `14`; line 87 `13` → `14`; line 138 `14` → `15`; add `"tool_first_hint.py"` to the list on lines 142-146; add `self.assertEqual(by["tool_first_hint.py"], ("PostToolUse", "Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell"))` after line 153; run red.
  2. Append the entry to `HOOK_DEFS`.
  3. Docstring: line 9 `12 hooks` → `14 hooks`; after the `graph_refresh.py` lines (35-37) add `  - PostToolUse    -> hooks/tool_first_hint.py (matcher: Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell) spec 004 FR-049: advises a script after 4 repeated edits or shell commands; never blocks`.
- Tests first: step 1; `python -m unittest tests.test_install_hooks -v` red before step 2.
- Verify: `python -m unittest tests.test_install_hooks tests.test_prompt_trigger -v` → exit 0.
- Do NOT: run the installer against the real `~/.claude/settings.json`; change any other entry, matcher or timeout; touch `adapters/`.
- Done when: the verify command passes.
- Open questions: none.

### T-63 — the `aidd status` line
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: XS

**Estimate**
- Effort: Low
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 40k
- Agent role: builder
- Model tier: medium
- Wave: 3

**Detail**
- Goal: `aidd status` prints `tool-first: N advisories / M edits this session` right after the graph-first line.
- Cites: FR-052, AC-045.
- Depends on: T-60, T-65.
- Read first: `skill/scripts/aidd_status.py` lines 173-190 and 710-745.
- Files to change: `skill/scripts/aidd_status.py`.
- Naming contract: new `def _tool_first_line(root=None) -> str` placed directly after `_graph_first_line`; called in `format_global` as `_tool_first_line(),  # aidd:FR-052` on the line after `_graph_first_line(),  # aidd:FR-027`.
- Behaviour:
  1. Copy the structure of `_graph_first_line`: `n = m = 0`; `root = root or ev.find_root()`; `sess = _current_session(root)`.
  2. When `sess`: `n = len(ev.events(root, kind='tool_miss', session=sess))`; `edits = ev.read_tool_first_state(sess).get('edits')`; `m = edits if isinstance(edits, int) and edits >= 0 else 0`.
  3. Any exception → `n = m = 0`. Return `f'tool-first: {n} advisories / {m} edits this session'`. Never raises.
- Tests first: T-60's `test_ac045_status_line` is red before this task.
- Verify: `python -m unittest tests.test_tool_first_hint tests.test_aidd_status tests.test_read_hint -v` → exit 0.
- Do NOT: change `_graph_first_line`, `format_status` or the verification and approval lines; touch `adapters/` (T-66 does the mirror).
- Done when: the verify command passes.
- Open questions: none.

### T-64 — document the nudge in `skill/SKILL.md`
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
- Wave: 4

**Detail**
- Goal: document the tool-first nudge next to rule T1.
- Cites: FR-050, FR-052.
- Depends on: T-61, T-63.
- Read first: `skill/SKILL.md` line 461 (the `**T1 Tool-first**` paragraph) and line 312 (the graph-first nudge paragraph, as the wording model).
- Files to change: `skill/SKILL.md`.
- Naming contract: documents exactly these names and no others: hook `tool_first_hint.py`, threshold 4, window 15 minutes, triggers `same_shape`, `same_file`, `same_command`, silencer `aidd tools` for 300 s, events `tool_miss` and `tool_query`, status line `tool-first: N advisories / M edits this session`.
- Behaviour: append one sentence block to the end of the T1 paragraph on line 461: "On Claude Code the `tool_first_hint.py` hook advises (never blocks) after 4 edits of the same shape or to the same file within 15 minutes, or 4 shell commands in a row of the same shape (`same_shape`, `same_file`, `same_command`; digits, quoted literals and paths are ignored when comparing). Only an `aidd tools` query run by the agent silences it for 300 s. Each advisory is a `tool_miss` event and `aidd status` prints `tool-first: N advisories / M edits this session`."
- Tests first: no code; the check below exits 1 before this task and 0 after.
- Verify: `python -c "import sys; t=open('skill/SKILL.md', encoding='utf-8').read(); sys.exit(0 if 'tool_first_hint.py' in t and 'tool-first: N advisories' in t else 1)"` → exit 0.
- Do NOT: change any other section; mention b1SycLink; edit `adapters/dot-aidd/AIDD.md` or `CORE.md`.
- Done when: the verify command passes.
- Open questions: none.

### T-66 — mirror the two changed scripts
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
- Wave: 4

**Detail**
- Goal: keep the project bundle identical to the skill source for the two scripts this amendment changes.
- Cites: FR-052, FR-053 (mirror).
- Depends on: T-63, T-65.
- Read first: `tests/test_dot_aidd_mirror.py` lines 55-80.
- Files to change: `adapters/dot-aidd/scripts/aidd_evidence.py`; `adapters/dot-aidd/scripts/aidd_status.py`.
- Naming contract: none new; both targets are byte copies of `skill/scripts/aidd_evidence.py` and `skill/scripts/aidd_status.py`, so every name is the one fixed in T-63 and T-65.
- Behaviour: `cp skill/scripts/aidd_evidence.py adapters/dot-aidd/scripts/aidd_evidence.py` and `cp skill/scripts/aidd_status.py adapters/dot-aidd/scripts/aidd_status.py`; no hand edits. The hook file has no mirror (`read_hint.py` has none either).
- Tests first: `tests/test_dot_aidd_mirror.py` already asserts equality; run it before (red after T-63/T-65) and after (exit 0).
- Verify: `python -m unittest tests.test_dot_aidd_mirror -v` → exit 0.
- Do NOT: edit either file by hand; touch any other mirror; copy `tool_first_hint.py` into `adapters/`.
- Done when: the mirror test passes.
- Open questions: none.

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-60 | tests | 25 | 90 | 1 |
| 2 | T-65 | builder | 10 | 50 | 0.5 |
| 3 | T-61, T-62, T-63 | builder | 40 | 220 | 2 |
| 4 | T-64, T-66 | docs, builder | 5 | 50 | 0.25 |

Total agent time (critical path): 80 min
Total tokens (k): 410
Total human ref (critical path): 3.75 h
Tasks: 7
Computed by script from the per-task Estimate blocks: agent time and human ref = max per wave, tokens = sum.
