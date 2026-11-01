# Borrador de tareas — cierre sin filas duplicadas de 008

Estado: borrador; no aprobado ni implementado. Se basa en el plan `amendment-verification-economy-plan.draft.md`. La implementación no activa caché histórica ni reutilización entre specs.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-380 | FR-314, FR-315, FR-316, FR-317 | `tests/test_coverage_manifest.py` | LOGIC | | | ejecución de la suite real |
| T-381 | FR-314, FR-315, FR-316, FR-317 | `tests/coverage_manifest.py` | LOGIC | | | editar spec o ejecutar casos |
| T-382 | FR-314, FR-315, FR-316, FR-317 | `tests/test_ci_runner.py` | LOGIC | | | ejecución de la suite real |
| T-383 | FR-314, FR-315, FR-316, FR-317 | `tests/run_parallel.py` | LOGIC | | | caché histórica, compartir entre specs |
| T-384 | FR-314, FR-315, FR-316, FR-317 | `specs/008-aidd-compact-review-direct-save/spec.md` | LOGIC | | | eliminar V-5 o perder `Covers` |

## Per-task detail

### T-380 — pruebas del generador de IDs
**Classify**
- Nature: REQUIREMENT
- Kind: LOGIC
**Estimate**
- Agent min: 10
- Human ref hours: 0.50
- Tokens (est): 70k
- Agent role: tests
- Model tier: medium
- Wave: 1
**Detail**
- Size: ~100 changed lines.
- Goal: demostrar selección completa y generación determinista sin ejecutar pruebas reales.
- Cites: FR-314, FR-315, FR-316, FR-317.
- Depends on: enmienda aprobada.
- Read first: `specs/008-aidd-compact-review-direct-save/amendment-verification-economy-plan.draft.md`; `docs/aidd-verification-overlap-2026-11-01.md`.
- Files to change: `tests/test_coverage_manifest.py` solamente.
- Naming contract: `test_complete_sorted`, `test_missing_fails`, `test_duplicate_fails`, `test_collection_error_fails`, `test_no_test_execution`, `test_added_or_renamed_id_fails`, `test_check_requires_matching_manifest` en `TestCoverageManifest`.
- Behaviour: usar suites sintéticas y un loader falso; importar el módulo futuro dentro de cada caso para recoger los siete casos antes del fallo rojo; verificar IDs canónicos ordenados, error por IDs faltantes, nuevos, renombrados o duplicados, comparación exacta contra el manifiesto existente y ausencia de llamadas a métodos de prueba.
- Tests first: crear los siete casos y registrar `python -m unittest tests.test_coverage_manifest -v` fallando por módulo no existente, no por cero pruebas.
- Verify: `python -m unittest tests.test_coverage_manifest -v` -> exit 0 y 7 casos después de T-381.
- Do NOT: importar la suite completa o ejecutar el runner real.
- Done when: casos rojos y verdes registrados por el orquestador.
- Open questions: none.

### T-381 — generador de manifiesto
**Classify**
- Nature: REQUIREMENT
- Kind: LOGIC
**Estimate**
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 90k
- Agent role: builder
- Model tier: high
- Wave: 2
**Detail**
- Size: ~120 changed lines.
- Goal: obtener la lista de casos requeridos de forma reproducible sin ejecutarlos.
- Cites: FR-314, FR-315, FR-316, FR-317.
- Depends on: T-380 rojo y enmienda aprobada.
- Read first: `tests/run_parallel.py`; `specs/008-aidd-compact-review-direct-save/amendment-verification-economy-plan.draft.md`; después del rojo, leer el archivo de pruebas creado por T-380.
- Files to change: `tests/coverage_manifest.py` solamente.
- Naming contract: `build_manifest(discovered_ids, selected_ids)` y `main(argv=None)`; modos `--dry-run`, `--check` y `--write`; módulos `test_aidd_review`, `test_review_template`, `test_aidd_status`, `test_cli_rules`, `test_typed_confirmations`, `test_rule_gate`, `test_aidd_rules`, `test_dot_aidd_mirror`.
- Behaviour: seleccionar exactamente `test_aidd_review`, `test_review_template`, `test_aidd_status`, `test_cli_rules`, `test_typed_confirmations`, `test_rule_gate`, `test_aidd_rules`, `test_dot_aidd_mirror`; normalizar solo el prefijo `tests.`, rechazar errores de recopilación, IDs vacíos, duplicados o faltantes y generar UTF-8 ordenado, un ID por línea con salto final. `--dry-run` no escribe y muestra conteo/hash; `--check` compara bytes con el destino fijo y falla si no existe o difiere; `--write` acepta exclusivamente el destino fijo del plan. Ningún modo ejecuta casos. Informar conteo y SHA-256, sin imprimir IDs completos.
- Tests first: T-380 debe estar rojo por ausencia del módulo.
- Verify: `python -m unittest tests.test_coverage_manifest -v` -> exit 0; `python tests/coverage_manifest.py --dry-run` -> exit 0 y 831 IDs en el árbol actual, o discrepancia explícita sin escribir; después de T-384 `python tests/coverage_manifest.py --check` -> exit 0.
- Do NOT: aceptar un conjunto incompleto, ejecutar test methods o escribir en otro destino.
- Done when: pruebas sintéticas verdes y lista contrastada con discovery; cambios futuros de pruebas que alteren IDs se detectan.
- Open questions: none.

### T-382 — pruebas del runner con manifiesto
**Classify**
- Nature: REQUIREMENT
- Kind: LOGIC
**Estimate**
- Agent min: 12
- Human ref hours: 0.60
- Tokens (est): 80k
- Agent role: tests
- Model tier: medium
- Wave: 1
**Detail**
- Size: ~100 changed lines.
- Goal: probar el rechazo de cobertura incompleta sin ejecutar una suite real.
- Cites: FR-314, FR-315, FR-316, FR-317.
- Depends on: enmienda aprobada.
- Read first: `tests/test_ci_runner.py`; contrato del manifiesto en el plan.
- Files to change: `tests/test_ci_runner.py` solamente.
- Naming contract: `run_suite`; `test_manifest_complete`, `test_manifest_missing_id`, `test_manifest_new_id`, `test_manifest_duplicate_id`, `test_manifest_required_skip`, `test_manifest_class_skip`, `test_manifest_changed`, `test_manifest_wrong_digest`, `test_manifest_empty`, `test_manifest_unreadable`, `test_manifest_malformed`, `test_manifest_cli_single_worker`, `test_manifest_worker_single_suite`, `test_manifest_cli_incomplete_options`, `test_manifest_cli_invalid_combinations`, `test_manifest_timeout`, `test_manifest_loader_failure`, `test_manifest_discovery_failure`, `test_legacy_cli_unchanged`.
- Behaviour: con suites sintéticas y archivos temporales comprobar IDs iniciados, nuevos, faltantes, duplicados, skips dinámicos/de clase, errores de archivo, hash incorrecto o cambiado, preflight, discovery, timeout y CLI anterior. Simular subprocess y afirmar exactamente un worker; probar su recorrido con discovery y `run_suite` falsos y afirmar exactamente una llamada a cada uno. Opciones faltantes, duplicadas, incompatibles, digest inválido o timeout no positivo deben producir código 2 sin subprocess; sin recursos externos.
- Tests first: `python -m unittest tests.test_ci_runner -v` -> fallos de funciones de manifiesto aún inexistentes, con los casos recogidos.
- Verify: `python -m unittest tests.test_ci_runner -v` -> exit 0 después de T-383.
- Do NOT: ejecutar discovery completa, debilitar los 18 IDs actuales o suprimir errores.
- Done when: rojo y verde sintético registrados.
- Open questions: none.

### T-383 — una sola ejecución con cobertura exigida
**Classify**
- Nature: REQUIREMENT
- Kind: LOGIC
**Estimate**
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 120k
- Agent role: builder
- Model tier: high
- Wave: 2
**Detail**
- Size: ~120 changed lines.
- Goal: ejecutar discovery una vez y fallar si la lista aprobada no se ejecutó por completo.
- Cites: FR-314, FR-315, FR-316, FR-317.
- Depends on: T-382 rojo y enmienda aprobada; serializar con el propietario del runner 009.
- Read first: `tests/run_parallel.py` `TrackingResult`, `run_suite`, `ci_worker`, `run_checked`, `main`; T-382.
- Files to change: `tests/run_parallel.py` solamente.
- Naming contract: `load_coverage_manifest(path)`, `REQUIRED_008_NEW_IDS` y opciones `--coverage-manifest`, `--manifest-sha256`, `--coverage-timeout`; conservar `run_suite`, `ci_worker`, `run_checked` y CLI previo.
- Behaviour: aceptar las tres opciones juntas solo con `--ci-guard` o el modo interno `--ci-guard-worker`, rechazar opciones faltantes/duplicadas/incompatibles, digest no hexadecimal de 64 caracteres o timeout no positivo con código 2 antes de lanzar, y propagar una vez al único worker, con timeout explícito de 3600 en la fila de 008. El worker valida UTF-8 ordenado, no vacío, sin duplicados ni líneas malformadas, y compara el SHA-256 recibido antes y después de ejecutar. Rechaza rutas fuera del spec 008 o enlaces que escapen. En la única discovery compara el conjunto exacto de los ocho módulos con el manifiesto, detecta IDs nuevos o ausentes, añade el manifiesto a los 18 obligatorios y a `REQUIRED_008_NEW_IDS`, y ejecuta una sola vez; falla si un ID no inicia o se omite. `REQUIRED_008_NEW_IDS` contiene exactamente los siete IDs completos de `test_coverage_manifest.TestCoverageManifest` nombrados en T-380 y los 19 IDs completos de `test_ci_runner.TestCIRunner` nombrados en T-382; estos 26 IDs no alteran los 831 del manifiesto. Errores de colección, preflight, instrumentación y timeout fallan. Sin opciones nuevas conservar exactamente CLI y timeout previos. En Linux los dos casos Windows-only quedan explícitamente sin verificar y el modo manifiesto falla si se omiten.
- Tests first: T-382 debe fallar por la capacidad ausente.
- Verify: `python -m unittest tests.test_ci_runner -v` -> exit 0; la ejecución completa se realiza una vez en T-384.
- Do NOT: validar solo conteos, aceptar skips requeridos, exponer datos sensibles, alterar el timeout de llamadas anteriores ni copiar evidencia de otra ronda.
- Done when: pruebas sintéticas verdes y compatibilidad anterior intacta.
- Open questions: none.

### T-384 — consolidar la tabla tras preservar la cobertura
**Classify**
- Nature: REQUIREMENT
- Kind: LOGIC
**Estimate**
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 80k
- Agent role: integrator
- Model tier: high
- Wave: 3
**Detail**
- Size: ~10 changed lines y un manifiesto generado de 831 IDs.
- Goal: ejecutar una sola suite en el cierre de 008, manteniendo la comprobación end-to-end.
- Cites: FR-314, FR-315, FR-316, FR-317.
- Depends on: T-381 y T-383 verdes; aprobación de la tabla final.
- Read first: `specs/008-aidd-compact-review-direct-save/spec.md` V-1 a V-5; plan y evidencia de recopilación.
- Files to change: `specs/008-aidd-compact-review-direct-save/spec.md` y `specs/008-aidd-compact-review-direct-save/verification-required-ids.txt` generado por T-381.
- Naming contract: V-1 usa `python tests/run_parallel.py --ci-guard --coverage-manifest specs/008-aidd-compact-review-direct-save/verification-required-ids.txt --manifest-sha256 74de8cc80120edcca2315e4a02a198495b7b0f4c76bb05cebff547c9a141bdc2 --coverage-timeout 3600`; V-5 conserva su comando, su ID, `contains: ROUNDTRIP OK` y sus `Covers`.
- Behaviour: para la primera integración generar la lista candidata sin ejecutar pruebas y exigir el digest fijado; en V-1 declarar `FR-301..FR-317, AC-301..AC-330, AC-332..AC-337, T-380, T-381, T-382, T-383, T-384`; comparar mecánicamente los códigos originales expandidos con la propuesta antes de eliminar V-2–V-4, y detenerse ante cualquier código perdido. Conservar V-5. Si la lista no corresponde a la recopilación actual o contiene skips, no dar PASS. Registrar entorno, IDs y skips en la evidencia. Para cambios futuros legítimos de IDs, generar el delta sin ejecutar, obtener autorización y actualizar manifiesto y digest conjuntamente; la huella inicial no es una constante eterna.
- Tests first: conservar los resultados de recopilación previos y las pruebas sintéticas de T-380/T-382; no ejecutar la suite antigua de nuevo.
- Verify: `python skill/scripts/check_spec.py specs/008-aidd-compact-review-direct-save` -> exit 0 estructural; `aidd verify specs/008-aidd-compact-review-direct-save` -> exit 0 en Windows solo si todos los IDs requeridos y V-5 pasan; en Linux los dos skips Windows-only se registran y no dan PASS estricto; una ejecución por entorno disponible.
- Do NOT: inferir un cierre Linux de la evidencia Windows, eliminar V-5, modificar otras specs, usar una caché histórica o afirmar cobertura de skips.
- Done when: evidencia de una sola suite por entorno, V-5, ausencia de omisiones no autorizadas y auditoría independiente.
- Open questions: none.

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-380, T-382 | tests | 12 | 150 | 0.60 |
| 2 | T-381, T-383 | builder | 20 | 210 | 1.00 |
| 3 | T-384 | integrator | 15 | 80 | 0.75 |

Total agent time (critical path): 47 min
Total tokens (k): 440
