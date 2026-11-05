"""Tests for the unified explorer (skill/scripts/graph_explorer.py) and `aidd graphs explorer` (aidd:FR-067..FR-069,
FR-076; AC-051, AC-057..AC-059, AC-064, AC-065). Synthetic project from tests/test_unified_graph.py; no network."""
import contextlib
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "skill" / "scripts"))
sys.path.insert(0, str(HERE))
from test_unified_graph import make_project, WIDGETS_ROW  # noqa: E402

F47_STATIC_IDS = (
    "active-focus-pill", "badge-starter-status", "btn-clear-focus", "btn-close-inspector", "btn-export-json",
    "btn-export-svg", "btn-reset-filters", "canvas-viewport", "focus-pill-name", "graph-data", "hop-radius-slider",
    "insp-body", "insp-domain", "insp-empty-state", "insp-id", "insp-purpose", "insp-title", "insp-trace-in",
    "insp-trace-out", "insp-type", "inspector-drawer", "lbl-hop-value", "minimap-canvas", "network-canvas",
    "omnibox-container", "omnibox-input", "search-dropdown", "select-entity", "select-module", "select-object",
    "select-spec", "select-table",
)


def payload_of(html):
    m = re.search(r'<script id="graph-data" type="application/json">(.*?)</script>', html, flags=re.S)
    assert m
    return json.loads(m.group(1))


def _quiet(fn, *a):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*a)


class UnifiedExplorerTests(unittest.TestCase):
    def setUp(self):
        import graph_explorer
        import aidd_graphs
        self.ge, self.ag = graph_explorer, aidd_graphs
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.R = make_project(self.tmp / "proj")

    def unified_html(self):
        out = self.tmp / "u.html"
        self.assertEqual(_quiet(self.ge.main, ["--root", str(self.R), "--out", str(out)]), 0)
        return out.read_text(encoding="utf-8")

    def test_root_mode_builds_all_layers(self):  # AC-050, AC-065
        self.assertEqual(_quiet(self.ge.main, ["--root", str(self.R)]), 0)
        out = self.R / "docs" / "graphs" / "explorer.html"
        self.assertTrue(out.is_file())
        names = [l["name"] for l in payload_of(out.read_text(encoding="utf-8"))["layers"]]
        self.assertEqual(names, [e["name"] for e in self.ag.load_registry(self.R)])

    def test_f47_layer_markup_unchanged(self):  # AC-059
        html = self.unified_html()
        self.assertIn('<div class="metric-pill"><span class="dot dot-db"></span>BD <strong id="metric-db">0</strong></div>',
                      html)
        self.assertIn('<label class="layer-cb-item"><input type="checkbox" id="layer-cb-db" checked value="db"> '
                      'Base de Datos</label>', html)
        for i in ("metric-code", "metric-spec", "metric-ui", "layer-cb-code", "layer-cb-spec", "layer-cb-ui"):
            self.assertIn('id="%s"' % i, html)

    def test_new_registered_graph_gets_pill_and_checkbox(self):  # AC-051
        make_project(self.R, [WIDGETS_ROW])
        html = self.unified_html()
        self.assertIn('id="metric-widgets"', html)
        self.assertIn('id="layer-cb-widgets"', html)
        self.assertIn("--layer-widgets:", html)

    def test_layer_checkboxes_are_wired(self):  # AC-059
        html = self.unified_html()
        self.assertIn("activeLayers.add(", html)
        self.assertIn("activeLayers.delete(", html)

    def test_f47_static_ids_present(self):  # AC-059
        html = self.unified_html()
        for i in F47_STATIC_IDS + ("insp-tech-details",):
            self.assertIn('id="%s"' % i, html, i)

    def test_self_contained_html(self):  # AC-058, FR-069
        shell = re.sub(r'<script id="graph-data".*?</script>', "", self.unified_html(), flags=re.S)
        for bad in ("http://", "https://", "//cdn", "<script src", "<link", "@import", "url("):
            self.assertNotIn(bad, shell)

    def test_no_data_innerhtml(self):  # AC-058
        self.assertNotIn("innerHTML = `", self.unified_html())

    def test_graph_mode_reads_toon(self):  # FR-067
        out = self.tmp / "ui.html"
        rc = _quiet(self.ge.main, ["--graph", str(self.R / ".aidd/graphs/ui.toon"), "--kind", "ui", "--layer", "ui",
                                   "--out", str(out)])
        self.assertEqual(rc, 0)
        p = payload_of(out.read_text(encoding="utf-8"))
        self.assertEqual(len(p["nodes"]), 1)
        self.assertEqual(p["nodes"][0]["layer"], "ui")

    def test_aidd_graphs_explorer_without_name(self):  # AC-057
        self.assertEqual(_quiet(self.ag.main, ["--root", str(self.R), "explorer"]), 0)
        self.assertTrue((self.R / "docs" / "graphs" / "explorer.html").is_file())
        x = self.tmp / "x.html"
        self.assertEqual(_quiet(self.ag.main, ["--root", str(self.R), "explorer", "--out", str(x)]), 0)
        self.assertTrue(x.is_file())

    def test_aidd_graphs_explorer_with_name(self):  # AC-057
        self.assertEqual(_quiet(self.ag.main, ["--root", str(self.R), "explorer", "db"]), 0)
        out = self.R / ".aidd" / "graphs" / "db.html"
        self.assertTrue(out.is_file())
        self.assertEqual([l["name"] for l in payload_of(out.read_text(encoding="utf-8"))["layers"]], ["db"])
        self.assertEqual(_quiet(self.ag.main, ["--root", str(self.R), "explorer", "nope"]), 1)

    def test_size_guard_and_skip(self):  # AC-064
        out = self.tmp / "o.html"
        self.assertEqual(_quiet(self.ge.main, ["--root", str(self.R), "--out", str(out), "--max-mb", "0.001"]), 3)
        self.assertFalse(out.exists())
        self.assertEqual(_quiet(self.ge.main, ["--root", str(self.R), "--out", str(out), "--skip", "db"]), 0)
        names = [l["name"] for l in payload_of(out.read_text(encoding="utf-8"))["layers"]]
        self.assertNotIn("db", names)


if __name__ == "__main__":
    unittest.main()
