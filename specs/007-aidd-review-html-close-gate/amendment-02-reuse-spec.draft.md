# Draft — coordinated verification and evidence reuse

**DRAFT: not approved or executable.** Amendment intake: 007 verification and evidence; 006 audit attribution and 008 unit convergence are dependencies, not duplicated specs. Based on `skill/templates/spec.md`. This draft follows 007 T-13–T-16 and must not weaken their fail-closed behavior.

## Minimum Requirements Checklist (fill before Step 3 starts)

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | AIDD verification and evidence | repo — skill/scripts/aidd_status.py | — |
| New development or modification of something existing? | Modification | repo — specs/007-aidd-review-html-close-gate/spec.md | — |
| Does it involve an external service, API, or integration? | External environments are explicitly excluded from the initial runnable slice unless a verified snapshot provider exists | [Proposed — unconfirmed] | resolve before approval |
| Who is requesting it? (role/profile, not necessarily the name) | Spec owner | [Proposed — unconfirmed] | resolve before approval |
| Dependencies on other modules or active developments? | 007 T-13–T-16; 006 audit attribution; 008 unit convergence | repo — specs/008-aidd-compact-review-direct-save/amendment-convergence-plan.draft.md | — |
| Business objective (1 sentence — what it achieves and why) | Avoid redundant runs and audits without allowing stale or unverifiable evidence to pass | [Proposed — unconfirmed] | resolve before approval |
| Expected visual fidelity level (if there's a mockup): exact \| functional behavior only | No mockup; CLI only | [Proposed — unconfirmed] | resolve before approval |

## Executive summary

- **Objective:** execute a truly identical verification once within a coordinated round and reuse historical evidence only when dependencies and environment are verified.
- **Scope:** round planning, canonical execution context, provenance/evidence integrity, explain-cache; independently authenticated audit carry-over and external-state reuse remain separate gated phases.
- **Cost:** draft estimates below; independent audit and final spec verification are additional.
- **Risks:** omitted transitive inputs, secret exposure, mutable state, false-positive cache hit, untrusted audit origin; fail closed.
- **Open decisions:** actual trusted environment verifier / audit provenance provider has not been identified; no production historical reuse is enabled by this draft alone.

## Functional requirements

| Code | Requirement | Source |
|---|---|---|
| FR-214 | Plan an explicitly opted-in shared observation once per round only when all consumers are known before execution and command, expected result, canonical cwd, effective environment and complete input declarations/snapshots match; otherwise execute separately. | repo — skill/scripts/aidd_status.py |
| FR-215 | A shared observation is one real run, not a historical cache hit: record one immutable evidence object, a canonical group manifest and a committed receipt per eligible consumer; validate relevant verification-policy projections and consumer snapshots before and after. Reject PASS for every participant on changed/unreadable inputs, invalid evidence or incomplete publication; a proven unrelated narrative edit alone does not invalidate the observation. | [Proposed — unconfirmed] |
| FR-216 | Local-only eligibility requires a trustworthy runner/provider to prove no undeclared filesystem/network/external dependence and capture the execution context. An approved label, environment JSON, elapsed TTL, matching hash, or process exit alone is not proof. Unknown => one execution per row. | repo — specs/007-aidd-review-html-close-gate/spec.md |
| FR-217 | A future historical hit additionally needs a verified matching environment/snapshot identity, input graph closure, command/cwd/expected and intact evidence; DB/network is ineligible until a separately proven provider validates the actual reset/snapshot and external dependencies. `--full` always executes. | [Proposed — unconfirmed] |
| FR-218 | `explain-cache` (read only) reports group decision, precise mismatch/unknown, relevant input changes, evidence identity and timing without printing secret values or the hashes of low-entropy secrets. | [Proposed — unconfirmed] |
| FR-219 | Audit carry-over requires an authentic independent auditor event, fixed scope, criteria version, input closure and intact evidence; only unchanged domains can carry forward. If host attestation/closure unavailable, record historical evidence but require new review. | repo — specs/008-aidd-compact-review-direct-save/amendment-convergence-plan.draft.md |

## Acceptance criteria

| Code | Scenario | Expected |
|---|---|---|
| AC-236 | Two opted-in consumers, identical complete context and a verified local provider | One actual subprocess, one evidence object, two traceable consumer references; result and timestamps equal. |
| AC-237 | Same command but different cwd, expected, input list or bytes, effective env, runner version or provider | Separate executions; explanation names difference without printing secrets. |
| AC-238 | Consumer input, manifest, source, cwd or effective context changes during execution; evidence damaged or a participant joins late | No shared PASS emitted; affected rows marked stale or executed after a stable new observation, without silently reusing prior output. |
| AC-239 | Default run, missing proof, forged manifest/flag, DB/network without verified snapshot, unknown dependency or provider error | No shared or historical reuse; execute independently and explain reason. |
| AC-240 | Full or forced mode; failing command, timeout, zero tests, mutated evidence | No green reuse; full runs every row; fail/timeout remain honest. |
| AC-241 | Historical source scope/inputs/env/snapshot identical and independently verified | Eligible only under a separately approved historical phase; otherwise log reason and execute. |
| AC-242 | Auditor identity, criteria version or relevant dependency changes, or hook evidence absent | No carry-over for affected scope; independent audit required. |
| AC-243 | Two specs consume same evidence object | Evidence is stored once; each receipt proves membership in a canonical manifest and a final commit marker. Deleting/corrupting or transplanting an object, manifest, receipt or marker prevents every affected green verdict. A crash before commit yields no PASS; rebuilding derived indexes after commit does not rerun the subprocess. |
| AC-244 | Narrative prose changes outside the relevant verification-policy projection during a run | The observation remains eligible only if the parser proves the change irrelevant; a changed row, Scope, Generated, selected wave mapping, dependency or unknown influence makes it stale. |
| AC-245 | A file within the aggregate spec Scope changes but is demonstrably outside a row's complete closure; then an actual row dependency changes | The unrelated file does not invalidate the shared observation in that round, though the separate aggregate spec gate may mark the overall spec stale. The real dependency change invalidates the affected observation; unknown or incomplete closure prevents grouping. A later verify executes again unless independently approved historical reuse applies. |
| AC-246 | An ordinary legacy evidence file exists and two later shared rounds use the same row | Each shared round creates a different in-spec receipt path and immutable object reference; the legacy file, prior receipts, events and checksums remain unchanged. The two invocations execute two actual subprocesses unless separately approved historical reuse applies. |
| AC-248 | Replay publication after crashes at each durability boundary, twice with identical events and once with conflicting payload | Identical journal replay is idempotent, conflict is rejected, incomplete rows cannot produce aggregate PASS, and unsupported durability fails closed. |
| AC-250 | Manifest participants are reordered, duplicated or altered, including a participant's closure_fp | Canonical construction yields identical bytes and digest regardless of input order; validators reject noncanonical or duplicate records, altered closure or mismatched mappings, and verify each participant against its own current policy_fp and closure_fp. |
| AC-249 | Change normalized Covers or row-to-FR/AC/task attribution after commit without changing command; change unrelated prose separately | Both R10 and JSON invalidate changed or unknown attribution, while proven unrelated prose does not invalidate the observation. |
| AC-247 | Query R10 and JSON after changing the participant row, Scope, Generated, a real dependency, or unrelated prose | Both validators recompute policy_fp and closure_fp and fail closed on missing, unreadable, incomplete or mismatched dependencies; irrelevant prose that provably leaves the projections unchanged does not stale the observation. |

## Verification

The exact executable rows will be integrated in the approved plan, without adding duplicate full-suite rows. Synthetic temporary repositories only; no custom temporary databases. A future real provider smoke test must be isolated, opt-in, capability-checked, and not depend on a live DB.

## Out of scope

Code changes before approval, production implementation of an unverified trusted provider, automatic approval/audit fabrication, modifying `.aidd/` manually, treating SHA alone as attestation, or unsafe interpretation of shell command text. Current implementation explicitly disables reuse; this document does not claim existing savings.
