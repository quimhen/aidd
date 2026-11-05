# Integration of amendments 03 + 04 into spec 007 (2026-11-03)

AIDD intake: AMENDMENT of `specs/007-aidd-review-html-close-gate`. Owner answered YES (2026-11-03) to
integrate; this note prepares the tagged approval. Nothing was approved; no `Approved:` line was written.

## What was merged

- Collision check before editing: no T-22..T-29, FR-220..FR-235 or AC-251..AC-268 existed in spec/plan/tasks.
- `find_spec.py 007 verification reuse progress pending` run first (exit 0, top match 007).
- `spec.md`: new `## Amendment 03/04 (2026-11-03)` with owner quotes, executive summary (03 + 04),
  FR-220..FR-223, AC-251..AC-258, FR-230..FR-235, AC-261..AC-268, out of scope, the 4 owner decisions of 03.
  Verification rows appended to the existing `## Verification` table (only the first such table is
  executed): 03 V-1 -> V-7, 03 V-2 -> V-8, 04 V-1 -> V-9, 04 V-2 -> V-10; the identical 03 V-3 / 04 V-3
  mirror rows merged into one V-11 (Covers T-24, T-28). Literal pipes in FR-235/AC-267 escaped as `\|`.
- `plan.md`: `## Amendment 03/04 (2026-11-03) — naming contract` (constants, functions, files, store paths,
  output strings, test classes and methods exactly as in the drafts) + FR -> file map.
- `tasks.md`: 8 rows T-22..T-29 + 8 per-task blocks (script post-check: all 8 blocks IDENTICAL to the
  drafts except `Wave:` remapped 1/2/3 -> 8/9/10); two conventions paragraphs; waves 8-10; dependency note.
  Two Target cells gained `, same owner as T-16` (T-23) and `, same owner as T-25` (T-29) to clear
  check_spec G6 (shared files), following the existing T-14..T-16 convention.
- Waves (script-computed: time = max, tokens = sum): 8 = T-22, T-26 (15 min, 140k); 9 = T-23, T-25, T-27
  (25 min, 240k); 10 = T-24, T-28, T-29 (5 min, 70k). Totals 142 -> 187 min, 1700k -> 2150k. 24 tasks, 10 waves.

## Check outputs

- `task_precision_check.py --root D:\Fuentes\AIDD` on 007 tasks.md: T-22..T-29 all `PASS (ready)`.
  (File summary: 24 tasks, 12 PASS, 12 FAIL; the FAILs are the pre-existing legacy T-01..T-12, untouched.)
- `check_spec.py specs/007-aidd-review-html-close-gate`: 1 gap, `R6 tasks.md changed after approval
  (hash mismatch) — approval is void` (expected).
- `aidd rules check`: PASS R1 R2 R3 R4 R5 R7 R9 R10 R11 R12 R13 R14; FAIL R6 (same expected hash mismatch).

## Owner approval

New tasks tag (from `aidd review specs/007-aidd-review-html-close-gate --check`): **`[tasks:dcb5f22c]`**.
The existing `review.md` is stale for this hash (STATE=stale, 78/117); `review.html` was not regenerated.

## Needs the owner

- Approve with the tag above (or regenerate the review page and review first); the old 2026-10-31 approval is void.
- Amendment 03 owner decisions 1-4 (spec.md) are still open: without the `charter_gate.py` opt-in and the
  input-cap decision the measured b1SycLink saving is 0.
- Note: T-25 (wave 9) verifies with the mirror test while the `aidd_status.py` mirror is only copied by
  T-24 in wave 10, so that per-task check is red until wave 10 (as in the draft; not changed).
