# T-25 verification evidence: 004-aidd-graph-first (2026-10-24)

Verifier run, one pass per verification (rule E9). STEP 1 ran in the background (aidd verify Jobs: 4 + run_parallel 8 workers at the same
time) while STEP 2 ran, so every STEP 2 timing up to the sql_graph runs was taken under heavy CPU load.

| AC/FR | command | result | evidence file | seconds |
|---|---|---|---|---|
| T-25 step 0 | sync skill/{scripts,hooks,templates,SKILL.md,AIDD.md} -> ~/.claude/skills/aidd; diff -rq | match (only a pre-existing aidd_evidence.py.bak remains in the installed folder) | step0-skill-sync.txt | <1 |
| V-1..V-9 (FR-001..FR-043) | python -m aidd.cli verify specs/004-aidd-graph-first | FAIL 5/9 rows (V-4, V-5, V-7, V-8 fail) | verify-run.txt, verify-V-1..9.txt | 228.5 |
| changed modules | python tests/run_parallel.py --changed | FAIL 9 of 296 units (38 modules) | run-parallel-changed.txt | 274.3 |
| triage | python -m aidd.cli triage | 0 shared, 4 specific; nothing written | triage.txt | 1.0 |
| AC-009 | code_graph.py full + no-op on D:\Fuentes\AIDD | PASS structure (code_state <- code_fingerprint, -> _code_state_scan -> _code_state_git -> git); time targets missed under load (10.4 s / 2.7 s vs 6 / 1.5); 4.07 MB | ac009-ac010-ac012-ac018-code-graph-snapshots.txt | 10.4 + 2.7 |
| AC-010 | aidd graphs show code latest_verify_run | PARTIAL: 9 lines, callers/callees/sinks/implements FR-205; spec title NOT joined | same | 2.1 |
| AC-011 | aidd graphs show method R10 | PASS | ac015-graphs-refresh-status.txt | 1.3 |
| AC-012 | snapshot --rev 69218be / after, diff, repeats --cmd status | FAIL as written (no events.toon sink, last_code_edit_ts not listed, `--full` flag missing) | ac009-ac010-ac012-ac018-code-graph-snapshots.txt | 9.9 + 8.8 + 4.2 + 1.7 + 1.5 |
| AC-013 | graph_trace.py -- status x2, -- progress | PASS: both runs reads 370, spawns 3, rereads 232, pairs 12 (on AIDD) | ac013-trace.txt | 15.5 / 9.6 / 3.6 |
| AC-014, AC-016, AC-017, AC-033 | tests.test_graph_snapshot (V-2), tests.test_code_graph (V-1) | PASS (unit level) | verify-V-1.txt, verify-V-2.txt | 60.0 / 18.0 |
| AC-015 | graphs refresh {code,method,spec,progress} --wait --force; graphs status | PASS: 4 graphs fresh | ac015-graphs-refresh-status.txt | 3.6+2.1+1.3+2.9+3.0 |
| AC-018 | snapshot --rev 69218be; repeats --cmd nope | PASS (4603 vs 5183 nodes; exit 2) | ac009-ac010-ac012-ac018-code-graph-snapshots.txt | 9.9 / 1.3 |
| AC-019, AC-020 | Grep/Bash nudge | not-verified (matcher not registered); test_read_hint passed in V-4 | ac019-ac020-nudge-not-verified.txt | - |
| AC-021 | sql_graph.py schema + dml on b1SycLink migrations (absolute paths) | PASS: exit 0, skipped_statements 27/28, 1411 functions, 1093 escribe edges, no KeyError | ac021-ac022-sql-graph.txt | 4.2 / 7.8 |
| AC-022 | same, second run | PASS for unchanged input (replayed 0 of 878; analysed 0, reused 1540); edit branches via V-6 PASS | ac021-ac022-sql-graph.txt | 1.3 / 1.9 |
| AC-023, AC-025, AC-031 | grep SKILL.md / AIDD.md / tasks template / spec | PASS static: E9 and T1 in both docs, run_parallel --changed cited, Jobs: 4, template has the aidd tools line | (this index) | <1 |
| AC-024, AC-026 | tests.test_perf_budget, tests.test_prompt_trigger (V-7) | FAIL (2 tests) | verify-V-7.txt | 31.1 |
| AC-027 | aidd job run x2 / last / edit / run / --bg + wait / list (scratch project) | PASS | ac027-job.txt | 0.9 / 0.5 / 0.6 / 0.6 / 0.7 / 0.5 |
| AC-028, AC-029 | tests.test_aidd_job, tests.test_aidd_triage (V-8) | FAIL (1 test: test_list_shows_job) | verify-V-8.txt | 35.0 |
| AC-030 | aidd tools verify (AIDD); aidd_tools.py db --root b1SycLink | PASS (cache written inside b1SycLink, see file) | ac030-ac032-tools-size.txt | 1.0 / 1.5, 0.8 |
| AC-032 | aidd size --files aidd_tools.py; --spec 004 | PASS (XS, L) | ac030-ac032-tools-size.txt | 0.4 / 0.6 |
| perf 2026-10-24 | aidd status --refresh (single) + snapshot diff | 10.8 s; speed-up not proven (see file) | perf-status-refresh.txt | 10.8 |

## Verdict per AC
- PASS: AC-009 (structure; time targets missed under load), AC-011, AC-013 (on AIDD), AC-014, AC-015, AC-016, AC-017, AC-018, AC-021, AC-022, AC-023, AC-025, AC-027, AC-030, AC-031, AC-032, AC-033.
- PARTIAL/FAIL: AC-010 (FR-205 spec title not joined in `graphs show`).
- FAIL: AC-012 (repeats does not name events.toon nor list last_code_edit_ts/resolve in_loop; `repeats` advertises `--full` which is not a valid flag).
- FAIL: AC-024 / AC-026 (V-7), AC-028/AC-029 row V-8, rows V-4 and V-5 (spec verification FAILED 5/9).
- not-verified: AC-019, AC-020 (hook matcher not registered by the owner; human script in ac019-ac020-nudge-not-verified.txt).
- Not run by the verifier: AC-001..AC-008 (Integraciones/b1SycLink progress cases outside this brief).

## Total wall time of the verifier run: about 12 min (705 s to this index; STEP 1 runs 228.5 s and 274.3 s overlapped with STEP 2).

## FAILURES for the owner
1. tests.test_find_spec (V-4, 10 errors): TestAuditRev1.{test_fallback_does_not_invent_matches, test_fulltext_fallback_when_index_misses_a_real_word, test_memory_lines_are_printed_by_the_cli, test_search_without_memory_is_unchanged, test_short_query_words_match_through_the_fallback}, TestEndToEnd.{test_exact_code_match_exits_0_and_ranks_it_top, test_index_is_reused_when_nothing_changed, test_index_rebuilds_after_a_real_edit, test_no_match_exits_1}, TestIndexOptimization.test_old_version_index_is_rebuilt: `PermissionError: [WinError 32] The process cannot access the file because it is being used by another process: 'C:\Users\jquimis\AppData\Local\Temp\tmp...'` at TemporaryDirectory cleanup (same cause as run_parallel's test_hooks.TestRecorders and TestCredentialHygiene, 2 errors each). Likely a child process still holding the temp dir; may be load related.
2. tests.test_evidence.TestRouting.test_kinds_are_routed_and_merged (V-5 and run_parallel): `AssertionError: ',graph_miss,' not found in` the session events.toon (the graph_miss kind is not routed to the session log).
3. tests.test_perf_budget.TestCodeGraphNoopRebuild.test_noop_rebuild_reparses_nothing_and_is_at_least_twice_as_fast (V-7: 0.56, run_parallel: 0.61): `no-op rebuild took 0.56 of a full build (best of 3)`, budget 0.5. Ran under load.
4. tests.test_perf_budget.TestPromptFindSpecDedupe.test_second_identical_prompt_spawns_no_find_spec (V-7 and run_parallel): `AssertionError: '[aidd]' not found in ''` (the first prompt produced no hook output).
5. tests.test_aidd_job.TestAiddJob.test_list_shows_job (V-8 and run_parallel): `aidd job: error: unrecognized arguments: --root <tmp>` (test passes --root after the subcommand; CLI only accepts it before).
6. tests.test_graphs_auto.TestAuto (run_parallel only; failures=3, errors=2): visible one is test_off_switch_and_no_graphs: `Lists differ: ["Graph 'code' (code): missing, refresh started in background; ..."] != []`; the other 4 names are cut by run_parallel's tail-only output.
7. tests.test_host_doctor.TestAntigravityDoctor.test_cli_accepts_host_antigravity: `WARN D1 shipped adapters/dot-aidd not found at C:\Users\jquimis\.claude\skills\adapters\dot-aidd`; tests.test_host_install.TestAntigravityInstall.test_cli_accepts_host_antigravity: `error: shipped bundle not found at C:\Users\jquimis\.claude\skills\adapters\dot-aidd` (CLI now resolves the installed skill first; bundle lookup misses).
8. Tool defects found while verifying: `graph_snapshot.py repeats` prints "... N more (--full)" but `--full` is rejected (exit 2); `sql_graph.py` resolves positional inputs against cwd instead of `--root`; `aidd triage` keys unittest failures as `pytest:(failures=N)` so different failures collapse and test names are lost; `aidd_tools.py db --root <proj>` writes `<proj>/.aidd/graphs/tools.cache.json` into the target project (created D:\Fuentes\b1SycLink\.aidd\graphs\tools.cache.json, left in place).
