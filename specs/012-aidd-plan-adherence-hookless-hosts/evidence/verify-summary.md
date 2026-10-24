# Spec 012 verification summary (T-18, verifier)

Date: 2026-10-21. Repo: D:\Fuentes\AIDD, branch feat/009-aidd-host-parity. All builders done before the run. Commands ran one at a time.

## Verification table

| V | Command | Result | Exit | Raw |
|---|---|---|---|---|
| V-1 | python -m pytest tests/test_aidd_next.py tests/test_aidd_guard.py -q | 44 passed, 20 subtests passed (59.9 s) | 0 | evidence/verify-v1-v3.txt |
| V-2 | python -m pytest tests/test_host_install.py tests/test_host_doctor.py -q | 72 passed, 1 skipped (test_host_install.py:625 "sh not available"), 23 subtests (108.9 s) | 0 | evidence/verify-v1-v3.txt |
| V-3 | python -m pytest tests/test_dot_aidd_mirror.py tests/test_rule_gate.py -q | 273 passed, 39 subtests (58.6 s) | 0 | evidence/verify-v1-v3.txt |
| V-4 | python tests/run_parallel.py | 50 modules / 346 units, 0 failed, 218 s wall, 8 workers; 4 classes flaky under load but passed alone (test_aidd_rules_r10 TestR10/TestR11/TestR10LegacyUnaffectedBySpec007, test_host_gates TestS3UnknownTools) | 0 | evidence/verify-v4.txt |

No failures. The remaining T-03 items and the D9 doctor cases pass (inside V-1 and V-2). `aidd status` writing guard_seen events broke no existing test (V-4 green).

## Real-data check (b1SyCLink, owner said yes for this step only)

Raw output: evidence/verify-b1sycLink.txt.

- The global `aidd` (it runs D:\Fuentes\AIDD\aidd) has `aidd guard`. b1SyCLink's `.aidd/scripts/aidd_guard.py` is **missing**, so the hook's python fallback does nothing there. Not reinstalled, as instructed.
- `aidd install --githooks`: created pre-commit and pre-push (there were no earlier hooks). Hooks dir = `.git/hooks`. A second run gave "0 written, 2 unchanged" (idempotent).
- AC-1201 with code staged (`Selection/supabase/migrations/3097_sl_hire_selection_fix.sql`): `aidd guard commit` gave **exit 0 with no output in 10.1 s**, not the expected exit 1. `aidd guard push` gave exit 0 in 1.7 s. The file was unstaged right away and the index is empty again.
  - Cause: the gate pointer targets `F38-eDoc-Import-Costing`, which is clean. The guard only checks the gate-target spec, so S05 code passes.
  - When `evaluate()` was given the S05 status (pointer left unchanged), it returned the expected findings: R6 (approval void, fix `aidd review S05-...`) and qa-audit (13 FAIL rows, fix `... aidd verify S05-...`). So the decision logic is correct, but choosing the spec from the gate pointer misses this case.
  - Speed: the real repo took 10.1 s against the 3 s goal. build_status alone took 6.9 s for F38 and 9.8 s for S05.
- Docs-only case (nothing staged): `aidd guard commit` gave exit 0 in 1.2 s, a pass as expected.

## Defects / notes back

| # | Owner file | Finding | One-line fix |
|---|---|---|---|
| 1 | skill/scripts/aidd_guard.py | AC-1201 not met on real data: staged S05 code passes because only the gate-pointer spec (F38) is evaluated | Also evaluate the open spec(s) that own the staged paths (or every open spec with R6/FAIL), not only `get_gate_spec` |
| 2 | skill/scripts/aidd_guard.py | `aidd guard commit` takes 10 s on b1SyCLink (goal: under 3 s) because a full `build_status` runs every time | Use a light approval/verification/qa read (no fingerprint, no R7/R10 derivation) on the guard path |
| 3 | (b1SyCLink install, owner action) | `.aidd/scripts/aidd_guard.py` is absent, so the hook fallback does nothing without a global aidd | Owner reruns the .aidd install in b1SyCLink when they choose to |
| 4 | tests/test_host_install.py:625 | One test is skipped on this machine ("sh not available") | None needed; it runs on hosts that have sh |

## Execution evidence

| Code | Kind | Evidence | Verified by |
|---|---|---|---|
| V-1 | command-output | specs/012-aidd-plan-adherence-hookless-hosts/evidence/verify-v1-v3.txt | agent |
| V-2 | command-output | specs/012-aidd-plan-adherence-hookless-hosts/evidence/verify-v1-v3.txt | agent |
| V-3 | command-output | specs/012-aidd-plan-adherence-hookless-hosts/evidence/verify-v1-v3.txt | agent |
| V-4 | command-output | specs/012-aidd-plan-adherence-hookless-hosts/evidence/verify-v4.txt | agent |
| AC-1201 | command-output | specs/012-aidd-plan-adherence-hookless-hosts/evidence/verify-b1sycLink.txt (FAIL on real data: exit 0 because the gate pointer is F38; docs-only half passes) | agent |
| AC-1204 | command-output | specs/012-aidd-plan-adherence-hookless-hosts/evidence/verify-b1sycLink.txt (idempotent re-run; the foreign-hook append case is covered only by V-2, since b1SyCLink had no hooks) | agent |
| AC-1205 | command-output | specs/012-aidd-plan-adherence-hookless-hosts/evidence/verify-b1sycLink.txt (`git rev-parse --git-path hooks` = .git/hooks, hooks written there) | agent |
| AC-1202, AC-1203, AC-1206, AC-1207 | command-output | covered by V-1/V-2 test runs only (evidence/verify-v1-v3.txt); AC-1207's 3 s budget is not met on the real b1SyCLink repo (10.1 s, finding #2) | agent |
