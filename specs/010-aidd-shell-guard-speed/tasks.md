# Tasks — AIDD shell guard speed (spec 010)

One row = one small PR. Estimates are agent wall time and tokens; the Human ref is derived. Revised after the pre-build coherence audit.

Tasks reference the single pre-build coherence audit (spec, plan, graph, estimates) that runs before this list is approved; there is no per-edit audit.

**Every task's implementation prompt restates these standards explicitly — a fresh agent doesn't inherit them from context:**
- **Scope: in and out, both stated explicitly.** In scope = exactly the codes and target file named by the row (plus the twins it names), nothing else. Anything else is a note back, never a bundled fix.
- **If anything needed to proceed is missing or ambiguous, stop and report it** instead of guessing.
- **SOLID** on any code touched.
- **One class/component per file.**
- **Naming & File Contract from `plan.md`**: snake_case Python, private helpers start with `_`.
- **Antifragile / Design for Failure**: the guard is a security gate: no argument is skipped by lexical guesswork, only results that no verb uses are not computed; every cache is cleared per decision call.
- **Decisions never change**: the (blocked, message) pair of every command must equal the previous guard's (the one pinned at commit 3cf5fcc).

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-01 | FR-1001, FR-1002, FR-1003 | skill/hooks/rule_gate.py | LOGIC | | | any other file; any new rule or message change; any lexical prefilter |
| T-02 | FR-1001, FR-1002, FR-1003, FR-1004 | tests/test_rule_gate_shell_speed.py | LOGIC | | | any other file |
| T-03 | FR-1003 | adapters/dot-aidd/hooks/rule_gate.py | LOGIC | | | editing the hook itself |
| T-04 | FR-1001, FR-1002, FR-1003, FR-1004, FR-1005 | specs/010-aidd-shell-guard-speed/evidence/verify-summary.md | LOGIC | | | editing source; qa-audit.md |

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
- Tokens (est): 70k
- Agent role: builder
- Model tier: high

**Decompose**
- Objective: remove the per-word filesystem resolution from the shell guard without changing any decision.
- Activities:
  1. Memoize `_locate` by path and `_abs_path` by `(token, base)`; add `_clear_caches()` and call it at the start of `decide(event)`.
  2. Make the `prot_args = [a for a in args if hit(a)]` evaluation in `_shell_block` lazy: only for the verbs that consume it, only for the arguments they need; `_prot_tok` unchanged; no lexical prefilter.
  3. Re-profile with the scratchpad script and confirm the per-word cost is gone; run only `python -m pytest tests/test_rule_gate.py -q -x` once.

### T-02
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 12
- Human ref hours: 0.6
- Tokens (est): 55k
- Agent role: tests
- Model tier: medium

**Decompose**
- Objective: prove decisions are identical and the speed target is met.
- Activities:
  1. Load the guard pinned at commit 3cf5fcc (`git show 3cf5fcc:skill/hooks/rule_gate.py` into a temp module, after `skill/scripts` is on `sys.path`) and compare (blocked, message) with the new guard over the generated command set (AC-1005, including symlink, junction, quoted-fragment and host-folder cases) and AC-1001..AC-1004.
  2. Count `_locate` calls with a monkeypatch: one per repeated token, none for the arguments of `echo` (FR-1001, FR-1002); `_clear_caches()` in `setUp`.
  3. Timing assertions: 2 KB padded under 500 ms, 12 KB under 2 s, 400 KB under 5 s, legitimate read-only heredoc under 500 ms; state in the test how the padding is built (spaced plain words after `echo`); generous margins for slow machines, skip nothing.

### T-03
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
- Objective: keep the installed copy identical.
- Activities:
  1. Copy `skill/hooks/rule_gate.py` over `adapters/dot-aidd/hooks/rule_gate.py` and confirm with `cmp`.

### T-04
**Classify**
- Nature: `REQUIREMENT`
- Priority: 2 HIGH
- Kind: LOGIC

**Estimate**
- Effort: Medium
- Agent min: 14
- Human ref hours: 0.7
- Tokens (est): 50k
- Agent role: tests
- Model tier: high

**Decompose**
- Objective: executed proof once, after the builders.
- Activities:
  1. Run `aidd verify specs/010-aidd-shell-guard-speed` (full suite once, in the background) and write the summary file with the before and after timings.
  2. Re-run the real OpenCode padded-command probe if time allows and record it.

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-01, T-02 | builder, tests | 12 | 125 | 0.6 |
| 2 | T-03 | builder | 4 | 15 | 0.2 |
| 3 | T-04 | tests | 14 | 50 | 0.7 |

Total agent time (critical path): 30 min
Total tokens (k): 190

## Approval gate

**Present the table above as a dry-run and wait for explicit approval before Step 5 starts on any row.**

Approved: 2026-10-13 hash:9b14e84de574

## Definition of Done (applies to every task above)
1. Code implements exactly the codes cited, in exactly the target file, following the plan's Naming & File Contract.
2. Builders only self-check statically; the executed verification runs once, in T-04, after the builders.
3. Every FR has a test or a recorded run (R10); anything not runnable is `not-verified` with a manual script.
