# PATCH-B12-B5: `aidd close-ledger` (B12) and `aidd red` (B5)

Diff against a clean export of HEAD (`git archive HEAD`); independent of PATCH-B10-B11-B6 (not applied, not needed).

## Apply
    cd D:/Fuentes/AIDD
    git apply --check --ignore-whitespace batch-staging/db-verify-rounds/PATCH-B12-B5.diff
    git apply --ignore-whitespace batch-staging/db-verify-rounds/PATCH-B12-B5.diff

Touches: `aidd/cli.py` (passthrough in `main()` + 2 subparsers), new `skill/scripts/aidd_close_ledger.py` and
`skill/scripts/aidd_red.py` (+ byte-identical copies in `adapters/dot-aidd/scripts/`), `tests/test_dot_aidd_mirror.py`
(both scripts added to `VERBATIM_SCRIPTS`), new `tests/test_b12_b5.py` (18 tests).

## B12 `aidd close-ledger <spec_dir> [--check-fresh] [--json] [--domains a,b] [--verify-hash hex]`
Read only, stdout. Heading `CLOSING AUDIT [domains: ...] [tasks:<h8>] [verify:<v8>]`; table built from
`## Verification` + `evidence/verify-<id>.txt`; with `--check-fresh` STALE/FALTA marks and `LISTO PARA AUDITAR`.
Domains: `--domains`, else closing-audit.md heading, else `aidd_rules.required_domains(spec)` (same rule as
`rules close`). tasks hash: `Approved:` line. verify hash: `--verify-hash`, else `ev.latest_verify_run`. Exit 2 without spec.md.

## B5 `aidd red <test-cmd...> --task T-nn [--spec id]` / `aidd red --check <spec>`
Runs the command from the project root (`--task/--spec/--timeout` anywhere, or `--` before the command). Exit != 0
writes `specs/<id>/evidence/red-T-nn.txt` (command, exit, first_failure, timestamp, test_file, test_file_sha1, 60 lines
of output) from the CLI process; exit 0 prints `NO-RED: el test pasó, no hay RED`, writes nothing, returns 1.
`--check`: lists receipts (flags a changed test file), `MISSING: T-nn` for `Agent role: tests` tasks without receipt
(exit 1), `EXEMPT` for a task block with a `RED: exempt (<reason>)` line. No git-based "new file" detection (not reliable).

## Results (in the clean copy)
- Before: `tests.test_dot_aidd_mirror tests.test_cli_rules` 27 tests OK; new tests 18 (16 errors/failures at RED).
- After: those 27 OK + `tests.test_b12_b5` 18 OK = 45 OK (re-checked on a fresh HEAD export with the patch applied).
- CLI tests set `AIDD_HOME=<repo>/skill` because `aidd.cli` prefers the installed `~/.claude/skills/aidd`.
- Not done: the new commands are not documented in `skill/SKILL.md`/`AIDD.md`; nothing installed, nothing committed.
