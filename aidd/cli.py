"""aidd — command-line entry point.

A thin dispatcher, not a reimplementation: every subcommand shells out to the
matching stdlib-only script under skill/scripts/, the same scripts the
Claude Code skill's hooks call. One implementation, two distribution
channels (this CLI for a human at a terminal or CI; the skill's hooks for an
AI agent) — never two copies of the logic to keep in sync.
"""
import argparse
import subprocess
import sys
from pathlib import Path


def _find_scripts_dir() -> Path:
    """Locate skill/scripts/ relative to this file. Works for an editable
    install (`pip install -e .`, source layout preserved) and for running
    straight from a repo checkout. A non-editable wheel install would need
    skill/ bundled as package data at the same relative position — until
    this is published that way, this lookup is the one source of truth."""
    here = Path(__file__).resolve()
    candidate = here.parent.parent / "skill" / "scripts"
    if candidate.is_dir():
        return candidate
    raise SystemExit(
        "Could not locate skill/scripts/ relative to the installed aidd package "
        f"(looked at {candidate}). If you're running from a wheel install rather "
        "than a repo checkout or `pip install -e .`, this lookup doesn't support "
        "that yet — see aidd/cli.py's _find_scripts_dir()."
    )


def _run(script_name: str, args: list, cwd: Path = None) -> int:
    scripts_dir = _find_scripts_dir()
    result = subprocess.run(
        [sys.executable, str(scripts_dir / script_name), *args],
        cwd=str(cwd) if cwd else None,
    )
    return result.returncode


def cmd_search(args):
    return _run("find_spec.py", args.query)


def cmd_tree(args):
    return _run("find_spec.py", ["--tree", args.spec_id])


def cmd_list(args):
    return _run("find_spec.py", ["--list"])


def cmd_reindex(args):
    return _run("find_spec.py", ["--reindex"])


def cmd_check(args):
    return _run("check_spec.py", [args.spec_dir])


def cmd_check_charter(args):
    return _run("check_charter.py", [args.root] if args.root else [])


def cmd_tasks_to_issues(args):
    # Every provider-specific flag (--provider, --repo, --org, --project,
    # --work-item-type, --workspace, --repo-slug) is forwarded verbatim via
    # `provider_args` (argparse.REMAINDER below) instead of re-declared here
    # one by one — tasks_to_issues.py's own argparse is the single source of
    # truth for what a provider accepts; this CLI never re-lists it and so
    # can't drift out of sync with it the way the old --repo-only version did.
    return _run("tasks_to_issues.py", [args.tasks_md, *args.provider_args])


def cmd_init(args):
    """Copy the tool-agnostic .aidd/ bundle (methodology + templates +
    scripts, no Claude-specific pieces) into a target project. This is
    exactly what adapters/README.md's manual `cp -r dot-aidd <project>/.aidd`
    step does — automated, so it's one command instead of a copy-paste."""
    import shutil

    repo_root = Path(__file__).resolve().parent.parent
    source = repo_root / "adapters" / "dot-aidd"
    if not source.is_dir():
        print(f"Could not find the .aidd bundle to install (looked at {source}).", file=sys.stderr)
        return 2

    target = Path(args.target).resolve() / ".aidd"
    if target.exists() and not args.force:
        print(f"{target} already exists — pass --force to overwrite, or remove it first.", file=sys.stderr)
        return 1

    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))
    print(f"Installed AIDD's methodology + scripts to {target}")
    print("Next: add AGENTS.md's AIDD section (see adapters/AGENTS.md.snippet) so your")
    print("agent tool actually reads it — `aidd init` alone doesn't wire that up.")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="aidd",
        description="AIDD — a methodology for working with AI coding agents.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Install the .aidd/ bundle into a project")
    p_init.add_argument("target", nargs="?", default=".", help="Target project directory (default: cwd)")
    p_init.add_argument("--force", action="store_true", help="Overwrite an existing .aidd/")
    p_init.set_defaults(func=cmd_init)

    p_search = sub.add_parser("search", help="Search the spec graph before creating something new")
    p_search.add_argument("query", nargs="+", help="Keywords or a SCREEN-XX/CTL-nnn/COMP-nnn/API-nnn code")
    p_search.set_defaults(func=cmd_search)

    p_tree = sub.add_parser("tree", help="Print one spec's use-case -> screen -> component -> control -> API graph")
    p_tree.add_argument("spec_id")
    p_tree.set_defaults(func=cmd_tree)

    p_list = sub.add_parser("list", help="List every spec from the index")
    p_list.set_defaults(func=cmd_list)

    p_reindex = sub.add_parser("reindex", help="Force a full rebuild of specs/index.toon")
    p_reindex.set_defaults(func=cmd_reindex)

    p_check = sub.add_parser("check", help="Run the mechanical gap-checker on one spec folder")
    p_check.add_argument("spec_dir")
    p_check.set_defaults(func=cmd_check)

    p_cc = sub.add_parser("check-charter", help="Run charter.md's checkable rules")
    p_cc.add_argument("root", nargs="?", default=None, help="Project root (default: cwd)")
    p_cc.set_defaults(func=cmd_check_charter)

    p_t2i = sub.add_parser(
        "tasks-to-issues",
        help="Turn an approved tasks.md into real issues (GitHub, Azure DevOps, or Bitbucket)",
        description="Provider-specific flags (--provider, --repo, --org, --project, "
                    "--work-item-type, --workspace, --repo-slug, --apply) are forwarded as-is — "
                    "run 'python skill/scripts/tasks_to_issues.py --help' for the full list.",
    )
    p_t2i.add_argument("tasks_md")
    p_t2i.add_argument("provider_args", nargs=argparse.REMAINDER,
                        help="Forwarded verbatim to tasks_to_issues.py, e.g. --provider azure_devops --org ... --apply")
    p_t2i.set_defaults(func=cmd_tasks_to_issues)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
