"""R9: host transcripts (.claude/projects/<proj>/<session>.jsonl) are not agent-writable, including via scripts."""
import unittest

from tests.gate_fixtures import Base

T = r"C:\Users\u\.claude\projects\P\S.jsonl"


class TranscriptGuard(Base):
    def ps(self, command):
        return self.run_hook("rule_gate.py", {"session_id": self.session, "cwd": str(self.root),
                                              "hook_event_name": "PreToolUse", "tool_name": "PowerShell",
                                              "tool_input": {"command": command}})

    # ---- blocked
    def test_python_open_append(self):
        self.assertBlocked(self.bash(f"python -c \"open(r'{T}','a').write('x')\""))

    def test_path_assembled_then_add_content(self):
        self.assertBlocked(self.ps("$p = Join-Path $env:USERPROFILE '.claude' ; "
                                   "Add-Content -Path ($p + '\\projects\\P\\S.jsonl') -Value x"))
        self.assertBlocked(self.ps("$d='.claude'; $f='\\projects\\P\\S' + '.jsonl'; Add-Content ($d+$f) x"))

    def test_write_tool(self):
        self.assertBlocked(self.gate(T, tool="Write", content="x"))

    def test_edit_tool(self):
        self.assertBlocked(self.gate(T, tool="Edit", old_string="a", new_string="b"))

    def test_set_content(self):
        self.assertBlocked(self.ps(f"Set-Content -Path '{T}' -Value x"))

    def test_redirect_append(self):
        self.assertBlocked(self.bash(f"echo x >> '{T}'"))

    def test_copy_item_onto(self):
        self.assertBlocked(self.ps(f"Copy-Item fake.jsonl '{T}'"))

    def test_ads_alias(self):
        self.assertBlocked(self.ps(f"Set-Content -Path '{T}::$DATA' -Value x"))
        self.assertBlocked(self.gate(T + "::$DATA", tool="Write", content="x"))

    # ---- allowed
    def test_reads_allowed(self):
        self.assertAllowed(self.ps(f"Select-String -Path '{T}' -Pattern approve"))
        self.assertAllowed(self.ps(f"Get-Content '{T}' -Tail 5"))
        self.assertAllowed(self.bash(f"python -c \"print(open(r'{T}').read())\""))
        self.assertAllowed(self.bash(f"python -c \"print(open(r'{T}','r').read())\""))
        self.assertAllowed(self.bash(f"grep approve '{T}'"))
        self.assertAllowed(self.bash(f"head -n 3 '{T}'"))
        self.assertAllowed(self.bash(f"cat '{T}'"))
        self.assertAllowed(self.ps(f"type '{T}'"))

    def test_unrelated_writes_allowed(self):
        other = str(self.root / "out" / "log.jsonl")
        self.assertAllowed(self.gate(other, tool="Write", content="x"))
        self.assertAllowed(self.ps(f"Add-Content -Path '{other}' -Value x"))
        s = r"C:\Users\u\.claude\settings.local.json"
        self.assertAllowed(self.gate(s, tool="Write", content="{}"))
        self.assertAllowed(self.ps(f"Set-Content -Path '{s}' -Value '{{}}'"))


if __name__ == "__main__":
    unittest.main()
