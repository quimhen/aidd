# Verification summary — spec 010 (T-04)

Executed 2026-10-14 with `aidd verify specs/010-aidd-shell-guard-speed` (verify hash `d66c2577`, PASSED 3/3 rows, 195 s wall).

| Row | Command | Result | Evidence file |
|---|---|---|---|
| V-1 | pytest tests/test_rule_gate_shell_speed.py | PASS (11 tests, 422 subtests) | evidence/verify-V-1.txt |
| V-2 | pytest tests/test_rule_gate.py tests/test_host_gates.py tests/test_dot_aidd_mirror.py | PASS | evidence/verify-V-2.txt |
| V-3 | python tests/run_parallel.py (full suite, once) | PASS | evidence/verify-V-3.txt |

## What the equivalence test proves

The new guard and the previous one (pinned at commit `3cf5fcc`) return the same (blocked, message) for 51 hand-written commands, 300 seeded generated commands (padded words, quoted fragments, globs, `bash -c` nesting, `..`, backslashes, 8.3 names, bare names from `specs/<id>`, `.gemini` and `.opencode` working directories) and bare names that are junctions or symlinks to protected folders. The 264 existing `test_rule_gate.py` tests pass unchanged.

## Timings (before: profile of the previous guard; after: this change)

| Padded command (plain words after `echo`, then a redirect into a spec file) | Before | After |
|---|---|---|
| 250 words | 1147 ms | 31 ms |
| 500 words | 2220 ms | 2 ms |
| 1000 words (about 2 KB) | 4389 ms | 6 ms |
| 2000 words (about 4 KB) | 8448 ms | 12 ms |
| 12 KB / 400 KB | timed out at 15 s (spec 009) | under 2 s / under 5 s asserted by V-1 |

Caveat: the profile script calls the inner function directly, so its caches carry over between sizes (only the first line starts empty). The in-process tests of V-1 clear the memo before each call and assert the thresholds.

## Found while testing (pre-existing, not introduced here)

A write through a FILE symlink to a protected file (`echo x > lnk`, with `lnk` pointing at `specs/001-x/tasks.md`) is NOT blocked, by the previous guard or by this one; a write through a FOLDER link (junction or directory symlink, `jd/tasks.md`) is blocked. The pre-build audit assumed both were blocked. Recorded as an open exception.

## NOT verified

The real OpenCode padded-command probe (task T-04 activity 2) was not re-run after this change.
