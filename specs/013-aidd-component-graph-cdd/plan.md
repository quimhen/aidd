# Plan — 013 AIDD Semantic Component Graph (builtin:ui) & Mechanical CDD Gates

## Naming & File Contract (fill this first — everything below depends on it)
| Item | Convention |
|---|---|
| Classes / components / types | PascalCase |
| Functions / variables / methods | snake_case (Python scripts) |
| File names | snake_case (`component_graph.py`, `test_component_graph.py`) |
| Classes per file | One (or module functions in scripts) |
| File-path pattern | `skill/scripts/<name>.py`, `tests/test_<name>.py` |

## Script / Code Map

| Code | Target file | Purpose / Contract | PR (once opened) |
|---|---|---|---|
| FR-1301 | skill/scripts/component_graph.py | Core extractor: parses `components-index.md` + UI source files (`.tsx`, `.jsx`, `.dart`, `.vue`); generates `.aidd/graphs/ui.toon` with exact physical paths | |
| FR-1302 | adapters/dot-aidd/scripts/component_graph.py | Byte-identical mirror of `component_graph.py` | |
| FR-1303 | skill/scripts/aidd_graphs.py | Register `builtin:ui` in registry; wire `show ui <query>` | |
| FR-1303 | adapters/dot-aidd/scripts/aidd_graphs.py | Byte-identical mirror of `aidd_graphs.py` | |
| FR-1304 | aidd/cli.py | CLI commands: `aidd component search`, `aidd component show`, `aidd component inject` | |
| FR-1305 | skill/scripts/check_spec.py | Rules G7 (Anti-Monolithic Screen) and G8 (Shared-First Path Guard) | |
| FR-1305 | adapters/dot-aidd/scripts/check_spec.py | Byte-identical mirror of `check_spec.py` | |
| FR-1307 | tests/test_dot_aidd_mirror.py | Add `component_graph.py` to `VERBATIM_SCRIPTS` list | |
| FR-1306 | tests/test_component_graph.py | Unit test suite for component graph extraction, speed, CLI, and G7/G8 rules | |

## Verification Command
`python -m pytest tests/test_component_graph.py tests/test_check_spec.py tests/test_dot_aidd_mirror.py -q`
