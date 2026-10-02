"""Regression (audit Rev 1): `aidd mem` must forward everything verbatim, including
options that come BEFORE the subcommand (`aidd mem --root X add ...`, `--help`)."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def aidd(*args):
    return subprocess.run([sys.executable, "-m", "aidd.cli", *args], cwd=str(REPO_ROOT),
                          capture_output=True, text=True, encoding="utf-8")


class TestAiddMemCli(unittest.TestCase):
    def test_root_before_subcommand(self):
        with tempfile.TemporaryDirectory() as d:
            r = aidd("mem", "--root", d, "add", "--type", "decision", "--title", "Use TOON for flows")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue(r.stdout.strip().startswith("m-"))
            r = aidd("mem", "--root", d, "search", "toon")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("Use TOON for flows", r.stdout)

    def test_root_after_subcommand(self):
        with tempfile.TemporaryDirectory() as d:
            r = aidd("mem", "add", "--type", "bugfix", "--title", "Fix off by one", "--root", d)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_help_is_forwarded(self):
        r = aidd("mem", "--help")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("import-claude-mem", r.stdout)

    def test_exit_code_is_forwarded(self):
        with tempfile.TemporaryDirectory() as d:
            r = aidd("mem", "--root", d, "search", "nothing-here")
            self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
