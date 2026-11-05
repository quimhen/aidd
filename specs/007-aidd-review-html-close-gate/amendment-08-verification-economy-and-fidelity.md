# Amendment 08 to spec 007: delegated-work verification economy, DB rounds and batches, approval preflight (minimal slice), measured visual fidelity

Intake: `AMENDMENT` of `specs/007-aidd-review-html-close-gate` (owner of E8/E9 text, R10, `aidd rules check/approve`).
Decided by the owner on 2026-11-04 ("este es un ajuste a la metodología, aplica el cambio en el repo"), with evidence
measured in b1SycLink. Adopts `batch-staging/db-verify-rounds/PROPOSAL.md`. Status: APPLIED to `skill/` and the
`adapters/dot-aidd/` mirror; the installed skill and project bundles are synchronized by the owner (see Pending).

| Code | Requirement | Where | Source |
|---|---|---|---|
| FR-290 | E9(f): on a builder/agent report the orchestrator makes ONE quick targeted check (test not weakened, files exist, diff, at most one narrow run), trusts reported evidence, and repeats the full verification once per round at close; independence comes from closing auditors. Exception: a concrete risk signal. | `skill/AIDD.md` + `skill/SKILL.md` E9 | owner 2026-11-04 |
| FR-291 | E8(e): ONE full DB run per round in ONE designated spec; the others use the narrow grouped form (several prefixes, one invocation) with their own slot and narrow Verification rows; measure first (413 s alone, >600 s parallel, 890 s with three agents; grouped F37 247 s vs ~15 min); `AIDD_VERIFY_TIMEOUT` only for full rows; order/cluster-state dependent tests made hermetic, never weakened; the project DB runner copies from the template into another slot when its work database is busy, else rebuilds from scratch (migrations + seeds), bounded ephemeral overflow. | `skill/AIDD.md` + `skill/SKILL.md` E8 | owner 2026-11-04 |
| FR-292 | Approval preflight (minimal slice of FR-270(1), amendment 07): `aidd rules check <spec>` also runs `check_verification` (the rule of `aidd rules approve`) while `tasks.md` has no `Approved:` line; the orchestrator runs it before asking the owner. The full `--preflight`/`--fix`/question-builder design stays in amendment 07 (NOT implemented). | `skill/scripts/aidd_status.py` `cmd_check`; text in AIDD.md/SKILL.md | evidence: approval refused after the click (b1SycLink 2026-11-04) |
| FR-293 | Visual fidelity is measured against the prototype (same h1, every CTL/COMP present, same columns, skeletons >= prototype); a green unit suite is not fidelity evidence (F38: vitest 258/258, 32/32 states differed). | `skill/AIDD.md` + `skill/SKILL.md`, after "Executed evidence, not textual" | owner 2026-11-04 |

## Verification

| # | Command | Expected | Covers |
|---|---|---|---|
| 1 | `python -m unittest tests.test_cli_rules tests.test_dot_aidd_mirror` | exit 0 | FR-290..FR-293 |

## Pending

- Synchronize projects (owner decision): `python tools/aidd_selective_update.py --help` (selective update tool), then
  update `~/.claude/skills/aidd` and each project's `.aidd/` bundle (b1SycLink) with it.
- Amendment 07 (full preflight) remains a draft.
- Tool candidates from the proposal (not implemented): `--only-tests` already accepts a comma list in b1SycLink's
  runner; `aidd verify` detecting concurrent full rows.
