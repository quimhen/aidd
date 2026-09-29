"""Tests for skill/scripts/link_pr_to_task.py — stdlib unittest, no
dependencies. Never touches a real tracker: provider modules are fake,
in-memory objects, same discipline as test_sync_issues.py.
"""
import json
import os
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import link_pr_to_task as lpt  # noqa: E402

TASKS_MD = """# Tasks — example

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | New view vs. reuse | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-01 | CTL-004 | session_provider.dart | reuse logic only | https://github.com/x/y/issues/1 | open | any other file |
| T-02 | CTL-007 | session_provider.dart | reuse logic only | https://github.com/x/y/issues/2 | open | any other file |
"""


def _fake_registry(providers):
    ns = types.SimpleNamespace()
    ns.get_providers = lambda project_root: providers
    return ns


def _provider(link_pr_result=True, calls=None):
    mod = types.ModuleType("fake_provider")
    mod.add_provider_args = lambda parser: None

    def link_pr(ref, pr_url, args, apply):
        if calls is not None:
            calls.append((ref, pr_url, apply))
        if not apply:
            return False
        return link_pr_result

    mod.link_pr = link_pr
    return mod


class TestResolveTaskId(unittest.TestCase):
    def _args(self, task_id=None, branch=None):
        return types.SimpleNamespace(task_id=task_id, branch=branch)

    def test_explicit_task_id_wins(self):
        args = self._args(task_id="T-05", branch="feature/T-01-thing")
        self.assertEqual(lpt.resolve_task_id(args), "T-05")

    def test_extracts_from_branch(self):
        args = self._args(branch="feature/T-01-fix-login")
        self.assertEqual(lpt.resolve_task_id(args), "T-01")

    @patch.dict(os.environ, {"GITHUB_HEAD_REF": "feature/CTL-002-thing"}, clear=True)
    def test_extracts_from_github_head_ref_when_no_branch(self):
        args = self._args()
        self.assertEqual(lpt.resolve_task_id(args), "CTL-002")

    @patch.dict(os.environ, {"BUILD_SOURCEBRANCH": "refs/heads/T-09-azure"}, clear=True)
    def test_extracts_from_build_sourcebranch_when_no_branch_or_github_env(self):
        args = self._args()
        self.assertEqual(lpt.resolve_task_id(args), "T-09")

    @patch.dict(os.environ, {
        "GITHUB_HEAD_REF": "feature/T-01-thing",
        "BUILD_SOURCEBRANCH": "refs/heads/T-09-azure",
    }, clear=True)
    def test_github_head_ref_checked_before_build_sourcebranch(self):
        args = self._args()
        self.assertEqual(lpt.resolve_task_id(args), "T-01")

    @patch.dict(os.environ, {}, clear=True)
    def test_no_match_anywhere_returns_none(self):
        args = self._args()
        self.assertIsNone(lpt.resolve_task_id(args))


class TestMainDryRun(unittest.TestCase):
    def test_dry_run_never_calls_link_pr_apply_true(self):
        with TemporaryDirectory() as d:
            tasks_md = Path(d) / "tasks.md"
            tasks_md.write_text(TASKS_MD, encoding="utf-8")
            (Path(d) / ".aidd-issues.json").write_text(
                json.dumps({"T-01": "https://github.com/x/y/issues/1"}), encoding="utf-8",
            )
            calls = []
            registry = _fake_registry({"github": _provider(calls=calls)})
            with patch.object(lpt, "extension_registry", registry), \
                 patch.object(sys, "argv", [
                     "link_pr_to_task.py", "--tasks-md", str(tasks_md), "--task-id", "T-01",
                 ]):
                with self.assertRaises(SystemExit) as cm:
                    lpt.main()
            self.assertEqual(cm.exception.code, 0)
            self.assertEqual(calls, [])
            self.assertEqual(tasks_md.read_text(encoding="utf-8"), TASKS_MD)

    def test_apply_without_pr_url_is_a_usage_error(self):
        with TemporaryDirectory() as d:
            tasks_md = Path(d) / "tasks.md"
            tasks_md.write_text(TASKS_MD, encoding="utf-8")
            registry = _fake_registry({"github": _provider()})
            with patch.object(lpt, "extension_registry", registry), \
                 patch.object(sys, "argv", [
                     "link_pr_to_task.py", "--tasks-md", str(tasks_md), "--task-id", "T-01", "--apply",
                 ]):
                with self.assertRaises(SystemExit) as cm:
                    lpt.main()
            self.assertEqual(cm.exception.code, 2)

    def test_unsynced_task_is_an_error(self):
        with TemporaryDirectory() as d:
            tasks_md = Path(d) / "tasks.md"
            tasks_md.write_text(TASKS_MD, encoding="utf-8")
            (Path(d) / ".aidd-issues.json").write_text(json.dumps({}), encoding="utf-8")
            registry = _fake_registry({"github": _provider()})
            with patch.object(lpt, "extension_registry", registry), \
                 patch.object(sys, "argv", [
                     "link_pr_to_task.py", "--tasks-md", str(tasks_md), "--task-id", "T-01",
                     "--pr-url", "https://github.com/x/y/pull/5", "--apply",
                 ]):
                with self.assertRaises(SystemExit) as cm:
                    lpt.main()
            self.assertEqual(cm.exception.code, 2)


class TestMainApply(unittest.TestCase):
    def test_apply_success_writes_tracker_ref_column(self):
        with TemporaryDirectory() as d:
            tasks_md = Path(d) / "tasks.md"
            tasks_md.write_text(TASKS_MD, encoding="utf-8")
            (Path(d) / ".aidd-issues.json").write_text(
                json.dumps({"T-01": "https://github.com/x/y/issues/1"}), encoding="utf-8",
            )
            calls = []
            registry = _fake_registry({"github": _provider(link_pr_result=True, calls=calls)})
            with patch.object(lpt, "extension_registry", registry), \
                 patch.object(sys, "argv", [
                     "link_pr_to_task.py", "--tasks-md", str(tasks_md), "--task-id", "T-01",
                     "--pr-url", "https://github.com/x/y/pull/5", "--apply",
                 ]):
                with self.assertRaises(SystemExit) as cm:
                    lpt.main()
            self.assertEqual(cm.exception.code, 0)
            self.assertEqual(calls, [("https://github.com/x/y/issues/1",
                                       "https://github.com/x/y/pull/5", True)])
            updated = tasks_md.read_text(encoding="utf-8")
            self.assertIn("https://github.com/x/y/pull/5", updated)

    def test_apply_failure_does_not_touch_tasks_md(self):
        with TemporaryDirectory() as d:
            tasks_md = Path(d) / "tasks.md"
            tasks_md.write_text(TASKS_MD, encoding="utf-8")
            (Path(d) / ".aidd-issues.json").write_text(
                json.dumps({"T-01": "https://github.com/x/y/issues/1"}), encoding="utf-8",
            )
            registry = _fake_registry({"github": _provider(link_pr_result=False)})
            with patch.object(lpt, "extension_registry", registry), \
                 patch.object(sys, "argv", [
                     "link_pr_to_task.py", "--tasks-md", str(tasks_md), "--task-id", "T-01",
                     "--pr-url", "https://github.com/x/y/pull/5", "--apply",
                 ]):
                with self.assertRaises(SystemExit) as cm:
                    lpt.main()
            self.assertEqual(cm.exception.code, 1)
            self.assertEqual(tasks_md.read_text(encoding="utf-8"), TASKS_MD)

    def test_apply_from_branch_task_id(self):
        with TemporaryDirectory() as d:
            tasks_md = Path(d) / "tasks.md"
            tasks_md.write_text(TASKS_MD, encoding="utf-8")
            (Path(d) / ".aidd-issues.json").write_text(
                json.dumps({"T-02": "https://github.com/x/y/issues/2"}), encoding="utf-8",
            )
            registry = _fake_registry({"github": _provider(link_pr_result=True)})
            with patch.object(lpt, "extension_registry", registry), \
                 patch.object(sys, "argv", [
                     "link_pr_to_task.py", "--tasks-md", str(tasks_md), "--branch", "feature/T-02-thing",
                     "--pr-url", "https://github.com/x/y/pull/9", "--apply",
                 ]):
                with self.assertRaises(SystemExit) as cm:
                    lpt.main()
            self.assertEqual(cm.exception.code, 0)
            updated = tasks_md.read_text(encoding="utf-8")
            self.assertIn("https://github.com/x/y/pull/9", updated)


if __name__ == "__main__":
    unittest.main()
