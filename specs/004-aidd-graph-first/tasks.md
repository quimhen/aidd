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

Total agent time (critical path): 350 min
Total tokens (k): 3566

## Approval gate

**Presenta esta tabla como dry-run y espera aprobación explícita antes de que el Step 5 empiece en cualquier fila.** Nunca se implementa una tarea no aprobada.

La aprobación es del usuario y es verificable: se le pregunta (AskUserQuestion) si aprueba las tareas y luego `aidd rules approve <spec_dir>` reemplaza la línea de abajo por `Approved: <YYYY-MM-DD> hash:<12 hex>`. Cualquier edición posterior de este archivo la invalida. No escribir esa línea a mano.

Approved: 2026-10-24 hash:ffdb647a14ce

## Definition of Done (applies to every task above)
1. El código implementa exactamente los códigos citados, en el archivo de destino, siguiendo el Naming & File Contract del plan.
2. Fila de mapeo en `qa-audit.md` por cada código tocado, con evidencia de archivo/función.
3. `PR/Spec ref` escrito en `plan.md` para cada código tocado, agregando, no sobrescribiendo.
4. Evidencia ejecutada (salida de comando o de tests guardada bajo `specs/004-aidd-graph-first/evidence/`), no solo lectura del código. NO por tarea: la corre el verificador (T-25) una vez por ola, tras terminar todos los builders, y escribe las filas R10 de los códigos de la ola; un builder solo hace autochequeo estático y no repite verificaciones sobre el mismo estado del código (regla E9).
