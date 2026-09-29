# AIDD — AI-Driven Development

**A methodology for working with AI coding agents**, not another AI coding agent itself. AIDD
makes an agent search before it creates, plan out loud before it builds, and get reviewed by
someone other than itself before a change is called done — automatically, on Claude Code, OpenCode,
Codex, Gemini CLI, and any other tool that can read a markdown file and run a shell command.

## The problem

AI coding agents are fast at writing code and bad at knowing what already exists. Left alone, they
duplicate specs nobody asked for, re-explain a flow in three paragraphs instead of drawing it, ship
a fix that fabricates success instead of actually calling the real backend, and grade their own
homework when asked to review it. AIDD is the set of habits that stops that — enforced by hooks
where the tool allows it, followed as a written discipline everywhere else.

## What it does

- **Searches before creating.** Every request runs against a compact, auto-built graph of every
  existing spec (`specs/index.toon`) before anything new gets created — a match means "amend this,"
  not "start over."
- **Plans out loud.** Ambiguity gets resolved as an explicit question before code is written, not
  discovered after a review.
- **Ships in small, reviewable pieces.** One code, one file, one PR — a wrong pass costs one edit,
  not a rewrite.
- **Never lets the implementer grade its own work.** Step 6's review must come from a separate
  agent dispatch. On Claude Code this is an actual technical gate
  (`hooks/require_independent_audit.py`), not just a rule stated in a doc.
- **Works the same across tools.** One methodology (`skill/AIDD.md`), thin adapters per tool — no
  relearning the process when the assistant changes.

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

## Status

Early — the core pipeline, the search/graph tools, and the Claude Code hooks (including the
independent-audit gate) are built and have been run against a real production codebase. The
OpenCode, Codex, and Gemini CLI adapters exist and follow the same methodology; only the Claude
Code hooks currently give it technical teeth.

## License

MIT — see [LICENSE](LICENSE).
