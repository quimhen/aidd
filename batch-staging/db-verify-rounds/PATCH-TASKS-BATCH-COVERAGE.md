# PATCH-TASKS-BATCH-COVERAGE: a spec may split its tasks over `tasks.md` + `tasks-<name>.md` batch files, and every check covers all of them

Diff against a clean export of HEAD with `PATCH-B10-B11-B6.diff` and `PATCH-B12-B5.diff` already applied (see "Base").

## Chosen way: A (extend the hash and the checks to `tasks.md` + `tasks-<name>.md`), not B (units)
Why A, measured on the code:
- B (`aidd_units.py`, `amendments/<unit>/manifest.json`, `aidd rules approve --unit`, `unit_approval_hash`) is a SECOND approval system
  (own manifest, own hash, own consent, own audit/review path: `aidd_unit_audit`, `aidd_unit_review`, 12+ test modules). Today
  no spec uses it, and the gate that blocks code (`rule_gate._target_violation`, `stop_gate`, `aidd_guard._light_status`) still asks for the
  legacy `tasks.md` approval. Using it would mean migrating F42 (and F36/F37/F38) to unit manifests AND teaching the code gate to
  require unit approvals: a much larger and riskier change than widening one function.
- A keeps ONE approval line (in `tasks.md`), ONE hash, ONE gate. The batch files only add content to that hash.

## Rule (name and order)
- Batch file = a regular file in the spec folder whose name fully matches `tasks-[A-Za-z0-9_-]+\.md` (`tasks-amendment-03.md`,
  `tasks-proposal-d08.md`). `tasks-detail.draft.md`, `tasks.draft.md`, `amendment-02-tasks.md`, `tasks-x.txt` are NOT batches (a dot in the stem or
  another name = draft/ignored).
- Combined tasks text = `tasks.md` text + for each batch in sorted file-name order (plain code-point sort) `\n<!-- aidd-batch: <name> -->\n` + the batch text.
  `rules.with_batches(spec_dir, base_text)` / `rules.read_tasks(spec_dir)` build it; `rules.split_tasks_segments(text)` splits it back.
- The hash is the SAME function as before (`approval_hash`, over the approval projection: `Approved:` lines and Status/Tracker/PR-ref cells neutral, CRLF neutral)
  applied to the combined text. Without batch files `with_batches` returns the base text object unchanged, so the hash is byte-for-byte the old one.
- The only `Approved:` line lives in `tasks.md`; `aidd rules approve` still writes it there (hash computed over the combined text). An `Approved:` line
  inside a batch counts as a second line: approval void (R6 "several Approved lines").

## Coverage: what reads the batches now
- R6 hash/validity: `aidd_rules.check_spec_dir` (R6 mismatch/void), `approval_valid`, `aidd rules approve` (check + tag + hash + review state), `aidd_status` (build_status approval, light status, `approval_tag`, review wait, mtimes), `aidd_guard` (`_light_status`, task owners/targets), `aidd_progress` (stages and task rows), closing-audit tag (`[tasks:<h8>]`, `required_domains`, `suggest_domains`, `verification_scope`, `uncovered_domains` hash), `aidd_tools` (targets/cross-spec).
- Code gate / hooks: `rule_gate._target_violation` (code edits blocked when any tasks file changed after approval), `_approval_gate` (hash of current vs would-be edit over combined text), `_tasks_last_change` (batch mtimes and `spec_edit` events), `mark_code_edit` (records `spec_edit` for batch files; the `hash` of `tasks.md` is the combined one), `stop_gate`.
- R1 (wave totals etc.): `_check_tasks` checks EACH file on its own (own `## Waves` table, own `Total agent time`, own token totals); batch messages are prefixed `[<file>]`; a `### T-nn` block in two files is an R1 violation.
- `check_spec.py`: reads the combined text (`read_tasks`), and its `aidd_rules.check_spec_dir`/`check_content` calls go through the same per-file R1.
- `aidd review`: `_load_sources` returns the combined `tasks.md` (items, headings and digest cover the batches); the size limit stays per FILE (`_oversize` splits the combined text back: 400 000 chars each, the error names the file); `sources_digest` and `[tasks:<h8>]` use the combined approval hash.
- `task_precision_check` lives in the client project (`tools/task_precision_check.py`, not in this repo): it already accepts the `tasks*.md` glob (stated in the F42 batch file), so no change here.
- Not covered on purpose: writing a batch file is not content-validated at write time by the hook (only `aidd rules check` / `check_spec` / the approval void it); the `--full` headings page lists the combined text under `tasks.md`.

## Tests (first, measured RED)
New `tests/test_tasks_batch_coverage.py` (20 tests): batch-name rule, compat pin (spec without batches: `with_batches` is the identical text and the hash equals the historical projection hash), hash changes with a new/edited batch, deterministic order independent of creation order, CRLF neutral, approve-valid then void after a batch edit, `Approved:` inside a batch, R1 per file (total, missing waves, duplicate task), status helper, review per-file size limit, digest/tag, check_spec.
- RED (before the change, same tests): 17 of 20 fail/error (3 pass by chance: good-batch R1, `Approved:` in a batch, tag without batches).
- GREEN (after): the 20 new tests pass. Regression set (mirror, cli_rules, b10_b11_b6, b12_b5, aidd_rules, aidd_rules_r10, aidd_status, check_spec, aidd_review, review_items, review_state, aidd_guard, aidd_progress, aidd_tools, unit_approval_gate, unit_hash): before the change 796 tests, after 816 (796 + 20 new). When the two runs went in parallel each showed 2 different `test_aidd_rules_r10` errors (shared-state flakiness under parallel load, in both the before and after copies); `test_aidd_rules_r10` alone passes in both (55 OK before; 75 OK together with the new file after). No other failure.

## Compatibility measured on the client project (read-only simulation, `sim_client.py`)
- 65 specs with `tasks.md`; hash OLD code == hash NEW code for 63 of them (all specs without batch files, e.g. `P01-Payrol-Foundation`: `c1b501a5c7a9` before and after = its recorded approval).
- Changed (they have a batch file): `F42-eDoc-AR-AP-Payments` (`19c48cb9b0a1` -> `440389e478dd`; its recorded `5aeba7de3db8` was already stale against the old hash) and `F36-eDoc-Purchasing` (`7ab7e3cbf43c` valid before -> `2084599bf5d6`, because `tasks-proposal-d08.md` matches the batch name).

## Client files to re-seal after installing (do not touch now)
- `specs/F42-eDoc-AR-AP-Payments`: new hash covers `tasks-amendment-03.md`; re-run the approval flow (`aidd rules approve`) once the owner approves the batch (its `tasks.md` approval was already out of date).
- `specs/F36-eDoc-Purchasing`: `tasks-proposal-d08.md` becomes part of the approval and flips the valid approval to void. Either rename the proposal (e.g. `proposal-d08-tasks.md`, outside the pattern) before installing, or re-approve F36 with it included. Decide before installing.
- F37/F38 (`amendment-02-tasks.md`) are not matched; to put them under the new coverage rename them `tasks-amendment-02.md` (then they are part of the hash and need re-approval).
- After install, `aidd review` of F37/F38/F36 only passes the size limit once their task text is split into files each under 400 000 chars; F36 alone has 856k so it needs at least 3 files.

## Base (acceptance of the two accepted patches)
- `PATCH-B10-B11-B6.diff` applied clean.
- `PATCH-B12-B5.diff` did NOT apply clean over B10: its `aidd/cli.py` hunk is a whole-file rewrite (LF) that conflicts with (a) the CRLF line endings of `aidd/cli.py` in HEAD and (b) the help line of `rules` that B10 changed (`close <spec_id> [--check]`). The other 6 files of B12/B5 applied clean (`--exclude=aidd/cli.py`). For the base copy `aidd/cli.py` was taken as B12's resulting content with B10's help line kept and CRLF restored. Base tests: `tests.test_dot_aidd_mirror tests.test_cli_rules tests.test_b10_b11_b6 tests.test_b12_b5` = 60 OK. This patch does not touch `aidd/cli.py`.

## Apply
    cd D:/Fuentes/AIDD   (after PATCH-B10-B11-B6 and PATCH-B12-B5, the latter with the cli.py caveat above)
    git apply --check --ignore-whitespace batch-staging/db-verify-rounds/PATCH-TASKS-BATCH-COVERAGE.diff
    git apply --ignore-whitespace batch-staging/db-verify-rounds/PATCH-TASKS-BATCH-COVERAGE.diff
Touches: `skill/scripts/{aidd_rules,aidd_status,aidd_review,check_spec,aidd_guard,aidd_progress,aidd_tools}.py`, `skill/hooks/{rule_gate,mark_code_edit,stop_gate}.py`,
their byte-identical copies in `adapters/dot-aidd/` (all but `stop_gate`, which has no copy there), and the new `tests/test_tasks_batch_coverage.py`.
Nothing installed, nothing committed. Not done: docs (`skill/AIDD.md`, `CORE.md`) do not describe the rule yet.
