# Borrador de plan — una ejecución de la suite en el cierre de 008

Estado: **borrador, no implementado ni aprobado**. Fuente: `docs/aidd-verification-overlap-2026-11-01.md`. Esta propuesta no activa caché histórica ni comparte resultados entre specs.

## Naming & File Contract

| Item | Convention |
|---|---|
| Runner | `tests/run_parallel.py`; preservar el comportamiento de las opciones existentes |
| Fixture tests | `tests/test_ci_runner.py`; `unittest`, sin lanzar una suite real en las pruebas sintéticas |
| Coverage manifest | `specs/008-aidd-compact-review-direct-save/verification-required-ids.txt`; IDs canónicos sin skips permitidos para la fila estricta |
| Verification table | `specs/008-aidd-compact-review-direct-save/spec.md`; conservar V-5 end-to-end y la unión completa de `Covers` |
| Evidence | una ejecución y su resultado por entorno; registrar IDs iniciados, skips y motivo sin copiar logs en prompts |

## Contrato propuesto

1. La ejecución de cierre selecciona una sola discovery de `tests`, registra cada ID iniciado y cada skip con su razón, y valida la lista de cobertura que antes estaba distribuida en V-2–V-4. La recopilación de IDs puede hacerse sin ejecutar los casos; no cuenta como una segunda prueba.
2. El comando de la tabla aprobada fija el SHA-256 exacto del manifiesto. El runner vuelve a comparar el conjunto exacto recopilado de los ocho módulos y exige que coincida con el manifiesto; un ID añadido, eliminado o renombrado falla. No hay reuso histórico: el suite se ejecuta de nuevo en cada verificación; los cambios de código durante su ejecución quedan sujetos al fingerprint agregado vigente.
3. Ningún caso requerido ausente o skip pasa silenciosamente en esta primera versión. Los dos casos Windows-only dejan la ejecución Linux parcial y sin PASS; no se afirma cobertura Windows en Linux ni viceversa. Los 18 IDs obligatorios existentes del runner 009 son una protección adicional, no sustituyen los 831 IDs recopilados para 008.
4. Mantener V-5 (`python tests/e2e_review_roundtrip.py`) como comprobación aparte. La fila consolidada debe conservar todos los códigos de `Covers` de V-1–V-4, incluyendo AC y espejo. Las pruebas por módulo siguen disponibles para desarrollo.
5. `--full`, códigos de salida, timeouts, historial de evidencia y gates se mantienen; no hay `REUSED` histórico. Una ejecución fallida o incompleta no da PASS. El informe debe separar lo ejecutado, los skips y las pruebas no verificadas.

## Incremento concreto propuesto

La primera implementación usa un manifiesto de texto UTF-8 con un ID canónico por línea, ordenado y sin duplicados. La lista candidata actual tiene 831 IDs y huella `74de8cc80120edcca2315e4a02a198495b7b0f4c76bb05cebff547c9a141bdc2`. El generador obtiene los IDs de los ocho módulos ya identificados sin ejecutar casos y compara contra la discovery global; debe rechazar errores de importación, IDs duplicados y cualquier caso que falte. No escribir un manifiesto desde una recopilación incompleta.

Esa huella es el contrato de la **primera** integración, no una constante eterna. Si cambian legítimamente los IDs, ejecutar el generador en modo lectura, presentar únicamente el delta de IDs y la nueva huella para revisión del dueño, y actualizar juntos manifiesto y comando mediante una enmienda autorizada. Hasta disponer de aprobación por unidad, la versión actual de AIDD exige el sello que corresponda a la tabla modificada; no inventar una aprobación ni afirmar que ya se puede aprobar solo el delta. Cambios que no alteren la lista no requieren regenerarla.

El runner agrega `--coverage-manifest`, `--manifest-sha256` y `--coverage-timeout` al modo `--ci-guard`; la fila fija 3600 segundos y el digest aprobado. El launcher transmite exactamente esas opciones al único worker. Este lee bytes estables y comprueba el digest fijado antes y después; con una única discovery compara el conjunto exacto de los ocho módulos con el manifiesto y, al terminar, exige que todos hayan iniciado y ninguno haya sido omitido. Un manifiesto cambiado antes o durante la ejecución, ilegible, vacío, duplicado o malformado falla. Mantiene los 18 IDs obligatorios, el preflight de guard fijado, la captura de errores y el comportamiento previo sin las nuevas opciones. El preflight y el timeout explícito de 3600 son cambios frente a la antigua V-1 y deben comprobarse; V-5 conserva su comando y esperado. En Linux dos skips dejan esta fila sin PASS; no se infiere evidencia Windows desde Linux.

Los 831 IDs preservan las filas históricas, pero no incluyen los tests nuevos de la propia enmienda. En modo manifiesto el worker exige adicionalmente los siete métodos `TestCoverageManifest` de T-380 y los 19 métodos `TestCIRunner` de T-382, con sus nombres completos exactos; un ID nuevo ausente u omitido también impide PASS. Estos 26 IDs son un contrato distinto de los 831 y de los 18 IDs ya existentes; no alterar el digest histórico de la lista para incluirlos silenciosamente.

Las opciones de manifiesto son un conjunto indivisible: faltantes, duplicadas, sin `--ci-guard` o su modo interno `--ci-guard-worker`, con digest inválido o timeout no positivo producen código 2 sin lanzar worker. La prueba sintética verifica tanto que el launcher crea exactamente un worker como que el worker llama exactamente una vez a discovery y una vez a `run_suite`; no basta con simular el subprocess. Las rutas antiguas `--ci-guard` y `--ci-guard-worker` sin opciones siguen funcionando exactamente como antes.

Fila de cierre propuesta, sujeta a comprobación mecánica de la unión original: `V-1 | python tests/run_parallel.py --ci-guard --coverage-manifest specs/008-aidd-compact-review-direct-save/verification-required-ids.txt --manifest-sha256 74de8cc80120edcca2315e4a02a198495b7b0f4c76bb05cebff547c9a141bdc2 --coverage-timeout 3600 | exit 0 | FR-301..FR-317, AC-301..AC-330, AC-332..AC-337` más los IDs literales de las tareas nuevas. `V-5` conserva `python tests/e2e_review_roundtrip.py`, `contains: ROUNDTRIP OK` y sus `Covers` originales. Antes de retirar una fila, comparar la unión expandida de códigos originales y nueva; una diferencia inesperada bloquea la integración.

Este diseño reduce el cierre de 008 de una discovery más tres ejecuciones dirigidas a una sola discovery y un solo recorrido de la suite, más V-5. Se verifica con pruebas sintéticas de selección, ID ausente, duplicado y skip, y después una única ejecución de cierre en cada entorno disponible. La actualización de los IDs después de cambiar pruebas es una operación explícita de recopilación sin ejecución, no una nueva auditoría. Este incremento no resuelve por sí solo la invalidación de un spec por archivos ajenos cuando su `Scope` sigue siendo global; delimitar y probar sus dependencias es trabajo separado.

## Bloqueos antes de implementar

- La revisión independiente de la integración con unidades detectó que T-357 añade pruebas en un módulo incluido en el manifiesto histórico. Si ambas enmiendas se integran juntas, recopilar el conjunto final y presentar su delta y digest; el valor de 831 es una línea base, no el conjunto final autorizado. La tabla debe declarar también las tareas y requisitos de unidades y exigir sus pruebas concretas, sin inferir cobertura de discovery.
- Definir cómo se autoriza el primer incremento con el mecanismo vigente sin atribuirle una aprobación por unidad que todavía no existe. Mantener las aprobaciones históricas intactas. La auditoría y cierre por unidad requieren un registrador verificable de auditoría independiente o conservar el cierre completo como alternativa; no afirmar que el borrador ya proporciona esa capacidad.
- Las tareas de economía se renumeraron T-380 a T-384 para no colisionar con T-360 a T-363 de la propuesta de convergencia. Comprobar unicidad otra vez al integrar cualquier enmienda.
- Los skips no identificados de la ronda Windows no se consideran cobertura. La fila estricta comprueba al ejecutar que los 831 IDs arrancan sin omisión; si no, no hay PASS y se conserva el diagnóstico sin repetir automáticamente.
- Completar y revisar tareas y pruebas sintéticas de IDs ausentes, nuevos o renombrados, skips dinámicos/de clase, manifiesto malformado o alterado antes/durante, propagación de timeout y preflight, y CLI anterior. Después presentar una única aprobación de la enmienda; no modificar la tabla activa ni el runner antes de ello.

## Validación y barrera

Tras la aprobación y cambios: pruebas sintéticas pequeñas del runner; una sola ronda de cierre completa por entorno disponible; comprobar IDs iniciados, motivos de skip, unión de `Covers` y V-5. Un auditor independiente revisa la evidencia sin repetir la suite. Informar ahorro medido, no estimar tokens como resultado.
