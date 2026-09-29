"""Bitbucket provider — talks to the Bitbucket Cloud REST API v2.0 directly
(urllib, stdlib only — no `requests` dependency, consistent with every other
aidd script). Auth: an app password via BITBUCKET_USERNAME / BITBUCKET_APP_PASSWORD
env vars (Basic auth) — never passed as a CLI flag, so it doesn't end up in
shell history or a session transcript.

Requires the repo's issue tracker to be enabled (Bitbucket repo settings) —
this script cannot enable it, and the API returns 404 for a repo where it's
off.

Contract v2 adds get_status()/link_pr() for sync_issues.py/link_pr_to_task.py,
same urllib-only, same error-handling style as create_issue().
"""
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request

CONTRACT_VERSION = 2


def add_provider_args(parser):
    parser.add_argument('--workspace', default=os.environ.get('BITBUCKET_WORKSPACE'),
                         help='Workspace ID — or set BITBUCKET_WORKSPACE')
    parser.add_argument('--repo-slug', default=os.environ.get('BITBUCKET_REPO_SLUG'),
                         help='Repository slug — or set BITBUCKET_REPO_SLUG')


def available(args):
    if not getattr(args, 'workspace', None):
        return False, "No workspace set — pass --workspace <id> or set BITBUCKET_WORKSPACE."
    if not getattr(args, 'repo_slug', None):
        return False, "No repo slug set — pass --repo-slug <slug> or set BITBUCKET_REPO_SLUG."
    if not os.environ.get('BITBUCKET_USERNAME') or not os.environ.get('BITBUCKET_APP_PASSWORD'):
        return False, ("Missing credentials — set BITBUCKET_USERNAME and BITBUCKET_APP_PASSWORD "
                        "(an app password with 'Issues: Write' scope) as environment variables, "
                        "never as a CLI flag.")
    return True, None


def create_issue(title, body, args, apply: bool):
    if not apply:
        return None
    url = f"https://api.bitbucket.org/2.0/repositories/{args.workspace}/{args.repo_slug}/issues"
    payload = json.dumps({
        'title': title,
        'content': {'raw': body, 'markup': 'markdown'},
    }).encode('utf-8')
    req = urllib.request.Request(url, data=payload, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', _basic_auth_header())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        detail = e.read().decode('utf-8', errors='ignore')
        print(f"  ! Bitbucket issue create failed: HTTP {e.code} — {detail[:300]}", file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f"  ! Bitbucket issue create failed: {e.reason}", file=sys.stderr)
        return None
    html_url = data.get('links', {}).get('html', {}).get('href')
    return html_url or f"issue #{data.get('id')}"


def _basic_auth_header():
    username = os.environ['BITBUCKET_USERNAME']
    app_password = os.environ['BITBUCKET_APP_PASSWORD']
    token = base64.b64encode(f"{username}:{app_password}".encode('utf-8')).decode('ascii')
    return f'Basic {token}'


def _issue_id(ref):
    """create_issue() returns either the issue's html url or a constructed
    'issue #<id>' fallback string — pull the numeric id out of either shape."""
    m = re.search(r'/issues/(\d+)\b', ref) or re.search(r'#(\d+)\b', ref)
    return m.group(1) if m else None


_CLOSED_STATES = {'resolved', 'closed', 'invalid', 'duplicate', 'wontfix'}
_OPEN_STATES = {'new', 'open', 'on hold'}


def get_status(ref, args):
    """'open' | 'closed' | None (can't be determined)."""
    issue_id = _issue_id(ref)
    if issue_id is None:
        print(f"  ! Bitbucket get_status: could not extract an issue id from {ref!r}", file=sys.stderr)
        return None
    url = f"https://api.bitbucket.org/2.0/repositories/{args.workspace}/{args.repo_slug}/issues/{issue_id}"
    req = urllib.request.Request(url)
    req.add_header('Authorization', _basic_auth_header())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print(f"  ! Bitbucket get_status failed: HTTP {e.code}", file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f"  ! Bitbucket get_status failed: {e.reason}", file=sys.stderr)
        return None
    state = str(data.get('state', '')).strip().lower()
    if state in _CLOSED_STATES:
        return 'closed'
    if state in _OPEN_STATES:
        return 'open'
    return None


def link_pr(ref, pr_url, args, apply: bool):
    """POST the PR url as a comment on the existing issue. Dry run
    (apply=False) never makes a network call and always returns False."""
    if not apply:
        return False
    issue_id = _issue_id(ref)
    if issue_id is None:
        print(f"  ! Bitbucket link_pr: could not extract an issue id from {ref!r}", file=sys.stderr)
        return False
    url = (f"https://api.bitbucket.org/2.0/repositories/{args.workspace}/"
           f"{args.repo_slug}/issues/{issue_id}/comments")
    payload = json.dumps({'content': {'raw': pr_url, 'markup': 'markdown'}}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', _basic_auth_header())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode('utf-8', errors='ignore')
        print(f"  ! Bitbucket link_pr failed: HTTP {e.code} — {detail[:300]}", file=sys.stderr)
        return False
    except urllib.error.URLError as e:
        print(f"  ! Bitbucket link_pr failed: {e.reason}", file=sys.stderr)
        return False
    return True
