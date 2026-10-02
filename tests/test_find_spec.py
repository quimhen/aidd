"""Tests for scripts/find_spec.py — stdlib unittest, no dependencies.

Run: python -m unittest discover -s tests -v
"""
import subprocess
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import find_spec  # noqa: E402


class TestTokenizeQuery(unittest.TestCase):
    def test_extracts_codes_and_words(self):
        codes, words = find_spec.tokenize_query(["fix the SCREEN-01 login button"])
        self.assertEqual(codes, {"SCREEN-01"})
        self.assertIn("login", words)
        self.assertIn("button", words)

    def test_stopwords_and_short_words_dropped(self):
        codes, words = find_spec.tokenize_query(["the a an of to in on for"])
        self.assertEqual(words, [])

    def test_unicode_words_not_mangled(self):
        # Portuguese: ç, ã must survive — the old Latin-only whitelist used to break this.
        _, words = find_spec.tokenize_query(["opção de pagamento"])
        self.assertIn("opção", words)

    def test_cjk_query_yields_a_token_not_nothing(self):
        _, words = find_spec.tokenize_query(["修改登录按钮"])
        self.assertTrue(any(len(w) >= 1 for w in words), "CJK query produced zero tokens")


class TestTokenizeText(unittest.TestCase):
    def test_dedupes_and_lowercases(self):
        # "screen" is itself a stopword (too generic — appears in nearly every doc), so
        # use a distinct word to check dedup/lowercasing without tripping the filter.
        words = find_spec.tokenize_text("Login LOGIN login Session")
        self.assertEqual(words, {"login", "session"})


class TestToonRoundTrip(unittest.TestCase):
    def test_index_survives_dumps_and_loads(self):
        index = {
            "version": find_spec.INDEX_VERSION,
            "generated": "2026-01-01T00:00:00+00:00",
            "specs": {
                "001-login": {
                    "path": "001-login",
                    "title": "Login, with a comma",
                    "codes": ["SCREEN-01", "CTL-001"],
                    "words": ["login", "session"],
                    "tree": [["US-001", "SCREEN-01", "CTL-001"]],
                    "files": {"spec.md": 1700000000.123, "plan.md": 1700000001.0},
                }
            },
        }
        text = find_spec.dumps_index(index)
        restored = find_spec.loads_index(text)
        entry = restored["specs"]["001-login"]
        self.assertEqual(entry["title"], "Login, with a comma")
        self.assertEqual(set(entry["codes"]), {"SCREEN-01", "CTL-001"})
        self.assertEqual(set(entry["words"]), {"login", "session"})
        self.assertEqual(entry["tree"], [["US-001", "SCREEN-01", "CTL-001"]])
        self.assertAlmostEqual(entry["files"]["spec.md"], 1700000000.123, places=2)

    def test_empty_codes_and_words_round_trip_as_empty(self):
        index = {
            "version": find_spec.INDEX_VERSION, "generated": "x",
            "specs": {"a": {"path": "a", "title": "", "codes": [], "words": [], "tree": [], "files": {}}},
        }
        restored = find_spec.loads_index(find_spec.dumps_index(index))
        entry = restored["specs"]["a"]
        self.assertEqual(entry["codes"], [])
        self.assertEqual(entry["words"], [])
        self.assertEqual(entry["tree"], [])


class TestRelationshipGraph(unittest.TestCase):
    MOCKUP_AUDIT = (
        "## Screen inventory\n"
        "| SCREEN-XX | id | Name | Type | Uses (COMP-nnn list) | Use case (US-nnn) | Purpose |\n"
        "|---|---|---|---|---|---|---|\n"
        "| SCREEN-01 | | Login | view | COMP-001 | US-001 | |\n"
        "\n"
        "## Component inventory\n"
        "| COMP-nnn | Name | Used in (SCREEN-XX list) | Contains (CTL-nnn list) | PR/Spec ref |\n"
        "|---|---|---|---|---|\n"
        "| COMP-001 | LoginForm | SCREEN-01 | CTL-001 | |\n"
        "\n"
        "## Control inventory\n"
        "| CTL-nnn | Screen or COMP-nnn | Text | id | Handler | Class | Calls API-nnn | Status | PR/Spec ref |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
        "| CTL-001 | COMP-001 | Save | | | | API-001 | Explicit | |\n"
    )

    def test_edges_reflect_the_real_hierarchy(self):
        edges = find_spec.parse_relationship_edges(self.MOCKUP_AUDIT)
        self.assertIn(("US-001", "SCREEN-01"), edges)
        self.assertIn(("SCREEN-01", "COMP-001"), edges)
        self.assertIn(("COMP-001", "CTL-001"), edges)
        self.assertIn(("CTL-001", "API-001"), edges)

    def test_paths_go_root_to_leaf(self):
        edges = find_spec.parse_relationship_edges(self.MOCKUP_AUDIT)
        paths = find_spec.build_tree_paths(edges)
        self.assertIn(["US-001", "SCREEN-01", "COMP-001", "CTL-001", "API-001"], paths)

    def test_shared_component_appears_under_every_screen(self):
        md = (
            "## Screen inventory\n"
            "| SCREEN-XX | id | Name | Type | Uses (COMP-nnn list) | Use case (US-nnn) | Purpose |\n"
            "|---|---|---|---|---|---|---|\n"
            "| SCREEN-01 | | A | view | COMP-001 | US-001 | |\n"
            "| SCREEN-02 | | B | view | COMP-001 | US-002 | |\n"
        )
        edges = find_spec.parse_relationship_edges(md)
        paths = find_spec.build_tree_paths(edges)
        under_s1 = any(p[:2] == ["US-001", "SCREEN-01"] and "COMP-001" in p for p in paths)
        under_s2 = any(p[:2] == ["US-002", "SCREEN-02"] and "COMP-001" in p for p in paths)
        self.assertTrue(under_s1 and under_s2, "shared component should appear under both screens")

    def test_screen_with_no_use_case_roots_under_unassigned(self):
        md = (
            "## Screen inventory\n"
            "| SCREEN-XX | id | Name | Type | Uses | Use case (US-nnn) | Purpose |\n"
            "|---|---|---|---|---|---|---|\n"
            "| SCREEN-09 | | Orphan | view | | | |\n"
        )
        edges = find_spec.parse_relationship_edges(md)
        self.assertIn(("UNASSIGNED", "SCREEN-09"), edges)


class TestEndToEnd(unittest.TestCase):
    """Exercises the CLI exactly as a user/hook would invoke it."""

    def _write_spec(self, specs_root: Path, name: str, mockup_audit: str, extra_files=None):
        d = specs_root / name
        d.mkdir(parents=True)
        (d / "mockup-audit.md").write_text(mockup_audit, encoding="utf-8")
        (d / "spec.md").write_text(f"# Spec: {name}\n", encoding="utf-8")
        for fname, content in (extra_files or {}).items():
            (d / fname).write_text(content, encoding="utf-8")
        return d

    def _run(self, cwd, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "find_spec.py"), *args],
            cwd=str(cwd), capture_output=True, text=True, timeout=15,
        )

    def test_no_specs_dir_is_safe_to_create(self):
        with TemporaryDirectory() as d:
            result = self._run(d, "anything")
            self.assertEqual(result.returncode, 1)
            self.assertIn("Safe to proceed", result.stdout)

    def test_no_match_exits_1(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "specs").mkdir()
            self._write_spec(root / "specs", "001-billing", "## Screen inventory\n| SCREEN-01 |\n")
            result = self._run(root, "totally-unrelated-quantum-widget")
            self.assertEqual(result.returncode, 1)
            self.assertIn("No match found", result.stdout)

    def test_exact_code_match_exits_0_and_ranks_it_top(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "specs").mkdir()
            self._write_spec(
                root / "specs", "002-auth",
                "## Control inventory\n| CTL-nnn |\n|---|\n| CTL-042 |\n",
            )
            result = self._run(root, "CTL-042")
            self.assertEqual(result.returncode, 0)
            self.assertIn("002-auth", result.stdout)
            self.assertIn("AMEND", result.stdout)

    def test_index_is_reused_when_nothing_changed(self):
        """Second call must not rebuild — same generated timestamp both times."""
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "specs").mkdir()
            self._write_spec(root / "specs", "003-x", "## Control inventory\n| CTL-nnn |\n|---|\n| CTL-001 |\n")
            self._run(root, "--reindex")
            first = (root / "specs" / "index.toon").read_text(encoding="utf-8")
            time.sleep(0.05)
            self._run(root, "CTL-001")
            second = (root / "specs" / "index.toon").read_text(encoding="utf-8")
            self.assertEqual(first, second, "index.toon should not be rewritten when nothing changed")

    def test_index_rebuilds_after_a_real_edit(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "specs").mkdir()
            spec_dir = self._write_spec(root / "specs", "004-y", "## Control inventory\n| CTL-nnn |\n|---|\n| CTL-001 |\n")
            self._run(root, "--reindex")
            time.sleep(1.1)  # ensure a distinguishable mtime — filesystems commonly quantize to 1s
            (spec_dir / "mockup-audit.md").write_text(
                "## Control inventory\n| CTL-nnn |\n|---|\n| CTL-002 |\n", encoding="utf-8"
            )
            result = self._run(root, "CTL-002")
            self.assertEqual(result.returncode, 0)
            self.assertIn("004-y", result.stdout)

    def test_list_reads_from_index_not_files(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "specs").mkdir()
            self._write_spec(root / "specs", "005-z", "## Control inventory\n| CTL-nnn |\n|---|\n| CTL-001 |\n")
            result = self._run(root, "--list")
            self.assertEqual(result.returncode, 0)
            self.assertIn("005-z", result.stdout)

    def test_tree_flag_prints_graph(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "specs").mkdir()
            md = (
                "## Screen inventory\n"
                "| SCREEN-XX | id | Name | Type | Uses | Use case (US-nnn) | Purpose |\n"
                "|---|---|---|---|---|---|---|\n"
                "| SCREEN-01 | | Login | view | | US-001 | |\n"
            )
            self._write_spec(root / "specs", "006-w", md)
            result = self._run(root, "--tree", "006-w")
            self.assertEqual(result.returncode, 0)
            self.assertIn("US-001", result.stdout)
            self.assertIn("SCREEN-01", result.stdout)

class TestIndexOptimization(unittest.TestCase):
    def _mk(self, root: Path, name: str, body: str):
        d = root / "specs" / name
        d.mkdir(parents=True)
        (d / "spec.md").write_text(body, encoding="utf-8")
        return d

    def _run(self, cwd, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "find_spec.py"), *args],
            cwd=str(cwd), capture_output=True, text=True, timeout=15,
        )

    def test_version_is_3(self):
        self.assertEqual(find_spec.INDEX_VERSION, 3)

    def test_old_version_index_is_rebuilt(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            self._mk(root, "001-a", "# A\nfacturacion electronica\n")
            self._run(root, "--reindex")
            idx = root / "specs" / "index.toon"
            idx.write_text(idx.read_text(encoding="utf-8").replace("version: 3", "version: 2"), encoding="utf-8")
            self.assertIsNone(find_spec.load_index(root / "specs"))
            result = self._run(root, "facturacion")
            self.assertEqual(result.returncode, 0)
            self.assertIn("rebuilt", result.stdout)
            self.assertIn("version: 3", idx.read_text(encoding="utf-8"))

    def test_words_capped_at_25(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            body = "# Big\n" + " ".join(f"termino{chr(97 + i % 26)}{chr(97 + i // 26)}x" for i in range(200))
            self._mk(root, "001-big", body)
            specs = root / "specs"
            idx = find_spec.build_index(specs, [specs / "001-big"])
            self.assertEqual(len(idx["specs"]["001-big"]["words"]), find_spec.MAX_WORDS_PER_SPEC)
            self.assertEqual(find_spec.MAX_WORDS_PER_SPEC, 25)

    def test_stopword_noise_absent(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            noise = "como cada entre desde hasta sobre cuando donde tambien puede deben "
            self._mk(root, "001-a", "# A\n" + noise * 5 + "inventario\n")
            specs = root / "specs"
            words = find_spec.build_index(specs, [specs / "001-a"])["specs"]["001-a"]["words"]
            for w in noise.split():
                self.assertNotIn(w, words)
            self.assertIn("inventario", words)

    def test_numbers_hex_and_short_dropped_accents_folded(self):
        terms = find_spec.index_terms("2026 deadbeef12 abc Opción 12345 cafe")
        self.assertNotIn("2026", terms)
        self.assertNotIn("deadbeef12", terms)
        self.assertNotIn("abc", terms)
        self.assertIn("opcion", terms)

    def test_tfidf_prefers_distinctive_terms(self):
        tfs = {
            "a": find_spec.index_terms("login login login sistema sistema"),
            "b": find_spec.index_terms("pagos pagos sistema"),
        }
        ranked = find_spec.rank_tfidf(tfs, limit=1)
        self.assertEqual(ranked["a"], ["login"])
        self.assertEqual(ranked["b"], ["pagos"])

    def test_accent_insensitive_query_finds_spec(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            self._mk(root, "001-a", "# A\nGestión de facturación electrónica\n")
            self._mk(root, "002-b", "# B\nreportes de inventario\n")
            for q in ("facturacion", "facturación", "FACTURACIÓN"):
                result = self._run(root, q)
                self.assertEqual(result.returncode, 0, q)
                self.assertIn("Top match: 001-a", result.stdout)

    def test_memory_hits_for_degrades_to_empty(self):
        self.assertEqual(find_spec.memory_hits_for({"SCREEN-01"}), [])
        self.assertEqual(find_spec.memory_hits_for(set(), Path(".")), [])

    def test_memory_hits_for_reads_memory(self):
        import aidd_memory
        with TemporaryDirectory() as d:
            root = Path(d)
            aidd_memory.add_entry(root, type="decision", title="Block save when empty", codes=["SCREEN-08"])
            lines = find_spec.memory_hits_for({"SCREEN-08"}, root)
            self.assertEqual(len(lines), 1)
            self.assertIn("decision", lines[0])
            self.assertIn("Block save when empty", lines[0])


class TestAuditRev1(unittest.TestCase):
    """End-to-end regressions from the independent audit (Rev 1): the CLI output,
    not just the helpers."""

    def _project(self, d, spec_text):
        spec = Path(d) / "specs" / "001-login"
        spec.mkdir(parents=True)
        (spec / "spec.md").write_text(spec_text, encoding="utf-8")
        return Path(d)

    def _search(self, root, *terms):
        return subprocess.run([sys.executable, str(SCRIPTS_DIR / "find_spec.py"), *terms],
                              cwd=str(root), capture_output=True, text=True, encoding="utf-8")

    def test_memory_lines_are_printed_by_the_cli(self):
        import aidd_memory
        with TemporaryDirectory() as d:
            root = self._project(d, "# Login\nSCREEN-08 shows the order ticket\n")
            aidd_memory.add_entry(root, type="decision", title="Block save when empty", codes=["SCREEN-08"])
            r = self._search(root, "SCREEN-08")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("Memory", r.stdout)
            self.assertIn("Block save when empty", r.stdout)

    def test_search_without_memory_is_unchanged(self):
        with TemporaryDirectory() as d:
            root = self._project(d, "# Login\nSCREEN-08 shows the order ticket\n")
            r = self._search(root, "SCREEN-08")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertNotIn("Memory", r.stdout)

    def test_fulltext_fallback_when_index_misses_a_real_word(self):
        filler = " ".join("alfa" + chr(97 + i) for i in range(26))
        with TemporaryDirectory() as d:
            root = self._project(d, f"# Login\n{filler}\nla zanahoria es el requisito raro\n")
            r = self._search(root, "zanahoria")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("001-login", r.stdout)
            self.assertIn("full-text", r.stdout)

    def test_fallback_does_not_invent_matches(self):
        with TemporaryDirectory() as d:
            root = self._project(d, "# Login\nSCREEN-08 shows the order ticket\n")
            r = self._search(root, "xylophone")
            self.assertEqual(r.returncode, 1)
            self.assertIn("No match", r.stdout)

    def test_short_query_words_match_through_the_fallback(self):
        with TemporaryDirectory() as d:
            root = self._project(d, "# Login\nthe pdf export uses the sap bridge\n")
            r = self._search(root, "pdf")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("001-login", r.stdout)


if __name__ == "__main__":
    unittest.main()
