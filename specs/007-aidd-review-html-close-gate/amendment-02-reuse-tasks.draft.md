# Draft tasks — coordinated verification and evidence reuse

**DRAFT: not approved and not build-ready.** Based on `skill/templates/tasks.md`. The trusted provider and transitive-input closure are unresolved safety gates. No production cache or audit carry-over may be enabled merely because synthetic tests pass. Same owner across shared files, with independent security audit.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-17 | FR-214, FR-218, AC-237, AC-239 | `skill/scripts/aidd_reuse.py` | LOGIC | | | execution, historical cache, DB |
| T-18 | FR-215, AC-236, AC-238, AC-240, AC-243, AC-244, AC-245, AC-246, AC-247, AC-248, AC-249, AC-250 | `skill/scripts/aidd_status.py` + `skill/scripts/aidd_rules.py` | LOGIC | | | old evidence mutation, auto-authentication |
| T-19 | FR-216, FR-217, AC-239, AC-241 | `skill/scripts/aidd_reuse.py` same owner as T-17 | LOGIC | | | provider not demonstrably trusted |
| T-20 | FR-219, AC-242 | `specs/006-aidd-phased-audits-attribution/` | LOGIC | | | forged audit provenance |
| T-21 | FR-214..FR-218, AC-236..AC-243 | `tests/test_reuse_planner.py` | LOGIC | | | run all suites per spec |

## Per-task detail

### T-17 — pure cohort planner and explanation
**Classify**
- Nature: `REQUIREMENT`
- Kind: LOGIC
**Estimate**
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 100k
- Agent role: builder
- Wave: 1
**Detail**
- Size: ~150 changed lines.
- Goal: deterministically identify candidates without executing or granting PASS, exposing reason codes for unknowns.
- Cites: FR-214, FR-218, AC-237, AC-239.
- Depends on: approved amendment; the `shared-round-v1` contract in the companion plan.
- Read first: `skill/scripts/aidd_status.py` functions `cmd_verify_many`, `cmd_verify` and `_reusable_input_rows`; plan behavioral contracts 1–5, 8.
- Files to change: `skill/scripts/aidd_reuse.py`; mirror `adapters/dot-aidd/scripts/aidd_reuse.py`; package registration and `tests/test_dot_aidd_mirror.py` in the task contract after audit.
- Naming contract: `plan_round(rows: list[dict], capability_checker) -> list[dict]` returns groups in first-participant order as `{group_id: str, participants: list[dict], eligible: bool, reason: str}`; `explain_round(plan: list[dict]) -> list[str]`. Participant keys, group-key dimensions and reason redaction follow `shared-round-v1` in the plan. Function signatures are internal and preserved after introduction.
- Behavior: preflight all consumers; group only opt-in rows with equal exact command/expected/cwd/ordered Inputs/input_fp/root/timeout/runner policy and the ephemeral effective-environment identity. Use the capability checker to verify same-run local isolation, not historical identity. Unknowns produce separate groups and reason codes. Duplicate row IDs fail preflight. `--full`, `--bail` and parallel Jobs disable grouping. Pure functions never issue processes or persist evidence.
- Tests first: tests in `tests/test_reuse_planner.py` demonstrate red for identical consumer grouping and distinct cwd/env/Inputs/expected; `python -m unittest tests.test_reuse_planner`.
- Verify: orchestrator `python -m unittest tests.test_reuse_planner tests.test_dot_aidd_mirror` -> exit 0; evidence preserved.
- Do NOT: execute a command, trust an unverified manifest, expose secrets or enable existing caches.
- Done when: pure plan and reason records cover all consumers with no false sharing; mirrors equal.
- Open questions: none.

### T-18 — one shared observation with independent consumer attribution
**Classify**
- Nature: `REQUIREMENT`
- Kind: LOGIC
**Estimate**
- Agent min: 25
- Human ref hours: 1.25
- Tokens (est): 160k
- Agent role: builder
- Wave: 2
**Detail**
- Size: ~150 changed lines.
- Goal: run an eligible group once, emit one immutable evidence object and per-consumer records; no historical hit.
- Cites: FR-215, AC-236, AC-238, AC-240, AC-243, AC-244, AC-245, AC-246, AC-247, AC-248, AC-249, AC-250.
- Depends on: T-17. A real verified same-run isolation capability is required only to enable production grouping; no historical environment identity provider is required for one actual observation.
- Read first: `skill/scripts/aidd_status.py` `cmd_verify_many`, `cmd_verify`; plan behavioral contracts 1–7.
- Files to change: `skill/scripts/aidd_status.py`, `skill/scripts/aidd_rules.py`, their adapter mirrors, `tests/test_wave_verification.py`, `tests/test_verify_regressions.py` and `tests/test_aidd_rules.py`.
- Naming contract: preserve `cmd_verify_many` / `cmd_verify` external signatures and legacy result fields; event label `SHARED-RUN`, receipt schema `shared-observation-v1`, canonical manifest schema `shared-group-v1`, final `committed` marker, aggregate `verify_run`, object path and per-row extra fields exactly as in the companion plan. Do not label a shared live run `REUSED`.
- Behavior: before start freeze all participants and their relevant policy and demonstrable row-transitive input/contract closure snapshots, excluding unrelated files even when they match aggregate spec Scope; retain the aggregate spec gate independently; execute one real subprocess, atomically write one immutable shared object, the canonical participant manifest and one small receipt per consumer. Append each participant event in pending state after objects and receipts verify; publish the final committed marker only when every event is durable and all snapshots revalidate. After commit, replay of derived indexes must not re-execute the subprocess. Change both `aidd_rules._run_problems` and `aidd_status._json_pass_evidence_problem` to resolve and validate versioned per-round in-spec receipts, manifest and object under their prescribed roots; independently recompute each participant’s current policy_fp and closure_fp and reject missing, unreadable, incomplete or mismatched dependencies, while retaining existing legacy evidence behavior. Preserve old `verify-<row>.txt`, old receipt files, prior event evidence pointers and their hashes unchanged. Recheck every snapshot and reject PASS for all affected participants after input/declaration/context mutation. Full, bail, parallel or unknown isolation falls back to independent execution.
- Manifest: write `shared-group-v1.participants` as exactly one `{spec_id,row_id,policy_fp,closure_fp}` record per participant in UTF-8 bytewise pair order, canonical JSON as specified in the companion plan; reject missing, extra, duplicated, noncanonical or malformed mappings and compare both fingerprints per participant.
- Journal and aggregation: implement `shared-participant-pending-v1` and tuple key exactly as the companion plan, reject same-key different-payload and no-op identical replay; aggregate `verify_run` requires every expected row and committed evidence before PASS, preserving ordinary row results and historical events. Enforce the plan's ordered file fsync, exclusive atomic rename, directory fsync and journal fsync, failing closed when any capability is unsupported or unproven. Both validators recompute normalized Covers and resolved row-to-FR/AC/task attribution as part of policy_fp.
- Tests first: add red tests in existing wave/verification/rules modules for one subprocess and one output object for two specs; exact mismatches in cmd/expected/cwd/env/Inputs; changed input mid-run; late participant; irrelevant narrative-only edit versus changed policy; unrelated file change inside aggregate Scope versus a real transitive dependency change, with aggregate spec verdict checked separately; incomplete or unknown dependency closure prevents grouping; crash at each write/fsync/rename/journal/marker boundary; identical replay twice and conflicting replay; missing, duplicate and conflicting aggregate rows; unsupported durability; changed Covers or row-to-FR/AC/task attribution without changed command versus unrelated prose in both validators; canonical manifest bytes/digest regardless of input order and rejection by both validators of reordered serialized records, duplicate/missing/extra mappings, or altered participant closure_fp; concurrent rounds; object/manifest/receipt/commit missing, corrupted, transplanted, symlinked, outside root or wrong digest; malformed receipt; pre-existing ordinary evidence remains byte-for-byte unchanged through two later rounds with distinct receipts; each round executes once, for two actual executions; historical caching requires separate approval; both R10 and JSON detect changed row/Scope/Generated/real dependency and accept proven irrelevant prose; legacy evidence still accepted; and `--full` invokes each row. Verify both R10 close and JSON never PASS a broken reference.
- Verify: orchestrator `python -m unittest tests.test_wave_verification tests.test_verify_regressions tests.test_aidd_rules tests.test_aidd_status tests.test_dot_aidd_mirror` -> exit 0; compare both mirror SHA-256 hashes.
- Do NOT: coalesce DB/network without verified proof, share an old result, retain secrets, alter historical evidence, trust user-written isolation flags, or repeat identical tests per spec in eligible round.
- Done when: isolated synthetic fixtures exercise one subprocess and one shared object, invalid paths, corrupt or uncommitted objects/receipts or changed snapshots cannot yield PASS; both validators recompute current policy and closure; two rounds preserve legacy evidence without claiming cross-round caching; every participant event precedes the final committed marker, legacy evidence and full mode remain compatible, and production grouping remains disabled until a real capability check is reviewed and verified. Synthetic proof is not a production provider.
- Open questions: none.

### T-19 — environment proof interface and explicit refusal
**Classify**
- Nature: `REQUIREMENT`
- Kind: LOGIC
**Estimate**
- Agent min: 25
- Human ref hours: 1.25
- Tokens (est): 160k
- Agent role: builder
- Wave: 3
**Detail**
- Size: ~150 changed lines.
- Goal: attest effective local runner inputs and isolation using a production verifier, or decline grouping if unavailable.
- Cites: FR-216, FR-217, AC-239, AC-241.
- Depends on: a proven platform-specific provider; same owner as T-17.
- Read first: plan contracts 3–7, `specs/007-aidd-review-html-close-gate/plan.md` raw fingerprint design.
- Files to change: `skill/scripts/aidd_reuse.py`, adapter mirror and focused provider tests; final platform implementation requires separately approved scope.
- Naming contract: provisional `verify_environment(context) -> proof | unavailable`; freeze proof schema, issuer and revocation before approval.
- Behavior: provider checks actual runner executable, environment and isolation before and after; rejects malformed, self-authored or missing proof and never stores secret values. External DB snapshot requires an independently verifiable identity.
- Tests first: fake and forged provider cases fail, different env/path fails; supported platform capability smoke must demonstrate real enforcement.
- Verify: `python -m unittest tests.test_reuse_planner` plus provider-specific smoke -> exit 0 only where the provider is demonstrably supported.
- Do NOT: turn on cache based on files alone, pretend Docker or a test double is an attestor, or claim unsupported OS has isolation.
- Done when: a real trusted provider is demonstrated and unsupported environments fail closed.
- Open questions: no production trusted provider/environment identity exists yet; resolve design and threat model before enabling.

### T-20 — independent audit carry-over contract
**Classify**
- Nature: `REQUIREMENT`
- Kind: LOGIC
**Estimate**
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 90k
- Agent role: architect
- Wave: 1
**Detail**
- Size: ~150 changed lines.
- Goal: specify conditions for preserving a prior domain audit without rereading unaffected content or treating untrusted events as independent.
- Cites: FR-219, AC-242.
- Depends on: authenticated audit producer and 006/008 compatibility.
- Read first: `specs/006-aidd-phased-audits-attribution/spec.md`, `specs/008-aidd-compact-review-direct-save/amendment-convergence-plan.draft.md`.
- Files to change: amendment artifacts under `specs/006-aidd-phased-audits-attribution/` and `specs/008-aidd-compact-review-direct-save/`, never their current approvals until revised under their own gate.
- Naming contract: a future `unit_audit` event must bind independent origin, unit hash, criteria version, input closure and evidence hash.
- Behavior: unchanged domain/scope may be carried only when source is trusted and all dependencies/evidence remain intact; otherwise audit afresh. No broad stale reset for unrelated changes.
- Tests first: demonstrate failure for forged/missing host event and shared dependency change.
- Verify: `python -m unittest tests.test_incremental_audit` -> exit 0 once the missing producer and that new test module are specified and approved; no full suite duplicated.
- Do NOT: synthesize auditor dispatch, accept legacy text-only assertions as authenticated, or use progress percentages as evidence.
- Done when: separate approved spec and verified producer support incremental audits.
- Open questions: authenticated unit-audit producer does not exist; this task remains blocked until its contract is proven.

### T-21 — coordinated integration and audit
**Classify**
- Nature: `REQUIREMENT`
- Kind: LOGIC
**Estimate**
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 100k
- Agent role: tests
- Wave: 3
**Detail**
- Size: ~150 changed lines.
- Goal: one coordinated round tests the union once and provides evidence for independent audit.
- Cites: FR-214..FR-218, AC-236..AC-243.
- Depends on: T-17 and T-18. T-19 and T-20 remain separate, blocked deliverables and are not prerequisites for the disabled production core or its synthetic tests.
- Read first: `specs/007-aidd-review-html-close-gate/amendment-02-reuse-plan.draft.md` contracts 1–8 and actual executed test outputs.
- Files to change: `tests/test_reuse_planner.py`, `tests/test_wave_verification.py`, `tests/test_verify_regressions.py` and evidence only.
- Naming contract: stable reason codes and `SHARED-RUN` in both text and JSON, no secret output.
- Behavior: count subprocesses; prove separate runs on every difference and no green after mutation/corruption; measure wall time, no duplicate per-spec suite.
- Tests first: suite is the test; capture red failure of representative cases before implementation.
- Verify: `python -m unittest tests.test_reuse_planner tests.test_wave_verification tests.test_verify_regressions tests.test_dot_aidd_mirror` -> exit 0, followed by independent read-only security audit.
- Do NOT: weaken tests, run two heavy suites at once, claim performance savings from fake providers or create DBs.
- Done when: outputs, subprocess counts and limitations are recorded; auditor sees scope and evidence. No production grouping or savings are claimed without a real supported provider.
- Open questions: none.

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-17, T-20 | architect, builder | 15 | 190 | 0.75 |
| 2 | T-18 | builder | 25 | 160 | 1.25 |
| 3 | T-19, T-21 | builder, tests | 25 | 260 | 1.25 |

Total agent time (critical path): 65 min
Total tokens (k): 610

T-17 and T-19 are serial because they share a file; T-20 is independent. T-19 and T-20 remain blocked on genuine host capabilities and cannot be implemented as fictional support. T-21 validates only the disabled core with synthetic fixtures until a real provider is approved. Estimates are tentative and must be reviewed before approval.
