"""Tests for skill/hooks/*.py — stdlib unittest, no dependencies.

These are AIDD's actual technical differentiator (hard gates, not prose), so
they're tested the same way tasks_to_issues.py's CLI path already is: run the
real script as a subprocess, feed it the exact JSON event shape Claude Code
sends on stdin, and assert on exit code + stderr/stdout — not by importing
and monkeypatching internals, since every hook here runs its logic at module
scope on import (that's the actual contract Claude Code invokes), not inside
a function unit tests could call directly.

Each test uses its own random session_id so marker/timestamp files in the
shared MARKER_DIR (a real temp directory, by design — see _common.py) never
collide with another test or a real session, and tearDown removes exactly
the two files this session's tests could have created.

Run: python -m unittest discover -s tests -v
"""
import json
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent / "skill" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

import _common  # noqa: E402


def run_hook(name: str, event: dict, timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOKS_DIR / name)],
        input=json.dumps(event), capture_output=True, text=True, timeout=timeout,
    )


class HookTestCase(unittest.TestCase):
    """Base class: a fresh session_id per test, cleaned up afterward."""

    def setUp(self):
        self.session_id = f"test-{uuid.uuid4().hex}"

    def tearDown(self):
        _common.marker_path(self.session_id).unlink(missing_ok=True)
        _common.timestamps_path(self.session_id).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# _common.py — pure helper functions, imported directly
# ---------------------------------------------------------------------------


class TestIsCodeFile(unittest.TestCase):
    def test_recognized_extension_is_code(self):
        self.assertTrue(_common.is_code_file("src/app/main.dart"))
        self.assertTrue(_common.is_code_file("service.py"))

    def test_markdown_is_never_code(self):
        self.assertFalse(_common.is_code_file("plan.md"))

    def test_none_path_is_not_code(self):
        self.assertFalse(_common.is_code_file(None))

    def test_specs_folder_excluded_even_with_code_extension(self):
        self.assertFalse(_common.is_code_file("specs/001-login/helper.py"))

    def test_design_system_folder_excluded(self):
        self.assertFalse(_common.is_code_file("design-system/tokens.py"))

    def test_installed_skill_sources_excluded(self):
        self.assertFalse(_common.is_code_file(
            str(Path.home() / ".claude" / "skills" / "aidd" / "hooks" / "require_aidd.py")
        ))

    def test_unrelated_python_file_is_code(self):
        self.assertTrue(_common.is_code_file("app/services/order_service.py"))


class TestIsQaAuditFile(unittest.TestCase):
    def test_matches_by_filename_only(self):
        self.assertTrue(_common.is_qa_audit_file("specs/001-login/qa-audit.md"))

    def test_rejects_other_filenames(self):
        self.assertFalse(_common.is_qa_audit_file("specs/001-login/plan.md"))

    def test_none_path_is_false(self):
        self.assertFalse(_common.is_qa_audit_file(None))


class TestIsGraphConsumerFile(unittest.TestCase):
    def test_plan_and_tasks_match(self):
        self.assertTrue(_common.is_graph_consumer_file("specs/001-login/plan.md"))
        self.assertTrue(_common.is_graph_consumer_file("specs/001-login/tasks.md"))

    def test_other_files_do_not_match(self):
        self.assertFalse(_common.is_graph_consumer_file("specs/001-login/spec.md"))


class TestTimestamps(unittest.TestCase):
    def setUp(self):
        self.session_id = f"test-{uuid.uuid4().hex}"

    def tearDown(self):
        _common.timestamps_path(self.session_id).unlink(missing_ok=True)

    def test_write_then_read_round_trips(self):
        self.assertEqual(_common.read_timestamps(self.session_id), {})
        _common.write_timestamp(self.session_id, "last_code_edit_ts")
        data = _common.read_timestamps(self.session_id)
        self.assertIn("last_code_edit_ts", data)

    def test_corrupt_file_reads_as_empty_not_a_crash(self):
        path = _common.timestamps_path(self.session_id)
        path.write_text("not json", encoding="utf-8")
        self.assertEqual(_common.read_timestamps(self.session_id), {})


# ---------------------------------------------------------------------------
# require_aidd.py — PreToolUse(Write|Edit) hard gate
# ---------------------------------------------------------------------------


class TestRequireAidd(HookTestCase):
    def test_blocks_code_file_without_marker(self):
        result = run_hook("require_aidd.py", {
            "session_id": self.session_id,
            "tool_input": {"file_path": "src/app.py"},
        })
        self.assertEqual(result.returncode, 2)
        self.assertIn("has not been invoked", result.stderr)

    def test_allows_code_file_once_marker_exists(self):
        _common.marker_path(self.session_id).write_text("invoked", encoding="utf-8")
        result = run_hook("require_aidd.py", {
            "session_id": self.session_id,
            "tool_input": {"file_path": "src/app.py"},
        })
        self.assertEqual(result.returncode, 0)

    def test_never_blocks_markdown(self):
        result = run_hook("require_aidd.py", {
            "session_id": self.session_id,
            "tool_input": {"file_path": "specs/001-login/plan.md"},
        })
        self.assertEqual(result.returncode, 0)

    def test_never_blocks_specs_folder_even_with_code_extension(self):
        result = run_hook("require_aidd.py", {
            "session_id": self.session_id,
            "tool_input": {"file_path": "specs/001-login/check.py"},
        })
        self.assertEqual(result.returncode, 0)


# ---------------------------------------------------------------------------
# mark_invoked.py / session_start.py — marker lifecycle
# ---------------------------------------------------------------------------


class TestMarkInvoked(HookTestCase):
    def test_marks_session_when_skill_is_aidd(self):
        result = run_hook("mark_invoked.py", {
            "session_id": self.session_id,
            "tool_input": {"skill": "aidd"},
        })
        self.assertEqual(result.returncode, 0)
        self.assertTrue(_common.marker_path(self.session_id).exists())

    def test_ignores_other_skills(self):
        result = run_hook("mark_invoked.py", {
            "session_id": self.session_id,
            "tool_input": {"skill": "some-other-skill"},
        })
        self.assertEqual(result.returncode, 0)
        self.assertFalse(_common.marker_path(self.session_id).exists())

    def test_case_insensitive_match(self):
        run_hook("mark_invoked.py", {
            "session_id": self.session_id,
            "tool_input": {"skill": "AIDD"},
        })
        self.assertTrue(_common.marker_path(self.session_id).exists())


class TestSessionStart(HookTestCase):
    def test_removes_existing_marker(self):
        _common.marker_path(self.session_id).write_text("invoked", encoding="utf-8")
        result = run_hook("session_start.py", {"session_id": self.session_id})
        self.assertEqual(result.returncode, 0)
        self.assertFalse(_common.marker_path(self.session_id).exists())

    def test_no_error_when_marker_absent(self):
        result = run_hook("session_start.py", {"session_id": self.session_id})
        self.assertEqual(result.returncode, 0)


# ---------------------------------------------------------------------------
# mark_code_edit.py / mark_agent_dispatch.py / mark_graph_rebuild.py — timestamps
# ---------------------------------------------------------------------------


class TestMarkCodeEdit(HookTestCase):
    def test_records_timestamp_for_code_file(self):
        run_hook("mark_code_edit.py", {
            "session_id": self.session_id,
            "tool_input": {"file_path": "src/app.py"},
        })
        self.assertIn("last_code_edit_ts", _common.read_timestamps(self.session_id))

    def test_does_not_record_for_markdown(self):
        run_hook("mark_code_edit.py", {
            "session_id": self.session_id,
            "tool_input": {"file_path": "spec.md"},
        })
        self.assertNotIn("last_code_edit_ts", _common.read_timestamps(self.session_id))


class TestMarkAgentDispatch(HookTestCase):
    def test_always_records_timestamp(self):
        result = run_hook("mark_agent_dispatch.py", {"session_id": self.session_id})
        self.assertEqual(result.returncode, 0)
        self.assertIn("last_agent_dispatch_ts", _common.read_timestamps(self.session_id))


class TestMarkGraphRebuild(HookTestCase):
    def test_records_on_rebuilt_output(self):
        run_hook("mark_graph_rebuild.py", {
            "session_id": self.session_id,
            "tool_input": {"command": "python scripts/find_spec.py login"},
            "tool_response": {"stdout": "Graph index: rebuilt\n1 spec found"},
        })
        self.assertIn("last_graph_rebuild_ts", _common.read_timestamps(self.session_id))

    def test_ignores_cache_hit_output(self):
        run_hook("mark_graph_rebuild.py", {
            "session_id": self.session_id,
            "tool_input": {"command": "python scripts/find_spec.py login"},
            "tool_response": {"stdout": "Graph index: unchanged (cache hit)"},
        })
        self.assertNotIn("last_graph_rebuild_ts", _common.read_timestamps(self.session_id))

    def test_ignores_unrelated_commands(self):
        run_hook("mark_graph_rebuild.py", {
            "session_id": self.session_id,
            "tool_input": {"command": "ls -la"},
            "tool_response": {"stdout": "Graph index: rebuilt"},
        })
        self.assertNotIn("last_graph_rebuild_ts", _common.read_timestamps(self.session_id))


# ---------------------------------------------------------------------------
# require_independent_audit.py — the Step 6 gate
# ---------------------------------------------------------------------------


class TestRequireIndependentAudit(HookTestCase):
    def _write_ts(self, **kwargs):
        path = _common.timestamps_path(self.session_id)
        path.write_text(json.dumps(kwargs), encoding="utf-8")

    def test_ignores_non_qa_audit_files(self):
        result = run_hook("require_independent_audit.py", {
            "session_id": self.session_id,
            "tool_input": {"file_path": "plan.md"},
        })
        self.assertEqual(result.returncode, 0)

    def test_allows_baseline_write_with_no_code_edit_yet(self):
        result = run_hook("require_independent_audit.py", {
            "session_id": self.session_id,
            "tool_input": {"file_path": "specs/001/qa-audit.md"},
        })
        self.assertEqual(result.returncode, 0)

    def test_blocks_when_code_edited_but_no_dispatch(self):
        self._write_ts(last_code_edit_ts=100.0)
        result = run_hook("require_independent_audit.py", {
            "session_id": self.session_id,
            "tool_input": {"file_path": "specs/001/qa-audit.md"},
        })
        self.assertEqual(result.returncode, 2)
        self.assertIn("must never be the same agent", result.stderr)

    def test_blocks_when_dispatch_happened_before_edit(self):
        self._write_ts(last_code_edit_ts=100.0, last_agent_dispatch_ts=50.0)
        result = run_hook("require_independent_audit.py", {
            "session_id": self.session_id,
            "tool_input": {"file_path": "specs/001/qa-audit.md"},
        })
        self.assertEqual(result.returncode, 2)

    def test_allows_when_dispatch_happened_after_edit(self):
        self._write_ts(last_code_edit_ts=100.0, last_agent_dispatch_ts=150.0)
        result = run_hook("require_independent_audit.py", {
            "session_id": self.session_id,
            "tool_input": {"file_path": "specs/001/qa-audit.md"},
        })
        self.assertEqual(result.returncode, 0)


# ---------------------------------------------------------------------------
# require_graph_coherence_audit.py — the Step 3/4 gate, same shape one step earlier
# ---------------------------------------------------------------------------


class TestRequireGraphCoherenceAudit(HookTestCase):
    def _write_ts(self, **kwargs):
        path = _common.timestamps_path(self.session_id)
        path.write_text(json.dumps(kwargs), encoding="utf-8")

    def test_ignores_files_other_than_plan_or_tasks(self):
        result = run_hook("require_graph_coherence_audit.py", {
            "session_id": self.session_id,
            "tool_input": {"file_path": "spec.md"},
        })
        self.assertEqual(result.returncode, 0)

    def test_allows_when_no_rebuild_this_session(self):
        result = run_hook("require_graph_coherence_audit.py", {
            "session_id": self.session_id,
            "tool_input": {"file_path": "plan.md"},
        })
        self.assertEqual(result.returncode, 0)

    def test_blocks_when_rebuilt_but_no_dispatch(self):
        self._write_ts(last_graph_rebuild_ts=100.0)
        result = run_hook("require_graph_coherence_audit.py", {
            "session_id": self.session_id,
            "tool_input": {"file_path": "tasks.md"},
        })
        self.assertEqual(result.returncode, 2)
        self.assertIn("Graph Coherence Auditor", result.stderr)

    def test_allows_when_dispatch_after_rebuild(self):
        self._write_ts(last_graph_rebuild_ts=100.0, last_agent_dispatch_ts=150.0)
        result = run_hook("require_graph_coherence_audit.py", {
            "session_id": self.session_id,
            "tool_input": {"file_path": "plan.md"},
        })
        self.assertEqual(result.returncode, 0)


# ---------------------------------------------------------------------------
# prompt_trigger.py — UserPromptSubmit early nudge
# ---------------------------------------------------------------------------


class TestPromptTrigger(unittest.TestCase):
    def test_fires_on_change_language(self):
        result = run_hook("prompt_trigger.py", {
            "prompt": "necesito modificar la pantalla de login",
            "cwd": str(Path(__file__).resolve().parent),
        })
        self.assertEqual(result.returncode, 0)
        self.assertIn("[aidd]", result.stdout)

    def test_silent_on_unrelated_prompt(self):
        result = run_hook("prompt_trigger.py", {
            "prompt": "what's the weather like today",
            "cwd": str(Path(__file__).resolve().parent),
        })
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_fires_on_english_bug_language(self):
        result = run_hook("prompt_trigger.py", {
            "prompt": "there's a bug in the checkout flow, please fix it",
            "cwd": str(Path(__file__).resolve().parent),
        })
        self.assertIn("[aidd]", result.stdout)


if __name__ == "__main__":
    unittest.main()
