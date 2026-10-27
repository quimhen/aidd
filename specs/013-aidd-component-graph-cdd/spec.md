# Spec — AIDD Semantic Component Graph (builtin:ui), Subgraph Prompt Injection & Mechanical CDD Gates (G7/G8)

Produced during Step 2 (Align). Intake: NEW SPEC, evolving `004-aidd-graph-first` from Python-AST file graphs into a high-speed, language-agnostic UI/Component knowledge graph that carries physical file paths and injects micro-contexts into agent prompts, eliminating recursive disk searches.

Risk: medium
<!-- medium: changes to check_spec, CLI, and graph registry; no database writes or external security boundaries -->

## Minimum Requirements Checklist (fill before Step 3 starts)

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | AIDD graph layer: `skill/scripts/component_graph.py`, `skill/scripts/aidd_graphs.py`, `skill/scripts/check_spec.py`, `aidd/cli.py`, templates and adapter mirrors | repo — skill/scripts/aidd_graphs.py:1 | → Step 2 align question |
| New development or modification of something existing? | New `builtin:ui` generator (`component_graph.py`), new `aidd component` CLI subcommands, and new mechanical gap checks G7/G8 in `check_spec.py` | user — "procedamos con esta propuesta" | → Step 2 align question |
| Does it involve an external service, API, or integration? | No: stdlib-only Python regex and lexical parsing; zero third-party packages, zero LLM calls | repo — skill/scripts/code_graph.py:1 | → Step 2 align question |
| Who is requesting it? (role/profile, not necessarily the name) | Senior Software Architect and Design Systems Lead | user — "el analisis es el mismo que he realizado, para esto habia pedido que se utilicen grafos de conocimiento" | → Step 2 align question |
| Dependencies on other modules or active developments? | Specs 004 (`aidd_graphs`), 002 (`check_spec`), and 009 (adapter mirror parity) | repo — specs/004-aidd-graph-first/spec.md:1 | → Step 2 align question |
| Business objective (1 sentence — what it achieves and why) | Index UI components into a compact graph with exact physical file paths, eliminating disk searches and preventing monolithic views via mechanical checks | user — "ten en cuenta que el grafo si debe contener la ruta fisica para que la busqueda sea rápida" | → Step 2 align question |
| Expected visual fidelity level (if there's a mockup): exact \| functional behavior only | Not applicable: no visual surface (CLI scripts, parser, graph generator) | user — "procedamos con esta propuesta" | → Step 2 align question |

**Source (rule R3) — every answered row needs exactly one of:** `user — "<the user's own words>"` · `repo — <path[:line]>` · `[Proposed — unconfirmed]`.

## Executive summary

<!-- aidd:FR-301 -->

- **Objective:** Create a compact, physical-path-indexed UI Component Knowledge Graph (`builtin:ui`) in TOON format, an active subgraph prompt injection helper, and mechanical CDD gap checks (G7/G8) in `check_spec.py`.
- **Scope:** `skill/scripts/component_graph.py` (and mirror in `adapters/dot-aidd/`), wiring in `aidd_graphs.py` (`builtin:ui`) and `aidd/cli.py` (`aidd component search|show|inject`), gap checks G7/G8 in `check_spec.py`, and test suite in `tests/test_component_graph.py`. Out: heavyweight AST compilers for every language, runtime UI rendering.
- **Cost:** 7 tasks across 3 waves (estimated ~45 agent minutes, ~250k tokens).
- **Risks:** Regex/lexical parsing of diverse frontend frameworks (.tsx, .jsx, .dart, .vue) must be resilient and never crash (fail-soft with partial graphs); component graph generation must finish in under 150 ms.
- **Open decisions:** none.

## Pipeline route

| Step | Status | Reason | Confirmation |
|---|---|---|---|
| -1 | run | `find_spec.py` ran; new feature area extending 004 into UI domain | |
| 0 | waived | no visual surface (CLI scripts, parsers) | user — "procedamos con esta propuesta" |
| 1 | waived | no visual surface | user — "procedamos con esta propuesta" |
| 1.5 | waived | no flows to draw | user — "procedamos con esta propuesta" |
| 2 | run | | |
| 3 | run | | |
| 4 | run | | |

## Visual debt

None: no `SCREEN-nn` code appears in this spec.

## Scope
- **Included:**
  1. `skill/scripts/component_graph.py`: parser scanning `components-index.md` and frontend files (`.tsx`, `.jsx`, `.dart`, `.vue`, `.html`). Outputs `.aidd/graphs/ui.toon`. Each node contains: `id` (`COMP-nnn`), `name`, `path` (exact physical file path relative to root), `pattern` (Compound/Slot/Atomic), `props` (comma-separated list), `slots`, `consumes`, and `consumers`.
  2. Integration with `aidd_graphs.py` under the name `ui` with generator `builtin:ui`.
  3. CLI subcommands in `aidd/cli.py`: `aidd component search <query>`, `aidd component show <id>`, and `aidd component inject <id>`.
  4. Mechanical gap checks in `check_spec.py`:
     - **G7 (Monolithic View Check):** Flags any `SCREEN-XX` in `mockup-audit.md` that has > 5 controls and 0 `COMP-nnn`.
     - **G8 (Shared-First Path Guard):** In `plan.md`, flags any `COMP-nnn` whose target file path is not within a shared directory (`shared/`, `components/`, `ui/`, `core/`, `widgets/`, `design-system/`, or `common/`).
  5. Identical mirror in `adapters/dot-aidd/` and test suite `tests/test_component_graph.py`.
- **Excluded:** Full TypeScript/Dart language compilers; modifying database graphs (`builtin:sql`); modifying existing closed specs.

## Functional requirements (cite codes, don't redescribe the UI)

| FR-nnn | Requirement | Cites (SCREEN-XX-Fnn / CTL-nnn / API-nnn) |
|---|---|---|
| FR-1301 | `skill/scripts/component_graph.py` builds the UI component graph from `design-system/components-index.md` and source directories. Every component node includes its exact physical file path relative to the project root, component name, pattern (Compound/Slot/Atomic), props list, slots, and consumers | — |
| FR-1302 | `component_graph.py` writes `.aidd/graphs/ui.toon` in compact TOON format (< 30 KB for 100+ components, execution time < 150 ms, stdlib-only, no third-party dependencies) | — |
| FR-1303 | `aidd_graphs.py` registers `ui` with refresh `builtin:ui` and default watch `design-system/components-index.md,src/**/*.{tsx,jsx,dart,vue},lib/**/*.{dart,tsx}`; `aidd graphs show ui <query>` prints matched component nodes with their physical path, pattern, and props | — |
| FR-1304 | `aidd/cli.py` exposes `aidd component search <term>`, `aidd component show <id>` and `aidd component inject <id>`. `inject` returns a concise 10-15 line snippet formatted for direct injection into a builder agent prompt | — |
| FR-1305 | `check_spec.py` implements rule G7: flags any `SCREEN-XX` in `mockup-audit.md` with > 5 controls and no referenced `COMP-nnn` as a monolithic view gap | — |
| FR-1306 | `check_spec.py` implements rule G8: flags any `COMP-nnn` in `plan.md` whose target path is not located under a shared directory (`shared/`, `components/`, `ui/`, `core/`, `widgets/`, `design-system/`, `common/`) | — |
| FR-1307 | `adapters/dot-aidd/` mirror files stay byte-identical and pass `tests/test_dot_aidd_mirror.py` | — |

## Acceptance cases

| Case | Real data (id) | Expected | Edge? |
|---|---|---|---|
| AC-1301 | A project with `design-system/components-index.md` containing `COMP-001` and `COMP-002` | `python component_graph.py` builds `.aidd/graphs/ui.toon` with exact physical paths, props and consumers | no |
| AC-1302 | `aidd component inject COMP-001` | Returns a 10-15 line YAML/text snippet showing physical file path, pattern, props, and consumers with 0 disk reads | no |
| AC-1303 | A `mockup-audit.md` with a screen having 8 `CTL-` rows and 0 `COMP-` rows | `check_spec.py` exits non-zero with gap `G7 monolithic screen SCREEN-XX: 8 controls but 0 COMP-nnn` | yes |
| AC-1304 | A `plan.md` with `COMP-001` mapped to `src/pages/checkout/Button.tsx` | `check_spec.py` exits non-zero with gap `G8 shared-first violation: COMP-001 path 'src/pages/checkout/Button.tsx' is not in a shared component directory` | yes |
| AC-1305 | A project with no frontend files or empty `components-index.md` | `component_graph.py` exits 0 with a clean, empty graph and never raises an unhandled exception | yes |
| AC-1306 | Performance budget: running `component_graph.py` over 200 components | Finishes in under 150 ms wall time | yes |

## Verification

Scope: auto

| # | Command | Expected | Covers |
|---|---|---|---|
| V-1 | python -m pytest tests/test_component_graph.py -q | exit 0 | FR-1301, FR-1302, FR-1303, FR-1304, FR-1305, FR-1306 |
| V-2 | python -m pytest tests/test_check_spec.py -q | exit 0 | FR-1305, FR-1306 |
| V-3 | python -m pytest tests/test_dot_aidd_mirror.py -q | exit 0 | FR-1307 |
| V-4 | python -m pytest tests/test_find_spec.py -q | exit 0 | FR-1301 |

## Optimization brief

Optimization targets: (1) correct result on real data, (2) zero disk reads by builder agents, (3) mechanical validation of Shared-First, (4) sub-150 ms execution.

Automation / parallelism: `component_graph.py` runs stdlib regex on file headers and `components-index.md` | tests and CLI wiring run in parallel waves | full suite runs once at converge.

| Option | Cost (tokens / min) | Risk | Recommended? |
|---|---|---|---|
| A (Built-in lexical/regex extractor with exact physical paths in compact TOON) | ~250k tokens / ~45 min | Low (pure stdlib, fast, fails soft) | Yes (Recommended) |
| B (Full AST compilers for TypeScript, Dart, Vue) | ~800k tokens / ~150 min | High (external npm/node dependencies, slow build, fragile) | No |

Owner pick: Option A

## Optional Align questions

| Question | Answer | Source |
|---|---|---|
| Physical path inclusion in graph nodes? | Yes, exact relative physical paths are mandatory for instant zero-disk search | user — "ten en cuenta que el grafo si debe contener la ruta fisica para que la busqueda sea rápida" |
| Default shared directories allowed for G8? | `shared/`, `components/`, `ui/`, `core/`, `widgets/`, `design-system/`, `common/` | repo — skill/templates/design-system/components-index.md:8 |
