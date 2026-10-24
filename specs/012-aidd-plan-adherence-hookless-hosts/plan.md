# Plan — AIDD plan adherence on hosts with no write hook (spec 012)

No screens, no database: the visual and DB sections of the template do not apply (spec.md pipeline route waives steps 0/1/1.5).

## Naming & File Contract (declared once; tasks cite this table)
| Item | Convention |
|---|---|
| Language / style | Python stdlib only, `snake_case` functions and files, 4-space indent, single-quoted strings in `skill/scripts/aidd_*.py` (matches aidd_status.py:1-60); JS in `adapters/opencode/plugins/aidd.js` keeps its camelCase |
| Classes per file | One. Both new scripts are function-only modules |
| New files | `skill/scripts/aidd_next.py`, `skill/scripts/aidd_guard.py`, `tests/test_aidd_next.py`, `tests/test_aidd_guard.py` |
| Mirrored copies (byte-identical) | `adapters/dot-aidd/scripts/aidd_next.py`, `adapters/dot-aidd/scripts/aidd_guard.py` |
| `aidd_next.py` public API | `build_next(spec_dir, root, status=None) -> dict`, `format_next(info) -> str` (<= 30 lines), `main(argv)` (`next [spec_dir] [--write] [--json]`) |
| `aidd_guard.py` public API | `staged_files(root) -> list[str]`, `is_code_file(rel) -> bool`, `evaluate(root, files, status=None) -> list[dict{rule,message,fix}]`, `main(argv)` (`guard commit\|push [--root DIR]`) |
| Hook installer API (in `install_host.py`) | `HostInstaller.install_githooks()`, constants `GITHOOK_MARKER`, `GITHOOK_NAMES = ('pre-commit', 'pre-push')`; new flag `--githooks` |
| Evidence event kind | `guard_override` `{hook:'guard', mode:'warn'\|'off', rules:[...]}` |
| Env var | `AIDD_GUARD=warn\|off` (owner only; read from the process environment) |
| Doctor checks | `D8` git hooks present and call aidd guard; `D9` NEXT.md present/creatable and the "run `aidd next`" line in CORE.md and the Antigravity rule; opencode version line extended with the truthful write-gate message |
| Output files | `.aidd/NEXT.md` (written by `aidd next --write`) |

## Code map (FR -> real code)
| FR | New / edited files | Evidence in the current code |
|---|---|---|
| FR-1201 `aidd next` | NEW `aidd_next.py`; `aidd/cli.py` (new `cmd_next`, `p_next` block, plain `_run("aidd_next.py", ...)` like `cmd_pending`, cli.py:102) | `build_status` returns approval (`tasks.approval`), `verification.status` (none/never-run/stale/failed/passed), `qa_audit`, `why_blocked`, `gate_pointer`, `route` (aidd_status.py:347-405). Step -1..7 derives from artifact presence plus those facts; open `R` violations from `rules.check_spec_dir` (aidd_rules.py:1674), already used by `_why_blocked` (aidd_status.py:431) |
| FR-1202 `guard commit` | NEW `aidd_guard.py`; `cli.py` `cmd_guard` | gate target = `ev.get_gate_spec(root)` (aidd_status.py:398); approval = `st['tasks']['approval']`; R5 chain order via `why_blocked`/`check_spec_dir`; verify = `st['verification']['status']` (`failed`/`stale` block); qa-audit via `rules.check_qa`/`check_content` (aidd_rules.py:1257, 1323) |
| FR-1203 `guard push` | `aidd_guard.py` | same `evaluate`, findings printed as `warn`, exit 0 |
| FR-1204 `--githooks` | `install_host.py` (new method + arg on the `install` subparser, install_host.py:467-475); `cli.py` `p_install` gets `--githooks`, `--host` optional when `--githooks` is alone (cli.py:333-341, `cmd_install` cli.py:107-115) | atomic, link-safe writers exist in `HostInstaller` (`_copy_file`, `_guard_links`, `_save_json`, `is_link`, install_host.py:104-124, 394-423); reuse for hook files |
| FR-1205 plugin shape | `adapters/opencode/plugins/aidd.js` (last line already `export default { id: "aidd", server: AiddPlugin, setup() {} }`, uncommitted per git status); `install_host.py` `install_opencode` (install_host.py:402-423) stops appending the relative `plugin` entry; `aidd_doctor.py` `_d4_opencode` (aidd_doctor.py:303-326) stops FAILing when the entry is absent | installer adds `.opencode/plugins/aidd.js` to `opencode.json` (install_host.py:421) and doctor FAILs without it (aidd_doctor.py:313-314): both change together |
| FR-1206 doctor | `aidd_doctor.py` (`run_host`, aidd_doctor.py:495-505; add `check_d8`, `check_d9`); text edits in `adapters/dot-aidd/CORE.md` (7,072 B, limit 12,288 at aidd_doctor.py:24) section 2 (CORE.md:19) and `adapters/antigravity/rules/aidd.md` (821 B, limit 24,000) | D2/D3 already measure sizes; D1 compares `.aidd/` with shipped `dot-aidd`, so CORE.md edits propagate |
| FR-1207 override | `aidd_guard.py` appends via `ev.append(root, session, kind, **detail)` (aidd_evidence.py:625); `aidd_status.py` `_override_stats` (aidd_status.py:489-495) and `format_global` (aidd_status.py:642-662) also count `guard_override`; `aidd_doctor.py` D6 (aidd_doctor.py:455-478) too | `--no-verify` list: `_derived_facts` (aidd_status.py:824) gets `commits_without_approval` |
| FR-1208 < 3 s | `aidd_guard.py` | see (b) |

## Decisions
**(a) Files.** Two new scripts because `next` (reader, 30-line text) and `guard` (decision, exit code) have different consumers; both are thin over `aidd_status.build_status`, so no new analysis exists. One owner per file. Waves: W1 `aidd_next.py`+test and `aidd_guard.py`+test (disjoint); W2 `install_host.py`, `cli.py`, plugin and doctor (one agent per file); W3 CORE.md/rule text, mirror copies, docs, b1SyncLink install, full suite once.

**(b) Speed (FR-1208).** There is no cached-status file today. `build_status` reads the evidence log and spec files and does not call `find_spec` or the graph rebuild (aidd_status.py:347-405; the graph fact is read from events, :362-367). `guard` therefore: reads staged names with ONE `git diff --cached --name-only` (helper pattern `_git`, aidd_status.py:758, 5 s timeout); returns 0 at once when no code file is staged (AC-1207); builds status for the gate-target spec ONLY (never `_spec_dirs`); passes one `FingerprintOnce` (aidd_status.py:674) so the worktree fingerprint is computed once. A test with 30 fixture specs and a 5,000-name staged list verifies the 3 s budget.

**(c) Portable hook command.** A POSIX `sh` script (Git for Windows runs it with its bundled sh) with a `# aidd-githook` marker line. Body: `if command -v aidd >/dev/null 2>&1; then aidd guard commit; elif [ -f .aidd/scripts/aidd_guard.py ]; then python .aidd/scripts/aidd_guard.py guard commit; fi`. The repo-relative path needs no drive or user (git runs hooks from the work-tree top). Hooks dir = `git -C <root> rev-parse --git-path hooks` (handles worktrees and `core.hooksPath`), resolved against `<root>` when relative. Foreign hook present: append one marked block once (idempotent by marker), never rewrite foreign lines; a foreign file with a non-sh shebang is skipped with a reason.

**(d) Override record.** Same mechanism as `rules_override`: `ev.append(root, session, 'guard_override', hook='guard', mode=..., rules=[...])` into `.aidd/evidence/events.toon` (rule_gate.py:1810-1823). `.aidd/` evidence is protected for agents (`PROTECTED_NAMES`, install_host.py:66), but the guard runs as the user's git process, not through the agent write gate, so the CLI may write it. `AIDD_GUARD` is read from the process environment only (pattern: `_sanitize_env`, aidd_status.py:114).

**(e) Mirror.** Yes for the two new scripts: add to `VERBATIM_SCRIPTS` (tests/test_dot_aidd_mirror.py:57-78) and copy byte-identical to `adapters/dot-aidd/scripts/`, because the hook falls back to `.aidd/scripts/aidd_guard.py` and that imports the mirrored `aidd_status`/`aidd_rules`. `aidd_status.py` is mirrored too, so its `guard_override` edit must be copied. `aidd_doctor.py` and `install_host.py` are not in the mirror (dot-aidd/scripts has neither). `skill/hooks/` is untouched, so the hooks mirror (test_dot_aidd_mirror.py:87-95) is unaffected.

**(f) Packaging.** `setup.py` (`BuildPyWithData`) and `MANIFEST.in` (`graft skill`, `graft adapters`) copy whole trees into `aidd/_data/`, so new scripts ship with no packaging change; `_find_scripts_dir` (cli.py:16-37) finds `_data/skill/scripts`.

## Risks and open questions for the owner
1. A false block stops a commit. Mitigation: guard blocks only when a code file is staged; docs and `specs/` always pass (FR-1202). [Confirmed by owner: "Acepto las cuatro decisiones"] "code file" = everything except `*.md|*.txt|*.toon`, `specs/**`, `docs/**`, `.aidd/**`, `.agents/**`, `.opencode/**`, `.gemini/**`, LICENSE. Owner to confirm the list.
2. Code staged with no gate-target spec: the spec is silent. [Confirmed by owner: "Acepto las cuatro decisiones"] pass with a one-line warning, since blocking would stop every non-AIDD commit.
3. [Proposed — unconfirmed, not part of the owner's four decisions] "verify stale for the staged code" reuses `verification_state` as is (aidd_rules.py:2830-2863).
4. [Confirmed by owner: "Acepto las cuatro decisiones"] `qa-audit.md` "failing row" = a `FAIL` token (case-insensitive) in the verdict column; the rules parser validates evidence rows, not a verdict (aidd_rules.py:1257). This is the AC-1201 case (b1SyncLink S05).
5. The plugin shape is already changed in the working tree; installer and doctor must change in the same PR or a fresh install FAILs D4 (aidd_doctor.py:313-314).
6. `--no-verify` is detected only after the fact. [Proposed — unconfirmed, not part of the owner's four decisions] store the last checked commit as a `guard_seen` event, not a new file.
7. `--githooks` writes into `.git/hooks`, outside `.aidd/`; the writer must refuse a hooks dir that is a link (reuse `_guard_links`).
8. [Confirmed by owner: "Acepto las cuatro decisiones"] If neither `aidd` nor `.aidd/scripts/` exists, the hook exits 0 (fail open, as the plugin does, aidd.js header lines 8-10).
9. An agent can export `AIDD_GUARD=off` in its own shell; the only mitigation is that every use is recorded and shown (FR-1207), the same residual risk as `AIDD_RULES=warn`.
10. Run pytest once at the end (W3), not per task, to avoid Windows/OneDrive file contention.

## Pre-build audit corrections (2026-10-21, auditor af25c04)
11. The guard filters `why_blocked` to R5, R6, a failed verification and a qa-audit FAIL row; R4/R7/R10/R11/R12 never block a commit (aidd_status.py:439 returns more, and the spec does not authorise them). Item 3 narrowed: block on `failed`, and on `stale` only when the staged code changed since the verify (the worktree fingerprint also counts unstaged/untracked files). [Proposed — unconfirmed] shown in the tasks approval.
12. Existing tests assert the relative plugin entry (tests/test_host_install.py:161,184-208; tests/test_host_doctor.py:117-135): rewritten in the same tasks as install_host.py / aidd_doctor.py (T3, T4), or V-2 fails.
13. `install_opencode` stops adding the entry but never removes an existing one; D4 checks the file and accepts the entry present or absent (b1SyncLink and 1.x installs keep working).
14. `guard_seen` / `commits_without_approval` scan at most the last 200 commits; only `guard commit` carries the 3 s budget. Corrected references: `FingerprintOnce` is aidd_rules.py:2601 (use `_fingerprint_once()` at aidd_status.py:674); `build_status` wraps `_build_status` (:340-405); do not call `_derived_facts` from the guard (:842); rule_gate recording is skill/hooks/rule_gate.py:1811-1823.

## Amendment 1 (2026-10-21): defects found by the T-18 verifier on b1SyCLink (owner: "Enmendar y corregir")
15. Which spec is checked: `evaluate` builds an owner map from the open specs' `tasks.md` `Target file` cells (strip any trailing parenthesised note such as `(same owner as T-01)`), matches the staged paths against it, and evaluates every owning open spec; with no owner it falls back to the gate target, and with neither it passes with one warning. "Open" = the spec has a recorded plan/tasks edit and no `spec_closed` event (reuse the open-specs helper the status code already uses, not `build_status`).
16. Speed: the guard stops calling `build_status` (7-10 s on b1SyCLink). Per owning spec it reads only: approval (hash of `tasks.md` vs the `Approved:` line and the recorded `approved` event, as `_why_blocked` does), `verification_state` (aidd_rules.py:2830) and the FAIL rows of `qa-audit.md` (existing parser). It calls no graph code, no `_derived_facts`, no fingerprint of the whole tree: for "stale" it compares the staged files' mtimes with the verification timestamp (already the implemented rule). Budget 3 s measured on D:\Fuentes\b1SyCLink (69 specs, 2.2 MB events log).
17. The b1SyCLink `.aidd/scripts/aidd_guard.py` is missing, so the hook's python fallback does nothing there; reinstalling that `.aidd/` is the owner's decision and out of scope (the global `aidd guard` is what runs).

## Verification traceability
V-1 covers `aidd_next`/`aidd_guard` (new tests); V-2 `test_host_install.py` and `test_host_doctor.py` gain githooks, plugin-shape and D8/D9 cases; V-3 mirror and rule-gate stay green after the two mirrored scripts and the `aidd_status.py` edit; V-4 full suite once.
