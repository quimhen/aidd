# QA Audit — AIDD 007: review.html approval, per-spec R6, executed close gate

**Audited by:** four independent closing auditors (security, functional, performance, database), none of whom implemented any task; earlier the T-10 closing auditor and a delta auditor (`closing-audit.md`).

## Verification summary
Verification: legacy close path (spec 007 was approved before `gate: 2` existed; see spec.md "Bootstrap"). Executed instead: full suite `python -m unittest discover -s tests` = 1524 tests OK; `tests/e2e_review_roundtrip.py` = ROUNDTRIP OK; per-AC harness runs in `evidence/`.

## Domain checklist
| Domain | Covered by | Result | Key findings |
|---|---|---|---|
| security | security auditor (opus) | PASS with LOW exceptions | review.md alone never approves; CSP + escaping hold; R-2 closed; new LOW: `_locate` can be re-rooted by a planted `specs/<id>/specs` folder when CLAUDE_PROJECT_DIR is unset |
| functional | functional auditor (opus) | PASS, 1 documented mismatch | AC-201, 205, 207, 210, 212, 216 and e2e re-run PASS; AC-215 sub-case "no pointer + several open specs" is inferred semantics, not "blocks none" |
| performance | performance auditor (sonnet) | PASS | stop_gate 262 ms (+13% vs HEAD, was +46%), rule_gate write 284 ms (faster than HEAD), well under the 15 s timeout |
| database | database auditor (sonnet) | PASS after fix | verify_run rows persisted raw commands: FIXED (redact_secrets in append_verify_run + test) |

## Mapping ledger
| Code | Status | Evidence (file/class/resource id) | PR/Spec ref | Screenshot diff done? |
|---|---|---|---|---|
| FR-201 | ✅ IMPLEMENTED | skill/hooks/rule_gate.py, skill/scripts/aidd_evidence.py (gate_target_specs) | T-01, T-06 | n/a |
| FR-202 | ✅ IMPLEMENTED | skill/scripts/aidd_review.py, skill/templates/review.html | T-03, T-04 | n/a |
| FR-203 | ✅ IMPLEMENTED | skill/scripts/aidd_review.py (review.md grammar) | T-03 | n/a |
| FR-204 | ✅ IMPLEMENTED | skill/scripts/aidd_status.py (cmd_approve, _consent) | T-05 | n/a |
| FR-205 | ✅ IMPLEMENTED | skill/scripts/aidd_rules.py (verification), aidd_status.py (aidd verify) | T-02, T-05 | n/a |
| FR-206 | ✅ IMPLEMENTED | skill/scripts/aidd_rules.py (closing audit), skill/hooks/stop_gate.py | T-02, T-07 | n/a |
| FR-207 | ✅ IMPLEMENTED | skill/templates/spec.md (Verification, Optimization brief) | T-09 | n/a |
| FR-208 | ✅ IMPLEMENTED | skill/scripts/check_spec.py, aidd_status.py (--refresh) | T-05, T-08 | n/a |
| FR-209 | ✅ IMPLEMENTED | skill/hooks/mark_code_edit.py, mark_agent_dispatch.py | T-12 | n/a |

## Device preflight
Preflight: not applicable (no device code; AIDD is a stdlib CLI plus hooks).

## Execution evidence
No SCREEN-nn, API-nnn or -Fnn codes in this spec; FR/AC execution outputs are saved under `evidence/` (ac-201.txt .. ac-218.txt, full-suite.txt, roundtrip/).

| Code | Kind | Evidence | Verified by |
|---|---|---|---|

## Bug reports
| # | Code | Symptom | Root cause | Fix | Pattern sweep |
|---|---|---|---|---|---|

## Revision log (append, never overwrite)
```
Rev 1 (2026-10-05) — 100% of FR-201..FR-209 implemented; AC-203/204 unverified in a real browser; suite 1524 OK
```

## Open exceptions (rows left unresolved on purpose)
| Code | Reason | Approved by |
|---|---|---|
| AC-203, AC-204 | the browser tools cannot open file://; static XSS sweep + CSP hash checked instead; owner to open one review.html and confirm check/comment/download | pending owner check |
| AC-202(2), AC-215 sub-case | with real events the gate target is inferred (never "ambiguous"); spec text describes "R8 blocks none" | owner, via this close |
| R-1 | cp/mv or glob/variable forms writing a spec artifact for non-numeric ids; lexical guard limit | owner, via this close |
| R-3 | a plan.md edit of an approved spec still moves the inferred target (logged as gate_pointer) | owner, via this close |
| security LOW | planted `specs/<id>/specs` folder re-roots `_locate` when CLAUDE_PROJECT_DIR is unset (normal hook runtime sets it) | owner, via this close |
| review_generated event | deleting review.html reopens the answer-only route (still needs the owner's tagged answer) | owner, via this close |
| F-5 | stop_gate +13% (262 ms), accepted | owner, via this close |
