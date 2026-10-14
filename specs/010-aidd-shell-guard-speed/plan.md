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

## Decision: full-key memo plus lazy evaluation, no lexical prefilter (spec option A)

A lexical prefilter ("a plain word cannot name a protected path") is UNSOUND and is excluded: `real_path` follows symlinks and junctions, so a bare word can resolve to a protected file; the guard strips quotes first, so `"spe"cs` and `"events".toon` have no marker in their raw text; and a working directory inside `.gemini` or `.opencode` makes bare names protected. Instead:

1. **Memo keyed by the FULL arguments.** `_locate(path)` depends only on the absolute path, the project directory and the disk, none of which change during one check, so it is memoized by that path; `_abs_path(tok, base)` is memoized by the pair `(tok, base)`, never by `tok` alone (the tracked shell cwd after a `cd` reaches it as `base`). `rule_gate.py` runs as a fresh process per hook call, but tests call it in-process, so expose `_clear_caches()` and call it at the start of `decide(event)`; the tests that call `_specs_tok` / `_host_tok` directly clear it in `setUp`.
2. **Lazy per-argument check.** In `_shell_block`, compute `hit()` only for the verbs that consume `prot_args`, and only for the arguments they need, instead of eagerly for every argument of every verb. A verb that does not consume the result (`echo`, `printf`, `cat`, `ls`) resolves nothing. The set of verbs and the order of evaluation of the decision are unchanged, so the decision is identical.
3. `_prot_tok` is left unchanged (it never touches the filesystem).

Known residual: a padded command whose verb DOES consume protected-path arguments with thousands of DISTINCT tokens (for example `rm a1 a2 ... a2000`) still costs about one resolution per distinct token; the fail-closed 15 s timeout of the host adapter covers it. Documented as a limit, not a bypass.

## Decision contract that must not change

For every command the pair (blocked, message) equals the previous implementation. Test strategy (T-02): load the previous guard pinned at commit `3cf5fcc` (`git show 3cf5fcc:skill/hooks/rule_gate.py` into a temp module, loaded AFTER the real `skill/scripts` folder is on `sys.path` because the old file computes `SCRIPTS_DIR` from its own location; the pin keeps the comparison meaningful after the change is committed) and compare it with the new guard over: the command lists of the existing `tests/test_rule_gate.py`, 300 generated commands (quoted paths, quoted fragments, globs, `bash -c` nesting, `..` forms, backslashes, 8.3 names, bare names that are symlinks or junctions to protected files, bare names from working directories inside `specs/<id>`, `.gemini` and `.opencode`, padded words), plus the timing assertions of FR-1004; a monkeypatched counter on `_locate` shows one resolution per repeated token and none for the arguments of `echo` (FR-1001, FR-1002). The padding in the timing tests states how it is built (spaced plain words after `echo`).

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
