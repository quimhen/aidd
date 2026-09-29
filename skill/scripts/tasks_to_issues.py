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

Each provider is a small stdlib-only module discovered at runtime via
extension_registry.get_providers() from skill/extensions/<id>/provider.py
(first-party) or <project_root>/.aidd/extensions/<id>/provider.py
(project-local/marketplace-installed) — this script only dispatches to the
chosen one; it never talks to any tracker's API itself.

Exit code 0 = ran successfully (dry run or apply). Exit code 2 = usage/setup error.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import extension_registry  # noqa: E402

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


def find_header_index(text, header_hint):
    """The raw header cells (as printed) of the first table found following a
    line containing `header_hint` — same table-location rule as table_rows(),
    but returning the header row itself instead of the data rows, so a caller
    can look up a column's position by name (e.g. 'Tracker ref', 'Status')
    instead of a hardcoded index."""
    lines = text.splitlines()
    found_hint = False
    for line in lines:
        stripped = line.strip()
        if not found_hint:
            if header_hint in line:
                found_hint = True
                # The hint often sits inside the header row itself (e.g. the
                # "Codes satisfied" cell text) rather than in a preceding
                # '## Section' heading — if so, this line already IS the
                # header row, so return it immediately instead of skipping
                # to the next '|' line (which would be the separator row).
                if stripped.startswith('|'):
                    m = TABLE_ROW_RE.match(stripped)
                    if m:
                        return [c.strip() for c in m.group(1).split('|')]
            continue
        if stripped.startswith('|'):
            m = TABLE_ROW_RE.match(stripped)
            if m:
                return [c.strip() for c in m.group(1).split('|')]
        elif stripped.startswith('#'):
            found_hint = False
    return []


def update_task_column(text, task_id, column_name, new_value):
    """Write `new_value` into the `column_name` cell of the row whose first
    column equals `task_id`, in tasks.md's main task table. Used by
    sync_issues.py (Status) and link_pr_to_task.py (Tracker ref) to write
    back into columns that are populated only by these scripts, never by
    hand. Returns the text unchanged (with a stderr warning) if the column
    or the row isn't found — never raises, never touches any other row."""
    header = find_header_index(text, 'Codes satisfied')
    if column_name not in header:
        print(f"warning: tasks.md has no {column_name!r} column — skipped", file=sys.stderr)
        return text
    col_idx = header.index(column_name)

    lines = text.splitlines(keepends=True)
    out = []
    for line in lines:
        stripped = line.rstrip('\r\n')
        m = TABLE_ROW_RE.match(stripped.strip())
        if m and stripped.strip().startswith('|'):
            cells = [c.strip() for c in m.group(1).split('|')]
            if cells and cells[0] == task_id and col_idx < len(cells):
                cells[col_idx] = new_value
                eol = line[len(stripped):]
                out.append('| ' + ' | '.join(cells) + ' |' + eol)
                continue
        out.append(line)
    return ''.join(out)


def parse_tasks(text):
    """Task | Codes satisfied | Target file | New view vs. reuse | [Tracker
    ref | Status |] Explicitly out of scope — templates/tasks.md's shape
    (the two tracker columns were added later, immediately before the last
    one). `codes`/`target_file` are read by fixed early index since those
    never move; `scope_note` is always r[-1] since "Explicitly out of scope"
    stays the last column regardless of how many tracker columns sit before
    it. Extra/missing trailing columns are otherwise tolerated
    (padded/ignored) so a project that adjusted the template slightly
    doesn't just silently get zero tasks."""
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
    providers_map = extension_registry.get_providers(Path.cwd())

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('tasks_md', type=Path, help='Path to a spec\'s tasks.md')
    parser.add_argument('--provider', choices=sorted(providers_map), default='github',
                         help='Issue tracker to create issues in (default: github)')
    parser.add_argument('--apply', action='store_true', help='Actually create issues. Default is a dry run.')
    # Each provider registers its own extra args (--repo for github; --org/--project
    # for azure_devops; --workspace/--repo-slug for bitbucket) on the same parser —
    # only the one selected by --provider is actually consulted, but registering all
    # up front means --help shows every option without a two-pass parse.
    for mod in providers_map.values():
        mod.add_provider_args(parser)
    args = parser.parse_args()

    provider = providers_map[args.provider]

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
