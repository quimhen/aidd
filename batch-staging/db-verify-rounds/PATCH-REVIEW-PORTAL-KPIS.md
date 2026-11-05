# PATCH-REVIEW-PORTAL-KPIS

Diff unificado contra HEAD (3521742 y posteriores al exportar): `PATCH-REVIEW-PORTAL-KPIS.diff`.
Hecho sobre una copia limpia (`git archive HEAD`); el arbol de trabajo de AIDD no se tocó.

## Archivos (6)
- `skill/templates/review.html` y espejo `adapters/dot-aidd/templates/review.html` (byte a byte)
- `skill/scripts/aidd_review.py` y espejo `adapters/dot-aidd/scripts/aidd_review.py` (byte a byte)
- `tests/test_review_template.py` (TestKpiHonesty + TestPortalBrowser con Playwright)
- `tests/test_aidd_review.py` (TestKpisFakes, TestKpisReal)

## Cómo aplicarlo
Desde la raíz de AIDD, con esos 6 archivos SIN otros cambios sin commitear (si los hay, aplicar en un
worktree/copia o mezclar a mano):

    git apply --check --whitespace=nowarn batch-staging/db-verify-rounds/PATCH-REVIEW-PORTAL-KPIS.diff
    git apply --whitespace=nowarn batch-staging/db-verify-rounds/PATCH-REVIEW-PORTAL-KPIS.diff

(Los archivos .py y las pruebas usan CRLF en el repo; el diff los conserva. Verificado: `git apply --check`
limpio sobre el export de HEAD.) Luego correr las pruebas de abajo.

## Qué cambia
1. KPIs: el generador calcula `data.kpis` (`_kpis` en `aidd_review.py`) y la plantilla solo los pinta; los
   marcadores de la plantilla son "—".
   - Esfuerzo: `summary.minutes` / `tokens_k` = `aidd_rules.plan_totals(tasks.md)` (campo "Total agent time
     (critical path)" o suma de la tabla Waves); si falta: "sin estimar".
   - Tareas: cuenta de códigos `T-*` de la página; olas = `aidd_review_items.wave_count` (filas de `## Waves`);
     sin tabla: "sin tabla Waves". Se retiró "DAG READY / 100% Cobertura" (no se medía).
   - Pantallas: cuenta de `SCREEN-*`; "Deuda visual abierta: N" = filas con Status=open de `## Visual debt` en
     spec.md (`_visual_debt_open_count`); sin sección: "sin tabla Visual debt". Se retiró "Executive Precision".
   - Verificaciones: cuenta de `V-*`; sub = resultado real de `check_verification` ("N problemas de lint ...").
     Se retiró "R1-R6 PASS / Zero-Regression" (no existía medición).
   - Franja inferior del mockup: se retiró "1440x900 / Executive Precision / 0 Desalineados"; ahora muestra
     pantalla activa y zoom.
2. Zoom (CTL-REV-009): botones −, `100%` (reinicio), + (50%..300%, pasos de 25) en la barra de viewport.
3. Desbordamiento a 375 px: `.kpi-row` pasa a `auto-fit minmax(min(100%,150px),1fr)`, `.kpi-card/.kpi-val/.kpi-sub`
   con `min-width:0` y wrap; medido 0 px a 375, 768 y 1440 (Playwright, página generada de una copia temporal).
4. "8 repeated codes skipped (first row wins)" en F39: el aviso es CORRECTO (no hay filas perdidas por error), pero
   el origen es ruido del extractor: en `mockup-audit.md` de F39 la tabla de interacciones tiene filas cuya
   primera celda es "SCREEN-144 CTL-39002", "SCREEN-146 header", etc. (4 de SCREEN-144 + 4 de SCREEN-146 = 8); el
   extractor toma el primer token como código de pantalla y descarta esas filas por repetidas (gana la fila del
   inventario de pantallas, que es la correcta). No cambia ningún ítem ni decisión; es un aviso informativo que
   puede silenciarse en un cambio aparte (ignorar en la pestaña de Pantallas las filas cuya primera celda
   contenga además un código CTL/COMP). No se tocó aquí.

## Resultados
Comando: `python -m unittest tests.test_dot_aidd_mirror tests.test_review_template tests.test_aidd_review
tests.test_visual_review_binding tests.test_aidd_review_items tests.test_aidd_review_state tests.test_cli_rules`
- Antes (HEAD): 263 pruebas, OK.
- RED (pruebas nuevas sin implementación): 6 fallos + 8 errores en las 14 pruebas nuevas.
- Después: 277 pruebas, OK (263 + 14 nuevas; incluye `test_dot_aidd_mirror`).
Las pruebas de navegador se saltan solas si falta node o Playwright (`AIDD_PLAYWRIGHT_DIR`, por defecto
`D:\Fuentes\b1SycLink\eDoc\web\node_modules\playwright`).
