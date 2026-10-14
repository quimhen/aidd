"""T-08 — doctor tests (FR-909, FR-910, FR-911; AC-004). stdlib unittest.

CLI contract assumed (plan Interface 2):
  python skill/scripts/aidd_doctor.py [--host H] [--root DIR] [--json]
Text mode: one line per check `PASS|FAIL <id> <message> -> <fix>`.
--json: either a list of check objects or an object holding such a list under
any key (e.g. "checks"); each check has id/status/message/fix.
Exit 1 when any of D1-D5 fails, else 0.
"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INSTALLER = REPO / "skill" / "scripts" / "install_host.py"
DOCTOR = REPO / "skill" / "scripts" / "aidd_doctor.py"
CORE_LIMIT = 12288


def run(script, *args):
    return subprocess.run([sys.executable, str(script), *map(str, args)],
                          capture_output=True, text=True, encoding="utf-8")


def install(host, root):
    r = run(INSTALLER, "install", host, root)
    assert r.returncode == 0, r.stdout + r.stderr


def doctor(host, root, *extra):
    return run(DOCTOR, "--host", host, "--root", root, *extra)


def failed(r, check_id):
    return re.search(rf"FAIL\s+{check_id}\b", r.stdout + r.stderr) is not None


def passed(r, check_id):
    return re.search(rf"PASS\s+{check_id}\b", r.stdout + r.stderr) is not None


class DoctorBase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name)


class TestNoAidd(DoctorBase):
    def test_ac004_missing_aidd(self):
        for host in ("gemini", "opencode"):
            with self.subTest(host=host):
                r = doctor(host, self.root)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn(f"aidd install --host {host}", r.stdout + r.stderr)


class TestHealthy(DoctorBase):
    def test_healthy_install_passes(self):
        for host in ("gemini", "opencode"):
            with self.subTest(host=host):
                root = self.root / host
                root.mkdir()
                install(host, root)
                r = doctor(host, root)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                for cid in ("D1", "D2", "D3", "D4", "D5"):
                    self.assertTrue(passed(r, cid), f"{cid}\n{r.stdout}{r.stderr}")

    def test_json_output(self):
        install("gemini", self.root)
        r = doctor("gemini", self.root, "--json")
        data = json.loads(r.stdout)
        if isinstance(data, dict):
            lists = [v for v in data.values() if isinstance(v, list)]
            self.assertTrue(lists, data)
            data = lists[0]
        self.assertTrue(data)
        ids = set()
        for c in data:
            for key in ("id", "status", "message", "fix"):
                self.assertIn(key, c)
            ids.add(c["id"])
        self.assertTrue({"D1", "D2", "D3", "D4", "D5"} <= ids, ids)


class TestChecksFail(DoctorBase):
    def test_d2_core_too_big(self):
        install("gemini", self.root)
        core = self.root / ".aidd" / "CORE.md"
        with open(core, "a", encoding="utf-8") as f:
            f.write("\n" + "x" * (CORE_LIMIT + 100))
        r = doctor("gemini", self.root)
        self.assertTrue(failed(r, "D2"), r.stdout + r.stderr)
        self.assertEqual(r.returncode, 1)

    def test_d3_import_line_removed(self):
        install("gemini", self.root)
        gm = self.root / "GEMINI.md"
        gm.write_text(gm.read_text(encoding="utf-8").replace("@.aidd/CORE.md", ""),
                      encoding="utf-8")
        r = doctor("gemini", self.root)
        self.assertTrue(failed(r, "D3"), r.stdout + r.stderr)
        self.assertEqual(r.returncode, 1)

    def test_d4_gemini_registration_removed(self):
        install("gemini", self.root)
        sp = self.root / ".gemini" / "settings.json"
        s = json.loads(sp.read_text(encoding="utf-8"))
        s["hooks"] = {}
        sp.write_text(json.dumps(s), encoding="utf-8")
        r = doctor("gemini", self.root)
        self.assertTrue(failed(r, "D4"), r.stdout + r.stderr)
        self.assertEqual(r.returncode, 1)

    def test_d4_gemini_command_altered(self):
        install("gemini", self.root)
        sp = self.root / ".gemini" / "settings.json"
        txt = sp.read_text(encoding="utf-8").replace("host_adapter.py", "noop.py")
        sp.write_text(txt, encoding="utf-8")
        r = doctor("gemini", self.root)
        self.assertTrue(failed(r, "D4"), r.stdout + r.stderr)

    def test_d4_opencode_registration_removed(self):
        install("opencode", self.root)
        cp = self.root / ".opencode" / "opencode.json"
        c = json.loads(cp.read_text(encoding="utf-8"))
        c["plugin"] = []
        cp.write_text(json.dumps(c), encoding="utf-8")
        r = doctor("opencode", self.root)
        self.assertTrue(failed(r, "D4"), r.stdout + r.stderr)
        self.assertEqual(r.returncode, 1)

    def test_d4_opencode_plugin_altered(self):
        install("opencode", self.root)
        plug = self.root / ".opencode" / "plugins" / "aidd.js"
        plug.write_text(plug.read_text(encoding="utf-8") + "\n// disabled\n", encoding="utf-8")
        r = doctor("opencode", self.root)
        self.assertTrue(failed(r, "D4"), r.stdout + r.stderr)
        self.assertEqual(r.returncode, 1)

    def test_d5_adapter_missing(self):
        for host in ("gemini", "opencode"):
            with self.subTest(host=host):
                root = self.root / host
                root.mkdir()
                install(host, root)
                (root / ".aidd" / "hooks" / "host_adapter.py").unlink()
                r = doctor(host, root)
                self.assertTrue(failed(r, "D5"), r.stdout + r.stderr)
                self.assertEqual(r.returncode, 1)


class TestFixBatchChecks(DoctorBase):
    def test_d5_python_not_on_path(self):
        import os
        install("gemini", self.root)
        with tempfile.TemporaryDirectory() as empty:
            env = dict(os.environ, PATH=empty)
            r = subprocess.run([sys.executable, str(DOCTOR), "--host", "gemini", "--root", str(self.root)],
                               capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertTrue(failed(r, "D5"), r.stdout + r.stderr)
        self.assertIn("python is not on path", (r.stdout + r.stderr).lower())
        self.assertEqual(r.returncode, 1)

    def test_d4_gemini_matcher_altered(self):
        install("gemini", self.root)
        sp = self.root / ".gemini" / "settings.json"
        s = json.loads(sp.read_text(encoding="utf-8"))
        n = 0
        for group in s["hooks"]["BeforeTool"]:
            if "aidd-gate" in json.dumps(group):
                group["matcher"] = "nothing_matches_this"
                n += 1
        self.assertTrue(n)
        sp.write_text(json.dumps(s), encoding="utf-8")
        r = doctor("gemini", self.root)
        self.assertTrue(failed(r, "D4"), r.stdout + r.stderr)
        self.assertEqual(r.returncode, 1)

    def test_d3_existing_geminimd_without_import_fix_text(self):
        install("gemini", self.root)
        (self.root / "GEMINI.md").write_text("# my own notes\n", encoding="utf-8")
        r = doctor("gemini", self.root)
        self.assertTrue(failed(r, "D3"), r.stdout + r.stderr)
        line = next(ln for ln in (r.stdout + r.stderr).splitlines() if re.search(r"FAIL\s+D3\b", ln))
        self.assertIn("@.aidd/CORE.md", line)
        self.assertNotIn("aidd install", line)


class TestFr913WordCounts(unittest.TestCase):
    def test_fr913_word_count_phrases_present(self):
        for rel in ("skill/templates/spec.md", "skill/AIDD.md", "skill/SKILL.md",
                    "adapters/dot-aidd/CORE.md"):
            txt = (REPO / rel).read_text(encoding="utf-8")
            for phrase in ("5+ words", "2+ words"):
                self.assertIn(phrase, txt, f"{rel} must contain {phrase!r}")


class TestSizeGuardFR910(unittest.TestCase):
    def test_core_under_limit(self):
        core = REPO / "adapters" / "dot-aidd" / "CORE.md"
        self.assertTrue(core.is_file())
        self.assertLess(core.stat().st_size, CORE_LIMIT)

    def test_pointers_do_not_say_read_in_full(self):
        for rel in ("adapters/GEMINI.md", "adapters/AGENTS.md.snippet",
                    "adapters/opencode/skills/aidd/SKILL.md"):
            txt = (REPO / rel).read_text(encoding="utf-8")
            self.assertNotIn("read it in full", txt.lower(), rel)
            self.assertIn("CORE.md", txt, f"{rel} must point to CORE.md")


if __name__ == "__main__":
    unittest.main()
