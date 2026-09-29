#!/usr/bin/env python3
"""
aidd link_pr_to_task — attaches an opened PR's URL to the tracker issue for
one task, and writes that URL into tasks.md's "Tracker ref" column.

Task id resolution order:
    1. --task-id, if given.
    2. an "[A-Za-z]+-\\d+" match out of --branch (same TASK_ID_RE shape
       tasks_to_issues.py already uses to recognize a task id).
    3. the same pattern out of the GITHUB_HEAD_REF env var, then
       BUILD_SOURCEBRANCH — checked in that order, so this runs unmodified
       inside a GitHub Actions or Azure Pipelines PR-triggered job with no
       extra flags.

The task id is then looked up in .aidd-issues.json (next to tasks.md, or at
--tasks-md's own sync map) to find the tracker ref tasks_to_issues.py
already created for it, and provider.link_pr(ref, pr_url, args, apply) does
the actual linking (contract v2).

Safety: --pr-url is required together with --apply. Without --apply, this
only prints what it WOULD link once a PR URL is known — no network/CLI call,
no write to tasks.md.

Usage:
    python link_pr_to_task.py --tasks-md <path> --pr-url <url> --apply
    python link_pr_to_task.py --tasks-md <path> --task-id T-01 --pr-url <url> --apply
    python link_pr_to_task.py --tasks-md <path> --branch feature/T-01-thing --pr-url <url> --apply
"""
import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import extension_registry  # noqa: E402
import tasks_to_issues as t2i  # noqa: E402

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

TASK_ID_SEARCH_RE = re.compile(r'[A-Za-z]+-\d+')


def resolve_task_id(args):
    """--task-id wins outright; otherwise search --branch, then
    GITHUB_HEAD_REF, then BUILD_SOURCEBRANCH, in that order, for the first
    task-id-shaped match."""
    if args.task_id:
        return args.task_id
    for candidate in (args.branch, os.environ.get('GITHUB_HEAD_REF'), os.environ.get('BUILD_SOURCEBRANCH')):
        if not candidate:
            continue
        m = TASK_ID_SEARCH_RE.search(candidate)
        if m:
            return m.group(0)
    return None


def main():
    providers_map = extension_registry.get_providers(Path.cwd())

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--tasks-md', type=Path, required=True, help="Path to a spec's tasks.md")
    parser.add_argument('--task-id', default=None,
                         help='Task id, e.g. T-01 — overrides --branch/environment detection')
    parser.add_argument('--branch', default=None,
                         help='Branch name to extract the task id from. Defaults to GITHUB_HEAD_REF, '
                              'then BUILD_SOURCEBRANCH, when omitted.')
    parser.add_argument('--pr-url', default=None,
                         help='The opened PR URL. Required together with --apply.')
    parser.add_argument('--provider', choices=sorted(providers_map), default='github',
                         help='Issue tracker to link the PR in (default: github)')
    parser.add_argument('--apply', action='store_true',
                         help='Actually post/attach the PR link and write it into tasks.md. '
                              'Default is a dry run.')
    for mod in providers_map.values():
        mod.add_provider_args(parser)
    args = parser.parse_args()

    if args.apply and not args.pr_url:
        print("--pr-url is required together with --apply", file=sys.stderr)
        sys.exit(2)

    if not args.tasks_md.exists():
        print(f"Not found: {args.tasks_md}", file=sys.stderr)
        sys.exit(2)

    task_id = resolve_task_id(args)
    if not task_id:
        print("Could not determine a task id — pass --task-id, or --branch, or run this where "
              "GITHUB_HEAD_REF/BUILD_SOURCEBRANCH is set.", file=sys.stderr)
        sys.exit(2)

    sync_path = args.tasks_md.parent / '.aidd-issues.json'
    synced = t2i.load_sync_map(sync_path)
    ref = synced.get(task_id)
    if not ref:
        print(f"No tracker ref found for {task_id} in {sync_path} — has it been synced with "
              f"tasks_to_issues.py --apply yet?", file=sys.stderr)
        sys.exit(2)

    provider = providers_map[args.provider]

    if not args.apply:
        pr_display = args.pr_url or "(a PR URL, once known)"
        print(f"Would link {task_id} ({ref}) to {pr_display}. Re-run with --pr-url <url> --apply "
              f"to actually link it.")
        sys.exit(0)

    ok = provider.link_pr(ref, args.pr_url, args, apply=True)
    if not ok:
        print(f"Failed to link the PR to {task_id} — see message above.", file=sys.stderr)
        sys.exit(1)

    text = args.tasks_md.read_text(encoding='utf-8')
    updated = t2i.update_task_column(text, task_id, 'Tracker ref', args.pr_url)
    args.tasks_md.write_text(updated, encoding='utf-8')
    print(f"Linked {task_id} ({ref}) -> {args.pr_url}, and wrote it into {args.tasks_md}'s "
          f"Tracker ref column.")
    sys.exit(0)


if __name__ == '__main__':
    main()
