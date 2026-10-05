"""Guard test: adapters/dot-aidd/ vs skill/ mirror drift — stdlib unittest,
no dependencies.

adapters/dot-aidd/scripts/ (and adapters/dot-aidd/extensions/) is a
hand-maintained mirror of skill/scripts/ (and skill/extensions/) — copy-paste,
not automated by anything. Two real drift bugs between these copies were
found and fixed by hand in this same session (a stale check_charter.py with a
broken table parser, and an incomplete mirror PENDING-SYNC.md had documented).
This test exists so that drift is caught by `python -m unittest discover -s
tests` (already run in CI, see .github/workflows/test.yml) instead of by
someone manually exercising the CLI in a real project.

Two layers:

  Layer 1 (textual): every script/extension file that is supposed to be a
  verbatim hand-copy must be byte-identical on both sides. This alone would
  have caught today's check_charter.py bug with nothing more than running the
  test suite.

  Layer 1 also covers extension_registry.py, which has ONE deliberate,
  documented difference (BUNDLED_EXTENSIONS_DIR vs SKILL_EXTENSIONS_DIR path
  resolution — see that file's own docstring on both sides): instead of a
  text diff, it checks structural/functional equivalence (same public
  functions/signatures via ast+inspect, same discover()/set_enabled()
  behavior over a throwaway fixture directory).

  Layer 2 (end-to-end smoke test): actually run `aidd init` (via
  aidd.cli.cmd_init, the real mechanism) to generate a project from
  adapters/dot-aidd/ the way a brand-new user would get it, then run each
  mirrored script against that generated project with minimal real
  arguments (not just --help) and confirm none of them raise an
  ImportError/traceback.

Run: python -m unittest discover -s tests -v
"""
import argparse
import ast
import importlib.util
import inspect
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_SCRIPTS = REPO_ROOT / "skill" / "scripts"
DOTAIDD_SCRIPTS = REPO_ROOT / "adapters" / "dot-aidd" / "scripts"
SKILL_EXTENSIONS = REPO_ROOT / "skill" / "extensions"
DOTAIDD_EXTENSIONS = REPO_ROOT / "adapters" / "dot-aidd" / "extensions"

sys.path.insert(0, str(REPO_ROOT))
import aidd.cli as aidd_cli  # noqa: E402

# Scripts expected to be BYTE-IDENTICAL hand-copies between skill/scripts/ and
# adapters/dot-aidd/scripts/ — everything the mirror is supposed to carry
# verbatim except extension_registry.py (deliberate adaptation, checked
# separately below).
VERBATIM_SCRIPTS = [
    "check_spec.py",
    "check_charter.py",
    "flowmap.py",
    "aidd_memory.py",
    "aidd_memory_import.py",
    "aidd_rules.py",
    "aidd_evidence.py",
    "aidd_status.py",
    "aidd_review.py",
    "aidd_review_items.py",
    "aidd_review_state.py",
    "find_spec.py",
    "aidd_calibrate.py",
    "tasks_to_issues.py",
    "link_pr_to_task.py",
    "sync_issues.py",
]

# Bundled provider extensions mirrored on both sides.
PROVIDER_IDS = ["github", "azure_devops", "bitbucket"]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Layer 1a — verbatim scripts must be byte-identical.
# ---------------------------------------------------------------------------


class TestScriptMirrorTextual(unittest.TestCase):
    def test_verbatim_scripts_match(self):
        mismatches = []
        for name in VERBATIM_SCRIPTS:
            skill_path = SKILL_SCRIPTS / name
            dot_path = DOTAIDD_SCRIPTS / name
            self.assertTrue(skill_path.is_file(), f"missing {skill_path}")
            self.assertTrue(dot_path.is_file(), f"missing {dot_path}")
            skill_text = skill_path.read_text(encoding="utf-8")
            dot_text = dot_path.read_text(encoding="utf-8")
            if skill_text != dot_text:
                mismatches.append(name)
        self.assertEqual(
            mismatches, [],
            "adapters/dot-aidd/scripts/ has drifted from skill/scripts/ for: "
            f"{mismatches}. These files must stay byte-identical hand-copies — "
            "re-copy skill/scripts/<name> over adapters/dot-aidd/scripts/<name>."
        )


# ---------------------------------------------------------------------------
# Layer 1b — bundled provider extensions must be byte-identical too.
# ---------------------------------------------------------------------------


class TestDocsAndTemplatesMirrorTextual(unittest.TestCase):
    """AIDD.md and the spec/qa-audit/review templates are byte-identical copies
    (adapters/dot-aidd/templates/tasks.md is a REDUCED variant: not checked)."""

    PAIRS = [
        ("AIDD.md",),
        ("templates", "spec.md"),
        ("templates", "qa-audit.md"),
        ("templates", "review.html"),
        ("templates", "review-full.html"),
    ]

    def test_docs_and_templates_match(self):
        for parts in self.PAIRS:
            with self.subTest(file="/".join(parts)):
                a = REPO_ROOT.joinpath("skill", *parts)
                b = REPO_ROOT.joinpath("adapters", "dot-aidd", *parts)
                self.assertTrue(a.is_file(), "missing in skill/: %s" % a)
                self.assertTrue(b.is_file(), "missing in adapters/dot-aidd/: %s" % b)
                self.assertEqual(a.read_bytes(), b.read_bytes(),
                                 "%s drifted between skill/ and adapters/dot-aidd/" % "/".join(parts))


class TestExtensionsMirrorTextual(unittest.TestCase):
    def test_provider_extension_files_match(self):
        mismatches = []
        for pid in PROVIDER_IDS:
            skill_dir = SKILL_EXTENSIONS / pid
            dot_dir = DOTAIDD_EXTENSIONS / pid
            self.assertTrue(skill_dir.is_dir(), f"missing {skill_dir}")
            self.assertTrue(dot_dir.is_dir(), f"missing {dot_dir}")
            skill_files = sorted(
                p.relative_to(skill_dir) for p in skill_dir.rglob("*")
                if p.is_file() and "__pycache__" not in p.parts
            )
            dot_files = sorted(
                p.relative_to(dot_dir) for p in dot_dir.rglob("*")
                if p.is_file() and "__pycache__" not in p.parts
            )
            self.assertEqual(skill_files, dot_files, f"{pid}: mirrored file lists differ")
            for rel in skill_files:
                a = (skill_dir / rel).read_text(encoding="utf-8")
                b = (dot_dir / rel).read_text(encoding="utf-8")
                if a != b:
                    mismatches.append(f"{pid}/{rel}")
        self.assertEqual(mismatches, [], f"extension files drifted: {mismatches}")


# ---------------------------------------------------------------------------
# Layer 1c — extension_registry.py: deliberate adaptation, checked for
# functional/structural equivalence instead of a byte diff.
# ---------------------------------------------------------------------------


class TestExtensionRegistryFunctionalEquivalence(unittest.TestCase):
    """extension_registry.py has exactly one deliberate, documented
    difference between the skill/ and adapters/dot-aidd/ copies: the
    BUNDLED_EXTENSIONS_DIR (dot-aidd) vs SKILL_EXTENSIONS_DIR (skill) module
    constant, because in the deployed .aidd/ copy "bundled with AIDD itself"
    and "this project" collapse into the same directory (see the module's own
    docstring on both sides). Everything else must be equivalent. This is
    checked three ways: (1) same public function names + signatures, (2) an
    AST diff of both files with the docstring and that one constant's
    assignment stripped out, (3) the same discover()/set_enabled() behavior
    exercised end-to-end over an identical throwaway fixture tree.
    """

    @classmethod
    def setUpClass(cls):
        cls.skill_mod = _load_module(
            SKILL_SCRIPTS / "extension_registry.py", "mirror_test_skill_ext_registry"
        )
        cls.dot_mod = _load_module(
            DOTAIDD_SCRIPTS / "extension_registry.py", "mirror_test_dot_ext_registry"
        )

    def test_public_functions_match_name_and_signature(self):
        # Return-type annotations that reference the locally-defined
        # Extension class stringify with each throwaway module's own name
        # (e.g. "mirror_test_skill_ext_registry.Extension") — strip those
        # two prefixes before comparing so the check isn't tripped up by an
        # artifact of how this test loads the two copies, not a real diff.
        def public_functions(mod, own_module_name):
            result = {}
            for n in dir(mod):
                obj = getattr(mod, n)
                if n.startswith("_") or not inspect.isfunction(obj):
                    continue
                sig = str(inspect.signature(obj)).replace(f"{own_module_name}.", "")
                result[n] = sig
            return result

        skill_funcs = public_functions(self.skill_mod, "mirror_test_skill_ext_registry")
        dot_funcs = public_functions(self.dot_mod, "mirror_test_dot_ext_registry")
        self.assertEqual(set(skill_funcs), set(dot_funcs), "public function set differs")
        for name in skill_funcs:
            self.assertEqual(
                skill_funcs[name], dot_funcs[name], f"signature differs for {name}()"
            )

    def test_public_class_shape_matches(self):
        def public_members(cls_obj):
            return sorted(n for n in dir(cls_obj) if not n.startswith("_"))

        self.assertEqual(
            public_members(self.skill_mod.Extension),
            public_members(self.dot_mod.Extension),
        )

    def test_function_bodies_match_ignoring_docstrings_and_dir_constant_name(self):
        """A deeper structural check than signatures alone: parse both files'
        actual function bodies (module-level and Extension's methods) with
        ast, drop each function's own docstring (prose legitimately differs
        between the two copies — see both files' module docstrings), rename
        the one deliberately-different constant (BUNDLED_EXTENSIONS_DIR vs
        SKILL_EXTENSIONS_DIR) and its matching Extension.source string label
        ("bundled" vs "first-party" -- the same deliberate distinction, see
        the Extension class's own docstring on both sides) to common
        placeholders, and compare the resulting AST dumps. Anything that
        still differs is real logic drift, not documentation or the
        documented path/label adaptation."""
        skill_src = (SKILL_SCRIPTS / "extension_registry.py").read_text(encoding="utf-8")
        dot_src = (DOTAIDD_SCRIPTS / "extension_registry.py").read_text(encoding="utf-8")

        def parse_normalized(source):
            source = source.replace("BUNDLED_EXTENSIONS_DIR", "EXTENSIONS_DIR_CONST")
            source = source.replace("SKILL_EXTENSIONS_DIR", "EXTENSIONS_DIR_CONST")
            source = source.replace('"bundled"', '"SRC_LABEL"')
            source = source.replace('"first-party"', '"SRC_LABEL"')
            return ast.parse(source)

        def function_defs(tree):
            return {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}

        def body_dump(node):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body = body[1:]  # drop this function's own docstring
            return "\n".join(ast.dump(stmt, annotate_fields=True) for stmt in body)

        skill_defs = function_defs(parse_normalized(skill_src))
        dot_defs = function_defs(parse_normalized(dot_src))
        self.assertEqual(set(skill_defs), set(dot_defs), "function definitions differ")

        mismatches = [
            name for name in skill_defs
            if body_dump(skill_defs[name]) != body_dump(dot_defs[name])
        ]
        self.assertEqual(
            mismatches, [],
            f"extension_registry.py function bodies differ beyond the deliberate "
            f"dir-constant rename, for: {mismatches} — real logic drift, fix by hand."
        )

    def test_discover_and_set_enabled_behave_the_same(self):
        with tempfile.TemporaryDirectory() as d:
            ext_dir = Path(d) / "extensions"
            (ext_dir / "demo").mkdir(parents=True)
            manifest = {
                "id": "demo",
                "name": "Demo",
                "description": "d",
                "version": "1.0.0",
                "kind": "provider",
                "entry": "provider.py",
            }
            (ext_dir / "demo" / "manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            (ext_dir / "demo" / "provider.py").write_text("X = 1\n", encoding="utf-8")

            with patch.object(self.skill_mod, "SKILL_EXTENSIONS_DIR", ext_dir), patch.object(
                self.dot_mod, "BUNDLED_EXTENSIONS_DIR", ext_dir
            ):
                skill_found = self.skill_mod.discover()
                dot_found = self.dot_mod.discover()
                self.assertEqual(len(skill_found), 1)
                self.assertEqual(len(dot_found), 1)
                self.assertEqual(skill_found[0].id, dot_found[0].id)
                self.assertEqual(skill_found[0].kind, dot_found[0].kind)
                self.assertTrue(skill_found[0].enabled)
                self.assertTrue(dot_found[0].enabled)

                self.assertTrue(self.skill_mod.set_enabled("demo", False))
                self.assertTrue(self.dot_mod.set_enabled("demo", False))

                skill_after = self.skill_mod.discover(include_disabled=True)
                dot_after = self.dot_mod.discover(include_disabled=True)
                self.assertFalse(skill_after[0].enabled)
                self.assertFalse(dot_after[0].enabled)


# ---------------------------------------------------------------------------
# Layer 2 — end-to-end smoke test via a real `aidd init`.
# ---------------------------------------------------------------------------


class TestDotAiddInitSmoke(unittest.TestCase):
    """Generate a real project from adapters/dot-aidd/ via aidd.cli.cmd_init
    (the actual `aidd init` mechanism), the way a brand-new user would get
    it, then run each mirrored script against it with minimal real arguments
    and confirm none of them raise an ImportError/traceback."""

    def test_generated_scripts_run_without_import_errors(self):
        with tempfile.TemporaryDirectory() as d:
            project_root = Path(d) / "myproject"
            project_root.mkdir()

            rc = aidd_cli.cmd_init(argparse.Namespace(target=str(project_root), force=False))
            self.assertEqual(rc, 0)

            scripts_dir = project_root / ".aidd" / "scripts"
            self.assertTrue(scripts_dir.is_dir())
            self.assertTrue((project_root / ".aidd" / "extensions").is_dir())

            def run(script, script_args):
                return subprocess.run(
                    [sys.executable, str(scripts_dir / script), *script_args],
                    cwd=str(project_root),
                    capture_output=True,
                    text=True,
                )

            # tasks_to_issues.py with no args: this imports the 3 bundled
            # providers on startup (extension_registry.get_providers()) before
            # argparse even runs — a real exercise of every provider.py import
            # path, not just --help. Usage error, exit 2, no traceback.
            r = run("tasks_to_issues.py", [])
            self.assertEqual(r.returncode, 2, f"stdout={r.stdout!r} stderr={r.stderr!r}")
            self.assertNotIn("Traceback", r.stderr)
            self.assertNotIn("ImportError", r.stderr)

            # extension_registry.py list: the 3 bundled providers must show up.
            r = run("extension_registry.py", ["list"])
            self.assertEqual(r.returncode, 0, f"stdout={r.stdout!r} stderr={r.stderr!r}")
            self.assertNotIn("Traceback", r.stderr)
            for pid in PROVIDER_IDS:
                self.assertIn(pid, r.stdout, f"{pid} missing from `extension_registry.py list` output")

            # A minimal real spec fixture for check_spec.py / find_spec.py /
            # check_charter.py to run against instead of an empty folder.
            spec_dir = project_root / "specs" / "001-demo"
            spec_dir.mkdir(parents=True)
            (spec_dir / "spec.md").write_text("# Demo spec\n", encoding="utf-8")
            (spec_dir / "mockup-audit.md").write_text(
                "## Use cases -> screens\n"
                "| Use case | Screen |\n"
                "|---|---|\n"
                "| US-001 | SCREEN-01 |\n",
                encoding="utf-8",
            )
            (spec_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
            (spec_dir / "tasks.md").write_text(
                "| Task | Codes satisfied |\n|---|---|\n| T-001 | SCREEN-01 |\n",
                encoding="utf-8",
            )

            r = run("check_spec.py", [str(spec_dir)])
            self.assertIn(r.returncode, (0, 1), f"stdout={r.stdout!r} stderr={r.stderr!r}")
            self.assertNotIn("Traceback", r.stderr)

            r = run("find_spec.py", ["--list"])
            self.assertIn(r.returncode, (0, 1), f"stdout={r.stdout!r} stderr={r.stderr!r}")
            self.assertNotIn("Traceback", r.stderr)

            (project_root / "charter.md").write_text(
                "## Checkable rules\n"
                "| Rule | Type | Pattern | Applies to (glob) |\n"
                "|---|---|---|---|\n",
                encoding="utf-8",
            )
            r = run("check_charter.py", [str(project_root)])
            self.assertEqual(r.returncode, 0, f"stdout={r.stdout!r} stderr={r.stderr!r}")
            self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()
