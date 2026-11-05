# Mockup Audit — 004 unified knowledge-graph explorer (amendment 2026-11-03)

Step 1 output for the amendment that ports the b1SycLink F47 explorer into AIDD and adopts the controls of the approved alias
mockup (FR-060..FR-077). The view is a PORT of an implemented view plus 8 adopted controls; this audit lists, by element id and
measured value, what each source contributes. Measured, never judged by eye: the comparison itself is T-VISUAL.

## Provenance
| Field | Value |
|---|---|
| Source 1 (view base) | `batch-staging/f47-port-sources/f47-spec/prototype/stitch-SCREEN-95.html` (F47 Stitch prototype, snapshot of b1SycLink `specs/F47-Unified-Knowledge-Graph-Explorer/prototype/`) and the implemented view `batch-staging/f47-port-sources/explorer/graph_explorer.py` |
| Hash (sha256) source 1 | prototype HTML `71777db574ec03bccd053b08882b6dc69a3083d08861c19ccfe1b22ea3406b25`; implemented view `50b5e91cf33bc0e97db3d3626d3e3c6631cce2aa825cfbae15926206c31e2a04` |
| Visual snapshot source 1 | `batch-staging/f47-port-sources/f47-spec/prototype/stitch-SCREEN-95.png` |
| Visual snapshot SHA-256 source 1 | `79c80eb1a46941dc1a59a2d50b905f226e1c9e1d47da03795b01cd1305a100a1` |
| Source 2 (adopted controls) | `specs/007-aidd-review-html-close-gate/prototypes/alias-graph-explorer/alias-graph-explorer.html` (approved Stitch mockup of spec 007) |
| Hash (sha256) source 2 | `33bd7fb75fd696fef77d1adc2d8e1f41314eca0b3514ace79fab752f2f6ad8d7` |
| Visual snapshot source 2 | `specs/007-aidd-review-html-close-gate/prototypes/alias-graph-explorer/alias-graph-explorer-1280.png` |
| Visual snapshot SHA-256 source 2 | `f0cf3f02c560fbf941264aa7272d0b96ac8991ad774c9784fb6b5e024aa58d1a` |
| Size | desktop 1280×800 and wider |
| Audit date | 2026-11-03 |
| Auditor (agent/person) | Claude (drafting lane W-F47PORT), by script reads of the files above |

## Screen inventory
| SCREEN-XX | DOM/node id | Name | Type (view/modal/sheet) | Uses (COMP-nnn list) | Use case (US-nnn) | Purpose |
|---|---|---|---|---|---|---|
| SCREEN-95 | `canvas-viewport` | Unified knowledge-graph explorer (F47 view base) | view | — (single-file generated page, no component library) | — | one layer per registered graph: omnibox, layer checkboxes, metric pills, canvas, minimap, inspector |
| SCREEN-901 | `graphContainer` | Alias graph explorer (spec 007; source of the 8 adopted controls) | view | — | — | zoom in, out, reset, zoom level, fit, centre, copy node, theme toggle |

## Element inventory (by element id; ported or adopted, no CTL codes)
| Source | Mockup id | Explorer id | Action | Measured value | Status |
|---|---|---|---|---|---|
| SCREEN-95 | omnibox | `omnibox-input` | search nodes | unchanged from the implemented view | ported |
| SCREEN-95 | layer toggles | `layer-cb-<layer id>` | filter a layer | one per registered graph; F47 markup for db, code, spec, ui | ported, generated |
| SCREEN-95 | metric pills | `metric-<layer id>` | node count per layer | one per registered graph | ported, generated |
| SCREEN-95 | inspector | `inspector-drawer`, `insp-tech-details` | node details and metadata | metadata block from the verified generator | ported |
| SCREEN-901 | `zoomInBtn` | `zoomInBtn` | zoom in | ×1.25 up to 4.0 (F47 value, owner decision) | adopted |
| SCREEN-901 | `zoomOutBtn` | `zoomOutBtn` | zoom out | ×0.8 down to 0.2 | adopted |
| SCREEN-901 | `zoomResetBtn` | `zoomResetBtn` | reset view | k = 1, x = y = 0 | adopted |
| SCREEN-901 | `zoomLevelDisplay` | `zoomLevelDisplay` | show zoom | `Math.round(k * 100) + "%"`, `100%` at start | adopted |
| SCREEN-901 | `fitViewBtn` | `fitViewBtn` | fit all nodes | 40 px margin, k in [0.2, 4.0] | adopted |
| SCREEN-901 | `centerNodeBtn` | `centerNodeBtn` | centre the focal node | focal node within 1 px of the canvas centre | adopted |
| SCREEN-901 | `copyNodeBtn` | `copyNodeBtn` | copy the focal node | JSON with `id`; feedback `Copiado` 1500 ms | adopted |
| SCREEN-901 | `themeToggleBtn` | `themeToggleBtn` | light or dark | light tokens from mockup lines 10-28; dark = F47; remembered in `localStorage` key `aidd-explorer-theme` | adopted |

## Behavior list per screen
| SCREEN-XX-Fnn | Screen | Rule (one testable sentence) | Status | Evidence |
|---|---|---|---|---|
| SCREEN-95-F01 | SCREEN-95 | Every graph listed by `aidd graphs list` appears as a layer with a pill and a checkbox. | Explicit | AC-050, AC-051 |
| SCREEN-95-F02 | SCREEN-95 | Unchecking a layer checkbox removes that layer from the neighbourhood view. | Explicit | AC-059 |
| SCREEN-95-F03 | SCREEN-95 | The page makes no request outside `file:`. | Explicit | AC-058, AC-063 |
| SCREEN-901-F01 | SCREEN-901 | Zoom in, out and reset change the zoom level text to 125%, 80% and 100%. | Explicit | AC-063 |
| SCREEN-901-F02 | SCREEN-901 | The theme toggle switches `--bg-dark` between `#091016` and `#ffffff` and the choice survives a reload when storage is available. | Explicit | AC-063 |

## Test-fixture identifiers (not product codes)
| Code | Where | Meaning |
|---|---|---|
| COMP-001 | T-70 fixture `ui.toon` row | synthetic component of the temporary test project; no UI component of AIDD |
| US-001 | T-70 fixture `specs/index.toon` codes and the `consumers` of COMP-001 | synthetic use-case code that makes the `references` cross link testable |

## Flows (Step 1.5)
| Origin | Action | Destination | Data passed | Condition | Alternative |
|---|---|---|---|---|---|
| SCREEN-95 | `aidd graphs explorer` | `docs/graphs/explorer.html` | every registered graph | size at most 25 MB | exit 3, nothing written; `--skip <name>` |
| SCREEN-95 | click a node | inspector | node id, layer, metadata | node visible | none |
| SCREEN-901 | click `themeToggleBtn` | same page, light or dark | `aidd-explorer-theme` | storage available | storage blocked: theme switches, not remembered |
