# Tasks — F47 Unified Knowledge Graph Explorer

One row = one small PR. Same rubric as the requirements-analysis workflow this borrows its task
format from: classify → estimate → decompose → assign, then present as a dry-run and wait for
approval before anything gets written.

Tasks reference the single pre-build coherence audit (spec, plan, graph, estimates) that runs before this list is approved; there is no per-edit audit.
Sources: `spec.md`, `plan.md`, `mockup-audit.md` (SCREEN-95, COMP-901..COMP-910, CTL-135001..CTL-135025) and Stitch prototype `stitch-SCREEN-95.png` / `stitch-SCREEN-95.html`.

**Every task's implementation prompt restates these standards explicitly — a fresh agent doesn't inherit them from context:**
- **Scope: in and out, both stated explicitly.** In scope = exactly the codes and target file(s) this row names, nothing else. Out of scope = everything else.
- **SOLID** on any code touched.
- **One class per file** — never bundle several classes into one file.
- **Naming & File Contract from `plan.md`** — snake_case for Python modules and functions, PascalCase for classes.
- **Antifragile / Design for Failure** — handle missing or partial graph files gracefully with clear warnings, never crashing.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Explicitly out of scope |
|---|---|---|---|---|
| T-01 | FR-001, FR-005 | `docs/db-graph/unified_graph_model.py` | LOGIC | UI HTML template; build_graph.py; any application code |
| T-02 | FR-001, FR-002, FR-004, FR-005, AC-001, AC-002, AC-003, AC-004 | `docs/db-graph/test_unified_explorer.py` | LOGIC | production HTML generator; any other test file |
| T-03 | SCREEN-95, COMP-901..COMP-910, CTL-135001..CTL-135025, FR-002..FR-008, AC-005 | `docs/db-graph/gen_unified_explorer.py` | LOGIC | schema introspection scripts; postgres container |
| T-04 | FR-001, FR-007 | `docs/db-graph/build_graph.py` | LOGIC | modifying database tables or SQL migrations |
| T-05 | SCREEN-95, COMP-901..COMP-910, AC-005 | `docs/db-graph/explorer.html` | VIEW-new | legacy DB-only explorer; external network calls |

## Per-task detail (one block per row above)

### T-01
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 350k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: Crear el módulo `unified_graph_model.py` que cargue y fusione los 4 grafos (`docs/db-graph/graph.json`, `.aidd/graphs/code.json`, `specs/index.toon`, `.aidd/graphs/ui.toon`) en una estructura relacional unificada en memoria.
- Activities:
  1. Parser de nodos y aristas de cada archivo fuente normalizando tipos e identificadores.
  2. Indexador de trazabilidad cruzada (Cross-Graph Trace) que enlace tablas BD con funciones backend, specs y componentes UI.
  3. Algoritmo de cálculo de subgrafo por radio de saltos (Hop Radius 1..5) desde un nodo focal.

### T-02
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 300k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: Crear la suite de pruebas unitarias `test_unified_explorer.py` para garantizar la integridad de la unificación de grafos y filtros.
- Activities:
  1. Prueba de carga y unificación de grafos reales del repositorio.
  2. Prueba de búsqueda predictiva en omnibox (latencia y filtrado).
  3. Prueba de aislamiento de vecindario y cálculo de radio de impacto.

### T-03
**Classify**
- Nature: `REQUIREMENT`
- Priority: 1 CRITICAL
- Kind: LOGIC

**Estimate**
- Effort: High
- Agent min: 35
- Human ref hours: 1.75
- Tokens (est): 650k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: Implementar `gen_unified_explorer.py` que serializa el explorador interactivo como un archivo HTML único con el diseño Executive Precision de Stitch SCREEN-95.
- Activities:
  1. Estructura visual con layout de 3 columnas (Sidebar de capas 280px, Lienzo central con minimapa, Drawer inspector 360px).
  2. Implementación del motor de grafo interactivo en Canvas/SVG con soporte de zoom, arrastre, agrupamiento por dominios y halo en nodo focal.
  3. Embebido completo de estilos, iconos y lógica JS sin dependencias externas bloqueantes.

### T-04
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: Low
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 200k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: Actualizar `build_graph.py` para invocar `gen_unified_explorer.py` y generar el nuevo `docs/db-graph/explorer.html` global.
- Activities:
  1. Importar y ejecutar `build_unified_explorer()` dentro del flujo principal de `build_graph.py`.
  2. Validar que la generación se ejecute tanto en modo local como con `--introspect`.

### T-05
**Classify**
- Nature: `REQUIREMENT`
- Priority: 1 CRITICAL
- Kind: VIEW-new

**Estimate**
- Effort: High
- Agent min: 30
- Human ref hours: 1.5
- Tokens (est): 600k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: Generar y validar el artefacto final `docs/db-graph/explorer.html` cumpliendo la fidelidad visual de SCREEN-95.
- Activities:
  1. Ejecución del pipeline de generación y verificación de tamaño y completitud.
  2. Validación funcional de apertura en navegador, rendimiento de animación y visualización de nodos.

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-01, T-02 | builder, tests | 20 | 650 | 1.0 |
| 2 | T-03, T-04 | builder | 35 | 850 | 1.75 |
| 3 | T-05 | builder | 30 | 600 | 1.5 |

Total agent time (critical path): 85 min
Total tokens (k): 2100

## Approval gate

**Present the table above as a dry-run and wait for explicit approval before Step 5 starts on any row.**

Approved: 2026-11-03 hash:90d658033549
