#!/usr/bin/env python3
"""Executive Precision Unified Graph Explorer generator for AIDD.
Single-file, self-contained interactive Canvas 2D visualization (0 CDN dependencies, stdlib only).

Usage:  python graph_explorer.py --graph FILE [--kind K] [--layer L] [--out <file.html>] [--title TEXT]
        python graph_explorer.py [--root DIR] [--out <file.html>] [--title TEXT]
(--root DIR: unified explorer of every registered graph, default <root>/docs/graphs/explorer.html;
 --graph FILE: one .json or .toon graph, default <graph>.html)
"""
import argparse
import html as _html
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import unified_graph  # noqa: E402

DEFAULT_TITLE = "AIDD :: Unified Knowledge Graph Explorer"
DEFAULT_UNIFIED_OUT = "docs/graphs/explorer.html"
DEFAULT_MAX_MB = 25
ALIAS_LEGEND = ("old name", "new name", "renamed in progress")


def embed_json(obj):
    """JSON safe inside <script>: no '</', no HTML comments, ASCII only."""
    s = json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026") \
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def build_unified_payload(graph, root_dir=None):
    """A unified payload (dict with `layers`) as is; any other graph dict as one layer (aidd:FR-067)."""
    if not isinstance(graph, dict):
        raise ValueError("graph must be a JSON object")
    if "layers" in graph:
        return graph
    return unified_graph.single_layer(graph)


_F47_LAYERS = ("db", "code", "spec", "ui")


def _metric_pills(layers):
    return "\n".join(
        '      <div class="metric-pill"><span class="dot dot-%s"></span>%s <strong id="metric-%s">0</strong></div>'
        % (l["id"], _html.escape(str(l["label"]), quote=True), l["id"]) for l in layers)


def _layer_checkboxes(layers):
    return "\n".join(
        '          <label class="layer-cb-item"><input type="checkbox" id="layer-cb-%s" checked value="%s"> %s</label>'
        % (l["id"], _html.escape(str(l["name"]), quote=True), _html.escape(str(l["title"]), quote=True))
        for l in layers)


def _extra_layer_css(layers):
    out = []
    for l in layers:
        if l["id"] in _F47_LAYERS:
            continue
        out.append(":root { --layer-%s: %s; }" % (l["id"], l["color"]))
        out.append(".dot-%s { background-color: var(--layer-%s); }" % (l["id"], l["id"]))
    return "\n".join(out)


def build_html(graph_data, title=DEFAULT_TITLE):
    payload = build_unified_payload(graph_data)
    embedded_data = embed_json(payload)
    safe_title = _html.escape(title, quote=True)
    layers = payload.get("layers") or []
    metric_pills_html = _metric_pills(layers)
    layer_checkboxes_html = _layer_checkboxes(layers)
    extra_layer_css = _extra_layer_css(layers)

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
  --alias-old: #f85149;
  --alias-new: #3fb950;
  --alias-prog: #d29922;
  --font-sans: "Roboto Flex", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}}
:root.light {{
  --bg-dark: #ffffff;
  --bg-surface: #f6f8fa;
  --bg-card: #ffffff;
  --bg-card-hover: #f6f8fa;
  --bg-input: #f6f8fa;
  --border-subtle: #d0d7de;
  --border-strong: #d0d7de;
  --text-main: #1b1f24;
  --text-muted: #667788;
  --text-faint: #667788;
  --alias-old: #d9383a;
  --alias-new: #1a7f37;
  --alias-prog: #bf8700;
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
{extra_layer_css}
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
.insp-tech-details {{ font-size: 11px; font-family: var(--font-mono); }}
.tech-row {{ display: flex; justify-content: space-between; padding: 2px 0; border-bottom: 1px solid rgba(255,255,255,0.03); }}
.tech-k {{ color: var(--text-muted); }}
.tech-v {{ color: #e2e8f0; }}
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
    <div id="legend-aliases" style="display:none;align-items:center;gap:10px;font-size:11px;padding:3px 8px;border-radius:4px;border:1px solid var(--border-subtle);background:var(--bg-card);">
      <div style="display:flex;align-items:center;gap:5px;"><span style="width:8px;height:8px;border-radius:50%;background-color:var(--alias-old);"></span><span>old name</span></div>
      <div style="display:flex;align-items:center;gap:5px;"><span style="width:8px;height:8px;border-radius:50%;background-color:var(--alias-new);"></span><span>new name</span></div>
      <div style="display:flex;align-items:center;gap:5px;"><span style="width:8px;height:8px;border-radius:50%;background-color:var(--alias-prog);"></span><span>renamed in progress</span></div>
      <span style="color:var(--text-faint);">•</span>
      <span style="color:var(--text-muted);">Edge type: <strong style="font-family:var(--font-mono);color:var(--text-main);">RENAMED_TO</strong></span>
    </div>
    <div class="metrics-pills">
{metric_pills_html}
    </div>
    <button id="btn-export-json" class="btn-icon">JSON</button>
    <button id="btn-export-svg" class="btn-icon">PNG</button>
    <button id="themeToggleBtn" class="btn-icon">Tema</button>
  </div>
</div>

<div id="aliases-empty-banner" style="display:none;background:var(--bg-card);border-bottom:1px solid var(--border-subtle);color:var(--alias-prog);padding:8px 16px;font-size:12px;">No aliases: the project has not generated .aidd/graphs/path-aliases.toon</div>
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
{layer_checkboxes_html}
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
      <span id="focus-pill-name" style="font-weight:600;color:var(--text-main);">-</span>
      <button id="btn-clear-focus" style="background:none;border:none;color:var(--text-main);cursor:pointer;">×</button>
    </div>
    <div class="floating-toolbar">
      <button id="zoomOutBtn" class="tool-btn">-</button>
      <span id="zoomLevelDisplay" class="tool-btn">100%</span>
      <button id="zoomInBtn" class="tool-btn">+</button>
      <button id="zoomResetBtn" class="tool-btn">1:1</button>
      <button id="fitViewBtn" class="tool-btn" title="Ajustar a la vista">Ajustar</button>
    </div>
  </div>

  <div class="minimap-container">
    <div class="minimap-header">Radar de Red</div>
    <div class="minimap-body"><canvas id="minimap-canvas" width="170" height="110"></canvas></div>
  </div>

  <aside class="inspector-drawer" id="inspector-drawer">
    <div class="inspector-header">
      <h2 id="insp-title" style="font-size:14px;color:var(--text-main);">Inspector</h2>
      <button id="btn-close-inspector" style="background:none;border:none;color:var(--text-main);cursor:pointer;">×</button>
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
        <div class="insp-card" id="insp-alias-card" style="display:none;">
          <div class="insp-card-title">Metadatos de Alias</div>
          <div class="insp-meta-row"><span>Scope:</span><span id="insp-scope" style="font-family:var(--font-mono);">-</span></div>
          <div class="insp-meta-row" style="flex-direction:column;gap:4px;"><span>Reason:</span><div id="insp-reason" style="font-family:var(--font-mono);color:var(--text-muted);">-</div></div>
        </div>
        <div class="insp-card">
          <button id="centerNodeBtn" class="btn-text-xs">Centrar nodo</button>
          <button id="copyNodeBtn" class="btn-text-xs">Copiar nodo</button>
        </div>
        <div class="insp-card">
          <div class="insp-card-title">Trazabilidad Cruzada</div>
          <div style="font-size:10px;color:var(--text-faint);margin-bottom:4px;">Entrantes</div>
          <div id="insp-trace-in"></div>
          <div style="font-size:10px;color:var(--text-faint);margin:8px 0 4px;">Salientes</div>
          <div id="insp-trace-out"></div>
        </div>
        <div class="insp-card">
          <div class="insp-card-title">Propiedades Técnicas</div>
          <div class="insp-tech-details" id="insp-tech-details"></div>
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
  const layers = rawData.layers || [];
  const LAYER_NAMES = layers.map(l => l.name);
  const layerColor = new Map(layers.map(l => [l.name, l.color]));
  const layerDomId = new Map(layers.map(l => [l.name, l.id]));
  const nodesByLayer = {{}};
  LAYER_NAMES.forEach(name => {{ nodesByLayer[name] = []; }});

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

  let activeLayers = new Set(LAYER_NAMES);
  let activeDomains = new Set(domains);
  let hopRadius = 2;
  let focalNodeId = null;

  let displayNodes = [];
  let displayEdges = [];

  const canvas = document.getElementById("network-canvas");
  const ctx = canvas.getContext("2d");
  const miniCanvas = document.getElementById("minimap-canvas");
  const miniCtx = miniCanvas ? miniCanvas.getContext("2d") : null;

  const ZOOM_MIN = 0.2;
  const ZOOM_MAX = 4.0;
  const FIT_MARGIN = 40;
  let transform = {{ x: 0, y: 0, k: 1.0 }};
  let isDragging = false;
  let dragStart = {{ x: 0, y: 0 }};
  let hoveredNode = null;

  layers.forEach(l => {{
    const m = document.getElementById("metric-" + l.id);
    if (m) m.textContent = ((nodesByLayer[l.name] || []).length || 0).toLocaleString();
  }});

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
    const specNodes = nodes.filter(n => n.kind === "spec");
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
        if (n && n.kind === "db" && (n.type === "table" || n.type === "view")) {{
          connectedTables.add(nid);
        }} else if (n && n.kind === "code") {{
          (outgoing.get(nid) || []).forEach(e2 => {{
            const n2 = nodeById.get(e2.target);
            if (n2 && n2.kind === "db" && (n2.type === "table" || n2.type === "view")) connectedTables.add(n2.id);
          }});
        }}
      }});

      const sn = nodeById.get(specId);
      const specDomain = (sn && sn.domain) ? sn.domain : selectedDomain;
      nodes.forEach(n => {{
        if (n.kind === "db" && (n.type === "table" || n.type === "view")) {{
          if (connectedTables.has(n.id) || (specDomain && n.domain === specDomain)) {{
            connectedTables.add(n.id);
          }}
        }}
      }});
      tables = Array.from(connectedTables).map(id => nodeById.get(id)).filter(Boolean);
    }} else if (selectedDomain) {{
      tables = nodes.filter(n => n.kind === "db" && (n.type === "table" || n.type === "view") && n.domain === selectedDomain);
    }} else {{
      tables = nodes.filter(n => n.kind === "db" && (n.type === "table" || n.type === "view"));
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
      if (n && (n.kind === "code" || n.kind === "ui" || (n.kind === "db" && n.type === "function"))) {{
        relatedEntities.set(n.id, n);
      }}
    }});
    (incoming.get(tableId) || []).forEach(e => {{
      const n = nodeById.get(e.source);
      if (n && (n.kind === "code" || n.kind === "ui" || (n.kind === "db" && n.type === "function"))) {{
        relatedEntities.set(n.id, n);
      }}
    }});

    tableCols.forEach(colId => {{
      (incoming.get(colId) || []).forEach(e => {{
        const n = nodeById.get(e.source);
        if (n && (n.kind === "code" || (n.kind === "db" && n.type === "function"))) {{
          relatedEntities.set(n.id, n);
        }}
      }});
      (outgoing.get(colId) || []).forEach(e => {{
        const n = nodeById.get(e.target);
        if (n && (n.kind === "code" || (n.kind === "db" && n.type === "function"))) {{
          relatedEntities.set(n.id, n);
        }}
      }});
    }});

    if (specId && nodeById.has(specId)) {{
      (outgoing.get(specId) || []).forEach(e => {{
        const n = nodeById.get(e.target);
        if (n && n.kind === "code" && (n.type === "CLASS" || n.type === "FILE")) {{
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
      if (ent.kind === "code") {{
        badge = ent.type === "CLASS" ? "Clase" : (ent.type === "FUNC" ? "Método" : "Archivo");
      }} else if (ent.kind === "ui") {{
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

    if (focalNode.kind === "db" && (focalNode.type === "table" || focalNode.type === "view")) {{
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
        activeLayers = new Set(LAYER_NAMES);
        layers.forEach(l => {{
          const cb = document.getElementById("layer-cb-" + l.id);
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
      const specNodes = nodes.filter(n => n.kind === "spec" && activeDomains.has(n.domain));
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

  function getNodeColor(n) {{
    const light = isLightTheme();
    if (n.type === "alias_old") return light ? "#d9383a" : "#f85149";
    if (n.type === "alias_new") return light ? "#1a7f37" : "#3fb950";
    const st = n.state || (n.metadata && n.metadata.state);
    if (st === "renamed") return light ? "#bf8700" : "#d29922";
    if (st === "deleted") return light ? "#d9383a" : "#f85149";
    return layerColor.get(n.layer) || "#94a3b8";
  }}

  function render() {{
    const w = canvas.getBoundingClientRect().width;
    const h = canvas.getBoundingClientRect().height;
    ctx.clearRect(0, 0, w, h);
    const light = isLightTheme();

    ctx.save();
    ctx.translate(transform.x, transform.y);
    ctx.scale(transform.k, transform.k);

    displayEdges.forEach(e => {{
      const s = displayNodes.find(n => n.id === e.source);
      const t = displayNodes.find(n => n.id === e.target);
      if (!s || !t) return;
      const isRenamedTo = (e.relation === "RENAMED_TO" || e.type === "RENAMED_TO");
      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(t.x, t.y);
      if (isRenamedTo) {{
        ctx.strokeStyle = light ? "#0b5cad" : "#6cb0f5";
        ctx.lineWidth = 1.6 / transform.k;
      }} else {{
        ctx.strokeStyle = e.cross_layer ? "rgba(56, 189, 248, 0.4)" : (light ? "rgba(27, 31, 36, 0.15)" : "rgba(255, 255, 255, 0.12)");
        ctx.lineWidth = 1.0 / transform.k;
      }}
      ctx.stroke();

      if (isRenamedTo) {{
        const angle = Math.atan2(t.y - s.y, t.x - s.x);
        const nodeRadius = (t.id === focalNodeId) ? 14 : 8;
        const arrowDist = nodeRadius + 2;
        const tipX = t.x - arrowDist * Math.cos(angle);
        const tipY = t.y - arrowDist * Math.sin(angle);
        const arrowLen = 8 / Math.max(0.5, transform.k);
        const arrowWidth = 4 / Math.max(0.5, transform.k);

        ctx.fillStyle = light ? "#0b5cad" : "#6cb0f5";
        ctx.beginPath();
        ctx.moveTo(tipX, tipY);
        ctx.lineTo(
          tipX - arrowLen * Math.cos(angle) + arrowWidth * Math.sin(angle),
          tipY - arrowLen * Math.sin(angle) - arrowWidth * Math.cos(angle)
        );
        ctx.lineTo(
          tipX - arrowLen * Math.cos(angle) - arrowWidth * Math.sin(angle),
          tipY - arrowLen * Math.sin(angle) + arrowWidth * Math.cos(angle)
        );
        ctx.closePath();
        ctx.fill();

        const midX = (s.x + t.x) / 2;
        const midY = (s.y + t.y) / 2;
        ctx.save();
        ctx.font = "9px " + (light ? 'ui-monospace, monospace' : '"JetBrains Mono", monospace');
        const textW = ctx.measureText("RENAMED_TO").width;
        const padX = 5;
        const padY = 3;
        ctx.fillStyle = light ? "#ffffff" : "#131e2a";
        ctx.strokeStyle = light ? "#d0d7de" : "#273e57";
        ctx.lineWidth = 1.0 / transform.k;
        ctx.beginPath();
        ctx.rect(midX - textW / 2 - padX, midY - 6 - padY, textW + 2 * padX, 12 + 2 * padY);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = light ? "#0b5cad" : "#6cb0f5";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText("RENAMED_TO", midX, midY);
        ctx.restore();
      }}
    }});

    displayNodes.forEach(n => {{
      const isFocal = (n.id === focalNodeId);
      const radius = isFocal ? 14 : 8;
      const col = getNodeColor(n);

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
        ctx.fillStyle = light ? (isFocal ? "#0b5cad" : "#1b1f24") : (isFocal ? "#70f3ff" : "#cbd5e1");
        ctx.textAlign = "center";
        ctx.fillText(n.label, n.x, n.y + radius + 12);
      }}
    }});

    ctx.restore();
    renderMinimap();
    updateZoomDisplay();
  }}

  function updateZoomDisplay() {{
    const zd = document.getElementById("zoomLevelDisplay");
    if (zd) zd.textContent = Math.round(transform.k * 100) + "%";
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

    if (n.kind === "spec") {{
      if (moduleSelect && moduleSelect.value !== (n.domain || "")) {{
        moduleSelect.value = n.domain || "";
        populateSpecDropdown(n.domain || "");
      }}
      if (specSelect) specSelect.value = n.id;
      document.getElementById("badge-starter-status").textContent = `Spec: ${{n.label}}`;
      populateTableDropdown(n.id, n.domain);
    }} else if (n.kind === "db" && (n.type === "table" || n.type === "view")) {{
      if (tableSelect) tableSelect.value = n.id;
      document.getElementById("badge-starter-status").textContent = `Tabla: ${{n.label}}`;
      populateEntityDropdown(n.id, specSelect ? specSelect.value : "");
    }} else if (n.kind === "code" || n.kind === "ui" || n.type === "function") {{
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
      const inName = document.createElement("span");
      inName.textContent = s ? s.label : e.source;
      const inRel = document.createElement("span");
      inRel.setAttribute("style", "color:var(--text-muted);");
      inRel.textContent = e.relation;
      row.appendChild(inName);
      row.appendChild(inRel);
      row.onclick = () => setFocalNode(e.source, true);
      inList.appendChild(row);
    }});

    const outList = document.getElementById("insp-trace-out");
    outList.innerHTML = "";
    outEdges.slice(0, 10).forEach(e => {{
      const t = nodeById.get(e.target);
      const row = document.createElement("div");
      row.className = "trace-item";
      const outName = document.createElement("span");
      outName.textContent = t ? t.label : e.target;
      const outRel = document.createElement("span");
      outRel.setAttribute("style", "color:var(--text-muted);");
      outRel.textContent = e.relation;
      row.appendChild(outName);
      row.appendChild(outRel);
      row.onclick = () => setFocalNode(e.target, true);
      outList.appendChild(row);
    }});

    const details = document.getElementById("insp-tech-details");
    details.textContent = "";
    if (n.metadata) Object.entries(n.metadata).forEach(([k, v]) => {{
      if (v === null || v === undefined || v === "") return;
      const r = document.createElement("div");
      r.className = "tech-row";
      const tk = document.createElement("span");
      tk.className = "tech-k";
      tk.textContent = k;
      const tv = document.createElement("span");
      tv.className = "tech-v";
      tv.textContent = typeof v === "object" ? JSON.stringify(v) : String(v);
      r.appendChild(tk);
      r.appendChild(tv);
      details.appendChild(r);
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
    activeLayers = new Set(LAYER_NAMES);
    layers.forEach(l => {{ const cb = document.getElementById("layer-cb-" + l.id); if (cb) cb.checked = true; }});
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
  renderAliasView();
  }};

  layers.forEach(l => {{
    const cb = document.getElementById("layer-cb-" + l.id);
    if (!cb) return;
    cb.addEventListener("change", () => {{
      if (cb.checked) activeLayers.add(l.name);
      else activeLayers.delete(l.name);
      recalculateSubgraph(false);
    }});
  }});

  document.getElementById("btn-clear-focus").onclick = () => {{
    focalNodeId = null;
    recalculateSubgraph(true);
  }};

  document.getElementById("zoomInBtn").onclick = () => {{ transform.k = Math.min(transform.k * 1.25, ZOOM_MAX); render(); }};
  document.getElementById("zoomOutBtn").onclick = () => {{ transform.k = Math.max(transform.k * 0.8, ZOOM_MIN); render(); }};
  document.getElementById("zoomResetBtn").onclick = () => {{ transform = {{ x: 0, y: 0, k: 1.0 }}; render(); }};
  document.getElementById("fitViewBtn").onclick = () => fitView();

  function fitView() {{
    if (displayNodes.length === 0) return;
    const w = canvas.getBoundingClientRect().width;
    const h = canvas.getBoundingClientRect().height;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    displayNodes.forEach(n => {{
      if (n.x < minX) minX = n.x;
      if (n.x > maxX) maxX = n.x;
      if (n.y < minY) minY = n.y;
      if (n.y > maxY) maxY = n.y;
    }});
    let k = Math.min((w - 2 * FIT_MARGIN) / Math.max(1, maxX - minX), (h - 2 * FIT_MARGIN) / Math.max(1, maxY - minY));
    k = Math.max(ZOOM_MIN, Math.min(k, ZOOM_MAX));
    transform = {{ x: w / 2 - ((minX + maxX) / 2) * k, y: h / 2 - ((minY + maxY) / 2) * k, k: k }};
    render();
  }}

  function getTransform() {{ return {{ x: transform.x, y: transform.y, k: transform.k }}; }}
  function getFocalId() {{ return focalNodeId; }}
  function selectNode(id) {{ setFocalNode(id, false); }}
  window.aiddExplorer = {{ getTransform, getFocalId, selectNode }};

  const THEME_KEY = "aidd-explorer-theme";
  function isLightTheme() {{ return document.documentElement.classList.contains("light"); }}
  function saveThemeChoice(theme) {{
    try {{ window.localStorage.setItem(THEME_KEY, theme); }} catch (err) {{ /* storage blocked: not remembered */ }}
  }}
  function loadThemeChoice() {{
    let choice = null;
    try {{ choice = window.localStorage.getItem(THEME_KEY); }} catch (err) {{ choice = null; }}
    if (choice === "light") document.documentElement.classList.add("light");
  }}
  function toggleTheme() {{
    document.documentElement.classList.toggle("light");
    saveThemeChoice(isLightTheme() ? "light" : "dark");
    render();
  }}
  document.getElementById("themeToggleBtn").onclick = () => toggleTheme();

  function centerOnFocal() {{
    if (!focalNodeId) return;
    const f = displayNodes.find(n => n.id === focalNodeId);
    if (!f) return;
    const w = canvas.getBoundingClientRect().width;
    const h = canvas.getBoundingClientRect().height;
    transform.x = w / 2 - f.x * transform.k;
    transform.y = h / 2 - f.y * transform.k;
    render();
  }}
  document.getElementById("centerNodeBtn").onclick = () => centerOnFocal();

  function copyFocalNode() {{
    if (!focalNodeId) return;
    const n = nodeById.get(focalNodeId);
    if (!n) return;
    const text = JSON.stringify({{ id: n.id, label: n.label, layer: n.layer, kind: n.kind, type: n.type, domain: n.domain, metadata: n.metadata }});
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      navigator.clipboard.writeText(text).catch(() => {{}});
    }} else {{
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try {{ document.execCommand("copy"); }} catch (err) {{ /* copy unavailable */ }}
      document.body.removeChild(ta);
    }}
    const btn = document.getElementById("copyNodeBtn");
    btn.textContent = "Copiado";
    setTimeout(() => {{ btn.textContent = "Copiar nodo"; }}, 1500);
  }}
  document.getElementById("copyNodeBtn").onclick = () => copyFocalNode();

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

  function renderAliasView() {{
    const hasAlias = layers.some(l => l.kind === "aliases" || l.name === "aliases");
    const legend = document.getElementById("legend-aliases");
    const banner = document.getElementById("aliases-empty-banner");
    if (!hasAlias) {{
      if (legend) legend.style.display = "none";
      if (banner) banner.style.display = "none";
      return;
    }}
    if (legend) legend.style.display = "flex";
    const aliasLayer = layers.find(l => l.kind === "aliases" || l.name === "aliases");
    const aliasNodes = nodes.filter(n => n.layer === (aliasLayer ? aliasLayer.name : "aliases") || n.kind === "aliases");
    const isEmpty = (aliasNodes.length === 0) || Boolean(aliasLayer && aliasLayer.missing);
    if (banner) banner.style.display = isEmpty ? "block" : "none";
  }}

  loadThemeChoice();
  resizeCanvas();
  initAllSpecsView();
}})();
</script>
</body>
</html>"""


def _size_report(payload, nbytes):
    """One line per layer (`name: N nodes`) plus the total edges, for the size-guard message (aidd:FR-076)."""
    lines = ["%s: %d nodes" % (l.get("name", "?"), l.get("count", 0)) for l in payload.get("layers") or []]
    lines.append("edges: %d (html %d bytes)" % (len(payload.get("edges") or []), nbytes))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--graph", default=None, help="Ruta al archivo graph.json específico")
    ap.add_argument("--out", default=None, help="Ruta del archivo HTML de salida")
    ap.add_argument("--title", default=DEFAULT_TITLE, help="Título del explorador")
    ap.add_argument("--root", default=None, help="Directorio raíz del proyecto AIDD")
    ap.add_argument("--kind", default="graph", help="Tipo del grafo de --graph (db, code, spec, ui, ...)")
    ap.add_argument("--layer", default="graph", help="Nombre de la capa de --graph")
    ap.add_argument("--max-mb", type=float, default=DEFAULT_MAX_MB,
                    help="Tope del HTML en MB (default %(default)s); por encima no se escribe nada (exit 3)")
    ap.add_argument("--skip", default="", help="Grafos a omitir en modo --root, separados por coma")
    a = ap.parse_args(argv)
    skip = [s.strip() for s in (a.skip or "").split(",") if s.strip()]

    if a.graph:
        gp = Path(a.graph)
        try:
            if gp.suffix.lower() == ".toon":
                raw = unified_graph.read_graph_file(gp, a.kind)
            else:
                raw = json.loads(gp.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    raise ValueError("graph JSON must be an object")
            raw_data = unified_graph.single_layer(raw, a.layer, a.kind)
        except (OSError, ValueError) as ex:
            print(f"graph_explorer: cannot read {gp}: {ex}", file=sys.stderr)
            return 2
        out = Path(a.out) if a.out else gp.with_suffix(".html")
        html_page = build_html(raw_data, a.title)
    else:
        root = Path(a.root) if a.root else Path.cwd()
        raw_data = unified_graph.load_unified(root, skip=skip)
        for w in raw_data.get("warnings", []):
            print(f"graph_explorer: {w}", file=sys.stderr)
        out = Path(a.out) if a.out else (root / DEFAULT_UNIFIED_OUT)
        html_page = build_html(raw_data, a.title)

    nbytes = len(html_page.encode("utf-8"))
    if nbytes > a.max_mb * 1_000_000:
        print(f"explorer: {nbytes} bytes > ceiling {a.max_mb:g} MB; nothing written", file=sys.stderr)
        print(_size_report(raw_data, nbytes), file=sys.stderr)
        return 3
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_page, encoding="utf-8")
    print(f"explorer: {len(raw_data.get('nodes', []))} nodes -> {out} ({len(html_page):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
