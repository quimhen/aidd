# INSTALL-BATCH: PATCH-B12-B5 + PATCH-TASKS-BATCH-COVERAGE (on top of portal + B10/B11/B6)

Nothing here is installed yet. The owner runs the installer with `!` (agents cannot: hook R9).

## What is installed
Starting point (measured 2026-11-05): `~/.claude/skills/aidd` and `D:/Fuentes/b1SycLink/.aidd` = HEAD of AIDD + the delivery of 2026-11-04 22:56
(`aidd_review.py`, `aidd_status.py`, `check_spec.py`, `templates/review.html` of portal + B10/B11/B6). The pip package `aidd-cli` (`aidd` command) still has the HEAD `cli.py`.

Adds, from one combined tree (copy of HEAD + portal + B10/B11/B6 + B12/B5 + batch-coverage):
- Skill (12 files): `hooks/{mark_code_edit,rule_gate,stop_gate}.py`, `scripts/{aidd_close_ledger(new),aidd_guard,aidd_progress,aidd_red(new),aidd_review,aidd_rules,aidd_status,aidd_tools,check_spec}.py`.
- Project `.aidd` (11 files, same minus `stop_gate.py`, which `.aidd` does not have).
- Package `site-packages/aidd/cli.py` (+ its RECORD row): the `aidd` command learns `close-ledger` and `red`; keeps the B10 help line of `rules`.
- `templates/review.html` is already installed equal (40788c2176), only verified.
NOT touched: `.aidd/memory`, `evidence`, `gate_spec`, `active_spec`, `graphs`, `calibration.toon`, `sqlcheck-cache.json`, `.aidd/scripts/graph_explorer.py`
(differs from HEAD, project-owned), `.aidd/templates/visual-flow.md`, anything under `specs/`, `CORE.md`, `providers/`, `*.bak` of the skill.

## Combined tree and how `cli.py` was resolved
`C:/Users/jquimis/AppData/Local/Temp/claude/496965ba541d9601/b04babae-8d68-44cd-bec6-541c2de69378/scratchpad/combined-batch/tree` (`git archive HEAD`, then the 4 diffs in order portal, B10, B12/B5, batch).
B12/B5's `aidd/cli.py` hunk (whole-file rewrite) was NOT applied; its only real changes (checked with difflib against its own "-" side: 2 pure insertions)
were inserted by hand into the B10 `cli.py`: the `close-ledger` and `red` sub-parsers before `verify`, and the `argv[0] in ("close-ledger","red")` dispatch before `review`.
B10's help line `close <spec_id> [--check]` is kept. Line endings: `git archive` on this Windows checkout (core.autocrlf=true) writes CRLF; the tree was re-normalised
to the committed blobs (LF) so installed bytes match what git distributes (the selective-update tool is CRLF-neutral anyway).

## Order (all in `INSTALL-COMMANDS.sh`, copy at `C:/Users/jquimis/install-batch-coverage.sh`)
0. preflight `inst_check.py before`: each touched file must be in a known state (HEAD or today's measured) else it stops.
1. timestamped backup in `~/aidd-backup/pre-batch-coverage-<ts>/` (whole skill, project scripts/hooks/templates, package `aidd/`, `RECORD`).
2. plans with `tools/aidd_selective_update.py` (`plan` for skill and project; `package-plan --cli` for `cli.py`+RECORD); the backups are the baseline.
3. ONE journaled `apply` of the three plans.
4. verification: `inst_check.py after` (sha256 installed == tree), `diff -q` per file, `.aidd` own folders still present.
5. `aidd --help | grep -E "close-ledger|red"` and `sim_hash.py` (read only) old code (backup) vs new code (installed) on the client specs.
6. OPTIONAL, commented, OWNER DECISION: `mv .../F36-eDoc-Purchasing/tasks-proposal-d08.md .../proposal-d08.draft.md`.

## Hash simulation (measured before installing, old = installed skill, new = combined tree)
65 specs with `tasks.md`; 63 identical. P01 `c1b501a5c7a9` stays; F37 `b27d68844c20` and F40 `91b72e559a09` unchanged (no batch files);
F42 `19c48cb9b0a1` -> `440389e478dd` (batch `tasks-amendment-03.md`; its recorded `5aeba7de3db8` was already stale; re-approve after the owner approves the batch).
F36 `7ab7e3cbf43c` (valid) -> `2084599bf5d6` because `tasks-proposal-d08.md` matches `tasks-<name>.md`: its approval would become VOID. Do step 6 (rename) to avoid it.
References to `tasks-proposal-d08` inside F36: 1 (`tasks-d08-final.draft.md` line 5, a draft; not changed).

## Tests (combined tree, each module run alone, sequentially)
See the final report / `combined-batch/tests.log`.

## Rollback
`python D:/Fuentes/AIDD/tools/aidd_selective_update.py recover --journal ~/aidd-backup/pre-batch-coverage-<ts>/journal` restores exactly the bytes of the transaction
(skill, project, `cli.py`, `RECORD`) and removes the 2 new scripts. Fallback by plain copy (only if recover refuses) is at the end of the script:
`cp -r $BK/skill/. $SK/`, `cp -r $BK/project/{scripts,hooks}/. $PR/...`, `cp $BK/site-aidd/cli.py $SITE/cli.py`, `cp $BK/dist-info/RECORD $DIST/RECORD`.
If F36 was renamed: `mv proposal-d08.draft.md tasks-proposal-d08.md`.

## Rehearsal done
`combined-batch/sandbox_plan.py` ran plan + apply + verify + recover on COPIES in the scratchpad (nothing real touched): all green, RECORD row updated, sandbox `cli.py --help` lists the new commands.
The real script was only syntax-checked (`bash -n`), never run.
