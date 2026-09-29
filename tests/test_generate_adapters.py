"""Tests for scripts/generate_adapters.py + adapter_targets.py — stdlib
unittest, no dependencies.

Run: python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import generate_adapters as ga  # noqa: E402
from adapter_targets import TARGETS  # noqa: E402

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
            written = ga.generate("cursor", root, force=True)
            self.assertEqual(len(written), len(ga.list_source_commands()))
            for f in written:
                self.assertTrue(f.is_file())
                self.assertTrue(str(f).replace("\\", "/").endswith(
                    f".cursor/commands/{f.name}"
                ))

    def test_skips_existing_without_force(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            first = ga.generate("gemini", root, force=False)
            self.assertTrue(first)
            second = ga.generate("gemini", root, force=False)
            self.assertEqual(second, [])

    def test_force_overwrites_existing(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            ga.generate("gemini", root, force=False)
            forced = ga.generate("gemini", root, force=True)
            self.assertEqual(len(forced), len(ga.list_source_commands()))

    def test_every_registered_target_generates_without_error(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            for key in TARGETS:
                written = ga.generate(key, root, force=True)
                self.assertEqual(len(written), len(ga.list_source_commands()), key)


if __name__ == "__main__":
    unittest.main()
