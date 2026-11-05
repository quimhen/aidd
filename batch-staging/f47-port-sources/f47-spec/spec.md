# Spec — F47 Unified Knowledge Graph Explorer

Produced during Step 2 (Align), from Step 1's mockup-audit.md. Nothing here is guessed —
a blank field is an open alignment question, not a placeholder to fill with a reasonable-sounding default.

Risk: medium

## Minimum Requirements Checklist (fill before Step 3 starts)

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | Arquitectura Global del Monorepositorio / Herramientas AIDD e Inspección de Grafos | repo — charter.md:148 | → Step 2 align question |
| New development or modification of something existing? | Nuevo desarrollo de visualizador global unificado evolucionando el explorador aislado de BD | user — "el concepto me parece bueno, pero el grafico se debe optimizar, ese explorer debe ser global para todos los grafos, como está todo interconectado, utiliza stitch para mejorarlo e implementa un nuevo spec en aidd para esta funcionalidad" | → Step 2 align question |
| Does it involve an external service, API, or integration? | No. Generación de un archivo HTML offline autocontenido sin dependencias CDN externas bloqueantes | repo — specs/F32-DB-Graph-Enrichment/spec.md:57 | → Step 2 align question |
| Who is requesting it? (role/profile, not necessarily the name) | Propietario del Repositorio / Arquitecto de Software Líder | user — "el concepto me parece bueno, pero el grafico se debe optimizar, ese explorer debe ser global para todos los grafos, como está todo interconectado, utiliza stitch para mejorarlo e implementa un nuevo spec en aidd para esta funcionalidad" | → Step 2 align question |
| Dependencies on other modules or active developments? | Consume `docs/db-graph/graph.json` (BD), `.aidd/graphs/code.json` (AST), `specs/index.toon` (Specs) y `.aidd/graphs/ui.toon` (UI) | repo — charter.md:150 | → Step 2 align question |
| Business objective (1 sentence — what it achieves and why) | Proveer un explorador gráfico interactivo, optimizado y unificado de toda la arquitectura del monorepositorio con trazabilidad multidominio y análisis de impacto en cascada | user — "el concepto me parece bueno, pero el grafico se debe optimizar, ese explorer debe ser global para todos los grafos, como está todo interconectado, utiliza stitch para mejorarlo e implementa un nuevo spec en aidd para esta funcionalidad" | → Step 2 align question |
| Expected visual fidelity level (if there's a mockup): exact \| functional behavior only | Exact. Fidelidad estricta al prototipo Stitch SCREEN-95 y sistema de diseño Executive Precision | user — "utiliza stitch para mejorarlo e implementa un nuevo spec en aidd para esta funcionalidad" | → Step 2 align question |

## Executive summary

- **Objective:** Generar un explorador gráfico interactivo autocontenido (`explorer.html`) que unifique en un solo lienzo los 4 grafos del monorepo (Base de Datos, Código Fuente AST, Especificaciones AIDD y Componentes UI) con navegación por capas y análisis de impacto.
- **Scope:** Nuevo generador `docs/db-graph/gen_unified_explorer.py`, suite de pruebas unitarias `docs/db-graph/test_unified_explorer.py`, actualización de `docs/db-graph/build_graph.py` e integración con `aidd_graphs.py`. Fuera de alcance: modificar la lógica de persistencia de las aplicaciones o añadir servidores backend runtime.
- **Cost:** ~85 min de tiempo de agente, ~2,100k tokens, 5 tareas en 3 waves.
- **Risks:** Rendimiento del renderizado en navegadores al manejar ~8,700 nodos en simultáneo; mitigado mediante clustering por dominio, radio de saltos acotado (hop-radius por defecto en 2 saltos) y virtualización del lienzo SVG/Canvas.
- **Open decisions:** Selección de la librería de renderizado embebida en el archivo autónomo (D3.js vs Cytoscape.js embebido sin dependencias externas).

## Pipeline route

| Step | Status | Reason | Confirmation |
|---|---|---|---|
| -1 | run | Búsqueda inicial en find_spec.py ejecutada | |
| 0 | run | Prototipo generado en Stitch MCP (SCREEN-95, id ac0f76f7a11d4670a2f9cba4484582cc) | |
| 1 | run | Auditoría de mockup realizada en mockup-audit.md | |
| 1.5 | run | Flujo visual documentado en visual-flow.toon | |
| 2 | run | Especificación y preguntas de alineación en curso | |
| 3 | run | Plan de arquitectura y mapeo a archivos pendiente | |
| 4 | run | Descomposición de tareas en tasks.md pendiente | |

## Scope

- **Included:**
  1. Generador de explorador unificado `docs/db-graph/gen_unified_explorer.py` que fusiona:
     - Grafo de Base de Datos (`docs/db-graph/graph.json`): 6,980 nodos (tablas, columnas, funciones, RLS policies).
     - Grafo de Código AST (`.aidd/graphs/code.json`): 1,094 módulos Python y funciones.
     - Grafo de Especificaciones AIDD (`specs/index.toon`): 69 especificaciones con relaciones US/SCREEN/COMP/CTL/API.
     - Grafo de Componentes UI (`.aidd/graphs/ui.toon`): 501 componentes React y vistas.
  2. Implementación de `SCREEN-95`:
     - Barra superior ejecutiva (`COMP-901`) con omnibox de búsqueda instantánea fuzzy (`COMP-902`).
     - Barra lateral de filtros (`COMP-903`) con alternador de capas (`COMP-904`), dominios (`COMP-905`) y slider de radio de saltos (1..5).
     - Lienzo de red interactivo (`COMP-906`) con soporte de clústeres, minimapa satelital (`COMP-907`) y controles de zoom/foco (`COMP-908`).
     - Inspector lateral desplegable (`COMP-909`) con ficha técnica, propósito, DDL/código y trazabilidad cruzada multidominio (`COMP-910`).
  3. Ensamblado como archivo HTML offline único en `docs/db-graph/explorer.html`.
  4. Suite de pruebas automatizadas `docs/db-graph/test_unified_explorer.py`.

- **Excluded:**
  1. Modificación de motores de base de datos o migraciones SQL de producción.
  2. Adición de servidores o procesos daemon HTTP adicionales (el visualizador debe ser autocontenido).
  3. Modificación de especificaciones ya cerradas (F01..F46, P01..P15, S01..S05).

## Functional requirements (cite codes, don't redescribe the UI)

| FR-nnn | Requirement | Cites (SCREEN-XX-Fnn / CTL-nnn / API-nnn) |
|---|---|---|
| FR-001 | El motor debe ingerir y normalizar en memoria los 4 grafos (`docs/db-graph/graph.json`, `.aidd/graphs/code.json`, `specs/index.toon`, `.aidd/graphs/ui.toon`) generando un modelo unificado de nodos y aristas cruzadas. | SCREEN-95-F01, COMP-906 |
| FR-002 | El buscador omnibox debe indexar todos los nodos con búsqueda predictiva por nombre, código o dominio (`[BD]`, `[AST]`, `[SPEC]`, `[UI]`) con respuesta menor a 50ms. | SCREEN-95-F02, COMP-902, CTL-135002, CTL-135007 |
| FR-003 | El panel de capas debe permitir encender o apagar dinámicamente cualquiera de las 4 capas de conocimiento reflejando el cambio de inmediato en el lienzo. | SCREEN-95-F03, COMP-904, CTL-135008..CTL-135011 |
| FR-004 | Al seleccionar un nodo focal, el lienzo debe aislar el subgrafo a una distancia de saltos configurable (1 a 5 saltos mediante slider). | SCREEN-95-F04, COMP-903, CTL-135013, CTL-135023, CTL-135024 |
| FR-005 | El inspector de nodo debe computar y mostrar la trazabilidad cruzada (Cross-Graph Trace) vinculando specs, funciones backend, DDL y componentes UI dependientes. | SCREEN-95-F05, COMP-909, COMP-910, CTL-135019..CTL-135022 |
| FR-006 | El lienzo debe incluir un minimapa interactivo en la esquina inferior derecha que permita paneo rápido y visualización de la posición relativa en el grafo global. | SCREEN-95-F01, COMP-907, CTL-135018 |
| FR-007 | El generador debe serializar el explorador como un único archivo `explorer.html` totalmente autónomo sin descargas remotas bloqueantes. | SCREEN-95-F06, CTL-135005 |
| FR-008 | El explorador debe admitir alternancia de distribución de layout (Jerárquico DAG, Fuerza Dirigida, Clúster por Dominio). | SCREEN-95-F01, COMP-901, CTL-135004 |

## Acceptance cases

| Case | Real data (id) | Expected | Edge? |
|---|---|---|---|
| AC-001 | Nodo BD `OPRM` (Nómina) | Muestra 4 columnas clave, RLS activo, specs P01/P05/F35 asociadas y componentes `CompanySelector` / `PeriodContext` vinculados. | no |
| AC-002 | Nodo Spec `F35-UI-Executive-Precision` | Muestra estado `CERRADA`, 5 tareas auditadas, componentes `ui-kit` creados y función SQL `pr_dashboard_analytics` vinculada. | no |
| AC-003 | Filtro solo `UI` activo | Oculta nodos BD, AST y Specs, mostrando exclusivamente los 501 componentes y su jerarquía de composición. | edge |
| AC-004 | Radio de saltos = 1 en nodo `pr_company_enable` | Muestra únicamente los vecinos directos (tabla `OCOM`, hook `OSLK`, y llamadores autorizados). | edge |
| AC-005 | Archivo generado `docs/db-graph/explorer.html` | Se abre localmente en un navegador sin conexión a Internet y renderiza el grafo sin errores en consola. | edge |

## Verification

Scope: docs/db-graph/**, .aidd/scripts/aidd_graphs.py

Generated: docs/db-graph/explorer.html

| # | Command | Expected | Covers |
|---|---|---|---|
| V-1 | `python -m unittest docs/db-graph/test_unified_explorer.py` | exit 0 | FR-001, FR-002, FR-003, FR-004, FR-005, FR-007, FR-008, AC-001, AC-002, AC-003, AC-004 |
| V-2 | `python docs/db-graph/build_graph.py` | exit 0 | FR-001, FR-007, AC-005 |
| V-3 | `python -m unittest docs/db-graph/test_gen_explorer.py` | exit 0 | FR-006, FR-007 |

## Optimization brief

Optimization targets, in order: (1) correct result on real data, (2) fewer moving parts, (3) reuse of existing code, (4) smaller PRs, (5) lower token cost.

Automation / parallelism: `docs/db-graph/gen_unified_explorer.py` procesa los archivos JSON/TOON existentes de forma determinista sin consultas dinámicas de red.

| Option | Cost (tokens / min) | Risk | Recommended? |
|---|---|---|---|
| A (Recomendado) | 2,200k tokens / 120 min | Bajo | Sí. Generador Python ligero embebiendo motor de grafos canvas/SVG en un único HTML de alto rendimiento conforme al diseño de Stitch SCREEN-95. |
| B | 4,500k tokens / 240 min | Alto | No. Crear una aplicación React Vite separada con servidor API intermedio (añade procesos daemon y viola la autonomía del artefacto). |

Owner pick: A

## Optional Align questions

| Question | Answer | Source |
|---|---|---|
| Which states must each screen/flow handle (empty, loading, error, offline)? | Carga inicial con skeleton/spinner, grafo activo con clusters, nodo focal seleccionado, modo impacto con proyección de cambios, y estado offline nativo. | repo — specs/F47-Unified-Knowledge-Graph-Explorer/mockup-audit.md |
| Who may see or do this (permissions/roles)? | Arquitectos, auditores y desarrolladores de b1SycLink. | repo — charter.md |
| Entry route: how does the user reach this from the app's start? | Apertura directa de `docs/db-graph/explorer.html` en el navegador o comando `aidd graphs explorer`. | repo — docs/db-graph/ |
| Target devices (phone, tablet, desktop, orientation)? | Desktop (1440x900 o superior para máxima densidad de información). | repo — specs/F47-Unified-Knowledge-Graph-Explorer/mockup-audit.md |
| Contract owner and status (who defines the backend contract, is it final or still moving)? | Final. Define la unificación de los esquemas consolidados de los 4 grafos existentes. | repo — docs/db-graph/graph.json |
| Shared-First UI library / Monorepo to reuse components from? | Tokens y estilos del sistema de diseño Executive Precision de Stitch (`#00677C`, Slate, Roboto Flex, JetBrains Mono). | repo — specs/F47-Unified-Knowledge-Graph-Explorer/prototype/stitch-SCREEN-95.html |
