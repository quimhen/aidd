# DRAFT — plan de conciliación Linux

Estado: sin aprobación. La enmienda complementa 009 T-19 y 010 T-05/T-06; no autoriza editar el guard de producción ni cambiar las reglas R6/R9.

## Contrato y archivos

La única modificación propuesta es `tests/test_rule_gate.py`, en los tres métodos señalados en las tareas. Windows conserva sus aserciones. Linux verifica separadamente los archivos protegidos reales y los nombres distintos por mayúsculas; el caso `.AIDD` continúa bajo R6. El test de rendimiento conserva método y umbral: en una copia efímera en almacenamiento nativo Linux pasó en 62 ms, frente a 579 ms en el montaje Windows.

## Dependencias y oleadas

Tras el sello de la versión final, una oleada modifica las tres pruebas. La evidencia roja son los fallos ya obtenidos; no hay que volver a ejecutarlos antes de empezar. El verificador ejecuta los tres casos modificados en Windows y Linux, y después coordina una sola ronda del guard, equivalencia y espejo en cada entorno disponible. En Linux usa almacenamiento nativo para la comparación de tiempo y documenta el entorno. La verificación no elimina casos ni oculta skips.

## Barreras y riesgos

Un auditor independiente revisa diferencias por plataforma y confirma que R6/R9 y los 300 casos de equivalencia permanecen cubiertos. Si una expectativa no coincide con el guard y la especificación aprobada, detener la modificación y documentar el caso; no ampliar silenciosamente una excepción ni modificar código de producción. No declarar una plataforma verde sin resultado real.
