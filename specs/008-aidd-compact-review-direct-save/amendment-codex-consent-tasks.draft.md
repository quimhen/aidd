# DRAFT — Codex consent transport investigation (deferred)

DRAFT, BLOCKED: this task is separate from the core unit approval amendment. No code implementation and no unit approval may infer Codex consent until a trusted source is demonstrated.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-358 | FR-354 | `specs/008-aidd-compact-review-direct-save/evidence/codex-transport-probe.md` | LOGIC | | | No code changes or simulated owner events |

## Per-task detail

### T-358 — Investigate authenticated Codex event transport (blocked)
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC
- Size: ~50 evidence lines; no production-code changes.
**Estimate**
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 70k
- Agent role: mapper
- Model tier: high
**Detail**
- **Goal:** Establish whether Codex exposes an authoritative owner-consent event suitable for an AIDD unit.
- **Cites:** FR-354
- **Depends on:** none
- **Read first:** `skill/scripts/aidd_evidence.py:1561`, `specs/008-aidd-compact-review-direct-save/spec.md:76`, host integration documentation available to the running session.
- **Files to change:** `specs/008-aidd-compact-review-direct-save/evidence/codex-transport-probe.md` only.
- **Naming contract:** report headings `Available host`, `Proven event origin`, `Session and digest binding`, `Unsupported cases`, `Next action`.
- **Behaviour:** Identify the documented owner-event channel and its trust boundary without reading or changing protected transcripts; record exact authenticated source, session identity, requested tag and observed result if demonstrable. If not demonstrable, report `unsupported` and preserve existing fail-closed review route. No synthetic owner event is accepted as evidence.
- **Tests first:** Attempt a read-only discovery of supported host capabilities and record the documented result; do not impersonate or send messages as an owner.
- **Verify:** `python skill/scripts/check_spec.py specs/008-aidd-compact-review-direct-save` -> exit 0 for structural checks; independent audit verifies the probe's provenance.
- **Do NOT:** write `.aidd` or host transcripts, create approval events, alter consent gates, create databases, or claim Codex support without an authenticated real event.
- **Done when:** report names a provably authentic channel and its lifecycle, or records `unsupported` and a concrete owner-controlled fallback; evidence is independently reviewed.
- **Open questions:** No authoritative authenticated Codex answer-event source has yet been established; do not claim or implement Codex event support until it is proven.

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-358 | mapper | 15 | 70 | 0.75 |

Total agent time (critical path): 15 min
Total tokens (k): 70
