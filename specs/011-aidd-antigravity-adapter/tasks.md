# Tasks — AIDD Antigravity adapter (spec 011)

One row = one small PR. Estimates are agent wall time and tokens; the Human ref is derived. Revised after the pre-build coherence audit.

Tasks reference the single pre-build coherence audit (spec, plan, graph, estimates) that runs before this list is approved; there is no per-edit audit.

**Every task's implementation prompt restates these standards explicitly — a fresh agent doesn't inherit them from context:**
- **Scope: in and out, both stated explicitly.** In scope = exactly the codes and target file named by the row (plus the companions it names), nothing else. Anything else is a note back, never a bundled fix.
- **If anything needed to proceed is missing or ambiguous, stop and report it** instead of guessing (a payload field, a path).
- **SOLID** on any code touched.
- **One class/component per file.**
- **Naming & File Contract from `plan.md`**: snake_case Python; templates keep the host's names.
- **Antifragile / Design for Failure**: every subprocess, file and JSON read can fail; the hook never wedges the host and always answers on stdout; a gate timeout fails closed; the installer never writes through a link.
- **Reuse, do not reimplement**: the rules live in `skill/hooks/rule_gate.py`; the adapter translates and spawns it. Existing hosts keep their behaviour byte for byte.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-01 | FR-1101, FR-1102 | skill/hooks/host_adapter.py | LOGIC | | | any other file; changing the gemini or opencode behaviour |
| T-02 | FR-1103, FR-1104 | skill/scripts/install_host.py | LOGIC | | | any other file except aidd/cli.py (same owner: the two choices lists and the hint) |
| T-03 | FR-1105 | skill/scripts/aidd_doctor.py | LOGIC | | | any other file |
| T-04 | FR-1106 | skill/hooks/rule_gate.py | LOGIC | | | any other file; any rule beyond the protected set |
| T-05 | FR-1103 | adapters/antigravity/rules/aidd.md | LOGIC | | | any other file except adapters/antigravity/skills/aidd/SKILL.md |
| T-06 | FR-1101, FR-1102, FR-1106 | tests/test_host_gates.py | LOGIC | | | any other file |
| T-07 | FR-1103, FR-1104, FR-1105 | tests/test_host_install.py | LOGIC | | | any other file except tests/test_host_doctor.py |
| T-08 | FR-1101, FR-1106 | adapters/dot-aidd/hooks/host_adapter.py | LOGIC | | | editing the hooks themselves |
| T-09 | FR-1107 | adapters/README.md | LOGIC | | | source code; any file except adapters/dot-aidd/CORE.md and skill/SKILL.md |
| T-10 | FR-1101, FR-1102, FR-1103, FR-1104, FR-1105, FR-1106, FR-1107, FR-1108 | specs/011-aidd-antigravity-adapter/evidence/verify-summary.md | LOGIC | | | editing source; qa-audit.md |

## Per-task detail (one block per row above)

### T-01
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: High
- Agent min: 12
- Human ref hours: 0.6
- Tokens (est): 75k
- Agent role: builder
- Model tier: high

**Decompose**
- Objective: the `antigravity` host in the adapter with the stdout JSON protocol.
- Activities:
  1. Add the host: `HOSTS`, the normaliser selector, `_tool_of` / `_args_of` / `_session_of` reading `toolCall.name`, `toolCall.args` and `conversationId`, the tool table of plan Interface 1, tolerant argument keys, project root from `workspacePaths`, and the normalised `cwd` set to the project root.
  2. Output protocol in `main()` around a run-core returning `(code, err_bytes)`: `pre` prints `{"decision":"deny","reason":...}` or `{"decision":"allow"}`, `post` prints `{}`, exit code 0; gate timeout denies, other failures allow and record `hook_error`; the exit-code path of gemini and opencode stays byte-identical.
  3. Update the docstring.

### T-02
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: High
- Agent min: 12
- Human ref hours: 0.6
- Tokens (est): 80k
- Agent role: builder
- Model tier: high

**Decompose**
- Objective: install the Antigravity files, wire the CLI and never write through a link.
- Activities:
  1. Add the `antigravity` host to `install_host.py`: skill and rule templates from `adapters/antigravity/`, the `.agents/hooks.json` merge with matcher `*` (plan Interface 2), `written/unchanged/skipped` reporting; in `aidd/cli.py` add `antigravity` to the `choices` of `aidd install --host` and `aidd doctor --host` and to the closing hint.
  2. The symlink-safety helper at the top of `_copy_file` and in `_write_bytes` for EVERY host: reparse-tag test on Windows (not the plain attribute), `os.path.islink` elsewhere; skip with the target named; with `--force` remove only the link (`os.unlink` / `os.rmdir`) and create a real folder; never `rmtree` a link.
  3. A sentinel-based self-check in a temp folder outside the repo.

### T-03
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3 MEDIUM
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 8
- Human ref hours: 0.4
- Tokens (est): 55k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: doctor support for the new host.
- Activities:
  1. Add D1 to D7 for `antigravity` as in plan Interface 2 (host auto-detection by `.agents/hooks.json` or `.agents/rules/aidd.md`; D4 requires matcher `*` and the exact command).
  2. D5 copies the installed `.aidd/hooks` into the temp fixture project with an unapproved open spec, runs the REGISTERED command string from `<tmp>/.agents` and passes only on exit 0 with stdout JSON `decision == "deny"`; D3 fails when `.agents/skills/aidd` is a link (reparse-tag test copied locally).

### T-04
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 8
- Human ref hours: 0.4
- Tokens (est): 50k
- Agent role: builder
- Model tier: high

**Decompose**
- Objective: the agent cannot disable the Antigravity gate by editing its registration.
- Activities:
  1. Handle `.agents/hooks.json` like `.gemini/settings.json` in the four places: `BASH_MARKERS` (add `.agents` and `hooks.json`), `HOST_GATE_FILES`, `_HOST_GATE_DIRS` (add `('.agents',)`) and `HOST_GATE_MESSAGE`; other files under `.agents/` stay writable.
  2. Keep every other behaviour; `tests/test_rule_gate.py` stays green (run it once).

### T-05
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3 MEDIUM
- Kind: LOGIC

**Estimate**
- Effort: Low
- Agent min: 4
- Human ref hours: 0.2
- Tokens (est): 20k
- Agent role: docs
- Model tier: medium

**Decompose**
- Objective: the two shipped templates.
- Activities:
  1. `adapters/antigravity/rules/aidd.md`: frontmatter `trigger: always_on`, a few lines (read `.aidd/CORE.md`, never AIDD.md whole, run `aidd doctor --host antigravity`) and `@[CORE](../../.aidd/CORE.md)`.
  2. `adapters/antigravity/skills/aidd/SKILL.md`: frontmatter `name: aidd` and a `description` (when to use AIDD), a thin pointer to `.aidd/CORE.md`; both well under 24,000 bytes.

### T-06
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 65k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: tests for the adapter protocol and the protected registration.
- Activities:
  1. Use the REAL payloads captured with `agy` (`write_to_file`, `replace_file_content`, `run_command`, `view_file`; scratchpad `agy/payloads.jsonl`) as fixtures: deny without approval (stdout JSON, exit 0), allow when approved, `view_file` allowed, `toolCall` null prints `{}`.
  2. Project root from `workspacePaths` with a foreign process cwd, the hook cwd `.agents`, a gate timeout answering `deny`, garbage stdin answering `allow`; `.agents/hooks.json` protected for file tools and shell (including `rm -r .agents`), other `.agents/` files writable.

### T-07
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 65k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: tests for the installer and the doctor on the new host.
- Activities:
  1. Install into a fresh project, second run unchanged, modified file skipped, foreign hook names kept, corrupt `hooks.json` skipped; the SYMLINK cases (AC-1103): a link at `.agents/skills/aidd` pointing at a temp folder with a sentinel: skipped without `--force`, replaced by a real folder with `--force`, sentinel and target untouched (try `os.symlink`, junction fallback; skip with a reason if neither can be created); the CLI accepts `--host antigravity` for install and doctor.
  2. Doctor: healthy install passes D1-D5 (D5 through the registered relative command from `.agents`), fails when the matcher is altered, when the rule file is missing, when `.agents/skills/aidd` is a link; `tests/test_host_doctor.py` is the same owner.

### T-08
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3 MEDIUM
- Kind: LOGIC

**Estimate**
- Effort: Low
- Agent min: 4
- Human ref hours: 0.2
- Tokens (est): 15k
- Agent role: builder
- Model tier: medium

**Decompose**
- Objective: keep the installed hook copies identical.
- Activities:
  1. Copy `skill/hooks/host_adapter.py` and `skill/hooks/rule_gate.py` over their `adapters/dot-aidd/hooks/` twins and confirm with `cmp`.

### T-09
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3 MEDIUM
- Kind: LOGIC

**Estimate**
- Effort: Low
- Agent min: 8
- Human ref hours: 0.4
- Tokens (est): 50k
- Agent role: docs
- Model tier: medium

**Decompose**
- Objective: documentation that matches the observed behaviour.
- Activities:
  1. `adapters/README.md`: an Antigravity tier (install with `aidd install --host antigravity`, doctor, what is written, the observed contract: hook cwd `.agents`, stdout JSON decision, `deny` reaches the model), the limits (app and IDE not verified, no `Stop` hook, user-level `~/.gemini/config/hooks.json` not protected, the matcher registered as `*`, `--dangerously-skip-permissions` as measured in T-10), and replace the "Antigravity is NOT covered" note.
  2. Same owner: `adapters/dot-aidd/CORE.md` host table gets the Antigravity tool names (`write_to_file`, `replace_file_content`, `run_command`) and stays under 12,288 bytes; `skill/SKILL.md` install section.

### T-10
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: High
- Agent min: 16
- Human ref hours: 0.8
- Tokens (est): 90k
- Agent role: tests
- Model tier: high

**Decompose**
- Objective: executed proof with the real host, once, after the builders.
- Activities:
  1. `aidd verify specs/011-aidd-antigravity-adapter` (full suite once, in the background); a documentation grep for FR-1107 (README, CORE.md and SKILL.md mention Antigravity install and limits).
  2. Real `agy` runs (about four prompts) in a scratch project installed with `aidd install --host antigravity` and an unapproved spec: AC-1105 (code write denied, file absent, message seen), AC-1107 (edit of `.agents/hooks.json` denied), AC-1106 (`--dangerously-skip-permissions`: measure and record), and that the always-on rule really injects the core (the model quotes a line of `CORE.md`; if the include does not resolve, report it so the rule is switched to inline).
  3. Run `aidd install --host antigravity D:/Fuentes/b1SycLink --force` and `aidd doctor --host antigravity --root D:/Fuentes/b1SycLink` (FR-1108, AC-1103: the repo's `skill/` folder must be unchanged); write everything to the target file.

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-01, T-02, T-03, T-04, T-05, T-06, T-07 | builder, docs, tests | 12 | 410 | 0.6 |
| 2 | T-08, T-09 | builder, docs | 8 | 65 | 0.4 |
| 3 | T-10 | tests | 16 | 90 | 0.8 |

Total agent time (critical path): 36 min
Total tokens (k): 565

## Approval gate

**Present the table above as a dry-run and wait for explicit approval before Step 5 starts on any row.**

Approved: 2026-10-13 hash:43a9c2bdf1e8

## Definition of Done (applies to every task above)
1. Code implements exactly the codes cited, in exactly the target file, following the plan's Naming & File Contract.
2. Builders only self-check statically; the executed verification runs once, in T-10, after the builders.
3. Every FR has a test or a recorded run (R10); anything not runnable is `not-verified` with a manual script.
