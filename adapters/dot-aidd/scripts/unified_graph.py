#!/usr/bin/env python3
"""Registry-driven unified graph model (aidd:FR-060).

Every graph of the project registry (`aidd_graphs.load_registry`, the charter `## Graphs` table or the
auto-detected defaults) becomes one layer of a single node-link payload; a graph added to the registry
appears here with no code change. Stdlib only. Reads never write; `load_unified` never raises.

Provenance: port of the LOGIC (never the paths or domain rules) of the F47 model, snapshot
`batch-staging/f47-port-sources/model/unified_graph_model.py`
sha256 e834afc297d64fddfad3a44927cd005642bd5f7850f9ec8b81418816fdb10a9c.

Usage:  python unified_graph.py [--root DIR] [--json]
"""
import argparse
import importlib
import json
import re
import sys
from collections import deque
from pathlib import Path

HERE = Path(__file__).resolve().parent

KIND_COLOURS = {"db": "#00bcd4", "code": "#10b981", "spec": "#a855f7", "ui": "#f59e0b"}
EXTRA_COLOURS = ["#ef4444", "#3b82f6", "#ec4899", "#84cc16", "#14b8a6", "#f97316", "#8b5cf6", "#eab308"]
KIND_PILL_LABELS = {"db": "BD", "code": "AST", "spec": "Spec", "ui": "UI"}
KIND_CHECKBOX_LABELS = {"db": "Base de Datos", "code": "Código AST", "spec": "Specs AIDD", "ui": "Componentes UI"}
DOMAIN_FIELDS = ("domain", "origin", "community", "group")
DEFAULT_DOMAIN = "Core"
REF_FIELDS = ("consumers", "consumes", "refs")
CODE_FIELDS = ("codes",)
TOON_SECTION_RE = re.compile(r"^([A-Za-z_][\w-]*)\[(\d+)\]\{([^}]*)\}:\s*$")

_NODE_CORE = {"id", "label", "name", "title", "type", "kind", "node", "purpose", "description", "comment"}


def _sibling(name):
    """Import a module that lives next to this file; None when it cannot be imported."""
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


def _endpoint(v):
    if isinstance(v, dict):
        v = v.get("id")
    return None if v is None else str(v)


def layer_id(name):
    """DOM-safe layer id: lower case, every char outside a-z, 0-9, '-' becomes '-'."""
    return re.sub(r"[^a-z0-9-]", "-", str(name).lower())


def layer_styles(entries):
    """One style per registry entry, in registry order (aidd:FR-064)."""
    out, k = [], 0
    for e in entries:
        name, kind = str(e.get("name", "")), str(e.get("kind", ""))
        if kind == name and kind in KIND_COLOURS:
            color, label, title = KIND_COLOURS[kind], KIND_PILL_LABELS[kind], KIND_CHECKBOX_LABELS[kind]
        else:
            color, label, title = EXTRA_COLOURS[k % len(EXTRA_COLOURS)], name, name
            k += 1
        out.append({"name": name, "id": layer_id(name), "kind": kind, "color": color, "label": label,
                    "title": title})
    return out


def read_graph_file(path, kind):
    """Read one graph file into {"nodes": [...], "edges": [...]}; ValueError on bad suffix or content."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".json":
        return _read_json(text)
    if suffix == ".toon":
        return TOON_READERS.get(kind, _read_generic_toon)(text)
    raise ValueError("unsupported graph file suffix: %s" % (path.suffix or "(none)"))


def _read_json(text):
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("graph JSON must be an object")
    nodes = data.get("nodes") or []
    edges = data.get("edges")
    if edges is None:
        edges = data.get("links") or []
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("graph JSON nodes/edges must be lists")
    return {"nodes": nodes, "edges": edges}


def _read_spec_toon(text):
    fs = _sibling("find_spec")
    if fs is None:
        raise ValueError("find_spec is not installed next to unified_graph")
    nodes = []
    for spec_id, s in sorted(fs.loads_index(text)["specs"].items()):
        nodes.append({"id": spec_id, "label": spec_id, "type": "spec", "purpose": s.get("title", ""),
                      "codes": list(s.get("codes", []))})
    return {"nodes": nodes, "edges": []}


def _read_ui_toon(text):
    cg = _sibling("component_graph")
    if cg is None:
        raise ValueError("component_graph is not installed next to unified_graph")
    nodes = []
    for cid, c in sorted(cg.parse_toon(text).items()):
        nodes.append({"id": cid, "label": c.get("name") or cid, "type": "component", "path": c.get("path", ""),
                      "pattern": c.get("pattern", ""), "consumers": list(c.get("consumers", [])),
                      "consumes": list(c.get("consumes", []))})
    return {"nodes": nodes, "edges": []}


def _read_generic_toon(text):
    nodes, cols, section = [], None, None
    for line in text.splitlines():
        m = TOON_SECTION_RE.match(line.strip()) if not line.startswith("  ") else None
        if m:
            section, cols = m.group(1), [c.strip() for c in m.group(3).split(",")]
            continue
        if cols is None or not line.startswith("  "):
            if line.strip():
                cols = None
            continue
        cells = line.strip().split(",", max(len(cols) - 1, 0))
        if not cells or not cells[0].strip():
            continue
        row = dict(zip(cols, (c.strip() for c in cells)))
        nid = cells[0].strip()
        label_col = next((c for c in cols if c in ("name", "title", "label")), None)
        node = {k: v for k, v in row.items() if k not in ("id", "label", "type")}
        node.update({"id": nid, "label": (row.get(label_col) if label_col else "") or nid, "type": section})
        nodes.append(node)
    return {"nodes": nodes, "edges": []}


def _read_aliases_toon(text):
    ag = _sibling("alias_graph")
    if ag is None:
        raise ValueError("alias_graph is not installed next to unified_graph")
    return ag.to_graph(ag.parse_aliases(text))


TOON_READERS = {"spec": _read_spec_toon, "ui": _read_ui_toon, "aliases": _read_aliases_toon}


def _str_list(v):
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v if x is not None and str(x) != ""]
    if isinstance(v, str):
        return [x for x in v.split("|") if x]
    if v is None:
        return []
    return [str(v)]


def _domain_of(n):
    for f in DOMAIN_FIELDS:
        v = n.get(f)
        if v is None or isinstance(v, (dict, list)):
            continue
        s = str(v).strip()
        if s:
            return s
    return DEFAULT_DOMAIN


def normalise(layer, kind, raw, prefix=True):
    """Normalised (nodes, edges) of one layer; ids become `<layer>:<raw id>` when `prefix` is true."""
    nodes, edges = [], []
    try:
        pid = (lambda r: "%s:%s" % (layer, r)) if prefix else (lambda r: r)
        seen = set()
        for n in (raw or {}).get("nodes") or []:
            if not isinstance(n, dict) or n.get("id") is None or str(n.get("id")) == "":
                continue
            rid = str(n["id"])
            if rid in seen:
                continue
            seen.add(rid)
            label = n.get("label") or n.get("name") or n.get("title") or rid
            ntype = n.get("type") or n.get("kind") or n.get("node") or ""
            purpose = n.get("purpose") or n.get("description") or n.get("comment") or ""
            codes, refs = [], []
            for f in CODE_FIELDS:
                codes += _str_list(n.get(f))
            for f in REF_FIELDS:
                refs += _str_list(n.get(f))
            skip = _NODE_CORE | set(CODE_FIELDS) | set(REF_FIELDS)
            metadata = {k: v for k, v in n.items()
                        if k not in skip and isinstance(v, (str, int, float, bool)) and v is not None}
            nodes.append({"id": pid(rid), "raw_id": rid, "label": str(label), "layer": layer, "kind": kind,
                          "type": str(ntype), "domain": _domain_of(n), "purpose": str(purpose),
                          "metadata": metadata, "codes": codes, "refs": refs})
        raw_edges = (raw or {}).get("edges")
        if raw_edges is None:
            raw_edges = (raw or {}).get("links")
        for e in raw_edges or []:
            if not isinstance(e, dict):
                continue
            s, t = _endpoint(e.get("source")), _endpoint(e.get("target"))
            if s is None or t is None or s not in seen or t not in seen:
                continue
            rel = e.get("relation") or e.get("type") or e.get("kind") or e.get("rel") or ""
            edges.append({"source": pid(s), "target": pid(t), "relation": str(rel), "layer": layer,
                          "cross_layer": False})
    except Exception:
        return nodes, edges
    return nodes, edges


# --- part 2: linking, loading, neighbourhood, CLI (aidd:FR-063, FR-065, FR-066) ------------------------------

MENTION_DOCS = ("spec.md", "plan.md", "tasks.md", "data-model.md")
MENTION_DB_TYPES = ("table", "view", "function")
WORD_RE = re.compile(r"\b[A-Za-z0-9_]{3,64}\b")
CODE_PATH_RE = re.compile(r"[\w/.-]+\.(?:py|ts|tsx|js|jsx|dart|sql|cs)\b")


def _clean_path(p):
    p = p.strip("`'\"").replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def link_cross_layers(root, nodes, edges):
    """Add generic `references` and `mentions` edges between layers; returns the number added."""
    root = Path(root)
    index = {}
    for n in nodes:
        for key in [n["raw_id"]] + list(n.get("codes") or []):
            index.setdefault(key, set()).add(n["id"])
    by_id = {n["id"]: n for n in nodes}
    have = {(e["source"], e["target"], e["relation"]) for e in edges}
    added = []

    def add(s, t, rel):
        k = (s, t, rel)
        if s != t and k not in have:
            have.add(k)
            added.append({"source": s, "target": t, "relation": rel, "layer": "cross", "cross_layer": True})

    for n in nodes:
        for ref in n.get("refs") or []:
            for target in sorted(index.get(ref, ())):
                if by_id[target]["layer"] != n["layer"]:
                    add(n["id"], target, "references")
    db_nodes = [n for n in nodes if n["kind"] == "db" and n["type"].lower() in MENTION_DB_TYPES]
    code_nodes = [n for n in nodes if n["kind"] == "code"]
    for n in nodes:
        if n["kind"] != "spec":
            continue
        text = []
        for doc in MENTION_DOCS:
            try:
                text.append((root / "specs" / n["raw_id"] / doc).read_text(encoding="utf-8", errors="replace"))
            except (OSError, ValueError):
                continue
        if not text:
            continue
        corpus = "\n".join(text)
        words = {w.lower() for w in WORD_RE.findall(corpus)}
        paths = {_clean_path(p) for p in CODE_PATH_RE.findall(corpus)}
        for d in db_nodes:
            if d["label"].lower() in words:
                add(n["id"], d["id"], "mentions")
        for c in code_nodes:
            src = _clean_path(str((c.get("metadata") or {}).get("source_file", "")))
            if _clean_path(c["raw_id"]) in paths or (src and src in paths):
                add(n["id"], c["id"], "mentions")
    edges.extend(added)
    return len(added)


def _empty(warnings):
    return {"summary": {"total_nodes": 0, "total_edges": 0, "by_layer": {}}, "layers": [], "domains": [],
            "nodes": [], "edges": [], "warnings": list(warnings)}


def _finish(layers, nodes, edges, warnings):
    nodes.sort(key=lambda n: n["id"])
    edges.sort(key=lambda e: (e["source"], e["target"], e["relation"]))
    by_layer = {l["name"]: 0 for l in layers}
    for n in nodes:
        by_layer[n["layer"]] = by_layer.get(n["layer"], 0) + 1
    for l in layers:
        l["count"] = by_layer.get(l["name"], 0)
    return {"summary": {"total_nodes": len(nodes), "total_edges": len(edges), "by_layer": by_layer},
            "layers": layers, "domains": sorted({n["domain"] for n in nodes if n.get("domain")}),
            "nodes": nodes, "edges": edges, "warnings": warnings}


def load_unified(root, names=None, skip=()):
    """Payload of every registered graph with an output, one layer each (never raises)."""
    try:
        root = Path(root)
        ag = _sibling("aidd_graphs")
        if ag is None:
            return _empty(["registry: aidd_graphs is not installed next to unified_graph"])
        wanted = None if names is None else {str(x) for x in names}
        skipped = {str(x) for x in (skip or ())}
        entries = [e for e in ag.load_registry(root) if e.get("output")
                   and (wanted is None or e["name"] in wanted) and e["name"] not in skipped]
    except Exception as ex:
        return _empty(["registry: unreadable (%s)" % type(ex).__name__])
    layers, nodes, edges, warnings = [], [], [], []
    for e, style in zip(entries, layer_styles(entries)):
        layer = dict(style, count=0, missing=False, error=False, output=e["output"])
        layers.append(layer)
        path = Path(e["output"])
        if not path.is_file():
            layer["missing"] = True
            warnings.append("%s: output missing (%s)" % (e["name"], e["output"]))
            continue
        try:
            raw = read_graph_file(path, e.get("kind", ""))
            ln, le = normalise(e["name"], e.get("kind", ""), raw, prefix=True)
        except Exception as ex:
            layer["error"] = True
            warnings.append("%s: unreadable (%s)" % (e["name"], type(ex).__name__))
            continue
        nodes.extend(ln)
        edges.extend(le)
    try:
        link_cross_layers(root, nodes, edges)
    except Exception as ex:
        warnings.append("cross-layer links: skipped (%s)" % type(ex).__name__)
    return _finish(layers, nodes, edges, warnings)


def single_layer(raw, layer="graph", kind="graph"):
    """Payload of one graph: one layer, raw ids, no cross links."""
    style = layer_styles([{"name": layer, "kind": kind}])[0]
    nodes, edges = normalise(layer, kind, raw, prefix=False)
    return _finish([dict(style, count=0, missing=False, error=False, output="")], nodes, edges, [])


def compute_neighborhood(graph, focal_node_id, hop_radius=2):
    """Subgraph within `hop_radius` hops of the focal node (undirected); F47 shape and suffix fallback."""
    nodes_by_id = {n["id"]: n for n in graph.get("nodes", [])}
    if focal_node_id not in nodes_by_id:
        focal = str(focal_node_id or "")
        matches = [nid for nid in nodes_by_id if focal and (nid.endswith(focal) or focal in nid)]
        if not matches:
            return {"nodes": [], "edges": [], "focal_node": None}
        focal_node_id = matches[0]
    adj = {nid: set() for nid in nodes_by_id}
    for e in graph.get("edges", []):
        s, t = e["source"], e["target"]
        if s in adj and t in adj:
            adj[s].add(t)
            adj[t].add(s)
    visited = {focal_node_id}
    queue = deque([(focal_node_id, 0)])
    while queue:
        curr, depth = queue.popleft()
        if depth >= hop_radius:
            continue
        for nb in sorted(adj.get(curr, ())):
            if nb not in visited:
                visited.add(nb)
                queue.append((nb, depth + 1))
    return {"focal_node": nodes_by_id[focal_node_id], "hop_radius": hop_radius,
            "nodes": [nodes_by_id[nid] for nid in sorted(visited)],
            "edges": [e for e in graph.get("edges", []) if e["source"] in visited and e["target"] in visited]}


def filter_graph(graph, active_layers=None, active_domains=None):
    """Nodes in the active layers and domains, and the edges between them (F47 shape)."""
    kept = [n for n in graph.get("nodes", [])
            if not (active_layers and n.get("layer") not in active_layers)
            and not (active_domains and n.get("domain") not in active_domains)]
    ids = {n["id"] for n in kept}
    kept_edges = [e for e in graph.get("edges", []) if e["source"] in ids and e["target"] in ids]
    return {"summary": {"total_nodes": len(kept), "total_edges": len(kept_edges)}, "nodes": kept,
            "edges": kept_edges}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Unified graph of every registered graph (aidd:FR-060).")
    ap.add_argument("--root", default=".", help="project root (default: the current directory)")
    ap.add_argument("--json", action="store_true", help="print the whole payload as JSON")
    a = ap.parse_args(argv)
    g = load_unified(Path(a.root))
    for w in g["warnings"]:
        print(w, file=sys.stderr)
    if a.json:
        print(json.dumps(g, indent=2, sort_keys=True))
    else:
        print("unified: %d nodes, %d edges, layers: %s" % (
            g["summary"]["total_nodes"], g["summary"]["total_edges"],
            ", ".join("%s=%d" % (l["name"], l["count"]) for l in g["layers"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
