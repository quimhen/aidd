"""Azure DevOps provider — wraps the `az boards work-item create` command
(azure-devops CLI extension). Requires `az login` (or the `AZURE_DEVOPS_EXT_PAT`
env var the extension reads itself) done ahead of time — this script only
shells out, same division of labor as github_provider.py.
"""
import os
import subprocess
import sys


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
    import json
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
