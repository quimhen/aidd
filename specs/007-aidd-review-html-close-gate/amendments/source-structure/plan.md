# Plan — Detect source stubs/duplicate definitions and report structural warnings

## Naming & File Contract

| Item | Convention |
|---|---|
| Functions and files | snake_case Python; preserve public ABI |
| Types/classes | PascalCase; no production class required |
| Target ownership | One lane per file; mirrors generated, not hand edited |

## Entry route

CLI input → existing parser → targeted read-only operation → bounded explicit verdict. Offline failures never fabricate PASS, consent or freshness.

## Exact implementation contract


- Archivos nuevos: `skill/scripts/aidd_source_shape.py`, `tests/test_aidd_source_shape.py`.
- Extensión: `skill/scripts/aidd_progress.py`, `tests/test_aidd_progress.py` (hay cambios preexistentes ajenos en el checkout; comparar antes de editar).
- Mirrors oficiales, después de cuerpos: `adapters/dot-aidd/scripts/aidd_source_shape.py`, `adapters/dot-aidd/scripts/aidd_progress.py` por herramienta de mirror del repo; no editar dos veces.
- Python snake_case para funciones/archivo. No clases de producción necesarias; diccionarios tipados por contrato estable.
- `inspect_python(path: Path) -> dict` devuelve `{"path": str, "status": "clean"|"findings"|"unknown", "findings": [{"kind": "duplicate_definition"|"stub"|"declaration"|"parse_error"|"unreadable", "symbol": str, "line": int, "previous_line": int|null}]}`.
- `inspect_targets(paths: list[Path]) -> list[dict]` preserva orden de entrada y nunca interpreta shell/globs ni importa el proyecto. Otro lenguaje se informa como no inspeccionado, sin aparentar cobertura.
- CLI inicial standalone: `python skill/scripts/aidd_source_shape.py --files <paths...> --json`. Exit0 sólo sin problemas ejecutables; exit1 stubs/duplicados; exit2 parse/lectura/uso inválido. Declaraciones solas no hacen fallar. Sin flags que desactiven gates.
- El resultado no afirma semántica correcta, alcance legal ni disponibilidad externa. La integración funcional sigue requiriendo ejecutar la ruta completa y sus pruebas.


## Execution contract

One file owner per lane. Native AIDD graphs first, bounded reads and outputs. Mechanical operations use mapping/dry-run/apply/post-check. Builders run static checks only; coordinator executes RED before each body, then the union of checks once after source freeze. Preserve failures and exact inputs; no invented PASS or consent. No Graphify, database, Docker, external API, installed-skill update or B1SyncLink write. Do NOT modify approval/event logs, relax gates, change unrelated local edits, reinterpret presence as behavior, or reuse a DB result from container identity alone. Final full verification and required perf/audit of the host spec remain applicable at official close.

## Approval gate

Pending owner consent through the official unit review package. This file is not an approval. Historical base approval remains independent and unchanged. No production implementation before the exact unit is approved.
