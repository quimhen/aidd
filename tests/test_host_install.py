"""T-07 — installer tests (FR-901..903, AC-005). stdlib unittest.

CLI contract assumed (plan Interface 2):
  python skill/scripts/install_host.py install <host> <project-root> [--force]
Each processed file is reported on stdout as a line holding the word
`created`/`unchanged`/`skipped`/... and the file's path (any order).
Exit code 0 on success, including when files are skipped.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INSTALLER = REPO / "skill" / "scripts" / "install_host.py"


def install(host, root, force=False):
    cmd = [sys.executable, str(INSTALLER), "install", host, str(root)]
    if force:
        cmd.append("--force")
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")


def snapshot(root):
    snap = {}
    for p in Path(root).rglob("*"):
        if p.is_file():
            snap[p.relative_to(root).as_posix()] = (p.read_bytes(), p.stat().st_mtime_ns)
    return snap


def lines_with(out, name):
    name = name.replace("\\", "/")
    return [ln for ln in out.replace("\\", "/").splitlines() if name in ln]


class HostInstallBase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name)

    def ok(self, r):
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout + r.stderr


class TestGeminiInstall(HostInstallBase):
    def test_fresh_install_files(self):
        self.ok(install("gemini", self.root))
        self.assertTrue((self.root / ".aidd" / "CORE.md").is_file())
        self.assertTrue((self.root / ".aidd" / "hooks" / "host_adapter.py").is_file())
        gm = (self.root / "GEMINI.md").read_text(encoding="utf-8")
        self.assertIn("@.aidd/CORE.md", gm)

    def test_settings_registration(self):
        self.ok(install("gemini", self.root))
        s = json.loads((self.root / ".gemini" / "settings.json").read_text(encoding="utf-8"))
        before = json.dumps(s["hooks"]["BeforeTool"])
        after = json.dumps(s["hooks"]["AfterTool"])
        self.assertIn("aidd-gate", before)
        self.assertIn("aidd-record", after)
        self.assertIn("host_adapter.py gemini pre", before)
        self.assertIn("host_adapter.py gemini post", after)

    def test_second_run_unchanged(self):
        self.ok(install("gemini", self.root))
        before = snapshot(self.root)
        out = self.ok(install("gemini", self.root))
        self.assertEqual(before, snapshot(self.root), "second run changed bytes or mtime")
        for rel in (".aidd/CORE.md", ".aidd/hooks/host_adapter.py", "GEMINI.md"):
            ls = lines_with(out, rel)
            self.assertTrue(ls, f"{rel} not reported")
            self.assertTrue(all("unchanged" in ln for ln in ls), ls)
        self.assertFalse([ln for ln in out.splitlines() if ln.lstrip().startswith("skipped")],
                         "second run must not skip any file")

    def test_modified_skipped_then_force(self):
        self.ok(install("gemini", self.root))
        core = self.root / ".aidd" / "CORE.md"
        original = core.read_bytes()
        core.write_text("my local edit\n", encoding="utf-8")
        out = self.ok(install("gemini", self.root))
        self.assertEqual(core.read_text(encoding="utf-8"), "my local edit\n")
        self.assertTrue(any("skipped" in ln for ln in lines_with(out, ".aidd/CORE.md")), out)
        self.ok(install("gemini", self.root, force=True))
        self.assertEqual(core.read_bytes(), original)

    def test_foreign_hooks_survive(self):
        gdir = self.root / ".gemini"
        gdir.mkdir()
        foreign = {"name": "other-hook", "type": "command", "command": "echo hi"}
        settings = {
            "theme": "dark",
            "hooks": {"BeforeTool": [{"matcher": "x", "hooks": [foreign]}]},
        }
        (gdir / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        self.ok(install("gemini", self.root))
        self.ok(install("gemini", self.root, force=True))
        s = json.loads((gdir / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(s["theme"], "dark")
        before = json.dumps(s["hooks"]["BeforeTool"])
        self.assertIn("other-hook", before)
        self.assertIn("aidd-gate", before)
        self.assertEqual(before.count("aidd-gate"), 1)
        self.assertEqual(json.dumps(s["hooks"]["AfterTool"]).count("aidd-record"), 1)

    def test_f4_mixed_group_keeps_foreign_matcher_and_aidd_gets_own_group(self):
        gdir = self.root / ".gemini"
        gdir.mkdir()
        foreign = {"name": "other-hook", "type": "command", "command": "echo hi"}
        old_aidd = {"name": "aidd-gate", "type": "command", "command": "python old/host_adapter.py gemini pre"}
        settings = {"hooks": {"BeforeTool": [{"matcher": "foreign_matcher", "hooks": [foreign, old_aidd]}]}}
        (gdir / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        self.ok(install("gemini", self.root))

        def groups():
            s = json.loads((gdir / "settings.json").read_text(encoding="utf-8"))
            return s["hooks"]["BeforeTool"]
        gs = groups()
        fgroups = [g for g in gs if "other-hook" in json.dumps(g)]
        agroups = [g for g in gs if "aidd-gate" in json.dumps(g)]
        self.assertEqual(len(fgroups), 1, gs)
        self.assertEqual(fgroups[0]["matcher"], "foreign_matcher")
        self.assertEqual(len(agroups), 1, gs)
        self.assertIsNot(fgroups[0], agroups[0])
        self.assertNotEqual(agroups[0]["matcher"], "foreign_matcher")
        self.assertNotIn("other-hook", json.dumps(agroups[0]))
        self.assertNotIn("aidd-gate", json.dumps(fgroups[0]))
        before = snapshot(self.root)
        self.ok(install("gemini", self.root))
        self.assertEqual(groups(), gs, "second run must not change the hook groups")
        self.assertEqual(before[".gemini/settings.json"][0],
                         snapshot(self.root)[".gemini/settings.json"][0])

    def test_corrupt_settings_not_overwritten(self):
        gdir = self.root / ".gemini"
        gdir.mkdir()
        bad = "{ this is not json"
        (gdir / "settings.json").write_text(bad, encoding="utf-8")
        for force in (False, True):
            out = self.ok(install("gemini", self.root, force=force))
            self.assertEqual((gdir / "settings.json").read_text(encoding="utf-8"), bad)
            self.assertTrue(
                any("skipped" in ln for ln in lines_with(out, "settings.json")), out)


class TestOpencodeInstall(HostInstallBase):
    def test_fresh_install_files(self):
        self.ok(install("opencode", self.root))
        self.assertTrue((self.root / ".aidd" / "CORE.md").is_file())
        self.assertTrue((self.root / ".aidd" / "hooks" / "host_adapter.py").is_file())
        self.assertTrue((self.root / ".opencode" / "skills" / "aidd" / "SKILL.md").is_file())
        self.assertTrue((self.root / ".opencode" / "plugins" / "aidd.js").is_file())
        cfg = json.loads((self.root / ".opencode" / "opencode.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["plugin"].count(".opencode/plugins/aidd.js"), 1)

    def test_second_run_unchanged(self):
        self.ok(install("opencode", self.root))
        before = snapshot(self.root)
        out = self.ok(install("opencode", self.root))
        self.assertEqual(before, snapshot(self.root))
        for rel in (".opencode/skills/aidd/SKILL.md", ".opencode/plugins/aidd.js"):
            ls = lines_with(out, rel)
            self.assertTrue(ls, f"{rel} not reported")
            self.assertTrue(all("unchanged" in ln for ln in ls), ls)

    def test_modified_plugin_skipped_then_force(self):
        self.ok(install("opencode", self.root))
        plug = self.root / ".opencode" / "plugins" / "aidd.js"
        original = plug.read_bytes()
        plug.write_text("// tampered\n", encoding="utf-8")
        out = self.ok(install("opencode", self.root))
        self.assertEqual(plug.read_text(encoding="utf-8"), "// tampered\n")
        self.assertTrue(any("skipped" in ln for ln in lines_with(out, "aidd.js")), out)
        self.ok(install("opencode", self.root, force=True))
        self.assertEqual(plug.read_bytes(), original)

    def test_ac005_existing_plugins_merged_once(self):
        odir = self.root / ".opencode"
        odir.mkdir()
        cfg = {
            "$schema": "https://opencode.ai/config.json",
            "model": "x/y",
            "plugin": [".opencode/plugins/graphify.js", ".opencode/plugins/aidd.js"],
        }
        (odir / "opencode.json").write_text(json.dumps(cfg), encoding="utf-8")
        for force in (False, True):
            self.ok(install("opencode", self.root, force=force))
            got = json.loads((odir / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(got["plugin"].count(".opencode/plugins/graphify.js"), 1)
            self.assertEqual(got["plugin"].count(".opencode/plugins/aidd.js"), 1)
            self.assertEqual(got["model"], "x/y")

    def test_graphify_only_gets_aidd_appended(self):
        odir = self.root / ".opencode"
        odir.mkdir()
        (odir / "opencode.json").write_text(
            json.dumps({"plugin": [".opencode/plugins/graphify.js"]}), encoding="utf-8")
        self.ok(install("opencode", self.root))
        got = json.loads((odir / "opencode.json").read_text(encoding="utf-8"))
        self.assertEqual(got["plugin"].count(".opencode/plugins/graphify.js"), 1)
        self.assertEqual(got["plugin"].count(".opencode/plugins/aidd.js"), 1)

    def test_corrupt_opencode_json_not_overwritten(self):
        odir = self.root / ".opencode"
        odir.mkdir()
        bad = "{ nope"
        (odir / "opencode.json").write_text(bad, encoding="utf-8")
        out = self.ok(install("opencode", self.root, force=True))
        self.assertEqual((odir / "opencode.json").read_text(encoding="utf-8"), bad)
        self.assertTrue(any("skipped" in ln for ln in lines_with(out, "opencode.json")), out)


class TestNeverDeletes(HostInstallBase):
    def test_memory_and_evidence_survive(self):
        for host in ("gemini", "opencode"):
            with self.subTest(host=host):
                self.ok(install(host, self.root))
                mem = self.root / ".aidd" / "memory" / "note.md"
                ev = self.root / ".aidd" / "evidence" / "run-1" / "result.txt"
                mem.parent.mkdir(parents=True, exist_ok=True)
                ev.parent.mkdir(parents=True, exist_ok=True)
                mem.write_text("keep me", encoding="utf-8")
                ev.write_text("evidence", encoding="utf-8")
                self.ok(install(host, self.root))
                self.ok(install(host, self.root, force=True))
                self.assertEqual(mem.read_text(encoding="utf-8"), "keep me")
                self.assertEqual(ev.read_text(encoding="utf-8"), "evidence")


# ---------------------------------------------------------------- spec 011 (T-07)
import os
import shutil

HOOKS_CMD = "python ../.aidd/hooks/host_adapter.py antigravity {}"


def expected_aidd_entry():
    def grp(kind):
        return [{"matcher": "*", "hooks": [{"type": "command",
                                            "command": HOOKS_CMD.format(kind), "timeout": 30}]}]
    return {"enabled": True, "PreToolUse": grp("pre"), "PostToolUse": grp("post")}


def make_dir_link(link, target):
    """Directory symlink, or a junction on Windows. Returns True when a link exists."""
    link = Path(link)
    try:
        os.symlink(str(target), str(link), target_is_directory=True)
        return True
    except (OSError, NotImplementedError, AttributeError):
        pass
    if os.name == "nt":
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                           capture_output=True, text=True)
        return r.returncode == 0 and link.exists()
    return False


def is_link(p):
    p = Path(p)
    if os.path.islink(p):
        return True
    if os.name == "nt":
        import stat
        try:
            tag = getattr(os.lstat(p), "st_reparse_tag", 0)
        except OSError:
            return False
        return tag in (getattr(stat, "IO_REPARSE_TAG_SYMLINK", 0xA000000C),
                       getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003))
    return False


class TestAntigravityInstall(HostInstallBase):
    def hooks(self):
        return json.loads((self.root / ".agents" / "hooks.json").read_text(encoding="utf-8"))

    def test_fresh_install_files(self):
        self.ok(install("antigravity", self.root))
        self.assertTrue((self.root / ".aidd" / "CORE.md").is_file())
        self.assertTrue((self.root / ".aidd" / "hooks" / "host_adapter.py").is_file())
        self.assertTrue((self.root / ".agents" / "skills" / "aidd" / "SKILL.md").is_file())
        rule = (self.root / ".agents" / "rules" / "aidd.md").read_text(encoding="utf-8")
        self.assertIn("always_on", rule)
        self.assertEqual(self.hooks()["aidd"], expected_aidd_entry())

    def test_second_run_unchanged(self):
        self.ok(install("antigravity", self.root))
        before = snapshot(self.root)
        out = self.ok(install("antigravity", self.root))
        self.assertEqual(before, snapshot(self.root), "second run changed bytes or mtime")
        for rel in (".aidd/CORE.md", ".agents/skills/aidd/SKILL.md", ".agents/rules/aidd.md",
                    ".agents/hooks.json"):
            ls = lines_with(out, rel)
            self.assertTrue(ls, f"{rel} not reported")
            self.assertTrue(all("unchanged" in ln for ln in ls), ls)
        self.assertFalse([ln for ln in out.splitlines() if ln.lstrip().startswith("skipped")], out)

    def test_modified_skill_skipped_then_force(self):
        self.ok(install("antigravity", self.root))
        sk = self.root / ".agents" / "skills" / "aidd" / "SKILL.md"
        original = sk.read_bytes()
        sk.write_text("my local edit\n", encoding="utf-8")
        out = self.ok(install("antigravity", self.root))
        self.assertEqual(sk.read_text(encoding="utf-8"), "my local edit\n")
        self.assertTrue(any("skipped" in ln for ln in lines_with(out, ".agents/skills/aidd/SKILL.md")), out)
        self.ok(install("antigravity", self.root, force=True))
        self.assertEqual(sk.read_bytes(), original)

    def test_foreign_hook_survives_and_aidd_once(self):
        adir = self.root / ".agents"
        adir.mkdir()
        other = {"enabled": True, "PreToolUse": [{"matcher": "run_command", "hooks": [
            {"type": "command", "command": "echo hi", "timeout": 5}]}]}
        (adir / "hooks.json").write_text(json.dumps({"other": other, "custom_key": 7}), encoding="utf-8")
        self.ok(install("antigravity", self.root))
        self.ok(install("antigravity", self.root, force=True))
        raw = (adir / "hooks.json").read_text(encoding="utf-8")
        data = json.loads(raw)
        self.assertEqual(data["other"], other)
        self.assertEqual(data["custom_key"], 7)
        self.assertEqual(data["aidd"], expected_aidd_entry())
        self.assertEqual(raw.count('"aidd"'), 1)
        self.assertEqual(raw.count("host_adapter.py antigravity pre"), 1)
        self.assertEqual(raw.count("host_adapter.py antigravity post"), 1)

    def test_corrupt_hooks_json_not_overwritten(self):
        adir = self.root / ".agents"
        adir.mkdir()
        (adir / "hooks.json").write_text("{ not json", encoding="utf-8")
        out = self.ok(install("antigravity", self.root))
        self.assertEqual((adir / "hooks.json").read_text(encoding="utf-8"), "{ not json")
        self.assertTrue(any("skipped" in ln for ln in lines_with(out, "hooks.json")), out)

    def test_memory_survives_install_and_force(self):
        self.ok(install("antigravity", self.root))
        mem = self.root / ".aidd" / "memory" / "x"
        mem.parent.mkdir(parents=True, exist_ok=True)
        mem.write_text("keep me", encoding="utf-8")
        self.ok(install("antigravity", self.root))
        self.ok(install("antigravity", self.root, force=True))
        self.assertEqual(mem.read_text(encoding="utf-8"), "keep me")

    def test_cli_accepts_host_antigravity(self):
        env = dict(os.environ, PYTHONPATH=str(REPO), PYTHONIOENCODING="utf-8")
        r = subprocess.run([sys.executable, "-m", "aidd.cli", "install", "--host", "antigravity",
                            str(self.root)], cwd=str(REPO), env=env,
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((self.root / ".agents" / "rules" / "aidd.md").is_file())


class TestSymlinkSafety(HostInstallBase):
    """AC-1103 / FR-1104: never write through a link; --force removes ONLY the link."""

    def setUp(self):
        super().setUp()
        self.target = self.root.parent / (self.root.name + "-target")
        self.target.mkdir()
        self.addCleanup(shutil.rmtree, str(self.target), True)
        self.sentinel = self.target / "sentinel.txt"
        self.sentinel.write_text("do not touch", encoding="utf-8")
        self.target_before = sorted(p.name for p in self.target.iterdir())

    def assert_target_untouched(self):
        self.assertEqual(self.sentinel.read_text(encoding="utf-8"), "do not touch")
        self.assertEqual(sorted(p.name for p in self.target.iterdir()), self.target_before)

    def link_skill_dir(self):
        skills = self.root / ".agents" / "skills"
        skills.mkdir(parents=True)
        link = skills / "aidd"
        if not make_dir_link(link, self.target):
            self.skipTest("cannot create a directory symlink or junction on this machine")
        return link

    def test_linked_skill_dir_skipped_without_force(self):
        link = self.link_skill_dir()
        out = self.ok(install("antigravity", self.root))
        ls = lines_with(out, ".agents/skills/aidd/SKILL.md")
        self.assertTrue(any("skipped" in ln and "symlink" in ln for ln in ls), out)
        self.assertTrue(any(self.target.name in ln for ln in ls), "line must name the link target: " + out)
        self.assertTrue(is_link(link), "link must still be a link")
        self.assert_target_untouched()
        self.assertFalse((self.target / "SKILL.md").exists())

    def test_linked_skill_dir_replaced_by_real_folder_with_force(self):
        link = self.link_skill_dir()
        self.ok(install("antigravity", self.root, force=True))
        self.assertFalse(is_link(link), "link must be replaced")
        self.assertTrue(link.is_dir())
        self.assertTrue((link / "SKILL.md").is_file())
        self.assert_target_untouched()
        self.assertTrue(self.target.is_dir())

    def test_linked_dot_aidd_skipped_then_force(self):
        link = self.root / ".aidd"
        if not make_dir_link(link, self.target):
            self.skipTest("cannot create a directory symlink or junction on this machine")
        out = self.ok(install("antigravity", self.root))
        self.assertTrue(any("skipped" in ln and "symlink" in ln for ln in lines_with(out, ".aidd/CORE.md")), out)
        self.assertTrue(is_link(link))
        self.assert_target_untouched()
        self.ok(install("antigravity", self.root, force=True))
        self.assertFalse(is_link(link))
        self.assertTrue((link / "CORE.md").is_file())
        self.assert_target_untouched()


if __name__ == "__main__":
    unittest.main()
