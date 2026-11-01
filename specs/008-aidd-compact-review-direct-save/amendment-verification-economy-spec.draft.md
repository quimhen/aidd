# Borrador de enmienda — evitar verificaciones duplicadas en 008

Estado: **borrador, no aprobado ni implementado**. La propuesta modifica el cierre de 008; no cambia aprobaciones existentes, no comparte resultados entre specs y no autoriza caché histórica.

## Alcance

El usuario pidió evitar que se repitan pruebas y auditorías sin cambios relevantes. En el árbol actual, la recopilación en Windows/Python 3.12 y Linux/Python 3.11 identificó los mismos 831 casos en V-2–V-4 y V-1, sin ejecutar esos casos durante la comparación. Detalles y límites: `docs/aidd-verification-overlap-2026-11-01.md`.

## Requisitos

| FR-nnn | Requirement | Cites |
|---|---|---|
| FR-314 | En el cierre de 008 ejecutar una sola vez la suite completa y mantener una comprobación separada del flujo end-to-end; preservar la unión de códigos cubiertos por V-1–V-4 y el comando V-5. | V-1..V-5 |
| FR-315 | Generar sin ejecutar casos un manifiesto reproducible de los IDs requeridos; rechazar recopilación incompleta, duplicados, errores o diferencias con discovery. El digest esperado se vincula al comando de verificación aprobado. | 008 V-2..V-4 |
| FR-316 | El runner compara el digest aprobado antes y después, exige el conjunto exacto de IDs de los módulos y los 26 tests nuevos de la enmienda, y que cada ID haya iniciado y no haya sido omitido; manifiesto vacío, ilegible, alterado o malformado falla. Registrar skips y razones sin convertirlos en PASS. | 009 FR-919 |
| FR-317 | Mantener los 18 IDs obligatorios, los timeouts, los errores del runner, la evidencia anterior y el comportamiento sin manifiesto. No activar reutilización entre specs ni entre rondas. | 009 FR-919; 007 FR-205 |

## Casos de aceptación

| Case | Real data | Expected | Edge? |
|---|---|---|---|
| AC-332 | Los ocho módulos candidatos de 008 | Una ejecución de discovery contiene el mismo conjunto de IDs que el manifiesto; V-5 se ejecuta aparte. | no |
| AC-333 | ID requerido ausente, duplicado, renombrado u omitido | El runner no entrega PASS y nombra el ID o la causa. | yes |
| AC-334 | Manifiesto modificado antes o durante la ejecución, vacío, ilegible o malformado | El runner compara con el digest aprobado, no entrega PASS y conserva la evidencia anterior. | yes |
| AC-335 | Dos tests exclusivos de Windows omitidos en Linux | El modo estricto de manifiesto no presenta esa ejecución como cierre completo; la cobertura Windows se informa aparte. | yes |
| AC-336 | Invocación anterior sin argumento de manifiesto | Comando, timeout, 18 IDs obligatorios y resultado conservan la semántica previa. | yes |
| AC-337 | Cambio de `Covers` al consolidar | La unión explícita de V-1–V-4 queda en la fila consolidada; V-5 y sus códigos se preservan. | yes |

## Riesgos y pendientes de revisión

Esta medida elimina ejecuciones duplicadas **dentro del cierre de 008**, no evita por sí sola que archivos ajenos invaliden un scope global ni agrupa pruebas entre specs. Se requieren pruebas sintéticas del runner, un manifiesto real revisable y una única ronda final por entorno. Cualquier skip requerido no está verificado y bloquea el PASS estricto. La aprobación visual sigue siendo opcional y no forma parte de esta enmienda.
