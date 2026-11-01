# DRAFT — conciliación de pruebas históricas Linux

Estado: borrador, sin aprobación ni autorización de implementación. Fuente: la ronda registrada en `../010-aidd-shell-guard-speed/evidence/amendment-portable-partial-2026-11-01.md`.

## Alcance propuesto

Las pruebas históricas del guard deben seguir ejecutándose tanto en Windows como en Linux, con expectativas que reflejen la semántica nativa del sistema de archivos. En Linux, las variantes de mayúsculas que no representan el mismo archivo no deben tratarse como alias Windows; las rutas protegidas reales y los enlaces que apunten a ellas siguen bloqueados. En Windows se conservan las comprobaciones de alias y rutas protegidas existentes.

La medición de rendimiento ya pasó de forma focal en almacenamiento local Linux (mediana 62 ms para el archivo irrelevante, frente a 579 ms en la ronda sobre el montaje Windows). Esta evidencia apunta al entorno; no se autoriza aumentar umbrales ni eliminar aserciones. La ronda de CI debe ejecutarse en su almacenamiento nativo y registrar su resultado real.

Cuatro pruebas fallaron en la ronda Linux: `test_plan_md_spellings_are_all_gated`, `test_tasks_spec_and_qa_spellings_are_all_gated`, `test_bypass_case_backslash_dotdot_and_relative` y `test_timing_irrelevant_file_spec_file_and_bash`. Dos pruebas fueron omitidas por depender de funciones de Windows. Los 291 casos y los motivos de omisión deben permanecer identificables; no se autoriza ocultar fallos o skips.

## Validación prevista

Primero registrar la causa específica de cada caso y contrastar decisiones con la evidencia T-23 y el guard fijado. Después de la aprobación de tareas, ejecutar únicamente las pruebas modificadas y una ronda coordinada por entorno que incluya la equivalencia de 300 comandos y los módulos afectados. No declarar verde un entorno no ejecutado ni repetir verificaciones sin cambios relevantes.
