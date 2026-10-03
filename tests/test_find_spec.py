"""Tests for scripts/find_spec.py — stdlib unittest, no dependencies.

Run: python -m unittest discover -s tests -v
"""
import contextlib
import io
import os
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

    def test_version_is_4(self):
        self.assertEqual(find_spec.INDEX_VERSION, 4)

    def test_old_version_index_is_rebuilt(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            self._mk(root, "001-a", "# A\nfacturacion electronica\n")
            specs = root / "specs"
            self._run(root, "--reindex")
            idx = specs / "index.toon"
            lines = idx.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], f"version: {find_spec.INDEX_VERSION}")
            lines[0] = "version: 3"
            idx.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self.assertTrue(idx.read_text(encoding="utf-8").startswith("version: 3"))
            self.assertIsNone(find_spec.load_index(specs))
            index, rebuilt, _changed = find_spec.get_index(specs, [specs / "001-a"])
            self.assertTrue(rebuilt)
            self.assertEqual(index["version"], find_spec.INDEX_VERSION)
            result = self._run(root, "facturacion")
            self.assertEqual(result.returncode, 0)
            self.assertIn("version: 4", idx.read_text(encoding="utf-8"))

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


SPEC_MD = """# Spec

## Acceptance cases

| ID | Case |
|---|---|
| AC-001 | User logs in |
| AC-002 | User logs out |

## Functional requirements

| ID | Requirement | Cites |
|---|---|---|
| FR-001 | Login works | AC-001 |
| FR-002 | Logout works | |
"""

TASKS_MD = """# Tasks

| ID | Task | Target | Codes satisfied |
|---|---|---|---|
| T-16 | Sync sales | SBO.DAL/PosVentaSync.cs | FR-005, FR-009, FR-010 |
"""

CONTRACTS_MD = """# Contracts

## API-001 Create sale

| API-002 | GET | /sales |
"""


class TestGraphParsers(unittest.TestCase):
    def test_spec_nodes_and_edges(self):
        nodes, edges = find_spec.parse_spec_nodes(SPEC_MD)
        ids = {n["id"]: n["kind"] for n in nodes}
        self.assertEqual(ids.get("AC-001"), "AC")
        self.assertEqual(ids.get("AC-002"), "AC")
        self.assertEqual(ids.get("FR-001"), "FR")
        self.assertEqual(ids.get("FR-002"), "FR")
        self.assertIn(("FR-001", "AC-001", "cites"), edges)
        self.assertEqual(len([e for e in edges if e[0] == "FR-002"]), 0)

    def test_task_edges(self):
        nodes, edges = find_spec.parse_task_nodes(TASKS_MD)
        self.assertEqual([n["id"] for n in nodes], ["T-16"])
        self.assertEqual(nodes[0]["kind"], "T")
        for fr in ("FR-005", "FR-009", "FR-010"):
            self.assertIn(("T-16", fr, "satisfies"), edges)
        self.assertIn(("T-16", "SBO.DAL/PosVentaSync.cs", "targets"), edges)

    def test_contracts_only_dir(self):
        with TemporaryDirectory() as d:
            (Path(d) / "contracts.md").write_text(CONTRACTS_MD, encoding="utf-8")
            g = find_spec.build_graph(Path(d))
        self.assertIn("API-001", g["nodes"])
        self.assertIn("API-002", g["nodes"])
        self.assertEqual(g["nodes"]["API-001"]["kind"], "API")
        self.assertEqual(g["edges"], [])

    def test_empty_and_malformed(self):
        for text in ("", "not a table\n|||\n## Acceptance cases\n| x"):
            for fn in (find_spec.parse_spec_nodes, find_spec.parse_task_nodes,
                       find_spec.parse_contract_nodes):
                nodes, edges = fn(text)
                self.assertEqual((nodes, edges), ([], []))
        with TemporaryDirectory() as d:
            g = find_spec.build_graph(Path(d))
        self.assertEqual(g["nodes"], {})
        self.assertEqual(g["edges"], [])

    def test_duplicate_ids_keep_first(self):
        text = SPEC_MD.replace("| AC-002 | User logs out |",
                               "| AC-001 | Duplicate |")
        with TemporaryDirectory() as d:
            (Path(d) / "spec.md").write_text(text, encoding="utf-8")
            g = find_spec.build_graph(Path(d))
        self.assertEqual(g["nodes"]["AC-001"]["label"], "User logs in")


GQ_SPEC = """# Demo

## Acceptance cases

| ID | Real data | Expected |
|----|-----------|----------|
| AC-001 | Sale 123 synced | ok |
| AC-002 | Sale 456 retried | ok |

## Functional requirements

| ID | Requirement | Cites |
|----|-------------|-------|
| FR-005 | Sync sales to SAP | AC-001, API-003 |
| FR-009 | Retry failed sync | AC-002 |
"""

GQ_TASKS = """# Tasks

| ID | Title | Codes | Target |
|----|-------|-------|--------|
| T-16 | Implement sync | FR-005, FR-009 | SBO.DAL/PosVentaSync.cs |
"""

GQ_CONTRACTS = """# Contracts

## API-003 POST /sales/sync

| ID | Purpose |
|----|---------|
| API-003 | Sync one sale |
"""


class TestGraphQuery(unittest.TestCase):
    def _spec(self, root, name="001-demo", tasks=GQ_TASKS):
        d = root / "specs" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "spec.md").write_text(GQ_SPEC, encoding="utf-8")
        (d / "tasks.md").write_text(tasks, encoding="utf-8")
        (d / "contracts.md").write_text(GQ_CONTRACTS, encoding="utf-8")
        return d

    def _index(self, root):
        specs = root / "specs"
        dirs = sorted(p for p in specs.iterdir() if p.is_dir())
        return find_spec.get_index(specs, dirs)

    def _code(self, index, code, specs):
        lines = []
        found = find_spec.print_code(index, code, specs_root=specs, out=lines.append)
        return found, lines

    def test_graph_round_trip_with_special_chars(self):
        g = {"nodes": {"T-1": {"kind": "T", "label": "a b", "file": "tasks.md", "line": 3},
                       "FR-1": {"kind": "FR", "label": "x", "file": "spec.md", "line": 9}},
             "edges": [("T-1", "C:/src/a;b:c.cs", "targets"), ("T-1", "FR-1", "satisfies")]}
        back = find_spec.decode_graph(find_spec.encode_graph(g))
        self.assertEqual(set(back["nodes"]), {"T-1", "FR-1"})
        self.assertEqual(back["nodes"]["T-1"]["line"], 3)
        self.assertEqual(sorted(back["edges"]), sorted(g["edges"]))

    def test_decode_garbage_never_raises(self):
        for cell in (None, "", "garbage", "N:a", "E:x", ";;;", "N:a:b:c:notint:d", "%%%:;:"):
            g = find_spec.decode_graph(cell)
            self.assertEqual(set(g), {"nodes", "edges"})

    def test_index_graph_contains_codes(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            self._spec(root)
            index, _r, _c = self._index(root)
            g = find_spec.decode_graph(index["specs"]["001-demo"]["graph"])
            for code in ("API-003", "T-16", "FR-005", "AC-001"):
                self.assertIn(code, g["nodes"])

    def test_print_code_api_and_task(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            self._spec(root)
            index, _r, _c = self._index(root)
            for code, kind in (("API-003", "API"), ("T-16", "T")):
                found, lines = self._code(index, code, root / "specs")
                self.assertTrue(found)
                self.assertLessEqual(len(lines), 25)
                self.assertIn(code, lines[0])
                self.assertIn(kind, lines[0])
            _f, lines = self._code(index, "t-16", root / "specs")
            text = "\n".join(lines)
            self.assertIn("FR-005", text)
            self.assertIn("FR-009", text)
            self.assertIn("SBO.DAL/PosVentaSync.cs", text)

    def test_print_code_unknown(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            self._spec(root)
            index, _r, _c = self._index(root)
            found, lines = self._code(index, "API-999", root / "specs")
            self.assertFalse(found)
            self.assertIn("No node", lines[0])

    def test_two_specs_share_budget(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            self._spec(root, "001-demo")
            self._spec(root, "002-other")
            index, _r, _c = self._index(root)
            found, lines = self._code(index, "API-003", root / "specs")
            self.assertTrue(found)
            self.assertLessEqual(len(lines), 25)
            self.assertGreaterEqual(len([ln for ln in lines if ln.startswith("API-003")]), 2)

    def test_tree_backend_only_non_empty(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            self._spec(root)
            index, _r, _c = self._index(root)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                find_spec.print_tree(index["specs"]["001-demo"])
            out = buf.getvalue()
            self.assertNotIn("no structure captured", out)
            self.assertIn("FR-005", out)
            self.assertTrue("AC-001" in out or "T-16" in out)

    def test_memory_neighbour_in_graph(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            self._spec(root)
            try:
                sys.path.insert(0, str(SCRIPTS_DIR))
                import aidd_memory
                aidd_memory.add_entry(root, type="decision", title="Sync uses API-003",
                                      codes=["API-003"], date="2026-10-01")
            except Exception as e:  # pragma: no cover
                nodes, edges = find_spec.memory_nodes_for({"API-003"}, root=root)
                self.assertEqual((nodes, edges), ([], []))
                self.skipTest(f"memory not creatable ({e}); AC-004 needs manual check")
            index, _r, _c = self._index(root)
            g = find_spec.decode_graph(index["specs"]["001-demo"]["graph"])
            mems = [k for k in g["nodes"] if k.startswith("MEM-")]
            self.assertTrue(mems)
            self.assertIn((mems[0], "API-003", "mentions"), g["edges"])
            _f, lines = self._code(index, "API-003", root / "specs")
            self.assertTrue(any("MEM-" in ln for ln in lines))

    def test_incremental_only_changed_spec(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            self._spec(root, "001-demo")
            d2 = self._spec(root, "002-other")
            specs = root / "specs"
            index, rebuilt, _c = self._index(root)
            self.assertTrue(rebuilt)
            before1 = dict(index["specs"]["001-demo"])
            before2 = dict(index["specs"]["002-other"])
            tasks = d2 / "tasks.md"
            tasks.write_text(GQ_TASKS.replace("T-16", "T-17"), encoding="utf-8")
            future = time.time() + 10
            os.utime(tasks, (future, future))
            dirs = sorted(p for p in specs.iterdir() if p.is_dir())
            self.assertEqual(find_spec.stale_spec_names(index, dirs), {"002-other"})
            index2, rebuilt2, changed = find_spec.get_index(specs, dirs)
            self.assertTrue(rebuilt2)
            self.assertEqual(changed, {"002-other"})
            self.assertEqual(index2["specs"]["001-demo"]["graph"], before1["graph"])
            self.assertEqual(index2["specs"]["001-demo"]["files"], before1["files"])
            self.assertNotEqual(index2["specs"]["002-other"]["graph"], before2["graph"])
            self.assertIn("T-17", find_spec.decode_graph(index2["specs"]["002-other"]["graph"])["nodes"])


if __name__ == "__main__":
    unittest.main()
