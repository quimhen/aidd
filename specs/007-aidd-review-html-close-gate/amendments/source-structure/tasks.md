# Tasks — Detect source stubs/duplicate definitions and report structural warnings

Pending official unit approval. No legacy approval is replaced.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-901 | FR-970, FR-971, FR-972, FR-973, FR-974, FR-975 | `tests/test_aidd_source_shape.py`, `skill/scripts/aidd_source_shape.py` | LOGIC | | | unrelated source, gates, DB, network, installed skill |
| T-902 | FR-970, FR-971, FR-972, FR-973, FR-974, FR-975 | `skill/scripts/aidd_source_shape.py` | LOGIC | | | unrelated source, gates, DB, network, installed skill |
| T-903 | FR-970, FR-971, FR-972, FR-973, FR-974, FR-975 | `skill/scripts/aidd_progress.py`, `tests/test_aidd_progress.py` | LOGIC | | | unrelated source, gates, DB, network, installed skill |
| T-904 | FR-970, FR-971, FR-972, FR-973, FR-974, FR-975 | `adapters/dot-aidd/scripts/aidd_source_shape.py`, `adapters/dot-aidd/scripts/aidd_progress.py`, `docs/aidd-source-shape.md` | LOGIC | | | unrelated source, gates, DB, network, installed skill |

### T-901

**Classify**
- Nature: REQUIREMENT
- Priority: 2
- Kind: LOGIC

**Estimate**
- Agent min: 8
- Human ref hours: 0.40
- Tokens (est): 15k
- Agent role: tests
- Model tier: medium
- Wave: 1

**Detail**
- Files to change: `tests/test_aidd_source_shape.py`, `skill/scripts/aidd_source_shape.py`
- Behaviour: First declare only inspect_python(path:Path)->dict and inspect_targets(paths:list[Path])->list[dict] interfaces in skill/scripts/aidd_source_shape.py; their bodies must raise NotImplementedError, with no implementation. This explicit scaffold is permitted by this task before RED. Then create TemporaryDirectory tests for direct same-scope duplicate definitions, final NotImplementedError overwriting a real body, long stubs, docstring-only stub, same method in distinct classes, @overload followed by implementation, abstract/Protocol/property declarations, conditional branches, syntax/unreadable unknown, and no importing inspected files. Assert both duplicate line numbers. CLI tests invoke the declared module but cannot treat import/collection errors as RED. Coordinator captures actual NotImplementedError/assertion RED before T-902; same file owner as T-902.
- Read first: unit plan.md, target functions resolved through native graph, and existing import/test fixture style. Do not widen unrelated reads.
- Verification: coordinator runs the applicable commands in unit spec.md once after freeze; a new behavior first requires genuine RED before the body. Builders only static checks.
- Do NOT: edit any file not named; modify approvals/events; execute DB or external services; hide failures or label AST success as runtime proof.
- Open questions: none.

### T-902

**Classify**
- Nature: REQUIREMENT
- Priority: 2
- Kind: LOGIC

**Estimate**
- Agent min: 12
- Human ref hours: 0.60
- Tokens (est): 25k
- Agent role: builder
- Model tier: medium
- Wave: 2

**Detail**
- Files to change: `skill/scripts/aidd_source_shape.py`
- Behaviour: Same owner as T-901. Replace the explicitly declared interfaces only after coordinator captures genuine semantic RED. Implement inspect_python(Path)->dict and inspect_targets(list[Path])->list[dict] exactly as plan.md. Parse AST without importing source. Distinguish executable stubs, declarations and direct lexical duplicate names; never parse Python with regex. CLI --files <paths...> --json; exit0 clean/declarations,1 executable stub/duplicate,2 unreadable/syntax/usage. No automatic tree scan. Depends T-901 RED.
- Read first: unit plan.md, target functions resolved through native graph, and existing import/test fixture style. Do not widen unrelated reads.
- Verification: coordinator runs the applicable commands in unit spec.md once after freeze; a new behavior first requires genuine RED before the body. Builders only static checks.
- Do NOT: edit any file not named; modify approvals/events; execute DB or external services; hide failures or label AST success as runtime proof.
- Open questions: none.

### T-903

**Classify**
- Nature: REQUIREMENT
- Priority: 2
- Kind: LOGIC

**Estimate**
- Agent min: 10
- Human ref hours: 0.50
- Tokens (est): 20k
- Agent role: builder
- Model tier: medium
- Wave: 3

**Detail**
- Files to change: `skill/scripts/aidd_progress.py`, `tests/test_aidd_progress.py`
- Behaviour: Add source_structure warnings for explicit Python Targets and detailed rendering with symbol/line. Tests first: preserve all task_state outputs, aliases/delete behavior, impl_pct and default columns. A clean AST is not functional PASS. --detail displays findings; final note distinguishes file presence from executed validation. Do NOT create verify events or mark tasks done. Same owner for both files. Depends T-902.
- Read first: unit plan.md, target functions resolved through native graph, and existing import/test fixture style. Do not widen unrelated reads.
- Verification: coordinator runs the applicable commands in unit spec.md once after freeze; a new behavior first requires genuine RED before the body. Builders only static checks.
- Do NOT: edit any file not named; modify approvals/events; execute DB or external services; hide failures or label AST success as runtime proof.
- Open questions: none.

### T-904

**Classify**
- Nature: REQUIREMENT
- Priority: 2
- Kind: LOGIC

**Estimate**
- Agent min: 5
- Human ref hours: 0.25
- Tokens (est): 10k
- Agent role: docs
- Model tier: medium
- Wave: 4

**Detail**
- Files to change: `adapters/dot-aidd/scripts/aidd_source_shape.py`, `adapters/dot-aidd/scripts/aidd_progress.py`, `docs/aidd-source-shape.md`
- Behaviour: Use the repo mirror tool after aidd tools mirror; dry-run/apply/post-check, exact byte copies. Document target-only usage and detection limits. Do NOT touch SKILL.md or installed copies; docs page is this unit sole documentation target. Coordinator runs mirror check once shared with the other units. Depends T-902/T-903.
- Read first: unit plan.md, target functions resolved through native graph, and existing import/test fixture style. Do not widen unrelated reads.
- Verification: coordinator runs the applicable commands in unit spec.md once after freeze; a new behavior first requires genuine RED before the body. Builders only static checks.
- Do NOT: edit any file not named; modify approvals/events; execute DB or external services; hide failures or label AST success as runtime proof.
- Open questions: none.

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-901 | tests | 8 | 15 | 0.40 |
| 2 | T-902 | builder | 12 | 25 | 0.60 |
| 3 | T-903 | builder | 10 | 20 | 0.50 |
| 4 | T-904 | docs | 5 | 10 | 0.25 |

Total agent time (critical path): 35 min
Total tokens (k): 70

## Execution contract

One file owner per lane. Native AIDD graphs first, bounded reads and outputs. Mechanical operations use mapping/dry-run/apply/post-check. Builders run static checks only; coordinator executes RED before each body, then the union of checks once after source freeze. Preserve failures and exact inputs; no invented PASS or consent. No Graphify, database, Docker, external API, installed-skill update or B1SyncLink write. Do NOT modify approval/event logs, relax gates, change unrelated local edits, reinterpret presence as behavior, or reuse a DB result from container identity alone. Final full verification and required perf/audit of the host spec remain applicable at official close.

## Approval gate

Pending owner consent through the official unit review package. This file is not an approval. Historical base approval remains independent and unchanged. No production implementation before the exact unit is approved.
