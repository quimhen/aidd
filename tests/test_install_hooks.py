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


def command_old(script_name):
    """The command string older installers wrote for a legacy aidd gate."""
    return f'python "{Path.home()}/.claude/skills/aidd/hooks/{script_name}"'


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

    def test_registers_thirteen_hooks_with_session_memory_only_by_default(self):
        self.assertEqual(len(install_hooks.HOOK_DEFS), 13)
        with TemporaryDirectory() as d:
            settings_path = Path(d) / "settings.json"
            with patch.object(install_hooks, "SETTINGS_PATH", settings_path):
                install_hooks.main([])
                install_hooks.main([])
            hooks = json.loads(settings_path.read_text(encoding="utf-8"))["hooks"]
            self.assertEqual(sum(len(v) for v in hooks.values()), 13)
            rh = [e for e in hooks["PreToolUse"]
                  if any("read_hint.py" in h["command"] for h in e["hooks"])]
            self.assertEqual(len(rh), 1)
            self.assertEqual(rh[0]["matcher"], "Read")
            commands = [h["command"] for v in hooks.values() for e in v for h in e["hooks"]]
            self.assertFalse(any("memory_file_context.py" in c for c in commands))
            ss = [e for e in hooks["SessionStart"]
                  if any("memory_context.py" in h["command"] for h in e["hooks"])]
            self.assertEqual(len(ss), 1)
            self.assertEqual(ss[0]["matcher"], "startup|resume|clear|compact")

    def test_record_dispatch_pre_is_installed_once_and_idempotent(self):
        with TemporaryDirectory() as d:
            settings_path = Path(d) / "settings.json"
            with patch.object(install_hooks, "SETTINGS_PATH", settings_path):
                install_hooks.main([])
                first = settings_path.read_text(encoding="utf-8")
                install_hooks.main([])
                self.assertEqual(first, settings_path.read_text(encoding="utf-8"))
            pre = json.loads(first)["hooks"]["PreToolUse"]
            rd = [e for e in pre if any("record_dispatch_pre.py" in h["command"] for h in e["hooks"])]
            self.assertEqual([e["matcher"] for e in rd], ["Task|Agent"])
            self.assertEqual(rd[0]["hooks"][0]["timeout"], 10)

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
            rh = [e for e in hooks["PreToolUse"]
                  if any("read_hint.py" in h["command"] for h in e["hooks"])]
            self.assertEqual([e["matcher"] for e in rh], ["Read"])   # still there

    def test_default_run_does_not_remove_an_already_installed_file_hook(self):
        with TemporaryDirectory() as d:
            settings_path = Path(d) / "settings.json"
            with patch.object(install_hooks, "SETTINGS_PATH", settings_path):
                install_hooks.main(["--with-memory-file-hook"])
                install_hooks.main([])
            hooks = json.loads(settings_path.read_text(encoding="utf-8"))["hooks"]
            self.assertEqual(sum(len(v) for v in hooks.values()), 14)

    def test_default_set_is_rule_gate_plus_recorders_and_stop(self):
        names = sorted(p.name for _, _, p in install_hooks.HOOK_DEFS)
        self.assertEqual(names, sorted([
            "session_start.py", "mark_invoked.py", "rule_gate.py", "prompt_trigger.py",
            "mark_code_edit.py", "mark_agent_dispatch.py", "mark_graph_rebuild.py",
            "memory_context.py", "mark_user_question.py", "stop_gate.py", "read_hint.py",
            "record_dispatch_pre.py", "graph_refresh.py"]))
        by = {p.name: (e, m) for e, m, p in install_hooks.HOOK_DEFS}
        self.assertEqual(by["rule_gate.py"], ("PreToolUse", "Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell"))
        self.assertEqual(by["mark_code_edit.py"], ("PostToolUse", "Write|Edit|MultiEdit|NotebookEdit|PowerShell"))
        self.assertEqual(by["mark_user_question.py"], ("PostToolUse", "AskUserQuestion"))
        self.assertEqual(by["stop_gate.py"][0], "Stop")
        self.assertEqual(by["read_hint.py"], ("PreToolUse", "Read"))
        self.assertEqual(by["record_dispatch_pre.py"], ("PreToolUse", "Task|Agent"))
        self.assertEqual(by["mark_graph_rebuild.py"], ("PostToolUse", "Bash|PowerShell"))
        self.assertEqual(by["graph_refresh.py"], ("PostToolUse", "Write|Edit|MultiEdit|NotebookEdit"))

    def test_every_entry_has_a_timeout_15_for_gates_10_for_the_rest(self):
        with TemporaryDirectory() as d:
            settings_path = Path(d) / "settings.json"
            with patch.object(install_hooks, "SETTINGS_PATH", settings_path):
                install_hooks.main(["--with-memory-file-hook"])
            hooks = json.loads(settings_path.read_text(encoding="utf-8"))["hooks"]
            seen = 0
            for entries in hooks.values():
                for e in entries:
                    for h in e["hooks"]:
                        seen += 1
                        want = 15 if h["command"].rstrip('"').endswith(("rule_gate.py", "stop_gate.py")) else 10
                        self.assertEqual(h.get("timeout"), want, h["command"])
            self.assertEqual(seen, 14)

    def test_old_matcher_entries_are_upgraded_in_place_and_foreign_hooks_kept(self):
        gate = install_hooks.command_for(install_hooks.SKILL_DIR / "hooks" / "rule_gate.py")
        mark = install_hooks.command_for(install_hooks.SKILL_DIR / "hooks" / "mark_code_edit.py")
        foreign = 'python "/x/foreign.py"'
        with TemporaryDirectory() as d:
            settings_path = Path(d) / "settings.json"
            settings_path.write_text(json.dumps({"hooks": {
                "PreToolUse": [
                    {"matcher": "Write|Edit", "hooks": [{"type": "command", "command": gate},
                                                        {"type": "command", "command": foreign}]},
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": 'python "/x/guard.py"'}]}],
                "PostToolUse": [{"matcher": "Write|Edit", "hooks": [{"type": "command", "command": mark}]}],
            }}), encoding="utf-8")
            with patch.object(install_hooks, "SETTINGS_PATH", settings_path):
                install_hooks.main([])
                first = settings_path.read_text(encoding="utf-8")
                install_hooks.main([])
                second = settings_path.read_text(encoding="utf-8")
            self.assertEqual(first, second)                      # idempotent after the upgrade
            hooks = json.loads(first)["hooks"]
            gate_entries = [e for e in hooks["PreToolUse"] if any(h["command"] == gate for h in e["hooks"])]
            self.assertEqual(len(gate_entries), 1)
            self.assertEqual(gate_entries[0]["matcher"], "Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell")
            self.assertEqual(gate_entries[0]["hooks"][0]["timeout"], 15)
            self.assertEqual(len(gate_entries[0]["hooks"]), 1)
            cmds = [h["command"] for e in hooks["PreToolUse"] for h in e["hooks"]]
            self.assertIn(foreign, cmds)                         # the foreign hook sharing the old entry survives
            self.assertIn('python "/x/guard.py"', cmds)
            foreign_entry = [e for e in hooks["PreToolUse"] if any(h["command"] == foreign for h in e["hooks"])][0]
            self.assertEqual(foreign_entry["matcher"], "Write|Edit")   # ...with its own, untouched matcher
            mark_entries = [e for e in hooks["PostToolUse"] if any(h["command"] == mark for h in e["hooks"])]
            self.assertEqual([e["matcher"] for e in mark_entries], ["Write|Edit|MultiEdit|NotebookEdit|PowerShell"])
            self.assertEqual(mark_entries[0]["hooks"][0]["timeout"], 10)
            self.assertEqual(sum(len(v) for v in hooks.values()) >= 10, True)

    def test_rev1_matcher_entries_are_upgraded_to_include_powershell(self):
        """An installation made by the previous version (Bash only) is upgraded in place, not duplicated."""
        old = {"PreToolUse": ("Write|Edit|MultiEdit|NotebookEdit|Bash", "rule_gate.py", 15),
               "PostToolUse": ("Bash", "mark_graph_rebuild.py", 10)}
        with TemporaryDirectory() as d:
            settings_path = Path(d) / "settings.json"
            hooks = {}
            for ev_name, (matcher, script, to) in old.items():
                cmd = install_hooks.command_for(install_hooks.SKILL_DIR / "hooks" / script)
                hooks[ev_name] = [{"matcher": matcher, "hooks": [{"type": "command", "command": cmd, "timeout": to}]}]
            settings_path.write_text(json.dumps({"hooks": hooks}), encoding="utf-8")
            with patch.object(install_hooks, "SETTINGS_PATH", settings_path):
                install_hooks.main([])
                first = settings_path.read_text(encoding="utf-8")
                install_hooks.main([])
                self.assertEqual(first, settings_path.read_text(encoding="utf-8"))
            got = json.loads(first)["hooks"]
            gate = [e for e in got["PreToolUse"] if any("rule_gate.py" in h["command"] for h in e["hooks"])]
            graph = [e for e in got["PostToolUse"] if any("mark_graph_rebuild.py" in h["command"] for h in e["hooks"])]
            self.assertEqual([e["matcher"] for e in gate], ["Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell"])
            self.assertEqual([e["matcher"] for e in graph], ["Bash|PowerShell"])

    def test_entry_with_right_matcher_but_no_timeout_gets_the_timeout(self):
        stop = install_hooks.command_for(install_hooks.SKILL_DIR / "hooks" / "stop_gate.py")
        with TemporaryDirectory() as d:
            settings_path = Path(d) / "settings.json"
            settings_path.write_text(json.dumps({"hooks": {"Stop": [
                {"hooks": [{"type": "command", "command": stop}]}]}}), encoding="utf-8")
            with patch.object(install_hooks, "SETTINGS_PATH", settings_path):
                install_hooks.main([])
            stops = json.loads(settings_path.read_text(encoding="utf-8"))["hooks"]["Stop"]
            self.assertEqual(len(stops), 1)
            self.assertEqual(stops[0]["hooks"][0]["timeout"], 15)

    def test_migration_removes_old_gates_keeps_foreign_hooks_and_is_idempotent(self):
        old = [("require_aidd.py", "Write|Edit"), ("require_independent_audit.py", "Write|Edit"),
               ("require_graph_coherence_audit.py", "Write|Edit")]
        foreign_pre = {"matcher": "Bash", "hooks": [{"type": "command", "command": 'python "/x/guard.py"'}]}
        # a foreign hook whose command merely resembles an old name must survive
        lookalike = {"matcher": "Write", "hooks": [{"type": "command", "command": 'python "/x/my_require_aidd.py.bak"'}]}
        mixed = {"matcher": "Write|Edit", "hooks": [
            {"type": "command", "command": command_old(old[0][0])},
            {"type": "command", "command": 'python "/x/keep_me.py"'}]}
        with TemporaryDirectory() as d:
            settings_path = Path(d) / "settings.json"
            settings_path.write_text(json.dumps({"hooks": {"PreToolUse": [
                foreign_pre, lookalike, mixed,
                {"matcher": "Write|Edit", "hooks": [{"type": "command", "command": command_old(old[1][0])}]},
                {"matcher": "Write|Edit", "hooks": [{"type": "command", "command": command_old(old[2][0])}]},
            ]}, "keep": 1}), encoding="utf-8")
            with patch.object(install_hooks, "SETTINGS_PATH", settings_path):
                install_hooks.main([])
                first = settings_path.read_text(encoding="utf-8")
                install_hooks.main([])
                second = settings_path.read_text(encoding="utf-8")
            self.assertEqual(first, second)
            settings = json.loads(first)
            self.assertEqual(settings["keep"], 1)
            cmds = [h["command"] for e in settings["hooks"]["PreToolUse"] for h in e["hooks"]]
            for name, _ in old:
                self.assertFalse(any(c.rstrip('"').endswith("/" + name) or c.rstrip('"').endswith("\\" + name)
                                     for c in cmds), name)
            self.assertIn('python "/x/guard.py"', cmds)
            self.assertIn('python "/x/keep_me.py"', cmds)
            self.assertIn('python "/x/my_require_aidd.py.bak"', cmds)
            self.assertEqual(sum("rule_gate.py" in c for c in cmds), 1)
            self.assertEqual(sum("read_hint.py" in c for c in cmds), 1)
            # 3 foreign/kept + rule_gate + read_hint + record_dispatch_pre
            self.assertEqual(len(cmds), 6)

    def test_migration_only_run_reports_change_and_prunes_empty_events(self):
        with TemporaryDirectory() as d:
            settings_path = Path(d) / "settings.json"
            settings_path.write_text(json.dumps({"hooks": {"Stop": [
                {"hooks": [{"type": "command", "command": command_old("require_aidd.py")}]}]}}), encoding="utf-8")
            r = install_hooks.remove_legacy(json.loads(settings_path.read_text(encoding="utf-8")))
            self.assertEqual(r, 1)

    def test_command_for_quotes_the_path(self):
        result = install_hooks.command_for(Path("/some/dir/hook.py"))
        self.assertTrue(result.startswith('python "'))
        self.assertTrue(result.endswith('"'))


if __name__ == "__main__":
    unittest.main()
