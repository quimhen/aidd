# DRAFT — Recovering existing owner consent across hosts

DRAFT / NO IMPLEMENTATION. This plan complements `amendment-codex-consent-tasks.draft.md` T-358 and does not approve or modify the active 007/008 tasks.

## Observed case

For 007, `aidd review --check` reports `STATE=complete approved=78/78 stale=no tag=[tasks:c865f422]`, while `aidd status` still reports `approval VOID`. The owner states that approval was already given and should not be requested again. The page state is a reviewed document, not in the current 007/008 contract a sufficient consent event. `aidd_status._consent` requires an owner answer/prompt recorded after both tasks and review or an owner-entered TTY confirmation; the latter would be a new user action, not replay of the existing one. `aidd_status._summary_answer` only accepts the exact hook-recorded answer, not agent text.

No available tool in this session exposes an authenticated Codex owner-answer event to AIDD. The existing `sync_ask_answers` parses AskUserQuestion transcript events; the available conversation content alone is not an authenticated external API. Do not read or modify protected host transcripts, generate synthetic prompts, drive a TTY as the owner, change review files, bypass R6 or claim the existing owner choice has been recorded.

## Proposed capability to investigate, not a selected implementation

1. Discover documented host capabilities for reading past authenticated user decisions or receiving a signed/host-authoritative event through a supported adapter. Confirm that role, session, question or review identifier, full current task/unit digest, choice and original timestamp can be verified without a transcript read by the agent.
2. If such a source exists, independently prove event origin and freshness relative to the current tasks and completed review; respect cancellation/refusal ordering. Replay only the existing owner decision, idempotently keyed by an authoritative source event ID, preserving its original time. A newer refusal supersedes approval.
3. Record through a dedicated validated AIDD-owned entry point, not arbitrary agent-authored JSON or unrestricted `ev.append`. Verify current content and a completed current review again immediately before the approval write. Log the source, event ID, decision, digest and timestamp without storing secrets.
4. Treat HTML completion as review evidence unless the approved contract explicitly defines an authenticated owner consent event. A writable HTML file or a browser click simulated by an agent is not sufficient to establish owner identity. Keep legacy `aidd rules approve` behavior unchanged until a separately approved migration defines a safe change.
5. If the platform exposes no authenticated event source or exact earlier response cannot be reconciled to the digest, return `unsupported` and preserve the review as complete without minting approval. Do not ask the owner to repeat an already-given consent contrary to their stated instruction; the orchestrator must explain the implementation limitation and can continue unrelated work.

## Tests required before implementation can be approved

- Actual supported host event retrieved twice produces one effect and keeps the original timestamp; a decision older than review/tasks, a wrong full digest, wrong role or missing host authentication refuses.
- Newer negative answer wins; cross-session behavior only when the same authoritative event and exact digest are verifiable.
- Plain text, assistant-written JSON, modified review files, mocked simulated browser click and agent-controlled TTY cannot become consent.
- Legacy HTML and summary workflows remain compatible; unavailability is explicit and does not block unrelated specs.
- Validate on a real supported Codex host without reading protected transcripts, with security and functional independent audit; no claims of support from mock tests alone.

## Open technical block

No authoritative Codex answer-event source is identified. T-358 remains an investigation, and implementation of replay is blocked until that source, the trust boundary and its authenticity are demonstrated. This is distinct from the separately documented future unit approval implementation; no user re-approval is inferred.
