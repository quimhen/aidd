# Draft plan — Codex native hooks and truthful attribution

**DRAFT: not approved.** Target surface: Codex inside ChatGPT desktop. Source: amendment-codex-hooks-spec.draft.md, current OpenAI hook/plugin documentation and local AIDD inspection. Do not change existing gates until integration, owner approval and prebuild audit.

## Naming & File Contract (fill this first — everything below depends on it)

| Item | Convention |
|---|---|
| Functions / variables / methods | snake_case; existing public signatures retained where possible |
| File names | Existing AIDD `snake_case.py`; `skill/` canonical with byte-identical `adapters/dot-aidd/` mirror where applicable |
| Host events | Codex native `tool_name`, `tool_input.command`, `session_id`, `cwd`, `tool_use_id`, `tool_response`; preserve origin and distinguish live hook from reconciliation |
| Evidence | Existing protected append-only evidence API only; no synthetic `spec_edit`/owner events |

## Dependency graph and wave split

1. Coordinate 007 fingerprint and 009 path portability before changing shared `aidd_evidence.py` or `rule_gate.py`. 008 owns approval/review semantics; no duplicate implementation.
2. Define and test a pure patch parser using actual host-format fixtures, including move source/destination, missing paths, UTF-8 and path aliases. Adapt Codex `PreToolUse` / `PostToolUse` payloads through the explicit host adapter; reuse existing gate for each resolved path. `Bash` and `apply_patch` are native hook paths, but never parse arbitrary shell text as an authoritative list of output paths.
3. For controlled scripts, define a separate explicit output-manifest protocol and reconciliation command; hash candidate files before and after, identify unexpected/unstable effects and report unresolved scope. An after-the-fact snapshot cannot enforce or undo writes. Existing Git guard remains a defense at commit, not a claim that all edits were blocked.
4. Reopening a historically closed spec must use a supported recorded reconciliation of a real change, separate event kind and exact previous/current hashes. Preserve existing owner approval validation and prevent falsely attributing earlier timestamps.
5. Investigate Codex owner consent from documented hook events only. Bind accepted event to session, project, exact hash, review freshness and time. A plain text file or synthetic event is not proof; no authenticated async-answer route is implemented until independently demonstrated. Keep the existing typed user prompt route as supported where observed.
6. Add an additive project-local `.codex/hooks.json` installer and a manually installable Codex desktop plugin containing the same skill and hooks. Do not modify global Codex settings or trust state. Doctor distinguishes configured, trusted and live-observed hooks; a configured-but-untrusted registration is not PASS.

## Tests that change

- Pure parser tests for all patch operations and adversarial aliases, fail-closed malformed/multi-project inputs.
- Scratch-project pre/post payload tests, including old closed spec plus a real plan change, no-op, unknown write, partial failure and no fabricated approval.
- Real Codex end-to-end in a disposable repository under supported Windows/Linux versions: observed pre-block, applied patch, post-event attribution, owner-prompt consent once, timeout/trust failures. A synthetic event test alone cannot prove host delivery.
- Codex desktop plugin packaging in a clean local install: manifest and relative paths resolve, skill is discoverable, hooks appear in Codex's review/trust UI, and enforcement starts only after the owner trusts the unchanged hook definition.
- Single focused verification round with independent security/functional audit; no multiple agents build simultaneously; do not rerun unchanged checks.

## Open contracts

The exact owner-consent event provenance and a platform-independent mechanism to constrain arbitrary shell side effects are not yet established. Keep those claims blocked; deliver and report only the supported native-tool coverage. Exact shared-file owner and slot schedule must be resolved when 007/009/008 work is frozen.
