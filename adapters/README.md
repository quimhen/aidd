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
Copy `GEMINI.md` as-is to the project root — it just points at `AGENTS.md`. **Not independently
verified this session** — Antigravity's exact plugin/hook system wasn't available to inspect, so
only the instructional layer (which is the important part) is covered here, not a hard gate. This
is the always-read context layer; Tier 5 below additionally gives Gemini CLI real per-step native
slash commands (`.gemini/commands/aidd-*.toml`) — the two are complementary, not a replacement of
one by the other.

**Tier 3 — OpenCode:** OpenCode has its own native skill format (confirmed identical in shape to
Claude Code's: YAML frontmatter + markdown body) and a plugin system with at least one confirmed
hook point (`tool.execute.before`).
- Copy `opencode/skills/aidd/SKILL.md` to `<project>/.opencode/skills/aidd/SKILL.md`.
- Copy `opencode/plugins/aidd.js` to `<project>/.opencode/plugins/aidd.js`, and add
  `".opencode/plugins/aidd.js"` to the `"plugin"` array in `.opencode/opencode.json`.
- This plugin can only **nudge** before a `bash` tool call (the one hook point this was verified
  against, via this project's existing `graphify.js` plugin) — OpenCode's plugin API doesn't
  expose a distinct "user prompt submitted" event or a per-tool-name write/edit gate the way
  Claude Code's hook system does, so it cannot hard-block a write the way
  `hooks/require_aidd.py` does for Claude Code. `AGENTS.md`/the OpenCode skill remain the
  primary instruction layer; this plugin is enforcement on top where it can reach.

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

## Install into a new project

```bash
cp -r dot-aidd "<project>/.aidd"
cat AGENTS.md.snippet >> "<project>/AGENTS.md"   # create AGENTS.md first if it doesn't exist
cp GEMINI.md "<project>/GEMINI.md"
mkdir -p "<project>/.opencode/skills/aidd" "<project>/.opencode/plugins"
cp opencode/skills/aidd/SKILL.md "<project>/.opencode/skills/aidd/SKILL.md"
cp opencode/plugins/aidd.js "<project>/.opencode/plugins/aidd.js"
# then add ".opencode/plugins/aidd.js" to .opencode/opencode.json's "plugin" array by hand
python ../skill/scripts/generate_adapters.py all "<project>"   # Gemini CLI, Cursor, Windsurf, Cline, Copilot commands
```

Keep `.aidd/AIDD.md` as the single edited copy of the methodology across every project and tool —
every adapter above points at it rather than repeating it, specifically so nothing drifts out of
sync between tools.
