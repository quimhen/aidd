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
- **Has a constitution that's actually checked.** Project-wide rules split into judgment calls
  (prose) and checkable ones (a pattern + glob table `check_constitution.py` runs for real) — not
  a principles doc trusted to memory.
- **Syncs to GitHub, not just markdown.** An approved `tasks.md` becomes real, trackable GitHub
  issues via `tasks_to_issues.py` — dry-run by default, never duplicates on re-run.

## What's in this repo

- **`skill/`** — the Claude Code skill: `SKILL.md`, enforcement hooks (`hooks/`), and every
  script/template (`scripts/`, `templates/`). `skill/AIDD.md` is the tool-agnostic methodology
  core every other adapter — including this repo's own CLI — points back to.
- **`aidd/`** — the CLI (`pip install -e .` → the `aidd` command): a thin dispatcher over
  `skill/scripts/`, for a human at a terminal or a CI job, no AI agent required.
- **`commands/`** — the eight `/aidd-*` pipeline-stage commands for Claude Code.
- **`adapters/`** — drop-in adapters for other agent tools (OpenCode skill + plugin, an
  `AGENTS.md` snippet for Codex and others, a `GEMINI.md` pointer) plus `dot-aidd/`, the portable
  `.aidd/` bundle (methodology + scripts + templates, no Claude-specific pieces) any project
  installs once and every adapter reads from. See `adapters/README.md` for the install steps.
- **`tests/`** — the stdlib `unittest` suite (zero dependencies, `python -m unittest discover -s
  tests`), run on every push/PR by `.github/workflows/test.yml`.

## Install (Claude Code)

```bash
cp -r skill ~/.claude/skills/aidd
python ~/.claude/skills/aidd/scripts/install_hooks.py
```

## Install (the CLI — for a terminal or CI, no AI agent needed)

```bash
git clone https://github.com/quimhen/aidd.git && cd aidd
pip install -e .
aidd init /path/to/your/project   # installs the .aidd/ bundle there
aidd search "login"               # search the spec graph
aidd check specs/001-login/       # mechanical gap-check
aidd check-constitution .         # run constitution.md's checkable rules
aidd tasks-to-issues specs/001-login/tasks.md --apply   # sync tasks to GitHub Issues
```

Not yet published to PyPI — install from a clone for now.

## Install (other tools)

See `adapters/README.md`.

## Documentation

- [**Why AIDD**](docs/WHY-AIDD.md) — what changes for you, in plain language, with the measured
  numbers.
- [**Pipeline reference**](docs/PIPELINE.md) — the full technical breakdown: the code system, the
  spec graph, every step, the enforcement hooks.
- [**FAQ**](docs/FAQ.md) — common questions. Have one that's not there? Open an
  [issue](../../issues) or a [discussion](../../discussions).
- [**Consulting**](docs/CONSULTING.md) — if your team wants help adopting AIDD.

## Status

Early — the core pipeline, the search/graph tools, the constitution checker, the GitHub-issues
sync, and the Claude Code hooks (including the independent-audit gate) are built, tested (53
stdlib `unittest` cases, run in CI), and have been run against a real production codebase. The
OpenCode, Codex, and Gemini CLI adapters exist and follow the same methodology; only the Claude
Code hooks currently give it technical teeth. Not yet published to PyPI. Deliberately no
multi-agent plugin marketplace — AIDD's adapters are curated, not a community catalog other
projects add to without review.

## License

MIT — see [LICENSE](LICENSE).
