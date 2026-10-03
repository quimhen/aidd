# Tasks — 004 AIDD Graph-First

Un renglón = un PR pequeño. Tarea de scripts/hooks/markdown: sin SCREEN/COMP/CTL, todas son LOGIC.

**Cada prompt de implementación repite estos estándares:**
- **Alcance:** dentro = solo los códigos y el archivo de destino de la fila; fuera = todo lo demás (un bug ajeno se reporta, no se arregla).
- **Si falta algo o es ambiguo, el agente se detiene y lo reporta.**
- **Regla W1:** grafo y filtros primero (`find_spec.py --tree`, `grep -n`, Read con `offset`/`limit`); no leer archivos enteros salvo el que se edita.
- **Stdlib only**, sin LLM; funciones snake_case, nombres del plan.md (Naming & File Contract).
- **Antifragile:** los parsers nunca lanzan; un error deja el grafo parcial más un aviso.
- Tras editar `skill/scripts/find_spec.py`, el espejo `adapters/dot-aidd/scripts/find_spec.py` queda idéntico (tarea T-08).

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-01 | FR-001, FR-002, FR-003 | skill/scripts/find_spec.py | LOGIC | | | cablear al índice; `--code`; el hook |
| T-02 | AC-001, AC-002, AC-003 | tests/test_find_spec.py | LOGIC | | | tests de `--code` y de versión del índice |
| T-03 | FR-008, AC-006 | skill/hooks/read_hint.py | LOGIC | | | registrar el hook; bloquear lecturas |
| T-04 | FR-004, FR-010, AC-004, AC-005 | skill/scripts/find_spec.py | LOGIC | | | `print_code`; `print_tree` |
| T-05 | FR-008 | skill/scripts/install_hooks.py | LOGIC | | | el contenido del hook |
| T-06 | FR-005, FR-006 | skill/scripts/find_spec.py | LOGIC | | | parsers; formato del índice |
| T-07 | AC-001, AC-004, AC-005 | tests/test_find_spec.py | LOGIC | | | tests del hook |
| T-08 | FR-007 | adapters/dot-aidd/scripts/find_spec.py | LOGIC | | | cualquier edición propia: solo copia idéntica |
| T-09 | FR-009 | skill/SKILL.md | LOGIC | | | AIDD.md y comandos (T-10) |
| T-10 | FR-009 | commands/aidd-converge.md | LOGIC | | | cualquier otro archivo |

## Per-task detail (one block per row above)

### T-01
**Classify**
- Nature: `REQUIREMENT`
- Priority: 1
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 4

**Decompose**
- Objective: añadir `GRAPH_CODE_RE`, `NODE_KINDS`/`EDGE_KINDS`, `parse_spec_nodes`, `parse_task_nodes`, `parse_contract_nodes` y `build_graph` como funciones puras, guiadas por encabezado (`table_rows`, `cell_codes`), sin cablearlas aún.

### T-02
**Estimate**
- Effort: Medium
- Agent min: 15
- Human ref hours: 2

**Decompose**
- Objective: tests de parsers con fixtures sintéticos: spec con 2 AC y 2 FR, tasks con T-16, carpeta con solo `contracts.md`.

### T-03
**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 3

**Decompose**
- Objective: hook PreToolUse Read que solo avisa (una vez por sesión y archivo; silencio con `limit`/`offset` o con un evento `find_spec` en la sesión) y su `tests/test_read_hint.py`.

### T-04
**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 4

**Decompose**
- Objective: `INDEX_VERSION` 4, columna `graph` en `dumps_index`/`loads_index`, `build_spec_entry` con nodes/edges, `memory_nodes_for`; un índice v3 se reconstruye sin excepción.

### T-05
**Estimate**
- Effort: Low
- Agent min: 10
- Human ref hours: 1.5

**Decompose**
- Objective: fila por defecto `PreToolUse Read` → `read_hint.py`, timeout corto, y actualizar `tests/test_install_hooks.py` con el nuevo conteo.

### T-06
**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 3

**Decompose**
- Objective: `neighbours`, `locate_in_file`, `print_code` (≤25 líneas), `--code` en `main`, y `print_tree` reescrito sobre aristas unificadas.

### T-07
**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 3

**Decompose**
- Objective: tests de extremo a extremo: `--code` ≤25 líneas, `--tree` no vacío sin mockup, reconstrucción de un índice v3, vecino MEM, y solo se re-parsea la spec tocada.

### T-08
**Estimate**
- Effort: Low
- Agent min: 5
- Human ref hours: 0.5

**Decompose**
- Objective: copiar `skill/scripts/find_spec.py` al espejo y pasar `tests/test_dot_aidd_mirror.py`.

### T-09
**Estimate**
- Effort: Low
- Agent min: 10
- Human ref hours: 1

**Decompose**
- Objective: en la regla W1 y en Step 6 de `skill/SKILL.md`, indicar `find_spec.py --code <CODE>` y que el auditor parte de los códigos cambiados más `check_spec.py`.

### T-10
**Estimate**
- Effort: Low
- Agent min: 5
- Human ref hours: 0.5

**Decompose**
- Objective: mismo ajuste de alcance del auditor en `commands/aidd-converge.md`.

## Waves

Los tiempos son de **agente**. Las tareas de una ola van en paralelo (archivos distintos) y una ola dura el máximo de sus tareas. T-04, T-06 y T-08 tocan `find_spec.py` y van en olas distintas.

| Wave | Tasks | Agent time (min) | Human ref (h) |
|---|---|---|---|
| 1 | T-01, T-02, T-03, T-09, T-10 | 25 | 4 |
| 2 | T-04, T-05 | 25 | 4 |
| 3 | T-06 | 20 | 3 |
| 4 | T-07, T-08 | 20 | 3 |

Total agent time (critical path): 90 min

## Approval gate

**Presenta esta tabla como dry-run y espera aprobación explícita antes de que el Step 5 empiece en cualquier fila.** Nunca se implementa una tarea no aprobada.

La aprobación es del usuario y es verificable: se le pregunta (AskUserQuestion) si aprueba las tareas y luego `aidd rules approve <spec_dir>` reemplaza la línea de abajo por `Approved: <YYYY-MM-DD> hash:<12 hex>`. Cualquier edición posterior de este archivo la invalida. No escribir esa línea a mano.

Approved: 2026-10-02 hash:37ed463c1371

## Definition of Done (applies to every task above)
1. El código implementa exactamente los códigos citados, en el archivo de destino, siguiendo el Naming & File Contract del plan.
2. Fila de mapeo en `qa-audit.md` por cada código tocado, con evidencia de archivo/función.
3. `PR/Spec ref` escrito en `plan.md` para cada código tocado, agregando, no sobrescribiendo.
4. Evidencia ejecutada (salida de comando o de tests guardada bajo `specs/004-aidd-graph-first/evidence/`), no solo lectura del código.
