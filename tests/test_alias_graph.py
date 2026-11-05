"""Tests for the alias graph layer (spec 007 amendment 06, tasks T-35..T-41).
FR-250..FR-257, AC-291..AC-295, AC-297..AC-299.
"""
import contextlib
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "skill" / "scripts"))
sys.path.insert(0, str(HERE))

FIXTURE_TEXT = (
    "version: 1\n"
    "generated: 2026-11-03T00:00:00+00:00\n"
    "aliases[2]{old,new,scope,reason}:\n"
    "  ordr_table.dart,oped_table.dart,mobile,F30\n"
    "  ocrd_table.dart,opar_table.dart,mobile,F30\n"
)


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args, **kwargs)


class AliasGraph(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.root = self.tmp / "proj"
        self.root.mkdir(parents=True, exist_ok=True)
        self.toon_path = self.root / ".aidd" / "graphs" / "path-aliases.toon"

    def tearDown(self):
        self._tmp.cleanup()

    def _write_fixture(self):
        self.toon_path.parent.mkdir(parents=True, exist_ok=True)
        self.toon_path.write_text(FIXTURE_TEXT, encoding="utf-8")
        return self.toon_path

    def test_parse_and_load_rows(self):
        import alias_graph
        rows = alias_graph.parse_aliases(FIXTURE_TEXT)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], {"old": "ordr_table.dart", "new": "oped_table.dart", "scope": "mobile", "reason": "F30"})
        self.assertEqual(rows[1], {"old": "ocrd_table.dart", "new": "opar_table.dart", "scope": "mobile", "reason": "F30"})

        toon = self._write_fixture()
        loaded = alias_graph.load_aliases(toon)
        self.assertEqual(loaded, rows)

    def test_bad_file_gives_empty(self):
        import alias_graph
        self.assertEqual(alias_graph.load_aliases(self.root / "does_not_exist.toon"), [])
        bad = self.root / "bad.toon"
        bad.write_bytes(b"\xff\x00{bad bytes")
        self.assertEqual(alias_graph.load_aliases(bad), [])

        bad_text = (
            "version: 1\n"
            "aliases[3]{old,new,scope,reason}:\n"
            "  invalid_row_only_one_field\n"
            "  ../escape.dart,normal.dart,scope,reason\n"
            "  slash/bad.dart,normal.dart,scope,reason\n"
            "not indented row,target.dart,s,r\n"
        )
        self.assertEqual(alias_graph.parse_aliases(bad_text), [])

    def test_to_graph_nodes_edges(self):
        import alias_graph
        rows = alias_graph.parse_aliases(FIXTURE_TEXT)
        g = alias_graph.to_graph(rows)
        nodes = g["nodes"]
        edges = g["edges"]
        self.assertEqual(len(nodes), 4)
        self.assertEqual(len(edges), 2)

        node_ids = {n["id"] for n in nodes}
        expected_ids = {
            "old:ordr_table.dart",
            "new:oped_table.dart",
            "old:ocrd_table.dart",
            "new:opar_table.dart",
        }
        self.assertEqual(node_ids, expected_ids)

        for n in nodes:
            if n["id"].startswith("old:"):
                self.assertEqual(n["type"], "alias_old")
            elif n["id"].startswith("new:"):
                self.assertEqual(n["type"], "alias_new")
            self.assertIn("scope", n)
            self.assertIn("reason", n)
            self.assertEqual(n["scope"], "mobile")
            self.assertEqual(n["reason"], "F30")

        self.assertEqual(edges[0]["type"], "RENAMED_TO")
        self.assertEqual(edges[0]["source"], "old:ordr_table.dart")
        self.assertEqual(edges[0]["target"], "new:oped_table.dart")
        self.assertEqual(edges[1]["type"], "RENAMED_TO")
        self.assertEqual(edges[1]["source"], "old:ocrd_table.dart")
        self.assertEqual(edges[1]["target"], "new:opar_table.dart")

        # Repeated row gives no new node and no new edge
        rows_with_repeat = rows + [{"old": "ordr_table.dart", "new": "oped_table.dart", "scope": "mobile", "reason": "F30"}]
        g2 = alias_graph.to_graph(rows_with_repeat)
        self.assertEqual(len(g2["nodes"]), 4)
        self.assertEqual(len(g2["edges"]), 2)

    def test_show_prints_neighbours(self):
        import alias_graph
        import aidd_graphs
        self._write_fixture()
        res = alias_graph.show_aliases(self.root, "ordr")
        self.assertEqual(res, "ordr_table.dart -> oped_table.dart [mobile] F30")

        res_none = alias_graph.show_aliases(self.root, "zzz")
        self.assertEqual(res_none, "No alias matching 'zzz'.")

        missing_root = self.tmp / "missing_proj"
        msg_missing = "Graph 'aliases' is missing; the project must generate .aidd/graphs/path-aliases.toon"
        self.assertEqual(alias_graph.show_aliases(missing_root, "ordr"), msg_missing)

        bad_root = self.tmp / "bad_proj"
        bad_file = bad_root / ".aidd" / "graphs" / "path-aliases.toon"
        bad_file.parent.mkdir(parents=True, exist_ok=True)
        bad_file.write_bytes(b"\xff\x00{")
        self.assertEqual(alias_graph.show_aliases(bad_root, "ordr"), msg_missing)

        # Also via aidd_graphs.show
        show_res = aidd_graphs.show(self.root, "aliases", "ordr")
        self.assertEqual(show_res, "ordr_table.dart -> oped_table.dart [mobile] F30")

    def test_registry_has_aliases_only_when_file_exists(self):
        import aidd_graphs
        # Without the file
        reg_without = aidd_graphs.load_registry(self.root)
        self.assertFalse(any(e["name"] == "aliases" for e in reg_without))

        # With the file
        self._write_fixture()
        reg_with = aidd_graphs.load_registry(self.root)
        alias_entries = [e for e in reg_with if e["name"] == "aliases"]
        self.assertEqual(len(alias_entries), 1)
        self.assertEqual(alias_entries[0]["kind"], "aliases")
        self.assertTrue(alias_entries[0]["output"].endswith("path-aliases.toon"))

        # With charter row named aliases AND the file: charter row wins, no duplicate
        charter = (
            "# Charter\n\n## Graphs\n\n"
            "| Name | Kind | Output | Refresh | Watch |\n"
            "|---|---|---|---|---|\n"
            "| aliases | aliases | .aidd/graphs/path-aliases.toon | python tools/gen.py | **/*.dart |\n"
        )
        (self.root / "charter.md").write_text(charter, encoding="utf-8")
        reg_charter = aidd_graphs.load_registry(self.root)
        charter_aliases = [e for e in reg_charter if e["name"] == "aliases"]
        self.assertEqual(len(charter_aliases), 1)
        self.assertEqual(charter_aliases[0]["refresh"], "python tools/gen.py")

    def test_explorer_accepts_toon(self):
        import graph_explorer
        toon = self._write_fixture()
        html_out = self.tmp / "explorer.html"
        rc = _quiet(graph_explorer.main, ["--graph", str(toon), "--kind", "aliases", "--layer", "aliases", "--out", str(html_out)])
        self.assertEqual(rc, 0)
        self.assertTrue(html_out.is_file())
        text = html_out.read_text(encoding="utf-8")
        self.assertIn("RENAMED_TO", text)
        self.assertIn("old name", text)
        self.assertIn("new name", text)
        self.assertIn("renamed in progress", text)
        self.assertIn('id="legend-aliases"', text)
        self.assertIn('id="insp-scope"', text)
        self.assertIn('id="insp-reason"', text)
        self.assertIn('id="aliases-empty-banner"', text)

    def test_explorer_html_is_self_contained(self):
        import graph_explorer
        toon = self._write_fixture()
        html_out = self.tmp / "explorer_self_contained.html"
        rc = _quiet(graph_explorer.main, ["--graph", str(toon), "--kind", "aliases", "--layer", "aliases", "--out", str(html_out)])
        self.assertEqual(rc, 0)
        text = html_out.read_text(encoding="utf-8")
        for forbidden in ("http://", "https://", "//cdn", "<script src", "<link href"):
            self.assertNotIn(forbidden, text)

    def test_unified_explorer_has_alias_layer(self):
        import graph_explorer
        from test_unified_graph import make_project
        alias_extra = ("aliases", "aliases", ".aidd/graphs/path-aliases.toon", FIXTURE_TEXT)
        proj_root = make_project(self.tmp / "unified_proj", extra_rows=(alias_extra,))
        html_out = self.tmp / "unified_explorer.html"
        rc = _quiet(graph_explorer.main, ["--root", str(proj_root), "--out", str(html_out)])
        self.assertEqual(rc, 0)
        text = html_out.read_text(encoding="utf-8")
        self.assertIn('id="metric-aliases"', text)
        self.assertIn('id="layer-cb-aliases"', text)

        m = re.search(r'<script id="graph-data" type="application/json">(.*?)</script>', text, flags=re.S)
        self.assertIsNotNone(m)
        payload = json.loads(m.group(1))
        layer_map = {l["name"]: l for l in payload.get("layers", [])}
        self.assertIn("aliases", layer_map)
        alias_layer = layer_map["aliases"]
        self.assertEqual(alias_layer.get("count"), 4)
        alias_nodes = [n for n in payload.get("nodes", []) if n.get("layer") == "aliases"]
        self.assertEqual(len(alias_nodes), 4)

    def test_progress_graph_task_state(self):
        import aidd_progress
        spec_dir = self.root / "specs" / "001-test"
        spec_dir.mkdir(parents=True, exist_ok=True)
        (self.root / "src").mkdir(parents=True, exist_ok=True)
        normal_file = self.root / "src" / "normal.py"
        normal_file.write_text("# aidd:FR-001\nprint('normal file long enough to exceed threshold')\n", encoding="utf-8")

        # Renumbered migration
        mig_dir = self.root / "migrations"
        mig_dir.mkdir(parents=True, exist_ok=True)
        (mig_dir / "0002_create_table.sql").write_text("-- migration sql file with enough content to be valid\n", encoding="utf-8")

        tasks_md = (
            "| Task | Codes satisfied | Target file | Status |\n"
            "|---|---|---|---|\n"
            "| T-01 | FR-001 | `src/normal.py` |  |\n"
            "| T-02 | FR-002 | `src/old.py (delete)` |  |\n"
            "| T-03 | FR-003 | `migrations/0001_create_table.sql` |  |\n"
        )
        (spec_dir / "tasks.md").write_text(tasks_md, encoding="utf-8")

        res = aidd_progress.measure(self.root, spec_dir)
        g = aidd_progress.graph(self.root, [res])
        task_nodes = {n["label"]: n for n in g["nodes"] if n.get("type") == "T"}
        self.assertIn("T-01", task_nodes)
        self.assertIn("T-02", task_nodes)
        self.assertIn("T-03", task_nodes)

        # Normal task has no 'state' key
        self.assertNotIn("state", task_nodes["T-01"])
        # Delete task satisfied has 'deleted'
        self.assertEqual(task_nodes["T-02"].get("state"), "deleted")
        # Renamed task has 'renamed'
        self.assertEqual(task_nodes["T-03"].get("state"), "renamed")


if __name__ == "__main__":
    unittest.main()
