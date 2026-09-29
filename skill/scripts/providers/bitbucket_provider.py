"""Bitbucket provider — talks to the Bitbucket Cloud REST API v2.0 directly
(urllib, stdlib only — no `requests` dependency, consistent with every other
aidd script). Auth: an app password via BITBUCKET_USERNAME / BITBUCKET_APP_PASSWORD
env vars (Basic auth) — never passed as a CLI flag, so it doesn't end up in
shell history or a session transcript.

Requires the repo's issue tracker to be enabled (Bitbucket repo settings) —
this script cannot enable it, and the API returns 404 for a repo where it's
off.
"""
import json
import os
import sys
import urllib.error
import urllib.request


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
    username = os.environ['BITBUCKET_USERNAME']
    app_password = os.environ['BITBUCKET_APP_PASSWORD']
    import base64
    token = base64.b64encode(f"{username}:{app_password}".encode('utf-8')).decode('ascii')
    req.add_header('Authorization', f'Basic {token}')
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
