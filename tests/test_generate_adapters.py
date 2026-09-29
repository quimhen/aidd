"""Tests for scripts/generate_adapters.py — stdlib unittest, no dependencies.

Adapter targets are no longer a hardcoded dict; they're discovered via
extension_registry.get_adapter_targets() from skill/extensions/adapters/
manifest.json folders (first-party) plus any project's own
.aidd/extensions/ (project-local). Tests that need "every registered
target" build a small in-repo fixture and patch
extension_registry.SKILL_EXTENSIONS_DIR at it, same idiom
test_install_hooks.py uses for SETTINGS_PATH.

Run: python -m unittest discover -s tests -v
"""
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import extension_registry  # noqa: E402
import generate_adapters as ga  # noqa: E402

REAL_TARGETS = extension_registry.get_adapter_targets()

SAMPLE_SOURCE = (
    "---\n"
    "description: AIDD Step 9 — sample step for testing\n"
    "---\n\n"
    "Invoke the `aidd` skill and run **Step 9 (Sample)** for: $ARGUMENTS\n"
    "\n"
    "- One bullet referencing nothing special.\n"
)


class TestParseSource(unittest.TestCase):
    def test_splits_description_and_body(self):
        description, body = ga.parse_source(SAMPLE_SOURCE)
        self.assertEqual(description, "AIDD Step 9 — sample step for testing")
        self.assertIn("Invoke the `aidd` skill and run", body)
        self.assertIn("$ARGUMENTS", body)

    def test_missing_frontmatter_raises(self):
        with self.assertRaises(ValueError):
            ga.parse_source("no frontmatter here\n")

    def test_missing_description_raises(self):
        with self.assertRaises(ValueError):
            ga.parse_source("---\nfoo: bar\n---\n\nbody\n")

    def test_every_real_source_command_parses(self):
        # Every commands/aidd-*.md in this repo must actually match the
        # fixed source format the generator assumes — a template that
        # doesn't parse would silently vanish from every generated target.
        sources = ga.list_source_commands()
        self.assertEqual(len(sources), 8)
        for src in sources:
            description, body = ga.parse_source(src.read_text(encoding="utf-8"))
            self.assertTrue(description)
            self.assertIn("Invoke the `aidd` skill and run", body)
            self.assertIn("$ARGUMENTS", body)


class TestSubstitute(unittest.TestCase):
    def test_replaces_both_placeholders(self):
        target = {
            "invoke_phrase": "Read the docs, then run",
            "arg_placeholder": "{{args}}",
        }
        _, body = ga.parse_source(SAMPLE_SOURCE)
        result = ga.substitute(body, target)
        self.assertNotIn("Invoke the `aidd` skill and run", result)
        self.assertIn("Read the docs, then run", result)
        self.assertNotIn("$ARGUMENTS", result)
        self.assertIn("{{args}}", result)


class TestRenderMarkdown(unittest.TestCase):
    def test_frontmatter_and_body_present(self):
        content = ga.render_markdown("A description", "body text", {"frontmatter_extra": {}})
        self.assertTrue(content.startswith("---\ndescription: A description\n---\n"))
        self.assertIn("body text", content)

    def test_extra_frontmatter_keys_included(self):
        content = ga.render_markdown(
            "A description", "body text", {"frontmatter_extra": {"mode": "agent"}}
        )
        self.assertIn("mode: agent", content)
        # description must still come before the closing delimiter
        self.assertLess(content.index("description:"), content.index("mode: agent"))


class TestRenderToml(unittest.TestCase):
    def test_produces_description_and_prompt_keys(self):
        content = ga.render_toml("A description", "line one\nline two", {})
        self.assertIn('description = """', content)
        self.assertIn('prompt = """', content)
        self.assertIn("line one\nline two", content)

    def test_rejects_triple_quote_in_content(self):
        with self.assertRaises(ValueError):
            ga.render_toml('has a triple """ quote', "body", {})


class TestGenerate(unittest.TestCase):
    def test_writes_one_file_per_source_command(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            written = ga.generate("cursor", root, REAL_TARGETS, force=True)
            self.assertEqual(len(written), len(ga.list_source_commands()))
            for f in written:
                self.assertTrue(f.is_file())
                self.assertTrue(str(f).replace("\\", "/").endswith(
                    f".cursor/commands/{f.name}"
                ))

    def test_skips_existing_without_force(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            first = ga.generate("gemini", root, REAL_TARGETS, force=False)
            self.assertTrue(first)
            second = ga.generate("gemini", root, REAL_TARGETS, force=False)
            self.assertEqual(second, [])

    def test_force_overwrites_existing(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            ga.generate("gemini", root, REAL_TARGETS, force=False)
            forced = ga.generate("gemini", root, REAL_TARGETS, force=True)
            self.assertEqual(len(forced), len(ga.list_source_commands()))

    def test_every_registered_target_generates_without_error(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            for key in REAL_TARGETS:
                written = ga.generate(key, root, REAL_TARGETS, force=True)
                self.assertEqual(len(written), len(ga.list_source_commands()), key)


class TestDiscoveryEndToEnd(unittest.TestCase):
    """Verifies the NEW discovery path (extension_registry.get_adapter_targets)
    end-to-end, using a small in-repo fixture instead of the real
    skill/extensions/adapters/ folder — so this test is independent of
    whatever first-party adapters happen to exist."""

    def _make_fixture(self, tmp_root: Path):
        ext_dir = tmp_root / "extensions"
        for key, dirname, fmt, arg_placeholder in (
            ("fakeagent-a", ".fakeagent-a/commands", "markdown", "$ARGUMENTS"),
            ("fakeagent-b", ".fakeagent-b/commands", "toml", "{{args}}"),
        ):
            folder = ext_dir / "adapters" / key
            folder.mkdir(parents=True, exist_ok=True)
            manifest = {
                "id": key,
                "name": f"Fake Agent {key[-1].upper()}",
                "description": "Test fixture adapter.",
                "version": "1.0.0",
                "kind": "adapter",
                "adapter": {
                    "dir": dirname,
                    "format": fmt,
                    "filename": "aidd-{stem}." + ("md" if fmt == "markdown" else "toml"),
                    "arg_placeholder": arg_placeholder,
                    "invoke_phrase": "Read the fixture docs, then run",
                },
            }
            (folder / "manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
        return ext_dir

    def test_get_adapter_targets_discovers_fixture(self):
        with TemporaryDirectory() as d:
            fixture_ext_dir = self._make_fixture(Path(d))
            with patch.object(extension_registry, "SKILL_EXTENSIONS_DIR", fixture_ext_dir):
                targets = extension_registry.get_adapter_targets()
        self.assertEqual(set(targets), {"fakeagent-a", "fakeagent-b"})
        self.assertEqual(targets["fakeagent-a"]["format"], "markdown")
        self.assertEqual(targets["fakeagent-b"]["format"], "toml")
        self.assertEqual(targets["fakeagent-a"]["name"], "Fake Agent A")

    def test_generate_end_to_end_from_discovered_targets(self):
        with TemporaryDirectory() as d:
            fixture_ext_dir = self._make_fixture(Path(d))
            with patch.object(extension_registry, "SKILL_EXTENSIONS_DIR", fixture_ext_dir):
                targets = extension_registry.get_adapter_targets()
            with TemporaryDirectory() as project_dir:
                root = Path(project_dir)
                written = ga.generate("fakeagent-a", root, targets, force=True)
                self.assertEqual(len(written), len(ga.list_source_commands()))
                for f in written:
                    self.assertTrue(f.is_file())
                    self.assertTrue(str(f).replace("\\", "/").endswith(
                        f".fakeagent-a/commands/{f.name}"
                    ))


if __name__ == "__main__":
    unittest.main()
