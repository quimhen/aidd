"""Tests for scripts/marketplace.py — stdlib unittest, no dependencies.

Every test builds its own throwaway catalog/ + project directory inside a
TemporaryDirectory and passes it explicitly via catalog_dir/project_root —
none of these ever touch this repo's real catalog/ (that's covered
separately by TestRealCatalog, a regression check that the shipped catalog
itself stays valid).
"""
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import marketplace as mp  # noqa: E402


def make_catalog(root: Path, packages: list[dict]) -> Path:
    """packages: list of dicts with at least 'id', plus package.json fields.
    Each package's files/ gets one file (files.get('content', 'hello')) at
    files['dest'] (default 'a.md') <- files/source.md."""
    (root / "packages").mkdir(parents=True, exist_ok=True)
    catalog_ids = []
    for pkg in packages:
        pkg_dir = root / "packages" / pkg["id"]
        (pkg_dir / "files").mkdir(parents=True, exist_ok=True)
        source_name = pkg.get("_source_name", "source.md")
        (pkg_dir / "files" / source_name).write_text(
            pkg.get("_content", "hello"), encoding="utf-8"
        )
        manifest = {
            "id": pkg["id"],
            "name": pkg.get("name", pkg["id"]),
            "description": pkg.get("description", "a test package"),
            "version": pkg.get("version", "1.0.0"),
            "author": pkg.get("author", "test"),
            "license": pkg.get("license", "MIT"),
            "kind": pkg.get("kind", "template"),
            "files": pkg.get("files", {"a.md": source_name}),
        }
        (pkg_dir / "package.json").write_text(json.dumps(manifest), encoding="utf-8")
        catalog_ids.append({"id": pkg["id"]})

    (root / "catalog.json").write_text(json.dumps({"packages": catalog_ids}), encoding="utf-8")
    (root / "catalog.community.json").write_text(json.dumps({"packages": []}), encoding="utf-8")
    return root


class TestLoadCatalog(unittest.TestCase):
    def test_merges_first_party_and_community(self):
        with TemporaryDirectory() as d:
            root = make_catalog(Path(d), [{"id": "pkg-a"}])
            (root / "catalog.community.json").write_text(
                json.dumps({"packages": [{"id": "pkg-b"}]}), encoding="utf-8"
            )
            # pkg-b needs its own folder too
            (root / "packages" / "pkg-b" / "files").mkdir(parents=True)
            (root / "packages" / "pkg-b" / "files" / "source.md").write_text("x", encoding="utf-8")
            (root / "packages" / "pkg-b" / "package.json").write_text(json.dumps({
                "id": "pkg-b", "name": "B", "description": "d", "version": "1.0.0",
                "author": "a", "license": "MIT", "kind": "template",
                "files": {"a.md": "source.md"},
            }), encoding="utf-8")

            ids = {pkg["id"] for pkg in mp.load_catalog(root)}
            self.assertEqual(ids, {"pkg-a", "pkg-b"})

    def test_duplicate_id_across_catalogs_only_counted_once(self):
        with TemporaryDirectory() as d:
            root = make_catalog(Path(d), [{"id": "pkg-a"}])
            (root / "catalog.community.json").write_text(
                json.dumps({"packages": [{"id": "pkg-a"}]}), encoding="utf-8"
            )
            ids = [pkg["id"] for pkg in mp.load_catalog(root)]
            self.assertEqual(ids, ["pkg-a"])

    def test_entry_without_matching_package_folder_is_skipped(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "packages").mkdir()
            (root / "catalog.json").write_text(
                json.dumps({"packages": [{"id": "ghost"}]}), encoding="utf-8"
            )
            (root / "catalog.community.json").write_text(json.dumps({"packages": []}), encoding="utf-8")
            self.assertEqual(mp.load_catalog(root), [])


class TestSearchCatalog(unittest.TestCase):
    def test_matches_description(self):
        with TemporaryDirectory() as d:
            root = make_catalog(Path(d), [
                {"id": "alpha", "description": "handles login flows"},
                {"id": "beta", "description": "handles checkout flows"},
            ])
            results = mp.search_catalog("login", root)
            self.assertEqual([p["id"] for p in results], ["alpha"])

    def test_no_match_returns_empty(self):
        with TemporaryDirectory() as d:
            root = make_catalog(Path(d), [{"id": "alpha"}])
            self.assertEqual(mp.search_catalog("nonexistent-term", root), [])


class TestInstallPackage(unittest.TestCase):
    def test_installs_declared_files_and_records_manifest(self):
        with TemporaryDirectory() as d, TemporaryDirectory() as p:
            root = make_catalog(Path(d), [{"id": "pkg-a", "files": {"docs/a.md": "source.md"}}])
            project_root = Path(p)
            written = mp.install_package("pkg-a", project_root, catalog_dir=root)
            self.assertEqual(len(written), 1)
            self.assertTrue((project_root / "docs" / "a.md").exists())
            manifest = json.loads((project_root / ".aidd" / "marketplace-manifest.json").read_text())
            self.assertIn("pkg-a", manifest)
            self.assertIn("docs/a.md", manifest["pkg-a"]["files"])

    def test_unknown_package_raises(self):
        with TemporaryDirectory() as d, TemporaryDirectory() as p:
            root = make_catalog(Path(d), [{"id": "pkg-a"}])
            with self.assertRaises(ValueError):
                mp.install_package("does-not-exist", Path(p), catalog_dir=root)

    def test_provider_kind_is_not_yet_installable(self):
        with TemporaryDirectory() as d, TemporaryDirectory() as p:
            root = make_catalog(Path(d), [{"id": "pkg-a", "kind": "provider"}])
            with self.assertRaises(NotImplementedError):
                mp.install_package("pkg-a", Path(p), catalog_dir=root)

    def test_hook_kind_is_not_yet_installable(self):
        with TemporaryDirectory() as d, TemporaryDirectory() as p:
            root = make_catalog(Path(d), [{"id": "pkg-a", "kind": "hook"}])
            with self.assertRaises(NotImplementedError):
                mp.install_package("pkg-a", Path(p), catalog_dir=root)

    def test_path_traversal_in_files_map_is_rejected(self):
        with TemporaryDirectory() as d, TemporaryDirectory() as p:
            root = make_catalog(Path(d), [{"id": "pkg-a"}])
            manifest_path = root / "packages" / "pkg-a" / "package.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["files"] = {"a.md": "../../../etc/passwd"}
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(ValueError):
                mp.install_package("pkg-a", Path(p), catalog_dir=root)

    def test_conflicting_file_between_two_packages_refused_without_force(self):
        with TemporaryDirectory() as d, TemporaryDirectory() as p:
            root = make_catalog(Path(d), [
                {"id": "pkg-a", "files": {"shared.md": "source.md"}},
                {"id": "pkg-b", "files": {"shared.md": "source.md"}},
            ])
            project_root = Path(p)
            mp.install_package("pkg-a", project_root, catalog_dir=root)
            with self.assertRaises(ValueError):
                mp.install_package("pkg-b", project_root, catalog_dir=root)
            # force overrides the refusal
            written = mp.install_package("pkg-b", project_root, force=True, catalog_dir=root)
            self.assertEqual(len(written), 1)


class TestRemovePackage(unittest.TestCase):
    def test_removes_unmodified_files_and_clears_manifest_entry(self):
        with TemporaryDirectory() as d, TemporaryDirectory() as p:
            root = make_catalog(Path(d), [{"id": "pkg-a", "files": {"a.md": "source.md"}}])
            project_root = Path(p)
            mp.install_package("pkg-a", project_root, catalog_dir=root)
            removed, skipped = mp.remove_package("pkg-a", project_root)
            self.assertEqual(len(removed), 1)
            self.assertEqual(skipped, [])
            self.assertFalse((project_root / "a.md").exists())
            manifest = json.loads((project_root / ".aidd" / "marketplace-manifest.json").read_text())
            self.assertNotIn("pkg-a", manifest)

    def test_skips_file_modified_since_install_without_force(self):
        with TemporaryDirectory() as d, TemporaryDirectory() as p:
            root = make_catalog(Path(d), [{"id": "pkg-a", "files": {"a.md": "source.md"}}])
            project_root = Path(p)
            mp.install_package("pkg-a", project_root, catalog_dir=root)
            (project_root / "a.md").write_text("edited by hand", encoding="utf-8")
            removed, skipped = mp.remove_package("pkg-a", project_root)
            self.assertEqual(removed, [])
            self.assertEqual(len(skipped), 1)
            self.assertTrue((project_root / "a.md").exists())

    def test_force_removes_modified_file_anyway(self):
        with TemporaryDirectory() as d, TemporaryDirectory() as p:
            root = make_catalog(Path(d), [{"id": "pkg-a", "files": {"a.md": "source.md"}}])
            project_root = Path(p)
            mp.install_package("pkg-a", project_root, catalog_dir=root)
            (project_root / "a.md").write_text("edited by hand", encoding="utf-8")
            removed, skipped = mp.remove_package("pkg-a", project_root, force=True)
            self.assertEqual(len(removed), 1)
            self.assertEqual(skipped, [])

    def test_removing_not_installed_package_raises(self):
        with TemporaryDirectory() as p:
            with self.assertRaises(ValueError):
                mp.remove_package("nope", Path(p))


class TestRealCatalog(unittest.TestCase):
    """Regression check: this repo's own shipped catalog/ must stay valid."""

    def test_shipped_catalog_loads_and_has_no_conflicts(self):
        packages = mp.load_catalog()
        self.assertTrue(packages, "expected at least one shipped package (hotfix-report)")
        ids = [p["id"] for p in packages]
        self.assertEqual(len(ids), len(set(ids)), "duplicate package id in the real catalog")

    def test_hotfix_report_installs_cleanly(self):
        with TemporaryDirectory() as p:
            project_root = Path(p)
            written = mp.install_package("hotfix-report", project_root)
            self.assertTrue(written)
            for f in written:
                self.assertTrue(f.exists())


if __name__ == "__main__":
    unittest.main()
