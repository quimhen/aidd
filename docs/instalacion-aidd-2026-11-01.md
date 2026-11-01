# Instalación local AIDD — 2026-11-01

Se aplicó el plan transaccional `aidd-release-final-20261101e` a dos perfiles de skill, el adaptador del proyecto b1SycLink, el paquete CLI de Python 3.12 y la configuración de hooks de Codex. El journal y respaldos están en `%TEMP%/aidd-release-final-20261101e/journal`. No se modificó la confianza de hooks de Codex.

La primera transacción detectó una diferencia de herencia de ACL en Windows y se detuvo. Su journal quedó en `rolled_back`; se cotejaron los hashes originales de los 89 destinos y se restauró el descriptor del único archivo afectado. Tras probar una corrección específica en un directorio aislado, una nueva transacción actualizó 89 archivos y terminó con código 0.

Comprobaciones posteriores con el ejecutable real de PATH: `aidd runtime` informó Python 3.12 y el CLI instalado en `site-packages`; `aidd navigator` generó un HTML; `aidd impact specs/P13-Payrol-Commissions --task T-163 --changed --base b6ff5002 --json` identificó la fixture modificada y los dos targets de la tarea, con línea base provisional y auditoría indeterminada. Un ID inexistente en `aidd verify ... --tasks` fue rechazado sin ejecutar comandos. Las tres instalaciones de SKILL pasaron el validador de formato.

La ronda de integración ejecutó 153 pruebas: una omitida y una falla de paridad de espejo; tras sincronizar la copia, la comprobación afectada pasó por separado. Otras pruebas puntuales posteriores cubren la fusión de perfil y la recuperación de ACL. No se ejecutó una suite completa de cierre ni la matriz CI.

Límites: el reuso automático de filas arbitrarias está deshabilitado hasta acreditar entorno e aislamiento; `verify --tasks` produce evidencia parcial. Los recibos de auditoría por unidad no se consideran vigentes sin procedencia comprobable. Los hooks Codex nuevos requieren confianza explícita del host. `aidd verify --help` actualmente trata `--help` como ruta y debe corregirse. No se declara AIDD completo ni se cierran specs por esta instalación.
