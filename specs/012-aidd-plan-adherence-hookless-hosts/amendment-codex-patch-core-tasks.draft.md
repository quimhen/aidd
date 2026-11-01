# Draft tasks — Codex patch pre-gate

**DRAFT: not approved.** Same owner for shared hook and tests; 007 and 009 shared-file work must be frozen before editing. This is the narrow pre-gate phase only.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-23 | FR-1210A, FR-1210B | `skill/hooks/codex_patch.py` | LOGIC | | | shell writes; post events; user hook config |
| T-24 | FR-1210C, FR-1210D | `skill/hooks/rule_gate.py` (same owner as T-23) | LOGIC | | | approvals, reopening, shell and async consent |

## Per-task detail

### T-23 — Parse and project the supported Codex patch subset
**Classify**
- Nature: `INCIDENT`
- Kind: LOGIC
**Estimate**
- Agent min: 30
- Human ref hours: 1.5
- Tokens (est): 150k
- Agent role: builder
- Model tier: high
**Detail**
- Size: ~150 changed lines.
- Goal: calculate exact per-target original and prospective text without mutating files, or reject before the gate can allow an ambiguous patch.
- Cites: FR-1210A, FR-1210B.
- Depends on: approved tasks and frozen shared work from 007/009.
- Read first: `skill/hooks/rule_gate.py` functions `_paths`, `_would_be`, `_decide_path`, `decide`; `skill/hooks/host_adapter.py` `_patch_paths`; `specs/012-aidd-plan-adherence-hookless-hosts/amendment-codex-patch-core-plan.draft.md` contract 1 and 4.
- Files to change: `skill/hooks/codex_patch.py`, `adapters/dot-aidd/hooks/codex_patch.py`, `tests/test_codex_patch.py`, `tests/test_dot_aidd_mirror.py`.
- Naming contract: `project_patch(command: str, cwd: str) -> list[PatchTarget]`; `PatchTarget` is a frozen dataclass in `codex_patch.py` containing `operation`, `source`, `destination`, `original`, `prospective`; failures raise the built-in `ValueError`. Per-file size maximum is 2 MiB and maximum 100 targets; reject binary, undecodable or unstable files. New file is mirrored byte-for-byte and added to the explicit mirror test inventory.
- Behaviour: parse only the bounded ASCII/LF add and single-hunk update grammar in the plan; compute unique-context prospective contents without writes; reject delete/move, CRLF, missing final LF, non-ASCII, fuzzy/duplicate matches, unrecognized, overlapping, malformed or unstable operations. Preserve exact content, not a normalized approximation. Do not project symlink escapes or cross-root writes as safe. The orchestrator performs the native scratch comparison after the wave.
- Tests first: add native-format add/update/multifile fixtures and rejection cases for delete/move, malformed headers, fuzzy or repeated context, CRLF, missing terminal LF, non-ASCII, invalid UTF-8, file mutation and bounds; demonstrate current gate does not inspect `tool_input.command`.
- Verify: `python -m unittest tests.test_codex_patch tests.test_dot_aidd_mirror` -> exit 0 with nonzero cases; mirror SHA-256 equal. Orchestrator runs this once as part of the union with T-24.
- Do NOT: parse Bash, allow a patch with unknown projection, touch user hook config, record events or treat synthetic events as native runtime evidence.
- Done when: focused tests and a real native scratch comparison pass, with mismatch/unsupported states recorded, and mirrors agree.
- Open questions: the scratch native smoke command and the actual Codex hook payload still require a deterministic, supported host harness; synthetic events alone are insufficient for a support claim.

### T-24 — Gate every native patch path and prospective content
**Classify**
- Nature: `INCIDENT`
- Kind: LOGIC
**Estimate**
- Agent min: 30
- Human ref hours: 1.5
- Tokens (est): 150k
- Agent role: builder
- Model tier: high
**Detail**
- Size: ~150 changed lines.
- Goal: ensure a supported Codex patch cannot pass the direct gate by omitting paths or content from the native event.
- Cites: FR-1210C, FR-1210D.
- Depends on: T-23; same owner as T-23; 007/009 shared files frozen.
- Read first: `skill/hooks/rule_gate.py` functions `_would_be`, `_env_control_write`, `_decide_path`, `decide`; `tests/test_rule_gate.py`; `specs/012-aidd-plan-adherence-hookless-hosts/amendment-codex-patch-core-plan.draft.md` contract 2–4.
- Files to change: `skill/hooks/rule_gate.py`, `adapters/dot-aidd/hooks/rule_gate.py`, `tests/test_rule_gate.py`, `tests/test_codex_patch.py` (same owner as T-23).
- Naming contract: preserve `decide(event) -> (blocked, message)` and the existing public hook output; `tool_name=apply_patch` invokes `project_patch`, then `_decide_path` once per original and destination with that target's own `old_string`, `new_string` or `content` input. `ValueError` and unexpected projection errors deny the entire patch with a concise reason; other tool behavior remains unchanged.
- Behaviour: perform all checks before returning allow; preserve the actual user/session/root and existing guards; for updates pass exact nonempty `old_string` and `new_string`, for adds pass `content`. Refuse delete/move, pre-existing add targets, empty originals or content-sensitive operations that cannot be projected. Never let path-only events bypass `_would_be` or `.env` checks.
- Tests first: reproduce native command payload bypass, then assert protected review and gate files, unapproved code, added control variables in `.env`, invalid or changed `tasks.md` approval, new R4 debt in plan/spec, symlink/path aliases, mixed patches, move to protected target, and unrelated valid patch. Test later blocked target cannot partially authorize earlier targets.
- Verify: `python -m unittest tests.test_codex_patch tests.test_rule_gate tests.test_host_gates tests.test_dot_aidd_mirror` -> exit 0 with nonzero cases; orchestrator runs this union once and audits independently.
- Do NOT: write protected state, synthesize approvals, silently accept unknown patch grammar, claim shell or post-event coverage, alter user hook configuration or weaken existing rules.
- Done when: focused union passes, real scratch pre-block/allow run is demonstrated, mirrors agree, and unverified host paths are explicitly reported.
- Open questions: a deterministic real-hook scratch proof of native tool name and payload remains unverified; do not claim runtime support until demonstrated.

## Waves
| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-23 | builder | 30 | 150 | 1.5 |
| 2 | T-24 | builder | 30 | 150 | 1.5 |

Total agent time (critical path): 60 min
Total tokens (k): 300

## Approval gate

Draft only. Native post-event provenance, reopening, shell writes and asynchronous approval are separate blocked phases. Integrate only after 007/009 ownership reconciliation, pre-build audit and owner approval of the final tasks hash. Do not write `Approved:` by hand.
