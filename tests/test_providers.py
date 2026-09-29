"""Tests for scripts/providers/*.py — stdlib unittest, no dependencies.

Every provider's own module docstring in providers/__init__.py states the
contract: available(args) -> (bool, str|None), create_issue(title, body,
args, apply) -> str|None, add_provider_args(parser). These tests exercise
that contract for azure_devops_provider and bitbucket_provider — the two
providers with no coverage at all until now (github_provider's default path
is already exercised indirectly via test_tasks_to_issues.py's dry-run CLI
tests). Nothing here makes a real network/CLI call: subprocess.run and
urllib.request.urlopen are mocked in every test, the same "never touch
external state" discipline test_tasks_to_issues.py already documents for
its own dry-run-only tests.
"""
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

PROVIDERS_DIR = Path(__file__).resolve().parent.parent / "skill" / "scripts" / "providers"
sys.path.insert(0, str(PROVIDERS_DIR.parent))  # so "providers" imports as a package
sys.path.insert(0, str(PROVIDERS_DIR))

import providers.azure_devops_provider as azure  # noqa: E402
import providers.bitbucket_provider as bitbucket  # noqa: E402
import providers.github_provider as github  # noqa: E402


def args_ns(**kwargs):
    return types.SimpleNamespace(**kwargs)


# ---------------------------------------------------------------------------
# github_provider — the default; only its available()/dry-run path lacked
# direct coverage (the CLI-level dry run in test_tasks_to_issues.py never
# calls create_issue(apply=True)).
# ---------------------------------------------------------------------------


class TestGithubProvider(unittest.TestCase):
    def test_dry_run_returns_none_without_calling_gh(self):
        with patch("providers.github_provider.subprocess.run") as run:
            result = github.create_issue("title", "body", args_ns(repo=None), apply=False)
        self.assertIsNone(result)
        run.assert_not_called()

    def test_available_true_when_gh_runs(self):
        with patch("providers.github_provider.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            ok, reason = github.available(args_ns())
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_available_false_when_gh_missing(self):
        with patch("providers.github_provider.subprocess.run", side_effect=FileNotFoundError):
            ok, reason = github.available(args_ns())
        self.assertFalse(ok)
        self.assertIn("gh CLI not found", reason)

    def test_create_issue_returns_url_on_success(self):
        with patch("providers.github_provider.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0, stdout="https://github.com/x/y/issues/9\n")
            result = github.create_issue("title", "body", args_ns(repo=None), apply=True)
        self.assertEqual(result, "https://github.com/x/y/issues/9")

    def test_create_issue_returns_none_on_failure(self):
        with patch("providers.github_provider.subprocess.run") as run:
            run.return_value = MagicMock(returncode=1, stderr="boom")
            result = github.create_issue("title", "body", args_ns(repo=None), apply=True)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# azure_devops_provider
# ---------------------------------------------------------------------------


class TestAzureDevopsProvider(unittest.TestCase):
    def test_available_false_when_az_missing(self):
        with patch("providers.azure_devops_provider.subprocess.run", side_effect=FileNotFoundError):
            ok, reason = azure.available(args_ns(org=None, project=None))
        self.assertFalse(ok)
        self.assertIn("az CLI not found", reason)

    def test_available_false_when_az_version_fails(self):
        with patch("providers.azure_devops_provider.subprocess.run") as run:
            run.return_value = MagicMock(returncode=1)
            ok, reason = azure.available(args_ns(org=None, project=None))
        self.assertFalse(ok)
        self.assertIn("check the install", reason)

    def test_available_false_when_org_missing(self):
        with patch("providers.azure_devops_provider.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            ok, reason = azure.available(args_ns(org=None, project="Proj"))
        self.assertFalse(ok)
        self.assertIn("No org set", reason)

    def test_available_false_when_project_missing(self):
        with patch("providers.azure_devops_provider.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            ok, reason = azure.available(args_ns(org="https://dev.azure.com/x", project=None))
        self.assertFalse(ok)
        self.assertIn("No project set", reason)

    def test_available_true_when_everything_set(self):
        with patch("providers.azure_devops_provider.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            ok, reason = azure.available(args_ns(org="https://dev.azure.com/x", project="Proj"))
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_dry_run_returns_none_without_calling_az(self):
        with patch("providers.azure_devops_provider.subprocess.run") as run:
            result = azure.create_issue(
                "title", "body",
                args_ns(work_item_type="Task", org="x", project="y"),
                apply=False,
            )
        self.assertIsNone(result)
        run.assert_not_called()

    def test_create_issue_prefers_url_field(self):
        payload = json.dumps({"url": "https://dev.azure.com/x/y/_apis/wit/workItems/42"})
        with patch("providers.azure_devops_provider.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0, stdout=payload)
            result = azure.create_issue(
                "title", "body",
                args_ns(work_item_type="Task", org="https://dev.azure.com/x", project="y"),
                apply=True,
            )
        self.assertEqual(result, "https://dev.azure.com/x/y/_apis/wit/workItems/42")

    def test_create_issue_falls_back_to_constructed_url_from_id(self):
        payload = json.dumps({"id": 42})
        with patch("providers.azure_devops_provider.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0, stdout=payload)
            result = azure.create_issue(
                "title", "body",
                args_ns(work_item_type="Task", org="https://dev.azure.com/x", project="y"),
                apply=True,
            )
        self.assertEqual(result, "https://dev.azure.com/x/y/_workitems/edit/42")

    def test_create_issue_returns_none_on_cli_failure(self):
        with patch("providers.azure_devops_provider.subprocess.run") as run:
            run.return_value = MagicMock(returncode=1, stderr="boom")
            result = azure.create_issue(
                "title", "body",
                args_ns(work_item_type="Task", org="x", project="y"),
                apply=True,
            )
        self.assertIsNone(result)


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
        with patch("providers.bitbucket_provider.urllib.request.urlopen") as urlopen:
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
        with patch("providers.bitbucket_provider.urllib.request.urlopen", return_value=cm):
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
        with patch("providers.bitbucket_provider.urllib.request.urlopen", side_effect=err):
            result = bitbucket.create_issue(
                "title", "body", args_ns(workspace="ws", repo_slug="repo"), apply=True
            )
        self.assertIsNone(result)

    @patch.dict("os.environ", {
        "BITBUCKET_USERNAME": "u", "BITBUCKET_APP_PASSWORD": "p",
    }, clear=True)
    def test_create_issue_returns_none_on_url_error(self):
        with patch("providers.bitbucket_provider.urllib.request.urlopen",
                    side_effect=URLError("no route to host")):
            result = bitbucket.create_issue(
                "title", "body", args_ns(workspace="ws", repo_slug="repo"), apply=True
            )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
