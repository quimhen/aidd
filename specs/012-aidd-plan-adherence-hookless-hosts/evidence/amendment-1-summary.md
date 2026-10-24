# Amendment 1 — verification summary (T-22)

Verifier: tests agent (T-22), 2026-10-21. No source, test or b1SyCLink file was edited; nothing was committed or pushed.

## Part 1 — AIDD repo (branch feat/009-aidd-host-parity)

| Command | Result |
|---|---|
| `python -m pytest tests/test_aidd_guard.py tests/test_aidd_next.py -q --no-header -p no:cacheprovider` | 51 passed, 20 subtests passed in 128.26s |
| `python -m pytest tests/test_host_install.py tests/test_host_doctor.py tests/test_dot_aidd_mirror.py -q --no-header -p no:cacheprovider` | 82 passed, 28 subtests passed in 262.76s |
| `cmp skill/scripts/aidd_guard.py adapters/dot-aidd/scripts/aidd_guard.py` | identical (no output, exit 0) |
| `python tests/run_parallel.py` (full suite, once) | 50 modules / 347 units, 1 failed, 562s wall, 8 workers |

Full-suite notes:
- Flaky under load, passed on the runner's own solo rerun: `test_aidd_rules_r10.TestR10`, `test_host_gates.TestS3UnknownTools`, `test_rule_gate.TestModesAndRobustness`.
- The only failure was `tests.test_rule_gate_shell_speed.TestRuleGateShellSpeed.test_400kb_padded_blocked_under_5s` (`AssertionError: 14.947 not less than 10.0`). This is a timing check, and the 8 workers were loading the machine at the time. Rerun alone, `python -m pytest tests/test_rule_gate_shell_speed.py -q` gave 11 passed, 422 subtests passed in 63.95s. This is load flakiness, not a defect. Owner file: `tests/test_rule_gate_shell_speed.py`. Optional fix: add it to the runner's list of tests rerun alone when flaky.

## Part 2 — b1SyCLink (HEAD 86514d6, branch with upstream origin/feat/edoc-specs-f12-f26, AIDD_GUARD unset)

| Step | Output |
|---|---|
| (a) `git diff --cached --name-only` before | empty |
| (b) `git add Selection/supabase/tests/s05_hire.test.sql` | staged (blob 4af04a2…) |
| (c) `aidd guard commit` | exit 1 in **2.03 s**: `BLOCKED R6 — spec S05-Select-Offer-Selection-Hire (owner of the staged code) has no valid tasks approval (approval void: tasks.md changed after approval). -> fix: aidd review S05-…, then aidd rules approve S05-…`; `BLOCKED qa-audit — specs/S05-Select-Offer-Selection-Hire/qa-audit.md has 13 row(s) with a FAIL verdict (V-1, V-2, security (+10 more)). -> fix: … then aidd verify S05-…`; `commit blocked (2 finding(s))` |
| (c) `aidd guard push` | exit 0 in **0.89 s**, no output. Push reads the outgoing commits (`@{upstream}...HEAD`), not the index, and this branch has no unpushed commits, so there are no warnings. That is the designed behaviour. |
| (d) `git restore --staged …` | `git diff --cached --name-only` empty; `git status --short` shows ` M Selection/supabase/tests/s05_hire.test.sql`; blob hash unchanged (4af04a2…) |
| (e) `aidd guard commit` with nothing staged | exit 0 in **1.59 s** |
| Hooks | `.git/hooks/pre-commit` and `.git/hooks/pre-push` both still contain `# aidd-githook` on line 2 |

The stage, guard and unstage sequence ran twice. The first run timed with `bc`, which is not installed, so it gave the same exits but no seconds. The second run used Python `time.perf_counter`. The index was empty after both runs.

## R10 evidence rows

| AC code | kind | evidence path | agent |
|---|---|---|---|
| AC-1201 | command-output | specs/012-aidd-plan-adherence-hookless-hosts/evidence/amendment-1-summary.md | tests (T-22) |
| AC-1208 | command-output | specs/012-aidd-plan-adherence-hookless-hosts/evidence/amendment-1-summary.md | tests (T-22) |

## Verdict

- AC-1208: **PASS** on real data. Exit 1 names S05 with the R6 and qa-audit (13 FAIL) findings and the fix commands, in 2.03 s (under 3 s), and the file was unstaged afterwards.
- AC-1201: **PASS** on real data for the blocking clause. Exit 1 names the failing qa-audit verification and the fix. The empty-index commit passes (1.59 s). The "only `specs/**/*.md` staged" variant was not staged in b1SyCLink because that was out of the approved scope; the guard unit tests cover it.
