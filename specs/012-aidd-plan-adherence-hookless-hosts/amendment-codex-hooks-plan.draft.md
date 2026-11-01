# Draft plan — Codex native hooks and truthful attribution

**DRAFT: not approved.** Source: amendment-codex-hooks-spec.draft.md, native OpenAI hook documentation and local AIDD inspection. Do not change existing gates until integration, owner approval and prebuild audit.

## Naming & File Contract (fill this first — everything below depends on it)

| Item | Convention |
|---|---|
| Functions / variables / methods | snake_case; existing public signatures retained where possible |
| File names | Existing AIDD `snake_case.py`; `skill/` canonical with byte-identical `adapters/dot-aidd/` mirror where applicable |
| Host events | Codex native `tool_name`, `tool_input.command`, `session_id`, `cwd`; preserve origin and distinguish live hook from reconciliation |
| Evidence | Existing protected append-only evidence API only; no synthetic `spec_edit`/owner events |

## Dependency graph and wave split

1. Coordinate 007 fingerprint and 009 path portability before changing shared `aidd_evidence.py` or `rule_gate.py`. 008 owns approval/review semantics; no duplicate implementation.
2. Define and test a pure patch parser using actual host-format fixtures, including move source/destination, missing paths, UTF-8 and path aliases. Adapt pre/post payload through an explicit Codex host adapter; reuse existing gate for each resolved path. Never parse arbitrary shell command text as an authoritative list of outputs.
3. For controlled scripts, define a separate explicit output-manifest protocol and reconciliation command; hash candidate files before and after, identify unexpected/unstable effects and report unresolved scope. An after-the-fact snapshot cannot enforce or undo writes. Existing Git guard remains a defense at commit, not a claim that all edits were blocked.
4. Reopening a historically closed spec must use a supported recorded reconciliation of a real change, separate event kind and exact previous/current hashes. Preserve existing owner approval validation and prevent falsely attributing earlier timestamps.
5. Investigate Codex owner consent from documented hook events only. Bind accepted event to session, project, exact hash, review freshness and time. A plain text file or synthetic event is not proof; no authenticated async-answer route is implemented until independently demonstrated. Keep the existing typed user prompt route as supported where observed.
6. Implement installer/doctor diagnostics for Codex only after obtaining a real isolated host capture; configuration trust must be assessed, not changed on the user's machine automatically. Add no network dependencies.

## Tests that change

- Pure parser tests for all patch operations and adversarial aliases, fail-closed malformed/multi-project inputs.
- Scratch-project pre/post payload tests, including old closed spec plus a real plan change, no-op, unknown write, partial failure and no fabricated approval.
- Real Codex end-to-end in a disposable repository under supported Windows/Linux versions: observed pre-block, applied patch, post-event attribution, owner-prompt consent once, timeout/trust failures. A synthetic event test alone cannot prove host delivery.
- Single focused verification round with independent security/functional audit; no multiple agents build simultaneously; do not rerun unchanged checks.

## Open contracts

The exact authenticated async-answer event and a platform-independent mechanism to constrain arbitrary shell side effects are not established. They are separate blocked work, not hidden assumptions or reasons to accept unsafe evidence. Exact shared-file owner and slot schedule must be resolved when 007/009/008 work is frozen.
