# Spec — AIDD shell guard speed: make rule_gate's shell check fast on long commands (exception E1 of spec 009)

Produced during Step 2 (Align). Measured intake (profile of `rule_gate._decide_bash`, scratchpad `perf/prof_shell.py`): about 4.3 ms per word for a command that mentions a protected path (250 words 1.1 s, 1000 words 4.4 s, 2000 words 8.4 s); 95 % of it is filesystem path resolution (`_locate` → `rel_to_root` → `real_path` → `realpath`, 3 calls per word, `nt._getfinalpathname` 30 058 calls for one 2 KB command). The pre-build audit showed that a lexical prefilter is unsound (symlinks and junctions, quoted fragments, host folders as working directory), so the fix is a full-key memo plus lazy evaluation.

Risk: high
<!-- high: it changes the security gate that blocks writes to protected paths; a wrong shortcut would open a bypass. -->

## Minimum Requirements Checklist (fill before Step 3 starts)

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | `skill/hooks/rule_gate.py` shell guard (`_shell_block`, `_decide_bash`, `_locate`, `_abs_path`) | user — "Confirmo spec diez" | → Step 2 align question |
| New development or modification of something existing? | Modification of the existing guard; originally decisions were to remain unchanged and only their cost change; the amendment enumerates four Linux exceptions | user — "Confirmo spec diez" | → Step 2 align question |
| Does it involve an external service, API, or integration? | No external service; it runs on every Claude Code, Gemini CLI and OpenCode shell tool call that mentions a protected path | repo — specs/009-aidd-host-parity/qa-audit.md:1 | → Step 2 align question |
| Who is requesting it? (role/profile, not necessarily the name) | The project owner, as pending item 3 of spec 009 | user — "Confirmo spec diez" | → Step 2 align question |
| Dependencies on other modules or active developments? | Spec 009 (host adapter fail-closed timeout, mirror in `adapters/dot-aidd/hooks/`), spec 002 (rules R9) | repo — specs/009-aidd-host-parity/qa-audit.md:1 | → Step 2 align question |
| Business objective (1 sentence — what it achieves and why) | A legitimate command of a few KB that mentions `.aidd` or `specs` must be decided in well under a second instead of 4 to 15 s, and a padded one must still be blocked quickly | user — "Confirmo spec diez" | → Step 2 align question |
| Expected visual fidelity level (if there's a mockup): exact \| functional behavior only | Not applicable: no screens | user — "Confirmo spec diez" | → Step 2 align question |

## Executive summary

- **Objective:** Keep shell guard decisions fast and correct the four enumerated Linux path classifications while retaining all other security decisions.
- **Scope:** the original path-resolution memo, lazy evaluation and equivalence tests; the four Linux exceptions and foreign drive-token classification; the byte-identical guard mirror. Out: weakening protected-path checks, resolving foreign shares, new rules, the evidence-log re-parse (E2), Gemini or Antigravity work.
- **Cost:** 6 tasks, 5 waves, about 65 min and 420k tokens; the amendment adds 2 tasks and 35 min.
- **Risks:** a shortcut that skips an argument which really resolves to a protected path (mitigated by lazy evaluation that only skips verbs which never use the result, by an equivalence test against the previous guard over hundreds of generated commands including symlink, junction, quoted-fragment and host-folder cases, and by the existing `test_rule_gate.py` tests).
- **Open decisions:** none.

## Pipeline route

| Step | Status | Reason | Confirmation |
|---|---|---|---|
| -1 | run | `find_spec.py` ran: nearest is 009 (this is its exception E1) | |
| 0 | waived | no visual surface (a hook) | user — "Confirmo spec diez" |
| 1 | waived | no visual surface (a hook) | user — "Confirmo spec diez" |
| 1.5 | waived | no visual surface (a hook) | user — "Confirmo spec diez" |
| 2 | run | | |
| 3 | run | | |
| 4 | run | | |

## Visual debt

None: no `SCREEN-nn` code appears in this spec.

## Scope
- **Included:** memoize path resolution per command in the shell guard, keyed by the full arguments (`_abs_path` by `(token, base)`); evaluate the per-argument protected check lazily, only for the verbs that use its result; keep decisions and messages identical except the four enumerated Linux exceptions; timing and equivalence tests; mirror copy.
- **Excluded:** changing block decisions outside the four enumerated Linux exceptions; any lexical prefilter that skips native filesystem resolution for a token (symlinks, junctions, quoted fragments and host folders make it unsound); the evidence-log re-parse (E2); the Antigravity adapter; any change to the host adapter's timeout (stays 15 s, fail-closed).

## Functional requirements (cite codes, don't redescribe the UI)

| FR-nnn | Requirement | Cites (SCREEN-XX-Fnn / CTL-nnn / API-nnn) |
|---|---|---|
| FR-1001 | Within one decision call, path resolution of the same token (same base directory) is computed once; the memo is cleared at the start of every decision call | — |
| FR-1002 | The per-argument protected check is evaluated only for the verbs that consume its result, not for every argument of every verb (`echo a a a ...` resolves nothing) | — |
| FR-1003 | Preserve the previous guard allow/block decision and message byte-for-byte except for the four explicitly listed Linux exceptions in the portable-path amendment; retain all other applicable R6/R9 protections and native realpath containment. | — |
| FR-1004 | A command padded to 12 KB of spaced words that mentions a protected path is decided in under 2 s (it took 15 s and hit the timeout), and one padded to 400 KB in under 5 s | — |
| FR-1005 | The fail-closed timeout of the host adapter and its message stay unchanged (covered by `tests/test_host_gates.py`) | — |

## Acceptance cases

| Case | Real data (id) | Expected | Edge? |
|---|---|---|---|
| AC-1001 | the measured 2 KB command (1000 words then a redirect into `specs/001-x/tasks.md`; 4389 ms before) | blocked with the same R9 message in under 500 ms | no |
| AC-1002 | the 12 KB padded command that hit the 15 s timeout in spec 009 | blocked by the guard itself in under 2 s | yes |
| AC-1003 | a legitimate 2 KB heredoc that only READS `.aidd/AIDD.md` (it took 4 s) | allowed in under 500 ms | yes |
| AC-1004 | a command run with the working directory inside `specs/001-x` that names only the bare file `tasks.md` | still blocked | yes |
| AC-1005 | 300 generated commands mixing quoted paths, quoted fragments, globs, `bash -c` nesting, `..` forms, 8.3 names, bare names that are symlinks or junctions to protected files, and commands run from inside `.gemini` or `.opencode` | the old and new (decision, message) are identical for all 300 generated commands, except a command matching one of the four enumerated Linux exceptions: explicitly assert its specified old and new outcome rather than skipping it; any other difference fails | yes |

## Verification

Scope: auto

| # | Command | Expected | Covers |
|---|---|---|---|
| V-1 | python -m pytest tests/test_rule_gate_shell_speed.py -q | exit 0 | FR-1001, FR-1002, FR-1003, FR-1004 |
| V-2 | python -m pytest tests/test_rule_gate.py tests/test_host_gates.py tests/test_dot_aidd_mirror.py -q | exit 0 | FR-1003, FR-1005 |
| V-3 | python tests/run_parallel.py | exit 0 | FR-1003 |

## Optimization brief

Automation / parallelism: the equivalence test generates its own commands and compares against the previous guard pinned at commit 3cf5fcc (not hand-written cases only) | the rule_gate change and the tests are independent in one wave | the full suite runs once, in the background

| Option | Cost (tokens / min) | Risk | Recommended? |
|---|---|---|---|
| A. Full-key memo plus lazy per-argument evaluation, decisions unchanged | about 190k / 30 | low to medium: no token is skipped by guesswork, only unused results are not computed | yes |
| B. A lexical prefilter that skips the filesystem for plain words | about 190k / 30 | high: unsound for symlinks, junctions, quoted fragments and host folders (pre-build audit) | no |
| C. Only a length cap that blocks long commands that mention a protected path | about 60k / 10 | low, but it false-blocks legitimate 4 to 8 KB heredocs | no |

Owner pick: A (Recommended), consistent with the owner's request to resolve the exception.

## Optional Align questions

| Question | Answer | Source |
|---|---|---|
| Which states must each screen/flow handle (empty, loading, error, offline)? | Not applicable: no screens | user — "Confirmo spec diez" |
| Who may see or do this (permissions/roles)? | Nobody interacts with it; it runs inside the hooks | user — "Confirmo spec diez" |
| Entry route: how does the user reach this from the app's start? | Every shell tool call on Claude Code, Gemini CLI and OpenCode | user — "Confirmo spec diez" |
| Target devices (phone, tablet, desktop, orientation)? | Windows 11 first (the 4 ms per word is Windows filesystem cost), Linux/macOS must not regress | user — "Confirmo spec diez" |
| Contract owner and status (who defines the backend contract, is it final or still moving)? | The decision contract is the existing behaviour of `_decide_bash` and its tests | user — "Confirmo spec diez" |


## Amendment — portable path exceptions



| Case | Real data (id) | Expected | Edge? |
|---|---|---|---|
| Foreign Windows drive task, Bash redirect on Linux | T-23 `ci-drive-tasks`: `D:/proj/specs/F23-eDoc-POS/tasks.md` | old/current allow → desired deny under applicable protected-shell gate; treat as lexical Windows drive, not as proof of native file existence. | yes |
| POSIX case-distinct ordinary path, Write on Linux | T-23 `ci-native-case-distinct`: `<root>/.AIDD/Evidence/events.toon` | Treat `.AIDD/Evidence` as an ordinary case-distinct path, not the protected `.aidd/evidence`. The `.toon` file remains blocked by R6 while the target spec is unapproved; allow only when all applicable rules permit it. Protected lowercase native paths remain denied. | yes |
| Code classification, Write on Linux | T-23 `ci-cmakelists`: `<root>/src/CMakeLists.txt` | old/current allow → desired deny in the reported unapproved-spec fixture: classify CMakeLists.txt as source subject to R6, not an unconditional ban. | yes |
| Non-code markdown classification, Write on Linux | T-23 `ci-uppercase-markdown`: `<root>/docs/A.MD` | old/current deny → desired allow in the reported fixture: classify uppercase Markdown as non-code subject to other applicable rules, not an unconditional exemption for protected files. | yes |

**Separate lexical correction, not an extra full-gate exception:** on Linux, `ci-drive-review`, `ci-drive-backslash-review` and `drive-mixed-case` already deny at the full gate but both old/current `lexical` fields are false; desired protected-token classification is true. Preserve the full deny and its existing message where unchanged. `ci-drive-tasks` is the one observed full-gate allow→deny case and its lexical classification must also change false→true. Check protected `tasks.md`, `review.md`, mixed case/separators and suffix handling without network access. Do not infer broader observed decision deltas from these four examples.

**Baseline:** both Windows and Linux reports contain 16 JSON cases each; every observed old/current full decision and message is identical. All Windows desired outcomes match old/current. On Linux the 12 remaining full-gate decisions match desired and remain byte-identical; protected UNC, extended UNC, `.aidd` paths, parent traversal and stream cases stay denied, native unrelated and the reported native uppercase plan/tasks cases retain their observed allow. Results do not prove Windows junction behavior or every possible command.
