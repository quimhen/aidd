# AIDD 008: integración de la ronda consolidada

La fila V-1 ejecuta una sola discovery mediante el runner con manifiesto y conserva la unión de códigos de las anteriores V-1 a V-4. V-5 se mantiene sin cambios. Antes de editar se compararon mecánicamente los 43 códigos originales: ninguno falta en la unión nueva. La recopilación anterior en D: obtuvo 831 IDs con SHA-256 `74de8cc80120edcca2315e4a02a198495b7b0f4c76bb05cebff547c9a141bdc2`.

El checkout en Windows con `core.autocrlf=true` convirtió el manifiesto a CRLF y alteró su digest. Se fijó LF para ese archivo en `.gitattributes`. El formato de los IDs y la cobertura real deben volver a comprobarse en el entorno de cierre.

Validación focalizada en el clon de recuperación: 37 pruebas sintéticas aprobaron y `check_spec.py` no encontró brechas estructurales. No se ejecutó la nueva tabla de verificación. La prueba de recopilación completa no pudo terminar porque el volumen D: que contiene las fixtures de b1SycLink estaba bloqueado por BitLocker. Las ejecuciones históricas y el sello anterior no se modificaron; la nueva tabla necesita verificación y auditoría. La igualdad de IDs tampoco prueba por sí sola equivalencia del aislamiento entre procesos; revisar ese riesgo antes de dar el cierre por aprobado.

Después de desbloquear D:, `python tests/coverage_manifest.py --check` terminó con código 0 y confirmó los 831 IDs y el digest. La detección del checkout real de las pruebas ahora trata un `OSError` de volumen inaccesible como fuente no disponible, con skip explícito, en vez de abortar la colección; un caso simulado de volumen bloqueado comprobó esa ruta. El runner estricto sigue sin contar skips obligatorios como PASS.
