# AIDD — cross-agent adapters

Everything here makes AIDD's methodology work identically across Claude Code, OpenCode, Codex,
Gemini CLI, Cursor, Windsurf, Cline, GitHub Copilot, and any other agent tool that can run a shell
command — without duplicating the pipeline per tool. One core, several thin pointers, plus one
generator for the tools whose native mechanism is "a command file in a fixed folder."

## Layers

**Tier 1 — the tool-agnostic core (does the real work, needs no agent-specific integration):**
`dot-aidd/` — copy this to `<project-root>/.aidd/`. It holds `AIDD.md` (the full methodology,
stripped of anything Claude-specific) plus `scripts/find_spec.py` and `scripts/check_spec.py` —
both pure stdlib Python, runnable by literally any agent that can execute a shell command. This
alone is enough for **any** agent to follow AIDD correctly if it's told to read `.aidd/AIDD.md` —
everything below is just making sure each tool actually gets told that, in its own convention.

**Tier 2 — `AGENTS.md`:** the emerging cross-tool convention (OpenAI Codex reads it natively;
increasingly respected by other tools too). Append `AGENTS.md.snippet`'s contents to the
project's own `AGENTS.md` (create one if it doesn't exist). This one file covers Codex fully,
and is a reasonable fallback for any tool with no more specific adapter below.

**Tier 2b — `GEMINI.md`:** Gemini CLI / Antigravity's own project-instructions convention.
Copy `GEMINI.md` as-is to the project root — it imports `.aidd/CORE.md` with Gemini CLI's `@file.md`
syntax (documented; whether Gemini reads `AGENTS.md` natively is NOT confirmed, so do not rely on a
pointer to it). `.aidd/CORE.md` is the short (~6 KB) entry for every non-Claude host: hosts
truncate reads at ~50 KB, and `AIDD.md` is ~120 KB, so loading it whole silently dropped
Steps 2-7. **Gate status (implemented, spec 009; pending verification against real binaries):**
Gemini CLI runs a `BeforeTool` hook from `.gemini/settings.json` (exit code 2 blocks the call) and
OpenCode runs `tool.execute.before` (a thrown error blocks it). Both go through
`.aidd/hooks/host_adapter.py`, which spawns `rule_gate.py` (the same gate Claude Code uses) and
passes its message through; an `AfterTool` / `tool.execute.after` call records `code_edit` and
`spec_edit` evidence. The host registration files (`.gemini/settings.json`,
`.opencode/opencode.json`, the plugin) are protected (R9). Antigravity has its own hook tier
(Tier 3b below). This is the always-read context layer; Tier 5
below additionally gives Gemini CLI real per-step native slash commands
(`.gemini/commands/aidd-*.toml`) — the two are complementary.

**Known limits, stated plainly:**
- Shell edits of code files are not gated (same as Claude Code); shell commands are only checked
  for writes into protected paths.
- An OpenCode `patch` is gated by the paths it names, not by its content.
- The OpenCode once-per-session reminder was dropped; the block message is the guidance.
- The Gemini hook command uses a relative path (`python .aidd/hooks/host_adapter.py ...`) and must
  be confirmed against a real Gemini CLI binary.
- OpenCode tool-argument names other than `filePath` / `command` (`oldString`, `newString`,
  `edits`, `patchText`) come from the plan, not from documentation.
- Owner approval has no AskUserQuestion transcript on these hosts: `aidd review <spec> --wait`,
  the owner approves in the page, then `aidd rules approve <spec>`.
- `python` must be on PATH: the Gemini hook and the OpenCode plugin call bare `python`. If it is
  missing the gate does nothing (the plugin warns once; `aidd doctor` D5 FAILs). On Linux/macOS
  alias `python` to python3.
- Shell protection of the registration files and `.aidd/` is heuristic (lexical), like R9 for
  `.aidd` on Claude Code: string-built paths in `python -c` can evade it.
- Other files under `.opencode/plugins/` are writable by design and run at startup, so one could
  rewrite `aidd.js` after a restart; `aidd doctor` D4 detects the change afterwards, it does not
  prevent it.
- `.gemini/.env` is protected, and writing AIDD_RULES / AIDD_TESTING / AIDD_EVIDENCE_DIR /
  AIDD_SESSION_ID into any `.env*` file with a file tool is blocked. That is a file-tool check
  only, not a guarantee: a two-step route (write the text to another file, then `mv`/`cat >>` it
  into `.env` from the shell), an OpenCode `patch`/`apply_patch` (gated by path, its text is not
  scanned) and an unknown append-style tool can still carry it, so treat the gate as raising the
  bar, like R9. AIDD_RULES stays an owner-only setting of the environment that launches the host.
- The unknown-tool pattern (S3) applies to OpenCode only: the installed Gemini matcher is
  `write_file|replace|run_shell_command`, so other Gemini or MCP write tools never reach the
  adapter. On OpenCode, built-in `todowrite` matches the write pattern: it costs two process
  spawns per call and logs `unmapped write-like tool` hook errors (accepted noise, open exception).
- The OpenCode plugin spawns the adapter only for write-like tools (reads cost nothing). Tools are
  matched by name (known list plus a write/edit/patch/replace/create/append/insert/save/delete/remove/move/rename pattern), so a write tool with an
  unusual name and no extractable path is NOT gated; unmapped cases are recorded as hook_error.
- A gate that does not answer within 15 s BLOCKS the call (fail-closed), so padding a shell command
  cannot skip it. The cause of the slowness is the lexical shell guard in `rule_gate.py`, about
  2 ms per word on commands that mention a protected path: a 2 KB such command stalls about 4 s and
  roughly 7 KB hits the limit (shorten the command). Making the tokenizer linear is a recorded
  follow-up, not part of spec 009.
- Real-binary status (2026-10-14): OpenCode 1.18.30 was driven with a model session and the plugin
  blocked a code write and a shell write to its own file. Gemini CLI could not be run here (its free
  personal tier is retired; no model session without an API key) so its hook rests on the public
  docs and the tests; in headless mode it also needs a trusted folder (`--skip-trust` or
  `GEMINI_CLI_TRUST_WORKSPACE=true`), and in an untrusted folder the project hooks may not load.
  Antigravity is covered by Tier 3b (spec 011). Never symlink `skill/` into `.agents/skills/`: a
  symlinked skill folder loads the 70 KB Claude `SKILL.md`. Details in
  `specs/009-aidd-host-parity/evidence/verify-summary.md`.

**Tier 3b — Antigravity (`agy` CLI):** `aidd install --host antigravity [project]`, then
`aidd doctor --host antigravity`. Written (same adapter and gate as Gemini/OpenCode):

| Path | What |
|---|---|
| `.aidd/**` | portable bundle, incl. `hooks/host_adapter.py` and `CORE.md` |
| `.agents/skills/aidd/SKILL.md` | thin pointer (~1.5 KB), not the 70 KB skill |
| `.agents/rules/aidd.md` | always-on rule (`trigger: always_on`, `@[CORE](../../.aidd/CORE.md)`) |
| `.agents/hooks.json` | `aidd` entry, matcher `*`, command `python ../.aidd/hooks/host_adapter.py antigravity pre\|post` |

Observed contract (real `agy` 1.3.5; first seen on 1.0.13; 2026-10-14):
- The hook runs with cwd `<project>/.agents`, hence the `../.aidd/...` command path.
- The PreToolUse payload has `toolCall {name, args}`, `conversationId`, `workspacePaths` and no cwd.
  Tools: `write_to_file {TargetFile, CodeContent}`, `replace_file_content {TargetFile, TargetContent,
  ReplacementContent, StartLine, EndLine}`, `run_command {CommandLine, Cwd}`, `view_file {AbsolutePath}`.
- The hook denies on stdout with `{"decision":"deny","reason":...}` (exit code unused); the model sees
  `tool call denied by pre-tool hook: <reason>`. The adapter always exits 0.
- The matcher `*` is the only syntax observed; the adapter allows non-write tools. The hook never sees
  the event name, so the phase is an argument (`pre` / `post`).

Verified with the real host in a scratch project with an unapproved spec:
- A `write_to_file` of `src/app.py` was denied (file absent, full R6 message seen by the model); an
  overwrite of `.agents/hooks.json` was denied by R9 and the file stayed byte-identical.
- `--dangerously-skip-permissions` does NOT skip the hooks (the write was still denied).
- The always-on rule injects the core: the model quoted the first line of `CORE.md` with no tool use.
- The installer never writes through a symlink or junction: without `--force` it reports
  `skipped (symlink at <path> -> <target>)`; with `--force` it replaces only the link by a real
  folder (exercised on b1SycLink, whose `.agents/skills/aidd` pointed at the repo's `skill/`, which
  stayed unchanged).

Not verified: the Antigravity app and IDE flavours (same `.agents/hooks.json` per the docs, but hook
cwd and payload were only observed on the CLI); `Stop` hooks (not used); `multi_replace_file_content`
arguments (the adapter tolerates several shapes); the host's exit-code semantics and crash behaviour
(undocumented). The user-level `~/.gemini/config/hooks.json` is NOT protected (outside the project).
Hardened in Amendment 1 of spec 011 (the five limits the closing audit had accepted): (1) the plugin hook
registrations `.agents/plugins/<name>/hooks.json` and the user-level `~/.gemini/config/hooks.json` are now
protected from agent writes (file tools by path, the shell guard by name, including `$HOME` and
`%USERPROFILE%` forms); whether the CLI loads project plugin hooks and how decisions from several hooks combine
is still not verified; (2) the files that could shadow the interpreter when the hook runs with cwd `.agents`
(direct children named `python*` or ending `.bat`, `.cmd`, `.exe`, `.com`, `.ps1`, also through a copy into the
folder) are protected; `.agents/rules/**` and `.agents/skills/**` stay writable; the hijack itself was never
reproduced with agy 1.3.5 (a planted `python.bat` did not replace the interpreter), so this is defence in
depth, and a non-`python` interpreter name or an absolute interpreter path at install time are not done;
(3) hook stdin nested deeper than 100 levels is denied in the PRE phase on every host (the POST phase never
denies; plain non-JSON garbage and empty stdin keep allowing with a hook error); (4) the installer writes
every file through a temporary file and `os.replace`, so a hard link at the destination is broken instead of
written through; (5) a `TargetFile` that is not a string and an unreadable `ReplacementChunks` are denied, a
relative `TargetFile` with no `workspacePaths` is resolved against the project found from the hook's cwd, and
`aidd install` exits 1 when a gate registration file (`.agents/hooks.json`, `.gemini/settings.json`,
`.opencode/opencode.json`) is skipped. Still open: the Antigravity app and IDE flavours,
`multi_replace_file_content` arguments seen in a real run, the host's exit-code semantics, and the file-symlink
gap of the shell guard (spec 010 X1).

**Tier 3 — OpenCode:** OpenCode has its own native skill format (confirmed identical in shape to
Claude Code's: YAML frontmatter + markdown body) and a plugin system with at least one confirmed
hook point (`tool.execute.before`).
- `aidd install --host opencode [project]` writes `.opencode/skills/aidd/SKILL.md` and
  `.opencode/plugins/aidd.js`, and appends `".opencode/plugins/aidd.js"` once to the `"plugin"`
  array in `.opencode/opencode.json` (existing entries kept).
- The plugin blocks gated write/edit/multiedit/patch/bash calls by throwing the gate's message
  (implemented; the earlier note that OpenCode cannot gate writes is superseded, and the real-binary
  check is still pending). `AGENTS.md`/the OpenCode skill remain the instruction layer.
- Verify with `aidd doctor --host opencode`.

**Tier 4 — Claude Code:** unchanged, not part of this adapter set — see
`../skill/` (the actual Claude Code skill: `SKILL.md` + `hooks/` + `scripts/` + `templates/`).
Claude Code is the one tool here with a real hard-block hook (`require_aidd.py`) and an
automatic Step -1 pre-run inside `prompt_trigger.py`; the other tools approximate what they can
of that behavior, honestly short of full parity where their own hook systems don't support it.

**Ollama** is a model backend, not an agent surface — there's nothing to adapt here directly.
Whichever agent CLI is configured to run against an Ollama-served model (OpenCode, or others)
already picks up that tool's own adapter above; the adapter operates at the agent-tool layer,
independent of which model is behind it.

**Tier 5 — generated native commands (Gemini CLI, Cursor, Windsurf, Cline, GitHub Copilot):**
these five agents all support the same real, documented mechanism — drop a command file with a
description + prompt body into a fixed per-agent folder, and the tool exposes it as a native
slash command. Rather than hand-maintain five near-identical copies of the eight
`commands/aidd-*.md` pipeline-stage commands, `skill/scripts/generate_adapters.py` renders all
five from that one source of truth. This is AIDD's optimized take on the mechanism spec-kit uses
for its ~35 agent integrations: spec-kit gets there through a 3-level class hierarchy per agent
plus an install manifest with content hashing and an upgrade/teardown lifecycle — machinery sized
for a package-manager-scale surface (extensions/presets/bundles, community catalogs) this project
deliberately doesn't have. AIDD keeps only the load-bearing part of that mechanism: one small
config dict per agent (`skill/scripts/adapter_targets.py` — install dir, file format, argument
placeholder, invocation phrasing), two renderer functions (Markdown, TOML), and idempotent
regeneration instead of a manifest to reconcile — same source template always produces the same
bytes, so there is nothing to hash or diff.

```bash
python skill/scripts/generate_adapters.py --list                     # see every available target
python skill/scripts/generate_adapters.py all <project-root>          # generate every target at once
python skill/scripts/generate_adapters.py cursor <project-root>       # or just one
python skill/scripts/generate_adapters.py all <project-root> --force  # overwrite files that already exist
```

Or, once `pip install -e .` is done, the same thing via the CLI: `aidd adapters list` /
`aidd adapters generate <target|all> [project-root] [--force]`.

Claude Code, OpenCode, and Codex are **not** in this generator, on purpose: Claude Code's skill
format and OpenCode's SKILL.md auto-trigger on matching request language, which is a stronger
mechanism than an explicit per-command slash file has to offer, and Codex has no verified native
command-file surface — see their own tiers above. Adding a sixth or seventh target later (Trae,
Kilocode, Qwen, ...) is one new entry in `adapter_targets.py`, not a new integration module.

## Plan adherence on hosts with no write hook (spec 012)

opencode 2.x (2.0.32, measured 2026-10-20/21) has no `tool.execute.before/after` hook: its plugin
context exposes agent, aisdk, catalog, command, integration, plugin, reference and skill hooks, and
the string `tool.execute` is absent from the binary. The plugin therefore loads (default export
`{ id, server, setup }`) but cannot block a write there, and `rule_gate` never runs. On 2.x the
enforcement is the git guard below. opencode 1.x keeps the plugin gate (Tier 3).

- `aidd next [spec_dir] [--write]` prints, with no LLM and in at most 30 lines, the gate-target spec,
  its current step, the open rule violations with their fix, whether `Approved:` is valid, the last
  `aidd verify` result and one next command. With no open spec it says so and names `aidd search`.
  `--write` stores the same text in `.aidd/NEXT.md`; `CORE.md` and the Antigravity rule tell the agent
  to run `aidd next` before each step.
- `aidd guard commit` reads the staged files, ignores documentation and `specs/`, and when a code
  file is staged it blocks (exit 1, message with the rule and the fix) on: R6 (the gate-target spec
  has no valid approval); R5 (`tasks.md`/`plan.md` out of chain order); a failed or stale
  `aidd verify` for the staged code; a FAIL row in `qa-audit.md`. A commit of only docs/`specs/` files
  always passes. It never blocks on R4, R7, R10, R11 or R12. With no open spec it passes with one
  warning.
- `aidd guard push` never blocks: it prints the same findings as warnings and exits 0.
- `aidd install --githooks [project]` (also `aidd install --host opencode|antigravity --githooks`)
  writes `pre-commit` and `pre-push` hooks that call `aidd guard`. It is idempotent, appends to a
  foreign hook instead of replacing it, refuses a hooks directory that is a link, and fails open
  (the commit proceeds) when `aidd` is not on PATH.
- `AIDD_GUARD=warn|off` turns blocks into warnings or disables the guard. Owner-only: set it in the
  environment that launches the commit, not from the agent. Each use is recorded as `guard_override`
  and shown by `aidd status`.

Known limits:
- `git commit --no-verify` bypasses the guard. `aidd status` lists commits whose staged code had no
  valid approval.
- A foreign hook that exits early never reaches the aidd block appended after it.

## Install into a new project

```bash
aidd install --host gemini   "<project>"   # .aidd/ + GEMINI.md + BeforeTool/AfterTool hooks
aidd install --host opencode "<project>"   # .aidd/ + OpenCode skill + plugin + opencode.json entry
aidd install --host antigravity "<project>" # .aidd/ + .agents/{skills,rules,hooks.json}
aidd doctor --host gemini|opencode|antigravity --root "<project>"   # PASS/FAIL per check, with the exact fix
cat AGENTS.md.snippet >> "<project>/AGENTS.md"   # Codex etc.; create AGENTS.md first if needed
python ../skill/scripts/generate_adapters.py all "<project>"   # Gemini CLI, Cursor, Windsurf, Cline, Copilot commands
```

`aidd install` is non-destructive: identical files are `unchanged`, missing ones `written`,
modified ones `skipped` unless `--force`; it never touches `.aidd/memory/`, `.aidd/evidence/`,
`gate_spec` or `active_spec`, and merges the host JSON by key. Add `--json` for machine output.
`aidd doctor` exits 1 when a blocking check fails.

Keep `.aidd/AIDD.md` as the single edited copy of the methodology across every project and tool —
every adapter above points at it rather than repeating it, specifically so nothing drifts out of
sync between tools.
