# Draft amendment — Codex native hooks and truthful attribution

**DRAFT: proposal, not approved.** Extends host parity (009 currently excludes Codex) and plan adherence (012); approval and review behavior remains governed by 007/008. Target surface: Codex running inside the ChatGPT desktop app, using Codex's native hook runtime. This draft does not change current gates or authorize code edits.

## Minimum Requirements Checklist (fill before Step 3 starts)

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | Codex host adapter, native hook registration, pre/post tool hooks, edit evidence, plugin package and doctor | repo — skill/hooks/mark_code_edit.py:31 | — |
| New development or modification of something existing? | Add Codex native-hook support for Codex CLI and ChatGPT desktop's Codex runtime; preserve documented coverage limits | OpenAI — https://developers.openai.com/codex/hooks | — |
| Does it involve an external service, API, or integration? | Codex native hooks; optional manually installed desktop plugin; local shell and Git; no network required | OpenAI — https://developers.openai.com/plugins/build/plugins | — |
| Who is requesting it? (role/profile, not necessarily the name) | Project owner using Codex inside ChatGPT desktop | user — "chatgpt desktop que contiene a codex" | — |
| Dependencies on other modules or active developments? | 007 fingerprints, 008 approval units and 009 portability must be coordinated; shared files have one owner | repo — specs/012-aidd-plan-adherence-hookless-hosts/spec.md:48 | — |
| Business objective (1 sentence — what it achieves and why) | Make the AIDD skill and its enforcement hooks work in Codex inside ChatGPT desktop so the approved methodology is followed and verifiable | user — "necesito que tambien sea compatible y que tenga 100% de funcionalidad" | — |
| Expected visual fidelity level (if there's a mockup): exact or functional behavior only | No visual surface in this adapter | repo — scope is hook registration, CLI and skill package | — |

## Executive summary

- **Objective:** make the AIDD skill and enforcement hooks usable in Codex inside ChatGPT desktop, with equivalent rule gates and edit evidence on supported native tools.
- **Scope:** package the AIDD skill for Codex discovery; install project-local native hook registrations without overwriting unrelated settings; normalize `apply_patch`, gate `Bash` and file edits before execution, record post-tool effects, expose trust and coverage in doctor, and preserve consent provenance. Use Codex's hook schema and plugin packaging format. No silent overrides.
- **Risks:** broad shell attribution, forged consent, partial patch operations, path aliases, concurrent writes and inherited closed-spec state. Default to explicit uncertainty and conservative gating.
- **Verified host constraints:** Codex documents pre/post hooks for `Bash`, `apply_patch`, MCP and other local function tools. Project hooks load only when the project `.codex/` layer is trusted; non-managed hooks also require the owner to trust the current hook definition. A `PreToolUse` denial can stop a supported tool before it runs, but a hook error, timeout or malformed response can let it run. `PostToolUse` cannot undo effects. Shell side effects cannot be fully attributed from command text, and specialized tool paths may opt out. ChatGPT web without the Codex runtime is out of scope.

## Scope

- Codex docs identify native hooks: https://developers.openai.com/codex/hooks. `exec_command` matches as `Bash`; `apply_patch` matches as `apply_patch` and aliases `Write` or `Edit`; both use `tool_input.command`. Codex discovers project-local `.codex/hooks.json` only when that project layer is trusted. Codex desktop supports manually installed plugins with lifecycle hooks; the owner must review and trust non-managed hooks, and plugin script files must be present in the execution environment: https://developers.openai.com/plugins/build/plugins.
- Existing recorder reads `file_path` / `notebook_path` / `edits` rather than patch `command`; shell command effects are not reliably attributable from text. User's global matcher omits `Bash` for this recorder, but changing only the matcher is insufficient.
- Out of scope: ChatGPT web without Codex, manipulating global hook settings or trust state, fabricating a `spec_edit` or owner event, bypassing R6/R9, claiming specialized or opt-out tool paths are sandboxed, interpreting `review.md` alone as owner consent, secret capture, and retroactively signing prior events.

## Functional requirements

| FR | Requirement | Cites |
|---|---|---|
| FR-1210 | On supported Codex `apply_patch` pre/post events, normalize the documented patch payload into all add/update/delete/move paths; reject malformed or ambiguous patches before operation and gate every path with existing R6/R9. Post records only confirmed effects. | 009 host parity |
| FR-1211 | A shell command is not presumed read-only or safely attributable from its text. For supported controlled scripts, use an approved explicit target manifest and verify actual before/after changes; unsupported side effects remain `unattributed` and are not claimed gated. Preflight must not claim that a post-hook can undo writes. | 012 guard |
| FR-1212 | A supported reconciliation records an honest `reconciled` event for a proven actual plan/tasks edit after historical closure, including root, path, old/new content hashes, approval hash and provenance; it is never forged as a past hook event. It must not grant approval or move the pointer without existing authorization. | 007 R6 |
| FR-1213 | Owner approval may use native `UserPromptSubmit` only when host authenticity, project/session, current task hash and timing relative to review are demonstrable; a replay of the same owner act is idempotent and does not request another decision. Unknown host or async-answer payload fails closed. `review.md` alone is not consent. | 008 consent |
| FR-1214 | Doctor and docs report actual discovered/trusted hook registrations, payload support, project trust prerequisite, and coverage limits without revealing prompt content or secrets; untrusted, skipped, failed or unobserved hooks are never reported as enforcing. | 012 doctor |
| FR-1215 | `aidd install --host codex <project>` installs `.aidd/`, an AIDD skill discoverable by Codex, and project-local `.codex/hooks.json` registrations without replacing unrelated hook groups. The repo also ships a valid local marketplace entry (`.agents/plugins/marketplace.json`) and plugin package bundling the same skill and lifecycle hooks for ChatGPT desktop. `aidd doctor --host codex` checks files, commands, and registrations and reports both the project-trust prerequisite and owner review/trust requirement for non-managed hooks; it never changes global settings or marks hooks trusted. | 009 host adapter |

## Acceptance cases

| Case | Real data (id) | Expected | Edge? |
|---|---|---|---|
| AC-1210 | Patch containing add/update/delete/move and multiple specs | Every resolved source and destination gated before any write; post records successful paths once | yes |
| AC-1211 | Patch with parent traversal, symlink escape, UNC, drive path, malformed marker or partial failure | A live, trusted pre-hook explicitly denies every ambiguous or unsafe patch before execution. If Codex skips the hook or the hook errors, times out or returns malformed output, report the route as unverified; do not claim it was blocked. | yes |
| AC-1212 | Bash / PowerShell executes a helper that writes unannounced files | No inference from shell text that all paths are known; report uncertainty and preserve guard constraints | yes |
| AC-1213 | Actual closed spec plan/tasks changed by controlled helper, approval hash verified | Reconciled evidence distinguishes observed state from historical hook event; no synthetic approval | yes |
| AC-1214 | Owner prompt with exact hash, stale hash, different project/session, negation and repeated delivery | Only demonstrably authentic current consent applies; replay idempotent; unknown source refused | yes |
| AC-1215 | Scratch project on Windows/Linux, real hook pre/post payloads | Recorded and blocked behavior matches actual host; trust/timeout failure surfaced, no claims based on fixtures alone | yes |
| AC-1216 | Codex inside ChatGPT desktop, clean project install and repo marketplace plugin | After app restart, plugin appears in the Plugins Directory; skill is discoverable; project hooks run only after the project layer is trusted, and plugin hooks only after the owner trusts their current definition. Supported `apply_patch` pre-hooks deny an unapproved write before execution. `Bash` hooks are tested only for the exact guardable command policy, never claimed to attribute all shell effects. Post-hooks record only verified effects and cannot undo a completed operation. Doctor identifies trust and observation state; unrelated settings remain unchanged. | yes |

## Verification

Draft only: the final Verification table and CI host/version matrix must be written into the active spec after cross-spec review. Run one targeted test round per changed input, followed by an independent audit. Acceptance requires real ChatGPT desktop Codex runtime evidence; unit simulations alone cannot establish hook delivery or trust behavior. Include a live negative case for an explicit pre-hook denial and separate cases for untrusted/skipped and failed/timed-out hooks, because those states do not prove the operation was blocked. Never claim arbitrary shell interception or sandboxing.
