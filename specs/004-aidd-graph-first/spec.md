# 004 — AIDD Graph-First (fewer reads, fewer audit rounds)

Extends 002 (hard rules) and 003. Motivation, observed on a real run (Integraciones spec 001-pos-sap-sync, 2026-10-02):
a change of 24 tasks was audited 4 times before any code and again after it; each auditor re-read ~66 KB of spec, and
the agent itself dumped whole event logs and files to answer one question. `specs/index.toon` for that spec had an empty
`tree` because the graph only parses the mockup audit, and a backend-only spec has none.

- **Audit loop:** R5/R7/R8 re-require an auditor after ANY later edit (fixed in 003 follow-up: `audit_since`, tolerance).
- **Whole-file reads:** nothing steers agents to the graph or to filters (rule W1 is prose only).
- **Thin graph:** acceptance cases, FR rows, tasks, API codes from `contracts.md` and memory are not indexed.

## Minimum Requirements Checklist

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | AIDD skill: `skill/scripts/find_spec.py` (index + query), `skill/hooks/` (read nudge), `skill/SKILL.md`, `skill/AIDD.md`, adapters mirror | repo — skill/scripts/find_spec.py:453 | → Step 2 align question |
| New development or modification of something existing? | Modification: extend the spec graph indexer and add a query interface; add a non-blocking hook nudge | user — "Confirmar tal cual" | → Step 2 align question |
| Does it involve an external service, API, or integration? | No. Stdlib only, no LLM calls | repo — skill/scripts/find_spec.py:1 | → Step 2 align question |
| Who is requesting it? (role/profile, not necessarily the name) | Head of Systems, owner and only user of the skill | repo — specs/003-aidd-interaction-evidence/spec.md:1 | → Step 2 align question |
| Dependencies on other modules or active developments? | 002 rules engine (`aidd_rules`), 001 memory (`aidd mem`), `check_spec.py`. No other active work | repo — specs/003-aidd-interaction-evidence/spec.md:1 | → Step 2 align question |
| Business objective (1 sentence — what it achieves and why) | Cut time and iterations per change by letting agents query a richer graph instead of reading files | user — "Confirmar tal cual" | → Step 2 align question |
| Expected visual fidelity level (if there's a mockup): exact \| functional behavior only | No mockup: scripts, hooks and markdown only | repo — specs/003-aidd-interaction-evidence/spec.md:1 | → Step 2 align question |

## Pipeline route

| Step | Status | Reason | Confirmation |
|---|---|---|---|
| -1 | run | find_spec found 002 as nearest; distinct area, new spec 004 | repo — specs/003-aidd-interaction-evidence/spec.md:1 |
| 0 | waived | no visual surface | user — "Confirmar tal cual" |
| 1 | waived | no mockup | user — "Confirmar tal cual" |
| 1.5 | waived | no flows to draw | user — "Confirmar tal cual" |
| 2 | run | | |
| 3 | run | | |
| 4 | run | | |

## Visual debt

No `SCREEN-nn` codes appear in this spec's files; no debt.

## Scope

In: index more artifacts of each spec into `specs/index.toon`; query them with bounded output; steer agents to it.
Out: any LLM or embedding; reading source code into the graph; changing R1–R12 semantics; hard-blocking reads.

## Functional requirements

| FR-nnn | Requirement | Cites |
|---|---|---|
| FR-001 | The indexer parses `spec.md` `## Acceptance cases` (`AC-nnn`, real data, expected, edge flag) and `## Functional requirements` (`FR-nnn`) into graph nodes under the spec | AC-001 |
| FR-002 | The indexer parses `tasks.md` rows (`T-nn`, codes satisfied, target file, status) and links `T-nn → API/FR/AC/SCREEN/COMP/CTL codes` | AC-002 |
| FR-003 | The indexer parses `contracts.md` into `API-nnn` nodes (name, route or SP) even when the spec has no `mockup-audit.md` | AC-003 |
| FR-004 | The indexer links `.aidd/memory` entries to codes and files, reusing `memory_hits_for` | AC-004 |
| FR-005 | `find_spec.py --code <CODE>` prints that node, its neighbours and the file:line of each, in at most 25 lines | AC-001 |
| FR-006 | `find_spec.py --tree <spec-id>` shows the full chain use case, screen, component, control, API plus FR/AC/T for specs with or without a mockup | AC-003 |
| FR-007 | Incremental rebuild: only changed spec files are re-parsed (existing mtime cache); an unchanged index costs one stat per file | AC-005 |
| FR-008 | A non-blocking `PreToolUse Read` hint: when a whole `spec.md`/`plan.md`/`contracts.md`/`tasks.md`/`events.toon` is read with no `limit` and no graph query this session, print one line pointing to `find_spec.py --code` | AC-006 |
| FR-009 | Auditor prompt scope: `aidd-converge` and SKILL.md tell each auditor to start from `find_spec.py --code` per changed code plus `check_spec.py`, not from full files | AC-006 |
| FR-010 | Index format stays backward compatible: an old `index.toon` is detected by `version` and rebuilt, never misread | AC-005 |
| FR-011 | Amendment 2026-10-07 (owner: AIDD stays independent of third-party graph tools). `aidd progress` measures implementation per spec with no LLM and no third-party tool: for each task of `tasks.md` it resolves the `Target file` paths in the project (also by path suffix, for specs that write paths relative to a sub-folder) and classifies it `missing`, `stub` (< 40 bytes), `present` or `marked` (file carries `aidd:<code>` of the codes the task satisfies, or `aidd:T-nn`); a cell with no path (waves, prose) is `n/a` and counted apart. Per spec: `Impl%` = (present+marked)/measurable, `Mark%` = marked/measurable, `Decl%` = tasks whose Status cell says done (declared, not measured) | AC-007 |
| FR-012 | `aidd progress` adds the stages AIDD already records: approved, `aidd verify` result (none/passed/failed), closing-audit coverage (covered/required domains, `closed` once the spec is closed) and closed | AC-007 |
| FR-013 | The result is written to `.aidd/graphs/progress.json` (nodes `spec` and `T` with their state, edges `contains` and `targets`) and registered as the built-in graph `progress` (`refresh: builtin:progress`), so `aidd graphs show progress <spec or T>` answers without reading files | AC-008 |

## Acceptance cases

| Case | Real data (id) | Expected | Edge? |
|---|---|---|---|
| AC-001 | `C:\Proyectos\Integraciones\Integraciones\specs`, `--code API-003` | node API-003 with its tasks T-13 and FR links, ≤ 25 lines, no mockup needed | no |
| AC-002 | same spec, `--code T-16` | lists FR-005, FR-009, FR-010 and target `SBO.DAL/PosVentaSync.cs` | no |
| AC-003 | same spec, `--tree 001-pos-sap-sync` | non-empty tree (today it is empty) | no |
| AC-004 | `D:\Fuentes\AIDD`, a code with a memory entry | the entry id appears as a neighbour | no |
| AC-005 | edit one task row, rerun | only `tasks.md` re-parsed; a `version: 3` index is rebuilt once, not crashed on | yes |
| AC-006 | Read of `plan.md` (171 lines) with no `limit` | one-line hint, read not blocked; no hint when `limit` is set | yes |
| AC-007 | `D:\Fuentes\b1SycLink`, `aidd progress` | one table for every spec: F25 98,7 % (75 of 76, only the closing `qa-audit.md` missing), F27 (no `Target file` column) shown as `n/a` with its declared %, F28 `closed` | yes |
| AC-008 | same project, `aidd graphs show progress F25-eDoc-Approvals` | the spec node with `impl_pct`, stages and its tasks, no spec file read | no |

## Optional Align questions

| Question | Answer | Source |
|---|---|---|
| Which states must each screen/flow handle (empty, loading, error, offline)? | N/A | |
| Who may see or do this (permissions/roles)? | N/A | |
| Entry route: how does the user reach this from the app's start? | `find_spec.py` CLI and the `Read` hook | |
| Target devices (phone, tablet, desktop, orientation)? | N/A | |
| Contract owner and status (who defines the backend contract, is it final or still moving)? | N/A | |
