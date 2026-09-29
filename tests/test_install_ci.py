"""Tests for scripts/install_ci.py — stdlib unittest, no dependencies.

Mirrors test_generate_adapters.py's file-writing test style: a fresh
install writes the file, a second run without --force skips it, and
--force overwrites it. Never touches a real project or network — every
test installs into a tempfile.TemporaryDirectory().

Run: python -m unittest discover -s tests -v
"""
import sys
import unittest
import unittest.mock
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import install_ci as ic  # noqa: E402


class TestInstall(unittest.TestCase):
    def test_fresh_install_writes_github_workflow(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            written = ic.install("github", root, force=False)
            self.assertIsNotNone(written)
            self.assertTrue(written.is_file())
            self.assertEqual(
                written,
                root / ".github" / "workflows" / "aidd.yml",
            )
            self.assertIn("pull_request", written.read_text(encoding="utf-8"))

    def test_fresh_install_writes_azure_pipeline(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            written = ic.install("azure-devops", root, force=False)
            self.assertIsNotNone(written)
            self.assertEqual(written, root / "azure-pipelines-aidd.yml")
            self.assertTrue(written.is_file())

    def test_second_run_without_force_skips(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            first = ic.install("github", root, force=False)
            self.assertIsNotNone(first)
            original_content = first.read_text(encoding="utf-8")

            # Tamper with the installed file so a silent overwrite would be
            # detectable.
            first.write_text("tampered", encoding="utf-8")

            second = ic.install("github", root, force=False)
            self.assertIsNone(second)
            self.assertEqual(first.read_text(encoding="utf-8"), "tampered")
            self.assertNotEqual(first.read_text(encoding="utf-8"), original_content)

    def test_force_overwrites_existing(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            first = ic.install("github", root, force=False)
            first.write_text("tampered", encoding="utf-8")

            second = ic.install("github", root, force=True)
            self.assertIsNotNone(second)
            self.assertEqual(second, first)
            self.assertIn("pull_request", second.read_text(encoding="utf-8"))

    def test_creates_parent_directories(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            self.assertFalse((root / ".github").exists())
            ic.install("github", root, force=False)
            self.assertTrue((root / ".github" / "workflows").is_dir())


class TestMain(unittest.TestCase):
    def _run_main(self, argv):
        with unittest.mock.patch.object(sys, "argv", ["install_ci.py"] + argv):
            with self.assertRaises(SystemExit) as cm:
                ic.main()
        return cm.exception.code

    def test_list_exits_zero(self):
        code = self._run_main(["--list"])
        self.assertEqual(code, 0)

    def test_no_args_exits_two(self):
        code = self._run_main([])
        self.assertEqual(code, 2)

    def test_unknown_target_exits_two(self):
        code = self._run_main(["not-a-real-target"])
        self.assertEqual(code, 2)

    def test_unknown_project_root_exits_two(self):
        code = self._run_main(["github", "/path/does/not/exist/at/all"])
        self.assertEqual(code, 2)

    def test_valid_install_via_main_exits_zero(self):
        with TemporaryDirectory() as d:
            code = self._run_main(["github", d, "--force"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
