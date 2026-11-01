# Draft — Codex patch pre-gate

**DRAFT, not approved.** Narrow phase of the Codex-hook amendment: protect supported native `apply_patch` operations before execution. It does not claim a successful PostToolUse recorder, shell-write coverage, spec reopening or authenticated asynchronous consent. Those remain separate blocked phases.

## Scope and evidence

The configured Codex pre-hook calls `rule_gate.py` directly. Its native `apply_patch` event carries patch text in `tool_input.command`; the existing `_paths` does not read it. Existing `_decide_path` also needs the prospective content to enforce R4/R6 and `.env` safeguards. A path-only `MultiEdit` envelope must therefore never be described as full gate parity.

This proposed phase accepts a precisely defined subset of patch grammar only when it can reconstruct prospective text without side effects. Unsupported, ambiguous, unstable, non-UTF-8, oversized or malformed content is denied before execution; it is not silently permitted. The pre-hook cannot by itself establish that the file remains unchanged until the tool writes it. Consequently, this draft is not ready to claim fail-closed protection under concurrency or production support. Existing non-Codex tools and owner-only protection remain unchanged. The actual Codex tool is not replaced.

## Requirements

| ID | Requirement |
|---|---|
| FR-1210A | In the direct `rule_gate.py` entrypoint recognize native `tool_name=apply_patch` and use one pure, strict patch parser shared through a new `skill/hooks/codex_patch.py` and its adapter mirror. This phase supports only the bounded Add File and single-hunk Update File subset defined in the plan; reject delete, move, extended syntax and uncertain payloads. No Bash parsing. |
| FR-1210B | For a supported add or uniquely matched update, reconstruct each target's prospective ASCII/LF content in memory. Create per-path input so `_decide_path` sees exactly that target's original and prospective content. Reject an operation if exact projection or stable preconditions cannot be established; never write a file during projection. |
| FR-1210C | Evaluate every source and destination with existing canonical root, symlink, R4/R6/R9, owner-only and `.env` protections before allowing the entire patch. Any denial or unsupported content denies the whole patch; no partial authorization. Do not grant approval or emit edit events. |
| FR-1210D | Preserve existing behavior for other tools and clearly report this phase as pre-gate only. The post-recorder, spec reopening, arbitrary shell writes and async consent remain unverified and disabled as Codex support claims. |

## Acceptance and constraints

The test matrix must include approved and unapproved code, edits to `tasks.md` that change an approval, protected `review.md`, `.env` control variables, mixed multi-file patches, supported adds/updates and refused delete/move, traversal, symlink and cross-root aliases, malformed or truncated markers, duplicate targets, ambiguous context, non-ASCII or CRLF inputs, file mutation during projection, and unrelated existing violations. Assert all paths are checked before any write; failures and timeouts must not become allows. Compare accepted projections against the real installed Codex `apply_patch` in a disposable project before claiming runtime parity; synthetic payloads alone are insufficient. Existing `tasks.md` and spec files remain subject to the same content checks and exceptions as before.

Dependency: finish and freeze the shared fingerprint/portability files in 007 and 009 before integration; this phase owns its listed hook files only. Blockers: establish the actual native hook payload and a deterministic host harness, and establish concurrency guarantees as stated in the plan. Unsupported grammar remains refused and is not silently expanded. No changes to user hook configuration or protected evidence are authorized by this draft.

Security evidence from 010: a hook's pre-write path check does not bind the later mutation to the same filesystem object. Native files can also have hard links with names unrelated to a known artifact; recognizing only case variants of known names does not prove such arbitrary aliases safe. The eventual host design must document which write operations replace an inode versus modify it in place, and either prevent writes through unverified aliases or honestly mark that guarantee unsupported. No scratch-only test proves absence of a concurrent substitution.
