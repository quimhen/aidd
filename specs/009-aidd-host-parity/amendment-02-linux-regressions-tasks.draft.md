# DRAFT — tareas para la conciliación Linux

Estado: no aprobado; no editar código o pruebas a partir de este borrador hasta completar el plan, la revisión y el sello de tareas.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-01 | FR-917, FR-920, FR-1003 | `tests/test_rule_gate.py` | LOGIC | | | cambiar el guard o eliminar cobertura Windows |

## Per-task detail

### T-01 — reconciliar expectativas por sistema operativo
**Classify**
- Nature: INCIDENT
- Kind: LOGIC
**Estimate**
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 100k
- Agent role: builder
- Model tier: high
- Wave: 1
**Detail**
- Size: ~80 changed lines; tres métodos de prueba y helpers estrictamente necesarios dentro del archivo objetivo.
- Goal: comprobar seguridad y equivalencia conforme a las reglas nativas sin perder aserciones de Windows.
- Cites: FR-917, FR-920, FR-1003.
- Depends on: plan y tareas finales aprobados; evidencia de los cuatro fallos y reconciliación de expectativas por plataforma.
- Read first: `tests/test_rule_gate.py` cuatro métodos citados en la enmienda; `tests/test_cross_platform_paths.py`; logs de la ronda y `tests/report_guard_portability.py`.
- Files to change: `tests/test_rule_gate.py` solamente; cualquier otro archivo requiere una tarea separada.
- Naming contract: conservar clases y nombres de `test_plan_md_spellings_are_all_gated`, `test_tasks_spec_and_qa_spellings_are_all_gated` y `test_bypass_case_backslash_dotdot_and_relative` para no perder cobertura requerida en CI.
- Behaviour: conservar todas las aserciones actuales en Windows. En `test_plan_md_spellings_are_all_gated`, Linux debe probar `plan.md` y `sub/../plan.md` como el artefacto protegido y verificar que `PLAN.md`, `Plan.md`, `plan.md.` y `plan.md ` son rutas nativas distintas sujetas a sus reglas ordinarias. En `test_tasks_spec_and_qa_spellings_are_all_gated`, Linux debe comprobar los nombres exactos `tasks.md`, `spec.md` y `qa-audit.md` con sus reglas R5/R2/R7, y tratar las variantes de mayúsculas como archivos distintos sujetos a R6 y R9 cuando corresponda. En `test_bypass_case_backslash_dotdot_and_relative`, Linux debe comprobar que `.AIDD/Evidence` no es `.aidd/evidence`, que un archivo de esa ruta sigue sujeto a R6 y que las formas inferiores y con `..` siguen bloqueadas por R9. Si una ruta de barra invertida no representa una ruta nativa, demostrar su decisión según el contrato aprobado, sin asumir un alias Windows. No modificar el test ni el umbral de rendimiento: el caso puntual ya pasó en almacenamiento local Linux.
- Tests first: usar los cuatro fallos ya registrados como evidencia roja; añadir únicamente pruebas que distingan protección real de alias extranjeros antes de corregir las expectativas.
- Verify: `python -m unittest tests.test_rule_gate.TestB3CanonicalPaths.test_plan_md_spellings_are_all_gated tests.test_rule_gate.TestB3CanonicalPaths.test_tasks_spec_and_qa_spellings_are_all_gated tests.test_rule_gate.TestR9ProtectedPaths.test_bypass_case_backslash_dotdot_and_relative` -> exit 0 en cada OS disponible; una ronda coordinada posterior verifica guard, equivalencia y espejos y registra skips reales.
- Do NOT: suprimir casos, desactivar R6/R9, convertir fallos en skips generales, cambiar el guard, aumentar límites sin evidencia o afirmar que un SO no disponible pasó.
- Done when: resultados por plataforma, seguridad y equivalencia están verificados; cualquier límite no verificado queda explícito.
- Open questions: none.

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-01 | builder | 20 | 100 | 1.0 |

Total agent time (critical path): 20 min
Total tokens (k): 100
