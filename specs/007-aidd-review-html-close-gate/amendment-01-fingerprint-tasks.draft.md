# Draft tasks — safe SQL fingerprints and Scope patterns

**DRAFT — not approved; no code writes authorized by this file.** Based on `skill/templates/tasks.md`. Baseline spec 007's previous approval does not cover these tasks. The same owner handles all four tasks in sequence because they share canonical files, mirrors and test files. The full advanced re-use design is explicitly outside this amendment.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-13 | FR-210, FR-212, FR-213, AC-219..221, AC-224, AC-226..228, AC-231, AC-232 | `skill/scripts/aidd_evidence.py` + `adapters/dot-aidd/scripts/aidd_evidence.py` + `tests/test_evidence.py` + `tests/test_code_fingerprint.py` + `tests/test_verify_regressions.py` | LOGIC | | | SQL semantic parser, row caching, Scope grammar, DB, installed copies |
| T-14 | FR-211, AC-222..225 | `skill/scripts/aidd_evidence.py` + `adapters/dot-aidd/scripts/aidd_evidence.py` + `tests/test_code_fingerprint.py` + `tests/test_verify_regressions.py` | LOGIC | | | same owner as T-13; new cache policy, changing consuming specs |
| T-15 | FR-211, AC-230, AC-233 | `skill/scripts/aidd_rules.py` + `adapters/dot-aidd/scripts/aidd_rules.py` + `tests/test_aidd_rules.py` + `tests/test_aidd_status.py` | LOGIC | | | same owner as T-13; DB, approval behavior |
| T-16 | FR-211, FR-212, AC-224, AC-229, AC-233 | `skill/scripts/aidd_status.py` + `adapters/dot-aidd/scripts/aidd_status.py` + `skill/scripts/aidd_rules.py` + `adapters/dot-aidd/scripts/aidd_rules.py` + `tests/test_wave_verification.py` + `tests/test_aidd_status.py` | LOGIC | | | same owner as T-13; new cache policy, DB |

## Per-task detail

### T-13 — SQL raw-byte integrity and fingerprint compatibility
**Classify**
- Nature: `INCIDENT`
- Kind: LOGIC
- Priority: 1
**Estimate**
- Agent min: 25
- Human ref hours: 1.25
- Tokens (est): 150k
- Agent role: builder
- Model tier: high
**Detail**
- Goal: fingerprint every in-scope SQL file by raw bytes and invalidate historical SQL fingerprints whose normalization was unsafe.
- Size: ~150 changed lines.
- Cites: FR-210, FR-212, FR-213, AC-219, AC-220, AC-221, AC-224, AC-226, AC-227, AC-228, AC-231, AC-232.
- Depends on: approved amendment and pre-build coherence audit.
- Read first: `skill/scripts/aidd_evidence.py:1954-2030`, `tests/test_evidence.py:202-245`, `tests/test_code_fingerprint.py:1-80`; the draft plan behavioral contract 1–4 and 7.
- Files to change: canonical evidence module and its listed mirror; `tests/test_evidence.py`, `tests/test_code_fingerprint.py` and `tests/test_verify_regressions.py` only.
- Naming contract: retain `sql_semantic(text) -> str`, `sql_digest(data) -> str`, `comment_only_edit(path, tool_input) -> bool`, `code_state(root, budget_s=8.0, scope=None, reuse=False)`, and `_fp_sql_chunk(root, rel)` two-argument compatibility; version SQL chunk prefix as `sql-raw-v2:` and hash with SHA-256; constant `EVIDENCE_ALGORITHM = 'raw-sql-v2-glob-v2'`, event key `code_algorithm`, and exception `_FpInputUnsafe` distinct from `_FpUnavailable`.
- Behavior: implement raw bytes and fail-closed streaming per plan 2–4; `sql_semantic` returns its input unchanged, `comment_only_edit` returns False, and `sql_digest` computes SHA-256 of bytes. Read SQL twice, compare digests and file metadata before/between/after, enforce budget and refuse instability; this detects observed races but does not prove atomicity against a writer that toggles and restores bytes between observations. Reject missing/unreadable SQL returned by Git enumeration and SQL that disappears/fails stat or read in filesystem walk; reject walk errors rather than silently omitting paths. Raise `_FpInputUnsafe` for unsafe SQL input, not `_FpUnavailable`: the latter alone retains Git-unavailable fallback, while unsafe input propagates without fallback and `code_state` returns `None`. Remove SQL `(path,size,mtime)` digest caching and never fall back to metadata for SQL. Add `EVIDENCE_ALGORITHM = 'raw-sql-v2-glob-v2'` and allow `code_algorithm` in `_VERIFY_EXTRA` for T-16. Synchronize mirror after canonical edit with scripted copy/dry-run/hash check.
- Tests first: add distinct dollar-body inputs, tagged strings containing comment delimiters, doubled quotes, nested block comments, unmatched delimiter, escaped tokens, adjacent quoted literals with newline versus space, byte/encoding differences, files larger than 5 MiB, same-size edits with restored mtime, old/new fingerprint comparison, and SQL listed then missing/inaccessible at isfile/stat/read (git and non-git). Simulate unsafe Git SQL while an otherwise successful non-Git fallback is available: `code_state`/verify must refuse without invoking fallback; simulate genuinely missing Git and prove normal fallback still works. Coordinate a writer mutating bytes during first read and restoring size/mtime; require snapshot/verify refusal. Test budget exhaustion and describe controlled-worktree limitation. Show red failure for dollar collision; revise legacy comment-only-equivalence assertions to raw-byte invalidation. Then implement.
- Verify: orchestrator runs `python -m unittest tests.test_evidence tests.test_code_fingerprint tests.test_verify_regressions tests.test_aidd_rules` -> exit 0 and `python -m unittest tests.test_wave_verification tests.test_aidd_status` -> exit 0; compare mirror SHA-256 -> equal. Builder runs only static Python compile checks of its files; tests first red is coordinated with orchestrator, not a second heavy wave.
- Do NOT: normalize SQL using inferred dialect, weaken collision tests, silently omit a listed SQL input, fall back to size/mtime, memoize by mutable metadata, claim atomicity against an adversarial writer, touch Scope policy, fabricate old evidence, change `.aidd/`, install a parser or broaden caching eligibility.
- Done when: required red and green outputs exist, mirror hashes agree, raw-byte changes invalidate correctly on both backends and large files, incomplete/racy scans fail closed, and an independent audit checks fingerprint soundness and migration.
- Open questions: none.

### T-14 — segment-aware Scope and Generated pattern safety
**Classify**
- Nature: `INCIDENT`
- Kind: LOGIC
- Priority: 1
**Estimate**
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 120k
- Agent role: builder
- Model tier: high
**Detail**
- Goal: implement correct, portable pattern handling without falsely excluding inputs or granting freshness on malformed patterns.
- Size: ~150 changed lines.
- Cites: FR-211, FR-212, AC-222, AC-223, AC-225.
- Depends on: T-13, same owner as T-13.
- Read first: `skill/scripts/aidd_evidence.py:1183-1203,2031-2044,2152-2210`, `skill/scripts/aidd_rules.py:2169-2230`, existing `TestScope` in `tests/test_code_fingerprint.py`, and draft plan 5–7.
- Files to change: canonical evidence module and its mirror; `tests/test_code_fingerprint.py` and `tests/test_verify_regressions.py` only.
- Naming contract: preserve `_scope_re(globs)`, `in_scope(rel, scope_rx)`, `code_state`, `fingerprint_of` and `last_code_edit_ts`; use the precise pattern grammar and failure behavior in plan 5.
- Behavior: compile segment-aware wildcards and character classes; normalize separators; reject unsafe or malformed patterns; test `Generated` and `Scope` separately, including last-edit fallback that cannot return a false-safe zero after a pattern failure. Keep `Inputs` Path.glob as-is and test matching parity for representative patterns. Sync mirror using scripted copy/dry-run/hash check.
- Tests first: P07 bracket-pattern reproducer must fail before the change; add exact positive/negative cases for `*`, `?`, `**`, range, negation, literal brackets, malformed/absolute/traversal patterns, `Generated`, git/non-git and outside/inside scope. Demonstrate invalid patterns refuse a passing verify rather than silently excluding an input.
- Verify: orchestrator runs `python -m unittest tests.test_evidence tests.test_code_fingerprint tests.test_verify_regressions tests.test_aidd_rules` -> exit 0 and `python -m unittest tests.test_wave_verification tests.test_aidd_status` -> exit 0; compare mirror SHA-256 -> equal. Builder runs only static Python compile checks and reports targeted red evidence.
- Do NOT: silently treat invalid Generated as exclude-all, change `Inputs` semantics, mark network/database checks hermetic, edit consuming specs or protected files, or run heavy suites concurrently.
- Done when: all required cases pass, the P07 pattern tracks edits, unknown patterns fail closed, mirror matches and audit finds no false-fresh path.
- Open questions: none.

### T-15 — unify Generated matching across verification consumers
**Classify**
- Nature: `INCIDENT`
- Kind: LOGIC
- Priority: 1
**Estimate**
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 95k
- Agent role: builder
- Model tier: high
**Detail**
- Goal: ensure runtime stability and close evaluation interpret Generated patterns identically to the scoped fingerprint.
- Size: ~100 changed lines.
- Cites: FR-211, AC-230, AC-233.
- Depends on: T-14; same owner as T-13.
- Read first: `skill/scripts/aidd_rules.py:2723-2740,2755-2780`, `skill/scripts/aidd_status.py:1595-1607,1986-1996`, plan behavioral contracts 5–6 and tests for Generated in `tests/test_aidd_status.py` and `tests/test_aidd_rules.py`.
- Files to change: `skill/scripts/aidd_rules.py`, `adapters/dot-aidd/scripts/aidd_rules.py`, `tests/test_aidd_rules.py`, `tests/test_aidd_status.py` only.
- Naming contract: preserve `_glob_hit(rel, globs) -> bool`; delegate to `aidd_evidence._scope_re` and `in_scope` with lazy import if required; no duplicate matcher. On malformed Generated patterns `_glob_hit` returns False and the corresponding fingerprint/verification refuses rather than excluding files.
- Behavior: use canonical matcher for all `Generated` runtime and close paths; handle no patterns as no match, normalize valid paths identically to Scope, fail safely on parser errors. In `_run_problems`, unconditionally validate current Generated even when recorded `code_changed=[]`; a malformed declaration makes the run stale and cannot be bypassed by empty iteration. T-16 implements equivalent JSON-verdict validation. Synchronize mirror by script with dry-run and hash post-check.
- Tests first: add end-to-end verify whose real command rewrites `output/report1.bin` under `Generated: output/report[0-9].bin`; it must be stable, retain evidence and agree with close check. Add unmatched changed output and malformed pattern cases that cannot pass, including an already approved/verified run with `code_changed=[]` after the current declaration becomes malformed. Run red before changing implementation.
- Verify: orchestrator runs `python -m unittest tests.test_aidd_rules tests.test_aidd_status tests.test_code_fingerprint` -> exit 0 and compares mirror SHA-256 -> equal. Builder only static Python compile checks; red run is orchestrated.
- Do NOT: create a second pattern grammar, alter `Inputs` or mark DB tests hermetic, ignore invalid patterns, change unrelated rules, or run heavy checks concurrently.
- Done when: runtime, fingerprint and close evaluate valid/invalid Generated patterns consistently and evidence demonstrates no false-fresh case.
- Open questions: none.

### T-16 — version verification evidence and row-cache eligibility
**Classify**
- Nature: `INCIDENT`
- Kind: LOGIC
- Priority: 1
**Estimate**
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 130k
- Agent role: builder
- Model tier: high
**Detail**
- Goal: distinguish historically unaffected code scopes from unsafe/unknown legacy scopes and prevent row caching without a verifiable execution-environment identity.
- Size: ~150 changed lines.
- Cites: FR-211, FR-212, AC-224, AC-229, AC-233, AC-234, AC-235.
- Depends on: T-15 and T-13; same owner as T-13.
- Read first: `skill/scripts/aidd_status.py:1525-1550,1781-1840,1986-2055,2097-2135`, `skill/scripts/aidd_rules.py:2755-2817`, `skill/scripts/aidd_evidence.py:1112-1155`, plan behavioral contract 8 and `tests/test_wave_verification.py`.
- Files to change: `skill/scripts/aidd_status.py`, `skill/scripts/aidd_rules.py`, corresponding `adapters/dot-aidd/scripts/` mirrors, `tests/test_wave_verification.py` and `tests/test_aidd_status.py` only.
- Naming contract: constant `aidd_evidence.EVIDENCE_ALGORITHM = 'raw-sql-v2-glob-v2'` and `_VERIFY_EXTRA` support are introduced by T-13; event key `code_algorithm`, row key `input_algorithm`; retain `_reusable_input_rows` signature and use the existing verification CLI. Preserve historical event readability.
- Behavior: record `code_algorithm` in aggregate/wave results and `input_algorithm` in executed rows with Inputs. In `_run_problems`, preserve legacy aggregate code freshness only under the exact literal non-SQL Scope/Generated proof in plan 8 and existing fingerprint/evidence checks; empty/global scope, SQL, any glob, unknown version, or inconsistent declarations make affected/unknown evidence stale. In `_json_pass_evidence_problem`, always validate current Generated even when `code_changed=[]`. Do not delete or rewrite history. Neither `_reusable_input_rows` nor in-memory multi-spec wave caching may return a row merely from `input_algorithm`, `Reuse: hermetic`, matching file hashes or command: the current system has no trustworthy environment verifier, so execute requested rows until a future attestation mechanism can prove environment identity and hermeticity. Emit a concise reason; do not claim that re-execution alone supplies such proof. Keep `--full` authoritative. Synchronize status/rules mirrors by script with dry-run/hash post-check.
- Tests first: construct a passing directly executed legacy run with exact non-SQL literal Scope/Generated, intact evidence and matching code fingerprint; prove its historical code portion stays unaffected and event is not rewritten. Change scope to SQL, a glob, empty/global or inconsistent declaration and prove stale. Construct a legacy non-SQL hermetic row with matching byte inputs but no environment identity; prove it does not produce REUSED. Run a second identical verification with a current marker but still no verifiable environment and assert no cache-hit indicator `REUSED`; corrupt evidence, changed input, unknown marker, `--full`, and same-wave multi-spec cache must likewise never produce a hit without proof. Add DB/network rows with absent or changed snapshot/environment identity and assert no hit. For a successful recorded run with `code_changed=[]`, replace current Generated with a malformed pattern and assert JSON refuses PASS; separately prove the close path is stale under T-15.
- Verify: `python -m unittest tests.test_wave_verification tests.test_aidd_status tests.test_verify_regressions tests.test_aidd_rules` -> exit 0; mirrors SHA-256 -> equal; builder runs static Python compile checks only.
- Do NOT: modify protected evidence files manually, delete historical events, apply a global stale decision based only on missing marker, fabricate prior environment attestations, treat current algorithm marker or hermetic label as environment proof, claim a DB check is hermetic without verified matching snapshot identity, or invent a new signing/runner subsystem inside this urgent fix.
- Done when: exact non-SQL historical code scopes are classified without global reset, all affected/unknown cases fail conservatively, no row is returned from cache without independently verifiable environment identity, and an independent audit verifies migration and the explicit temporary runtime cost.
- Open questions: none.

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-13 | builder | 25 | 150 | 1.25 |
| 2 | T-14 | builder | 20 | 120 | 1.0 |
| 3 | T-15 | builder | 15 | 95 | 0.75 |
| 4 | T-16 | builder | 20 | 130 | 1.0 |

Total agent time (critical path): 80 min
Total tokens (k): 495

## Approval gate

This draft is not an approval. Merge/reconcile into spec 007, run structural and independent pre-build checks, then present the final task hash through AIDD's owner review. Do not write an `Approved:` line by hand. One coordinated targeted verification plus independent audit follows the code wave; do not infer product PASS from static checks.
