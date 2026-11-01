# Instalación local AIDD — 2026-11-01

Se aplicó el plan transaccional `aidd-release-final-20261101e` a dos perfiles de skill, el adaptador del proyecto b1SycLink, el paquete CLI de Python 3.12 y la configuración de hooks de Codex. El journal y respaldos están en `%TEMP%/aidd-release-final-20261101e/journal`. No se modificó la confianza de hooks de Codex.

La primera transacción detectó una diferencia de herencia de ACL en Windows y se detuvo. Su journal quedó en `rolled_back`; se cotejaron los hashes originales de los 89 destinos y se restauró el descriptor del único archivo afectado. Tras probar una corrección específica en un directorio aislado, una nueva transacción actualizó 89 archivos y terminó con código 0.

Comprobaciones posteriores con el ejecutable real de PATH: `aidd runtime` informó Python 3.12 y el CLI instalado en `site-packages`; `aidd navigator` generó un HTML; `aidd impact specs/P13-Payrol-Commissions --task T-163 --changed --base b6ff5002 --json` identificó la fixture modificada y los dos targets de la tarea, con línea base provisional y auditoría indeterminada. Un ID inexistente en `aidd verify ... --tasks` fue rechazado sin ejecutar comandos. Las tres instalaciones de SKILL pasaron el validador de formato.

La ronda de integración ejecutó 153 pruebas: una omitida y una falla de paridad de espejo; tras sincronizar la copia, la comprobación afectada pasó por separado. Otras pruebas puntuales posteriores cubren la fusión de perfil y la recuperación de ACL. No se ejecutó una suite completa de cierre ni la matriz CI.

Límites: el reuso automático de filas arbitrarias está deshabilitado hasta acreditar entorno e aislamiento; `verify --tasks` produce evidencia parcial. Los recibos de auditoría por unidad no se consideran vigentes sin procedencia comprobable. Los hooks Codex nuevos requieren confianza explícita del host. Se corrigió la ayuda `aidd verify --help` para explicar la selección parcial. No se declara AIDD completo ni se cierran specs por esta instalación.

Se efectuó un despacho real mínimo de subagente (`hook_smoke`, respuesta `OK`) después de actualizar `mark_agent_dispatch.py`; la consulta al registro AIDD del proyecto no mostró un evento nuevo atribuible a ese despacho. No se infiere que la integración de esta superficie con `PostToolUse` esté operativa. La relación entre encargo, subagente y auditoría sigue indeterminada hasta que el host entregue y registre sus eventos reales.

## Actualización posterior sin requisito de hooks

El usuario autorizó prescindir de hooks de Codex. El commit `94e572a` instala una ruta alternativa: una revisión real e independiente de Codex en solo lectura produce recibos por unidad; una prueba en un repositorio sintético comprobó el registro y el reconocimiento de dos dominios. También habilita aprobación visual opcional de unidades y reuso de verificaciones Python bajo un contrato offline explícito; el contrato declara dependencias y no demuestra aislamiento. Las verificaciones parciales no cierran una spec; las ejecuciones `--changed` y `--tasks` no comparten caché de ronda. La línea base histórica sin evidencia suficiente sigue indeterminada.

Se aplicó el plan `%TEMP%/aidd-release-nohooks-20261101/release-plans.json`: 39 archivos seleccionados en ambos perfiles y el adaptador del proyecto, conservando personalizaciones. No se cambió la confianza de hooks. `aidd runtime` y la ayuda de `verify` se comprobaron con el ejecutable instalado; los perfiles pasaron validación de SKILL. Las pruebas focalizadas pasaron en Windows y la vista auxiliar se capturó sin otorgar una aprobación. El visor completo y la matriz Linux aún requieren la verificación que corresponda; esta actualización no certifica el cierre de todos los puntos del plan.
