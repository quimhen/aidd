# Propuesta: verificación de base de datos por rondas y lotes (borrador)

Estado: ADOPTADO el 2026-11-04 en `specs/007-aidd-review-html-close-gate/amendment-08-verification-economy-and-fidelity.md` (E8(e) en `skill/AIDD.md` y `skill/SKILL.md`, espejo `adapters/dot-aidd/AIDD.md`); se conserva como evidencia. Texto original: borrador para adopción. Origen: proyecto b1SycLink, medición del
2026-11-04 (`specs/F38-eDoc-Import-Costing/evidence/verify-V-2.txt` y logs de la jornada).

## Problema medido

Todas las bases de trabajo viven en un solo contenedor Postgres (3,8 GB de RAM). La fila completa de db_verify
(478 archivos pgTAP) tarda 413 s sola, más de 600 s con corridas simultáneas (el timeout por defecto de
`aidd verify`, configurable con `AIDD_VERIFY_TIMEOUT`) y 890 s con 3 agentes activos. Las bases por slot aíslan
datos, no recursos.

## Metodología (texto listo para adoptar)

1. **Una sola corrida completa a la vez**, en un único spec designado por ronda. Los demás specs usan la forma
   estrecha (`--only-tests <prefijo>`) con su propio `--slot N`.
2. **Agrupar en una invocación, no una por test.** Hoy `--only-tests` acepta UNA sola subcadena (filtro
   `subcadena in nombre_de_archivo`, sin lista ni regex): agrupar significa elegir un prefijo común.
   `--skip-tests` acepta lista de nombres exactos. **Experimental:** `--tap --runner psql --tap-batch-allowlist`
   agrupa archivos permitidos en un proceso psql; paridad comparada solo en 12 archivos, sin ahorro medido.
3. **Pruebas dependientes del orden/estado:** detectarlas comparando resultado solo vs. en la suite y corregirlas
   (ej. `foundation_lookup_plans` pasa sola y falla en la suite por el plan EXPLAIN).
4. **Medir antes de optimizar;** no afirmar ahorros sin medición con mismo contenido, selección y base libre.
5. **Timeout:** subir `AIDD_VERIFY_TIMEOUT` solo para filas completas; costo: una fila lenta retiene el candado
   de su base hasta agotar el timeout.
6. **Slots por agente:** 1, 2, 3 para agentes distintos; la base por defecto, para `aidd verify`.

Documentación local ya escrita: `docs/RULE-ONE-TEST-DB.md`, sección "Metodología: verificación de base de datos
por rondas y lotes", en b1SycLink.

## Puntos de adopción sugeridos (a decidir por el mantenedor de AIDD)

- `aidd/AIDD.md`, sección de verificación (Step 6 / ejecución de filas `aidd verify`): regla de ronda con un spec
  designado para filas pesadas (complementa la política de reuso ya existente de AGENTS.md).
- Plantilla de AGENTS.md del proyecto (`templates/`): párrafo "Up to N work databases" con el enlace a la metodología.
- Ayuda de `aidd verify`: mencionar `AIDD_VERIFY_TIMEOUT` y su uso solo para filas completas.
- Mejora de herramienta (candidata, no implementada): que `db_verify.py --only-tests` acepte varias subcadenas, y
  que `aidd verify` detecte filas completas concurrentes y las serialice.

## Falta medir

- Tiempo de la forma estrecha con 2 y 3 slots simultáneos.
- Costo de reconexión en `--tap-batch-allowlist` frente a un proceso por archivo; ahorro real del modo agrupado
  en una lista mayor que los 12 archivos de empleados.
- Si conviene serializar también las corridas estrechas mientras hay una completa en curso.
- Relación entre RAM del contenedor y número de corridas simultáneas tolerables (solo se midió con 3,8 GB).
