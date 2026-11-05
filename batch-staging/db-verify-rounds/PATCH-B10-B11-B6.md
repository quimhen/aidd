# PATCH-B10-B11-B6 (amendment 09 backlog B10, B11, B6)

Made on a clean export of HEAD (not on the dirty working tree). Touches only: `skill/scripts/aidd_status.py`,
`skill/scripts/aidd_review.py`, `skill/scripts/check_spec.py` (and the byte-identical mirrors in
`adapters/dot-aidd/scripts/`), `aidd/cli.py` (help text) and the new `tests/test_b10_b11_b6.py`.

## What each tool does
- B10 `aidd rules close <id> --check`: dry run of `rules close`. Same `_close_gaps` (R6/R7, fresh evidence) plus the
  "Yes, close" answer gate, but it lists ALL that is missing (does not stop at the first group), records no event and
  does not clear the active-spec pointer. Exit 0 only if the real close would be accepted now. States that it applies
  the close gates, not those of `aidd rules check`.
- B11 `AIDD_FINGERPRINT_BUDGET` (seconds, default 8; invalid/zero/negative/inf/nan fall back to 8): used for the three
  `ev.code_state(root, scope=scope)` calls of `skill/scripts/aidd_status.py` (start, end, revalidation). The
  "cannot fingerprint" refusal now names the variable. (The "reuse the scan across specs of a round" half of B11 is not
  done.)
- B6 spec-size warning: `WARN_REVIEW_SOURCE_CHARS = 300_000`, `size_warnings()` in `aidd_review.py`; `aidd review` prints
  `warning: <file> is N chars ...` on stderr for a source in (300000, 400000]; `check_spec.py` prints `WARNING:` (not a
  gap, exit code unchanged). The 400 000 refusal is unchanged.

## Apply (from the AIDD repo root; the patch is independent of the uncommitted work, check first)
    git apply --check batch-staging/db-verify-rounds/PATCH-B10-B11-B6.diff
    git apply batch-staging/db-verify-rounds/PATCH-B10-B11-B6.diff
If the working tree already changed `aidd_status.py` near the touched hunks, use `git apply --3way` or `patch -p1`.
Then run the tests below. Not installed anywhere else (`~/.claude/skills/aidd`, project `.aidd/`): sync as usual.
Note: `aidd` CLI uses the installed skill scripts, so `aidd rules close --check` works only after syncing; the new
CLI test sets `AIDD_HOME` to the repo `skill/` for that reason.

## Results (clean copy)
- Baseline before (HEAD): `python -m unittest tests.test_dot_aidd_mirror tests.test_cli_rules tests.test_aidd_status
  tests.test_aidd_review tests.test_check_spec tests.test_verify_regressions` -> 281 tests, OK.
- RED: the new file against HEAD -> 15 tests, 13 failing/erroring (missing feature).
- After (same set + `tests.test_b10_b11_b6`): 296 tests, all OK (the only failure of the first run was the new CLI test
  picking the installed skill; fixed with `AIDD_HOME`; re-run of new + mirror + cli_rules: 42 tests OK).
