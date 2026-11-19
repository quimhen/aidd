# Spec — Native future output targets

Risk: high

AIDD intake: AMENDMENT — existing007 unit registration and impact contract; no duplicate spec.
Wave AIDD-FUTURE-TARGETS, owner /root. Proposed unit future-targets, versionv1. No code approved yet.

## Minimum Requirements Checklist

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | Native amendment migration and impact snapshots | repo — skill/scripts/aidd_units.py:564 | — |
| New development or modification of something existing? | Correct rejection of genuinely absent future output targets | repo — skill/scripts/aidd_units.py:619 | — |
| Does it involve an external service, API, or integration? | No runtime external service; official release after verification | repo — pyproject.toml:7 | — |
| Who is requesting it? (role/profile, not necessarily the name) | AIDD owner via coordinator; exact task approval remains required | repo — batch-staging/future-targets-independent-plan.md:1 | — |
| Dependencies on other modules or active developments? | Existing migration/approval/build/audit contracts and generated mirror | repo — skill/scripts/aidd_rules.py:1390 | — |
| Business objective (1 sentence — what it achieves and why) | Register and approve future files without fake placeholders or weaker executed proof | repo — batch-staging/future-targets-independent-plan.md:9 | — |
| Expected visual fidelity level (if there's a mockup): exact or functional behavior only | CLI/backend only, no visual surface or mockup | repo — skill/scripts/aidd_units.py:564 | — |

## Executive summary

- **Objective:** Permit genuine future target absence during preparation without relaxing required inputs or executed evidence.
- **Scope:** Canonical units module, generated mirror, two existing test modules and release version0.5.2.
- **Cost:** Six tasks;26 total agent minutes,18 critical-path minutes;184k tokens;3 waves.
- **Risks:** Absence confused with unsafe path or missing input; race or stale evidence. Explicit state and strict executed snapshots prevent these.
- **Open decisions:** Exact unit task approval only. No unresolved implementation branch.

## Pipeline route

| Step | Status | Reason | Confirmation |
|---|---|---|---|
| -1 | run | Native graphs/find_spec inspected007 and existing units; none owns requested targets | |
| 0 | run | No GUI/mockup; inspect native CLI contract | |
| 1 | run | Map preparation and failure states | |
| 1.5 | run | Plan/apply/review/build/audit flow defined | |
| 2 | run | Observed defect and independent plan constrain change | |
| 3 | run | Exact function and file boundaries in plan.md | |
| 4 | run | Six concrete tasks awaiting official unit consent | |

## Requirements

| FR | Requirement | Source |
|---|---|---|
| FR-1190 | migration_plan/apply binds genuine candidate-target absence explicitly; existing files retain content fingerprints; missing strict roles or parent scope still fail. No placeholder is created. | repo — batch-staging/future-targets-independent-plan.md:15 |
| FR-1191 | Plan/apply and snapshot rechecks detect creation, deletion, mutation or unsafe/case/link/ancestor substitution; no success receipt on failure. Same filename in any strict role remains strict across the required closure. | repo — batch-staging/future-targets-independent-plan.md:16 |
| FR-1192 | Read-only plural impact planning permits typed initial target absence; singular executed audit snapshots remain strict. Approval still hashes target names, not output contents; creating output changes impact, not consent. | repo — skill/scripts/aidd_rules.py:1390 |
| FR-1193 | Migration→readiness/review→native consent→build preflight is reachable before creating future files; missing executed targets cannot produce current audit evidence. Preserve ownership, inputs, visual assets, base/parent seals and legacy behavior. | repo — batch-staging/future-targets-independent-plan.md:24 |

## Acceptance cases

| Case | Real data (id) | Expected | Edge? |
|---|---|---|---|
| Future output | Temporary unit fixture: absent leaf and nested output | Native plan/apply succeeds; output remains absent | no |
| Required file absent | Temporary fixture: target also declared input or visual asset | Registration and impact reject | yes |
| Filesystem substitution | Temporary fixture: output appears, changes type or linked ancestor changes | Reviewed digest rejected; no success receipt | yes |
| Output lifecycle | Temporary fixture: absent output becomes an empty file, then populated | Impact changes; strict executed audit requires actual output | yes |
| Approval before implementation | Native temporary fixture using existing test helpers | Review, genuine fixture consent and build preflight remain possible before output creation | yes |

## Acceptance criteria

Registration accepts missing leaf and nested output directory but creates only native manifest/receipt.
ABSENT differs from empty-file hash. Every strict role and parent remains mandatory. Both plan/apply
checkpoints reject changed reviewed state and clean only this invocation's exact created manifest.
Read-only impact reports missing output deterministically; strict audit cannot materialize it.
Creating output invalidates impact-bound audit evidence while legitimate consent/build scope stays valid.
No change to executed verification reuse, fiscal project files, protected adapters or approval records.

## Verification

| # | Command | Covers | Expected |
|---|---|---|---|
| 1 | python -m unittest tests.test_aidd_unit_migration tests.test_aidd_unit_impact tests.test_aidd_unit_build_gate tests.test_aidd_unit_review_package tests.test_aidd_unit_consent tests.test_aidd_unit_audit_incremental tests.test_aidd_readiness tests.test_aidd_check_scope | FR-1190, FR-1191, FR-1192, FR-1193 | exit 0 |
| 2 | python -c "from pathlib import Path; import aidd,tomllib; assert Path('skill/scripts/aidd_units.py').read_bytes()==Path('adapters/dot-aidd/scripts/aidd_units.py').read_bytes(); assert aidd.__version__==tomllib.loads(Path('pyproject.toml').read_text(encoding='utf-8'))['project']['version']=='0.5.2'" | FR-1190, FR-1193 | exit 0 |

Only coordinator executes tests/build/release. Builders perform static checks and report no behavioral PASS.
Approval is native owner consent to this exact package; no Approved line or evidence is authored here.

## Capacity & test budget

| Item | Budget |
|---|---|
| Environment | Windows host, 15.7 GiB RAM; temporary filesystem fixtures; Python 3.12 |
| Heavy concurrency | One root-owned runner; no DB, Docker or application build |
| Verification row 1 | 180 s target; one coordinated union after RED and source freeze |
| Verification row 2 | 10 s target; byte equality and version metadata only |
| Dataset | Minimal temporary unit fixtures; no production data or volume seed |

These are preparation budgets, not measured performance results. Builders execute no suites.
