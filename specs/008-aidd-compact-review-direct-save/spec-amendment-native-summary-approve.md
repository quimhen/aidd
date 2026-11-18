# Spec amendment — AIDD 008 native explicit-summary Approve compatibility

PROPOSED policy extension to existing FR-313 / AC-327, not a repeat of F12 approval. AIDD intake: AMENDMENT — Fast Lane — one contained consent-recognition extension; no implementation yet.

The owner genuinely chose English Approve for a trusted native question explicitly asking “¿Apruebas con resumen … [tasks:hash]?” Current exact-label Spanish summary policy rejects that choice and routes to an unrelated stale review page. Preserve the genuine question, offered labels and answer unchanged. This amendment deliberately extends semantic policy and needs its own new owner approval.

## Scope

Exactly three implementation files: `skill/scripts/aidd_status.py`, `adapters/dot-aidd/scripts/aidd_status.py`, `tests/test_native_summary_approve_compat.py`. No evidence, review documents, task seals, generic answer API, unit-consent API or hooks are rewritten. Existing hook delegates to the canonical helper.

## Functional requirements

- FR-313-N1: Preserve existing exact Spanish `Aprobar con resumen` behaviour, including its current spacing handling and old regression cases.
- FR-313-N2: English choice must be exactly `Approve` after stripping outer whitespace, explicitly offered as `Approve`, from the newest trusted answer for the current tag and exact known session, after since_ts and not in the future.
- FR-313-N3: English question must start with positive explicit `¿Apruebas con resumen` intent and include the current tag in its initial question clause. Reject negated, quoted, conditional or alternative-mode intent. Unrelated narrative such as “No cambian producción” after the initial question must remain valid.
- FR-313-N4: English path requires a matching earlier trusted question event, same session/tool_use_id, question text and offered options. No typed prompt, raw answer text, missing/ambiguous anchor, nonoffered option, wrong tag, stale event or cross-session event establishes summary consent.
- FR-313-N5: Newest topical answer for the current tag is authoritative: a newer rejection, plain/ambiguous Approve or invalid offered label cancels an older eligible response. Do not retry older events through a second fallback query.
- FR-313-N6: Return the original evidence event, never rewrite its chosen label, options, native provenance, task hash or timestamp. Existing cmd_approve then records the supported summary route normally; no approval event is appended by the helper.

## Closed recognition grammar

For the new English branch only: normalize whitespace for analysis but retain original stored data. Initial clause ends at the first `?` and must begin `¿Apruebas con resumen ` (case-insensitive; repeated spaces allowed). It must contain the exact current task tag; it must contain none of the standalone tokens `no`, `sin`, `o`, `si`, `cuando`, `u`, `versus`, `vs`, none of the phrases `siempre que`, `en caso de`, `sujeto a`, `condicionado a`, `a condición de`, `hasta que`, and no quote/backtick prefix. Reject explicit approval negation anywhere in the question: `no aprobar`, `no apruebes`, `no apruebas`, `no autorizo`, `sin aprobar`, `nunca aprobar`. This intentionally conservative grammar does not accept other English/Spanish summary phrasings. Keep the legacy Spanish-label branch independent of this new grammar.

## Acceptance cases

1. Native exact question shape with current tag, offered Approve, exact same session, trusted question+answer and fresh timestamp returns the original event. Include the narrative “No cambian producción” to prevent overbroad negation matching.
2. Exact legacy Spanish-label route remains accepted and its existing negative-label cases remain refused.
3. Eight negative groups in T-09 all return None and create no approved event.

## Verification and budget

Only focused stdlib unittest commands in the task; no database, network or full regression suite. Estimated ten agent minutes including independent review. The current F12 decision remains unchanged. Root, from the genuine Root session, re-invokes ordinary official rules approve after this NEW policy change passes and is integrated. Never widen the policy to accept a child session merely to make the command convenient.
