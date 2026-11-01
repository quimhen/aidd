# DRAFT — Unit verification, audit carry-over and consolidated close

DRAFT ONLY. New host authentication and environment attestation are not assumed. These tasks do not authorize implementation or approval.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-361 | FR-360, FR-363 | `skill/scripts/aidd_status.py` | LOGIC | | | No DB, deploy or manual consent |
| T-362 | FR-361, FR-363 | `skill/scripts/aidd_rules.py` | LOGIC | | | No DB, deploy or manual consent |
| T-360 | FR-362 | `skill/scripts/aidd_status.py` | LOGIC | | | No DB, deploy or manual consent |
| T-363 | FR-360, FR-361, FR-362, FR-363 | `tests/test_aidd_unit_convergence.py` | LOGIC | | | No DB, deploy or manual consent |

## Per-task detail
### T-361 — Execute selected unit checks
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC
- Size: ~150 changed lines; split into another reviewed task if exceeded.
**Estimate**
- Agent min: 20
- Human ref hours: 1
- Tokens (est): 95k
- Agent role: builder
- Model tier: high
**Detail**
- **Goal:** Execute selected unit checks.
- **Cites:** FR-360, FR-363
- **Depends on:** core T-350..T-354 and 007 T-13..T-16
- **Read first:** `skill/scripts/aidd_status.py:1769`, `skill/scripts/aidd_rules.py:2755`, `specs/008-aidd-compact-review-direct-save/amendment-units-plan.draft.md`.
- **Files to change:** `skill/scripts/aidd_status.py`, `tests/test_aidd_unit_verify.py`; adapter mirror: `adapters/dot-aidd/scripts/aidd_status.py`. When adapter mirror is not `none`, use scripted copy and hash post-check.
- **Naming contract:** Extend `cmd_verify` with optional `unit_id=None`; parse `aidd verify <spec> --unit <id>` without changing no-unit signatures. The result event is `unit_verify_run` with spec, unit_id, full unit digest, verify table hash, rows, output evidence hashes, scope and algorithm version.
- **Behaviour:** Load only the registered in-unit checks.md and current approved full digest; execute declared rows with existing timeout/evidence handling, never use REUSED without separately verified environment, record `unit_verify_run`; never produce a spec-wide verify_run.
- **Tests first:** Invalid/missing/draft unit refuses; only selected rows execute; unrelated spec output unchanged; same command without verified environment executes twice; --full executes; tampered evidence fails closed.
- **Verify:** `python -m unittest tests.test_aidd_unit_verify` -> exit 0; orchestrator also runs `python -m unittest tests.test_dot_aidd_mirror` -> exit 0 after mirrors.
- **Do NOT:** fake owner/auditor events, weaken checks, permit cache hits based only on a manifest flag, change unlisted files, create a database or deploy.
- **Done when:** target cases and exact tests pass; logs saved, independent audit performed and legacy behavior remains unchanged.
- **Open questions:** none

### T-362 — Check independent unit-audit validity
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC
- Size: ~150 changed lines; split into another reviewed task if exceeded.
**Estimate**
- Agent min: 20
- Human ref hours: 1
- Tokens (est): 95k
- Agent role: builder
- Model tier: high
**Detail**
- **Goal:** Check independent unit-audit validity.
- **Cites:** FR-361, FR-363
- **Depends on:** core T-350..T-354 and 007 T-13..T-16
- **Read first:** `skill/scripts/aidd_status.py:1769`, `skill/scripts/aidd_rules.py:2755`, `specs/008-aidd-compact-review-direct-save/amendment-units-plan.draft.md`.
- **Files to change:** `skill/scripts/aidd_rules.py`, `tests/test_aidd_unit_audit.py`; adapter mirror: `adapters/dot-aidd/scripts/aidd_rules.py`. When adapter mirror is not `none`, use scripted copy and hash post-check.
- **Naming contract:** Expose `unit_audit_gaps(root: Path, spec_id: str, unit_id: str, digest: str) -> list[str]`; consume only independently recorded `unit_audit` evidence and its declared dependencies.
- **Behaviour:** Require real auditor event, exact unit and digest, expected domain and rule version, input/evidence hashes and separately verified environment; an absent verifier, unstructured legacy audit, stale shared dependency or unproven source returns a gap. Do not mint or alter audits.
- **Tests first:** Unrelated explicitly disjoint file leaves a proven audit current; changed shared input, modified evidence, same-owner auditor, missing event or unknown environment fails closed; legacy checks remain unchanged.
- **Verify:** `python -m unittest tests.test_aidd_unit_audit` -> exit 0; orchestrator also runs `python -m unittest tests.test_dot_aidd_mirror` -> exit 0 after mirrors.
- **Do NOT:** fake owner/auditor events, weaken checks, permit cache hits based only on a manifest flag, change unlisted files, create a database or deploy.
- **Done when:** target cases and exact tests pass; logs saved, independent audit performed and legacy behavior remains unchanged.
- **Open questions:** The trusted unit-scoped auditor evidence producer is not yet defined; do not infer `unit_audit` events or implement this phase until the recorder and host provenance contract are reviewed.

### T-360 — Validate and close the consolidated unit set
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC
- Size: ~150 changed lines; split into another reviewed task if exceeded.
**Estimate**
- Agent min: 20
- Human ref hours: 1
- Tokens (est): 95k
- Agent role: builder
- Model tier: high
**Detail**
- **Goal:** Validate and close the consolidated unit set.
- **Cites:** FR-362
- **Depends on:** T-361, T-362
- **Read first:** `skill/scripts/aidd_status.py:1769`, `skill/scripts/aidd_rules.py:2755`, `specs/008-aidd-compact-review-direct-save/amendment-units-plan.draft.md`.
- **Files to change:** `skill/scripts/aidd_status.py`, `tests/test_aidd_unit_close.py`; adapter mirror: `adapters/dot-aidd/scripts/aidd_status.py`. When adapter mirror is not `none`, use scripted copy and hash post-check.
- **Naming contract:** Extend `cmd_close(spec_arg)` without changing its public signature; resolve unit manifests and require a current owner close event tagged `[spec:<id>]`.
- **Behaviour:** For a unit-enabled spec check every declared unit and parent is approved with fresh digest, unit verification has passed with intact evidence, all required independent domains pass, and actual owner close consent exists. If any is missing print the unit and reason; do not auto-close, approve, deploy or synthesize event. For legacy specs use existing branch.
- **Tests first:** One unapproved draft blocks; one stale dependency, missing audit or absent owner consent blocks; all valid plus owner consent closes once; legacy close unchanged.
- **Verify:** `python -m unittest tests.test_aidd_unit_close` -> exit 0; orchestrator also runs `python -m unittest tests.test_dot_aidd_mirror` -> exit 0 after mirrors.
- **Do NOT:** fake owner/auditor events, weaken checks, permit cache hits based only on a manifest flag, change unlisted files, create a database or deploy.
- **Done when:** target cases and exact tests pass; logs saved, independent audit performed and legacy behavior remains unchanged.
- **Open questions:** The trusted unit-scoped auditor evidence producer is not yet defined; do not infer `unit_audit` events or implement this phase until the recorder and host provenance contract are reviewed.

### T-363 — Prove mixed legacy and unit lifecycle
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC
- Size: ~150 changed lines; split into another reviewed task if exceeded.
**Estimate**
- Agent min: 25
- Human ref hours: 1.25
- Tokens (est): 100k
- Agent role: tests
- Model tier: high
**Detail**
- **Goal:** Prove mixed legacy and unit lifecycle.
- **Cites:** FR-360, FR-361, FR-362, FR-363
- **Depends on:** T-360, T-361, T-362
- **Read first:** `skill/scripts/aidd_status.py:1769`, `skill/scripts/aidd_rules.py:2755`, `specs/008-aidd-compact-review-direct-save/amendment-units-plan.draft.md`.
- **Files to change:** `tests/test_aidd_unit_convergence.py`, `tests/test_aidd_unit_convergence.py`; adapter mirror: none. When adapter mirror is not `none`, use scripted copy and hash post-check.
- **Naming contract:** Use unittest `TestUnitConvergence` with isolated temporary repositories, synthetic code and an injected trusted-event fixture.
- **Behaviour:** Exercise two units, overlapping shared dependency, real output file hashes, stale screenshot, missing owner event and legacy spec; prove no generated source file is accepted as owner event. No actual DB, network, deploy, UI or browser.
- **Tests first:** Unit checks do not imply spec close; changing shared input invalidates relevant unit/audit; absent environment blocks cache hits; no owner event blocks close; legacy behavior preserved.
- **Verify:** `python -m unittest tests.test_aidd_unit_convergence` -> exit 0; orchestrator also runs `python -m unittest tests.test_dot_aidd_mirror` -> exit 0 after mirrors.
- **Do NOT:** fake owner/auditor events, weaken checks, permit cache hits based only on a manifest flag, change unlisted files, create a database or deploy.
- **Done when:** target cases and exact tests pass; logs saved, independent audit performed and legacy behavior remains unchanged.
- **Open questions:** The trusted unit-scoped auditor evidence producer is not yet defined; do not infer `unit_audit` events or implement this phase until the recorder and host provenance contract are reviewed.

## Waves
| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-361 | builder | 20 | 95 | 1.0 |
| 2 | T-360, T-362 | builder | 20 | 190 | 1.0 |
| 3 | T-363 | tests | 25 | 100 | 1.25 |

Total agent time (critical path): 65 min
Total tokens (k): 385

## Approval gate
Separate review and explicit owner approval of these final tasks is required. A trusted environment verifier, if ever added, needs a separate approved contract.
