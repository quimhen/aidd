# Plan — 004 AIDD Graph-First

Borrador del Mapper independiente (Step 3). Tarea sin pantallas ni componentes: Screen/Component/Entry/Device/Design system = N/A (sin mockup, sin UI).

## Naming & File Contract

| Item | Convention |
|---|---|
| Language/deps | Python 3, stdlib only, sin LLM. Funciones snake_case (como `find_spec.py`), constantes UPPER_SNAKE |
| Files | Los parsers viven en `skill/scripts/find_spec.py` (estilo actual: todo en un archivo). Hook nuevo = archivo nuevo |
| Classes per file | Ninguna clase nueva (solo funciones) |
| Index format | `INDEX_VERSION` 3 → 4 (`find_spec.py:110`). `load_index` ya devuelve None si la versión no coincide (`:505`): un índice viejo se reconstruye. FR-010 solo necesita test |

Nombres nuevos, todos en `skill/scripts/find_spec.py` salvo indicación:

| Name | Purpose |
|---|---|
| `NODE_KINDS`, `EDGE_KINDS`, `GRAPH_CODE_RE` | vocabulario del grafo; `GRAPH_CODE_RE` separado de `CODE_RE` para no alterar el ranking de búsqueda |
| `parse_spec_nodes(spec_md_text)` | `(nodes, edges)`: filas `AC-nnn` de `## Acceptance cases` y `FR-nnn` de `## Functional requirements` |
| `parse_task_nodes(tasks_md_text)` | filas `T-nn`: códigos satisfechos, archivo destino, estado; aristas `T→código` |
| `parse_contract_nodes(contracts_md_text)` | nodos `API-nnn` con ruta o SP, sin necesitar mockup |
| `memory_nodes_for(codes, root)` | nodos MEM desde `memory_hits_for` (`:273`); nunca lanza, degrada a [] |
| `locate_in_file(spec_dir, fname, code)` | primera línea donde aparece el código (file:line) |
| `build_graph(spec_dir)` | une aristas del mockup (`parse_relationship_edges`, `:365`) con las nuevas |
| `neighbours(entry, code)` | consulta de adyacencia |
| `print_code(index, code)` | salida de `--code`, máximo 25 líneas |
| `skill/hooks/read_hint.py` (nuevo) | aviso PreToolUse Read, sin bloquear (FR-008) |
| `tests/test_read_hint.py` (nuevo) | tests del hook; los de parsers van en `tests/test_find_spec.py` |

Cambian: `build_spec_entry` (`:453`) añade nodes/edges; `dumps_index`/`loads_index` (`:159`/`:177`) añaden la columna `graph`; `print_tree` (`:673`) se reescribe; `main` (`:695`) añade `--code <CODE>`.
Espejo: `adapters/dot-aidd/scripts/find_spec.py` debe quedar idéntico byte a byte (`tests/test_dot_aidd_mirror.py`); copiar tras cada edición. `read_hint.py` no se espeja (verificar que dot-aidd no tiene carpeta hooks).

## FR / AC → code

| Req | Code | Test |
|---|---|---|
| FR-001 | `parse_spec_nodes` desde `build_spec_entry` | AC-001: spec.md de fixture con 2 AC y 2 FR |
| FR-002 | `parse_task_nodes`; aristas `satisfies`, `targets` | AC-002: T-16 da FR-005/009/010 y el archivo destino |
| FR-003 | `parse_contract_nodes` | AC-003: carpeta con solo contracts.md |
| FR-004 | `memory_nodes_for`, kind MEM, arista `mentions` | AC-004: `.aidd/memory` temporal con una entrada |
| FR-005 | `main --code`, `print_code`, `neighbours`, `locate_in_file` | AC-001: API-003 muestra nodo, T-13 y FR, ≤25 líneas |
| FR-006 | `print_tree` sobre aristas unificadas | AC-003: árbol no vacío sin mockup |
| FR-007 | `stale_spec_names` (`:518`, mtime por spec) sin cambios | AC-005: tocar tasks.md reconstruye solo esa spec |
| FR-008 | `skill/hooks/read_hint.py` + fila en `install_hooks.py` | AC-006 |
| FR-009 | `skill/SKILL.md`, `skill/AIDD.md`, comando `aidd-converge` (prosa) | test de texto en `tests/test_find_spec.py` |
| FR-010 | `INDEX_VERSION = 4` + guarda de `load_index` | AC-005: archivo `version: 3` se reconstruye sin excepción |

Decisión sobre FR-007: la granularidad de caché es por spec (hoy), no por archivo; parsear una spec de 66 KB cuesta milisegundos. Se mantiene por spec y AC-005 se lee como "solo se reconstruye la spec tocada".

## Index schema (version 4)

Se añade una columna `graph` tras `tree`: `TABLE_FIELDS = ['id','title','codes','words','tree','graph','files']`. La celda une registros con `;`, codificada como `_encode_tree` (`:149`): nodo `N:<ID>:<kind>:<file>:<line>:<label>`, arista `E:<from>:<to>:<kind>`. Etiquetas truncadas a 60 caracteres y sin `| ; :`.

| Kind | Source | Label |
|---|---|---|
| US, SCREEN, COMP, CTL | mockup-audit (existente) | existente |
| AC | spec.md `## Acceptance cases` | dato real recortado |
| FR | spec.md `## Functional requirements` | requisito recortado |
| T | tasks.md filas `T-\d+` | archivo destino |
| API | contracts.md | ruta o SP |
| MEM | `.aidd/memory` | `m-id tipo título` |

Aristas: `contains` (cadena mockup), `cites` (FR→AC), `satisfies` (T→FR/AC/API/SCREEN/COMP/CTL), `targets` (T→archivo), `mentions` (MEM→código). `--tree` une la cadena del mockup con FR→AC, T→FR y API←T; una spec backend da cadenas tipo `FR-001 → AC-001 → T-02`.

`--code <CODE>` (acotado): línea 1 `CODE kind  label  (spec/file:line)`; luego ≤8 vecinos por grupo, una línea cada uno; MEM máximo 3; tope duro `lines[:24]` más `  ... +N more (use --tree <spec>)`. Si el código está en varias specs, el presupuesto se reparte (`25 // nspecs`, mínimo 6). No encontrado: `No node 'X'` con ids cercanos y exit 2.

## Hook design (FR-008, AC-006)

Los eventos `find_spec` ya existen (`mark_graph_rebuild.py:62-69`, SESSION_KIND en `aidd_evidence.py:122`), así que no hace falta un tipo nuevo de evento. `skill/hooks/read_hint.py` (PreToolUse, matcher `Read`):
1. Lee el evento con `_common.read_event`; cualquier entrada rara termina en exit 0 con `main` envuelto en try/except (como `memory_file_context.py:87-92`).
2. El nombre base debe ser spec.md, plan.md, contracts.md, tasks.md o events.toon, bajo `specs/` (events.toon bajo `.aidd/evidence/`).
3. Si `limit` u `offset` vienen informados: silencio.
4. Si la sesión ya tiene un evento `find_spec`: silencio.
5. Una vez por (sesión, archivo), con el marcador de `memory_file_context._first_time`.
6. Salida `additionalContext` con una línea que apunta a `find_spec.py --code` o a Read con limit. Nunca `permissionDecision: deny` (decisión confirmada por el usuario: solo avisar).
7. Registro: fila por defecto `('PreToolUse', 'Read', hooks/read_hint.py)` en `install_hooks.py`, timeout corto en `timeout_for`, y actualizar el conteo de hooks en `tests/test_install_hooks.py`.

## Risks

1. Los formatos de tabla de specs reales varían: los parsers se guían por encabezado (`table_rows`, `cell_codes`), toleran columnas ausentes y nunca lanzan.
2. `contracts.md` no tiene plantilla fija: confirmar la columna de ruta/SP con `skill/templates/contracts.md`. La spec real de Integraciones queda fuera del repo, así que los tests usan fixtures sintéticos y esa spec es solo verificación manual.
3. Si `CODE_RE` incluyera `T-`/`FR-`, inundaría la lista `codes`: por eso `GRAPH_CODE_RE` es aparte.
4. Dos PRs paralelos sobre `find_spec.py` chocan: se secuencian.
5. `aidd_memory` puede faltar en la instalación espejo: `memory_nodes_for` devuelve [].
6. Dos hooks Read (este y el opcional de memoria) emiten contexto: probar que ambos conviven.

## Preguntas abiertas

Ninguna bloqueante. Decidido: `--code` acepta un solo código; el hook solo avisa.

---

# Enmienda 2026-10-24 — grafo de código propio (FR-014..FR-024, AC-009..AC-018)

Borrador del Mapper independiente, con anclas verificadas. `aidd/cli.py` reenvía `graphs` como REMAINDER (L404-408, L583): NO hay cambio en `aidd/cli.py` (ninguna tarea lo toca; los subcomandos nuevos viven en `aidd_graphs.py`). Ojo: `_find_scripts_dir` (cli.py:17-28) busca primero `$AIDD_HOME` y la skill instalada, y el repo solo al final; por eso T-25 sincroniza la skill instalada antes de verificar.

## Naming & File Contract (adiciones)

Todos stdlib-only. Los scripts nuevos importan `aidd_evidence` solo dentro de try/except (los scripts generados de `adapters/dot-aidd/.aidd/scripts` se prueban sin errores de import: `tests/test_dot_aidd_mirror.py` L369).

| Archivo (dueño único) | Contenido |
|---|---|
| `skill/scripts/code_graph.py` (nuevo) | `DEFAULT_GLOBS`, `GRAPH_REL=".aidd/graphs/code.json"`, `SCHEMA_VERSION=1`, `READ_FUNCS`, `SPAWN_FUNCS`, `MARKER_RE`. `build(root, globs=None, previous=None) -> (graph, stats)` (stats = parsed/reused/warnings), `file_shas(root, rels)` (autocontenido: un `git hash-object --stdin-paths` con respaldo en Python `sha1(b"blob %d\0"+datos)`; NO importa `aidd_evidence.blob_shas`, así T-11 y T-12 son independientes), `list_files(root, globs)`, `parse_file(rel, text) -> (nodes, edges, warnings)` (visitor `ast`), `resolve_calls(nodes, edges)` (por alcance: mismo módulo, imports explícitos, luego nombre global; >1 candidato = una arista por candidato con `ambiguous:true`; 0 = nodo SINK `unresolved`; nunca se descarta), `link_markers(graph)` (aristas `implements` a ids planos `FR-205`), `main(argv)` (`--root --out --quiet --full`) |
| `skill/scripts/method_graph.py` (nuevo) | `GRAPH_REL=".aidd/graphs/method.json"`, `SOURCES`, `build(root)`, `parse_rules`, `parse_steps`, `link_enforcers(graph, code_graph)` (token exacto `Rn` o `aidd:Rn`, `via: mention`), `main(argv)` |
| `skill/scripts/graph_trace.py` (nuevo) | `RUNTIME_KEY="runtime"`, `class Tracer` (`sys.setprofile` + `threading.setprofile`, solo sinks cerrados: `open`, `io.open`, `Path.read_text/read_bytes`, `json.load`, `subprocess.Popen.__init__`, `os.system`; atribuye a la FUNC del bundle AIDD que llama), `run_traced(root, argv, graph_path) -> int` (mapea el subcomando a su script con el mismo escaneo `ast` de `entrypoints()` y lo ejecuta EN PROCESO con `runpy.run_path` y `sys.argv` parcheado, con el refresco de grafos desactivado; `aidd.cli.main` no sirve porque su `_run` lanza un proceso hijo que el profiler no ve; captura `SystemExit`), `merge_runtime(graph, counts)`, `main(argv)` |
| `skill/scripts/graph_snapshot.py` (nuevo) | `SNAP_DIR_REL=".aidd/graphs/snapshots"`, `DIFF_CAP=25`, `LABEL_RE`, `canonical(graph) -> bytes`, `snapshot(root, name, label, rev=None, replace=False)`, `diff(root, a, b, full=False) -> (rc, text)`, `changed(root, spec=None, name="code") -> dict` (incluye `affected`), `repeats(root, cmd=None, label=None) -> [str]`, `_build_at_rev(root, name, rev)` (`git archive` a un tmp), `entrypoints()` (escaneo `ast` de las llamadas `_run("x.py", [sub, ...])` de `aidd/cli.py`: subcomando a script y, dentro del script, `cmd_<sub>` si existe, si no `main`; más el `main` de cada hook; `aidd/cli.py` no tiene tabla). Los snapshots viven en `.aidd/graphs/snapshots/<name>/<L>.json` |
| `skill/scripts/aidd_graphs.py` (existe, dueño único) | `_autodetect` (L77): entradas `code` (`builtin:code`), `method` (`builtin:method`), `spec` (`builtin:spec`); toda fila `code` (charter o autodetectada, p. ej. graphify) cuyo Refresh no sea `builtin:code` se renombra `code-<herramienta>` al cargar, con aviso (hoy el charter gana sobre lo autodetectado, L12/L104). `_command` (L240): ramas `builtin:code|method|spec|sql-schema|sql-dml` (la rama `builtin:sql` no cambia). `auto` (L418-430) deja de saltar el kind `spec` cuando su refresh es `builtin:spec`. `show` (L354): kinds code/method (callers, callees, sinks, implements, tope 25; atributos `sha`/`runtime`). `status` (L301): estado por sha, no por mtime. `refresh`: `--force` (salta el debounce de 60 s) y `re-parsed N`. `main` (L465): `repeats|trace|snapshot|diff|changed` delegan en `graph_snapshot`/`graph_trace` |
| `skill/scripts/aidd_evidence.py` (existe, dueño único) | `'graph_snapshot'` en `PROJECT_KINDS` (L148), `append_graph_snapshot(root, session, name, label, sha256, nodes, edges, rev='')` junto a `append_spec_closed`, `blob_shas(root, rels)` extraído de `_code_state_git` (una sola implementación; `_code_state_git` la llama; sin cambio de comportamiento); `SESSION_KINDS` += `graph_miss`; `runs_find_spec(command)` reconoce además `aidd graphs show|repeats|changed|status` y `aidd search|tree`; `_rotate_if_needed` (L412) no recorta las filas `graph_snapshot` |
| `skill/scripts/aidd_status.py` (existe, dueño único) | `cmd_activate` (L1318): toma la línea base `<spec>@open` si falta (llama al CLI de grafos en segundo plano; si falla, solo avisa) |
| `tests/test_dot_aidd_mirror.py` (existe, dueño único) | `VERBATIM_SCRIPTS` (L61) += los 4 scripts nuevos; prueba nueva: cada script nuevo responde `--help` con rc 0 (solo stdlib) y SKILL.md, AIDD.md y aidd-converge.md nombran los comandos nuevos (FR-022) |
| `skill/scripts/sql_graph.py` (existe, dueño único) | FR-028: protección en `analyze_sql` (L611) contra alias o nombres que no son tablas, contados en `meta.skipped_statements`. FR-029: `--kind schema` con checkpoint JSON por prefijo de migraciones (hash de los shas ordenados), reproduce solo la cola y rehace todo si cambia o desaparece una vieja. FR-030: `--kind dml` con caché por `sha(cuerpo)` + hash del esquema de las tablas tocadas. Espejo en `adapters/dot-aidd/scripts/sql_graph.py` |
| `skill/hooks/read_hint.py` (existe, dueño único; los hooks solo se espejan si están en `VERBATIM_HOOKS`) | FR-025/026/027: cubre `Read`, `Grep`, `Glob` y `Bash`/`PowerShell` de búsqueda o lectura, sobre código y specs; solo las consultas del agente (`source='bash'`) callan 300 s; registra `graph_miss`; el mensaje nombra el grafo a construir |
| `skill/hooks/mark_graph_rebuild.py` (existe, dueño único) | registra como consulta del agente (`append_find_spec(source='bash')`) lo que `aidd_evidence.runs_find_spec` reconoce |
| `skill/scripts/install_hooks.py` (existe, dueño único) | matcher de `read_hint` = `Read|Grep|Glob|Bash|PowerShell` |
| `tests/test_read_hint.py` (existe; mismo dueño que T-03) | casos AC-019 y AC-020 |
| `tests/test_sql_graph_incremental.py` (nuevo) | FR-028..030 con migraciones sintéticas y un fixture del alias `oitw` |
| `skill/hooks/prompt_trigger.py` (existe, dueño único; confirmar con `VERBATIM_HOOKS` si lleva espejo) | FR-032: no ejecuta `find_spec` ni inyecta el bloque Step -1 para mensajes de sistema o de agentes (prompt que empieza por `<` o `[`, notificaciones de tareas) ni cuando los mismos términos ya se respondieron en la sesión contra un `specs/index.toon` sin cambios en los últimos 15 min (estado por sesión en el directorio temporal `aidd-hooks`, clave = hash de términos + mtime-independiente: hash del contenido del índice); el evento `find_spec` con `source='hook'` solo se escribe si de verdad corrió |
| `tests/test_prompt_trigger.py` (nuevo) | AC-024: diez mensajes (seis de agentes, tres repetidos) → como máximo 2 ejecuciones de `find_spec` y 2 bloques inyectados; los omitidos no dejan evento |
| `tests/test_perf_budget.py` (nuevo) | AC-026: reconstrucción sin cambios de `code_graph` re-parsea 0 archivos y es ≥ 2x más rápida que la completa; `graph_snapshot.changed` sobre un árbol sin cambios hace exactamente 1 spawn de `git hash-object`; el segundo prompt idéntico hace 0 spawns de `find_spec`. Solo conteos y razones, nunca tiempos absolutos |
| `skill/SKILL.md`, `skill/AIDD.md` (+ copia), `commands/aidd-converge.md` | FR-031/FR-033: regla `E9` (protocolo de economía de verificación, 5 puntos) junto a E1-E8; `check_spec.py` se corre una vez antes de la auditoría de cierre y tras la última edición de spec/plan/tasks (no antes de cada pase manual); mismas filas same-owner que T-09/T-22/T-23/T-10/T-24 |
| `skill/scripts/aidd_job.py` (nuevo, T-39) + espejo | FR-035/036: `run [--bg] [--key globs] [--name n] [--force] -- <cmd...>`, `wait <id>`, `last <name>`, `list`; `inputs_hash` = sha256 de los hashes de contenido (reutiliza `code_graph.file_shas`/`list_files`, nunca mtime) de los archivos que cumplen `--key` (por defecto globs de código + tests); veredicto en `.aidd/jobs/<name>-<inputs8>/verdict.json` y `log.txt`; misma entrada + mismo comando = `CACHED` sin ejecutar; `--bg` lanza un proceso desacoplado; parsea la línea final `RESULT: ok\|fail\|stale\|refused - <N> items - evidence <path>` o la deriva del código de salida; salidas 0/1/2 de la herramienta, 3 de `last` cuando no hay veredicto vigente; solo el CLI escribe `.aidd/jobs/` |
| `skill/scripts/aidd_triage.py` (nuevo, T-40) + espejo | FR-037: port de b1SycLink `tools/verify_triage.py` (79 líneas): lee `specs/<id>/evidence/verify-*.txt`, extrae ítems fallidos (pgTAP `[FAIL] x.test.sql`, vitest ` FAIL  file > test`, pytest `FAILED file::test`, errores `tsc`) y agrupa los que fallan en 2+ specs; solo lectura, `--json` |
| `skill/scripts/aidd_tools.py` (nuevo, T-44) + espejo | FR-039/041: catálogo `aidd tools [keywords] [--json]` con grupos verify/graph/db/docs/generate/gate; fuentes: docstring (primera línea) de `skill/scripts/*.py` y de las carpetas `tools/`, `*/tools/`, `*/scripts/` del proyecto (`.py`, `.ps1`, `.sh`), detección de los flags `--plan`, `--check`, `--dry-run` por texto; salida de hasta 40 líneas; caché del escaneo del proyecto por hash de contenido de esas carpetas (no mtime) |
| `aidd/cli.py` (existe, T-43; ÚNICO cambio de CLI de esta enmienda, corrige la nota anterior de "ninguna tarea lo toca") | FR-038/041: reenvía `job`, `triage` y `tools` a sus scripts como `graphs` (REMAINDER, `_run("<script>.py", [...])`); si algún test de `tests/` lista los subcomandos del CLI, el dueño reporta qué aserción cambia |
| `skill/templates/tasks.md` (existe, T-46) | FR-040: en la lista de estándares que cada prompt de Builder/Auditor repite, una línea tool-first: antes de hacer a mano un paso repetitivo, largo o comprobable, ejecutar `aidd tools <palabras>` y usar la herramienta; el camino manual necesita una razón escrita |
| `tests/test_aidd_job.py`, `tests/test_aidd_triage.py`, `tests/test_aidd_tools.py` (nuevos; reemplazan los stubs en rojo) | AC-027..AC-030 con proyectos temporales; `aidd job` se prueba con una herramienta de juguete y conteo de spawns |
| `skill/hooks/prompt_trigger.py` (T-33, ampliación) | además de FR-032, el hint de una vez por sesión nombra `aidd tools`, `aidd graphs`, `aidd job` y `aidd triage` (FR-040) |
| `skill/scripts/aidd_status.py` (T-26) | además de `cmd_activate`: línea `graph-first: N misses / M searches` (FR-027) |
| `tests/test_code_graph.py`, `tests/test_graph_snapshot.py`, `tests/test_graph_trace_method.py` (nuevos) | proyecto temporal (`tempfile` + `git init`) y directorio de evidencia temporal (`_test_dir`): nunca escriben `graph_snapshot` en el log real |
| `skill/SKILL.md`, `skill/AIDD.md`, `commands/aidd-converge.md` | FR-022 (T-09/T-10 ya tocaron SKILL.md y aidd-converge: filas nuevas con `same owner as T-09` / `T-10`) |

Espejo byte-idéntico en `adapters/dot-aidd/scripts/`: los cuatro scripts nuevos, `aidd_graphs.py`, `aidd_evidence.py`, `aidd_status.py`. Cada dueño copia su propio archivo al espejo (la fila lista ambas rutas). `aidd/cli.py` no se espeja.

## FR / AC → código → prueba

| Req | Código | Prueba (V) |
|---|---|---|
| FR-014 / AC-009 | `code_graph.build/parse_file/resolve_calls`, `aidd_graphs._autodetect/_command` | V-1: caller `code_fingerprint`→`code_state`, spawn `git`, SyntaxError = aviso + resto, ambiguos marcados, nombre `code` siempre builtin |
| FR-015 / AC-010 | `code_graph.link_markers`, `aidd_graphs.show` | V-1: markers → `implements`; `show` ≤ 25 líneas; unión en consulta con `find_spec` y `progress.json` |
| FR-016 / AC-011 | `method_graph.build/link_enforcers` | V-3: R10 con FUNC en `aidd_rules.py`; regla sin enforcer → `unlinked` |
| FR-017 / AC-012, AC-018 | `graph_snapshot.repeats/entrypoints` | V-3: fixture con sink por 2 caminos y llamada en bucle; `--cmd` desconocido → exit 2 |
| FR-018 / AC-013 | `graph_trace.Tracer/run_traced/merge_runtime` | V-3: comando fixture dos veces → mismos conteos |
| FR-019 / AC-014, AC-018 | `graph_snapshot.snapshot/canonical`, `aidd_evidence.append_graph_snapshot` | V-2: sha del archivo = sha del evento; etiqueta inválida o repetida rechazada; `--rev` ignora el árbol sucio |
| FR-020 / AC-014 | `graph_snapshot.diff` | V-2: par limpio imprime deltas; archivo editado o sin evento → exit 2 `snapshot altered` |
| FR-021 / AC-015 | `aidd_graphs._autodetect/status/refresh --force`, `builtin:spec` | V-4: cuatro grafos listados, ninguno `no-refresh` |
| FR-022 / AC-015 | docs + espejo | V-4 (`test_dot_aidd_mirror`) + prueba de texto sobre SKILL.md/AIDD.md/aidd-converge.md |
| FR-023 / AC-016, AC-017 | `aidd_evidence.blob_shas`, `code_graph.file_shas`, `graph_snapshot.changed`, `aidd_status.cmd_activate` | V-1/V-2: mismo tamaño + `os.utime` hacia atrás sigue listado; contenido idéntico no; sin línea base → exit 2 |
| FR-024 / AC-016 | `code_graph.build(previous=)`, `refresh --wait` imprime `re-parsed N, reused M`, `changed` imprime `affected` | V-1: `re-parsed 2` tras editar 2 archivos con `--wait --force`; `affected` con un import inverso |
| FR-025, FR-026 / AC-019 | `read_hint.main`, `mark_graph_rebuild`, `aidd_evidence.runs_find_spec`, `install_hooks` | V-4: búsqueda tras la consulta del hook (`source='hook'`) avisa; tras una consulta del agente calla 300 s y luego avisa de nuevo |
| FR-027 / AC-020 | `read_hint` (`graph_miss`), `aidd_status` (línea `graph-first`) | V-4/V-2: tres búsquedas, una dentro de los 300 s → `2 misses / 3 searches` |
| FR-028 / AC-021 | `sql_graph.analyze_sql` | V-6: fixture con el alias `oitw` termina con `skipped_statements > 0` |
| FR-031 / AC-023 | `SKILL.md`/`AIDD.md` regla E9 | V-7 vía prueba de texto en `tests/test_dot_aidd_mirror.py` (T-21 ya compara palabras; E9 y `run_parallel.py --changed` se añaden a esa lista) |
| FR-032 / AC-024 | `prompt_trigger.py` | V-7: `tests/test_prompt_trigger.py` |
| FR-033 / AC-025 | `SKILL.md`, `aidd-converge.md`, `tasks.md` (DoD), `spec.md` (`Jobs: 4`) | V-7: prueba de texto que busca "every time"/"per task" en esos archivos |
| FR-034 / AC-026 | `tests/test_perf_budget.py` | V-7 |
| FR-035, FR-036 / AC-027 | `aidd_job.run/wait/last/list`, contrato `RESULT:` | V-8 (se añade a `## Verification` tras la primera aprobación, porque el gate bloquea crear los módulos antes): `tests.test_aidd_job` |
| FR-037 / AC-028 | `aidd_triage` | V-8: `tests.test_aidd_triage` |
| FR-038, FR-041 / AC-029 | `aidd/cli.py`, espejos | V-8 + `tests.test_dot_aidd_mirror` |
| FR-039 / AC-030 | `aidd_tools` | V-9: `tests.test_aidd_tools` |
| FR-040 / AC-031 | `SKILL.md`/`AIDD.md` regla T1, `templates/tasks.md`, `prompt_trigger` | V-4/V-7: prueba de texto y prueba del hint |
| FR-029, FR-030 / AC-022 | `sql_graph` (`--kind schema`, `--kind dml`), `aidd_graphs._command` | V-6: añadir una migración reproduce 1 archivo; editar una vieja reproduce todo; cambiar una tabla reanaliza solo sus cuerpos |

## Esquemas

Grafo JSON (compatible con `_load_graph`/`show`): `{"schema":1,"generated":<excluido del hash>,"nodes":[...],"edges":[...],"warnings":[...]}`.
- Nodos `{id,type,label,source_file,source_location}`: `FILE` (+`sha`, `parsed`), `FUNC` (id `rel::qual.name`, `lineno`, `rule_ids[]`, `markers[]`), `CLASS`, `SINK` (`sink_kind` file|spawn|unresolved), `RULE`, `STEP`, `CMD`, `TEMPLATE`, `SCRIPT`.
- Aristas `{source,target,relation}`: `defines`, `imports`, `calls` (+`ambiguous`, `in_loop`), `reads` (+`path` si es literal), `spawns` (+`argv0`), `implements`, `enforced_by`, `uses`, `invokes`; `runtime` (entero) y `runtime_detail` en la arista FUNC→SINK.
- `sha` solo en FILE: blob de git del contenido del working tree; nunca mtime ni tamaño.
- Forma canónica del snapshot: `json.dumps({schema,name,label,rev,nodes ordenados por id,edges ordenadas por (source,target,relation,attrs)}, sort_keys=True, separators=(",",":"), ensure_ascii=True)`; se excluyen `generated` y rutas absolutas (ids relativos con `/`). El archivo es el cuerpo canónico exacto y el sha256 son esos bytes. Evento `graph_snapshot{name,label,sha256,nodes,edges,rev,spec}` por `aidd_evidence.append` (log de proyecto, protegido por R9; escribe el CLI, nunca el agente).

## Olas (dependencias reales)

`code_graph` es autocontenido (no depende de `blob_shas`); `graph_miss` y `runs_find_spec` (T-11) ← `read_hint`/`mark_graph_rebuild`; `code_graph` ← `method_graph.link_enforcers`, `merge_runtime`, `repeats`; `append_graph_snapshot` ← `snapshot/diff`; el despacho de `aidd_graphs` ← todos; los docs usan nombres ya fijados arriba.

| Ola | Tareas | Por qué |
|---|---|---|
| 5 | T-11 evidence, T-12 code_graph, T-31 sql_graph, T-21 mirror test, T-22/T-23/T-24 docs | archivos disjuntos; firmas fijadas en este plan |
| 6 | T-13 method_graph, T-14 graph_trace, T-15 graph_snapshot, T-27 read_hint, T-30 mark_graph_rebuild, T-28 install_hooks | necesitan el esquema de `code_graph` o los tipos de evento de T-11 |
| 7 | T-17 aidd_graphs, T-26 aidd_status, T-16, T-18, T-19, T-29, T-32, T-33 prompt_trigger, T-34 test_prompt_trigger, T-35 test_perf_budget, T-36 SKILL.md E9, T-37 AIDD.md E9, T-38 aidd-converge.md (pruebas contra interfaces ya fijadas en este plan) | integra los generadores; las pruebas comparten ola con su código (regla 2 de Step 4) |
| 8 | T-25 verificador | primero sincroniza la skill instalada con el repo (`diff -rq skill/scripts ~/.claude/skills/aidd/scripts` vacío); luego `aidd verify`, snapshots antes (rev `69218be`)/después (árbol de trabajo), evidencia AC-012/013/014/016/017/018/019/020/021/022 y re-validación de las optimizaciones del 2026-10-24 |

## Riesgos (enmienda)

1. Llamadas ambiguas (`main`, `run`): se marcan `ambiguous`, nunca se descartan; `show`/`repeats` las excluyen de los conteos "seguros" salvo `--include-ambiguous`.
2. Profiler en Windows: solo dentro de `trace`; filtro por `co_filename` bajo el bundle AIDD y conjunto cerrado de sinks; normalizar `\` y la unidad; hilos con `threading.setprofile`; los procesos hijos se cuentan como `spawn` por argv0, no se perfilan.
3. `trace` corre en proceso; un comando que haga `os._exit` o se reejecute rompe la cuenta: se detecta y se avisa. Determinismo (AC-013) con dos corridas.
4. Hash de 7k archivos ≈ 1 s con un solo `git hash-object --stdin-paths`; `changed` no parsea; límite de 30 s y respaldo en Python (`sha1(b"blob %d\0"+datos)`).
5. R9: `.aidd/` es de solo lectura para el agente; snapshots y evento los escribe el CLI. La edición manual de `before.json` (AC-014) la hace un test en el proyecto temporal, no el agente en el repo.
6. Incrementalidad con esquema cambiado: `SCHEMA_VERSION` + versión del extractor en el grafo; si difiere se reparsea todo.
7. Una fila `code` de terceros (graphify, también declarada en el charter de b1SycLink) se renombra `code-<herramienta>` al cargar (decisión del dueño: herramienta propia, no de terceros).
8. Tamper-evidence limitada (auditoría previa): un archivo de snapshot editado o una etiqueta sin evento se detectan siempre; quien tenga shell puede re-registrar un hash (R9 es léxico) y la rotación de `events.toon` (2000 filas) borraría eventos viejos. Mitigación: las filas `graph_snapshot` no rotan, `diff` imprime cuántos eventos y qué rev tiene cada etiqueta y avisa si fue reemplazada; el spec dice "evidente", no "a prueba de manipulación".
9. Skill instalada vs repo: el CLI usa primero `$AIDD_HOME`/la skill instalada. T-25 sincroniza la instalada antes de verificar para no probar código viejo.
10. El checkpoint de `db-schema` serializa el modelo en JSON (sin `pickle`); si el modelo no es serializable tal cual, el builder lo detiene y lo reporta antes de improvisar.
11. Las optimizaciones del 2026-10-24 siguen sin confirmar en git (`aidd_evidence`, `aidd_status`, `aidd_rules`, `aidd_progress`, `aidd_review` y sus espejos): el snapshot "antes" usa `--rev 69218be` y el "después" el árbol de trabajo, así la comparación es limpia sin necesidad de commit.

## Enmienda 2 (2026-10-24): optimización de los residuales (FR-044..FR-048)

Parámetros de análisis (`aidd size`): clase L porque toca `aidd_rules.py` (regla de gate); grafo existente sin refrescar (los símbolos ya están en el grafo `code`), un solo verify al cierre, un auditor por dominio lanzados juntos en UN mensaje después de congelar el código (FR-046).

**Nombres fijados (todos stdlib, sin dependencias nuevas; el código sigue en una sola ruta de lectura):**

| Archivo (dueño único) | Contenido |
|---|---|
| `skill/scripts/aidd_evidence.py` + espejo (T-48) | `read_cache()` (context manager; activa un dict por proceso `_READ_CACHE` y lo vacía al salir), `cached_read(path, reader)` (con el alcance activo devuelve el texto guardado si `(size, mtime_ns)` coincide; fuera del alcance llama a `reader(path)` sin guardar), `forget_read(path=None)` (borra una entrada o todas); `append` y toda escritura de `aidd_evidence` llaman a `forget_read`; `_read_rows` lee por `cached_read` |
| `skill/scripts/aidd_rules.py` + espejo (T-47) | `_read(p)` usa `aidd_evidence.cached_read`; toda función de `aidd_rules` que escribe un archivo llama a `aidd_evidence.forget_read(path)`; `closing_audit_diagnosis(spec_dir, root) -> list[str]` (una línea por problema, mismas condiciones que `closing_audit_covers`: dominio sin auditor que cuente tras la última edición y el último `verify_run`, auditor haiku, tag `[tasks:]`/`[verify:]` distinto, informe menor que `CLOSING_AUDIT_MIN_RESULT`, auditor anterior a `code_since`) |
| `skill/scripts/aidd_status.py` + espejo (T-49) | los comandos `status` y `progress` corren dentro de `with aidd_evidence.read_cache():`; bajo cada spec abierta imprime las líneas de `closing_audit_diagnosis` y, si faltan dominios, `next: dispatch one auditor per missing domain (<lista>) in ONE message` |
| `skill/hooks/prompt_trigger.py` (T-50) | constante `FIND_SPEC_TIMEOUT = 8` usada en la llamada a `find_spec` |
| `skill/scripts/aidd_job.py` + espejo, `.gitignore` (T-51) | `_valid_job_id(s)` (regex `^[A-Za-z0-9_.-]+$`, sin `..`) y `_job_dir(root, id)` (resuelve bajo `.aidd/jobs/`, `None` si escapa) usados por `wait`, `last` y `_exec` (salida 2 `refused`); el `cmd` que se guarda en `job.json`/`verdict.json` pasa por `aidd_evidence.redact_secrets` (import en try/except); `.gitignore` añade `.aidd/jobs/` |
| `skill/SKILL.md`, `skill/AIDD.md` + espejo (T-57, T-58) | sección única "Close sequence" con los cinco pasos de FR-046(b) y la frase "any code edit after the dispatch voids those auditors" |

El alcance de la caché es explícito (`with`) y los hooks y decisiones de gate nunca lo abren: una decisión de gate siempre lee del disco (riesgo 12).

**FR / AC → código → prueba**

| Req | Código | Prueba (V) |
|---|---|---|
| FR-044 / AC-035 | tabla `## Verification` de `spec.md` (V-5, V-10, V-11, V-12) | el verificador (T-59) corre `aidd verify` y cita los tiempos por fila |
| FR-045 / AC-036, AC-037 | `aidd_evidence.read_cache/cached_read/forget_read`, `aidd_rules._read`, `aidd_status` | V-7 (`tests/test_perf_budget.py`: conteos de lecturas con `graph_trace`), V-5 (`tests/test_aidd_rules.py`: invalidación, mismo tamaño, fuera del alcance) |
| FR-046 / AC-038 | `aidd_rules.closing_audit_diagnosis`, `aidd_status`, docs | V-5 y V-11: cuatro casos (sin auditor, tag distinto, haiku, edición posterior) |
| FR-047 / AC-039 | `prompt_trigger.FIND_SPEC_TIMEOUT` | V-7 (`tests/test_prompt_trigger.py`) |
| FR-048 / AC-040 | `aidd_job._valid_job_id/_job_dir`, `.gitignore` | V-8 (`tests/test_aidd_job.py`) |

**Olas:** ola 9 = T-47..T-58 en paralelo (archivos disjuntos; las firmas están fijadas arriba, así `aidd_status` y las pruebas no esperan al código); ola 10 = T-59 verificador (primero sincroniza la skill instalada con el repo, luego `aidd verify` una vez, la medición dinámica AC-036 con `graph_trace` antes/después y los auditores de cierre en un solo mensaje).

**Riesgos de la enmienda:** 12. Una caché de lecturas puede dejar una decisión de gate con un archivo viejo: por eso está apagada por defecto, solo la abren `status` y `progress`, se valida `(size, mtime_ns)` en cada acierto y toda escritura propia la invalida; los hooks y `rule_gate` nunca entran al alcance. 13. `mtime_ns` con la misma marca y el mismo tamaño dentro de un mismo comando: aceptado porque dentro del alcance solo escribe el propio proceso, que invalida. 14. `redact_secrets` solo cubre pares `clave=valor`; queda como excepción conocida (L3 sigue abierta). 15. Dos auditores de ediciones posteriores al despacho: el cierre se congela antes de lanzarlos (FR-046).

## Preguntas abiertas (enmienda)

Ninguna bloqueante. Fuera de esta enmienda, por decisión: conectar `check_spec.py`, `aidd verify` y el auditor de cierre al conjunto `changed` (FR-024 solo imprime `changed` y `affected`).
