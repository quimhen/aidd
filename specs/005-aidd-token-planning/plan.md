# Plan — 005 AIDD token planning

Borrador del Mapper independiente (Step 3, modelo medio) y revisado por cuatro auditores de nivel medio. Sin pantallas ni componentes: Screen/Component/Entry/Device/Design system = N/A.

## Naming & File Contract

Stdlib only, una responsabilidad por función. Líneas de `skill/scripts/aidd_rules.py` antes de editar.

| Name | Purpose |
|---|---|
| `AGENT_ROLES`, `MODEL_TIERS`, `LOWEST_TIER_RE`, `HUMAN_FACTOR_DEFAULT` | constantes junto a `RULE_IDS` (`:26`); `RULE_IDS` suma `R13` y `R14`; `MODEL_TIERS = ('medium','high')`, cualquier otro valor (incluido `low`) es inválido |
| `_is_legacy_tasks(text)` | `approval_valid` y encabezado Waves sin columna `tokens` (FR-009) |
| `_check_tokens(blocks, waves)` | `Tokens (est):` por tarea, `Tokens (k)` por ola = SUMA, `Total tokens (k):` = suma de olas (R1) |
| `_check_roles(blocks)` | R13: `Agent role:` en `AGENT_ROLES`, `Model tier:` en `MODEL_TIERS` |
| `_wave_roles_ok(row, blocks)` | la columna `Roles` de la ola coincide con los roles de sus tareas (FR-005) |
| `derived_human_hours(agent_min, factor)` | minutos × factor / 60 (FR-003); no bloquea en v1 |
| `plan_totals(tasks_text)` | `{'minutes','tokens_k'}` para `aidd status` y `check_spec` (FR-008) |
| `is_low_tier(model)`, `_subagent_counts(event)` | R14: no cuenta si `model` contiene `haiku` (sin distinguir mayúsculas, incluye `claude-haiku-*`); vacío o `inherit` cuenta |
| `_uncovered_reasons(...)` | dominio → `tier` o `none`, para decir "model tier too low (R14)" en R7 |
| `_strip_code_spans(text)` | quita fragmentos entre backticks de una línea; solo en el bucle de specs hermanas de R4 (FR-011) |
| `skill/scripts/aidd_calibrate.py` (nuevo) | `load_calibration`, `parse_closed_tasks`, `record(spec_dir, root)` con UNA fila agregada por clase y clave (spec, clase), idempotente; `main` con `record <spec_dir>` |
| `skill/templates/calibration.toon` (nuevo) | semilla con los datos medidos de la spec 004 |
| `parse_transcript_pairs(path, start_offset)` (`aidd_evidence.py`) | lee el transcript JSONL desde un offset, solo líneas completas; guarda `tool_use` de `AskUserQuestion` (id → `input.questions`) y, en el `tool_result` con ese id, usa `toolUseResult.answers` (si no, `parse_answers` sobre `content`); devuelve `(pares, nuevo_offset)`; nunca lanza |
| `sync_ask_answers(transcript_path, session, root=None)` | agrega los eventos `question` y `answer` que faltan; no duplica por `tool_use_id` ni por texto de pregunta ya registrado (incluye los que escribiría el hook PostToolUse); archivo marcador `<tmp>/aidd-hooks/<sid>.transcript.json` con `{offset, ids}` |
| `record_queued_messages(root, session, queued)` | registra cada entrada de `queued_messages` como evento `prompt` con `source='queued'`, sin duplicados (marcador con timestamp o sha1) |

## FR / AC → code

| Req | Code anchor |
|---|---|
| FR-001, AC-002 | `_check_tasks` (`aidd_rules.py:318-411`): variante de encabezado en `:329-330`, textos en `:321-322` y `:332-334`, relleno a 6 celdas en `:339`, Agent time y Human ref por variante en `:376-381` y `:388-391`; `_check_tokens` |
| FR-002, AC-006 | `aidd_calibrate.py`; subcomando `calibrate` en `aidd/cli.py`; `calibration.toon` |
| FR-003, AC-001 | `derived_human_hours`; plantilla `tasks.md`; texto de `SKILL.md` |
| FR-004, AC-003 | `_check_roles` desde `_check_tasks`; el gate de `tasks.md` ya corre `check_content` (`rule_gate.py:531-539`) |
| FR-005 | encabezado y `_wave_roles_ok`; `aidd_status._waves` (`:139-150`) lee las columnas por nombre |
| FR-006, AC-004, AC-005 | `mark_agent_dispatch.py:44-47` registra `model`; filtro R14 en `_uncovered` (`aidd_rules.py:1210-1236`), sitios R5 (`aidd_rules.py:1499,1507,1512`, `rule_gate.py:224-239`) y `aidd_status.py:194`; `stop_gate.py` lo recibe vía `uncovered_domains` |
| FR-007 | cabecera `Risk:` en la plantilla de spec; `SKILL.md` y `aidd-converge.md`; solo documentación |
| FR-008 | `aidd_status.py` (`:139-150`, `:208-209`, `:340`) y línea en `check_spec.py` |
| FR-009, AC-007 | `_is_legacy_tasks` al inicio de los chequeos nuevos. Las specs 001-004 no se tocan; `approval_hash` y `approval_valid` no cambian |
| FR-010, AC-008 | `aidd_status.py:574` (cierre) y `:596` (abandono, con `spec_id` porque `d` puede ser None) pasan `must_contain=f'[spec:{id}]'`; la pregunta lleva la misma etiqueta |
| FR-011, AC-009 | `aidd_rules.py:853`, solo en el bucle de specs hermanas (`:845-853`); no tocar `:841-843` |
| FR-012, AC-010 | guía en `SKILL.md`/`AIDD.md`: resumen de objetivos con costo y UNA confirmación; el clic del popup queda registrado por FR-013; si no hay transcript, vale la respuesta escrita (FR-010) |
| FR-013, AC-011 | funciones de `aidd_evidence.py` arriba; `rule_gate.py` llama a `sync_ask_answers` antes de `decide()` (`:1043`) y antes de la salida rápida de comandos de shell (`:1038`) para que `aidd rules approve` vea el clic; `prompt_trigger.py` también (`:198`); `transcript_path` sale de `C.str_field(event,'transcript_path')` (`_common.py:106`); R9: `is_protected_path` (`aidd_rules.py:1281`) suma `(^|/)\.claude/projects/[^/]+/[^/]+\.jsonl$` y `rule_gate._protected`/`_mentions` lo reflejan |
| FR-014, AC-012 | `prompt_trigger.py:198`, dentro del mismo `try`, llama a `record_queued_messages` con `event['queued_messages']` |

Formato real del transcript (verificado en esta sesión): línea `assistant` con `message.content[]` → `{type:'tool_use', id, name:'AskUserQuestion', input:{questions:[{question,options:[{label}]}]}}`; línea `user` con `toolUseResult = {questions, answers:{<pregunta>: <etiqueta>}}` y `tool_result.tool_use_id`. Se empareja siempre por `tool_use_id`, nunca por búsqueda de texto (otros resultados contienen la misma etiqueta).

## Data formats

Bloque de tarea en `tasks.md`:
```
- Agent min: 2
- Tokens (est): 60k
- Agent role: builder
- Model tier: medium
- Human ref hours: 0.1
```
Waves (nuevo): `| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |`; el encabezado de 4 columnas sigue válido solo en modo legado. Tiempo de ola = máximo de sus tareas; Tokens = suma; debajo, `Total agent time (critical path): N min` y `Total tokens (k): N`.

`.aidd/calibration.toon`: `human_factor: 3`; clases Low 1 min / 45k, Medium 2 min / 62k, High 4 min / 90k (fuente `seed-004`); tabla `runs` con una fila por (spec, clase).

Evento de subagente: `{type, desc, head, model}`; `model` sale de `tool_input.model`, vacío si falta. Eventos `question`/`answer` ganan `tool_use_id` opcional.

## Risks

1. Cambiar R1 rompe tests y plantillas (el encabezado antiguo aparece en 5 sitios de tests). Mitigación: modo legado y un helper `new_tasks()` en `gate_fixtures.py`.
2. Hay que re-sincronizar la skill instalada y el espejo (incluir `aidd_calibrate.py`). Los hooks no están en el espejo: se reinstalan.
3. El nombre del campo del modelo en el Agent tool se asume `model`; verificarlo con un payload real. Si falta, R14 degrada a "cuenta" (falla abierta).
4. Abandonar usa `since_ts=0`: un `Abandon` viejo de la sesión cuenta, pero ahora solo para el mismo spec por la etiqueta.
5. No reescribir el `tasks.md` de ninguna spec aprobada: invalidaría su aprobación y bloquearía las ediciones de código. El `tasks.md` de esta spec usa el encabezado vigente (las reglas nuevas aún no existen); su migración al formato nuevo se hace al cerrarla.
6. El transcript depende del formato del host: si cambia, el sync no registra nada (falla segura) y queda la respuesta escrita. Leer el transcript en cada llamada cuesta tiempo: el marcador de offset lo hace incremental.
7. Un agente no debe poder escribir en el transcript: se protege con R9 (Write/Edit y la mención lexical en shell).

## Task split

Roles y nivel de modelo por tarea; minutos y tokens según la línea base medida en la spec 004. Una ola solo agrupa archivos distintos.

| Wave | Task | File | Role / tier | Min | Tokens (k) |
|---|---|---|---|---|---|
| 1 | T-01 | skill/scripts/aidd_rules.py (constantes, R14, filtros R5) | builder / medium | 3 | 75 |
| 1 | T-02 | skill/hooks/mark_agent_dispatch.py | builder / medium | 1 | 50 |
| 1 | T-03 | skill/scripts/aidd_calibrate.py y skill/templates/calibration.toon | builder / medium | 3 | 70 |
| 1 | T-04 | skill/templates/tasks.md y spec.md | docs / medium | 2 | 50 |
| 1 | T-05 | skill/scripts/aidd_evidence.py (sync del transcript, queued, tool_use_id) | builder / medium | 3 | 70 |
| 2 | T-06 | skill/scripts/aidd_rules.py (R1 tokens, R13, legado, encabezado doble) | builder / high | 3 | 80 |
| 2 | T-07 | skill/hooks/rule_gate.py (filtro R14, llamada al sync, mención R9) | builder / medium | 3 | 70 |
| 2 | T-08 | aidd/cli.py | builder / medium | 1 | 50 |
| 2 | T-09 | skill/hooks/prompt_trigger.py (sync y mensajes en cola) | builder / medium | 2 | 55 |
| 3 | T-10 | skill/scripts/aidd_status.py (totales, filtro R14, etiquetas de cierre y abandono) | builder / medium | 3 | 65 |
| 3 | T-11 | skill/scripts/check_spec.py | builder / medium | 1 | 50 |
| 3 | T-12 | skill/scripts/aidd_rules.py (FR-011 y ruta protegida del transcript) | builder / medium | 2 | 55 |
| 4 | T-13 | tests/test_aidd_rules.py y gate_fixtures.py | tests / medium | 3 | 75 |
| 4 | T-14 | tests/test_r14.py | tests / medium | 2 | 60 |
| 4 | T-15 | tests/test_aidd_calibrate.py | tests / medium | 2 | 55 |
| 4 | T-16 | tests/test_aidd_status.py | tests / medium | 2 | 55 |
| 4 | T-17 | tests/test_typed_confirmations.py | tests / medium | 2 | 60 |
| 4 | T-18 | tests/test_transcript_sync.py (AC-011 y AC-012) | tests / medium | 3 | 65 |
| 5 | T-19 | skill/SKILL.md y skill/AIDD.md (resumen y una confirmación) | docs / medium | 2 | 60 |
| 5 | T-20 | commands/aidd-tasks.md y commands/aidd-converge.md | docs / medium | 1 | 50 |
| 5 | T-21 | adapters/dot-aidd/scripts (espejo de los scripts cambiados) | builder / medium | 1 | 50 |
| 6 | T-22 | auditoría de performance | auditor / high | 3 | 70 |
| 6 | T-23 | auditoría de lógica (R14, legado, sync del transcript, confirmaciones) | auditor / high | 3 | 70 |

Camino crítico: 17 min de agente (olas 3 / 3 / 3 / 3 / 2 / 3). Tokens: 1410k en total (olas 315 / 255 / 170 / 370 / 160 / 140). Horas humanas de referencia = minutos × 3 / 60, derivadas.

## Preguntas abiertas

Ninguna bloqueante. El piso de modelo solo excluye el nivel más bajo; un modelo ausente o heredado cuenta.
