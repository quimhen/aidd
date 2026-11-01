# AIDD: avance de unidades y verificación — 2026-11-01

- La revisión de una unidad incluye sus archivos de tareas y una identidad del checkout en el paquete canónico. Se añadieron selección de unidad por objetivo y una ruta de registro basada en respuestas de hooks existentes. La auditoría encontró que el registrador actual recorta preguntas a 1000 caracteres: no se ha demostrado una aprobación real de una unidad larga ni el consentimiento de Codex. La ruta no está conectada al gate.
- La selección por ruta no demuestra identidad de hardlinks con otro nombre. No usarla como control de escritura hasta cubrir ese caso. Conservar el gate legado.
- `aidd_reuse.py` planifica compartir solo si hay un verificador externo de aislamiento; no está conectado al verificador productivo ni produce ahorro medido.
- `codex_patch.py` extrae rutas y proyecta un subconjunto estricto de parches. No está conectado al gate: la reconstrucción no cubre todos los formatos y la identidad puede cambiar entre comprobar y escribir.
- Comprobación focalizada posterior a estos cambios: 51 pruebas y espejo de archivos, código 0. No constituye verificación de cierre, auditoría de dominio registrada ni prueba de matriz CI.
