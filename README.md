# AIDD — AI-Driven Development

A methodology for working with AI coding agents — Claude Code, OpenCode, Codex, Gemini CLI, and
others — that makes "search before creating," "align before planning," and "never let the
implementer grade its own work" the default, not something you have to remember.

## What's in this repo

- **`skill/`** — the Claude Code skill: `SKILL.md`, enforcement hooks (`hooks/`), the search/graph
  tools (`scripts/find_spec.py`, `scripts/check_spec.py`), and every artifact template
  (`templates/`). `skill/AIDD.md` is the tool-agnostic methodology core every other adapter points
  back to.
- **`commands/`** — the eight `/aidd-*` pipeline-stage commands for Claude Code.
- **`adapters/`** — drop-in adapters for other agent tools (OpenCode skill + plugin, an
  `AGENTS.md` snippet for Codex and others, a `GEMINI.md` pointer) plus `dot-aidd/`, the portable
  `.aidd/` bundle (methodology + scripts + templates, no Claude-specific pieces) any project
  installs once and every adapter reads from. See `adapters/README.md` for the install steps.

## Install (Claude Code)

```bash
cp -r skill ~/.claude/skills/aidd
python ~/.claude/skills/aidd/scripts/install_hooks.py
```

## Install (other tools)

See `adapters/README.md`.
