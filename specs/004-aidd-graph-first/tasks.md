# Tasks — 004 AIDD Graph-First

Un renglón = un PR pequeño. Tarea de scripts/hooks/markdown: sin SCREEN/COMP/CTL, todas son LOGIC.

Enmienda 2026-10-24: T-01..T-10 son el trabajo ya construido (olas 1-4, aprobadas el 2026-10-02); T-11..T-38 (sin T-20) son el grafo de código propio, el hook de grafo primero, los grafos SQL y las correcciones de "ejecutar a cada momento" (olas 5-8, FR-014..FR-034). La auditoría previa única ya corrió y sus hallazgos están aplicados.

**Cada prompt de implementación repite estos estándares:**
- **Alcance:** dentro = solo los códigos y el archivo de destino de la fila; fuera = todo lo demás (un bug ajeno se reporta, no se arregla).
- **Si falta algo o es ambiguo, el agente se detiene y lo reporta.**
- **Regla W1/G1:** grafo y filtros primero (`find_spec.py --code`, `aidd graphs show`, `grep -n`, Read con `offset`/`limit`); nunca graphify; no leer archivos enteros salvo el que se edita.
- **Stdlib only**, sin LLM; funciones snake_case, nombres del plan.md (Naming & File Contract y su enmienda).
- **Antifragile:** los parsers nunca lanzan; un error deja el grafo parcial más un aviso.
- **Espejo:** tras editar un script de `skill/scripts/` que esté en `VERBATIM_SCRIPTS`, el mismo dueño copia el archivo idéntico a `adapters/dot-aidd/scripts/` (la fila lista ambas rutas). Los builders solo hacen autochequeo estático; las pruebas ejecutadas las corre el verificador (T-25) UNA vez; el único caso permitido a un builder de rol `tests` es correr SU propio módulo una sola vez al escribirlo (nunca otras suites ni repeticiones). Regla E9: la misma verificación no se repite sobre el mismo estado del código.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-01 | FR-001, FR-002, FR-003 | skill/scripts/find_spec.py | LOGIC | | | cablear al índice; `--code`; el hook |
| T-02 | AC-001, AC-002, AC-003 | tests/test_find_spec.py | LOGIC | | | tests de `--code` y de versión del índice |
| T-03 | FR-008, AC-006 | skill/hooks/read_hint.py | LOGIC | | | registrar el hook; bloquear lecturas |
| T-04 | FR-004, FR-010, AC-004, AC-005 | skill/scripts/find_spec.py (same owner as T-01) | LOGIC | | | `print_code`; `print_tree` |
| T-05 | FR-008 | skill/scripts/install_hooks.py | LOGIC | | | el contenido del hook |
| T-06 | FR-005, FR-006 | skill/scripts/find_spec.py (same owner as T-01) | LOGIC | | | parsers; formato del índice |
| T-07 | AC-001, AC-004, AC-005 | tests/test_find_spec.py (same owner as T-02) | LOGIC | | | tests del hook |
| T-08 | FR-007 | adapters/dot-aidd/scripts/find_spec.py | LOGIC | | | cualquier edición propia: solo copia idéntica |
| T-09 | FR-009 | skill/SKILL.md | LOGIC | | | AIDD.md y comandos (T-10) |
| T-10 | FR-009 | commands/aidd-converge.md | LOGIC | | | cualquier otro archivo |
| T-11 | FR-019, FR-023, FR-026, FR-027 | skill/scripts/aidd_evidence.py + adapters/dot-aidd/scripts/aidd_evidence.py | LOGIC | | | cualquier otro cambio de `code_state`/`code_fingerprint`; los generadores |
| T-12 | FR-014, FR-015, FR-023, FR-024 | skill/scripts/code_graph.py + adapters/dot-aidd/scripts/code_graph.py | LOGIC | | | método, trace, snapshot; cablear a `aidd_graphs` |
| T-13 | FR-016 | skill/scripts/method_graph.py + adapters/dot-aidd/scripts/method_graph.py | LOGIC | | | editar los documentos que parsea; cablear a `aidd_graphs` |
| T-14 | FR-018 | skill/scripts/graph_trace.py + adapters/dot-aidd/scripts/graph_trace.py | LOGIC | | | cablear a `aidd_graphs`; perfilar procesos hijos |
| T-15 | FR-017, FR-019, FR-020, FR-023, FR-024 | skill/scripts/graph_snapshot.py + adapters/dot-aidd/scripts/graph_snapshot.py | LOGIC | | | cablear a `aidd_graphs`; wiring de `check_spec`/`aidd verify` |
| T-16 | AC-009, AC-010, AC-016, AC-017 | tests/test_code_graph.py | LOGIC | | | pruebas de snapshot, trace y método |
| T-17 | FR-021, FR-014, FR-015, FR-029, FR-030 | skill/scripts/aidd_graphs.py + adapters/dot-aidd/scripts/aidd_graphs.py | LOGIC | | | lógica de los generadores; `aidd_status.py` |
| T-18 | AC-014, AC-018, AC-016, AC-020 | tests/test_graph_snapshot.py | LOGIC | | | pruebas de code_graph, trace y método |
| T-19 | AC-011, AC-012, AC-013, AC-015 | tests/test_graph_trace_method.py | LOGIC | | | pruebas de code_graph y snapshot |
| T-21 | FR-022 | tests/test_dot_aidd_mirror.py | LOGIC | | | cualquier otro test; copiar scripts (los copia cada dueño) |
| T-22 | FR-022 | skill/SKILL.md (same owner as T-09) | LOGIC | | | AIDD.md y comandos |
| T-23 | FR-022 | skill/AIDD.md + adapters/dot-aidd/AIDD.md | LOGIC | | | SKILL.md y comandos |
| T-24 | FR-022 | commands/aidd-converge.md (same owner as T-10) | LOGIC | | | cualquier otro archivo |
| T-25 | FR-014, FR-017, FR-018, FR-019, FR-020, FR-023, FR-025, FR-029, FR-031, FR-034 | specs/004-aidd-graph-first/evidence/ | LOGIC | | | editar código fuente; solo ejecutar y guardar evidencia |
| T-26 | FR-023, FR-027 | skill/scripts/aidd_status.py + adapters/dot-aidd/scripts/aidd_status.py | LOGIC | | | `aidd verify`, estado y todo lo que no sea `cmd_activate` y la línea `graph-first` |
| T-27 | FR-025, FR-026, FR-027 | skill/hooks/read_hint.py (same owner as T-03) | LOGIC | | | registrar el hook (T-28); bloquear búsquedas |
| T-28 | FR-025 | skill/scripts/install_hooks.py (same owner as T-05) | LOGIC | | | el contenido del hook |
| T-29 | AC-019, AC-020 | tests/test_read_hint.py | LOGIC | | | pruebas de grafos y SQL |
| T-30 | FR-026 | skill/hooks/mark_graph_rebuild.py | LOGIC | | | `aidd_evidence.py` (T-11) y el hook de lectura |
| T-31 | FR-028, FR-029, FR-030 | skill/scripts/sql_graph.py + adapters/dot-aidd/scripts/sql_graph.py | LOGIC | | | registrar los grafos (T-17); la rama `builtin:sql` combinada |
| T-32 | AC-021, AC-022 | tests/test_sql_graph_incremental.py | LOGIC | | | pruebas de los demás grafos |
| T-33 | FR-032 | skill/hooks/prompt_trigger.py | LOGIC | | | el hook de lectura (T-27) y el registro de hooks |
| T-34 | AC-024 | tests/test_prompt_trigger.py | LOGIC | | | las pruebas de prompt_trigger que ya están en tests/test_hooks.py |
| T-35 | FR-034, AC-026 | tests/test_perf_budget.py | LOGIC | | | tiempos absolutos de reloj; pruebas de otros módulos |
| T-36 | FR-031, FR-033 | skill/SKILL.md (same owner as T-09) | LOGIC | | | AIDD.md y comandos |
| T-37 | FR-031 | skill/AIDD.md + adapters/dot-aidd/AIDD.md (same owner as T-23) | LOGIC | | | SKILL.md y comandos |
| T-38 | FR-033 | commands/aidd-converge.md (same owner as T-10) | LOGIC | | | cualquier otro archivo |
| T-39 | FR-035, FR-036 | skill/scripts/aidd_job.py + adapters/dot-aidd/scripts/aidd_job.py | LOGIC | | | cablear al CLI (T-43); integrar con `aidd verify` |
| T-40 | FR-037 | skill/scripts/aidd_triage.py + adapters/dot-aidd/scripts/aidd_triage.py | LOGIC | | | cablear al CLI (T-43); escribir evidencia |
| T-41 | AC-027 | tests/test_aidd_job.py | LOGIC | | | pruebas de triage, tools y size |
| T-42 | AC-028 | tests/test_aidd_triage.py | LOGIC | | | pruebas de job, tools y size |
| T-43 | FR-038, FR-041 | aidd/cli.py | LOGIC | | | cualquier subcomando que no sea `job`, `triage`, `tools`, `size` |
| T-44 | FR-039, FR-040, FR-041, FR-042 | skill/scripts/aidd_tools.py + adapters/dot-aidd/scripts/aidd_tools.py | LOGIC | | | cablear al CLI (T-43); crear grafos o snapshots |
| T-45 | AC-030, AC-032 | tests/test_aidd_tools.py | LOGIC | | | pruebas de job y triage |
| T-46 | FR-040, FR-043 | skill/templates/tasks.md | LOGIC | | | adapters/dot-aidd/templates/tasks.md (variante reducida) y comandos |
| T-47 | FR-045, FR-046 | skill/scripts/aidd_rules.py + adapters/dot-aidd/scripts/aidd_rules.py | LOGIC | | | cambiar la semántica de R1-R14; leer en caché en hooks o decisiones de gate |
| T-48 | FR-045 | skill/scripts/aidd_evidence.py + adapters/dot-aidd/scripts/aidd_evidence.py (same owner as T-11) | LOGIC | | | cambiar el formato de `events.toon`; caché fuera del alcance `read_cache()` |
| T-49 | FR-045, FR-046 | skill/scripts/aidd_status.py + adapters/dot-aidd/scripts/aidd_status.py (same owner as T-26) | LOGIC | | | `cmd_activate` y la línea `graph-first`; otros subcomandos |
| T-50 | FR-047 | skill/hooks/prompt_trigger.py (same owner as T-33) | LOGIC | | | dedupe y salto de mensajes de sistema; registro de hooks |
| T-51 | FR-048 | skill/scripts/aidd_job.py + adapters/dot-aidd/scripts/aidd_job.py + .gitignore (same owner as T-39 for aidd_job.py) | LOGIC | | | semántica de CACHED; `--key` con 0 archivos (L2) |
| T-52 | AC-037, AC-038 | tests/test_aidd_rules.py | LOGIC | | | pruebas de status, evidence y progress |
| T-53 | AC-036, AC-037 | tests/test_perf_budget.py (same owner as T-35) | LOGIC | | | tiempos absolutos de reloj; pruebas de otros módulos |
| T-54 | AC-038 | tests/test_aidd_status.py | LOGIC | | | pruebas de rules, evidence y progress |
| T-55 | AC-040 | tests/test_aidd_job.py (same owner as T-41) | LOGIC | | | pruebas de triage, tools y size |
| T-56 | AC-039 | tests/test_prompt_trigger.py (same owner as T-34) | LOGIC | | | las pruebas de prompt_trigger de tests/test_hooks.py |
| T-57 | FR-046 | skill/SKILL.md (same owner as T-09) | LOGIC | | | AIDD.md y comandos |
| T-58 | FR-046 | skill/AIDD.md + adapters/dot-aidd/AIDD.md (same owner as T-23) | LOGIC | | | SKILL.md y comandos |
| T-59 | FR-044, FR-045, FR-046, FR-047, FR-048 | specs/004-aidd-graph-first/evidence/ (same owner as T-25) | LOGIC | | | editar código fuente; solo ejecutar y guardar evidencia |
| T-60 | FR-049..FR-054, AC-041..AC-046 | tests/test_tool_first_hint.py | LOGIC | | | any production code; any other test file |
| T-65 | FR-051, FR-052, FR-053 | skill/scripts/aidd_evidence.py (same owner as T-11) | LOGIC | | | any other event kind; rotation and spill logic |
| T-61 | FR-049, FR-050, FR-051, FR-053, FR-054 | skill/hooks/tool_first_hint.py | LOGIC | | | blocking behaviour; any other hook |
| T-62 | FR-049 | skill/scripts/install_hooks.py (same owner as T-05) | LOGIC | | | any other host adapter |
| T-63 | FR-052 | skill/scripts/aidd_status.py (same owner as T-26) | LOGIC | | | the verification and approval lines of `format_global`; `_graph_first_line` |
| T-64 | FR-050, FR-052 | skill/SKILL.md (same owner as T-09) | LOGIC | | | any other section |
| T-66 | FR-052, FR-053 | adapters/dot-aidd/scripts/aidd_evidence.py + adapters/dot-aidd/scripts/aidd_status.py | LOGIC | | | any change that is not a byte copy |
| T-70 | FR-060..FR-066, AC-050..AC-056 | tests/test_unified_graph.py | LOGIC | | | any production code |
| T-71 | FR-060, FR-061, FR-062, FR-064 | skill/scripts/unified_graph.py | LOGIC | | | linking, loading, neighbourhood, CLI |
| T-72 | FR-060, FR-063, FR-065, FR-066 | skill/scripts/unified_graph.py (same owner as T-71) | LOGIC | | | readers and styles of T-71 |
| T-73 | FR-067, FR-068, FR-069, FR-076, AC-051, AC-057..AC-059, AC-064, AC-065 | tests/test_unified_explorer.py | LOGIC | | | any production code |
| T-74 | FR-067, AC-060 | skill/scripts/graph_explorer.py + tests/test_graph_explorer.py | LOGIC | | | any edit of the copied file |
| T-80 | FR-071..FR-075, AC-062 | tests/test_explorer_controls.py | LOGIC | | | any production code; browser |
| T-81 | FR-071..FR-075, AC-063 | tests/test_explorer_controls_browser.py | LOGIC | | | any production code |
| T-75 | FR-064, FR-067, FR-069, FR-076 | skill/scripts/graph_explorer.py (same owner as T-74) | LOGIC | | | the JS block; size guard |
| T-76 | FR-067, FR-069, AC-058, AC-059 | skill/scripts/graph_explorer.py (same owner as T-74) | LOGIC | | | Python functions; controls |
| T-82 | FR-071, FR-074, FR-075 | skill/scripts/graph_explorer.py (same owner as T-74) | VIEW-new | | | inspector and theme controls |
| T-83 | FR-071, FR-072, FR-073 | skill/scripts/graph_explorer.py (same owner as T-74) | VIEW-new | | | toolbar controls |
| T-84 | FR-076, AC-064 | skill/scripts/graph_explorer.py (same owner as T-74) | LOGIC | | | HTML and JS |
| T-77 | FR-068, AC-057 | skill/scripts/aidd_graphs.py (same owner as T-17) | LOGIC | | | registry, refresh, show |
| T-78 | FR-070, AC-061 | adapters/dot-aidd/scripts/unified_graph.py + adapters/dot-aidd/scripts/graph_explorer.py + adapters/dot-aidd/scripts/aidd_graphs.py + tests/test_dot_aidd_mirror.py | LOGIC | | | any hand edit of a mirrored file |
| T-79 | FR-068, FR-070 | skill/SKILL.md (same owner as T-09) + aidd/cli.py | LOGIC | | | any other section or help string |
| T-85 | FR-077, AC-066 | tests/visual_compare_explorer.py + tests/test_visual_compare_explorer.py | LOGIC | | | any production file; judgement by eye |

## Per-task detail (one block per row above)

### T-01
**Classify**
- Nature: `REQUIREMENT`
- Priority: 1
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.25
- Tokens (est): 62k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: añadir `GRAPH_CODE_RE`, `NODE_KINDS`/`EDGE_KINDS`, `parse_spec_nodes`, `parse_task_nodes`, `parse_contract_nodes` y `build_graph` como funciones puras, guiadas por encabezado (`table_rows`, `cell_codes`), sin cablearlas aún.

### T-02
**Estimate**
- Effort: Medium
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 55k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: tests de parsers con fixtures sintéticos: spec con 2 AC y 2 FR, tasks con T-16, carpeta con solo `contracts.md`.

### T-03
**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 1
- Tokens (est): 55k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: hook PreToolUse Read que solo avisa (una vez por sesión y archivo; silencio con `limit`/`offset` o con un evento `find_spec` en la sesión) y su `tests/test_read_hint.py`.

### T-04
**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.25
- Tokens (est): 62k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: `INDEX_VERSION` 4, columna `graph` en `dumps_index`/`loads_index`, `build_spec_entry` con nodes/edges, `memory_nodes_for`; un índice v3 se reconstruye sin excepción.

### T-05
**Estimate**
- Effort: Low
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 45k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: fila por defecto `PreToolUse Read` → `read_hint.py`, timeout corto, y actualizar `tests/test_install_hooks.py` con el nuevo conteo.

### T-06
**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 1
- Tokens (est): 62k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: `neighbours`, `locate_in_file`, `print_code` (≤25 líneas), `--code` en `main`, y `print_tree` reescrito sobre aristas unificadas.

### T-07
**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 1
- Tokens (est): 55k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: tests de extremo a extremo: `--code` ≤25 líneas, `--tree` no vacío sin mockup, reconstrucción de un índice v3, vecino MEM, y solo se re-parsea la spec tocada.

### T-08
**Estimate**
- Effort: Low
- Agent min: 5
- Human ref hours: 0.25
- Tokens (est): 20k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: copiar `skill/scripts/find_spec.py` al espejo y pasar `tests/test_dot_aidd_mirror.py`.

### T-09
**Estimate**
- Effort: Low
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 30k
- Agent role: docs
- Model tier: medium

**Decompose**
- Objective: en la regla W1 y en Step 6 de `skill/SKILL.md`, indicar `find_spec.py --code <CODE>` y que el auditor parte de los códigos cambiados más `check_spec.py`.

### T-10
**Estimate**
- Effort: Low
- Agent min: 5
- Human ref hours: 0.25
- Tokens (est): 20k
- Agent role: docs
- Model tier: medium

**Decompose**
- Objective: mismo ajuste de alcance del auditor en `commands/aidd-converge.md`.

### T-11
**Classify**
- Nature: `REQUIREMENT`
- Priority: 1
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 1
- Tokens (est): 55k
- Agent role: builder
- Model tier: high

**Decompose**
- Objective: en `aidd_evidence.py`: `'graph_snapshot'` en `PROJECT_KINDS` y sus filas exentas de la rotación (`_rotate_if_needed`); `'graph_miss'` en `SESSION_KINDS`; `append_graph_snapshot(root, session, name, label, sha256, nodes, edges, rev='')`; `blob_shas(root, rels)` extraído de `_code_state_git` (una sola implementación, sin cambio de comportamiento); `runs_find_spec(command)` reconoce además `aidd graphs show|repeats|changed|status` y `aidd search|tree`. Copiar al espejo.

### T-12
**Estimate**
- Effort: High
- Agent min: 35
- Human ref hours: 1.75
- Tokens (est): 110k
- Agent role: builder
- Model tier: high

**Decompose**
- Objective: `code_graph.py` según el plan: `build` incremental por sha (`previous=`), `file_shas` autocontenido (un `git hash-object --stdin-paths` con respaldo en Python; no importa `aidd_evidence`), `list_files`, `parse_file` (`ast` más `tokenize` para comentarios: FILE/FUNC/CLASS, defines/imports/calls/reads/spawns, markers), `resolve_calls` (ambiguos marcados, nunca descartados), `link_markers` (`implements` a ids planos), `main`. Copiar al espejo.

### T-13
**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 1
- Tokens (est): 70k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: `method_graph.py`: `build`, `parse_rules` (regex `^\| \*\*(R\d+)\*\*`; R8 ausente se reporta), `parse_steps` (`### Step N`), `link_enforcers` (token `Rn`/`aidd:Rn` en docstring o comentario leído con `tokenize`, `via: mention`), `unlinked`/`aidd:self-checked`, `main`. Copiar al espejo.

### T-14
**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.25
- Tokens (est): 80k
- Agent role: builder
- Model tier: high

**Decompose**
- Objective: `graph_trace.py`: `Tracer` con `sys.setprofile` y `threading.setprofile`, sinks cerrados, atribución a la FUNC del bundle AIDD (ids por nombre de archivo bajo `skill/scripts/`), `run_traced` que ejecuta el script del subcomando EN PROCESO con `runpy.run_path` y `sys.argv` parcheado y refresco de grafos desactivado (avisa ante `os._exit`), `merge_runtime`, `main`. Apagado por defecto. Copiar al espejo.

### T-15
**Estimate**
- Effort: High
- Agent min: 40
- Human ref hours: 2
- Tokens (est): 130k
- Agent role: builder
- Model tier: high

**Decompose**
- Objective: `graph_snapshot.py`: `canonical`, `snapshot` (archivo en `snapshots/<name>/<L>.json`, etiqueta validada, `--replace`, `--rev` con `git archive` a un tmp), `diff` (verifica sha256 contra el evento más reciente; exit 2 `snapshot altered`; imprime número de eventos y rev por etiqueta y avisa si fue reemplazada), `changed` (+`affected`), `repeats` (sinks, llamadas sin resolver y FUNCs), `entrypoints` (escaneo `ast` de las llamadas `_run("x.py", [sub, ...])` de `aidd/cli.py`). Ampliación por tamaño de tarea (FR-023/FR-042): `open_manifest(root, spec)` escribe `.aidd/graphs/snapshots/manifests/<spec-id>@open.json` = `{rel: sha}` de los archivos que vigila cada grafo (una pasada de `git hash-object`, sin parsear ni construir grafos) y `changed` lee ese manifiesto o, si no existe, un snapshot de grafo con la misma etiqueta. Copiar al espejo.

### T-16
**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 1
- Tokens (est): 60k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: `tests/test_code_graph.py` con proyecto temporal (`git init`) y evidencia temporal: caller→callee, sink `git` alcanzado de forma transitiva, SyntaxError = aviso, ambiguos, `implements` (p. ej. `latest_verify_run`→FR-205), `refresh --wait --force` imprime `re-parsed N, reused M`, `affected` con un import inverso, mismo tamaño + `os.utime` hacia atrás sigue como cambiado.

### T-17
**Estimate**
- Effort: High
- Agent min: 40
- Human ref hours: 2
- Tokens (est): 130k
- Agent role: builder
- Model tier: high

**Decompose**
- Objective: `aidd_graphs.py`: `_autodetect` con `code`/`method`/`spec`/`db-schema`/`db-dml` builtin y renombrado `code-<herramienta>` de toda fila `code` que no sea `builtin:code`; `_command` con las ramas nuevas (la de `builtin:sql` no cambia); `auto` deja de saltar el kind `spec` cuando su refresh es `builtin:spec`; `show` para code/method (≤25 líneas, unión en consulta con `find_spec` y `progress.json`); `status` por sha de los archivos que cada grafo vigila; `refresh --force` y `--wait` con la línea `re-parsed N, reused M`; `main` con `repeats|trace|snapshot|diff|changed`. Copiar al espejo.

### T-18
**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.25
- Tokens (est): 70k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: `tests/test_graph_snapshot.py`: sha del archivo = sha del evento, etiqueta inválida o repetida, rutas `<name>/<L>.json` sin colisión entre grafos, `--rev` ignora el árbol sucio, `diff` limpio y con archivo editado (exit 2), sin evento (exit 2), `changed` sin línea base (exit 2), y el manifiesto `<spec-id>@open` que toma `cmd_activate` en un proyecto temporal (AC-033: solo el manifiesto, ningún grafo ni snapshot al activar), con `changed` leyendo ese manifiesto o un snapshot de la misma etiqueta.

### T-19
**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 1
- Tokens (est): 60k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: `tests/test_graph_trace_method.py`: regla R10 con enforcer y regla `unlinked`, R8 ausente, `repeats` con sink por dos caminos y en bucle, `--cmd` desconocido, `trace` dos veces con los mismos conteos de lectura y de spawn, `status` con cuatro grafos y ninguno `no-refresh`.

### T-21
**Estimate**
- Effort: Low
- Agent min: 12
- Human ref hours: 0.6
- Tokens (est): 35k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: en `tests/test_dot_aidd_mirror.py`: añadir los cuatro scripts nuevos a `VERBATIM_SCRIPTS` (L61), una prueba de que cada uno responde `--help` con rc 0 usando solo stdlib, y una prueba de texto que exige que SKILL.md, AIDD.md y aidd-converge.md nombren `builtin:code`, `repeats`, `trace`, `snapshot` y `diff`.

### T-22
**Estimate**
- Effort: Low
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 45k
- Agent role: docs
- Model tier: medium

**Decompose**
- Objective: en G1, W1 y Step 6 de `skill/SKILL.md`: `builtin:code`/`method`/`spec`, `db-schema`/`db-dml`, `repeats`, `trace`, `snapshot`/`diff`/`changed`, el aviso de grafo primero (qué lo silencia y qué no) y que los comparativos usan snapshots del grafo, nunca archivos editados a mano.

### T-23
**Estimate**
- Effort: Low
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 30k
- Agent role: docs
- Model tier: medium

**Decompose**
- Objective: la misma descripción del grafo de código, los snapshots y el aviso de grafo primero en `skill/AIDD.md` y su copia idéntica `adapters/dot-aidd/AIDD.md`.

### T-24
**Estimate**
- Effort: Low
- Agent min: 5
- Human ref hours: 0.25
- Tokens (est): 20k
- Agent role: docs
- Model tier: medium

**Decompose**
- Objective: en `commands/aidd-converge.md`, el auditor cita `aidd graphs diff <A> <B>` y ambos hashes para cualquier comparativo antes/después.

### T-25
**Estimate**
- Effort: Medium
- Agent min: 40
- Human ref hours: 2
- Tokens (est): 90k
- Agent role: tests
- Model tier: high

**Decompose**
- Objective: con todos los builders terminados, (1) sincronizar la skill instalada con el repo y comprobar que `diff -rq skill/scripts ~/.claude/skills/aidd/scripts` queda vacío (el CLI usa primero la instalada); (2) ejecutar `aidd verify specs/004-aidd-graph-first`; (3) tomar los snapshots `before` (`--rev 69218be`) y `after` (árbol de trabajo) y correr `repeats`; (4) `trace` en b1SycLink dos veces; (5) el dogfood de este spec (AC-016/AC-017); (6) `sql_graph` y `db-schema`/`db-dml` sobre las migraciones de b1SycLink (AC-021/AC-022); (7) AC-019/AC-020 con una búsqueda real; (8) AC-023..AC-026 (regla E9, hook sin repetición, presupuestos de ejecución) y AC-027..AC-033 (`aidd job`, `aidd triage`, `aidd tools`, `aidd size`, activar solo con manifiesto) con las pruebas ya escritas, sin repetirlas. Protocolo E9 para esta misma tarea: UNA corrida de `aidd verify specs/004-aidd-graph-first` (las filas corren en paralelo por `Jobs: 4`) y UNA de `python tests/run_parallel.py --changed`, sin repetir ninguna sobre el mismo estado del código; informar tiempo de reloj y tokens de cada una; guardar la salida bajo `specs/004-aidd-graph-first/evidence/` y una fila R10 por código.

### T-26
**Estimate**
- Effort: Low
- Agent min: 20
- Human ref hours: 1
- Tokens (est): 55k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: en `aidd_status.py`: `cmd_activate` (L1318) toma SOLO el manifiesto de hashes `<spec-id>@open` si falta (llamando a `graph_snapshot.open_manifest` en proceso: una pasada de hash, sin construir ni parsear grafos y sin procesos de fondo; si falla, solo avisa), y `aidd status` imprime `graph-first: N misses / M searches this session` a partir de los eventos `graph_miss`. Copiar al espejo.

### T-27
**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.25
- Tokens (est): 70k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: `read_hint.py` cubre `Read`, `Grep`, `Glob` y `Bash`/`PowerShell` de búsqueda o lectura (`grep`, `rg`, `cat`, `sed`, `type`, `Select-String`, `findstr`) sobre código y specs; solo una consulta del agente (`source='bash'`) callan 300 s, nunca la del hook; registra `graph_miss{tool,target}`; el mensaje nombra el grafo a construir si no existe. Solo avisa, nunca bloquea.

### T-28
**Estimate**
- Effort: Low
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 30k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: el matcher de `read_hint` en `install_hooks.py` pasa a `Read|Grep|Glob|Bash|PowerShell` y `tests/test_install_hooks.py` se ajusta solo si cuenta matchers.

### T-29
**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 1
- Tokens (est): 55k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: `tests/test_read_hint.py`: AC-019 (la consulta del hook no silencia, la del agente calla 300 s y luego avisa de nuevo; `Grep` y `grep` por Bash avisan; los `.py` cuentan) y AC-020 (tres búsquedas → `2 misses / 3 searches`).

### T-30
**Estimate**
- Effort: Low
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 40k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: `mark_graph_rebuild.py` registra como consulta del agente (`source='bash'`) toda orden que `aidd_evidence.runs_find_spec` reconozca, no solo `find_spec.py`.

### T-31
**Estimate**
- Effort: High
- Agent min: 60
- Human ref hours: 3
- Tokens (est): 180k
- Agent role: sql
- Model tier: high

**Decompose**
- Objective: en `sql_graph.py`: FR-028 (protección del `KeyError` de `analyze_sql`, contado en `skipped_statements`), FR-029 (`--kind schema` con checkpoint JSON por prefijo de migraciones; reproduce solo la cola, todo si cambia una vieja; sin `pickle`) y FR-030 (`--kind dml` con caché por `sha(cuerpo)` + hash del esquema de las tablas tocadas). Si el modelo no se serializa a JSON tal cual, se detiene y lo reporta. Copiar al espejo.

### T-32
**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.25
- Tokens (est): 70k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: `tests/test_sql_graph_incremental.py` con migraciones sintéticas: fixture del alias `oitw` (sin excepción, `skipped_statements > 0`), añadir una migración reproduce 1 archivo, editar una vieja reproduce todas y lo dice, cambiar una tabla reanaliza solo los cuerpos que la tocan.

### T-33
**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.25
- Tokens (est): 80k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: `prompt_trigger.py` deja de repetir el mismo paso en cada mensaje (FR-032): no ejecuta `find_spec` ni inyecta el bloque Step -1 para mensajes de sistema o de agentes (prompt que empieza por `<` o `[`, notificaciones de tareas, reportes de subagentes), ni cuando los mismos términos ya se respondieron en la sesión contra un `specs/index.toon` sin cambios (hash del contenido del índice, no mtime) en los últimos 15 minutos; el estado vive por sesión en el directorio temporal `aidd-hooks`; el evento `find_spec` con `source='hook'` solo se escribe cuando `find_spec` realmente corrió; el registro del prompt y el resto del comportamiento no cambian. El hint de una vez por sesión nombra además `aidd tools`, `aidd graphs`, `aidd job`, `aidd triage` y `aidd size` (FR-040, FR-043). Confirmar con `VERBATIM_HOOKS` si el hook se espeja.

### T-34
**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 1
- Tokens (est): 55k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: reemplazar el placeholder `tests/test_prompt_trigger.py` con pruebas reales de AC-024: diez mensajes (seis de agentes o notificaciones, tres con los mismos términos) dan como máximo 2 ejecuciones de `find_spec` y 2 bloques inyectados, y los mensajes omitidos no dejan evento `find_spec` con `source='hook'`; un índice cambiado vuelve a ejecutar; el hint de la primera vez nombra `aidd tools`, `aidd graphs`, `aidd job`, `aidd triage` y `aidd size`. Puede correr SU módulo una sola vez.

### T-35
**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.25
- Tokens (est): 70k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: reemplazar el placeholder `tests/test_perf_budget.py` con presupuestos medidos en ejecución (FR-034, AC-026), solo conteos y razones: la reconstrucción sin cambios de `code_graph` re-parsea 0 archivos y es al menos 2x más rápida que la completa en un proyecto temporal, `graph_snapshot.changed` sobre un árbol sin cambios hace exactamente 1 spawn de `git hash-object` (contado con `graph_trace`), y un segundo prompt idéntico hace 0 spawns de `find_spec` en `prompt_trigger`. Puede correr SU módulo una sola vez.

### T-36
**Estimate**
- Effort: Low
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 50k
- Agent role: docs
- Model tier: medium

**Decompose**
- Objective: en `skill/SKILL.md`, junto a E1-E8, añadir la regla `E9` (economía de verificación, FR-031: no repetir la misma verificación sobre el mismo estado del código; selección por cambio con `tests/run_parallel.py --changed`; tiempos por módulo antes de repetir tras más de 2 minutos; pruebas que afirman conteos y razones y tiempos solo con margen 3x; reportar tiempo de reloj y tokens), la regla `T1` (tool-first, FR-040: antes de hacer a mano un paso repetitivo, largo o comprobable se ejecuta `aidd tools <palabras>` y se usa la herramienta; el camino manual necesita una razón escrita) y la regla `P1` (proporcionalidad, FR-042: `aidd size` clasifica XS/S/M/L y entrega los parámetros de análisis; lo que la clase excluye no se crea: un cambio XS nunca construye un grafo, snapshot o job nuevo; la tabla de parámetros por clase). Describir `aidd job` y `aidd triage` y el contrato `RESULT:` de las herramientas (FR-035..FR-037). Corregir las frases que mandan ejecutar "cada vez": `check_spec.py` se corre una vez antes de la auditoría de cierre y tras la última edición de spec/plan/tasks (FR-033). No dejar la frase "every time" ligada a una ejecución.

### T-37
**Estimate**
- Effort: Low
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 40k
- Agent role: docs
- Model tier: medium

**Decompose**
- Objective: las mismas reglas `E9`, `T1` y `P1`, la descripción de `aidd job`/`aidd triage`/`aidd tools`/`aidd size` y la corrección de `check_spec.py` en `skill/AIDD.md`, y copia idéntica a `adapters/dot-aidd/AIDD.md` (`cmp` debe dar idéntico).

### T-38
**Estimate**
- Effort: Low
- Agent min: 5
- Human ref hours: 0.25
- Tokens (est): 20k
- Agent role: docs
- Model tier: medium

**Decompose**
- Objective: en `commands/aidd-converge.md`, `check_spec.py` se corre una vez antes de la auditoría de cierre (no antes de cada pase manual), la verificación ejecutada sigue la regla E9 y el auditor parte de los parámetros de análisis de `aidd size`; mantener las palabras `builtin:code`, `repeats`, `trace`, `snapshot` y `diff` que exige la prueba de documentos.

### T-39
**Estimate**
- Effort: High
- Agent min: 40
- Human ref hours: 2
- Tokens (est): 130k
- Agent role: builder
- Model tier: high

**Decompose**
- Objective: `skill/scripts/aidd_job.py` (FR-035, FR-036) con los subcomandos `run [--bg] [--key globs] [--name n] [--force] -- <cmd...>`, `wait <id>`, `last <name>`, `list`: `inputs_hash` = sha256 de los hashes de contenido de los archivos que cumplen `--key` (por defecto los globs de código y tests; reutiliza `code_graph.file_shas`/`list_files` con respaldo en stdlib; nunca mtime); veredicto en `.aidd/jobs/<name>-<inputs8>/verdict.json` y `log.txt`; misma entrada y mismo comando = imprime el veredicto marcado `CACHED` sin ejecutar; `--bg` lanza un proceso desacoplado y devuelve el id, `wait` bloquea hasta que termina y devuelve el código de la herramienta, `last` devuelve el veredicto o el código 3 si las entradas cambiaron o no hay; parsea la línea final `RESULT: ok|fail|stale|refused - <N> items - evidence <path>` o la deriva del código de salida; solo el CLI escribe `.aidd/jobs/`; antifragil (timeouts, un veredicto ilegible se ignora y se re-ejecuta). Copiar al espejo.

### T-40
**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.25
- Tokens (est): 70k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: `skill/scripts/aidd_triage.py` (FR-037), port de `D:\Fuentes\b1SycLink\tools\verify_triage.py` (79 líneas; leerlo entero, es el origen): solo lectura, stdlib, sin LLM; lee `specs/<id>/evidence/verify-*.txt` de cada spec (o de los indicados), lista las filas PASS/FAIL, extrae los ítems fallidos (pgTAP `[FAIL] x.test.sql`, vitest ` FAIL  file > test`, pytest `FAILED file::test`, errores de `tsc`) y agrupa los que fallan en 2 o más specs como compartidos; `--json`; no escribe nada. Copiar al espejo.

### T-41
**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.25
- Tokens (est): 70k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: reemplazar el placeholder `tests/test_aidd_job.py` con pruebas de AC-027 sobre una herramienta de juguete en un proyecto temporal (que cuenta sus ejecuciones en un archivo): `run` dos veces sin cambios imprime `CACHED` y la herramienta se ejecutó una sola vez; tras editar un archivo vigilado se ejecuta de nuevo; el hash es de contenido (mismo tamaño con mtime restaurado también invalida); `--bg` + `wait` devuelve el código de la herramienta; `last` devuelve 3 cuando las entradas cambiaron; el veredicto trae el sha256 de las entradas y los segundos; la línea `RESULT:` se parsea y su ausencia se deriva del código de salida; un veredicto corrupto se ignora. Puede correr SU módulo una sola vez.

### T-42
**Estimate**
- Effort: Low
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 45k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: reemplazar el placeholder `tests/test_aidd_triage.py` con pruebas de AC-028: dos specs temporales cuya evidencia de verify lista el mismo archivo pgTAP `a.test.sql` y una también `b.test.sql` (más casos vitest, pytest y tsc): `a` aparece compartido por 2 specs y `b` específico, `--json` es válido y no se escribe nada. Puede correr SU módulo una sola vez.

### T-43
**Estimate**
- Effort: Low
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 45k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: `aidd/cli.py` reenvía `job`, `triage`, `tools` y `size` a sus scripts como ya hace con `graphs` (REMAINDER y `_run("<script>.py", [...])`; `size` va a `aidd_tools.py size ...`); sin tocar otros subcomandos. Revisar con grep si algún test de `tests/` lista los subcomandos del CLI y reportar qué aserción cambia (sin editarla) y si hay una lista de scripts empaquetados en `pyproject.toml`/`MANIFEST.in` que deba incluir los scripts nuevos.

### T-44
**Estimate**
- Effort: Medium
- Agent min: 40
- Human ref hours: 2
- Tokens (est): 100k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: `skill/scripts/aidd_tools.py` (FR-039, FR-041, FR-042): (1) `aidd tools [keywords] [--json]`: catálogo agrupado por tarea (verify, graph, db, docs, generate, gate) de los comandos de AIDD y de las herramientas del proyecto (carpetas `tools/`, `*/tools/`, `*/scripts/`; `.py`, `.ps1`, `.sh`) con una línea cada una: la primera línea de documentación del script y los flags `--plan`/`--check`/`--dry-run` si su texto los menciona; filtrado por palabras, salida de hasta 40 líneas, escaneo del proyecto cacheado por el hash de contenido de esas carpetas; (2) `aidd tools size [--spec <id> | --files <f...>] [--json]` (FR-042): clasifica XS/S/M/L con las entradas medibles (número de archivos de destino de `tasks.md` o `--files`, archivos cambiados desde `<spec-id>@open` y su `affected` si existe el manifiesto, áreas sensibles: base de datos, hooks, CLI, reglas del gate, cruce entre specs) con los umbrales del spec (XS = 1 archivo sin área sensible; S = 2; M = 3 a 8; L = más de 8, área sensible o cruce) e imprime la clase y los parámetros de análisis de la clase (grafo, línea base, pruebas, verificación, auditoría, agentes) exactamente como en FR-042; lo que la clase excluye no se crea. Stdlib, nunca lanza; `--help` con 0. Copiar al espejo.

### T-45
**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 1
- Tokens (est): 65k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: reemplazar el placeholder del módulo (crear `tests/test_aidd_tools.py` si el stub aún no existe) con pruebas de AC-030 y AC-032: en un proyecto temporal con `tools/` y `eDoc/tools/`, `aidd tools db` lista las herramientas con su primera línea de documentación y sus flags `--dry-run`/`--check`, respeta el tope de 40 líneas y la segunda corrida reutiliza la caché; `size` clasifica 1 archivo como XS, 2 como S, 4 como M y 9 archivos (o un archivo de hooks o SQL) como L, e imprime los parámetros de cada clase (XS: sin refresh, sin línea base, pruebas por `run_parallel --changed`, sin auditor; L: snapshots antes/después y auditor por dominio). Puede correr SU módulo una sola vez.

### T-46
**Estimate**
- Effort: Low
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 35k
- Agent role: docs
- Model tier: medium

**Decompose**
- Objective: en `skill/templates/tasks.md`, en la lista de estándares que cada prompt de Builder/Auditor repite, añadir la línea tool-first (antes de hacer a mano un paso repetitivo, largo o comprobable, ejecutar `aidd tools <palabras>` y usar la herramienta; el camino manual necesita una razón escrita) y la línea `Analysis parameters: <salida de aidd size para esta tarea>`, y documentar el campo opcional `Size:` (XS|S|M|L; informativo, no es un gate) en el bloque de detalle de la tarea. No tocar la variante reducida de adapters.

### T-47
**Estimate**
- Effort: Medium
- Agent min: 40
- Human ref hours: 2
- Tokens (est): 100k
- Agent role: builder
- Model tier: high

**Decompose**
- Objective: en `skill/scripts/aidd_rules.py` (FR-045, FR-046): (1) `_read(p)` lee por `aidd_evidence.cached_read(path, reader)` (firma fijada en plan.md; sin el alcance activo se comporta como hoy) y cada función de este módulo que escribe un archivo llama antes a `aidd_evidence.forget_read(path)`; (2) `closing_audit_diagnosis(spec_dir, root) -> list[str]`: una línea por problema con las MISMAS condiciones que `closing_audit_covers` (dominio requerido sin auditor que cuente tras la última edición de código y el último `verify_run`, auditor haiku, `[tasks:<h8>]` o `[verify:<v8>]` distinto, informe menor que `CLOSING_AUDIT_MIN_RESULT`, auditor anterior a `code_since`); extraer UNA función `_closing_audit_reason(...) -> str|None` (reutilizando `_subagent_counts`, `closing_audit_header`, `_result_chars` y `latest_verify_run`, y la condición gate-2 del tag `[verify:]`) y hacer que `closing_audit_covers` sea `reason is None` y el diagnóstico la use, para que las dos no puedan divergir; el aviso de "dominio requerido sin auditor" va por su propio camino porque `covers` recibe un conjunto de dominios; nunca lanza. No cambiar la semántica de ninguna regla. Copiar al espejo. Autochequeo estático solamente.

### T-48
**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.25
- Tokens (est): 70k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: en `skill/scripts/aidd_evidence.py` (FR-045): `read_cache()` (context manager que activa `_READ_CACHE` por proceso y lo vacía al salir, apagado por defecto), `cached_read(path, reader)` (con el alcance activo devuelve el texto guardado solo si `(size, mtime_ns)` del `os.stat` actual coincide; fuera del alcance llama a `reader(path)` sin guardar), `forget_read(path=None)`; `append` y toda escritura de este módulo llaman a `forget_read`; `_read_rows` lee por `cached_read`. Ningún hook entra al alcance. Copiar al espejo. Autochequeo estático solamente.

### T-49
**Estimate**
- Effort: Medium
- Agent min: 30
- Human ref hours: 1.5
- Tokens (est): 80k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: en `skill/scripts/aidd_status.py` (FR-045, FR-046): los comandos `status` y `progress` corren dentro de `with aidd_evidence.read_cache():`; bajo cada spec abierta imprime las líneas de `aidd_rules.closing_audit_diagnosis` y, si faltan dominios, la línea `next: dispatch one auditor per missing domain (<lista>) in ONE message`; sin problemas no imprime nada nuevo. No tocar `cmd_activate` ni la línea `graph-first`. Copiar al espejo. Autochequeo estático solamente.

### T-50
**Estimate**
- Effort: Low
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 30k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: en `skill/hooks/prompt_trigger.py` (FR-047): constante `FIND_SPEC_TIMEOUT = 8` usada en la llamada a `find_spec` (hoy `timeout=10` en la línea de `subprocess`), siempre menor que el timeout del hook que registra `install_hooks.py`; sin cambiar el dedupe ni el resto.

### T-51
**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.25
- Tokens (est): 60k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: en `skill/scripts/aidd_job.py` (FR-048): `_valid_job_id(s)` (regex `^[A-Za-z0-9_.-]+$` sin `..`) y `_job_dir(root, id)` (resuelve bajo `.aidd/jobs/`, `None` si escapa) usados por `wait`, `last` y `_exec` (salida 2 con `refused`); el `cmd` guardado en `job.json` y `verdict.json` pasa por `aidd_evidence.redact_secrets` (import en try/except); añadir `.aidd/jobs/` a `.gitignore`. Copiar el script al espejo. No cambiar la semántica de CACHED. Autochequeo estático solamente.

### T-52
**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.25
- Tokens (est): 65k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: en `tests/test_aidd_rules.py` (AC-037, AC-038): dentro de `read_cache()` una segunda lectura toca el disco una vez; un archivo reescrito dentro del alcance (también con el mismo tamaño) se lee de nuevo; fuera del alcance nunca se usa la caché; ni `rule_gate` ni los hooks ni una decisión de gate abren `read_cache()` (prueba por búsqueda del símbolo en `skill/hooks/` y en las funciones de decisión); `closing_audit_diagnosis` en un spec temporal con cuatro casos (sin auditor, tag distinto, haiku, edición de código posterior) devuelve la línea con el dominio y la razón, y vacía con todos los dominios cubiertos. Puede correr SU módulo una sola vez.

### T-53
**Estimate**
- Effort: Medium
- Agent min: 20
- Human ref hours: 1
- Tokens (est): 55k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: en `tests/test_perf_budget.py` (AC-036): con `graph_trace` sobre un proyecto temporal, `status` lee cada archivo de decisión una sola vez dentro del alcance (conteos de lecturas y relecturas, nunca tiempos de reloj) y dos corridas coinciden en todos los conteos. Puede correr SU módulo una sola vez.

### T-54
**Estimate**
- Effort: Low
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 45k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: en `tests/test_aidd_status.py` (AC-038): `aidd status` imprime, bajo la spec, la línea de diagnóstico y el `next: dispatch one auditor per missing domain` cuando faltan dominios, y nada de eso con todos cubiertos. Puede correr SU módulo una sola vez.

### T-55
**Estimate**
- Effort: Low
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 45k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: en `tests/test_aidd_job.py` (AC-040): `aidd job wait ../x` y `aidd job last "a/b"` salen con 2 y `refused` sin leer fuera de `.aidd/jobs/`; `job.json` y `verdict.json` guardan `--token=[redacted]`; `.gitignore` contiene `.aidd/jobs/`. Puede correr SU módulo una sola vez.

### T-56
**Estimate**
- Effort: Low
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 30k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: en `tests/test_prompt_trigger.py` (AC-039): `FIND_SPEC_TIMEOUT` es como máximo 8 y menor que el timeout de hook que registra `install_hooks.py`. Puede correr SU módulo una sola vez.

### T-57
**Estimate**
- Effort: Low
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 40k
- Agent role: docs
- Model tier: medium

**Decompose**
- Objective: en `skill/SKILL.md` (FR-046(b)): una sola sección "Close sequence" con los cinco pasos (congelar el código, `aidd verify` una vez, UN mensaje con un auditor por dominio requerido, escribir `qa-audit.md`, aprobar y `aidd rules close`) y la frase "any code edit after the dispatch voids those auditors"; reemplazar las frases que hoy presentan dos caminos sin decir cuál cuenta. No tocar otras secciones.

### T-58
**Estimate**
- Effort: Low
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 30k
- Agent role: docs
- Model tier: medium

**Decompose**
- Objective: lo mismo que T-57 en `skill/AIDD.md` y copia idéntica a `adapters/dot-aidd/AIDD.md` (mismas palabras, mismo orden de pasos).

### T-59
**Estimate**
- Effort: Medium
- Agent min: 40
- Human ref hours: 2
- Tokens (est): 90k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: verificador de la ola 10: sincroniza la skill instalada con el repo (`diff -rq skill/scripts ~/.claude/skills/aidd/scripts` vacío), corre `aidd verify specs/004-aidd-graph-first` UNA vez (E9), mide AC-036 con `graph_trace.py --root D:\Fuentes\AIDD -- status` dos veces y guarda la salida y los tiempos por fila bajo `specs/004-aidd-graph-first/evidence/`, y escribe las filas R10 de FR-044..FR-048. No edita código fuente.

### T-60 — failing tests first
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: S

**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.0
- Tokens (est): 90k
- Agent role: tests
- Model tier: medium
- Wave: 11

**Detail**
- Goal: encode AC-041..AC-046 and the FR-054 normalisation as unit tests that fail on the current code.
- Cites: FR-049..FR-054, AC-041..AC-046.
- Depends on: none.
- Read first: `tests/test_read_hint.py` lines 1-80 (`ReadHintCase.setUp`, `run_hook`, `_env`, `add_find_spec`, `ctx`) and lines 211-227 (`test_ac020_status_line_end_to_end`); `skill/scripts/aidd_evidence.py` lines 147-179 and 710-770; `skill/scripts/aidd_status.py` lines 173-190 and 710-725.
- Files to change: `tests/test_tool_first_hint.py` (new).
- Naming contract: `HOOK = ROOT / "skill" / "hooks" / "tool_first_hint.py"`; class `ToolFirstHintCase(unittest.TestCase)` with helpers `run_hook(self, stdin)`, `_env(self)` (context manager, copy of `ReadHintCase._env`), `edit_ev(self, rel, old, new)` -> dict with `tool_name='Edit'`, `shell_ev(self, command, tool='Bash')` -> dict, `ctx(self, r)` -> str, `misses(self)` -> list of `tool_miss` details, `add_query(self, source, age=0.0)` (appends a `tool_query` event with `aidd_evidence.time.time` patched to `time.time() - age`), `load_hook(self)` -> module loaded with `importlib.util.spec_from_file_location("tool_first_hint", HOOK)`. Test methods: `test_shape_normalises_quotes_paths_digits`, `test_ac046_owner_case_four_status_edits`, `test_ac041_one_advisory_only`, `test_ac042_unrelated_shapes_no_advisory`, `test_same_file_four_edits_fires_same_file`, `test_window_older_than_900s_does_not_count`, `test_shell_four_consecutive_same_shape`, `test_shell_run_broken_by_other_command`, `test_read_only_git_never_counts`, `test_aidd_tools_command_records_tool_query`, `test_ac043_tools_query_silences_for_300s`, `test_hook_source_query_does_not_silence`, `test_ac044_corrupt_state_file`, `test_malformed_stdin`, `test_no_project_root_no_output`, `test_edits_counter_counts_every_edit_tool`, `test_ac045_status_line`, `test_new_kinds_are_session_kinds`. Production names exercised: `tool_first_hint._shape(text) -> str`; `aidd_evidence.tool_first_state_path(session) -> Path`; `aidd_evidence.read_tool_first_state(session) -> dict`; `aidd_status._tool_first_line(root=None) -> str`; event kinds `tool_miss`, `tool_query`. Hook payload keys used (Claude Code `PostToolUse` schema): `session_id`, `cwd`, `tool_name`, `tool_input`; `tool_input` keys `file_path`, `old_string`, `new_string`, `edits`, `content`, `notebook_path`, `new_source`, `command`.
- Behaviour:
  1. `setUp`: temp root with `specs/F36-eDoc-Purchasing`, `specs/F37-eDoc-Supplier-Invoice`, `specs/F38-eDoc-Import-Costing`, `specs/F39-eDoc-X` directories, each with a `tasks.md`; `self.evid = root/"evid"`; `self.sid = f"test-{uuid.uuid4().hex}"`; `self.env = dict(os.environ, AIDD_TESTING="1", AIDD_EVIDENCE_DIR=str(self.evid))`; `run_hook` runs `[sys.executable, str(HOOK)]` with `cwd=str(self.root)`, `timeout=15`.
  2. Row text used by AC-046: `ROW = "| T-{t} | FR-{f} | `eDoc/supabase/migrations/{m}.sql` | LOGIC | | {s} |"`; the four calls use `(t, f, m)` = `(91, 12, "3411_pinv_base")`, `(92, 13, "3412_pinv_ret")`, `(93, 14, "3413_imc_base")`, `(94, 15, "3414_imc_cost")`, `old` with `s=""` and `new` with `s="done"`, one file each in the order F36, F37, F38, F39.
  3. `test_shape_normalises_quotes_paths_digits`: `_shape(ROW.format(t=91, f=12, m="3411_pinv_base", s="done")) == "| T-<N> | FR-<N> | <Q> | LOGIC | | done |"`; `_shape("python tools/gen_f36_tests.py --apply specs/F36") == "python <P> --apply <P>"`; `_shape('a  "x"\n  \'y\' 7') == "a <Q> <Q> <N>"`.
  4. `test_ac046_owner_case_four_status_edits`: calls 1-3 → `stdout == ""`; call 4 → `ctx` contains `aidd tools md` and `4 edits with the same shape`; `misses()` has one item with `kind == "same_shape"` and `count == 4`; `test_ac041_one_advisory_only` adds a 5th call with `t=95` on `specs/F36-eDoc-Purchasing/tasks.md` → `stdout == ""` and still one `tool_miss`.
  5. `test_ac042_unrelated_shapes_no_advisory`: 4 Edit calls on the 4 different files with `old`/`new` `("alpha", "beta")`, `("x = 1", "x = 2; y")`, `("## A", "## B\nmore")`, `("foo()", "bar(baz)")` → all `stdout == ""`, `misses() == []`.
  6. `test_same_file_four_edits_fires_same_file`: the 4 calls of step 5 all on `specs/F36-eDoc-Purchasing/tasks.md` → call 4 advises, `misses()[0]["kind"] == "same_shape"` is false and `== "same_file"` is true, `ctx` contains `specs/F36-eDoc-Purchasing/tasks.md`.
  7. `test_window_older_than_900s_does_not_count`: run calls 1-3 of step 2, then rewrite the state file (path from `aidd_evidence.tool_first_state_path(self.sid)` inside `_env`) subtracting 901 from every timestamp in `shapes` and `files`, then call 4 → `stdout == ""`.
  8. `test_shell_four_consecutive_same_shape`: 4 Bash calls `python tools/gen_f3{n}_tests.py --apply specs/F3{n}` for n = 6..9 → 4th has `ctx` containing `4 shell commands in a row with the same shape` and `aidd tools python gen_f39_tests`; `misses()[0]["kind"] == "same_command"`. `test_shell_run_broken_by_other_command`: 3 such calls, then `python -m unittest -v`, then a 4th such call → all `stdout == ""`.
  9. `test_read_only_git_never_counts`: 5 Bash calls `git status` then 5 PowerShell calls `git log -n 3` → all `stdout == ""`, `misses() == []`.
  10. `test_aidd_tools_command_records_tool_query`: Bash `aidd tools migration` → `stdout == ""`; one `tool_query` event in the session with `detail["source"] == "agent"`.
  11. `test_ac043_tools_query_silences_for_300s`: `add_query("agent")`, then the 4 calls of step 2 → no output, `misses() == []`; new session id, `add_query("agent", age=301)`, the 4 calls → call 4 advises. `test_hook_source_query_does_not_silence`: `add_query("hook")`, the 4 calls → call 4 advises.
  12. `test_ac044_corrupt_state_file`: inside `_env`, write bytes `b"\xff{"` to `tool_first_state_path(self.sid)` (create parent dirs), run one Edit → `(returncode, stdout, stderr) == (0, "", "")`; the state file is now valid JSON with `edits == 1`. `test_malformed_stdin`: stdin `"{not json"` → `(0, "")`. `test_no_project_root_no_output`: a second temp dir with no `specs/` and no `.aidd/`, the 4 calls of step 2 with that `cwd` → all `stdout == ""` and no state file for the session.
  13. `test_edits_counter_counts_every_edit_tool`: one `Write` (`file_path`, `content`), one `NotebookEdit` (`notebook_path`, `new_source`), one `MultiEdit` (`file_path`, `edits=[{"old_string":"a","new_string":"b"}]`), one `Edit` → `aidd_evidence.read_tool_first_state(self.sid)["edits"] == 4`.
  14. `test_ac045_status_line`: the 4 calls of step 2 then the 4 shell calls of step 8 → with `_env()` and `unittest.mock.patch.object(aidd_status, "_current_session", return_value=self.sid)`: `aidd_status._tool_first_line(self.root) == "tool-first: 2 advisories / 4 edits this session"`; with a fresh session id → `"tool-first: 0 advisories / 0 edits this session"`.
  15. `test_new_kinds_are_session_kinds`: `{"tool_miss", "tool_query"} <= aidd_evidence.SESSION_KINDS`.
- Tests first: this task IS the tests; run `python -m unittest tests.test_tool_first_hint -v` and keep the red output (every test fails or errors on current code because the hook file and helpers do not exist).
- Verify: `python -m unittest tests.test_tool_first_hint -v` → red before T-61/T-63/T-65, exit 0 after.
- Do NOT: touch production code; use a database, Docker or the network; write outside the temp dirs; weaken an assertion later.
- Done when: the 18 tests exist with exactly these names and the red run is recorded by the verifier.
- Open questions: none.

### T-65 — evidence kinds and state path in `aidd_evidence.py`
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: S

**Estimate**
- Effort: Low
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 50k
- Agent role: builder
- Model tier: medium
- Wave: 12

**Detail**
- Goal: route `tool_miss` and `tool_query` to the per-session log and give the hook and `aidd status` one shared path for the per-session state file.
- Cites: FR-051, FR-052, FR-053.
- Depends on: T-60.
- Read first: `skill/scripts/aidd_evidence.py` lines 134-179; `tests/test_evidence.py` lines 390-410.
- Files to change: `skill/scripts/aidd_evidence.py`; `tests/test_evidence.py` (lines 398-408 only).
- Naming contract: `SESSION_KINDS` gains `'tool_miss'` and `'tool_query'` with the comment `# aidd:FR-051 aidd:FR-052 tool_query / tool_miss: the tool-first hook (per-session evidence)`; new `def tool_first_state_path(session) -> Path` returning `_sessions_dir() / (_safe_sid(session) + '.tool-first.json')`; new `def read_tool_first_state(session) -> dict` returning the parsed JSON object or `{}`.
- Behaviour:
  1. Tests first in `tests/test_evidence.py`: after line 398 add `ev.append(self.root, "s", "tool_miss", kind="same_shape", target="x", count=4)` and `ev.append(self.root, "s", "tool_query", source="agent", command="aidd tools x")`; change both `19` on lines 407-408 to `21`; run it red.
  2. Add the two kinds to the `SESSION_KINDS` frozenset literal on lines 147-148.
  3. Add `tool_first_state_path` and `read_tool_first_state` directly after `_session_path` (line 179). `read_tool_first_state`: `json.loads(path.read_text(encoding='utf-8'))`; return it only when it is a `dict`; on `(OSError, UnicodeDecodeError, ValueError)` return `{}`. Never raises.
- Tests first: step 1; `python -m unittest tests.test_evidence -v` red before step 2.
- Verify: `python -m unittest tests.test_evidence -v` → exit 0; `python -m unittest tests.test_tool_first_hint.ToolFirstHintCase.test_new_kinds_are_session_kinds -v` → exit 0.
- Do NOT: change `PROJECT_KINDS`, rotation, spill or lock code; write the state file from this module; touch `adapters/` (T-66 does the mirror).
- Done when: both verify commands pass.
- Open questions: none.

### T-61 — the hook `skill/hooks/tool_first_hint.py`
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: M

**Estimate**
- Effort: High
- Agent min: 40
- Human ref hours: 2.0
- Tokens (est): 140k
- Agent role: builder
- Model tier: high
- Wave: 13

**Detail**
- Goal: implement FR-049..FR-051, FR-053 and FR-054 so the hook tests of T-60 pass; the hook only advises and always exits 0.
- Cites: FR-049, FR-050, FR-051, FR-053, FR-054.
- Depends on: T-60, T-65.
- Read first: `skill/hooks/read_hint.py` lines 1-30, 122-151, 226-295; `skill/hooks/_common.py` lines 99-126; `skill/scripts/aidd_evidence.py` lines 134-179 (after T-65), 710-720, 1284-1290; the tests created by T-60 in the file named in T-60's Files to change.
- Files to change: `skill/hooks/tool_first_hint.py` (new).
- Naming contract: constants `N_REPEAT = 4`, `WINDOW_S = 900`, `SILENCE_S = 300`, `MAX_KEYS = 200`, `EDIT_TOOLS = frozenset({'Edit', 'Write', 'MultiEdit', 'NotebookEdit'})`, `SHAPE_TOOLS = frozenset({'Edit', 'MultiEdit'})`, `SHELL_TOOLS = frozenset({'Bash', 'PowerShell'})`, `READ_ONLY_GIT_RE = re.compile(r'^\s*git\s+(?:status|log|diff)\b', re.I)`, `TOOLS_QUERY_RE = re.compile(r'\baidd(?:\.exe)?\s+tools\b|aidd_tools\.py', re.I)`, `QUOTED_RE = re.compile(r'`[^`\n]*`|"[^"\n]*"|\'[^\'\n]*\'')`, `PATHLIKE_RE = re.compile(r'[^\s<>|]*[\\/][^\s<>|]*')`, `DIGITS_RE = re.compile(r'\d+')`, `SECRET_RE` (copy of read_hint.py line 29). Functions: `_shape(text) -> str`; `_edit_shape(tool, ti) -> str | None`; `_rel_key(path, root, cwd) -> str`; `_scrub(text) -> str` (copy of read_hint.py lines 122-123); `_fresh_state() -> dict`; `_load_state(path) -> tuple[dict, bool]`; `_save_state(path, state) -> None`; `_trim(stamps_by_key, now) -> dict`; `_update_counters(state, tool, ti, root, cwd, now) -> list[tuple[str, str, int, str]]` (kind, key, count, label); `_silenced(ev, sid) -> bool`; `_keywords(kind, label) -> str`; `_advice(kind, count, label, keywords) -> str`; `main() -> None`. Event kinds written: `tool_query{source:'agent', command}`, `tool_miss{kind, target, count}`. Trigger kinds: `same_shape`, `same_file`, `same_command`. State JSON: `{"v": 1, "edits": int, "shapes": {key: [ts...]}, "files": {key: [ts...]}, "shell": {"key": str, "run": int}, "advised": [key...]}`. Hook payload keys read (Claude Code `PostToolUse` schema): `session_id`, `cwd`, `tool_name`, `tool_input`; `tool_input` keys `file_path`, `old_string`, `new_string`, `edits`, `command`.
- Behaviour:
  1. `_shape(text)`: `str(text)[:4000]`; `QUOTED_RE` → `<Q>`; `PATHLIKE_RE` → `<P>`; `DIGITS_RE` → `<N>`; `re.sub(r'\s+', ' ', ...)`; `.strip()`. Order exactly as FR-054.
  2. `_edit_shape(tool, ti)`: only for `SHAPE_TOOLS`. `Edit`: needs `old_string` and `new_string` as str, else None. `MultiEdit`: `ti['edits']` list of dicts with str `old_string`/`new_string`, else None. Value = `hashlib.sha1((ext + '\x1f' + '\x1e'.join(_shape(o) + '\x1f' + _shape(n) for o, n in pairs)).encode('utf-8')).hexdigest()[:16]` where `ext = os.path.splitext(ti['file_path'])[1].lower()`.
  3. `_rel_key(path, root, cwd)`: absolute path (joined to `cwd` when relative); when under `root` → `os.path.relpath(...).replace('\\', '/')`, else `os.path.normcase(abs).replace('\\', '/')`.
  4. `_load_state(path)`: missing file → `(_fresh_state(), True)`; read+`json.loads` returning a dict with int `edits`, dict `shapes`, dict `files`, dict `shell`, list `advised` → `(state, True)`; any other content or `(OSError, UnicodeDecodeError, ValueError)` → `(_fresh_state(), False)`. `_save_state`: `path.parent.mkdir(parents=True, exist_ok=True)`, write `path.with_suffix('.tmp')`, then `os.replace`; swallow `OSError`.
  5. `_trim(stamps_by_key, now)`: drop timestamps older than `now - WINDOW_S`, drop empty keys, then keep only the `MAX_KEYS` keys with the newest last timestamp.
  6. `_update_counters`: `EDIT_TOOLS` → `edits += 1`. `SHAPE_TOOLS` with a shape → append `now` to `shapes['same_shape:' + shape]`; with a str `file_path` → append `now` to `files['same_file:' + _rel_key(...).lower()]`. `SHELL_TOOLS`: str `command`, non-empty after strip, not `READ_ONLY_GIT_RE` → key `'same_command:' + sha1(_shape(command))[:16]`; same key as `shell['key']` → `run += 1`, else `{'key': key, 'run': 1}`; an excluded command leaves `shell` unchanged. Then `_trim` both dicts. Return, in this order, every trigger with count ≥ `N_REPEAT` among: the current call's shape key (`same_shape`, label = the rel path), its file key (`same_file`, label = the rel path), the shell key (`same_command`, label = `_shape(command)[:120]`).
  7. `_silenced(ev, sid)`: True when `ev.events(None, session=sid, kind='tool_query')` has an event with `detail.source != 'hook'` and `now - ts <= SILENCE_S`; any exception → False.
  8. `_keywords(kind, label)`: edits → extension without dot plus the parent directory base name, lowercased, joined by one space (`specs/F39-eDoc-X/tasks.md` → `md f39-edoc-x`); `same_command` → the first token's base name without extension plus the first later token that does not start with `-` and is not `<P>`/`<Q>`/`<N>`, taken from the ORIGINAL command's same token, base name without extension (`python tools/gen_f39_tests.py --apply specs/F39` → `python gen_f39_tests`).
  9. `_advice(kind, count, label, keywords)` returns exactly: `same_shape` → `f"AIDD tool-first (T1): {count} edits with the same shape in the last 15 min."`; `same_file` → `f"AIDD tool-first (T1): {count} edits to {label} in the last 15 min."`; `same_command` → `f"AIDD tool-first (T1): {count} shell commands in a row with the same shape."`; each followed by `f" Run `aidd tools {keywords}`; if no tool fits, write a script with dry-run, apply and check and save it under tools/ so `aidd tools` indexes it. Advisory only, nothing was blocked."`.
  10. `main()`: `sys.stdout.reconfigure(encoding='utf-8')` when available; `event = read_event()`; not a dict, `tool_input` not a dict or `tool_name` not in `EDIT_TOOLS | SHELL_TOOLS` → return. `sid = session_of(event)`; `cwd` from the event else `os.getcwd()`; import `aidd_evidence as ev` from `<skill>/scripts`; `root = ev.known_root(cwd)`; None → return. Shell command matching `TOOLS_QUERY_RE` → `ev.append(None, sid, 'tool_query', source='agent', command=_scrub(command))`, return. `path = ev.tool_first_state_path(sid)`; `state, ok = _load_state(path)`; `fired = _update_counters(...)`; `_save_state(path, state)`; `not ok` → return. Keep triggers whose key is not in `state['advised']`; none → return. `_silenced(ev, sid)` → return (keys are NOT marked advised). Add every kept key to `advised`, `_save_state`; first trigger → `ev.append(None, sid, 'tool_miss', kind=kind, target=_scrub(label), count=count)`; write `json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": _advice(...)}}, ensure_ascii=False) + '\n'`.
  11. Module bottom: `if __name__ == '__main__':` `try: main()` `except BaseException:` try `ev.record_hook_error(None, sid-or-None, 'tool_first_hint', repr(exc))` inside its own `try/except Exception: pass`; then `sys.exit(0)`. Module docstring names FR-049..FR-054 and says "Only advises: never denies, never blocks, never raises, always exits 0."
- Tests first: T-60 must be red before this task; keep it unmodified.
- Verify: `python -m unittest tests.test_read_hint -v` → exit 0; `python -m unittest tests.test_tool_first_hint -v` → every test passes except the status-line test, which waits for T-63.
- Do NOT: print anything to stderr; deny or block a tool call; write state inside the project tree; read the edited file from disk; count `Grep`, `Glob` or `Read`; import anything outside the stdlib, `_common` and `aidd_evidence`; edit `read_hint.py`.
- Done when: every hook test of T-60 passes and the read_hint tests still pass.
- Open questions: none.

### T-62 — register the hook in `install_hooks.py`
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: XS

**Estimate**
- Effort: Low
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 40k
- Agent role: builder
- Model tier: medium
- Wave: 13

**Detail**
- Goal: install `tool_first_hint.py` as a `PostToolUse` hook on every Claude Code machine through the existing installer.
- Cites: FR-049.
- Depends on: T-60.
- Read first: `skill/scripts/install_hooks.py` lines 1-95; `tests/test_install_hooks.py` lines 76-155.
- Files to change: `tests/test_install_hooks.py`; `skill/scripts/install_hooks.py`.
- Naming contract: new `HOOK_DEFS` entry `('PostToolUse', 'Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell', SKILL_DIR / 'hooks' / 'tool_first_hint.py')` appended as the last element; timeout from `DEFAULT_TIMEOUT` (10); test method `test_registers_thirteen_hooks_with_session_memory_only_by_default` renamed `test_registers_fourteen_hooks_with_session_memory_only_by_default`.
- Behaviour:
  1. Tests first in `tests/test_install_hooks.py`: line 80 `13` → `14`; line 87 `13` → `14`; line 138 `14` → `15`; add `"tool_first_hint.py"` to the list on lines 142-146; add `self.assertEqual(by["tool_first_hint.py"], ("PostToolUse", "Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell"))` after line 153; run red.
  2. Append the entry to `HOOK_DEFS`.
  3. Docstring: line 9 `12 hooks` → `14 hooks`; after the `graph_refresh.py` lines (35-37) add `  - PostToolUse    -> hooks/tool_first_hint.py (matcher: Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell) spec 004 FR-049: advises a script after 4 repeated edits or shell commands; never blocks`.
- Tests first: step 1; `python -m unittest tests.test_install_hooks -v` red before step 2.
- Verify: `python -m unittest tests.test_install_hooks tests.test_prompt_trigger -v` → exit 0.
- Do NOT: run the installer against the real `~/.claude/settings.json`; change any other entry, matcher or timeout; touch `adapters/`.
- Done when: the verify command passes.
- Open questions: none.

### T-63 — the `aidd status` line
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: XS

**Estimate**
- Effort: Low
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 40k
- Agent role: builder
- Model tier: medium
- Wave: 13

**Detail**
- Goal: `aidd status` prints `tool-first: N advisories / M edits this session` right after the graph-first line.
- Cites: FR-052, AC-045.
- Depends on: T-60, T-65.
- Read first: `skill/scripts/aidd_status.py` lines 173-190 and 710-745.
- Files to change: `skill/scripts/aidd_status.py`.
- Naming contract: new `def _tool_first_line(root=None) -> str` placed directly after `_graph_first_line`; called in `format_global` as `_tool_first_line(),  # aidd:FR-052` on the line after `_graph_first_line(),  # aidd:FR-027`.
- Behaviour:
  1. Copy the structure of `_graph_first_line`: `n = m = 0`; `root = root or ev.find_root()`; `sess = _current_session(root)`.
  2. When `sess`: `n = len(ev.events(root, kind='tool_miss', session=sess))`; `edits = ev.read_tool_first_state(sess).get('edits')`; `m = edits if isinstance(edits, int) and edits >= 0 else 0`.
  3. Any exception → `n = m = 0`. Return `f'tool-first: {n} advisories / {m} edits this session'`. Never raises.
- Tests first: T-60's `test_ac045_status_line` is red before this task.
- Verify: `python -m unittest tests.test_tool_first_hint tests.test_aidd_status tests.test_read_hint -v` → exit 0.
- Do NOT: change `_graph_first_line`, `format_status` or the verification and approval lines; touch `adapters/` (T-66 does the mirror).
- Done when: the verify command passes.
- Open questions: none.

### T-64 — document the nudge in `skill/SKILL.md`
**Classify**
- Nature: `REQUIREMENT`
- Priority: 4
- Kind: LOGIC
- Size: XS

**Estimate**
- Effort: Low
- Agent min: 5
- Human ref hours: 0.25
- Tokens (est): 25k
- Agent role: docs
- Model tier: medium
- Wave: 14

**Detail**
- Goal: document the tool-first nudge next to rule T1.
- Cites: FR-050, FR-052.
- Depends on: T-61, T-63.
- Read first: `skill/SKILL.md` line 461 (the `**T1 Tool-first**` paragraph) and line 312 (the graph-first nudge paragraph, as the wording model).
- Files to change: `skill/SKILL.md`.
- Naming contract: documents exactly these names and no others: hook `tool_first_hint.py`, threshold 4, window 15 minutes, triggers `same_shape`, `same_file`, `same_command`, silencer `aidd tools` for 300 s, events `tool_miss` and `tool_query`, status line `tool-first: N advisories / M edits this session`.
- Behaviour: append one sentence block to the end of the T1 paragraph on line 461: "On Claude Code the `tool_first_hint.py` hook advises (never blocks) after 4 edits of the same shape or to the same file within 15 minutes, or 4 shell commands in a row of the same shape (`same_shape`, `same_file`, `same_command`; digits, quoted literals and paths are ignored when comparing). Only an `aidd tools` query run by the agent silences it for 300 s. Each advisory is a `tool_miss` event and `aidd status` prints `tool-first: N advisories / M edits this session`."
- Tests first: no code; the check below exits 1 before this task and 0 after.
- Verify: `python -c "import sys; t=open('skill/SKILL.md', encoding='utf-8').read(); sys.exit(0 if 'tool_first_hint.py' in t and 'tool-first: N advisories' in t else 1)"` → exit 0.
- Do NOT: change any other section; mention b1SycLink; edit `adapters/dot-aidd/AIDD.md` or `CORE.md`.
- Done when: the verify command passes.
- Open questions: none.

### T-66 — mirror the two changed scripts
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: XS

**Estimate**
- Effort: Low
- Agent min: 5
- Human ref hours: 0.25
- Tokens (est): 25k
- Agent role: builder
- Model tier: medium
- Wave: 14

**Detail**
- Goal: keep the project bundle identical to the skill source for the two scripts this amendment changes.
- Cites: FR-052, FR-053 (mirror).
- Depends on: T-63, T-65.
- Read first: `tests/test_dot_aidd_mirror.py` lines 55-80.
- Files to change: `adapters/dot-aidd/scripts/aidd_evidence.py`; `adapters/dot-aidd/scripts/aidd_status.py`.
- Naming contract: none new; both targets are byte copies of `skill/scripts/aidd_evidence.py` and `skill/scripts/aidd_status.py`, so every name is the one fixed in T-63 and T-65.
- Behaviour: `cp skill/scripts/aidd_evidence.py adapters/dot-aidd/scripts/aidd_evidence.py` and `cp skill/scripts/aidd_status.py adapters/dot-aidd/scripts/aidd_status.py`; no hand edits. The hook file has no mirror (`read_hint.py` has none either).
- Tests first: `tests/test_dot_aidd_mirror.py` already asserts equality; run it before (red after T-63/T-65) and after (exit 0).
- Verify: `python -m unittest tests.test_dot_aidd_mirror -v` → exit 0.
- Do NOT: edit either file by hand; touch any other mirror; copy `tool_first_hint.py` into `adapters/`.
- Done when: the mirror test passes.
- Open questions: none.

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
- Wave: 11

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
- Wave: 12

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
- Wave: 13

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
- Done when: V-15 and V-20 pass.
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
- Wave: 12

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
- Wave: 12

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
- Wave: 12

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
- Wave: 12

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
- Wave: 14

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
- Wave: 15

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
- Wave: 16

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
- Wave: 17

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
- Wave: 18

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
- Wave: 19

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
- Done when: both Verify results match and V-21 prints the path.
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
- Model tier: medium
- Wave: 20

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
- Model tier: medium
- Wave: 20

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

### T-85 — (T-VISUAL) measured comparison with the two mockups
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 30
- Human ref hours: 1.0
- Tokens (est): 120k
- Agent role: tests
- Model tier: high
- Wave: 20

**Detail**
- Goal: compare the generated page with the F47 Stitch prototype and the approved alias mockup by measured values only, and report every difference.
- Cites: FR-077, AC-066.
- Depends on: T-84.
- Read first: `batch-staging/f47-port-sources/f47-spec/prototype/stitch-SCREEN-95.html` (its `tailwind-config` script and fonts); `batch-staging/f47-port-sources/f47-spec/mockup-audit.md`; `specs/007-aidd-review-html-close-gate/prototypes/alias-graph-explorer/alias-graph-explorer.html` lines 1-60 and 380-560; `specs/007-aidd-review-html-close-gate/prototypes/alias-graph-explorer/alias-graph-explorer.sha256`.
- Files to change: `tests/visual_compare_explorer.py` (new script, not a test module) and `tests/test_visual_compare_explorer.py` (new unit-test module: class `VisualCompareExplorer(unittest.TestCase)` with the single method `test_required_checks_match`, which imports `visual_compare_explorer` with `tests` on `sys.path`, calls `compare()`, skips with the visible reason `no Chromium available` when the report holds the single `not-comparable` check of step 7, and otherwise asserts `report["summary"]["required_differ"] == 0`; the module exists so the Verification row can run through the unittest runner).
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
- Verify: `python -m unittest discover -s tests -p "test_visual_compare_explorer.py" -v` → exit 0 (the test skips visibly without a browser and never fails for that reason); the script stays runnable by hand with `python tests/visual_compare_explorer.py` → exit 0 and the printed JSON reports zero required differences.
- Do NOT: judge by screenshot or by eye; edit any production file or mockup; call Stitch; write into `specs/` (the coordinator archives the printed report as evidence).
- Done when: the report runs, all required checks match, and every non-required difference is listed for the owner.
- Size: ~140 changed lines.
- Open questions: none.

## Waves

Los tiempos son de **agente**. Las tareas de una ola van en paralelo (archivos distintos) y una ola dura el máximo de sus tareas. Las olas 1-4 son el trabajo ya construido de T-01..T-10; las olas 5-8 son la primera enmienda y las olas 9-10 (T-47..T-59, FR-044..FR-048) la segunda. Las pruebas comparten ola con el código que prueban cuando la interfaz ya está fijada en el plan (regla 2 de Step 4); los builders solo hacen autochequeo estático y el verificador (T-25 en la ola 8, T-59 en la ola 10) ejecuta todo.

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-01, T-02, T-03, T-09, T-10 | builder, tests, docs | 25 | 222 | 1.25 |
| 2 | T-04, T-05 | builder | 25 | 107 | 1.25 |
| 3 | T-06 | builder | 20 | 62 | 1 |
| 4 | T-07, T-08 | tests, builder | 20 | 75 | 1 |
| 5 | T-11, T-12, T-21, T-22, T-23, T-24, T-31 | builder, tests, docs, sql | 60 | 475 | 3 |
| 6 | T-13, T-14, T-15, T-27, T-28, T-30 | builder | 40 | 420 | 2 |
| 7 | T-16, T-17, T-18, T-19, T-26, T-29, T-32, T-33, T-34, T-35, T-36, T-37, T-38, T-39, T-40, T-41, T-42, T-43, T-44, T-45, T-46 | builder, tests, docs | 40 | 1375 | 2 |
| 8 | T-25 | tests | 40 | 90 | 2 |
| 9 | T-47, T-48, T-49, T-50, T-51, T-52, T-53, T-54, T-55, T-56, T-57, T-58 | builder, tests, docs | 40 | 650 | 2 |
| 10 | T-59 | tests | 40 | 90 | 2 |
| 11 | T-60, T-70 | tests | 25 | 170 | 2 |
| 12 | T-65, T-71, T-73, T-74, T-80, T-81 | builder, tests | 25 | 470 | 5 |
| 13 | T-61, T-62, T-63, T-72 | builder | 40 | 320 | 4 |
| 14 | T-64, T-66, T-75 | docs, builder | 25 | 170 | 1.5 |
| 15 | T-76 | builder | 25 | 120 | 1 |
| 16 | T-82 | builder | 25 | 100 | 1 |
| 17 | T-83 | builder | 25 | 110 | 1 |
| 18 | T-84 | builder | 15 | 60 | 0.5 |
| 19 | T-77 | builder | 15 | 60 | 0.5 |
| 20 | T-78, T-79, T-85 | builder, docs, tests | 30 | 160 | 1.5 |

Total agent time (critical path): 600 min
Total tokens (k): 5306

Waves 1-10 total 350 min and 3566k tokens; waves 11-20 (amendments 2026-11-03) total 250 min and 1740k tokens, computed by `waves.py` in the scratchpad from the `- Wave:` lines of T-60..T-85. The tool-first tasks (T-60..T-66, draft waves 1-4) and the unified-explorer tasks (T-70..T-85, draft waves 1-10) were shifted by +10 and share waves 11-14 (no two tasks of a wave touch the same file). Waves 14-19 give `skill/scripts/graph_explorer.py` one owner (T-74) in sequence. T-85 is the draft's T-VISUAL gate (numeric id so the wave checker counts it).

## Approval gate

**Presenta esta tabla como dry-run y espera aprobación explícita antes de que el Step 5 empiece en cualquier fila.** Nunca se implementa una tarea no aprobada.

La aprobación es del usuario y es verificable: se le pregunta (AskUserQuestion) si aprueba las tareas y luego `aidd rules approve <spec_dir>` reemplaza la línea de abajo por `Approved: <YYYY-MM-DD> hash:<12 hex>`. Cualquier edición posterior de este archivo la invalida. No escribir esa línea a mano.

Approved: 2026-11-04 hash:134f6679ba73

## Definition of Done (applies to every task above)
1. El código implementa exactamente los códigos citados, en el archivo de destino, siguiendo el Naming & File Contract del plan.
2. Fila de mapeo en `qa-audit.md` por cada código tocado, con evidencia de archivo/función.
3. `PR/Spec ref` escrito en `plan.md` para cada código tocado, agregando, no sobrescribiendo.
4. Evidencia ejecutada (salida de comando o de tests guardada bajo `specs/004-aidd-graph-first/evidence/`), no solo lectura del código. NO por tarea: la corre el verificador (T-25) una vez por ola, tras terminar todos los builders, y escribe las filas R10 de los códigos de la ola; un builder solo hace autochequeo estático y no repite verificaciones sobre el mismo estado del código (regla E9).
