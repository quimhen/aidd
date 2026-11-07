# Draft tasks — Codex hooks and truthful attribution

**DRAFT — NOT APPROVED.** Target: Codex inside ChatGPT desktop. Existing spec 012 approval does not cover these tasks. Do not edit production until the amendment is aligned, audited and approved.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-23 | FR-1210, AC-1210, AC-1211 | `skill/hooks/host_adapter.py` (same owner as T-23) | LOGIC | | | Do not parse Bash as a patch; do not invent a host payload; no actual project hook or evidence write. |
| T-24 | FR-1210, AC-1210, AC-1211 | `skill/hooks/rule_gate.py` (same owner as T-23) | LOGIC | | | Do not weaken existing R6/R9, permit partially assessed patches or modify user config. |
| T-25 | FR-1210, AC-1210 | `skill/hooks/mark_code_edit.py` (same owner as T-23) | LOGIC | | | Do not record arbitrary shell effects or synthesize approval/old timestamps; no actual project evidence. |
| T-26 | FR-1212, AC-1213 | `skill/scripts/aidd_evidence.py` (same owner as T-23) | LOGIC | | | Do not expose a public API that accepts self-attested proof from arbitrary command; never edit protected state by hand. |
| T-27 | FR-1210, FR-1212, AC-1210, AC-1213, AC-1215 | `tests/test_codex_hooks_e2e.py` (same owner as T-23) | LOGIC | | | No real user transcript, no actual host hook trust changes, no external model calls in CI, no standalone suite repeat. |
| T-28 | FR-1211, AC-1212 | `skill/hooks/host_adapter.py` (same owner as T-23) | LOGIC | | | Do not replace the shell with an unbounded regex allowlist, loosen R9 or call post-hoc attribution enforcement. |
| T-29 | FR-1213, AC-1214 | `skill/hooks/prompt_trigger.py` (same owner as T-23) | LOGIC | | | Do not fabricate owner events, reinterpret model-generated content as user input or request repeated approval. |
| T-30 | FR-1214, AC-1215 | `skill/scripts/aidd_doctor.py` (same owner as T-23) | LOGIC | | | Do not enable trust, edit user hooks, override R6 or claim all shell writes protected. |
| T-31 | FR-1215, AC-1216 | `skill/scripts/install_host.py` | LOGIC | | | Do not overwrite `.codex/hooks.json` groups, global Codex config or trust state; do not claim coverage for unsupported/opt-out tool paths. |
| T-32 | FR-1215, AC-1216 | `plugins/aidd-codex/`, `.agents/plugins/marketplace.json` and `tests/test_codex_install.py` | LOGIC | | | Do not publish to the public plugin directory or modify the user's installed plugins; owner installs from the local repo marketplace and reviews hook trust. |

## Per-task detail (one block per row above)

### T-31 — Install Codex project hooks without changing user trust
**Classify**
- Nature: `REQUIREMENT`
- Priority: 1
- Kind: LOGIC
**Estimate**
- Agent min: 16
- Human ref hours: 0.8
- Tokens (est): 80k
- Agent role: builder
- Model tier: high
**Detail**
- Goal: Add `aidd install --host codex <project>` for `.aidd/`, Codex skill discovery and a project-local `.codex/hooks.json`.
- Cites: FR-1215, AC-1216.
- Files to change: `skill/scripts/install_host.py`, `tests/test_host_install.py`, and docs; existing settings are merged additively and preserved.
- Behavior: Register Codex-native `PreToolUse` and `PostToolUse` handlers for `Bash` and `apply_patch` plus only lifecycle events whose payload and enforcement are verified. Use project-relative commands and a Windows `commandWindows` variant where needed, merge without dropping unrelated hooks, remain idempotent, and never install into global config or mark hooks trusted. Project hooks run only when the `.codex/` project layer is trusted; doctor must separately report project trust, hook-definition trust and observed delivery. An explicit pre-hook denial can block a supported call; a hook error, timeout, malformed result or untrusted/skipped hook may let it run.
- Tests first: Scratch project with existing hook sources, repeated install, malformed config, missing Python, Windows paths and a clean install.
- Verify: targeted install and doctor suites plus real ChatGPT desktop Codex runtime captures for trusted and untrusted project states, accepted denial, hook error/timeout, and positive post-event delivery.
- Done when: native registrations are discovered, user trust remains unchanged, unrelated config is preserved, and live pre/post behavior is observed.

### T-32 — Package AIDD as a manually installable Codex desktop plugin
**Classify**
- Nature: `REQUIREMENT`
- Priority: 1
- Kind: LOGIC
**Estimate**
- Agent min: 16
- Human ref hours: 0.8
- Tokens (est): 80k
- Agent role: builder
- Model tier: high
**Detail**
- Goal: Make the skill, scripts and native lifecycle hooks discoverable from a repo-scoped local marketplace in ChatGPT desktop.
- Cites: FR-1215, AC-1216.
- Files to change: `plugins/aidd-codex/plugin.json`, bundled skill/hooks, `.agents/plugins/marketplace.json` and `tests/test_codex_install.py`.
- Behavior: Follow the current OpenAI plugin manifest and root-relative path rules; declare `extensions.com.openai.hooks` or the default `hooks/hooks.json`; bundle the skill and hook scripts in the package; add a repo marketplace entry pointing to it. Keep all script paths inside the package and use `PLUGIN_ROOT` where the installed plugin location is needed. Do not add remote services, publish the plugin or claim the regular ChatGPT web surface runs local hooks.
- Tests first: Validate the manifest, marketplace file and all referenced files/commands; compare bundled hook bytes to canonical files and exercise the package in a clean local Codex desktop install.
- Verify: manifest/marketplace/path checks plus actual plugin discovery and hook trust review in ChatGPT desktop. Confirm an unchanged install remains trusted, a changed hook requires new trust, and an explicit denial blocks only the supported pre-tool path. Hook errors/timeouts and opt-out paths are reported as uncovered.
- Done when: the plugin loads, the skill is discoverable, the hooks run after explicit trust, and their live gate/evidence behavior matches the CLI install.

### T-23 — Normalize documented Codex patch events
**Classify**
- Nature: `REQUIREMENT`
- Priority: 1
- Kind: LOGIC
**Estimate**
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 100k
- Agent role: builder
- Model tier: high
**Detail**
- Size: ~150 changed lines.
- Goal: Normalize documented Codex patch events.
- Cites: FR-1210, AC-1210, AC-1211.
- Depends on: 007 T-13..16 and 009 T-19 freeze before shared files; real native payload capture from a scratch run.
- Read first: `skill/hooks/host_adapter.py`, `skill/hooks/rule_gate.py`, `skill/hooks/mark_code_edit.py`, `skill/scripts/aidd_evidence.py`, `skill/scripts/aidd_status.py` and the draft plan.
- Files to change: `skill/hooks/host_adapter.py`, `tests/test_host_gates.py`, its `adapters/dot-aidd/` mirror when it exists; exact cross-spec shared ownership must be frozen before integrating.
- Naming contract: normalize_codex_patch(event: dict) -> dict: return a MultiEdit envelope with an edits entry per source and destination, tool/session/cwd preserved; raise ValueError on missing or malformed command, unknown patch marker, duplicate ambiguous destination, missing end marker or NUL. Accept only patch syntax confirmed by captured Codex `apply_patch` inputs or existing parser fixtures; the OpenAI hook contract documents `tool_input.command`, not every patch-language marker. Do not treat context lines as headers. Resolve no paths in the parser. Implement the canonical file and copy its adapter mirror through a dry-run plus hash-checked script.
- Behaviour: normalize_codex_patch(event: dict) -> dict: return a MultiEdit envelope with an edits entry per source and destination, tool/session/cwd preserved; raise ValueError on missing or malformed command, unknown patch marker, duplicate ambiguous destination, missing end marker or NUL. Accept the exact Add File, Update File, Delete File and Move to markers used by Codex; do not treat context lines as headers. Resolve no paths in the parser. Implement the canonical file and copy its adapter mirror through a dry-run plus hash-checked script.
- Tests first: Construct synthetic documented apply_patch `tool_input.command` add/update/delete/move/multi-root payloads, null and malformed inputs; assert current adapter does not return correct complete list before implementing. Include newline and UTF-8 paths.
- Verify: `python -m unittest discover -s tests -p "test_host_gates.py"` -> exit 0 with named nonzero tests; orchestrator batches the union once per wave and records results.
- Do NOT: Do not parse Bash as a patch; do not invent a host payload; no actual project hook or evidence write.
- Done when: target behavior and security cases pass, mirror hashes agree when applicable, and independent audit records the limits.
- Open questions: none.

### T-24 — Gate every normalized patch path before execution
**Classify**
- Nature: `REQUIREMENT`
- Priority: 1
- Kind: LOGIC
**Estimate**
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 100k
- Agent role: builder
- Model tier: high
**Detail**
- Size: ~150 changed lines.
- Goal: Gate every normalized patch path before execution.
- Cites: FR-1210, AC-1210, AC-1211.
- Depends on: T-23; same owner as T-23; 009 T-19 freeze before shared files.
- Read first: `skill/hooks/host_adapter.py`, `skill/hooks/rule_gate.py`, `skill/hooks/mark_code_edit.py`, `skill/scripts/aidd_evidence.py`, `skill/scripts/aidd_status.py` and the draft plan.
- Files to change: `skill/hooks/rule_gate.py`, `tests/test_rule_gate.py`, its `adapters/dot-aidd/` mirror when it exists; exact cross-spec shared ownership must be frozen before integrating.
- Naming contract: Retain decide(event)->(bool,str). Normalize only Codex tool_name apply_patch using T-23; evaluate every path against current _decide_path and existing R6/R9, both move source and destination, before returning allow; if normalization fails, return the documented explicit denial. Document that this guarantee applies only when Codex actually invokes a trusted hook and the handler returns a valid denial; Codex may run the tool if the hook errors, times out, returns malformed output, is untrusted, or the path opts out. For other tools preserve existing behavior. Mirror exact bytes.
- Behaviour: Retain decide(event)->(bool,str). Normalize only Codex tool_name apply_patch using T-23; evaluate every path against current _decide_path and existing R6/R9, both move source and destination, before returning allow; if normalization fails, deny with explicit reason. For other tools preserve existing behavior. Mirror exact bytes.
- Tests first: Use scratch projects: one unapproved code target, a protected target, a move to protected destination, symlink escape, UNC/drive alias, malformed or empty patch and a valid approved patch; red test must demonstrate that current command payload bypasses path checks.
- Verify: `python -m unittest discover -s tests -p "test_rule_gate.py"` -> exit 0 with named nonzero tests; orchestrator batches the union once per wave and records results.
- Do NOT: Do not weaken existing R6/R9, permit partially assessed patches or modify user config.
- Done when: target behavior and security cases pass, mirror hashes agree when applicable, and independent audit records the limits.
- Open questions: none.

### T-25 — Record confirmed patch changes with truthful provenance
**Classify**
- Nature: `REQUIREMENT`
- Priority: 1
- Kind: LOGIC
**Estimate**
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 100k
- Agent role: builder
- Model tier: high
**Detail**
- Size: ~150 changed lines.
- Goal: Record confirmed patch changes with truthful provenance.
- Cites: FR-1210, AC-1210.
- Depends on: T-23 and T-24; same owner as T-23.
- Read first: `skill/hooks/host_adapter.py`, `skill/hooks/rule_gate.py`, `skill/hooks/mark_code_edit.py`, `skill/scripts/aidd_evidence.py`, `skill/scripts/aidd_status.py` and the draft plan.
- Files to change: `skill/hooks/mark_code_edit.py`, `tests/test_hooks.py`, its `adapters/dot-aidd/` mirror when it exists; exact cross-spec shared ownership must be frozen before integrating.
- Naming contract: Retain existing hook entrypoint and event signatures; normalize the same Codex patch event and, only if tool_response indicates successful complete application, record existing spec_edit or code_edit once for each actual validated changed path. On ambiguous or failed response, write no success event and return a hook_error; distinguish moves and preserve session/cwd. Mirror exact bytes.
- Behaviour: Retain existing hook entrypoint and event signatures; normalize the same Codex patch event and, only if tool_response indicates successful complete application, record existing spec_edit or code_edit once for each actual validated changed path. On ambiguous or failed response, write no success event and return a hook_error; distinguish moves and preserve session/cwd. Mirror exact bytes.
- Tests first: Test synthetic pre/post events for successful plan/tasks edit after closed spec, code patch, move, multi-file, duplicate delivery and failure; ensure idempotent tool-use attribution and no approval event. First demonstrate current command payload yields no path.
- Verify: `python -m unittest discover -s tests -p "test_hooks.py"` -> exit 0 with named nonzero tests; orchestrator batches the union once per wave and records results.
- Do NOT: Do not record arbitrary shell effects or synthesize approval/old timestamps; no actual project evidence.
- Done when: target behavior and security cases pass, mirror hashes agree when applicable, and independent audit records the limits.
- Open questions: Native pre/post provenance, exact successful response shape and protected per-invocation state have not yet been demonstrated; do not implement or infer a trusted event.

### T-26 — Reconcile a proved closed-spec change honestly
**Classify**
- Nature: `REQUIREMENT`
- Priority: 1
- Kind: LOGIC
**Estimate**
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 100k
- Agent role: builder
- Model tier: high
**Detail**
- Size: ~150 changed lines.
- Goal: Reconcile a proved closed-spec change honestly.
- Cites: FR-1212, AC-1213.
- Depends on: T-25; same owner as T-23; 007 fingerprint work frozen.
- Read first: `skill/hooks/host_adapter.py`, `skill/hooks/rule_gate.py`, `skill/hooks/mark_code_edit.py`, `skill/scripts/aidd_evidence.py`, `skill/scripts/aidd_status.py` and the draft plan.
- Files to change: `skill/scripts/aidd_evidence.py`, `tests/test_evidence.py`, its `adapters/dot-aidd/` mirror when it exists; exact cross-spec shared ownership must be frozen before integrating.
- Naming contract: Add reconcile_observed_spec_edit(root, session, spec, path, old_hash, new_hash, tool_use_id) returning a structured status. A trusted live hook supplies old/new hashes from a controlled atomic patch operation; reject absent proof, same content, path escape, digest mismatch, duplicate ID with inconsistent data, or approval hash mismatch. Store a distinct reconciliation event, never spec_edit dated in the past; open_specs recognizes the event only for plan/tasks after closure and current digest equals recorded new digest. Never grant approval or move gate implicitly. Mirror exact bytes.
- Behaviour: Add reconcile_observed_spec_edit(root, session, spec, path, old_hash, new_hash, tool_use_id) returning a structured status. A trusted live hook supplies old/new hashes from a controlled atomic patch operation; reject absent proof, same content, path escape, digest mismatch, duplicate ID with inconsistent data, or approval hash mismatch. Store a distinct reconciliation event, never spec_edit dated in the past; open_specs recognizes the event only for plan/tasks after closure and current digest equals recorded new digest. Never grant approval or move gate implicitly. Mirror exact bytes.
- Tests first: Build scratch events for prior closure, proven later change and matching approval, status-only/no-op, stale/forged hash, duplicate delivery, unrelated spec and changed file after observation. Assert reopen only on valid record.
- Verify: `python -m unittest discover -s tests -p "test_evidence.py"` -> exit 0 with named nonzero tests; orchestrator batches the union once per wave and records results.
- Do NOT: Do not expose a public API that accepts self-attested proof from arbitrary command; never edit protected state by hand.
- Done when: target behavior and security cases pass, mirror hashes agree when applicable, and independent audit records the limits.
- Open questions: Native pre/post provenance, exact successful response shape and protected per-invocation state have not yet been demonstrated; do not implement or infer a trusted event.

### T-27 — Test end-to-end Codex gate and recorder
**Classify**
- Nature: `REQUIREMENT`
- Priority: 1
- Kind: LOGIC
**Estimate**
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 100k
- Agent role: builder
- Model tier: high
**Detail**
- Size: ~150 changed lines.
- Goal: Test end-to-end Codex gate and recorder.
- Cites: FR-1210, FR-1212, AC-1210, AC-1213, AC-1215.
- Depends on: T-23..T-26.
- Read first: `skill/hooks/host_adapter.py`, `skill/hooks/rule_gate.py`, `skill/hooks/mark_code_edit.py`, `skill/scripts/aidd_evidence.py`, `skill/scripts/aidd_status.py` and the draft plan.
- Files to change: `tests/test_codex_hooks_e2e.py`, `tests/test_codex_hooks_e2e.py`, its `adapters/dot-aidd/` mirror when it exists; exact cross-spec shared ownership must be frozen before integrating.
- Naming contract: Create stdlib unittest scratch-only integration harness exercising native event adapters pre then post through temp fixture project. Test 007-like old close/new tasks edit/current hash, pre-block unapproved patch, owner-approved path passes, post success reopens, failure no record and unrelated spec untouched. Unit test payloads are simulated; separately document a real isolated Codex run before claiming host compatibility.
- Behaviour: Create stdlib unittest scratch-only integration harness exercising native event adapters pre then post through temp fixture project. Test 007-like old close/new tasks edit/current hash, pre-block unapproved patch, owner-approved path passes, post success reopens, failure no record and unrelated spec untouched. Unit test payloads are simulated; separately document a real isolated Codex run before claiming host compatibility.
- Tests first: Capture red baseline before implementation against existing `_paths`; after code freeze orchestrator runs this file once with existing test_host_gates/test_rule_gate/test_hooks/test_evidence in one targeted invocation.
- Verify: `python -m unittest discover -s tests -p "test_codex_hooks_e2e.py"` -> exit 0 with named nonzero tests; orchestrator batches the union once per wave and records results.
- Do NOT: No real user transcript, no actual host hook trust changes, no external model calls in CI, no standalone suite repeat.
- Done when: target behavior and security cases pass, mirror hashes agree when applicable, and independent audit records the limits.
- Open questions: none.

### T-28 — Define controlled-shell gate with measured coverage
**Classify**
- Nature: `REQUIREMENT`
- Priority: 1
- Kind: LOGIC
**Estimate**
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 100k
- Agent role: builder
- Model tier: high
**Detail**
- Size: ~150 changed lines.
- Goal: Define controlled-shell gate with measured coverage.
- Cites: FR-1211, AC-1212.
- Depends on: T-23..T-27; same owner as T-23.
- Read first: `skill/hooks/host_adapter.py`, `skill/hooks/rule_gate.py`, `skill/hooks/mark_code_edit.py`, `skill/scripts/aidd_evidence.py`, `skill/scripts/aidd_status.py` and the draft plan.
- Files to change: `skill/hooks/host_adapter.py`, `tests/test_host_gates.py`, its `adapters/dot-aidd/` mirror when it exists; exact cross-spec shared ownership must be frozen before integrating.
- Naming contract: BLOCKED: implement only after an enforceable host sandbox or trusted output-manifest mechanism is demonstrated. Shell text is never an authoritative write list; when write coverage cannot be proved, fail closed for the controlled write route. Read-only commands must remain usable through a proven read-only sandbox or an explicitly secured route. A post-run snapshot is evidence only, never prevention. Record unsupported ordinary shell as uncovered, not falsely gated.
- Behaviour: BLOCKED: implement only after an enforceable host sandbox or trusted output-manifest mechanism is demonstrated. Shell text is never an authoritative write list; when write coverage cannot be proved, fail closed for the controlled write route. Read-only commands must remain usable through a proven read-only sandbox or an explicitly secured route. A post-run snapshot is evidence only, never prevention. Record unsupported ordinary shell as uncovered, not falsely gated.
- Tests first: Must test indirect child processes, dynamically resolved paths, symlink escapes, write attempts before/after snapshots, unknown commands, legitimate reads and ambiguous manifests on Windows and Linux.
- Verify: `python -m unittest discover -s tests -p "test_host_gates.py"` -> exit 0 with named nonzero tests; orchestrator batches the union once per wave and records results.
- Do NOT: Do not replace the shell with an unbounded regex allowlist, loosen R9 or call post-hoc attribution enforcement.
- Done when: target behavior and security cases pass, mirror hashes agree when applicable, and independent audit records the limits.
- Open questions: Host capability and provenance are not established; do not implement.

### T-29 — Capture owner consent from authenticated Codex event
**Classify**
- Nature: `REQUIREMENT`
- Priority: 1
- Kind: LOGIC
**Estimate**
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 100k
- Agent role: builder
- Model tier: high
**Detail**
- Size: ~150 changed lines.
- Goal: Capture owner consent from authenticated Codex event.
- Cites: FR-1213, AC-1214.
- Depends on: T-23..T-27; 008 consent contract reviewed.
- Read first: `skill/hooks/host_adapter.py`, `skill/hooks/rule_gate.py`, `skill/hooks/mark_code_edit.py`, `skill/scripts/aidd_evidence.py`, `skill/scripts/aidd_status.py` and the draft plan.
- Files to change: `skill/hooks/prompt_trigger.py`, `tests/test_typed_confirmations.py`, its `adapters/dot-aidd/` mirror when it exists; exact cross-spec shared ownership must be frozen before integrating.
- Naming contract: BLOCKED: native UserPromptSubmit is documented but an authenticated source for asynchronous approval selection is not demonstrated. Preserve existing tagged typed user-prompt behavior. Specify implementation only after actual host payload provenance, root/session/time/review binding and replay rules are established; never derive approval from review.md alone.
- Behaviour: BLOCKED: native UserPromptSubmit is documented but an authenticated source for asynchronous approval selection is not demonstrated. Preserve existing tagged typed user-prompt behavior. Specify implementation only after actual host payload provenance, root/session/time/review binding and replay rules are established; never derive approval from review.md alone.
- Tests first: Test wrong/stale tag, negation, other root/session, prior review, replay idempotency and fabricated async event; a live owner event in an isolated real host is required for a support claim.
- Verify: `python -m unittest discover -s tests -p "test_typed_confirmations.py"` -> exit 0 with named nonzero tests; orchestrator batches the union once per wave and records results.
- Do NOT: Do not fabricate owner events, reinterpret model-generated content as user input or request repeated approval.
- Done when: target behavior and security cases pass, mirror hashes agree when applicable, and independent audit records the limits.
- Open questions: Host capability and provenance are not established; do not implement.

### T-30 — Report host support without changing user trust
**Classify**
- Nature: `REQUIREMENT`
- Priority: 1
- Kind: LOGIC
**Estimate**
- Agent min: 20
- Human ref hours: 1.0
- Tokens (est): 100k
- Agent role: builder
- Model tier: high
**Detail**
- Size: ~150 changed lines.
- Goal: Report host support without changing user trust.
- Cites: FR-1214, AC-1215.
- Depends on: T-23..T-27; before any claim of native support.
- Read first: `skill/hooks/host_adapter.py`, `skill/hooks/rule_gate.py`, `skill/hooks/mark_code_edit.py`, `skill/scripts/aidd_evidence.py`, `skill/scripts/aidd_status.py` and the draft plan.
- Files to change: `skill/scripts/aidd_doctor.py`, `tests/test_host_doctor.py`, its `adapters/dot-aidd/` mirror when it exists; exact cross-spec shared ownership must be frozen before integrating.
- Naming contract: Add a documented Codex capability report separating discovered hooks, trust status and live observed pre/post behavior. Unknown means unverified, not pass. Do not print secrets or change config. Verify installer/package decisions separately with existing owner; mirror module if present.
- Behaviour: Add a documented Codex capability report separating discovered hooks, trust status and live observed pre/post behavior. Unknown means unverified, not pass. Do not print secrets or change config. Verify installer/package decisions separately with existing owner; mirror module if present.
- Tests first: Scratch fixtures cover no config, configured-not-trusted, supported actual observation, unsupported tool and timeout; compare doctor output without reading user transcript.
- Verify: `python -m unittest discover -s tests -p "test_host_doctor.py"` -> exit 0 with named nonzero tests; orchestrator batches the union once per wave and records results.
- Do NOT: Do not enable trust, edit user hooks, override R6 or claim all shell writes protected.
- Done when: target behavior and security cases pass, mirror hashes agree when applicable, and independent audit records the limits.
- Open questions: none.

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-23 | builder | 20 | 100 | 1.0 |
| 2 | T-24 | builder | 20 | 100 | 1.0 |
| 3 | T-25 | builder | 20 | 100 | 1.0 |
| 4 | T-26 | builder | 20 | 100 | 1.0 |
| 5 | T-27, T-30 | builder | 20 | 200 | 1.0 |
| 6 | T-28, T-29 | blocked | 20 | 200 | 1.0 |
| 7 | T-31, T-32 | builder | 32 | 160 | 1.6 |

Total agent time (critical path): 152 min
Total tokens (k): 960

## Approval gate

All rows remain unapproved. Prebuild audit, collision review, cross-spec ownership and owner approval are mandatory. A scenario test using fabricated events is not evidence of a real host invocation. A T-28 route that claims unrestricted shell-write gating and a T-29 route that claims authenticated consent remain blocked until their exact host contracts are demonstrated; the supported scope must be narrowed to enforceable native paths before approval.
