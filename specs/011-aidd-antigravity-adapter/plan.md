# Plan — AIDD Antigravity adapter (spec 011)

No screens: the Screen → Code and Component → Code maps do not apply. This plan fixes names, file ownership and the interfaces the parallel tasks depend on. The contract below was OBSERVED with the real `agy` 1.0.13 (probe hook; captured payloads in the session scratchpad `agy/payloads.jsonl`, and `agy/probe_hook.py` shows how they were captured). Revised after the pre-build coherence audit (7 findings applied).

## Naming & File Contract (fill this first — everything below depends on it)
| Item | Convention |
|---|---|
| Classes / components / types | PascalCase |
| Functions / variables / methods | snake_case (the repo's own Python style) |
| File names | snake_case for Python; templates keep the host's own names (`SKILL.md`, `aidd.md`) |
| Classes per file | One. Never bundle multiple classes into one file. |
| File-path pattern | adapter in `skill/hooks/host_adapter.py` (mirrored byte-identical in `adapters/dot-aidd/hooks/`), CLI helpers in `skill/scripts/`, shipped host templates in `adapters/antigravity/`, tests in `tests/test_host_*.py` |

## Observed Antigravity contract (the facts the code relies on)

| Fact | Evidence |
|---|---|
| Workspace hooks file: `<project>/.agents/hooks.json`; the hook command runs with the working directory `<project>/.agents` (the folder that holds hooks.json) | probe payload log: `cwd` ends with `\.agents` |
| PreToolUse payload keys: `toolCall {name, args}`, `conversationId`, `workspacePaths` (list of project roots, forward slashes), `stepIdx`, `modelName`, `transcriptPath`, `artifactDirectoryPath`; PostToolUse adds `error`, and `toolCall` can be null; there is no `cwd` | probe log; docs |
| Tools: `write_to_file {TargetFile, CodeContent, Overwrite}`, `replace_file_content {TargetFile, TargetContent, ReplacementContent, StartLine, EndLine, AllowMultiple}`, `multi_replace_file_content` (arguments not observed: treat `ReplacementChunks` as a list of `{TargetContent, ReplacementContent}` and tolerate other shapes), `run_command {CommandLine, Cwd, WaitMsBeforeAsync}`, `view_file {AbsolutePath}` | probe log; docs |
| PreToolUse answer: stdout JSON `{"decision": "allow\|auto_approve\|deny\|ask\|force_ask\|deny_unless_prior_grant", "reason": "..."}`; `deny` reaches the model as `tool call denied by pre-tool hook: <reason>` and the call does not run | real run: `FORBIDDEN.py` was not created |
| The hook `matcher` was only ever observed with `"*"`; whether it is a regex, a glob or an exact name is NOT verified | probe used `*`; docs say regex |
| Exit-code semantics, crash and timeout behaviour are undocumented | docs; so the adapter never relies on an exit code |
| Rules: `.agents/rules/*.md`, frontmatter `trigger: always_on`, a single file over 24,000 bytes is truncated, `@[label](path)` inlines a file | docs |
| Skills: `.agents/skills/<name>/SKILL.md`, frontmatter `description` required, `name` optional | docs |

## Decision: extend the spec 009 layer (option A)

The adapter keeps spawning `rule_gate.py` and `mark_code_edit.py` with the Claude-shaped event; only the translation and the answer protocol are new. Existing hosts (gemini, opencode) keep their exit-code behaviour byte for byte.

## Interface 1 — `host_adapter.py antigravity pre|post` (T-01)

```
python <hooks>/host_adapter.py antigravity <pre|post>      stdin: the Antigravity payload (UTF-8 JSON)
exit code : always 0 (the answer is on stdout)
stdout    : pre  -> one JSON object {"decision":"deny","reason":"<gate message>"} when the gate blocks,
                    {"decision":"allow"} otherwise
            post -> {}
```

Normalisation (then the same `pre` order as the other hosts: no project -> allow; non-write tool -> allow; session marker; spawn `rule_gate.py`):

| Antigravity input | Normalised `tool_name` / `tool_input` |
|---|---|
| `write_to_file {TargetFile, CodeContent}` | `Write {file_path, content}` |
| `replace_file_content {TargetFile, TargetContent, ReplacementContent}` | `Edit {file_path, old_string, new_string}` |
| `multi_replace_file_content {TargetFile, ReplacementChunks[]}` | `MultiEdit {file_path, edits:[{file_path, old_string, new_string}]}` |
| `run_command {CommandLine, Cwd}` | `Bash {command}`; the callee `cwd` is `Cwd` when it is inside the project |
| anything else (`view_file`, search, web, `toolCall` null) | allowed, no gate call |

Internals T-01 must change (found by the audit): `HOSTS`; the normaliser selector (today every non-gemini host goes to the opencode normaliser); `_tool_of` (read `toolCall.name`, also used by `unmapped_write_tool`); `_args_of` (read `toolCall.args`); `_session_of` (read `conversationId`); and the normalised event's `cwd` must be set to the PROJECT ROOT (today it is the hook's own cwd, `.agents`, and that becomes the `rule_gate` subprocess cwd). The antigravity branch lives in `main()` around a run-core that returns `(code, err_bytes)`; the exit-code path keeps `_pass_stderr` and its return value, so gemini and opencode stay byte-identical.

Project root: the first `workspacePaths` entry (or the nearest ancestor of it) holding `.aidd/AIDD.md`; fallback: the project of the absolute `TargetFile`. A missing `cwd` is not an error (`_cwd_of` falls back to the process cwd, `.agents`, and `_project_root` walks up). Session id: `conversationId`, sanitized as for the other hosts. Block output: `reason` is the gate's stderr text. A gate timeout answers `deny` (fail-closed); any other internal failure answers `allow` and records `hook_error`. Argument keys are read tolerantly (`TargetFile|AbsolutePath|FilePath|file_path|path`, `CodeContent|Content|content`, `CommandLine|command`) and an unmapped write-like tool name is recorded as `hook_error` and allowed, as for the other hosts.

## Interface 2 — installer, CLI and shipped templates (T-02, T-05)

`install_host.py install antigravity <project-root> [--force] [--json]`; `aidd/cli.py` (owned by T-02) adds `antigravity` to the `choices` of BOTH `aidd install --host` and `aidd doctor --host` and to the closing hint:

| File written | Source | Notes |
|---|---|---|
| `.aidd/**` | `adapters/dot-aidd/` | as the other hosts |
| `.agents/skills/aidd/SKILL.md` | `adapters/antigravity/skills/aidd/SKILL.md` (T-05) | thin pointer: frontmatter `name: aidd` and `description`, points to `.aidd/CORE.md`, the install and doctor commands |
| `.agents/rules/aidd.md` | `adapters/antigravity/rules/aidd.md` (T-05) | frontmatter `trigger: always_on`; short text plus `@[CORE](../../.aidd/CORE.md)`; whether the include path resolves is checked with the real `agy` in T-10 (fallback: inline the core, doctor then compares) |
| `.agents/hooks.json` | merged by key | the `aidd` entry: `PreToolUse` and `PostToolUse`, matcher `*` (the only syntax observed; the adapter already allows non-write tools), hooks `[{type: command, command: "python ../.aidd/hooks/host_adapter.py antigravity pre"` (and `post`)`, timeout: 30}]`; `enabled: true`; foreign names untouched; a corrupt file is skipped, never overwritten |

**Symlink safety (all hosts, one helper).** The helper sits at the top of `_copy_file` (before the `is_dir` / `exists` checks, which follow links) and in `_write_bytes`, so the copies and the JSON merges are all covered. Before writing a destination it checks every path component from the project root down. Link detection: on Windows `os.lstat(p).st_reparse_tag in (stat.IO_REPARSE_TAG_SYMLINK, stat.IO_REPARSE_TAG_MOUNT_POINT)` (NOT the plain reparse-point attribute: OneDrive and other cloud placeholders set it too and real folders would be reported as links; `os.path.isjunction` needs Python 3.12 and the repo supports 3.10); elsewhere `os.path.islink`; the target is read with `os.readlink`. If a component is a link the file is reported `skipped (symlink -> <target>)`; with `--force` ONLY the link itself is removed (`os.unlink` for a file link, `os.rmdir` for a directory symlink or junction) and a real folder is created. Never `shutil.rmtree` on a link, never follow it to write, never touch the target. A test uses a link whose target is a temp folder with a sentinel file.

`aidd_doctor.py --host antigravity` (T-03): D1 files equal to the shipped ones; D2 `CORE.md` under 12 KB and the rule file under 24,000 bytes; D3 skill and rule pointers present and naming `.aidd/CORE.md`, and `.agents/skills/aidd` is NOT a link (same reparse-tag test, copied locally because `install_host.py` has another owner); D4 the `aidd` entry of `.agents/hooks.json` with matcher `*` and the exact command; D5 copies the installed `.aidd/hooks` into the temp fixture project, builds an unapproved open spec, then runs the REGISTERED command string from `<tmp>/.agents` (the hook cwd) with an Antigravity-shaped `write_to_file` event and passes only on exit 0 with stdout JSON `decision == "deny"` (the exit-code hosts keep passing on exit 2); D6 `rules_override` events; D7 `agy --version` (information). A missing `.aidd` makes the relative command fail: D1 reports it, and the app and IDE flavours' hook cwd is documented as unverified.

## Interface 3 — protected gate file (T-04)

`.agents/hooks.json` is added to the four places that handle `.gemini/settings.json` in `rule_gate.py`: `BASH_MARKERS` (add `.agents` and `hooks.json`), `HOST_GATE_FILES`, `_HOST_GATE_DIRS` (add `('.agents',)`, which is what makes `rm -r .agents` get checked) and `HOST_GATE_MESSAGE`; other files under `.agents/` stay writable.

## File ownership (one owner per file)

| File | Task | Notes |
|---|---|---|
| `skill/hooks/host_adapter.py` | T-01 | antigravity host, stdout JSON protocol; other hosts unchanged |
| `skill/scripts/install_host.py` | T-02 | antigravity host, symlink-safe writes for every host; same owner for `aidd/cli.py` (the two `choices` lists and the hint) |
| `skill/scripts/aidd_doctor.py` | T-03 | antigravity checks |
| `skill/hooks/rule_gate.py` | T-04 | `.agents/hooks.json` protected in the four places |
| `adapters/antigravity/skills/aidd/SKILL.md`, `adapters/antigravity/rules/aidd.md` | T-05 | new shipped templates |
| `tests/test_host_gates.py` | T-06 | adapter protocol with the real captured payloads, FR-1106 |
| `tests/test_host_install.py`, `tests/test_host_doctor.py` | T-07 | install (incl. the symlink cases) and doctor |
| `adapters/dot-aidd/hooks/host_adapter.py`, `adapters/dot-aidd/hooks/rule_gate.py` | T-08 | byte-identical copies after T-01 and T-04 |
| `adapters/README.md` | T-09 | also `adapters/dot-aidd/CORE.md` (host table) and `skill/SKILL.md` (install section) |
| `specs/011-aidd-antigravity-adapter/evidence/verify-summary.md` | T-10 | `aidd verify`, real `agy` runs, the b1SycLink install; the closing auditors write `qa-audit.md` |

## Risks and how the plan covers them

- **The installer writes through the b1SycLink symlink and edits the repo's skill folder.** The symlink-safety helper at the top of `_copy_file` and in `_write_bytes`, and a sentinel test; AC-1103.
- **The matcher syntax is not what the plan assumes.** The entry registers `*` (observed); a wrong syntax cannot make the gate silently inactive.
- **The hook command resolves from the wrong folder.** Observed cwd `.agents`, command `../.aidd/...`, doctor D5 runs the REGISTERED command from that folder; the adapter also locates the project from `workspacePaths`.
- **The rule's `@[...]` include does not resolve.** Checked with the real `agy` in T-10; fallback inline.
- **`--dangerously-skip-permissions` skips the hook.** Measured in T-10 (AC-1106) and documented.
- **A crash of the hook with no JSON.** The adapter answers `allow` and records `hook_error`; its own timeout stays under the host's 30 s default (the gate timeout is 15 s).
- **OneDrive folders reported as links.** The reparse-tag test instead of the attribute.

## Verification plan

V-1 to V-4 of the spec. FR-1107 (docs) and FR-1108 (the b1SycLink install) are covered by recorded runs of T-10 (a documentation grep and `aidd doctor --host antigravity --root D:/Fuentes/b1SycLink`). The real `agy` runs (AC-1105, AC-1106, AC-1107) are executed by T-10 and recorded as evidence, keeping to about four prompts.
