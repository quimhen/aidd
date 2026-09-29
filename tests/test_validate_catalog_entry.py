"""Tests for scripts/validate_catalog_entry.py — stdlib unittest, no dependencies.

Every test that needs a catalog builds its own throwaway one and patches
the module's CATALOG_DIR constant (same technique tests/test_install_hooks.py
already uses for install_hooks.SETTINGS_PATH) — none of these mutate this
repo's real catalog/.
"""
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import validate_catalog_entry as vce  # noqa: E402

VALID_MANIFEST = {
    "id": "sample-pkg",
    "name": "Sample",
    "description": "A sample package for tests.",
    "version": "1.0.0",
    "author": "test",
    "license": "MIT",
    "kind": "template",
    "files": {"a.md": "source.md"},
}


def write_package(root: Path, package_id: str, manifest: dict, source_content: str = "hello"):
    pkg_dir = root / "packages" / package_id
    (pkg_dir / "files").mkdir(parents=True, exist_ok=True)
    (pkg_dir / "files" / "source.md").write_text(source_content, encoding="utf-8")
    (pkg_dir / "package.json").write_text(json.dumps(manifest), encoding="utf-8")


def write_catalogs(root: Path, first_party_ids: list[str], community_ids: list[str] = ()):
    (root / "catalog.json").write_text(
        json.dumps({"packages": [{"id": i} for i in first_party_ids]}), encoding="utf-8"
    )
    (root / "catalog.community.json").write_text(
        json.dumps({"packages": [{"id": i} for i in community_ids]}), encoding="utf-8"
    )


class TestValidateManifest(unittest.TestCase):
    def test_valid_manifest_has_no_errors_outside_file_check(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            write_package(root, "sample-pkg", VALID_MANIFEST)
            with patch.object(vce, "CATALOG_DIR", root):
                errors = vce.validate_manifest("sample-pkg", VALID_MANIFEST)
        self.assertEqual(errors, [])

    def test_missing_required_field_reported(self):
        manifest = dict(VALID_MANIFEST)
        del manifest["license"]
        errors = vce.validate_manifest("sample-pkg", manifest)
        self.assertTrue(any("license" in e for e in errors))

    def test_id_mismatch_with_folder_reported(self):
        manifest = dict(VALID_MANIFEST, id="different-id")
        with TemporaryDirectory() as d:
            root = Path(d)
            write_package(root, "sample-pkg", manifest)
            with patch.object(vce, "CATALOG_DIR", root):
                errors = vce.validate_manifest("sample-pkg", manifest)
        self.assertTrue(any("!= folder name" in e for e in errors))

    def test_invalid_semver_reported(self):
        manifest = dict(VALID_MANIFEST, version="v1.0")
        errors = vce.validate_manifest("sample-pkg", manifest)
        self.assertTrue(any("semver" in e for e in errors))

    def test_invalid_kind_reported(self):
        manifest = dict(VALID_MANIFEST, kind="plugin")
        errors = vce.validate_manifest("sample-pkg", manifest)
        self.assertTrue(any("kind" in e for e in errors))

    def test_path_traversal_in_files_reported(self):
        manifest = dict(VALID_MANIFEST, files={"a.md": "../../outside.md"})
        with TemporaryDirectory() as d:
            root = Path(d)
            write_package(root, "sample-pkg", VALID_MANIFEST)  # real files/ for the traversal check
            with patch.object(vce, "CATALOG_DIR", root):
                errors = vce.validate_manifest("sample-pkg", manifest)
        self.assertTrue(any("escapes its own files/ folder" in e for e in errors))

    def test_missing_source_file_reported(self):
        manifest = dict(VALID_MANIFEST, files={"a.md": "does-not-exist.md"})
        with TemporaryDirectory() as d:
            root = Path(d)
            write_package(root, "sample-pkg", VALID_MANIFEST)
            with patch.object(vce, "CATALOG_DIR", root):
                errors = vce.validate_manifest("sample-pkg", manifest)
        self.assertTrue(any("does not exist" in e for e in errors))


class TestLoadPackage(unittest.TestCase):
    def test_missing_folder_reported(self):
        with TemporaryDirectory() as d:
            with patch.object(vce, "CATALOG_DIR", Path(d)):
                manifest, errors = vce.load_package("nope")
        self.assertIsNone(manifest)
        self.assertTrue(any("no such folder" in e for e in errors))

    def test_invalid_json_reported(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            pkg_dir = root / "packages" / "broken"
            pkg_dir.mkdir(parents=True)
            (pkg_dir / "package.json").write_text("{not json", encoding="utf-8")
            with patch.object(vce, "CATALOG_DIR", root):
                manifest, errors = vce.load_package("broken")
        self.assertIsNone(manifest)
        self.assertTrue(any("not valid JSON" in e for e in errors))


class TestFindReviewFlags(unittest.TestCase):
    def test_flags_subprocess_usage(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            write_package(root, "sample-pkg", VALID_MANIFEST, source_content="import subprocess\n")
            with patch.object(vce, "CATALOG_DIR", root):
                flags = vce.find_review_flags("sample-pkg")
        self.assertTrue(any("subprocess" in f for f in flags))

    def test_no_flags_for_plain_markdown(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            write_package(root, "sample-pkg", VALID_MANIFEST, source_content="# just docs\n")
            with patch.object(vce, "CATALOG_DIR", root):
                flags = vce.find_review_flags("sample-pkg")
        self.assertEqual(flags, [])


class TestCheckDuplicateIds(unittest.TestCase):
    def test_no_duplicates_is_clean(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            write_catalogs(root, ["a"], ["b"])
            with patch.object(vce, "CATALOG_DIR", root):
                errors = vce.check_duplicate_ids()
        self.assertEqual(errors, [])

    def test_community_cannot_shadow_first_party(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            write_catalogs(root, ["shared-id"], ["shared-id"])
            with patch.object(vce, "CATALOG_DIR", root):
                errors = vce.check_duplicate_ids()
        self.assertTrue(any("duplicate package id" in e for e in errors))


class TestValidateEndToEnd(unittest.TestCase):
    def test_valid_package_passes_with_no_errors(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            write_package(root, "sample-pkg", VALID_MANIFEST)
            write_catalogs(root, ["sample-pkg"])
            with patch.object(vce, "CATALOG_DIR", root):
                errors, flags = vce.validate(["sample-pkg"])
        self.assertEqual(errors, [])

    def test_broken_package_fails(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            write_catalogs(root, [])
            with patch.object(vce, "CATALOG_DIR", root):
                errors, flags = vce.validate(["missing-pkg"])
        self.assertTrue(errors)


class TestRealCatalog(unittest.TestCase):
    """Regression check: this repo's own shipped catalog/ must pass validation."""

    def test_shipped_catalog_is_valid(self):
        errors, flags = vce.validate(vce.all_package_ids())
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
