"""Tests for scripts/install_hooks.py — stdlib unittest, no dependencies.

Never touches the real ~/.claude/settings.json: every test monkeypatches
install_hooks.SETTINGS_PATH to a path inside a TemporaryDirectory first.
"""
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import install_hooks  # noqa: E402


class TestInstallHooks(unittest.TestCase):
    def test_creates_settings_with_every_hook_when_absent(self):
        with TemporaryDirectory() as d:
            settings_path = Path(d) / "settings.json"
            with patch.object(install_hooks, "SETTINGS_PATH", settings_path):
                install_hooks.main()
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            event_names = {name for name, _, _ in install_hooks.HOOK_DEFS}
            self.assertEqual(set(settings["hooks"].keys()), event_names)
            total_entries = sum(len(v) for v in settings["hooks"].values())
            self.assertEqual(total_entries, len(install_hooks.HOOK_DEFS))

    def test_idempotent_second_run_adds_nothing(self):
        with TemporaryDirectory() as d:
            settings_path = Path(d) / "settings.json"
            with patch.object(install_hooks, "SETTINGS_PATH", settings_path):
                install_hooks.main()
                first = settings_path.read_text(encoding="utf-8")
                install_hooks.main()
                second = settings_path.read_text(encoding="utf-8")
            self.assertEqual(first, second)

    def test_never_touches_unrelated_existing_hooks(self):
        with TemporaryDirectory() as d:
            settings_path = Path(d) / "settings.json"
            settings_path.write_text(json.dumps({
                "hooks": {
                    "SessionStart": [
                        {"hooks": [{"type": "command", "command": "python \"/some/other/tool.py\""}]}
                    ]
                },
                "unrelatedTopLevelKey": True,
            }), encoding="utf-8")
            with patch.object(install_hooks, "SETTINGS_PATH", settings_path):
                install_hooks.main()
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertTrue(settings["unrelatedTopLevelKey"])
            session_start_commands = {
                h.get("command")
                for entry in settings["hooks"]["SessionStart"]
                for h in entry.get("hooks", [])
            }
            self.assertIn('python "/some/other/tool.py"', session_start_commands)
            self.assertTrue(any("session_start.py" in c for c in session_start_commands))

    def test_invalid_existing_json_is_left_untouched(self):
        with TemporaryDirectory() as d:
            settings_path = Path(d) / "settings.json"
            settings_path.write_text("{not valid json", encoding="utf-8")
            with patch.object(install_hooks, "SETTINGS_PATH", settings_path):
                with self.assertRaises(SystemExit) as cm:
                    install_hooks.main()
            self.assertEqual(cm.exception.code, 1)
            self.assertEqual(settings_path.read_text(encoding="utf-8"), "{not valid json")

    def test_registers_ten_hooks_with_session_memory_only_by_default(self):
        self.assertEqual(len(install_hooks.HOOK_DEFS), 10)
        with TemporaryDirectory() as d:
            settings_path = Path(d) / "settings.json"
            with patch.object(install_hooks, "SETTINGS_PATH", settings_path):
                install_hooks.main([])
                install_hooks.main([])
            hooks = json.loads(settings_path.read_text(encoding="utf-8"))["hooks"]
            self.assertEqual(sum(len(v) for v in hooks.values()), 10)
            commands = [h["command"] for v in hooks.values() for e in v for h in e["hooks"]]
            self.assertFalse(any("memory_file_context.py" in c for c in commands))
            ss = [e for e in hooks["SessionStart"]
                  if any("memory_context.py" in h["command"] for h in e["hooks"])]
            self.assertEqual(len(ss), 1)
            self.assertEqual(ss[0]["matcher"], "startup|resume|clear|compact")

    def test_file_context_hook_is_opt_in_and_idempotent(self):
        with TemporaryDirectory() as d:
            settings_path = Path(d) / "settings.json"
            with patch.object(install_hooks, "SETTINGS_PATH", settings_path):
                install_hooks.main([])
                install_hooks.main(["--with-memory-file-hook"])
                first = settings_path.read_text(encoding="utf-8")
                install_hooks.main(["--with-memory-file-hook"])
                second = settings_path.read_text(encoding="utf-8")
            self.assertEqual(first, second)
            hooks = json.loads(first)["hooks"]
            pt = [e for e in hooks["PreToolUse"]
                  if any("memory_file_context.py" in h["command"] for h in e["hooks"])]
            self.assertEqual(len(pt), 1)
            self.assertEqual(pt[0]["matcher"], "Read|Edit|Write")

    def test_default_run_does_not_remove_an_already_installed_file_hook(self):
        with TemporaryDirectory() as d:
            settings_path = Path(d) / "settings.json"
            with patch.object(install_hooks, "SETTINGS_PATH", settings_path):
                install_hooks.main(["--with-memory-file-hook"])
                install_hooks.main([])
            hooks = json.loads(settings_path.read_text(encoding="utf-8"))["hooks"]
            self.assertEqual(sum(len(v) for v in hooks.values()), 11)

    def test_command_for_quotes_the_path(self):
        result = install_hooks.command_for(Path("/some/dir/hook.py"))
        self.assertTrue(result.startswith('python "'))
        self.assertTrue(result.endswith('"'))


if __name__ == "__main__":
    unittest.main()
