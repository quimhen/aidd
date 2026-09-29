"""Tests for skill/extensions/<id>/provider.py — stdlib unittest, no dependencies.

Every provider module's contract (documented previously in
skill/scripts/providers/__init__.py, now migrated to the extension registry):
available(args) -> (bool, str|None), create_issue(title, body, args, apply)
-> str|None, add_provider_args(parser). These tests exercise that contract
for azure_devops_provider and bitbucket_provider — the two providers with no
coverage at all until now (github_provider's default path is already
exercised indirectly via test_tasks_to_issues.py's dry-run CLI tests).
Nothing here makes a real network/CLI call: subprocess.run and
urllib.request.urlopen are mocked in every test, the same "never touch
external state" discipline test_tasks_to_issues.py already documents for
its own dry-run-only tests.
"""
import importlib.util
import json
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

EXTENSIONS_DIR = Path(__file__).resolve().parent.parent / "skill" / "extensions"


def _load_provider(ext_id):
    """Load skill/extensions/<ext_id>/provider.py under a unique module name
    (same technique extension_registry.get_providers() uses at runtime) —
    every extension's entry file is literally named provider.py, so a plain
    sys.path-based `import provider` would collide across the three of them."""
    entry = EXTENSIONS_DIR / ext_id / "provider.py"
    spec = importlib.util.spec_from_file_location(f"test_ext_provider_{ext_id}", entry)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


github = _load_provider("github")
azure = _load_provider("azure_devops")
bitbucket = _load_provider("bitbucket")


def args_ns(**kwargs):
    return types.SimpleNamespace(**kwargs)


# ---------------------------------------------------------------------------
# github_provider — the default; only its available()/dry-run path lacked
# direct coverage (the CLI-level dry run in test_tasks_to_issues.py never
# calls create_issue(apply=True)).
# ---------------------------------------------------------------------------


class TestGithubProvider(unittest.TestCase):
    def test_dry_run_returns_none_without_calling_gh(self):
        with patch("subprocess.run") as run:
            result = github.create_issue("title", "body", args_ns(repo=None), apply=False)
        self.assertIsNone(result)
        run.assert_not_called()

    def test_available_true_when_gh_runs(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            ok, reason = github.available(args_ns())
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_available_false_when_gh_missing(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            ok, reason = github.available(args_ns())
        self.assertFalse(ok)
        self.assertIn("gh CLI not found", reason)

    def test_create_issue_returns_url_on_success(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=0, stdout="https://github.com/x/y/issues/9\n")
            result = github.create_issue("title", "body", args_ns(repo=None), apply=True)
        self.assertEqual(result, "https://github.com/x/y/issues/9")

    def test_create_issue_returns_none_on_failure(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=1, stderr="boom")
            result = github.create_issue("title", "body", args_ns(repo=None), apply=True)
        self.assertIsNone(result)

    def test_get_status_open(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=0, stdout="open\n")
            result = github.get_status("https://github.com/x/y/issues/9", args_ns(repo=None))
        self.assertEqual(result, "open")

    def test_get_status_closed_extracts_number_from_url(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=0, stdout="closed\n")
            result = github.get_status("https://github.com/x/y/issues/9", args_ns(repo="x/y"))
        self.assertEqual(result, "closed")
        called_cmd = run.call_args[0][0]
        self.assertIn("9", called_cmd)
        self.assertNotIn("https://github.com/x/y/issues/9", called_cmd)

    def test_get_status_returns_none_on_cli_failure(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=1, stderr="boom")
            result = github.get_status("https://github.com/x/y/issues/9", args_ns(repo=None))
        self.assertIsNone(result)

    def test_get_status_returns_none_on_unexpected_output(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=0, stdout="weird\n")
            result = github.get_status("https://github.com/x/y/issues/9", args_ns(repo=None))
        self.assertIsNone(result)

    def test_link_pr_dry_run_returns_false_without_calling_gh(self):
        with patch("subprocess.run") as run:
            result = github.link_pr("https://github.com/x/y/issues/9", "https://github.com/x/y/pull/1",
                                     args_ns(repo=None), apply=False)
        self.assertFalse(result)
        run.assert_not_called()

    def test_link_pr_apply_success(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=0, stdout="")
            result = github.link_pr("https://github.com/x/y/issues/9", "https://github.com/x/y/pull/1",
                                     args_ns(repo=None), apply=True)
        self.assertTrue(result)

    def test_link_pr_apply_failure(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=1, stderr="boom")
            result = github.link_pr("https://github.com/x/y/issues/9", "https://github.com/x/y/pull/1",
                                     args_ns(repo=None), apply=True)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# azure_devops_provider
# ---------------------------------------------------------------------------


class TestAzureDevopsProvider(unittest.TestCase):
    def test_available_false_when_az_missing(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            ok, reason = azure.available(args_ns(org=None, project=None))
        self.assertFalse(ok)
        self.assertIn("az CLI not found", reason)

    def test_available_false_when_az_version_fails(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=1)
            ok, reason = azure.available(args_ns(org=None, project=None))
        self.assertFalse(ok)
        self.assertIn("check the install", reason)

    def test_available_false_when_org_missing(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            ok, reason = azure.available(args_ns(org=None, project="Proj"))
        self.assertFalse(ok)
        self.assertIn("No org set", reason)

    def test_available_false_when_project_missing(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            ok, reason = azure.available(args_ns(org="https://dev.azure.com/x", project=None))
        self.assertFalse(ok)
        self.assertIn("No project set", reason)

    def test_available_true_when_everything_set(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            ok, reason = azure.available(args_ns(org="https://dev.azure.com/x", project="Proj"))
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_dry_run_returns_none_without_calling_az(self):
        with patch("subprocess.run") as run:
            result = azure.create_issue(
                "title", "body",
                args_ns(work_item_type="Task", org="x", project="y"),
                apply=False,
            )
        self.assertIsNone(result)
        run.assert_not_called()

    def test_create_issue_prefers_url_field(self):
        payload = json.dumps({"url": "https://dev.azure.com/x/y/_apis/wit/workItems/42"})
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=0, stdout=payload)
            result = azure.create_issue(
                "title", "body",
                args_ns(work_item_type="Task", org="https://dev.azure.com/x", project="y"),
                apply=True,
            )
        self.assertEqual(result, "https://dev.azure.com/x/y/_apis/wit/workItems/42")

    def test_create_issue_falls_back_to_constructed_url_from_id(self):
        payload = json.dumps({"id": 42})
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=0, stdout=payload)
            result = azure.create_issue(
                "title", "body",
                args_ns(work_item_type="Task", org="https://dev.azure.com/x", project="y"),
                apply=True,
            )
        self.assertEqual(result, "https://dev.azure.com/x/y/_workitems/edit/42")

    def test_create_issue_returns_none_on_cli_failure(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=1, stderr="boom")
            result = azure.create_issue(
                "title", "body",
                args_ns(work_item_type="Task", org="x", project="y"),
                apply=True,
            )
        self.assertIsNone(result)

    def test_get_status_open(self):
        payload = json.dumps({"fields": {"System.State": "Active"}})
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=0, stdout=payload)
            result = azure.get_status("https://dev.azure.com/x/y/_workitems/edit/42",
                                       args_ns(org="https://dev.azure.com/x"))
        self.assertEqual(result, "open")
        called_cmd = run.call_args[0][0]
        self.assertIn("42", called_cmd)

    def test_get_status_closed(self):
        payload = json.dumps({"fields": {"System.State": "Closed"}})
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=0, stdout=payload)
            result = azure.get_status("x/y/_workitems/edit/42", args_ns(org="https://dev.azure.com/x"))
        self.assertEqual(result, "closed")

    def test_get_status_returns_none_on_cli_failure(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=1, stderr="boom")
            result = azure.get_status("x/y/_workitems/edit/42", args_ns(org="https://dev.azure.com/x"))
        self.assertIsNone(result)

    def test_get_status_returns_none_on_bad_json(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=0, stdout="not json")
            result = azure.get_status("x/y/_workitems/edit/42", args_ns(org="https://dev.azure.com/x"))
        self.assertIsNone(result)

    def test_link_pr_dry_run_returns_false_without_calling_az(self):
        with patch("subprocess.run") as run:
            result = azure.link_pr("x/y/_workitems/edit/42", "https://github.com/x/y/pull/1",
                                    args_ns(org="https://dev.azure.com/x"), apply=False)
        self.assertFalse(result)
        run.assert_not_called()

    def test_link_pr_apply_success(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=0, stdout="")
            result = azure.link_pr("x/y/_workitems/edit/42", "https://github.com/x/y/pull/1",
                                    args_ns(org="https://dev.azure.com/x"), apply=True)
        self.assertTrue(result)

    def test_link_pr_apply_failure(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=1, stderr="boom")
            result = azure.link_pr("x/y/_workitems/edit/42", "https://github.com/x/y/pull/1",
                                    args_ns(org="https://dev.azure.com/x"), apply=True)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# bitbucket_provider
# ---------------------------------------------------------------------------


class TestBitbucketProvider(unittest.TestCase):
    def test_available_false_when_workspace_missing(self):
        ok, reason = bitbucket.available(args_ns(workspace=None, repo_slug="repo"))
        self.assertFalse(ok)
        self.assertIn("No workspace set", reason)

    def test_available_false_when_repo_slug_missing(self):
        ok, reason = bitbucket.available(args_ns(workspace="ws", repo_slug=None))
        self.assertFalse(ok)
        self.assertIn("No repo slug set", reason)

    @patch.dict("os.environ", {}, clear=True)
    def test_available_false_when_credentials_missing(self):
        ok, reason = bitbucket.available(args_ns(workspace="ws", repo_slug="repo"))
        self.assertFalse(ok)
        self.assertIn("Missing credentials", reason)

    @patch.dict("os.environ", {
        "BITBUCKET_USERNAME": "u", "BITBUCKET_APP_PASSWORD": "p",
    }, clear=True)
    def test_available_true_when_everything_set(self):
        ok, reason = bitbucket.available(args_ns(workspace="ws", repo_slug="repo"))
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_dry_run_returns_none_without_network_call(self):
        with patch("urllib.request.urlopen") as urlopen:
            result = bitbucket.create_issue(
                "title", "body", args_ns(workspace="ws", repo_slug="repo"), apply=False
            )
        self.assertIsNone(result)
        urlopen.assert_not_called()

    @patch.dict("os.environ", {
        "BITBUCKET_USERNAME": "u", "BITBUCKET_APP_PASSWORD": "p",
    }, clear=True)
    def test_create_issue_returns_html_url_on_success(self):
        response_body = json.dumps({"links": {"html": {"href": "https://bitbucket.org/ws/repo/issues/3"}}})
        cm = MagicMock()
        cm.read.return_value = response_body.encode("utf-8")
        cm.__enter__.return_value = cm
        with patch("urllib.request.urlopen", return_value=cm):
            result = bitbucket.create_issue(
                "title", "body", args_ns(workspace="ws", repo_slug="repo"), apply=True
            )
        self.assertEqual(result, "https://bitbucket.org/ws/repo/issues/3")

    @patch.dict("os.environ", {
        "BITBUCKET_USERNAME": "u", "BITBUCKET_APP_PASSWORD": "p",
    }, clear=True)
    def test_create_issue_returns_none_on_http_error(self):
        err = HTTPError(url="https://api.bitbucket.org/x", code=403, msg="Forbidden",
                         hdrs=None, fp=None)
        err.read = lambda: b"no access"
        with patch("urllib.request.urlopen", side_effect=err):
            result = bitbucket.create_issue(
                "title", "body", args_ns(workspace="ws", repo_slug="repo"), apply=True
            )
        self.assertIsNone(result)

    @patch.dict("os.environ", {
        "BITBUCKET_USERNAME": "u", "BITBUCKET_APP_PASSWORD": "p",
    }, clear=True)
    def test_create_issue_returns_none_on_url_error(self):
        with patch("urllib.request.urlopen",
                    side_effect=URLError("no route to host")):
            result = bitbucket.create_issue(
                "title", "body", args_ns(workspace="ws", repo_slug="repo"), apply=True
            )
        self.assertIsNone(result)

    @patch.dict("os.environ", {
        "BITBUCKET_USERNAME": "u", "BITBUCKET_APP_PASSWORD": "p",
    }, clear=True)
    def test_get_status_open(self):
        response_body = json.dumps({"state": "open"})
        cm = MagicMock()
        cm.read.return_value = response_body.encode("utf-8")
        cm.__enter__.return_value = cm
        with patch("urllib.request.urlopen", return_value=cm):
            result = bitbucket.get_status(
                "https://bitbucket.org/ws/repo/issues/3", args_ns(workspace="ws", repo_slug="repo")
            )
        self.assertEqual(result, "open")

    @patch.dict("os.environ", {
        "BITBUCKET_USERNAME": "u", "BITBUCKET_APP_PASSWORD": "p",
    }, clear=True)
    def test_get_status_closed(self):
        response_body = json.dumps({"state": "resolved"})
        cm = MagicMock()
        cm.read.return_value = response_body.encode("utf-8")
        cm.__enter__.return_value = cm
        with patch("urllib.request.urlopen", return_value=cm):
            result = bitbucket.get_status(
                "https://bitbucket.org/ws/repo/issues/3", args_ns(workspace="ws", repo_slug="repo")
            )
        self.assertEqual(result, "closed")

    def test_get_status_returns_none_when_ref_has_no_id(self):
        result = bitbucket.get_status("no-id-here", args_ns(workspace="ws", repo_slug="repo"))
        self.assertIsNone(result)

    @patch.dict("os.environ", {
        "BITBUCKET_USERNAME": "u", "BITBUCKET_APP_PASSWORD": "p",
    }, clear=True)
    def test_get_status_returns_none_on_http_error(self):
        err = HTTPError(url="https://api.bitbucket.org/x", code=404, msg="Not Found",
                         hdrs=None, fp=None)
        with patch("urllib.request.urlopen", side_effect=err):
            result = bitbucket.get_status(
                "https://bitbucket.org/ws/repo/issues/3", args_ns(workspace="ws", repo_slug="repo")
            )
        self.assertIsNone(result)

    def test_link_pr_dry_run_returns_false_without_network_call(self):
        with patch("urllib.request.urlopen") as urlopen:
            result = bitbucket.link_pr(
                "https://bitbucket.org/ws/repo/issues/3", "https://github.com/x/y/pull/1",
                args_ns(workspace="ws", repo_slug="repo"), apply=False,
            )
        self.assertFalse(result)
        urlopen.assert_not_called()

    @patch.dict("os.environ", {
        "BITBUCKET_USERNAME": "u", "BITBUCKET_APP_PASSWORD": "p",
    }, clear=True)
    def test_link_pr_apply_success(self):
        cm = MagicMock()
        cm.read.return_value = b"{}"
        cm.__enter__.return_value = cm
        with patch("urllib.request.urlopen", return_value=cm):
            result = bitbucket.link_pr(
                "https://bitbucket.org/ws/repo/issues/3", "https://github.com/x/y/pull/1",
                args_ns(workspace="ws", repo_slug="repo"), apply=True,
            )
        self.assertTrue(result)

    @patch.dict("os.environ", {
        "BITBUCKET_USERNAME": "u", "BITBUCKET_APP_PASSWORD": "p",
    }, clear=True)
    def test_link_pr_apply_failure_on_http_error(self):
        err = HTTPError(url="https://api.bitbucket.org/x", code=403, msg="Forbidden",
                         hdrs=None, fp=None)
        err.read = lambda: b"no access"
        with patch("urllib.request.urlopen", side_effect=err):
            result = bitbucket.link_pr(
                "https://bitbucket.org/ws/repo/issues/3", "https://github.com/x/y/pull/1",
                args_ns(workspace="ws", repo_slug="repo"), apply=True,
            )
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
