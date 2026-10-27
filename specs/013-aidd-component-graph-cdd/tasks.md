# Tasks — 013 AIDD Semantic Component Graph (builtin:ui) & Mechanical CDD Gates

Approved: 2026-10-27 hash:04b1232a7eca

One row = one small PR. Estimates are agent wall time and tokens; the Human ref is derived.

Every task's implementation prompt restates these standards explicitly:
- **Scope: in and out, both stated explicitly.** In scope = exactly the codes and target file named by the row.
- **Physical Paths**: Every component node must carry its exact relative physical path.
- **SOLID and Antifragile**: All parsers fail soft with warnings, never crash.
- **Stdlib only**: No third-party packages, zero LLM calls in scripts.
- **Mirror parity**: Mirrored files in `adapters/dot-aidd/` must remain byte-identical.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-01 | FR-1301, FR-1302 | skill/scripts/component_graph.py | LOGIC | | closed | any other file; AST compilers |
| T-02 | FR-1303 | skill/scripts/aidd_graphs.py | LOGIC | | closed | modifying builtin:code or builtin:sql |
| T-03 | FR-1304 | aidd/cli.py | LOGIC | | closed | modifying unrelated subcommands |
| T-04 | FR-1305, FR-1306 | skill/scripts/check_spec.py | LOGIC | | closed | modifying existing rules G1-G6 |
| T-05 | FR-1307 | adapters/dot-aidd/scripts/component_graph.py | LOGIC | | closed | editing script contents directly; companions T-02 and T-04 |
| T-06 | FR-1301, FR-1302, FR-1303, FR-1304, FR-1305, FR-1306 | tests/test_component_graph.py | LOGIC | | closed | any other file |
| T-07 | FR-1307 | tests/test_dot_aidd_mirror.py | LOGIC | | closed | any other test file |

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| Wave 1 | T-01, T-04 | builder | 8 | 90 | 0.8 |
| Wave 2 | T-02, T-03, T-05 | builder | 5 | 80 | 0.7 |
| Wave 3 | T-06, T-07 | tests | 8 | 70 | 0.6 |

Total agent time (critical path): 21 min
Total tokens (k): 240

## Per-task detail

### T-01
**Classify**
- Nature: `FEATURE`
- Priority: 1 HIGH
- Kind: LOGIC

**Estimate**
- Agent min: 8
- Human ref hours: 0.8
- Tokens (est): 45k
- Agent role: builder
- Model tier: medium

**Target**
- File: `skill/scripts/component_graph.py`
- Codes: `FR-1301, FR-1302`

### T-02
**Classify**
- Nature: `FEATURE`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Agent min: 5
- Human ref hours: 0.5
- Tokens (est): 25k
- Agent role: builder
- Model tier: medium

**Target**
- File: `skill/scripts/aidd_graphs.py`
- Codes: `FR-1303`

### T-03
**Classify**
- Nature: `FEATURE`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Agent min: 5
- Human ref hours: 0.5
- Tokens (est): 30k
- Agent role: builder
- Model tier: medium

**Target**
- File: `aidd/cli.py`
- Codes: `FR-1304`

### T-04
**Classify**
- Nature: `FEATURE`
- Priority: 1 HIGH
- Kind: LOGIC

**Estimate**
- Agent min: 8
- Human ref hours: 0.8
- Tokens (est): 45k
- Agent role: builder
- Model tier: medium

**Target**
- File: `skill/scripts/check_spec.py`
- Codes: `FR-1305, FR-1306`

### T-05
**Classify**
- Nature: `FEATURE`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Agent min: 4
- Human ref hours: 0.4
- Tokens (est): 25k
- Agent role: builder
- Model tier: medium

**Target**
- File: `adapters/dot-aidd/scripts/component_graph.py`
- Codes: `FR-1307`

### T-06
**Classify**
- Nature: `TESTS`
- Priority: 1 HIGH
- Kind: LOGIC

**Estimate**
- Agent min: 8
- Human ref hours: 0.8
- Tokens (est): 45k
- Agent role: tests
- Model tier: medium

**Target**
- File: `tests/test_component_graph.py`
- Codes: `FR-1301, FR-1302, FR-1303, FR-1304, FR-1305, FR-1306`

### T-07
**Classify**
- Nature: `TESTS`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Agent min: 4
- Human ref hours: 0.4
- Tokens (est): 25k
- Agent role: tests
- Model tier: medium

**Target**
- File: `tests/test_dot_aidd_mirror.py`
- Codes: `FR-1307`
