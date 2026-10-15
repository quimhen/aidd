# Plan — AIDD host parity (spec 009)

No screens: the Screen → Code and Component → Code maps do not apply. This plan fixes names, file ownership and the two interfaces the parallel tasks depend on. Revised after the pre-build coherence audit (12 findings applied).

## Naming & File Contract (fill this first — everything below depends on it)
| Item | Convention |
|---|---|
| Classes / components / types | PascalCase (Python classes, JS plugin export `AiddPlugin`) |
| Functions / variables / methods | snake_case in Python (the repo's own style), camelCase in the JS plugin |
| File names | snake_case for Python (`host_adapter.py`, `install_host.py`, `aidd_doctor.py`), lowercase for the OpenCode plugin (`aidd.js`) |
| Classes per file | One. Never bundle multiple classes into one file. |
| File-path pattern | hooks in `skill/hooks/` (mirrored byte-identical in `adapters/dot-aidd/hooks/`), CLI helpers in `skill/scripts/` (NOT mirrored; run through `aidd/cli.py`), tests in `tests/test_host_*.py` |

## Decision: reuse `rule_gate`, do not reimplement (Optimization brief option A)

`skill/hooks/rule_gate.py` already holds R1-R12 and the per-spec gate target. The adapter **spawns `rule_gate.py` as a subprocess** with the normalised JSON on stdin and passes its exit code and stderr through. It never imports `decide()`: `main()` also does the `AIDD_RULES` off/warn handling, the `rules_override` record (FR-908), the transcript sync, the caller marker and the fail-open `hook_error`, which `decide()` skips. `mark_code_edit.py` reads stdin at import time, so it is also spawned.

Known facts the plan relies on (verified in the audit): `SCRIPTS_DIR = ../scripts` (so installed `.aidd/hooks` + `.aidd/scripts` works); `.aidd/**` except `memory/` is already R9-protected; a missing session id becomes `unknown-session`; the legacy `require_aidd` check blocks any code write unless the per-session marker file exists, and only Claude's Skill-tool hook creates it.

## Interface 1 — `host_adapter.py` (T-01), consumed by T-03, T-04, T-05, T-06

```
python <hooks>/host_adapter.py <host> <phase>        host = gemini | opencode      phase = pre | post
stdin  : the host's own JSON event (UTF-8)
exit 0 : allow (or not an AIDD project, or a tool that is not a write)
exit 2 : block; stderr = the rule_gate message (names the next action)
stdout : empty on pre (Gemini reads stdout as JSON), empty on post
```

Order on `pre`: (1) no `.aidd/AIDD.md` in `cwd` or any parent → exit 0 (FR-912); (2) tool not a write/shell tool → exit 0; (3) create the session "AIDD invoked" marker (`_common.marker_path(session)`) so `require_aidd` is satisfied; (4) spawn `rule_gate.py` with the normalised event and return its exit code and stderr. `post`: spawn `mark_code_edit.py` with the normalised event (evidence `code_edit` / `spec_edit`).

| Host input | Normalised `tool_name` / `tool_input` |
|---|---|
| Gemini `write_file {file_path, content}` | `Write {file_path, content}` |
| Gemini `replace {file_path, old_string, new_string}` | `Edit {file_path, old_string, new_string}` |
| Gemini `run_shell_command {command}` | `Bash {command}` |
| OpenCode `write {filePath, content}` | `Write {file_path, content}` |
| OpenCode `edit {filePath, oldString, newString}` | `Edit {file_path, old_string, new_string}` |
| OpenCode `patch` / `multiedit` (paths in args) | `MultiEdit` over the named paths |
| OpenCode `bash {command}` | `Bash {command}` |
| anything else (reads, search, web) | allowed, exit 0, no gate call |

Shell commands go through the same gate, which checks protected paths only (R9); shell edits of code files remain the documented, ungated limit (FR-905). A malformed payload exits 0 and records `hook_error` (fail-open on a crash, as on Claude); a block is never silent.

**Approval on these hosts.** There is no AskUserQuestion transcript, so consent comes from the review page: `aidd review <spec>`, `aidd review <spec> --wait`, then `aidd rules approve <spec>` (the typed `Approve [tasks:<hash8>]` stays a fallback). T-11 documents this in `CORE.md`; AC-006 pins it.

## Interface 2 — install layout (T-04), consumed by T-05, T-07, T-08, T-09

`install_host.py install <host> <project-root> [--force]` does **not** call `aidd init` (`cmd_init --force` runs `rmtree` on `.aidd/`, which would delete memory, evidence and the gate pointer). It copies `adapters/dot-aidd/` file by file into `<project-root>/.aidd/`, comparing content, never deleting, then writes the host files. The shipped source is located from the `aidd` package root (`aidd/cli.py`'s `repo_root`), so the scripts are CLI-only: they live in `skill/scripts/`, run through `aidd/cli.py` `_run`, and are NOT mirrored into `adapters/dot-aidd/scripts/` (only `hooks/` is mirrored).

| Host | Files written | Registration |
|---|---|---|
| gemini | `.aidd/**` (incl. `CORE.md`, `hooks/`), `GEMINI.md` (imports `@.aidd/CORE.md`) | `.gemini/settings.json`: `hooks.BeforeTool` and `hooks.AfterTool` entries named `aidd-gate` / `aidd-record`, command `python .aidd/hooks/host_adapter.py gemini pre\|post`, matcher `write_file\|replace\|run_shell_command`. Exact schema taken from the Gemini hooks reference at build time, cited in the file header |
| opencode | `.aidd/**`, `.opencode/skills/aidd/SKILL.md`, `.opencode/plugins/aidd.js` | `".opencode/plugins/aidd.js"` appended once to the `plugin` array of `.opencode/opencode.json`, existing entries kept |

Idempotent: a file whose content equals the shipped one is `unchanged`; a modified one is `skipped` unless `--force`. JSON files are merged by key, never rewritten wholesale.

`aidd_doctor.py [--host H] [--root DIR] [--json]` checks, each with a `PASS|FAIL <id> <message> -> <fix>` line: `D1` `.aidd/` complete and equal to the shipped `adapters/dot-aidd/` (located as above), `D2` `CORE.md` under 12 KB, `D3` pointer files present and importing the core, `D4` hook or plugin registered and the registration unaltered, `D5` gate dry-run: a fixture write with no approval must exit 2, `D6` `rules_override` present, `D7` host binary version vs pinned range (warning only). Exit 1 when any D1-D5 fails.

## File ownership (one owner per file)

| File | Task | Notes |
|---|---|---|
| `skill/hooks/host_adapter.py` | T-01 | new; Interface 1 incl. marker and no-AIDD-project exit |
| `skill/hooks/rule_gate.py` | T-02 | add the host config files to the R9 protected set (FR-911); no other change |
| `adapters/opencode/plugins/aidd.js` | T-03 | rewritten: builds `{sessionID, cwd, tool, args}`, spawns the adapter, throws on exit 2 |
| `skill/scripts/install_host.py` | T-04 | new; per-file copy, no `cmd_init` |
| `skill/scripts/aidd_doctor.py` | T-05 | new |
| `tests/test_host_gates.py` | T-06 | FR-904 to FR-908, FR-911, FR-912; AC-001 to AC-003, AC-006; node-based check of `aidd.js` (skipped with a reason when `node` is absent) |
| `tests/test_host_install.py` | T-07 | FR-901 to FR-903; AC-005 |
| `tests/test_host_doctor.py` | T-08 | FR-909, FR-910, FR-911 (D4); AC-004 |
| `aidd/cli.py` | T-09 | `install` and `doctor` subcommands, passthrough like `pending` |
| `tests/test_dot_aidd_mirror.py` | T-10 | owns the byte-identical hook copies in `adapters/dot-aidd/hooks/` (host_adapter, rule_gate, _common, require_aidd, require_independent_audit, require_graph_coherence_audit, mark_code_edit) and a new hooks list in the test |
| `adapters/README.md` | T-11 | also owns `skill/SKILL.md` (host sections, quote wording), `adapters/dot-aidd/CORE.md`, `adapters/GEMINI.md`, `adapters/AGENTS.md.snippet`, `adapters/opencode/skills/aidd/SKILL.md` (delivered earlier, uncommitted; CORE.md gains the approval route) |
| `skill/templates/spec.md` | T-13 | quote wording 5+ words / 2+ words; same owner for its `adapters/dot-aidd/templates/spec.md` twin and for `skill/AIDD.md` with its `adapters/dot-aidd/AIDD.md` twin |
| `skill/scripts/aidd_status.py` | T-14 | dated hook errors and overrides; same owner for its `adapters/dot-aidd/scripts/aidd_status.py` twin and `tests/test_aidd_status.py` |
| (no source file) verification | T-12 | `aidd verify`, evidence files; the closing auditor of Step 6 writes `qa-audit.md` (R7), outside this list |

## Risks and how the plan covers them

- **Host contract differs from the public docs.** T-04 and T-03 fetch the vendor docs at build time and cite them; T-12 runs the real binary when present and records `not-verified` plus a manual script when not (R10).
- **Gate blocks the wrong spec.** Reused per-spec gate target and `aidd rules activate`; AC-003 pins it.
- **Gate blocks every write with a Claude-only message.** The adapter creates the marker (FR-912); AC-002 asserts the message is absent.
- **Install destroys the owner's memory or evidence.** Per-file copy, never `rmtree` (AC-005).
- **Agent edits the registration to switch the gate off.** FR-911 (T-02) and `doctor` D4.
- **Windows shell quoting.** The command string uses `python` and forward slashes; T-06 includes a path with spaces.
- **`aidd.js` throw path untested by Python.** T-06 adds a node-based check or a recorded manual-test row.

## Verification plan

V-1 to V-5 of the spec. The full suite (`tests/run_parallel.py`) runs once, after the last wave, never per task.
