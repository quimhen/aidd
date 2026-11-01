# Evidencia de solapamiento en verificaciones AIDD

Estado: análisis y propuesta; no se han modificado las tablas de verificación ni se ha ejecutado una suite para este análisis.

## Método

En Windows/Python 3.12 y Linux/Python 3.11 se recopiló `python -m unittest discover -s tests` y se recopilaron los módulos de las filas dirigidas por separado, sin ejecutar métodos de prueba. Se normalizó únicamente el prefijo `tests.` del identificador de cada caso. La primera recopilación dio 2.318 identificadores únicos en ambos sistemas; una comprobación posterior, tras añadir pruebas de rutas en otro módulo, dio 2.323. Todos los casos de los 13 módulos comparados aparecieron en discovery. No se detectaron skips mediante decoradores en esos módulos durante la segunda recopilación, pero eso no detecta llamadas a `skipTest` durante la ejecución. El script temporal es `%TEMP%/aidd_collect_overlap.py`; los conteos describen el árbol de trabajo de esta fecha y deben volver a verificarse si cambian la recopilación o los módulos.

Una tercera recopilación, después de añadir tres pruebas más de rutas, dio 2.326 IDs en ambos entornos. Los conjuntos de los módulos candidatos fueron idénticos por SHA-256 sobre IDs ordenados, UTF-8 y un salto de línea por ID: 008, 831 IDs, `74de8cc80120edcca2315e4a02a198495b7b0f4c76bb05cebff547c9a141bdc2`; 007, 1.201 IDs, `2394c18d48390782f239eba9390f36700dd19a2d17e766ad4861574a50661adf`. Estas huellas describen la lista, no garantizan equivalencia de entorno ni ejecución.

## Resultado

| Spec | Filas dirigidas incluidas en discovery | Casos recopilados en esas filas | Filas que deben conservarse |
|---|---|---:|---|
| 008 | V-2, V-3, V-4 | 831 | V-1 y V-5 (`e2e_review_roundtrip.py`) |
| 007 | V-2, V-3, V-4, V-5 | 1.201 | V-1 y V-6 (`e2e_review_roundtrip.py`) |

Los 831 y 1.201 son ejecuciones de casos potencialmente redundantes **por cierre de cada spec**, no minutos o tokens medidos. No prueban que los casos hayan pasado, ni que no se omitan en ejecución. Se observaron condiciones dependientes de entorno, por ejemplo disponibilidad de Node y `AIDD_REVIEW_FAKES_ONLY`; la recopilación por sí sola no garantiza que los casos realmente arranquen o se ejecuten en la configuración de cierre.

Un análisis mecánico de `Covers` expandió las cuatro filas originales de 008: 43 códigos FR/AC. La fila propuesta contiene esos 43 y añade 10 códigos de la enmienda (`FR-314..FR-317` y `AC-332..AC-337`), sin perder códigos originales. También comprobó que V-5 conserva en la tabla actual `python tests/e2e_review_roundtrip.py` y `contains: ROUNDTRIP OK`. Este análisis no ejecutó verificaciones; el script temporal es `%TEMP%/aidd_008_cover_union.py`.

En una ronda posterior, detallada en la evidencia parcial del spec 010, `test_r9_8dot3_alias` y `test_r9_junction_into_evidence` se omitieron en Linux porque son exclusivos de Windows. La misma ronda en Windows registró 12 skips en total, pero la salida no conservó sus IDs y razones. Para resolver la incertidumbre se ejecutaron únicamente esos dos casos en Windows con salida detallada: ambos pasaron; no se repitió la suite. Los demás skips de la ronda siguen sin identificarse. Hay además skips dinámicos posibles por ausencia de Node, Git, módulos o fuentes F28. El manifiesto futuro debe distinguir cada causa y no convertir la ausencia de evidencia en PASS.

## Propuesta conservadora

1. Mantener la prueba end-to-end como fila separada. Conservar las pruebas enfocadas para desarrollo, pero evaluar consolidar en cierre V-2–V-4 de 008 dentro de V-1 y V-2–V-5 de 007 dentro de V-1.
2. Transferir explícitamente a la fila consolidada la unión completa de `Covers`, incluidos todos los AC y requisitos de espejo. No borrar una referencia que no esté presente en la unión.
3. Antes de aprobar la consolidación, definir cómo se registrarán los casos iniciados y omitidos con razón, y demostrar que los escenarios requeridos no quedan cubiertos solo por un skip. La instrumentación de CI existente es un candidato a evaluar; sus 18 IDs obligatorios actuales no prueban por sí solos los 831 o 1.201 casos.
4. Si existe una diferencia de contexto, selección, skip o cobertura que no pueda probarse equivalente, conservar la fila dirigida correspondiente. Mantener el resultado y el tiempo por comprobación en evidencia cuando resulte necesario para el auditor.
5. Esta consolidación es por tabla y no activa la reutilización automática entre specs ni la caché entre rondas. El cierre y la auditoría independiente siguen siendo obligatorios.

La oportunidad se identificó mediante una revisión independiente en modo lectura. El control de evidencia y los cambios de `Covers` necesitan un plan de tareas revisable y la aprobación aplicable antes de modificar las tablas activas.
