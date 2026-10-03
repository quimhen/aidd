# QA Audit — 005 AIDD token planning

Auditorías de cierre independientes (ninguna implementó): performance (opus `high`, verificación delta y verificación final en sonnet) y lógica y seguridad (opus `high`) con re-auditoría tras las correcciones. Resultado final: PASS WITH NOTES.

## Mapping ledger
| Code | Status | Evidence (file/class/resource id) | PR/Spec ref | Screenshot diff done? |
|---|---|---|---|---|
| FR-001 | ✅ IMPLEMENTED | skill/scripts/aidd_rules.py `_check_tasks`, `_check_tokens`; TestTokenPlanning | T-06 | n/a (sin UI) |
| FR-002 | ✅ IMPLEMENTED | skill/scripts/aidd_calibrate.py, `aidd calibrate record` (aidd/cli.py); tests/test_aidd_calibrate.py | T-03, T-08 | n/a |
| FR-003 | ✅ IMPLEMENTED | `derived_human_hours`; plantilla tasks.md; SKILL.md | T-04, T-06, T-19 | n/a |
| FR-004 | ✅ IMPLEMENTED | `_check_roles` (R13) | T-06 | n/a |
| FR-005 | ✅ IMPLEMENTED | `_wave_roles_ok`; `aidd_status._waves` por nombre | T-06, T-10 | n/a |
| FR-006 | ✅ IMPLEMENTED | mark_agent_dispatch.py (modelo, `model_source`, agentes integrados y de archivo); R14 en aidd_rules, rule_gate, stop_gate, aidd_status | T-01, T-02, T-07, T-10 | n/a |
| FR-007 | ✅ IMPLEMENTED | cabecera `Risk:` en plantilla; SKILL.md y aidd-converge.md | T-04, T-19, T-20 | n/a |
| FR-008 | ✅ IMPLEMENTED | `plan_totals`; línea en check_spec.py y en `aidd status` | T-10, T-11 | n/a |
| FR-009 | ✅ IMPLEMENTED | `_is_legacy_tasks` (solo aprobado y sin columna de tokens es legado); 001-004 intactos | T-06, F1 | n/a |
| FR-010 | ✅ IMPLEMENTED | aidd_status.py cierre y abandono con `[spec:<id>]`; `typed_approval` (respuestas negativas, `since_ts`) | T-10, F4 | n/a |
| FR-011 | ✅ IMPLEMENTED | `_strip_code_spans` solo en specs hermanas (R4) | T-12 | n/a |
| FR-012 | ✅ IMPLEMENTED | guía de una sola confirmación en SKILL.md y AIDD.md | T-19, T-20 | n/a |
| FR-013 | ✅ IMPLEMENTED | aidd_evidence.py `sync_ask_answers`; llamada en rule_gate.py y prompt_trigger.py; transcript protegido (R9) | T-05, T-07, T-09, T-12, F3 | n/a |
| FR-014 | ✅ IMPLEMENTED | `record_queued_messages` y `queued_messages` en prompt_trigger.py | T-05, T-09 | n/a |
| AC-001 | ✅ IMPLEMENTED | `aidd status` y `check_spec.py` imprimen `~N min`; TestPlanTokens | T-10, T-11, T-16 | n/a |
| AC-002 | ✅ IMPLEMENTED | TestTokenPlanning (suma por ola y total) | T-13 | n/a |
| AC-003 | ✅ IMPLEMENTED | TestTokenPlanning (R13) | T-13 | n/a |
| AC-004 | ✅ IMPLEMENTED | tests/test_r14.py (haiku no cuenta, mensaje "model tier too low") | T-14 | n/a |
| AC-005 | ✅ IMPLEMENTED | tests/test_r14.py (sonnet, opus, sin modelo cuentan) | T-14 | n/a |
| AC-006 | ✅ IMPLEMENTED | tests/test_aidd_calibrate.py (idempotente) | T-15 | n/a |
| AC-007 | ✅ IMPLEMENTED | `check_spec.py` sobre 004 y 005 sin hallazgos R1/R13; fixture legado aprobado | T-13, F1 | n/a |
| AC-008 | ✅ IMPLEMENTED | tests/test_typed_confirmations.py | T-17 | n/a |
| AC-009 | ✅ IMPLEMENTED | TestTokenPlanning (R4 con backticks) | T-13 | n/a |
| AC-010 | ⚠️ PARTIAL | el flujo de un solo clic depende de instalar los scripts en `~/.claude/skills/aidd`; ver excepciones | T-19 | n/a |
| AC-011 | ✅ IMPLEMENTED | clic `[tasks:37ed463c]` → 'Approve' recuperado del transcript real; tests/test_transcript_sync.py | T-18 | n/a |
| AC-012 | ✅ IMPLEMENTED | tests/test_transcript_sync.py (`queued_messages` sin duplicados) | T-18 | n/a |

## Device preflight
N/A: tarea de scripts y hooks, sin dispositivo ni UI.

## Execution evidence
| Code | Kind | Evidence | Verified by |
|---|---|---|---|
| AC-011 | command-output | evidence/suite-and-audits-005.txt | agent |
| AC-007 | command-output | evidence/suite-and-audits-005.txt | agent |
| AC-004 | command-output | evidence/suite-and-audits-005.txt | agent |

Suite completa: 1159 tests OK (antes 1033).

## Bug reports
| # | Code | Symptom | Root cause | Fix | Pattern sweep |
|---|---|---|---|---|---|
| 1 | FR-013 | un clic que llega al transcript después de la sincronización de su pregunta se pierde | `parse_transcript_pairs` reconstruía `known` en cada llamada y el offset ya había pasado la pregunta | `pending` persistido en el marcador (máximo 20) | `grep` de `known = {}` en aidd_evidence.py: 1 uso, corregido |
| 2 | FR-006 | el gate en vivo (rule_gate) y R8 no decían "model tier too low" | el mensaje se construía en tres sitios y solo el de check_spec añadía la nota | nota añadida en rule_gate `_qa_gate` y stop_gate | `grep` de "auditor subagent ran": 3 sitios, los 3 corregidos |
| 3 | FR-009 | un tasks.md nuevo con el encabezado antiguo evadía los chequeos de tokens y roles | la exención dependía de la forma del encabezado y no de la aprobación | exención solo si `_is_legacy_tasks` (aprobado y sin columna de tokens) | fixtures migrados a un solo helper; sondas del auditor |
| 4 | FR-006 | un agente `Explore` (haiku por defecto) sin campo `model` contaba como auditor | solo se leía `tool_input.model` | resolución por tabla de agentes integrados y por `model:` del archivo del agente | los demás tipos (`general-purpose`, `Plan`, otros) se resuelven vacíos y cuentan: desconocido, falla abierta |
| 5 | FR-013 | un script podía escribir en el transcript y falsificar aprobaciones | `_mentions` no incluía rutas de transcript | patrón `.claude…projects….jsonl` en `_mentions`; sufijo `::$DATA` | brecha residual al partir la palabra `.claude` en pedazos |
| 6 | FR-010 | un `Abandon` escrito antes de una aprobación seguía vigente y un "No, keep it" no lo cancelaba | `since_ts` fijo en 0 y respuestas negativas ignoradas | `since_ts` desde la última aprobación o cierre; la respuesta etiquetada más reciente gana | mismo patrón en cierre y aprobación, revisado |
| 7 | FR-006 | seis despachos de subagentes (T-19, T-20, ajuste de stop_gate, auditorías, F1-F4) no quedaron en el log de evidencia | el hook PostToolUse de Agent falla sin dejar `hook_error`, probablemente por su timeout de 10 s con muchos agentes corriendo tests en paralelo | sin arreglo en esta spec: se despachó una verificación final con la máquina en reposo y quedó registrada; pasa a la spec 006 | revisión del log: los despachos de T-01 a T-18 y T-21 sí constan |

## Resilience check (per code that crosses a boundary — network, DB, disk, external API, hardware)
| Code | Timeout set? | Retry/backoff? | Graceful degradation? | Recoverable trace on failure (where)? |
|---|---|---|---|---|
| FR-013, FR-014 | timeout de 10 s del hook | n/a (el offset retoma lo no leído) | un transcript ausente, vacío o con otro formato no registra nada y no lanza; queda la respuesta escrita | `hook_error` en el log de sesión |
| FR-006 | timeout de 10 s del hook | n/a | modelo no resuelto = cuenta (falla abierta, documentado) | campo `model_source` en el evento |

## Backend contract check (per API-nnn touched)
N/A: no se tocó ningún API-nnn.

## Database robustness check (per API-nnn/entity that touches a database)
N/A: sin base de datos.

## Performance & Best Practices check (Performance & Best Practices Auditor — applies to any code touched, every convergence)
| File/class | OOP/SOLID verified in code? | Interfaces used at real boundaries? | Locking/isolation deliberate for the engine? | Connection pooling verified (not just declared)? | No N+1 / unbatched loop? | No blocking call on hot path? |
|---|---|---|---|---|---|---|
| skill/scripts/aidd_evidence.py (sync, queued, typed) | funciones con una responsabilidad | transcript leído solo por offset | marcador escrito con `os.replace` (atómico) | n/a | uniones lineales (300 eventos: 8 ms) | transcript real de 5.3 MB: primera pasada 42 ms, sin cambios 0.2 ms |
| skill/hooks/rule_gate.py | n/a | n/a | n/a | n/a | n/a | el hook agrega ≈47 ms sobre el arranque de Python; `_mentions` peor caso adversarial de 100 KB: 541 ms |
| skill/hooks/mark_agent_dispatch.py | n/a | n/a | n/a | n/a | n/a | resolución de modelo ≈ +20 ms sobre el arranque |
| skill/scripts/aidd_rules.py y check_spec.py | n/a | n/a | n/a | n/a | `_check_tasks` de 500 tareas: 45-74 ms | `check_spec.py` de la spec 005: 93 ms |

## Revision log (append, never overwrite)
- 2026-10-03: auditoría de performance (opus, high): PASS WITH NOTES.
- 2026-10-03: auditoría de lógica y seguridad (opus, high): FAIL; tres hallazgos altos corregidos (F1-F3) y dos menores (F4).
- 2026-10-03: re-auditoría de seguridad y funcionamiento (opus, high): PASS WITH NOTES.
- 2026-10-03: verificación delta de performance (sonnet): PASS WITH NOTES.
- 2026-10-03: verificación final de performance (sonnet, registrada tras la última edición): PASS WITH NOTES.

## Open exceptions (rows left unresolved on purpose)
| Code | Reason | Approved by |
|---|---|---|
| AC-010 | Falta instalar la spec en `~/.claude/skills/aidd` (el guard de AIDD impide que el agente escriba ahí); hasta entonces el clic del popup no se registra y se usa la respuesta escrita | pendiente del usuario |
| FR-013 | Brecha residual: un script con la palabra `.claude` partida (`'.cl'+'aude'`) escribe en el transcript. Endurecimiento propuesto: aceptar solo respuestas cuyo `tool_use_id` también registró el hook PostToolUse | pendiente del usuario |
| FR-006 | Se desconoce si `general-purpose`, `Plan` o los agentes de plugins corren en haiku; hoy cuentan (falla abierta). El campo `model` explícito siempre se respeta | pendiente del usuario |
| FR-010 | Un clic de "Abandon" no lo cancela un `No, keep it` escrito después, porque se evalúa primero el clic | pendiente del usuario |
| FR-013 | Mejoras opcionales de performance: limitar con `readline(limit)` el tamaño de línea del transcript (una línea de 12 MB cuesta 54 ms) y evitar que un `Bash ls` importe el módulo de evidencia (+17 ms por proceso) | pendiente del usuario |
