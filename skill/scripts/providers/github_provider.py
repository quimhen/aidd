"""GitHub provider — wraps the `gh` CLI. Default provider (--provider github),
preserves tasks_to_issues.py's original pre-multi-provider behavior exactly.
"""
import subprocess
import sys


def add_provider_args(parser):
    parser.add_argument('--repo', default=None, help='owner/name — defaults to gh\'s own repo detection')


def available(args):
    try:
        subprocess.run(['gh', '--version'], capture_output=True, timeout=5)
        return True, None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, "gh CLI not found — install it and run `gh auth login` first, or omit --apply for a dry run."


def create_issue(title, body, args, apply: bool):
    if not apply:
        return None
    cmd = ['gh', 'issue', 'create', '--title', title, '--body', body]
    if getattr(args, 'repo', None):
        cmd += ['--repo', args.repo]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"  ! gh issue create failed: {result.stderr.strip()}", file=sys.stderr)
        return None
    return result.stdout.strip()  # gh prints the created issue's URL
