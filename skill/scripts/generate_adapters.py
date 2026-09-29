#!/usr/bin/env python3
"""
aidd adapter generator — renders the 8 canonical commands/aidd-*.md templates
into each agent tool's own native command format, from one source of truth.

This is AIDD's optimized version of spec-kit's integration mechanism.
spec-kit gets the same output (a native command file per agent, per template)
through a 3-level class hierarchy plus an install manifest with content
hashing, upgrade/teardown, and per-agent event injection — machinery sized
for a package-manager-scale surface (extensions/presets/bundles, community
catalogs). AIDD has none of that surface by design (curated adapters, not a
marketplace — see docs/WHY-AIDD.md), so this keeps only the part of spec-kit's
mechanism that's actually load-bearing: read the template once, substitute a
small fixed set of placeholders, write it out in the target's format. One
function per format, one manifest.json per agent (skill/extensions/adapters/,
discovered via extension_registry.get_adapter_targets()) — no classes, no
install manifest, no per-agent Python file.

Regeneration is idempotent: same source template + same target config always
produces the same bytes, so there's nothing to hash, diff, or reconcile on
upgrade — just overwrite (that's what --force is for; without it, an existing
file is left alone so a hand-edited copy is never clobbered silently).

Usage:
    python generate_adapters.py --list
    python generate_adapters.py <target|all> [project-root] [--force]

Exit code 0 = files written (or nothing to do because they already exist and
--force wasn't passed). Exit code 2 = usage error or unknown target.
"""
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extension_registry  # noqa: E402

_COMMANDS_DIR = Path(__file__).resolve().parent.parent.parent / "commands"
_SKILL_PHRASE = "Invoke the `aidd` skill and run"
_FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---\n\n?(.*)$', re.DOTALL)
_DESCRIPTION_RE = re.compile(r'^description:\s*(.+)$', re.MULTILINE)


def list_source_commands() -> list[Path]:
    """Every commands/aidd-*.md file, sorted — the single source of truth
    every target renders from. Sorted by name, not pipeline step order:
    generation doesn't care about step order, only about being complete."""
    if not _COMMANDS_DIR.is_dir():
        return []
    return sorted(_COMMANDS_DIR.glob("aidd-*.md"))


def parse_source(text: str) -> tuple[str, str]:
    """Split a commands/aidd-*.md file into (description, body).

    The source format is fixed and simple by construction (one
    "description:" line in frontmatter, a body using only "$ARGUMENTS" and
    the literal skill-invocation phrase) — a hand-rolled two-group regex is
    enough; a full YAML parser would be reading more structure than this
    format ever has.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("source command is missing a --- frontmatter block")
    frontmatter, body = m.group(1), m.group(2)
    desc_m = _DESCRIPTION_RE.search(frontmatter)
    if not desc_m:
        raise ValueError("source command's frontmatter has no 'description:' line")
    return desc_m.group(1).strip(), body.rstrip("\n")


def substitute(body: str, target: dict) -> str:
    """Apply the two placeholder substitutions every target needs.

    Both are literal, not regex-driven — the source templates are AIDD's
    own, so the exact literal text is known and stable; a regex here would
    be solving a problem that doesn't exist.
    """
    body = body.replace(_SKILL_PHRASE, target["invoke_phrase"])
    body = body.replace("$ARGUMENTS", target["arg_placeholder"])
    return body


def render_markdown(description: str, body: str, target: dict) -> str:
    """Render target formats that keep a YAML-frontmatter markdown command
    (Cursor, Windsurf, Cline, Copilot) — description line, any
    target-specific extra frontmatter keys, then the body unchanged."""
    lines = ["---", f"description: {description}"]
    for key, value in target.get("frontmatter_extra", {}).items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    lines.append(body)
    lines.append("")
    return "\n".join(lines)


_TRIPLE_QUOTE = '"' * 3


def _toml_string(value: str) -> str:
    """Render *value* as a TOML multiline basic string.

    AIDD's own source templates never contain a triple-double-quote
    sequence or control characters — they're hand-written prose — so the
    one escape that matters in practice is a backslash. Guard the
    unsupported case loudly instead of silently emitting invalid TOML for
    content this project doesn't actually produce.
    """
    if _TRIPLE_QUOTE in value:
        raise ValueError(
            "source content contains a literal triple-double-quote, which "
            "the simple multiline-basic-string renderer here does not support"
        )
    escaped = value.replace("\\", "\\\\")
    return f'"""\n{escaped}\n"""'


def render_toml(description: str, body: str, target: dict) -> str:
    """Render the Gemini CLI TOML command format: description + prompt."""
    del target  # unused — TOML has no extra frontmatter concept
    return (
        f"description = {_toml_string(description)}\n"
        "\n"
        f"prompt = {_toml_string(body)}\n"
    )


_RENDERERS = {
    "markdown": render_markdown,
    "toml": render_toml,
}


def render_command(src: Path, target_key: str, targets: dict) -> tuple[str, str]:
    """Return (destination filename, rendered content) for one source
    command file rendered against one target's config."""
    target = targets[target_key]
    description, raw_body = parse_source(src.read_text(encoding="utf-8"))
    body = substitute(raw_body, target)
    renderer = _RENDERERS[target["format"]]
    content = renderer(description, body, target)
    stem = src.stem.removeprefix("aidd-")
    filename = target["filename"].format(stem=stem)
    return filename, content


def generate(target_key: str, project_root: Path, targets: dict, force: bool = False) -> list[Path]:
    """Render every source command for one target into project_root.
    Returns the list of files actually written (skips existing files unless
    force=True, and reports which ones were skipped via stderr)."""
    target = targets[target_key]
    dest_dir = project_root / target["dir"]
    written: list[Path] = []
    for src in list_source_commands():
        filename, content = render_command(src, target_key, targets)
        dest = dest_dir / filename
        if dest.exists() and not force:
            print(f"skip (exists): {dest}", file=sys.stderr)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        written.append(dest)
    return written


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if args else 2)

    if args[0] == "--list":
        # --list has no project-root positional arg of its own (it's a pure
        # info dump), so it discovers against Path.cwd() — the same default
        # generate() below uses when no project-root is given on the CLI.
        targets = extension_registry.get_adapter_targets(Path.cwd())
        print(f"{len(list_source_commands())} source command(s) in {_COMMANDS_DIR}")
        print("\nAvailable targets:")
        for key, cfg in targets.items():
            print(f"  {key:10s} {cfg['name']:20s} -> {cfg['dir']}/ ({cfg['format']})")
        sys.exit(0)

    force = "--force" in args
    positional = [a for a in args if a != "--force"]
    target_arg = positional[0]
    project_root = Path(positional[1]) if len(positional) > 1 else Path.cwd()

    if not project_root.is_dir():
        print(f"Not a directory: {project_root}", file=sys.stderr)
        sys.exit(2)

    # Discovery must use THIS project's root, not a fixed one — a project
    # can define its own custom adapter target in its own .aidd/extensions/.
    targets = extension_registry.get_adapter_targets(project_root)

    if target_arg == "all":
        keys = list(targets)
    elif target_arg in targets:
        keys = [target_arg]
    else:
        available = ", ".join(targets)
        print(f"Unknown target {target_arg!r}. Available: {available}, or 'all'.", file=sys.stderr)
        sys.exit(2)

    total_written = 0
    for key in keys:
        written = generate(key, project_root, targets, force=force)
        total_written += len(written)
        for f in written:
            print(f"wrote {f}")

    print(f"\n{total_written} file(s) written across {len(keys)} target(s).")
    sys.exit(0)


if __name__ == "__main__":
    main()
