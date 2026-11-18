# Tasks — Graph V5 corrective adoption proposal

Analysis parameters: bounded adoption, two production modules plus one existing test module and canonical mirrors; existing graph/prototype reused, no new graph generation. Proposal only; prior draft implementation is disclosed, never retroactively approved.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-951 | FR-375, FR-376, FR-379 | tests/test_code_graph_raw_hashes.py | LOGIC | | | new source body; main/installed trees; DB |
| T-952 | FR-375, FR-379 | skill/scripts/code_graph.py; skill/scripts/aidd_graphs.py; adapters/dot-aidd/scripts/code_graph.py; adapters/dot-aidd/scripts/aidd_graphs.py | LOGIC | | | kernel/schema-format/unrelated provider/other source changes |
| T-953 | FR-377, FR-378 | isolated V5 context manifest and execution/audit receipts | LOGIC | | | owner seal fabrication; main publication/install |

## Per-task detail (one block per row above)
### T-951
- Nature: INCIDENT
- Priority: 2 HIGH
- Kind: LOGIC
- Agent min: 8
- Human ref hours: 0.40
- Tokens (est): 10k
- Agent role: builder
- Model tier: medium
- Objective: Adopt existing tests before adopting the raw-hash body.
- Activities: Require fresh R5 and real current corrective task approval. Read dependency-pins.json and plan exact paths. Use scripted mapping/dry-run/apply/postcheck to copy prototype tests/test_code_graph_raw_hashes.py unchanged to a root-created isolated adoption runtime. Preserve one RawWorkingTreeHashes class and both existing exact method names/assertions from plan. Add test_legacy_filtered_hash_alias_does_not_reuse_old_ast and test_builtin_code_generation_invalidates_legacy_freshness_stamp with exact scenario/assertions in the binding migration contract. Root must run actual RED for these new cases against the existing no-filters/extractor3 prototype before T-952 generation body, without relabelling oldRED2. Changes are test definitions only by builder. Root qualifies historical RED via official 4b immutable-proof rules or executes V-GR1 RED against pinned old code before T-952. Builder static only; report hash and leave incomplete until actual RED eligibility/execution exists.
- Do NOT: execute suites, fake fresh RED, modify test assertions, run DB, touch B1/main/installed files or protected owner state. Tools-first/native graph/no Graphify; DB only db_verify slots1..3/default, none needed.
### T-952
- Nature: INCIDENT
- Priority: 2 HIGH
- Kind: LOGIC
- Agent min: 10
- Human ref hours: 0.50
- Tokens (est): 20k
- Agent role: builder
- Model tier: medium
- Depends on: T-951 actual RED or official eligible exact-input RED proof
- Objective: Adopt raw-byte hashing and invalidate legacy native graph generations safely.
- Activities: Assert old/new code hashes in plan, compare reversed single argv delta to baseline, STOP on drift. Script-copy prototype source to isolated skill/scripts/code_graph.py and adapters/dot-aidd/scripts/code_graph.py, dry-run/apply/postcheck. Preserve file_shas(root,rels), _git(root,args,data=None), fallback, timeout, parser/cache schema and all unrelated bytes. Then implement exact FR-379 contract: EXTRACTOR_VERSION3 to4; _code_generation() and builtin-only _inputs_hashes generation salt/unknown omission; mechanical mirror both modules with postcheck. AST parse/static only; hand fresh final input hashes to root. Historical2d9eaca is starting prototype, not final migrated source hash.
- Do NOT: run tests; change kernel, unrelated graph feature behavior/cache policies, original or installed files, approvals or security rules. Tools-first/native graph/no Graphify; DB only db_verify slots1..3/default, none needed.
### T-953
- Nature: INCIDENT
- Priority: 2 HIGH
- Kind: LOGIC
- Agent min: 10
- Human ref hours: 0.50
- Tokens (est): 15k
- Agent role: tests
- Model tier: medium
- Depends on: T-952
- Objective: Produce truthful V5 closure and current audit prerequisites.
- Activities: Root verifier freezes all five 4b kernel pins plus adopted graph source and retained V4 files; computes official complete transitive unit execution/fixture closure. Execute or authoritatively qualify V-GR1..4 once using exact commands; no skip-based or count-only PASS. Preserve historical failures/audits unchanged. Fresh independent functional/security auditor reviews actual frozen proof. Root prepares exact official V5 owner package only after that review; ask genuine distinct V5 context consent, no fabricated seal. Report actual statuses, pins and any unresolved closure; final host-spec close gates remain.
- Do NOT: author own independent review, forge owner/audit records, install/merge/publish to main, run DB or broad suites without separately demonstrated uncovered risk. Tools-first/native graph/no Graphify; DB only db_verify slots1..3/default, none needed.

## Waves
| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-951 | builder | 8 | 10 | 0.40 |
| 2 | T-952 | builder | 10 | 20 | 0.50 |
| 3 | T-953 | tests | 10 | 15 | 0.50 |
Total agent time (critical path): 28 min
Total tokens (k): 45

## Approval gate
Corrective adoption of an existing isolated prototype requires explicit fresh task consent, then official exact V5 unit approval separately. No prior gate is retroactively manufactured. Existing Graph V4 owner state remains FALSE and audit FAIL until real current-context workflow resolves it.
Approved: PENDING
