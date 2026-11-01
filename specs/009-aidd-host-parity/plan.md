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


<!-- 009 amendment 01 integrated for review; approvals pending -->

# Draft plan — amendment 01 host and CI portability

**DRAFT — R6 approval required before implementation.** No UI or database change. Reuse the existing rule gate and path helpers; do not implement a second policy engine. The exact code changes and regression cases are in the companion task draft.

## Naming & File Contract (fill this first — everything below depends on it)
| Item | Convention |
|---|---|
| Classes / components / types | Python PascalCase test classes; existing function-style modules remain function-style |
| Functions / variables / methods | Python snake_case; preserve existing public signatures |
| File names | Existing snake_case paths in `skill/`, `tests/` and `.github/workflows/` |
| Classes per file | Keep existing classes; do not combine unrelated new classes |
| File-path pattern (if one exists) | `skill/` sources and byte-identical required `adapters/dot-aidd/` mirrors; `tests/test_*.py` |

## File ownership and dependencies

| Target | Task | Contract |
|---|---|---|
| `tests/test_aidd_readiness.py` | T-15 | Convert existing eight pytest functions into unittest cases, preserving two parameter values (at least nine cases). |
| `tests/test_visual_review_binding.py` | T-16 | Convert existing six pytest functions into unittest cases with snapshot and gate assertions intact. |
| `skill/scripts/flowmap.py`, mirror | T-17 | Precompute escaped JSON outside f-string expression; preserve rendered output and signature. |
| `tests/test_cross_platform_paths.py` | T-18 | Add native/foreign spelling and deny/allow regression cases; no real network share needed. |
| `skill/hooks/rule_gate.py`, `skill/scripts/aidd_evidence.py`, mirrors | T-19 | Preserve native real-path checks; foreign spelling cannot be mistaken for a local path; keep R6/R9 fail-closed. This overlaps the fingerprint amendment in spec 007: T-19 waits for its `aidd_evidence.py` work to be integrated and frozen, then the same file owner applies T-19 serially; do not start both at once. |
| `skill/scripts/aidd_memory_import.py`, mirror | T-20 | Diagnose absolute path conversion on Windows; preserve inside project relative path and rejection of outside paths. |
| `tests/test_aidd_memory_import.py` | T-20 | Add explicit inside/outside, sibling-prefix, symlink/junction, foreign path and nonexistent-relative cases; same owner as importer. |
| `tests/report_guard_portability.py` | T-23 | Compare old/current/desired for reported guard regressions on each OS before changing the guard; publish the exact proposed exception list for owner review. |
| `tests/test_ci_runner.py` | T-24 | Test runner's exact exit, required-case and skip handling with synthetic stdlib suites. |
| `tests/run_parallel.py` | T-25 | Add `--ci-guard` to the existing runner (default behavior unchanged): load pinned guard, run full discovery once, count named cases and fail on failures, skips of required cases, unavailable baseline, exceptions or timeout. |
| `tests/requirements-test.txt` | T-26 | Pin `pytest==8.3.5` only as test dependency for existing spec 009/010 verification rows; runtime dependencies stay empty. |
| `.github/workflows/test.yml` | T-21 | Keep six-cell matrix, install test-only requirements, run the CI runner once and make the pinned guard available. |
| evidence only | T-22 | Run tests once in coordinated round and record actual matrix results; no invented Linux evidence. |

## Security and verification contract

Path parsing must distinguish native filesystem resolution from lexical recognition of a foreign-platform spelling. Actual symlink/junction targets and `..` containment use native canonical resolution. A foreign Windows drive/UNC string on POSIX must never be asserted to name a real local path merely because it resembles one. Protected spec artifacts or `.aidd` in an ambiguous foreign token are denied; unrelated native files are allowed. POSIX native `.AIDD` and `.aidd`, or names with trailing dots, may be distinct: do not claim they are the same filesystem object. A Windows-style token carries Windows alias semantics and is classified conservatively without granting access. For memory import, allow a nonexistent relative file only if resolving its existing ancestors proves containment; reject foreign absolute paths that cannot be mapped safely, sibling prefixes, traversal and symlink/junction escapes. Existing privacy restrictions remain. Unavailable native link/junction capabilities are explicitly not verified.

Before T-19, T-23 compares pinned and current guards with each reported failing input on Windows and Linux and records `(old, current, desired)`. Any actual deviation from spec 010 FR-1003 is proposed as a named, minimal security correction and requires reconciliation of spec 010 and owner approval; all remaining generated and handwritten cases retain exact decision/message parity. Never broadly waive FR-1003. T-24 then T-25 establish one cross-platform stdlib runner: `tests/run_parallel.py --ci-guard` launches its worker once; the worker calls `load_old_guard()` and fails if it returns `None`, performs one `unittest` discovery and tracks the exact IDs and skips. The parent captures and forwards stdout/stderr, preserves failure and turns a child timeout into a nonzero result; the workflow job has a longer timeout. Required equivalence skips fail; an unavailable native junction is recorded as not verified rather than pass.

Builders use static checks only; the orchestrator executes focused tests once in their respective waves. For final close, 009 V-5 and CI both name `python tests/run_parallel.py --ci-guard`; one actual run per OS/interpreter cell supplies its evidence without rerunning the suite for V-1–V-4. Before consolidating, compare test IDs collected by old V-1–V-4 and new discovery without executing either set; prove identical coverage on both OSes, preserve assertions and report conditional skips. Only if complete may historical V-1–V-4 become traceability records; keep any demonstrably uncovered check separate. Changing the Verification table invalidates its old approval and requires a new one. Python test-only dependencies are pinned in `tests/requirements-test.txt`; runtime dependencies remain empty and spec 010 pytest rows remain unchanged. Six-cell GitHub evidence requires an authorized push or independently verified CI; Windows alone does not prove Ubuntu. Pinned SHA is `3cf5fccaa395f1dbe709b0ce800d1ad412418d39`; CI checks `git cat-file -e '3cf5fccaa395f1dbe709b0ce800d1ad412418d39^{commit}'` under native Windows PowerShell and native Linux Bash. The static quoted argument is not built from untrusted text and does not replace loader preflight.

Pre-build collection-only observation on Windows: the five current V-1–V-4 modules produced 307 case IDs through `pytest --collect-only` and the same 307 IDs through unittest discovery, with zero missing and zero additional IDs. Neither collection executed those tests. This is a baseline for the current checkout only, not evidence of equivalent execution, unchanged behavior after conversion, or Linux coverage; T-25/T-22 must verify those conditions without running another full suite.
