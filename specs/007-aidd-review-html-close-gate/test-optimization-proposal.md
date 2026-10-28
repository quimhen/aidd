# Propuesta: verificación determinista y económica por ola

Fecha: 2026-10-27. Estado: análisis y propuesta; implementación pendiente de aprobación.
Amendment de 007 (FR-205: verificación ejecutada), con impacto en las reglas E7–E9.

## Objetivo solicitado

Los scripts ejecutan los tests, comprueban sus resultados y calculan el veredicto completo de la ola. El agente revisa ese veredicto, su cobertura, vigencia y métricas; diagnostica los fallos y modifica código cuando corresponda. No sustituye asserts por lectura de SQL, logs o razonamiento propio.

## Evidencia del repositorio

| Hallazgo | Fuente | Implicación |
|---|---|---|
| Ya existe un ejecutor con timeout, evidencia, hashes, tiempos y caché por fila/ronda | `skill/scripts/aidd_status.py:1435`, `:1469`, `:1516`, `:1589` | Extenderlo; no crear un segundo sistema de ejecución |
| `contains:` comprueba texto sin exigir exit 0 | `skill/scripts/aidd_status.py:1461` | Un proceso fallido puede aprobar si imprimió el texto esperado |
| No hay selección ni validación mecánica de cobertura por ola | `skill/scripts/aidd_status.py:1589`, `skill/scripts/aidd_rules.py:2025` | Ejecutar algunas filas no demuestra que se verificó toda la ola |
| El runner convierte `NO TESTS RAN` en éxito | `tests/run_parallel.py:121` | Una ejecución vacía puede quedar verde |
| La selección no comprueba el exit code de Git; los procesos de tests no tienen timeout | `tests/run_parallel.py:68`, `:121` | Selección vacía ante error; procesos sin límite |
| El runner divide módulos por clases automáticamente | `tests/run_parallel.py:113` | Puede repetir imports y preparación costosa; medir antes de dividir |
| SQL sin parser o sin comprobador de motor termina en exit 0 | `skill/scripts/aidd_sqlcheck.py:185` | Omitir compilación no debe equivaler a validarla |
| La suite completa se combina con ejecuciones de módulos ya incluidos | `specs/007-aidd-review-html-close-gate/spec.md:165–169` | La caché de comandos idénticos no elimina selecciones parcialmente solapadas |
| Los scripts distribuidos tienen un espejo obligatorio | `tests/test_dot_aidd_mirror.py` | Mantener `adapters/dot-aidd/scripts/` y documentación distribuida |

Los ejemplos `db_verify.py` y `apply_local_db.py` citados en la metodología pertenecen a proyectos consumidores. No se encontró un runner de integración DB propio ni una BD configurada en AIDD. Aquí se puede probar la orquestación y sus contadores; medir tiempos reales de SQL, seeds y preparación requiere el runner del proyecto consumidor.

### Línea base ejecutada

Comando: `python -m unittest tests.test_aidd_sqlcheck tests.test_aidd_status.TestVerify -v`.
Se utilizó Python 3.14 instalado por uv mediante su ruta absoluta, porque `python` no está en PATH y `py` no encuentra una instalación.

Resultado de unittest: **17 tests, 21,338 s, exit 0, 1 skipped** (`pglast` ausente); 16 ejecutados sin fallo.
Esto valida el comportamiento actual, incluido un test que espera exit 0 para un motor SQL sin comprobador. No demuestra que los huecos señalados estén corregidos. No se ejecutaron la suite completa ni tests de integración contra una BD real.

## Contrato propuesto

### 1. Un manifiesto completo por ola

Interfaz propuesta, aún no disponible: `aidd verify <spec...> --wave <id> --json`.

El planificador deriva las tareas de la tabla Waves y sus códigos; resuelve las filas de Verification mediante Covers. Debe admitir una asociación explícita tarea/fila para tareas sin códigos o verificaciones compartidas. Un enlace desconocido, ambiguo o faltante es un error de configuración, nunca una selección vacía aprobada.

El manifiesto enumera tareas, códigos, scripts, inputs y recursos. Deduplica invocaciones idénticas y conserva todas sus asociaciones de cobertura. Scripts distintos que cubren el mismo código siguen ejecutándose: compartir cobertura no significa equivalencia. La suite completa no se combina con subconjuntos incluidos salvo que un adaptador pueda demostrarlo mediante IDs de tests; no inferir equivalencia a partir del texto del comando.

Antes de ejecutar, valida el manifiesto entero. Después de los builders, ejecuta todos sus scripts ejecutables aunque alguno falle. Si una dependencia falla, registra los dependientes como bloqueados y sigue con los independientes. Rechaza `--bail` para el cierre completo de una ola. Un resultado de ola no sustituye la verificación final de toda la spec.

### 2. El script decide

PASS exige exit 0, evidencia válida y vigente, cobertura completa y comprobaciones satisfechas. `contains:` es una condición adicional, no una alternativa al exit code. Un test negativo debe estar encapsulado en un test que termine con exit 0 al comprobar correctamente el fallo esperado.

Para tests, cero ejecutados, selección fallida, informe ausente o mal formado y timeout producen FAIL/ERROR. Una ola documental sin tests debe declararse expresamente y reportarse como no aplicable; no se convierte en una ejecución de tests exitosa. Lint y compilación reportan archivos comprobados, no cantidades ficticias de tests.

JSON versionado: identidad de spec/ola y manifiesto, huellas de inputs, resultado agregado, filas previstas/ejecutadas/reutilizadas/fallidas/bloqueadas, cobertura, tests ejecutados/omitidos cuando el runner los reporte, tiempos, evidencia y motivos de no reutilización. stdout JSON contiene solo JSON; diagnósticos van a stderr. Exit no cero si el resultado no es PASS. El agente consume el resumen; abre logs específicos únicamente para diagnosticar.

Los adaptadores de resultados usan salidas estructuradas del runner (por ejemplo unittest/JUnit) cuando estén disponibles. No declarar cobertura de asserts a partir de una búsqueda de texto. La cobertura del manifiesto prueba que se ejecutaron los checks declarados; la calidad y suficiencia de esos checks sigue necesitando revisión técnica.

### 3. Economía de ejecución

- Reutilizar `_run_row` y la infraestructura de evidencia/caché existentes; los resultados nuevos deben someterse al contrato actualizado antes de aceptar cachés anteriores.
- Una invocación idéntica con los mismos inputs se ejecuta una vez por lote. Reutilización conserva el origen y comprueba la integridad de evidencia.
- `run_parallel.py`: módulo completo como unidad predeterminada; división por clases explícita, timeout, deduplicación y reporte estructurado. Error de Git no produce una lista vacía exitosa. Cambio de helpers/fixtures de tests debe seleccionar sus dependientes o recurrir conservadoramente al conjunto completo.
- No reintentar automáticamente todos los fallos: reintento explícito y acotado, con primer fallo y segundo resultado conservados y estado flaky visible. Nunca reportarlo como PASS limpio.
- Probar costes mediante contadores de invocaciones, preparaciones y lecturas; usar tiempos para diagnóstico y presupuestos con tolerancia. No reducir cobertura para mejorar una cifra.

### 4. Base de datos

La compilación SQL estática y los tests DB son fases diferentes. La primera no prueba permisos, resultados, planes de ejecución ni interacción entre migraciones. Si el comprobador es obligatorio y falta, el script falla; una omisión opcional debe quedar explícita y no satisfacer una comprobación requerida de la ola.

Cada proyecto declara su motor, comando de preparación, runner de integración, datos iniciales y recurso exclusivo. Una preparación por lote, una base de trabajo fija por proyecto y bloqueo entre procesos que compartan ese recurso. La preparación se comparte con los tests del lote; estos usan rollback, limpieza o un reset reproducible para no contaminarse. No se ejecuta SQL improvisado por archivo desde el agente.

La clave de plantilla incluye bootstrap, migraciones, seeds y motor/configuración relevantes. La clave de resultado incluye además tests, runner, dependencias/versiones relevantes y estado inicial reproducible. El hash de un SQL aislado solo permite reutilizar su compilación, no sus tests de integración. Si no puede probarse el estado externo, no reutilizar un PASS de integración; sí puede reutilizarse una plantilla válida para reconstruirlo.

Preparación, aplicación de migraciones y validación tienen registros diferentes: un archivo ya comprobado puede necesitar aplicarse a una base recién restablecida. Un PASS de tests nunca aplica ni autoriza cambios en producción.

El runner informa tiempos de preparación, aplicación, seeds, tests y limpieza; cache hits/misses y número de reconstrucciones. Debe poder detectar reconstrucciones o invocaciones duplicadas y presupuestos declarados excedidos. El bloqueo no debe quedar abandonado tras timeout o caída del proceso.

## Opciones para decidir alcance

Estimaciones preliminares de trabajo automatizado, no benchmarks ni compromisos de aceleración.

| Opción | Alcance | Riesgo/coste relativo | Recomendación |
|---|---|---|---|
| A | Endurecer exit codes, cero tests, timeout y omisiones SQL | Menor cambio; no demuestra cobertura de ola | Parche inicial si se necesita una entrega mínima |
| B | A + manifiesto/cobertura por ola, JSON, deduplicación y contrato DB medible | Cambio medio en orquestación y compatibilidad de evidencia | Recomendada: satisface el pedido completo en AIDD |
| C | B + implementar/optimizar un adaptador de integración de un motor y proyecto concreto | Depende del runner y datos reales; no estimable aquí con rigor | Después de identificar el proyecto consumidor |

Owner pick: pendiente. La opción B automatiza la evaluación en AIDD; C es necesaria para demostrar y corregir cuellos de botella internos de una BD concreta.

## Desglose propuesto de B

| Ola | Trabajo | Archivos principales | Dependencias |
|---|---|---|---|
| 1 | Contrato y resolución de cobertura; endurecer runner local y compilación SQL; tests de esos comportamientos | `skill/scripts/aidd_rules.py`, `tests/run_parallel.py`, `skill/scripts/aidd_sqlcheck.py`, tests asociados | Contrato de resultado fijado antes de integrar |
| 2 | Integrar selección por ola, agregación JSON y reutilización segura en el ejecutor existente; adaptar evidencia de ola sin habilitar cierre de spec; tests de ejecución | `skill/scripts/aidd_status.py`, `skill/scripts/aidd_evidence.py` si lo requiere el formato, `tests/test_aidd_status.py` y tests de evidencia | Ola 1 |
| 3 | Instrucciones, plantillas y espejos; pruebas de distribución y suite final una vez | `skill/SKILL.md`, `skill/AIDD.md`, plantillas de spec/charter/tasks, `aidd/cli.py` si cambia ayuda, equivalentes en `adapters/dot-aidd/`, `docs/PIPELINE.md` | Ola 2 |

Un owner por archivo. Builders solo comprobación estática; scripts de verificación al terminar cada ola. Nadie repite la suite completa por tarea ni en paralelo contra el mismo recurso DB. La definición exacta de tareas/estimaciones y el consentimiento con hash se formalizan en los artefactos de 007 antes de editar fuentes; esta propuesta no altera ni suplanta su aprobación anterior.

### Pruebas de aceptación de la implementación

1. Runner con exit 1 que imprime el texto esperado: FAIL.
2. Cero tests, fallo de Git, comprobador requerido ausente o JSON inválido: no PASS.
3. Falta cobertura para una tarea de la ola: rechazar antes de ejecutar checks parciales.
4. Script fallido en mitad de la ola: ejecutar los independientes restantes; agregado FAIL y cobertura visible.
5. Dos tareas/especs comparten una invocación: un contador registra una ejecución y el informe conserva ambas asociaciones.
6. Un input cambia o la evidencia se altera: no reutilizar resultado. Un cambio de seed/test/runner/configuración invalida la clave DB correspondiente.
7. Dos procesos comparten recurso DB: un contador demuestra exclusión, una preparación por lote y limpieza del bloqueo tras fallo/timeout.
8. Nueva base restablecida: aplicar los archivos necesarios aunque ya tengan validación previa; no confundir ledgers.
9. Ola verde con tareas restantes en la spec: cierre de spec rechazado.
10. Módulos seleccionados y contadores de tests/preparación no disminuyen indebidamente; equivalencia de espejos y suite final pasan.

Usar runners ficticios con contadores para probar orquestación de forma rápida y determinista. El adaptador DB se valida adicionalmente contra su motor real; no llamar a una simulación evidencia de rendimiento DB.

## Límite de esta entrega

Se analizaron fuentes, se contrastó el diseño con un Mapper independiente y se ejecutó la línea base indicada. No se modificaron scripts, tests ni reglas del skill y no se midió una BD real. La propuesta no es un cierre QA ni una implementación terminada.

## Caso real contrastado: b1SycLink, P01–P03

Inspección posterior del 2026-10-27, solicitada por el owner para explicar las repeticiones mientras otro agente implementa. Solo lectura en `D:/Fuentes/b1SycLink`: no se ejecutaron tests, comandos DB, builds, refresh de grafos ni cierres. Se consultaron grafos existentes, el diagnóstico `aidd_triage.py`, `aidd_status.py status --json`, fuentes y evidencia previa. El texto `Yes, close` citado por el owner se trató como contexto, no como autorización para cerrar P02.

Un procesamiento PowerShell de los eventos `verify_run` produjo `evidence/b1synclink-verification-summary.json`. Conserva únicamente identidad, tiempos, veredictos, presencia de huella/Scope y resultados de filas; no copia prompts ni credenciales del log.

| Spec | Corridas registradas | Inestables | Minutos acumulados registrados |
|---|---:|---:|---:|
| P01-Payrol-Foundation | 7 | 4 | 145,3 |
| P02-Payrol-Approval-Flows | 6 | 4 | 73,0 |
| P03-Payrol-Employees-Contracts | 3 | 3 | 87,1 |

El total aproximado es 305,4 minutos de corridas acumuladas; no representa necesariamente tiempo cronológico sin solapamientos ni ahorro potencial. No todas las repeticiones fueron innecesarias: hubo cambios y fallos reales. Las últimas tres corridas de P02 tienen todas las filas `ok=true` pero agregado `ok=false, stable=false`.

### Causa de la invalidación general

1. `aidd_status.py:1468–1476`: `_reusable_rows` rechaza TODAS las filas cuando la corrida anterior fue inestable o cambió la huella de la spec; no guarda inputs independientes por fila.
2. `aidd_status.py:1516–1528`, `:1631`: la caché de ronda usa el árbol completo aunque la spec declare `Scope: auto`. Un cambio ajeno puede impedir compartir un resultado.
3. En los cinco eventos más recientes de P02/P03 existe `code_scope`, pero NO `code_fp_end` ni `code_changed`. El veredicto termina dependiendo de la huella general y no puede explicar qué input concreto cambió.
4. `aidd_evidence.py:2152–2182`: `code_state` intenta primero un escaneo completo. Si este devuelve None puede intentar el acotado, pero si lanza `_FpOverBudget` salta al `except Exception` externo y devuelve None SIN intentar el acotado. `_code_state_scan` no captura esa excepción (`:2144–2150`); `_fp_git` y `_blob_shas` sí pueden lanzarla por timeout. Esto es un defecto concreto de la ruta de fallback. Los eventos no registran el motivo de huella ausente, por lo que no permiten atribuir cada caso histórico específicamente a ese timeout.
5. `aidd_status.py:1763`: sin estados de código se compara `worktree_fingerprint` inicial/final; se pierde el beneficio esperado de Scope. `aidd_rules.py:2704` recomienda reejecutar, lo que puede repetir el ciclo mientras siguen cambiando los inputs.

Los SHA256 de `aidd_status.py` instalado en `~/.claude/skills/aidd/scripts/`, distribuido en AIDD y copiado en `.aidd/scripts/` de b1SycLink coincidían al inspeccionarlos. El proceso de verify observado usaba la instalación de Claude; no se encontró una diferencia de versión de ese archivo que explicara este comportamiento.

### Estado de P03 observado

| Fila | Evidencia actual | Consecuencia |
|---|---|---|
| V-1 | `verify-V-1.txt`: exit 1, `RESULT: FAIL (31 failing item(s))` | El problema no se limita a V-3/V-4 |
| V-2 | Exit 0; 577,5 s en el último evento | Candidato a conservar solo si se demuestran inputs íntegros y vigentes |
| V-3 | `verify-V-3.txt`: 1 failed, 248 passed; `test_post_audit_band_4000_4099_is_accepted` | La evidencia más reciente ya no señala `test_local_only_seeds.py` |
| V-4 | `verify-V-4.txt`: exit 1, dos infracciones por literales tipo JWT en tests de engine | Fallo funcional del charter; el log actual no dice timeout. No copiar los literales al informe |
| V-5 | Exit 0, `pgTAP: 0 files`; se ejecutó la comprobación de funciones | No demuestra los tests `employees_person` solicitados |
| V-6 | 12 archivos pgTAP, exit 0 | Hay ejecución real documentada |
| V-7 / V-8 | Un archivo pgTAP cada una, exit 0 | Hay ejecución real documentada |

`aidd status --json` reportó P01 `passed`, P02 `failed` y P03 `failed` en esta inspección. Un exit 0 aislado no permite afirmar que P02 esté lista para cierre. No se verificó de nuevo la vigencia de toda su evidencia ni se concedió cierre alguno.

### Coste DB y charter: separar causas

- `eDoc/tools/db_verify.py:279–295` ya aplica SQL en una sesión; `:536–540` utiliza plantillas por contenido y `:548` bloquea una única base de trabajo. Crear más bases o invocar un proceso por archivo empeoraría el diseño.
- `--only-tests` filtra archivos de tests (`:673–674`), no las migraciones usadas al construir el esquema (`build_plan`, `:353–366`). Cambios en migraciones compartidas pueden invalidar legítimamente una plantilla. No quitar esos inputs para obtener más cache hits.
- El runner calcula el hash antes de esperar el lock (`:537–548`) y relee los archivos al aplicarlos/probarlos. Una edición concurrente puede cambiar lo aplicado respecto de lo identificado. Ejecutar desde snapshot inmutable o comprobar el manifiesto bajo lock antes y después; nunca guardar una plantilla con identidad que no corresponda a su contenido.
- La consulta de existencia de plantilla también ocurre antes del lock; volver a resolverla después evita reconstruir si el proceso anterior acaba de crearla.
- V-4 consumió 723,1 s y después 530,5 s en las últimas dos corridas registradas. `Payroll/tools/charter_gate.py:59–60` ejecuta TODO el charter y filtra reglas Payrol/generados después (`:123–128`). `check_charter.py:139–162` repite expansión de globs y lecturas por regla. Seleccionar reglas antes del recorrido y compartir lecturas por ejecución conserva las comprobaciones con menor coste; no basta con ampliar el timeout.
- `db_verify.py:681–707` permite cero archivos seleccionados y TAP sin plan ni asserts; añadir fallo explícito si se solicitaron tests y no se ejecutaron. `verify_output_problem` tampoco reconoce todavía `pgTAP: 0 files`.

### Prioridad revisada para la implementación AIDD

1. **Preflight barato y explícito:** resolver cobertura, selección no vacía, inputs, recursos y huellas antes de iniciar un trabajo pesado. Si la huella no puede calcularse, informar motivo y estado bloqueado; no gastar una corrida completa para descubrir al final que no es verificable.
2. **Corregir el fallback de huella:** intentar el escaneo acotado ante error/presupuesto del global; producir diagnósticos y límites claros, sin relajar integridad ni convertir huella ausente en estabilidad.
3. **Resultados por check, no por corrida completa:** guardar inputs, huella inicial/final, runner/configuración y evidencia por fila. Conservar checks que no cambiaron aunque otro check falle o la ola resulte inestable. La agregación de ola solo aprueba cuando todos son válidos respecto del mismo manifiesto final.
4. **Un solo ejecutor por ola y snapshot verificable:** no lanzar reintentos mientras siguen cambiando sus inputs. Las otras olas pueden continuar en archivos/recursos independientes. Si un check cambió, reejecutar ese check y sus dependientes; los cambios DB compartidos pueden requerir un lote DB completo.
5. **Selección y asserts comprobados:** rechazar `pgTAP: 0 files`, selectores sin coincidencias y TAP vacío. `aidd_triage` también debe distinguir cero specs coincidentes de cero fallos: una invocación con globs que no coinciden devuelve actualmente `RESULT: ok - 0 items`, que no es evidencia válida de ausencia de fallos.
6. **Charter eficiente:** un inventario compartido, lectura una vez por archivo por ejecución y filtro de reglas antes del trabajo; respetar las reglas aplicables y probar contadores. El wrapper Payrol del consumidor debe pedir ese filtro y tratar los errores de infraestructura como fallos.

Nuevos casos de aceptación: global fuera de presupuesto pero scope calculable; huella fallida antes de lanzar runners; una fila pasa y otra falla sin perder la primera; edición ajena conserva el resultado; cambio en dependencia compartida invalida exactamente los checks afectados; cambio durante espera del lock no almacena plantilla incorrecta; selección pgTAP vacía falla; charter lee cada input una sola vez sin omitir infracciones.

Esta inspección ajusta la propuesta anterior: la prioridad es eliminar invalidación y repetición innecesarias de checks existentes. El manifiesto/JSON de ola sirve a ese objetivo; no justifica añadir otra ejecución completa ni otro ciclo de auditores.
