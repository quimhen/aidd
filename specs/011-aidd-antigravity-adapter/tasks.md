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
| T-11 | FR-1109, FR-1113 | skill/hooks/host_adapter.py (same owner as T-01) | LOGIC | | | any other file; changing the allow behaviour for plain garbage or empty stdin |
| T-12 | FR-1110, FR-1111 | skill/hooks/rule_gate.py (same owner as T-04) | LOGIC | | | any other file; changing HOST_GATE_MESSAGE; any rule beyond the protected set |
| T-13 | FR-1112, FR-1113 | skill/scripts/install_host.py (same owner as T-02) | LOGIC | | | any other file |
| T-14 | FR-1109, FR-1110, FR-1111, FR-1113 | tests/test_host_gates.py (same owner as T-06) | LOGIC | | | any other file |
| T-15 | FR-1112, FR-1113 | tests/test_host_install.py (same owner as T-07) | LOGIC | | | any other file |
| T-16 | FR-1109, FR-1110, FR-1111, FR-1113 | adapters/dot-aidd/hooks/host_adapter.py (same owner as T-08) | LOGIC | | | editing the hooks themselves; same owner for its rule_gate.py twin |
| T-17 | FR-1109, FR-1110, FR-1111, FR-1112, FR-1113 | adapters/README.md (same owner as T-09) | LOGIC | | | source code; any other file |
| T-18 | FR-1109, FR-1110, FR-1111, FR-1112, FR-1113 | specs/011-aidd-antigravity-adapter/evidence/amendment-1-summary.md | LOGIC | | | editing source; qa-audit.md |

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

## Amendment 1 — per-task detail (T-11 to T-18, hardening of Y1 to Y5; plan.md "Amendment 1")

### T-11
**Classify**
- Nature: `INCIDENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: High
- Agent min: 12
- Human ref hours: 0.6
- Tokens (est): 70k
- Agent role: builder
- Model tier: high

**Decompose**
- Objective: the adapter never turns a nesting bomb or an unresolved target into allow.
- Activities:
  1. Y1 (PRE phase only; POST never denies): a depth scan of the raw stdin text before `json.loads`, skipped when `text.count('[') + text.count('{') <= 100`, otherwise a `re.finditer` tokenization of strings and brackets (skip the character after a backslash), stop above depth 100; plus a `RecursionError` guard; over the limit deny on every host (exit 2 with a stderr message for gemini and opencode, `{"decision":"deny","reason":...}` with exit 0 for antigravity); plain non-JSON garbage and empty stdin keep their current behaviour.
  2. Y1/Y5: an Antigravity `multi_replace_file_content` whose `ReplacementChunks` cannot be parsed into edits is denied (today `_ag_chunks` returns None and the call is allowed) and chunk-level path keys are read; a gated write whose path key is present but not a string is denied; with `workspacePaths` missing or without a project, find the project by walking up from the process cwd and resolve a relative `TargetFile` against it.

### T-12
**Classify**
- Nature: `INCIDENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: High
- Agent min: 12
- Human ref hours: 0.6
- Tokens (est): 70k
- Agent role: builder
- Model tier: high

**Decompose**
- Objective: more registration and interpreter-shadowing files protected, nothing else blocked.
- Activities:
  1. ONE shared `_gate_match(segs, pattern)` (`fnmatch.fnmatchcase` per component on `_norm_comp` output, equal lengths) used by `_host_gate_file` AND by both branches of `_host_tok` (the relative-suffix compare and the `_locate` result): the shell redirect, writer and copier paths decide only through `_host_tok`, which compares exact tuples today. Patterns: `('.agents','plugins','*','hooks.json')` and the direct children of `.agents` named `python*` or ending `.bat`, `.cmd`, `.exe`, `.com`, `.ps1`.
  2. The user-level file `~/.gemini/config/hooks.json` is outside any project root (`_host_gate_file` loops over `ev.project_roots`): add an absolute check on `ev.canon_path` against `os.path.expanduser('~/.gemini/config/hooks.json')` for file tools, and treat the suffix `('.gemini','config','hooks.json')` as protected on ANY token in the shell guard (absolute, relative, `$HOME`, `%USERPROFILE%`); a copier whose destination is the plain `.agents` folder has its source basenames matched against the direct-child patterns.
  3. A separate `HOST_GATE_EXTRA_MESSAGE` names the new files; `HOST_GATE_MESSAGE` stays byte-identical; `.agents/rules/**` and `.agents/skills/**` stay writable; `tests/test_rule_gate.py` and `tests/test_rule_gate_shell_speed.py` stay green (run each once).

### T-13
**Classify**
- Nature: `INCIDENT`
- Priority: 3 MEDIUM
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 60k
- Agent role: builder
- Model tier: high

**Decompose**
- Objective: the installer never writes through a hard link and never hides a skipped gate registration.
- Activities:
  1. Y4: `_write_bytes` writes to a temporary file in the destination folder (`os.open(..., O_CREAT|O_EXCL|O_WRONLY, 0o666)`, a non-`.py` suffix, unlinked in `finally`) and `os.replace`s it onto the target; if `os.replace` fails the file is recorded `skipped` and the run fails, never an in-place fallback; unchanged files are still never rewritten; the symlink guard stays.
  2. Y5, implemented once in `_record` (or at the end of `run`): any `skipped` row whose path is `.agents/hooks.json`, `.gemini/settings.json` or `.opencode/opencode.json` sets `self.failed` (exit 1), including a corrupt file with `--force`.

### T-14
**Classify**
- Nature: `INCIDENT`
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
- Objective: tests for Y1, Y2, Y3 and Y5 on the adapter and the gate.
- Activities:
  1. Y1 on all three hosts: nesting 1,200 and 3,000 levels (the audit's values) and a nested `Extra` key inside a `ReplacementChunks` entry aimed at `.agents/hooks.json` are denied; garbage and empty stdin keep their behaviour; the real captured payloads still pass.
  2. Y2/Y3: write, edit and shell redirects (and a `cp python.exe .agents/` copier) to `.agents/plugins/p/hooks.json`, `.agents/python.bat`, `.agents/python.exe`, `.agents/x.cmd`, `.agents/y.ps1` and the user-level hook file (a temporary home: set BOTH `HOME` and `USERPROFILE` in the subprocess environment, since `os.path.expanduser` reads USERPROFILE on Windows; also shell forms `$HOME/.gemini/config/hooks.json` and an absolute path) are denied; `.agents/rules/x.md`, `.agents/skills/y/SKILL.md` and `.agents/plugins/p/readme.md` are allowed (spec approved so only the protection can block); Y5: a list `TargetFile` is denied, an unparseable `ReplacementChunks` is denied, and a relative `TargetFile` with no `workspacePaths` and the process cwd `.agents` is gated.

### T-15
**Classify**
- Nature: `INCIDENT`
- Priority: 3 MEDIUM
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 8
- Human ref hours: 0.4
- Tokens (est): 50k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: tests for Y4 and the installer half of Y5.
- Activities:
  1. A hard link (`os.link`) planted as `.agents/rules/aidd.md` to an outside file with a sentinel: `--force` replaces the rule by the template and leaves the outside file and its sentinel untouched (skip with a stated reason if hard links cannot be created).
  2. With `.agents` linked and no `--force` the install exits 1 and says the gate registration was skipped; with `--force` it exits 0; the same exit-1 rule for a corrupt `.gemini/settings.json` and `.opencode/opencode.json`, so the three existing tests that assert exit 0 on a corrupt registration file (`test_corrupt_settings_not_overwritten` with and without `--force`, `test_corrupt_opencode_json_not_overwritten`, `test_corrupt_hooks_json_not_overwritten`) switch to assert exit 1 while still asserting the file is untouched.

### T-16
**Classify**
- Nature: `INCIDENT`
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
  1. Copy `skill/hooks/host_adapter.py` and `skill/hooks/rule_gate.py` over their `adapters/dot-aidd/hooks/` twins (this task also owns the `rule_gate.py` twin) and confirm with `cmp`.

### T-17
**Classify**
- Nature: `INCIDENT`
- Priority: 3 MEDIUM
- Kind: LOGIC

**Estimate**
- Effort: Low
- Agent min: 8
- Human ref hours: 0.4
- Tokens (est): 45k
- Agent role: docs
- Model tier: medium

**Decompose**
- Objective: the documentation states what is hardened and what remains.
- Activities:
  1. `adapters/README.md`: the Antigravity known limits (1) to (5) become "hardened in Amendment 1" with the exact behaviour (depth limit 100, protected files, atomic install, exit 1) and keep what remains open (the app and IDE flavours, `multi_replace_file_content`, host exit-code semantics, a non-`python` interpreter name).

### T-18
**Classify**
- Nature: `INCIDENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: High
- Agent min: 14
- Human ref hours: 0.7
- Tokens (est): 80k
- Agent role: tests
- Model tier: high

**Decompose**
- Objective: executed proof of the amendment, once, after the builders.
- Activities:
  1. `aidd verify specs/011-aidd-antigravity-adapter` (V-1 to V-5, the full suite once, in the background) and the spec 010 equivalence test.
  2. One real `agy` prompt (the scratch project of spec 011) asking the model to create `.agents/python.bat`: denied by the gate, the file does not exist; then `.agents/rules/x.md` is creatable (approve the scratch spec only if needed, otherwise report the R6 denial as the expected outcome for non-protected files); re-run the b1SycLink install and doctor; write everything to `evidence/amendment-1-summary.md`.

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-01, T-02, T-03, T-04, T-05, T-06, T-07 | builder, docs, tests | 12 | 410 | 0.6 |
| 2 | T-08, T-09 | builder, docs | 8 | 65 | 0.4 |
| 3 | T-10 | tests | 16 | 90 | 0.8 |
| 4 | T-11, T-12, T-13, T-14, T-15 | builder, tests | 12 | 315 | 0.6 |
| 5 | T-16, T-17 | builder, docs | 8 | 60 | 0.4 |
| 6 | T-18 | tests | 14 | 80 | 0.7 |

Total agent time (critical path): 70 min
Total tokens (k): 1020

## Approval gate

**Present the table above as a dry-run and wait for explicit approval before Step 5 starts on any row.**

Approved: 2026-10-13 hash:81286ab52e92

## Definition of Done (applies to every task above)
1. Code implements exactly the codes cited, in exactly the target file, following the plan's Naming & File Contract.
2. Builders only self-check (compile, parse and the targeted test file of their own change, once); the full executed verification runs once per wave group, in T-10 and in T-18, after the builders.
3. Every FR has a test or a recorded run (R10); anything not runnable is `not-verified` with a manual script.
