# Tasks — Explicit bounded incremental graph refresh after a stale code miss

V2 owner approval was genuinely recorded. This V4 convergence package requires a fresh current owner seal; no legacy approval is replaced.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-911 | FR-370, FR-371, FR-372, FR-373, FR-374 | `tests/test_aidd_graphs.py`, `tests/test_aidd_graphs_empty_query.py`, `tests/test_aidd_graphs_running_state.py` | LOGIC | | | unrelated source, gates, DB, network, installed skill |
| T-912 | FR-370, FR-371, FR-372, FR-373, FR-374 | `skill/scripts/aidd_graphs.py` | LOGIC | | | unrelated source, gates, DB, network, installed skill |
| T-913 | FR-370, FR-371, FR-372, FR-373, FR-374 | `adapters/dot-aidd/scripts/aidd_graphs.py`, `docs/aidd-graph-fresh-query.md` | LOGIC | | | unrelated source, gates, DB, network, installed skill |

### T-911

**Classify**
- Nature: REQUIREMENT
- Priority: 2
- Kind: LOGIC

**Estimate**
- Agent min: 8
- Human ref hours: 0.40
- Tokens (est): 15k
- Agent role: tests
- Model tier: medium
- Wave: 1

**Detail**
- Files to change: `tests/test_aidd_graphs.py`
- Behaviour: Use temporary graphs and patch only process refresh boundary. Assert one refresh/reload/requery on opt-in stale builtin code miss; zero refresh for default/fresh miss/stale hit; error/lock/timeout remain uncertain; flag stripped from CLI query; at most one repeat when still absent; concurrent calls honor existing lock/debounce; wrong graph rejects flag. Capture RED before T-912.
- Read first: unit plan.md, target functions resolved through native graph, and existing import/test fixture style. Do not widen unrelated reads.
- Verification: coordinator runs the applicable commands in unit spec.md once after freeze; a new behavior first requires genuine RED before the body. Builders only static checks.
- Do NOT: edit any file not named; modify approvals/events; execute DB or external services; hide failures or label AST success as runtime proof.
- Open questions: none.

### T-912

**Classify**
- Nature: REQUIREMENT
- Priority: 2
- Kind: LOGIC

**Estimate**
- Agent min: 17
- Human ref hours: 0.85
- Tokens (est): 35k
- Agent role: builder
- Model tier: medium
- Wave: 2

**Detail**
- Files to change: `skill/scripts/aidd_graphs.py`
- Behaviour: Extend show(root,name,query,limit=25,refresh_on_miss=False); helper _show_code_retry(root,e,query,limit) performs at most one registered incremental refresh/reload. CLI --refresh-on-miss only code; remove exact flag token before query assembly. Reuse _get/status/refresh/_load_graph/_show_code; no shell command built with query, refresh all, forced full parse, hook changes or Graphify. Existing timeout/lock/debounce remain. Preserve no-flag ABI. Depends T-911 RED.
- Read first: unit plan.md, target functions resolved through native graph, and existing import/test fixture style. Do not widen unrelated reads.
- Verification: coordinator runs the applicable commands in unit spec.md once after freeze; a new behavior first requires genuine RED before the body. Builders only static checks.
- Do NOT: edit any file not named; modify approvals/events; execute DB or external services; hide failures or label AST success as runtime proof.
- Open questions: none.

### T-913

**Classify**
- Nature: REQUIREMENT
- Priority: 2
- Kind: LOGIC

**Estimate**
- Agent min: 5
- Human ref hours: 0.25
- Tokens (est): 10k
- Agent role: docs
- Model tier: medium
- Wave: 3

**Detail**
- Files to change: `adapters/dot-aidd/scripts/aidd_graphs.py`, `docs/aidd-graph-fresh-query.md`
- Behaviour: Mirror by repo tool with dry/apply/postcheck. Document opt-in and changed/reused counts, uncertainty after failed refresh and no guarantee a miss proves absence. No installed-skill change or common SKILL.md edit. Depends T-912.
- Read first: unit plan.md, target functions resolved through native graph, and existing import/test fixture style. Do not widen unrelated reads.
- Verification: coordinator runs the applicable commands in unit spec.md once after freeze; a new behavior first requires genuine RED before the body. Builders only static checks.
- Do NOT: edit any file not named; modify approvals/events; execute DB or external services; hide failures or label AST success as runtime proof.
- Open questions: none.

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-911 | tests | 8 | 15 | 0.40 |
| 2 | T-912 | builder | 17 | 35 | 0.85 |
| 3 | T-913 | docs | 5 | 10 | 0.25 |

Total agent time (critical path): 30 min
Total tokens (k): 60

## Execution contract

One file owner per lane. Native AIDD graphs first, bounded reads and outputs. Mechanical operations use mapping/dry-run/apply/post-check. Builders run static checks only; coordinator executes RED before each body, then the union of checks once after source freeze. Preserve failures and exact inputs; no invented PASS or consent. No Graphify, database, Docker, external API, installed-skill update or B1SyncLink write. Do NOT modify approval/event logs, relax gates, change unrelated local edits, reinterpret presence as behavior, or reuse a DB result from container identity alone. Final full verification and required perf/audit of the host spec remain applicable at official close.

## Approval gate

Pending owner consent through the official unit review package. This file is not an approval. Historical base approval remains independent and unchanged. No production implementation before the exact unit is approved.

## V3 convergence evidence

T-911/T-912 include the confirmed empty-query guard and its new focused test module. Root-authorized repair was staged, RED7FAIL/5PASS and GREEN12PASS executed, independent review PASS. No additional source group or feature was changed. Execution and diff inputs are included in manifest v3. Fresh official audit and owner V3 seal are pending; no task completion/approval is manufactured here.

## V4 convergence evidence

T-911/T-912 also cover the confirmed pending-state violation under a real active refresh lock, within original FR-373. Separate actual4-case RED/GREEN and independent review are manifest inputs. Main AST and its12-case prior dispatch coverage are unchanged; no broad123/48 run is repeated. Fresh current audit and exact V4 owner seal remain pending.
