"""Tests for skill/scripts/sync_issues.py — stdlib unittest, no dependencies.

Never touches a real tracker: provider modules are fake, in-memory
SimpleNamespace-style objects injected via
unittest.mock.patch.object(sync_issues, 'extension_registry', ...), the same
"mock everything that would cross a process/network boundary" discipline
test_tasks_to_issues.py and test_extension_providers.py already use.
"""
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import sync_issues  # noqa: E402
import tasks_to_issues as t2i  # noqa: E402

TASKS_MD = """# Tasks — example

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | New view vs. reuse | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-01 | CTL-004 | session_provider.dart | reuse logic only | https://github.com/x/y/issues/1 | open | any other file |
| T-02 | CTL-007 | session_provider.dart | reuse logic only | https://github.com/x/y/issues/2 | open | any other file |
"""


def _fake_registry(providers):
    """A stand-in for extension_registry exposing only what sync_issues uses:
    get_providers(project_root) -> {id: module}."""
    ns = types.SimpleNamespace()
    ns.get_providers = lambda project_root: providers
    return ns


def _v2_provider(status_by_ref):
    mod = types.ModuleType("fake_v2_provider")
    mod.add_provider_args = lambda parser: None
    mod.get_status = lambda ref, args: status_by_ref.get(ref)
    mod.link_pr = lambda ref, pr_url, args, apply: False
    return mod


def _v1_only_provider():
    mod = types.ModuleType("fake_v1_provider")
    mod.add_provider_args = lambda parser: None
    # deliberately no get_status/link_pr — the v1 shape
    return mod


class TestCurrentStatus(unittest.TestCase):
    def test_reads_existing_status_cell(self):
        self.assertEqual(sync_issues.current_status(TASKS_MD, "T-01"), "open")

    def test_missing_row_is_empty_string(self):
        self.assertEqual(sync_issues.current_status(TASKS_MD, "T-99"), "")

    def test_missing_status_column_is_empty_string(self):
        old_shape = (
            "| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | "
            "New view vs. reuse | Explicitly out of scope |\n"
            "|---|---|---|---|---|\n"
            "| T-01 | CTL-004 | x | reuse logic only | any other file |\n"
        )
        self.assertEqual(sync_issues.current_status(old_shape, "T-01"), "")


class TestMainDryRun(unittest.TestCase):
    """No --apply here on purpose — must never write to tasks.md."""

    def test_dry_run_prints_diff_and_writes_nothing(self):
        with TemporaryDirectory() as d:
            tasks_md = Path(d) / "tasks.md"
            tasks_md.write_text(TASKS_MD, encoding="utf-8")
            provider = _v2_provider({
                "https://github.com/x/y/issues/1": "closed",
                "https://github.com/x/y/issues/2": "open",
            })
            registry = _fake_registry({"github": provider})
            with patch.object(sync_issues, "extension_registry", registry), \
                 patch.object(sys, "argv", ["sync_issues.py", str(tasks_md)]):
                with self.assertRaises(SystemExit) as cm:
                    sync_issues.main()
            self.assertEqual(cm.exception.code, 0)
            # Nothing written without --apply.
            self.assertEqual(tasks_md.read_text(encoding="utf-8"), TASKS_MD)

    def test_v1_only_provider_skips_without_crashing(self):
        with TemporaryDirectory() as d:
            tasks_md = Path(d) / "tasks.md"
            tasks_md.write_text(TASKS_MD, encoding="utf-8")
            registry = _fake_registry({"github": _v1_only_provider()})
            with patch.object(sync_issues, "extension_registry", registry), \
                 patch.object(sys, "argv", ["sync_issues.py", str(tasks_md)]):
                with self.assertRaises(SystemExit) as cm:
                    sync_issues.main()
            self.assertEqual(cm.exception.code, 0)

    def test_missing_sync_map_exits_cleanly(self):
        with TemporaryDirectory() as d:
            tasks_md = Path(d) / "tasks.md"
            tasks_md.write_text(TASKS_MD, encoding="utf-8")
            provider = _v2_provider({})
            registry = _fake_registry({"github": provider})
            with patch.object(sync_issues, "extension_registry", registry), \
                 patch.object(sys, "argv", ["sync_issues.py", str(tasks_md)]):
                with self.assertRaises(SystemExit) as cm:
                    sync_issues.main()
            self.assertEqual(cm.exception.code, 0)

    def test_missing_tasks_md_is_a_usage_error(self):
        registry = _fake_registry({"github": _v2_provider({})})
        with patch.object(sync_issues, "extension_registry", registry), \
             patch.object(sys, "argv", ["sync_issues.py", "/no/such/tasks.md"]):
            with self.assertRaises(SystemExit) as cm:
                sync_issues.main()
        self.assertEqual(cm.exception.code, 2)


class TestMainApply(unittest.TestCase):
    def test_apply_writes_changed_status_only_for_synced_rows(self):
        with TemporaryDirectory() as d:
            tasks_md = Path(d) / "tasks.md"
            tasks_md.write_text(TASKS_MD, encoding="utf-8")
            (Path(d) / ".aidd-issues.json").write_text(
                t2i.json.dumps({
                    "T-01": "https://github.com/x/y/issues/1",
                    "T-02": "https://github.com/x/y/issues/2",
                }), encoding="utf-8",
            )
            provider = _v2_provider({
                "https://github.com/x/y/issues/1": "closed",  # changes
                "https://github.com/x/y/issues/2": "open",    # unchanged
            })
            registry = _fake_registry({"github": provider})
            with patch.object(sync_issues, "extension_registry", registry), \
                 patch.object(sys, "argv", ["sync_issues.py", str(tasks_md), "--apply"]):
                with self.assertRaises(SystemExit) as cm:
                    sync_issues.main()
            self.assertEqual(cm.exception.code, 0)
            updated = tasks_md.read_text(encoding="utf-8")
            self.assertEqual(sync_issues.current_status(updated, "T-01"), "closed")
            self.assertEqual(sync_issues.current_status(updated, "T-02"), "open")

    def test_apply_never_touches_a_row_without_a_sync_map_entry(self):
        with_extra_row = TASKS_MD + "| T-03 | CTL-009 | other.dart | reuse logic only | | | any other file |\n"
        with TemporaryDirectory() as d:
            tasks_md = Path(d) / "tasks.md"
            tasks_md.write_text(with_extra_row, encoding="utf-8")
            (Path(d) / ".aidd-issues.json").write_text(
                t2i.json.dumps({"T-01": "https://github.com/x/y/issues/1"}), encoding="utf-8",
            )
            provider = _v2_provider({"https://github.com/x/y/issues/1": "closed"})
            registry = _fake_registry({"github": provider})
            with patch.object(sync_issues, "extension_registry", registry), \
                 patch.object(sys, "argv", ["sync_issues.py", str(tasks_md), "--apply"]):
                with self.assertRaises(SystemExit):
                    sync_issues.main()
            updated = tasks_md.read_text(encoding="utf-8")
            self.assertEqual(sync_issues.current_status(updated, "T-03"), "")


if __name__ == "__main__":
    unittest.main()
