"""aidd adapter target registry — one small data table, not one Python class
per agent.

This is the optimization over spec-kit's mechanism: spec-kit gets the same
result (a native slash-command file per agent, rendered from one shared
template) through a 3-level class hierarchy (``IntegrationBase`` ->
``MarkdownIntegration``/``TomlIntegration``/``YamlIntegration`` -> ~35
per-agent subclasses), plus an install manifest with content hashing,
upgrade/teardown lifecycle, and per-agent native-event injection — machinery
built for a package-manager-scale surface (extensions, presets, bundles,
community catalogs) that a curated, single-methodology skill has no use for.

What AIDD actually needs from that mechanism is just: for each agent tool,
know (a) where its native command files live, (b) what format they're in,
(c) what its argument placeholder looks like, and (d) how it phrases "run
this AIDD step" given whether it has an invokable-skill concept or not.
That's four fields. One dict per target, no subclassing, no install
manifest — regenerating is idempotent (same source -> same bytes), so there
is nothing to hash or reconcile.

Every entry:
    name            display name, used in generated messages only
    dir             install directory, relative to a project root
    format          "markdown" | "toml" — picks the renderer in
                    generate_adapters.py
    filename        destination filename pattern; "{stem}" is the source
                    command's stem (e.g. "scope" from "aidd-scope.md")
    arg_placeholder replaces the source template's literal "$ARGUMENTS"
    invoke_phrase   replaces the source template's literal
                    "Invoke the `aidd` skill and run" — every target here
                    has no first-class invokable-skill concept the way
                    Claude Code/OpenCode do, so it's pointed at
                    .aidd/AIDD.md directly instead of asked to "invoke a
                    skill" that doesn't exist for it
    frontmatter_extra  optional extra frontmatter keys this agent's command
                       format requires beyond "description" (e.g. Copilot's
                       "mode: agent")

Claude Code, OpenCode, and Codex are deliberately not in this table: Claude
Code's skill format and OpenCode's SKILL.md are richer than a per-command
file (the whole methodology auto-triggers on matching language, not just on
an explicit slash command), and Codex has no verified native command-file
surface — all three already have their own tier in adapters/README.md and
gain nothing from this generic per-command renderer. This registry is for
agents whose real, documented mechanism *is* "drop a markdown/TOML file
with a description + prompt body in a specific folder" — the same shape
spec-kit targets with its Markdown/Toml integration classes.
"""

_POINTER_PHRASE = (
    "Read `.aidd/AIDD.md` in full (if you haven't already this session), then run"
)

TARGETS: dict[str, dict] = {
    "gemini": {
        "name": "Gemini CLI",
        "dir": ".gemini/commands",
        "format": "toml",
        "filename": "aidd-{stem}.toml",
        "arg_placeholder": "{{args}}",
        "invoke_phrase": _POINTER_PHRASE,
    },
    "cursor": {
        "name": "Cursor",
        "dir": ".cursor/commands",
        "format": "markdown",
        "filename": "aidd-{stem}.md",
        "arg_placeholder": "$ARGUMENTS",
        "invoke_phrase": _POINTER_PHRASE,
    },
    "windsurf": {
        "name": "Windsurf",
        "dir": ".windsurf/workflows",
        "format": "markdown",
        "filename": "aidd-{stem}.md",
        "arg_placeholder": "$ARGUMENTS",
        "invoke_phrase": _POINTER_PHRASE,
    },
    "cline": {
        "name": "Cline",
        "dir": ".clinerules/workflows",
        "format": "markdown",
        "filename": "aidd-{stem}.md",
        "arg_placeholder": "$ARGUMENTS",
        "invoke_phrase": _POINTER_PHRASE,
    },
    "copilot": {
        "name": "GitHub Copilot",
        "dir": ".github/prompts",
        "format": "markdown",
        "filename": "aidd-{stem}.prompt.md",
        "arg_placeholder": "${input}",
        "invoke_phrase": _POINTER_PHRASE,
        # Copilot prompt files use "mode: agent" in frontmatter to run with
        # full tool access instead of chat-only; every AIDD step needs that.
        "frontmatter_extra": {"mode": "agent"},
    },
}
