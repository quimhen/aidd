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


def cmd_flow(args):
    extra = [args.flow_file]
    for flag, on in (("--check", args.check), ("--pseudo", args.pseudo), ("--mermaid", args.mermaid), ("--open", args.open)):
        if on:
            extra.append(flag)
    if args.output:
        extra += ["-o", args.output]
    if args.spec_dir:
        extra += ["--spec-dir", args.spec_dir]
    return _run("flowmap.py", extra)


def cmd_mem(args):
    # Everything after `aidd mem` is forwarded verbatim to aidd_memory.py
    # (add / search / show / timeline / file / inject / compact / stats /
    # import-claude-mem), so the CLI and the skill share one implementation.
    return _run("aidd_memory.py", args.mem_args)


def cmd_status(args):
    # Pure passthrough to aidd_status.py (`status [spec_dir] [--json]`).
    return _run("aidd_status.py", ["status", *args.status_args])


def cmd_progress(args):
    out = list(args.spec_dirs)
    if args.root:
        out += ["--root", args.root]
    out += [f for f, on in (("--json", args.json), ("--detail", args.detail), ("--no-write", args.no_write),
                            ("--quiet", args.quiet)) if on]
    return _run("aidd_progress.py", out)


def cmd_pending(args):
    # Passthrough to aidd_pending.py (`<spec_dir|tasks.md> [--root DIR] [--json]`).
    return _run("aidd_pending.py", args.pending_args)


def cmd_calibrate(args):
    # Passthrough to aidd_calibrate.py (`record <spec_dir>`).
    return _run("aidd_calibrate.py", [args.action, args.spec_dir])


def cmd_rules(args):
    # Pure passthrough to aidd_status.py (`rules check|approve|close|abandon <spec>`).
    return _run("aidd_status.py", ["rules", *args.rules_args])


def cmd_review(args):
    # aidd:FR-202 aidd:FR-203 aidd:FR-303 aidd:FR-309 aidd:FR-313 — passthrough to aidd_review.py
    # (`<spec_dir> [--open] [--check] [--wait] [--comments] [--summary] [--full] [--timeout S]
    # [--interval S]`); aidd_review.py owns the parsing.
    return _run("aidd_review.py", [args.spec_dir, *args.review_flags])


def cmd_verify(args):
    # aidd:FR-205 — passthrough to aidd_status.py (`verify <spec>`); main() short-circuits it.
    return _run("aidd_status.py", ["verify", *args.verify_args])


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


def cmd_marketplace_list(args):
    return _run("marketplace.py", ["list"])


def cmd_marketplace_search(args):
    return _run("marketplace.py", ["search", args.query])


def cmd_marketplace_install(args):
    mp_args = ["install", args.package_id, args.project_root]
    if args.force:
        mp_args.append("--force")
    return _run("marketplace.py", mp_args)


def cmd_marketplace_remove(args):
    mp_args = ["remove", args.package_id, args.project_root]
    if args.force:
        mp_args.append("--force")
    return _run("marketplace.py", mp_args)


def cmd_adapters_list(args):
    return _run("generate_adapters.py", ["--list"])


def cmd_adapters_generate(args):
    generate_args = [args.target, args.project_root]
    if args.force:
        generate_args.append("--force")
    return _run("generate_adapters.py", generate_args)


def cmd_extensions_list(args):
    return _run("extension_registry.py", ["list"])


def cmd_extensions_info(args):
    return _run("extension_registry.py", ["info", args.id])


def cmd_extensions_enable(args):
    return _run("extension_registry.py", ["enable", args.id])


def cmd_extensions_disable(args):
    return _run("extension_registry.py", ["disable", args.id])


def cmd_tracker_sync(args):
    # Same forwarding discipline as cmd_tasks_to_issues: only the positional
    # tasks_md is declared here, every provider-specific flag (--provider,
    # --repo, --org, --project, --work-item-type, --workspace, --repo-slug,
    # --apply) is forwarded verbatim via provider_args (argparse.REMAINDER).
    return _run("sync_issues.py", [args.tasks_md, *args.provider_args])


def cmd_tracker_link_pr(args):
    # tasks_md is a positional here (unlike link_pr_to_task.py's own
    # --tasks-md flag) so it anchors argparse.REMAINDER the same way
    # cmd_tasks_to_issues/cmd_tracker_sync's leading positional does.
    # argparse.REMAINDER only swallows a trailing run of flag-looking
    # tokens (--pr-url, --branch, --task-id, --provider, --apply, ...)
    # when a bare positional value precedes them; a REMAINDER-only
    # subparser with --tasks-md declared as its own leading flag breaks
    # (the first "--task-id"-shaped token after --tasks-md's value gets
    # eaten as an unrecognized optional instead of forwarded — verified
    # empirically). Translating back to --tasks-md here keeps
    # link_pr_to_task.py's own CLI untouched.
    return _run("link_pr_to_task.py", ["--tasks-md", args.tasks_md, *args.link_args])


def cmd_ci_install(args):
    ci_args = [args.target, args.project_root]
    if args.force:
        ci_args.append("--force")
    return _run("install_ci.py", ci_args)


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
    print("For Gemini CLI, Cursor, Windsurf, Cline, or GitHub Copilot, also run:")
    print(f"  aidd adapters generate all {args.target}")
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

    p_flow = sub.add_parser("flow", help="Flowmap: render a visual-flow.toon to an interactive actors x processes flow + pseudocode")
    p_flow.add_argument("flow_file")
    p_flow.add_argument("-o", "--output")
    p_flow.add_argument("--check", action="store_true", help="validate only")
    p_flow.add_argument("--pseudo", action="store_true", help="print generated pseudocode (markdown)")
    p_flow.add_argument("--mermaid", action="store_true", help="print Mermaid (markdown-embed fallback)")
    p_flow.add_argument("--spec-dir", help="cross-check node codes against this spec folder")
    p_flow.add_argument("--open", action="store_true")
    p_flow.set_defaults(func=cmd_flow)

    p_mem = sub.add_parser(
        "mem", help="AIDD Memory: curated, code-anchored decisions/bugfixes/constraints (add, search, show, compact, import-claude-mem)",
        add_help=False)
    p_mem.add_argument("mem_args", nargs=argparse.REMAINDER, help="forwarded to aidd_memory.py (try: aidd mem search <words>)")
    p_mem.set_defaults(func=cmd_mem)

    p_status = sub.add_parser(
        "status", help="Hard-rules ledger of ALL open specs from the evidence log (route, alignment, approval, waves, auditors); --json; --refresh adds git/review/verification facts",
        add_help=False)
    p_status.add_argument("status_args", nargs=argparse.REMAINDER, help="forwarded to aidd_status.py (try: aidd status [spec_dir] --json)")
    p_status.set_defaults(func=cmd_status)

    p_pending = sub.add_parser(
        "pending", help="Script prefilter: which tasks.md tasks still lack their Target file, grouped into lanes (no agents, no tokens)",
        add_help=False)
    p_pending.add_argument("pending_args", nargs=argparse.REMAINDER, help="forwarded to aidd_pending.py (try: aidd pending specs/001-x --json)")
    p_pending.set_defaults(func=cmd_pending)

    p_progress = sub.add_parser(
        "progress", help="Implementation % per spec (target files present / marked aidd:<code>) plus approved/verify/audit/closed stages; no LLM, no third-party graph; writes .aidd/graphs/progress.json",
        add_help=False)
    p_progress.add_help = True
    p_progress.add_argument("spec_dirs", nargs="*", help="spec folders (default: every specs/*/tasks.md)")
    p_progress.add_argument("--root", help="project root (default: current directory)")
    for flag, text in (("--json", "machine-readable summary"), ("--detail", "list missing/stub/not-measurable tasks"),
                       ("--no-write", "do not write .aidd/graphs/progress.json"), ("--quiet", "write the graph, print nothing")):
        p_progress.add_argument(flag, action="store_true", help=text)
    p_progress.set_defaults(func=cmd_progress)

    p_rules = sub.add_parser(
        "rules", help="Hard rules: check <spec_dir> | approve <spec_dir> | close <spec_id> | abandon <spec_id> [--reason TEXT]",
        add_help=False)
    p_rules.add_argument("rules_args", nargs=argparse.REMAINDER, help="forwarded to aidd_status.py (try: aidd rules check specs/001-x)")
    p_rules.set_defaults(func=cmd_rules)

    p_graphs = sub.add_parser(
        "graphs", help="Project graphs registry: list | status | refresh <name|all> | show <name> <query> | explorer <name>",
        add_help=False)
    p_graphs.add_argument("graphs_args", nargs=argparse.REMAINDER, help="forwarded to aidd_graphs.py")
    p_graphs.set_defaults(func=lambda a: _run("aidd_graphs.py", a.graphs_args))

    p_review = sub.add_parser(
        "review", help="aidd review <spec> [--open] [--check] [--wait] [--comments] [--summary] [--full] [--timeout S] [--interval S]: generate specs/<id>/review.html (compact page) or read the approval state")
    p_review.add_argument("spec_dir", help="spec folder, e.g. specs/008-x (first, then the flags)")
    p_review.add_argument("review_flags", nargs=argparse.REMAINDER,
                          help="forwarded to aidd_review.py: --open, --check (ONE status line; exit 0 complete / 2 pending / 3 stale, legacy, too many items), --wait (poll, then ONE status line; exit 0 complete / 2 timeout / 3 cannot help), --comments (<CODE>: <comment> lines), --summary (mechanical summary, writes nothing), --full (long page with heading keys), --timeout S, --interval S")
    p_review.set_defaults(func=cmd_review)

    p_verify = sub.add_parser(
        "verify", help="Run the spec's ## Verification commands and record the evidence (verify <spec>)",
        add_help=False)
    p_verify.add_argument("verify_args", nargs=argparse.REMAINDER, help="forwarded to aidd_status.py verify")
    p_verify.set_defaults(func=cmd_verify)

    p_cal = sub.add_parser(
        "calibrate", help="Record measured minutes/tokens of a closed spec into .aidd/calibration.toon")
    p_cal.add_argument("action", choices=["record"], help="record")
    p_cal.add_argument("spec_dir", help="spec folder, e.g. specs/005-x")
    p_cal.set_defaults(func=cmd_calibrate)

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

    p_adapters = sub.add_parser(
        "adapters",
        help="Generate native command files for other agent tools (Gemini CLI, Cursor, Windsurf, Cline, Copilot)",
        description="Renders commands/aidd-*.md into each agent tool's own native command "
                    "format and directory. Claude Code, OpenCode, and Codex are not covered here — "
                    "see adapters/README.md, they already have a richer native mechanism.",
    )
    adapters_sub = p_adapters.add_subparsers(dest="adapters_command", required=True)

    p_adapters_list = adapters_sub.add_parser("list", help="List available adapter targets")
    p_adapters_list.set_defaults(func=cmd_adapters_list)

    p_adapters_generate = adapters_sub.add_parser(
        "generate", help="Write native command files for one target (or 'all') into a project"
    )
    p_adapters_generate.add_argument("target", help="gemini | cursor | windsurf | cline | copilot | all")
    p_adapters_generate.add_argument("project_root", nargs="?", default=".", help="Target project directory (default: cwd)")
    p_adapters_generate.add_argument("--force", action="store_true", help="Overwrite files that already exist")
    p_adapters_generate.set_defaults(func=cmd_adapters_generate)

    p_marketplace = sub.add_parser(
        "marketplace",
        help="Browse and install third-party packages from catalog/ (providers/adapters/templates/hooks)",
        description="See catalog/README.md for what a package is and how to submit one. All 4 "
                    "kinds (adapter/template/provider/hook) can be listed, searched, and installed — "
                    "an installed provider/hook is auto-discovered from .aidd/extensions/, see "
                    "skill/scripts/extension_registry.py.",
    )
    marketplace_sub = p_marketplace.add_subparsers(dest="marketplace_command", required=True)

    p_mp_list = marketplace_sub.add_parser("list", help="List every package in the catalog")
    p_mp_list.set_defaults(func=cmd_marketplace_list)

    p_mp_search = marketplace_sub.add_parser("search", help="Search the catalog by id/name/description")
    p_mp_search.add_argument("query")
    p_mp_search.set_defaults(func=cmd_marketplace_search)

    p_mp_install = marketplace_sub.add_parser("install", help="Install a package into a project")
    p_mp_install.add_argument("package_id")
    p_mp_install.add_argument("project_root", nargs="?", default=".")
    p_mp_install.add_argument("--force", action="store_true", help="Override a file-conflict refusal")
    p_mp_install.set_defaults(func=cmd_marketplace_install)

    p_mp_remove = marketplace_sub.add_parser("remove", help="Remove an installed package from a project")
    p_mp_remove.add_argument("package_id")
    p_mp_remove.add_argument("project_root", nargs="?", default=".")
    p_mp_remove.add_argument("--force", action="store_true", help="Remove even files modified since install")
    p_mp_remove.set_defaults(func=cmd_marketplace_remove)

    p_extensions = sub.add_parser(
        "extensions",
        help="List, inspect, enable, or disable auto-discovered provider/adapter/hook extensions",
        description="Extensions are discovered from skill/extensions/**/manifest.json (first-party) "
                    "and <project>/.aidd/extensions/**/manifest.json (project-local, including anything "
                    "'aidd marketplace install' put there) — see skill/scripts/extension_registry.py.",
    )
    extensions_sub = p_extensions.add_subparsers(dest="extensions_command", required=True)

    p_ext_list = extensions_sub.add_parser("list", help="List every discovered extension")
    p_ext_list.set_defaults(func=cmd_extensions_list)

    p_ext_info = extensions_sub.add_parser("info", help="Show one extension's manifest")
    p_ext_info.add_argument("id")
    p_ext_info.set_defaults(func=cmd_extensions_info)

    p_ext_enable = extensions_sub.add_parser("enable", help="Enable an extension")
    p_ext_enable.add_argument("id")
    p_ext_enable.set_defaults(func=cmd_extensions_enable)

    p_ext_disable = extensions_sub.add_parser("disable", help="Disable an extension")
    p_ext_disable.add_argument("id")
    p_ext_disable.set_defaults(func=cmd_extensions_disable)

    p_tracker = sub.add_parser(
        "tracker",
        help="Sync tasks.md status from the tracker and link opened PRs to their task's issue",
        description="See skill/scripts/sync_issues.py and skill/scripts/link_pr_to_task.py.",
    )
    tracker_sub = p_tracker.add_subparsers(dest="tracker_command", required=True)

    p_tracker_sync = tracker_sub.add_parser(
        "sync",
        help="Diff (or write, with --apply) tasks.md's Status column against live tracker status",
        description="Provider-specific flags (--provider, --repo, --org, --project, "
                    "--work-item-type, --workspace, --repo-slug, --apply) are forwarded as-is — "
                    "run 'python skill/scripts/sync_issues.py --help' for the full list.",
    )
    p_tracker_sync.add_argument("tasks_md")
    p_tracker_sync.add_argument("provider_args", nargs=argparse.REMAINDER,
                                 help="Forwarded verbatim to sync_issues.py, e.g. --provider azure_devops --org ... --apply")
    p_tracker_sync.set_defaults(func=cmd_tracker_sync)

    p_tracker_link = tracker_sub.add_parser(
        "link-pr",
        help="Attach an opened PR's URL to its task's tracker issue and tasks.md row",
        description="tasks_md is positional here (translated back to link_pr_to_task.py's own "
                    "--tasks-md flag). Every other flag (--pr-url, --branch, --task-id, --provider, "
                    "--apply, and provider-specific flags) is forwarded as-is — run "
                    "'python skill/scripts/link_pr_to_task.py --help' for the full list.",
    )
    p_tracker_link.add_argument("tasks_md", help="Path to a spec's tasks.md")
    p_tracker_link.add_argument("link_args", nargs=argparse.REMAINDER,
                                 help="Forwarded verbatim to link_pr_to_task.py, e.g. --pr-url ... --branch ... --apply")
    p_tracker_link.set_defaults(func=cmd_tracker_link_pr)

    p_ci = sub.add_parser(
        "ci",
        help="Install a CI workflow file (GitHub Actions or Azure Pipelines) for this project",
        description="See skill/scripts/install_ci.py and skill/templates/ci/*.yml. Opt-in and "
                    "explicit, on purpose — nothing else in AIDD writes this file for you.",
    )
    ci_sub = p_ci.add_subparsers(dest="ci_command", required=True)

    p_ci_install = ci_sub.add_parser("install", help="Copy a CI template into this project's conventional CI path")
    p_ci_install.add_argument("target", help="github | azure-devops")
    p_ci_install.add_argument("project_root", nargs="?", default=".", help="Target project directory (default: cwd)")
    p_ci_install.add_argument("--force", action="store_true", help="Overwrite an existing CI file")
    p_ci_install.set_defaults(func=cmd_ci_install)

    return parser


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "mem":
        # `aidd mem ...` is a pure passthrough to aidd_memory.py, so options that
        # come before the subcommand (--root X, --help) work too — argparse's
        # REMAINDER would otherwise choke on a leading option.
        sys.exit(_run("aidd_memory.py", argv[1:]))
    if argv and argv[0] in ("status", "rules", "verify"):
        # Same passthrough for the hard-rules commands (aidd_status.py owns the parsing);
        # `aidd verify <spec>` -> `aidd_status.py verify <spec>` (aidd:FR-205).
        sys.exit(_run("aidd_status.py", argv))
    if argv and argv[0] == "graphs":
        sys.exit(_run("aidd_graphs.py", argv[1:]))
    if argv and argv[0] == "review":
        # aidd:FR-313 — aidd_review.py owns the parsing, so the flags work in any order
        # (`aidd review --summary <spec>` as well as `aidd review <spec> --summary`); the
        # REMAINDER subparser below rejected a leading flag with exit 2 (= --check `pending`).
        sys.exit(_run("aidd_review.py", argv[1:]))
    parser = build_parser()
    args = parser.parse_args(argv)
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
