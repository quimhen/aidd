import json
import tempfile
import unittest
from pathlib import Path
from dataclasses import replace

from skill.scripts.aidd_units import discover_units, load_unit, resolve_units


class UnitManifests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def manifest(self, spec="007-aidd-review-html-close-gate", unit="A11", **changes):
        folder = self.root / "specs" / spec / "amendments" / unit
        folder.mkdir(parents=True, exist_ok=True)
        data = dict(schema_version=1, spec_id=spec, unit_id=unit, sequence=1,
                    parents=[], paths=["docs/input.md"], targets=["src/output.py"])
        data.update(changes)
        file = folder / "manifest.json"
        file.write_text(json.dumps(data), encoding="utf-8")
        return file

    def test_stable_order_and_cross_spec_qualified_parents(self):
        a = load_unit(self.manifest(unit="A10", sequence=2), self.root)
        b = load_unit(self.manifest(unit="A11", sequence=1,
                      parents=[a.key]), self.root)
        c = load_unit(self.manifest(spec="008-test", unit="A11"), self.root)
        self.assertEqual(resolve_units([b, c, a]), resolve_units([c, a, b]))
        order = resolve_units([b, c, a])
        self.assertLess(order.index(a), order.index(b))
        self.assertEqual(set(order), set(discover_units(self.root)))

    def test_missing_manifest_and_parent(self):
        (self.root / "specs/s/amendments/a").mkdir(parents=True)
        with self.assertRaises(ValueError):
            discover_units(self.root)
        a = load_unit(self.manifest(parents=["other:missing"]), self.root)
        with self.assertRaises(ValueError):
            resolve_units([a])

    def test_duplicate_id_sequence_and_cycle(self):
        a = load_unit(self.manifest(unit="a", sequence=1), self.root)
        b = load_unit(self.manifest(unit="b", sequence=2), self.root)
        for units in ([a, a], [a, replace(b, sequence=1)],
                      [replace(a, parents=(b.key,)), replace(b, parents=(a.key,))]):
            with self.subTest(units=units), self.assertRaises(ValueError):
                resolve_units(units)

    def test_invalid_manifest_and_paths(self):
        for bad in ("../escape", "/absolute", "C:/windows", "C:relative", "a\\b", "x/../b"):
            with self.subTest(path=bad), self.assertRaises(ValueError):
                load_unit(self.manifest(paths=[bad]), self.root)
        for changes in (dict(sequence=True), dict(schema_version=True),
                        dict(parents=["bad"]), dict(paths=["a", "a"]),
                        dict(paths=["a", "A"]), dict(extra=1)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                load_unit(self.manifest(**changes), self.root)

    def test_oversized_and_duplicate_json_keys(self):
        file = self.manifest()
        file.write_bytes(b" " * (1024 * 1024 + 1))
        with self.assertRaises(ValueError):
            load_unit(file, self.root)
        file.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
        with self.assertRaises(ValueError):
            load_unit(file, self.root)

    def test_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            link = self.root / "escape"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unavailable")
            with self.assertRaises(ValueError):
                load_unit(self.manifest(paths=["escape/file"]), self.root)

    def test_broken_amendments_link_is_not_ignored(self):
        spec = self.root / 'specs' / 'test'
        spec.mkdir(parents=True)
        try:
            (spec / 'amendments').symlink_to(self.root / 'missing', target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('directory symlinks unavailable')
        with self.assertRaises(ValueError):
            discover_units(self.root)


if __name__ == "__main__":
    unittest.main()
