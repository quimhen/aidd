#!/usr/bin/env python3
"""docs/db-graph/gen_unified_explorer.py
Generador del Explorador Global Unificado de Grafos de b1SyncLink (SCREEN-95).
Cumple con la arquitectura de diseño Executive Precision, 100% autónomo y offline
(cero dependencias de red / CDN externas).
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from unified_graph_model import UnifiedGraphModel

F28_TABLES = ["OSYQ", "OSUC", "OGES", "OVTR", "OASI", "OPRM"]

def embed_json(obj):
    """Genera JSON seguro dentro de un bloque <script> HTML."""
    s = json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def read_component(name: str) -> str:
    p = HERE / "components" / name
    if p.exists():
        return p.read_text(encoding="utf-8")
    return f"<!-- Component {name} missing -->"


def generate_html(graph_data: dict) -> str:
    """Construye el documento HTML autónomo incorporando los componentes y estilos."""
    omnibox_html = read_component("graph_omnibox.html")
    sidebar_html = read_component("graph_sidebar.html")
    canvas_html = read_component("graph_canvas.html")
    minimap_html = read_component("graph_minimap.html")
    inspector_html = read_component("graph_inspector.html")

    # Extraer dominios únicos
    all_domains = sorted(list({n.get("domain", "Core") for n in graph_data.get("nodes", []) if n.get("domain")}))

    data_payload = {
        "summary": graph_data.get("summary", {}),
        "domains": all_domains,
        "f28": F28_TABLES,
        "nodes": graph_data.get("nodes", []),
        "edges": graph_data.get("edges", []),
    }
    embedded_data = embed_json(data_payload)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>b1SyncLink :: Unified Knowledge Graph Explorer (SCREEN-95)</title>
<style>
/* ==========================================================================
   EXECUTIVE PRECISION DESIGN SYSTEM TOKENS & STYLES (100% OFFLINE)
   ========================================================================== */
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
  
  /* Capas de color semántico */
  --layer-db: #00bcd4;       /* Cian brillante */
  --layer-db-dark: #00677c;  /* Teal corporativo */
  --layer-code: #10b981;     /* Esmeralda */
  --layer-spec: #a855f7;     /* Violeta */
  --layer-ui: #f59e0b;       /* Ámbar */
  --layer-cross: #38bdf8;    /* Azul trazabilidad */
  --impact-cascade: #ef4444; /* Rojo alerta */

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

/* Topbar */
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
.brand {{
  display: flex;
  align-items: center;
  gap: 10px;
}}
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
.brand-text {{ display: flex; flex-direction: column; }}
.brand-title {{ font-weight: 700; font-size: 13px; letter-spacing: 0.02em; color: #fff; }}
.brand-sub {{ font-size: 10px; color: var(--text-muted); font-family: var(--font-mono); }}

/* Omnibox */
.search-container {{
  flex: 1;
  max-width: 580px;
  position: relative;
}}
.search-input-wrapper {{
  display: flex;
  align-items: center;
  background-color: var(--bg-input);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 0 10px;
  gap: 8px;
  height: 34px;
  transition: all 0.15s ease;
}}
.search-input-wrapper:focus-within {{
  border-color: var(--layer-db);
  box-shadow: 0 0 0 2px rgba(0, 188, 212, 0.2);
}}
.search-icon {{ color: var(--text-muted); }}
#omnibox-input {{
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-main);
  font-size: 13px;
}}
#omnibox-input::placeholder {{ color: var(--text-faint); }}
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
.search-res-item:hover, .search-res-item.active {{
  background-color: var(--bg-card-hover);
}}
.search-res-label {{
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
}}
.search-res-sub {{
  font-size: 11px;
  color: var(--text-muted);
  max-width: 250px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}}

/* Topbar Actions */
.topbar-actions {{
  display: flex;
  align-items: center;
  gap: 12px;
}}
.metrics-pills {{
  display: flex;
  gap: 6px;
}}
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
.metric-val {{ font-weight: 600; color: #fff; }}

.topbar-divider {{ width: 1px; height: 22px; background-color: var(--border-subtle); }}

.action-select {{
  background-color: var(--bg-input);
  color: var(--text-main);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 12px;
  outline: none;
}}
.topbar-btn-group {{ display: flex; gap: 6px; }}
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
  transition: all 0.15s;
}}
.btn-icon:hover {{
  background-color: var(--bg-card-hover);
  border-color: var(--border-strong);
}}

/* App Body Layout */
.app-container {{
  flex: 1;
  display: flex;
  position: relative;
  overflow: hidden;
}}

/* Left Sidebar */
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
.sidebar-title {{
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 12px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}}
.sidebar-scrollable {{
  flex: 1;
  overflow-y: auto;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}}

/* Punto de Inicio Starter Box */
.filter-section-starter {{
  background: linear-gradient(180deg, rgba(0, 103, 124, 0.18) 0%, rgba(14, 23, 32, 0.6) 100%);
  border: 1px solid var(--layer-db-dark);
  border-radius: 6px;
  padding: 10px;
}}
.starter-heading {{
  color: #70f3ff;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 4px;
}}
.select-group {{
  display: flex;
  flex-direction: column;
  gap: 4px;
}}
.select-label {{
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  font-weight: 600;
}}
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
  transition: border-color 0.15s;
}}
.action-select-block:focus {{
  border-color: var(--layer-db);
}}

.filter-section-title {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin-bottom: 8px;
}}
.badge-count {{
  font-family: var(--font-mono);
  font-size: 10px;
  background-color: var(--bg-card);
  padding: 1px 5px;
  border-radius: 3px;
  color: var(--text-main);
}}
.btn-text-xs {{
  background: none;
  border: none;
  color: var(--layer-db);
  font-size: 11px;
  cursor: pointer;
}}
.btn-text-xs:hover {{ text-decoration: underline; }}

.layer-checkbox-group {{ display: flex; flex-direction: column; gap: 6px; }}
.layer-cb-item {{
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 4px;
  background-color: var(--bg-card);
  border: 1px solid transparent;
  cursor: pointer;
  user-select: none;
  font-size: 12px;
}}
.layer-cb-item:hover {{ border-color: var(--border-strong); }}
.layer-cb-item input {{ display: none; }}
.custom-cb {{
  width: 14px;
  height: 14px;
  border-radius: 3px;
  border: 1px solid var(--border-strong);
  display: flex;
  align-items: center;
  justify-content: center;
}}
.layer-cb-item input:checked + .custom-cb::after {{
  content: "";
  width: 8px;
  height: 8px;
  border-radius: 2px;
}}
.cb-indicator-db::after {{ background-color: var(--layer-db); }}
.cb-indicator-code::after {{ background-color: var(--layer-code); }}
.cb-indicator-spec::after {{ background-color: var(--layer-spec); }}
.cb-indicator-ui::after {{ background-color: var(--layer-ui); }}
.layer-name {{ flex: 1; }}
.layer-badge {{
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-muted);
}}

/* Hop Slider */
.hop-slider-container {{
  background-color: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 10px;
}}
.hop-slider-marks {{
  display: flex;
  justify-content: space-between;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-muted);
  margin-bottom: 4px;
}}
#hop-radius-slider {{
  width: 100%;
  accent-color: var(--layer-db);
  cursor: pointer;
}}
.slider-hint {{
  font-size: 10px;
  color: var(--text-faint);
  margin-top: 6px;
}}

/* Toggle Switch */
.toggle-control-row {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 8px 10px;
  cursor: pointer;
}}
.toggle-label-wrapper {{ display: flex; flex-direction: column; }}
.toggle-main-label {{ font-size: 12px; font-weight: 500; }}
.toggle-sub-label {{ font-size: 10px; color: var(--text-muted); }}
.switch {{
  position: relative;
  display: inline-block;
  width: 32px;
  height: 18px;
}}
.switch input {{ opacity: 0; width: 0; height: 0; }}
.slider.round {{
  position: absolute;
  cursor: pointer;
  top: 0; left: 0; right: 0; bottom: 0;
  background-color: var(--bg-input);
  border: 1px solid var(--border-strong);
  transition: .2s;
  border-radius: 18px;
}}
.slider.round:before {{
  position: absolute;
  content: "";
  height: 12px;
  width: 12px;
  left: 2px;
  bottom: 2px;
  background-color: var(--text-muted);
  transition: .2s;
  border-radius: 50%;
}}
input:checked + .slider.round {{
  background-color: var(--impact-cascade);
  border-color: var(--impact-cascade);
}}
input:checked + .slider.round:before {{
  transform: translateX(14px);
  background-color: #fff;
}}

/* Domain chips */
.domain-chips-container {{
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}}
.domain-chip {{
  font-size: 11px;
  background-color: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  padding: 3px 8px;
  cursor: pointer;
  user-select: none;
  transition: all 0.1s;
}}
.domain-chip.active {{
  background-color: #1a3248;
  border-color: var(--layer-db);
  color: #fff;
}}

/* Quick Hubs */
.quick-hubs-list {{
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}}
.hub-tag {{
  font-family: var(--font-mono);
  font-size: 11px;
  background-color: #102636;
  border: 1px solid var(--layer-db-dark);
  color: #70f3ff;
  border-radius: 4px;
  padding: 2px 7px;
  cursor: pointer;
}}
.hub-tag:hover {{
  background-color: #00677c;
  color: #fff;
}}

/* Center Canvas Viewport */
.canvas-viewport {{
  flex: 1;
  position: relative;
  overflow: hidden;
  background: radial-gradient(circle at center, #0f1c29 0%, #080d12 100%);
}}
#network-canvas {{
  width: 100%;
  height: 100%;
  display: block;
}}
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
  box-shadow: 0 4px 12px rgba(0,0,0,0.4);
}}
.focus-dot {{
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: var(--layer-db);
  box-shadow: 0 0 8px var(--layer-db);
}}
.focus-label {{ font-weight: 600; color: #fff; }}
.btn-clear-pill {{
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 16px;
  cursor: pointer;
  line-height: 1;
}}
.btn-clear-pill:hover {{ color: #fff; }}

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
.toolbar-sep {{ width: 1px; background-color: var(--border-subtle); margin: 3px 2px; }}

.canvas-tooltip {{
  position: absolute;
  background-color: rgba(14, 23, 32, 0.95);
  border: 1px solid var(--border-strong);
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 11px;
  pointer-events: none;
  z-index: 30;
  box-shadow: 0 8px 20px rgba(0,0,0,0.5);
  max-width: 280px;
}}

/* Minimap */
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
  box-shadow: 0 4px 16px rgba(0,0,0,0.4);
}}
.minimap-header {{
  padding: 4px 8px;
  background-color: var(--bg-card);
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 10px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}}
.minimap-body {{ position: relative; width: 100%; height: 110px; }}
#minimap-canvas {{ width: 100%; height: 100%; display: block; }}
.minimap-viewport-rect {{
  position: absolute;
  border: 1px solid var(--layer-db);
  background-color: rgba(0, 188, 212, 0.1);
  pointer-events: none;
}}

/* Right Node Inspector Drawer */
.inspector-drawer {{
  width: 360px;
  min-width: 360px;
  background-color: var(--bg-surface);
  border-left: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  z-index: 10;
}}
.inspector-header {{
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  justify-content: space-between;
}}
.inspector-headline {{ display: flex; align-items: center; gap: 8px; }}
.inspector-layer-pill {{
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 3px;
  background-color: var(--layer-db);
  color: #000;
}}
.inspector-title {{ font-size: 14px; font-weight: 600; color: #fff; }}
.btn-icon-xs {{
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
}}
.btn-icon-xs:hover {{ color: #fff; }}

.inspector-content {{ flex: 1; overflow-y: auto; padding: 16px; }}
.inspector-empty-state {{
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: var(--text-faint);
  gap: 12px;
  padding: 20px;
}}
.insp-card {{
  background-color: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 12px;
}}
.insp-card-title {{
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}}
.insp-meta-row {{
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 12px;
}}
.insp-meta-key {{ color: var(--text-muted); }}
.insp-meta-code {{ font-family: var(--font-mono); font-size: 11px; color: var(--layer-db); }}
.insp-meta-val {{ font-weight: 500; }}
.insp-purpose-text {{ font-size: 12px; line-height: 1.5; color: #cbd5e1; }}

.trace-group-title {{
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-faint);
  margin: 8px 0 4px;
}}
.trace-list {{ display: flex; flex-direction: column; gap: 4px; }}
.trace-item {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 5px 8px;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
}}
.trace-item:hover {{
  border-color: var(--layer-db);
  background-color: var(--bg-card-hover);
}}
.trace-item-label {{ font-family: var(--font-mono); }}
.trace-item-rel {{ color: var(--text-muted); font-size: 10px; }}

.insp-tech-details {{ font-size: 11px; font-family: var(--font-mono); }}
.tech-row {{ display: flex; justify-content: space-between; padding: 2px 0; border-bottom: 1px solid rgba(255,255,255,0.03); }}
.tech-k {{ color: var(--text-muted); }}
.tech-v {{ color: #e2e8f0; }}

/* Scrollbars */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: var(--bg-dark); }}
::-webkit-scrollbar-thumb {{ background: var(--border-strong); border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: var(--text-faint); }}
</style>
</head>
<body>

{omnibox_html}

<div class="app-container">
  {sidebar_html}
  {canvas_html}
  {minimap_html}
  {inspector_html}
</div>

<script id="graph-data" type="application/json">{embedded_data}</script>

<script>
/* ==========================================================================
   UNIFIED GRAPH ENGINE & CONTROLLER (100% OFFLINE)
   ========================================================================== */
(function() {{
  "use strict";

  const rawData = JSON.parse(document.getElementById("graph-data").textContent);
  const nodes = rawData.nodes || [];
  const edges = rawData.edges || [];
  const domains = rawData.domains || [];
  const f28Hubs = rawData.f28 || [];

  // Indices
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

  // State
  let activeLayers = new Set(["db", "code", "spec", "ui"]);
  let activeDomains = new Set(domains);
  let hopRadius = 2;
  let impactMode = false;
  let focalNodeId = null;
  let currentLayout = "concentric";

  // Visual Nodes & Edges in Canvas
  let displayNodes = [];
  let displayEdges = [];

  // Canvas context
  const canvas = document.getElementById("network-canvas");
  const ctx = canvas.getContext("2d");
  const miniCanvas = document.getElementById("minimap-canvas");
  const miniCtx = miniCanvas ? miniCanvas.getContext("2d") : null;

  // Viewport Transform
  let transform = {{ x: 0, y: 0, k: 1.0 }};
  let isDragging = false;
  let dragStart = {{ x: 0, y: 0 }};
  let hoveredNode = null;

  // Initialize Layer Metrics
  document.getElementById("metric-db").textContent = (nodesByLayer.db.length || 0).toLocaleString();
  document.getElementById("metric-code").textContent = (nodesByLayer.code.length || 0).toLocaleString();
  document.getElementById("metric-spec").textContent = (nodesByLayer.spec.length || 0).toLocaleString();
  document.getElementById("metric-ui").textContent = (nodesByLayer.ui.length || 0).toLocaleString();

  document.getElementById("badge-db-count").textContent = (nodesByLayer.db.length || 0).toLocaleString();
  document.getElementById("badge-code-count").textContent = (nodesByLayer.code.length || 0).toLocaleString();
  document.getElementById("badge-spec-count").textContent = (nodesByLayer.spec.length || 0).toLocaleString();
  document.getElementById("badge-ui-count").textContent = (nodesByLayer.ui.length || 0).toLocaleString();

  // 5-Level Cascading Drill-Down: Módulo -> Spec -> Tabla -> Objeto/Clase -> Demás objetos/Aristas
  const moduleSelect = document.getElementById("select-module");
  const specSelect = document.getElementById("select-spec");
  const tableSelect = document.getElementById("select-table");
  const entitySelect = document.getElementById("select-entity");
  const objectSelect = document.getElementById("select-object");

  function populateModuleDropdown() {{
    if (!moduleSelect) return;
    const countByDomain = new Map();
    nodes.forEach(n => {{
      const d = n.domain || "Core";
      countByDomain.set(d, (countByDomain.get(d) || 0) + 1);
    }});
    moduleSelect.innerHTML = '<option value="">— Todos los Módulos —</option>';
    domains.forEach(d => {{
      const opt = document.createElement("option");
      opt.value = d;
      const cnt = countByDomain.get(d) || 0;
      opt.textContent = `${{d}} (${{cnt.toLocaleString()}} nodos)`;
      moduleSelect.appendChild(opt);
    }});
  }}

  function populateSpecDropdown(selectedDomain) {{
    if (!specSelect) return;
    specSelect.innerHTML = '<option value="">— Todas las Specs —</option>';
    const specNodes = nodes.filter(n => n.layer === "spec");
    
    // Filtrar estrictamente por dominio si se seleccionó un módulo
    const filtered = selectedDomain ? specNodes.filter(n => n.domain === selectedDomain) : specNodes;
    filtered.sort((a, b) => a.label.localeCompare(b.label));

    filtered.forEach(sn => {{
      const opt = document.createElement("option");
      opt.value = sn.id;
      const title = sn.purpose ? (sn.purpose.length > 40 ? sn.purpose.substring(0, 40) + "…" : sn.purpose) : sn.raw_id;
      opt.textContent = `[${{sn.domain}}] ${{sn.label}} — ${{title}}`;
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

  // Inicializar selectores
  populateModuleDropdown();
  populateSpecDropdown("");

  // Nivel 1: Cambio de Módulo
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
        document.querySelectorAll(".domain-chip").forEach(chip => {{
          if (chip.textContent === mod) chip.classList.add("active");
          else chip.classList.remove("active");
        }});
        document.getElementById("badge-starter-status").textContent = `Módulo: ${{mod}}`;
      }} else {{
        activeDomains = new Set(domains);
        document.querySelectorAll(".domain-chip").forEach(chip => chip.classList.add("active"));
        document.getElementById("badge-starter-status").textContent = "Todas las Specs";
      }}
      recalculateSubgraph(false);
    }});
  }}

  // Nivel 2: Cambio de Spec
  if (specSelect) {{
    specSelect.addEventListener("change", () => {{
      const specId = specSelect.value;
      if (specId) {{
        activeLayers = new Set(["db", "code", "spec", "ui"]);
        ["db", "code", "spec", "ui"].forEach(layer => {{
          const cb = document.getElementById(`layer-cb-${{layer}}`);
          if (cb) cb.checked = true;
        }});
        document.getElementById("count-active-layers").textContent = "4/4";

        const sn = nodeById.get(specId);
        if (sn) {{
          if (moduleSelect && !moduleSelect.value) {{
            moduleSelect.value = sn.domain || "";
          }}
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

  // Nivel 3: Cambio de Tabla
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

  // Nivel 4: Cambio de Objeto (Entidad o Clase)
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

  // Nivel 5: Demás objetos o Aristas (aislar la última arista / nodo hoja con radio 1)
  if (objectSelect) {{
    objectSelect.addEventListener("change", () => {{
      const objId = objectSelect.value;
      if (objId) {{
        const targetNode = nodeById.get(objId);
        if (targetNode) {{
          hopRadius = 1;
          const hopSlider = document.getElementById("hop-radius-slider");
          if (hopSlider) hopSlider.value = 1;
          document.getElementById("lbl-hop-value").textContent = "1 salto";

          document.getElementById("badge-starter-status").textContent = `${{targetNode.label}} (${{targetNode.layer}})`;
          setFocalNode(objId, true);
        }}
      }}
    }});
  }}

  // Populate Domain Chips
  const domainContainer = document.getElementById("domain-chips-list");
  if (domainContainer) {{
    domains.forEach(d => {{
      const chip = document.createElement("div");
      chip.className = "domain-chip active";
      chip.textContent = d;
      chip.onclick = () => {{
        if (activeDomains.has(d)) {{
          activeDomains.delete(d);
          chip.classList.remove("active");
        }} else {{
          activeDomains.add(d);
          chip.classList.add("active");
        }}
        recalculateSubgraph();
      }};
      domainContainer.appendChild(chip);
    }});
  }}

  // Populate Quick Hubs
  const quickHubsContainer = document.getElementById("quick-hubs-container");
  if (quickHubsContainer) {{
    f28Hubs.forEach(hubName => {{
      const tag = document.createElement("div");
      tag.className = "hub-tag";
      tag.textContent = hubName;
      tag.onclick = () => {{
        // Find matching node
        const found = nodes.find(n => n.label.toUpperCase() === hubName || n.raw_id === hubName || n.id.includes(hubName));
        if (found) setFocalNode(found.id);
      }};
      quickHubsContainer.appendChild(tag);
    }});
  }}

  // Resize canvas
  function resizeCanvas() {{
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    render();
  }}
  window.addEventListener("resize", resizeCanvas);

  // BFS Neighborhood Calculator
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
      // Priorizar nodo focal (profundidad 0), salto 1 (profundidad 1) y luego los mas conectados de salto 2
      finalNodes.sort((a, b) => (a.depth || 0) - (b.depth || 0));
      finalNodes = finalNodes.slice(0, 200);
    }}
    const finalSet = new Set(finalNodes.map(n => n.id));
    const subEdges = edges.filter(e => finalSet.has(e.source) && finalSet.has(e.target));
    return {{ nodes: finalNodes, edges: subEdges }};
  }}

  // Subgraph Layout Positioning
  function layoutNodes(layoutType) {{
    const w = canvas.getBoundingClientRect().width;
    const h = canvas.getBoundingClientRect().height;
    const cx = w / 2;
    const cy = h / 2;

    if (!focalNodeId || displayNodes.length === 0) {{
      // Distribución en constelación multi-anillo balanceada para todas las specs
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

    // Concentric rings around focal node
    const focal = displayNodes.find(n => n.id === focalNodeId);
    if (focal) {{
      focal.x = cx;
      focal.y = cy;
    }}

    // Group by depth
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

  // Recalculate Subgraph (mantiene la escala del usuario si maintainScale es true)
  function recalculateSubgraph(maintainScale = false) {{
    if (!focalNodeId) {{
      // Vista panorámica de Specs (constelación de especificaciones AIDD)
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

    layoutNodes(currentLayout);

    const w = canvas.getBoundingClientRect().width;
    const h = canvas.getBoundingClientRect().height;
    if (!maintainScale) {{
      transform.k = 1.0;
      transform.x = 0;
      transform.y = 0;
    }} else {{
      // Centrar suavemente sobre el nodo focal manteniendo exactamente el nivel de zoom
      transform.x = (w / 2) * (1 - transform.k);
      transform.y = (h / 2) * (1 - transform.k);
    }}
    render();
  }}

  // Color mapper
  function getNodeColor(layer) {{
    switch (layer) {{
      case "db": return "#00bcd4";
      case "code": return "#10b981";
      case "spec": return "#a855f7";
      case "ui": return "#f59e0b";
      default: return "#94a3b8";
    }}
  }}

  // Main Render Loop
  function render() {{
    const w = canvas.getBoundingClientRect().width;
    const h = canvas.getBoundingClientRect().height;
    ctx.clearRect(0, 0, w, h);

    ctx.save();
    ctx.translate(transform.x, transform.y);
    ctx.scale(transform.k, transform.k);

    // Draw Edges
    displayEdges.forEach(e => {{
      const s = displayNodes.find(n => n.id === e.source);
      const t = displayNodes.find(n => n.id === e.target);
      if (!s || !t) return;

      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(t.x, t.y);

      if (e.cross_layer) {{
        ctx.strokeStyle = "rgba(56, 189, 248, 0.4)";
        ctx.setLineDash([4, 4]);
        ctx.lineWidth = 1.5 / transform.k;
      }} else {{
        ctx.strokeStyle = impactMode ? "rgba(239, 68, 68, 0.35)" : "rgba(255, 255, 255, 0.12)";
        ctx.setLineDash([]);
        ctx.lineWidth = 1.0 / transform.k;
      }}
      ctx.stroke();
      ctx.setLineDash([]);
    }});

    // Draw Nodes
    displayNodes.forEach(n => {{
      const isFocal = (n.id === focalNodeId);
      const isHovered = (hoveredNode && hoveredNode.id === n.id);
      const radius = isFocal ? 14 : (isHovered ? 11 : 8);
      const col = getNodeColor(n.layer);

      // Glow halo for focal node
      if (isFocal) {{
        ctx.beginPath();
        ctx.arc(n.x, n.y, radius + 8, 0, 2 * Math.PI);
        ctx.fillStyle = "rgba(0, 188, 212, 0.25)";
        ctx.fill();

        ctx.beginPath();
        ctx.arc(n.x, n.y, radius + 4, 0, 2 * Math.PI);
        ctx.strokeStyle = "#70f3ff";
        ctx.lineWidth = 2 / transform.k;
        ctx.stroke();
      }}

      // Node Body
      ctx.beginPath();
      ctx.arc(n.x, n.y, radius, 0, 2 * Math.PI);
      ctx.fillStyle = isHovered ? "#ffffff" : col;
      ctx.fill();
      ctx.strokeStyle = "#091016";
      ctx.lineWidth = 2 / transform.k;
      ctx.stroke();

      // Label
      if (transform.k > 0.6 || isFocal || isHovered) {{
        ctx.font = `${{isFocal ? "bold 11px" : "10px"}} Roboto Flex, sans-serif`;
        ctx.fillStyle = isFocal ? "#70f3ff" : (isHovered ? "#ffffff" : "#cbd5e1");
        ctx.textAlign = "center";
        ctx.fillText(n.label, n.x, n.y + radius + 12);
      }}
    }});

    ctx.restore();
    renderMinimap();
  }}

  // Minimap
  function renderMinimap() {{
    if (!miniCtx) return;
    const mw = miniCanvas.width;
    const mh = miniCanvas.height;
    miniCtx.clearRect(0, 0, mw, mh);

    if (displayNodes.length === 0) return;

    // Bounding box
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    displayNodes.forEach(n => {{
      if (n.x < minX) minX = n.x;
      if (n.x > maxX) maxX = n.x;
      if (n.y < minY) minY = n.y;
      if (n.y > maxY) maxY = n.y;
    }});

    const padding = 60;
    minX -= padding; maxX += padding;
    minY -= padding; maxY += padding;

    const scaleX = mw / (maxX - minX || 1);
    const scaleY = mh / (maxY - minY || 1);
    const scale = Math.min(scaleX, scaleY);

    miniCtx.fillStyle = "rgba(0, 188, 212, 0.6)";
    displayNodes.forEach(n => {{
      const mx = (n.x - minX) * scale;
      const my = (n.y - minY) * scale;
      miniCtx.fillRect(mx - 1, my - 1, 2, 2);
    }});
  }}

  // Pan & Zoom
  function resetZoom() {{
    const w = canvas.getBoundingClientRect().width;
    const h = canvas.getBoundingClientRect().height;
    transform = {{ x: 0, y: 0, k: 1.0 }};
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
      return;
    }}

    // Hit test
    const rect = canvas.getBoundingClientRect();
    const mx = (e.clientX - rect.left - transform.x) / transform.k;
    const my = (e.clientY - rect.top - transform.y) / transform.k;

    let hit = null;
    for (const n of displayNodes) {{
      const dx = n.x - mx;
      const dy = n.y - my;
      if (dx * dx + dy * dy <= 144) {{
        hit = n;
        break;
      }}
    }}

    if (hit !== hoveredNode) {{
      hoveredNode = hit;
      canvas.style.cursor = hit ? "pointer" : "default";
      const tt = document.getElementById("canvas-tooltip");
      if (hit) {{
        tt.style.display = "block";
        tt.style.left = `${{e.clientX - rect.left + 14}}px`;
        tt.style.top = `${{e.clientY - rect.top + 14}}px`;
        tt.innerHTML = `<strong>${{hit.label}}</strong> (${{hit.layer.toUpperCase()}})<br><span style="color:var(--text-muted)">${{hit.domain}}</span><br>${{hit.purpose || ""}}`;
      }} else {{
        tt.style.display = "none";
      }}
      render();
    }}
  }});

  window.addEventListener("mouseup", () => {{ isDragging = false; }});

  canvas.addEventListener("wheel", e => {{
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.12 : 0.88;
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    transform.x = mouseX - (mouseX - transform.x) * zoomFactor;
    transform.y = mouseY - (mouseY - transform.y) * zoomFactor;
    transform.k = Math.max(0.15, Math.min(transform.k * zoomFactor, 4.0));
    render();
  }}, {{ passive: false }});

  // Select Node & Inspector (mantiene la escala por defecto)
  function setFocalNode(id, maintainScale = true) {{
    focalNodeId = id;
    const n = nodeById.get(id);
    if (!n) return;

    // Show Inspector
    document.getElementById("insp-empty-state").style.display = "none";
    document.getElementById("insp-body").style.display = "block";
    document.getElementById("insp-title").textContent = n.label;
    document.getElementById("insp-id").textContent = n.id;
    document.getElementById("insp-type-layer").textContent = `${{n.type}} / ${{n.layer.toUpperCase()}}`;
    document.getElementById("insp-domain").textContent = n.domain;
    document.getElementById("insp-purpose").textContent = n.purpose || "Sin descripción documentada.";

    const pill = document.getElementById("insp-layer-pill");
    pill.textContent = n.layer.toUpperCase();
    pill.style.backgroundColor = getNodeColor(n.layer);

    // Sync Starter Status Badge and 5-Level Cascading Selectors
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
    }} else if (n.domain) {{
      document.getElementById("badge-starter-status").textContent = `${{n.label}} (${{n.domain}})`;
    }}

    // Cross-graph trace lists
    const inEdges = incoming.get(id) || [];
    const outEdges = outgoing.get(id) || [];
    document.getElementById("insp-trace-count").textContent = inEdges.length + outEdges.length;

    const inList = document.getElementById("insp-trace-in");
    inList.innerHTML = "";
    inEdges.slice(0, 15).forEach(e => {{
      const s = nodeById.get(e.source);
      const row = document.createElement("div");
      row.className = "trace-item";
      row.innerHTML = `<span class="trace-item-label">${{s ? s.label : e.source}}</span><span class="trace-item-rel">${{e.relation}}</span>`;
      row.onclick = () => setFocalNode(e.source, true);
      inList.appendChild(row);
    }});
    if (inEdges.length === 0) inList.innerHTML = `<span style="color:var(--text-faint);font-size:11px;">Sin enlaces entrantes</span>`;

    const outList = document.getElementById("insp-trace-out");
    outList.innerHTML = "";
    outEdges.slice(0, 15).forEach(e => {{
      const t = nodeById.get(e.target);
      const row = document.createElement("div");
      row.className = "trace-item";
      row.innerHTML = `<span class="trace-item-label">${{t ? t.label : e.target}}</span><span class="trace-item-rel">${{e.relation}}</span>`;
      row.onclick = () => setFocalNode(e.target, true);
      outList.appendChild(row);
    }});
    if (outEdges.length === 0) outList.innerHTML = `<span style="color:var(--text-faint);font-size:11px;">Sin enlaces salientes</span>`;

    // Metadata table
    const details = document.getElementById("insp-tech-details");
    details.innerHTML = "";
    if (n.metadata) {{
      for (const [k, v] of Object.entries(n.metadata)) {{
        if (v === null || v === undefined || v === "") continue;
        const r = document.createElement("div");
        r.className = "tech-row";
        r.innerHTML = `<span class="tech-k">${{k}}</span><span class="tech-v">${{typeof v === "object" ? JSON.stringify(v) : v}}</span>`;
        details.appendChild(r);
      }}
    }}

    recalculateSubgraph(maintainScale);
  }}

  canvas.addEventListener("click", e => {{
    if (hoveredNode) {{
      setFocalNode(hoveredNode.id);
    }}
  }});

  // Omnibox Fuzzy Search & Dropdown
  const searchInput = document.getElementById("omnibox-input");
  const searchDropdown = document.getElementById("search-dropdown");

  searchInput.addEventListener("input", () => {{
    const q = searchInput.value.trim().toLowerCase();
    if (!q) {{
      searchDropdown.style.display = "none";
      return;
    }}

    const matches = nodes.filter(n => {{
      return n.label.toLowerCase().includes(q) || n.id.toLowerCase().includes(q) || (n.purpose && n.purpose.toLowerCase().includes(q));
    }}).slice(0, 20);

    searchDropdown.innerHTML = "";
    if (matches.length === 0) {{
      searchDropdown.innerHTML = `<div style="padding:10px 14px;color:var(--text-faint);">Sin coincidencias para "${{q}}"</div>`;
      searchDropdown.style.display = "block";
      return;
    }}

    matches.forEach(m => {{
      const item = document.createElement("div");
      item.className = "search-res-item";
      item.innerHTML = `
        <div class="search-res-label">
          <span class="dot dot-${{m.layer}}"></span>
          <span>${{m.label}}</span>
          <span style="font-size:10px;font-family:var(--font-mono);color:var(--text-muted);">[${{m.layer.toUpperCase()}}]</span>
        </div>
        <div class="search-res-sub">${{m.purpose || m.domain}}</div>
      `;
      item.onclick = () => {{
        searchDropdown.style.display = "none";
        searchInput.value = m.label;
        setFocalNode(m.id);
      }};
      searchDropdown.appendChild(item);
    }});
    searchDropdown.style.display = "block";
  }});

  window.addEventListener("keydown", e => {{
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {{
      e.preventDefault();
      searchInput.focus();
    }}
    if (e.key === "Escape") {{
      searchDropdown.style.display = "none";
    }}
  }});

  document.addEventListener("click", e => {{
    if (!e.target.closest("#omnibox-container")) {{
      searchDropdown.style.display = "none";
    }}
  }});

  // Layer Toggles
  ["db", "code", "spec", "ui"].forEach(layer => {{
    const cb = document.getElementById(`layer-cb-${{layer}}`);
    if (cb) {{
      cb.addEventListener("change", () => {{
        if (cb.checked) activeLayers.add(layer);
        else activeLayers.delete(layer);
        document.getElementById("count-active-layers").textContent = `${{activeLayers.size}}/4`;
        recalculateSubgraph();
      }});
    }}
  }});

  // Hop radius slider
  const hopSlider = document.getElementById("hop-radius-slider");
  if (hopSlider) {{
    hopSlider.addEventListener("input", () => {{
      hopRadius = parseInt(hopSlider.value, 10);
      document.getElementById("lbl-hop-value").textContent = `${{hopRadius}} saltos`;
      recalculateSubgraph();
    }});
  }}

  // Impact mode toggle
  const toggleImpact = document.getElementById("toggle-impact-mode");
  if (toggleImpact) {{
    toggleImpact.addEventListener("change", () => {{
      impactMode = toggleImpact.checked;
      render();
    }});
  }}

  // Layout selector
  const selectLayout = document.getElementById("select-layout");
  if (selectLayout) {{
    selectLayout.addEventListener("change", () => {{
      currentLayout = selectLayout.value;
      layoutNodes(currentLayout);
      render();
    }});
  }}

  // Reset all filters button
  const btnReset = document.getElementById("btn-reset-filters");
  if (btnReset) {{
    btnReset.addEventListener("click", () => {{
      // 1. Reset layers
      activeLayers = new Set(["db", "code", "spec", "ui"]);
      ["db", "code", "spec", "ui"].forEach(layer => {{
        const cb = document.getElementById(`layer-cb-${{layer}}`);
        if (cb) cb.checked = true;
      }});
      document.getElementById("count-active-layers").textContent = "4/4";

      // 2. Reset domains
      activeDomains = new Set(domains);
      document.querySelectorAll(".domain-chip").forEach(chip => chip.classList.add("active"));

      // 3. Reset starter selects (Jerarquía completa de 5 niveles)
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

      // 4. Reset hop radius
      hopRadius = 2;
      if (hopSlider) hopSlider.value = 2;
      document.getElementById("lbl-hop-value").textContent = "2 saltos";

      // 5. Reset impact mode
      impactMode = false;
      if (toggleImpact) toggleImpact.checked = false;

      // 6. Reset layout
      currentLayout = "concentric";
      if (selectLayout) selectLayout.value = "concentric";

      // 7. Clear focal node
      focalNodeId = null;
      document.getElementById("active-focus-pill").style.display = "none";
      if (searchInput) searchInput.value = "";

      // 8. Reset inspector drawer
      document.getElementById("insp-empty-state").style.display = "flex";
      document.getElementById("insp-body").style.display = "none";

      // 9. Reset viewport
      resetZoom();

      // 10. Por defecto mostrar solo todas las specs, no un spec seleccionado
      initAllSpecsView();
    }});
  }}

  // Clear focus button
  document.getElementById("btn-clear-focus").onclick = () => {{
    focalNodeId = null;
    if (specSelect) specSelect.value = "";
    document.getElementById("badge-starter-status").textContent = moduleSelect && moduleSelect.value ? `Módulo: ${{moduleSelect.value}}` : "Global";
    recalculateSubgraph();
  }};

  // Zoom buttons
  document.getElementById("btn-zoom-in").onclick = () => {{
    transform.k = Math.min(transform.k * 1.25, 4.0);
    render();
  }};
  document.getElementById("btn-zoom-out").onclick = () => {{
    transform.k = Math.max(transform.k * 0.8, 0.2);
    render();
  }};
  document.getElementById("btn-zoom-reset").onclick = resetZoom;
  document.getElementById("btn-relayout").onclick = () => {{
    layoutNodes(currentLayout);
    render();
  }};

  // Close inspector
  document.getElementById("btn-close-inspector").onclick = () => {{
    document.getElementById("inspector-drawer").style.display = "none";
  }};

  // Export JSON
  document.getElementById("btn-export-json").onclick = () => {{
    const exportData = {{
      focalNode: focalNodeId ? nodeById.get(focalNodeId) : null,
      hopRadius: hopRadius,
      nodes: displayNodes,
      edges: displayEdges
    }};
    const blob = new Blob([JSON.stringify(exportData, null, 2)], {{ type: "application/json" }});
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `subgraph-${{focalNodeId || "unified"}}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }};

  // Export PNG
  document.getElementById("btn-export-svg").onclick = () => {{
    const a = document.createElement("a");
    a.href = canvas.toDataURL("image/png");
    a.download = `graph-${{focalNodeId || "unified"}}.png`;
    a.click();
  }};

  // Initial Boot: Por defecto solo debe mostrar todas las specs, no un spec seleccionado
  resizeCanvas();
  initAllSpecsView();

}})();
</script>
</body>
</html>"""


def main(argv=None):
    parser = argparse.ArgumentParser(description="Genera explorer.html unificado multidominio")
    parser.add_argument("--out", default=str(HERE / "explorer.html"), help="Ruta del archivo HTML de salida")
    args = parser.parse_args(argv)

    print("Cargando modelo unificado de grafos...")
    model = UnifiedGraphModel(root=ROOT)
    graph_data = model.load()
    summary = graph_data.get("summary", {})
    print(f"Grafo unificado cargado con exito: {summary.get('total_nodes')} nodos, {summary.get('total_edges')} aristas.")

    out_path = Path(args.out)
    html_content = generate_html(graph_data)
    out_path.write_text(html_content, encoding="utf-8")
    print(f"Artefacto generado en: {out_path} ({len(html_content):,} bytes)")


if __name__ == "__main__":
    main()
