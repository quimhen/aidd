"""GitHub provider — wraps the `gh` CLI. Default provider (--provider github),
preserves tasks_to_issues.py's original pre-multi-provider behavior exactly.

Contract v2 adds get_status()/link_pr() for sync_issues.py/link_pr_to_task.py —
bidirectional status sync and PR<->task linking, still gh-CLI-only, same
subprocess/error-handling style as create_issue() below.
"""
import re
import subprocess
import sys

CONTRACT_VERSION = 2


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


def _issue_ref(ref):
    """create_issue() returns a full issue URL — `gh issue view/comment` also
    accept a bare number, but extract it when we have one anyway so a ref
    that's just a number (hand-entered, or from a future provider version)
    works the same way."""
    m = re.search(r'/issues/(\d+)\b', ref)
    return m.group(1) if m else ref


def get_status(ref, args):
    """'open' | 'closed' | None (can't be determined)."""
    cmd = ['gh', 'issue', 'view', _issue_ref(ref), '--json', 'state', '-q', '.state']
    if getattr(args, 'repo', None):
        cmd += ['--repo', args.repo]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"  ! gh issue view failed: {e}", file=sys.stderr)
        return None
    if result.returncode != 0:
        print(f"  ! gh issue view failed: {result.stderr.strip()}", file=sys.stderr)
        return None
    state = result.stdout.strip().lower()
    return state if state in ('open', 'closed') else None


def link_pr(ref, pr_url, args, apply: bool):
    """Comment the PR url onto the existing issue. Dry run (apply=False)
    never shells out and always returns False."""
    if not apply:
        return False
    cmd = ['gh', 'issue', 'comment', _issue_ref(ref), '--body', pr_url]
    if getattr(args, 'repo', None):
        cmd += ['--repo', args.repo]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"  ! gh issue comment failed: {e}", file=sys.stderr)
        return False
    if result.returncode != 0:
        print(f"  ! gh issue comment failed: {result.stderr.strip()}", file=sys.stderr)
        return False
    return True
