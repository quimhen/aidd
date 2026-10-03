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
