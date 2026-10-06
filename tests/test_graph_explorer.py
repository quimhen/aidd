"""Tests for skill/scripts/graph_explorer.py (generic graph explorer generator)."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skill" / "scripts"))
import graph_explorer as g  # noqa: E402

HOSTILE = 'Note </script><script>alert(1)</script> & "q"     n http://x.invalid'

NODES = [
    {"id": "a", "label": "Alpha", "type": "table", "domain": "core", "purpose": HOSTILE, "weird_field": "zz9"},
    {"id": "b", "label": "Beta", "type": "column", "domain": "core", "nullable": False, "extra_n": 7},
    {"id": "c", "label": "Gamma", "type": "function", "domain": "sync"},
]
EDGES = [
    {"source": "b", "target": "a", "relation": "belongs_to"},
    {"source": "c", "target": "b", "relation": "writes", "op": "UPDATE"},
]
G_EDGES = {"nodes": NODES, "edges": EDGES}
G_LINKS = {"nodes": NODES, "links": EDGES}


def data_of(html):
    m = re.search(r'<script id="graph-data" type="application/json">(.*?)</script>', html, flags=re.S)
    assert m
    return m.group(1)


def test_edges_and_links_equivalent():
    h1, h2 = g.build_html(G_EDGES, "T"), g.build_html(G_LINKS, "T")
    assert h1 == h2
    d = json.loads(data_of(h1))
    assert len(d["edges"]) == 2 and d["group"] == "domain"
    assert {n["id"] for n in d["nodes"]} == {"a", "b", "c"}


def test_deterministic():
    rev = {"nodes": list(reversed(NODES)), "edges": list(reversed(EDGES))}
    assert g.build_html(G_EDGES, "T") == g.build_html(rev, "T")
    assert g.build_html(G_EDGES, "T") == g.build_html(json.loads(json.dumps(G_EDGES)), "T")


def test_embedded_json_escaped():
    html = g.build_html(G_EDGES, "T")
    raw = data_of(html)
    assert "<" not in raw and ">" not in raw and "&" not in raw
    assert " " not in html and " " not in html
    assert html.count("</script>") == 2
    raw.encode("ascii")
    by = {n["id"]: n for n in json.loads(raw)["nodes"]}
    assert by["a"]["purpose"] == HOSTILE


def test_title_escaped():
    html = g.build_html(G_EDGES, '<b>"x"</b> & __DATA__')
    assert "<b>" not in html
    assert "&lt;b&gt;&quot;x&quot;&lt;/b&gt; &amp; __DATA__" in html
    assert json.loads(data_of(html))["nodes"]


def test_extra_fields_rendered():
    html = g.build_html(G_EDGES, "T")
    d = json.loads(data_of(html))
    by = {n["id"]: n for n in d["nodes"]}
    assert by["a"]["weird_field"] == "zz9" and by["b"]["extra_n"] == 7
    # card renders every key generically, with a priority list first
    assert "Object.keys(n).sort().forEach(row)" in html
    for k in ("purpose_source", "source_location", "data_type", "community"):
        assert '"' + k + '"' in html
    assert "Incoming" in html and "Outgoing" in html and 'id="q"' in html and 'id="ft"' in html


def test_no_external_resources():
    shell = re.sub(r'<script id="graph-data".*?</script>', "", g.build_html(G_EDGES, "T"), flags=re.S)
    assert "http://" not in shell and "https://" not in shell
    assert not re.search(r'(src|href)\s*=\s*["\'](?!#)', shell)
    assert "@import" not in shell and "url(" not in shell


def test_group_autodetect():
    nodes = [{"id": "x", "community": 3}, {"id": "y", "community": 4}]
    assert json.loads(data_of(g.build_html({"nodes": nodes}, "T")))["group"] == "community"
    assert json.loads(data_of(g.build_html({"nodes": [{"id": "x"}]}, "T")))["group"] == ""


def test_cli_exit_codes(tmp_path):
    gp = tmp_path / "graph.json"
    gp.write_text(json.dumps(G_LINKS), encoding="utf-8")
    assert g.main(["--graph", str(gp), "--title", "Mine"]) == 0
    default_out = tmp_path / "graph.html"
    assert default_out.read_text(encoding="utf-8").startswith("<!doctype html>")
    o2 = tmp_path / "b.html"
    assert g.main(["--graph", str(gp), "--out", str(o2), "--title", "Mine"]) == 0
    assert o2.read_bytes() == default_out.read_bytes()
    assert g.main(["--graph", str(tmp_path / "missing.json")]) == 2
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert g.main(["--graph", str(bad)]) == 2
    nonode = tmp_path / "nn.json"
    nonode.write_text("[1,2]", encoding="utf-8")
    assert g.main(["--graph", str(nonode)]) == 2


def test_size_sanity():
    nodes = [{"id": f"n{i:05d}", "label": f"Node {i}", "type": "t%d" % (i % 5), "domain": "d%d" % (i % 7)}
             for i in range(5000)]
    edges = [{"source": f"n{i % 5000:05d}", "target": f"n{(i * 7 + 1) % 5000:05d}", "relation": "r%d" % (i % 3)}
             for i in range(10000)]
    html = g.build_html({"nodes": nodes, "links": edges}, "Big")
    assert len(html) < 3_000_000
    assert "MAXR=200" in html
    assert html == g.build_html({"nodes": nodes, "links": edges}, "Big")
