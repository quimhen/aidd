# Mockup Audit — F47 Unified Knowledge Graph Explorer

## Provenance
| Field | Value |
|---|---|
| Source | projects/4131466547769539953/screens/ac0f76f7a11d4670a2f9cba4484582cc |
| Hash (sha256, if a file) | n/a — remote Stitch screen |
| Visual snapshot | prototype/stitch-SCREEN-95.png |
| Visual snapshot SHA-256 | 79c80eb1a46941dc1a59a2d50b905f226e1c9e1d47da03795b01cd1305a100a1 |
| Size | 640780 |
| Audit date | 2026-11-03 |
| Auditor (agent/person) | Antigravity |

## Screen inventory
| SCREEN-XX | DOM/node id | Name | Type (view/modal/sheet) | Uses (COMP-nnn list) | Use case (US-nnn) | Purpose |
|---|---|---|---|---|---|---|
| SCREEN-95 | root | Global Unified Knowledge Graph Explorer | view | COMP-901, COMP-902, COMP-903, COMP-904, COMP-905, COMP-906, COMP-907, COMP-908, COMP-909, COMP-910 | US-095 | Explorador interactivo global de los 4 grafos del monorepositorio (BD, Código AST, Specs AIDD, Componentes UI) con análisis de impacto y trazabilidad cruzada. |

## Component inventory
Prioritize reuse via a "Shared-First" methodology: check `design-system/` and monorepo shared components.

| COMP-nnn | Name | Used in (SCREEN-XX list) | Contains (CTL-nnn list) | PR/Spec ref | Pattern / Shared Library |
|---|---|---|---|---|---|
| COMP-901 | GraphHeaderBar | SCREEN-95 | CTL-135001, CTL-135002, CTL-135003, CTL-135004, CTL-135005, CTL-135006 | F47 | Header estructural de alta densidad (56px) con breadcrumb, métricas y controles globales |
| COMP-902 | GraphOmniboxSearch | SCREEN-95, COMP-901 | CTL-135002, CTL-135007 | F47 | Buscador fuzzy predictivo unificado con etiquetas de dominio (`[BD]`, `[AST]`, `[SPEC]`, `[UI]`) |
| COMP-903 | GraphFilterSidebar | SCREEN-95 | CTL-135008, CTL-135009, CTL-135010, CTL-135011, CTL-135012, CTL-135013 | F47 | Panel lateral izquierdo (280px) de configuración de capas, dominios y radio de saltos |
| COMP-904 | GraphLayerToggleGroup | SCREEN-95, COMP-903 | CTL-135008, CTL-135009, CTL-135010, CTL-135011 | F47 | Toggles con switch, chips cromáticos y contadores para las 4 capas de conocimiento |
| COMP-905 | GraphDomainFilter | SCREEN-95, COMP-903 | CTL-135012 | F47 | Selector por dominio de negocio (Nómina, eDoc, Selección, Mobile Sync) |
| COMP-906 | GraphCanvasViewport | SCREEN-95 | CTL-135014, CTL-135015, CTL-135016, CTL-135017, CTL-135018 | F47 | Lienzo de red interactivo con soporte de clústeres, halos focales, etiquetas semánticas de aristas y física de partículas |
| COMP-907 | GraphMinimap | SCREEN-95, COMP-906 | CTL-135018 | F47 | Vista satelital interactiva flotante (180x120px) con navegación rápida por recuadro |
| COMP-908 | GraphFloatingToolbar | SCREEN-95, COMP-906 | CTL-135014, CTL-135015, CTL-135016, CTL-135017 | F47 | Botonera flotante en lienzo (Zoom +, Zoom -, Reset 100%, Recentrar en Nodo Focal, Congelar Física) |
| COMP-909 | GraphNodeInspectorDrawer | SCREEN-95 | CTL-135019, CTL-135020, CTL-135021, CTL-135022, CTL-135023, CTL-135024, CTL-135025 | F47 | Inspector lateral derecho (360px) con ficha técnica, propósito documentado, DDL/código y análisis de impacto |
| COMP-910 | GraphCrossTracePanel | SCREEN-95, COMP-909 | CTL-135021, CTL-135022 | F47 | Desglose interactivo de conexiones cruzadas (Specs vinculadas, funciones SQL/endpoints y componentes UI dependientes) |

## Control inventory
| CTL-nnn | Screen or COMP-nnn | Visible text | id | Action/handler | Destination | Data source | States | Class/style | Calls API-nnn (if any) | Status | PR/Spec ref |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CTL-135001 | COMP-901 | b1SyncLink > Arquitectura > Explorador Global de Grafos | breadcrumb-nav | navigate_home | SCREEN-95 | static | normal | text-xs text-slate-500 | | Explicit | F47 |
| CTL-135002 | COMP-902 | Buscar en el grafo (⌘K)... | omnibox-input | on_search_query | self | unified_graph_index | empty, typing, results | font-sans text-xs bg-slate-50 | | Explicit | F47 |
| CTL-135003 | COMP-901 | 6,980 Nodos BD · 1,094 Módulos · 501 UI · 69 Specs | metrics-pills | filter_by_layer | self | graph_metrics | normal, hover | font-mono text-[11px] | | Explicit | F47 |
| CTL-135004 | COMP-901 | Jerárquico DAG | layout-selector | set_graph_layout | self | layout_options | open, closed, selected | rounded-sm border px-2 py-1 | | Explicit | F47 |
| CTL-135005 | COMP-901 | Exportar | export-btn | export_graph_data | download | graph_state | normal, exporting | btn-outline text-xs | | Explicit | F47 |
| CTL-135006 | COMP-901 | Pantalla Completa | fullscreen-btn | toggle_fullscreen | browser_fullscreen | window | normal, active | btn-icon | | Explicit | F47 |
| CTL-135007 | COMP-902 | Resultado sugerido ([BD] OPRM) | search-result-item | select_focal_node | COMP-906 | omnibox_results | highlighted, normal | p-2 hover:bg-slate-100 | | Explicit | F47 |
| CTL-135008 | COMP-904 | Base de Datos (6,980) | toggle-layer-db | toggle_layer_db | COMP-906 | layer_filter_state | checked, unchecked | switch-teal | | Explicit | F47 |
| CTL-135009 | COMP-904 | Código Fuente (1,094) | toggle-layer-code | toggle_layer_code | COMP-906 | layer_filter_state | checked, unchecked | switch-blue | | Explicit | F47 |
| CTL-135010 | COMP-904 | Specs AIDD (69) | toggle-layer-spec | toggle_layer_spec | COMP-906 | layer_filter_state | checked, unchecked | switch-emerald | | Explicit | F47 |
| CTL-135011 | COMP-904 | Componentes UI (501) | toggle-layer-ui | toggle_layer_ui | COMP-906 | layer_filter_state | checked, unchecked | switch-purple | | Explicit | F47 |
| CTL-135012 | COMP-905 | Dominio de Negocio (Nómina / eDoc / ...) | domain-checkboxes | filter_domain | COMP-906 | domain_metadata | checked, unchecked | checkbox-dense | | Explicit | F47 |
| CTL-135013 | COMP-903 | Profundidad de Rastreo (1..5 saltos) | hop-slider | set_hop_radius | COMP-906 | filter_state | 1, 2, 3, 4, 5 | slider-teal | | Explicit | F47 |
| CTL-135014 | COMP-908 | Zoom In (+) | zoom-in-btn | zoom_in | COMP-906 | canvas_zoom | normal, pressed | btn-canvas-ctrl | | Explicit | F47 |
| CTL-135015 | COMP-908 | Zoom Out (-) | zoom-out-btn | zoom_out | COMP-906 | canvas_zoom | normal, pressed | btn-canvas-ctrl | | Explicit | F47 |
| CTL-135016 | COMP-908 | Ajustar a Pantalla | fit-view-btn | fit_to_viewport | COMP-906 | canvas_dimensions | normal, pressed | btn-canvas-ctrl | | Explicit | F47 |
| CTL-135017 | COMP-908 | Recentrar en Focal Node | recenter-btn | center_on_focal | COMP-906 | focal_node_id | enabled, disabled | btn-canvas-ctrl | | Explicit | F47 |
| CTL-135018 | COMP-907 | Minimapa de Navegación | minimap-canvas | pan_to_minimap_click | COMP-906 | canvas_overview | rendering | border rounded-lg shadow-md | | Explicit | F47 |
| CTL-135019 | COMP-906 | Nodo de Grafo (clic) | graph-node-element | on_node_click | COMP-909 | graph_data | idle, hovered, selected | svg/canvas-node | | Explicit | F47 |
| CTL-135020 | COMP-909 | Cerrar Inspector | close-inspector-btn | toggle_inspector | self | ui_state | visible, hidden | btn-icon-sm | | Explicit | F47 |
| CTL-135021 | COMP-910 | Spec Vinculada (ej. F35) | cross-trace-spec-link | navigate_to_spec | COMP-906 | node_links | clickable | badge-emerald cursor-pointer | | Explicit | F47 |
| CTL-135022 | COMP-910 | Componente UI Vinculado | cross-trace-ui-link | focus_ui_component | COMP-906 | node_links | clickable | badge-purple cursor-pointer | | Explicit | F47 |
| CTL-135023 | COMP-909 | Convertir en Nodo Focal | make-focal-btn | set_as_focal_node | COMP-906 | selected_node_id | active, loading | btn-primary-teal w-full | | Explicit | F47 |
| CTL-135024 | COMP-909 | Aislar Vecindario (1 salto) | isolate-neighborhood-btn | isolate_subgraph | COMP-906 | selected_node_id | active | btn-outline w-full | | Explicit | F47 |
| CTL-135025 | COMP-909 | Copiar Enlace Permanente | copy-permalink-btn | copy_node_url | clipboard | current_location | idle, copied | btn-ghost-sm | | Explicit | F47 |

## Navigation map
| Origin | Action | Destination | Data passed | Condition | Alternative |
|---|---|---|---|---|---|
| SCREEN-95 | CTL-135002 (Buscar y seleccionar) | COMP-906 | `node_id` | Nodo existe en grafo unificado | Mostrar "Sin resultados" en dropdown |
| SCREEN-95 | CTL-135019 (Clic en nodo del lienzo) | COMP-909 | `node_id`, atributos completos | Nodo clickeado | Deselección al hacer clic en fondo |
| SCREEN-95 | CTL-135021 (Clic en link de spec) | COMP-906 | `spec_node_id` | Spec existe en grafo | Inspección de tasks.md / spec.md |
| SCREEN-95 | CTL-135023 (Convertir en focal) | COMP-906 | `focal_node_id`, `hop_radius` | Nodo seleccionado | Mantener foco actual |

## Behavior list per screen
| SCREEN-XX-Fnn | Screen | Rule (one testable sentence) | Status | Evidence |
|---|---|---|---|---|
| SCREEN-95-F01 | SCREEN-95 | El explorador carga y unifica los 4 grafos (BD, AST, Specs, UI) en una estructura homogénea con nodos y aristas tipadas. | Explicit | `docs/db-graph/gen_unified_explorer.py` |
| SCREEN-95-F02 | SCREEN-95 | El buscador omnibox filtra instantáneamente por nombre, tipo o dominio con latencia menor a 50ms sobre los ~8,700 nodos indexados. | Explicit | `docs/db-graph/unified_graph_index.js` |
| SCREEN-95-F03 | SCREEN-95 | Desactivar un toggle de capa (BD, AST, Specs, UI) oculta sus nodos y aristas asociadas sin recargar la página. | Explicit | test_unified_explorer.py |
| SCREEN-95-F04 | SCREEN-95 | Al seleccionar un nodo focal con radio de saltos N, el lienzo oculta los nodos fuera del radio y resalta el camino de trazabilidad. | Explicit | test_unified_explorer.py |
| SCREEN-95-F05 | SCREEN-95 | El panel inspector muestra la trazabilidad cruzada (Cross-Graph Trace) conectando la tabla con sus specs, endpoints y componentes UI. | Explicit | test_unified_explorer.py |
| SCREEN-95-F06 | SCREEN-95 | El archivo generado es un único archivo HTML autocontenido (offline, sin dependencias CDN externas bloqueantes) apto para distribución y CI/CD. | Explicit | test_unified_explorer.py |

## Use cases referenced
| US-nnn | Description | Source |
|---|---|---|
| US-095 | Navegación e inspección unificada de la arquitectura del monorepositorio con análisis de impacto multidominio. | user — "ese explorer debe ser global para todos los grafos, como está todo interconectado, utiliza stitch para mejorarlo e implementa un nuevo spec en aidd para esta funcionalidad" |
