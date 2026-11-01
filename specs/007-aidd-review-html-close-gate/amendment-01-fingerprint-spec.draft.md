# Draft amendment 01 — safe SQL fingerprints and Scope patterns

**DRAFT — not approved and not merged into spec 007.** Existing approvals are historical and do not authorize these tasks. This backend-only draft has no visual surface. It covers only the two confirmed validity risks; incremental row reuse, approval units, visual versioning and cross-platform CI are subsequent work.

## Minimum Requirements Checklist (template: skill/templates/spec.md)

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | AIDD code evidence and verification scope | repo — skill/scripts/aidd_evidence.py:1960 | — |
| New development or modification of something existing? | Amendment to spec 007 fingerprint and verification | repo — specs/007-aidd-review-html-close-gate/plan.md:32 | — |
| Does it involve an external service, API, or integration? | No new service; existing Git and filesystem remain inputs | repo — tests/test_code_fingerprint.py:21 | — |
| Who is requesting it? (role/profile, not necessarily the name) | Project owner | user — "procedamos con las optimizaciones antes de continuar con los specs de b1synclink" | — |
| Dependencies on other modules or active developments? | Evidence hooks, per-spec and generated scopes, installed adapter mirror | repo — skill/scripts/aidd_evidence.py:1183 | — |
| Business objective (1 sentence — what it achieves and why) | Prevent false-fresh verification without needless re-execution for provably irrelevant changes. | user — "la ejecucion innecesaria consume el doble de tokens" | — |
| Expected visual fidelity level (if there's a mockup): exact \| functional behavior only | Not applicable; no screen or visual mockup. | repo — skill/scripts/aidd_evidence.py:1963 | — |

## Scope

- Included: raw-byte SQL content fingerprint, fail-closed file enumeration, conservative change classification, shared Scope/Generated pattern matching, versioned verification evidence and temporarily blocking cache eligibility without a verified environment, adapter mirrors, focused tests, migration/compatibility notice.
- Excluded: SQL semantic normalization unless a later amendment defines and tests an explicit dialect/context; changing `Inputs` syntax, implementing a new trusted environment verifier, inferring dependencies or declaring DB checks hermetic, R6/approval UX, visual-version model, CI dependency/install issues, updating consuming specs' `Scope`/`Generated`, altering protected `.aidd/` state manually.

## Functional requirements

| FR-nnn | Requirement | Cites (SCREEN-XX-Fnn / CTL-nnn / API-nnn) |
|---|---|---|
| FR-210 | Fingerprint raw SQL bytes, without interpreting dialect, literals or comments; `comment_only_edit` cannot classify an SQL edit as non-code by default. A future, separately approved optimization may normalize semantically only with explicit, validated dialect and context. | spec 007 FR-205; supersedes spec 006 comment-only behavior for this release |
| FR-211 | Every Scope/Generated consumer, including `aidd_rules._glob_hit` during and after verification, uses the same root-relative, segment-aware pattern grammar supporting `*`, `?`, `**` and bracket classes such as `[0-4]`. Invalid patterns cannot silently narrow Scope or broaden Generated exclusion. | spec 007 FR-205; `eDoc`/Payroll incident P07 |
| FR-212 | Aggregate verification runs and individual row-cache entries carry an explicit evidence-algorithm version. Preserve historical events; assess legacy aggregate code-fingerprint impact narrowly rather than resetting every spec. Never automatically reuse any row unless its evidence, declared inputs, hermeticity and required execution-environment identity are verifiable and match. Unknowns fail closed without fabricating prior metadata. | spec 007 FR-205 and R10 |
| FR-213 | If a listed SQL input disappears or cannot be inspected or read while a snapshot is taken, verification fails closed instead of silently omitting that input or using size/mtime as its content. | spec 007 FR-205 and R10 |

## Acceptance cases

| Case | Real data (id) | Expected | Edge? |
|---|---|---|---|
| AC-219 | `SELECT $$a--b$$;` vs `SELECT $$a--c$$;` | Raw-byte SQL digests and applicable code fingerprints differ. | PostgreSQL dollar quote |
| AC-220 | `$tag$...$tag$` containing `--`, `/* */`, `'`, newlines; two bodies differing only inside the literal | Raw bytes are not normalized or decoded and fingerprints differ. | Tagged and multiline |
| AC-221 | SQL edits differing only in comments or whitespace, including unmatched quotes and non-UTF8 bytes | Every different byte sequence changes the digest, and an edit is not classified as comment-only. This can rerun a relevant check even if the edit was only commentary. | Intentional conservative cost |
| AC-222 | `Payroll/supabase/migrations/23[0-4]*` and `.../2300_example.sql` | Scope matches; an actual edit is reflected by fingerprint and last edit, including git and filesystem fallback. | Concrete P07 incident |
| AC-223 | `*`, `?`, `**`, ranges, negated classes, literal bracket and bad/unsafe pattern in Scope and Generated | Matching is deterministic and segment-aware; invalid Scope prevents a passing verification, invalid Generated never excludes files; `Scope:auto` and empty-scope semantics are unchanged. | Bad and unsafe patterns |
| AC-224 | Old recorded fingerprint/evidence and new algorithm on identical file contents | Retain the event; distinguish narrowly demonstrable unaffected non-SQL code scope from SQL/unsupported/unknown scope; never treat matching content as proof of unchanged execution environment. No manual evidence deletion or fabricated audit. | Upgrade compatibility |
| AC-225 | Edit a known outside-scope file, an inside-scope file and a generated output | Outside-scope edit preserves a valid scoped fingerprint; inside-scope edit invalidates; a properly declared output remains excluded. | Unrelated and output changes |
| AC-226 | PostgreSQL adjacent string literals separated by a newline versus spaces only | Do not normalize the newline away when it changes lexical interpretation; preserve input exactly if equivalence is uncertain. | Significant whitespace |
| AC-227 | Two files exceeding 5 MiB or files whose bytes differ despite equal size and restored mtime, for git and non-git | Both raw-byte changes alter their fingerprint; unreadable, unstable or budget-exhausted files refuse verification instead of falling back to size/mtime. | Large or stealthily changed file |
| AC-228 | Tracked SQL listed by Git disappears before `isfile`/hashing, or a non-Git SQL file disappears or becomes inaccessible between directory enumeration and stat/read | No partial `code_state` or valid fingerprint is returned, and end-to-end verify refuses a passing verdict; legitimate staged deletion can be verified after the Git index no longer lists it. | Concurrent deletion/access error |
| AC-229 | A passing pre-upgrade non-SQL hermetic row with intact log and unchanged raw input, but no verifiable environment identity | The row remains recorded historically but is not automatically reused; execution is required when that row is needed. A current algorithm marker alone is not environment proof; unknown/missing/changed environment, corrupt evidence and changed input never reuse. | Legacy per-row cache |
| AC-230 | A valid `Generated: output/report[0-9].bin` is rewritten by an executed command | Fingerprint exclusion, runtime stability and close evaluation agree the matching file is a generated output; an invalid pattern refuses the result, and an unmatched changed file makes the run stale. | Consumer parity |
| AC-231 | A coordinated writer changes SQL during the first stream read and restores size/mtime before the second | Verification refuses when the two complete byte digests differ; documentation states that two matching reads alone cannot prove an atomic snapshot against an adversarial writer, and a controlled worktree or trusted snapshot is required for that stronger guarantee. | Concurrent writer |
| AC-232 | Git scanner encounters an unsafe/missing listed SQL input while a non-Git fallback could scan the same tree | Snapshot and verify refuse; a genuinely missing/unavailable Git executable alone still permits the documented non-Git fallback. | Fallback classification |
| AC-233 | A previously approved verification has `changed=[]`, then the current `Generated:` declaration is malformed | Close evaluation and machine-readable JSON verdict refuse freshness regardless of whether any file was rewritten during the prior run. | Invalid declaration after verify |
| AC-234 | A legacy verification has a recorded explicit literal-only non-SQL Scope/Generated, matching current declarations and raw content; no SQL or affected pattern is included | Report its code-fingerprint portion as not affected by the SQL/glob change; preserve the historical record. This alone does not prove row environment or authorize `REUSED`. An empty/global Scope, SQL, affected glob, unknown input or inconsistent declarations is conservatively affected. | Selective legacy migration |
| AC-235 | A database or network verification, or an otherwise unchanged test, without verifiable identity of all required external state/toolchain | Do not reuse a row merely because `Reuse: hermetic` or the current algorithm marker is present. A database check is not reusable without a verifiable matching snapshot identity. | External state |

## Verification

| # | Command | Expected | Covers |
|---|---|---|---|
| V-1 | `python -m unittest tests.test_evidence tests.test_code_fingerprint tests.test_verify_regressions tests.test_aidd_rules` | exit 0 | FR-210, FR-211, FR-212, FR-213, AC-219..AC-228, AC-230..AC-233 |
| V-2 | `python -m unittest tests.test_wave_verification tests.test_aidd_status` | exit 0 | FR-211, FR-212, FR-213, AC-228..AC-230, AC-232..AC-235 and existing cache safety |

No row is declared hermetic here. Targeted runs validate behavior; final spec 007 verification and its independent audit remain separate.

## Review notes

The precise raw-byte and fail-closed behavior is in the plan draft. Preserve all historical results and avoid a global reset based solely on a missing version marker; compute code-fingerprint impact per affected scope. Legacy rows without pre-existing verifiable environment proof cannot be automatically reused even when files match, and running a row again does not itself create a trustworthy environment attestation. The current runner has no such verifier: caching remains blocked where the required identity is not provable; a separate future amendment must design the verifier and measure the performance effect. SQL edits consisting only of comments or whitespace also invalidate checks in scope until a later, explicit-dialect optimization is specified and proven. No user consent is inferred from a draft.
