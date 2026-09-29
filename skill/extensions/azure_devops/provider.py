"""Azure DevOps provider — wraps the `az boards work-item create` command
(azure-devops CLI extension). Requires `az login` (or the `AZURE_DEVOPS_EXT_PAT`
env var the extension reads itself) done ahead of time — this script only
shells out, same division of labor as github_provider.py.

Contract v2 adds get_status()/link_pr() for sync_issues.py/link_pr_to_task.py,
same az-CLI-only, same subprocess/error-handling style as create_issue().
"""
import json
import os
import re
import subprocess
import sys

CONTRACT_VERSION = 2


def add_provider_args(parser):
    parser.add_argument('--org', default=os.environ.get('AZURE_DEVOPS_ORG'),
                         help='Org URL, e.g. https://dev.azure.com/myorg — or set AZURE_DEVOPS_ORG')
    parser.add_argument('--project', default=os.environ.get('AZURE_DEVOPS_PROJECT'),
                         help='Project name — or set AZURE_DEVOPS_PROJECT')
    parser.add_argument('--work-item-type', default='Task',
                         help='Work item type to create (default: Task)')


def available(args):
    try:
        result = subprocess.run(['az', '--version'], capture_output=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, "az CLI not found — install the Azure CLI and run `az login` first, or omit --apply for a dry run."
    if result.returncode != 0:
        return False, "az CLI found but `az --version` failed — check the install."
    if not getattr(args, 'org', None):
        return False, "No org set — pass --org https://dev.azure.com/<org> or set AZURE_DEVOPS_ORG."
    if not getattr(args, 'project', None):
        return False, "No project set — pass --project <name> or set AZURE_DEVOPS_PROJECT."
    return True, None


def create_issue(title, body, args, apply: bool):
    if not apply:
        return None
    cmd = [
        'az', 'boards', 'work-item', 'create',
        '--title', title,
        '--type', args.work_item_type,
        '--org', args.org,
        '--project', args.project,
        '--description', body,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"  ! az boards work-item create failed: {result.stderr.strip()}", file=sys.stderr)
        return None
    # az returns JSON by default; pull out id/url without requiring a JSON dep.
    try:
        data = json.loads(result.stdout)
        url = data.get('url') or data.get('_links', {}).get('html', {}).get('href')
        work_item_id = data.get('id')
        if url:
            return url
        if work_item_id:
            return f"{args.org}/{args.project}/_workitems/edit/{work_item_id}"
    except (json.JSONDecodeError, AttributeError):
        pass
    return result.stdout.strip()


def _work_item_id(ref):
    """create_issue() returns either a raw `url` field or our own constructed
    '<org>/<project>/_workitems/edit/<id>' string — pull the numeric id out of
    either shape (or a REST API '.../workItems/<id>' url) so callers always
    hand `az boards work-item show/update` a bare --id."""
    m = (re.search(r'_workitems/edit/(\d+)\b', ref)
         or re.search(r'workItems/(\d+)\b', ref)
         or re.search(r'/(\d+)$', ref))
    return m.group(1) if m else ref


_CLOSED_STATES = {'closed', 'done', 'resolved', 'completed', 'removed'}


def get_status(ref, args):
    """'open' | 'closed' | None (can't be determined)."""
    cmd = ['az', 'boards', 'work-item', 'show', '--id', _work_item_id(ref),
           '--org', args.org, '--fields', 'System.State']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"  ! az boards work-item show failed: {e}", file=sys.stderr)
        return None
    if result.returncode != 0:
        print(f"  ! az boards work-item show failed: {result.stderr.strip()}", file=sys.stderr)
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    state = str(data.get('fields', {}).get('System.State', '')).strip().lower()
    if not state:
        return None
    return 'closed' if state in _CLOSED_STATES else 'open'


def link_pr(ref, pr_url, args, apply: bool):
    """Attach the PR url as a discussion comment on the existing work item.
    Dry run (apply=False) never shells out and always returns False."""
    if not apply:
        return False
    cmd = ['az', 'boards', 'work-item', 'update', '--id', _work_item_id(ref),
           '--discussion', pr_url, '--org', args.org]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"  ! az boards work-item update failed: {e}", file=sys.stderr)
        return False
    if result.returncode != 0:
        print(f"  ! az boards work-item update failed: {result.stderr.strip()}", file=sys.stderr)
        return False
    return True
