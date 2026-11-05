"""Tests for skill/scripts/unified_graph.py, the registry-driven unified graph model (aidd:FR-060..FR-066).

AC-050..AC-056 on a synthetic project: the charter declares db, spec, ui and code; nothing is
auto-detected. stdlib unittest only.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "skill" / "scripts"))

CHARTER_HEAD = ("# Charter\n\n## Graphs\n\n"
                "| Name | Kind | Output | Refresh | Watch |\n"
                "|---|---|---|---|---|\n")
BASE_ROWS = (
    ("db", "db", ".aidd/graphs/db.json", "", ""),
    ("spec", "spec", "specs/index.toon", "", ""),
    ("ui", "ui", ".aidd/graphs/ui.toon", "", ""),
    ("code", "code", ".aidd/graphs/code.json", "builtin:code", "**/*.py"),
)
DB_GRAPH = {
    "nodes": [
        {"id": "table:ORDR", "label": "ORDR", "type": "table", "domain": "sales"},
        {"id": "column:ORDR.status", "label": "status", "type": "column", "domain": "sales"},
        {"id": "table:OCRD", "label": "OCRD", "type": "table"},
    ],
    "edges": [{"source": "column:ORDR.status", "target": "table:ORDR", "relation": "belongs_to"}],
}
CODE_GRAPH = {"nodes": [{"id": "app/orders.py", "type": "FILE", "source_file": "app/orders.py"}], "edges": []}
SPEC_TOON = ("version: 4\n"
             "generated: 2026-11-03T00:00:00+00:00\n"
             "specs[1]{id,title,codes,words,tree,graph,files}:\n"
             "  001-orders,001 — Orders,US-001|FR-001,orders,,,spec.md=1\n")
SPEC_MD = "Orders spec. Reads table ORDR, sets status and changes app/orders.py.\n"
UI_TOON = ("version: 1\n"
           "generated: 2026-11-03T00:00:00+00:00\n"
           "components[1]{id,name,path,pattern,props,slots,consumes,consumers}:\n"
           "  COMP-001,OrderCard,src/OrderCard.tsx,Atomic,,,,US-001\n")
WIDGETS_ROW = ("widgets", "widgets", ".aidd/graphs/widgets.json",
               json.dumps({"nodes": [{"id": "w1", "label": "Widget one"}], "edges": []}))
NOTES_ROW = ("notes", "notes", ".aidd/graphs/notes.toon",
             "version: 1\nnotes[2]{id,title,owner}:\n  N-1,First note,ann\n  N-2,Second note,bob\n")


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_project(root, extra_rows=()):
    """Write the synthetic project into `root`; each extra row is (name, kind, output, text)."""
    root = Path(root)
    rows = [r for r in BASE_ROWS] + [(n, k, o, "", "") for n, k, o, _t in extra_rows]
    _write(root / "charter.md", CHARTER_HEAD + "".join("| %s | %s | %s | %s | %s |\n" % r for r in rows))
    _write(root / ".aidd/graphs/db.json", json.dumps(DB_GRAPH))
    _write(root / ".aidd/graphs/code.json", json.dumps(CODE_GRAPH))
    _write(root / "specs/index.toon", SPEC_TOON)
    _write(root / "specs/001-orders/spec.md", SPEC_MD)
    _write(root / ".aidd/graphs/ui.toon", UI_TOON)
    for _n, _k, output, text in extra_rows:
        _write(root / output, text)
    return root


class UnifiedGraphTests(unittest.TestCase):
    def setUp(self):
        import unified_graph
        import aidd_graphs
        self.u, self.ag = unified_graph, aidd_graphs
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def project(self, extra_rows=()):
        return make_project(self.tmp, extra_rows)

    def test_layers_follow_registry(self):  # AC-050
        root = self.project()
        g = self.u.load_unified(root)
        names = [l["name"] for l in g["layers"]]
        self.assertEqual(names, [e["name"] for e in self.ag.load_registry(root)])
        self.assertEqual(names, ["db", "spec", "ui", "code"])
        self.assertEqual(g["summary"]["by_layer"], {"db": 3, "spec": 1, "ui": 1, "code": 1})

    def test_new_registered_kind_is_a_layer(self):  # AC-051
        g = self.u.load_unified(self.project([WIDGETS_ROW]))
        layer = {l["name"]: l for l in g["layers"]}["widgets"]
        self.assertEqual(layer["count"], 1)
        self.assertEqual(layer["color"], self.u.EXTRA_COLOURS[0])
        self.assertEqual([n["id"] for n in g["nodes"] if n["layer"] == "widgets"], ["widgets:w1"])

    def test_unknown_toon_kind_is_a_layer(self):  # AC-052
        g = self.u.load_unified(self.project([NOTES_ROW]))
        notes = [n for n in g["nodes"] if n["layer"] == "notes"]
        self.assertEqual(len(notes), 2)
        self.assertEqual(sorted(n["label"] for n in notes), ["First note", "Second note"])

    def test_layer_colours(self):  # AC-051, FR-064
        g = self.u.load_unified(self.project([WIDGETS_ROW, NOTES_ROW]))
        colour = {l["name"]: l["color"] for l in g["layers"]}
        for k in ("db", "code", "spec", "ui"):
            self.assertEqual(colour[k], self.u.KIND_COLOURS[k])
        self.assertEqual(colour["widgets"], self.u.EXTRA_COLOURS[0])
        self.assertEqual(colour["notes"], self.u.EXTRA_COLOURS[1])

    def test_cross_layer_links(self):  # AC-053
        g = self.u.load_unified(self.project())
        cross = [e for e in g["edges"] if e["cross_layer"]]
        triples = {(e["source"], e["target"], e["relation"]) for e in cross}
        self.assertIn(("ui:COMP-001", "spec:001-orders", "references"), triples)
        self.assertIn(("spec:001-orders", "db:table:ORDR", "mentions"), triples)
        self.assertIn(("spec:001-orders", "code:app/orders.py", "mentions"), triples)
        targets = {e["target"] for e in cross}
        self.assertNotIn("db:column:ORDR.status", targets)
        self.assertNotIn("db:table:OCRD", targets)
        self.assertTrue(all(e["layer"] == "cross" for e in cross))
        self.assertEqual(len(triples), len(cross))

    def test_neighbourhood_radius(self):  # AC-054
        g = self.u.load_unified(self.project())
        r1 = self.u.compute_neighborhood(g, "db:table:ORDR", hop_radius=1)
        r2 = self.u.compute_neighborhood(g, "db:table:ORDR", hop_radius=2)
        self.assertEqual(r1["focal_node"]["id"], "db:table:ORDR")
        self.assertEqual(len(r1["nodes"]), 3)
        self.assertEqual(len(r2["nodes"]), 5)
        self.assertTrue({n["id"] for n in r1["nodes"]} <= {n["id"] for n in r2["nodes"]})
        none = self.u.compute_neighborhood(g, "zzz")
        self.assertEqual(none["nodes"], [])
        self.assertIsNone(none["focal_node"])

    def test_layer_and_domain_filtering(self):  # AC-055
        g = self.u.load_unified(self.project())
        db = self.u.filter_graph(g, active_layers={"db"})
        self.assertEqual(len(db["nodes"]), 3)
        self.assertTrue(all(n["layer"] == "db" for n in db["nodes"]))
        sales = self.u.filter_graph(g, active_domains={"sales"})
        self.assertEqual(len(sales["nodes"]), 2)
        for sub in (db, sales):
            kept = {n["id"] for n in sub["nodes"]}
            self.assertTrue(all(e["source"] in kept and e["target"] in kept for e in sub["edges"]))

    def test_fail_open(self):  # AC-056
        root = self.project()
        (root / ".aidd/graphs/code.json").unlink()
        (root / ".aidd/graphs/db.json").write_text("{not json", encoding="utf-8")
        g = self.u.load_unified(root)
        layers = {l["name"]: l for l in g["layers"]}
        self.assertTrue(layers["code"]["missing"])
        self.assertTrue(layers["db"]["error"])
        self.assertTrue(any(w.startswith("code: output missing (") for w in g["warnings"]))
        self.assertTrue(any(w.startswith("db: unreadable (") for w in g["warnings"]))
        self.assertEqual(g["summary"]["by_layer"]["spec"], 1)
        self.assertEqual(g["summary"]["by_layer"]["ui"], 1)

    def test_deterministic(self):  # FR-062
        root = self.project([WIDGETS_ROW, NOTES_ROW])
        a = json.dumps(self.u.load_unified(root), sort_keys=True)
        b = json.dumps(self.u.load_unified(root), sort_keys=True)
        self.assertEqual(a, b)

    def test_no_project_specific_paths(self):  # FR-060, FR-062
        text = (REPO / "skill" / "scripts" / "unified_graph.py").read_text(encoding="utf-8")
        for bad in ("docs/db-graph", "graphify-out", "Payroll", "mobile", "b1Sy", "eDoc", "Nomina"):
            self.assertNotIn(bad, text)


if __name__ == "__main__":
    unittest.main()
