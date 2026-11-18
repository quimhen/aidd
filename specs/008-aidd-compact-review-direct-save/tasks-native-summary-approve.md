# Tasks — AIDD 008 native explicit-summary Approve compatibility

PROPOSED. New semantic policy extension, separate from already genuine F12 approval. No source implementation is authorized until its own actual owner approval. Derived from matching tasks template.

Tools first: one mapping script with dry-run/apply/post-check; never bulk-edit mirrors by hand. Native AIDD graph first, then only named source ranges. No database creation or access; if a later unrelated task needs a DB, only db_verify default or slots1..3. No global tests, hook/rules overrides, fabricated approvals, review-checkbox edits or answer relabeling.

## File-Change Map (MANDATORY — the contract between spec and code)

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Explicitly out of scope |
|---|---|---|---|---|
| T-09 | FR-313-N1..N6; FR-313 / AC-327 extension | `skill/scripts/aidd_status.py` + `adapters/dot-aidd/scripts/aidd_status.py` + `tests/test_native_summary_approve_compat.py` | LOGIC | Generic consent APIs, hook changes, evidence rewrites, task seals, DB or production |

## Per-task detail (one block per row above)

### T-09 — Recognize a genuine native explicit-summary English Approve
**Classify**
- Nature: INCIDENT
- Priority: 2 HIGH
- Kind: LOGIC
- Status: PROPOSED
- Size: 140 changed canonical/test lines maximum, plus mechanically identical mirror delta.
**Estimate**
- Effort: Medium
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 16k
- Agent role: builder
- Model tier: high
**Decompose**
- Goal: Accept the original native English Approve only for an explicitly positive summary question while preserving all existing Spanish consent and refusal semantics.
- Cites: existing `specs/008-aidd-compact-review-direct-save/spec.md` FR-313 and AC-327; proposal `spec-amendment-native-summary-approve.md` FR-313-N1..N6 and Closed recognition grammar.
- Depends on: actual new owner approval and independent Root pre-build plan review; not a repeat approval of F12 tasks.
- Read first: `skill/scripts/aidd_status.py:1407`; `skill/scripts/aidd_evidence.py:1626`; `skill/hooks/rule_gate.py:450`; `tests/test_aidd_status.py:1805`; `specs/008-aidd-compact-review-direct-save/spec.md:83`; `specs/008-aidd-compact-review-direct-save/spec.md:117`.
- Files to change: `skill/scripts/aidd_status.py`, `adapters/dot-aidd/scripts/aidd_status.py`, `tests/test_native_summary_approve_compat.py`.
- Naming contract: `_summary_answer(ev, root, session, since, tag)` unchanged; private `_native_summary_approve_question(question, tag)` returns bool; `_SUMMARY_NATIVE_LABEL_RE`; existing SUMMARY_LABEL stays exactly Aprobar con resumen. Test class `TestNativeSummaryApproveCompat`, with helper `_record_native_answer` using existing public ev.append_question/ev.append_answer and synthetic callback IDs.
- Behaviour: (1) Preserve legacy exact-label Spanish path. (2) Select newest topical current-tag answer only once using existing ev._answer_event trust boundary; both exact legacy and exact English labels may reach branch validation, but newer rejection/invalid intent must terminate with None, never revive older consent. (3) English requires exact stripped Approve and exact offered Approve at the matching pair index, known same session, since < answer.ts <= time.time()+1, nonempty matching native tool_use_id and one preceding same-session question anchor with matching question/options. (4) Apply the exact closed grammar in the amendment: anchored positive initial question and same current tag, no no/sin/o/si/cuando/u/versus/vs token or siempre que/en caso de/sujeto a/condicionado a/a condición de/hasta que phrase in that clause, and no listed approval-negation phrase anywhere; unrelated post-question No cambian producción is allowed. (5) Return the original event or None; append no approvals and modify no evidence. (6) Mirror the canonical change with a SHA-guarded script; no hook or generic API changes.
- Tests first: Create the focused file using `Spec007Base` from `test_aidd_status` under unittest discovery and actual public ev APIs in temporary test projects. Positive cases: `test_native_explicit_summary_approve_accepts_original_event` with current synthetic [tasks:1234abcd], real question+answer anchor and unrelated narrative No cambian producción; `test_legacy_spanish_summary_route_unchanged`. Eight negative methods, with subTests for listed variants (the conditional/alternative group must include siempre que, cuando, en caso de, sujeto a, condicionado a, a condición de, hasta que, u otra modalidad, versus HTML and vs HTML): `test_plain_approve_without_summary_intent_refused`; `test_negated_quoted_conditional_or_alternative_intent_refused`; `test_nonoffered_or_mismatched_question_anchor_refused`; `test_wrong_or_missing_task_tag_refused`; `test_stale_or_future_answer_refused`; `test_wrong_or_unknown_session_refused`; `test_typed_or_forged_raw_answer_refused`; `test_newer_rejection_or_invalid_intent_cancels_older_consent`. Every refusal returns None and leaves approved-event count zero. Add `test_adapter_mirror_matches_canonical_summary_implementation` without editing unrelated mirror content. First demonstrate the new positive case RED on current source; existing refusal cases may already pass and must not be claimed RED.
- Verify: From D:/Fuentes/AIDD run `python -m unittest discover -s tests -p test_native_summary_approve_compat.py -v` -> exit 0, all new cases pass; `python -m unittest discover -s tests -p test_aidd_status.py -k TestSummaryRoute -v` -> exit 0, existing summary-route cases pass. Root independently reviews exact diff, native question/answer preservation and mirror mapping. No runtime is claimed from source inspection.
- Do NOT: change SUMMARY_LABEL, relabel Approve to Spanish, write review.md checkmarks or Approved lines, append synthetic approval events, accept typed prompts/raw text/nonoffered labels, permit child/cross-session consent, weaken existing Spanish route, run DB/global tests, disable hooks/rules, modify manifests/seals or historical audits, install an ad hoc helper/profile, repeat the old F12 approval question.
- Done when: both positive cases and all eight negative groups pass; newest-answer cancellation is proven; legacy tests stay green; mirror is exact for changed implementation; original actual F12 question/answer remains byte-for-byte unchanged; independent review passes before integration.
- Open questions:

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 008-NATIVE-1 | T-09 | builder | 10 | 16 | 0.5 |

Total agent time (critical path): 10 min
Total tokens (k): 16

## Approval gate

PROPOSED — present this NEW policy extension after independent Root R5 review. The question must offer the exact existing option Aprobar con resumen. This approval is for T-09, not the already authorized F12 work. Do not write an approval line by hand.
