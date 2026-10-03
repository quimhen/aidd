# QA Audit — 004 AIDD Graph-First

Auditor de cierre: dominio **performance** (único requerido: las tareas no citan API/ui/SQL), subagente independiente que no implementó. Resultado: PASS WITH NOTES.

## Mapping ledger
| Code | Status | Evidence (file/class/resource id) | PR/Spec ref | Screenshot diff done? |
|---|---|---|---|---|
| FR-001 | ✅ IMPLEMENTED | skill/scripts/find_spec.py `parse_spec_nodes`; tests TestGraphParsers | T-01 / plan.md FR→code | n/a (sin UI) |
| FR-002 | ✅ IMPLEMENTED | find_spec.py `parse_task_nodes`; AC-002 | T-01 | n/a |
| FR-003 | ✅ IMPLEMENTED | find_spec.py `parse_contract_nodes`, `build_graph`; AC-003 | T-01 | n/a |
| FR-004 | ✅ IMPLEMENTED | find_spec.py `memory_nodes_for`; TestGraphQuery (MEM neighbour) | T-04 | n/a |
| FR-005 | ✅ IMPLEMENTED | find_spec.py `print_code`, `--code` (≤25 líneas) | T-06 | n/a |
| FR-006 | ✅ IMPLEMENTED | find_spec.py `print_tree` (spec backend sin mockup: árbol no vacío) | T-06 | n/a |
| FR-007 | ✅ IMPLEMENTED | `stale_spec_names` sin cambios; test de reindex incremental | T-07 | n/a |
| FR-008 | ✅ IMPLEMENTED | skill/hooks/read_hint.py + install_hooks.py (solo avisa, exit 0) | T-03, T-05 | n/a |
| FR-009 | ✅ IMPLEMENTED | skill/SKILL.md (W1 y Step 6), commands/aidd-converge.md:10 | T-09, T-10 | n/a |
| FR-010 | ✅ IMPLEMENTED | `INDEX_VERSION = 4`; test_old_version_index_is_rebuilt | T-04, T-07 | n/a |
| AC-001 | ✅ IMPLEMENTED | `--code API-003` sobre la spec real de Integraciones: 6 líneas | T-06 | n/a |
| AC-002 | ✅ IMPLEMENTED | `--code T-16`: FR-005, FR-009, FR-010 y archivo destino | T-06 | n/a |
| AC-003 | ✅ IMPLEMENTED | `--tree 001-pos-sap-sync`: 87 líneas (antes vacío) | T-06 | n/a |
| AC-004 | ✅ IMPLEMENTED | TestGraphQuery: vecino MEM vía `aidd_memory.add_entry` en raíz temporal | T-07 | n/a |
| AC-005 | ✅ IMPLEMENTED | índice v3 se reconstruye; solo la spec tocada cambia | T-07 | n/a |
| AC-006 | ✅ IMPLEMENTED | tests/test_read_hint.py (5 casos, no bloquea) | T-03 | n/a |

## Device preflight
N/A: tarea de scripts y hooks, sin dispositivo ni UI.

## Execution evidence
Evidencia ejecutada guardada bajo `specs/004-aidd-graph-first/evidence/`.

| Code | Kind | Evidence | Verified by |
|---|---|---|---|
| AC-001 | command-output | evidence/graph-queries-integraciones.txt | agent |
| AC-002 | command-output | evidence/graph-queries-integraciones.txt | agent |
| AC-003 | command-output | evidence/graph-queries-integraciones.txt | agent |

Suite: `python -m unittest tests.test_dot_aidd_mirror tests.test_find_spec tests.test_read_hint tests.test_install_hooks tests.test_rule_gate tests.test_stop_gate tests.test_aidd_rules tests.test_hooks` → 526 tests OK.

## Bug reports
| # | Code | Symptom | Root cause | Fix | Pattern sweep |
|---|---|---|---|---|---|
| 1 | FR-008 | `aidd rules approve` rechazaba la aprobación hecha con AskUserQuestion | Claude Code 2.1.288 no dispara PostToolUse para AskUserQuestion: no se registra la respuesta | `typed_approval` en aidd_evidence.py (prompt escrito por el usuario con `[tasks:<hash8>]`); solo aprobación de tareas | `grep` de `affirmative_answer` en skill/: 3 usos, todos pasan por la función corregida |

## Resilience check (per code that crosses a boundary — network, DB, disk, external API, hardware)
| Code | Timeout set? | Retry/backoff? | Graceful degradation? | Recoverable trace on failure (where)? |
|---|---|---|---|---|
| FR-001..004 | n/a (lectura local) | n/a | Los parsers nunca lanzan: devuelven vacío; `decode_graph` ante celda corrupta da grafo vacío; `memory_nodes_for` da ([], []) | El índice se reconstruye solo (versión 4) |
| FR-008 | Timeout 10 s del hook | n/a | Sale con exit 0 ante cualquier error; nunca bloquea una lectura | `hook_error` solo si el hook puede registrarlo |

## Backend contract check (per API-nnn touched)
N/A: no se tocó ningún API-nnn.

## Database robustness check (per API-nnn/entity that touches a database)
N/A: sin base de datos.

## Performance & Best Practices check (Performance & Best Practices Auditor — applies to any code touched, every convergence)
| File/class | OOP/SOLID verified in code? | Interfaces used at real boundaries? | Locking/isolation deliberate for the engine? | Connection pooling verified (not just declared)? | No N+1 / unbatched loop? | No blocking call on hot path? |
|---|---|---|---|---|---|---|
| skill/scripts/find_spec.py | Funciones puras con una responsabilidad cada una | n/a | n/a | n/a | Pasada única por parser; sin bucles cuadráticos (14–27 ms con una fila de 40 KB) | `--code` cache-hit: 231 ms frente a 183 ms de Python vacío (≈50 ms de sobrecosto); reconstrucción ≈90 ms por spec |
| skill/hooks/read_hint.py | Una responsabilidad | n/a | n/a | n/a | n/a | ≈340 ms por Read de archivo no objetivo (≈160 ms sobre el arranque de Python, medido con `cmd /c`); en archivos objetivo lee el log de sesión (acotado por rotación) |
| skill/scripts/aidd_evidence.py, aidd_rules.py | n/a | n/a | n/a | n/a | `typed_approval` lee el log de prompts 2 veces; `audit_since` es un sort | Despreciable |

## Revision log (append, never overwrite)
- 2026-10-03: auditoría de cierre de performance (agente independiente): PASS WITH NOTES, sin bloqueantes.

## Open exceptions (rows left unresolved on purpose)
| Code | Reason | Approved by |
|---|---|---|
| FR-007 (nota 2) | La columna `graph` crece con la spec: 5.1 KB en la spec real (bajo el umbral de 10 KB) y 47 KB en una sintética de 200 FR + 250 tareas. Mejora opcional: recortar etiquetas/`targets` o guardar el grafo por spec en archivo aparte | pendiente del usuario |
| FR-006 (nota 4) | `print_tree` reimprime un nodo compartido bajo cada padre; un DAG muy ancho puede crecer mucho. Mejora opcional: imprimir el subárbol una sola vez con "(ver arriba)" o limitar líneas | pendiente del usuario |
| FR-008 (nota 5) | `read_hint.py` cuesta ≈340 ms por Read (mayormente arranque de Python y `cmd`). Mejora opcional: comprobar el marcador antes de leer el log, o medir en uso real antes de endurecer | pendiente del usuario |
