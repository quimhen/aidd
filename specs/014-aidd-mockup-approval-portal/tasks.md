# Tasks — 014 AIDD Mockup-First Spec Approval & Visual Verification Portal

One row = one small PR. Estimates are agent wall time and tokens; the Human ref is derived.

Every task's implementation prompt restates these standards explicitly:
- **Scope: in and out, both stated explicitly.** In scope = exactly the codes and target file named by the row.
- **Strict CSP Compliance**: No external resources, no eval, script sha256 substituted into meta tag.
- **Contract Markers Invariance**: Preserve all existing DOM IDs and pure export functions tested by `test_review_template.py`.
- **Mirror Parity**: `adapters/dot-aidd/templates/review.html` must remain byte-identical to `skill/templates/review.html`.
- **Stdlib Only**: No third-party Python packages.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-01 | FR-1408 | skill/scripts/aidd_review.py | LOGIC | | open | modifying digest calculation; modifying review_state |
| T-02 | FR-1401, FR-1402, FR-1403, FR-1404, FR-1405, FR-1406, FR-1407 | skill/templates/review.html | VIEW | | open | breaking existing DOM ids or button handlers |
| T-03 | FR-1401, FR-1402, FR-1403, FR-1404, FR-1405, FR-1406, FR-1407 | adapters/dot-aidd/templates/review.html | VIEW | | open | manual edits divergent from skill/templates/review.html |
| T-04 | FR-1401, FR-1402, FR-1403, FR-1404, FR-1405, FR-1406, FR-1407, FR-1408 | tests/test_review_template.py | LOGIC | | open | any other test file |

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| Wave 1 | T-01 | builder | 8 | 50 | 0.8 |
| Wave 2 | T-02 | builder | 15 | 100 | 1.5 |
| Wave 3 | T-03, T-04 | builder, tests | 5 | 50 | 0.5 |

Total agent time (critical path): 28 min
Total tokens (k): 200

## Per-task detail

### T-01
**Classify**
- Nature: `FEATURE`
- Priority: 1 HIGH
- Kind: LOGIC

**Estimate**
- Agent min: 8
- Human ref hours: 0.8
- Tokens (est): 50k
- Agent role: builder
- Model tier: medium

**Target**
- File: `skill/scripts/aidd_review.py`
- Codes: `FR-1408`

### T-02
**Classify**
- Nature: `FEATURE`
- Priority: 1 HIGH
- Kind: VIEW

**Estimate**
- Agent min: 15
- Human ref hours: 1.5
- Tokens (est): 100k
- Agent role: builder
- Model tier: medium

**Target**
- File: `skill/templates/review.html`
- Codes: `FR-1401, FR-1402, FR-1403, FR-1404, FR-1405, FR-1406, FR-1407`

### T-03
**Classify**
- Nature: `FEATURE`
- Priority: 1 HIGH
- Kind: VIEW

**Estimate**
- Agent min: 3
- Human ref hours: 0.3
- Tokens (est): 20k
- Agent role: builder
- Model tier: medium

**Target**
- File: `adapters/dot-aidd/templates/review.html`
- Codes: `FR-1401, FR-1402, FR-1403, FR-1404, FR-1405, FR-1406, FR-1407`

### T-04
**Classify**
- Nature: `TEST`
- Priority: 1 HIGH
- Kind: LOGIC

**Estimate**
- Agent min: 5
- Human ref hours: 0.5
- Tokens (est): 30k
- Agent role: tests
- Model tier: medium

**Target**
- File: `tests/test_review_template.py`
- Codes: `FR-1401, FR-1402, FR-1403, FR-1404, FR-1405, FR-1406, FR-1407, FR-1408`
