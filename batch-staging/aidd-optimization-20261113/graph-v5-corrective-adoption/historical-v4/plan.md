# Plan — Explicit bounded incremental graph refresh after a stale code miss

## Naming & File Contract

| Item | Convention |
|---|---|
| Functions and files | snake_case Python; preserve public ABI |
| Types/classes | PascalCase; no production class required |
| Target ownership | One lane per file; mirrors generated, not hand edited |

## Entry route

CLI input → existing parser → targeted read-only operation → bounded explicit verdict. Offline failures never fabricate PASS, consent or freshness.

## Exact implementation contract


Actualmente `skill/scripts/aidd_graphs.py::show` (`:888`) carga el grafo, calcula `stale` y ante un miss de código devuelve la advertencia. El refresco existe en `refresh(root,name,background=True,force=False)` y `code_graph.build_with_cache`; conserva contenidos no modificados. El caso observado no demuestra un defecto del algoritmo incremental: falta una operación simple para refrescar y repetir la consulta sin varios pasos manuales.

- Nuevo flag **opt-in** `aidd graphs show code <query> --refresh-on-miss`. Sin flag, comportamiento idéntico.
- Sólo si grafo builtin:code está stale y la consulta no encontró FILE/FUNC: invocar una vez el refresh incremental registrado, foreground con el timeout ya establecido por el mecanismo de refresco. No hacer `refresh all`, no forzar full parse ni importar/ejecutar fuentes del proyecto.
- Tras refresh exitoso volver a cargar nodos/stamp y repetir **una vez** la consulta original. Etiqueta clara de consulta repetida y resumen `re-parsed N,reused M`.
- Lock ocupado/debounce/timeout/error: devolver estado explícito `pending`/`failed`, mensaje acotado y comando para consultar luego; no afirmar ausencia, frescura ni resultado actualizado.
- Consulta con hit/fresh miss y flag no inicia procesos. Grafo externo, UI, method, SQL o desconocido conservan comportamiento; el flag fuera de code debe fallar como uso inválido, no hacer fallback silencioso.
- No refrescar por defecto en hooks/read hints ni romper la política XS/S. El usuario/agente pide el flag expresamente. No Graphify ni proveedor externo.

Firma propuesta compatible: `show(root,name,query,limit=25,refresh_on_miss=False)`; helper privado `_show_code_retry(root,e,query,limit)` encapsula una única repetición, sin recursión no acotada. La CLI elimina el flag antes de ensamblar el query; un nombre de símbolo que lo contenga como texto normal debe seguir consultable mediante separador `--` si la CLI actual lo soporta, o documentar que sólo el token exacto es flag. No inventar nuevos flags de tiempo en este incremento.


## Execution contract

One file owner per lane. Native AIDD graphs first, bounded reads and outputs. Mechanical operations use mapping/dry-run/apply/post-check. Builders run static checks only; coordinator executes RED before each body, then the union of checks once after source freeze. Preserve failures and exact inputs; no invented PASS or consent. No Graphify, database, Docker, external API, installed-skill update or B1SyncLink write. Do NOT modify approval/event logs, relax gates, change unrelated local edits, reinterpret presence as behavior, or reuse a DB result from container identity alone. Final full verification and required perf/audit of the host spec remain applicable at official close.

## Approval gate

Pending owner consent through the official unit review package. This file is not an approval. Historical base approval remains independent and unchanged. No production implementation before the exact unit is approved.

## V3 convergence plan

Preserve all existing graph contracts. Reject a missing/blank joined query after all supported options are stripped and before show. Add only tests/test_aidd_graphs_empty_query.py; real focused RED/GREEN and independent review are retained under batch-staging/aidd-optimization-20261113/graph-empty-query-v3. Do not repeat the unrelated123/48 suites, change graph refresh, install runtime, forge a seal or treat V2 consent as V3 consent. Fresh official audit/owner review closes the delta.

## V4 active-lock convergence plan

Honor FR-373/AC-370-3/4 when status is genuinely running: opt-in missing query result must be pending/uncertain, not unqualified absence, and must not start another refresh. Add only tests/test_aidd_graphs_running_state.py and retain real4-case RED/GREEN/independent review. Valid hits, no-flag behavior, parser and generation implementation remain unchanged. Current native audit and owner exact V4 seal are mandatory; no original verifier or B1 source/runtime changes.
