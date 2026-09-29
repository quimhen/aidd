# AIDD — AI-Driven Development

[![PyPI](https://img.shields.io/pypi/v/aidd-cli.svg)](https://pypi.org/project/aidd-cli/)
[![Sponsor](https://img.shields.io/badge/sponsor-%E2%9D%A4-db61a2)](https://github.com/sponsors/quimhen)

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
  relearning the process when the assistant changes. For Claude Code, OpenCode, and Codex, that's
  a native skill/AGENTS.md pointer; for Gemini CLI, Cursor, Windsurf, Cline, and GitHub Copilot,
  `generate_adapters.py` renders each one's own native command-file format straight from
  `commands/aidd-*.md` — one source, no per-agent copy to keep in sync. Both the issue-tracker
  providers and these adapter targets are auto-discovered extensions (see
  [`docs/EXTENDING.md`](docs/EXTENDING.md)), so a project can add its own without forking this repo.
- **Has a charter that's actually checked.** Project-wide rules split into judgment calls
  (prose) and checkable ones (a pattern + glob table `check_charter.py` runs for real) — not
  a principles doc trusted to memory. Run against a real production project, it caught two
  stale claims in that project's own hand-written notes about specific libraries being unused
  (both false, verified in seconds) and a third that turned out far worse than self-rated
  (340 real violations of a rule logged as low-severity).
- **Verifies its own map before planning against it.** The spec graph is parsed mechanically
  (fast, cheap), which also means it can misparse a renamed code or a stale relationship — so a
  rebuild dispatches an independent Graph Coherence Auditor before `plan.md`/`tasks.md` build on
  the new edges. Enforced by a hook pair, not a step an agent could skip under time pressure.
- **Syncs to GitHub, Azure DevOps, or Bitbucket — not just markdown.** An approved `tasks.md`
  becomes real, trackable issues via `tasks_to_issues.py --provider {github,azure_devops,
  bitbucket}` — dry-run by default, never duplicates on re-run. It stays in sync from there:
  `aidd tracker sync` diffs (or writes, with `--apply`) `tasks.md`'s Status column against live
  tracker status, and `aidd tracker link-pr` attaches an opened PR's URL back to its task's
  tracker issue and `tasks.md` row. CI templates for both trackers ship under
  `skill/templates/ci/`, installed with `aidd ci install {github,azure-devops}`.
- **Has a package-install mechanism, kept to the load-bearing parts — not yet a third-party
  ecosystem.** `catalog/` is the marketplace *mechanism*: packages (templates, agent adapters,
  issue-tracker providers, hooks) install into *your* project with `aidd marketplace install
  <id>`, content-hashed so `remove` never discards a file you hand-edited since. A
  `provider`/`adapter`/`hook` package lands under `.aidd/extensions/<id>/` and is
  auto-discovered from there — no code change to this repo needed to use it. Structural
  validation runs in CI on every submission; a maintainer still reviews and merges each one by
  hand — see `catalog/README.md`. Today that catalog holds exactly one package, first-party
  (`hotfix-report`); zero third-party submissions have been merged yet — the mechanism is built
  and tested, the ecosystem it's built for doesn't exist yet. Manage what's discovered
  (first-party or project-local) with `aidd extensions list|info <id>|enable <id>|disable <id>`
  — see [`docs/EXTENDING.md`](docs/EXTENDING.md).

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
- **`catalog/`** — the marketplace mechanism: `schema.json`, two registries (`catalog.json`
  first-party, currently one package; `catalog.community.json` third-party, currently empty),
  and `packages/<id>/` folders. Installed/searched via `skill/scripts/marketplace.py` (or `aidd
  marketplace ...`), validated in CI by `skill/scripts/validate_catalog_entry.py`. See
  `catalog/README.md` and `catalog/CONTRIBUTING.md`.
- **`tests/`** — the stdlib `unittest` suite (zero dependencies, `python -m unittest discover -s
  tests`), run on every push/PR by `.github/workflows/test.yml` (and `catalog-validate.yml` for
  anything touching `catalog/`).

## Install (Claude Code)

```bash
cp -r skill ~/.claude/skills/aidd
python ~/.claude/skills/aidd/scripts/install_hooks.py
```

## Install (the CLI — for a terminal or CI, no AI agent needed)

```bash
pip install aidd-cli
aidd init /path/to/your/project   # installs the .aidd/ bundle there
aidd search "login"               # search the spec graph
aidd check specs/001-login/       # mechanical gap-check
aidd check-charter .         # run charter.md's checkable rules
aidd tasks-to-issues specs/001-login/tasks.md --apply   # sync tasks (github by default)
aidd tasks-to-issues specs/001-login/tasks.md --provider azure_devops --org ... --project ... --apply
aidd adapters generate all /path/to/your/project   # native commands for Gemini CLI, Cursor, Windsurf, Cline, Copilot
aidd marketplace list                              # browse installable third-party packages
aidd marketplace install hotfix-report /path/to/your/project
aidd extensions list                               # discovered provider/adapter/hook extensions
aidd tracker sync specs/001-login/tasks.md --provider github --repo owner/repo   # dry-run status diff
aidd tracker link-pr specs/001-login/tasks.md --pr-url ... --branch ... --apply
aidd ci install github /path/to/your/project       # install the GitHub Actions CI template
```

Published on PyPI as [`aidd-cli`](https://pypi.org/project/aidd-cli/). To work on AIDD itself
instead of just using it, clone and install in editable mode:

```bash
git clone https://github.com/quimhen/aidd.git && cd aidd
pip install -e .
```

## Install (other tools)

See `adapters/README.md`.

## Documentation

- [**Why AIDD**](docs/WHY-AIDD.md) — what changes for you, in plain language, with the measured
  numbers.
- [**Pipeline reference**](docs/PIPELINE.md) — the full technical breakdown: the code system, the
  spec graph, every step, the enforcement hooks.
- [**FAQ**](docs/FAQ.md) — common questions. Have one that's not there? Open an
  [issue](../../issues) or a [discussion](../../discussions).
- [**Extending AIDD**](docs/EXTENDING.md) — the three extension seams (issue tracker
  providers and multi-agent adapter targets, both auto-discovered from
  `skill/extensions/**/manifest.json` or `.aidd/extensions/**/manifest.json`, plus
  charter checkable rules), and how they relate to the marketplace (`catalog/`).
- [**Consulting**](docs/CONSULTING.md) — if your team wants help adopting AIDD.

## Status

Early — the core pipeline, the search/graph tools, the charter checker, the graph-coherence
gate, the issue-tracker sync (GitHub/Azure DevOps/Bitbucket, plus bidirectional status sync
via `aidd tracker sync` and PR<->task linking via `aidd tracker link-pr`), CI templates and
`aidd ci install`, the Claude Code hooks (nine of them, including the independent-audit and
graph-coherence gates), the multi-agent adapter generator (`generate_adapters.py`, rendering
Gemini CLI/Cursor/Windsurf/Cline/Copilot commands from one source), the real auto-discovery
extension registry (`extension_registry.py`, loading provider/adapter/hook extensions from
`skill/extensions/**/manifest.json` and `.aidd/extensions/**/manifest.json` — see
`docs/EXTENDING.md`), and the marketplace (`catalog/` + `marketplace.py` +
`validate_catalog_entry.py`, one first-party package shipped so far: `hotfix-report`) are built,
tested (stdlib `unittest`, run in CI), and have been run against a real production
codebase. OpenCode, Codex, and the five generated adapter targets follow the same methodology;
only the Claude Code hooks currently give it technical teeth. Published on PyPI as `aidd-cli`.
The marketplace is intentionally not a fully automated accept path: CI validates structure and
flags anything worth a human's attention, but a maintainer reviews and merges every catalog
submission by hand — see `catalog/README.md`.

## Support this project

If AIDD saves your agent sessions real time, [sponsor it on GitHub](https://github.com/sponsors/quimhen)
— it funds the time spent maintaining the pipeline, the hooks, and the multi-agent adapters.

## License

MIT — see [LICENSE](LICENSE).
