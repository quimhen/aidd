# QA Audit — 004 AIDD Graph-First (amendment 2026-10-24: FR-014..FR-043, AC-009..AC-034, T-11..T-46)

**Audited by:** independent subagents that built none of the amendment. Pass 1: a closing auditor over the whole amendment (49 tool uses). Pass 2: an incremental closing auditor that re-validated 20 claims against the current code. Pass 3 (after the last code edit, the one the R7 gate counts): one dedicated auditor per domain left uncovered, `security` and `performance`, both read-only (code, tests and recorded evidence; no measurement repeated, rule E9). `database` and `functional` were covered by the earlier auditors. The dispatcher wrote this file from their reports, because an auditor's own write is not counted by the gate until its final report is recorded.

CLOSING AUDIT [domains: database, functional, performance, security] [tasks:ffdb647a] [verify:8b32a0b5]

## Verification summary
Second amendment (current): `aidd verify specs/004-aidd-graph-first` PASSED 12/12 rows, verify hash 8b32a0b5b209, 75.5 s (rows V-5, V-10, V-11, V-12 replace the old single V-5), after the last code edit; auditors of the second amendment ran after it (Rev 6). The text below is the first amendment's record.

Verification: `aidd verify specs/004-aidd-graph-first` PASSED 9/9 rows, verify hash e4f8f026df27, run twice on purpose: 164.6 s (first, machine loaded, slowest row V-5 159.8 s) and 81 s (final, after two small post-audit code edits; V-5 74.1 s). Per-row output of the final run: `evidence/verify-V-1.txt` .. `evidence/verify-V-9.txt`. Gate runs, the dynamic before/after and the validation of every host are in `evidence/final-ac-evidence.md`. `evidence/INDEX.md`, `evidence/verify-run.txt` and `evidence/triage.txt` are from the FIRST verification run (failed, before the fix batch): history only.

## Domain checklist (filled from the auditors' reports)
The first line of the closing auditor's prompt is `CLOSING AUDIT [domains: database, functional, performance, security] [tasks:ffdb647a] [verify:8b32a0b5]`.

Closing auditor id (pass 2): tool_use_id toolu_01MBVeeHuSg25T816vWsPFSZ. Pass 1: tool_use_id toolu_01XP6oAXB4e6ucbVTHPQmqkp. Pass 3 performance auditor: tool_use_id toolu_0151H2ASLRhGi9rksqBrwmfr (header `PERFORMANCE AUDIT [domain: performance] [tasks:59ce9ef2]`). Pass 3 security auditor: header `SECURITY AUDIT [domain: security] [tasks:59ce9ef2]`, agent ab8bfb0565385866d.

| Domain | Covered by auditor? | Result | Key findings |
|---|---|---|---|
| database | yes (pass 1 and 2) | PASS | `sql_graph.py` is static analysis only (no connect/sqlite/psycopg import). KeyError guard skips UPDATE/MERGE targets not in `model.tables` (`sql_graph.py:626-632`, `:1049`); checkpoint = JSON keyed by `_prefix_key` plus parser hash; `_prefix_diff` (`:777`) forces a full replay on a removed / reordered / edited old migration and says why; dml cache keyed by body sha + `_schema_hash`; relative inputs resolve under `--root` first (`:696-700`). Executed: V-6 (17 tests), real data AC-021/AC-022 in `final-ac-evidence.md` |
| functional | yes (pass 1 and 2) | PASS WITH EXCEPTIONS | 39 of 46 amendment codes PASS with an executed check; AC-019/AC-020 (and FR-025..FR-027 end to end) not exercised in a real session; AC-012 partial; AC-016 dogfood baseline never taken |
| performance | yes (pass 3, dedicated) | PASS WITH EXCEPTIONS | N+1, re-read and spawn reductions are real, count-based and tested (tests/test_perf_budget.py asserts counts; `time.perf_counter` only feeds messages); AC-034 is a sound same-command before/after (reads 7792 -> 374, spawns 7 -> 3, 141.1 s -> 8.4 s, profiler on both). Residuals: `aidd_rules._read` has no cache (`aidd_rules.py:1639-1646`; 240 reads, 203 re-reads per `status`); `events.toon` read 5x per `status`, its "cached parse" is not demonstrated by a runtime trace; no-op code-graph refresh 2.7-3.6 s and `status --refresh` 10.8 s; V-5 row 159.8 s of 164.6 s; `prompt_trigger.py:186` runs find_spec with `timeout=10` inside a 10 s hook (no margin on the first prompt) |
| security | yes (pass 3, dedicated) | PASS WITH EXCEPTIONS | No injection, deserialization, shell or hook-blocking defect: every subprocess is an argv list (no `shell=True`, `os.system`, pickle, eval, yaml.load in scope); label regex `^[A-Za-z0-9._@-]{1,64}$` plus `..` ban (`graph_snapshot.py:50`, `:113`); `--rev` refused if it starts with `-`, resolved by `rev-parse --verify` to a 40/64-hex sha (`:324-331`); `_extract_tar` skips absolute, `..`, symlinks and specials (`:334-352`); hooks wrap work in try/except and exit 0, never deny. Findings: L8 `aidd job wait <id>` path traversal on read, L9 `.aidd/jobs/` not git-ignored while logs/cmd may hold secrets, L3 scrub is key=value only, L10 predictable temp paths, tamper-evidence is detection-only (L7) |

## Mapping ledger
Evidence note: the standalone command outputs cited below (`ac009-...`, `ac013-trace.txt`, `ac015-...`, `ac021-...`, `ac027-job.txt`, `ac030-...`, `graph-queries-integraciones.txt`, `perf-status-refresh.txt`) predate two small post-audit code edits (`aidd/cli.py` help strings, `aidd_doctor.py` resolver) that do not touch the behaviours they document; the covering tests were re-run by the final `aidd verify`. They are cited here and not repeated in the Execution evidence table, which keeps only files newer than the last code edit.

| Code | Status | Evidence (file/class/resource id) | PR/Spec ref | Screenshot diff done? |
|---|---|---|---|---|
| FR-001 | ✅ IMPLEMENTED | skill/scripts/find_spec.py `parse_spec_nodes`; V-4 (tests.test_find_spec) | T-01 | n/a (no UI) |
| FR-002 | ✅ IMPLEMENTED | find_spec.py `parse_task_nodes`; AC-002 | T-01 | n/a |
| FR-003 | ✅ IMPLEMENTED | find_spec.py `parse_contract_nodes`, `build_graph`; AC-003 | T-01 | n/a |
| FR-004 | ✅ IMPLEMENTED | find_spec.py `memory_nodes_for`; V-4 | T-04 | n/a |
| FR-005 | ✅ IMPLEMENTED | find_spec.py `print_code` (<= 25 lines) | T-06 | n/a |
| FR-006 | ✅ IMPLEMENTED | find_spec.py `print_tree` | T-06 | n/a |
| FR-007 | ✅ IMPLEMENTED | `stale_spec_names`; V-4 incremental reindex test | T-07 | n/a |
| FR-008 | ✅ IMPLEMENTED | skill/hooks/read_hint.py (advises only, exit 0); V-4 (tests.test_read_hint) | T-03, T-05 | n/a |
| FR-009 | ✅ IMPLEMENTED | skill/SKILL.md W1/Step 6; commands/aidd-converge.md:7,12 | T-09, T-10 | n/a |
| FR-010 | ✅ IMPLEMENTED | `INDEX_VERSION`; V-4 old-version rebuild test | T-04, T-07 | n/a |
| FR-014 | ✅ IMPLEMENTED | skill/scripts/code_graph.py; `aidd_graphs._rename_foreign_code` aidd_graphs.py:179-192; V-1; `ac009-ac010-ac012-ac018-code-graph-snapshots.txt` (169 files, 5183 nodes) | T-12, T-17 | n/a |
| FR-015 | ✅ IMPLEMENTED | code_graph `implements` edges; `show code latest_verify_run` prints `implements: FR-205 -> 007-...` (final-ac-evidence.md AC-010); V-1 | T-12 | n/a |
| FR-016 | ✅ IMPLEMENTED | skill/scripts/method_graph.py; V-3; `ac015-graphs-refresh-status.txt` (14 rules, 0 unlinked). Extra `cites` STEP->RULE edge accepted (AC-011 needs it) | T-13 | n/a |
| FR-017 | ✅ IMPLEMENTED | graph_snapshot.py `repeats` (cap `_cap`, `--full`); unknown `--cmd` exits 2; V-3 | T-15 | n/a |
| FR-018 | ✅ IMPLEMENTED | skill/scripts/graph_trace.py `run_traced`, `--scripts-dir`; V-3; `ac013-trace.txt`; AC-034 | T-14 | n/a |
| FR-019 | ✅ IMPLEMENTED | graph_snapshot.py `snapshot` (event logged BEFORE `os.replace`); aidd_evidence.py `append_graph_snapshot`; V-2 | T-11, T-15 | n/a |
| FR-020 | ✅ IMPLEMENTED | graph_snapshot.py `diff` (sha recomputed vs the most recent event, `snapshot altered` exit 2); V-2. Detection-only (L7) | T-15 | n/a |
| FR-021 | ✅ IMPLEMENTED | aidd_graphs.py `_run_and_stamp`, builtin:spec; V-3; `ac015-graphs-refresh-status.txt` | T-17 | n/a |
| FR-022 | ✅ IMPLEMENTED | V-4 (tests.test_dot_aidd_mirror byte-identical mirror); `step0-skill-sync.txt` | T-21..T-24 | n/a |
| FR-023 | ✅ IMPLEMENTED | git blob sha baseline, `changed` one `git hash-object` pass (V-7); manifest on activate (V-2) | T-11, T-15, T-26 | n/a |
| FR-024 | ✅ IMPLEMENTED | code_graph incremental `re-parsed N, reused M`; V-1; `ac015-...` | T-12, T-15 | n/a |
| FR-025 | ⚠️ PARTIAL | read_hint.py `_graph_first`, `_command_target`; matcher registered in `~/.claude/settings.json`; unit only (V-4). Not exercised in a real session until restart | T-27, T-28 | n/a |
| FR-026 | ⚠️ PARTIAL | read_hint.py `_silenced` (300 s); V-4 unit only | T-27, T-30 | n/a |
| FR-027 | ⚠️ PARTIAL | `graph_miss` recorded before the throttle decision; aidd_status.py `_graph_first_line`; V-4/V-5 unit only | T-26, T-27 | n/a |
| FR-028 | ✅ IMPLEMENTED | sql_graph.py :626-632, :1049; V-6; b1SycLink run exit 0 | T-31 | n/a |
| FR-029 | ✅ IMPLEMENTED | sql_graph.py `load_model`, `_prefix_diff`; V-6; real data `replayed 0 of 878` | T-31 | n/a |
| FR-030 | ✅ IMPLEMENTED | sql_graph.py `BodyAnalyses`; V-6; real data `analysed 0 bodies, reused 1540` | T-31 | n/a |
| FR-031 | ✅ IMPLEMENTED | E9 (a)-(e) in skill/SKILL.md:443 and skill/AIDD.md:571; V-4 | T-36, T-37 | n/a |
| FR-032 | ✅ IMPLEMENTED | prompt_trigger.py system-message skip, dedupe `_DEDUP_TTL`; V-7. Residual: find_spec timeout equals hook timeout (see Performance) | T-33, T-34 | n/a |
| FR-033 | ✅ IMPLEMENTED | commands/aidd-converge.md:7; tasks.md:645; spec.md `Jobs: 4`; V-4 | T-36, T-38 | n/a |
| FR-034 | ✅ IMPLEMENTED | tests/test_perf_budget.py (counts, no wall times); V-7; `perf-status-refresh.txt` | T-35 | n/a |
| FR-035 | ✅ IMPLEMENTED | aidd_job.py `cmd_run` (CACHED only when `cmd_hash` AND `inputs_hash` match); V-8; `ac027-job.txt` | T-39 | n/a |
| FR-036 | ✅ IMPLEMENTED | aidd_job.py `_parse_output`; AIDD.md:582; V-8 | T-39 | n/a |
| FR-037 | ✅ IMPLEMENTED | skill/scripts/aidd_triage.py; V-8 (incl. `test_read_only`) | T-40 | n/a |
| FR-038 | ✅ IMPLEMENTED | aidd/cli.py:409-415 forwards `job`, `triage`; V-4 `--help` + mirror; V-8 | T-43 | n/a |
| FR-039 | ✅ IMPLEMENTED | skill/scripts/aidd_tools.py; V-9; `ac030-ac032-tools-size.txt` | T-44 | n/a |
| FR-040 | ✅ IMPLEMENTED | T1 in SKILL.md:445 and AIDD.md:572; templates/tasks.md:16; V-7 | T-36, T-37, T-46 | n/a |
| FR-041 | ✅ IMPLEMENTED | aidd/cli.py forwards `tools`; V-4; V-9 | T-43, T-44 | n/a |
| FR-042 | ✅ IMPLEMENTED | aidd_tools.py `size`; V-9; `ac030-ac032-tools-size.txt` | T-44 | n/a |
| FR-043 | ✅ IMPLEMENTED | templates/tasks.md:17, :39; prompt hint names `aidd size` (V-7) | T-46 | n/a |
| AC-001 | ✅ IMPLEMENTED | `--code API-003` on Integraciones: 6 lines (`graph-queries-integraciones.txt`) | T-06 | n/a |
| AC-002 | ✅ IMPLEMENTED | `--code T-16` (same file) | T-06 | n/a |
| AC-003 | ✅ IMPLEMENTED | `--tree 001-pos-sap-sync`: 87 lines (same file) | T-06 | n/a |
| AC-004 | ✅ IMPLEMENTED | MEM neighbour test (V-4) | T-07 | n/a |
| AC-005 | ✅ IMPLEMENTED | v3 index rebuilt, only the touched spec re-parsed (V-4) | T-07 | n/a |
| AC-006 | ✅ IMPLEMENTED | tests/test_read_hint.py (V-4) | T-03 | n/a |
| AC-009 | ✅ IMPLEMENTED | `ac009-ac010-ac012-ac018-code-graph-snapshots.txt`; syntax-error partial graph in V-1 | T-12, T-16 | n/a |
| AC-010 | ✅ IMPLEMENTED | final-ac-evidence.md AC-010 | T-12, T-17 | n/a |
| AC-011 | ✅ IMPLEMENTED | `ac015-graphs-refresh-status.txt` (`show method R10`); V-3 | T-13, T-19 | n/a |
| AC-012 | ⚠️ PARTIAL | `--full` works; FUNC with `resolve` in `ext_in_loop` present before (`aidd_rules._evidence_path`), absent after (final-ac-evidence.md AC-012). Spec text corrected after pass 1 | T-15, T-19 | n/a |
| AC-013 | ✅ IMPLEMENTED | `ac013-trace.txt`: two runs agree on every count (run on AIDD with `status`, accepted deviation) | T-14, T-19 | n/a |
| AC-014 | ✅ IMPLEMENTED | V-2 (clean pair deltas; hand-edited snapshot exits 2) | T-15, T-18 | n/a |
| AC-015 | ✅ IMPLEMENTED | `ac015-graphs-refresh-status.txt`; V-3 | T-17, T-19 | n/a |
| AC-016 | ⚠️ PARTIAL | fixture tests V-1/V-2; no `004-aidd-graph-first@open` baseline (`aidd size --spec 004...` prints `no baseline`) | T-15, T-16 | n/a |
| AC-017 | ✅ IMPLEMENTED | V-1/V-2 (same size + backdated mtime still changed) | T-16, T-18 | n/a |
| AC-018 | ✅ IMPLEMENTED | `ac009-...` (rev snapshot vs worktree; `repeats --cmd nope` exit 2) | T-15, T-18 | n/a |
| AC-019 | ⚠️ PARTIAL | unit only (V-4); human script `evidence/ac019-ac020-nudge-not-verified.txt` | T-27, T-29 | n/a |
| AC-020 | ⚠️ PARTIAL | unit only (V-4); same human script | T-26, T-29 | n/a |
| AC-021 | ✅ IMPLEMENTED | final-ac-evidence.md AC-021 (relative paths under `--root`, exit 0); V-6 | T-31, T-32 | n/a |
| AC-022 | ✅ IMPLEMENTED | V-6; real data replay 0 of 878, reused 1540 | T-31, T-32 | n/a |
| AC-023 | ✅ IMPLEMENTED | SKILL.md:443, AIDD.md:571; V-4 docs test | T-36, T-37 | n/a |
| AC-024 | ✅ IMPLEMENTED | V-7 tests.test_prompt_trigger | T-33, T-34 | n/a |
| AC-025 | ✅ IMPLEMENTED | V-4; tasks.md:645; spec.md `Jobs: 4` | T-36, T-38 | n/a |
| AC-026 | ✅ IMPLEMENTED | V-7 tests.test_perf_budget (counts) | T-35 | n/a |
| AC-027 | ✅ IMPLEMENTED | `ac027-job.txt` (CACHED, counter file proves no re-execution); V-8 | T-39, T-41 | n/a |
| AC-028 | ✅ IMPLEMENTED | V-8 tests.test_aidd_triage | T-40, T-42 | n/a |
| AC-029 | ✅ IMPLEMENTED | V-4 (`--help` rc 0, byte-identical mirror) | T-43 | n/a |
| AC-030 | ✅ IMPLEMENTED | `ac030-ac032-tools-size.txt`; V-9. Side effect L1 | T-44, T-45 | n/a |
| AC-031 | ✅ IMPLEMENTED | SKILL.md:445, AIDD.md:572, templates/tasks.md:16; V-7 | T-36, T-37, T-46 | n/a |
| AC-032 | ✅ IMPLEMENTED | `ac030-ac032-tools-size.txt`; V-9 | T-44, T-45 | n/a |
| AC-033 | ✅ IMPLEMENTED | V-2 tests.test_graph_snapshot | T-11, T-15 | n/a |
| AC-034 | ✅ IMPLEMENTED | final-ac-evidence.md AC-034 (reads 7792 -> 374, spawns 7 -> 3, 141.1 s -> 8.4 s) | T-14, T-25 | n/a |
| FR-044 | ✅ IMPLEMENTED | spec.md `## Verification` V-5, V-10, V-11, V-12 (one module each, `Jobs: 4`); `aidd verify` PASSED 12/12, hash 8b32a0b5b209, wall 75.5 s vs 164.6 s (`evidence/verify-V-*.txt`) | T-59 | n/a |
| FR-045 | ✅ IMPLEMENTED | aidd_evidence.py `read_cache`/`cached_read`/`forget_read` (:410-455), aidd_rules.py `_read`/`_cached_read_fn` (:1648-1670, looked up per call, never memoised), aidd_status.py `_read_scope` (:825, used :1985), aidd_progress.py `_scoped_main`; `ac036-status-reads-after-cache.txt` (reads 374 -> 180, rereads 226 -> 30, spawns 3) | T-47, T-48, T-49 | n/a |
| FR-046 | ✅ IMPLEMENTED | aidd_rules.py `_closing_audit_reason` (:2936), `closing_audit_covers` (:2989, same truth table), `closing_audit_diagnosis` (:3001); aidd_status.py `_print_closing_diagnosis` (:834, regex `(\w+): missing`); "Close sequence" in SKILL.md:464 and AIDD.md:602 (mirror identical); V-5, V-11 | T-47, T-49, T-57, T-58 | n/a |
| FR-047 | ✅ IMPLEMENTED | skill/hooks/prompt_trigger.py:174 `FIND_SPEC_TIMEOUT = 8`, used :189; V-7 | T-50 | n/a |
| FR-048 | ✅ IMPLEMENTED | aidd_job.py `_valid_job_id`/`_job_dir` (:100-118), `cmd_wait` :601, `cmd_last` :624, `_exec_main` :571, `_redact_cmd` :121; `.gitignore:12` `.aidd/jobs/`; V-8 | T-51 | n/a |
| AC-035 | ✅ IMPLEMENTED | spec.md rows V-5, V-10, V-11, V-12; per-row logs exit 0 (`verify-V-5/10/11/12.txt`); the "start in the same batch" half is shown by the single 75.5 s wall vs the 66 s slowest row | T-59 | n/a |
| AC-036 | ✅ IMPLEMENTED | `ac036-status-reads-after-cache.txt`: two runs agree (reads 180 <= 200, rereads 30 <= 60, spawns 3) | T-53, T-59 | n/a |
| AC-037 | ✅ IMPLEMENTED | tests/test_aidd_rules.py `TestReadCache` (:2337, incl. `test_no_hook_opens_the_read_cache` :2402), tests/test_perf_budget.py :210; V-5, V-7 | T-52, T-53 | n/a |
| AC-038 | ✅ IMPLEMENTED | tests/test_aidd_rules.py `TestClosingAuditDiagnosis` (:2409), tests/test_aidd_status.py (:2484-2513); unit-level (no CLI transcript, see F3) | T-52, T-54 | n/a |
| AC-039 | ✅ IMPLEMENTED | tests/test_prompt_trigger.py `TestFindSpecTimeout` (:216), install_hooks default 10 s; V-7 | T-56 | n/a |
| AC-040 | ✅ IMPLEMENTED | tests/test_aidd_job.py `TestJobHardening` (:187-241: `wait ../x`, `last a/b` exit 2 `refused`, `--token=[redacted]` in job.json and verdict.json, `.gitignore`); V-8; unit-level (see F3) | T-51, T-55 | n/a |

## Device preflight
Preflight: N/A: scripts, hooks and CLI; no device and no UI.

## Execution evidence
| Code | Kind | Evidence | Verified by |
|---|---|---|---|
| AC-010 | command-output | evidence/final-ac-evidence.md | agent |
| AC-012 | command-output | evidence/final-ac-evidence.md | agent |
| AC-014 | log | evidence/verify-V-2.txt | agent |
| AC-016 | log | evidence/verify-V-1.txt | agent |
| AC-017 | log | evidence/verify-V-2.txt | agent |
| AC-019 | not-verified | evidence/ac019-ac020-nudge-not-verified.txt | agent |
| AC-020 | not-verified | evidence/ac019-ac020-nudge-not-verified.txt | agent |
| AC-021 | command-output | evidence/final-ac-evidence.md | agent |
| AC-022 | log | evidence/verify-V-6.txt | agent |
| AC-023 | log | evidence/verify-V-4.txt | agent |
| AC-024 | log | evidence/verify-V-7.txt | agent |
| AC-025 | log | evidence/verify-V-4.txt | agent |
| AC-026 | log | evidence/verify-V-7.txt | agent |
| AC-028 | log | evidence/verify-V-8.txt | agent |
| AC-029 | log | evidence/verify-V-4.txt | agent |
| AC-031 | log | evidence/verify-V-7.txt | agent |
| AC-033 | log | evidence/verify-V-2.txt | agent |
| AC-034 | command-output | evidence/final-ac-evidence.md | agent |
| FR-014 | log | evidence/verify-V-1.txt | agent |
| FR-016 | log | evidence/verify-V-3.txt | agent |
| FR-028 | log | evidence/verify-V-6.txt | agent |
| FR-034 | log | evidence/verify-V-7.txt | agent |
| FR-035 | log | evidence/verify-V-8.txt | agent |
| FR-039 | log | evidence/verify-V-9.txt | agent |
| FR-044 | log | evidence/verify-V-5.txt | agent |
| FR-045 | command-output | evidence/ac036-status-reads-after-cache.txt | agent |
| FR-046 | log | evidence/verify-V-11.txt | agent |
| FR-047 | log | evidence/verify-V-7.txt | agent |
| FR-048 | log | evidence/verify-V-8.txt | agent |
| AC-035 | log | evidence/verify-V-12.txt | agent |
| AC-036 | command-output | evidence/ac036-status-reads-after-cache.txt | agent |
| AC-037 | log | evidence/verify-V-5.txt | agent |
| AC-038 | log | evidence/verify-V-11.txt | agent |
| AC-039 | log | evidence/verify-V-7.txt | agent |
| AC-040 | log | evidence/verify-V-8.txt | agent |

## Bug reports
| # | Code | Symptom | Root cause | Fix | Pattern sweep |
|---|---|---|---|---|---|
| 1 | FR-008 | `aidd rules approve` refused an AskUserQuestion approval (2026-10-02 audit) | Claude Code 2.1.288 fires no PostToolUse for AskUserQuestion | `typed_approval` in aidd_evidence.py | `grep affirmative_answer skill/`: 3 uses, all through the fixed function |
| 2 | FR-017 / AC-012 | `repeats ... --full` exit 2 `unrecognized arguments` | `_cap` printed `(--full)` but the `repeats` subparser had no flag | flag added graph_snapshot.py:1045; final run exit 0 | `--full` on `diff`/`changed`/`repeats` all present |
| 3 | FR-028 / AC-021 | relative migration dirs resolved against the cwd | `_collect` used `Path(p)` as given | `_collect` resolves under `--root` first sql_graph.py:696-700 | n/a (single input-collection function) |
| 4 | FR-038 | `aidd job list --root X` exit 2 (V-8 first run) | `--root` only on the top-level parser | `--root` added to every subparser aidd_job.py:635-636; V-8 PASS | aidd_triage / aidd_tools not re-checked (low) |
| 5 | FR-037 | unittest failures collapsed to `(failures=1)` keys | extractor keyed on the summary line | `FAIL:/ERROR:` names extracted aidd_triage.py:46-59; V-8 | n/a |
| 6 | FR-038 / FR-041 | `aidd --help` described `job`, `triage`, `tools`, `size` as other tools | the builder wrote the strings without the real interfaces | strings rewritten in aidd/cli.py:409-415; independent review PASS WITH NOTES | those four commands are the only ones in that loop |
| 7 | FR-014 / FR-021 | the terminal `aidd` was a stale non-editable package; `doctor` could not find the shipped bundle | `site-packages/aidd` was an old snapshot; `aidd_doctor.repo_root` lacked the `_data` fallback | `pip install --no-deps --force-reinstall D:/Fuentes/AIDD`; `repo_root` fixed; `doctor` D1 PASS in 3 hosts | `grep -n "def repo_root\|def _repo_root" skill/scripts/`: only these two resolvers |

## Resilience check (per code that crosses a boundary — network, DB, disk, external API, hardware)
| Code | Timeout set? | Retry/backoff? | Graceful degradation? | Recoverable trace on failure (where)? |
|---|---|---|---|---|
| FR-014/FR-024 code_graph git | yes `GIT_TIMEOUT` | n/a | git missing/timeout -> in-process blob sha | partial graph + warnings |
| FR-019 graph_snapshot git/sql | yes (`SQL_TIMEOUT`) | n/a | refusal rc 2, never raises | message names the cause |
| FR-035 aidd_job | yes `--timeout` (exit 4), git 60 s | no (by design) | hashing falls back to in-process blob sha | `log.txt` + `verdict.json` in the job folder |
| FR-039 aidd_tools | yes timeout=60 | n/a | cache miss -> rescan | n/a |
| FR-025 read_hint / FR-032 prompt_trigger | hook timeout (host); prompt_trigger find_spec timeout 10 s equals the 10 s hook timeout (residual) | n/a | every path returns exit 0, never blocks | `hook_error` when loggable |
| FR-029/FR-030 sql_graph files | n/a (local disk) | n/a | corrupt checkpoint/cache -> full replay / re-analyse | `db-schema: full replay (<reason>)` line |

## Backend contract check (per API-nnn touched)
N/A: no API-nnn touched.

## Database robustness check (per API-nnn/entity that touches a database)
| Code | Connection pooled (or exception written down)? | Released in guaranteed path (finally/using)? | Connection validated before use? | Transaction boundaries explicit? | Index/plan verified (engine's own plan tool)? |
|---|---|---|---|---|---|
| FR-028..FR-030 | n/a: no connection; `sql_graph.py` reads `.sql` files only (no driver imported) | n/a | n/a | n/a | n/a (static model of migrations; no engine touched) |

## Performance & Best Practices check (Performance & Best Practices Auditor — applies to any code touched, every convergence)
| File/class | OOP/SOLID verified in code? | Interfaces used at real boundaries? | Locking/isolation deliberate for the engine? | Connection pooling verified (not just declared)? | No N+1 / unbatched loop? | No blocking call on hot path? |
|---|---|---|---|---|---|---|
| aidd_status / aidd_rules (`status`) | single-purpose functions | n/a | evidence log `_locked` | n/a | NO: `aidd_rules._read` (aidd_rules.py:1639-1646) has no memo; 240 reads / 203 re-reads per `status`, `events.toon` read 5x (`ac013-trace.txt`) | `status --refresh` 10.8 s, not on a hook path |
| code_graph.py | yes | n/a | n/a | n/a | one `git hash-object` pass, re-parse only changed shas (asserted by counts in test_perf_budget) | no-op refresh 2.7-3.6 s (tree scan + sha), keep it off hooks |
| sql_graph.py | yes | n/a | n/a | n/a | append-only replay, per-body cache | b1SycLink schema 4.2 s -> 1.3 s, dml 7.8 s -> 1.9 s |
| prompt_trigger.py | yes | n/a | n/a | n/a | dedupe per session: second identical prompt spawns 0 find_spec | first prompt: find_spec `timeout=10` (prompt_trigger.py:186) inside a 10 s hook, no margin |

Measured residual cost, ranked (what to optimise next):
1. V-5 module set (tests.test_aidd_rules, test_evidence, test_aidd_status, test_aidd_progress): 159.8 s of the 164.6 s first verify and 74.1 s of the final 81 s (541 tests). Split into rows or `run_parallel`; it dominates every close.
2. `status` path: `aidd_rules._read` re-reads (203 of 240) and `events.toon` parsed 5x per command; add a per-process mtime/size-keyed memo (cuts about 200 reads per status). The "events.toon cached parse" claim in `perf-status-refresh.txt` is not demonstrated by a runtime trace.
3. Code graph: no-op refresh still 2.7-3.6 s; `status --refresh` 8-11 s.
4. Lower find_spec timeout in prompt_trigger.py to 6-8 s so it fits inside the 10 s hook.
5. `aidd tools` second run not faster on AIDD (1.02 -> 1.15 s).

## Revision log (append, never overwrite)
```
Rev 6 (2026-10-24) — second amendment (FR-044..FR-048, AC-035..AC-040, T-47..T-59): code frozen, `aidd verify` PASSED 12/12 (hash 8b32a0b5b209, 75.5 s), then ONE message with four domain auditors on sonnet after the last code edit: database PASS (toolu_01TjG2DYurFCtMQkGpHQnrhb), performance PASS WITH EXCEPTIONS (toolu_01Th1sXjMZY3RvJVZMuoeLLo), security PASS WITH EXCEPTIONS (toolu_01DcXktvyrvdZHa5EAT8CTf3), functional PASS WITH EXCEPTIONS (toolu_01NRUKB3wmC2SC4hdsiVN73Z); no blocking finding; new items L11, L12, P2, F3, R14
Rev 1 (2026-10-03) — performance-only closing audit of FR-001..FR-010 / AC-001..AC-006: PASS WITH NOTES
Rev 2 (2026-10-24) — closing audit of the 2026-10-24 amendment, domains database/functional/performance/security: 39/46 amendment codes PASS (84.8%), 7 PARTIAL
Rev 3 (2026-10-24, after pass 1) — edits made while or after pass 1 ran: aidd/cli.py help strings of job/triage/tools/size; skill/scripts/aidd_doctor.py repo_root resolver (independent review PASS WITH NOTES); evidence/ac019-ac020 script corrected for the 300 s throttle; spec.md AC-012 and AC-016 wording; updates of every LLM host; aidd verify re-run once (81 s, same hash). Evidence: final-ac-evidence.md section "Update and validation of every LLM host"
Rev 4 (2026-10-24) — incremental closing audit (pass 2): 20 claims re-validated, none failed
Rev 5 (2026-10-24) — dedicated per-domain auditors after the last code edit (pass 3): performance PASS WITH EXCEPTIONS, security PASS WITH EXCEPTIONS (no blocking finding; new items L8, L9, L10 below)
```

## Open exceptions (rows left unresolved on purpose)
| Code | Reason | Approved by |
|---|---|---|
| AC-019, AC-020, FR-025, FR-026, FR-027 | Not exercised end to end in a real session. The matcher `Read\|Grep\|Glob\|Bash\|PowerShell` is registered but Claude Code must be restarted before the nudge can be observed. Human script: `evidence/ac019-ac020-nudge-not-verified.txt` | owner (pending the restart) |
| AC-012 | Status stays PARTIAL because `repeats --full` was verified before the final spec wording; the measurable difference is the FUNC with `resolve` in `ext_in_loop` | owner |
| AC-016 | Dogfood baseline `004-aidd-graph-first@open` never taken; the temp-project tests of V-1/V-2 stand in. The "full suite once at close" is not recorded (only 17 affected modules + the 9 verify rows) | owner |
| M4 (E9) | MEDIUM (process). `aidd verify` and `run_parallel` over 17 modules ran on the same code state; 14 modules overlap, about 55 s duplicated. Lesson: `aidd verify` alone for the gate, `run_parallel --changed` only while building | owner |
| L1 (AC-030) | LOW. `aidd tools` writes its scan cache into the target project (`b1SycLink/.aidd/graphs/tools.cache.json`, 13 KB). Owner to keep or delete | owner |
| L2 (FR-035) | LOW. A `--key` that matches 0 files hashes the empty set, so the command stays CACHED regardless of edits. Proposed fix: zero matched files = never CACHED | owner |
| L3 (FR-027) | LOW. `graph_miss` target scrubbing (read_hint.py:29, :122-123) only masks `key=value`; a literal secret as a Grep/Glob pattern is logged (120 chars) under the git-ignored `.aidd/evidence`. Fix: hash or `aidd_evidence.redact_secrets` | owner |
| L4 (FR-031, FR-042) | LOW. AIDD.md:573 omits the per-class parameter table and the "an XS change never builds a graph, snapshot or job" sentence that SKILL.md:447-455 has | owner |
| L5 | LOW, accepted: `cites` edge, `inputs` map in method snapshots, `--root` after the subcommand, unittest extractor in triage | auditor |
| L6 (FR-025) | LOW. The Read nudge for a markdown template suggested a code-graph query; `_name_hint` should prefer `find_spec`/`aidd search` for non-code targets | owner |
| L7 (security) | LOW, by design. `aidd job run -- <cmd>`, `graph_trace --scripts-dir`, `AIDD_HOME` and `runpy.run_path` execute code the caller chose. Snapshot tamper-evidence is detection-only: it catches an edit of the snapshot file alone; a writer of both file and event log, or `--replace`, defeats it (the claim should read "detects alteration of the file alone") | auditor |
| L8 (security, FR-035) | LOW. `aidd job wait <id>` joins `args.id` onto the jobs dir without validation (aidd_job.py:554), so `..` reads `status.json`/`verdict.json`/log tail from another directory; `_exec <jobdir>` runs the `cmd` of that dir's `job.json` (:538-547). Needs a caller who can already run arbitrary commands. Fix: require `id` to match `[A-Za-z0-9_.-]+-[0-9a-f]{8}` and resolve under the jobs dir | owner |
| L9 (security, FR-035) | LOW-MEDIUM. `.aidd/jobs/` is not git-ignored (`.gitignore` ignores only `.aidd/evidence/`); `log.txt`, `job.json` and `verdict.json` hold the full output and command list, so a token passed on the command line could be committed by `git add .aidd`. Fix: add `.aidd/jobs/` to `.gitignore` and scrub `cmd` | owner |
| L10 (security) | LOW. Predictable temp paths (read_hint.py:19 `MARKER_DIR`, prompt_trigger.py `_state_path`) matter only on a shared POSIX host; session id is sanitised; no escalation. `_extract_tar` does not reject a drive-relative `C:foo` member (source is the user's own `git archive`) | auditor |
| F1 (functional, pass 3) | MEDIUM (citation). `ac009-ac010-ac012-ac018-code-graph-snapshots.txt` is the first-run record: it says "VERDICT AC-012: FAIL as written", `--full` exit 2 (fixed, bug #2) and an FR-205 title not joined (superseded by final-ac-evidence AC-010); read AC-010 and AC-012 in `final-ac-evidence.md`. It also shows the code_graph timing targets NOT met under load (full build 10.4 s vs 6 s, no-op 2.7 s vs 1.5 s) | owner |
| F2 (functional, pass 3) | LOW. AC-027 deviation: the spec asks for the second run's zero spawns counted with `aidd graphs trace`; `ac027-job.txt` used a counter file instead (sound substitute, accepted). AC-032 L case "full suite once at close" is not recorded either (same as AC-016). Line refs: the sql_graph.py table guard is :629-633 and :1030 (:1049 is a view-body try/except). Database auditor: two low test gaps (mid-list reorder branch not asserted directly; no test with relative path and a different cwd) | owner |
| P1 (performance) | MEDIUM residual, accepted: `aidd_rules._read` re-reads, `events.toon` 5x per status, V-5 160 s row, find_spec timeout 10 s inside a 10 s hook. Ranked in the Performance section | owner |
| L11 (security, FR-048) | LOW. `AIDD_JOB_REAL_CMD` hands the real argv to the `--bg` worker and is never removed from its environment, so the job's tool and its children inherit the unredacted command line (`env`, a crash reporter or a verbose runner would put a secret into `log.txt`/`verdict.json`). Bounded: the secret was already on the command line. Fix: `os.environ.pop('AIDD_JOB_REAL_CMD', None)` right after reading it in `_exec_main`; not applied here because any code edit after the verify and the auditors voids them | owner |
| L12 (security) | LOW/INFO. `cmd_hash` is stored unredacted (offline brute force of a low-entropy secret; both files are git-ignored); the cache signature `(size, mtime_ns)` can serve stale text for one printout on a coarse-timestamp filesystem (status/progress only, never a gate; adding `st_ctime_ns` would close it); an id ending in `.` aliases the same Windows directory (collision, no escape); `_redact_cmd` fails open when `aidd_evidence` cannot be imported | owner |
| P2 (performance, amendment 2) | LOW. V-11 (`tests.test_aidd_status`, 145 tests) is about 66 s, 88 % of the 75.5 s verify wall: split it or share fixtures; about 150 of the 180 remaining reads are first reads of distinct files (the floor); the 30 rereads on the real tree are guarded only by the evidence file, no test enforces the 200-read ceiling; the 8 s `find_spec` timeout leaves a 2 s margin inside the 10 s hook; `_evidence()` grows `sys.path` per call if `aidd_evidence` cannot be imported | owner |
| F3 (functional, amendment 2) | LOW (evidence). `evidence/verify-run.txt` and `final-ac-evidence.md:10` are from the earlier 9-row runs (the 12/12 run, hash 8b32a0b5b209, is in `verify-V-*.txt` and `ac036-...`); `evidence/INDEX.md` has no entry for AC-035..AC-040; the CLI sequences of AC-038 and AC-040 are covered by unit tests only, with no captured transcript; a haiku auditor gets the "tier" explanation only when its description matches the domain | owner |
| R14 (owner request, 2026-10-24) | The owner stated that haiku must not be an auditor, "de sonnet en adelante". Today R14 excludes only models whose name contains `haiku` (`aidd_rules.py:34`); an absent, inherited or unknown model still counts. Requiring sonnet or higher is a change of rule semantics and needs its own amendment | owner |
| Outside 004: host tests | `tests.test_host_install` and `tests.test_host_doctor`, `test_cli_accepts_host_antigravity` (2 failures of 73): PYTHONPATH on the checkout so `aidd` resolves to the checkout (no `_data`) while scripts come from the installed skill; neither `install_host._repo_root` nor `aidd_doctor.repo_root` tries the checkout. Not caused by 004; fix is one extra candidate in each resolver, right after closing | owner (spec 009 area) |
| FR-006, FR-007, FR-008 (2026-10-03 notes) | Kept from Rev 1: graph column growth, `print_tree` re-printing shared nodes, read_hint per-Read cost | owner |

VERDICT database: PASS
VERDICT functional: PASS WITH EXCEPTIONS
VERDICT performance: PASS WITH EXCEPTIONS
VERDICT security: PASS WITH EXCEPTIONS
VERDICT: PASS WITH EXCEPTIONS
