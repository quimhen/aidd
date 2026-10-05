# QA Audit — AIDD 008: compact tabbed review, direct save, `aidd review --wait/--summary`, review mode choice

**Audited by:** one independent closing auditor (opus) covering functional, performance and security, plus two per-domain auditors dispatched after the last verify run because this host does not report the closing auditor's result length (open decision O-10 of spec 007): a security auditor (opus, PASS: label route, forged answers, picker check, CSP) and a performance auditor (sonnet, PASS: review_state 119 ms on F15, 727 items; hooks load the review modules lazily). Nobody audited their own work. Earlier: T-05 closing audit and a delta audit (`closing-audit.md`), a Mapper, three pre-build audits and two independent critics.

## Verification summary
Verification: `aidd verify 008-aidd-compact-review-direct-save` PASSED, 5/5 rows, verify hash 100a2c23 (evidence/verify-V-1.txt .. verify-V-5.txt): full suite 1751 OK, review tests 113 OK, status/rules/gate tests 672 OK, mirror 8 OK, e2e `ROUNDTRIP OK`.

## Domain checklist (filled from the single closing auditor's report)
The closing auditor's first line was `CLOSING AUDIT [domains: functional, performance, security] [tasks:e2e2d243] [verify:100a2c23]`.

Closing auditor id: toolu_01GqtPwzxJdrUsfBwSp1UQei

| Domain | Covered by closing auditor? | Result | Key findings |
|---|---|---|---|
| security | yes | PASS | Exact `Aprobar con resumen` is the only label that mints source=summary; near-misses, typed prompts, wrong or missing tag, other-session answers and answers older than tasks.md are refused; review.md alone never approves; picker checks spec and tasks_hash; CSP and escaping unchanged; one LOW (L-1) accepted |
| functional | yes | PASS | F28 copy 175 codes, Q10/Q11 pending; one-line states and exits in both argument orders; F23 93 five-digit CTL codes reviewable; carry-over 174/175 after editing one row; legacy 007 review.md rejected without a crash |
| performance | yes | PASS | F15 727 items: extract 61 ms, review_state 92 ms, generate 116 ms; `--wait` about 0.1 s per poll; hook hot paths unchanged (82-129 ms) |

## Mapping ledger
| Code | Status | Evidence (file/class/resource id) | PR/Spec ref | Screenshot diff done? |
|---|---|---|---|---|
| FR-301..FR-308 | ✅ IMPLEMENTED | skill/scripts/aidd_review_items.py, aidd_review_state.py, aidd_review.py, skill/templates/review.html | T-01, T-02, T-07, T-08 | n/a |
| FR-309..FR-313 | ✅ IMPLEMENTED | aidd_review_state.py (status_line, comment_lines, summary_lines), aidd_status.py (_summary_answer), rule_gate.py | T-03, T-07, T-08 | n/a |

## Device preflight
Preflight: not applicable (no device code; AIDD is a stdlib CLI, hooks and a static page).

## Execution evidence
No SCREEN-nn, API-nnn or -Fnn codes in this spec; FR/AC execution outputs are saved under `evidence/` (verify-V-1..V-5, delta-*.txt, the e2e roundtrip).

| Code | Kind | Evidence | Verified by |
|---|---|---|---|

## Bug reports
| # | Code | Symptom | Root cause | Fix | Pattern sweep |
|---|---|---|---|---|---|

## Revision log (append, never overwrite)
```
Rev 1 (2026-10-05) — 100% of FR-301..FR-313 implemented; 31/31 AC re-verified after the delta fixes; suite 1751 OK; verify 5/5
```

## Open exceptions (rows left unresolved on purpose)
| Code | Reason | Approved by |
|---|---|---|
| L-1 | an over-cap spec whose review.html has no parseable blob reports STATE=stale instead of too_many_items, and the exact `Aprobar con resumen` answer approves; not agent-exploitable (owner-only page plus the owner's own click, same as the by-design --full path) | owner, via this close |
| native folder picker | stubbed in tests; the real picker in Chrome/Edge from file:// is an owner-run check | owner |
| --wait cost | review_state re-extracts on every poll (about 0.1 s on F15), accepted | owner, via this close |
