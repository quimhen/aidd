# AIDD — cross-agent adapters

Everything here makes AIDD's methodology work identically across Claude Code, OpenCode, Codex,
Gemini CLI/Antigravity, and any other agent tool that can run a shell command — without
duplicating the pipeline per tool. One core, several thin pointers.

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
only the instructional layer (which is the important part) is covered here, not a hard gate.

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

## Install into a new project

```bash
cp -r dot-aidd "<project>/.aidd"
cat AGENTS.md.snippet >> "<project>/AGENTS.md"   # create AGENTS.md first if it doesn't exist
cp GEMINI.md "<project>/GEMINI.md"
mkdir -p "<project>/.opencode/skills/aidd" "<project>/.opencode/plugins"
cp opencode/skills/aidd/SKILL.md "<project>/.opencode/skills/aidd/SKILL.md"
cp opencode/plugins/aidd.js "<project>/.opencode/plugins/aidd.js"
# then add ".opencode/plugins/aidd.js" to .opencode/opencode.json's "plugin" array by hand
```

Keep `.aidd/AIDD.md` as the single edited copy of the methodology across every project and tool —
every adapter above points at it rather than repeating it, specifically so nothing drifts out of
sync between tools.
