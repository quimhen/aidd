# Plan — AIDD 008 native explicit-summary Approve compatibility

PROPOSED; copied from matching plan template sections. Independent Root R5 review and a new actual owner decision are required before code edits.

## Naming & File Contract (fill this first — everything below depends on it)

| Item | Convention |
|---|---|
| Functions | Preserve `_summary_answer(ev, root, session, since, tag)` signature and returned original event/None |
| Private helper | `_native_summary_approve_question(question, tag)` returns bool; canonical module only, mirrored identically |
| Constants | `_SUMMARY_NATIVE_LABEL_RE`; exact legacy SUMMARY_LABEL unchanged |
| Files | Canonical script, existing adapter mirror, one focused unittest file |

## Component → Code map

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Explicitly out of scope |
|---|---|---|---|---|
| T-09 | FR-313-N1..N6, existing FR-313/AC-327 extension | `skill/scripts/aidd_status.py` + `adapters/dot-aidd/scripts/aidd_status.py` + `tests/test_native_summary_approve_compat.py` | LOGIC | Evidence files, generic consent APIs, unit seals, production/database work |

## Implementation sequence

1. Add focused RED tests using real public question/answer APIs in temporary test projects; do not represent a synthetic test event as actual owner approval.
2. Extend only the canonical summary helper and its private positive-question predicate. Query newest topical answer once with labels admitting the legacy exact label or new exact Approve; evaluate that newest event only. Preserve Spanish branch behaviour. English branch additionally validates exact known session, freshness, native tool anchor, exact offered label and the closed positive-intent grammar.
3. Copy canonical script to existing adapter mirror through a SHA-guarded mapping, preserving existing mirror policy. No hook source changes: current hook delegates to this helper.
4. Run only focused new tests and existing summary-route regressions; independently review consent negatives, mirror parity and untouched native evidence. Main integration invalidates relevant audit snapshots, so Root coordinates the final actual audit cohort rather than reusing earlier reports blindly.
5. Root invokes ordinary approval from its own genuine session for the unchanged actual F12 decision. This is verification of the new recognizer, not a new F12 question or a forged summary label.

Tools first: one mapping script with dry-run/apply/post-check; never bulk-edit mirrors by hand. Native AIDD graph first, then only named source ranges. No database creation or access; if a later unrelated task needs a DB, only db_verify default or slots1..3. No global tests, hook/rules overrides, fabricated approvals, review-checkbox edits or answer relabeling.
