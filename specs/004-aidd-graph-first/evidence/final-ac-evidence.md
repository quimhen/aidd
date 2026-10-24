# Spec 004 — final evidence (2026-10-24, after the fix batch)

Code state: worktree after the fix batch; installed skill synced with the repo (`diff -rq skill/scripts ~/.claude/skills/aidd/scripts` shows only the old `aidd_evidence.py.bak`).
Protocol E9: every command below ran ONCE on this code state.

## Gate runs

| What | Command | Result | Wall |
|---|---|---|---|
| Verification table | `aidd verify specs/004-aidd-graph-first` (Jobs: 4) | PASSED 9/9 rows, verify hash e4f8f026df27 | 164.6 s (slowest row V-5: 159.8 s) |
| Affected modules after the fix batch | `python tests/run_parallel.py tests.test_dot_aidd_mirror tests.test_aidd_tools tests.test_install_hooks tests.test_graphs_auto tests.test_graph_trace_method tests.test_code_graph tests.test_read_hint tests.test_find_spec tests.test_hooks tests.test_graph_snapshot tests.test_aidd_status tests.test_evidence tests.test_perf_budget tests.test_prompt_trigger tests.test_aidd_job tests.test_aidd_triage tests.test_sql_graph_incremental` | 17 modules, 116 units, 0 failed | 55 s (8 workers) |

Per-row output: `verify-V-1.txt` .. `verify-V-9.txt` in this folder.

## AC-034 — dynamic before/after of `status` (graph_trace --scripts-dir, same project)

| Code | Command | totals |
|---|---|---|
| rev 69218be (before the 2026-10-24 performance work), scripts extracted with `git archive 69218be skill/scripts` | `python skill/scripts/graph_trace.py --root D:\Fuentes\AIDD --scripts-dir <extracted>/skill/scripts -- status` | reads 7792, spawns 7, rereads 7646, pairs 11; 141.1 s (profiler on) |
| worktree after the work | `python skill/scripts/graph_trace.py --root D:\Fuentes\AIDD -- status` | reads 374, spawns 3, rereads 226, pairs 12; 8.4 s (profiler on) |

About 21x fewer file reads, 2.3x fewer spawns, 17x less wall time for the same command. (Earlier AC-013 check: two runs of the same trace agree on every count.)

## AC-012 — `repeats --full`

`graph_snapshot.py --root . repeats --cmd status --label verify-before-04 --full` exits 0 with 346 lines: it lists `sink:file:*` (111 paths, 10 callers, `in_loop@_locked`) and `FUNC skill/scripts/aidd_rules.py::_evidence_path ... ext_in_loop=pathlib.Path,replace,resolve`. The same command on `verify-after-04` exits 0 with 354 lines and has 0 lines with `ext_in_loop=resolve`. The generic `sink:file:*` is expected: a path built from constants has no literal. Static path counts for `sink:file:*` went from 111 to 118: that metric is NOT the performance evidence (see AC-034).

## AC-021 / AC-022 — SQL on b1SycLink (read-only inputs)

- Relative paths now resolve against `--root`: `sql_graph.py --root D:/Fuentes/b1SycLink --out <scratch> --kind schema --checkpoint <scratch> eDoc/supabase/migrations Payroll/supabase/migrations` exits 0: 293 tables, 63 views, 4452 columns, 526 indexes, 8024 edges, 27 skipped statements; 5.1 s; no KeyError.
- First verifier run (absolute paths): schema 4.2 s then 1.3 s (`replayed 0 of 878`); dml 7.8 s then 1.9 s (`analysed 0 bodies, reused 1540`); 1411 functions, 1093 `escribe` edges.

## AC-010

`aidd_graphs.py --root . show code latest_verify_run` prints callers, callees, `ext: 4 external calls`, `sinks reached: * (file)` and `implements: FR-205 -> 007-aidd-review-html-close-gate (Spec — AIDD 007 ...): Close gate = executed verification ...`.

## Not verified end to end

AC-019 / AC-020 (graph-first nudge for Grep/Glob/Bash): the hook code and its unit tests pass (tests.test_read_hint, tests.test_aidd_status), but the matcher `Read|Grep|Glob|Bash|PowerShell` is registered only after the owner runs `python ~/.claude/skills/aidd/scripts/install_hooks.py`. The human test script is in `ac019-ac020-nudge-not-verified.txt`.

## Findings outside this spec

`tests.test_host_doctor`, `tests.test_host_install` and `test_cli_accepts_host_antigravity` fail with `shipped bundle not found at ~/.claude/skills/adapters/dot-aidd`: `install_host.py` is untouched by this spec (last changed in 69218be); the environment has no packaged `aidd/_data` bundle. Not attributable to 004.

## Update and validation of every LLM host (2026-10-24, owner approved: "actualiza el skill en todos los llm" / "valida actualizacion de todo")

| Target | Action | Validation result |
|---|---|---|
| Claude Code skill `~/.claude/skills/aidd` | files copied from the repo (scripts, hooks, templates, SKILL.md, AIDD.md) | `diff -rq` vs repo: 0 differences in scripts, hooks, templates, extensions; SKILL.md and AIDD.md identical (only an old `aidd_evidence.py.bak` extra) |
| Claude Code commands `~/.claude/commands` | `aidd-converge.md` and `aidd-tasks.md` copied | 8 of 8 identical to `commands/` |
| Claude Code hooks `~/.claude/settings.json` | `install_hooks.py` run | "Upgraded (new matcher / timeout): PreToolUse"; read_hint matcher is now `Read|Grep|Glob|Bash|PowerShell`, timeout 10; sessions must be restarted |
| Codex `~/.codex/hooks.json` | hooks already point at `~/.claude/skills/aidd/hooks` (current); read_hint matcher aligned | matcher `Read|Grep|Glob|Bash|PowerShell` |
| Antigravity global `~/.agents/skills/aidd` | 18 files + SKILL.md + AIDD.md copied (it was stale: 8 scripts differed, 7 missing) | 0 differences afterwards |
| Gemini global `~/.gemini/config/skills/aidd` | none needed | symlink to `D:/Fuentes/AIDD/skill` (always current) |
| b1SycLink bundles (gemini, opencode, antigravity) | `install_host.py install <host> D:/Fuentes/b1SycLink`: 7 new files written; the 7 skipped `.aidd` files were proven identical to older shipped versions in git history (no local edit) and overwritten with `--force` through the opencode install; `GEMINI.md` deliberately kept (its only local change is the line `@AGENTS.md`) | after: gemini 68 rows, 1 not unchanged (GEMINI.md, intended); antigravity 69/0; opencode 69/0 through the installed CLI; `.aidd/scripts` vs `adapters/dot-aidd/scripts`: 0 differences; `aidd doctor`: D1 PASS x3 ("equal to the shipped adapters/dot-aidd"), 19 PASS, 6 WARN (D6: 1428 `rules_override` events, newest 2026-10-07, pre-existing; D7 versions, informational) |
| `aidd` CLI package (terminal command) | the installed copy was a stale snapshot (34 scripts, `cli.py` 29509 bytes, NO `job`/`triage`/`tools`/`size`); reinstalled with `pip install --no-deps --force-reinstall D:/Fuentes/AIDD` (10 s) | from a neutral cwd `aidd --help` lists the four commands; package `_data` has 41 scripts, 0 differences with `skill/scripts`; `cli.py` identical; `aidd install --json --host opencode D:/Fuentes/b1SycLink` through the installed CLI: 69 rows, 0 changes |
| Defects found by this validation | (1) `aidd --help` text of `job`, `triage`, `tools`, `size` described other tools (written by a builder without the real interface): fixed in `aidd/cli.py`; (2) `aidd_doctor.repo_root` lacked the package `_data` fallback that `install_host.py` has: fixed, D1 now PASS | re-run of `aidd doctor` from a neutral cwd: D1 PASS in the three hosts |
| Still failing, outside 004 | `tests.test_host_install` and `tests.test_host_doctor`, test `test_cli_accepts_host_antigravity` (2 failures of 73 tests): they run with `PYTHONPATH` on the checkout, so `aidd` resolves to the checkout (no `_data`) while the scripts come from the installed skill, and neither `install_host._repo_root` nor `aidd_doctor.repo_root` considers the checkout (`aidd` package parent) as a candidate | not fixed here on purpose (a fifth code edit after the closing audit would exceed the R7 tolerance); fix is one extra candidate in each resolver, to do right after closing |

Edits made while or after the closing audit ran (not audited, disclosed): `aidd/cli.py` help strings, `skill/scripts/aidd_doctor.py` resolver, plus the host/package updates above.
