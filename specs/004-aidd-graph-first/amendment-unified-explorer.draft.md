# Draft — amendment to spec 004: the unified knowledge-graph explorer, driven by the graph registry

**DRAFT: not approved, not executable, no `Approved:` line.** Not integrated into `spec.md` yet (one integration round for
this draft and the tool-first draft is planned by the coordinator). Amendment intake: `AMENDMENT` of
`specs/004-aidd-graph-first` (this spec already owns `aidd graphs explorer`, the graph registry `load_registry` and the FR-039
catalog). Not Fast Lane: new module, a ported explorer, new controls, a CLI behaviour change and mirrors.
Owner direction (verbatim, typed by the owner, 2026-11-03): "yo pedi que ese explorador se implemente en aidd al parecer no lo
hizo, esa es una funcionalidad que debemos implementar y la complementas con el nuevo grafo" and "si adicionamos un grafo en
aidd este tambien se debe poder leer con el explorer". Owner decisions on this draft (typed answers, 2026-11-03) are listed in
`## Owner decisions` below.

## Problem (observed, not assumed)

- The b1SycLink spec F47 (Unified Knowledge Graph Explorer, closed, 5 tasks) built a multi-layer explorer, but only inside
  b1SycLink: `docs/db-graph/unified_graph_model.py` (523 lines), `docs/db-graph/gen_unified_explorer.py` (2016 lines + 5
  HTML components) and a rewritten `.aidd/scripts/graph_explorer.py` (1371 lines, Canvas 2D). The AIDD source has none of it:
  `skill/scripts/graph_explorer.py` is still the 207-line searchable list viewer (ids `q`, `list`, `card`, `fg`, `ft`, `count`).
- The b1SycLink explorer's `--root` mode does `from unified_graph_model import UnifiedGraphModel` after putting
  `docs/db-graph` on `sys.path` (snapshot line 1355): copied alone into AIDD it fails in every other project.
- The F47 model reads FOUR hard-coded paths and hard-codes four layers (`db`, `code`, `spec`, `ui`) in Python, CSS, HTML and JS.
  A graph added to the AIDD registry (for example the `aliases` graph of amendment 06 to spec 007) never appears in it.

## Inventory (measured on the immutable snapshot)

| Piece (b1SycLink) | b1SycLink-specific parts that must be generalised | Decision |
|---|---|---|
| `unified_graph_model.py` | Paths `docs/db-graph/graph.json`, `.aidd/graphs/code.json`, `specs/index.toon`, `.aidd/graphs/ui.toon` (lines 26-29); a `Payroll/supabase/migrations` regex scan (lines 68-109); `_infer_domain` with spec prefixes `P..`, `S..`, `F06/F09/F55`, the eDoc list `F12..F54` and words `payroll`, `nomina`, `edoc`, `sri`, `pur_`, `imc_` (lines 179-207); ad-hoc TOON parsing with `split(",", 6)` (lines 209-308); Spanish relation names; domain gating `Sync Mobile`; a `mobile/` path fallback (line 424); `__file__` three levels up as root | Port the LOGIC only into the new `skill/scripts/unified_graph.py`, driven by `aidd_graphs.load_registry`; TOON read with AIDD's own readers `find_spec.loads_index` and `component_graph.parse_toon`; generic domain fields; English relation names |
| `.aidd/scripts/graph_explorer.py` (1371 lines) | `--root` imports `unified_graph_model` from `docs/db-graph`; default out `docs/db-graph/explorer.html`; root = `__file__` three levels up; four layers hard-coded in CSS (lines 115-119, 230-233), pills (394-397), checkboxes (441-444), JS (513, 527, 545-548, 854-855, 1093-1096, 1272-1273); 26 `.layer === "<db/code/spec/ui>"` tests; a `--graph` heuristic that calls every id starting with `F` or `P` a spec (lines 38-46) | Port the VIEW unchanged (same DOM, CSS, strings); generate the layer elements from the registry; wire `--root` to `unified_graph` |
| `gen_unified_explorer.py` + `components/graph_*.html` | `F28_TABLES` hubs, `docs/db-graph` paths; it is the generator whose output F47 verified (V-2) | Reference only (snapshot). Three blocks are taken from it: the working layer-checkbox listener, the technical-properties block, the metadata loop |
| `test_unified_explorer.py` (5 tests) | Thresholds on b1SycLink data (more than 6000 db nodes, the table `OPRM`, the domain `eDoc`) | Rewritten on synthetic temporary projects |
| `build_graph.py`, `explorer.html` (23 MB) | DB builder that needs a Postgres; a generated output | Stay out |

Also measured (`python -m pytest` on a scratch copy of the snapshot with the current `tests/test_graph_explorer.py`): 6 of 9 old
tests fail on a plain copy; after id-only assertion updates 4 remain red for real behaviour gaps (`test_deterministic`,
`test_group_autodetect`, `test_cli_exit_codes`, `test_extra_fields_rendered`). In the 1371-line explorer the layer checkboxes have
NO change listener, and two trace rows build `innerHTML` from node labels. This amendment fixes those gaps and defects.

## Immutable snapshot (Read-first for every task)

`batch-staging/f47-port-sources/` (15 files copied by `cp` with a script, each with its `.sha256`, verified by `cmp` and
`sha256sum -c`): `explorer/graph_explorer.py` (sha256 `50b5e91c…2a04`, identical to `batch-staging/f47-explorer/` of
amendment 06), `model/unified_graph_model.py` (`e834afc2…0a9c`), `model/test_unified_explorer.py`,
`reference/gen_unified_explorer.py`, `reference/test_gen_explorer.py`, `reference/components/graph_{canvas,inspector,minimap,omnibox,sidebar}.html`,
`f47-spec/{spec,tasks,mockup-audit}.md` and `f47-spec/prototype/` (the F47 Stitch prototype `stitch-SCREEN-95.html` and `.png`,
same bytes as b1SycLink `specs/F47-Unified-Knowledge-Graph-Explorer/prototype/`). Files are read-only.

## Owner decisions (2026-11-03, typed answers; they close Q-1..Q-5 of the first version)

| # | Decision | Owner answer (verbatim) | Effect on this draft |
|---|---|---|---|
| Q-1 | Base = the 1371-line explorer + the 3 blocks of the verified generator | user — "Archivo de 1.371 líneas + 3 bloques (Recommended)" | T-74..T-76 |
| Q-2 | Keep the Spanish strings; translate later | user — "Mantener español, traducir después (Recommended)" | no translation task |
| Q-3 | Output `docs/graphs/explorer.html`, VERSIONED in git | user — "docs/graphs/explorer.html versionado" | FR-076, AC-064, AC-065, T-75, T-77, T-84; no git-ignore task |
| Q-4 | Resolved visual-debt row + measured comparison | user — "Fila resuelta + comparación medida (Recommended)" | `## Visual debt`, FR-077, AC-066, T-VISUAL |
| Q-5 | Generic domain fields declared by each graph; no project names in AIDD | user — "Campos genéricos de dominio (Recommended)" | FR-062, T-70 `test_no_project_specific_paths` |
| Controls | Adopt every control of the approved alias mockup, for all layers | user — "Sí, adoptar todos los controles" | FR-071..FR-075, AC-062, AC-063, T-80..T-83 |
| Q-6 | Ceiling 25 MB, exit 3 above it; b1SycLink runs it with `--skip code-graphify` (about 20 MB) | user — "Tope 25 MB, omitiendo code-graphify (Recommended)" | FR-076, AC-064, T-84 |
| Q-7 | Keep the F47 zoom (×1.25, range 0.2 to 4.0); the buttons take the mockup ids | user — "Los de F47: x1,25, rango 0,2-4,0 (Recommended)" | FR-074, T-82 |
| Dark palette | Keep the F47 dark palette; T-VISUAL records the difference as known and accepted | user — "Conservar la paleta de F47 (Recommended)" | FR-072, FR-077, T-VISUAL |
| Theme memory | Remember the theme in the browser (`localStorage` inside try/catch; identical behaviour when storage is blocked) | user — "Sí, guardarla en el navegador (Recommended)" | FR-072, AC-063, T-81, T-83 |

## Size and git risk (Q-3) — measured

- Measured 2026-11-03 (`measure_size.py` in the scratchpad, read-only on b1SycLink): the snapshot explorer over the F47 model
  of b1SycLink (4 layers, 20,254 nodes, 75,298 edges) writes **19.0 MB** (19,041,883 bytes; about 199 bytes per node or
  edge); zlib level 6 compresses it to **1.0 MB**. The F47 generator's own build was 23.5 MB.
- The b1SycLink registry today lists 7 graphs: 94,990 nodes and 222,315 edges in total, 73,032 nodes and 144,169 edges of them
  in `code-graphify` alone. At 199 bytes per element the full registry would give **about 63 MB**; without `code-graphify`,
  about 20 MB.
- Risk: the file is versioned, so EVERY regeneration adds a new blob to git history (about 1 MB compressed per commit at
  b1SycLink scale, about 3 MB with every layer), and history never shrinks without a rewrite. Mitigation in this draft: a size
  ceiling (FR-076), a `--skip` option, and regeneration only on demand (`aidd graphs explorer` is never run by a hook).
- **Ceiling: 25 MB** (`--max-mb 25`, owner decision Q-6; below GitHub's 50 MB warning). b1SycLink runs the explorer with
  `--skip code-graphify` (measured estimate about 20 MB).

## Minimum Requirements Checklist

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | `skill/scripts/aidd_graphs.py` (`explorer` subcommand), `skill/scripts/graph_explorer.py`, new `skill/scripts/unified_graph.py`, mirrors in `adapters/dot-aidd/scripts/` | repo — `skill/scripts/aidd_graphs.py:1118-1133` | — |
| New development or modification? | Modification of `graph_explorer.py` and `aidd_graphs.py`; one new module | repo — `skill/scripts/graph_explorer.py:1-10` | — |
| External service, API, integration? | None at runtime; the HTML stays one self-contained file | user — "si adicionamos un grafo en aidd este tambien se debe poder leer con el explorer" | — |
| Who is requesting it? | Owner | user — "yo pedi que ese explorador se implemente en aidd al parecer no lo hizo" | — |
| Dependencies? | The registry (`load_registry`), `find_spec.loads_index`, `component_graph.parse_toon`; amendment 06 to spec 007 is re-based on this one | repo — `skill/scripts/aidd_graphs.py:200-219` | — |
| Business objective | One explorer that shows every registered graph as a layer, so any new graph (the alias graph first) is readable with no extra work | user — "esa es una funcionalidad que debemos implementar y la complementas con el nuevo grafo" | — |
| Expected visual fidelity | F47 view unchanged + the 8 controls of the approved alias mockup; verified by measured comparison | user — "Fila resuelta + comparación medida (Recommended)" | — |

## Executive summary

- **What:** `aidd graphs explorer` with no name writes `docs/graphs/explorer.html` (versioned): the F47 Canvas 2D explorer,
  one layer per graph in `aidd graphs list`, plus the alias mockup's controls (zoom in, out, reset, zoom level, fit, centre,
  copy node, light or dark theme). With a name it keeps today's single-graph behaviour, in the same view.
- **How:** a new stdlib module `unified_graph.py` (logic ported from F47, generalised) builds the layered payload FROM THE
  REGISTRY; the explorer draws the metric pill, the layer checkbox and the colour of each layer from that payload.
- **Owner principle:** a graph registered in the charter `## Graphs` table, or auto-detected, becomes a layer with no code
  change. JSON graphs and TOON graphs of any kind are read; `spec` and `ui` TOON use AIDD's own readers; an unknown TOON kind
  still shows its rows as nodes; a kind adds a dedicated reader through `TOON_READERS` (amendment 06 does it for `aliases`).
- **Size:** 16 tasks in 10 waves; totals in `## Waves`.

## Functional requirements

| Code | Requirement | Source |
|---|---|---|
| FR-060 | New stdlib module `skill/scripts/unified_graph.py`, a port of the LOGIC (never the view) of b1SycLink `docs/db-graph/unified_graph_model.py` (snapshot `batch-staging/f47-port-sources/model/unified_graph_model.py`, provenance stated in its docstring). It reads the graphs from `aidd_graphs.load_registry(root)`, never from fixed paths: each registry entry with an `output` becomes one layer named after the entry. | user — "si adicionamos un grafo en aidd este tambien se debe poder leer con el explorer" |
| FR-061 | Readers: `.json` with `nodes` and `edges` or `links`; `.toon` through `TOON_READERS[kind]` (`spec` → `find_spec.loads_index`, `ui` → `component_graph.parse_toon`); any other `.toon` through the generic section reader (one node per row, first column = id). Unsupported suffix or invalid content raises `ValueError` inside the reader only. | repo — `skill/scripts/find_spec.py:250`, `skill/scripts/component_graph.py:365` |
| FR-062 | Normalised payload, deterministic (nodes sorted by `id`, edges by `source`, `target`, `relation`): node keys `id`, `raw_id`, `label`, `layer`, `kind`, `type`, `domain`, `purpose`, `metadata`, `codes`, `refs`; edge keys `source`, `target`, `relation`, `layer`, `cross_layer`. Node ids are `<layer>:<raw id>` in the unified payload and the raw id in the single-graph payload. Domain = the first non-empty field the graph itself declares among `domain`, `origin`, `community`, `group`, else `Core`; AIDD names no project domain. | user — "Campos genéricos de dominio (Recommended)" |
| FR-063 | Generic cross-layer links (no project rules): `references` from a node's `consumers`, `consumes` or `refs` value to the node of ANOTHER layer whose raw id or `codes` entry equals it; `mentions` from a `spec`-kind node to `db`-kind tables, views and functions whose label appears as a word in its `spec.md`, `plan.md`, `tasks.md` or `data-model.md`, and to `code`-kind nodes whose path appears there. Cross edges carry `layer` `cross` and `cross_layer` true; duplicates collapse. | snapshot `model/unified_graph_model.py:310-447` |
| FR-064 | Layer style from the registry order: an entry whose name equals its kind and is `db`, `code`, `spec` or `ui` keeps the F47 colour and labels; every other entry takes the next colour of `EXTRA_COLOURS` and its name as pill label and checkbox title. | snapshot `explorer/graph_explorer.py:115-119, 394-397, 441-444` |
| FR-065 | `compute_neighborhood(graph, focal_node_id, hop_radius=2)` and `filter_graph(graph, active_layers=None, active_domains=None)` keep the F47 signatures and return shapes. | snapshot `model/unified_graph_model.py:449-523` |
| FR-066 | Fail open: a missing output gives a layer with `missing` true and the warning `<name>: output missing (<path>)`; an unreadable one gives `error` true and `<name>: unreadable (<exception class>)`; `load_unified` never raises. | repo — `skill/scripts/aidd_graphs.py:200-219` |
| FR-067 | `skill/scripts/graph_explorer.py` becomes the 1371-line F47 explorer with its view unchanged, plus: layer pills, checkboxes, CSS colours and JS layer sets generated from the payload `layers`; working checkbox listeners; the technical-properties block (`insp-tech-details`) of the verified F47 generator, filled with `textContent`; trace rows built with `textContent`; `--root` mode through `unified_graph.load_unified`; `--graph` accepts `.toon` with `--kind` and `--layer`; non-object JSON exits 2. | user — "Archivo de 1.371 líneas + 3 bloques (Recommended)" |
| FR-068 | `aidd graphs explorer` without a name runs the explorer with `--root` and writes `<root>/docs/graphs/explorer.html` (or `--out FILE`); with a name it behaves as today and also passes `--kind` and `--layer`; `--skip` and `--max-mb` pass through; an unknown name still exits 1. | user — "docs/graphs/explorer.html versionado" |
| FR-069 | The generated HTML is self-contained: no `http://`, `https://`, `//cdn`, `<script src`, `<link`, `@import` or `url(` outside the embedded data. | snapshot `explorer/graph_explorer.py:3` |
| FR-070 | Mirrors in `adapters/dot-aidd/scripts/` are byte copies made by `cp`; `unified_graph.py` joins the mirror guard lists; `skill/SKILL.md` G1 and the `aidd graphs` help describe the no-name form, the output path and the size options. | repo — `tests/test_dot_aidd_mirror.py:60-110` |
| FR-071 | The explorer adopts, for every layer, the 8 controls of the approved alias mockup with the mockup's ids: `zoomInBtn`, `zoomOutBtn`, `zoomResetBtn` (the three F47 floating-toolbar buttons re-identified, same place and class), `zoomLevelDisplay` and `fitViewBtn` (added to the same toolbar), `centerNodeBtn` and `copyNodeBtn` (inspector, after the purpose card), `themeToggleBtn` (header, after the PNG export button). | user — "Sí, adoptar todos los controles" |
| FR-072 | Theme: dark (the F47 tokens) by default; `themeToggleBtn` toggles the class `light` on `<html>`; `:root.light` redefines 10 tokens with the mockup's light palette (`--bg-dark` and `--bg-card` `#ffffff`; `--bg-surface`, `--bg-card-hover`, `--bg-input` `#f6f8fa`; `--border-subtle`, `--border-strong` `#d0d7de`; `--text-main` `#1b1f24`; `--text-muted`, `--text-faint` `#667788`); 4 inline `color:#fff` become `var(--text-main)`; the canvas edge and label colours follow the theme. The dark palette stays the F47 one. The choice is remembered in `localStorage` key `aidd-explorer-theme` (`light` or `dark`), every access inside try/catch; with storage blocked the page behaves identically except that the choice is not remembered. | user — "Sí, guardarla en el navegador (Recommended)"; user — "Conservar la paleta de F47 (Recommended)" |
| FR-073 | Copy node writes the focal node as JSON (`id`, `label`, `layer`, `kind`, `type`, `domain`, `metadata`) with `navigator.clipboard.writeText`, falling back to a hidden textarea and `document.execCommand("copy")`; the button shows `Copiado` for 1500 ms (`textContent`); no focal node does nothing. | mockup lines 1200-1208 |
| FR-074 | Zoom keeps the F47 factors (in ×1.25 up to 4.0, out ×0.8 down to 0.2, reset k = 1, x = y = 0); `zoomLevelDisplay` shows `Math.round(k * 100) + "%"` after every render, wheel included; fit places every displayed node inside the canvas with a 40 px margin, k clamped to [0.2, 4.0]; centre puts the focal node at the canvas centre. | user — "Los de F47: x1,25, rango 0,2-4,0 (Recommended)" |
| FR-075 | Test hook: `window.aiddExplorer = {getTransform, getFocalId, selectNode}` (read-only copies; `selectNode(id)` calls the existing `setFocalNode`). | FR-071 testability |
| FR-076 | Size guard (owner chose a versioned file): `graph_explorer.py` gets `--max-mb` (default `25`) and `--skip NAME[,NAME]`; when the HTML would exceed the ceiling it writes nothing, prints the size and the node and edge count per layer, and exits 3. Default unified output: `docs/graphs/explorer.html`. | user — "docs/graphs/explorer.html versionado"; user — "Tope 25 MB, omitiendo code-graphify (Recommended)" |
| FR-077 | Measured visual comparison (T-VISUAL): a script compares the generated page with the F47 Stitch prototype and with the approved alias mockup by selectors, CSS tokens, counts and computed values only; each check is `match`, `differ`, `accepted-differ` (a difference the owner accepted, such as the F47 dark palette) or `not-comparable` with a reason; nothing is judged by eye. | user — "Fila resuelta + comparación medida (Recommended)" |

## Acceptance criteria

| Code | Scenario | Expected |
|---|---|---|
| AC-050 | Synthetic project whose charter declares `db`, `spec`, `ui`, `code` | layer names equal the names of `load_registry(root)`, in that order; `by_layer` = db 3, spec 1, ui 1, code 1 |
| AC-051 | Add a charter row `widgets` (kind `widgets`, JSON output with one node) | layer `widgets` with 1 node, colour `EXTRA_COLOURS[0]`; the HTML has `metric-widgets`, `layer-cb-widgets` and `--layer-widgets`; no code change |
| AC-052 | Add a charter row `notes` with a `.toon` of an unknown kind (2 rows) | layer `notes` with 2 nodes whose labels are the `title` column |
| AC-053 | Cross links on the fixture | `ui:COMP-001 -> spec:001-orders references`, `spec:001-orders -> db:table:ORDR mentions`, `spec:001-orders -> code:app/orders.py mentions`; no edge to the column `status` nor to the table `OCRD` |
| AC-054 | Neighbourhood from `db:table:ORDR` | radius 1 = 3 nodes, radius 2 = 5 nodes and contains radius 1; focal `zzz` gives no nodes and focal `None` |
| AC-055 | Filters | layer `db` only gives 3 nodes all in `db`; domain `sales` gives 2 nodes; edges only between kept nodes |
| AC-056 | `code.json` deleted and `db.json` = `{not json` | no exception; `code` layer `missing`, `db` layer `error`, both warnings present, other layers loaded |
| AC-057 | `aidd_graphs.main(["--root", R, "explorer"])` | exit 0, `R/docs/graphs/explorer.html` exists; `explorer db` writes `R/.aidd/graphs/db.html` with one layer `db`; `explorer nope` exits 1 |
| AC-058 | Generated HTML | FR-069 holds; no `innerHTML = \`` template built from data |
| AC-059 | Generated HTML for the four F47 layers | the 32 static F47 element ids, `insp-tech-details`, and the pill and checkbox markup of `db` byte-equal to the F47 lines 394 and 441; checkbox listeners call `activeLayers.add(` and `activeLayers.delete(` |
| AC-060 | `tests/test_graph_explorer.py` | 9 passed after only the id or key updates listed in T-74 |
| AC-061 | Mirrors | `tests/test_dot_aidd_mirror.py` green with `unified_graph.py` in both lists |
| AC-062 | Generated HTML, unified (4 layers) and single-graph | each of the 8 control ids of FR-071 appears exactly once; `:root.light` defines the 10 FR-072 tokens with those values; `btn-zoom-in`, `btn-zoom-out`, `btn-zoom-reset` no longer appear |
| AC-063 | Headless browser on the synthetic page (skipped when Playwright or Chromium is absent) | zoom in 100% → 125%; zoom out from 100% → 80%; reset → 100%; fit → display between 20% and 400%; after `selectNode` and centre the focal node is within 1 px of the canvas centre; copy → clipboard JSON with the focal `id`; theme → computed `--bg-dark` `#ffffff`, then `#091016` again; after choosing light and reloading, the page opens light; with `localStorage` blocked (getter throws) the toggle still works, no page error, and a reload opens dark; 0 requests to a non-`file:` URL |
| AC-064 | `--max-mb 0.001` on the fixture | exit 3, no file written, message with bytes and per-layer counts; `--skip db` removes layer `db` from the payload; the default ceiling is 25 MB |
| AC-065 | `graph_explorer.main(["--root", R])` without `--out` | writes `R/docs/graphs/explorer.html` |
| AC-066 | T-VISUAL report | JSON with every check `match`, `differ`, `accepted-differ` or `not-comparable`; 0 `differ` among the required checks of T-VISUAL; the dark-palette difference is `accepted-differ`; every other difference listed with its measured values |

## Verification

| # | Command | Expected | Covers |
|---|---|---|---|
| V-1 | `python -m unittest discover -s tests -p "test_unified_graph.py" -v` | exit 0 (10 tests) | T-70, T-71, T-72, AC-050..AC-056 |
| V-2 | `python -m unittest discover -s tests -p "test_unified_explorer.py" -v` | exit 0 (11 tests) | T-73, T-75, T-76, T-77, T-84, AC-051, AC-057..AC-059, AC-064, AC-065 |
| V-3 | `python -m pytest tests/test_graph_explorer.py -q` | `9 passed` | T-74, T-75, T-76, AC-060 |
| V-4 | `python -m unittest discover -s tests -p "test_explorer_controls*.py" -v` | exit 0 (browser tests may report `skipped`, never `failed`) | T-80..T-83, AC-062, AC-063 |
| V-5 | `python -m pytest tests/test_aidd_graphs.py tests/test_graphs_auto.py -q` | 0 failed (no regression) | T-77 |
| V-6 | `python -m unittest tests.test_dot_aidd_mirror -v` | exit 0 | T-78, AC-061 |
| V-7 | `python skill/scripts/unified_graph.py --root . --json` | exit 0; the `layers` names equal the names printed by `python skill/scripts/aidd_graphs.py list` | FR-060 on the real AIDD repo |
| V-8 | `python skill/scripts/aidd_graphs.py explorer` | exit 0, prints the path of `docs/graphs/explorer.html` | FR-068 |
| V-9 | `python tests/visual_compare_explorer.py` | exit 0; JSON report on stdout | T-VISUAL, AC-066 |

Synthetic temporary directories only; no database, Docker or network; `db_verify.py` and `aidd verify` are never run by a builder.

## Visual debt (row to add to spec 004 at integration — owner decision Q-4)

| Codes | Blocks spec | Status | Mockup source |
|---|---|---|---|
| SCREEN-95 (b1SycLink F47 code, view base) | 004-aidd-graph-first | resolved — measured by T-VISUAL | `batch-staging/f47-port-sources/f47-spec/prototype/stitch-SCREEN-95.html` (sha256 in the sibling `.sha256`; same bytes as b1SycLink `specs/F47-Unified-Knowledge-Graph-Explorer/prototype/`) |
| SCREEN-901 (spec 007, adopted controls) | 004-aidd-graph-first | resolved — measured by T-VISUAL | `specs/007-aidd-review-html-close-gate/prototypes/alias-graph-explorer/alias-graph-explorer.html` (sha256 `33bd7fb7…d8d7` in `alias-graph-explorer.sha256`) |

Known facts for the owner: F47 closed with unit tests and a build only (no screenshot comparison); the 1371-line base is a subset
of the verified generator view (20 elements exist only there: domain chips, impact mode, layout select, relayout, minimap
toggle and frame, canvas tooltip, quick hubs, layer counters and badges, the kbd hint, the inspector layer pill, trace counter).
T-VISUAL lists them as `differ`; they are not adopted (owner decision Q-1).

## Interaction with amendment 06 to spec 007 (alias graph)

Amendment 06 was re-based on this draft on 2026-11-03: its T-42 is gone (superseded by T-74..T-76 here), its T-38 keeps only
the alias-specific view, it registers `TOON_READERS["aliases"]`, and it adds no control (FR-071..FR-075 here). Its waves start
after wave 10 of this amendment.

## Out of scope

Building or refreshing any graph (`build_graph.py`, the 23 MB `explorer.html`); any project domain map; translating the Spanish
UI strings (owner decision Q-2); the 20 generator-only controls (Q-1); the alias layer view (amendment 06); a git-ignore rule for
the output (owner decision Q-3: versioned); the mockup's dark palette (owner kept F47's); editing b1SycLink.

## Open questions

None: Q-1..Q-7, the controls, the dark palette and the theme memory were answered by the owner on 2026-11-03 (`## Owner decisions`).

---

# Tasks — amendment unified explorer

Every task prompt restates: scope in and out exactly as written; stop and report on any ambiguity; stdlib only (Playwright
only in the skipped-when-absent browser tests and the T-VISUAL script); one responsibility per function; snake_case with a
leading underscore for module-private helpers; design for failure (every file read in
`try/except (OSError, UnicodeDecodeError, ValueError)`); tool-first (copies by `cp`, bulk text changes by a script with dry-run,
apply and post-check, never by hand); no databases, no Docker, no network; the builder never runs `aidd verify` or `db_verify.py`.
**UI rule:** the view is the F47 view ported unchanged (logic and view); only the layer elements are generated and the 8 mockup
controls are added.

| Task | Codes satisfied | Target file | View / logic | Deps | Explicitly out of scope |
|---|---|---|---|---|---|
| T-70 | FR-060..FR-066, AC-050..AC-056 | `tests/test_unified_graph.py` | LOGIC | none | any production code |
| T-71 | FR-060, FR-061, FR-062, FR-064 | `skill/scripts/unified_graph.py` | LOGIC | T-70 | linking, loading, neighbourhood, CLI |
| T-72 | FR-060, FR-063, FR-065, FR-066 | `skill/scripts/unified_graph.py` | LOGIC | T-71 | readers and styles of T-71 |
| T-73 | FR-067, FR-068, FR-069, FR-076, AC-051, AC-057..AC-059, AC-064, AC-065 | `tests/test_unified_explorer.py` | LOGIC | T-70 | any production code |
| T-74 | FR-067, AC-060 | `skill/scripts/graph_explorer.py`, `tests/test_graph_explorer.py` | LOGIC and view (copy) | none | any edit of the copied file |
| T-80 | FR-071..FR-075, AC-062 | `tests/test_explorer_controls.py` | LOGIC | T-70 | any production code; browser |
| T-81 | FR-071..FR-075, AC-063 | `tests/test_explorer_controls_browser.py` | LOGIC | T-70 | any production code |
| T-75 | FR-064, FR-067, FR-069, FR-076 | `skill/scripts/graph_explorer.py` (Python side) | LOGIC | T-72, T-74 | the JS block; size guard |
| T-76 | FR-067, FR-069, AC-058, AC-059 | `skill/scripts/graph_explorer.py` (JS and inspector) | LOGIC and view | T-75 | Python functions; controls |
| T-82 | FR-071, FR-074, FR-075 | `skill/scripts/graph_explorer.py` (toolbar controls) | LOGIC and view | T-76, T-80, T-81 | inspector and theme controls |
| T-83 | FR-071, FR-072, FR-073 | `skill/scripts/graph_explorer.py` (inspector controls, theme) | LOGIC and view | T-82 | toolbar controls |
| T-84 | FR-076, AC-064 | `skill/scripts/graph_explorer.py` (`main`) | LOGIC | T-83 | HTML and JS |
| T-77 | FR-068, AC-057 | `skill/scripts/aidd_graphs.py` | LOGIC | T-84 | registry, refresh, show |
| T-78 | FR-070, AC-061 | `adapters/dot-aidd/scripts/`, `tests/test_dot_aidd_mirror.py` | LOGIC | T-77 | any hand edit of a mirrored file |
| T-79 | FR-068, FR-070 | `skill/SKILL.md`, `aidd/cli.py` | LOGIC | T-77 | any other section or help string |
| T-VISUAL | FR-077, AC-066 | `tests/visual_compare_explorer.py` | LOGIC | T-84 | any production file; judgement by eye |

### T-70 — model tests first
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 80k
- Agent role: tests
- Model tier: medium
- Wave: 1

**Detail**
- Goal: encode AC-050..AC-056 as unit tests on a synthetic project, red on the current code.
- Cites: FR-060..FR-066, AC-050..AC-056.
- Depends on: none.
- Read first: `batch-staging/f47-port-sources/model/test_unified_explorer.py` (the 5 F47 tests to rewrite); `skill/scripts/aidd_graphs.py` lines 85-113 and 200-219 (charter table and `load_registry`); `skill/scripts/find_spec.py` lines 250-283; `skill/scripts/component_graph.py` lines 365-395.
- Files to change: `tests/test_unified_graph.py` (new).
- Naming contract: module function `make_project(root, extra_rows=())` returning `Path`; class `UnifiedGraphTests(unittest.TestCase)` with `test_layers_follow_registry`, `test_new_registered_kind_is_a_layer`, `test_unknown_toon_kind_is_a_layer`, `test_layer_colours`, `test_cross_layer_links`, `test_neighbourhood_radius`, `test_layer_and_domain_filtering`, `test_fail_open`, `test_deterministic`, `test_no_project_specific_paths`. Production names exercised: `unified_graph.load_unified(root, names=None, skip=())`, `unified_graph.compute_neighborhood(graph, focal_node_id, hop_radius=2)`, `unified_graph.filter_graph(graph, active_layers=None, active_domains=None)`, `unified_graph.KIND_COLOURS`, `unified_graph.EXTRA_COLOURS`, `aidd_graphs.load_registry(root)`. Payload keys: `summary`, `by_layer`, `layers`, `nodes`, `edges`, `warnings`, `missing`, `error`, `color`, `relation`, `cross_layer`, `focal_node`. Fixture keys and values: node field `source_file`, edge relation `belongs_to`.
- Behaviour:
  1. Put `skill/scripts` on `sys.path` (pattern of `tests/test_graph_explorer.py` line 7).
  2. `make_project(root, extra_rows)` writes into a `tempfile.TemporaryDirectory`: `charter.md` with a `## Graphs` table (header `| Name | Kind | Output | Refresh | Watch |`) and rows `db` (`.aidd/graphs/db.json`), `spec` (`specs/index.toon`), `ui` (`.aidd/graphs/ui.toon`), `code` (`.aidd/graphs/code.json`, refresh `builtin:code`, watch `**/*.py`), then one row per `extra_rows` item `(name, kind, output, text)` whose text is written at `output`.
  3. Fixture files: db JSON with nodes `table:ORDR` (label ORDR, type table, domain sales), `column:ORDR.status` (label status, type column, domain sales), `table:OCRD` (label OCRD, type table) and edge `column:ORDR.status -> table:ORDR` relation `belongs_to`; code JSON with node `app/orders.py` (type FILE, `source_file` the same path); `specs/index.toon` = `version: 4`, `generated: 2026-11-03T00:00:00+00:00`, `specs[1]{id,title,codes,words,tree,graph,files}:` and row `  001-orders,001 — Orders,US-001|FR-001,orders,,,spec.md=1`; `specs/001-orders/spec.md` = `Orders spec. Reads table ORDR, sets status and changes app/orders.py.`; `ui.toon` = `version: 1`, `generated: ...`, `components[1]{id,name,path,pattern,props,slots,consumes,consumers}:` and row `  COMP-001,OrderCard,src/OrderCard.tsx,Atomic,,,,US-001`. This fixture was checked against the real readers on 2026-11-03 (registry = the 4 charter rows, nothing auto-detected).
  4. The 10 tests assert exactly AC-050..AC-056; `test_layer_colours` checks db, code, spec and ui colours equal `KIND_COLOURS` and a row `widgets` gets `EXTRA_COLOURS[0]`, a second extra row `notes` gets `EXTRA_COLOURS[1]`; `test_deterministic` compares `json.dumps(..., sort_keys=True)` of two loads; `test_no_project_specific_paths` asserts the source text of `skill/scripts/unified_graph.py` contains none of `docs/db-graph`, `graphify-out`, `Payroll`, `mobile`, `b1Sy`, `eDoc`, `Nomina`.
- Tests first: this task IS the tests; run the Verify command and keep the red output (ImportError of `unified_graph`).
- Verify: `python -m unittest discover -s tests -p "test_unified_graph.py" -v` → fails before T-71 and T-72, exit 0 after them.
- Do NOT: write production code; read b1SycLink files; use pytest fixtures (stdlib unittest only); assert on counts other than the fixture values.
- Done when: the file exists, 10 tests are collected and all fail or error on the current code.
- Size: ~140 changed lines.
- Open questions: none.

### T-71 — unified_graph part 1: readers, normalisation, styles
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.0
- Tokens (est): 100k
- Agent role: builder
- Model tier: high
- Wave: 2

**Detail**
- Goal: the reading half of the registry-driven model: any registered graph file becomes normalised nodes and edges.
- Cites: FR-060, FR-061, FR-062, FR-064.
- Depends on: T-70.
- Read first: `batch-staging/f47-port-sources/model/unified_graph_model.py` lines 1-63 and 209-308 (logic only, never its paths or domain rules); `skill/scripts/find_spec.py` lines 199-283; `skill/scripts/component_graph.py` lines 365-395; `skill/scripts/graph_explorer.py` lines 23-31.
- Files to change: `skill/scripts/unified_graph.py` (new).
- Naming contract: docstring first line `Registry-driven unified graph model (aidd:FR-060).` and a provenance line naming the snapshot path and sha256 `e834afc297d64fddfad3a44927cd005642bd5f7850f9ec8b81418816fdb10a9c`; `HERE = Path(__file__).resolve().parent`; constants `KIND_COLOURS = {"db": "#00bcd4", "code": "#10b981", "spec": "#a855f7", "ui": "#f59e0b"}`, `EXTRA_COLOURS = ["#ef4444", "#3b82f6", "#ec4899", "#84cc16", "#14b8a6", "#f97316", "#8b5cf6", "#eab308"]`, `KIND_PILL_LABELS = {"db": "BD", "code": "AST", "spec": "Spec", "ui": "UI"}`, `KIND_CHECKBOX_LABELS = {"db": "Base de Datos", "code": "Código AST", "spec": "Specs AIDD", "ui": "Componentes UI"}`, `DOMAIN_FIELDS = ("domain", "origin", "community", "group")`, `DEFAULT_DOMAIN = "Core"`, `REF_FIELDS = ("consumers", "consumes", "refs")`, `CODE_FIELDS = ("codes",)`, `TOON_SECTION_RE = re.compile(r"^([A-Za-z_][\w-]*)\[(\d+)\]\{([^}]*)\}:\s*$")`, `TOON_READERS = {"spec": _read_spec_toon, "ui": _read_ui_toon}`; functions `_sibling(name)` (import a module from `HERE`, `None` on ImportError), `_endpoint(v)`, `layer_id(name) -> str`, `layer_styles(entries) -> list`, `read_graph_file(path, kind) -> dict`, `_read_json(text)`, `_read_spec_toon(text)`, `_read_ui_toon(text)`, `_read_generic_toon(text)`, `normalise(layer, kind, raw, prefix=True) -> tuple`. Style keys `name`, `id`, `kind`, `color`, `label`, `title`. Node keys `id`, `raw_id`, `label`, `layer`, `kind`, `type`, `domain`, `purpose`, `metadata`, `codes`, `refs`; edge keys `source`, `target`, `relation`, `layer`, `cross_layer`.
- Behaviour:
  1. `layer_id`: lower-case, every character outside `a-z`, `0-9`, `-` becomes `-`.
  2. `layer_styles(entries)`: in registry order; when `kind == name` and kind is a key of `KIND_COLOURS`, colour, label and title come from the three KIND dicts; otherwise colour = `EXTRA_COLOURS[k % 8]` with `k` counting such entries from 0, label = title = name.
  3. `read_graph_file(path, kind)`: read UTF-8; suffix `.json` → `_read_json`; suffix `.toon` → `TOON_READERS.get(kind, _read_generic_toon)`; any other suffix → `ValueError`. Every reader takes the text and returns `{"nodes": [...], "edges": [...]}`.
  4. `_read_json`: top level must be a dict, else `ValueError`; edges from `edges`, else `links`.
  5. `_read_spec_toon`: `_sibling("find_spec").loads_index(text)["specs"]`; one node per spec `{"id": spec_id, "label": spec_id, "type": "spec", "purpose": title, "codes": codes}`; no edges. `_read_ui_toon`: `_sibling("component_graph").parse_toon(text)`; node `{"id", "label": name or id, "type": "component", "path", "pattern", "consumers", "consumes"}`; no edges. Missing sibling → `ValueError`.
  6. `_read_generic_toon`: for each line matching `TOON_SECTION_RE`, the following lines that start with two spaces are rows; split on `,` with maxsplit = columns − 1; node id = first cell, label = the cell of the first column named `name`, `title` or `label`, else the id; `type` = section name; other columns as string fields; no edges.
  7. `normalise(layer, kind, raw, prefix=True)`: skip nodes without `id`; label = `label`, `name`, `title` or id; type = `type`, `kind` or `node`; purpose = `purpose`, `description`, `comment` or empty; domain per FR-062 (numbers become strings); `codes` and `refs` from `CODE_FIELDS` and `REF_FIELDS` (lists of strings, or `|`-split strings); `metadata` = remaining scalar fields; edges through `_endpoint`, relation = `relation`, `type`, `kind` or `rel`; drop edges whose ends are not nodes of this layer; with `prefix` true every id becomes `<layer>:<raw id>`.
- Tests first: read the T-70 tests in `tests/test_unified_graph.py` before coding; they stay red until T-72; run `python -m unittest discover -s tests -p "test_unified_graph.py" -v` before and after and report the counts.
- Verify: `python -c "import sys; sys.path.insert(0,'skill/scripts'); import unified_graph as u; print(u.layer_id('Code Graphify'))"` → prints code-graphify, exit 0.
- Do NOT: read fixed project paths; add domain rules or project names; import `graph_explorer`; write files; raise from `normalise`.
- Done when: the module imports with stdlib only and the Verify line prints the expected value.
- Size: ~140 changed lines.
- Open questions: none.

### T-72 — unified_graph part 2: linking, loading, neighbourhood, CLI
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.0
- Tokens (est): 100k
- Agent role: builder
- Model tier: high
- Wave: 3

**Detail**
- Goal: complete the model so `load_unified` returns the layered payload of every registered graph and T-70 is green.
- Cites: FR-060, FR-063, FR-065, FR-066.
- Depends on: T-71.
- Read first: `batch-staging/f47-port-sources/model/unified_graph_model.py` lines 310-523; `skill/scripts/aidd_graphs.py` lines 200-219.
- Files to change: `skill/scripts/unified_graph.py`.
- Naming contract: constants `MENTION_DOCS = ("spec.md", "plan.md", "tasks.md", "data-model.md")`, `MENTION_DB_TYPES = ("table", "view", "function")`, `WORD_RE = re.compile(r"\b[A-Za-z0-9_]{3,64}\b")`, `CODE_PATH_RE = re.compile(r"[\w/.-]+\.(?:py|ts|tsx|js|jsx|dart|sql|cs)\b")`; T-71 functions used here: `layer_styles(entries)`, `normalise(layer, kind, raw, prefix=True)`, `read_graph_file(path, kind)`; functions `link_cross_layers(root, nodes, edges) -> int`, `load_unified(root, names=None, skip=()) -> dict`, `single_layer(raw, layer="graph", kind="graph") -> dict`, `compute_neighborhood(graph, focal_node_id, hop_radius=2) -> dict`, `filter_graph(graph, active_layers=None, active_domains=None) -> dict`, `main(argv=None) -> int` with argparse flags `--root` and `--json`. Payload keys `summary` (`total_nodes`, `total_edges`, `by_layer`), `layers` (style keys plus `count`, `missing`, `error`, `output`), `domains`, `nodes`, `edges`, `warnings`. Relations `references`, `mentions`; cross edge `layer` value `cross`; neighbourhood keys `focal_node`, `hop_radius`, `nodes`, `edges`.
- Behaviour:
  1. `link_cross_layers`: index raw id and every `codes` entry to node ids; for each node and each `refs` value, add `references` to every indexed node of another layer. For each node of kind `spec`, read the `MENTION_DOCS` under `root/specs/<raw_id>/` (missing files ignored); add `mentions` to db-kind nodes with type in `MENTION_DB_TYPES` whose lower-case label is in the lower-case `WORD_RE` words, and to code-kind nodes whose raw id or `metadata.source_file` is in the `CODE_PATH_RE` matches (stripped of `./` and quotes). Deduplicate on source, target, relation; return the number added.
  2. `load_unified(root, names=None, skip=())`: `_sibling("aidd_graphs").load_registry(root)`, keep entries with an `output`, in `names` when given and not in `skip`; styles from `layer_styles`; per entry missing file → FR-066 missing warning; reader or normalise error → FR-066 unreadable warning; then link, sort per FR-062, fill `summary`, `layers[].count` and sorted `domains`. Never raises: a registry failure gives an empty payload with one warning.
  3. `single_layer(raw, layer, kind)`: same payload with one layer, `normalise(..., prefix=False)`, no linking.
  4. `compute_neighborhood` and `filter_graph`: F47 logic of snapshot lines 449-523 with `collections.deque` for the queue; same keys and suffix-match fallback.
  5. `main`: `--root` default the current directory; prints `unified: N nodes, M edges, layers: a=1, b=2` or the payload with `--json`; warnings go to stderr; exit 0.
- Tests first: read `skill/scripts/unified_graph.py` (T-71) and the T-70 tests in `tests/test_unified_graph.py` first; before this task they are red; after it all 10 are green.
- Verify: `python -m unittest discover -s tests -p "test_unified_graph.py" -v` → exit 0, 10 tests OK; `python skill/scripts/unified_graph.py --help` → exit 0.
- Do NOT: change T-71 functions beyond bug fixes the tests reveal (report each); add project-specific domain or path rules; write any file.
- Done when: V-1 and V-7 pass.
- Size: ~140 changed lines.
- Open questions: none.

### T-73 — explorer tests first
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 80k
- Agent role: tests
- Model tier: medium
- Wave: 2

**Detail**
- Goal: encode AC-051, AC-057..AC-059, AC-064 and AC-065 for the explorer and the `explorer` subcommand, red on the current code.
- Cites: FR-067, FR-068, FR-069, FR-076, AC-051, AC-057..AC-059, AC-064, AC-065.
- Depends on: T-70.
- Read first: `batch-staging/f47-port-sources/explorer/graph_explorer.py` lines 380-500 and 1325-1371; `skill/scripts/aidd_graphs.py` lines 1118-1133; `tests/test_graph_explorer.py` lines 1-30.
- Files to change: `tests/test_unified_explorer.py` (new).
- Naming contract: constant `F47_STATIC_IDS` = the 32 ids `active-focus-pill`, `badge-starter-status`, `btn-clear-focus`, `btn-close-inspector`, `btn-export-json`, `btn-export-svg`, `btn-reset-filters`, `canvas-viewport`, `focus-pill-name`, `graph-data`, `hop-radius-slider`, `insp-body`, `insp-domain`, `insp-empty-state`, `insp-id`, `insp-purpose`, `insp-title`, `insp-trace-in`, `insp-trace-out`, `insp-type`, `inspector-drawer`, `lbl-hop-value`, `minimap-canvas`, `network-canvas`, `omnibox-container`, `omnibox-input`, `search-dropdown`, `select-entity`, `select-module`, `select-object`, `select-spec`, `select-table`; helper `payload_of(html)` (regex of `tests/test_graph_explorer.py` `data_of`); class `UnifiedExplorerTests(unittest.TestCase)` with `test_root_mode_builds_all_layers`, `test_f47_layer_markup_unchanged`, `test_new_registered_graph_gets_pill_and_checkbox`, `test_layer_checkboxes_are_wired`, `test_f47_static_ids_present`, `test_self_contained_html`, `test_no_data_innerhtml`, `test_graph_mode_reads_toon`, `test_aidd_graphs_explorer_without_name`, `test_aidd_graphs_explorer_with_name`, `test_size_guard_and_skip`. Imports: `from test_unified_graph import make_project`; production names `graph_explorer.main(argv=None)`, `aidd_graphs.main(argv)`, `load_registry(R)` (alias of `aidd_graphs.load_registry`); CLI flags `--root`, `--out`, `--graph`, `--kind`, `--layer`, `--max-mb`, `--skip`; default path `docs/graphs/explorer.html`.
- Behaviour:
  1. `test_root_mode_builds_all_layers`: `graph_explorer.main(["--root", R])` returns 0, writes `R/docs/graphs/explorer.html`; payload `layers` names equal those of `load_registry(R)`.
  2. `test_f47_layer_markup_unchanged`: the HTML contains `<div class="metric-pill"><span class="dot dot-db"></span>BD <strong id="metric-db">0</strong></div>` and `<label class="layer-cb-item"><input type="checkbox" id="layer-cb-db" checked value="db"> Base de Datos</label>` and the ids `metric-code`, `metric-spec`, `metric-ui`, `layer-cb-code`, `layer-cb-spec`, `layer-cb-ui`.
  3. `test_new_registered_graph_gets_pill_and_checkbox`: with extra row `widgets` the HTML has `id="metric-widgets"`, `id="layer-cb-widgets"` and `--layer-widgets:`.
  4. `test_layer_checkboxes_are_wired`: the HTML contains `activeLayers.add(` and `activeLayers.delete(`.
  5. `test_f47_static_ids_present`: every id of `F47_STATIC_IDS` and `insp-tech-details` appears as `id="..."`.
  6. `test_self_contained_html`: with the `graph-data` script removed, none of `http://`, `https://`, `//cdn`, `<script src`, `<link`, `@import`, `url(` appears.
  7. `test_no_data_innerhtml`: the string ``innerHTML = ` `` (innerHTML assigned from a template literal) does not appear.
  8. `test_graph_mode_reads_toon`: `main(["--graph", ui_toon, "--kind", "ui", "--layer", "ui", "--out", O])` returns 0 and the payload has 1 node with layer `ui`.
  9. `test_aidd_graphs_explorer_without_name`: `aidd_graphs.main(["--root", R, "explorer"])` returns 0 and `R/docs/graphs/explorer.html` exists; with `--out X` the file X exists.
  10. `test_aidd_graphs_explorer_with_name`: `explorer db` returns 0 and `R/.aidd/graphs/db.html` has one layer `db`; `explorer nope` returns 1.
  11. `test_size_guard_and_skip`: `main(["--root", R, "--out", O, "--max-mb", "0.001"])` returns 3 and O does not exist; `main(["--root", R, "--out", O, "--skip", "db"])` returns 0 and the payload has no layer `db`.
- Tests first: this task IS the tests; read `make_project` in `tests/test_unified_graph.py` (T-70) first; run the Verify command and keep the red output.
- Verify: `python -m unittest discover -s tests -p "test_unified_explorer.py" -v` → fails now, exit 0 after T-77.
- Do NOT: write production code; read the snapshot at test time (ids are constants); use the network; edit `tests/test_unified_graph.py`.
- Done when: 11 tests are collected and fail or error on the current code.
- Size: ~150 changed lines.
- Open questions: none.

### T-74 — copy the F47 explorer and update the old assertions
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2
- Kind: LOGIC

**Estimate**
- Effort: Low
- Agent min: 15
- Human ref hours: 0.5
- Tokens (est): 60k
- Agent role: builder
- Model tier: medium
- Wave: 2

**Detail**
- Goal: `skill/scripts/graph_explorer.py` becomes the F47 explorer (logic and view, copied unchanged) and the old tests check its ids.
- Cites: FR-067, AC-060.
- Depends on: none.
- Read first: `batch-staging/f47-port-sources/explorer/graph_explorer.py` lines 1-100 and 1325-1371; `batch-staging/f47-port-sources/explorer/graph_explorer.py.sha256`; `skill/scripts/graph_explorer.py`; `tests/test_graph_explorer.py`.
- Files to change: `skill/scripts/graph_explorer.py`, `tests/test_graph_explorer.py`.
- Naming contract: no new names; the copied file keeps `main(argv=None)`, `build_html(graph_data, title=DEFAULT_TITLE)`, `build_unified_payload(graph, root_dir=None)`, `embed_json(obj)`; the test file keeps every test function name (among them `test_deterministic`, `test_extra_fields_rendered`, `test_group_autodetect`, `test_cli_exit_codes`); old asserted node keys `purpose_source`, `source_location`, `data_type`, `community` are dropped from the key loop.
- Behaviour:
  1. Check the snapshot with `sha256sum -c graph_explorer.py.sha256` inside its folder, then `cp` it over `skill/scripts/graph_explorer.py`; no hand edit.
  2. Write a scratch script with a mapping table (old → new, each must match exactly once; dry-run prints the 9 hits, apply writes, post-check re-counts): `d["group"] == "domain"` → `d["domains"] == ["core", "sync"]`; `by["a"]["weird_field"] == "zz9" and by["b"]["extra_n"] == 7` → the same keys under `["metadata"]`; `"Object.keys(n).sort().forEach(row)"` → `"Object.entries(n.metadata)"`; the 2-line loop over `purpose_source`, `source_location`, `data_type`, `community` → removed; the line asserting `Incoming`, `Outgoing`, `id="q"`, `id="ft"` → asserts `id="insp-trace-in"`, `id="insp-trace-out"`, `id="omnibox-input"`, `id="select-module"`, `id="insp-tech-details"`; `["group"] == "community"` → `["domains"] == ["3", "4"]`; `["group"] == ""` → `["domains"] == ["Core"]`; `.startswith("<!doctype html>")` → `.lower().startswith("<!doctype html>")`; `"MAXR=200" in html` → `"finalNodes.length > 200" in html`. This mapping was measured on a scratch copy on 2026-11-03.
  3. Run the old tests: expected 5 passed, 4 failed (`test_deterministic`, `test_extra_fields_rendered`, `test_group_autodetect`, `test_cli_exit_codes`); those 4 turn green in T-75 and T-76. Report the result and each mapping row as `old -> new`.
- Tests first: run `python -m pytest tests/test_graph_explorer.py -q` before the copy (9 passed), after the copy (6 failed) and after the mapping (4 failed).
- Verify: `python -c "import filecmp,sys; sys.exit(0 if filecmp.cmp('batch-staging/f47-port-sources/explorer/graph_explorer.py','skill/scripts/graph_explorer.py',shallow=False) else 1)"` → exit 0; `python -m pytest tests/test_graph_explorer.py -q` → 5 passed, 4 failed.
- Do NOT: edit the copied explorer; weaken any other assertion; touch the snapshot, the b1SycLink file or `aidd_graphs.py`.
- Done when: the copy is byte-identical and the test counts match step 3.
- Size: ~20 changed lines.
- Open questions: none.

### T-80 — control tests first (static)
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 80k
- Agent role: tests
- Model tier: medium
- Wave: 2

**Detail**
- Goal: encode AC-062 (the 8 adopted controls exist, are wired, and the light theme redefines the tokens) without a browser.
- Cites: FR-071..FR-075, AC-062.
- Depends on: T-70.
- Read first: `specs/007-aidd-review-html-close-gate/prototypes/alias-graph-explorer/alias-graph-explorer.html` lines 1-60, 380-440, 515-560 and 1160-1210; `batch-staging/f47-port-sources/explorer/graph_explorer.py` lines 106-125, 455-470 and 1300-1310.
- Files to change: `tests/test_explorer_controls.py` (new).
- Naming contract: constants `CONTROL_IDS = ("zoomInBtn", "zoomOutBtn", "zoomResetBtn", "zoomLevelDisplay", "fitViewBtn", "centerNodeBtn", "copyNodeBtn", "themeToggleBtn")`, `LIGHT_TOKENS = {"--bg-dark": "#ffffff", "--bg-surface": "#f6f8fa", "--bg-card": "#ffffff", "--bg-card-hover": "#f6f8fa", "--bg-input": "#f6f8fa", "--border-subtle": "#d0d7de", "--border-strong": "#d0d7de", "--text-main": "#1b1f24", "--text-muted": "#667788", "--text-faint": "#667788"}`, `OLD_ZOOM_IDS = ("btn-zoom-in", "btn-zoom-out", "btn-zoom-reset")`; class `ExplorerControlsTests(unittest.TestCase)` with `test_each_control_once_unified`, `test_each_control_once_single_graph`, `test_old_zoom_ids_gone`, `test_controls_are_wired`, `test_light_theme_tokens`, `test_test_hook_present`, `test_self_contained`; helper `light_block(html)` returning the text of the `:root.light` rule; imports `from test_unified_graph import make_project`, `graph_explorer.main(argv=None)`, `graph_explorer.build_html(graph_data, title=DEFAULT_TITLE)`; JS names asserted `window.aiddExplorer`, `classList.toggle("light")`, `navigator.clipboard`.
- Behaviour:
  1. Unified page from `make_project` and single-graph page from `build_html({"nodes": [{"id": "a"}], "edges": []}, "T")`: each id of `CONTROL_IDS` occurs exactly once as `id="..."` in both.
  2. None of `OLD_ZOOM_IDS` occurs.
  3. For each control id the page contains `getElementById("<id>")` (the handler is attached by id).
  4. `light_block(html)` defines each key of `LIGHT_TOKENS` with exactly that value; the page contains `classList.toggle("light")`.
  5. The page contains `window.aiddExplorer` and `navigator.clipboard`.
  6. Self-contained check of FR-069 on both pages.
- Tests first: this task IS the tests; run the Verify command and keep the red output.
- Verify: `python -m unittest discover -s tests -p "test_explorer_controls.py" -v` → fails now, exit 0 after T-83.
- Do NOT: write production code; open a browser; use the network.
- Done when: 7 tests are collected and fail or error on the current code.
- Size: ~110 changed lines.
- Open questions: none.

### T-81 — control tests first (headless browser, measured behaviour)
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.0
- Tokens (est): 100k
- Agent role: tests
- Model tier: high
- Wave: 2

**Detail**
- Goal: prove each control WORKS on a synthetic graph by measured values in a real browser (AC-063), skipped cleanly when no browser is installed.
- Cites: FR-071..FR-075, AC-063.
- Depends on: T-70.
- Read first: `specs/007-aidd-review-html-close-gate/prototypes/alias-graph-explorer/alias-graph-explorer.html` lines 1160-1210; `batch-staging/f47-port-sources/explorer/graph_explorer.py` lines 1060-1100 and 1240-1310.
- Files to change: `tests/test_explorer_controls_browser.py` (new).
- Naming contract: module flag `HAVE_BROWSER` (true when `playwright.sync_api` imports and Chromium launches); class `ExplorerControlsBrowserTests(unittest.TestCase)` decorated `unittest.skipUnless(HAVE_BROWSER, "playwright/chromium not installed")` with `test_zoom_buttons_and_display`, `test_fit_view`, `test_center_on_selected_node`, `test_copy_node`, `test_theme_toggle_changes_tokens`, `test_theme_remembered_after_reload`, `test_theme_works_with_storage_blocked`, `test_no_external_requests`; storage key `aidd-explorer-theme`; init script `add_init_script` that redefines `window.localStorage` with a getter that throws; helper `open_page(html_path)` returning the page; JS hook `window.aiddExplorer.getTransform()`, `window.aiddExplorer.getFocalId()`, `window.aiddExplorer.selectNode(id)`; page events `request`; computed value `getComputedStyle(document.documentElement).getPropertyValue("--bg-dark")`; imports `from test_unified_graph import make_project`, `graph_explorer.main(argv=None)`.
- Behaviour:
  1. Build the unified page of `make_project` with `graph_explorer.main(["--root", R, "--out", O])`; open `file://` O in headless Chromium at 1280×800; record every request whose URL does not start with `file:` (expected 0).
  2. Zoom: initial display text `100%`; click `#zoomInBtn` → `125%`; click `#zoomResetBtn` → `100%`; click `#zoomOutBtn` → `80%`.
  3. Fit: click `#fitViewBtn`; the display value parses to a number between 20 and 400 and `getTransform()` differs from before.
  4. Centre: `selectNode("db:table:ORDR")`, click `#centerNodeBtn`; the focal node's screen position (node x × k + transform x, same for y) is within 1 px of the canvas centre.
  5. Copy: grant `clipboard-read` and `clipboard-write`, select the node, click `#copyNodeBtn`; `navigator.clipboard.readText()` parses as JSON with `id` = `db:table:ORDR`; the button text is `Copiado` right after the click.
  6. Theme: computed `--bg-dark` is `#091016`; after clicking `#themeToggleBtn` it is `#ffffff`; after a second click `#091016` again (compare trimmed, lower-case).
  7. `test_theme_remembered_after_reload`: click `#themeToggleBtn` once, reload the page in the same context; computed `--bg-dark` is `#ffffff` and `localStorage.getItem("aidd-explorer-theme")` is `light`.
  8. `test_theme_works_with_storage_blocked`: new context whose init script makes every `localStorage` access throw; collect `pageerror` events; clicking `#themeToggleBtn` still gives `#ffffff`; after a reload the page opens with `#091016`; 0 page errors.
- Tests first: this task IS the tests; on a machine with Playwright they fail now; record the run.
- Verify: `python -m unittest discover -s tests -p "test_explorer_controls_browser.py" -v` → fails or skips now; after T-83: exit 0 (skipped is allowed only where Playwright is absent).
- Do NOT: write production code; load any non-file URL; add Playwright to `tests/requirements-test.txt`; judge anything by screenshot.
- Done when: 8 tests are collected and fail (or skip without a browser) on the current code.
- Size: ~150 changed lines.
- Open questions: none.

### T-75 — explorer, Python side: registry layers and modes
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.0
- Tokens (est): 120k
- Agent role: builder
- Model tier: high
- Wave: 4

**Detail**
- Goal: the explorer builds its payload with `unified_graph` and generates the layer pills, checkboxes and colours from the registry, with the F47 markup unchanged for the four F47 layers.
- Cites: FR-064, FR-067, FR-069, FR-076.
- Depends on: T-72, T-74.
- Read first: `skill/scripts/graph_explorer.py` lines 1-100, 110-120, 225-235, 390-450 and 1325-1371 (after T-74); `tests/test_graph_explorer.py`.
- Files to change: `skill/scripts/graph_explorer.py` (Python functions, the CSS and the HTML of pills and checkboxes only).
- Naming contract: new helpers `_metric_pills(layers) -> str`, `_layer_checkboxes(layers) -> str`, `_extra_layer_css(layers) -> str`; f-string placeholders `{metric_pills_html}`, `{layer_checkboxes_html}`, `{extra_layer_css}`; new CLI flags `--kind` (default `graph`) and `--layer` (default `graph`); `DEFAULT_UNIFIED_OUT = "docs/graphs/explorer.html"`; kept names `build_unified_payload(graph, root_dir=None)`, `build_html(graph_data, title=DEFAULT_TITLE)`, `main(argv=None)`; calls `unified_graph.load_unified(root, names=None, skip=())`, `unified_graph.single_layer(raw, layer, kind)`, `unified_graph.read_graph_file(path, kind)`.
- Behaviour:
  1. Module top: put the script folder on `sys.path` and `import unified_graph`; the docstring Usage lists `--root DIR`, `--graph FILE [--kind K] [--layer L]`.
  2. `build_unified_payload`: a dict with key `layers` is returned as is; any other dict goes through `unified_graph.single_layer(graph)`; a non-dict raises `ValueError`. The F47 heuristic of snapshot lines 38-46 is deleted.
  3. Pills: replace snapshot lines 394-397 by `{metric_pills_html}`; `_metric_pills` emits per layer, 6-space indent, `<div class="metric-pill"><span class="dot dot-{id}"></span>{label} <strong id="metric-{id}">0</strong></div>` with `html.escape` on the label. Checkboxes: replace lines 441-444 by `{layer_checkboxes_html}`; `_layer_checkboxes` emits, 10-space indent, `<label class="layer-cb-item"><input type="checkbox" id="layer-cb-{id}" checked value="{name}"> {title}</label>`. For the four F47 layers the output equals the original lines byte for byte.
  4. CSS: keep lines 115-119 and 230-233 unchanged (they are theme tokens too); insert `{extra_layer_css}` after the `.dot-ui` rule; `_extra_layer_css` emits `:root {{ --layer-{id}: {color}; }}` and `.dot-{id} {{ background-color: var(--layer-{id}); }}` only for layer ids other than `db`, `code`, `spec`, `ui`.
  5. `main`: with `--graph`: suffix `.toon` → `read_graph_file(path, kind)`; else JSON load; then `single_layer(raw, layer, kind)`; default out `<graph>.html`; any `OSError` or `ValueError` (JSON errors included) → message on stderr and exit 2. Without `--graph`: root = `--root` or the current directory; `load_unified(root)`; warnings to stderr; default out `root / DEFAULT_UNIFIED_OUT` (parent folders created). Print `explorer: N nodes -> OUT (B bytes)` and exit 0.
- Tests first: in `tests/test_graph_explorer.py` the tests deterministic, group autodetect and cli exit codes are red before this task and green after it; read `skill/scripts/unified_graph.py` and `tests/test_unified_explorer.py` first.
- Verify: `python -m pytest tests/test_graph_explorer.py -q` → 8 passed, 1 failed (the extra-fields test, closed by T-76).
- Do NOT: touch the JS block (T-76); change any other CSS rule, string or element; import from `docs`; add the size guard (T-84); add a dependency.
- Done when: the Verify counts match and the T-73 tests root mode, layer markup, new registered graph and graph mode toon pass.
- Size: ~120 changed lines.
- Open questions: none.

### T-76 — explorer, JS side: dynamic layers, listeners, technical properties
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.0
- Tokens (est): 120k
- Agent role: builder
- Model tier: high
- Wave: 5

**Detail**
- Goal: the explorer JS works for any set of registered layers, the layer checkboxes filter the graph, and the inspector shows every metadata field safely.
- Cites: FR-067, FR-069, AC-058, AC-059.
- Depends on: T-75.
- Read first: `skill/scripts/graph_explorer.py` JS block (after T-75); `batch-staging/f47-port-sources/reference/gen_unified_explorer.py` lines 772-775, 1749-1758 and 1828-1840; `batch-staging/f47-port-sources/reference/components/graph_inspector.html` lines 58-63.
- Files to change: `skill/scripts/graph_explorer.py` (JS block, the inspector HTML and 4 CSS rules).
- Naming contract: JS constants `layers`, `LAYER_NAMES`, `layerColor`, `layerDomId`; element id `insp-tech-details`; CSS classes `insp-tech-details`, `tech-row`, `tech-k`, `tech-v` (rules copied from the reference lines 772-775); calls `activeLayers.add(`, `activeLayers.delete(`, `recalculateSubgraph(false)`, `Object.entries(n.metadata)`.
- Behaviour:
  1. Replace the fixed `nodesByLayer` literal by `const layers = rawData.layers || [];`, `LAYER_NAMES` (layer names), `layerColor` and `layerDomId` maps, and a `nodesByLayer` built from `LAYER_NAMES`.
  2. Replace each `new Set(["db", "code", "spec", "ui"])` (3 places) by `new Set(LAYER_NAMES)` and the two `["db", "code", "spec", "ui"].forEach` loops by `layers.forEach` using `"layer-cb-" + l.id`.
  3. Replace the 4 metric lines by one loop over `layers` setting `"metric-" + l.id`; `getNodeColor(layer)` returns `layerColor.get(layer) || "#94a3b8"`.
  4. Add, after the reset handler, one `change` listener per layer checkbox: checked → `activeLayers.add(l.name)`, else `activeLayers.delete(l.name)`; then `recalculateSubgraph(false)` (logic taken from reference lines 1828-1840).
  5. With a script (dry-run, apply, post-check): replace the 26 occurrences of `.layer === "db|code|spec|ui"` on `n`, `n2`, `ent`, `focalNode` by `.kind === ` with the same literal; the post-check counts 0 left and 26 new.
  6. Inspector: after the `insp-trace-out` card add the card title `Propiedades Técnicas` and `<div class="insp-tech-details" id="insp-tech-details"></div>` (reference component lines 58-63); in `setFocalNode` fill it from `Object.entries(n.metadata)` skipping empty values, building `tech-row` with `tech-k` and `tech-v` spans through `textContent` (never `innerHTML`).
  7. The two trace rows that set `row.innerHTML` from a template literal are rebuilt with two spans and `textContent`, same style attribute.
- Tests first: the extra-fields test and the T-73 tests wired checkboxes, static ids and no data innerHTML are red before this task.
- Verify: `python -m pytest tests/test_graph_explorer.py -q` → 9 passed; `python -m unittest discover -s tests -p "test_unified_explorer.py" -v` → only the two aidd-graphs explorer tests and the size-guard test still fail.
- Do NOT: add any control of the reference generator beyond the three blocks named here; add the 8 mockup controls (T-82, T-83); change strings, colours or layout of other elements; touch Python functions of T-75.
- Done when: both Verify results match.
- Size: ~110 changed lines.
- Open questions: none.

### T-82 — adopted controls: toolbar zoom, zoom level, fit, test hook
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2
- Kind: VIEW-new

**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.0
- Tokens (est): 100k
- Agent role: builder
- Model tier: high
- Wave: 6

**Detail**
- Goal: the floating toolbar carries the mockup's zoom controls with the mockup ids, a live zoom level and fit view, for every layer.
- Cites: FR-071, FR-074, FR-075.
- Depends on: T-76, T-80, T-81.
- Read first: `specs/007-aidd-review-html-close-gate/prototypes/alias-graph-explorer/alias-graph-explorer.html` lines 428-440, 1000-1008 and 1160-1190; `skill/scripts/graph_explorer.py` (after T-76) the `.floating-toolbar` rule, the toolbar markup and the three zoom handlers.
- Files to change: `skill/scripts/graph_explorer.py` (toolbar markup, its handlers, `render`, the test hook).
- Naming contract: element ids `zoomInBtn`, `zoomOutBtn`, `zoomResetBtn`, `zoomLevelDisplay`, `fitViewBtn`; JS functions `updateZoomDisplay()`, `fitView()`; constants `ZOOM_MIN = 0.2`, `ZOOM_MAX = 4.0`, `FIT_MARGIN = 40`; hook `window.aiddExplorer = {getTransform, getFocalId, selectNode}` (functions `getTransform()`, `getFocalId()`, `selectNode(id)`); existing names used `transform`, `displayNodes`, `render()`, `setFocalNode(id, maintainScale)`.
- Behaviour:
  1. Toolbar markup, in order, class `tool-btn` on each: `zoomOutBtn` (label `-`), `zoomLevelDisplay` (a `span`, text `100%`), `zoomInBtn` (label `+`), `zoomResetBtn` (label `1:1`), `fitViewBtn` (label `Ajustar`, title `Ajustar a la vista`). The ids `btn-zoom-in`, `btn-zoom-out`, `btn-zoom-reset` disappear (re-identified, same F47 handlers).
  2. Handlers: in → `transform.k = Math.min(transform.k * 1.25, ZOOM_MAX)`; out → `Math.max(transform.k * 0.8, ZOOM_MIN)`; reset → `transform = {x: 0, y: 0, k: 1.0}`; each calls `render()`.
  3. `updateZoomDisplay()` sets `zoomLevelDisplay.textContent = Math.round(transform.k * 100) + "%"`; it is the last statement of `render()`, so the wheel updates it too.
  4. `fitView()`: bounds of `displayNodes` (x, y); k = min((width − 2 × FIT_MARGIN) / max(1, bounds width), (height − 2 × FIT_MARGIN) / max(1, bounds height)) clamped to [ZOOM_MIN, ZOOM_MAX]; translate so the bounds centre is the canvas centre; `render()`. No nodes → nothing.
  5. Test hook: `getTransform()` returns a copy of `transform`, `getFocalId()` returns `focalNodeId`, `selectNode(id)` calls `setFocalNode(id, false)`.
- Tests first: the T-80 tests for these ids and the T-81 zoom and fit tests are red before this task.
- Verify: `python -m unittest discover -s tests -p "test_explorer_controls*.py" -v` → zoom, fit, ids-once and old-ids tests pass; `python -m pytest tests/test_graph_explorer.py -q` → 9 passed.
- Do NOT: add the centre, copy or theme controls (T-83); change the wheel factors; restyle the toolbar beyond the two new elements; use `innerHTML`.
- Done when: both Verify results match.
- Size: ~70 changed lines.
- Open questions: none.

### T-83 — adopted controls: centre, copy node, light or dark theme
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2
- Kind: VIEW-new

**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.0
- Tokens (est): 110k
- Agent role: builder
- Model tier: high
- Wave: 7

**Detail**
- Goal: the inspector carries centre and copy, the header carries the theme toggle, and the light theme redefines the explorer tokens from the mockup's light palette.
- Cites: FR-071, FR-072, FR-073.
- Depends on: T-82.
- Read first: `specs/007-aidd-review-html-close-gate/prototypes/alias-graph-explorer/alias-graph-explorer.html` lines 1-60, 380-390, 515-530, 540-560 and 1190-1210; `skill/scripts/graph_explorer.py` (after T-82) the `:root` tokens, the header buttons, the inspector purpose card, `setFocalNode` and `render`.
- Files to change: `skill/scripts/graph_explorer.py` (inspector and header markup, `:root.light` rule, handlers, two canvas colours, four inline colours).
- Naming contract: element ids `centerNodeBtn`, `copyNodeBtn`, `themeToggleBtn`; CSS rule `:root.light` with the 10 tokens of FR-072; JS functions `centerOnFocal()`, `copyFocalNode()`, `toggleTheme()`, `isLightTheme()`, `loadThemeChoice()`, `saveThemeChoice(theme)`; constant `THEME_KEY = "aidd-explorer-theme"`; class name `light`; button feedback text `Copiado`; labels `Centrar nodo`, `Copiar nodo`, `Tema`; CSS class `btn-icon` (existing) for the header button; existing functions used `render()`, `setFocalNode(id, maintainScale)`.
- Behaviour:
  1. Markup: `themeToggleBtn` (class `btn-icon`, label `Tema`) right after `btn-export-svg`; a new `insp-card` after the purpose card with `centerNodeBtn` and `copyNodeBtn` (class `btn-text-xs`).
  2. `toggleTheme()`: `document.documentElement.classList.toggle("light")`, then `saveThemeChoice(isLightTheme() ? "light" : "dark")`, then `render()`; `isLightTheme()` reads that class. `saveThemeChoice` writes `localStorage[THEME_KEY]` inside try/catch (any error ignored). At start, before the first render, `loadThemeChoice()` reads the key inside try/catch and adds the class `light` only when the value is exactly `light`; any error or other value keeps dark.
  3. CSS: add `:root.light {{ ... }}` right after the `:root` rule with the 10 FR-072 tokens and values; replace the 4 inline `color:#fff` of `focus-pill-name`, `btn-clear-focus`, `insp-title`, `btn-close-inspector` by `color:var(--text-main)` with a script (dry-run lists 4 hits, post-check 1 left: the `badge-starter-status` badge on its teal gradient keeps `#fff`).
  4. Canvas: in `render`, when `isLightTheme()` the non-cross edge colour is `rgba(27, 31, 36, 0.15)` and labels `#1b1f24` (focal label `#0b5cad`); otherwise the current values.
  5. `centerOnFocal()`: no focal → return; translate so the focal display node sits at the canvas centre at the current k; `render()`.
  6. `copyFocalNode()`: no focal → return; text = `JSON.stringify` of `id`, `label`, `layer`, `kind`, `type`, `domain`, `metadata`; `navigator.clipboard.writeText(text)` when available, else a hidden `textarea` with `document.execCommand("copy")`; set the button `textContent` to `Copiado` and restore the label after 1500 ms.
- Tests first: the T-80 tests light tokens and wired controls and the T-81 centre, copy and theme tests are red before this task.
- Verify: `python -m unittest discover -s tests -p "test_explorer_controls*.py" -v` → exit 0 (browser tests skipped only without Playwright); `python -m pytest tests/test_graph_explorer.py -q` → 9 passed.
- Do NOT: change the dark tokens; use any storage other than that one `localStorage` key; let a storage error reach the page; use `innerHTML`; add icons from a CDN; touch the toolbar controls of T-82.
- Done when: both Verify results match.
- Size: ~105 changed lines.
- Open questions: none.

### T-84 — size guard and skip option
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2
- Kind: LOGIC

**Estimate**
- Effort: Low
- Agent min: 15
- Human ref hours: 0.5
- Tokens (est): 60k
- Agent role: builder
- Model tier: medium
- Wave: 8

**Detail**
- Goal: a versioned explorer never silently grows past the owner's ceiling.
- Cites: FR-076, AC-064.
- Depends on: T-83.
- Read first: `skill/scripts/graph_explorer.py` `main` (after T-83).
- Files to change: `skill/scripts/graph_explorer.py` (`main` and one helper only).
- Naming contract: constant `DEFAULT_MAX_MB = 25`; CLI flags `--max-mb` (float, default `DEFAULT_MAX_MB`) and `--skip` (comma-separated names); helper `_size_report(payload, nbytes) -> str`; exit code `3`; existing `build_html(graph_data, title=DEFAULT_TITLE)`; call `unified_graph.load_unified(root, names=None, skip=())`.
- Behaviour:
  1. `--skip` splits on `,`, strips, drops empties, and is passed as `skip` to `load_unified` (ignored in `--graph` mode).
  2. After `build_html`, if the UTF-8 byte length exceeds `max_mb × 1,000,000`: print to stderr `explorer: B bytes > ceiling C MB; nothing written` and `_size_report` (one line per layer `name: N nodes`, plus total edges), then return 3 without writing.
  3. Otherwise write and print as before.
- Tests first: T-73 `test_size_guard_and_skip` is red before this task.
- Verify: `python -m unittest discover -s tests -p "test_unified_explorer.py" -v` → only the two aidd-graphs explorer tests still fail.
- Do NOT: change HTML or JS; truncate or sample the graph; write a partial file.
- Done when: the size-guard test passes.
- Size: ~30 changed lines.
- Open questions: none.

### T-77 — `aidd graphs explorer` without a name
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2
- Kind: LOGIC

**Estimate**
- Effort: Low
- Agent min: 15
- Human ref hours: 0.5
- Tokens (est): 60k
- Agent role: builder
- Model tier: medium
- Wave: 9

**Detail**
- Goal: no name builds the unified explorer at `docs/graphs/explorer.html`; a name keeps today's behaviour with the layer kind passed through.
- Cites: FR-068, AC-057.
- Depends on: T-84.
- Read first: `skill/scripts/aidd_graphs.py` lines 20-35 and 1053-1142; `tests/test_aidd_graphs.py` lines 215-235.
- Files to change: `skill/scripts/aidd_graphs.py`.
- Naming contract: no new public names; local `name` in the `explorer` branch; subprocess flags `--root`, `--out`, `--graph`, `--kind`, `--layer`, `--max-mb`, `--skip`; default unified path `docs/graphs/explorer.html`.
- Behaviour:
  1. Change the condition `cmd == "explorer" and rest` to `cmd == "explorer"`; `name` = `rest[0]` when `rest` is non-empty and `rest[0]` does not start with `--`, else none.
  2. With a name: unchanged lookup and exit 1 for an unknown name; the subprocess gets in addition `--kind`, the entry kind or `graph`, and `--layer`, the entry name.
  3. Without a name: out = `--out` value or `root/docs/graphs/explorer.html`; run the explorer with `--root` and `--out`, passing `--max-mb` and `--skip` through when given; print the out path when the exit code is 0; return that code (3 included).
  4. Docstring Usage line: `aidd_graphs.py explorer [name] [--out FILE] [--skip A,B] [--max-mb N]   (no name: unified explorer of every registered graph, docs/graphs/explorer.html)`.
- Tests first: the two aidd-graphs explorer tests of T-73 are red before this task.
- Verify: `python -m unittest discover -s tests -p "test_unified_explorer.py" -v` → exit 0; `python -m pytest tests/test_aidd_graphs.py tests/test_graphs_auto.py -q` → 0 failed.
- Do NOT: touch `load_registry`, refresh, status or `show`; change the exit code 2 of a call without a subcommand; add a git-ignore rule.
- Done when: both Verify results match and V-8 prints the path.
- Size: ~30 changed lines.
- Open questions: none.

### T-78 — mirrors
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC

**Estimate**
- Effort: Low
- Agent min: 5
- Human ref hours: 0.25
- Tokens (est): 20k
- Agent role: builder
- Model tier: low
- Wave: 10

**Detail**
- Goal: `adapters/dot-aidd/scripts/` carries byte copies of the three changed scripts and the guard test knows the new module.
- Cites: FR-070, AC-061.
- Depends on: T-77.
- Read first: `tests/test_dot_aidd_mirror.py` lines 55-110 and 390-408.
- Files to change: `adapters/dot-aidd/scripts/unified_graph.py`, `adapters/dot-aidd/scripts/graph_explorer.py`, `adapters/dot-aidd/scripts/aidd_graphs.py`, `tests/test_dot_aidd_mirror.py`.
- Naming contract: list constants `VERBATIM_SCRIPTS` and `GRAPH_FIRST_SCRIPTS` each gain the entry `"unified_graph.py"` (after `"graph_explorer.py"` and after `"component_graph.py"` respectively).
- Behaviour: three `cp` commands from `skill/scripts/` to `adapters/dot-aidd/scripts/`; then the two one-line list insertions; no other edit.
- Tests first: before the copies the mirror test fails on `graph_explorer.py` and `aidd_graphs.py` drift.
- Verify: `python -m unittest tests.test_dot_aidd_mirror -v` → exit 0.
- Do NOT: hand-edit any mirrored file; touch `build/`; change other list entries.
- Done when: the mirror test is green.
- Size: ~2 changed lines (plus 3 copies).
- Open questions: none.

### T-79 — documentation
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC

**Estimate**
- Effort: Low
- Agent min: 5
- Human ref hours: 0.25
- Tokens (est): 20k
- Agent role: docs
- Model tier: low
- Wave: 10

**Detail**
- Goal: the skill and the CLI help describe the unified explorer, its versioned path and the size options.
- Cites: FR-068, FR-070.
- Depends on: T-77.
- Read first: `skill/SKILL.md` lines 286-295; `aidd/cli.py` lines 430-440.
- Files to change: `skill/SKILL.md`, `aidd/cli.py`.
- Naming contract: no code names; help text `explorer [name]`.
- Behaviour:
  1. In SKILL.md G1 item 1 replace the sentence "`aidd graphs explorer <name>` writes a single-file HTML explorer for the owner." by: "`aidd graphs explorer <name>` writes a single-file HTML explorer of one graph; `aidd graphs explorer` with no name writes `docs/graphs/explorer.html` (versioned), the unified explorer of every registered graph: each graph is a layer with its own colour, count and checkbox, and a graph added to the registry appears there with no code change. Above 25 MB nothing is written (exit 3): pass `--skip <name>` or `--max-mb N`; every regeneration adds a blob to git history, so regenerate on demand only."
  2. In `aidd/cli.py` change `explorer <name>` to `explorer [name]` in the `graphs` help string only.
- Tests first: none needed beyond the existing guard `python -m unittest tests.test_dot_aidd_mirror -v` (docs vocabulary test).
- Verify: `python -m unittest tests.test_dot_aidd_mirror -v` → exit 0.
- Do NOT: edit other sections, other help strings or any other doc.
- Done when: both texts are changed and the guard is green.
- Size: ~2 changed lines.
- Open questions: none.

### T-VISUAL — measured comparison with the two mockups
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 30
- Human ref hours: 1.0
- Tokens (est): 120k
- Agent role: verifier
- Model tier: high
- Wave: 10

**Detail**
- Goal: compare the generated page with the F47 Stitch prototype and the approved alias mockup by measured values only, and report every difference.
- Cites: FR-077, AC-066.
- Depends on: T-84.
- Read first: `batch-staging/f47-port-sources/f47-spec/prototype/stitch-SCREEN-95.html` (its `tailwind-config` script and fonts); `batch-staging/f47-port-sources/f47-spec/mockup-audit.md`; `specs/007-aidd-review-html-close-gate/prototypes/alias-graph-explorer/alias-graph-explorer.html` lines 1-60 and 380-560; `specs/007-aidd-review-html-close-gate/prototypes/alias-graph-explorer/alias-graph-explorer.sha256`.
- Files to change: `tests/visual_compare_explorer.py` (new script, not a test module).
- Naming contract: functions `check_sha(path, sha_file) -> bool`, `mockup_tokens(html) -> dict`, `prototype_colours(html) -> set`, `page_measures(page) -> dict`, `compare() -> dict`, `main() -> int`; report keys `checks` (each `id`, `source`, `kind`, `expected`, `actual`, `status`, `reason`, `required`) and `summary` (`match`, `differ`, `not_comparable`, `required_differ`); `kind` values `selector`, `token`, `count`, `computed`; `status` values `match`, `differ`, `accepted-differ`, `not-comparable`; constants `PROTOTYPE = "batch-staging/f47-port-sources/f47-spec/prototype/stitch-SCREEN-95.html"`, `ALIAS_MOCKUP = "specs/007-aidd-review-html-close-gate/prototypes/alias-graph-explorer/alias-graph-explorer.html"`; fixture import `from test_unified_graph import make_project` (`tests` on `sys.path`).
- Behaviour:
  1. Verify both mockup files against their sha256 files; a mismatch is a required `differ`.
  2. Build the page of a synthetic project (same fixture as `make_project` in `tests/test_unified_graph.py`) in a temporary folder with `graph_explorer.main`; open it headless with Playwright (no network; non-file requests are a required `differ`).
  3. Alias mockup, required checks: each of the 8 FR-071 ids present once (`selector`); the 10 light tokens computed after clicking `themeToggleBtn` equal the mockup's light values of FR-072 (`computed`); zoom display text `100%` at start (`computed`).
  4. Alias mockup, reported but not required: the mockup dark tokens against the F47 dark tokens (`token`, status `accepted-differ`, reason "owner kept the F47 dark palette, 2026-11-03"); zoom step and range (mockup ×1.15, 0.4 to 2.5; page ×1.25, 0.2 to 4.0; status `accepted-differ`, reason "owner kept the F47 zoom"); the alias-only ids (`aliasCountText`, `stat-counts`, `detailScope`, `detailReason`, `emptyBanner`, legend) as `not-comparable`, reason "alias layer: amendment 06".
  5. F47 prototype, required checks: the colour `#00677c` is the computed `--layer-db-dark`; the page fonts include `Roboto Flex` and `JetBrains Mono` (`computed` on `--font-sans` and `--font-mono`). Reported: every other hex of the prototype's `tailwind-config` present or absent among the page tokens (`token`), and the 20 generator-only elements listed in `## Visual debt` as `differ`, reason "owner decision Q-1".
  6. Layout, spacing and canvas pixels are `not-comparable` with reason "different DOM; no pixel judgement".
  7. Print the report as JSON (sorted keys) on stdout; exit 0 when `required_differ` is 0, else 1; without Playwright print one `not-comparable` check and exit 2.
- Tests first: the script is the measuring tool; run it once before T-82 to record that the 8 control ids are `differ`.
- Verify: `python tests/visual_compare_explorer.py` → exit 0, required_differ 0 in the printed JSON.
- Do NOT: judge by screenshot or by eye; edit any production file or mockup; call Stitch; write into `specs/` (the coordinator archives the printed report as evidence).
- Done when: the report runs, all required checks match, and every non-required difference is listed for the owner.
- Size: ~140 changed lines.
- Open questions: none.

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-70 | tests | 20 | 80 | 1 |
| 2 | T-71, T-73, T-74, T-80, T-81 | builder, tests | 25 | 420 | 4.5 |
| 3 | T-72 | builder | 25 | 100 | 1 |
| 4 | T-75 | builder | 25 | 120 | 1 |
| 5 | T-76 | builder | 25 | 120 | 1 |
| 6 | T-82 | builder | 25 | 100 | 1 |
| 7 | T-83 | builder | 25 | 110 | 1 |
| 8 | T-84 | builder | 15 | 60 | 0.5 |
| 9 | T-77 | builder | 15 | 60 | 0.5 |
| 10 | T-78, T-79, T-VISUAL | builder, docs, verifier | 30 | 160 | 1.5 |

Total agent time (critical path): 230 min
Total tokens (k): 1330
Total human reference hours: 13
Tasks: 16 in 10 waves (computed by `waves.py` in the scratchpad from the task blocks). Waves 4..9 edit the same file
`skill/scripts/graph_explorer.py` and are strictly sequential; no two tasks of one wave touch the same file.
