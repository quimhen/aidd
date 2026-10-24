# Spec — AIDD plan adherence on hosts with no write hook (opencode 2.x, Antigravity): git guard + NEXT.md

Produced during Step 2 (Align). Intake: NEW SPEC, a follow-up of 009 (host parity) and 011 (Antigravity adapter), not an amendment: it adds a host-agnostic enforcement layer. Evidence measured on this machine (2026-10-20/21):

- opencode 2.0.32 (`opencode2`) loads a plugin only if its default export is `{ id, setup | effect }`; the legacy `server` shape of 1.x is rejected (log `err_eb0b0ec0`). Its plugin context (`@opencode-ai/plugin/dist/v2`) has agent, aisdk, catalog, command, integration, plugin, reference and skill hooks and **no** `tool.execute.before/after`; the string `tool.execute` is absent from the v2 binary. A v2 plugin therefore cannot block a write: the `rule_gate` never runs there.
- b1SyncLink (opencode and Antigravity sessions): S05 was committed as "partial 85%" while its own `qa-audit.md` said FAIL (9 pgTAP files failing, 10 SECURITY DEFINER functions over the allow-list); `aidd status` there lists 10+ open eDoc specs with a valid approval, a stale verification, no closing auditor and no `qa-audit.md`; `STATE.md` is days behind git (`specs/S05-Select-Offer-Selection-Hire/qa-audit.md:8`).

Risk: medium
<!-- medium: new hooks on the owner's git repos (a wrong block could stop commits); it does not write to databases or touch money. -->

## Minimum Requirements Checklist (fill before Step 3 starts)

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | AIDD cross-host layer: `aidd/cli.py`, `skill/scripts/aidd_status.py`, `skill/scripts/install_host.py`, `skill/scripts/aidd_doctor.py`, `adapters/dot-aidd/` and `adapters/opencode/` | user — "Omitir pasos visuales y confirmo alcance" | → Step 2 align question |
| New development or modification of something existing? | New commands (`aidd next`, `aidd guard`, `aidd install --githooks`) on top of the 009/011 layer; modifies the opencode plugin template and `aidd doctor` | user — "Omitir pasos visuales y confirmo alcance" | → Step 2 align question |
| Does it involve an external service, API, or integration? | Yes: git hooks (`pre-commit`, `pre-push`) and the opencode 2.x plugin API (`{id, setup}`), contract observed in the installed SDK | repo — specs/009-aidd-host-parity/qa-audit.md:1 | → Step 2 align question |
| Who is requesting it? (role/profile, not necessarily the name) | The project owner, who works with opencode2 and Antigravity in b1SyncLink | user — "Omitir pasos visuales y confirmo alcance" | → Step 2 align question |
| Dependencies on other modules or active developments? | Specs 009, 010, 011 (adapter, installer, doctor, protected files); `aidd rules`, `aidd status`, `aidd verify` as the single source of truth | repo — specs/011-aidd-antigravity-adapter/spec.md:3 | → Step 2 align question |
| Business objective (1 sentence — what it achieves and why) | On hosts without a write hook the agent must still follow the approved plan: no commit of out-of-plan or failing work, and a one-screen "next action" it re-reads every step | user — "Omitir pasos visuales y confirmo alcance" | → Step 2 align question |
| Expected visual fidelity level (if there's a mockup): exact \| functional behavior only | Not applicable: no screens | user — "Omitir pasos visuales y confirmo alcance" | → Step 2 align question |

## Executive summary

- **Objective:** Make plan adherence host-agnostic: a mechanical `NEXT.md` the agent follows and a git guard that refuses to commit work that breaks the approved plan, because opencode 2.x has no write hook.
- **Scope:** `aidd next`, `aidd guard commit|push`, `aidd install --githooks`, doctor checks, the opencode `{id, setup}` plugin shape, `CORE.md` and rule text; installed in b1SyncLink. Out: Gemini CLI, opencode 1.x behaviour, an MCP write proxy, fixing b1SyncLink's S05.
- **Cost:** to be estimated in Step 4 (about 8 tasks, 3 waves).
- **Risks:** `git commit --no-verify` bypasses the guard (documented, listed by the next `aidd status`); a false block stops a commit (escape: owner-only `AIDD_GUARD=warn`, recorded); the guard must stay fast (under 3 s) so nobody disables it.
- **Open decisions:** none.

## Pipeline route

| Step | Status | Reason | Confirmation |
|---|---|---|---|
| -1 | run | `find_spec.py` ran: nearest are 002/003/009 (this is a distinct enforcement layer) | |
| 0 | waived | no visual surface (CLI, git hooks, plugin) | user — "Omitir pasos visuales y confirmo alcance" |
| 1 | waived | no visual surface (CLI, git hooks, plugin) | user — "Omitir pasos visuales y confirmo alcance" |
| 1.5 | waived | no visual surface (CLI, git hooks, plugin) | user — "Omitir pasos visuales y confirmo alcance" |
| 2 | run | | |
| 3 | run | | |
| 4 | run | | |

## Visual debt

None: no `SCREEN-nn` code appears in this spec.

## Scope
- **Included:** `aidd next [spec] [--write]` (mechanical summary: gate-target spec, current step, first failing rule with its fix, next command; at most 30 lines; `--write` refreshes `.aidd/NEXT.md`); `aidd guard commit|push` (decision from `aidd status` facts, no LLM); `aidd install --githooks [project]` (idempotent `pre-commit` and `pre-push` that call `aidd guard`, never overwriting a foreign hook); opencode plugin template as `{ id, server, setup }`; `aidd doctor` checks for the git hooks, NEXT.md and the plugin shape, and a truthful line "write gate: none on opencode 2.x, enforcement: git guard"; `CORE.md` and the Antigravity rule tell the agent to run `aidd next` before each step; docs; the install in b1SyncLink.
- **Excluded:** an MCP server that proxies writes; Gemini CLI and opencode 1.x changes; repairing S05 or any b1SyncLink spec; CI server checks (the existing `aidd ci install` stays as is); blocking `git push`.

## Functional requirements (cite codes, don't redescribe the UI)

| FR-nnn | Requirement | Cites (SCREEN-XX-Fnn / CTL-nnn / API-nnn) |
|---|---|---|
| FR-1201 | `aidd next [spec_dir]` prints, with no LLM and in at most 30 lines: the gate-target spec, its current step (-1..7 from the artifacts present), the open `R` violations with their fix, whether `Approved:` is valid, the last `aidd verify` result (pass, fail, stale, never-run) and ONE next command. With no open spec it says so and names `aidd search`. `--write` writes the same text to `.aidd/NEXT.md` | — |
| FR-1202 | `aidd guard commit` reads the staged files (`git diff --cached --name-only`), ignores documentation and `specs/`, and when a code file is staged it blocks (exit 1, message naming rule and fix) if: the gate-target spec has no valid approval (R6); `tasks.md`/`plan.md` are out of chain order (R5); the last `aidd verify` of that spec failed, or is stale for the staged code; or its `qa-audit.md` exists with a failing row. A commit with only docs/specs files always passes. Amendment 1 (defect found on b1SyCLink, AC-1201): the spec checked is NOT only the gate target: the guard also evaluates every open spec that owns a staged code path (its `tasks.md` `Target file` cells match the staged file, a trailing `(same owner as ...)` note ignored); the gate target is checked when no open spec owns any staged path | — |
| FR-1203 | `aidd guard push` never blocks: it prints the same findings as warnings and exits 0 | — |
| FR-1204 | `aidd install --githooks [project]` writes `.git/hooks/pre-commit` and `pre-push` that call `aidd guard` through a portable command (no drive letter or user path baked in), appends to an existing foreign hook instead of replacing it, is idempotent, and works in a worktree (`git rev-parse --git-path hooks`). `aidd install --host opencode\|antigravity` offers it and `--githooks` can run alone | — |
| FR-1205 | The opencode plugin template exports `{ id: "aidd", server, setup }`; `aidd install --host opencode` writes it and no relative `plugin` entry for files under `.opencode/plugins/` (auto-discovered); `aidd doctor --host opencode` reads `opencode --version`, and for 2.x reports "write gate: none, enforcement: git guard" and fails if the git hooks are missing; the installer stops adding the relative `plugin` entry but leaves an existing one untouched, and the doctor accepts that entry present or absent | — |
| FR-1206 | `aidd doctor` for opencode and antigravity checks: git hooks installed and pointing at `aidd guard`; `.aidd/NEXT.md` present or creatable; `CORE.md` and the Antigravity rule contain the "run `aidd next` before each step" line | — |
| FR-1207 | `AIDD_GUARD=warn\|off` (owner environment only) turns blocks into warnings or disables the guard; every use is recorded as `guard_override` and shown by `aidd status`, like `rules_override`. `git commit --no-verify` is documented as a known bypass: the next `aidd status` lists commits whose staged code had no valid approval | — |
| FR-1208 | `aidd guard commit` finishes in under 3 s on a real repo with 70 specs, a 2 MB events log and a large worktree (measured on b1SyCLink: `build_status` alone took 7-10 s). Amendment 1: the guard does NOT call `build_status`; it makes a light read per owning spec: approval (hash of `tasks.md` against the `Approved:` line and the recorded `approved` event), the last verification result (`verification_state`) and the FAIL rows of `qa-audit.md`; no graph rebuild, no network, no full status | — |

## Acceptance cases

| Case | Real data (id) | Expected | Edge? |
|---|---|---|---|
| AC-1201 | b1SyncLink at HEAD `86514d6`: S05 with `qa-audit.md` FAIL and code staged | `aidd guard commit` exits 1 naming the failing verification and the fix; the same commit with only `specs/**/*.md` staged passes | no |
| AC-1202 | a scratch repo with an open spec whose `tasks.md` has no valid `Approved:` and a staged `src/app.py` | blocked with R6 and the command `aidd review <spec>`; after `aidd rules approve` the same commit passes | no |
| AC-1203 | `aidd next` in b1SyncLink and in this repo | at most 30 lines, names one next command, runs in under 2 s | no |
| AC-1204 | a repo that already has a `pre-commit` hook of its own (husky-style) | `aidd install --githooks` keeps the foreign lines and appends the aidd call once; running it twice changes nothing | yes |
| AC-1205 | a git worktree (hooks dir shared via `git rev-parse --git-path hooks`) | the hook is installed where git will run it | yes |
| AC-1206 | `opencode2 --version` = 2.0.32 | doctor prints "write gate: none" and fails when the git hooks are absent; the plugin loads with no `err_` in the opencode log | yes |
| AC-1207 | a staged file list of 0 entries and one of 5,000 entries | passes instantly with no files; the 5,000-file list still answers in under 3 s | yes |
| AC-1208 | Amendment 1: b1SyCLink with the gate pointer on F38-eDoc-Import-Costing (clean) and `Selection/supabase/tests/s05_hire.test.sql` staged (a modified Target file of S05, listed in its `tasks.md`; S05's approval is void and its `qa-audit.md` has 13 FAIL rows). Known limit: a file that no open spec lists as a Target (for example the `3093`-`3097` fix migrations of b1SyCLink) cannot be attributed and falls back to the gate target | `aidd guard commit` exits 1 naming S05, the R6 and qa-audit findings and the fix commands, and answers in under 3 s on that repo; the file is unstaged afterwards | yes |

## Verification

Scope: auto

| # | Command | Expected | Covers |
|---|---|---|---|
| V-1 | python -m pytest tests/test_aidd_next.py tests/test_aidd_guard.py -q | exit 0 | FR-1201, FR-1202, FR-1203, FR-1207, FR-1208 |
| V-2 | python -m pytest tests/test_host_install.py tests/test_host_doctor.py -q | exit 0 | FR-1204, FR-1205, FR-1206 |
| V-3 | python -m pytest tests/test_dot_aidd_mirror.py tests/test_rule_gate.py -q | exit 0 | FR-1206 |
| V-4 | python tests/run_parallel.py | exit 0 | FR-1201 |

## Optimization brief

Automation / parallelism: `aidd_status.py` already computes approval, verify and audit facts, so `next` and `guard` are thin readers of it (no new analysis) | the guard, the next command and the plugin/doctor change touch disjoint files and run in one wave | the full suite runs once at the end, in the background

| Option | Cost (tokens / min) | Risk | Recommended? |
|---|---|---|---|
| A. NEXT.md + git guard on commit, push warns | about 450k / 35 | low: no host dependency, bypass with `--no-verify` is listed by status | yes |
| B. A plus an MCP server that proxies writes | about 1,100k / 90 | high: invasive, breaks native tools | no |
| C. NEXT.md only (instructions) | about 150k / 12 | high: the pattern already evaded with `warn` in b1SyncLink | no |

Owner pick: A, user — "Git hooks + NEXT.md (Recommended)"
