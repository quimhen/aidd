#!/usr/bin/env python3
"""
aidd sync_issues — bidirectional status sync between a spec's tasks.md and
whichever issue tracker tasks_to_issues.py already created issues in.

Reads the same `.aidd-issues.json` sync map tasks_to_issues.py writes (next
to tasks.md, task id -> tracker ref), asks the provider's get_status(ref,
args) — contract v2 — for each synced task's live status, prints a diff
against the Status column already in tasks.md, and on --apply writes the
live status back into that column for ONLY the rows that have a sync-map
entry. A row with no tracker ref is never touched.

A v1-only third-party provider (no get_status) degrades gracefully: this
prints one clear note and exits 0 rather than crashing.

Safety: like tasks_to_issues.py, this defaults to a dry run that only PRINTS
the diff. Nothing is written to tasks.md until --apply is passed.

Usage:
    python sync_issues.py <path-to-tasks.md> [--provider github|azure_devops|bitbucket] [--apply]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import extension_registry  # noqa: E402
import tasks_to_issues as t2i  # noqa: E402

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def current_status(text, task_id):
    """The Status column's current value for this task id in tasks.md's
    table — '' if the table, the Status column, or the row itself isn't
    there yet."""
    header = t2i.find_header_index(text, 'Codes satisfied')
    if 'Status' not in header:
        return ''
    col_idx = header.index('Status')
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith('|'):
            continue
        m = t2i.TABLE_ROW_RE.match(stripped)
        if not m:
            continue
        cells = [c.strip() for c in m.group(1).split('|')]
        if cells and cells[0] == task_id and col_idx < len(cells):
            return cells[col_idx]
    return ''


def main():
    providers_map = extension_registry.get_providers(Path.cwd())

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('tasks_md', type=Path, help="Path to a spec's tasks.md")
    parser.add_argument('--provider', choices=sorted(providers_map), default='github',
                         help='Issue tracker to read live status from (default: github)')
    parser.add_argument('--apply', action='store_true',
                         help='Write live status back into tasks.md. Default only prints a diff.')
    for mod in providers_map.values():
        mod.add_provider_args(parser)
    args = parser.parse_args()

    if not args.tasks_md.exists():
        print(f"Not found: {args.tasks_md}", file=sys.stderr)
        sys.exit(2)

    provider = providers_map[args.provider]
    if not hasattr(provider, 'get_status'):
        print(f"Provider {args.provider!r} has no get_status() (contract v1 only) — "
              f"nothing to sync, skipping.")
        sys.exit(0)

    sync_path = args.tasks_md.parent / '.aidd-issues.json'
    synced = t2i.load_sync_map(sync_path)
    if not synced:
        print(f"No tracker refs found in {sync_path} — nothing to sync. "
              f"Run tasks_to_issues.py --apply first.")
        sys.exit(0)

    text = args.tasks_md.read_text(encoding='utf-8')

    print(f"{'Status diff' if not args.apply else 'Syncing status'} for {args.tasks_md} "
          f"({args.provider}):")
    print("=" * 60)
    print(f"{'Task':10s} {'tasks.md':12s}    {'tracker'}")

    updated_text = text
    changed = False
    for task_id, ref in synced.items():
        old_status = current_status(text, task_id) or '-'
        live_status = provider.get_status(ref, args)
        live_display = live_status or '? (unknown)'
        marker = '==' if live_status and old_status == live_status else '->'
        print(f"{task_id:10s} {old_status:12s} {marker} {live_display}")
        if args.apply and live_status and live_status != current_status(text, task_id):
            updated_text = t2i.update_task_column(updated_text, task_id, 'Status', live_status)
            changed = True

    if args.apply:
        if changed:
            args.tasks_md.write_text(updated_text, encoding='utf-8')
            print(f"\n{args.tasks_md} updated.")
        else:
            print("\nNo status changes to write.")
    else:
        print("\nDry run — nothing written. Re-run with --apply to write live status into tasks.md.")

    sys.exit(0)


if __name__ == '__main__':
    main()
