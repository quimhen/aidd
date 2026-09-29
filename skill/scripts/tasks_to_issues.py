#!/usr/bin/env python3
"""
aidd tasks -> issue tracker — turns a spec's tasks.md into real, trackable
issues, one per approved task, in whichever tracker the project actually
uses: GitHub (default), Azure DevOps, or Bitbucket. Own design (not a port of
any other tool's version) — the "integrate with the issue tracker" piece,
generalized past GitHub-only after this script's original version, following
spec-kit's own precedent of shipping more than one tracker (its git/github
extensions) — not its extension/catalog machinery, which AIDD doesn't have.

Why this exists: tasks.md's approval gate (Step 4) makes the task list a
dry-run the user signs off on before Step 5 starts — but once approved, the
work of actually tracking each task (who's doing it, is it done, link the PR)
has nowhere to live except that same markdown file. This script promotes each
approved row to a real tracker issue, so a team's existing workflow
(assignees, boards, closing via commit message) applies to it.

Safety: creating issues is external, visible state — this defaults to a dry
run that only PRINTS what it would create. Nothing is created until --apply
is passed explicitly.

Sync tracking: a `.aidd-issues.json` file next to tasks.md maps each task id
to the issue it already created, so re-running this script after adding new
tasks doesn't duplicate issues for ones already synced — the same
"write the reference back, never duplicate" discipline AIDD already uses for
PR/Spec ref columns elsewhere, applied to this new integration point.

Usage:
    python tasks_to_issues.py <path-to-tasks.md> [--provider github|azure_devops|bitbucket] [--apply]
    python tasks_to_issues.py <path-to-tasks.md> --repo owner/name --apply                    # github (default)
    python tasks_to_issues.py <path-to-tasks.md> --provider azure_devops --org https://dev.azure.com/x --project P --apply
    python tasks_to_issues.py <path-to-tasks.md> --provider bitbucket --workspace w --repo-slug r --apply

Each provider is a small stdlib-only module under providers/ (see
providers/__init__.py for the two-function contract) — this script only
dispatches to the chosen one; it never talks to any tracker's API itself.

Exit code 0 = ran successfully (dry run or apply). Exit code 2 = usage/setup error.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from providers import github_provider, azure_devops_provider, bitbucket_provider  # noqa: E402

PROVIDERS = {
    'github': github_provider,
    'azure_devops': azure_devops_provider,
    'bitbucket': bitbucket_provider,
}

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

TABLE_ROW_RE = re.compile(r'^\|(.+)\|\s*$')
TASK_ID_RE = re.compile(r'^[A-Za-z]+-\d+$')


def table_rows(text, header_hint):
    """Same mechanism as check_spec.py's own table_rows — one markdown table
    following a line containing header_hint, header row skipped, separator
    rows skipped."""
    lines = text.splitlines()
    rows = []
    found_hint = False
    in_table = False
    header_seen = False
    for line in lines:
        if not found_hint:
            if header_hint in line:
                found_hint = True
            continue
        if not in_table:
            stripped = line.strip()
            if stripped.startswith('|'):
                in_table = True
            elif stripped.startswith('#'):
                found_hint = False
                continue
            else:
                continue
        m = TABLE_ROW_RE.match(line.strip())
        if not m:
            if header_seen:
                in_table = False
                found_hint = False
            continue
        cells = [c.strip() for c in m.group(1).split('|')]
        if not header_seen:
            header_seen = True
            continue
        if set(''.join(cells)) <= set('-: '):
            continue
        rows.append(cells)
    return rows


def parse_tasks(text):
    """Task | Codes satisfied | Target file | New view vs. reuse | Explicitly
    out of scope — the exact shape templates/tasks.md ships. Extra/missing
    trailing columns are tolerated (padded/ignored) so a project that adjusted
    the template slightly doesn't just silently get zero tasks."""
    rows = table_rows(text, 'Codes satisfied')
    tasks = []
    for r in rows:
        if not r or not TASK_ID_RE.match(r[0]):
            continue
        codes = r[1] if len(r) > 1 else ''
        target_file = r[2] if len(r) > 2 else ''
        scope_note = r[-1] if len(r) > 4 else ''
        tasks.append({'id': r[0], 'codes': codes, 'target_file': target_file, 'scope_note': scope_note})
    return tasks


def find_detail_section(text, task_id):
    """The '### <task-id>' block (Classify/Estimate/Decompose/Assign rubric),
    verbatim, up to the next heading of level <= 3. Returns '' if not found —
    a task with no detail section still gets an issue from the table row
    alone, it just won't have the rubric in the body."""
    pattern = re.compile(
        rf'^###\s+{re.escape(task_id)}\s*$(.*?)(?=^#{{1,3}}\s|\Z)',
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    return m.group(1).strip() if m else ''


def load_sync_map(path: Path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}


def save_sync_map(path: Path, data: dict):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('tasks_md', type=Path, help='Path to a spec\'s tasks.md')
    parser.add_argument('--provider', choices=sorted(PROVIDERS), default='github',
                         help='Issue tracker to create issues in (default: github)')
    parser.add_argument('--apply', action='store_true', help='Actually create issues. Default is a dry run.')
    # Each provider registers its own extra args (--repo for github; --org/--project
    # for azure_devops; --workspace/--repo-slug for bitbucket) on the same parser —
    # only the one selected by --provider is actually consulted, but registering all
    # three up front means --help shows every option without a two-pass parse.
    for mod in PROVIDERS.values():
        mod.add_provider_args(parser)
    args = parser.parse_args()

    provider = PROVIDERS[args.provider]

    if not args.tasks_md.exists():
        print(f"Not found: {args.tasks_md}", file=sys.stderr)
        sys.exit(2)

    if args.apply:
        ok, reason = provider.available(args)
        if not ok:
            print(reason, file=sys.stderr)
            sys.exit(2)

    text = args.tasks_md.read_text(encoding='utf-8')
    tasks = parse_tasks(text)
    if not tasks:
        print("No task rows found — is this really a tasks.md with a 'Codes satisfied' column?")
        sys.exit(0)

    sync_path = args.tasks_md.parent / '.aidd-issues.json'
    synced = load_sync_map(sync_path)

    print(f"{'Would create' if not args.apply else 'Creating'} {args.provider} issues for {args.tasks_md}:")
    print("=" * 60)

    created_any = False
    for task in tasks:
        if task['id'] in synced:
            print(f"  = {task['id']} — already synced: {synced[task['id']]}")
            continue

        title = f"{task['id']}: {task['codes']}".strip(': ')
        body_lines = [
            f"**Codes:** {task['codes']}",
            f"**Target file:** `{task['target_file']}`" if task['target_file'] else None,
            f"**Explicitly out of scope:** {task['scope_note']}" if task['scope_note'] else None,
        ]
        detail = find_detail_section(text, task['id'])
        if detail:
            body_lines += ['', '---', '', detail]
        body = '\n'.join(line for line in body_lines if line is not None)

        print(f"  + {title}")
        if not args.apply:
            continue

        url = provider.create_issue(title, body, args, apply=True)
        if url:
            synced[task['id']] = url
            created_any = True
            print(f"    -> {url}")

    if args.apply and created_any:
        save_sync_map(sync_path, synced)
        print(f"\nSync map updated: {sync_path}")
    elif not args.apply:
        print("\nDry run — nothing created. Re-run with --apply to actually create these issues.")

    sys.exit(0)


if __name__ == '__main__':
    main()
