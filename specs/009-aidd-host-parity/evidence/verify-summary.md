# Verification summary — spec 009 (T-12)

Executed 2026-10-13 with `aidd verify specs/009-aidd-host-parity` (verify hash `ca40f194`, PASSED 5/5 rows, 201 s wall).

| Row | Command | Result | Evidence file |
|---|---|---|---|
| V-1 | pytest tests/test_host_install.py | PASS | evidence/verify-V-1.txt |
| V-2 | pytest tests/test_host_gates.py | PASS | evidence/verify-V-2.txt |
| V-3 | pytest tests/test_host_doctor.py | PASS | evidence/verify-V-3.txt |
| V-4 | pytest tests/test_aidd_status.py tests/test_dot_aidd_mirror.py | PASS | evidence/verify-V-4.txt |
| V-5 | python tests/run_parallel.py (full suite, once) | PASS | evidence/verify-V-5.txt |

## Integration fixes found while verifying (applied before the run)

- `tests/test_host_install.py`: asserted the word `skipped` anywhere in the output, but the installer's summary line says `0 skipped`; now asserts that no file line starts with `skipped`.
- `tests/test_host_gates.py`: read `path` from the event top level; the evidence row keeps it under `detail.path`.
- `skill/scripts/aidd_doctor.py` (D5): the fixture spec was never "open" (no recorded plan/tasks edit), so the dry-run exited 0; it now replays those two edits through the adapter's `post` phase first. D5 now proves the gate blocks an unapproved code write end to end.

## Fix batch after the first closing audit (verdict was PASS WITH EXCEPTIONS)

Applied, with tests, before the second verification: S1 (a write of AIDD_RULES / AIDD_TESTING / AIDD_EVIDENCE_DIR / AIDD_SESSION_ID into any `.env*` file is blocked and `.gemini/.env` is protected), S2 (D5 resolves `python` from PATH and fails when it is missing; the OpenCode plugin warns once), S3 (a write-like tool name outside the known list is gated: `write|edit|patch|replace|create|append|insert|save|delete|remove|move|rename`), P1 (the OpenCode plugin filters by tool name in JS before spawning Python), S6 (session id sanitized), F3 (D3 fix text never suggests `--force` over the owner's GEMINI.md), F4 (the aidd hook entry gets its own group), F5 (host-neutral override wording), FR-913 (guard test for the quote wording). Two test/contract slips found by running the batch: the D3 test rejected the literal `--force` inside "do not use --force", and `create_file` was not matched by the first pattern (now it is).

## Partial coverage kept as an exception

- AC-006: owner approval on a Gemini/OpenCode host is exercised with a recorded tagged answer (the typed-consent route), not with the real review page (`aidd review` + `--wait`); the review-page path itself is `not-verified` here and is covered by the existing review tests of spec 008.
- Open low findings left as exceptions: S4 (a new plugin file under `.opencode/plugins/` can run at the next start and rewrite the gate; `aidd doctor` D4 detects it afterwards), S5 (shell protection is lexical, same as R9 on Claude Code).

## Real-binary runs, 2026-10-14 (after the close)

- **OpenCode 1.18.30: VERIFIED with a model session** in a scratch project installed with `aidd install --host opencode` and an unapproved open spec. (1) The `write` tool call on `src/app.py` was BLOCKED by the plugin through the real host: the model received the full R6 message, `src/app.py` was not created. This confirms the tool name `write`, the argument `filePath`, that `throw new Error(stderr)` in `tool.execute.before` blocks, and that the message reaches the model verbatim. (2) A shell command appending to `.opencode/plugins/aidd.js` was BLOCKED (R9 + FR-911) and the plugin stayed byte-identical. A third command (a shell write of a code file) was not conclusive: the model's own quoting error made it fail before reaching the gate, so the documented "shell edits of code files are not gated" limit stays unverified in a real run.
- **Gemini CLI 0.42.0: NOT verifiable on this machine.** Headless runs fail before any tool call: `IneligibleTierError: This client is no longer supported for Gemini Code Assist for individuals ... migrate to the Antigravity suite` (the free personal tier was retired), so no model session can start without an API key or a Vertex project. It also needs a trusted folder in headless mode (`GEMINI_CLI_TRUST_WORKSPACE=true` or `--skip-trust`); in an untrusted folder the project `.gemini/settings.json` hooks may not load, so the gate could be inactive there (not confirmed). The hook contract itself (exit 2 blocks, matcher, event JSON) rests on the public docs and on the unit/integration tests.
- **Finding:** the "Gemini" that was used on b1SycLink was Antigravity (`.antigravitycli`, `.agents/skills`), not Gemini CLI. In that project `.agents/skills/aidd` is a SYMLINK to the repo's `skill/` folder, so the host loads the 70 KB Claude `SKILL.md` (truncated by the host) instead of `CORE.md`. Antigravity has no documented hook mechanism found in public docs; its skills folder is `.agents/skills`, rules are capped at 12,000 characters. A dedicated Antigravity adapter is a follow-up, not covered by spec 009.

## NOT verified (R10: not-verified, status PARTIAL)

Nothing here was run against the real Gemini CLI or OpenCode binaries: both were found installed (gemini 0.42.0, opencode 1.18.30) but running them needs an authenticated model session, which was not started without the owner's go-ahead. The unit and integration tests drive `host_adapter.py` and the plugin with host-shaped events written from the vendors' public docs.

Manual test script for the owner (about 5 minutes, per host):

1. `aidd install --host gemini <scratch-project>` (and `--host opencode` in another scratch project); then `aidd doctor --host <h> --root <scratch-project>` must print PASS for D1-D5.
2. In the scratch project create `specs/001-x/{spec.md,plan.md,tasks.md}` with `Approved: PENDING` in tasks.md.
3. Start the host in the scratch project and ask it: "create src/app.py with print('hi')". Expected: the host reports a block that mentions R6 / approval; `src/app.py` does not exist.
4. Confirm the Gemini hook command resolves from the project root (the installer writes `python .aidd/hooks/host_adapter.py gemini pre`); if the host runs hooks from another directory the command must use `$GEMINI_PROJECT_DIR`.
5. On OpenCode confirm the block message reaches the model (the plugin throws `Error(stderr)`), and that `edit` and `write` arguments are named `filePath` / `oldString` / `newString` / `content`.
6. Approve the spec the owner way (`aidd review specs/001-x`, `--wait`, then `aidd rules approve specs/001-x`) and repeat step 3: the write must now succeed.

Known limits (documented in adapters/README.md): shell edits of code files are not gated (same as Claude Code); an OpenCode `patch` is gated by path only, not by content.
