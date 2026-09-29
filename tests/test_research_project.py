"""Tests for scripts/research_project.py — stdlib unittest, no dependencies.

Run: python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import research_project  # noqa: E402


class TestSlugify(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(research_project.slugify("Order History"), "order-history")

    def test_collapses_punctuation(self):
        self.assertEqual(research_project.slugify("login_page"), "login-page")

    def test_empty_falls_back(self):
        self.assertEqual(research_project.slugify("___"), "area")


class TestPropose(unittest.TestCase):
    def test_no_hit_dirs_yields_no_candidates(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / "src").mkdir()
            (root / "src" / "main.py").write_text("print(1)", encoding="utf-8")
            self.assertEqual(research_project.propose(root), [])

    def test_finds_pages_dir_children(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            pages = root / "lib" / "pages"
            (pages / "login").mkdir(parents=True)
            (pages / "login" / "login_page.dart").write_text("class LoginPage {}", encoding="utf-8")
            (pages / "orders").mkdir()
            (pages / "orders" / "orders_page.dart").write_text("class OrdersPage {}", encoding="utf-8")

            candidates = research_project.propose(root)
            slugs = {c["slug"] for c in candidates}
            self.assertEqual(slugs, {"login", "orders"})
            for c in candidates:
                self.assertTrue(c["proposed_folder"].startswith("specs/"))
                self.assertEqual(c["files"], 1)

    def test_merges_same_slug_across_hit_dirs(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            pages = root / "pages"
            controllers = root / "controllers"
            (pages / "orders").mkdir(parents=True)
            (pages / "orders" / "orders_page.tsx").write_text("export const x = 1;", encoding="utf-8")
            (controllers / "orders").mkdir(parents=True)
            (controllers / "orders" / "orders_controller.ts").write_text("export const y = 1;", encoding="utf-8")

            candidates = research_project.propose(root)
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0]["slug"], "orders")
            self.assertEqual(candidates[0]["files"], 2)
            self.assertEqual(len(candidates[0]["sources"]), 2)

    def test_ignores_noise_dirs(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            pages = root / "pages"
            noise = pages / "node_modules"
            (noise / "somepkg").mkdir(parents=True)
            (noise / "somepkg" / "index.js").write_text("module.exports = {}", encoding="utf-8")
            pages.mkdir(exist_ok=True)

            candidates = research_project.propose(root)
            self.assertEqual(candidates, [])

    def test_bare_file_under_hit_dir_is_its_own_candidate(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            views = root / "views"
            views.mkdir()
            (views / "dashboard.py").write_text("def view(): pass", encoding="utf-8")

            candidates = research_project.propose(root)
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0]["slug"], "dashboard")


class TestHasExistingSpecs(unittest.TestCase):
    def test_false_when_no_specs_dir(self):
        with TemporaryDirectory() as td:
            self.assertFalse(research_project.has_existing_specs(Path(td)))

    def test_false_when_specs_dir_empty(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / "specs").mkdir()
            self.assertFalse(research_project.has_existing_specs(root))

    def test_true_when_specs_dir_has_a_feature_folder(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / "specs" / "001-login").mkdir(parents=True)
            self.assertTrue(research_project.has_existing_specs(root))


if __name__ == "__main__":
    unittest.main()
