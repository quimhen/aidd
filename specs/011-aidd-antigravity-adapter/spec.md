# Spec — AIDD Antigravity adapter: skill pointer, always-on rule and write gate for the agy host (follow-up of spec 009)

Produced during Step 2 (Align). Intake (measured with the real `agy` 1.0.13 on this machine, probe hook in the scratchpad): the "Gemini" used on b1SycLink was Antigravity, where `.agents/skills/aidd` is a SYMLINK to the repo's `skill/` folder, so the host loads the 70 KB Claude `SKILL.md`. Antigravity has hooks, rules and skills of its own: `.agents/hooks.json`, `.agents/rules/*.md`, `.agents/skills/<name>/SKILL.md`. Observed contract: the hook runs with the working directory `<project>/.agents`; the PreToolUse payload has `toolCall.name` and `toolCall.args`, `conversationId` and `workspacePaths` (no `cwd`); tool names `write_to_file {TargetFile, CodeContent}`, `replace_file_content {TargetFile, TargetContent, ReplacementContent, StartLine, EndLine}`, `run_command {CommandLine, Cwd}`, `view_file {AbsolutePath}`; the hook answers on stdout with `{"decision":"deny","reason":"..."}` and the model receives `tool call denied by pre-tool hook: <reason>`; `auto_approve` lets the call run.

Risk: high
<!-- high: it adds a write gate on another host and touches the installer that replaces a symlink; a wrong replacement could damage the repo skill folder. -->

## Minimum Requirements Checklist (fill before Step 3 starts)

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | AIDD cross-host layer for the Antigravity host (agy CLI, app and IDE): `skill/hooks/host_adapter.py`, `skill/scripts/install_host.py`, `skill/scripts/aidd_doctor.py`, `adapters/antigravity/` | user — "Confirmo spec once" | → Step 2 align question |
| New development or modification of something existing? | New host adapter built on the spec 009 layer (adapter, installer, doctor), plus fixing the symlinked skill in b1SycLink | user — "Confirmo spec once" | → Step 2 align question |
| Does it involve an external service, API, or integration? | Yes: Antigravity hooks (`.agents/hooks.json`, PreToolUse stdout JSON decision), rules and skills; contract observed with the real `agy` 1.0.13 and the public docs | repo — specs/009-aidd-host-parity/evidence/verify-summary.md:1 | → Step 2 align question |
| Who is requesting it? (role/profile, not necessarily the name) | The project owner, who worked a week in b1SycLink with Antigravity | user — "Confirmo spec once" | → Step 2 align question |
| Dependencies on other modules or active developments? | Spec 009 (host adapter, installer, doctor, protected gate files), spec 010 (shell guard speed) | repo — specs/009-aidd-host-parity/qa-audit.md:1 | → Step 2 align question |
| Business objective (1 sentence — what it achieves and why) | On Antigravity the agent must load the short `CORE.md` (always-on rule) instead of a truncated 70 KB skill, and must be unable to write code without an approved spec | user — "Confirmo spec once" | → Step 2 align question |
| Expected visual fidelity level (if there's a mockup): exact \| functional behavior only | Not applicable: no screens | user — "Confirmo spec once" | → Step 2 align question |

## Executive summary

- **Objective:** Make AIDD enforce its rules on Antigravity (install, short always-on rule, write gate) and replace the symlinked 70 KB skill in b1SycLink.
- **Scope:** `antigravity` host in `host_adapter.py` (event normalisation and the stdout JSON decision protocol), `aidd install --host antigravity`, `aidd doctor` checks, protection of `.agents/hooks.json`, a thin `SKILL.md` and an always-on rule in `adapters/antigravity/`, docs; then run the install in b1SycLink. Out: Gemini CLI, OpenCode, Antigravity app/IDE verification beyond the CLI, the file-symlink gap of spec 010 (X1).
- **Cost:** 10 tasks, 3 waves, about 36 min and 565k tokens.
- **Risks:** the installer must never write through a symlink (it would edit the repo's skill folder): detected and tested; the hook relative path depends on the hook cwd (observed `.agents`): the command is `../.aidd/hooks/host_adapter.py` and doctor D5 proves it; `--dangerously-skip-permissions` may skip hooks (to be measured and documented).
- **Open decisions:** none.

## Pipeline route

| Step | Status | Reason | Confirmation |
|---|---|---|---|
| -1 | run | `find_spec.py` ran: nearest is 009 (this is its Antigravity follow-up) | |
| 0 | waived | no visual surface (hook, installer) | user — "Confirmo spec once" |
| 1 | waived | no visual surface (hook, installer) | user — "Confirmo spec once" |
| 1.5 | waived | no visual surface (hook, installer) | user — "Confirmo spec once" |
| 2 | run | | |
| 3 | run | | |
| 4 | run | | |

## Visual debt

None: no `SCREEN-nn` code appears in this spec.

## Scope
- **Included:** the `antigravity` host in `host_adapter.py` (normalise `write_to_file`, `replace_file_content`, `multi_replace_file_content`, `run_command`; project root from `workspacePaths`; session from `conversationId`; answer on stdout with `{"decision": ...}` for PreToolUse and `{}` for PostToolUse; deny on a gate timeout); `aidd install --host antigravity` writing `.agents/skills/aidd/SKILL.md` (thin), `.agents/rules/aidd.md` (always on, includes the short core) and the `aidd` entry of `.agents/hooks.json`, never writing through a symlink or junction; `aidd doctor` for the new host; `.agents/hooks.json` protected like the other gate files; docs; the b1SycLink install replacing the symlink; a real `agy` verification.
- **Excluded:** Gemini CLI and OpenCode changes; the file-symlink gap (spec 010 X1); the Antigravity app and IDE flavours (documented as unverified); user-level `~/.gemini/config/hooks.json`; a hook for the `Stop` event.

## Functional requirements (cite codes, don't redescribe the UI)

| FR-nnn | Requirement | Cites (SCREEN-XX-Fnn / CTL-nnn / API-nnn) |
|---|---|---|
| FR-1101 | `host_adapter.py antigravity pre\|post` reads the Antigravity payload (`toolCall.name`, `toolCall.args`, `conversationId`, `workspacePaths`) and normalises `write_to_file {TargetFile, CodeContent}` to Write, `replace_file_content {TargetFile, TargetContent, ReplacementContent}` to Edit, `multi_replace_file_content {TargetFile, ReplacementChunks}` to MultiEdit, `run_command {CommandLine, Cwd}` to Bash; every other tool (for example `view_file`) is allowed untouched | — |
| FR-1102 | For `antigravity pre` the adapter answers on stdout with one JSON object: `{"decision":"deny","reason":<the gate message>}` when the gate blocks, `{"decision":"allow"}` otherwise; for `post` it prints `{}`; it never relies on an exit code; an internal crash answers `allow` and records a hook error; a gate timeout answers `deny` (fail-closed) | — |
| FR-1103 | `aidd install --host antigravity` writes `.aidd/**`, `.agents/skills/aidd/SKILL.md` (thin pointer to `.aidd/CORE.md`), `.agents/rules/aidd.md` (always on, short, includes the core) and merges the `aidd` entry of `.agents/hooks.json` (PreToolUse and PostToolUse, matcher `*` because the matcher syntax was only observed with `*` and the adapter already allows non-write tools, command `python ../.aidd/hooks/host_adapter.py antigravity pre\|post`); idempotent, non-destructive, foreign hook names untouched | — |
| FR-1104 | The installer never writes through a symlink or junction: when `.agents/skills/aidd` (or any path it writes) is a link it reports `skipped` with the link target, and with `--force` it removes ONLY the link and creates a real folder; the link target (the repo's `skill/` folder) is never modified | — |
| FR-1105 | `aidd doctor --host antigravity` checks D1 to D7 for the host: files present and equal to the shipped ones, the always-on rule size under 24,000 bytes, the `aidd` entry in `.agents/hooks.json` with the exact matcher and command, a gate dry-run that must answer `deny` for a code write with no approval, and `agy --version` as information | — |
| FR-1106 | `.agents/hooks.json` is protected from agent writes like the other host gate files (R9), for file tools and the shell guard; other files under `.agents/` stay writable | — |
| FR-1107 | The docs state the Antigravity install and its limits: hook cwd, `--dangerously-skip-permissions` behaviour as measured, app and IDE not verified, no `Stop` hook, user-level hooks file not protected; `CORE.md` lists the Antigravity tool names in its host table | — |
| FR-1108 | In b1SycLink the symlinked skill is replaced by the real install and `aidd doctor --host antigravity` passes there | — |

## Acceptance cases

| Case | Real data (id) | Expected | Edge? |
|---|---|---|---|
| AC-1101 | the real payload of `write_to_file` captured with `agy` 1.0.13 (`TargetFile` absolute path, `CodeContent`, `workspacePaths` of the scratch project) with an unapproved open spec | `antigravity pre` prints `{"decision":"deny","reason":...}` naming R6 | no |
| AC-1102 | the real payloads of `replace_file_content` and `run_command` (`CommandLine: echo done`) | the edit is denied without approval, the harmless command is allowed | no |
| AC-1103 | b1SycLink: `.agents/skills/aidd` is a symlink to `D:\Fuentes\AIDD\skill` | install without `--force` skips with the target named and changes nothing in `D:\Fuentes\AIDD\skill`; with `--force` only the link is replaced by a real folder | yes |
| AC-1104 | a `PostToolUse` payload with `toolCall` null | `{}` printed, exit 0, no traceback | yes |
| AC-1105 | real `agy` in a scratch project installed with `aidd install --host antigravity` and an unapproved spec | a `write_to_file` of `src/app.py` is denied and the file does not exist; the model sees the R6 message | no |
| AC-1106 | the same real `agy` with `--dangerously-skip-permissions` | outcome measured and written in the README (hooks run or not) | yes |
| AC-1107 | an agent edit of `.agents/hooks.json` through `write_to_file` or `run_command` | denied (R9, FR-1106) | no |

## Verification

Scope: auto

| # | Command | Expected | Covers |
|---|---|---|---|
| V-1 | python -m pytest tests/test_host_gates.py -q | exit 0 | FR-1101, FR-1102, FR-1106 |
| V-2 | python -m pytest tests/test_host_install.py tests/test_host_doctor.py -q | exit 0 | FR-1103, FR-1104, FR-1105 |
| V-3 | python -m pytest tests/test_dot_aidd_mirror.py tests/test_rule_gate.py -q | exit 0 | FR-1106 |
| V-4 | python tests/run_parallel.py | exit 0 | FR-1101 |

## Optimization brief

Automation / parallelism: the adapter, installer, doctor and gate protection are independent files in one wave; the real payloads captured with `agy` are reused as test fixtures; the full suite runs once at the end, in the background | the real `agy` runs are the verification, not a manual script

| Option | Cost (tokens / min) | Risk | Recommended? |
|---|---|---|---|
| A. Extend the spec 009 layer (adapter, installer, doctor) with an `antigravity` host | about 565k / 36 | medium: stdout-JSON protocol differs from the exit-code hosts | yes |
| B. A separate adapter script only for Antigravity | about 700k / 45 | high: a second gate translation to keep in sync | no |

Owner pick: A (Recommended), consistent with the owner's request to start with Antigravity.

## Optional Align questions

| Question | Answer | Source |
|---|---|---|
| Which states must each screen/flow handle (empty, loading, error, offline)? | Not applicable: no screens | user — "Confirmo spec once" |
| Who may see or do this (permissions/roles)? | The owner installs; the agent only triggers the gate | user — "Confirmo spec once" |
| Entry route: how does the user reach this from the app's start? | `aidd install --host antigravity` and `aidd doctor --host antigravity` | user — "Confirmo spec once" |
| Target devices (phone, tablet, desktop, orientation)? | Windows 11 and the `agy` CLI first; the app and IDE flavours best effort | user — "Confirmo spec once" |
| Contract owner and status (who defines the backend contract, is it final or still moving)? | Google defines the hook contract; observed with `agy` 1.0.13, it can move: doctor shows the version | user — "Confirmo spec once" |
