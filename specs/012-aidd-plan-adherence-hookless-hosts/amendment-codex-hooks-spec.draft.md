# Draft amendment — Codex native hooks and truthful attribution

**DRAFT: proposal, not approved.** Extends host parity (009 currently excludes Codex) and plan adherence (012); approval and review behavior remains governed by 007/008. This draft does not change current gates or authorize code edits.

## Minimum Requirements Checklist (fill before Step 3 starts)

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | Codex host adapter, pre/post tool hooks, edit evidence, approval adapter and doctor | repo — skill/hooks/mark_code_edit.py:31 | — |
| New development or modification of something existing? | Add Codex native-hook support without claiming parity for arbitrary shell side effects | repo — specs/009-aidd-host-parity/spec.md:46 | — |
| Does it involve an external service, API, or integration? | Codex native hooks; local shell and Git; no network required | repo — skill/hooks/host_adapter.py:20 | — |
| Who is requesting it? (role/profile, not necessarily the name) | Owner using Codex to orchestrate AIDD | [Proposed — unconfirmed] | → Step 2 align question |
| Dependencies on other modules or active developments? | 007 fingerprints, 008 approval units and 009 portability must be coordinated; shared files have one owner | repo — specs/012-aidd-plan-adherence-hookless-hosts/spec.md:48 | — |
| Business objective (1 sentence — what it achieves and why) | Register real edits and owner consent once, and enforce approved task scope on supported Codex operations | [Proposed — unconfirmed] | → Step 2 align question |
| Expected visual fidelity level (if there's a mockup): exact or functional behavior only | No visual surface in this adapter | [Proposed — unconfirmed] | → Step 2 align question |

## Executive summary

- **Objective:** truthful pre/post observability and gate decisions for supported Codex-native tools, with honest handling of unknown shell effects.
- **Scope:** normalize `apply_patch` payload, gate and attribute each actual affected path, report shell limitations, reconcile proven real changes, preserve existing valid owner-consent paths. No silent overrides.
- **Risks:** broad shell attribution, forged consent, partial patch operations, path aliases, concurrent writes and inherited closed-spec state. Default to explicit uncertainty and conservative gating.
- **Open decisions:** no claim of authenticated async-answer transport or arbitrary-shell write blocking until a supported host contract is independently demonstrated.

## Scope

- Codex docs identify native hooks: https://developers.openai.com/codex/hooks. `exec_command` hooks as `Bash`; `apply_patch` hooks as `apply_patch` and matches aliases `Write` or `Edit`; its `tool_input.command` contains patch text.
- Existing recorder reads `file_path` / `notebook_path` / `edits` rather than patch `command`; shell command effects are not reliably attributable from text. User's global matcher omits `Bash` for this recorder, but changing only the matcher is insufficient.
- Out of scope: manipulating the user's hook configuration, fabricating a `spec_edit` or owner event, bypassing R6/R9, asserting all writes are intercepted, interpreting `review.md` alone as owner consent, secret capture, and retroactively signing prior events.

## Functional requirements

| FR | Requirement | Cites |
|---|---|---|
| FR-1210 | On supported Codex `apply_patch` pre/post events, normalize the documented patch payload into all add/update/delete/move paths; reject malformed or ambiguous patches before operation and gate every path with existing R6/R9. Post records only confirmed effects. | 009 host parity |
| FR-1211 | A shell command is not presumed read-only or safely attributable from its text. For supported controlled scripts, use an approved explicit target manifest and verify actual before/after changes; unsupported side effects remain `unattributed` and are not claimed gated. Preflight must not claim that a post-hook can undo writes. | 012 guard |
| FR-1212 | A supported reconciliation records an honest `reconciled` event for a proven actual plan/tasks edit after historical closure, including root, path, old/new content hashes, approval hash and provenance; it is never forged as a past hook event. It must not grant approval or move the pointer without existing authorization. | 007 R6 |
| FR-1213 | Owner approval may use native `UserPromptSubmit` only when host authenticity, project/session, current task hash and timing relative to review are demonstrable; a replay of the same owner act is idempotent and does not request another decision. Unknown host or async-answer payload fails closed. `review.md` alone is not consent. | 008 consent |
| FR-1214 | Doctor and docs report actual discovered/trusted hook registrations, payload support, and coverage limits without revealing prompt content or secrets; failure to observe an event must not be called success. | 012 doctor |

## Acceptance cases

| Case | Real data (id) | Expected | Edge? |
|---|---|---|---|
| AC-1210 | Patch containing add/update/delete/move and multiple specs | Every resolved source and destination gated before any write; post records successful paths once | yes |
| AC-1211 | Patch with parent traversal, symlink escape, UNC, drive path, malformed marker or partial failure | No false safe attribution or silent allow; reason names affected scope | yes |
| AC-1212 | Bash / PowerShell executes a helper that writes unannounced files | No inference from shell text that all paths are known; report uncertainty and preserve guard constraints | yes |
| AC-1213 | Actual closed spec plan/tasks changed by controlled helper, approval hash verified | Reconciled evidence distinguishes observed state from historical hook event; no synthetic approval | yes |
| AC-1214 | Owner prompt with exact hash, stale hash, different project/session, negation and repeated delivery | Only demonstrably authentic current consent applies; replay idempotent; unknown source refused | yes |
| AC-1215 | Scratch project on Windows/Linux, real hook pre/post payloads | Recorded and blocked behavior matches actual host; trust/timeout failure surfaced, no claims based on fixtures alone | yes |

## Verification

Draft only: the final Verification table and CI host/version matrix must be written into the active spec after cross-spec review. Run one targeted test round per changed input, followed by an independent audit; never declare arbitrary shell interception or Codex async consent supported from unit simulations alone.
