# Plan — 014 AIDD Mockup-First Spec Approval & Visual Verification Portal

## Naming & File Contract (fill this first — everything below depends on it)
| Item | Convention |
|---|---|
| Classes / components / types | PascalCase |
| Functions / variables / methods | snake_case (Python scripts), camelCase (JavaScript in template) |
| File names | snake_case (`aidd_review.py`), kebab-case (`review.html`) |
| Template files | `skill/templates/review.html`, `adapters/dot-aidd/templates/review.html` |
| Mirror parity | `adapters/dot-aidd/templates/review.html` must remain byte-identical to `skill/templates/review.html` |

## Script / Code Map

| Code | Target file | Purpose / Contract | PR (once opened) |
|---|---|---|---|
| FR-1408 | skill/scripts/aidd_review.py | Parse `mockup-audit.md` and spec prototype assets; inject mockups into `DATA_JSON` | |
| FR-1401 | skill/templates/review.html | Modernized Executive Header with status pulse, progress badge, and R6 action | |
| FR-1402 | skill/templates/review.html | Top KPI Metric Cards (Effort, Tasks, Mockups, Verifications) dynamically populated | |
| FR-1403 | skill/templates/review.html | Split-View container layout (60% Mockup Canvas / 40% Tabbed Panels) with auto-collapse | |
| FR-1404 | skill/templates/review.html | Interactive Mockup Canvas rendering `SCREEN-XX` images via local/CSP data URIs | |
| FR-1405 | skill/templates/review.html | Viewport switchers (Desktop 1440, Tablet 768, Mobile 375) and zoom controls | |
| FR-1406 | skill/templates/review.html | Component-level highlight and synchronization between checklist and mockup tags | |
| FR-1407 | skill/templates/review.html | Single-column graceful collapse when a spec has 0 screens | |
| FR-1401 | adapters/dot-aidd/templates/review.html | Byte-identical mirror of `skill/templates/review.html` | |
| FR-1401 | tests/test_review_template.py | Unit test coverage for executive portal, mockups data, DOM markers, and exports | |

## Verification Command
`pytest tests/test_review_template.py tests/test_aidd_review.py tests/test_dot_aidd_mirror.py -q`
