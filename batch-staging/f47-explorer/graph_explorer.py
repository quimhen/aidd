#!/usr/bin/env python3
"""Executive Precision Unified Graph Explorer generator for AIDD.
Single-file, self-contained interactive Canvas 2D visualization (0 CDN dependencies, stdlib only).

Usage:  python graph_explorer.py --graph <graph.json> [--out <file.html>] [--title TEXT]
        python graph_explorer.py [--root DIR] [--out <file.html>] [--title TEXT]
"""
import argparse
import html as _html
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_TITLE = "AIDD :: Unified Knowledge Graph Explorer"


def embed_json(obj):
    """JSON safe inside <script>: no '</', no HTML comments, ASCII only."""
    s = json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026") \
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def build_unified_payload(graph, root_dir=None):
    """Normalizes any generic or multi-layer graph into the unified explorer schema."""
    nodes = []
    edges = []

    raw_nodes = graph.get("nodes", []) or []
    for n in raw_nodes:
        if not isinstance(n, dict) or n.get("id") is None:
            continue
        nid = str(n["id"])
        domain = n.get("domain") or n.get("origin") or n.get("group") or "Core"
        layer = n.get("layer")
        if not layer:
            if ":table:" in nid or n.get("type") in ("table", "view", "column"):
                layer = "db"
            elif ":spec:" in nid or n.get("type") == "spec" or nid.startswith("F") or nid.startswith("P"):
                layer = "spec"
            elif ":ui:" in nid or n.get("type") == "component" or "COMP-" in nid:
                layer = "ui"
            else:
                layer = "code"

        nodes.append({
            "id": nid,
            "raw_id": n.get("raw_id", nid),
            "label": n.get("label", nid),
            "layer": layer,
            "type": n.get("type", "node"),
            "domain": domain,
            "purpose": n.get("purpose") or n.get("description") or n.get("comment") or "",
            "metadata": {k: v for k, v in n.items() if k not in ("id", "label", "layer", "type", "domain", "purpose") and isinstance(v, (str, int, float, bool))}
        })

    raw_edges = graph.get("edges") if graph.get("edges") is not None else graph.get("links", [])
    for e in raw_edges or []:
        if not isinstance(e, dict):
            continue
        s = str(e.get("source", ""))
        t = str(e.get("target", ""))
        if not s or not t:
            continue
        edges.append({
            "source": s,
            "target": t,
            "relation": e.get("relation", "rel"),
            "cross_layer": bool(e.get("cross_layer", False)),
        })

    domains = sorted(list({n["domain"] for n in nodes if n.get("domain")}))
    return {
        "summary": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "by_layer": {
                "db": sum(1 for n in nodes if n["layer"] == "db"),
                "code": sum(1 for n in nodes if n["layer"] == "code"),
                "spec": sum(1 for n in nodes if n["layer"] == "spec"),
                "ui": sum(1 for n in nodes if n["layer"] == "ui"),
            }
        },
        "domains": domains,
        "nodes": nodes,
        "edges": edges,
    }


def build_html(graph_data, title=DEFAULT_TITLE):
    payload = build_unified_payload(graph_data)
    embedded_data = embed_json(payload)
    safe_title = _html.escape(title, quote=True)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{safe_title}</title>
<style>
:root {{
  --bg-dark: #091016;
  --bg-surface: #0e1720;
  --bg-card: #131e2a;
  --bg-card-hover: #192737;
  --bg-input: #152230;
  --border-subtle: #1c2b3c;
  --border-strong: #273e57;
  --text-main: #f1f5f9;
  --text-muted: #8e9fab;
  --text-faint: #56687a;
  --layer-db: #00bcd4;
  --layer-db-dark: #00677c;
  --layer-code: #10b981;
  --layer-spec: #a855f7;
  --layer-ui: #f59e0b;
  --layer-cross: #38bdf8;
  --impact-cascade: #ef4444;
  --font-sans: "Roboto Flex", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  background-color: var(--bg-dark);
  color: var(--text-main);
  font-family: var(--font-sans);
  font-size: 13px;
  line-height: 1.4;
  height: 100vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}}
.topbar {{
  height: 52px;
  background-color: var(--bg-surface);
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  gap: 16px;
  z-index: 20;
}}
.brand {{ display: flex; align-items: center; gap: 10px; }}
.brand-icon {{
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, var(--layer-db-dark), #003642);
  border: 1px solid var(--layer-db);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #70f3ff;
}}
.brand-title {{ font-weight: 700; font-size: 13px; color: #fff; }}
.brand-sub {{ font-size: 10px; color: var(--text-muted); font-family: var(--font-mono); }}
.search-container {{ flex: 1; max-width: 540px; position: relative; }}
.search-input-wrapper {{
  display: flex;
  align-items: center;
  background-color: var(--bg-input);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 0 10px;
  gap: 8px;
  height: 34px;
}}
.search-input-wrapper:focus-within {{
  border-color: var(--layer-db);
  box-shadow: 0 0 0 2px rgba(0, 188, 212, 0.2);
}}
#omnibox-input {{
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-main);
  font-size: 13px;
}}
.kbd-shortcut {{
  font-family: var(--font-mono);
  font-size: 10px;
  background-color: var(--bg-card);
  color: var(--text-muted);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  padding: 1px 5px;
}}
.search-results-dropdown {{
  position: absolute;
  top: 40px;
  left: 0;
  right: 0;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-strong);
  border-radius: 6px;
  max-height: 380px;
  overflow-y: auto;
  box-shadow: 0 12px 30px rgba(0,0,0,0.6);
  z-index: 50;
}}
.search-res-item {{
  padding: 8px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  cursor: pointer;
}}
.search-res-item:hover {{ background-color: var(--bg-card-hover); }}
.topbar-actions {{ display: flex; align-items: center; gap: 12px; }}
.metrics-pills {{ display: flex; gap: 6px; }}
.metric-pill {{
  display: flex;
  align-items: center;
  gap: 5px;
  background-color: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  padding: 2px 7px;
  font-size: 11px;
  font-family: var(--font-mono);
}}
.dot {{ width: 6px; height: 6px; border-radius: 50%; }}
.dot-db {{ background-color: var(--layer-db); }}
.dot-code {{ background-color: var(--layer-code); }}
.dot-spec {{ background-color: var(--layer-spec); }}
.dot-ui {{ background-color: var(--layer-ui); }}
.btn-icon {{
  display: flex;
  align-items: center;
  gap: 5px;
  background-color: var(--bg-card);
  color: var(--text-main);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 11px;
  cursor: pointer;
}}
.app-container {{ flex: 1; display: flex; position: relative; overflow: hidden; }}
.sidebar-panel {{
  width: 280px;
  min-width: 280px;
  background-color: var(--bg-surface);
  border-right: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  z-index: 10;
}}
.sidebar-header {{
  padding: 12px 14px;
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  justify-content: space-between;
}}
.sidebar-title {{ font-weight: 600; font-size: 12px; color: var(--text-muted); text-transform: uppercase; }}
.btn-text-xs {{ background: none; border: none; color: var(--layer-db); font-size: 11px; cursor: pointer; }}
.sidebar-scrollable {{ flex: 1; overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 16px; }}
.filter-section-starter {{
  background: linear-gradient(180deg, rgba(0, 103, 124, 0.18) 0%, rgba(14, 23, 32, 0.6) 100%);
  border: 1px solid var(--layer-db-dark);
  border-radius: 6px;
  padding: 10px;
}}
.starter-heading {{ color: #70f3ff; font-weight: 700; }}
.select-group {{ display: flex; flex-direction: column; gap: 4px; }}
.select-label {{ font-size: 10px; text-transform: uppercase; color: var(--text-muted); font-weight: 600; }}
.action-select-block {{
  width: 100%;
  background-color: var(--bg-input);
  color: var(--text-main);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  padding: 6px 8px;
  font-size: 12px;
  outline: none;
  cursor: pointer;
}}
.filter-section-title {{ display: flex; align-items: center; justify-content: space-between; font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px; }}
.layer-checkbox-group {{ display: flex; flex-direction: column; gap: 6px; }}
.layer-cb-item {{ display: flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: 4px; background-color: var(--bg-card); cursor: pointer; font-size: 12px; }}
.canvas-viewport {{ flex: 1; position: relative; overflow: hidden; background: radial-gradient(circle at center, #0f1c29 0%, #080d12 100%); }}
#network-canvas {{ width: 100%; height: 100%; display: block; }}
.active-focus-pill {{
  position: absolute;
  top: 14px;
  left: 14px;
  background-color: rgba(19, 30, 42, 0.9);
  backdrop-filter: blur(8px);
  border: 1px solid var(--layer-db);
  border-radius: 20px;
  padding: 4px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  z-index: 5;
}}
.floating-toolbar {{
  position: absolute;
  bottom: 20px;
  left: 20px;
  background-color: rgba(19, 30, 42, 0.85);
  backdrop-filter: blur(8px);
  border: 1px solid var(--border-strong);
  border-radius: 6px;
  display: flex;
  gap: 4px;
  padding: 4px;
  z-index: 5;
}}
.tool-btn {{
  background: none;
  border: none;
  color: var(--text-main);
  width: 30px;
  height: 30px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}}
.tool-btn:hover {{ background-color: var(--bg-card-hover); color: var(--layer-db); }}
.minimap-container {{
  position: absolute;
  bottom: 20px;
  right: 380px;
  width: 170px;
  background-color: rgba(14, 23, 32, 0.9);
  backdrop-filter: blur(8px);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  overflow: hidden;
  z-index: 5;
}}
.minimap-header {{ padding: 4px 8px; background-color: var(--bg-card); font-size: 10px; color: var(--text-muted); font-family: var(--font-mono); }}
.minimap-body {{ position: relative; width: 100%; height: 110px; }}
#minimap-canvas {{ width: 100%; height: 100%; display: block; }}
.inspector-drawer {{
  width: 360px;
  min-width: 360px;
  background-color: var(--bg-surface);
  border-left: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  z-index: 10;
}}
.inspector-header {{ padding: 12px 16px; border-bottom: 1px solid var(--border-subtle); display: flex; align-items: center; justify-content: space-between; }}
.inspector-content {{ flex: 1; overflow-y: auto; padding: 16px; }}
.insp-card {{ background-color: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 12px; margin-bottom: 12px; }}
.insp-card-title {{ font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px; }}
.insp-meta-row {{ display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 12px; }}
.trace-item {{ display: flex; align-items: center; justify-content: space-between; padding: 5px 8px; background-color: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 4px; font-size: 11px; cursor: pointer; margin-bottom: 4px; }}
.trace-item:hover {{ border-color: var(--layer-db); }}
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: var(--bg-dark); }}
::-webkit-scrollbar-thumb {{ background: var(--border-strong); border-radius: 3px; }}
</style>
</head>
<body>

<div class="topbar">
  <div class="brand">
    <div class="brand-icon">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="6" cy="6" r="3"/><circle cx="18" cy="6" r="3"/><circle cx="12" cy="18" r="3"/>
        <line x1="8.5" y1="7.5" x2="15.5" y2="7.5"/><line x1="7.5" y1="8.5" x2="10.5" y2="15.5"/><line x1="16.5" y1="8.5" x2="13.5" y2="15.5"/>
      </svg>
    </div>
    <div class="brand-text">
      <span class="brand-title">AIDD</span>
      <span class="brand-sub">Unified Knowledge Graph</span>
    </div>
  </div>

  <div class="search-container" id="omnibox-container">
    <div class="search-input-wrapper">
      <input type="text" id="omnibox-input" placeholder="Buscar nodo, tabla, spec o componente... (⌘K o /)" autocomplete="off">
      <kbd class="kbd-shortcut">⌘K</kbd>
    </div>
    <div class="search-results-dropdown" id="search-dropdown" style="display: none;"></div>
  </div>

  <div class="topbar-actions">
    <div class="metrics-pills">
      <div class="metric-pill"><span class="dot dot-db"></span>BD <strong id="metric-db">0</strong></div>
      <div class="metric-pill"><span class="dot dot-code"></span>AST <strong id="metric-code">0</strong></div>
      <div class="metric-pill"><span class="dot dot-spec"></span>Spec <strong id="metric-spec">0</strong></div>
      <div class="metric-pill"><span class="dot dot-ui"></span>UI <strong id="metric-ui">0</strong></div>
    </div>
    <button id="btn-export-json" class="btn-icon">JSON</button>
    <button id="btn-export-svg" class="btn-icon">PNG</button>
  </div>
</div>

<div class="app-container">
  <aside class="sidebar-panel">
    <div class="sidebar-header">
      <span class="sidebar-title">Filtros & Navegación</span>
      <button id="btn-reset-filters" class="btn-text-xs">Restablecer</button>
    </div>
    <div class="sidebar-scrollable">
      <div class="filter-section-starter">
        <div class="filter-section-title">
          <span class="starter-heading">Navegación Jerárquica (5 Niveles)</span>
          <span id="badge-starter-status" style="font-family:var(--font-mono);font-size:10px;color:#fff;">Global</span>
        </div>
        <div class="select-group">
          <label class="select-label">1. Módulo</label>
          <select id="select-module" class="action-select-block"><option value="">— Todos los Módulos —</option></select>
        </div>
        <div class="select-group" style="margin-top:8px;">
          <label class="select-label">2. Spec AIDD</label>
          <select id="select-spec" class="action-select-block"><option value="">— Todas las Specs —</option></select>
        </div>
        <div class="select-group" style="margin-top:8px;">
          <label class="select-label">3. Tabla</label>
          <select id="select-table" class="action-select-block" disabled><option value="">— Seleccionar Tabla —</option></select>
        </div>
        <div class="select-group" style="margin-top:8px;">
          <label class="select-label">4. Objeto (Entidad / Clase)</label>
          <select id="select-entity" class="action-select-block" disabled><option value="">— Seleccionar Entidad o Clase —</option></select>
        </div>
        <div class="select-group" style="margin-top:8px;">
          <label class="select-label">5. Demás objetos / Aristas</label>
          <select id="select-object" class="action-select-block" disabled><option value="">— Seleccionar Objeto / Arista —</option></select>
        </div>
      </div>

      <div class="filter-section">
        <div class="filter-section-title"><span>Capas</span></div>
        <div class="layer-checkbox-group">
          <label class="layer-cb-item"><input type="checkbox" id="layer-cb-db" checked value="db"> Base de Datos</label>
          <label class="layer-cb-item"><input type="checkbox" id="layer-cb-code" checked value="code"> Código AST</label>
          <label class="layer-cb-item"><input type="checkbox" id="layer-cb-spec" checked value="spec"> Specs AIDD</label>
          <label class="layer-cb-item"><input type="checkbox" id="layer-cb-ui" checked value="ui"> Componentes UI</label>
        </div>
      </div>

      <div class="filter-section">
        <div class="filter-section-title"><span>Radio de Vecindario</span><span id="lbl-hop-value">2 saltos</span></div>
        <input type="range" id="hop-radius-slider" min="1" max="5" value="2" step="1" style="width:100%;accent-color:var(--layer-db);">
      </div>
    </div>
  </aside>

  <div class="canvas-viewport" id="canvas-viewport">
    <canvas id="network-canvas"></canvas>
    <div class="active-focus-pill" id="active-focus-pill" style="display:none;">
      <span style="width:8px;height:8px;border-radius:50%;background:#00bcd4;"></span>
      <span id="focus-pill-name" style="font-weight:600;color:#fff;">-</span>
      <button id="btn-clear-focus" style="background:none;border:none;color:#fff;cursor:pointer;">×</button>
    </div>
    <div class="floating-toolbar">
      <button id="btn-zoom-in" class="tool-btn">+</button>
      <button id="btn-zoom-out" class="tool-btn">-</button>
      <button id="btn-zoom-reset" class="tool-btn">100%</button>
    </div>
  </div>

  <div class="minimap-container">
    <div class="minimap-header">Radar de Red</div>
    <div class="minimap-body"><canvas id="minimap-canvas" width="170" height="110"></canvas></div>
  </div>

  <aside class="inspector-drawer" id="inspector-drawer">
    <div class="inspector-header">
      <h2 id="insp-title" style="font-size:14px;color:#fff;">Inspector</h2>
      <button id="btn-close-inspector" style="background:none;border:none;color:#fff;cursor:pointer;">×</button>
    </div>
    <div class="inspector-content">
      <div id="insp-empty-state" style="padding:20px;text-align:center;color:var(--text-faint);">Selecciona un nodo para ver sus relaciones.</div>
      <div id="insp-body" style="display:none;">
        <div class="insp-card">
          <div class="insp-meta-row"><span>ID:</span><code id="insp-id" style="color:var(--layer-db);">-</code></div>
          <div class="insp-meta-row"><span>Tipo:</span><span id="insp-type">-</span></div>
          <div class="insp-meta-row"><span>Dominio:</span><span id="insp-domain">-</span></div>
          <div style="margin-top:8px;font-size:12px;color:#cbd5e1;" id="insp-purpose"></div>
        </div>
        <div class="insp-card">
          <div class="insp-card-title">Trazabilidad Cruzada</div>
          <div style="font-size:10px;color:var(--text-faint);margin-bottom:4px;">Entrantes</div>
          <div id="insp-trace-in"></div>
          <div style="font-size:10px;color:var(--text-faint);margin:8px 0 4px;">Salientes</div>
          <div id="insp-trace-out"></div>
        </div>
      </div>
    </div>
  </aside>
</div>

<script id="graph-data" type="application/json">{embedded_data}</script>

<script>
(function() {{
  "use strict";
  const rawData = JSON.parse(document.getElementById("graph-data").textContent);
  const nodes = rawData.nodes || [];
  const edges = rawData.edges || [];
  const domains = rawData.domains || [];

  const nodeById = new Map();
  const outgoing = new Map();
  const incoming = new Map();
  const nodesByLayer = {{ db: [], code: [], spec: [], ui: [] }};

  nodes.forEach(n => {{
    nodeById.set(n.id, n);
    outgoing.set(n.id, []);
    incoming.set(n.id, []);
    if (nodesByLayer[n.layer]) nodesByLayer[n.layer].push(n);
  }});

  edges.forEach(e => {{
    if (outgoing.has(e.source)) outgoing.get(e.source).push(e);
    if (incoming.has(e.target)) incoming.get(e.target).push(e);
  }});

  let activeLayers = new Set(["db", "code", "spec", "ui"]);
  let activeDomains = new Set(domains);
  let hopRadius = 2;
  let focalNodeId = null;

  let displayNodes = [];
  let displayEdges = [];

  const canvas = document.getElementById("network-canvas");
  const ctx = canvas.getContext("2d");
  const miniCanvas = document.getElementById("minimap-canvas");
  const miniCtx = miniCanvas ? miniCanvas.getContext("2d") : null;

  let transform = {{ x: 0, y: 0, k: 1.0 }};
  let isDragging = false;
  let dragStart = {{ x: 0, y: 0 }};
  let hoveredNode = null;

  document.getElementById("metric-db").textContent = (nodesByLayer.db.length || 0).toLocaleString();
  document.getElementById("metric-code").textContent = (nodesByLayer.code.length || 0).toLocaleString();
  document.getElementById("metric-spec").textContent = (nodesByLayer.spec.length || 0).toLocaleString();
  document.getElementById("metric-ui").textContent = (nodesByLayer.ui.length || 0).toLocaleString();

  // 5-Level Cascading Drill-Down Selects: Módulo -> Spec -> Tabla -> Objeto/Clase -> Demás objetos/Aristas
  const moduleSelect = document.getElementById("select-module");
  const specSelect = document.getElementById("select-spec");
  const tableSelect = document.getElementById("select-table");
  const entitySelect = document.getElementById("select-entity");
  const objectSelect = document.getElementById("select-object");

  function populateModuleDropdown() {{
    if (!moduleSelect) return;
    moduleSelect.innerHTML = '<option value="">— Todos los Módulos —</option>';
    domains.forEach(d => {{
      const opt = document.createElement("option");
      opt.value = d;
      opt.textContent = d;
      moduleSelect.appendChild(opt);
    }});
  }}

  function populateSpecDropdown(selectedDomain) {{
    if (!specSelect) return;
    specSelect.innerHTML = '<option value="">— Todas las Specs —</option>';
    const specNodes = nodes.filter(n => n.layer === "spec");
    const filtered = selectedDomain ? specNodes.filter(n => n.domain === selectedDomain) : specNodes;
    filtered.sort((a, b) => a.label.localeCompare(b.label));
    filtered.forEach(sn => {{
      const opt = document.createElement("option");
      opt.value = sn.id;
      opt.textContent = `[${{sn.domain}}] ${{sn.label}}`;
      specSelect.appendChild(opt);
    }});
  }}

  function populateTableDropdown(specId, selectedDomain) {{
    if (!tableSelect) return;
    tableSelect.innerHTML = '<option value="">— Seleccionar Tabla —</option>';
    let tables = [];

    if (specId && nodeById.has(specId)) {{
      const connectedTables = new Set();
      const direct = new Set();
      (outgoing.get(specId) || []).forEach(e => direct.add(e.target));
      (incoming.get(specId) || []).forEach(e => direct.add(e.source));

      direct.forEach(nid => {{
        const n = nodeById.get(nid);
        if (n && n.layer === "db" && (n.type === "table" || n.type === "view")) {{
          connectedTables.add(nid);
        }} else if (n && n.layer === "code") {{
          (outgoing.get(nid) || []).forEach(e2 => {{
            const n2 = nodeById.get(e2.target);
            if (n2 && n2.layer === "db" && (n2.type === "table" || n2.type === "view")) connectedTables.add(n2.id);
          }});
        }}
      }});

      const sn = nodeById.get(specId);
      const specDomain = (sn && sn.domain) ? sn.domain : selectedDomain;
      nodes.forEach(n => {{
        if (n.layer === "db" && (n.type === "table" || n.type === "view")) {{
          if (connectedTables.has(n.id) || (specDomain && n.domain === specDomain)) {{
            connectedTables.add(n.id);
          }}
        }}
      }});
      tables = Array.from(connectedTables).map(id => nodeById.get(id)).filter(Boolean);
    }} else if (selectedDomain) {{
      tables = nodes.filter(n => n.layer === "db" && (n.type === "table" || n.type === "view") && n.domain === selectedDomain);
    }} else {{
      tables = nodes.filter(n => n.layer === "db" && (n.type === "table" || n.type === "view"));
    }}

    tables.sort((a, b) => a.label.localeCompare(b.label));
    tables.forEach(t => {{
      const opt = document.createElement("option");
      opt.value = t.id;
      opt.textContent = `[Tabla] ${{t.label}} (${{t.domain || 'DB'}})`;
      tableSelect.appendChild(opt);
    }});
    tableSelect.disabled = (tables.length === 0);
  }}

  function populateEntityDropdown(tableId, specId) {{
    if (!entitySelect) return;
    entitySelect.innerHTML = '<option value="">— Seleccionar Entidad o Clase —</option>';
    if (!tableId || !nodeById.has(tableId)) {{
      entitySelect.disabled = true;
      return;
    }}

    const tNode = nodeById.get(tableId);
    const relatedEntities = new Map();

    const tableCols = new Set();
    (incoming.get(tableId) || []).forEach(e => {{
      if (e.relation === "pertenece_a") tableCols.add(e.source);
    }});
    (outgoing.get(tableId) || []).forEach(e => {{
      if (e.relation === "pertenece_a") tableCols.add(e.target);
    }});

    (outgoing.get(tableId) || []).forEach(e => {{
      const n = nodeById.get(e.target);
      if (n && (n.layer === "code" || n.layer === "ui" || (n.layer === "db" && n.type === "function"))) {{
        relatedEntities.set(n.id, n);
      }}
    }});
    (incoming.get(tableId) || []).forEach(e => {{
      const n = nodeById.get(e.source);
      if (n && (n.layer === "code" || n.layer === "ui" || (n.layer === "db" && n.type === "function"))) {{
        relatedEntities.set(n.id, n);
      }}
    }});

    tableCols.forEach(colId => {{
      (incoming.get(colId) || []).forEach(e => {{
        const n = nodeById.get(e.source);
        if (n && (n.layer === "code" || (n.layer === "db" && n.type === "function"))) {{
          relatedEntities.set(n.id, n);
        }}
      }});
      (outgoing.get(colId) || []).forEach(e => {{
        const n = nodeById.get(e.target);
        if (n && (n.layer === "code" || (n.layer === "db" && n.type === "function"))) {{
          relatedEntities.set(n.id, n);
        }}
      }});
    }});

    if (specId && nodeById.has(specId)) {{
      (outgoing.get(specId) || []).forEach(e => {{
        const n = nodeById.get(e.target);
        if (n && n.layer === "code" && (n.type === "CLASS" || n.type === "FILE")) {{
          relatedEntities.set(n.id, n);
        }}
      }});
    }}

    const entityList = Array.from(relatedEntities.values());
    if (entityList.length === 0) {{
      const opt = document.createElement("option");
      opt.value = tableId;
      opt.textContent = `[Entidad Base] Modelo de ${{tNode.label}} (${{tNode.domain}})`;
      entitySelect.appendChild(opt);
      entitySelect.disabled = false;
      return;
    }}

    entityList.sort((a, b) => {{
      if (a.layer !== b.layer) return a.layer.localeCompare(b.layer);
      return a.label.localeCompare(b.label);
    }});

    entityList.forEach(ent => {{
      const opt = document.createElement("option");
      opt.value = ent.id;
      let badge = "Objeto";
      if (ent.layer === "code") {{
        badge = ent.type === "CLASS" ? "Clase" : (ent.type === "FUNC" ? "Método" : "Archivo");
      }} else if (ent.layer === "ui") {{
        badge = "UI";
      }} else if (ent.type === "function") {{
        badge = "Procedimiento";
      }}
      opt.textContent = `[${{badge}}] ${{ent.label}} (${{ent.domain || 'Code'}})`;
      entitySelect.appendChild(opt);
    }});
    entitySelect.disabled = false;
  }}

  function populateEdgeObjectDropdown(entityId, tableId) {{
    if (!objectSelect) return;
    objectSelect.innerHTML = '<option value="">— Seleccionar Objeto / Arista —</option>';
    const focalId = entityId || tableId;
    if (!focalId || !nodeById.has(focalId)) {{
      objectSelect.disabled = true;
      return;
    }}

    const items = [];
    const focalNode = nodeById.get(focalId);

    const outEdges = outgoing.get(focalId) || [];
    const inEdges = incoming.get(focalId) || [];

    outEdges.forEach(e => {{
      const target = nodeById.get(e.target);
      if (target) {{
        items.push({{
          id: target.id,
          label: `[Arista: ${{e.relation}}] -> ${{target.label}} (${{target.layer}}/${{target.type || 'nodo'}})`,
          targetId: target.id,
          relation: e.relation
        }});
      }}
    }});

    inEdges.forEach(e => {{
      const source = nodeById.get(e.source);
      if (source) {{
        items.push({{
          id: source.id,
          label: `[Arista: ${{e.relation}}] <- ${{source.label}} (${{source.layer}}/${{source.type || 'nodo'}})`,
          targetId: source.id,
          relation: e.relation
        }});
      }}
    }});

    if (focalNode.layer === "db" && (focalNode.type === "table" || focalNode.type === "view")) {{
      inEdges.forEach(e => {{
        if (e.relation === "pertenece_a") {{
          const colNode = nodeById.get(e.source);
          if (colNode && colNode.type === "column") {{
            items.push({{
              id: colNode.id,
              label: `[Columna] ${{colNode.label}}`,
              targetId: colNode.id,
              relation: "columna"
            }});
          }}
        }}
      }});
    }}

    if (items.length === 0) {{
      objectSelect.disabled = true;
      return;
    }}

    const seen = new Set();
    items.forEach(item => {{
      const key = item.id + "_" + item.relation;
      if (!seen.has(key)) {{
        seen.add(key);
        const opt = document.createElement("option");
        opt.value = item.targetId;
        opt.textContent = item.label;
        objectSelect.appendChild(opt);
      }}
    }});
    objectSelect.disabled = false;
  }}

  // Por defecto solo debe mostrar todas las specs, no un spec seleccionado
  function initAllSpecsView() {{
    focalNodeId = null;
    if (moduleSelect) moduleSelect.value = "";
    populateSpecDropdown("");
    if (specSelect) specSelect.value = "";
    if (tableSelect) {{
      tableSelect.innerHTML = '<option value="">— Seleccionar Tabla —</option>';
      tableSelect.disabled = true;
    }}
    if (entitySelect) {{
      entitySelect.innerHTML = '<option value="">— Seleccionar Entidad o Clase —</option>';
      entitySelect.disabled = true;
    }}
    if (objectSelect) {{
      objectSelect.innerHTML = '<option value="">— Seleccionar Objeto / Arista —</option>';
      objectSelect.disabled = true;
    }}
    document.getElementById("badge-starter-status").textContent = "Todas las Specs";
    document.getElementById("insp-empty-state").style.display = "flex";
    document.getElementById("insp-body").style.display = "none";
    document.getElementById("active-focus-pill").style.display = "none";
    recalculateSubgraph(false);
  }}

  populateModuleDropdown();
  populateSpecDropdown("");

  if (moduleSelect) {{
    moduleSelect.addEventListener("change", () => {{
      const mod = moduleSelect.value;
      populateSpecDropdown(mod);
      if (tableSelect) {{
        tableSelect.innerHTML = '<option value="">— Seleccionar Tabla —</option>';
        tableSelect.disabled = true;
      }}
      if (entitySelect) {{
        entitySelect.innerHTML = '<option value="">— Seleccionar Entidad o Clase —</option>';
        entitySelect.disabled = true;
      }}
      if (objectSelect) {{
        objectSelect.innerHTML = '<option value="">— Seleccionar Objeto / Arista —</option>';
        objectSelect.disabled = true;
      }}
      focalNodeId = null;
      if (specSelect) specSelect.value = "";
      if (mod) {{
        activeDomains = new Set([mod]);
        document.getElementById("badge-starter-status").textContent = `Módulo: ${{mod}}`;
      }} else {{
        activeDomains = new Set(domains);
        document.getElementById("badge-starter-status").textContent = "Todas las Specs";
      }}
      recalculateSubgraph(false);
    }});
  }}

  if (specSelect) {{
    specSelect.addEventListener("change", () => {{
      const specId = specSelect.value;
      if (specId) {{
        activeLayers = new Set(["db", "code", "spec", "ui"]);
        ["db", "code", "spec", "ui"].forEach(l => {{
          const cb = document.getElementById(`layer-cb-${{l}}`);
          if (cb) cb.checked = true;
        }});
        const sn = nodeById.get(specId);
        if (sn) {{
          if (moduleSelect && !moduleSelect.value) moduleSelect.value = sn.domain || "";
          populateTableDropdown(specId, sn.domain);
          if (entitySelect) {{
            entitySelect.innerHTML = '<option value="">— Seleccionar Entidad o Clase —</option>';
            entitySelect.disabled = true;
          }}
          if (objectSelect) {{
            objectSelect.innerHTML = '<option value="">— Seleccionar Objeto / Arista —</option>';
            objectSelect.disabled = true;
          }}
          document.getElementById("badge-starter-status").textContent = `Spec: ${{sn.label}}`;
          setFocalNode(sn.id, true);
        }}
      }} else {{
        if (tableSelect) {{
          tableSelect.innerHTML = '<option value="">— Seleccionar Tabla —</option>';
          tableSelect.disabled = true;
        }}
        if (entitySelect) {{
          entitySelect.innerHTML = '<option value="">— Seleccionar Entidad o Clase —</option>';
          entitySelect.disabled = true;
        }}
        if (objectSelect) {{
          objectSelect.innerHTML = '<option value="">— Seleccionar Objeto / Arista —</option>';
          objectSelect.disabled = true;
        }}
        focalNodeId = null;
        recalculateSubgraph(true);
      }}
    }});
  }}

  if (tableSelect) {{
    tableSelect.addEventListener("change", () => {{
      const tableId = tableSelect.value;
      if (tableId) {{
        const tNode = nodeById.get(tableId);
        if (tNode) {{
          populateEntityDropdown(tableId, specSelect ? specSelect.value : "");
          if (objectSelect) {{
            objectSelect.innerHTML = '<option value="">— Seleccionar Objeto / Arista —</option>';
            objectSelect.disabled = true;
          }}
          document.getElementById("badge-starter-status").textContent = `Tabla: ${{tNode.label}}`;
          setFocalNode(tableId, true);
        }}
      }} else {{
        if (entitySelect) {{
          entitySelect.innerHTML = '<option value="">— Seleccionar Entidad o Clase —</option>';
          entitySelect.disabled = true;
        }}
        if (objectSelect) {{
          objectSelect.innerHTML = '<option value="">— Seleccionar Objeto / Arista —</option>';
          objectSelect.disabled = true;
        }}
        if (specSelect && specSelect.value) {{
          setFocalNode(specSelect.value, true);
        }}
      }}
    }});
  }}

  if (entitySelect) {{
    entitySelect.addEventListener("change", () => {{
      const entityId = entitySelect.value;
      if (entityId) {{
        const entNode = nodeById.get(entityId);
        if (entNode) {{
          populateEdgeObjectDropdown(entityId, tableSelect ? tableSelect.value : "");
          document.getElementById("badge-starter-status").textContent = `Objeto: ${{entNode.label}}`;
          setFocalNode(entityId, true);
        }}
      }} else {{
        if (objectSelect) {{
          objectSelect.innerHTML = '<option value="">— Seleccionar Objeto / Arista —</option>';
          objectSelect.disabled = true;
        }}
        if (tableSelect && tableSelect.value) {{
          setFocalNode(tableSelect.value, true);
        }}
      }}
    }});
  }}

  if (objectSelect) {{
    objectSelect.addEventListener("change", () => {{
      const objId = objectSelect.value;
      if (objId) {{
        hopRadius = 1;
        document.getElementById("hop-radius-slider").value = 1;
        document.getElementById("lbl-hop-value").textContent = "1 salto";
        setFocalNode(objId, true);
      }}
    }});
  }}

  function resizeCanvas() {{
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    render();
  }}
  window.addEventListener("resize", resizeCanvas);

  function computeNeighborhood(focalId, radius) {{
    if (!nodeById.has(focalId)) return {{ nodes: [], edges: [] }};
    const visited = new Set([focalId]);
    const queue = [[focalId, 0]];
    const nodeDepths = new Map([[focalId, 0]]);

    while (queue.length > 0) {{
      const [curr, depth] = queue.shift();
      if (depth >= radius) continue;
      const neighbors = [];
      (outgoing.get(curr) || []).forEach(e => neighbors.push(e.target));
      (incoming.get(curr) || []).forEach(e => neighbors.push(e.source));

      for (const nxt of neighbors) {{
        if (!visited.has(nxt)) {{
          const nNode = nodeById.get(nxt);
          if (nNode && activeLayers.has(nNode.layer)) {{
            visited.add(nxt);
            nodeDepths.set(nxt, depth + 1);
            queue.push([nxt, depth + 1]);
          }}
        }}
      }}
    }}

    let finalNodes = Array.from(visited).map(id => ({{ ...nodeById.get(id), depth: nodeDepths.get(id) || 0 }}));
    if (finalNodes.length > 200) {{
      finalNodes.sort((a, b) => (a.depth || 0) - (b.depth || 0));
      finalNodes = finalNodes.slice(0, 200);
    }}
    const finalSet = new Set(finalNodes.map(n => n.id));
    const subEdges = edges.filter(e => finalSet.has(e.source) && finalSet.has(e.target));
    return {{ nodes: finalNodes, edges: subEdges }};
  }}

  function layoutNodes() {{
    const w = canvas.getBoundingClientRect().width;
    const h = canvas.getBoundingClientRect().height;
    const cx = w / 2, cy = h / 2;

    if (!focalNodeId || displayNodes.length === 0) {{
      const total = displayNodes.length;
      if (total <= 12) {{
        const r = Math.min(w, h) * 0.35;
        displayNodes.forEach((n, idx) => {{
          const theta = (idx / total) * 2 * Math.PI - Math.PI / 2;
          n.x = cx + r * Math.cos(theta);
          n.y = cy + r * Math.sin(theta);
        }});
      }} else {{
        const ring1Count = Math.round(total * 0.38);
        const ring2Count = total - ring1Count;
        const r1 = Math.min(w, h) * 0.22;
        const r2 = Math.min(w, h) * 0.40;

        displayNodes.forEach((n, idx) => {{
          if (idx < ring1Count) {{
            const theta = (idx / ring1Count) * 2 * Math.PI - Math.PI / 2;
            n.x = cx + r1 * Math.cos(theta);
            n.y = cy + r1 * Math.sin(theta);
          }} else {{
            const j = idx - ring1Count;
            const theta = (j / ring2Count) * 2 * Math.PI - Math.PI / 2;
            n.x = cx + r2 * Math.cos(theta);
            n.y = cy + r2 * Math.sin(theta);
          }}
        }});
      }}
      return;
    }}

    const focal = displayNodes.find(n => n.id === focalNodeId);
    if (focal) {{ focal.x = cx; focal.y = cy; }}

    const byDepth = new Map();
    displayNodes.forEach(n => {{
      if (n.id === focalNodeId) return;
      const d = n.depth || 1;
      if (!byDepth.has(d)) byDepth.set(d, []);
      byDepth.get(d).push(n);
    }});

    const ringStep = Math.min(w, h) * 0.18;
    byDepth.forEach((arr, d) => {{
      const ringRadius = d * ringStep;
      arr.forEach((n, idx) => {{
        const theta = (idx / arr.length) * 2 * Math.PI + (d * 0.5);
        n.x = cx + ringRadius * Math.cos(theta);
        n.y = cy + ringRadius * Math.sin(theta);
      }});
    }});
  }}

  function recalculateSubgraph(maintainScale = false) {{
    if (!focalNodeId) {{
      const specNodes = nodes.filter(n => n.layer === "spec" && activeDomains.has(n.domain));
      displayNodes = specNodes.map(n => ({{ ...n, depth: 1 }}));
      const idSet = new Set(displayNodes.map(n => n.id));
      displayEdges = edges.filter(e => idSet.has(e.source) && idSet.has(e.target));
      document.getElementById("active-focus-pill").style.display = "none";
    }} else {{
      const sub = computeNeighborhood(focalNodeId, hopRadius);
      displayNodes = sub.nodes;
      displayEdges = sub.edges;
      const pill = document.getElementById("active-focus-pill");
      pill.style.display = "flex";
      const focal = nodeById.get(focalNodeId);
      document.getElementById("focus-pill-name").textContent = focal ? focal.label : focalNodeId;
    }}

    layoutNodes();
    const w = canvas.getBoundingClientRect().width;
    const h = canvas.getBoundingClientRect().height;
    if (!maintainScale) {{
      transform.k = 1.0;
      transform.x = 0;
      transform.y = 0;
    }} else {{
      transform.x = (w / 2) * (1 - transform.k);
      transform.y = (h / 2) * (1 - transform.k);
    }}
    render();
  }}

  function getNodeColor(layer) {{
    switch (layer) {{
      case "db": return "#00bcd4";
      case "code": return "#10b981";
      case "spec": return "#a855f7";
      case "ui": return "#f59e0b";
      default: return "#94a3b8";
    }}
  }}

  function render() {{
    const w = canvas.getBoundingClientRect().width;
    const h = canvas.getBoundingClientRect().height;
    ctx.clearRect(0, 0, w, h);

    ctx.save();
    ctx.translate(transform.x, transform.y);
    ctx.scale(transform.k, transform.k);

    displayEdges.forEach(e => {{
      const s = displayNodes.find(n => n.id === e.source);
      const t = displayNodes.find(n => n.id === e.target);
      if (!s || !t) return;
      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(t.x, t.y);
      ctx.strokeStyle = e.cross_layer ? "rgba(56, 189, 248, 0.4)" : "rgba(255, 255, 255, 0.12)";
      ctx.lineWidth = 1.0 / transform.k;
      ctx.stroke();
    }});

    displayNodes.forEach(n => {{
      const isFocal = (n.id === focalNodeId);
      const radius = isFocal ? 14 : 8;
      const col = getNodeColor(n.layer);

      if (isFocal) {{
        ctx.beginPath();
        ctx.arc(n.x, n.y, radius + 8, 0, 2 * Math.PI);
        ctx.fillStyle = "rgba(0, 188, 212, 0.25)";
        ctx.fill();
      }}

      ctx.beginPath();
      ctx.arc(n.x, n.y, radius, 0, 2 * Math.PI);
      ctx.fillStyle = col;
      ctx.fill();

      if (transform.k > 0.5 || isFocal) {{
        ctx.font = `${{isFocal ? "bold 11px" : "10px"}} Roboto Flex, sans-serif`;
        ctx.fillStyle = isFocal ? "#70f3ff" : "#cbd5e1";
        ctx.textAlign = "center";
        ctx.fillText(n.label, n.x, n.y + radius + 12);
      }}
    }});

    ctx.restore();
    renderMinimap();
  }}

  function renderMinimap() {{
    if (!miniCtx) return;
    const mw = miniCanvas.width, mh = miniCanvas.height;
    miniCtx.clearRect(0, 0, mw, mh);
    if (displayNodes.length === 0) return;

    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    displayNodes.forEach(n => {{
      if (n.x < minX) minX = n.x;
      if (n.x > maxX) maxX = n.x;
      if (n.y < minY) minY = n.y;
      if (n.y > maxY) maxY = n.y;
    }});
    const scale = Math.min(mw / (maxX - minX || 1), mh / (maxY - minY || 1));
    miniCtx.fillStyle = "rgba(0, 188, 212, 0.6)";
    displayNodes.forEach(n => {{
      miniCtx.fillRect((n.x - minX) * scale, (n.y - minY) * scale, 2, 2);
    }});
  }}

  function setFocalNode(id, maintainScale = true) {{
    focalNodeId = id;
    const n = nodeById.get(id);
    if (!n) return;

    document.getElementById("insp-empty-state").style.display = "none";
    document.getElementById("insp-body").style.display = "block";
    document.getElementById("insp-title").textContent = n.label;
    document.getElementById("insp-id").textContent = n.id;
    document.getElementById("insp-type").textContent = `${{n.type}} / ${{n.layer.toUpperCase()}}`;
    document.getElementById("insp-domain").textContent = n.domain;
    document.getElementById("insp-purpose").textContent = n.purpose || "Sin descripción documentada.";

    if (n.layer === "spec") {{
      if (moduleSelect && moduleSelect.value !== (n.domain || "")) {{
        moduleSelect.value = n.domain || "";
        populateSpecDropdown(n.domain || "");
      }}
      if (specSelect) specSelect.value = n.id;
      document.getElementById("badge-starter-status").textContent = `Spec: ${{n.label}}`;
      populateTableDropdown(n.id, n.domain);
    }} else if (n.layer === "db" && (n.type === "table" || n.type === "view")) {{
      if (tableSelect) tableSelect.value = n.id;
      document.getElementById("badge-starter-status").textContent = `Tabla: ${{n.label}}`;
      populateEntityDropdown(n.id, specSelect ? specSelect.value : "");
    }} else if (n.layer === "code" || n.layer === "ui" || n.type === "function") {{
      if (entitySelect) entitySelect.value = n.id;
      document.getElementById("badge-starter-status").textContent = `Objeto: ${{n.label}}`;
      populateEdgeObjectDropdown(n.id, tableSelect ? tableSelect.value : "");
    }} else if (n.type === "column" || n.type === "check" || n.type === "index" || n.type === "trigger") {{
      if (objectSelect) objectSelect.value = n.id;
      document.getElementById("badge-starter-status").textContent = `Arista: ${{n.label}}`;
    }}

    const inEdges = incoming.get(id) || [];
    const outEdges = outgoing.get(id) || [];
    const inList = document.getElementById("insp-trace-in");
    inList.innerHTML = "";
    inEdges.slice(0, 10).forEach(e => {{
      const s = nodeById.get(e.source);
      const row = document.createElement("div");
      row.className = "trace-item";
      row.innerHTML = `<span>${{s ? s.label : e.source}}</span><span style="color:var(--text-muted);">${{e.relation}}</span>`;
      row.onclick = () => setFocalNode(e.source, true);
      inList.appendChild(row);
    }});

    const outList = document.getElementById("insp-trace-out");
    outList.innerHTML = "";
    outEdges.slice(0, 10).forEach(e => {{
      const t = nodeById.get(e.target);
      const row = document.createElement("div");
      row.className = "trace-item";
      row.innerHTML = `<span>${{t ? t.label : e.target}}</span><span style="color:var(--text-muted);">${{e.relation}}</span>`;
      row.onclick = () => setFocalNode(e.target, true);
      outList.appendChild(row);
    }});

    recalculateSubgraph(maintainScale);
  }}

  canvas.addEventListener("mousedown", e => {{
    isDragging = true;
    dragStart = {{ x: e.clientX - transform.x, y: e.clientY - transform.y }};
  }});

  window.addEventListener("mousemove", e => {{
    if (isDragging) {{
      transform.x = e.clientX - dragStart.x;
      transform.y = e.clientY - dragStart.y;
      render();
    }}
  }});

  window.addEventListener("mouseup", () => {{ isDragging = false; }});

  canvas.addEventListener("wheel", e => {{
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.12 : 0.88;
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left, mouseY = e.clientY - rect.top;
    transform.x = mouseX - (mouseX - transform.x) * zoomFactor;
    transform.y = mouseY - (mouseY - transform.y) * zoomFactor;
    transform.k = Math.max(0.15, Math.min(transform.k * zoomFactor, 4.0));
    render();
  }}, {{ passive: false }});

  canvas.addEventListener("click", e => {{
    const rect = canvas.getBoundingClientRect();
    const mx = (e.clientX - rect.left - transform.x) / transform.k;
    const my = (e.clientY - rect.top - transform.y) / transform.k;
    for (const n of displayNodes) {{
      const dx = n.x - mx, dy = n.y - my;
      if (dx * dx + dy * dy <= 144) {{
        setFocalNode(n.id, true);
        break;
      }}
    }}
  }});

  document.getElementById("btn-reset-filters").onclick = () => {{
    activeLayers = new Set(["db", "code", "spec", "ui"]);
    ["db", "code", "spec", "ui"].forEach(l => {{ document.getElementById(`layer-cb-${{l}}`).checked = true; }});
    activeDomains = new Set(domains);
    if (moduleSelect) moduleSelect.value = "";
    populateSpecDropdown("");
    if (specSelect) specSelect.value = "";
    if (tableSelect) {{
      tableSelect.innerHTML = '<option value="">— Seleccionar Tabla —</option>';
      tableSelect.disabled = true;
    }}
    if (entitySelect) {{
      entitySelect.innerHTML = '<option value="">— Seleccionar Entidad o Clase —</option>';
      entitySelect.disabled = true;
    }}
    if (objectSelect) {{
      objectSelect.innerHTML = '<option value="">— Seleccionar Objeto / Arista —</option>';
      objectSelect.disabled = true;
    }}
    document.getElementById("badge-starter-status").textContent = "Global";
    focalNodeId = null;
    hopRadius = 2;
    document.getElementById("hop-radius-slider").value = 2;
    document.getElementById("lbl-hop-value").textContent = "2 saltos";
    document.getElementById("insp-empty-state").style.display = "block";
    document.getElementById("insp-body").style.display = "none";
    initAllSpecsView();
  }};

  document.getElementById("btn-clear-focus").onclick = () => {{
    focalNodeId = null;
    recalculateSubgraph(true);
  }};

  document.getElementById("btn-zoom-in").onclick = () => {{ transform.k = Math.min(transform.k * 1.25, 4.0); render(); }};
  document.getElementById("btn-zoom-out").onclick = () => {{ transform.k = Math.max(transform.k * 0.8, 0.2); render(); }};
  document.getElementById("btn-zoom-reset").onclick = () => {{ transform = {{ x: 0, y: 0, k: 1.0 }}; render(); }};

  document.getElementById("btn-export-json").onclick = () => {{
    const blob = new Blob([JSON.stringify({{ focalNode: focalNodeId, nodes: displayNodes, edges: displayEdges }}, null, 2)], {{ type: "application/json" }});
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `graph-${{focalNodeId || "unified"}}.json`;
    a.click();
  }};

  document.getElementById("btn-export-svg").onclick = () => {{
    const a = document.createElement("a");
    a.href = canvas.toDataURL("image/png");
    a.download = `graph-${{focalNodeId || "unified"}}.png`;
    a.click();
  }};

  resizeCanvas();
  initAllSpecsView();
}})();
</script>
</body>
</html>"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--graph", default=None, help="Ruta al archivo graph.json específico")
    ap.add_argument("--out", default=None, help="Ruta del archivo HTML de salida")
    ap.add_argument("--title", default=DEFAULT_TITLE, help="Título del explorador")
    ap.add_argument("--root", default=None, help="Directorio raíz del proyecto AIDD")
    a = ap.parse_args(argv)

    root = Path(a.root).resolve() if a.root else Path(__file__).resolve().parent.parent.parent

    if a.graph:
        gp = Path(a.graph)
        try:
            raw_data = json.loads(gp.read_text(encoding="utf-8"))
        except Exception as ex:
            print(f"graph_explorer: cannot read {gp}: {ex}", file=sys.stderr)
            return 2
        out = Path(a.out) if a.out else gp.with_suffix(".html")
        html_page = build_html(raw_data, a.title)
    else:
        # Modo Unificado Global del Proyecto AIDD
        sys.path.insert(0, str(root / "docs" / "db-graph"))
        try:
            from unified_graph_model import UnifiedGraphModel
            model = UnifiedGraphModel(root=root)
            raw_data = model.load()
        except Exception as ex:
            print(f"graph_explorer: error building unified model: {ex}", file=sys.stderr)
            return 2
        out = Path(a.out) if a.out else (root / "docs" / "db-graph" / "explorer.html")
        html_page = build_html(raw_data, a.title)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_page, encoding="utf-8")
    print(f"explorer: {len(raw_data.get('nodes', []))} nodes -> {out} ({len(html_page):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
