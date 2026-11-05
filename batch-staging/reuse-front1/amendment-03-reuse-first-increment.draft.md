# Draft — amendment 03 to spec 007: cross-spec reuse of offline-contract rows (first increment)

**DRAFT: not approved, not executable, no `Approved:` line.** Amendment intake: `AMENDMENT` of
`specs/007-aidd-review-html-close-gate` (verification and evidence). It does not edit or replace
`amendment-02-reuse-*` (shared observation, provider, audit carry-over stay there and stay blocked).
Owner requirement (verbatim): "si una prueba es compartida no se repita". Measurements and rationale:
`batch-staging/reuse-front1/` (`measure_shared_rows.py`, `measure_paid_waste.py` and their outputs).

## Minimum Requirements Checklist

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | `aidd verify` evidence reuse | repo — `skill/scripts/aidd_status.py` | — |
| New development or modification? | Modification of `cmd_verify` / `cmd_verify_many` | repo — `skill/scripts/aidd_status.py:1861`, `:2083` | — |
| External service, API, integration? | None. Database and external-state rows are explicitly refused | owner brief 2026-11-03 | — |
| Who is requesting it? | Owner (AIDD + b1SycLink) | owner brief 2026-11-03 | — |
| Dependencies? | Existing offline contract (`_contract_environment_id`, `_reusable_input_rows`, `wave_cache`); NOT the amendment-02 provider | repo — `skill/SKILL.md` "Incremental verification and reusable checks" | — |
| Business objective | A shared, owner-declared hermetic check that already passed on identical Inputs and environment is not executed again by another spec in a later invocation | owner brief 2026-11-03 | — |
| Expected visual fidelity | No mockup; CLI only | — | — |

## Executive summary

- **Objective:** extend the already-accepted same-spec historical reuse (`_reusable_input_rows`) and
  the in-invocation `wave_cache` to a cross-spec, cross-invocation lookup, with the same identity
  checks, PASS only, and a hard refusal for database runners.
- **Not in scope:** generic (non-contract) sharing, the disabled whole-tree round cache, DB/network
  rows, node/npm/`python -m` runners, Inputs cap, amendment-02 receipts/manifest/journal.
- **Measured value (b1SycLink, 2026-11-03):** 0 of 77 shared rows eligible today; after the owner
  opts `Payroll/tools/charter_gate.py` in and its 28 991-file input set fits the fingerprint cap,
  ≈25 min per full Payroll round (≈27 % of the 120.8 min strict repeated runtime measured since
  2026-10-28). Without those two owner actions the saving is 0.
- **Risk:** an incomplete owner `Inputs` declaration now affects every consuming spec, not one.

## Functional requirements

| Code | Requirement | Source |
|---|---|---|
| FR-220 | After a stable `cmd_verify` run (not `--full`, not `--tasks`, not `--wave`), every PASS row that is `Reuse: hermetic`, has `Inputs`, an unchanged `input_fp`, and a non-None `_contract_environment_id` equal to the one recorded, is stored once in a project store `.aidd/evidence/contract-reuse-v1/` as a content-addressed object `<sha256>.txt` plus one entry in `.aidd/evidence/contract-reuse-v1.json`. Existing files are never overwritten; FAIL, timeout (exit -1) and reused rows are never stored. | owner brief 2026-11-03; `aidd_status.py:2457-2482` |
| FR-221 | Before executing such a row, `cmd_verify` looks up the key (cmd, expected, ordered Inputs, input_fp, environment declaration, environment_id) in the store; it reuses the entry only if the object's sha256 matches, `_cached_pass_valid` accepts it, `row_input_fingerprint` and `_contract_environment_id` recomputed now still equal the key, and the entry's source spec differs from the current spec or is the same spec (both allowed). The reused result carries `reused: true`, `cross_spec: true`, `source_spec`, `source_sha256`, and the line printed is `CROSS-REUSED row <n> (PASS): <cmd> (passed in <source_spec> on the same Inputs and environment) → <rel>`. | owner brief 2026-11-03 |
| FR-222 | A command is a database/external runner when, case-insensitively, it contains any of `db_verify`, `psql`, `pg_prove`, `docker`, `supabase`, `--tap`; `_contract_environment_id` returns `None` for such a command, so no reuse path (same-spec, wave, cross-spec) can ever accept it. | owner brief 2026-11-03 ("database rows are never reused across runs") |
| FR-223 | `--full` and `AIDD_VERIFY_ROUND=off` disable FR-220 storage and FR-221 lookup; any error reading, parsing or validating the store falls back to executing the row (never a PASS without execution or valid entry), and never raises. | `aidd_status.py:1785-1787` |

## Acceptance criteria

| Code | Scenario | Expected |
|---|---|---|
| AC-251 | Spec `one` verified in invocation 1; spec `two` (same contract row) verified in invocation 2 with identical Inputs and environment | `_run_row` called once in total; spec `two`'s result has `reused`, `cross_spec`, `source_spec == 'one'`; its evidence file bytes equal the stored object |
| AC-252 | Same as AC-251 but Inputs bytes, environment id, expected or command differ in invocation 2 | Row executes in invocation 2 |
| AC-253 | Stored object deleted, truncated or its bytes altered; index JSON corrupted | Row executes; no exception; exit code reflects the real run |
| AC-254 | Invocation 1 row FAILS (or times out) | Nothing stored; invocation 2 executes |
| AC-255 | Row is `python eDoc/tools/db_verify.py --psql "docker exec -i x psql"` declared hermetic with contract | `_contract_environment_id` returns `None`; never stored, never reused, executes every time |
| AC-256 | `--full`, or `AIDD_VERIFY_ROUND=off` | No lookup, no store write; row executes |
| AC-257 | Row without `Reuse: hermetic` / `Inputs` / `Environment` (all b1SycLink rows today) | Behaviour byte-for-byte unchanged versus current code: executes, nothing stored |
| AC-258 | Store write fails (read-only dir) | Verification result unchanged; a `note: contract store not written (<Type>)` line printed |

## Verification

| # | Command | Expected | Covers |
|---|---|---|---|
| V-1 | `python -m unittest tests.test_contract_store -v` | exit 0 | T-22, T-23, AC-251..AC-258 |
| V-2 | `python -m unittest tests.test_verify_git_contract tests.test_wave_verification tests.test_verify_regressions -v` | exit 0 | T-23, AC-257 (no regression) |
| V-3 | `python -m unittest tests.test_dot_aidd_mirror -v` | exit 0 | T-24 |

Synthetic temporary directories only; no database, no Docker, no `db_verify.py`.

## Out of scope

Re-enabling `round_on`; sharing rows without the offline contract; DB/network/Docker rows; node,
npm, PowerShell or `python -m` runners; raising the 20 000-file Inputs cap; amendment-02 receipts,
canonical manifest and journal; editing any b1SycLink spec; changing installed skills.

---

# Tasks — amendment 03

Every task prompt restates: scope in and out exactly as written; stop and report on any ambiguity;
one responsibility per function; snake_case Python functions with a leading underscore for module
private helpers (the convention of `aidd_status.py`); design for failure (every store read/write in
`try/except (OSError, ValueError, TypeError, KeyError)`, fail closed = execute the row); tool-first
(bulk mirror sync by `cp`/script, never by hand-typing the file twice); repo rules: no temporary
databases, `db_verify.py` is never run, no `aidd verify` by the builder.

Analysis parameters: `aidd size --files skill/scripts/aidd_status.py tests/test_contract_store.py` → expected L (gate rules / CLI area).

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-22 | FR-220, FR-221, FR-222, FR-223, AC-251..AC-258 | `tests/test_contract_store.py` | LOGIC | | | any production code; any other test file |
| T-23 | FR-220, FR-221, FR-222, FR-223 | `skill/scripts/aidd_status.py` | LOGIC | | | `round_on`, `_round_*` functions, `aidd_rules.py`, any non-contract row behaviour |
| T-24 | FR-220..FR-223 (mirror) | `adapters/dot-aidd/scripts/aidd_status.py` | LOGIC | | | any change that is not a byte copy of T-23's file |
| T-25 | FR-222 docs | `skill/SKILL.md` | LOGIC | | | any other section of SKILL.md; b1SycLink files |

## Per-task detail

### T-22 — failing tests first
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: S

**Estimate**
- Effort: Medium
- Agent min: 15
- Human ref hours: 0.75
- Tokens (est): 70k
- Agent role: tests
- Model tier: medium
- Wave: 1

**Detail**
- Goal: encode AC-251..AC-258 as unit tests that fail on the current code.
- Cites: FR-220, FR-221, FR-222, FR-223, AC-251, AC-252, AC-253, AC-254, AC-255, AC-256, AC-257, AC-258.
- Depends on: none.
- Read first: `tests/test_verify_git_contract.py` lines 1-116 (header and class `ContractReuse`); `skill/scripts/aidd_status.py` lines 1663-1753 and 2184-2263.
- Files to change: `tests/test_contract_store.py` (new).
- Naming contract: class `CrossSpecContractReuse(unittest.TestCase)` with methods `test_second_invocation_other_spec_reuses`, `test_any_identity_change_executes`, `test_damaged_store_executes`, `test_failure_is_never_stored`, `test_db_runner_has_no_environment_id`, `test_full_and_round_off_disable`, `test_non_contract_rows_unchanged`, `test_store_write_failure_is_a_note`. Store paths asserted: `<tmp>/.aidd/evidence/contract-reuse-v1.json` and `<tmp>/.aidd/evidence/contract-reuse-v1/<sha256>.txt`. Patched production name: `status._contract_store_put`. Production entry points exercised (existing, unchanged signatures): `status.cmd_verify(spec_arg, full=False, bail=False, wave=None, result_sink=None, wave_cache=None, task_ids=None)` called as `cmd_verify('one')`, `cmd_verify('two')`, `cmd_verify('one', full=True)`, with `result_sink` a `dict` that `cmd_verify` fills via `result_sink.update(ok=..., stable=..., results=[...], ...)` (current lines 2512-2562); `wave_cache` is never passed.
- Behaviour:
  1. File header identical to `tests/test_verify_git_contract.py` lines 1-11 (`sys.path.insert(0, <repo>/skill/scripts)`, `import aidd_status as status`).
  2. Each test builds a temporary root with specs `one` and `two` whose `spec.md` holds the row `| V1 | python test.py | exit 0 | test.py | hermetic | contract:offline;vars=none;packages=none |` under `| # | Command | Expected | Inputs | Reuse | Environment |`, and patches exactly the set used in `ContractReuse.test_round_shares_only_identical_inputs_and_environment` (lines 50-61), except `ev.latest_verify_run` returns `None` always, so the existing same-spec path cannot satisfy the test, and NO `wave_cache` is passed (each spec is a separate `status.cmd_verify(name)` call = separate invocation).
  3. `test_second_invocation_other_spec_reuses`: verify `one`, then `two` → `len(calls) == 1`; `sink = {}` passed as `result_sink` for `two` has `sink['results']` with one row with `reused is True`, `cross_spec is True`, `source_spec == 'one'`; `specs/two/evidence/verify-V1.txt` bytes equal the stored object bytes.
  4. `test_any_identity_change_executes`: after a stored PASS from `one`, change in turn (a) the patched input fingerprint, (b) the patched environment id, (c) Expected in `two`'s spec to `contains: passed`, (d) the command to `python test.py -v`; each `cmd_verify('two')` adds exactly one call.
  5. `test_damaged_store_executes`: (a) delete the object file, (b) overwrite it with `b'garbage'`, (c) write `{not json` to the index; each time `cmd_verify('two')` returns 0 and adds one call; no exception escapes.
  6. `test_failure_is_never_stored`: `_run_row` returns `(1, '')` for `one`; the index file is absent or has no entry; `cmd_verify('two')` executes.
  7. `test_db_runner_has_no_environment_id`: call the REAL `status._contract_environment_id` (not patched) with `python eDoc/tools/db_verify.py --psql "docker exec -i x psql -U postgres" --tap` and with `python tools/run.py --tap`, declaration `contract:offline;vars=none;packages=none` → both `assertIsNone`.
  8. `test_full_and_round_off_disable`: `cmd_verify('one', full=True)` and, separately, under `patch.dict(os.environ, {'AIDD_VERIFY_ROUND': 'off'})`, each executes and the index file does not exist afterwards.
  9. `test_non_contract_rows_unchanged`: table `| # | Command | Expected |` with `| V1 | python test.py | exit 0 |`; two invocations → two calls; the index file does not exist.
  10. `test_store_write_failure_is_a_note`: patch `status._contract_store_put` with `side_effect=OSError`; `cmd_verify('one')` returns 0 and captured stdout contains `note: contract store not written`.
- Tests first: this task IS the tests; run `python -m unittest tests.test_contract_store -v` and keep the red output (every test except `test_non_contract_rows_unchanged` fails or errors on the current code).
- Verify: `python -m unittest tests.test_contract_store -v` → red before T-23; exit 0 after T-23.
- Do NOT: touch production code; use a real database, Docker, `db_verify.py` or the network; weaken an assertion later; pass a shared `wave_cache` dict (that tests the existing in-round path, not this one).
- Done when: the 8 tests exist with exactly these names and the red run is recorded by the verifier.
- Open questions: none.

### T-23 — store and cross-spec lookup in `aidd_status.py`
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: L (gate/CLI area)

**Estimate**
- Effort: Medium
- Agent min: 25
- Human ref hours: 1.25
- Tokens (est): 120k
- Agent role: builder
- Model tier: high
- Wave: 2

**Detail**
- Goal: implement FR-220..FR-223 with the smallest change to `cmd_verify`.
- Cites: FR-220, FR-221, FR-222, FR-223, AC-251, AC-252, AC-253, AC-254, AC-255, AC-256, AC-257, AC-258.
- Depends on: T-22 (tests red first).
- Read first: `skill/scripts/aidd_status.py` lines 1612-1625 (`_cached_pass_valid`), 1663-1753 (`_contract_environment_id`), 1756-1792 (`_reusable_input_rows`, `ROUND_TTL_DEFAULT`, `_round_enabled`, `_round_paths`), 2184-2263 (`cmd_verify` row loop), 2457-2482 (wave_cache store).
- Files to change: `skill/scripts/aidd_status.py`.
- Naming contract: constants `CONTRACT_STORE_VERSION = 'contract-reuse-v1'`, `CONTRACT_STORE_MAX_ENTRIES = 300`, `_DB_RUNNER_RE = re.compile(r'db_verify|psql|pg_prove|docker|supabase|--tap', re.I)`; functions `_contract_store_paths(root) -> tuple[Path, Path]`, `_contract_store_key(cmd, expected, inputs, input_fp, declaration, environment_id) -> str`, `_contract_store_get(root, key, expected) -> tuple[bytes, dict] | None`, `_contract_store_put(root, key, data, result, spec_name) -> None`; result fields `cross_spec`, `source_spec`, `source_sha256`; stdout prefix `CROSS-REUSED row`; note text `note: contract store not written (<ExceptionType>)`; index JSON `{"version": "contract-reuse-v1", "entries": [{"key", "sha256", "sha1", "cmd", "expected", "exit", "ok", "spec", "ts"}]}`.
- Behaviour:
  1. Add the three constants right after `ROUND_MAX_ENTRIES`.
  2. In `_contract_environment_id`, immediately after the shell-metacharacter check (`if any(c in cmd for c in '|&;<>\n\r`$'): return None`), add `if _DB_RUNNER_RE.search(cmd): return None`. Nothing else in that function changes.
  3. `_contract_store_paths(root)` returns `(Path(root) / '.aidd' / 'evidence' / f'{CONTRACT_STORE_VERSION}.json', Path(root) / '.aidd' / 'evidence' / CONTRACT_STORE_VERSION)`.
  4. `_contract_store_key(...)` returns the sha256 hex of `json.dumps([_verification_key(cmd), _verification_key(expected), sorted(inputs), input_fp, declaration.strip(), environment_id], ensure_ascii=True, separators=(',', ':'))`.
  5. `_contract_store_get(root, key, expected)`: read the index; if `version` differs → `None`; take the LAST entry with that `key`; read `<dir>/<entry['sha256']>.txt`; return `(data, entry)` only if `hashlib.sha256(data).hexdigest() == entry['sha256']` and `_cached_pass_valid(data, entry, expected)`; wrap everything in `try/except Exception: return None`.
  6. `_contract_store_put(root, key, data, result, spec_name)`: create the directory; write the object with mode `'xb'` (ignore `FileExistsError`, never overwrite); load the index (missing or invalid → empty list); remove entries with the same `key`; append the new entry (`exit` 0, `ok` True, `spec` = spec_name, `ts` = `time.time()`, `sha1` = `result['sha1']`); keep the last `CONTRACT_STORE_MAX_ENTRIES`; write `<json>.<os.getpid()>.tmp` then `os.replace` onto the index. Exceptions propagate to the caller.
  7. In `cmd_verify._one`, directly after the existing `hit = ... input_reuse ...` block and before the `rhit = ...` line: when `wave is None and task_ids is None and _round_enabled(full) and inputs and input_fp and env_id and r.get('reuse') == 'hermetic'`, compute the key, call `_contract_store_get`; on a hit re-check `rules.row_input_fingerprint(root, inputs) == input_fp` and `_contract_environment_id(cmd, env_decl) == env_id`; write the bytes to `final`; build `res` exactly like the existing REUSED branch (current lines 2253-2258) plus `cross_spec=True, source_spec=entry['spec'], source_sha256=entry['sha256'], secs=0.0`; print `CROSS-REUSED row {n} (PASS): {one_line[:100]} (passed in {entry['spec']} on the same Inputs and environment) → {rel}`; return `res`. Any exception in this block → fall through to execution.
  8. After the existing `if wave_cache is not None and stable and not full:` block, add a block guarded by `wave is None and task_ids is None and _round_enabled(full) and stable`, iterating `results` with the SAME eligibility checks as that block (original row `reuse == 'hermetic'`, inputs, `ok is True`, `environment_id`, `input_fp` unchanged now, `_contract_environment_id` unchanged now, evidence sha1 intact) plus `not result.get('reused')`; call `_contract_store_put(root, key, data, result, d.name)` inside `try/except (OSError, ValueError, TypeError, KeyError) as e:` that prints `note: contract store not written ({type(e).__name__})`.
- Tests first: T-22 red output must exist before the first edit.
- Verify: `python -m unittest tests.test_contract_store tests.test_verify_git_contract tests.test_wave_verification tests.test_verify_regressions -v` → exit 0 (orchestrator's verifier, once, after the wave).
- Do NOT: change `round_on`, `_round_lookup`, `_round_store`, `_reusable_input_rows` or the `wave_cache` semantics; change any path for rows without the contract; store FAIL, timeout (exit -1) or reused rows; look up or store under `--full`, `--tasks`, `--wave` or `AIDD_VERIFY_ROUND=off`; delete or overwrite an existing object file; write any evidence file other than the current row's own `final` path; add a TTL; import non-standard-library modules; touch `aidd_rules.py`.
- Done when: the Verify command exits 0 and `git diff --stat` lists only `skill/scripts/aidd_status.py` for this task.
- Open questions: none.

### T-24 — adapter mirror
**Classify**
- Nature: `REQUIREMENT`
- Priority: 3
- Kind: LOGIC
- Size: XS

**Estimate**
- Effort: Low
- Agent min: 3
- Human ref hours: 0.15
- Tokens (est): 20k
- Agent role: builder
- Model tier: medium
- Wave: 3

**Detail**
- Goal: keep `adapters/dot-aidd/scripts/aidd_status.py` byte-identical to `skill/scripts/aidd_status.py`.
- Cites: FR-220, FR-221, FR-222, FR-223.
- Depends on: T-23.
- Read first: `tests/test_dot_aidd_mirror.py` lines 70-120 (mirrored file list; `skill/scripts/aidd_status.py` is listed at line 76).
- Files to change: `adapters/dot-aidd/scripts/aidd_status.py`.
- Naming contract: no new names; the file is a byte copy.
- Behaviour:
  1. `cp skill/scripts/aidd_status.py adapters/dot-aidd/scripts/aidd_status.py`.
  2. Run the Verify command.
- Tests first: existing `tests/test_dot_aidd_mirror.py` fails after T-23 and before this copy.
- Verify: `python -m unittest tests.test_dot_aidd_mirror -v` → exit 0.
- Do NOT: edit the mirror by hand; touch any other adapter file.
- Done when: the Verify command exits 0.
- Open questions: none.

### T-25 — document the rule in SKILL.md
**Classify**
- Nature: `REQUIREMENT`
- Priority: 4
- Kind: LOGIC
- Size: XS

**Estimate**
- Effort: Low
- Agent min: 5
- Human ref hours: 0.25
- Tokens (est): 20k
- Agent role: docs
- Model tier: medium
- Wave: 2

**Detail**
- Goal: state the cross-spec rule and the database refusal where the offline contract is documented.
- Cites: FR-221, FR-222.
- Depends on: none (text only; ships with T-23).
- Read first: `skill/SKILL.md` line 455 (paragraph starting `**Incremental verification and reusable checks.**`); `tests/test_dot_aidd_mirror.py` lines 115 and 426-436.
- Files to change: `skill/SKILL.md`.
- Naming contract: the appended sentence uses the literal token `CROSS-REUSED` and the runner list `db_verify`, `psql`, `pg_prove`, `docker`, `supabase`, `--tap`.
- Behaviour:
  1. Append to the end of that paragraph, exactly: "A passing contract row is stored once per project; a later `aidd verify` of any spec with the same command, expected result, Inputs and environment takes that stored result instead of running it (`CROSS-REUSED`); database and container runners (`db_verify`, `psql`, `pg_prove`, `docker`, `supabase`, `--tap`) can never use the contract."
- Tests first: none (documentation); the mirror suite is the regression guard.
- Verify: `python -m unittest tests.test_dot_aidd_mirror -v` → exit 0.
- Do NOT: rewrite other sentences; claim savings; touch b1SycLink `AGENTS.md` or any installed skill.
- Done when: the Verify command exits 0 and the sentence appears once.
- Open questions: none.

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-22 | tests | 15 | 70 | 0.75 |
| 2 | T-23, T-25 | builder, docs | 25 | 140 | 1.25 |
| 3 | T-24 | builder | 3 | 20 | 0.15 |

Total agent time (critical path): 43 min
Total tokens (k): 230

After wave 3 one verifier runs V-1..V-3 once, then an independent read-only security auditor reviews
the diff (domains: security, functional).

## Owner decisions required before approval

1. Accept that an owner `Inputs` mistake now propagates to every spec reusing that row.
2. Whether `charter_gate.py` is opted in (b1SycLink edit of 9 Payroll `## Verification` tables) and
   how the 28 991-file input set is handled (narrower charter globs in b1SycLink, or a separate AIDD
   change to the 20 000-file cap). Without this the increment saves 0 minutes in b1SycLink.
3. Whether the DB rows shared by F27/F36/F37/F38 (373 s each) and F28/F30/F33/F55 (305 s) are
   de-duplicated in the specs themselves (one full row per round, `--only-tests <prefix>` in the
   others) — the only measured lever for DB repetition that respects "DB rows are never reused".
4. Whether the contract surface is later widened to `python -m pytest|unittest` (separate amendment).

Approval line intentionally absent: only `aidd rules approve` may add it after the owner's decision.
