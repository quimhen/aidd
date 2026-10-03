# Tasks — 005 AIDD token planning

Un renglón = un PR pequeño. Tarea de scripts/hooks/markdown: sin SCREEN/COMP/CTL, todas son LOGIC.

**Cada prompt de implementación repite estos estándares:**
- **Alcance:** dentro = solo los códigos y el archivo de destino de la fila; fuera = todo lo demás (un bug ajeno se reporta, no se arregla).
- **Si falta algo o es ambiguo, el agente se detiene y lo reporta.**
- **Regla W1:** grafo y filtros primero (`find_spec.py --code`, `grep -n`, Read con `offset`/`limit`); no leer archivos enteros salvo el que se edita.
- **Stdlib only**, sin LLM; nombres exactos de `plan.md` (Naming & File Contract).
- **Antifragile:** parsers y hooks nunca lanzan; ante error, degradan y dejan rastro.
- **Modelo:** cada tarea se ejecuta con el rol y el nivel de modelo indicados (`medium` u `high`); las auditorías nunca usan el nivel más bajo.
- Los tiempos y tokens de cada bloque salen de la línea base medida en la spec 004; las horas humanas son derivadas (minutos × 3 / 60).

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-01 | FR-006 | skill/scripts/aidd_rules.py | LOGIC | | | R1, R13, FR-011 y la ruta protegida (T-06, T-12) |
| T-02 | FR-006 | skill/hooks/mark_agent_dispatch.py | LOGIC | | | cualquier otro archivo |
| T-03 | FR-002 | skill/scripts/aidd_calibrate.py | LOGIC | | | el subcomando de la CLI (T-08) |
| T-04 | FR-001, FR-003, FR-007 | skill/templates/tasks.md | LOGIC | | | spec.md de plantillas y la documentación |
| T-05 | FR-013, FR-014 | skill/scripts/aidd_evidence.py | LOGIC | | | los hooks que lo llaman (T-07, T-09) |
| T-06 | FR-001, FR-004, FR-005, FR-009 | skill/scripts/aidd_rules.py | LOGIC | | | filtro R14 y FR-011 |
| T-07 | FR-006, FR-013 | skill/hooks/rule_gate.py | LOGIC | | | prompt_trigger.py (T-09) |
| T-08 | FR-002 | aidd/cli.py | LOGIC | | | la lógica de calibración |
| T-09 | FR-013, FR-014 | skill/hooks/prompt_trigger.py | LOGIC | | | rule_gate.py (T-07) |
| T-10 | FR-005, FR-006, FR-008, FR-010 | skill/scripts/aidd_status.py | LOGIC | | | check_spec.py (T-11) |
| T-11 | FR-008 | skill/scripts/check_spec.py | LOGIC | | | aidd_status.py (T-10) |
| T-12 | FR-011, FR-013 | skill/scripts/aidd_rules.py | LOGIC | | | R1, R13 y R14 |
| T-13 | AC-002, AC-003, AC-007, AC-009 | tests/test_aidd_rules.py | LOGIC | | | tests de R14 y de confirmaciones |
| T-14 | AC-004, AC-005 | tests/test_r14.py | LOGIC | | | cualquier otro archivo |
| T-15 | AC-006 | tests/test_aidd_calibrate.py | LOGIC | | | cualquier otro archivo |
| T-16 | AC-001 | tests/test_aidd_status.py | LOGIC | | | cualquier otro archivo |
| T-17 | AC-008 | tests/test_typed_confirmations.py | LOGIC | | | cualquier otro archivo |
| T-18 | AC-011, AC-012 | tests/test_transcript_sync.py | LOGIC | | | cualquier otro archivo |
| T-19 | FR-003, FR-007, FR-010, FR-012 | skill/SKILL.md | LOGIC | | | AIDD.md y comandos (T-20) |
| T-20 | FR-007, FR-012 | commands/aidd-converge.md | LOGIC | | | cualquier otro archivo |
| T-21 | FR-013 | adapters/dot-aidd/scripts/aidd_rules.py | LOGIC | | | cualquier edición propia: solo copia idéntica |
| T-22 | AC-010 | specs/005-aidd-token-planning/qa-audit.md | LOGIC | | | cualquier cambio de código |
| T-23 | AC-011 | specs/005-aidd-token-planning/qa-audit.md | LOGIC | | | cualquier cambio de código |

## Per-task detail (one block per row above)

### T-01
**Estimate**
- Effort: Medium
- Agent min: 3
- Human ref hours: 0.15
- Tokens (est): 75k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: constantes `AGENT_ROLES`, `MODEL_TIERS`, `LOWEST_TIER_RE`, `HUMAN_FACTOR_DEFAULT`, `R13`/`R14` en `RULE_IDS`, `is_low_tier`, `_subagent_counts`, `_uncovered_reasons` y el filtro R14 en `_uncovered` y en los sitios R5.

### T-02
**Estimate**
- Effort: Low
- Agent min: 1
- Human ref hours: 0.05
- Tokens (est): 50k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: registrar `model` (de `tool_input.model`, vacío si falta) en el evento `subagent`.

### T-03
**Estimate**
- Effort: Medium
- Agent min: 3
- Human ref hours: 0.15
- Tokens (est): 70k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: `aidd_calibrate.py` (`load_calibration`, `parse_closed_tasks`, `record` idempotente por spec y clase, `main`) y la semilla `skill/templates/calibration.toon`.

### T-04
**Estimate**
- Effort: Low
- Agent min: 2
- Human ref hours: 0.1
- Tokens (est): 50k
- Agent role: docs
- Model tier: medium

**Decompose**
- Objective: plantilla `tasks.md` con `Tokens (est)`, `Agent role`, `Model tier`, columnas `Roles` y `Tokens (k)` y la línea `Total tokens (k)`; cabecera `Risk:` en la plantilla de spec.

### T-05
**Estimate**
- Effort: Medium
- Agent min: 3
- Human ref hours: 0.15
- Tokens (est): 70k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: `parse_transcript_pairs`, `sync_ask_answers`, `record_queued_messages`, `tool_use_id` opcional en los eventos y el marcador de offset; nunca lanza y no duplica.

### T-06
**Estimate**
- Effort: High
- Agent min: 3
- Human ref hours: 0.15
- Tokens (est): 80k
- Agent role: builder
- Model tier: high

**Decompose**
- Objective: R1 con encabezado doble (legado y nuevo), `_check_tokens`, `_check_roles` (R13), `_wave_roles_ok`, `_is_legacy_tasks`, `derived_human_hours`, `plan_totals`.

### T-07
**Estimate**
- Effort: Medium
- Agent min: 3
- Human ref hours: 0.15
- Tokens (est): 70k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: filtro R14 en los sitios R5, llamada a `sync_ask_answers` antes de `decide()` y de la salida rápida de shell, y mención lexical del transcript en R9.

### T-08
**Estimate**
- Effort: Low
- Agent min: 1
- Human ref hours: 0.05
- Tokens (est): 50k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: subcomando `aidd calibrate record <spec_dir>`.

### T-09
**Estimate**
- Effort: Low
- Agent min: 2
- Human ref hours: 0.1
- Tokens (est): 55k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: `prompt_trigger.py` llama a `sync_ask_answers` y a `record_queued_messages` en el mismo `try` de registro del prompt.

### T-10
**Estimate**
- Effort: Medium
- Agent min: 3
- Human ref hours: 0.15
- Tokens (est): 65k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: `_waves` por nombre de columna, totales de minutos y tokens en la línea de estado, filtro R14 (`:194`) y etiquetas `[spec:<id>]` en cierre y abandono (con `spec_id` en abandono).

### T-11
**Estimate**
- Effort: Low
- Agent min: 1
- Human ref hours: 0.05
- Tokens (est): 50k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: línea informativa `~N min, ~Nk tokens` en `check_spec.py` usando `plan_totals`.

### T-12
**Estimate**
- Effort: Low
- Agent min: 2
- Human ref hours: 0.1
- Tokens (est): 55k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: `_strip_code_spans` solo en el bucle de specs hermanas de R4, y la ruta protegida `.claude/projects/*/*.jsonl` en `is_protected_path`.

### T-13
**Estimate**
- Effort: Medium
- Agent min: 3
- Human ref hours: 0.15
- Tokens (est): 75k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: tests de R1 con tokens (suma por ola y total), R13, exención legada y R4 con ejemplos entre backticks; actualizar `tests/gate_fixtures.py` con un helper de `tasks.md` nuevo.

### T-14
**Estimate**
- Effort: Medium
- Agent min: 2
- Human ref hours: 0.1
- Tokens (est): 60k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: tests de R14: `haiku` no cuenta, `sonnet` y modelo ausente sí, `claude-haiku-*` sin distinguir mayúsculas, mensaje "model tier too low".

### T-15
**Estimate**
- Effort: Medium
- Agent min: 2
- Human ref hours: 0.1
- Tokens (est): 55k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: tests de `aidd calibrate record`: una fila por clase, segunda corrida sin duplicados, spec sin datos usa la semilla.

### T-16
**Estimate**
- Effort: Medium
- Agent min: 2
- Human ref hours: 0.1
- Tokens (est): 55k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: tests de `aidd status`: totales `~N min, ~Nk tokens` y columnas leídas por nombre.

### T-17
**Estimate**
- Effort: Medium
- Agent min: 2
- Human ref hours: 0.1
- Tokens (est): 60k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: tests de cierre y abandono escritos con etiqueta `[spec:<id>]`: aceptado para el spec correcto, rechazado para otro id o desde un mensaje de subagente.

### T-18
**Estimate**
- Effort: Medium
- Agent min: 3
- Human ref hours: 0.15
- Tokens (est): 65k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: tests de transcript: par con clic, segunda ejecución sin duplicados, transcript sin preguntas, `queued_messages` sin duplicados y ruta protegida.

### T-19
**Estimate**
- Effort: Low
- Agent min: 2
- Human ref hours: 0.1
- Tokens (est): 60k
- Agent role: docs
- Model tier: medium

**Decompose**
- Objective: en `SKILL.md` y `AIDD.md`: planificar en minutos y tokens, horas humanas derivadas, roles y niveles de modelo, piso de modelo para auditores, `Risk:`, y el flujo de una sola confirmación con resumen de objetivos.

### T-20
**Estimate**
- Effort: Low
- Agent min: 1
- Human ref hours: 0.05
- Tokens (est): 50k
- Agent role: docs
- Model tier: medium

**Decompose**
- Objective: reglas de nivel de modelo y de riesgo en `commands/aidd-converge.md` y `commands/aidd-tasks.md`.

### T-21
**Estimate**
- Effort: Low
- Agent min: 1
- Human ref hours: 0.05
- Tokens (est): 50k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: copiar los scripts cambiados (`aidd_rules.py`, `aidd_evidence.py`, `aidd_status.py`, `check_spec.py`, `aidd_calibrate.py`) al espejo y pasar `tests/test_dot_aidd_mirror.py`.

### T-22
**Estimate**
- Effort: High
- Agent min: 3
- Human ref hours: 0.15
- Tokens (est): 70k
- Agent role: auditor
- Model tier: high

**Decompose**
- Objective: auditoría de performance independiente (costo del sync del transcript por llamada de hook, tamaño del índice, regex).

### T-23
**Estimate**
- Effort: High
- Agent min: 3
- Human ref hours: 0.15
- Tokens (est): 70k
- Agent role: auditor
- Model tier: high

**Decompose**
- Objective: auditoría de lógica independiente: R14, exención legada, sync del transcript y confirmaciones escritas; incluye una prueba real del clic del popup.

## Waves

Los tiempos son de **agente**. Las tareas de una ola van en paralelo (archivos distintos) y una ola dura el máximo de sus tareas. `aidd_rules.py` aparece en las olas 1, 2 y 3, nunca dos veces en la misma. Tokens por ola (suma): 315k, 255k, 170k, 370k, 160k, 140k; total 1410k. Roles: olas 1 a 3 builder y docs, ola 4 tests, ola 5 docs y builder, ola 6 auditor.

| Wave | Tasks | Agent time (min) | Human ref (h) |
|---|---|---|---|
| 1 | T-01, T-02, T-03, T-04, T-05 | 3 | 0.15 |
| 2 | T-06, T-07, T-08, T-09 | 3 | 0.15 |
| 3 | T-10, T-11, T-12 | 3 | 0.15 |
| 4 | T-13, T-14, T-15, T-16, T-17, T-18 | 3 | 0.15 |
| 5 | T-19, T-20, T-21 | 2 | 0.1 |
| 6 | T-22, T-23 | 3 | 0.15 |

Total agent time (critical path): 17 min

## Approval gate

**Presenta esta tabla como dry-run y espera aprobación explícita antes de que el Step 5 empiece en cualquier fila.** Nunca se implementa una tarea no aprobada.

La aprobación es del usuario y es verificable: se le pregunta (AskUserQuestion) si aprueba las tareas y luego `aidd rules approve <spec_dir>` reemplaza la línea de abajo por `Approved: <YYYY-MM-DD> hash:<12 hex>`. Cualquier edición posterior de este archivo la invalida. No escribir esa línea a mano.

Approved: 2026-10-03 hash:cca39e73eb06

## Definition of Done (applies to every task above)
1. El código implementa exactamente los códigos citados, en el archivo de destino, siguiendo el Naming & File Contract del plan.
2. Fila de mapeo en `qa-audit.md` por cada código tocado, con evidencia de archivo/función.
3. `PR/Spec ref` escrito en `plan.md` para cada código tocado, agregando, no sobrescribiendo.
4. Evidencia ejecutada (salida de comando o de tests guardada bajo `specs/005-aidd-token-planning/evidence/`), no solo lectura del código.
