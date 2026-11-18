# Bounded AIDD verification security overlay â€” proposal

AIDD intake: AMENDMENT â€” Fast Lane â€” Spec007 existing verification safety convergence. New owner exception pending. No UI or application behavior changes. Scope and exact behavior are in security-boundary-plan.md; independent R5-security-plan-review-v2.md PASS does not authorize code.

## Verification

Scope: skill/scripts/aidd_rules.py, skill/scripts/aidd_amendment_verify.py, skill/scripts/aidd_round.py, skill/scripts/aidd_status.py, skill/scripts/aidd_evidence.py, tests/test_verify_round.py, tests/test_verify_round_reuse.py, tests/test_verify_amendment.py

| # | Command | Expected | Codes | Inputs | Tier |
|---|---|---|---|---|---|
| V-4B1 | `python -m unittest discover -s tests -p test_historical_reuse_security.py -v` | exit 0 | FR-205, FR-207, FR-450..458 | `skill/scripts/aidd_rules.py`, `skill/scripts/aidd_amendment_verify.py`, `skill/scripts/aidd_round.py`, `skill/scripts/aidd_status.py`, `skill/scripts/aidd_evidence.py`, `tests/test_verify_round.py`, `tests/test_verify_round_reuse.py`, `tests/test_verify_amendment.py` | functional |
| V-4B2 | `python -m unittest discover -s tests -p test_dry_run_identity_security.py -v` | exit 0 | FR-205, FR-207, FR-450..458 | `skill/scripts/aidd_rules.py`, `skill/scripts/aidd_amendment_verify.py`, `skill/scripts/aidd_round.py`, `skill/scripts/aidd_status.py`, `skill/scripts/aidd_evidence.py`, `tests/test_verify_round.py`, `tests/test_verify_round_reuse.py`, `tests/test_verify_amendment.py` | functional |
| V-4B3 | `python -m unittest discover -s tests -p test_verify_round*.py -v` | exit 0 | FR-205, FR-207, FR-450..458 | `skill/scripts/aidd_rules.py`, `skill/scripts/aidd_amendment_verify.py`, `skill/scripts/aidd_round.py`, `skill/scripts/aidd_status.py`, `skill/scripts/aidd_evidence.py`, `tests/test_verify_round.py`, `tests/test_verify_round_reuse.py`, `tests/test_verify_amendment.py` | functional |
| V-4B4 | `python -m unittest discover -s tests -p test_verify_amendment.py -v` | exit 0 | FR-205, FR-207, FR-450..458 | `skill/scripts/aidd_rules.py`, `skill/scripts/aidd_amendment_verify.py`, `skill/scripts/aidd_round.py`, `skill/scripts/aidd_status.py`, `skill/scripts/aidd_evidence.py`, `tests/test_verify_round.py`, `tests/test_verify_round_reuse.py`, `tests/test_verify_amendment.py` | functional |
| V-4B5 | `python -m unittest discover -s tests -p test_amendment_truncated_command.py -v` | exit 0 | FR-205, FR-207, FR-450..458 | `skill/scripts/aidd_rules.py`, `skill/scripts/aidd_amendment_verify.py`, `skill/scripts/aidd_round.py`, `skill/scripts/aidd_status.py`, `skill/scripts/aidd_evidence.py`, `tests/test_verify_round.py`, `tests/test_verify_round_reuse.py`, `tests/test_verify_amendment.py` | functional |
| V-4B6 | `python -m unittest tests.test_aidd_rules.TestVerificationGaps tests.test_aidd_rules.TestVerificationState tests.test_aidd_rules.TestFingerprintOnce tests.test_wave_verification.WaveVerificationTests tests.test_wave_verification.WaveEndToEnd.test_multi_spec_wave_runs_shared_check_once_and_preserves_coverage tests.test_wave_verification.WaveEndToEnd.test_multi_spec_wave_does_not_reuse_undeclared_external_checks -v` | exit 0 | FR-205, FR-207, FR-450..458 | `skill/scripts/aidd_rules.py`, `skill/scripts/aidd_amendment_verify.py`, `skill/scripts/aidd_round.py`, `skill/scripts/aidd_status.py`, `skill/scripts/aidd_evidence.py`, `tests/test_verify_round.py`, `tests/test_verify_round_reuse.py`, `tests/test_verify_amendment.py` | functional |

New test modules are authored only after authorization, before source fixes. All commands run in the isolated runtime; command6 uses root-qualified tests namespace modules with root on PYTHONPATH; verify each imported module resolves to the exact isolated source (shadowing is failure), and only isolated skill/scripts import paths. Nonzero collection required. No business DB/browser/build suite or123/48 replay. This is a planned verification table, not evidence of execution.

## Capacity & test budget

RAM: 15.68 GB
Heavy runs at a time: 1
Round budget: 900 s
Not verified: proposed targeted isolated tests; no runtime throughput or DB cache safety claim is made from plan lint.

| # | Tier | Est. s | Budget s | Data scale | Scale justification |
|---|---|---|---|---|---|
| V-4B1 | functional | 60 | 300 | temporary files and selected unit fixtures only | Existing measured affected suite durations inform bounded estimates; actual elapsed time will be recorded. |
| V-4B2 | functional | 60 | 300 | temporary files and selected unit fixtures only | Existing measured affected suite durations inform bounded estimates; actual elapsed time will be recorded. |
| V-4B3 | functional | 60 | 300 | temporary files and selected unit fixtures only | Existing measured affected suite durations inform bounded estimates; actual elapsed time will be recorded. |
| V-4B4 | functional | 60 | 300 | temporary files and selected unit fixtures only | Existing measured affected suite durations inform bounded estimates; actual elapsed time will be recorded. |
| V-4B5 | functional | 60 | 300 | temporary files and selected unit fixtures only | Existing measured affected suite durations inform bounded estimates; actual elapsed time will be recorded. |
| V-4B6 | functional | 60 | 300 | temporary files and selected unit fixtures only | Existing measured affected suite durations inform bounded estimates; actual elapsed time will be recorded. |

## Pipeline route

| Step | Status | Reason | Confirmation |
|---|---|---|---|
| -1 | run | Existing Spec007 findings and native graph examined; this is bounded security convergence. | R5-security-plan-review-v2.md |
| 0 | waived | Backend-only verification kernel; no visual surface. | user — "Autorizar corrección de seguridad" |
| 1 | waived | Backend-only verification kernel; no mockup surface. | user — "Autorizar corrección de seguridad" |
| 1.5 | waived | Backend-only verification kernel; no visual prototype. | user — "Autorizar corrección de seguridad" |
| 2 | run | Exact behavior and boundaries documented. | security-boundary-plan.md |
| 3 | run | Bounded task plan prepared; no source execution yet. | security-boundary-tasks.md |
| 4 | run | Independent plan audit PASS, new owner authorization pending. | R5-security-plan-review-v2.md |

## Minimum Requirements Checklist

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| What changes? | Dry-run identity suppression; hermetic-only historical proof with final sink checks; raw Git hash algorithm. | user — "Autorizar corrección de seguridad" | Stop |
| What stays gated? | Real owner consent, prior evidence integrity, Inputs, environment, original integration and installation. | user — "Autorizar corrección de seguridad" | Stop |
| How is execution verified? | Six targeted isolated commands, real RED/GREEN, no DB/broad suites, independent audit. | user — "Autorizar corrección de seguridad" | Stop |
| Is new scope authorized? | Actual bounded owner exception received; isolated tests first, no original integration or installation. | user — "Autorizar corrección de seguridad" | Do not implement |

## Actual bounded owner decision

user — "Autorizar corrección de seguridad"

Native callback `call_b794c9b285a84cf7a4a322165505f640`; task hash `4e4fde48cb47`. This answers the explicitly stated backend-only visual waivers and checklist scope. Test-first isolated implementation is authorized; original/installed integration and owner unit seals remain separate. No Approved line or historical audit event is fabricated.
