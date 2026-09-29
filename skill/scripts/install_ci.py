#!/usr/bin/env python3
"""
aidd CI installer — copies one of skill/templates/ci/*.yml into a project's
conventional CI path.

This is opt-in, on purpose: unlike `aidd init` (which just copies a local
methodology bundle a project already asked for), installing a CI file adds
*shared, always-on* state — a workflow that will run on every teammate's PR
the moment it lands on the default branch. That's a decision a project
should make explicitly, one command at a time; nothing in AIDD writes this
file on its own, and no other command chains into calling this one for you.

Mirrors skill/scripts/generate_adapters.py's shape deliberately (same
--list, same positional-args-plus-flag CLI, same exit codes) — this is the
same kind of idempotent-overwrite copy, just one file instead of eight
per-target renders:

Usage:
    python install_ci.py --list
    python install_ci.py <github|azure-devops> [project-root] [--force]

Targets:
    github        -> <project-root>/.github/workflows/aidd.yml
    azure-devops  -> <project-root>/azure-pipelines-aidd.yml

    azure-devops installs as azure-pipelines-aidd.yml, deliberately NOT
    azure-pipelines.yml — a project may already have its own
    azure-pipelines.yml for other build/release purposes, and this file is
    meant to be wired up as its own, separate pipeline definition in Azure
    DevOps (Pipelines -> New pipeline -> pick this file) rather than
    silently overwriting whatever that project's existing top-level
    pipeline already does.

Exit code 0 = done (file written, or already existed and --force wasn't
passed — that is a skip, not an error). Exit code 2 = usage error or
unknown target.
"""
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "ci"

# id -> (source template filename, destination path relative to project root)
TARGETS = {
    "github": (
        "github-actions-aidd.yml",
        Path(".github") / "workflows" / "aidd.yml",
    ),
    "azure-devops": (
        "azure-pipelines-aidd.yml",
        Path("azure-pipelines-aidd.yml"),
    ),
}


def install(target_key: str, project_root: Path, force: bool = False) -> Path | None:
    """Copy one CI template into project_root at its conventional path.
    Returns the destination Path if written, or None if it already existed
    and force=False (the skip is reported to stderr, same as
    generate_adapters.generate() does for an existing rendered command)."""
    template_name, rel_dest = TARGETS[target_key]
    src = _TEMPLATES_DIR / template_name
    dest = project_root / rel_dest

    if dest.exists() and not force:
        print(f"skip (exists): {dest}", file=sys.stderr)
        return None

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if args else 2)

    if args[0] == "--list":
        print("Available CI targets:")
        for key, (template_name, rel_dest) in TARGETS.items():
            print(f"  {key:14s} {template_name:28s} -> {rel_dest}")
        sys.exit(0)

    force = "--force" in args
    positional = [a for a in args if a != "--force"]
    target_arg = positional[0]
    project_root = Path(positional[1]) if len(positional) > 1 else Path.cwd()

    if target_arg not in TARGETS:
        available = ", ".join(TARGETS)
        print(f"Unknown target {target_arg!r}. Available: {available}.", file=sys.stderr)
        sys.exit(2)

    if not project_root.is_dir():
        print(f"Not a directory: {project_root}", file=sys.stderr)
        sys.exit(2)

    written = install(target_arg, project_root, force=force)
    if written is not None:
        print(f"wrote {written}")
        print("This runs on every PR from now on — commit it deliberately, "
              "and add any required secrets (GITHUB_TOKEN is automatic; "
              "AZURE_DEVOPS_EXT_PAT is not).")

    sys.exit(0)


if __name__ == "__main__":
    main()
