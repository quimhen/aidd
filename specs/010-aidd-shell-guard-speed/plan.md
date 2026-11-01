# Plan — AIDD shell guard speed (spec 010)

No screens: the Screen → Code and Component → Code maps do not apply. This plan fixes names, ownership and the decision contract that must not change. Revised after the pre-build coherence audit (a lexical prefilter was rejected as unsound).

## Naming & File Contract (fill this first — everything below depends on it)
| Item | Convention |
|---|---|
| Classes / components / types | PascalCase |
| Functions / variables / methods | snake_case (the repo's own Python style); module-level private helpers start with `_` |
| File names | snake_case: `tests/test_rule_gate_shell_speed.py` |
| Classes per file | One. Never bundle multiple classes into one file. |
| File-path pattern | hook in `skill/hooks/rule_gate.py`, byte-identical mirror in `adapters/dot-aidd/hooks/rule_gate.py`, test in `tests/` |

## Diagnosis (measured, not guessed)

`rule_gate._decide_bash(event, ti)` on a command that mentions a protected path costs about 4.3 ms per word (250 words 1.1 s, 1000 words 4.4 s, 2000 words 8.4 s). cProfile on a 2 KB command: 6.3 s total, 5.98 s inside `_locate` (3006 calls, 3 per word), of which `rel_to_root` → `canon_path` → `real_path` → `ntpath.realpath` → `nt._getfinalpathname` (30 058 calls). The call sites are `_host_tok` (2005 calls), `_specs_tok` (1001) and the per-word `hit()` in `_shell_block` (1000). Cause found by the audit: `prot_args = [a for a in args if hit(a)]` in `_shell_block` resolves EVERY argument of EVERY verb, including `echo`, before it knows whether the verb uses the result. The cost is per-word filesystem path resolution, not the tokenizer.

## Original speed decision: full-key memo plus lazy evaluation, no lexical prefilter (spec option A)

A lexical prefilter ("a plain word cannot name a protected path") is UNSOUND and is excluded: `real_path` follows symlinks and junctions, so a bare word can resolve to a protected file; the guard strips quotes first, so `"spe"cs` and `"events".toon` have no marker in their raw text; and a working directory inside `.gemini` or `.opencode` makes bare names protected. Instead:

1. **Memo keyed by the FULL arguments.** `_locate(path)` depends only on the absolute path, the project directory and the disk, none of which change during one check, so it is memoized by that path; `_abs_path(tok, base)` is memoized by the pair `(tok, base)`, never by `tok` alone (the tracked shell cwd after a `cd` reaches it as `base`). `rule_gate.py` runs as a fresh process per hook call, but tests call it in-process, so expose `_clear_caches()` and call it at the start of `decide(event)`; the tests that call `_specs_tok` / `_host_tok` directly clear it in `setUp`.
2. **Lazy per-argument check.** In `_shell_block`, compute `hit()` only for the verbs that consume `prot_args`, and only for the arguments they need, instead of eagerly for every argument of every verb. A verb that does not consume the result (`echo`, `printf`, `cat`, `ls`) resolves nothing. The set of verbs and the order of evaluation of the decision are unchanged, so the decision is identical.
3. `_prot_tok` is left unchanged (it never touches the filesystem).

Known residual: a padded command whose verb DOES consume protected-path arguments with thousands of DISTINCT tokens (for example `rm a1 a2 ... a2000`) still costs about one resolution per distinct token; the fail-closed 15 s timeout of the host adapter covers it. Documented as a limit, not a bypass.

## Decision contract and four enumerated exceptions

For every command the pair (blocked, message) equals the previous implementation except the four explicitly enumerated portable-path amendment cases. Test strategy (T-02): load the previous guard pinned at commit `3cf5fcc` (`git show 3cf5fcc:skill/hooks/rule_gate.py` into a temp module, loaded AFTER the real `skill/scripts` folder is on `sys.path` because the old file computes `SCRIPTS_DIR` from its own location; the pin keeps the comparison meaningful after the change is committed) and compare it with the new guard over: the command lists of the existing `tests/test_rule_gate.py`, 300 generated commands (quoted paths, quoted fragments, globs, `bash -c` nesting, `..` forms, backslashes, 8.3 names, bare names that are symlinks or junctions to protected files, bare names from working directories inside `specs/<id>`, `.gemini` and `.opencode`, padded words), plus the timing assertions of FR-1004; a monkeypatched counter on `_locate` shows one resolution per repeated token and none for the arguments of `echo` (FR-1001, FR-1002). The padding in the timing tests states how it is built (spaced plain words after `echo`).

## File ownership (one owner per file)

| File | Task | Notes |
|---|---|---|
| `skill/hooks/rule_gate.py` | T-01 | memo, `_clear_caches()` called from `decide`, lazy `hit()`; no behaviour change, docstring note |
| `tests/test_rule_gate_shell_speed.py` | T-02 | equivalence vs the guard pinned at 3cf5fcc, `_locate` call counting, AC-1001..AC-1005, timings |
| `adapters/dot-aidd/hooks/rule_gate.py` | T-03 | byte-identical copy after T-01 (the mirror test already guards it) |
| `specs/010-aidd-shell-guard-speed/evidence/verify-summary.md` | T-04 | `aidd verify` result; the closing auditors write `qa-audit.md` |

## Risks and how the plan covers them

- **Skipping an argument that really resolves to a protected path (a bypass).** No token is skipped by guesswork: only results no verb uses are not computed; equivalence test against the pinned old guard on generated commands including symlink, junction, quoted-fragment and host-folder cases; the existing `test_rule_gate.py` tests.
- **Stale memo in the in-process tests.** `_clear_caches()` at the start of every `decide` and in the direct-call tests' `setUp`.
- **Linux/macOS regressions.** The change is platform-neutral; V-3 runs the whole suite.

## Verification plan

V-1 to V-3 of the spec (V-2 also runs `tests/test_host_gates.py`, which covers the fail-closed timeout, FR-1005); the full suite once at the end.


## Amendment — portable path exceptions

# Plan — 010 portable path exceptions

Input: `amendment-portable-path-exceptions-spec.draft.md`; the owner reviewed the exceptions and approved the resulting tasks. The `.AIDD` case remains subject to R6 as clarified by the owner. T-23 is local evidence. No UI or database work.

## Naming & File Contract
| Item | Convention |
|---|---|
| Python module, functions and variables | existing snake_case; keep current helper signatures |
| Tests | existing unittest classes and `test_...` methods |
| Mirror | `skill/hooks/rule_gate.py` → `adapters/dot-aidd/hooks/rule_gate.py`, byte-identical |

## Scope and behavior
The Linux T-23 cases are: drive `tasks.md` allow→deny; case-distinct native `.AIDD/Evidence/events.toon` remains subject to R6 and is not the protected lowercase `.aidd` path; `CMakeLists.txt` allow→deny under R6; `docs/A.MD` deny→allow under other applicable guards. Neither ordinary path is exempt from applicable rules. Drive `review.md` forms remain deny with same message but gain protected lexical classification. Other decisions and messages remain unchanged. Never access a real UNC share; lexical analysis must not assert foreign tokens refer to native objects.

## Responsibilities and dependencies
Wave 1 test owner adds narrowly specified regression tests in `tests/test_cross_platform_paths.py`; wave 2 guard owner changes `skill/hooks/rule_gate.py` and mirrors via a script, retaining existing names `_specs_tok`, `_abs_path_raw`, `_locate`. Do not edit `skill/scripts/aidd_evidence.py`: T-19 already conditions such edits on need, and necessity is not established; stop and report if necessary. Coordinate with 009 T-18/T-19 and spec 007 before any shared change. A fresh independent auditor reviews the resulting delta once after the coordinated verification.

## Verification plan
The owner/orchestrator runs one coordinated targeted discovery on Windows and Linux with `python -m unittest discover -s tests -p test_cross_platform_paths.py -v`, `python -m unittest discover -s tests -p test_rule_gate.py -v`, `python -m unittest discover -s tests -p test_rule_gate_shell_speed.py -v`, `python -m unittest discover -s tests -p test_dot_aidd_mirror.py -v`; execute each module once per verified environment, serially. Compare the pinned old guard for all unchanged corpus cases, including decisions and messages; the four approved exceptions are verified independently and must not disable the equivalence corpus. Count missing baseline/loader and platform skips as not verified, not success. Record outputs and provenance without secrets; no full-suite rerun in this scope unless a distinct final gate requires it, and reuse eligible prior evidence under AIDD rules.


Pinned baseline equivalence retains the narrowly documented spec-011 message-list normalization already present in `tests/test_rule_gate_shell_speed.py`; outside that documented compatibility normalization and four proposed full-gate exceptions, compare the complete decision and message. If an exception appears in the existing 300-command corpus, assert its explicit expected outcome and retain all 300 checks; stop for an authorized test-file amendment if the existing compare helper cannot express it.
