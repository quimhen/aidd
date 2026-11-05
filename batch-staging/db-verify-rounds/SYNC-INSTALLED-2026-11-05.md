# Sincronizacion fuente <- instalado (2026-11-05)

Amendment 10 de spec 007, item 0 (H0 / FR-370). Decision del owner 2026-11-05: "aplicar parches y commit local" (sin push).

## Ramas y commits

- Rama de partida: `wip/aidd-2026-11-01` (HEAD `cfe1d0f`). No se ha tocado.
- Rama nueva: `sync/installed-2026-11-05`.
  - `b559962` snapshot del arbol de trabajo tal cual (todo lo que estaba sin commitear, sin cambios).
  - Segundo commit: la sincronizacion (este documento va incluido en el).
- Sin push. `main` no se ha tocado.

## Metodo

Comparacion fichero a fichero (sha256 sobre bytes con CRLF->LF) del arbol combinado instalado
(`scratchpad/combined-batch/tree`) contra el arbol de trabajo, y despues una clasificacion a tres bandas contra
`cfe1d0f` (base comun del arbol combinado):

- (a) solo instalado (combinado != HEAD, fuente == HEAD) -> se copio el fichero del combinado.
- (b) solo fuente (combinado == HEAD) -> se dejo el fichero del fuente.
- (c) ambos lados -> `git merge-file` (fuente / HEAD / instalado) y resolucion explicita.

Scripts (scratchpad de la sesion, `sync/`): `cmp.py`, `classify.py`, `merge3.py`, `resolve_status.py`, `apply.py`,
`pre_targets.py`, `runtests.py`.

## Lo que se aplico

(a) copiado del instalado (19): `skill/` y `adapters/dot-aidd/` de `hooks/mark_code_edit.py`, `hooks/rule_gate.py`,
`scripts/aidd_guard.py`, `scripts/aidd_review.py`, `scripts/aidd_rules.py`, `scripts/aidd_tools.py`,
`scripts/check_spec.py`, `templates/review.html`; ademas `skill/hooks/stop_gate.py`, `tests/test_aidd_review.py`,
`tests/test_review_template.py`.

Nuevos del instalado (7): `skill/scripts/aidd_close_ledger.py`, `skill/scripts/aidd_red.py` (y sus espejos en
`adapters/dot-aidd/scripts/`), `tests/test_b10_b11_b6.py`, `tests/test_b12_b5.py`, `tests/test_tasks_batch_coverage.py`.

(c) fusionados (6):

| Fichero | Resultado |
|---|---|
| `aidd/cli.py` | merge limpio: cli instalado (close-ledger, red, `close <spec_id> [--check]`) + del fuente `explorer [name]` y el subcomando `coverage` (aidd_coverage.py). |
| `skill/scripts/aidd_progress.py` (+ espejo) | merge limpio: batch coverage del instalado + alias via `alias_graph.load_aliases` y estados renamed/deleted del fuente. |
| `tests/test_dot_aidd_mirror.py` | merge limpio: lista del instalado + `unified_graph.py`, `aidd_coverage.py`, `alias_graph.py` del fuente. |
| `skill/scripts/aidd_status.py` (+ espejo) | 2 conflictos, ver abajo. Se conserva el preflight FR-292 de `cmd_check`. |

### Conflictos de `aidd_status.py` (`cmd_verify`)

1. Inicio de seleccion de filas: el fuente anadio la rama `--changed` (`always_rows`, `_changed_selection_fingerprint`,
   `added`); el instalado cambio `_read(d / 'tasks.md')` por `_read_tasks(d)` (tasks.md + `tasks-<nombre>.md`).
   Resolucion: bloque del fuente completo, leyendo con `_read_tasks(d)`.
2. Recomprobacion final de la seleccion: mismo caso; bloque del fuente (con `always_rows`) leyendo con `_read_tasks(d)`.

Ningun conflicto quedo sin resolver.

## (b) diferencias declaradas: fuente != instalado tras la fusion

Solo fuente, a proposito: `skill/AIDD.md`, `skill/SKILL.md`, `scripts/aidd_evidence.py`, `scripts/aidd_graphs.py`,
`scripts/aidd_unit_audit.py`, `scripts/graph_explorer.py`, `scripts/install_hooks.py`, y los nuevos
`aidd_coverage.py`, `alias_graph.py`, `unified_graph.py`, `hooks/tool_first_hint.py`; y por fusion
`aidd_progress.py`, `aidd_status.py` (FR-292 + `--changed`), `aidd/cli.py`. `adapters/dot-aidd/` igual.
Nota: `~/.claude/skills/aidd/CORE.md` (27-oct) es mas viejo que `adapters/dot-aidd/CORE.md` (le falta el parrafo
"Wave contract"); no es divergencia del fuente. `~/.claude/skills/aidd/scripts/aidd_evidence.py.bak` existe solo en
el instalado (resto de una instalacion; no se copio).

## Comprobaciones de hash

- `precheck.json`: los 25 ficheros objetivo coinciden con su hash (LF) salvo `aidd_progress.py` y `aidd_status.py`
  (skill y proyecto), que difieren solo por (b)/(c) declarado.
- `sim_hash.py` en ambos sentidos (instalado vs fuente, lectura sobre b1SycLink): salida identica. P01
  `c1b501a5c7a9` OK, F37 `b27d68844c20` sin cambio, F40 sin cambio, F42 `440389e478dd`; 63/65 iguales, cambian F42 y
  F38 (ficheros de lote), igual que con el instalado.

## Pruebas (cada modulo por separado y en secuencia, `AIDD_HOME=<repo>/skill`)

Antes = paquete instalado (`combined-batch/tests.log`); despues = rama de sincronizacion.

| modulo | antes | despues |
|---|---|---|
| test_dot_aidd_mirror | 13 OK | 13 OK |
| test_cli_rules | 14 OK | 15 OK (+1 del fuente) |
| test_b12_b5 | 18 OK | 18 OK |
| test_tasks_batch_coverage | 20 OK | 20 OK |
| test_b10_b11_b6 | 15 OK | 15 OK |
| test_review_template | 63 OK | 63 OK |
| test_aidd_review | 64 OK | 64 OK |
| test_aidd_review_items | 65 OK | 65 OK |
| test_aidd_review_state | 52 OK | 52 OK |
| test_aidd_rules | 245 OK | 245 OK |
| test_aidd_rules_r10 | 55 OK | 55 OK |
| test_aidd_status | 147 OK | 147 OK |
| test_check_spec | 42 OK | 42 OK |
| test_aidd_guard | 38 OK | 38 OK |
| test_aidd_progress | 16 OK | 16 OK |
| test_aidd_tools | 12 OK | 12 OK |
| test_aidd_unit_hash | 5 OK | 5 OK |
| test_rule_gate | 266 OK | 266 OK (en la 1a pasada fallo solo la prueba de tiempos `test_timing_irrelevant_file_spec_file_and_bash`, fichero irrelevante 219 ms frente a 68 ms de python pelado, fuera del margen bajo carga; `rule_gate.py` es identico al instalado; repetida sola: OK) |
| test_stop_gate | 43 OK | 43 OK |

Pruebas del fuente (b): test_evidence 156, test_install_hooks 17, test_aidd_coverage 18, test_alias_graph 9,
test_unified_graph 10, test_verify_changed_policy 11, test_explorer_controls 7, test_unified_explorer 11,
test_tool_first_hint 18, test_graph_explorer 9 (pytest; con unittest corre 0 por ser estilo pytest): todas OK.

## Como volver atras

- Sin esta sincronizacion: `git switch wip/aidd-2026-11-01` deja HEAD en `cfe1d0f`; el estado previo exacto del
  arbol de trabajo esta en el commit `b559962` de esta rama (`git diff cfe1d0f b559962`).
- Copia de seguridad completa del arbol de trabajo previo (sin `.git`):
  `C:\Users\jquimis\AppData\Local\Temp\claude\496965ba541d9601\b04babae-8d68-44cd-bec6-541c2de69378\scratchpad\sync-backup\aidd-worktree-pre-sync-2026-11-05.tar`
  (+ `status-before.txt`, `diff-before.patch`). Ojo: el scratchpad es temporal de la sesion.

## Pendiente

- Nada instalado ni en `~/.claude/skills/aidd` ni en `b1SycLink/.aidd`: el preflight FR-292 y `--changed` siguen
  sin estar instalados (H0.1). Reinstalar desde esta rama es decision del owner.
- `tools/aidd_bundle_diff.py` (T-00) no se escribio; la comparacion se hizo con scripts de scratchpad.
